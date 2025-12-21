# Plan

Build a ToS-conscious “Company Culture Insights” ingestion pipeline that pulls *publicly accessible* review/interview/compensation signals from Glassdoor/Blind/Levels.fyi via the existing `WebConnector` + `FirecrawlClient`, extracts structured records, caches them in MongoDB, and exposes them via FastAPI + optional Celery refresh jobs.

## Requirements
- Extract (when publicly available): reviews/ratings, interview experiences & questions, compensation ranges, culture keywords + sentiment, WLB indicators, management ratings.
- Respectful outbound behavior: reuse `alfred/core/rate_limit.py` + add per-source policies as needed.
- Caching: Mongo-backed, with refresh controls (`refresh=true`) and TTL/indexing.
- Compliance: default to public pages + official APIs only; do not bypass paywalls/logins/captchas.
- No network calls in unit tests; use fixtures for parsing/extraction.

## Scope
- In:
  - “Integration” via search + crawl of public pages on `glassdoor.com`, `teamblind.com`, `levels.fyi` (and optionally other public sources if needed).
  - Service-layer APIs: `GlassdoorService`, `BlindService`, and a unified `CompanyCultureInsightsService` orchestrator.
  - Mongo persistence + indexes.
  - FastAPI endpoints and (optional) Celery task to refresh.
- Out (initially):
  - Scraping behind auth/paywalls, or using stolen/private APIs.
  - Storing user cookies/sessions.
  - Full historical backfills across many companies (do incremental, company-by-company first).

## Files and entry points
- Existing building blocks to reuse:
  - `apps/alfred/connectors/web_connector.py` (search)
  - `apps/alfred/connectors/firecrawl_connector.py` (scrape/crawl)
  - `apps/alfred/core/rate_limit.py` (throttling)
  - `apps/alfred/services/mongo.py` + `apps/alfred/connectors/mongo_connector.py` (Mongo)
  - `apps/alfred/services/company_researcher.py` (pattern: cache + refresh + sources persisted)
- New (proposed):
  - `apps/alfred/services/glassdoor_service.py`
  - `apps/alfred/services/blind_service.py`
  - `apps/alfred/services/company_culture_insights.py` (or `company_insights.py`)
  - `apps/alfred/schemas/company_insights.py`
  - `apps/alfred/api/company_insights/routes.py`
  - `apps/alfred/tasks/company_insights.py` (optional background refresh)

## Data model / API changes
- Mongo collection (proposed): `company_culture_insights`
  - Key fields:
    - `company` (normalized string), `generated_at`, `sources[]` (url/title/provider/error/raw_markdown_hash)
    - `reviews[]` (rating, summary, pros/cons, date, role/location where available, source_url)
    - `interviews[]` (process summary, difficulty, questions[], outcome, date, role, source_url)
    - `compensation[]` (role, level, base/bonus/equity ranges, currency, geo, source_url)
    - `signals` (culture_keywords[], sentiment, wlb_indicators, management_rating)
    - `meta` (coverage counts, extraction confidence, parsing version)
  - Indexes:
    - `{company: 1, generated_at: -1}`
    - TTL (optional) on `generated_at` or a dedicated `expires_at`
    - Unique-ish dedupe indexes (e.g., hash of `(company, source_url, snippet/date)` for review/interview items)

## Action items
[ ] Research current official access options (Glassdoor partner/API availability; Blind/TeamBlind official endpoints; Levels.fyi usage constraints) and codify as “allowed modes”
[ ] Define Pydantic schemas (`Review`, `InterviewExperience`, `SalaryData`, plus unified response model) and Mongo document shape
[ ] Implement `GlassdoorService` and `BlindService` as *source adapters*:
     - build provider-specific search queries (e.g., `site:glassdoor.com "<company>" reviews`)
     - fetch markdown via Firecrawl
     - extract structured items via deterministic parsing first, LLM fallback second (with strict JSON schema)
[ ] Implement caching + refresh semantics in `CompanyCultureInsightsService` (match `CompanyResearchService` patterns)
[ ] Add rate-limit policies per provider/domain and integrate waits at search + fetch boundaries
[ ] Persist raw source metadata + structured outputs to Mongo; ensure indexes on startup (similar to `DocStorageService.ensure_indexes()`)
[ ] Add FastAPI endpoints:
     - `GET /company/insights?name=...&refresh=false`
     - optional: `GET /company/insights/{company}/latest`
[ ] Add optional Celery task to refresh insights asynchronously (store task result pointer + status)
[ ] Add tests:
     - unit tests for parsing/extraction using saved markdown fixtures
     - integration tests (marked `integration`) that run only when external services are available

## Testing and validation
- Unit: `pytest -q` focusing on schema validation + parsing from fixtures (no network).
- Integration (optional): `pytest -q -m integration` with Mongo + Firecrawl/Searx configured.
- Manual: hit new endpoint with `refresh=false` then `refresh=true` and confirm Mongo writes + caching.

## Risks and edge cases
- ToS/legal/compliance: Glassdoor and Blind may restrict scraping; default must be “public only” and degrade gracefully when blocked.
- Content accessibility: login walls/captchas → expect partial data; record “coverage” + warnings instead of failing.
- Data quality: duplicates, stale posts, missing structured fields; require dedupe + confidence scoring.
- Rate limiting: domains may block aggressive crawling; keep K small and cache aggressively.
- Prompt injection in crawled content: treat as untrusted; use schema-first extraction and sanitize.

## Open questions
- Should we support a user-provided “bring your own access” mode (e.g., paste exported text/links) later, or strictly public-only forever?
- What freshness target do you want (e.g., TTL 7 days vs 30 days), and do you want per-company manual refresh only or scheduled refresh?
- For compensation: is Levels.fyi the primary source, or should we also ingest other public datasets (to reduce reliance on any single site)?

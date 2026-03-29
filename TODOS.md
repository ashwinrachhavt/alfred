# TODOS

## Daily Collision: Cross-Domain Semantic Surfacing
**What:** Scheduled Celery job that takes two zettels from different domains with high embedding similarity and presents them side-by-side.
**Why:** Forces cross-domain thinking. The resonance between "LangGraph fan-out" and "ant colony foraging" is where real insight lives. Unique feature no competitor has.
**How to start:** After Agent Home ships and KB has 50+ zettels across 3+ domains, create a Celery beat task that runs daily. Query Qdrant for high cross-domain similarity pairs. Present in the agent chat as a "Daily Collision" card.
**Effort:** M (human) -> S (CC) | **Priority:** P2
**Depends on:** Agent Home v1 + KB depth (50+ zettels, 3+ domains)
**Added:** 2026-03-28 via /plan-ceo-review

## Add Anthropic Provider to llm_factory.py
**What:** Implement the `anthropic` case in `get_chat_model()` using `langchain-anthropic` (ChatAnthropic). Currently only openai and ollama work.
**Why:** Model selector UI only supports OpenAI + Ollama. Anthropic support enables Claude models for the agent, which are strong at philosophical/analytical tasks.
**How to start:** Add `anthropic` to `LLMProvider` enum in settings.py. Implement the case in `llm_factory.py:get_chat_model()`. Add `ANTHROPIC_API_KEY` to settings.
**Effort:** S (human) -> S (CC) | **Priority:** P3
**Depends on:** Model selector UI shipping
**Added:** 2026-03-28 via /plan-ceo-review

## Unify Retrieval: Qdrant for Both Documents and Zettels
**What:** Index zettel embeddings in Qdrant instead of Postgres JSON + in-process cosine scoring. Give `search_kb` one unified vector search path.
**Why:** Document chunks are in Qdrant but zettel embeddings are in Postgres JSON with in-process scoring. Two retrieval systems means no unified ranking for push retrieval and related cards.
**How to start:** Create a `zettels` collection in Qdrant. Write a migration script to embed and index all existing zettels. Update `search_kb` tool to query both collections with unified scoring. Remove in-process cosine from zettelkasten_service.py.
**Effort:** M (human) -> S (CC) | **Priority:** P1 (blocks push retrieval quality)
**Depends on:** Qdrant Cloud access
**Added:** 2026-03-28 via /plan-ceo-review

## Adaptive Engagement Threshold
**What:** Replace the fixed score-40 auto-capture threshold with one that learns from user behavior (saves-to-zettel rate, manual captures, reading patterns).
**Why:** The fixed threshold of 40 is calibrated by intuition. Fast skimmers may never hit 40; deep readers always exceed it. An adaptive threshold would reduce false positives (noisy captures of content the user didn't care about) and false negatives (missed articles the user engaged with but didn't trigger the threshold).
**How to start:** After v1 ships, collect 2 weeks of engagement score data. Analyze the distribution of scores for pages the user manually saved vs. pages that were auto-captured but never revisited. Use the crossover point as the new threshold.
**Depends on:** Smart Reader v1 being live and generating engagement data in `reading_sessions` table.
**Added:** 2026-03-27 via /plan-eng-review

"""Central dependency providers (FastAPI + tasks).

These helpers keep heavy clients (Mongo, Neo4j, LLM wrappers) process-scoped and
reusable, avoiding per-request connection creation and enabling test-time cache
clearing/overrides.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from alfred.core.settings import settings

if TYPE_CHECKING:
    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.connectors.web_connector import WebConnector
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService
    from alfred.services.company_researcher import (
        CompanyInsightsService,
        CompanyInterviewsService,
        CompanyResearchService,
    )
    from alfred.services.culture_fit_profiles import CultureFitProfileService
    from alfred.services.datastore import DataStoreService
    from alfred.services.doc_storage_pg import DocStorageService
    from alfred.services.extraction_service import ExtractionService
    from alfred.services.graph_service import GraphService
    from alfred.services.interview_prep import InterviewPrepService
    from alfred.services.interview_questions import InterviewQuestionsService
    from alfred.services.job_applications import JobApplicationService
    from alfred.services.llm_service import LLMService
    from alfred.services.system_design import SystemDesignService
    from alfred.services.unified_interview_agent import UnifiedInterviewAgent


@lru_cache(maxsize=1)
def get_datastore_service() -> DataStoreService:
    from alfred.services.datastore import DataStoreService

    return DataStoreService()


@lru_cache(maxsize=1)
def get_graph_service() -> GraphService | None:
    if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
        return None

    from alfred.services.graph_service import GraphService

    return GraphService(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )


@lru_cache(maxsize=1)
def get_llm_service() -> LLMService:
    from alfred.services.llm_service import LLMService

    return LLMService()


@lru_cache(maxsize=1)
def get_extraction_service() -> ExtractionService | None:
    # Avoid wiring the extractor when no features require it.
    needs_extraction = bool(
        settings.enable_ingest_enrichment
        or settings.enable_ingest_classification
        or (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password)
    )
    if not needs_extraction:
        return None

    from alfred.services.extraction_service import ExtractionService

    return ExtractionService(llm_service=get_llm_service())


@lru_cache(maxsize=1)
def get_doc_storage_service() -> DocStorageService:
    from alfred.services.doc_storage_pg import DocStorageService as PgDocStorageService

    return PgDocStorageService(
        session=None,
        graph_service=get_graph_service(),
        extraction_service=get_extraction_service(),
    )


@lru_cache(maxsize=1)
def get_interview_prep_service() -> InterviewPrepService:
    from alfred.services.interview_prep import InterviewPrepService

    return InterviewPrepService()


@lru_cache(maxsize=1)
def get_job_application_service() -> JobApplicationService:
    from alfred.services.job_applications import JobApplicationService

    return JobApplicationService(database=None)


@lru_cache(maxsize=1)
def get_culture_fit_profile_service() -> CultureFitProfileService:
    from alfred.services.culture_fit_profiles import CultureFitProfileService

    return CultureFitProfileService(database=None)


@lru_cache(maxsize=1)
def get_firecrawl_client() -> FirecrawlClient:
    from alfred.connectors.firecrawl_connector import FirecrawlClient

    return FirecrawlClient(base_url=settings.firecrawl_base_url, timeout=settings.firecrawl_timeout)


@lru_cache(maxsize=1)
def get_primary_web_search_connector() -> WebConnector:
    from alfred.connectors.web_connector import WebConnector

    return WebConnector(mode="searx", searx_k=8)


@lru_cache(maxsize=1)
def get_fallback_web_search_connector() -> WebConnector:
    from alfred.connectors.web_connector import WebConnector

    return WebConnector(mode="multi", searx_k=8)


@lru_cache(maxsize=1)
def get_company_research_service() -> CompanyResearchService:
    from alfred.services.company_researcher import CompanyResearchService

    return CompanyResearchService(
        search_results=8,
        primary_search=get_primary_web_search_connector(),
        fallback_search=get_fallback_web_search_connector(),
        firecrawl=get_firecrawl_client(),
        store=get_datastore_service().with_collection(settings.company_research_collection),
    )


@lru_cache(maxsize=1)
def get_company_insights_service() -> CompanyInsightsService:
    from alfred.services.company_researcher import CompanyInsightsService

    return CompanyInsightsService(
        collection_name=settings.company_insights_collection,
        cache_ttl_hours=settings.company_insights_cache_ttl_hours,
    )


@lru_cache(maxsize=1)
def get_outreach_service():
    from alfred.services.outreach_service import OutreachService

    return OutreachService()


@lru_cache(maxsize=1)
def get_company_interviews_service() -> CompanyInterviewsService:
    from alfred.services.company_researcher import CompanyInterviewsService

    return CompanyInterviewsService()


@lru_cache(maxsize=1)
def get_interview_questions_service() -> InterviewQuestionsService:
    from alfred.services.interview_questions import InterviewQuestionsService

    return InterviewQuestionsService(
        primary_search=get_primary_web_search_connector(),
        fallback_search=get_fallback_web_search_connector(),
        firecrawl=get_firecrawl_client(),
    )


@lru_cache(maxsize=1)
def get_unified_interview_agent() -> UnifiedInterviewAgent:
    from alfred.services.unified_interview_agent import UnifiedInterviewAgent

    return UnifiedInterviewAgent(
        questions_service=get_interview_questions_service(),
        company_research_service=get_company_research_service(),
    )


@lru_cache(maxsize=1)
def get_system_design_service() -> SystemDesignService:
    from alfred.services.system_design import SystemDesignService

    return SystemDesignService(
        collection_name=settings.system_design_sessions_collection,
        llm_service=get_llm_service(),
    )


@lru_cache(maxsize=1)
def get_knowledge_agent_service() -> KnowledgeAgentService:
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService

    return KnowledgeAgentService(doc_service=get_doc_storage_service())

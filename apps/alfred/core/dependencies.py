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
    from alfred.agents.interviews_unified.agent import UnifiedInterviewAgent
    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.connectors.web_connector import WebConnector
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService
    from alfred.services.company_research_service import (
        CompanyInsightsService,
        CompanyInterviewsService,
        CompanyResearchService,
    )
    from alfred.services.datastore import DataStoreService
    from alfred.services.doc_storage_pg import DocStorageService
    from alfred.services.extraction_service import ExtractionService
    from alfred.services.graph_service import GraphService
    from alfred.services.interview_service import (
        InterviewPrepService,
        InterviewQuestionsService,
    )
    from alfred.services.job_hunt_service import JobApplicationService, JobHuntService
    from alfred.services.llm_service import LLMService
    from alfred.services.system_design import SystemDesignService
    from alfred.services.web_service import WebService


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
    from alfred.core.redis_client import get_redis_client
    from alfred.services.doc_storage_pg import DocStorageService as PgDocStorageService

    return PgDocStorageService(
        session=None,
        graph_service=get_graph_service(),
        extraction_service=get_extraction_service(),
        redis_client=get_redis_client(),
    )


@lru_cache(maxsize=1)
def get_interview_prep_service() -> InterviewPrepService:
    from alfred.services.interview_service import InterviewPrepService

    return InterviewPrepService()


@lru_cache(maxsize=1)
def get_job_application_service() -> JobApplicationService:
    from alfred.services.job_hunt_service import JobApplicationService

    return JobApplicationService()


@lru_cache(maxsize=1)
def get_firecrawl_client() -> FirecrawlClient:
    from alfred.connectors.firecrawl_connector import FirecrawlClient

    return FirecrawlClient(base_url=settings.firecrawl_base_url, timeout=settings.firecrawl_timeout)


@lru_cache(maxsize=1)
def get_primary_web_search_connector() -> WebConnector:
    from alfred.connectors.web_connector import WebConnector

    return WebConnector(searx_k=8)


@lru_cache(maxsize=1)
def get_fallback_web_search_connector() -> WebConnector:
    # SearxNG-only: keep a single consistent provider for predictable latency/cost.
    return get_primary_web_search_connector()


@lru_cache(maxsize=1)
def get_company_research_service() -> CompanyResearchService:
    from alfred.services.company_research_service import CompanyResearchService

    return CompanyResearchService(
        search_results=8,
        primary_search=get_primary_web_search_connector(),
        fallback_search=get_fallback_web_search_connector(),
        firecrawl=get_firecrawl_client(),
        store=get_datastore_service().with_collection(settings.company_research_collection),
    )


@lru_cache(maxsize=1)
def get_company_insights_service() -> CompanyInsightsService:
    from alfred.services.company_research_service import CompanyInsightsService

    return CompanyInsightsService(
        collection_name=settings.company_insights_collection,
        cache_ttl_hours=settings.company_insights_cache_ttl_hours,
    )


@lru_cache(maxsize=1)
def get_company_interviews_service() -> CompanyInterviewsService:
    from alfred.services.company_research_service import CompanyInterviewsService

    return CompanyInterviewsService()


@lru_cache(maxsize=1)
def get_interview_questions_service() -> InterviewQuestionsService:
    from alfred.services.interview_service import InterviewQuestionsService

    return InterviewQuestionsService(
        primary_search=get_primary_web_search_connector(),
        fallback_search=get_fallback_web_search_connector(),
        firecrawl=get_firecrawl_client(),
    )


@lru_cache(maxsize=1)
def get_thread_service():
    from alfred.services.thread_service import ThreadService

    return ThreadService()


@lru_cache(maxsize=1)
def get_unified_interview_agent() -> UnifiedInterviewAgent:
    from alfred.agents.interviews_unified.agent import UnifiedInterviewAgent

    return UnifiedInterviewAgent(
        questions_service=get_interview_questions_service(),
        company_research_service=get_company_research_service(),
        thread_service=get_thread_service(),
    )


@lru_cache(maxsize=1)
def get_system_design_service() -> SystemDesignService:
    from alfred.services.system_design import SystemDesignService

    return SystemDesignService(
        collection_name=settings.system_design_sessions_collection,
        llm_service=get_llm_service(),
    )


@lru_cache(maxsize=1)
def get_web_service() -> WebService:
    from alfred.services.web_service import WebService

    return WebService(searx_k=10)


@lru_cache(maxsize=1)
def get_job_hunt_service() -> JobHuntService:
    from alfred.services.job_hunt_service import JobHuntService

    return JobHuntService(
        applications=get_job_application_service(),
        company_research=get_company_research_service(),
    )


@lru_cache(maxsize=1)
def get_knowledge_agent_service() -> KnowledgeAgentService:
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService

    return KnowledgeAgentService(doc_service=get_doc_storage_service())


@lru_cache(maxsize=1)
def get_planning_service():
    from alfred.services.planning_service import PlanningService

    return PlanningService(llm_service=get_llm_service())


@lru_cache(maxsize=1)
def get_memory_service():
    from alfred.services.memory_service import MemoryService

    return MemoryService(
        doc_storage=get_doc_storage_service(),
        thread_service=get_thread_service(),
        llm_service=get_llm_service(),
    )


@lru_cache(maxsize=1)
def get_language_service():
    from alfred.services.language_service import LanguageService

    return LanguageService()


@lru_cache(maxsize=1)
def get_text_assist_service():
    from alfred.services.text_assist_service import TextAssistService

    return TextAssistService(llm_service=get_llm_service(), language_service=get_language_service())


@lru_cache(maxsize=1)
def get_summarization_service():
    from alfred.services.summarization_service import SummarizationService

    return SummarizationService(
        doc_storage=get_doc_storage_service(),
        llm_service=get_llm_service(),
        language_service=get_language_service(),
    )

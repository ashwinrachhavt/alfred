"""Central dependency providers (FastAPI + tasks).

These helpers keep heavy clients (Mongo, Neo4j, LLM wrappers) process-scoped and
reusable, avoiding per-request connection creation and enabling test-time cache
clearing/overrides.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from pymongo.database import Database

from alfred.core.settings import settings

if TYPE_CHECKING:
    from alfred.connectors.firecrawl_connector import FirecrawlClient
    from alfred.connectors.mongo_connector import MongoConnector
    from alfred.connectors.web_connector import WebConnector
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService
    from alfred.services.company_insights import CompanyInsightsService
    from alfred.services.company_interviews import CompanyInterviewsService
    from alfred.services.company_researcher import CompanyResearchService
    from alfred.services.culture_fit_profiles import CultureFitProfileService
    from alfred.services.doc_storage_pg import DocStorageService
    from alfred.services.extraction_service import ExtractionService
    from alfred.services.graph_service import GraphService
    from alfred.services.interview_prep import InterviewPrepService
    from alfred.services.interview_questions import InterviewQuestionsService
    from alfred.services.job_applications import JobApplicationService
    from alfred.services.llm_service import LLMService
    from alfred.services.mongo import MongoService
    from alfred.services.panel_interview_simulator import PanelInterviewService
    from alfred.services.system_design import SystemDesignService


@lru_cache(maxsize=1)
def get_mongo_connector() -> MongoConnector:
    from alfred.connectors.mongo_connector import MongoConnector

    return MongoConnector()


@lru_cache(maxsize=1)
def get_mongo_database() -> Database:
    return get_mongo_connector().database


@lru_cache(maxsize=1)
def get_mongo_service() -> MongoService:
    from alfred.services.mongo import MongoService

    return MongoService(connector=get_mongo_connector())


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
    # Prefer Postgres backend; fall back to Mongo if explicitly requested.
    if settings.doc_storage_backend.lower() == "mongo":
        from alfred.services.doc_storage import DocStorageService as MongoDocStorageService

        return MongoDocStorageService(
            database=get_mongo_database(),
            graph_service=get_graph_service(),
            extraction_service=get_extraction_service(),
        )

    from alfred.services.doc_storage_pg import DocStorageService as PgDocStorageService

    return PgDocStorageService(
        session=None,
        graph_service=get_graph_service(),
        extraction_service=get_extraction_service(),
    )


@lru_cache(maxsize=1)
def get_interview_prep_service() -> InterviewPrepService:
    from alfred.services.interview_prep import InterviewPrepService

    return InterviewPrepService(database=get_mongo_database())


@lru_cache(maxsize=1)
def get_job_application_service() -> JobApplicationService:
    from alfred.services.job_applications import JobApplicationService

    return JobApplicationService(database=get_mongo_database())


@lru_cache(maxsize=1)
def get_culture_fit_profile_service() -> CultureFitProfileService:
    from alfred.services.culture_fit_profiles import CultureFitProfileService

    return CultureFitProfileService(database=get_mongo_database())


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

    mongo = get_mongo_service().with_collection(settings.company_research_collection)
    return CompanyResearchService(
        search_results=8,
        primary_search=get_primary_web_search_connector(),
        fallback_search=get_fallback_web_search_connector(),
        firecrawl=get_firecrawl_client(),
        mongo=mongo,
    )


@lru_cache(maxsize=1)
def get_company_insights_service() -> CompanyInsightsService:
    from alfred.services.company_insights import CompanyInsightsService

    return CompanyInsightsService(
        collection_name=settings.company_insights_collection,
        cache_ttl_hours=settings.company_insights_cache_ttl_hours,
    )


@lru_cache(maxsize=1)
def get_company_interviews_service() -> CompanyInterviewsService:
    from alfred.services.company_interviews import CompanyInterviewsService

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
def get_panel_interview_service() -> PanelInterviewService:
    from alfred.services.panel_interview_simulator import PanelInterviewService

    return PanelInterviewService(
        collection_name=settings.panel_interview_sessions_collection,
        company_interviews_service=get_company_interviews_service(),
    )


@lru_cache(maxsize=1)
def get_system_design_service() -> SystemDesignService:
    from alfred.services.system_design import SystemDesignService

    return SystemDesignService(
        database=get_mongo_database(),
        collection_name=settings.system_design_sessions_collection,
        llm_service=get_llm_service(),
    )


@lru_cache(maxsize=1)
def get_knowledge_agent_service() -> KnowledgeAgentService:
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService

    return KnowledgeAgentService(doc_service=get_doc_storage_service())

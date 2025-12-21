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
    from alfred.services.company_researcher import CompanyResearchService
    from alfred.services.doc_storage import DocStorageService
    from alfred.services.extraction_service import ExtractionService
    from alfred.services.graph_service import GraphService
    from alfred.services.llm_service import LLMService
    from alfred.services.mongo import MongoService


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
    from alfred.services.doc_storage import DocStorageService

    return DocStorageService(
        database=get_mongo_database(),
        graph_service=get_graph_service(),
        extraction_service=get_extraction_service(),
    )


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
def get_knowledge_agent_service() -> KnowledgeAgentService:
    from alfred.services.agents.mind_palace_agent import KnowledgeAgentService

    return KnowledgeAgentService(doc_service=get_doc_storage_service())

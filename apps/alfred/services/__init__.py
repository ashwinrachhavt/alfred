"""Service layer package.

Keep imports lazy to avoid initializing heavyweight dependencies at import time
(e.g., LLM clients). Downstream code can still access common symbols from
`alfred.services` thanks to `__getattr__` proxies.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CompanyResearchService",
    "generate_company_research",
    "DataStoreService",
]


def __getattr__(name: str) -> Any:  # PEP 562 lazy attribute access
    if name in {"CompanyResearchService", "generate_company_research"}:
        from .company_researcher import CompanyResearchService, generate_company_research

        return {  # type: ignore[return-value]
            "CompanyResearchService": CompanyResearchService,
            "generate_company_research": generate_company_research,
        }[name]
    if name == "DataStoreService":
        from .datastore import DataStoreService

        return DataStoreService
    raise AttributeError(name)

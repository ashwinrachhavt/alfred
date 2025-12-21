"""Celery task package.

Tasks are imported explicitly here so Celery's autodiscovery can find them via
`app.autodiscover_tasks(["alfred"])` without the API process needing to import
task modules.
"""

from . import company_research as company_research  # noqa: F401
from . import document_enrichment as document_enrichment  # noqa: F401
from . import mind_palace_agent as mind_palace_agent  # noqa: F401

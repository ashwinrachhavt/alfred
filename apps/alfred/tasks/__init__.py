"""Celery task package.

Tasks are imported explicitly here so Celery's autodiscovery can find them via
`app.autodiscover_tasks(["alfred"])` without the API process needing to import
task modules.
"""

from . import deep_research as deep_research
from . import document_concepts as document_concepts
from . import document_enrichment as document_enrichment
from . import document_pipeline as document_pipeline
from . import document_processing as document_processing
from . import document_title_image as document_title_image
from . import learning_concepts as learning_concepts
from . import batch_linking as batch_linking
from . import daily_briefing as daily_briefing
from . import mind_palace_agent as mind_palace_agent

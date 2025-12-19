import logging

from alfred.core.celery import create_celery_app
from alfred.core.logging import setup_logging

# Bytecode disabling is controlled via environment or settings.

# Ensure worker logs are configured consistently.
setup_logging()

# Worker entrypoint (used by docker-compose and local `celery -A ...`).
app = create_celery_app(include_tasks=True)

logging.getLogger(__name__).info("Celery app initialized")

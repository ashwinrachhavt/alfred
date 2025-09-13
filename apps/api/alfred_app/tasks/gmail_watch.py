from __future__ import annotations

import logging
from celery import shared_task
from alfred_app.core.config import settings

logger = logging.getLogger(__name__)


@shared_task(name="alfred_app.tasks.gmail_watch.renew_gmail_watch")
def renew_gmail_watch():
    """Renew Gmail users.watch for all stored accounts. Safe to run daily."""
    if not settings.enable_gmail:
        logger.info("Gmail disabled; skipping watch renewal")
        return {"renewed": 0, "skipped": "gmail_disabled"}
    try:
        from alfred_app.services.gmail import GmailService
    except Exception as e:
        logger.warning("GmailService unavailable: %s", e)
        return {"renewed": 0, "skipped": "deps_missing"}

    if not settings.gcp_pubsub_topic:
        logger.info("GCP_PUBSUB_TOPIC not set; skipping watch renewal")
        return {"renewed": 0, "skipped": "no_topic"}

    count = 0
    for profile_id, email in GmailService.list_all_accounts():
        try:
            GmailService.watch_mailbox(profile_id, email)
            count += 1
        except Exception as e:
            logger.error("Failed to renew watch for %s/%s: %s", profile_id, email, e)
    logger.info("Renewed Gmail watch for %d account(s)", count)
    return {"renewed": count}


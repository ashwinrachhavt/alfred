"""Knowledge push notifications via Redis.

Lightweight notification queue for surfacing newly auto-created zettels
that relate to recent agent conversations. Uses a Redis list with 7-day TTL.
All operations are best-effort: if Redis is unavailable, functions return
empty/zero and log a warning.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from alfred.core.redis_client import get_redis_client

logger = logging.getLogger(__name__)

NOTIFICATIONS_KEY = "alfred:knowledge_notifications"
NOTIFICATION_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days


def push_knowledge_notification(notification: dict) -> bool:
    """Push a notification to the Redis list.

    Returns True if successfully pushed, False otherwise.
    """
    try:
        r = get_redis_client()
        if r is None:
            logger.debug("Redis unavailable, skipping knowledge notification push")
            return False

        # Ensure created_at is set
        if "created_at" not in notification:
            notification["created_at"] = datetime.now(UTC).isoformat()

        r.lpush(NOTIFICATIONS_KEY, json.dumps(notification))
        # Refresh TTL on each push so the list stays alive while active
        r.expire(NOTIFICATIONS_KEY, NOTIFICATION_TTL_SECONDS)
        return True
    except Exception:
        logger.warning("Failed to push knowledge notification", exc_info=True)
        return False


def get_pending_notifications(limit: int = 10) -> list[dict]:
    """Read and consume up to ``limit`` pending notifications.

    Uses LRANGE to read from the end (oldest first) then LTRIM to remove
    consumed entries. Returns a list of notification dicts.
    """
    try:
        r = get_redis_client()
        if r is None:
            return []

        # List is LPUSH'd, so newest is at index 0.
        # Read the newest ``limit`` entries.
        raw_items = r.lrange(NOTIFICATIONS_KEY, 0, limit - 1)
        if not raw_items:
            return []

        # Trim consumed entries
        r.ltrim(NOTIFICATIONS_KEY, len(raw_items), -1)

        notifications = []
        for raw in raw_items:
            try:
                notifications.append(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                logger.warning("Skipping malformed notification: %s", raw)
        return notifications
    except Exception:
        logger.warning("Failed to read knowledge notifications", exc_info=True)
        return []


def get_notification_count() -> int:
    """Return the number of pending notifications."""
    try:
        r = get_redis_client()
        if r is None:
            return 0
        return r.llen(NOTIFICATIONS_KEY) or 0
    except Exception:
        logger.warning("Failed to count knowledge notifications", exc_info=True)
        return 0

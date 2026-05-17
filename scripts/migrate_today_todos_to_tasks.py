"""One-time migration bridge from Today todos to task-system rows.

Usage:
    uv run python scripts/migrate_today_todos_to_tasks.py --dry-run
    uv run python scripts/migrate_today_todos_to_tasks.py --user-id dev-user
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from alfred.core.database import get_session
from alfred.services.tasks.today_migration_service import TodayTodoMigrationService


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate DailyEntryRow(kind='todo') rows into TaskRow.")
    parser.add_argument("--user-id", default=None, help="Optional user id to scope migration.")
    parser.add_argument("--dry-run", action="store_true", help="Report actions without writing tasks.")
    args = parser.parse_args()

    session_iter = get_session()
    session = next(session_iter)
    try:
        result = TodayTodoMigrationService(session).migrate(user_id=args.user_id, dry_run=args.dry_run)
        print(json.dumps(asdict(result), indent=2, default=str))
    finally:
        session.close()


if __name__ == "__main__":
    main()

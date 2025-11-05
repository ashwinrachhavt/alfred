"""Alembic environment configuration."""

from __future__ import annotations

import logging
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

ROOT_DIR = Path(__file__).resolve().parents[3]
APPS_DIR = ROOT_DIR / "apps"
for path in (APPS_DIR, ROOT_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Ensure models are imported so that ``Base.metadata`` is populated
import alfred.core.db_models  # noqa: F401,E402
from alfred.core.config import settings  # noqa: E402
from alfred.core.database import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

logger = logging.getLogger("alembic.env")

target_metadata = Base.metadata


def _get_database_url() -> str:
    url = settings.database_url_sync
    if not url:
        raise RuntimeError("DATABASE_URL is not configured; cannot run migrations")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = _get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    url = _get_database_url()
    config.set_main_option("sqlalchemy.url", url)
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

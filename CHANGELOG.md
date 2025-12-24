# Changelog

All notable changes will be documented in this file. Follow Keep a Changelog style; versions are date-stamped until releases are tagged.

## 2025-12-23

- Fixed interview sync persistence when using the Postgres-backed ProxyCollection by implementing `bulk_write` and `$setOnInsert` handling in the Mongo emulation layer.
- Added outreach persistence to Postgres (`outreach_runs`, `outreach_contacts`) and migrated database accordingly.
- Enabled Alembic autogenerate flow: `scripts/alembic_autogen.sh` and `make alembic-autogen` / `make alembic-upgrade` with `PYTHONPATH=apps` + `DATABASE_URL`.
- Clarified database docs in README for Postgres + autogen usage.

## 2025-12-22

- Contact discovery resiliency: Apollo falls back to mixed_people/search + organization_top_people; caching preserved.

## 2025-12-21

- Initial migrations and schema (research, learning, zettelkasten).

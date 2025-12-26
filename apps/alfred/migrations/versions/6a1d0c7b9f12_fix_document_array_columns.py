"""Ensure document array columns use Postgres ARRAY types.

This repo historically had environments where tables were created via SQLModel
metadata (or older revisions) with JSON/JSONB columns for list fields. Newer
migrations define these as native Postgres arrays.

This migration is written to be safe and idempotent:
- If the column is already the desired array type, it only normalizes defaults/nulls.
- If the column is JSON/JSONB, it converts JSON arrays into Postgres arrays.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import context, op

# revision identifiers, used by Alembic.
revision: str = "6a1d0c7b9f12"
down_revision: Union[str, None] = "3f5a2d8f4cba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # These are Postgres-only conversions; allow sqlite dev envs to skip.
    if context.get_context().dialect.name != "postgresql":
        return

    # docs.tags: json/jsonb -> text[] (and normalize defaults/constraints/index)
    op.execute("DROP INDEX IF EXISTS ix_documents_tags")
    op.execute(
        """
        DO $$
        DECLARE
          t text;
        BEGIN
          SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
            INTO t
          FROM pg_attribute a
          JOIN pg_class c ON a.attrelid = c.oid
          JOIN pg_namespace n ON c.relnamespace = n.oid
          WHERE n.nspname = current_schema()
            AND c.relname = 'documents'
            AND a.attname = 'tags'
            AND a.attnum > 0
            AND NOT a.attisdropped;

          IF t IS NULL THEN
            RETURN;
          END IF;

          IF t IN ('json', 'jsonb') THEN
            EXECUTE 'ALTER TABLE documents ALTER COLUMN tags DROP DEFAULT';
            EXECUTE $q$
              ALTER TABLE documents
              ALTER COLUMN tags TYPE text[]
              USING (
                CASE
                  WHEN tags IS NULL THEN ARRAY[]::text[]
                  WHEN jsonb_typeof(tags::jsonb) = 'array' THEN ARRAY(
                    SELECT jsonb_array_elements_text(tags::jsonb)
                  )
                  ELSE ARRAY[]::text[]
                END
              )
            $q$;
          END IF;

          EXECUTE 'UPDATE documents SET tags = ARRAY[]::text[] WHERE tags IS NULL';
          EXECUTE 'ALTER TABLE documents ALTER COLUMN tags SET DEFAULT ARRAY[]::text[]';
          EXECUTE 'ALTER TABLE documents ALTER COLUMN tags SET NOT NULL';
        END $$;
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_tags ON documents USING gin (tags)")

    # documents.embedding: json/jsonb -> double precision[]
    op.execute(
        """
        DO $$
        DECLARE
          t text;
        BEGIN
          SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
            INTO t
          FROM pg_attribute a
          JOIN pg_class c ON a.attrelid = c.oid
          JOIN pg_namespace n ON c.relnamespace = n.oid
          WHERE n.nspname = current_schema()
            AND c.relname = 'documents'
            AND a.attname = 'embedding'
            AND a.attnum > 0
            AND NOT a.attisdropped;

          IF t IN ('json', 'jsonb') THEN
            EXECUTE $q$
              ALTER TABLE documents
              ALTER COLUMN embedding TYPE double precision[]
              USING (
                CASE
                  WHEN embedding IS NULL THEN NULL
                  WHEN jsonb_typeof(embedding::jsonb) = 'array' THEN ARRAY(
                    SELECT (jsonb_array_elements_text(embedding::jsonb))::double precision
                  )
                  ELSE NULL
                END
              )
            $q$;
          END IF;
        END $$;
        """
    )

    # doc_chunks.embedding: json/jsonb -> double precision[]
    op.execute(
        """
        DO $$
        DECLARE
          t text;
        BEGIN
          SELECT pg_catalog.format_type(a.atttypid, a.atttypmod)
            INTO t
          FROM pg_attribute a
          JOIN pg_class c ON a.attrelid = c.oid
          JOIN pg_namespace n ON c.relnamespace = n.oid
          WHERE n.nspname = current_schema()
            AND c.relname = 'doc_chunks'
            AND a.attname = 'embedding'
            AND a.attnum > 0
            AND NOT a.attisdropped;

          IF t IN ('json', 'jsonb') THEN
            EXECUTE $q$
              ALTER TABLE doc_chunks
              ALTER COLUMN embedding TYPE double precision[]
              USING (
                CASE
                  WHEN embedding IS NULL THEN NULL
                  WHEN jsonb_typeof(embedding::jsonb) = 'array' THEN ARRAY(
                    SELECT (jsonb_array_elements_text(embedding::jsonb))::double precision
                  )
                  ELSE NULL
                END
              )
            $q$;
          END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # Best-effort downgrade back to jsonb for list fields.
    if context.get_context().dialect.name != "postgresql":
        return

    op.execute("DROP INDEX IF EXISTS ix_documents_tags")
    op.execute("ALTER TABLE documents ALTER COLUMN tags DROP DEFAULT")
    op.execute("ALTER TABLE documents ALTER COLUMN tags TYPE jsonb USING to_jsonb(tags)")
    op.execute("ALTER TABLE documents ALTER COLUMN tags SET DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE documents ALTER COLUMN tags SET NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_documents_tags ON documents USING gin (tags)")

    op.execute("ALTER TABLE documents ALTER COLUMN embedding TYPE jsonb USING to_jsonb(embedding)")
    op.execute("ALTER TABLE doc_chunks ALTER COLUMN embedding TYPE jsonb USING to_jsonb(embedding)")

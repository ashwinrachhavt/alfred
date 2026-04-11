#!/bin/bash
# Migrate all data from Neon to local PostgreSQL
# Run this when Neon quota resets
#
# Usage: bash scripts/migrate_neon_to_local.sh

set -e

NEON_URL="postgresql://neondb_owner:npg_ACxpJatYyr51@ep-jolly-union-akj1jhtl-pooler.c-3.us-west-2.aws.neon.tech/neondb?sslmode=require"
LOCAL_URL="postgresql://localhost:5432/alfred"
DUMP_FILE="/tmp/alfred_neon_dump.sql"

echo "1. Testing Neon connection..."
pg_isready -h ep-jolly-union-akj1jhtl-pooler.c-3.us-west-2.aws.neon.tech -U neondb_owner -d neondb || {
    echo "ERROR: Neon is still unreachable. Quota may not have reset yet."
    exit 1
}

echo "2. Dumping Neon data (schema excluded, data only)..."
PGPASSWORD=npg_ACxpJatYyr51 pg_dump \
    -h ep-jolly-union-akj1jhtl-pooler.c-3.us-west-2.aws.neon.tech \
    -U neondb_owner \
    -d neondb \
    --data-only \
    --no-owner \
    --no-privileges \
    --exclude-table=alembic_version \
    -f "$DUMP_FILE"

echo "3. Dump size: $(du -h $DUMP_FILE | cut -f1)"

echo "4. Loading into local PostgreSQL..."
psql -d alfred -f "$DUMP_FILE"

echo "5. Verifying..."
psql -d alfred -c "SELECT 'zettel_cards' as tbl, COUNT(*) FROM zettel_cards UNION ALL SELECT 'documents', COUNT(*) FROM documents UNION ALL SELECT 'thinking_sessions', COUNT(*) FROM thinking_sessions UNION ALL SELECT 'zettel_links', COUNT(*) FROM zettel_links;"

echo "Done! Local DB now has all Neon data."
rm -f "$DUMP_FILE"

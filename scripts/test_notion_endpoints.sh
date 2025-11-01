#!/bin/bash
set -euo pipefail

BASE_URL=${BASE_URL:-"http://127.0.0.1:8080/notion"}
TEST_PAGE_ID=${NOTION_TEST_PAGE_ID:-}
TEST_DB_ID=${NOTION_TEST_DB_ID:-}
TEST_PARENT_ID=${NOTION_TEST_PARENT_ID:-${NOTION_PARENT_PAGE_ID:-}}

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required for this script" >&2
  exit 1
fi

divider() {
  printf '\n%s\n' "=============================="
}

echo "Testing Notion API endpoints against $BASE_URL"

divider
echo "GET /status"
curl -s "$BASE_URL/status" | jq '.'

divider
echo "GET /search?query=test"
curl -s "$BASE_URL/search?query=test" | jq '{results: (.results | length)}'

divider
echo "GET /notes"
curl -s "$BASE_URL/notes" | jq '{results: (.results // [] | length), has_more}'

divider
echo "GET /clients"
curl -s "$BASE_URL/clients" | jq '{results: (.results // [] | length), has_more}'

if [[ -n "$TEST_PAGE_ID" ]]; then
  divider
  echo "GET /page/$TEST_PAGE_ID"
  curl -s "$BASE_URL/page/$TEST_PAGE_ID" | jq '{id: .id, last_edited_time}'

  divider
  echo "GET /page/$TEST_PAGE_ID/children"
  curl -s "$BASE_URL/page/$TEST_PAGE_ID/children" | jq '{results: (.results | length), has_more}'

  divider
  echo "GET /page/$TEST_PAGE_ID/markdown"
  curl -s "$BASE_URL/page/$TEST_PAGE_ID/markdown"
else
  divider
  echo "Skipping page-specific endpoints; set NOTION_TEST_PAGE_ID to enable"
fi

if [[ -n "$TEST_DB_ID" ]]; then
  divider
  echo "GET /database/$TEST_DB_ID/query"
  curl -s "$BASE_URL/database/$TEST_DB_ID/query" | jq '{results: (.results | length), has_more}'

  divider
  echo "POST /sync"
  curl -s -X POST "$BASE_URL/sync" \
    -H "Content-Type: application/json" \
    -d "{\"db_id\": \"$TEST_DB_ID\", \"page_limit\": 5}" | jq '.'
else
  divider
  echo "Skipping database sync; set NOTION_TEST_DB_ID to enable"
fi

if [[ -n "$TEST_PARENT_ID" ]]; then
  divider
  echo "POST /write (create under parent)"
  curl -s -X POST "$BASE_URL/write" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"CLI Smoke Test\", \"md\": \"# hello from script\\n- item 1\\n- item 2\", \"parent_page_id\": \"$TEST_PARENT_ID\"}" | jq '{ok, mode, page_id}'

  divider
  echo "POST /pages (legacy convenience)"
  curl -s "$BASE_URL/pages" --get --data-urlencode "title=CLI Test Page" --data-urlencode "md=Created via /pages"
else
  divider
  echo "Skipping page creation; set NOTION_TEST_PARENT_ID or NOTION_PARENT_PAGE_ID"
fi

if [[ -n "$TEST_PAGE_ID" ]]; then
  divider
  echo "POST /write (append to existing page)"
  curl -s -X POST "$BASE_URL/write" \
    -H "Content-Type: application/json" \
    -d "{\"title\": \"ignored\", \"md\": \"### appended via script\", \"page_id\": \"$TEST_PAGE_ID\"}" | jq '{ok, mode}'
fi

divider
echo "Done."

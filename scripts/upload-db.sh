#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${1:?Usage: upload-db.sh <path-to-sqlite-db>}"
WEBHOOK_URL="${WEBHOOK_URL:?WEBHOOK_URL environment variable must be set}"

if [[ ! -f "$DB_PATH" ]]; then
    echo "Error: file not found: $DB_PATH" >&2
    exit 1
fi

FILENAME="$(basename "$DB_PATH")"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

HTTP_CODE=$(curl -sSf -o /dev/null -w "%{http_code}" \
    -F "payload_json={\"content\":\"db backup: ${FILENAME} (${TIMESTAMP})\"}" \
    -F "files[0]=@${DB_PATH};filename=${FILENAME}" \
    "$WEBHOOK_URL")

echo "Upload complete — HTTP ${HTTP_CODE}"

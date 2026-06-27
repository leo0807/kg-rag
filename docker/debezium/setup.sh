#!/usr/bin/env bash
# Register Debezium PostgreSQL connector and verify CDC topics.
#
# Prerequisites:
#   1. PostgreSQL must have wal_level = logical
#      (set in postgresql.conf or: ALTER SYSTEM SET wal_level = logical; SELECT pg_reload_conf();)
#   2. DB user must have REPLICATION privilege
#   3. Debezium Connect REST must be reachable at CONNECT_URL
#
# Usage:
#   DB_PASSWORD=secret ./docker/debezium/setup.sh
#   CONNECT_URL=http://debezium-connect:8083 DB_PASSWORD=secret ./docker/debezium/setup.sh
set -euo pipefail

CONNECT_URL="${CONNECT_URL:-http://localhost:8083}"
DB_USER="${DB_USER:-aviation}"
DB_PASSWORD="${DB_PASSWORD:?DB_PASSWORD is required}"
DB_NAME="${DB_NAME:-aviation}"
CONNECTOR_NAME="aviation-postgres-cdc"

echo "[1/3] Waiting for Debezium Connect at ${CONNECT_URL} ..."
for i in $(seq 1 30); do
  if curl -sf "${CONNECT_URL}/connectors" > /dev/null 2>&1; then
    echo "      Ready after ${i}s"
    break
  fi
  sleep 2
done
curl -sf "${CONNECT_URL}/connectors" > /dev/null || { echo "ERROR: Debezium Connect not reachable"; exit 1; }

echo "[2/3] Registering connector ${CONNECTOR_NAME} ..."
# Delete existing connector if present (idempotent re-run)
curl -sf -X DELETE "${CONNECT_URL}/connectors/${CONNECTOR_NAME}" 2>/dev/null || true
sleep 1

curl -sf -X POST "${CONNECT_URL}/connectors" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"${CONNECTOR_NAME}\",
    \"config\": {
      \"connector.class\": \"io.debezium.connector.postgresql.PostgresConnector\",
      \"tasks.max\": \"1\",
      \"database.hostname\": \"app-db\",
      \"database.port\": \"5432\",
      \"database.user\": \"${DB_USER}\",
      \"database.password\": \"${DB_PASSWORD}\",
      \"database.dbname\": \"${DB_NAME}\",
      \"topic.prefix\": \"cdc\",
      \"table.include.list\": \"public.conversations,public.query_feedback,public.llm_usage\",
      \"plugin.name\": \"pgoutput\",
      \"publication.autocreate.mode\": \"filtered\",
      \"slot.name\": \"debezium_aviation_slot\",
      \"tombstones.on.delete\": \"false\",
      \"decimal.handling.mode\": \"string\",
      \"time.precision.mode\": \"connect\",
      \"snapshot.mode\": \"initial\"
    }
  }"

echo ""
echo "[3/3] Verifying connector status ..."
sleep 3
STATUS=$(curl -sf "${CONNECT_URL}/connectors/${CONNECTOR_NAME}/status")
echo "$STATUS" | python3 -m json.tool 2>/dev/null || echo "$STATUS"

echo ""
echo "CDC topics will appear at:"
echo "  cdc.public.conversations"
echo "  cdc.public.query_feedback"
echo "  cdc.public.llm_usage"
echo ""
echo "Done. Monitor consumer lag:"
echo "  kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group cdc-clickhouse-sync"

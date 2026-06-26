#!/bin/bash
# setup-internal-tls.sh
# Generates a self-signed CA and per-service TLS certificates for internal
# services: neo4j, postgres, redis, elasticsearch.
#
# Usage:
#   ./scripts/setup-internal-tls.sh [output-dir]
#
# Default output: docker/certs/
#
# Mount example in docker-compose.yml:
#   neo4j:
#     volumes:
#       - ./docker/certs/neo4j.crt:/ssl/neo4j.crt:ro
#       - ./docker/certs/neo4j.key:/ssl/neo4j.key:ro
#       - ./docker/certs/ca.crt:/ssl/ca.crt:ro
#
# After generation, trust the CA on clients:
#   cp docker/certs/ca.crt /usr/local/share/ca-certificates/kg-rag-ca.crt
#   update-ca-certificates

set -euo pipefail

CERTS_DIR="${1:-$(dirname "$0")/../docker/certs}"
DAYS=825   # Max accepted by most browsers/clients for internal certs
COUNTRY="CN"
ORG="KG-RAG"

mkdir -p "$CERTS_DIR"

# Resolve to absolute path after mkdir (handles relative inputs)
CERTS_DIR="$(cd "$CERTS_DIR" && pwd)"

echo "==> Generating internal TLS certificates in: $CERTS_DIR"

# ── Self-signed CA ─────────────────────────────────────────────────────────────
echo "--- CA root certificate ---"
openssl genrsa -out "$CERTS_DIR/ca.key" 4096 2>/dev/null
openssl req -new -x509 -days "$DAYS" \
    -key "$CERTS_DIR/ca.key" \
    -out "$CERTS_DIR/ca.crt" \
    -subj "/C=$COUNTRY/O=$ORG/CN=KG-RAG-Internal-CA"
echo "    ca.key / ca.crt"

# ── Helper: generate service cert signed by the CA ────────────────────────────
gen_cert() {
    local NAME="$1"   # file prefix, e.g. "neo4j"
    local CN="$2"     # Common Name / primary DNS
    local SAN="$3"    # SANs, e.g. "DNS:neo4j,DNS:localhost,IP:127.0.0.1"

    local KEY="$CERTS_DIR/${NAME}.key"
    local CSR="$CERTS_DIR/${NAME}.csr"
    local CRT="$CERTS_DIR/${NAME}.crt"

    openssl genrsa -out "$KEY" 2048 2>/dev/null
    openssl req -new -key "$KEY" -out "$CSR" \
        -subj "/C=$COUNTRY/O=$ORG/CN=$CN"
    openssl x509 -req -days "$DAYS" \
        -in "$CSR" -CA "$CERTS_DIR/ca.crt" -CAkey "$CERTS_DIR/ca.key" \
        -CAcreateserial -out "$CRT" \
        -extfile <(printf "subjectAltName=%s\n" "$SAN") 2>/dev/null
    rm -f "$CSR"
    echo "    ${NAME}.key / ${NAME}.crt  (CN=$CN)"
}

# ── Service certificates ───────────────────────────────────────────────────────
echo "--- Service certificates ---"
gen_cert "neo4j"          "neo4j"          "DNS:neo4j,DNS:localhost,IP:127.0.0.1"
gen_cert "postgres"       "postgres"       "DNS:postgres,DNS:localhost,IP:127.0.0.1"
gen_cert "redis"          "redis"          "DNS:redis,DNS:localhost,IP:127.0.0.1"
gen_cert "elasticsearch"  "elasticsearch"  "DNS:elasticsearch,DNS:localhost,IP:127.0.0.1"

# ── Permissions ───────────────────────────────────────────────────────────────
chmod 600 "$CERTS_DIR"/*.key
chmod 644 "$CERTS_DIR"/*.crt

echo ""
echo "Done. Files written to: $CERTS_DIR"
echo ""
echo "Next steps:"
echo "  1. Mount certs into each service container (see header comments)."
echo "  2. Add 'docker/certs/' to .gitignore — never commit private keys."
echo "  3. Trust the CA on client machines:"
echo "       cp $CERTS_DIR/ca.crt /usr/local/share/ca-certificates/kg-rag-ca.crt"
echo "       update-ca-certificates"

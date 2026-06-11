#!/bin/bash
# I4.2: Generate self-signed TLS certificates for all services.
set -euo pipefail

CERTS_DIR="${1:-./certs}"
DAYS="${2:-3650}"
COUNTRY="CN"
ORG="KG-RAG"

mkdir -p "$CERTS_DIR"
cd "$CERTS_DIR"

echo "=== 生成自签 TLS 证书（有效期 ${DAYS} 天）==="

# ── CA ────────────────────────────────────────────────────────────────────────
echo "--- 生成 CA 根证书 ---"
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days "$DAYS" -key ca.key -out ca.crt \
    -subj "/C=$COUNTRY/O=$ORG/CN=KG-RAG-CA"

# ── 服务证书生成函数 ──────────────────────────────────────────────────────────
gen_cert() {
    local NAME="$1"
    local CN="$2"
    local SAN="${3:-}"

    openssl genrsa -out "${NAME}.key" 2048

    if [ -n "$SAN" ]; then
        openssl req -new -key "${NAME}.key" -out "${NAME}.csr" \
            -subj "/C=$COUNTRY/O=$ORG/CN=$CN" \
            -addext "subjectAltName=$SAN"
        openssl x509 -req -days "$DAYS" \
            -in "${NAME}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
            -out "${NAME}.crt" \
            -extfile <(echo "subjectAltName=$SAN")
    else
        openssl req -new -key "${NAME}.key" -out "${NAME}.csr" \
            -subj "/C=$COUNTRY/O=$ORG/CN=$CN"
        openssl x509 -req -days "$DAYS" \
            -in "${NAME}.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
            -out "${NAME}.crt"
    fi
    rm -f "${NAME}.csr"
    echo "  ✓ $NAME ($CN)"
}

# Nginx / frontend-facing cert
gen_cert "server"   "kg-rag.local" \
    "DNS:kg-rag.local,DNS:localhost,IP:127.0.0.1"

# Internal service certs
gen_cert "postgres"       "postgres"
gen_cert "redis"          "redis"
gen_cert "neo4j"          "neo4j"
gen_cert "elasticsearch"  "elasticsearch"
gen_cert "minio"          "minio"

# Set restrictive permissions on private keys
chmod 600 ./*.key
chmod 644 ./*.crt

echo ""
echo "✓ 证书生成完成: $CERTS_DIR"
echo ""
echo "后续步骤："
echo "  1. 将 ca.crt 导入到客户端信任链"
echo "  2. docker-compose 挂载各服务证书"
echo "  3. 在 .env 中配置各服务的证书路径"

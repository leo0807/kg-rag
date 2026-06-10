#!/bin/bash
# backup.sh — 全量数据备份
# 用法: ./scripts/backup.sh [backup_dir]
#       默认备份到 ./backups/YYYYMMDD_HHMMSS/
set -euo pipefail
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="${1:-./backups}/$TIMESTAMP"
mkdir -p "$BACKUP_DIR"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠️  $*"; }

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
# 自动检测运行环境
if docker ps --format '{{.Names}}' | grep -q 'aviation-backend'; then
  true  # 生产
else
  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.dev.yml"
fi

# ── 1. PostgreSQL ─────────────────────────────────────────────────────
backup_postgres() {
  log "备份 PostgreSQL..."
  $COMPOSE exec -T app-db pg_dump -U aviation aviation 2>/dev/null \
    | gzip > "$BACKUP_DIR/postgres.sql.gz" \
    && ok "postgres.sql.gz ($(du -sh "$BACKUP_DIR/postgres.sql.gz" | cut -f1))" \
    || warn "PostgreSQL 备份失败"
}

# ── 2. Neo4j ──────────────────────────────────────────────────────────
backup_neo4j() {
  log "备份 Neo4j..."
  mkdir -p "$BACKUP_DIR/neo4j"
  docker run --rm \
    --volumes-from aviation-neo4j:ro \
    -v "$BACKUP_DIR/neo4j:/backup" \
    alpine tar czf /backup/neo4j_data.tar.gz -C /data . 2>/dev/null \
    && ok "neo4j_data.tar.gz" \
    || warn "Neo4j 备份失败（容器未运行？）"
}

# ── 3. MinIO 文件存储 ─────────────────────────────────────────────────
backup_minio() {
  log "备份 MinIO..."
  docker run --rm \
    --volumes-from aviation-minio:ro \
    -v "$BACKUP_DIR:/backup" \
    alpine tar czf /backup/minio.tar.gz -C /minio_data . 2>/dev/null \
    && ok "minio.tar.gz" \
    || warn "MinIO 备份失败（容器未运行？）"
}

# ── 4. etcd（Milvus 元数据）──────────────────────────────────────────
backup_etcd() {
  log "备份 etcd..."
  $COMPOSE exec -T etcd etcdctl snapshot save /tmp/etcd_snap.db \
    --endpoints=localhost:2379 2>/dev/null \
    && docker cp aviation-etcd:/tmp/etcd_snap.db "$BACKUP_DIR/etcd.db" \
    && ok "etcd.db" \
    || warn "etcd 备份失败"
}

# ── 5. 配置文件 ───────────────────────────────────────────────────────
backup_config() {
  log "备份配置..."
  [[ -f .env ]]                && cp .env "$BACKUP_DIR/env.backup"
  cp docker-compose*.yml "$BACKUP_DIR/" 2>/dev/null || true
  ok "配置文件"
}

# ── 6. 清单 ──────────────────────────────────────────────────────────
write_manifest() {
  local size
  size=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)
  local git_rev="unknown"
  git rev-parse --short HEAD 2>/dev/null && git_rev=$(git rev-parse --short HEAD)
  cat > "$BACKUP_DIR/manifest.json" <<EOF
{
  "timestamp": "$(date -Iseconds)",
  "git_rev": "$git_rev",
  "backup_dir": "$BACKUP_DIR",
  "total_size": "$size",
  "components": ["postgres", "neo4j", "minio", "etcd", "config"]
}
EOF
  ok "manifest.json"
}

# ── 主流程 ────────────────────────────────────────────────────────────
echo "=== KG-RAG 备份开始 ==="
backup_postgres
backup_neo4j
backup_minio
backup_etcd
backup_config
write_manifest

echo ""
echo "✅ 备份完成: $BACKUP_DIR"
echo "   大小: $(du -sh "$BACKUP_DIR" | cut -f1)"

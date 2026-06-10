#!/bin/bash
# restore.sh — 从备份目录恢复数据
# 用法: ./scripts/restore.sh <备份目录>
#   例: ./scripts/restore.sh ./backups/20240101_020000
set -euo pipefail

BACKUP_DIR="${1:-}"
[[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]] && {
  echo "用法: $0 <备份目录>"
  echo "可用备份:"
  ls -1d ./backups/*/ 2>/dev/null || echo "  （无备份）"
  exit 1
}

cd "$(dirname "$0")/.."
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

log()  { echo "[$(date '+%H:%M:%S')] $*"; }
ok()   { echo "  ✓ $*"; }
warn() { echo "  ⚠️  $*" >&2; }

echo "=== KG-RAG 数据恢复 ==="
echo "来源: $BACKUP_DIR"
if [[ -f "$BACKUP_DIR/manifest.json" ]]; then
  echo "备份时间: $(grep timestamp "$BACKUP_DIR/manifest.json" | grep -o '[0-9T:+-]*' | head -1)"
fi
read -r -p "确认从此备份恢复？输入 'yes': " confirm
[[ "$confirm" != "yes" ]] && echo "已取消" && exit 0

# ── 停止应用层（保留数据库）────────────────────────────────────────
log "停止应用服务..."
$COMPOSE stop backend celery-worker frontend 2>/dev/null || true

# ── PostgreSQL ──────────────────────────────────────────────────────
if [[ -f "$BACKUP_DIR/postgres.sql.gz" ]]; then
  log "恢复 PostgreSQL..."
  $COMPOSE up -d app-db
  sleep 5
  gunzip -c "$BACKUP_DIR/postgres.sql.gz" \
    | $COMPOSE exec -T app-db psql -U aviation -d postgres -c "DROP DATABASE IF EXISTS aviation;" 2>/dev/null || true
  gunzip -c "$BACKUP_DIR/postgres.sql.gz" \
    | $COMPOSE exec -T app-db psql -U aviation \
    && ok "PostgreSQL 恢复完成" \
    || warn "PostgreSQL 恢复失败"
fi

# ── Neo4j ────────────────────────────────────────────────────────────
if [[ -f "$BACKUP_DIR/neo4j/neo4j_data.tar.gz" ]]; then
  log "恢复 Neo4j（需停止容器）..."
  $COMPOSE stop neo4j
  docker run --rm \
    --volumes-from aviation-neo4j \
    -v "$BACKUP_DIR/neo4j:/backup:ro" \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/neo4j_data.tar.gz -C /data" \
    && ok "Neo4j 数据已恢复" \
    || warn "Neo4j 恢复失败"
  $COMPOSE start neo4j
fi

# ── MinIO ────────────────────────────────────────────────────────────
if [[ -f "$BACKUP_DIR/minio.tar.gz" ]]; then
  log "恢复 MinIO..."
  $COMPOSE stop minio
  docker run --rm \
    --volumes-from aviation-minio \
    -v "$BACKUP_DIR:/backup:ro" \
    alpine sh -c "rm -rf /minio_data/* && tar xzf /backup/minio.tar.gz -C /minio_data" \
    && ok "MinIO 数据已恢复" \
    || warn "MinIO 恢复失败"
  $COMPOSE start minio
fi

# ── 重启应用 ──────────────────────────────────────────────────────────
log "重启应用服务..."
$COMPOSE up -d backend
sleep 15
if curl -sf http://localhost:8000/api/health >/dev/null; then
  ok "后端已就绪"
else
  warn "后端启动异常，请查看日志：docker compose logs --tail=50 backend"
fi

echo ""
echo "✅ 恢复完成"

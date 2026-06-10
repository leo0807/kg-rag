#!/bin/bash
# upgrade.sh — 升级到最新版本（git pull + 重建镜像 + 滚动重启）
set -euo pipefail
ENV=${1:-prod}
cd "$(dirname "$0")/.."

case "$ENV" in
  dev)  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.dev.yml" ;;
  prod) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml" ;;
  *)    echo "用法: $0 [dev|prod]"; exit 1 ;;
esac

log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "拉取最新代码..."
git pull --ff-only

log "备份当前数据..."
./scripts/backup.sh || log "⚠️  备份失败，继续升级（请手动备份）"

log "重建镜像..."
$COMPOSE build --parallel backend frontend

log "滚动重启后端..."
$COMPOSE up -d --no-deps backend

log "等待后端就绪..."
for i in $(seq 1 30); do
  curl -sf http://localhost:8000/api/health >/dev/null && break
  sleep 5
done

$COMPOSE up -d --no-deps frontend

log "升级完成"
echo "✓ 版本: $(git rev-parse --short HEAD)"

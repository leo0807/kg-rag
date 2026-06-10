#!/bin/bash
# restart.sh — 重启指定服务
# 用法: ./scripts/restart.sh [service] [env]
#   ./scripts/restart.sh backend dev
#   ./scripts/restart.sh          → 重启所有
set -euo pipefail
SERVICE=${1:-}
ENV=${2:-dev}
cd "$(dirname "$0")/.."

case "$ENV" in
  dev)  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.dev.yml" ;;
  prod) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml" ;;
  *)    COMPOSE="docker compose -f docker-compose.yml" ;;
esac

if [[ -n "$SERVICE" ]]; then
  echo "重启 $SERVICE..."
  $COMPOSE restart "$SERVICE"
else
  echo "重启所有服务..."
  $COMPOSE restart
fi
echo "✓ 完成"

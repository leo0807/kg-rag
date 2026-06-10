#!/bin/bash
# logs.sh — 查看服务日志
# 用法: ./scripts/logs.sh [service] [env] [--tail=N]
#   ./scripts/logs.sh backend dev --tail=200
#   ./scripts/logs.sh              → 所有服务最近100行
set -euo pipefail
SERVICE=${1:-}
ENV=${2:-dev}
TAIL=${3:---tail=100}
cd "$(dirname "$0")/.."

case "$ENV" in
  dev)  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.dev.yml" ;;
  prod) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml" ;;
  test) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.test.yml" ;;
  *)    COMPOSE="docker compose -f docker-compose.yml" ;;
esac

if [[ -n "$SERVICE" ]]; then
  $COMPOSE logs "$TAIL" -f "$SERVICE"
else
  $COMPOSE logs "$TAIL" -f
fi

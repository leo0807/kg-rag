#!/bin/bash
# stop.sh — 停止服务
set -euo pipefail
ENV=${1:-dev}
cd "$(dirname "$0")/.."

case "$ENV" in
  dev)  COMPOSE="docker compose -f docker-compose.yml -f docker-compose.dev.yml" ;;
  prod) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml" ;;
  test) COMPOSE="docker compose -f docker-compose.yml -f docker-compose.test.yml" ;;
  all)  COMPOSE="docker compose -f docker-compose.yml" ;;
  *)    echo "用法: $0 [dev|prod|test|all]"; exit 1 ;;
esac

echo "停止 $ENV 服务..."
$COMPOSE stop
echo "✓ 已停止"

#!/bin/bash
set -e

docker compose -f docker-compose.yml \
  -f docker-compose.prod.yml up -d --build

echo ""
echo "生产环境已启动"

#!/bin/bash
set -e

docker compose -f docker-compose.yml \
  -f docker-compose.dev.yml up -d

echo ""
echo "基础服务已启动，请手动启动 backend 和 frontend"
echo ""
echo "  backend:  cd backend && uvicorn src.main:app --reload"
echo "  frontend: cd frontend && npm run dev"

#!/bin/bash
# clean.sh — 清理开发环境数据（危险操作！）
set -euo pipefail
cd "$(dirname "$0")/.."

echo "⚠️  警告：此操作将删除所有 Docker 卷（数据库数据、向量数据等）"
echo "仅用于开发环境重置！"
read -r -p "输入 'yes' 确认: " confirm
[[ "$confirm" != "yes" ]] && echo "已取消" && exit 0

echo "停止所有服务..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans

echo "清理构建缓存..."
docker system prune -f

echo "✓ 环境已清理，可重新运行 ./scripts/deploy.sh dev --init"

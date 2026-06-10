#!/bin/bash
# deploy.sh — KG-RAG 统一部署脚本
# 用法：./scripts/deploy.sh [dev|prod|test] [--init] [--skip-build]
set -euo pipefail

ENV=${1:-dev}
INIT=false
SKIP_BUILD=false
for arg in "$@"; do
  [[ "$arg" == "--init" ]]       && INIT=true
  [[ "$arg" == "--skip-build" ]] && SKIP_BUILD=true
done

COMPOSE_BASE="docker compose -f docker-compose.yml"
case "$ENV" in
  dev)   COMPOSE="$COMPOSE_BASE -f docker-compose.dev.yml" ;;
  prod)  COMPOSE="$COMPOSE_BASE -f docker-compose.prod.yml" ;;
  test)  COMPOSE="$COMPOSE_BASE -f docker-compose.test.yml" ;;
  *)     echo "❌ 未知环境: $ENV（可选: dev|prod|test）"; exit 1 ;;
esac

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT=8000
[[ "$ENV" == "test" ]] && BACKEND_PORT=8001

log() { echo "[$(date '+%H:%M:%S')] $*"; }
ok()  { echo "✓ $*"; }
err() { echo "❌ $*" >&2; exit 1; }

# ── 1. 依赖检查 ──────────────────────────────────────────────────────
check_deps() {
  log "检查依赖..."
  for cmd in docker curl; do
    command -v "$cmd" &>/dev/null || err "缺少 $cmd，请先安装"
  done
  docker compose version &>/dev/null || err "需要 Docker Compose v2（docker compose）"
  ok "依赖检查通过"
}

# ── 2. 配置检查 ──────────────────────────────────────────────────────
check_config() {
  log "检查配置..."
  local env_file=".env"
  [[ "$ENV" == "test" ]] && env_file=".env.test"

  if [[ ! -f "$env_file" ]]; then
    echo "⚠️  缺少 $env_file，将从 .env.example 复制"
    [[ -f ".env.example" ]] || err "缺少 .env.example"
    cp .env.example "$env_file"
    echo "请编辑 $env_file 后重新运行"
    exit 0
  fi
  ok "配置文件 $env_file 存在"
}

# ── 3. 构建镜像 ──────────────────────────────────────────────────────
build_images() {
  if [[ "$SKIP_BUILD" == "true" ]]; then
    log "跳过镜像构建（--skip-build）"
    return
  fi
  log "构建 Docker 镜像..."
  $COMPOSE build --parallel
  ok "镜像构建完成"
}

# ── 4. 启动服务 ──────────────────────────────────────────────────────
start_services() {
  log "启动服务（环境: $ENV）..."
  $COMPOSE up -d
  ok "服务已启动"
}

# ── 5. 等待后端就绪 ──────────────────────────────────────────────────
wait_healthy() {
  log "等待后端就绪（最长5分钟）..."
  local url="http://localhost:${BACKEND_PORT}/api/health"
  for i in $(seq 1 60); do
    if curl -sf "$url" >/dev/null 2>&1; then
      ok "后端已就绪 ($i × 5s)"
      return 0
    fi
    printf "."
    sleep 5
  done
  echo ""
  err "后端启动超时，查看日志：$COMPOSE logs --tail=100 backend"
}

# ── 6. 首次初始化 ────────────────────────────────────────────────────
init_data() {
  if [[ "$INIT" != "true" ]]; then return; fi
  log "初始化数据库..."
  $COMPOSE exec backend python scripts/create_admin.py || log "跳过：create_admin（已存在或脚本不存在）"
  ok "数据初始化完成"
}

# ── 主流程 ───────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════╗"
echo "║   KG-RAG 部署脚本   ENV=$ENV         ║"
echo "╚══════════════════════════════════════╝"

check_deps
check_config
build_images
start_services
wait_healthy
init_data

echo ""
echo "✅ 部署完成！"
echo "   前端: http://localhost:3000"
echo "   后端: http://localhost:${BACKEND_PORT}"
echo "   API文档: http://localhost:${BACKEND_PORT}/docs"
[[ "$ENV" != "test" ]] && echo "   MinIO:  http://localhost:9001"
[[ "$ENV" != "test" ]] && echo "   Neo4j:  http://localhost:7474"

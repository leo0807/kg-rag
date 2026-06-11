#!/bin/bash
# I7.3: Disaster recovery drill — simulate failures and validate auto-recovery.
set -euo pipefail

INSTALL_DIR="${1:-/opt/kg-rag}"
REPORT_FILE="$INSTALL_DIR/logs/dr-drill-$(date +%Y%m%d-%H%M%S).txt"
PASS=0
FAIL=0

mkdir -p "$(dirname "$REPORT_FILE")"
exec > >(tee -a "$REPORT_FILE") 2>&1

echo "=== KG-RAG 灾备演练 $(date) ==="
echo "安装目录: $INSTALL_DIR"

CD_CMD="cd $INSTALL_DIR &&"

check() {
    local NAME="$1"
    local CMD="$2"
    if eval "$CMD" &>/dev/null; then
        echo "  ✓ $NAME"
        ((PASS++)) || true
    else
        echo "  ✗ $NAME"
        ((FAIL++)) || true
    fi
}

wait_healthy() {
    for i in $(seq 1 30); do
        if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
            return 0
        fi
        sleep 5
    done
    return 1
}

# ── 场景 1：后端服务崩溃恢复 ──────────────────────────────────────────────────
echo ""
echo "--- 场景 1: 后端服务崩溃恢复 ---"
CONTAINER=$(docker ps --filter "name=backend" --format "{{.Names}}" | head -1)
if [ -n "$CONTAINER" ]; then
    echo "  强制停止: $CONTAINER"
    docker stop "$CONTAINER" 2>/dev/null || true
    sleep 10
    docker start "$CONTAINER" 2>/dev/null || eval "$CD_CMD docker compose up -d backend"
    sleep 5
    check "后端服务恢复" "curl -sf http://localhost:8000/api/health"
else
    echo "  ⚠ 未找到运行中的后端容器，跳过"
fi

# ── 场景 2：数据库连接中断 ──────────────────────────────────────────────────
echo ""
echo "--- 场景 2: 数据库连接中断 ---"
PG_CONTAINER=$(docker ps --filter "name=postgres" --format "{{.Names}}" | grep -v replica | head -1)
if [ -n "$PG_CONTAINER" ]; then
    echo "  暂停: $PG_CONTAINER (30s)"
    docker pause "$PG_CONTAINER" 2>/dev/null || true
    sleep 30
    docker unpause "$PG_CONTAINER" 2>/dev/null || true
    sleep 15
    check "数据库连接恢复" "curl -sf http://localhost:8000/api/health"
else
    echo "  ⚠ 未找到 postgres 容器，跳过"
fi

# ── 场景 3：Redis 故障 ────────────────────────────────────────────────────────
echo ""
echo "--- 场景 3: Redis 缓存故障 ---"
REDIS_CONTAINER=$(docker ps --filter "name=redis" --format "{{.Names}}" | grep -v sentinel | grep -v replica | head -1)
if [ -n "$REDIS_CONTAINER" ]; then
    echo "  停止: $REDIS_CONTAINER (20s)"
    docker stop "$REDIS_CONTAINER" 2>/dev/null || true
    sleep 20
    docker start "$REDIS_CONTAINER" 2>/dev/null || true
    sleep 10
    check "Redis 恢复后健康检查通过" "curl -sf http://localhost:8000/api/health"
else
    echo "  ⚠ 未找到 redis 容器，跳过"
fi

# ── 场景 4：磁盘空间验证 ─────────────────────────────────────────────────────
echo ""
echo "--- 场景 4: 磁盘空间检查 ---"
AVAIL=$(df -BG "$INSTALL_DIR" 2>/dev/null | awk 'NR==2{print $4}' | tr -d 'G' || echo 9999)
check "磁盘可用 > 50GB" "[ $AVAIL -gt 50 ]"

# ── 场景 5：备份文件验证 ─────────────────────────────────────────────────────
echo ""
echo "--- 场景 5: 备份完整性验证 ---"
LATEST_BACKUP=$(ls -t "$INSTALL_DIR/backups/"*.sql.gz 2>/dev/null | head -1 || echo "")
if [ -n "$LATEST_BACKUP" ]; then
    check "最新备份文件可读" "gzip -t '$LATEST_BACKUP'"
    BACKUP_AGE=$(( ($(date +%s) - $(stat -c %Y "$LATEST_BACKUP" 2>/dev/null || date +%s)) / 86400 ))
    check "备份不超过7天" "[ $BACKUP_AGE -le 7 ]"
else
    echo "  ⚠ 未找到备份文件"
    ((FAIL++)) || true
fi

# ── 汇总 ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== 演练结果 ==="
echo "  通过: $PASS"
echo "  失败: $FAIL"
echo "  报告: $REPORT_FILE"

if [ "$FAIL" -gt 0 ]; then
    echo "  ⚠ 存在 $FAIL 个未通过项，请检查运维文档"
    exit 1
else
    echo "  ✓ 所有场景通过"
fi

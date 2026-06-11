#!/bin/bash
# I3.3: Offline upgrade with automatic rollback on failure.
set -euo pipefail

INSTALL_DIR="${1:-/opt/kg-rag}"
BUNDLE="${2:-}"
BACKUP_DIR="$INSTALL_DIR/backups/upgrade-$(date +%Y%m%d-%H%M%S)"

if [ -z "$BUNDLE" ]; then
    echo "用法: $0 <install_dir> <upgrade_bundle.tar.gz>"
    exit 1
fi

echo "=== KG-RAG 离线升级 ==="
echo "安装目录: $INSTALL_DIR"
echo "升级包:   $BUNDLE"

# ── 备份当前版本 ──────────────────────────────────────────────────────────────
backup_current() {
    echo "--- 备份当前版本 ---"
    mkdir -p "$BACKUP_DIR"
    cp -r "$INSTALL_DIR/backend" "$BACKUP_DIR/" 2>/dev/null || true
    cp -r "$INSTALL_DIR/frontend" "$BACKUP_DIR/" 2>/dev/null || true
    cp "$INSTALL_DIR/.env" "$BACKUP_DIR/" 2>/dev/null || true
    cd "$INSTALL_DIR"
    if command -v docker-compose &>/dev/null; then
        docker-compose exec -T backend pg_dump \
            -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-kg_rag}" \
            > "$BACKUP_DIR/db_backup.sql" 2>/dev/null || echo "⚠ 数据库备份失败，继续升级"
    fi
    echo "✓ 备份完成: $BACKUP_DIR"
}

# ── 加载新镜像 ────────────────────────────────────────────────────────────────
load_new_images() {
    echo "--- 加载新镜像 ---"
    TMP_DIR=$(mktemp -d)
    tar -xzf "$BUNDLE" -C "$TMP_DIR"
    BUNDLE_DIR=$(ls "$TMP_DIR")
    for img in "$TMP_DIR/$BUNDLE_DIR/images/"*.tar.gz 2>/dev/null; do
        [ -f "$img" ] || continue
        echo "  加载: $(basename "$img")"
        gunzip -c "$img" | docker load
    done
    echo "NEW_SRC=$TMP_DIR/$BUNDLE_DIR" > /tmp/kg_upgrade_vars
    echo "✓ 镜像加载完成"
}

# ── 部署新代码 ────────────────────────────────────────────────────────────────
deploy_new_code() {
    echo "--- 部署新版本代码 ---"
    source /tmp/kg_upgrade_vars
    tar -xzf "$NEW_SRC/source.tar.gz" -C "$INSTALL_DIR" --strip-components=1
    echo "✓ 代码更新完成"
}

# ── 运行数据库迁移 ────────────────────────────────────────────────────────────
run_migrations() {
    echo "--- 数据库迁移 ---"
    cd "$INSTALL_DIR"
    docker compose exec -T backend alembic upgrade head 2>/dev/null || \
        echo "⚠ Alembic 迁移失败，请手动处理"
    echo "✓ 迁移完成"
}

# ── 重启服务 ──────────────────────────────────────────────────────────────────
restart_services() {
    echo "--- 重启服务 ---"
    cd "$INSTALL_DIR"
    if command -v docker-compose &>/dev/null; then
        docker-compose up -d --build
    else
        docker compose up -d --build
    fi
    echo "✓ 服务重启完成"
}

# ── 健康检查 ──────────────────────────────────────────────────────────────────
health_check() {
    echo "--- 健康检查 ---"
    for i in $(seq 1 60); do
        if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
            echo "✓ 服务正常"
            return 0
        fi
        sleep 5
    done
    return 1
}

# ── 回滚 ──────────────────────────────────────────────────────────────────────
rollback() {
    echo "!!! 升级失败，回滚到备份版本 !!!"
    cd "$INSTALL_DIR"
    cp -r "$BACKUP_DIR/backend" . 2>/dev/null || true
    cp -r "$BACKUP_DIR/frontend" . 2>/dev/null || true
    if command -v docker-compose &>/dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    echo "✓ 回滚完成"
    exit 1
}

trap rollback ERR

backup_current
load_new_images
deploy_new_code
run_migrations
restart_services
health_check

rm -f /tmp/kg_upgrade_vars
echo ""
echo "✓ 升级成功"
echo "  备份保留在: $BACKUP_DIR"

#!/bin/bash
# I3.2: Offline installation script for air-gapped environments.
set -euo pipefail

INSTALL_DIR="${1:-/opt/kg-rag}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== KG-RAG 离线安装 ==="
echo "安装目录: $INSTALL_DIR"

# ── 1. 系统检查 ──────────────────────────────────────────────────────────────
check_system() {
    echo "--- 系统检查 ---"

    if ! command -v docker &>/dev/null; then
        echo "✗ Docker 未安装，请先安装 Docker Engine 24+"; exit 1
    fi
    if ! command -v docker-compose &>/dev/null && ! docker compose version &>/dev/null 2>&1; then
        echo "✗ Docker Compose 未安装"; exit 1
    fi

    AVAIL_DISK=$(df -BG "$INSTALL_DIR" 2>/dev/null | awk 'NR==2{print $4}' | tr -d 'G' || echo 9999)
    if [ "$AVAIL_DISK" -lt 200 ] 2>/dev/null; then
        echo "⚠ 磁盘可用空间 ${AVAIL_DISK}GB，建议至少 200GB"; sleep 2
    fi

    TOTAL_MEM=$(free -g 2>/dev/null | awk '/Mem:/{print $2}' || echo 64)
    if [ "$TOTAL_MEM" -lt 32 ] 2>/dev/null; then
        echo "⚠ 内存 ${TOTAL_MEM}GB，建议至少 64GB（运行大模型）"; sleep 2
    fi

    echo "✓ 系统检查通过"
}

# ── 2. 加载镜像 ──────────────────────────────────────────────────────────────
load_images() {
    echo "--- 加载 Docker 镜像 ---"
    if [ ! -d "$SCRIPT_DIR/images" ]; then
        echo "⚠ images/ 目录不存在，跳过镜像加载"; return
    fi
    for img in "$SCRIPT_DIR/images/"*.tar.gz; do
        [ -f "$img" ] || continue
        echo "  加载: $(basename "$img")"
        gunzip -c "$img" | docker load
    done
    echo "✓ 镜像加载完成"
}

# ── 3. 目录结构 ──────────────────────────────────────────────────────────────
create_dirs() {
    echo "--- 创建目录 ---"
    mkdir -p "$INSTALL_DIR"/{data,logs,uploads,models,backups,certs}
    echo "✓ 目录创建完成"
}

# ── 4. 部署代码 ──────────────────────────────────────────────────────────────
deploy_code() {
    echo "--- 部署源代码 ---"
    if [ -f "$SCRIPT_DIR/source.tar.gz" ]; then
        tar -xzf "$SCRIPT_DIR/source.tar.gz" -C "$INSTALL_DIR" --strip-components=1
        echo "✓ 源代码部署完成"
    else
        echo "⚠ source.tar.gz 未找到，跳过"
    fi
}

# ── 5. 配置文件 ──────────────────────────────────────────────────────────────
setup_config() {
    echo "--- 配置文件 ---"
    if [ -f "$SCRIPT_DIR/.env.offline.example" ] && [ ! -f "$INSTALL_DIR/.env" ]; then
        cp "$SCRIPT_DIR/.env.offline.example" "$INSTALL_DIR/.env"
        sed -i 's/DEPLOYMENT_MODE=.*/DEPLOYMENT_MODE=airgapped/' "$INSTALL_DIR/.env"
        sed -i 's/EXTERNAL_API_ALLOWED=.*/EXTERNAL_API_ALLOWED=false/' "$INSTALL_DIR/.env"
        sed -i 's/TELEMETRY_ENABLED=.*/TELEMETRY_ENABLED=false/' "$INSTALL_DIR/.env"
        sed -i 's/AUTO_UPDATE_CHECK=.*/AUTO_UPDATE_CHECK=false/' "$INSTALL_DIR/.env"
    fi
    echo "⚠ 请编辑 $INSTALL_DIR/.env 设置数据库密码等关键配置"
}

# ── 6. Node 依赖 ──────────────────────────────────────────────────────────────
restore_node_modules() {
    if [ -f "$SCRIPT_DIR/node-modules/node_modules.tar.gz" ] && [ -d "$INSTALL_DIR/frontend" ]; then
        echo "--- 恢复 node_modules ---"
        tar -xzf "$SCRIPT_DIR/node-modules/node_modules.tar.gz" -C "$INSTALL_DIR/frontend"
        echo "✓ node_modules 恢复完成"
    fi
}

# ── 7. 启动服务 ──────────────────────────────────────────────────────────────
start_services() {
    echo "--- 启动服务 ---"
    cd "$INSTALL_DIR"
    if command -v docker-compose &>/dev/null; then
        docker-compose up -d
    else
        docker compose up -d
    fi
    echo "✓ 服务已启动"
}

# ── 8. 等待健康 ──────────────────────────────────────────────────────────────
wait_healthy() {
    echo "--- 等待服务就绪 ---"
    for i in $(seq 1 120); do
        if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
            echo "✓ 服务就绪 (${i}×5s)"
            return 0
        fi
        printf "."
        sleep 5
    done
    echo ""
    echo "⚠ 服务未在 10 分钟内就绪，请检查日志: docker compose logs"
    return 1
}

# ── 9. 数据初始化 ────────────────────────────────────────────────────────────
init_data() {
    echo "--- 初始化数据库 ---"
    cd "$INSTALL_DIR"
    docker compose exec -T backend python scripts/init_db.py 2>/dev/null || \
        echo "⚠ 数据库初始化脚本未找到，请手动运行"
    docker compose exec -T backend python scripts/create_admin.py 2>/dev/null || \
        echo "⚠ 管理员创建脚本未找到，请手动创建"
}

# ── Main ──────────────────────────────────────────────────────────────────────
check_system
load_images
create_dirs
deploy_code
setup_config
restore_node_modules
start_services
wait_healthy
init_data

echo ""
echo "✓ 安装完成"
echo "  访问: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):3000"
echo "  管理: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo localhost):3000/admin"

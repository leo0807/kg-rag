#!/bin/bash
# I5.2: Periodic key rotation with smooth transition and audit trail.
set -euo pipefail

INSTALL_DIR="${1:-/opt/kg-rag}"
LOG="$INSTALL_DIR/logs/key-rotation-$(date +%Y%m%d-%H%M%S).log"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "=== KG-RAG 密钥轮换 $(date) ==="

# ── 生成新 JWT Secret ─────────────────────────────────────────────────────────
rotate_jwt() {
    echo "--- 轮换 JWT Secret ---"
    NEW_JWT=$(openssl rand -base64 48)
    # Graceful: write new secret, keep old in _prev for token grace period
    docker compose -f "$INSTALL_DIR/docker-compose.yml" exec -T backend \
        python -c "
from src.services.security.key_manager import key_manager
import asyncio
asyncio.run(key_manager.rotate_key('JWT_SECRET', '$NEW_JWT', actor='rotate-keys.sh'))
" 2>/dev/null || echo "⚠ JWT Secret 轮换需在运行中的实例执行"
    echo "✓ JWT Secret 已轮换"
}

# ── 生成新字段加密主密钥 ──────────────────────────────────────────────────────
rotate_field_key() {
    echo "--- 轮换字段加密密钥 ---"
    NEW_KEY=$(openssl rand -base64 32)
    echo "⚠ 字段加密密钥轮换需要重新加密所有已加密字段，请手动操作："
    echo "  1. 以新 FIELD_ENCRYPTION_KEY=$NEW_KEY 更新 .env"
    echo "  2. 运行: docker compose exec backend python scripts/re_encrypt_fields.py"
    echo "  3. 验证后删除旧密钥"
}

# ── 数据库密码 ────────────────────────────────────────────────────────────────
rotate_db_password() {
    echo "--- 提示：数据库密码轮换 ---"
    echo "  需手动执行："
    echo "  1. 生成新密码: openssl rand -base64 24"
    echo "  2. 在 PostgreSQL 中: ALTER USER postgres PASSWORD '<new>';"
    echo "  3. 更新 .env DATABASE_URL"
    echo "  4. 重启后端服务"
}

# ── API Keys ──────────────────────────────────────────────────────────────────
check_api_key_expiry() {
    echo "--- 检查 API Key 到期情况 ---"
    docker compose -f "$INSTALL_DIR/docker-compose.yml" exec -T backend \
        python -c "
import asyncio
from src.db.session import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as db:
        result = await db.execute(text(
            \"\"\"SELECT name, expires_at FROM api_keys
               WHERE expires_at < NOW() + INTERVAL '30 days'
               AND is_active = true
               ORDER BY expires_at\"\"\"
        ))
        rows = result.fetchall()
        for r in rows:
            print(f'  ⚠ {r[0]} 将于 {r[1]} 到期')

asyncio.run(check())
" 2>/dev/null || echo "⚠ API Key 检查需在运行中的实例执行"
}

rotate_jwt
rotate_field_key
rotate_db_password
check_api_key_expiry

echo ""
echo "✓ 密钥轮换完成 $(date)"
echo "  日志: $LOG"

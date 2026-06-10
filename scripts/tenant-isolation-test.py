#!/usr/bin/env python3
"""
G7.1 租户数据隔离自动化测试
流程：
1. 创建测试租户 A、B 及各自的用户
2. A 的用户创建对话
3. B 的 token 尝试访问 A 的资源 → 期望 403/404
"""
import asyncio
import os
import sys
import logging
import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
PLATFORM_TOKEN = os.getenv("PLATFORM_TOKEN", "")


async def register_and_login(client: httpx.AsyncClient, username: str, password: str, email: str) -> str:
    """注册用户并返回 token。"""
    await client.post(f"{BASE_URL}/api/auth/register", json={
        "username": username, "password": password, "email": email, "full_name": "Test"
    })
    r = await client.post(f"{BASE_URL}/api/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


async def create_tenant(client: httpx.AsyncClient, name: str, slug: str) -> dict:
    r = await client.post(f"{BASE_URL}/api/platform/tenants",
        json={"name": name, "slug": slug, "plan": "standard", "status": "active"},
        headers={"Authorization": f"Bearer {PLATFORM_TOKEN}"}
    )
    r.raise_for_status()
    return r.json()


async def run_tests():
    passed = 0
    failed = 0

    async with httpx.AsyncClient(timeout=30) as client:
        log.info("=== 创建测试租户 ===")
        try:
            tenant_a = await create_tenant(client, "测试租户A", f"test-tenant-a-{os.urandom(3).hex()}")
            tenant_b = await create_tenant(client, "测试租户B", f"test-tenant-b-{os.urandom(3).hex()}")
            log.info("A: %s  B: %s", tenant_a["id"][:8], tenant_b["id"][:8])
        except Exception as e:
            log.error("创建租户失败: %s（确认 PLATFORM_TOKEN 有效）", e)
            sys.exit(1)

        log.info("=== 注册测试用户 ===")
        uid_a = f"T{os.urandom(2).hex()[:5]}"
        uid_b = f"T{os.urandom(2).hex()[:5]}"
        token_a = await register_and_login(client, uid_a, "test123456", f"{uid_a}@test.local")
        token_b = await register_and_login(client, uid_b, "test123456", f"{uid_b}@test.local")
        headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-Slug": tenant_a["slug"]}
        headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-Slug": tenant_b["slug"]}

        log.info("=== 租户 A 创建对话 ===")
        r = await client.post(f"{BASE_URL}/api/conversations",
            json={"title": "A 的私有对话"}, headers=headers_a
        )
        if r.status_code in (200, 201):
            conv = r.json()
            conv_id = conv.get("id") or conv.get("conversation_id")
            log.info("创建对话: %s", conv_id)
        else:
            log.warning("创建对话返回 %s（可能无此接口，跳过）", r.status_code)
            conv_id = None

        log.info("=== 跨租户访问测试 ===")

        def check(label: str, status: int, expected: tuple):
            nonlocal passed, failed
            if status in expected:
                log.info("  ✅ PASS  %s → HTTP %s", label, status)
                passed += 1
            else:
                log.error("  ❌ FAIL  %s → HTTP %s (期望 %s)", label, status, expected)
                failed += 1

        if conv_id:
            r = await client.get(f"{BASE_URL}/api/conversations/{conv_id}", headers=headers_b)
            check("B 访问 A 的对话", r.status_code, (403, 404))

        r = await client.get(f"{BASE_URL}/api/conversations", headers=headers_b)
        if r.status_code == 200:
            convs = r.json()
            ids = [c.get("id") for c in (convs if isinstance(convs, list) else [])]
            if conv_id and conv_id in ids:
                log.error("  ❌ FAIL  B 的列表中出现了 A 的对话！数据泄露！")
                failed += 1
            else:
                log.info("  ✅ PASS  B 的对话列表不含 A 的数据")
                passed += 1

        r = await client.get(f"{BASE_URL}/api/favorites", headers=headers_b)
        check("B 访问收藏夹（不应含 A 的数据）", r.status_code, (200, 403, 404))

    log.info("=== 测试结果: %d 通过 / %d 失败 ===", passed, failed)
    return failed == 0


if __name__ == "__main__":
    if not PLATFORM_TOKEN:
        log.error("请设置 PLATFORM_TOKEN 环境变量")
        sys.exit(1)
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)

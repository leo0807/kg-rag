#!/usr/bin/env python3
"""
check-env.py — 环境变量配置校验
用法: python scripts/check-env.py [.env文件路径]
"""
import os
import re
import sys
from pathlib import Path


def load_env(path: str) -> dict[str, str]:
    env: dict[str, str] = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


REQUIRED: list[tuple[str, str]] = [
    ("JWT_SECRET",              "JWT 签名密钥"),
    ("DATABASE_URL",            "PostgreSQL 连接串"),
    ("NEO4J_URI",               "Neo4j 连接地址"),
    ("NEO4J_PASSWORD",          "Neo4j 密码"),
    ("MILVUS_HOST",             "Milvus 主机"),
    ("STORAGE_ENDPOINT",        "MinIO 端点"),
]

RECOMMENDED: list[tuple[str, str]] = [
    ("LLM_API_KEY",             "LLM API 密钥（API模式必填）"),
    ("LANGFUSE_PUBLIC_KEY",     "Langfuse 追踪密钥"),
    ("DINGTALK_WEBHOOK",        "钉钉告警 Webhook"),
]

WEAK_DEFAULTS = {"changeme", "password", "secret", "test", "dev", "aviation123",
                 "aviation-jwt-secret-change-in-production", "minioadmin"}

ok_count = warn_count = err_count = 0


def ok(msg: str)   -> None: global ok_count;   ok_count += 1;   print(f"  ✓ {msg}")
def warn(msg: str) -> None: global warn_count; warn_count += 1; print(f"  ⚠️  {msg}")
def err(msg: str)  -> None: global err_count;  err_count += 1;  print(f"  ❌ {msg}")


def check_required(env: dict) -> None:
    print("\n[必填项]")
    for key, desc in REQUIRED:
        val = env.get(key, "")
        if not val:
            err(f"{key} 未配置 — {desc}")
        elif val in WEAK_DEFAULTS:
            warn(f"{key} 使用默认值，生产环境请修改")
        else:
            ok(f"{key}")


def check_recommended(env: dict) -> None:
    print("\n[推荐配置]")
    for key, desc in RECOMMENDED:
        val = env.get(key, "")
        if not val:
            warn(f"{key} 未配置 — {desc}")
        else:
            ok(f"{key}")


def check_jwt_strength(env: dict) -> None:
    print("\n[安全检查]")
    secret = env.get("JWT_SECRET", "")
    if len(secret) < 32:
        warn("JWT_SECRET 长度不足 32 位，建议使用 openssl rand -base64 48 生成")
    elif secret in WEAK_DEFAULTS:
        err("JWT_SECRET 使用弱默认值，生产环境存在安全风险")
    else:
        ok("JWT_SECRET 强度合格")


def check_database_url(env: dict) -> None:
    url = env.get("DATABASE_URL", "")
    if url and "asyncpg" not in url and "postgresql" in url:
        warn("DATABASE_URL 建议使用 postgresql+asyncpg:// 驱动")
    elif url and "asyncpg" in url:
        ok("DATABASE_URL 驱动正确（asyncpg）")


def check_app_env(env: dict) -> None:
    app_env = env.get("APP_ENV", "development")
    debug   = env.get("DEBUG", "false").lower()
    if app_env == "production" and debug == "true":
        warn("生产环境（APP_ENV=production）不应开启 DEBUG=true")
    else:
        ok(f"APP_ENV={app_env} DEBUG={debug}")


def main() -> int:
    env_file = sys.argv[1] if len(sys.argv) > 1 else ".env"
    if not Path(env_file).exists():
        print(f"❌ 找不到 {env_file}，请先复制 .env.example")
        return 1

    print(f"=== KG-RAG 环境配置校验：{env_file} ===")
    env = load_env(env_file)
    os.environ.update(env)  # allow connectivity checks that read env

    check_required(env)
    check_recommended(env)
    check_jwt_strength(env)
    check_database_url(env)
    check_app_env(env)

    print(f"\n结果: ✓{ok_count} ⚠️{warn_count} ❌{err_count}")
    if err_count > 0:
        print("请修复上述错误后重新部署")
        return 1
    elif warn_count > 0:
        print("存在警告，建议处理后部署到生产环境")
        return 0
    else:
        print("配置检查通过！")
        return 0


if __name__ == "__main__":
    sys.exit(main())

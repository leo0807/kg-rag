FROM python:3.12-slim AS base

WORKDIR /app

# 系统依赖（pdfplumber + LibreOffice .doc 转换）
RUN apt-get update && apt-get install -y \
    gcc g++ curl \
    libreoffice libreoffice-writer \
    fonts-wqy-zenhei fonts-wqy-microhei fonts-noto-cjk \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# ── 依赖层（pip 缓存独立，requirements 不变就不重建）────────────────
FROM base AS deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── 应用层 ──────────────────────────────────────────────────────────
FROM deps AS app

# 非 root 用户（UID 1001 避免与常见系统账号冲突）
RUN groupadd -g 1001 appgroup && useradd -u 1001 -g appgroup -s /bin/sh appuser

COPY src/ ./src/
COPY scripts/ ./scripts/

RUN mkdir -p uploads uploads/snapshots logs \
    && chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" \
    || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

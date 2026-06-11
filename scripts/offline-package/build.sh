#!/bin/bash
# I3.1: Build an offline installation bundle for air-gapped deployments.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUTPUT_DIR="kg-rag-offline-$(date +%Y%m%d)"

echo "=== KG-RAG 离线包构建 ==="
echo "输出目录: $OUTPUT_DIR"

mkdir -p "$OUTPUT_DIR/images"
mkdir -p "$OUTPUT_DIR/python-wheels"
mkdir -p "$OUTPUT_DIR/node-modules"
mkdir -p "$OUTPUT_DIR/models"

# 1. Docker 镜像
IMAGES=(
    "neo4j:5.20"
    "milvusdb/milvus:v2.4.0"
    "postgres:15"
    "redis:7-alpine"
    "minio/minio:latest"
    "elasticsearch:8.7.0"
    "etcd:v3.5.5"
    "ollama/ollama:latest"
    "node:20-alpine"
    "python:3.12-slim"
    "nginx:1.25-alpine"
)

echo "--- 拉取并保存 Docker 镜像 ---"
for img in "${IMAGES[@]}"; do
    echo "  拉取: $img"
    docker pull "$img"
    FNAME=$(echo "$img" | tr '/:' '__')
    docker save "$img" | gzip > "$OUTPUT_DIR/images/${FNAME}.tar.gz"
    echo "  保存: $OUTPUT_DIR/images/${FNAME}.tar.gz"
done

# 2. Python wheels
echo "--- 下载 Python 依赖 ---"
pip download -r "$REPO_ROOT/backend/requirements.txt" \
    --dest "$OUTPUT_DIR/python-wheels" \
    --platform manylinux2014_x86_64 \
    --python-version 312 \
    --only-binary=:all: 2>/dev/null || \
pip download -r "$REPO_ROOT/backend/requirements.txt" \
    --dest "$OUTPUT_DIR/python-wheels"

# 3. Node 依赖 tarball
echo "--- 打包 Node 依赖 ---"
(cd "$REPO_ROOT/frontend" && npm ci --prefer-offline 2>/dev/null || true)
if [ -d "$REPO_ROOT/frontend/node_modules" ]; then
    tar -czf "$OUTPUT_DIR/node-modules/node_modules.tar.gz" \
        -C "$REPO_ROOT/frontend" node_modules
fi

# 4. 源代码快照
echo "--- 打包源代码 ---"
(cd "$REPO_ROOT" && git archive HEAD --format=tar.gz -o "$OUTPUT_DIR/source.tar.gz")

# 5. 部署脚本 & 配置模板
cp "$SCRIPT_DIR/install.sh" "$OUTPUT_DIR/"
[ -f "$REPO_ROOT/.env.example" ] && cp "$REPO_ROOT/.env.example" "$OUTPUT_DIR/.env.offline.example"
[ -d "$REPO_ROOT/docs" ] && cp -r "$REPO_ROOT/docs" "$OUTPUT_DIR/"

# 6. 模型说明
cat > "$OUTPUT_DIR/models/README.txt" <<'MODEL_README'
模型文件下载说明
================
以下模型需要单独下载（体积较大，未打包在离线包中）：

1. QA 模型（Qwen2.5-72B）：
   ollama pull qwen2.5:72b

2. Embedding 模型（BGE-M3）：
   从 HuggingFace 下载: BAAI/bge-m3

3. Reranker（BGE-Reranker-large）：
   从 HuggingFace 下载: BAAI/bge-reranker-large

4. 视觉模型（Qwen2-VL-7B）：
   ollama pull qwen2-vl:7b

将模型文件放置于 /opt/kg-rag/models/ 目录下。
MODEL_README

# 7. 打最终压缩包
echo "--- 打包完成 ---"
tar -czf "${OUTPUT_DIR}.tar.gz" "$OUTPUT_DIR"
rm -rf "$OUTPUT_DIR"

echo ""
echo "✓ 离线包构建完成: ${OUTPUT_DIR}.tar.gz"
echo "  大小: $(du -sh "${OUTPUT_DIR}.tar.gz" | cut -f1)"

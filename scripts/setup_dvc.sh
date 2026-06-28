#!/bin/bash
# DVC — data version control setup for ML assets.
# Tracks GNN training snapshots, RAGAS eval datasets, finetune data.
# Storage: MinIO / S3 compatible remote.
#
# Usage: ./scripts/setup_dvc.sh [minio_endpoint] [bucket]
#   Default: http://localhost:9000, kg-rag-dvc
set -euo pipefail

MINIO_ENDPOINT="${1:-http://localhost:9000}"
BUCKET="${2:-kg-rag-dvc}"
MINIO_ACCESS="${MINIO_ACCESS_KEY:-minioadmin}"
MINIO_SECRET="${MINIO_SECRET_KEY:-minioadmin}"

cd "$(dirname "$0")/.."

echo "Setting up DVC with MinIO remote..."

# Install DVC with S3 support
pip install "dvc[s3]" --quiet

# Initialize DVC if not already
if [ ! -d ".dvc" ]; then
    dvc init
    echo "DVC initialized"
fi

# Configure MinIO as remote
dvc remote add --default -f minio "s3://${BUCKET}/dvc"
dvc remote modify minio endpointurl "${MINIO_ENDPOINT}"
dvc remote modify minio access_key_id "${MINIO_ACCESS}"
dvc remote modify minio secret_access_key "${MINIO_SECRET}"

# Track ML assets
mkdir -p models scripts/finetune_data scripts/eval/results

# Add tracking for model directory
if [ -d "models" ]; then
    dvc add models/
    echo "Tracking models/ directory"
fi

# Add tracking for finetune data
if [ -d "scripts/finetune_data" ]; then
    dvc add scripts/finetune_data/
    echo "Tracking scripts/finetune_data/"
fi

# Add tracking for RAGAS results
if [ -d "scripts/eval/results" ]; then
    dvc add scripts/eval/results/
    echo "Tracking scripts/eval/results/"
fi

# Add .dvc files to git
git add .dvc/ .dvcignore models.dvc scripts/ 2>/dev/null || true

echo ""
echo "✓ DVC configured with MinIO remote: ${MINIO_ENDPOINT}/${BUCKET}"
echo "  To push data: dvc push"
echo "  To pull data: dvc pull"
echo "  To reproduce pipeline: dvc repro"

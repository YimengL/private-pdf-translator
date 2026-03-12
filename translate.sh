#!/bin/bash
set -euo pipefail

PIPELINE_DIR="$HOME/git/private-pdf-translator"

# 1. Validate input
if [ -z "${1:-}" ]; then
    echo "❌ Usage: translate <path-to-pdf>"
    exit 1
fi

if [ ! -f "$1" ]; then
    echo "❌ File not found: $1"
    exit 1
fi

# 2. Start Docker Desktop if not running
if ! docker info > /dev/null 2>&1; then
    echo "🐳 Starting Docker Desktop..."
    open -a Docker
    echo "⏳ Waiting for Docker to be ready (60s max)..."
    for i in $(seq 1 12); do
        sleep 5
        docker info > /dev/null 2>&1 && break
        if [ "$i" -eq 12 ]; then
            echo "❌ Docker did not start in time"
            exit 1
        fi
    done
fi

# 3. Retrieve API key from Mac Keychain
API_KEY=$(security find-generic-password \
    -a "$USER" -s "anthropic-german-mail" -w 2>/dev/null || true)
if [ -z "$API_KEY" ]; then
    echo "❌ API key not found in Keychain. Run:"
    echo "   security add-generic-password -a \"\$USER\" -s \"anthropic-german-mail\" -w \"sk-ant-xxxxx\""
    exit 1
fi

# 4. Derive output path
INPUT_DIR=$(cd "$(dirname "$1")" && pwd)
INPUT_FILE=$(basename "$1")
OUTPUT_FILE="${INPUT_FILE/ori_/pro_}"

# 5. Run pipeline
echo "🚀 Starting pipeline: $INPUT_FILE → $OUTPUT_FILE"
docker compose -f "$PIPELINE_DIR/docker-compose.yml" run --rm \
    -e ANTHROPIC_API_KEY="$API_KEY" \
    -v "$INPUT_DIR:/data" \
    pipeline python3 pipeline.py "/data/$INPUT_FILE" "/data/$OUTPUT_FILE"

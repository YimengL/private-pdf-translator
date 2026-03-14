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

# 2. Build image if not present
if ! docker image inspect german-mail-pipeline > /dev/null 2>&1; then
    echo "🔨 Building Docker image (first time only)..."
    docker build -t german-mail-pipeline "$PIPELINE_DIR"
fi

# 3. Start Docker Desktop if not running
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

# 4. Retrieve API key from Mac Keychain
API_KEY=$(security find-generic-password \
    -a "$USER" -s "anthropic-german-mail" -w 2>/dev/null || true)
if [ -z "$API_KEY" ]; then
    echo "❌ API key not found in Keychain. Run:"
    echo "   security add-generic-password -a \"\$USER\" -s \"anthropic-german-mail\" -w \"sk-ant-xxxxx\""
    exit 1
fi

# 5. Derive output path
INPUT_DIR=$(cd "$(dirname "$1")" && pwd)
INPUT_FILE=$(basename "$1")

if [[ "$INPUT_FILE" == proc_* ]]; then
    echo "❌ File already processed: $INPUT_FILE"
    exit 1
fi

OUTPUT_FILE="proc_${INPUT_FILE#ori_}"

# 6. Run pipeline
echo "🚀 Starting pipeline: $INPUT_FILE → $OUTPUT_FILE"
docker run --rm \
    -e ANTHROPIC_API_KEY="$API_KEY" \
    -e OLLAMA_HOST=http://host.docker.internal:11434 \
    -v "$INPUT_DIR:/data" \
    german-mail-pipeline \
    python3 pipeline.py "/data/$INPUT_FILE" "/data/$OUTPUT_FILE"

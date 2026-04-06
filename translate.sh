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

# 2. Build image if missing or source files have changed
_needs_build() {
    if ! docker image inspect german-mail-pipeline > /dev/null 2>&1; then
        return 0
    fi
    IMAGE_TS=$(docker inspect german-mail-pipeline --format='{{.Created}}' | xargs -I{} date -j -f "%Y-%m-%dT%H:%M:%S" "{}" "+%s" 2>/dev/null)
    LATEST=$(stat -f "%m" "$PIPELINE_DIR/Dockerfile" "$PIPELINE_DIR/pyproject.toml" "$PIPELINE_DIR/pipeline.py" | sort -n | tail -1)
    [ "$LATEST" -gt "$IMAGE_TS" ]
}
if _needs_build; then
    echo "🔨 Building Docker image..."
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

# 4. Resolve secrets — env var → Doppler (if available) → Mac Keychain
if [ -z "${ANTHROPIC_API_KEY:-}" ] && command -v doppler &>/dev/null; then
    ANTHROPIC_API_KEY=$(doppler secrets get ANTHROPIC_API_KEY --plain 2>/dev/null || true)
fi
ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-$(security find-generic-password -a "$USER" -s "anthropic-german-mail" -w 2>/dev/null || true)}"

if [ -z "${DEEPL_API_KEY:-}" ] && command -v doppler &>/dev/null; then
    DEEPL_API_KEY=$(doppler secrets get DEEPL_API_KEY --plain 2>/dev/null || true)
fi
DEEPL_API_KEY="${DEEPL_API_KEY:-$(security find-generic-password -a "$USER" -s "deepl-german-mail" -w 2>/dev/null || true)}"

if [ -z "$ANTHROPIC_API_KEY" ] || [ -z "$DEEPL_API_KEY" ]; then
    echo "❌ API keys not found. Set via env var, Doppler, or Mac Keychain."
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
    -e ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY" \
    -e DEEPL_API_KEY="$DEEPL_API_KEY" \
    --mount "type=bind,source=${INPUT_DIR},target=/data" \
    german-mail-pipeline \
    "/data/$INPUT_FILE"

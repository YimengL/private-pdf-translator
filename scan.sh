#!/bin/bash
set -euo pipefail

PIPELINE_DIR="$HOME/git/private-pdf-translator"
IMAGE="german-mail-pipeline"

# 1. Validate input and folders
if [ -z "${1:-}" ] || [ ! -f "$1" ]; then
    echo "❌ Usage: scan.sh <path-to-pdf>"
    exit 1
fi
if [ -z "${SCAN_RAW_ROOT:-}" ] || [ -z "${SCAN_MASKED_ROOT:-}" ]; then
    echo "❌ Set SCAN_RAW_ROOT and SCAN_MASKED_ROOT (two separate folders)."
    exit 1
fi
RAW_ROOT=$(cd "$SCAN_RAW_ROOT" && pwd -P)
mkdir -p "$SCAN_MASKED_ROOT"
MASKED_ROOT=$(cd "$SCAN_MASKED_ROOT" && pwd -P)
INPUT="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
case "$INPUT" in
    "$RAW_ROOT"/*) ;;
    *) echo "❌ File is not inside SCAN_RAW_ROOT: $RAW_ROOT"; exit 1 ;;
esac
case "$MASKED_ROOT/" in
    "$RAW_ROOT"/*) echo "❌ Masked folder must not be inside the raw folder."; exit 1 ;;
esac
REL="${INPUT#"$RAW_ROOT"/}"

# 2. Docker: must be running; build image if missing or source changed
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Start Docker Desktop and try again."
    exit 1
fi
_needs_build() {
    if ! docker image inspect "$IMAGE" > /dev/null 2>&1; then
        return 0
    fi
    IMAGE_TS=$(docker inspect "$IMAGE" --format='{{.Created}}' | xargs -I{} date -j -f "%Y-%m-%dT%H:%M:%S" "{}" "+%s" 2>/dev/null)
    LATEST=$(stat -f "%m" "$PIPELINE_DIR"/{Dockerfile,pyproject.toml,pipeline.py,local_pipeline.py,local_redact.py} | sort -n | tail -1)
    [ "$LATEST" -gt "$IMAGE_TS" ]
}
if _needs_build; then
    echo "🔨 Building Docker image..."
    docker build -t "$IMAGE" "$PIPELINE_DIR"
fi

# 3. Run the local pipeline: no network, raw folder read-only
echo "🔒 Scanning (no network): $REL"
CODE=0
docker run --rm --network none --entrypoint python3 \
    --mount "type=bind,source=${RAW_ROOT},target=/raw,readonly" \
    --mount "type=bind,source=${MASKED_ROOT},target=/masked" \
    "$IMAGE" local_pipeline.py "/raw/$REL" --raw-root /raw --masked-root /masked || CODE=$?

case "$CODE" in
    0) echo "✅ Gate passed. Masked file: $MASKED_ROOT/${REL%.*}.txt" ;;
    2) echo "⛔ Gate blocked: sensitive items still visible. Nothing was written." ;;
    *) echo "❌ Scan failed (exit $CODE). Nothing was written." ;;
esac
exit "$CODE"

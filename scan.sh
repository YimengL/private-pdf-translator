#!/bin/bash
set -euo pipefail

PIPELINE_DIR="$HOME/git/private-pdf-translator"
IMAGE="german-mail-pipeline"

# 1. Validate input and folders
if [ -z "${1:-}" ] || [ ! -f "$1" ]; then
    echo "❌ Usage: scan.sh <path-to-pdf>"
    exit 1
fi
if [ -z "${SCAN_ROOT:-}" ]; then
    echo "❌ Set SCAN_ROOT (folder with original/, masked/ and index/)."
    exit 1
fi
for d in original masked index; do
    [ -d "$SCAN_ROOT/$d" ] || { echo "❌ Missing folder: $SCAN_ROOT/$d"; exit 1; }
done
RAW_ROOT=$(cd "$SCAN_ROOT/original" && pwd -P)
MASKED_ROOT=$(cd "$SCAN_ROOT/masked" && pwd -P)
INDEX_ROOT=$(cd "$SCAN_ROOT/index" && pwd -P)
INPUT="$(cd "$(dirname "$1")" && pwd -P)/$(basename "$1")"
case "$INPUT" in
    "$RAW_ROOT"/*) ;;
    *) echo "❌ File is not inside $RAW_ROOT"; exit 1 ;;
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
    --mount "type=bind,source=${INDEX_ROOT},target=/index" \
    "$IMAGE" local_pipeline.py "/raw/$REL" --raw-root /raw --masked-root /masked || CODE=$?

case "$CODE" in
    0) echo "✅ Gate passed. Masked file: $MASKED_ROOT/${REL%.*}.txt" ;;
    2) echo "⛔ Gate blocked: sensitive items still visible. Nothing was written." ;;
    *) echo "❌ Scan failed (exit $CODE). Nothing was written." ;;
esac
exit "$CODE"

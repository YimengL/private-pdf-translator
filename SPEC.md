# German Mail Pipeline — SPEC.md

## Instructions for Claude Code
- Use plan mode throughout
- Show me the full plan first and wait for my approval
- Show each file diff one by one and wait for my approval before moving to next file
- Explain WHY for key decisions
- Do not proceed to the next file without my explicit approval

---

## Goal
Process weekly German physical mail (scanned PDF) into a single output PDF containing:
- Original scanned pages
- Local AI full translation (private)
- Claude AI translation + bilingual summary + action points + inconsistency report

---

## Entry Point
```bash
translate ~/path/to/ori_2024_001_mail.pdf
```
- `translate` is a shell script located at `/usr/local/bin/translate`
- Works from any folder on Mac
- Input file always prefixed with `ori_`
- Output file always prefixed with `pro_`, saved in same folder as input

**Example:**
```
Input:  ~/mails/2024_001_mail/ori_2024_001_mail.pdf
Output: ~/mails/2024_001_mail/pro_2024_001_mail.pdf
```

---

## Tech Stack
- Mac M5, Docker Desktop
- Tesseract (OCR, German language pack)
- Microsoft Presidio (PII redaction, runs locally)
- translategemma via Ollama (local translation, no cloud)
- Claude API — model: claude-sonnet-4-6 (translation + summary + analysis)
- pypdf or reportlab (PDF generation and gluing)
- Shell script entry point (`translate.sh`)
- Python 3.12 (runs inside Docker container)

---

## Docker Architecture
```yaml
services:
  ollama:
    image: ollama/ollama
    # pulls translategemma model on first run

  pipeline:
    image: python:3.12
    volumes:
      - input PDF folder mounted
      - output folder = same as input folder
    environment:
      - ANTHROPIC_API_KEY (injected from Mac Keychain by shell script)
    depends_on:
      - ollama
```

Everything runs in Docker. Nothing installed directly on Mac except Docker Desktop.

---

## Shell Script (`translate.sh` → `/usr/local/bin/translate`)
```bash
#!/bin/bash

# 1. Validate input
if [ -z "$1" ]; then
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
    echo "⏳ Waiting for Docker to be ready..."
    sleep 25
fi

# 3. Retrieve API key from Mac Keychain
API_KEY=$(security find-generic-password -a "$USER" -s "anthropic-api-key" -w)

# 4. Derive output path from input filename
INPUT_DIR=$(dirname "$1")
INPUT_FILE=$(basename "$1")
OUTPUT_FILE="${INPUT_FILE/ori_/pro_}"

# 5. Run pipeline in Docker
docker compose -f ~/german-mail-pipeline/docker-compose.yml run \
  -e ANTHROPIC_API_KEY=$API_KEY \
  -v "$INPUT_DIR:/data" \
  pipeline python3 pipeline.py "/data/$INPUT_FILE" "/data/$OUTPUT_FILE"
```

---

## Pipeline Steps (`pipeline.py`)

### Step 1 — Tesseract OCR
- Convert scanned PDF pages to images (300 DPI)
- Extract German text using Tesseract (`lang=deu`)
- Output: raw German text string

### Step 2 — Presidio PII Redaction (OCR text)
- Detect PII: names, email, phone, IBAN, addresses, IDs, dates
- Redact detected PII with `[REDACTED]` placeholder
- Log what was found (type + position, not the value)
- Output: redacted German text + PII report

### Step 3 — translategemma (local, unredacted text)
- Send raw OCR text (unredacted) to translategemma via Ollama
- Translate German → English fully locally
- No data leaves the machine
- Output: full English translation (may be mediocre quality — that's OK)

### Step 4 — Presidio PII Redaction (translategemma output)
- Redact PII from translategemma English translation too
- Output: redacted English translation

### Step 5 — Claude API
Send to Claude:
- Redacted OCR text (original German, redacted)
- Redacted translategemma translation (English, redacted)

Claude instruction:
```
You are given two versions of the same German document:
1. OCR-extracted German text (PII redacted)
2. Local AI English translation (PII redacted)

Please provide ALL of the following:

## ENGLISH TRANSLATION
Full accurate translation of the document from German to English.

## ENGLISH SUMMARY
3-5 bullet points covering the main points.

## 中文摘要 (Traditional Chinese Summary)
Same summary in Traditional Chinese (繁體中文).

## KEY INFORMATION
Extract key facts, figures, dates, amounts, organization names, references.

## ⚡ ACTION POINTS
List required actions and deadlines. Mark urgent items with ⚠️.

## ⚠️ INCONSISTENCY REPORT
Compare the two translation versions. Flag any differences, ambiguities,
or places where meaning may have been lost due to PII redaction.
Note confidence level: HIGH / MEDIUM / LOW for the overall translation.
```

### Step 6 — Generate Output PDF
Three sections glued into one PDF:

**Page 1: Cover Page**
```
Document: ori_2024_001_mail.pdf
Processed: 2026-03-12 14:30
PII Redacted: 5 items found
Languages: German → English + 中文
```

**Pages 2-X: Original scanned pages** (unchanged)

**Next section: translategemma Full Translation**
- Header: "Local AI Translation (translategemma) — Private, Unredacted Input"
- Full English translation text

**Final section: Claude AI Analysis**
- English Translation
- English Summary
- 中文摘要
- Key Information
- ⚡ Action Points
- ⚠️ Inconsistency Report

---

## Error Handling & Graceful Degradation

| Step | On Failure | Behaviour |
|---|---|---|
| Docker startup | Timeout after 60s | Exit with clear error message |
| Tesseract OCR | Crash or empty output | Log warning, attempt translategemma vision directly |
| Presidio redaction | Crash | Log warning, skip redaction, warn user before continuing |
| translategemma | Timeout (5 min) or crash | Log warning, skip local translation section, continue with Claude only |
| Claude API | Network error / timeout | Retry once, then save partial output and notify user |
| PDF gluing | Crash | Save each section as separate PDF files instead |

Pipeline never fully breaks — always produces some output.

---

## Output Naming Convention
```
Input:  ori_YYYY_NNN_description.pdf
Output: pro_YYYY_NNN_description.pdf
```
Both files always in the same folder.

---

## Secrets Management
- API key stored in Mac Keychain only
- Retrieved by shell script at runtime:
```bash
security add-generic-password -a "$USER" -s "anthropic-api-key" -w "sk-ant-xxxxx"
```
- Never stored in `.env`, never committed to GitHub

---

## Performance Estimates (5-page document)
| Step | Time |
|---|---|
| Docker cold start | ~25s |
| Ollama + model load | ~15s |
| Tesseract OCR | ~1 min |
| Presidio redaction | ~5s |
| translategemma translation | ~2-4 min |
| Claude API | ~20s |
| PDF gluing | ~5s |
| **Total** | **~4-6 minutes** |

---

## GitHub Repository
- Private repo
- `.gitignore`:
  ```
  *.pdf
  output/
  .env
  __pycache__/
  ```
- Files to commit:
  - `SPEC.md` (this file)
  - `CLAUDE.md` (maintained by Claude Code)
  - `translate.sh`
  - `docker-compose.yml`
  - `Dockerfile`
  - `pipeline.py`
  - `requirements.txt`
  - `README.md`
  - `.env.example`

---

## Open Questions (test on first real letter)
1. Does translategemma vision work on scanned images directly?
   - If YES → consider removing Tesseract to simplify pipeline
   - If NO → keep Tesseract as OCR step (current plan)
2. Is translategemma German quality acceptable as cross-reference?
   - If NO → consider swapping to qwen3-vl or llava-llama3 (easy swap)

---

## Key Design Decisions
- **Two models** → translategemma (private, full text) + Claude (quality, redacted) for cross-validation
- **Presidio on both** → redact OCR text AND translategemma output before sending to Claude
- **Graceful degradation** → pipeline always produces output even if steps fail
- **Docker for everything** → nothing installed on Mac except Docker Desktop
- **Mac Keychain** → API key never touches disk or GitHub
- **ori_/pro_ naming** → output always next to input, no folder switching needed
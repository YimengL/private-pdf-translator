# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Instructions

**Always use plan mode throughout this project:**
1. Show the full plan first and wait for explicit approval
2. Show each file diff one by one and wait for approval before moving to the next file
3. Explain WHY for key decisions
4. Do not proceed to the next file without explicit approval

## Project Overview

German Mail Pipeline — processes scanned German PDF mail into an enriched output PDF with OCR text, local AI translation, and Claude AI analysis (English translation + bilingual summary + action points + inconsistency report).

## Entry Point

```bash
translate ~/path/to/ori_2024_001_mail.pdf
```

- `translate` → shell script installed at `/usr/local/bin/translate` (from `translate.sh`)
- Input files are always prefixed with `ori_`
- Output files are always prefixed with `pro_`, saved in the same folder as input

## Architecture

```
translate.sh (shell script)
  → validates input, starts Docker Desktop if needed
  → retrieves ANTHROPIC_API_KEY from Mac Keychain
  → runs docker compose with input PDF mounted at /data

pipeline.py (Python 3.12 inside Docker)
  Step 1: Tesseract OCR — PDF pages → images (300 DPI) → German text
  Step 2: Presidio — redact PII from OCR text → [REDACTED]
  Step 3: translategemma via Ollama — translate raw OCR text (unredacted) locally
  Step 4: Presidio — redact PII from translategemma English output
  Step 5: Claude API (claude-sonnet-4-6) — receives both redacted texts, produces:
            English translation, English summary, 中文摘要, key info, action points, inconsistency report
  Step 6: PDF assembly — cover page + original pages + translategemma section + Claude section
```

## Tech Stack

- Python 3.12 (inside Docker)
- Docker Desktop (everything runs in containers — nothing installed on Mac)
- Tesseract (German language pack: `lang=deu`)
- Microsoft Presidio (local PII redaction)
- translategemma via Ollama (local translation, no cloud)
- Claude API — `claude-sonnet-4-6`
- pypdf or reportlab (PDF generation)

## Secrets Management

API key lives in Mac Keychain only — never in `.env`, never committed to GitHub:
```bash
# To store:
security add-generic-password -a "$USER" -s "anthropic-api-key" -w "sk-ant-xxxxx"
# Retrieved at runtime by translate.sh:
API_KEY=$(security find-generic-password -a "$USER" -s "anthropic-api-key" -w)
```

## Error Handling Policy

Pipeline never fully fails — always produces some output:

| Step | On Failure |
|---|---|
| Tesseract OCR | Log warning, attempt translategemma vision directly |
| Presidio | Log warning, skip redaction, warn user before continuing |
| translategemma | Log warning, skip local translation section, continue with Claude only |
| Claude API | Retry once, then save partial output and notify user |
| PDF gluing | Save each section as separate PDF files instead |

## Key Design Decisions

- **Two models**: translategemma (private, full unredacted text) + Claude (quality, redacted) for cross-validation
- **Presidio on both**: redact OCR text AND translategemma output before sending anything to Claude
- **Docker for everything**: no Mac dependencies except Docker Desktop
- **Mac Keychain**: API key never touches disk or GitHub

## Open Questions (to validate on first real letter)

1. Does translategemma vision work on scanned images directly? If YES → consider removing Tesseract
2. Is translategemma German translation quality acceptable? If NO → consider swapping to qwen3-vl or llava-llama3

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Instructions

**Always use plan mode throughout this project:**
1. Show the full plan first and wait for explicit approval
2. Show each file diff one by one and wait for approval before moving to the next file
3. Explain WHY for key decisions
4. Do not proceed to the next file without explicit approval

## Project Overview

German Mail Pipeline — processes scanned German mail (PDF or phone photo) into an output PDF with local AI translation and Claude AI analysis (English translation + bilingual summary + action points + inconsistency report).

## Entry Point

```bash
translate ~/path/to/ori_2024_001_mail.pdf
```

- `translate` → shell script installed at `/usr/local/bin/translate` (from `translate.sh`)
- Input files prefixed with `ori_`, output prefixed with `pro_`, saved in same folder
- Also accepts image files: `.jpg`, `.jpeg`, `.png`, `.tiff`

## Architecture

```
translate.sh
  → validates input, starts Docker Desktop if needed
  → retrieves ANTHROPIC_API_KEY from Mac Keychain (service: "anthropic-german-mail")
  → runs docker compose with input mounted at /data

pipeline.py (Python 3.12 inside Docker)
  Step 1: pdf2image / PIL    — PDF or image → list of PIL images (300 DPI, capped at 3508px)
  Step 2: Tesseract OCR      — images → raw German text + OCR confidence score (--psm 1, lang=deu)
  Step 3: Presidio stub      — redact German text (STUB — returns None, blocks Claude)
  Step 4: translategemma     — images → English translation via Ollama vision (local, private)
  Step 5: Presidio stub      — redact English text (STUB — returns None, blocks Claude)
  Step 6: Claude API         — SKIPPED until REDACTION_IMPLEMENTED = True
  Step 7: PDF assembly       — summary + Claude translation + local translation
```

## Critical Flag

```python
REDACTION_IMPLEMENTED = False  # in pipeline.py
```

**Claude step (step 6) is blocked while this is False.** No unredacted text is ever sent to cloud. Flip to `True` only after Presidio is fully implemented and tested in steps 3 & 5.

## Output Layout

```
Page 1        Summary (Claude-generated):
                - Importance score 0–100 + reason
                - Action points (⚠️ urgent) + why each matters
                - Key information (English)
                - Key information (简体中文)
                - Sensitive info flagged
                - Local LLM quality score 0–100
                - Disagreements: [Page X] German sentence | Claude vs Local | why it matters
Page 2–x      Claude full translation
Page x–y      translategemma full translation
```

Original scanned pages are NOT included in the output PDF — they remain on disk untouched.

## Tech Stack

- Python 3.12 (inside Docker)
- Docker Desktop (nothing installed on Mac except Docker Desktop)
- Tesseract (`lang=deu`, `--psm 1`) — OCR for redaction/Claude path only
- translategemma via Ollama — vision model, translates directly from images (local, private)
- Microsoft Presidio — PII redaction (not yet implemented)
- Claude API — `claude-sonnet-4-6`
- pypdf + reportlab (PDF generation, STSong-Light for CJK)
- prompt.md — Claude prompt template, edit to tune output without touching pipeline.py

## Secrets Management

API key in Mac Keychain only — never in `.env`, never committed to GitHub:
```bash
# Store (run once per Mac, use Bitwarden as source of truth):
security add-generic-password -a "$USER" -s "anthropic-german-mail" -w "sk-ant-xxxxx"
# Retrieved at runtime by translate.sh automatically
```

## Local Data (off-repo, on Mac)

- `~/.german-mail/index.json` — processed document history (sender, type, reference, deadline)
- `~/.german-mail/costs.log` — Claude API cost per run

## Error Handling Policy

Pipeline never fully fails — always produces some output:

| Step | On Failure |
|---|---|
| Load input | Log warning, exit with clear message |
| Tesseract OCR | Log warning, OCR confidence = 0, continue |
| translategemma | Log warning, skip local translation section |
| Claude API | Retry once, then save partial `.txt` fallback files |
| PDF assembly | Save each section as separate `.txt` files instead |

## Milestones

| # | Milestone | Status |
|---|---|---|
| M0 | Infrastructure + local pipeline (all files created) | ✅ done |
| M1 | First real letter test — validate OCR + translategemma + PDF end-to-end | next |
| M2 | Presidio PII redaction — implement steps 3 & 5, flip flag | |
| M3 | Claude analysis — tune prompt.md on real output, generate sample_output.png | |
| M4 | Polish — index/history, cost log, edge cases, install on both Macs | |

## Key Design Decisions

- **translategemma uses vision**: sends raw images directly — no OCR needed for translation path
- **Tesseract is still needed**: OCR → Presidio redaction → Claude (text only, never images to cloud)
- **REDACTION_IMPLEMENTED flag**: single switch that blocks all cloud calls until privacy is ready
- **prompt.md separate from code**: tune Claude output without touching pipeline.py
- **Docker for everything**: no Mac dependencies except Docker Desktop
- **Bitwarden + Mac Keychain**: Bitwarden as source of truth, Keychain for runtime access

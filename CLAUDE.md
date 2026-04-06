# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Instructions

- Always use plan mode
- Show full plan first, wait for approval
- Show each file diff one by one, wait for approval before next
- Explain WHY for key decisions

## Project Overview

Processes scanned German mail (PDF or phone photo) into an output PDF with local AI translation and Claude AI analysis.

## Entry Points

```bash
# One-shot translate (standalone)
translate ~/gdrive/mail_in/ori_letter.pdf
```

- `translate` → `/usr/local/bin/translate` (symlink to `translate.sh`)
- Input: any file not prefixed `proc_` (strips `ori_` if present)
- Output: prefixed `proc_`, saved in same folder
- Also accepts: `.jpg`, `.jpeg`, `.png`, `.tiff`
- Watch/orchestration is handled by [home-automation](https://github.com/YimengL/home-automation)

## Architecture

```
translate.sh → Docker → pipeline.py
  Step 1: OCR (page-by-page)  — PDF/image → text + confidence (streaming, low memory)
  Step 2: Presidio             — redact German text (skipped for English input)
  Step 3: DeepL API            — German text → English translation (skipped for English input)
  Step 4: Presidio             — redact English text
  Step 5: Claude API           — analyse redacted text (prompt.md or prompt_en.md)
  Step 6: PDF assembly         — summary + DeepL translation + OCR German (if German input)
  Step 7: Sidecar JSON         — proc_filename.json alongside PDF (contract for home-automation)
```

## Tech Stack

- Python 3.12, Docker Desktop
- Tesseract (`lang=deu`, `--psm 1 --oem 1`)
- DeepL API (translation)
- langdetect (language detection)
- Microsoft Presidio (PII redaction — active)
- Claude API `claude-sonnet-4-6`
- reportlab + STSong-Light (CJK)
- `prompt.md` / `prompt_en.md` — Claude prompt templates (edit to tune without touching pipeline.py)

## Secrets

Resolution order: env var → Doppler → Mac Keychain.

```bash
# Mac Keychain (fallback)
security add-generic-password -a "$USER" -s "anthropic-german-mail" -w "sk-ant-xxxxx"
security add-generic-password -a "$USER" -s "deepl-german-mail" -w "your-deepl-key"

# Doppler (recommended)
doppler setup  # select project: private-pdf-translator, config: prd
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow Instructions

- Always use plan mode
- Show full plan first, wait for approval
- Show each file diff one by one, wait for approval before next
- Explain WHY for key decisions

## Project Overview

Processes scanned German mail (PDF or phone photo) into an output PDF with local AI translation and Claude AI analysis.

## Entry Point

```bash
translate ~/path/to/ori_2024_001_mail.pdf
```

- `translate` → `/usr/local/bin/translate` (from `translate.sh`)
- Input: any file not prefixed `proc_` (strips `ori_` if present)
- Output: prefixed `proc_`, saved in same folder
- Also accepts: `.jpg`, `.jpeg`, `.png`, `.tiff`

## Architecture

```
translate.sh → Docker → pipeline.py
  Step 1: pdf2image       — PDF/image → PIL images
  Step 2: Tesseract OCR   — images → text + confidence
  Step 2b: langdetect     — detect language → is_english flag
  Step 3: Presidio        — redact German text (skipped for English input)
  Step 4: DeepL API       — German text → English translation (skipped for English input)
  Step 5: Presidio        — redact English text
  Step 6: Claude API      — analyse redacted text (prompt.md or prompt_en.md)
  Step 7: PDF assembly    — summary + DeepL translation + OCR German if German
  Step 8: Sidecar JSON   — proc_filename.json alongside PDF (contract for home-server)
```

## Tech Stack

- Python 3.12, Docker Desktop
- Tesseract (`lang=deu`, `--psm 1 --oem 1`)
- DeepL free API (translation)
- langdetect (language detection)
- Microsoft Presidio (PII redaction — active)
- Claude API `claude-sonnet-4-6`
- reportlab + STSong-Light (CJK), pypdf
- `prompt.md` / `prompt_en.md` — Claude prompt templates (edit to tune without touching pipeline.py)

## Secrets

API keys in Mac Keychain only:
```bash
security add-generic-password -a "$USER" -s "anthropic-german-mail" -w "sk-ant-xxxxx"
security add-generic-password -a "$USER" -s "deepl-german-mail" -w "your-deepl-key"
```
Use Bitwarden as source of truth across Macs.

## Local Data (off-repo)

- `~/.german-mail/index.json` — document history
- `~/.german-mail/costs.log` — API cost log

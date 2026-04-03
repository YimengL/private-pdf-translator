# German Mail Pipeline

Processes scanned German mail (PDF or photo) into a structured output PDF. Uses Tesseract OCR,
Presidio PII redaction, DeepL for translation, and Claude AI (`claude-sonnet-4-6`) for analysis.

![Sample output](sample_output.jpg)

## Prerequisites

- Docker Desktop (running)
- Secrets via Doppler, env var, or Mac Keychain (see below)

## Install

```bash
# Clone the repo
git clone git@github.com:YimengL/private-pdf-translator.git ~/git/private-pdf-translator

# Install the translate command (one-time)
ln -s ~/git/private-pdf-translator/translate.sh /usr/local/bin/translate
```

The Docker image is built automatically on first run.

## Secrets

Resolution order: env var → Doppler → Mac Keychain.

```bash
# Mac Keychain (fallback)
security add-generic-password -a "$USER" -s "anthropic-german-mail" -w "sk-ant-xxxxx"
security add-generic-password -a "$USER" -s "deepl-german-mail" -w "your-deepl-key"

# Doppler (recommended)
doppler setup  # select project: private-pdf-translator, config: prd
```

## Usage

### One-shot translate

```bash
translate ~/gdrive/mail_in/ori_letter.pdf
```

### Watch mode (daemon)

```bash
cd ~/git/private-pdf-translator
doppler run -- docker compose up
```

Watches `~/gdrive/mail_in/` for new `ori_*.pdf` files and processes them automatically.

## Output

**German input:**
```
Page 1      Summary — importance score, type, sender, deadline, action points,
                      key info (EN + 中文), sensitive info
Page 2–x    DeepL translation
Page x–y    OCR German (for verification)
```

**English input (auto-detected):**
```
Page 1      Summary — importance score, type, sender, deadline, action points,
                      key info (EN + 中文), sensitive info
```

PII redacted before any text reaches Claude:
- German input: phone numbers, IBAN, tax ID, passwords
- English input: phone numbers, IBAN

## Sidecar JSON

Every processed file produces a `proc_filename.json` alongside the PDF. This is the contract for downstream automation (DB write, R2 upload, Telegram notification).

Fields: `schema_version`, `filename`, `original_filename`, `date`, `issued`*, `sender`, `reference`*, `type`, `importance`, `amount`*, `deadline`*, `action_items`, `ocr_confidence`, `deepl_score`*, `claude_confidence`, `tokens_in`, `tokens_out`, `cost_usd`, `model`

*optional — omitted if not found or uncertain

## Known limitations

- CJK mixed lines (Chinese + German) fall back to Helvetica — German umlauts normalised (ß→ss etc.)
- English input (auto-detected via langdetect) — pipeline logic implemented but untested on real English mail
- Image input (.jpg, .png etc.) — code path exists but untested

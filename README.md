# German Mail Pipeline

Processes scanned German mail (PDF or photo) into a structured output PDF. Uses Tesseract OCR,
Presidio PII redaction, translategemma:4b (local LLM) for a best-effort translation, and
Claude AI (claude-sonnet-4-6) to translate and analyse the redacted content.

![Sample output](sample_output.jpg)

## Troubleshooting

**`model failed to load` / llama runner crash**
Homebrew's Ollama (`brew install ollama`) may be behind the version required by translategemma. Install directly from ollama.com instead:
```bash
brew uninstall ollama
curl -fsSL https://ollama.com/install.sh | sh
```
The install script sets up Ollama as a background service that starts at login automatically.

---

## Prerequisites

- Docker Desktop (running)
- Mac Keychain entry for your Anthropic API key:

```bash
security add-generic-password -a "$USER" -s "anthropic-german-mail" -w "sk-ant-xxxxx"
```

## Install

```bash
# Clone the repo
git clone git@github.com:yourname/private-pdf-translator.git ~/git/private-pdf-translator

# Install the translate command
cp translate.sh /usr/local/bin/translate
chmod +x /usr/local/bin/translate

# The image is built automatically on first run of `translate`
```

## Usage

```bash
translate ~/mails/2024_001/ori_2024_001_letter.pdf
```

Any file not prefixed `proc_` is treated as input. Output is prefixed `proc_`, saved in the same folder. The `ori_` prefix is stripped if present.
Also accepts image files: `.jpg`, `.jpeg`, `.png`, `.tiff`

## Output

**German input:**
```
Page 1        Summary — importance score, type, sender, deadline, action points,
                        key info (EN + 中文), sensitive info
Page 2–x      Claude full translation
Page x–y      translategemma translation
Page y–z      OCR German (for verification)
```

**English input (auto-detected):**
```
Page 1        Summary — importance score, type, sender, deadline, action points,
                        key info (EN + 中文), sensitive info
Page 2–x      Claude analysis
```

PII redacted before any text reaches Claude:
- German input: phone numbers, IBAN, tax ID, passwords
- English input: phone numbers, IBAN

## Known limitations

- Local LLM (translategemma 4b) hallucination on dense legal text — Claude output is reliable, local translation is best-effort
- CJK mixed lines (Chinese + German) fall back to Helvetica — German umlauts normalised (ß→ss etc.)
- English input (auto-detected via langdetect) — pipeline logic implemented but untested on real English mail
- Image input (.jpg, .png etc.) — code path exists but untested

## Local data

- `~/.german-mail/index.json` — processed document history
- `~/.german-mail/costs.log` — Claude API cost log

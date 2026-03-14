# German Mail Pipeline

Processes scanned German mail (PDF or photo) into a structured output PDF with local AI translation and analysis.

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

# Build the Docker image (first time only, ~5 min)
cd ~/git/private-pdf-translator
docker compose build
```

## Usage

```bash
translate ~/mails/2024_001/ori_2024_001_letter.pdf
```

Any file not prefixed `proc_` is treated as input. Output is prefixed `proc_`, saved in the same folder. The `ori_` prefix is stripped if present.
Also accepts image files: `.jpg`, `.jpeg`, `.png`, `.tiff`

## Output

```
Page 1        Summary — importance score, action points, key info (EN + 中文),
                        local LLM quality score, disagreements
Page 2–x      Claude full translation
Page x–y      translategemma full translation
```

## Current limitations

PII redaction (Presidio) is not yet implemented. Until it is:
- Claude analysis step is **skipped** — no unredacted text is sent to cloud
- Output contains local LLM translation only
- A warning is printed in the logs

## Local data

- `~/.german-mail/index.json` — processed document history
- `~/.german-mail/costs.log` — Claude API cost log

## Next iteration

- [ ] Add Presidio PII redaction (steps 3 & 5 in `pipeline.py`)
- [ ] Set `REDACTION_IMPLEMENTED = True` in `pipeline.py`
- [ ] Claude analysis and summary page become active
- [ ] Generate `sample_output.png` with fake data to verify layout, fonts, and Chinese rendering

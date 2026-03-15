# HANDOVER.md

## Current Progress

**Milestone M3 — functionally complete.** Claude fires, summary renders, CJK works.

| Milestone | Status |
|---|---|
| M0 — all files created | ✅ |
| M1 — first real letter test | ✅ |
| M2 — Presidio PII redaction | ✅ |
| M3 — Claude analysis + summary page | ✅ |
| M4 — Polish (index, costs, English input) | |

**What works:**
- pymupdf loads scanner PDFs correctly (poppler was too strict)
- Tesseract OCR at 87-94% confidence on real German letters
- Full-page image detection: scanned PDFs skip masking, embedded-photo PDFs mask correctly
- OCR garbage line filtering (alpha ratio + min length)
- Auto-rebuild Docker when `pipeline.py`, `Dockerfile`, or `requirements.txt` change
- Pipeline gracefully degrades at each step
- Full pipeline tested on car ticket (scanned PDF, 84% OCR confidence)
- Presidio caught IBAN, phone numbers, PIN — Claude received redacted text
- CJK rendering working (STSong-Light, leading=20, umlaut normalisation)
- Emoji fallback: ⚠️→[URGENT], 🔴→[HIGH], 📅→[DATE], 🔗→[LINK]
- IMPORTANCE section: type/sender/deadline/actions in one block

## Last Completed

M2/M3 session. Bugs fixed and output polished:
- Fixed RecognizerRegistry language mismatch (Presidio DE engine)
- Fixed full-page image masking whiting out scanned PDFs
- Added fonts-symbola for emoji; prompt.md now copied into Docker
- Removed EMAIL_ADDRESS from redaction (not needed)
- Restructured prompt IMPORTANCE to include type/sender/deadline/actions
- CJK lines use STSong-Light; mixed lines fall back to Helvetica

## Next Immediate Step

**M4 — Polish:**
1. Test on a different real letter (not car ticket) to confirm happy path
2. Review `~/.german-mail/index.json` — check sender/type/deadline parsing is accurate
3. Review `~/.german-mail/costs.log` — confirm cost tracking is writing correctly
4. Consider English input support (`en_` prefix — skip local translation)

## Open Decisions & Known Issues

**`REDACTION_IMPLEMENTED = True`** — Presidio active, Claude step unblocked.

**Local translation quality — known issue**
translategemma 4b and 12b both hallucinate on dense German legal/administrative text. Tested vision and text-to-text approaches — both unreliable. Local translation section in output PDF is currently poor quality. Not worth further effort — Claude (M2) is the quality path. Consider `qwen2.5:7b` as an alternative in future.

**Presidio result on car ticket:** IBAN ✅, phone ✅, PIN ✅ — no tuning needed so far.

**Keychain service name**
SPEC used `anthropic-api-key`. Changed to `anthropic-german-mail`.

**Output prefix changed from SPEC**
SPEC used `pro_`. Changed to `proc_`. Any input not prefixed `proc_` is accepted; `ori_` stripped if present.

**Output layout changed from SPEC**
Original scanned pages NOT in output PDF. Layout: local translation → OCR German (verification). When M2 done: summary → Claude translation → local translation → OCR German.

**Ollama install**
Must install from ollama.com directly — `brew install ollama` gives v0.18.0 which crashes with translategemma. See README troubleshooting.

**sample_output.png not yet created**
Deferred to M3.

## Future Ideas

- **Page-correspondence layout**: original scan page → translation pages → next scan page (no shrinking)
- **Overlay translation on original layout**: replace German text with English in-place (advanced, pymupdf)
- **English input support**: skip local translation, no summary needed, detect via filename prefix `en_`
- **qwen2.5:7b**: try as alternative local translation model if needed

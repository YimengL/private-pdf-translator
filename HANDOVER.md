# HANDOVER.md

## Current Progress

**Milestone M1 — complete.** Pipeline tested on real scanned letter.

| Milestone | Status |
|---|---|
| M0 — all files created | ✅ |
| M1 — first real letter test | ✅ |
| M2 — Presidio PII redaction | ✅ |
| M3 — Claude analysis + summary page | |
| M4 — Polish (index, costs, English input) | |

**What works:**
- pymupdf loads scanner PDFs correctly (poppler was too strict)
- Tesseract OCR at 87-94% confidence on real German letters
- Image masking removes embedded photo noise before OCR
- OCR garbage line filtering (alpha ratio + min length)
- Auto-rebuild Docker when `pipeline.py`, `Dockerfile`, or `requirements.txt` change
- Pipeline gracefully degrades at each step

## Last Completed

M1 real-letter test session. Key findings and fixes applied:
- Switched from `pdf2image` (poppler) to `pymupdf` — handles scanner PDFs
- Switched Ollama to native Mac install (Docker can't use Metal GPU)
- Switched local translation from vision to text-to-text (OCR text → translategemma)
- Added image region masking for OCR (white-out embedded photos)
- Added OCR garbage line filter (`_clean_ocr_text`)
- Reverted to `translategemma:4b` (12b also unreliable)

## Next Immediate Step

**M3 — Claude analysis + summary page:**
1. Run full pipeline end-to-end on a real letter — verify Claude step now fires
2. Check `## SENSITIVE INFO` section in Claude output — confirm entity types logged, no values leaked
3. Tune Presidio if IBAN / Aktenzeichen not caught correctly
4. Build summary page in output PDF (sender, type, deadline, action)

## Open Decisions & Known Issues

**`REDACTION_IMPLEMENTED = True`** — Presidio active, Claude step unblocked.

**Local translation quality — known issue**
translategemma 4b and 12b both hallucinate on dense German legal/administrative text. Tested vision and text-to-text approaches — both unreliable. Local translation section in output PDF is currently poor quality. Not worth further effort — Claude (M2) is the quality path. Consider `qwen2.5:7b` as an alternative in future.

**Presidio tuning — unknown effort**
German-specific PII (IBAN, Aktenzeichen like `315.07.251484.0`) may need custom Presidio recognisers. Standard `de_core_news_lg` handles names/emails/phones well.

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

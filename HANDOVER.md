# HANDOVER.md

## Current Progress

**Milestone M0 — complete.** All infrastructure and pipeline files created.

| File | Status |
|---|---|
| `.gitignore`, `requirements.txt`, `Dockerfile`, `docker-compose.yml` | ✅ |
| `translate.sh` | ✅ |
| `prompt.md` | ✅ |
| `pipeline.py` | ✅ |
| `README.md` | ✅ |

Pipeline runs end-to-end locally: OCR + translategemma + PDF assembly.
Claude step intentionally blocked (see open decisions).

## Last Completed

Full session build — all 8 files created and reviewed one by one.
`CLAUDE.md` restructured as README. `HANDOVER.md` introduced.

## Next Immediate Step

**M0 wrap-up:**
1. Commit all files (6 commits — see README for commit plan)
2. `cp translate.sh /usr/local/bin/translate && chmod +x /usr/local/bin/translate`
3. `docker compose build`

**Then M1:** Run pipeline on a real scanned letter. Validate OCR + translategemma + PDF output.

## Open Decisions & Known Issues

**`REDACTION_IMPLEMENTED = False` in `pipeline.py`**
Claude step (step 6) is hard-blocked. Do NOT flip to `True` until Presidio is fully implemented and tested in steps 3 & 5. This is intentional — no unredacted text should reach the cloud.

**translategemma diverged from SPEC**
SPEC assumed translategemma was text-only. It is a vision model (Gemma 3, SigLIP encoder). Architecture was updated: translategemma now receives raw images directly. Tesseract is kept only for the OCR → redaction → Claude path.

**Keychain service name**
SPEC used `anthropic-api-key`. Changed to `anthropic-german-mail` for clarity. All files use the new name.

**Output layout changed from SPEC**
Original scanned pages are NOT embedded in the output PDF. Layout: summary (page 1) → Claude translation → local translation.

**Presidio (M2) — unknown tuning effort**
German-specific PII (IBAN, Aktenzeichen) may need custom Presidio recognisers. Test on a real letter before estimating.

**sample_output.png not yet created**
Deferred to M3. Add `make_sample.py` to generate a fake-data sample page for README and layout verification.

**English input support (deferred to M4)**
When input is English: skip translategemma (step 4), skip local translation section in PDF, no summary needed (user can read English directly). Detection via filename convention: `ori_en_YYYY_NNN_description.pdf`. Claude still runs for redaction + key info extraction. ~30 min once Presidio is in.

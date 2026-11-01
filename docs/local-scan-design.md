# Local-only scan pipeline — design

Tracking: Linear LIF-90 (parent), LIF-91 to LIF-97 (sub-issues).

## Purpose

A second pipeline next to `translate`. It turns a raw scanned PDF (rental
contract, utility bill, bank statement, tax letter) into a masked text file
that a coding agent (Claude Code or Codex) may read. No cloud API is called
by the pipeline itself.

The existing `translate` flow does not change. `pipeline.py`, `main.py` and
`translate.sh` stay untouched. New code lives in new files and imports from
`pipeline.py`.

## Threat model

The agent is a cloud model. Anything it reads leaves the machine. So:

* The agent must never read a raw PDF or raw OCR text.
* Protection is technical (deny rules, folder permissions, no network),
  not only instructions in a skill.
* Redaction is not perfect, so a gate checks the masked text before the
  agent sees it.

## Flow

```
raw PDF (private folder, agent blocked)
  -> hash + index lookup (skip if already scanned)
  -> OCR (Tesseract, Docker, --network none)
  -> redact (two tiers)
  -> gate (block on high-tier leftovers)
  -> save masked .txt (masked folder, agent allowed)
  -> write index row (SQLite)
```

Raw OCR text is never saved. It exists only in memory.

## Sensitivity tiers

| Tier | Items | Masking | Gate |
|---|---|---|---|
| High | tax ID / tax number, PIN, password, TAN, ID or passport number, date of birth | full mask, e.g. `[TAX_ID]` | blocks, exit non-zero |
| Moderate | IBAN, phone number | partial mask | logs count, continues |

* Tiers apply to fields, not whole documents.
* The tier lists live in one config at the top of `local_redact.py`.
* The gate prints counts by type and page only. Never values.
* If redaction fails, the text is withheld (fail closed).

## Folders

```
raw/<folder>/<name>.pdf        private, agent blocked
masked/<folder>/<name>.txt     agent allowed
```

* Same sub-path and base name on both sides. Only the root and extension differ.
* The masked folder is not a subfolder of the raw folder.
* Raw originals stay out of Google Drive, or are encrypted first.
* The Drive connector is off for sessions that use this workflow.

## Files (all new)

| File | Role |
|---|---|
| `local_pipeline.py` | OCR, redact, gate, write masked file |
| `local_redact.py` | two-tier masking and extra recognizers; reuses the Presidio setup |
| `local_index.py` | SQLite index |
| `scan.sh` | Docker wrapper, `--network none`, raw mounted read-only |

Also: `pyproject.toml` gets the new files in `include` and a `pdf-scan`
script (additive). OCR is reused as is, including its `_clean_ocr_text`
cleanup (it removes junk lines from logos and stamps). The OCR logic is
not changed in this work.

## Review loops

* Local LLM (Ollama): reads the masked text and reports sensitive fields
  that masking missed. Part of the gate, second pass.
* Cloud agent: reads the masked text and reports possible OCR gaps (page
  order, missing or garbled text). Shown in the note as "check original".

## SQLite index

Table `documents`: `sha256`, `path`, `path_history`, `masked_path`,
`scanned_at`, `gate_result`, `doc_type`, `agent_processed_at`.

* Key is the hash of the untouched PDF. Never annotate the original: any
  change to the bytes changes the hash.
* A move or rename keeps the hash, so the row is found and only the path
  is updated (old path goes to `path_history`).
* Before OCR: look up the hash and skip if already scanned and passed.
  `--force` rescans.
* After the masked file is saved: write the row, also when the gate
  blocked. Written last, so a crash never leaves a false "done".
* No document content in the database.

## Commands

* `scan.sh <pdf>`: run the pipeline.
* `scan.sh --apply-moves`: show each suggested name and folder, ask
  yes or no, move the raw PDF and the masked file together, update the
  index. Never overwrites an existing file.
* `scan.sh --verify`: check each row: raw and masked files exist at the
  mirrored paths and the hash matches. Prints counts and mismatching
  paths only.

The agent never runs these. The skill prints the exact command and waits.
The user runs it and pastes the output.

## Handover to the agent (Part 2)

1. User runs `scan.sh` in their own terminal.
2. The script prints one line: gate passed (with count of masked items)
   or gate blocked (type and page only).
3. On pass, the user asks the agent to process the masked file.
4. The agent reads only the masked file, classifies the document, and
   writes a vault note. It also suggests a better name and folder.
5. The skill prints `--apply-moves`, the user runs it, then `--verify`,
   and pastes the output. The agent checks that database, masked tree
   and note agree.

## Security layers

1. Read deny rule for the raw folder in Claude Code settings.
2. Raw folder out of reach at OS level (restricted permissions or an
   encrypted volume), because Bash deny rules are pattern-based.
3. Docker with `--network none`.
4. Gate before the agent.
5. Test with a dummy file in the raw folder: the agent must be refused.

## Build order

1. LIF-91 `local_pipeline.py`
2. LIF-92 gate
3. LIF-93 `local_redact.py`
4. LIF-94 `scan.sh` and `pdf-scan`
5. LIF-95 SQLite index
6. LIF-96 `--apply-moves` and `--verify`
7. LIF-97 folders and deny rules

After every step: run `translate` on a dummy PDF and confirm the same
output; `git diff pipeline.py` stays empty. Test only with fake documents.

## Out of scope (Part 2, separate ticket)

* The skill: document-type detection, rich fact records (JSON details by
  type), cross-check against earlier documents of the same sender and type.
* Optional local Ollama first-round check (type, and whether high-tier
  items still look visible). Runs on the host after the Docker step,
  because the container has no network.
* Apple Vision as an alternative OCR, only if Tesseract quality is poor.
  It runs on macOS only, not in Docker.

## Open questions

* Folder locations for raw and masked.
* Which Ollama models are installed.
* First document types to support in Part 2.
* Whether the old flow's partial masking of tax IDs should be fixed
  separately (not part of this work).

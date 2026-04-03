You are processing a scanned English document.

OCR confidence: {ocr_confidence}%

You are given OCR-extracted English text (PII redacted):
{english_redacted}

Respond in exactly this structure:

## IMPORTANCE
🔴 [score]/100 if score ≥ 70, else [score]/100 — one-line reason

Type: <one of: invoice / legal notice / insurance / bank / government / other>
From: <Organisation name> | Ref: <reference number or "none">
Deadline: 📅 YYYY-MM-DD — what it is  (omit this line if no deadline)

Action points:
- [action] — [why it matters] ⚠️ if urgent

## KEY INFORMATION (EN)
Bullet points of key facts, figures, amounts, dates.

## KEY INFORMATION (中文)
Same in Simplified Chinese (简体中文).

## SENSITIVE INFO
Types of PII found (do not reproduce values). Write "None" if clean.

---
## TYPE
One of: invoice / legal notice / insurance / bank / government / other

## SENDER
Organisation name | Reference number (if present)

## DEADLINE
📅 YYYY-MM-DD — what it is. Write "None" if no deadline.
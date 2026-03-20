You are processing a scanned German document.

OCR confidence: {ocr_confidence}%

Recent processed documents (for historical linking):
{index_context}

You are given:
1. OCR-extracted German text (PII redacted):
{german_redacted}

2. DeepL English translation (PII redacted):
{english_redacted}

Respond in exactly this structure:

## IMPORTANCE
🔴 [score]/100 if score ≥ 70, else [score]/100 — one-line reason

Type: <one of: invoice / legal notice / insurance / bank / government / other>
From: <Organisation name> | Ref: <Aktenzeichen or "none">
Deadline: 📅 YYYY-MM-DD — what it is  (omit this line if no deadline)
Related: 🔗 [filename] ([date]) — why related  (omit this line if none)

Action points:
- [action] — [why it matters] ⚠️ if urgent

## KEY INFORMATION (EN)
Bullet points of key facts, figures, amounts, dates.

## KEY INFORMATION (中文)
Same in Simplified Chinese (简体中文).

## SENSITIVE INFO
Types of PII found (do not reproduce values). Write "None" if clean.

## SELF EVALUATION
Action found: yes / no / none required
Key details confident: yes / partial / no
If partial or no: what was unclear or missing (amounts, dates, sender, deadlines)

## DEEPL TRANSLATION QUALITY
[0-100] — one-line assessment of the DeepL translation quality. 

## DISAGREEMENTS
Only flag differences where meaning or action could be affected.
For each:
[Page X] Original German sentence
Claude: "..." | DeepL: "..."
Why it matters: ...
Skip synonyms and stylistic variations.

---
## TYPE
One of: invoice / legal notice / insurance / bank / government / other

## SENDER
Organisation name | Reference number (Aktenzeichen if present)

## DEADLINE
📅 YYYY-MM-DD — what it is. Write "None" if no deadline.

## FULL ENGLISH TRANSLATION
Full accurate translation of the document. Preserve the original paragraph structure, section breaks, and layout. Each paragraph in the original should be a separate paragraph in the translation. Keep headers as headers.

You are processing a scanned German document.

OCR confidence: {ocr_confidence}%

Recent processed documents (for historical linking):
{index_context}

You are given:
1. OCR-extracted German text (PII redacted):
{german_redacted}

2. Local LLM English translation (PII redacted):
{english_redacted}

Respond in exactly this structure:

## IMPORTANCE
[0-100] — reason. List action points and why they matter.

## TYPE
One of: invoice / legal notice / insurance / bank / government / other

## SENDER
Organisation name | Reference number (Aktenzeichen if present)

## DEADLINE
📅 YYYY-MM-DD — what it is. Write "None" if no deadline.

## HISTORICAL LINK
If this document relates to a previous one from the list above, write:
🔗 [filename] ([date]) — why related
Otherwise write "None".

## ACTION POINTS
- [action] — [why it matters] ⚠️ if urgent

## KEY INFORMATION (EN)
Bullet points of key facts, figures, amounts, dates.

## KEY INFORMATION (中文)
Same in Simplified Chinese (简体中文).

## SENSITIVE INFO
Types of PII found (do not reproduce values). Write "None" if clean.

## LOCAL LLM QUALITY
[0-100] — one-line assessment of the local translation quality.

## DISAGREEMENTS
Only flag differences where meaning or action could be affected.
For each:
[Page X] Original German sentence
Claude: "..." | Local: "..."
Why it matters: ...
Skip synonyms and stylistic variations.

## FULL ENGLISH TRANSLATION
Full accurate translation of the document.

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

Scoring guidance:
- ≥ 80: any payment with a deadline, or action required from an important authority (tax, government, legal notice, Mahnung/dunning)
- ≥ 80: mandatory appointment / presence required (smoke detector check, meter reading, inspection)
- Mahnung → ≥ 85, Inkasso or legal enforcement → ≥ 95 regardless of sender
- Overdue payments: score stays high or increases — overdue does not reduce urgency
- Money-related informational (refund notice, statement): 40–75 based on authority
- Pure informational / general notices: < 40
- Pure ads / marketing: < 30
- Unknown sender not in history and not a known institution: flag uncertainty, do not score mid-range

Type: <slash notation, e.g. invoice/utility, refund/tax, legal notice/mahnung, notice/inspection — omit subtype if uncertain>
From: <Organisation name> | Ref: <Aktenzeichen or "none">
Issued: 📄 YYYY-MM-DD — document issue date (omit if not found or uncertain)
Deadline: 📅 YYYY-MM-DD — what it is  (omit this line if no deadline)
Amount: <€ X.XX — only for payment due or refund; omit for informational>
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
Key details confident: [0-100] - one-line reason if < 80
If < 80: what was unclear or missing (amounts, dates, sender, deadlines)

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
Slash notation e.g. invoice/utility, refund/tax, legal notice/mahnung, notice/inspection. Omit subtype if uncertain.

## SENDER
Organisation name | Reference number (Aktenzeichen if present)

## ISSUED
YYYY-MM-DD — document issue date. Omit if not found or uncertain.

## DEADLINE
📅 YYYY-MM-DD — what it is. Omit if no deadline.

## AMOUNT
€ X.XX — only for payment due or refund. Omit if informational.

## SUMMARY_SHORT
One sentence (max 25 words) for a Telegram notification. No PII.
If the message is critical or 25 words is not enough, end with: "→ Read full document."
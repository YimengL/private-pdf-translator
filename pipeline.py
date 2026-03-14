import io
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import fitz  # pymupdf
import ollama
import pytesseract
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
REDACTION_IMPLEMENTED = False   # guard: flip to True once Presidio is added
OLLAMA_HOST           = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TRANSLATE_MODEL       = "translategemma"
TRANSLATE_TIMEOUT     = 300     # seconds per page
MAX_LONG_SIDE         = 3508    # ~A4 at 300 DPI
SUPPORTED_IMAGES      = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
PROMPT_PATH           = Path(__file__).parent / "prompt.md"
INDEX_PATH            = Path.home() / ".german-mail" / "index.json"
OCR_CONFIDENCE_WARN   = 70.0    # % below which we flag low confidence


# ── Main ─────────────────────────────────────────────────────────────────────
def main(input_pdf: str, output_pdf: str) -> None:
    log.info(f"Input:  {input_pdf}")
    log.info(f"Output: {output_pdf}")

    images           = step1_load_input(input_pdf)
    raw_german, conf = step2_ocr(images)
    german_redacted  = step3_redact_de(raw_german)
    local_english    = step4_local_translate(images)
    english_redacted = step5_redact_en(local_english)
    claude_output    = step6_claude(german_redacted, english_redacted, conf)
    step7_build_pdf(output_pdf, local_english, claude_output)
    update_index(input_pdf, claude_output)


# ── Step 1: Load input ───────────────────────────────────────────────────────
def _normalise_image(img: Image.Image) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / long_side
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
        log.info(f"  Resized {w}×{h} → {new_size[0]}×{new_size[1]}")
    return img


def step1_load_input(input_path: str) -> list | None:
    log.info("Step 1: Load input")
    try:
        suffix = Path(input_path).suffix.lower()
        if suffix == ".pdf":
            doc = fitz.open(input_path)
            mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
            images = []
            for page in doc:
                pix = page.get_pixmap(matrix=mat)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                images.append(img)
            log.info(f"  PDF: {len(images)} page(s) at 300 DPI")
        elif suffix in SUPPORTED_IMAGES:
            img = Image.open(input_path)
            images = [_normalise_image(img)]
            log.info(f"  Image: 1 page loaded")
        else:
            log.warning(f"  Unsupported file type: {suffix}")
            return None
        return images
    except Exception as e:
        log.warning(f"Step 1 FAILED: {e}")
        return None


# ── Step 2: Tesseract OCR ────────────────────────────────────────────────────
def step2_ocr(images: list | None) -> tuple[str | None, float]:
    log.info("Step 2: Tesseract OCR")
    if images is None:
        log.warning("  Skipping — no images")
        return None, 0.0
    try:
        pages, confidences = [], []
        for i, img in enumerate(images, 1):
            log.info(f"  OCR page {i}/{len(images)}")
            data = pytesseract.image_to_data(img, lang="deu",
                                             config="--psm 1",
                                             output_type=pytesseract.Output.DICT)
            confs = [c for c in data["conf"] if c != -1]
            confidences.extend(confs)
            text = pytesseract.image_to_string(img, lang="deu", config="--psm 1")
            pages.append(text)

        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
        if avg_conf < OCR_CONFIDENCE_WARN:
            log.warning(f"  ⚠️  Low OCR confidence: {avg_conf:.0f}% — translation may be unreliable")
        else:
            log.info(f"  OCR confidence: {avg_conf:.0f}%")

        result = "\n\n---\n\n".join(pages)
        log.info(f"  Extracted {len(result)} characters")
        return result, avg_conf
    except Exception as e:
        log.warning(f"Step 2 FAILED: {e}")
        return None, 0.0


# ── Step 3: PII redaction (German) — stub ───────────────────────────────────
def step3_redact_de(text: str | None) -> str | None:
    log.info("Step 3: PII redaction (German)")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Redaction not implemented — output withheld from Claude")
        return None
    # TODO: Presidio German redaction
    return text


# ── Step 4: Local translation (translategemma vision) ───────────────────────
def step4_local_translate(images: list | None) -> str | None:
    log.info("Step 4: Local translation (translategemma)")
    if images is None:
        log.warning("  Skipping — no images")
        return None
    try:
        client = ollama.Client(host=OLLAMA_HOST, timeout=TRANSLATE_TIMEOUT)
        log.info("  Ensuring translategemma model is available...")
        client.pull(TRANSLATE_MODEL)

        pages = []
        for i, img in enumerate(images, 1):
            log.info(f"  Translating page {i}/{len(images)}")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            response = client.chat(
                model=TRANSLATE_MODEL,
                messages=[{
                    "role": "user",
                    "content": "Translate every word of this German document page to English. Do not summarise or skip any content. Output a complete word-for-word translation.",
                    "images": [buf.getvalue()]
                }],
                options={"num_predict": 4096}
            )
            pages.append(response.message.content)

        result = "\n\n---\n\n".join(pages)
        log.info(f"  Translation: {len(result)} characters")
        return result
    except Exception as e:
        log.warning(f"Step 4 FAILED: {e} — skipping local translation")
        return None


# ── Step 5: PII redaction (English) — stub ──────────────────────────────────
def step5_redact_en(text: str | None) -> str | None:
    log.info("Step 5: PII redaction (English)")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Redaction not implemented — output withheld from Claude")
        return None
    # TODO: Presidio English redaction
    return text


# ── Step 6: Claude API ───────────────────────────────────────────────────────
def _load_index_context() -> str:
    if not INDEX_PATH.exists():
        return "No previous documents."
    entries = json.loads(INDEX_PATH.read_text())
    return "\n".join(
        f"- {e['filename']} ({e['date']}) | {e['type']} | {e['sender']} | Ref: {e['reference']}"
        for e in entries[-20:]
    )


def _log_cost(usage) -> None:
    input_cost  = usage.input_tokens  / 1_000_000 * 3.0
    output_cost = usage.output_tokens / 1_000_000 * 15.0
    total = input_cost + output_cost
    log.info(f"  Tokens: {usage.input_tokens} in / {usage.output_tokens} out — ${total:.4f}")
    cost_log = Path.home() / ".german-mail" / "costs.log"
    cost_log.parent.mkdir(parents=True, exist_ok=True)
    with open(cost_log, "a") as f:
        f.write(f"{datetime.now().isoformat()} | in={usage.input_tokens} out={usage.output_tokens} cost=${total:.4f}\n")


def step6_claude(german_redacted: str | None, english_redacted: str | None,
                 ocr_confidence: float) -> str | None:
    log.info("Step 6: Claude API analysis")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Skipping — PII redaction not yet implemented. No unredacted text sent to cloud.")
        return None
    if german_redacted is None or english_redacted is None:
        log.warning("  Skipping — missing redacted input")
        return None
    try:
        prompt = PROMPT_PATH.read_text(encoding="utf-8").format(
            ocr_confidence=f"{ocr_confidence:.0f}",
            index_context=_load_index_context(),
            german_redacted=german_redacted,
            english_redacted=english_redacted,
        )
        client = anthropic.Anthropic()
        for attempt in (1, 2):
            try:
                message = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=4096,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = message.content[0].text
                _log_cost(message.usage)
                return result
            except Exception as e:
                if attempt == 2:
                    raise
                log.warning(f"  Attempt {attempt} failed: {e} — retrying...")
    except Exception as e:
        log.warning(f"Step 6 FAILED: {e}")
        return None


# ── Step 7: Build output PDF ─────────────────────────────────────────────────
def _parse_claude_output(text: str) -> tuple[str, str]:
    marker = "## FULL ENGLISH TRANSLATION"
    if marker in text:
        idx = text.index(marker)
        return text[:idx].strip(), text[idx:].strip()
    return text, ""


def _make_styles() -> dict:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return {
        "h1":       ParagraphStyle("h1",       fontName="Helvetica-Bold", fontSize=16, spaceAfter=6),
        "h2":       ParagraphStyle("h2",       fontName="Helvetica-Bold", fontSize=12, spaceAfter=4),
        "body":     ParagraphStyle("body",     fontName="Helvetica",      fontSize=10, leading=14),
        "body_cjk": ParagraphStyle("body_cjk", fontName="STSong-Light",   fontSize=10, leading=14),
    }


def _clean_line(line: str) -> str:
    return re.sub(r'\*+([^*]+)\*+', r'\1', line)  # strip **bold** and *italic*


def _text_to_flowables(content: str, title: str, styles: dict) -> list:
    flowables = [Paragraph(title, styles["h1"]), Spacer(1, 6*mm)]
    for line in content.splitlines():
        if line.startswith("## "):
            flowables += [Spacer(1, 4*mm), Paragraph(_clean_line(line[3:]), styles["h2"])]
        elif line.strip():
            flowables.append(Paragraph(_clean_line(line), styles["body"]))
    return flowables


def step7_build_pdf(output_pdf: str, local_english: str | None,
                    claude_output: str | None) -> None:
    log.info("Step 7: Build output PDF")
    try:
        styles = _make_styles()
        story  = []

        if claude_output:
            summary, translation = _parse_claude_output(claude_output)
            story += _text_to_flowables(summary, "Summary", styles)
            if translation:
                story += [PageBreak()] + _text_to_flowables(translation, "Claude Translation", styles)

        if local_english:
            if story:
                story.append(PageBreak())
            story += _text_to_flowables(
                local_english, "Local LLM Translation (translategemma)", styles)

        if not story:
            log.warning("  No content — pipeline produced no output")
            return

        doc = SimpleDocTemplate(output_pdf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm,  bottomMargin=20*mm)
        doc.build(story)
        log.info(f"  ✅ Written: {output_pdf}")
    except Exception as e:
        log.warning(f"Step 7 FAILED: {e}")
        _save_fallback_text(output_pdf, local_english, claude_output)


def _save_fallback_text(output_pdf: str, local_english: str | None,
                        claude_output: str | None) -> None:
    base = output_pdf.replace(".pdf", "")
    if local_english:
        Path(f"{base}_local.txt").write_text(local_english, encoding="utf-8")
        log.info(f"  Fallback saved: {base}_local.txt")
    if claude_output:
        Path(f"{base}_claude.txt").write_text(claude_output, encoding="utf-8")
        log.info(f"  Fallback saved: {base}_claude.txt")


# ── Index ────────────────────────────────────────────────────────────────────
def _extract_field(text: str, header: str) -> str:
    match = re.search(rf"## {header}\n(.+)", text)
    return match.group(1).strip() if match else "unknown"


def update_index(input_pdf: str, claude_output: str | None) -> None:
    if claude_output is None:
        return
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    sender_line = _extract_field(claude_output, "SENDER")
    parts       = sender_line.split("|")
    sender      = parts[0].strip() if parts else "unknown"
    reference   = parts[1].strip().replace("Ref:", "").strip() if len(parts) > 1 else "unknown"

    entry = {
        "filename":  Path(input_pdf).name,
        "date":      datetime.now().strftime("%Y-%m-%d"),
        "type":      _extract_field(claude_output, "TYPE"),
        "sender":    sender,
        "reference": reference,
        "deadline":  _extract_field(claude_output, "DEADLINE"),
    }
    entries = json.loads(INDEX_PATH.read_text()) if INDEX_PATH.exists() else []
    entries.append(entry)
    INDEX_PATH.write_text(json.dumps(entries, ensure_ascii=False, indent=2))
    log.info(f"  Index updated: {entry['sender']} | {entry['reference']}")


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: pipeline.py <input_pdf> <output_pdf>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

import json
import html
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import fitz  # pymupdf
import deepl
import pytesseract
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer
from PIL import ImageDraw


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
REDACTION_IMPLEMENTED = True    # Presidio PII redaction active
TRANSLATE_MODEL       = "DeepL"
MAX_LONG_SIDE         = 3508    # ~A4 at 300 DPI
SUPPORTED_IMAGES      = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}
PROMPT_PATH           = Path(__file__).parent / "prompt.md"
PROMPT_EN_PATH        = Path(__file__).parent / "prompt_en.md"
OCR_CONFIDENCE_WARN   = 70.0    # % below which we flag low confidence


# ── Main ─────────────────────────────────────────────────────────────────────
def main(input_pdf: str, output_pdf: str) -> None:
    log.info(f"Input:  {input_pdf}")
    log.info(f"Output: {output_pdf}")

    raw_german, conf       = step1_load_input(input_pdf)
    is_english             = _detect_language(raw_german)
    if is_english:
        log.info("  Detected English document — skipping local translation")
    german_redacted  = None if is_english else step2_redact_de(raw_german)
    local_english    = None if is_english else step3_deepl_translate(german_redacted)
    english_redacted = step4_redact_en(raw_german if is_english else local_english)
    claude_output, claude_usage    = step5_claude(german_redacted, english_redacted, conf, is_english)
    step6_build_pdf(output_pdf, raw_german, local_english, claude_output, conf, is_english)
    step7_write_sidecar(output_pdf, input_pdf, claude_output, conf, claude_usage)


# ── Step 1: Load input ───────────────────────────────────────────────────────
def _mask_image_regions(pil_img: Image.Image, page: fitz.Page, scale: float) -> Image.Image:
    """White-out embedded image regions so Tesseract only sees text."""
    img = pil_img.copy()
    draw = ImageDraw.Draw(img)
    for item in page.get_images(full=True):
        xref = item[0]
        for rect in page.get_image_rects(xref):
            page_rect = page.rect
            page_area = page_rect.width * page_rect.height
            img_area  = rect.width * rect.height
            if img_area / page_area > 0.9:
                log.info("  Skipping — full-page image (scanned PDF)")
                continue
            x0, y0 = int(rect.x0 * scale), int(rect.y0 * scale)
            x1, y1 = int(rect.x1 * scale), int(rect.y1 * scale)
            draw.rectangle([x0, y0, x1, y1], fill="white")
    return img


def _normalise_image(img: Image.Image) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side > MAX_LONG_SIDE:
        scale = MAX_LONG_SIDE / long_side
        new_size = (int(w * scale), int(h * scale))
        img = img.resize(new_size, Image.LANCZOS)
        log.info(f"  Resized {w}×{h} → {new_size[0]}×{new_size[1]}")
    return img


def step1_load_input(input_path: str) -> tuple[str | None, float]:
    """Load input and OCR page-by-page - keeps only one page in memory at a time."""
    log.info("Step 1: Load and OCR")
    try:
        suffix = Path(input_path).suffix.lower()
        if suffix == ".pdf":
            doc = fitz.open(input_path)
            mat = fitz.Matrix(200/72, 200/72)
            scale = 200/72
            pages, page_confs = [], []
            for i, page in enumerate(doc, 1):
                log.info(f" OCR page {i}/{len(doc)}")
                pix = page.get_pixmap(matrix=mat, annots=False)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                img = _mask_image_regions(img, page, scale)
                data = pytesseract.image_to_data(img, lang="deu",
                                                 config="--psm 1 --oem 1",
                                                 output_type=pytesseract.Output.DICT)
                confs = [c for c in data["conf"] if c != -1]
                page_confs.append(sum(confs) / len(confs) if confs else 0.0)
                log.info(f"  Page {i} confidence: {page_confs[-1]:.0f}%")
                text = pytesseract.image_to_string(img, lang="deu", config="--psm 1 --oem 1")
                pages.append(text)
                del img, pix # free page memory before loading next
            key_confs = page_confs[:2]
            avg_conf = sum(key_confs) / len(key_confs) if key_confs else 0.0
            if avg_conf < OCR_CONFIDENCE_WARN:
                log.warning(f"  ⚠️  Low OCR confidence (pages 1-2): {avg_conf:.0f}% — translation may be unreliable")
            else:
                log.info(f"  OCR confidence (pages 1-2): {avg_conf:.0f}%")
            result = _clean_ocr_text("\n\n---\n\n".join(pages))
            log.info(f"  {len(doc)} page(s), {len(result)} characters extracted")
            return result, avg_conf
        elif suffix in SUPPORTED_IMAGES:
            img = _normalise_image(Image.open(input_path))
            data = pytesseract.image_to_data(img, lang="deu",
                                             config="--psm 1 --oem 1",
                                             output_type=pytesseract.Output.DICT)
            confs = [c for c in data["conf"] if c != -1]
            conf = sum(confs) / len(confs) if confs else 0.0
            text = pytesseract.image_to_string(img, lang="deu", config="--psm 1 --oem 1")
            log.info(f" Image: 1 page, confidence: {conf:.0f}%")
            return _clean_ocr_text(text), conf
        else:
            log.warning(f"  Unsupported file type: {suffix}")
            return None, 0.0
    except Exception as e:
        log.warning(f"Step 1 FAILED: {e}")
        return None, 0.0


def _clean_ocr_text(text: str) -> str:
    clean = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            clean.append(line)
            continue
        alpha_ratio = sum(c.isalnum() or c.isspace() for c in stripped) / len(stripped)
        word_count = len(stripped.split())
        if alpha_ratio >= 0.6 and (word_count >= 3 or len(stripped) >= 15):
            clean.append(line)
    return "\n".join(clean)


# ── PII masking helpers ──────────────────────────────────────────────────────
def _mask_value(value: str) -> str:
    n = len(value)
    if n == 0:
        return value
    if n <= 8:
        show = max(0, n - 5)
        if show == 0:
            return "*" * n
        show_s = max(1, show // 2 + show % 2)
        show_e = show - show_s
        if show_e == 0:
            return value[:show_s] + "*" * (n - show_s)
        return value[:show_s] + "*" * (n - show_s - show_e) + value[n - show_e:]
    else:
        show_s = max(1, n // 5)
        show_e = max(1, n // 5)
        return value[:show_s] + "*" * (n - show_s - show_e) + value[n - show_e:]


def _redact(entity_type: str, matched_text: str) -> str:
    if entity_type == "PASSWORD":
        for sep in (":", "="):
            if sep in matched_text:
                idx = matched_text.index(sep)
                keyword = matched_text[:idx + 1]
                value = matched_text[idx + 1:].strip()
                return f"{keyword} [PASSWORD: {'*' * len(value)}]"
        return f"[PASSWORD: {'*' * len(matched_text)}]"
    return f"[{entity_type}: {_mask_value(matched_text)}]"


# ── Presidio lazy singletons ─────────────────────────────────────────────────
_presidio_de = _presidio_en = _presidio_anon = None


def _get_presidio_de():
    global _presidio_de, _presidio_anon
    if _presidio_de is None:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, PatternRecognizer, Pattern
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        tax_id = PatternRecognizer(
            supported_entity="TAX_ID",
            patterns=[
                Pattern("steuer_id",      r"\b\d{2}\s?\d{3}\s?\d{3}\s?\d{3}\b", 0.85),
                Pattern("steuernr_slash", r"\b\d{2,3}/\d{3}/\d{4,5}\b",          0.80),
                Pattern("steuernr_plain", r"\b\d{10,13}\b",                        0.40),
            ],
            context=["Steuer-ID", "Steuernummer", "StNr", "IdNr"],
            supported_language="de",
        )
        password = PatternRecognizer(
            supported_entity="PASSWORD",
            patterns=[Pattern("password_de",
                r"(?:Passwort|Kennwort|Zugangscode|Passcode|PIN)\s*[:=]\s*\S+", 0.9)],
            context=["Passwort", "Kennwort", "Zugangscode", "PIN"],
            supported_language="de",
        )
        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "de", "model_name": "de_core_news_md"}],
        })
        registry = RecognizerRegistry(supported_languages=["de"])
        registry.load_predefined_recognizers(languages=["de"])
        registry.add_recognizer(tax_id)
        registry.add_recognizer(password)
        _presidio_de = AnalyzerEngine(nlp_engine=provider.create_engine(),
                                      registry=registry, supported_languages=["de"])
        _presidio_anon = AnonymizerEngine()
        log.info("Presidio DE engine initialised")
    return _presidio_de, _presidio_anon


def _get_presidio_en():
    global _presidio_en, _presidio_anon
    if _presidio_en is None:
        from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        from presidio_anonymizer import AnonymizerEngine

        provider = NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_md"}],
        })
        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(languages=["en"])
        _presidio_en = AnalyzerEngine(nlp_engine=provider.create_engine(),
                                      registry=registry, supported_languages=["en"])
        if _presidio_anon is None:
            _presidio_anon = AnonymizerEngine()
        log.info("Presidio EN engine initialised")
    return _presidio_en, _presidio_anon


# ── Step 2: PII redaction (German) — stub ───────────────────────────────────
def step2_redact_de(text: str | None) -> str | None:
    log.info("Step 2: PII redaction (German)")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Redaction not implemented — output withheld from Claude")
        return None
    if text is None:
        log.warning("  Skipping — no OCR text")
        return None
    try:
        from presidio_anonymizer.entities import OperatorConfig
        analyzer, anonymizer = _get_presidio_de()
        DE_ENTITIES = ["PHONE_NUMBER", "IBAN_CODE", "TAX_ID", "PASSWORD"]
        results = analyzer.analyze(text=text, language="de", entities=DE_ENTITIES)
        counts: dict[str, int] = {}
        for r in results:
            counts[r.entity_type] = counts.get(r.entity_type, 0) + 1
        log.info(f"  Entities found: {counts}" if counts else "  No PII entities found")
        operators = {
            e: OperatorConfig("custom", {"lambda": lambda x, et=e: _redact(et, x)})
            for e in DE_ENTITIES
        }
        redacted = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        return redacted.text
    except Exception as e:
        log.warning(f"Step 2 FAILED: {e} — withholding from Claude")
        return None


# ── Step 3: DeepL translation ───────────────────────────────────────────────
def step3_deepl_translate(text: str | None) -> str | None:
    log.info("Step 3: DeepL translation")
    if text is None:
        log.warning("  Skipping — no OCR text")
        return None
    try:
        api_key = os.getenv("DEEPL_API_KEY")
        translator = deepl.Translator(api_key)
    
        result = translator.translate_text(text, target_lang="EN-US").text
        result = html.unescape(result)
        log.info(f"  Translation: {len(result)} characters")
        return result
    except Exception as e:
        log.warning(f"Step 3 FAILED: {e} — skipping translation")
        return None


# ── Step 4: PII redaction (English) — stub ──────────────────────────────────
def step4_redact_en(text: str | None) -> str | None:
    log.info("Step 4: PII redaction (English)")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Redaction not implemented — output withheld from Claude")
        return None
    if text is None:
        log.warning("  Skipping — no translation text")
        return None
    try:
        from presidio_anonymizer.entities import OperatorConfig
        analyzer, anonymizer = _get_presidio_en()
        EN_ENTITIES = ["PHONE_NUMBER", "IBAN_CODE"]
        results = analyzer.analyze(text=text, language="en", entities=EN_ENTITIES)
        counts: dict[str, int] = {}
        for r in results:
            counts[r.entity_type] = counts.get(r.entity_type, 0) + 1
        log.info(f"  Entities found: {counts}" if counts else "  No PII entities found")
        operators = {
            e: OperatorConfig("custom", {"lambda": lambda x, et=e: _redact(et, x)})
            for e in EN_ENTITIES
        }
        redacted = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)
        return redacted.text
    except Exception as e:
        log.warning(f"Step 4 FAILED: {e} — withholding from Claude")
        return None


# ── Step 5: Claude API ───────────────────────────────────────────────────────
def _detect_language(text: str | None) -> bool:
    """Returns True if document is predominantly English."""
    if not text:
        return False
    try:
        from langdetect import detect
        return detect(text) == "en"
    except Exception:
        return False


def _log_cost(usage) -> None:
    input_cost  = usage.input_tokens  / 1_000_000 * 3.0
    output_cost = usage.output_tokens / 1_000_000 * 15.0
    total = input_cost + output_cost
    log.info(f"  Tokens: {usage.input_tokens} in / {usage.output_tokens} out — ${total:.4f}")


def step5_claude(german_redacted: str | None, english_redacted: str | None,
                 ocr_confidence: float, is_english: bool = False) -> tuple[str | None, dict | None]:
    log.info("Step 5: Claude API analysis")
    if not REDACTION_IMPLEMENTED:
        log.warning("  ⚠️  Skipping — PII redaction not yet implemented. No unredacted text sent to cloud.")
        return None, None
    if english_redacted is None:
        log.warning("  Skipping — missing redacted input")
        return None, None
    if not is_english and german_redacted is None:
        log.warning("  Skipping — missing redacted input")
        return None, None
    try:
        prompt_path = PROMPT_EN_PATH if is_english else PROMPT_PATH
        fmt_args = dict(ocr_confidence=f"{ocr_confidence:.0f}")
        if is_english:
            fmt_args["english_redacted"] = english_redacted
        else:
            fmt_args["german_redacted"]  = german_redacted
            fmt_args["english_redacted"] = english_redacted
        prompt = prompt_path.read_text(encoding="utf-8").format(**fmt_args)
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
                usage_dict = {
                    "tokens_in": message.usage.input_tokens,
                    "tokens_out": message.usage.output_tokens,
                    "cost_usd": round((message.usage.input_tokens / 1_000_000 * 3.0) +
                    (message.usage.output_tokens / 1_000_000 * 15.0), 4),
                }
                return result, usage_dict
            except Exception as e:
                if attempt == 2:
                    raise
                log.warning(f"  Attempt {attempt} failed: {e} — retrying...")
    except Exception as e:
        log.warning(f"Step 5 FAILED: {e}")
        return None, None


# ── Step 6: Build output PDF ─────────────────────────────────────────────────
def _make_styles() -> dict:
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont("NotoEmoji", "/usr/share/fonts/truetype/ancient-scripts/Symbola_hint.ttf"))
    return {
        "h1":       ParagraphStyle("h1",       fontName="Helvetica-Bold", fontSize=16, spaceAfter=6),
        "h2":       ParagraphStyle("h2",       fontName="Helvetica-Bold", fontSize=12, spaceAfter=4),
        "h2_cjk":  ParagraphStyle("h2_cjk",  fontName="STSong-Light",   fontSize=12, spaceAfter=4),
        "body":     ParagraphStyle("body",     fontName="Helvetica",      fontSize=10, leading=14),
        "body_cjk": ParagraphStyle("body_cjk", fontName="STSong-Light",   fontSize=10, leading=20),
    }


def _clean_line(line: str) -> str:
    return re.sub(r'\*+([^*]+)\*+', r'\1', line)  # strip **bold** and *italic*


def _has_cjk(text: str) -> bool:
    return any('\u4e00' <= c <= '\u9fff' for c in text)


EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FFFF\U00002600-\U000027BF\U0000FE00-\U0000FE0F]+")


def _encode_emoji(text: str) -> str:
    text = text.replace('⚠️', '[URGENT]').replace('🔴', '[HIGH]').replace('📅', '[DATE]').replace('🔗', '[LINK]')
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return EMOJI_RE.sub(lambda m: f'<font name="NotoEmoji">{m.group()}</font>', text)


def _normalize_for_cjk(text: str) -> str:
    return text.replace("ß", "ss").replace("ä", "ae").replace("ö", "oe") \
               .replace("ü", "ue").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")


def _text_to_flowables(content: str, title: str, styles: dict) -> list:
    flowables = [Paragraph(title, styles["h1"]), Spacer(1, 6*mm)]
    for line in content.splitlines():
        if line.startswith("## "):
            cleaned_h2 = _encode_emoji(_clean_line(line[3:]))
            h2_style = styles["h2_cjk"] if _has_cjk(cleaned_h2) else styles["h2"]
            flowables += [Spacer(1, 4*mm), Paragraph(cleaned_h2, h2_style)]
        elif line.strip():
            cleaned = _clean_line(line)
            encoded = _encode_emoji(cleaned)
            if _has_cjk(cleaned):
                flowables.append(Paragraph(_normalize_for_cjk(encoded), styles["body_cjk"]))
            else:
                flowables.append(Paragraph(encoded, styles["body"]))
    return flowables


def _build_metadata_block(ocr_confidence: float, is_english: bool, styles) -> list:
    lines = [
        f"OCR: Tesseract deu  |  confidence: {ocr_confidence:.0f}%",
        f"Translation: {TRANSLATE_MODEL}" if not is_english else "Translation: N/A (English input)",
        f"Analysis: claude-sonnet-4-6",
    ]
    text = "\n".join(lines)
    return _text_to_flowables(text, "Processing Info", styles)


def step6_build_pdf(output_pdf: str, raw_german: str | None,
                    local_english: str | None, claude_output: str | None,
                    ocr_confidence: float = 0.0,
                    is_english: bool = False) -> None:
    log.info("Step 6: Build output PDF")
    try:
        styles = _make_styles()
        story  = []
        story += _build_metadata_block(ocr_confidence, is_english, styles)

        if claude_output:
            story += _text_to_flowables(claude_output, "Summary", styles)

        if not is_english:
            if local_english:
                if story:
                    story.append(PageBreak())
                story += _text_to_flowables(
                    local_english, "DeepL Translation", styles)

            if raw_german:
                if story:
                    story.append(PageBreak())
                story += _text_to_flowables(
                    raw_german, "OCR Output (German — for verification)", styles)

        if not story:
            log.warning("  No content — pipeline produced no output")
            return

        doc = SimpleDocTemplate(output_pdf, pagesize=A4,
                                leftMargin=20*mm, rightMargin=20*mm,
                                topMargin=20*mm,  bottomMargin=20*mm)
        doc.build(story)
        log.info(f"  ✅ Written: {output_pdf}")
    except Exception as e:
        log.warning(f"Step 6 FAILED: {e}")
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


def _parse_int(pattern: str, text: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _parse_date(text: str) -> str | None:
    m = re.search(r'(\d{4}-\d{2}-\d{2})', text)
    return m.group(1) if m else None


# ── Step 7: Write sidecar JSON ───────────────────────────────────────────────
def step7_write_sidecar(output_pdf: str, input_pdf: str,
                        claude_output: str | None,
                        ocr_confidence: float,
                        claude_usage: dict | None) -> None:
    log.info("Step 7: Write sidecar JSON")
    try:
        out_path = Path(output_pdf)
        data: dict = {
            "schema_version": 1,
            "filename": out_path.name,
            "original_filename": Path(input_pdf).name,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "ocr_confidence": round(ocr_confidence),
            "model": "claude-sonnet-4-6",
            "force_retranslate": False,
            "force_reingest": False,
        }
        if claude_usage:
            data["tokens_in"] = claude_usage["tokens_in"]
            data["tokens_out"] = claude_usage["tokens_out"]
            data["cost_usd"] = claude_usage["cost_usd"]
        if claude_output:
            sender_line = _extract_field(claude_output, "SENDER")
            parts = sender_line.split("|")
            sender = parts[0].strip()
            reference = parts[1].strip().replace("Ref:", "").strip() if len(parts) > 1 else None
            doc_type = _extract_field(claude_output, "TYPE")

            if sender and sender != "unknown":
                data["sender"] = sender
            if reference and reference != "unknown":
                data["reference"] = reference
            if doc_type and doc_type != "unknown":
                data["type"] = doc_type
            
            issued = _parse_date(_extract_field(claude_output, "ISSUED"))
            deadline = _parse_date(_extract_field(claude_output, "DEADLINE"))
            amount = _extract_field(claude_output, "AMOUNT")

            if issued:
                data["issued"] = issued
            if deadline:
                data["deadline"] = deadline
            if amount and amount != "unknown":
                data["amount"] = amount

            importance = _parse_int(r'(\d+)/100', claude_output)
            claude_conf = _parse_int(r'Key details confident:\s*\[?(\d+)\]?', claude_output)
            deepl_score = _parse_int(r'## DEEPL TRANSLATION QUALITY\s*\n\[?(\d+)\]?', claude_output)

            if importance is not None:
                data["importance"] = importance
            if claude_conf is not None:
                data["claude_confidence"] = claude_conf
            if deepl_score is not None:
                data["deepl_score"] = deepl_score
            action_items = []
            m = re.search(r'Action points:\n((?:- .+\n?)+)', claude_output)
            if m:
                for line in m.group(1).strip().splitlines():
                    if line.strip().startswith("- "):
                        action_items.append(line.strip()[2:].split(" — ")[0].strip())
                if action_items:
                    data["action_items"] = action_items

            summary_short = _extract_field(claude_output, "SUMMARY_SHORT")
            if summary_short and summary_short != "unknown":
                data["summary_short"] = summary_short
        sidecar = out_path.with_suffix(".json")
        sidecar.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info(f"  ✅ Sidecar written: {sidecar.name}")  
    except Exception as e:
        log.warning(f"Step 7 FAILED: {e}")



def derive_output_path(input_path: Path) -> Path:
    """
    Derive proc_*.pdf output path from an input PDF.

    ori_x.pdf -> proc_x.pdf
    anything_else.pdf -> proc_anything_else.pdf
    """
    name = input_path.name
    output_name = "proc_" + (name[len("ori_"):] if name.startswith("ori_") else name)
    return input_path.parent / output_name


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: pipeline.py <input_pdf> <output_pdf>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])

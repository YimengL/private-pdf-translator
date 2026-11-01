import argparse
import logging
import sys
import tempfile
from collections import Counter
from pathlib import Path

import fitz  # pymupdf

from local_redact import HIGH_TIER, MODERATE_TIER, get_analyzer, redact_de
from pipeline import step1_load_input

log = logging.getLogger(__name__)


def gate(masked: str) -> Counter:
    """Re-scan masked text. Returns leftover sensitive items counted by type."""
    analyzer, _ = get_analyzer()
    results = analyzer.analyze(text=masked, language="de",
                               entities=sorted(HIGH_TIER | MODERATE_TIER))
    return Counter(r.entity_type for r in results)


def masked_path(input_path: Path, raw_root: Path, masked_root: Path) -> Path:
    """Mirror the raw sub-path under the masked root, with a .txt extension."""
    rel = input_path.resolve().relative_to(raw_root.resolve())
    return masked_root / rel.with_suffix(".txt")


def iter_pages(input_path: Path):
    """Yield (page_number, single-page file). Images count as one page."""
    if input_path.suffix.lower() != ".pdf":
        yield 1, input_path
        return
    with fitz.open(input_path) as src, tempfile.TemporaryDirectory() as tmp:
        for i in range(len(src)):
            page_file = Path(tmp) / f"page_{i + 1}.pdf"
            with fitz.open() as one:
                one.insert_pdf(src, from_page=i, to_page=i)
                one.save(page_file)
            yield i + 1, page_file


def main(input_path: str, raw_root: str, masked_root: str) -> int:
    src = Path(input_path)
    out = masked_path(src, Path(raw_root), Path(masked_root))

    pages, confs = [], []
    blocked, moderate = {}, Counter()
    for n, page_file in iter_pages(src):
        raw_text, conf = step1_load_input(str(page_file))
        if raw_text is None:
            log.error(f"OCR failed on page {n} - nothing written")
            return 1
        masked = redact_de(raw_text)
        if masked is None:
            log.error(f"Redaction failed on page {n} - nothing written")
            return 1
        try:
            counts = gate(masked)
        except Exception as e:
            log.error(f"Gate failed on page {n} ({type(e).__name__}) - nothing written")
            return 2
        high = {k: v for k, v in counts.items() if k in HIGH_TIER}
        if high:
            blocked[n] = high
        moderate.update({k: v for k, v in counts.items() if k in MODERATE_TIER})
        pages.append(masked)
        confs.append(conf)
    if not pages:
        log.error("No pages found - nothing written")
        return 1
    if blocked:
        log.error(f"Gate BLOCKED - high-tier items still visible (page: counts): {blocked} - nothing written")
        return 2
    if moderate:
        log.info(f"Gate: moderate-tier items left: {dict(moderate)}")

    result = "".join(f"=== page {n} ===\n\n{t}\n\n" for n, t in enumerate(pages, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")
    log.info(f"Masked text written ({len(pages)} page(s), OCR avg {sum(confs)/len(confs):.0f}%)")
    return 0


def cli() -> None:
    parser = argparse.ArgumentParser(prog="pdf-scan")
    parser.add_argument("pdf_path")
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--masked-root", required=True)
    args = parser.parse_args()
    sys.exit(main(args.pdf_path, args.raw_root, args.masked_root))


if __name__ == "__main__":
    cli()

import argparse
import logging
import sys
from pathlib import Path

from pipeline import step1_load_input, step2_redact_de

log = logging.getLogger(__name__)


def masked_path(input_path: Path, raw_root: Path, masked_root: Path) -> Path:
    """Mirror the raw sub-path under the masked root, with a .txt extension."""
    rel = input_path.resolve().relative_to(raw_root.resolve())
    return masked_root / rel.with_suffix(".txt")


def main(input_path: str, raw_root: str, masked_root: str) -> int:
    src = Path(input_path)
    out = masked_path(src, Path(raw_root), Path(masked_root))

    raw_text, conf = step1_load_input(str(src))
    if raw_text is None:
        log.error("OCR failed - nothing written")
        return 1

    masked = step2_redact_de(raw_text)
    if masked is None:
        log.error("Redaction failed - nothing written")
        return 1

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(masked, encoding="utf-8")
    log.info(f"Masked text written ({len(masked)} characters, OCR {conf:.0f}%)")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="pdf-scan")
    parser.add_argument("pdf_path")
    parser.add_argument("--raw-root", required=True)
    parser.add_argument("--masked-root", required=True)
    args = parser.parse_args()
    sys.exit(main(args.pdf_path, args.raw_root, args.masked_root))

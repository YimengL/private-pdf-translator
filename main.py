import argparse
import logging
import os
from pathlib import Path

import pipeline
import watcher


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    parser = argparse.ArgumentParser(prog="pdf-translator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("watch")
    p.add_argument("folder", nargs="?", default=os.environ.get("WATCH_FOLDER"))

    p = sub.add_parser("translate")
    p.add_argument("pdf_path")

    args = parser.parse_args()

    if args.cmd == "watch":
        if not args.folder:
            parser.error("folder argument or WATCH_FOLDER env var is required")
        watcher.start(args.folder)
    elif args.cmd == "translate":
        path = Path(args.pdf_path)
        pipeline.main(str(path), str(pipeline.derive_output_path(path)))

if __name__ == "__main__":
    main()

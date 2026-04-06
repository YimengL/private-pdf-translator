import argparse
import logging
from pathlib import Path

import pipeline


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main():
    parser = argparse.ArgumentParser(prog="pdf-translator")

    parser.add_argument("pdf_path")

    args = parser.parse_args()

    path = Path(args.pdf_path)
    pipeline.main(str(path), str(pipeline.derive_output_path(path)))

if __name__ == "__main__":
    main()

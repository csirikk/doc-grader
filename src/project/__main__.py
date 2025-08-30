# project/__main__.py
"""
Usage:
  python -m project path/to/file.md [-d|--debug]
  python -m project path/to/file.pdf
"""

import sys
import argparse
from pathlib import Path
from .parsers.md_parser import parse_markdown

def handle_markdown(path: Path, debug: bool = False) -> int:
    doc = parse_markdown(path, debug=debug)
    sys.stdout.write(doc.model_dump_json(indent=2) + "\n")
    return 0


def handle_pdf(path: Path, debug: bool = False) -> int:
    # TODO:
    sys.stdout.write(f"pdf handler selected: {path}\n")
    return 0


def detect_handler(path: Path):
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return handle_markdown
    if ext == ".pdf":
        return handle_pdf
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="project",
    )
    parser.add_argument(
        "input",
        help="Path to input file (type can be .md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable parser debug output"
    )
    args = parser.parse_args(argv)

    path = Path(args.input)
    if not path.exists():
        sys.stderr.write(f"[error] File not found: {path}\n")
        return 1
    if not path.is_file():
        sys.stderr.write(f"[error] Not a regular file: {path}\n")
        return 1

    format_handler = detect_handler(path)
    if format_handler is None:
        sys.stderr.write(f"[error] Unsupported filetype '{path.suffix}', try .md, .markdown, .pdf")
        return 1

    return format_handler(path, args.debug)


if __name__ == "__main__":
    raise SystemExit(main())

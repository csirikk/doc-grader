"""__main__.py
CLI entry point for the tool.

Usage examples:
    python -m project doc.md
    python -m project doc.md other.md third.md --out findings_out
    python -m project assignment.pdf   # (PDF handler placeholder)

Notes:
- Always runs detector pipeline for Markdown
- Designed for easy extension: append detectors to the `detectors` list.
"""

import sys
import argparse
from pathlib import Path
import json
from typing import List

from .parsers.md_parser import parse_markdown
from .detectors.length_detector import LengthDetector
from .detectors.base_detector import BaseDetector
from .schemas.ir import Document, Paragraph, Span
from .util import doc_hash, summarize_document, print_findings


def _process_markdown(path: Path, *, debug: bool, outdir: Path) -> int:
    doc = parse_markdown(path, debug=debug)
    print("=" * 80)
    print(f"File: {path}")
    h = doc_hash(str(path))
    print(f"Hash: {h}")
    summary = summarize_document(doc)
    print("IR Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    # Detector pipeline TODO: config
    detectors: List[BaseDetector] = [LengthDetector()]
    all_findings = 0
    for det in detectors:
        findings = det.detect_on_ir(doc, h)
        print_findings(det, findings, outdir)
        all_findings += len(findings)

    print("=" * 80)
    print(f"Done.\nTotal findings: {all_findings}")
    return 0


def handle_pdf(path: Path, debug: bool = False) -> int:
    # TODO:
    sys.stdout.write(f"pdf handler selected: {path}\n")
    return 0


def detect_handler(path: Path):
    ext = path.suffix.lower()
    if ext in {".md", ".markdown"}:
        return "markdown"
    if ext == ".pdf":
        return "pdf"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more input paths (.md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable parser debug output"
    )
    parser.add_argument(
        "--out", default="writefinding_cli", help="Output directory for findings"
    )
    args = parser.parse_args(argv)

    outdir = Path(args.out)
    for raw in args.inputs:
        path = Path(raw)
        kind = detect_handler(path)
        if kind == "markdown":
            _process_markdown(path, debug=args.debug, outdir=outdir)
        elif kind == "pdf":
            handle_pdf(path, args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

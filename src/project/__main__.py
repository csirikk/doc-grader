import argparse
from pathlib import Path
import json
from typing import List, Optional

from .parsers.md_parser import parse_markdown
from .parsers.pdf_parser import parse_pdf
from .detectors.length_detector import LengthDetector
from .detectors.base_detector import BaseDetector
from .schemas.ir import Document
from .util import doc_hash, summarize_document, print_findings
from .logger import set_debug, debug


def _run_pipeline(doc: Document, *, outdir: Path, detectors: Optional[List[BaseDetector]] = None) -> int:
    hash_value = doc_hash(doc.source_path)
    print("=" * 80)
    print(f"File: {doc.source_path}")
    print(f"Hash: {hash_value}")
    summary = summarize_document(doc)
    print("IR Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    detectors = detectors or [LengthDetector()]
    all_findings = 0
    for det in detectors:
        debug("running detector %s on %s", det.code, doc.source_path)
        findings = det.detect_on_ir(doc, hash_value)
        print_findings(det, findings, outdir)
        all_findings += len(findings)

    print("=" * 80)
    print(f"Done.\nTotal findings: {all_findings}")
    debug("finished processing %s with %d findings", doc.source_path, all_findings)
    return all_findings

def parse_input_to_document(path: Path) -> Optional[Document]:
    ext = path.suffix.lower()
    if not path.exists():
        print(f"Missing file: {path}")
        return None
    try:
        if ext in {".md", ".markdown"}:
            debug("parsing markdown file %s", path)
            return parse_markdown(path)
        if ext == ".pdf":
            debug("TODO: not yet implemented, trying to parse pdf file %s", path)
            return parse_pdf(path)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        debug("Exception while parsing %s: %s", path, e)
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project")
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more input paths (.md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--out", default="test/findings_out", help="Output directory for findings"
    )
    args = parser.parse_args(argv)

    outdir = Path(args.out)
    if args.debug:
        set_debug(True)
        debug("debug logging enabled")
    detectors: List[BaseDetector] = [LengthDetector()]
    for raw in args.inputs:
        path = Path(raw)
        doc = parse_input_to_document(path)
        if doc is None:
            print(f"Skipping unsupported file type: {path}")
            continue
        _run_pipeline(doc, outdir=outdir, detectors=detectors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

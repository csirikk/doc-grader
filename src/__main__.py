"""CLI entry point."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from docling.datamodel.document import DoclingDocument

from .logger import configure_logging
from .parsers import parse
from .schemas.ir import Document
from .util import compute_doc_hash

logger = logging.getLogger(__name__)


def _export_markdown(doc: DoclingDocument, file_path: Path, outdir: Path) -> None:
    md_file = outdir / f"{file_path.stem}.md"
    try:
        md_output = doc.export_to_markdown()
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_output)
        logger.debug(f"Exported Markdown to: {md_file}")
    except Exception as e:
        logger.error(f"Error exporting Markdown to {md_file}: {e}")


def _export_json(doc: DoclingDocument, file_path: Path, outdir: Path) -> None:
    json_file = outdir / f"{file_path.stem}.json"
    try:
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(doc.model_dump_json())
        logger.debug(f"Exported JSON structure to: {json_file}")
    except Exception as e:
        logger.error(f"Error exporting JSON to {json_file}: {e}")


def _print_statistics(ir_doc: Document) -> None:
    print("Docling stats:")
    print(f"  Paragraphs: {ir_doc.total_paragraphs}")
    print(f"  Headings:   {ir_doc.total_headings}")
    print(f"  Words:      {ir_doc.total_words}")
    print(f"  Tables:     {len(ir_doc.docling_doc.tables)}")
    print(f"  Pictures:   {len(ir_doc.docling_doc.pictures)}")


def run_docling_demo(
    ir_doc: Document,
    *,
    file_path: Path,
    outdir: Path,
) -> None:
    print("=" * 80)
    print(f"File: {file_path}")

    if not outdir.exists():
        try:
            outdir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Error creating directory {outdir}: {e}")
            return
    _export_markdown(ir_doc.docling_doc, file_path, outdir)
    _export_json(ir_doc.docling_doc, file_path, outdir)
    _print_statistics(ir_doc)


def parse_input_to_ir(path: Path) -> Optional[Document]:
    """Parse file and wrap in IR Document."""
    doc = parse(path)
    if doc is None:
        return None
    try:
        sha256 = compute_doc_hash(str(path))
    except OSError:
        return None

    return Document.from_docling(doc=doc, source_path=str(path), sha256=sha256)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="project")
    parser.add_argument(
        "inputs", nargs="+", help="One or more input paths (.md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--out", default="out/findings/", help="Output directory for findings"
    )
    parser.add_argument(
        "-c", "--config", help="Path to JSON config file for detectors", default=None
    )
    args = parser.parse_args(argv)

    if args.debug:
        configure_logging(logging.DEBUG)
        logger.debug("Debug logging enabled")
    else:
        configure_logging(logging.INFO)

    base_outdir = Path(args.out)
    exit_code = 0

    for raw_path in args.inputs:
        path = Path(raw_path)

        ir_doc = parse_input_to_ir(path)

        if ir_doc is None:
            logger.warning(f"Skipping unsupported file type: {path}")
            exit_code = 1
            continue

        file_outdir = base_outdir / path.stem

        if isinstance(ir_doc, Document):
            run_docling_demo(ir_doc, file_path=path, outdir=file_outdir)
        else:
            logger.error(f"Unexpected document type returned: {type(ir_doc)}")
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

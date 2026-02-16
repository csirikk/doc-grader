"""CLI entry point."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from docling.datamodel.document import DoclingDocument

from .logger import (
    debug,
    set_debug,
)
from .parsers import parse


def _export_markdown(doc: DoclingDocument, file_path: Path, outdir: Path) -> None:
    md_file = outdir / f"{file_path.stem}.md"
    try:
        md_output = doc.export_to_markdown()
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(md_output)
        debug(f"Exported Markdown to: {md_file}")
    except Exception as e:
        print(f"Error exporting Markdown to {md_file}: {e}", file=sys.stderr)


def _export_json(doc: DoclingDocument, file_path: Path, outdir: Path) -> None:
    json_file = outdir / f"{file_path.stem}.json"
    try:
        with open(json_file, "w", encoding="utf-8") as f:
            f.write(doc.model_dump_json())
        debug(f"Exported JSON structure to: {json_file}")
    except Exception as e:
        print(f"Error exporting JSON to {json_file}: {e}", file=sys.stderr)


def _print_statistics(doc: DoclingDocument) -> None:
    num_texts = len(doc.texts)
    num_tables = len(doc.tables)
    num_pics = len(doc.pictures)

    print("Docling stats:")
    print(f"  Paragraphs: {num_texts}")
    print(f"  Tables:     {num_tables}")
    print(f"  Pictures:   {num_pics}")


def run_docling_demo(
    doc: DoclingDocument,
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
            print(f"Error creating directory {outdir}: {e}", file=sys.stderr)
            return

    _export_markdown(doc, file_path, outdir)
    _export_json(doc, file_path, outdir)
    _print_statistics(doc)


def parse_input_to_document(path: Path) -> Optional[DoclingDocument]:
    if not path.exists():
        print(f"Error: Missing file {path}", file=sys.stderr)
        return None
    try:
        return parse(path)
    except Exception as e:
        print(f"Error parsing {path}: {e}", file=sys.stderr)
        debug("Exception while parsing %s: %s", path, e)
        return None


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
        set_debug(True)
        debug("debug logging enabled")

    base_outdir = Path(args.out)
    exit_code = 0

    for raw_path in args.inputs:
        path = Path(raw_path)
        doc = parse_input_to_document(path)
        if doc is None:
            print(f"Skipping unsupported file type: {path}")
            exit_code = 1
            continue
        file_outdir = base_outdir / path.stem

        if isinstance(doc, DoclingDocument):
            run_docling_demo(doc, file_path=path, outdir=file_outdir)
        else:
            print(
                f"Error: Unexpected document type returned: {type(doc)}",
                file=sys.stderr,
            )
            exit_code = 1

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

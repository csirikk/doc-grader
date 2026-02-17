"""Unified parser interface returning IR-oriented parse output."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import Field

from ..schemas.base import StrictModel
from ..schemas.finding import AnalyserInfo, Finding
from ..schemas.ir import Document, DocumentRef
from ..utils import next_id

if TYPE_CHECKING:
    from pathlib import Path

    from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md"}


class ParseMeta(StrictModel):
    """Metadata about the parsing process."""

    parsed_ok: bool = False
    error: str | None = None
    used_ocr: bool = False
    table_structure: bool = False


class ParseOutput(StrictModel):
    """Output from the parsing process."""

    doc_ref: DocumentRef
    ir: Document | None = None
    parser_findings: list[Finding] = Field(default_factory=list)
    parse_meta: ParseMeta = Field(default_factory=ParseMeta)


class DocumentParser:
    """Handles Docling conversion, hashing, and IR generation."""

    def __init__(self) -> None:
        # Lazy import heavy dependencies
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TableStructureOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            MarkdownFormatOption,
            PdfFormatOption,
        )

        self.do_ocr = True
        self.do_table_structure = True

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = self.do_ocr
        pdf_options.do_table_structure = self.do_table_structure
        pdf_options.ocr_options.lang = ["ces", "eng", "slk"]
        pdf_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True
        )

        self.converter: DocumentConverter = DocumentConverter(
            allowed_formats=[InputFormat.PDF, InputFormat.MD],
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options),
                InputFormat.MD: MarkdownFormatOption(),
            },
        )

    def _make_finding(
        self,
        doc_ref: DocumentRef,
        ac_code: str,
        title: str,
        summary: str,
        run_id: str | None,
        config_hash: str | None,
    ) -> Finding:
        return Finding(
            analyser=AnalyserInfo(
                analyser_id="PARSER",
                name="Parser",
                run_id=run_id,
                config_hash=config_hash,
            ),
            document=doc_ref,
            finding_id=next_id(f"PARSER:{ac_code}"),
            ac_code=ac_code,
            title=title,
            summary=summary,
        )

    def _create_error_output(
        self,
        doc_ref: DocumentRef,
        parse_meta: ParseMeta,
        ac_code: str,
        title: str,
        summary: str,
        error_msg: str,
        run_id: str | None,
        config_hash: str | None,
    ) -> ParseOutput:
        parse_meta.error = error_msg
        parse_meta.parsed_ok = False

        finding = self._make_finding(
            doc_ref, ac_code, title, summary, run_id, config_hash
        )
        return ParseOutput(
            doc_ref=doc_ref,
            ir=None,
            parser_findings=[finding],
            parse_meta=parse_meta,
        )

    def parse(
        self,
        path: Path,
        *,
        run_id: str | None = None,
        config_hash: str | None = None,
    ) -> ParseOutput:
        """Parse the given document."""
        doc_ref = DocumentRef(source_path=str(path), origin=None, binary_hash=None)

        parse_meta = ParseMeta(
            used_ocr=self.do_ocr,
            table_structure=self.do_table_structure,
        )

        if not path.exists():
            return self._create_error_output(
                doc_ref,
                parse_meta,
                "MISSING",
                "Input file missing",
                f"Input file does not exist: {path}",
                "File missing",
                run_id,
                config_hash,
            )

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return self._create_error_output(
                doc_ref,
                parse_meta,
                "DOCTYPE",
                "Unsupported file type",
                f"Unsupported suffix: {path.suffix}",
                f"Unsupported suffix: '{path.suffix}'",
                run_id,
                config_hash,
            )

        try:
            logger.debug("Parsing %s with Docling...", path)
            doc = self.converter.convert(path).document

            if doc.origin is None:
                return self._create_error_output(
                    doc_ref,
                    parse_meta,
                    "PARSE_NO_ORIGIN",
                    "Missing document origin",
                    "Docling did not populate document origin.",
                    "Missing origin",
                    run_id,
                    config_hash,
                )

            doc_ref.origin = doc.origin
            doc_ref.binary_hash = int(doc.origin.binary_hash)
            parse_meta.parsed_ok = True
            parse_meta.error = None

            ir = Document.from_docling(doc=doc, doc_ref=doc_ref)
            return ParseOutput(
                doc_ref=doc_ref,
                ir=ir,
                parser_findings=[],
                parse_meta=parse_meta,
            )
        except Exception as e:
            logger.error("Error parsing %s: %s", path, e)
            return self._create_error_output(
                doc_ref,
                parse_meta,
                "PARSE_ERROR",
                "Parse failed",
                f"Parser failed: {e}",
                str(e),
                run_id,
                config_hash,
            )

"""Unified parser interface returning IR-oriented parse output."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any, Optional

from pydantic import Field

from ..schemas.finding import AnalyserInfo, Finding, StrictModel
from ..schemas.ir import Document, DocumentRef
from ..util import compute_doc_hash, next_id

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown"}


class ParseOutput(StrictModel):
    document_ref: DocumentRef
    ir: Optional[Document] = None
    parser_findings: list[Finding] = Field(default_factory=list)
    parse_meta: dict[str, Any] = Field(default_factory=dict)


class DocumentParser:
    """Handles Docling conversion, hashing, and IR generation."""

    def __init__(self):
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            PdfPipelineOptions,
            TableStructureOptions,
        )
        from docling.document_converter import DocumentConverter, PdfFormatOption

        self.do_ocr = True
        self.do_table_structure = True

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.do_ocr
        pipeline_options.do_table_structure = self.do_table_structure
        pipeline_options.table_structure_options = TableStructureOptions(
            do_cell_matching=True
        )

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )

    def _make_finding(
        self,
        document_ref: DocumentRef,
        ac_code: str,
        title: str,
        summary: str,
        run_id: Optional[str],
        config_hash: Optional[str],
    ) -> Finding:
        return Finding(
            analyser=AnalyserInfo(
                analyser_id="PARSER",
                name="Parser",
                run_id=run_id,
                config_hash=config_hash,
            ),
            document=document_ref,
            finding_id=next_id(f"PARSER:{ac_code}"),
            ac_code=ac_code,
            title=title,
            summary=summary,
        )

    def parse(
        self,
        path: Path,
        *,
        run_id: Optional[str] = None,
        config_hash: Optional[str] = None,
    ) -> ParseOutput:
        mimetype, _ = mimetypes.guess_type(str(path))
        source_path = str(path)
        doc_ref = DocumentRef(source_path=source_path, sha256=None, mimetype=mimetype)

        parse_meta = {
            "parsed_ok": False,
            "error": None,
            "used_ocr": self.do_ocr,
            "table_structure": self.do_table_structure,
        }

        def _error_result(
            ac_code: str, title: str, summary: str, error_msg: str
        ) -> ParseOutput:
            parse_meta["error"] = error_msg
            finding = self._make_finding(
                doc_ref, ac_code, title, summary, run_id, config_hash
            )
            return ParseOutput(
                document_ref=doc_ref,
                ir=None,
                parser_findings=[finding],
                parse_meta=parse_meta,
            )

        if not path.exists():
            return _error_result(
                "MISSING",
                "Input file missing",
                f"Input file does not exist: {path}",
                "File missing",
            )

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return _error_result(
                "DOCTYPE",
                "Unsupported file type",
                f"Unsupported suffix: {path.suffix}",
                f"Unsupported suffix: '{path.suffix}'",
            )

        try:
            doc_ref.sha256 = compute_doc_hash(source_path)
        except OSError as e:
            return _error_result(
                "IO_ERROR", "Cannot read file", f"Failed to read: {e}", str(e)
            )

        try:
            logger.debug("Parsing %s with Docling...", path)
            doc = self.converter.convert(path).document

            parse_meta["parsed_ok"] = True
            ir = Document.from_docling(
                doc=doc,
                source_path=doc_ref.source_path,
                sha256=doc_ref.sha256,
                mimetype=doc_ref.mimetype,
            )
            return ParseOutput(
                document_ref=doc_ref, ir=ir, parser_findings=[], parse_meta=parse_meta
            )
        except Exception as e:
            logger.error("Error parsing %s: %s", path, e)
            return _error_result(
                "PARSE_ERROR", "Parse failed", f"Parser failed: {e}", str(e)
            )

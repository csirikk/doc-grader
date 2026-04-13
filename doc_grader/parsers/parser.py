"""Unified parser interface returning IR-oriented parse output."""

from __future__ import annotations

import codecs
import io
import logging
import re
import unicodedata
from typing import TYPE_CHECKING

import charset_normalizer
from docling_core.types.doc.base import (
    CoordOrigin,
)
from docling_core.types.doc.document import (
    PictureItem,
    SectionHeaderItem,
    TableCell,
    TableItem,
    TextItem,
)
from docling_core.types.doc.labels import DocItemLabel
from docling_core.types.io import DocumentStream
from pydantic import Field

from ..schemas.base import StrictModel
from ..schemas.finding import AnalyserInfo, Finding, HumanStatus, JudgeStatus
from ..schemas.ir import Document, DocumentRef
from ..utils import next_id

if TYPE_CHECKING:
    from pathlib import Path

    from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".md"}
SUPPORTED_LANGUAGES = {"cs", "sk", "en"}


def _detect_language(text: str) -> str:
    """Return a BCP-47 code ('cs', 'sk', 'en') for text.

    Returns 'en' when text is too short, ambiguous, or the top result is unsupported.
    """
    if not text or len(text.split()) < 20:
        return "en"
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        probs = detect_langs(text)
        top = probs[0]
        lang = top.lang if top.lang in SUPPORTED_LANGUAGES else "en"
        if lang != "en" and top.prob < 0.80:
            lang = "en"
        return lang
    except Exception:
        return "en"


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


def clean_pdf_text(text: str) -> str:
    """Normalise broken PDF-extracted Czech/Slovak diacritics.

    This function only applies deterministic repairs for Czech and Slovak
    letters when a spacing diacritic was extracted separately from its base
    letter, e.g. "ˇc" -> "č" or "´a" -> "á". It intentionally limits reordering
    to valid Czech/Slovak letter+diacritic combinations to avoid corrupting
    unrelated text in non-Czech/Slovak documents.

    What this fixes:
    - caron-based letters: č ď ě ň ř š ť ž
    - acute-based letters: á é í ý ó ú ĺ ŕ
    - ring-based letters: ů
    - diaeresis-based letters: ä
    - circumflex-based letters: ô
    - dotless ı extracted instead of i

    What is intentionally NOT fixed:
    - ľ/Ľ, including any apostrophe-like marks near other 'tall' letters
    - any ambiguous cases where multiple interpretations are possible

    In particular, ľ is often extracted as an apostrophe-like mark near "l"
    rather than as a true caron. Repairing that safely requires contextual
    heuristics and may introduce false positives in English or other text,
    so this function does not attempt it.
    """  # noqa: RUF002
    if not text:
        return text

    # Replace latin dotless ı with standard i  # noqa: RUF003
    text = text.replace("\u0131", "i")

    # Convert spacing diacritics commonly emitted by PDF extraction into
    # Unicode combining marks.
    text = text.replace("\u02c7", "\u030c")  # ˇ -> combining caron
    text = text.replace("\u00b4", "\u0301")  # ´ -> combining acute  # noqa: RUF003
    text = text.replace("\u02da", "\u030a")  # ˚ -> combining ring above
    text = text.replace("\u00a8", "\u0308")  # ¨ -> combining diaeresis
    text = text.replace("\u02c6", "\u0302")  # ˆ -> combining circumflex  # noqa: RUF003

    # Remove spaces immediately after combining marks.
    text = re.sub(r"([\u030C\u0301\u030A\u0308\u0302])\s+", r"\1", text)

    # Reorder only valid Czech/Slovak diacritic+letter combinations.

    # Caron: č ď ě ň ř š ť ž
    text = re.sub(r"(\u030C)([cCdDeEnNrRsStTzZ])", r"\2\1", text)

    # Acute: á é í ý ó ú ĺ ŕ
    text = re.sub(r"(\u0301)([aAeEiIyYoOuUlLrR])", r"\2\1", text)

    # Ring above: ů
    text = re.sub(r"(\u030A)([uU])", r"\2\1", text)

    # Diaeresis: ä
    text = re.sub(r"(\u0308)([aA])", r"\2\1", text)

    # Circumflex: ô
    text = re.sub(r"(\u0302)([oO])", r"\2\1", text)

    return unicodedata.normalize("NFC", text)


def _clean_md_image_src(src: str) -> str:
    """Normalise a Markdown image source string for local resolution."""
    from urllib.parse import unquote

    cleaned = src.strip()
    cleaned = unquote(cleaned)
    cleaned = cleaned.replace("\\", "/")
    return cleaned


def extract_md_image_uris(text: str) -> list[str]:
    """Extract ordered Markdown image URIs using markdown-it tokens."""
    if not text:
        logger.debug("Markdown image extraction skipped: empty input")
        return []

    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(text)

    uris: list[str] = []
    for token in tokens:
        if token.type != "inline" or not token.children:
            continue
        for child in token.children:
            if child.type != "image":
                continue
            src_attr = child.attrGet("src")
            src = str(src_attr) if src_attr is not None else ""
            cleaned = _clean_md_image_src(src)
            if cleaned:
                uris.append(cleaned)

    logger.debug("Extracted %d markdown image URI(s)", len(uris))
    return uris


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

        self.do_ocr = False
        self.do_table_structure = True

        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = self.do_ocr
        pdf_options.do_table_structure = self.do_table_structure
        pdf_options.generate_picture_images = True
        pdf_options.generate_page_images = True
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
        judge_status: JudgeStatus = "not_to_be_judged",
        human_status: HumanStatus = "proposed",
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
            judge_status=judge_status,
            human_status=human_status,
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
        logger.debug(
            "Parser error output: code=%s title=%s reason=%s source=%s",
            ac_code,
            title,
            error_msg,
            doc_ref.source_path,
        )

        finding = self._make_finding(
            doc_ref,
            ac_code,
            title,
            summary,
            run_id,
            config_hash,
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
        student_id: str | None = None,
    ) -> ParseOutput:
        """Parse the given document."""
        doc_ref = DocumentRef(source_path=str(path), student_id=student_id)
        suffix = path.suffix.lower()

        parse_meta = ParseMeta(
            used_ocr=self.do_ocr,
            table_structure=self.do_table_structure,
        )
        logger.debug("Parser start: path=%s suffix=%s", path, suffix)

        if not path.is_file():
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

        if suffix not in SUPPORTED_EXTENSIONS:
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

        findings: list[Finding] = []
        file_size = path.stat().st_size
        logger.debug("Parser input size: %d bytes", file_size)

        if file_size == 0:
            parse_meta.parsed_ok = True
            findings.append(
                self._make_finding(
                    doc_ref,
                    "EMPTY_FILE",
                    "Empty Document",
                    "File is 0 bytes.",
                    run_id,
                    config_hash,
                )
            )
            return ParseOutput(
                doc_ref=doc_ref,
                ir=None,
                parser_findings=findings,
                parse_meta=parse_meta,
            )

        try:
            logger.debug("Parsing %s with Docling...", path)
            md_image_uris: list[str] = []

            if suffix == ".md":
                raw_bytes = path.read_bytes()

                results = charset_normalizer.from_bytes(raw_bytes)
                best_match = results.best()
                encoding = best_match.encoding if best_match else "utf-8"

                logger.debug("Markdown decode encoding: %s", encoding)
                if not codecs.lookup(encoding).name == "utf-8":
                    findings.append(
                        self._make_finding(
                            doc_ref,
                            "DOCTYPE",
                            "Auto-detected Encoding",
                            f"Converted from {encoding} to UTF-8",
                            run_id,
                            config_hash,
                        )
                    )

                clean_text = raw_bytes.decode(encoding, errors="replace")
                md_image_uris = extract_md_image_uris(clean_text)
                logger.debug(
                    "Markdown extraction produced %d URI(s)", len(md_image_uris)
                )

                source = DocumentStream(
                    name=path.name,
                    stream=io.BytesIO(clean_text.encode("utf-8")),
                )
            else:
                source = path

            logger.debug("Docling conversion start")
            converted = self.converter.convert(source)
            doc = converted.document
            logger.debug("Docling conversion complete")

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

            words, chars, paras, headings, pictures = 0, 0, 0, 0, 0
            combined_text_parts: list[str] = []
            section_paths: dict[str, str] = {}
            paragraph_labels = {DocItemLabel.TEXT, DocItemLabel.PARAGRAPH}

            # heading_stack[i] has the heading text at depth i+1
            heading_stack: list[str] = []

            is_pdf = suffix == ".pdf"
            for item, _ in doc.iterate_items():
                prov_items = getattr(item, "prov", None)
                if prov_items:
                    for prov in prov_items:
                        if (
                            prov.bbox
                            and prov.bbox.coord_origin == CoordOrigin.BOTTOMLEFT
                        ):
                            page = doc.pages.get(prov.page_no)
                            if page and page.size and page.size.height:
                                prov.bbox = prov.bbox.to_top_left_origin(
                                    page_height=page.size.height
                                )

                if is_pdf:
                    if isinstance(item, TextItem) and item.text:
                        item.text = clean_pdf_text(item.text)

                    elif (
                        isinstance(item, TableItem)
                        and item.data
                        and item.data.table_cells
                    ):
                        for cell in item.data.table_cells:
                            if isinstance(cell, TableCell) and cell.text:
                                cell.text = clean_pdf_text(cell.text)

                if not isinstance(item, TextItem):  # does not add tables to text
                    if isinstance(item, PictureItem):
                        pictures += 1
                    continue

                if isinstance(item, SectionHeaderItem):
                    level = item.level
                    heading_text = (item.text or "").strip()
                    if heading_text:
                        heading_stack = heading_stack[: level - 1]
                        heading_stack.append(heading_text)
                        headings += 1
                elif item.label in paragraph_labels:
                    paras += 1

                if item.text and item.text.strip():
                    words += len(item.text.split())
                    chars += len(item.text)

                    cref = item.get_ref().cref
                    section_paths[cref] = " > ".join(heading_stack)
                    combined_text_parts.append(item.text)

            combined_text = " ".join(combined_text_parts)
            detected_language = _detect_language(combined_text)
            logger.debug("Detected document language: %r", detected_language)

            ir = Document(
                doc_ref=doc_ref,
                docling_doc=doc,
                total_words=words,
                total_chars=chars,
                total_paragraphs=paras,
                total_headings=headings,
                total_pictures=pictures,
                section_paths=section_paths,
                md_image_uris=md_image_uris,
                language=detected_language,
            )

            return ParseOutput(
                doc_ref=doc_ref,
                ir=ir,
                parser_findings=findings,
                parse_meta=parse_meta,
            )

        except Exception as e:
            logger.exception("Parser exception for %s", path)
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

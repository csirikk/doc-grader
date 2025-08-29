# Research Q8: Unified document representation for PDF and Markdown

**Research question:** What unified intermediate representation (IR) can reliably normalize PDF and Markdown documents while preserving structure, layout, and location for detectors?

## 1. Introduction

Technical reports for IFJ/IPP are submitted as `.pdf` and `.md`. Our detectors need consistent blocks (headings, paragraphs, lists, code, tables, figures) and precise **locations** (page, bbox, line/offset) for evidence highlighting. A single IR and a simple Python pipeline keep grading auditable and evaluation deterministic.

## 2. Main points

- **Unified IR:** `Document{meta, blocks[]}` with block types `Heading`, `Paragraph`, `List`, `CodeBlock`, `Quote`, `Table`, `Figure`.plus minimal inline tokens when needed.
- **Location:** Each block carries a `span` with `{source, page?, line_start?, line_end?, start_offset?, end_offset?, bbox?}`.
- **Assets:** Images/figures are extracted to files with `page`, `bbox`, and `hash`. Tables are structured when possible or flagged as `table_image` when not.
- **Tech stack:** Use `unstructured` for both PDF and MD, with helpers for images (PyMuPDF), tables (Camelot?/pdfplumber), and fine Markdown inlines (markdown-it-py). Use Pydantic v2 for IR model and JSON.

## 3. Possible approaches

### Approach A: Unstructured-centric [CHOSEN]

- **Process**:

1. **Partition** with `unstructured`
   - PDF: `partition_pdf`
   - MD: `partition_md` (or parse MD directly when fine inline marks are needed).
2. **Markdown enrichment** (MD only): run **markdown-it-py** to recover inline marks (bold/links/code) and compute line/byte offsets.
3. **PDF enrichment** (PDF only):
   - **Images/figures:** **PyMuPDF** to extract XObjects, record `page`, `bbox`, `hash`.
   - **Tables:** **Camelot** / **pdfplumber** fallback.
4. **Normalize -> IR:** map elements to blocks/inlines, attach `span`
5. **Serialize:** write IR JSON + assets; keep links to original files.
6. **Detectors:** run detectors over IR, output findings.
7. **UI/output:** resolve `span` back to exact page/lines/offsets to showcase relevant details.

- **Pros**: One API for both formats, Python-native, OCR included, preserves page/offset/bbox
- **Cons**: Table parsing may fail on borderless layouts, use confidence thresholds and fallback to `table_image`.

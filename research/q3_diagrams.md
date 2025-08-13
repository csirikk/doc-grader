# Research Q3: Detecting and evaluating diagrams and tables

**Research question:** How can the presence and quality of non-textual elements, such as diagrams and tables in PDF and Markdown documents, be reliably detected and evaluated?

## 1. Introduction

Technical documentation for projects in courses like IFJ and IPP often requires diagrams (class diagrams, FSMs, etc.) and structured tables. Manually verifying the presence and assessing the quality of these elements is time-consuming. This research explores automated methods to detect them, classify their type, and (optionally) assess quality.

## 2. Main points

- **Multiple formats:** Documents are submitted in both `.pdf` and `.md` formats. Markdown references external image files and has native text tables, PDFs embed images and render tables as positioned text or raster images.
- **Extraction:** Need robust image and table extraction (markdown image paths, markdown pipe tables, HTML tables, PDF image XObjects plus tables) without losing structure.
- **Diagrams vs non-diagrams:** Differentiate diagrams (class diagram, FSM) from screenshots of code, tables exported as images, logos, decorative icons.
- **Tables:** Distinguish true text tables (preferred, parseable) from table screenshots (image-only). Identify required tables (e.g., list of tokens, grammar rules). Flag when a required table exists only as an image.
- **Type identification:** Diagram classes: class, sequence, FSM/state, architecture, other. Table classes: token_table, grammar_table, test_matrix, other_table, table_image.
- **Quality (?):** Evaluating diagram/table quality is very hard. "Quality" can refer to correctness (does it accurately model the system? impossible without automated code analysis), completeness (does it include all required components?), and clarity (is it readable and well-formatted?).

## 3. Possible approaches

### Image and table detection (extraction)

Extraction is straightforward:

- **Markdown:**
  - Images: parse `![]()` patterns (markdown-it-py), resolve relative paths, hash.
  - Tables: detect pipe tables and HTML `<table>` blocks; normalize to CSV-like rows; metadata `{rows, cols, header_cells, text_hash}`.

- **PDF:**
  - Images: use `PyMuPDF` to iterate XObjects; retain page number, bbox.
  - Tables (text-based): apply a PDF table extractor (camelot, pdfplumber, tabula) on each page; heuristics: aligned text in grid, repeated vertical boundaries.
  - Table images: leftover large rectangular images with high line density and regular grid (Hough lines) but not captured by table parser.

Store unified element metadata: `{id, kind=diagram|table|table_image|image_other, source(page|path), page_no, bbox?, rows?, cols?, hash}`.

### Approach A: Local, open-source models (fine-tuned)

Use a pre-trained vision model fine-tuned on labeled image elements, parse markdown/PDF text tables separately.

- **Process:**
  1. Collect labeled dataset: {uml, fsm, code_screenshot, text_screenshot, decorative, table_image} + separate parsed text tables.
  2. Fine-tune model for image classes, merge with text-table parser.
- **Pros:** Privacy, predictable cost.
- **Cons:** Big dataset needed, separate handling for text tables. Unpredictable student designs.

### Approach B: API-based vision LLMs

Use vision API for image elements, parse markdown/PDF text tables separately.

- **Process:**
  1. Feed images to API with prompt requesting `{category, is_diagram, is_table_image, issues}`.
  2. Merge with text-table parser.
- **Pros:** Easy small dataset creation, quick prototype.
- **Cons:** Cost, latency. Reliance on prompt for distinguishing table images from diagrams.

### Approach C: Hybrid presence and type detection (no quality scoring)

Focus on required element presence (diagrams & required table categories) + basic type classification.

- **Process:**
  1. Extract images & text tables.
  2. Apply lightweight local classifier model / low-cost API prompt for image types.
  3. Map findings to required list: {class_diagram?, fsm_diagram?, token_table?, grammar_table?}.
  4. Flag missing images/tables.
- **Pros:** Objective, low annotation, easy user configuration.
- **Cons:** No feedback on quality.

## 4. AI generated comparison summary

| Approach               | Scope (diagrams + tables)    | Complexity | Cost        | Data need | Reproducibility | Quality depth | Primary risk        |
|------------------------|------------------------------|------------|-------------|-----------|-----------------|---------------|---------------------|
| A Local fine-tune      | Images + table_image         | Med/High   | Low runtime | Med/High  | High            | Low–Med       | Insufficient labels |
| B API vision LLM       | Images + table_image         | Very low   | High/call   | None      | Medium          | Medium        | Cost / drift        |
| C Hybrid presence-only | Presence/types + text tables | Low        | Low–Med     | Low       | High            | Low           | Limited feedback    |

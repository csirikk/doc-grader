# Tool overview

Helper for grading IFJ/IPP project documentation.

## 1. Motivation

Manual grading is slow and inconsistent.
The tool flags parts of the file which it thinks should affect the score negatively, explains why and suggests a point deduction. Optionally provides natural language feedback to the grader and/or student.

## 2. Typical flow

- Convert PDF to Markdown to paragraphs and extract assets (images, tables)
- Statically parse source code to extract entities (classes, functions, etc.)
- Run detectors, get list of findings `{code, evidence, confidence, location, ...}`
- Rule engine transforms findings into error codes
- Aggregate deductions and suggest score
- Generate reports

## 3. Inputs

| Item                  | Format                              | Notes              |
| --------------------- | ----------------------------------- | ------------------ |
| Student documentation | .pdf or .md                         | required           |
| Student source code   | .php, .py, etc.                     | optional, for diagram analysis |
| Project assignment    | .pdf or .md                         | optional, for copied spec text detection |
| Error-codes           | Based on assessment criteria, in list   | -                  |
| Course configuration  | IFJ vs IPP detector sets            | different penalties and requirements |
| Custom grading rules  | natural language/custom error codes | optional overrides |

## 4. Outputs

| For grader                                               | For student                                           |
| -------------------------------------------------------- | ----------------------------------------------------- |
| List of deductions                                       | Plain-text list of approved deductions and reasonings |
| Suggested total score and individual deduction weights   | Summary feedback                                      |
| Highlighted sections in UI (optional)                    | -                                                     |
| Batch error summaries, trends across projects (optional) | -                                                     |

## 5. Design overview

### Key components

1. **PDF/Markdown parser**
   - Converts input documents into a unified IR format of typed blocks (headings, paragraphs, lists, code blocks, quotes, tables, figures).
   - Markdown: uses markdown-it-py for tokenization, preserves line/byte offsets.
   - PDF: uses PyMuPDF for text/image extraction, preserves page numbers and bounding boxes.
2. **Source code parser**
   - Statically analyzes student source code to extract key entities (class names, function signatures, relationships).
   - This data provides ground truth for diagram and implementation-related detectors.
   - Status: Planned
3. **Local dataset** of past docs/code/assignments
   - For training/validation of models, few-shot examples for LLMs.
4. **Detectors**  
   - A suite of specialized modules that identify specific issues.
   - Each returns `{code, evidence, confidence, location, ...}`.
   - Current: LENGTH analyzer (too-short, too-long)
5. **Rule engine**  
   - Maps detector output to a code table.
   - Applies filtering (confidence threshold, deduplication).
   - Status: Basic
6. **Scoring + export** (JSON / plain text).
7. **CLI** prototype (GUI later).

### Detectors (WIP)

Automatically identify specific issues in student documentation. Each detector outputs `{code, evidence, confidence, location, ...}`.

**Implemented:**

| Detector                          | Code   | Approach                                                     | Status       |
|-----------------------------------|--------|--------------------------------------------------------------|--------------|
| Length/completeness               | LENGTH | Heuristics on word/paragraph counts and ratios               | Implemented  |

**Planned:**

| Detector                          | Code        | Approach                                                     | Status   |
|-----------------------------------|-------------|--------------------------------------------------------------|----------|
| Document structure                | STRUCT      | TBD                                                          | Planned  |
| Copied content                    | COPY        | SBERT embeddings vs specs? (TBD)                             | Planned  |
| Diagram Presence                  | NODIAGRAM   | Heuristic image and vector graphics extraction.              | Planned  |
| Table Presence                    | NOTABLE     | Parse Markdown tables and use PDF table extraction tools.    | Planned  |
| Diagram Quality                   | BADDIAGRAM  | Vision API to classify type and compare against source code. | Planned  |
| Table Quality                     | BADTABLE    | Vision API to classify type and compare against source code? | Planned  |
| Writing style                     | STYLE       | Multilingual LLM                                             | Planned  |
| Content appropriateness           | CONTENT     | Multilingual LLM                                             | Planned  |
| Generic Promptable                | CUSTOM      | single powerful LLM, custom prompt                           | Planned  |
| Language mixing                   | LANG        | cz/sk/en detection                                           | Planned  |
| Terminology                       | TERM        | Domain-specific, OOP focus for IPP                           | Planned  |
| Format compliance                 | FORMAT      | PDF/markdown requirements                                    | Planned  |

## Rule engine

Convert raw detector findings into actionable grading deductions. Inputs are `{code, evidence, confidence, location, ...}` + error code definitions -> output = `{deduction, weight, reason, ...}`. The system is unified, with a single rule engine that applies different configurations (enabled detectors, penalty weights) for both IPP and IFJ.

**Current implementation:** Basic filtering by confidence threshold (default 0.80) and deduplication by finding_id. Returns aggregated findings with summary statistics.

**Planned features:**

| Feature             | Possible approach                 | Notes                                 |
| ------------------- | --------------------------------- | ------------------------------------- |
| Mapping method      | Static YAML/JSON config           | Learned mapping out of scope for now? |
| Deduction weights   | Fixed vs. adaptive per doc?       | Allow per-project/ overrides.         |
| Thresholds          | Confidence cut-off per detector   | Manual tuning or learned thresholds?  |
| Conflict resolution | Deduplication logic               | One deduction per issue type?         |
| Grader overrides    | CLI flag / config file            | File-based override format?           |
| Batch scoring       | -                                 | Out of scope for now.                 |
| Explainability      | -                                 | Include evidence snippets in reports. |

- Possible feedback loop for tuning rule accuracy over time?

### Design diag

![Design v0.2](img/design_v0_2.png)

## 6. Design questions

- Local models vs. OpenAI API for detectors
- How to handle image/diagram/table checks
- Evaluation strategy. how to measure the accuracy and effectiveness of the detectors, and the final grading (precision/recall against manual grading)
- Security/privacy
- Handling different languages (cz/sk/en)
- Possibility of constraining the documentation specification to help the automated evaluation process.

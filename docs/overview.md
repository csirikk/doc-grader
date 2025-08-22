# Tool overview - v0.3 (21. 8. 2025)

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
| Error-codes           | Based on grading rubrics, in list   | -                  |
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
   - Converts input documents into a unified format of text paragraphs and extracted assets (images, tables).
2. **Source code parser**
   - Statically analyzes student source code to extract key entities (class names, function signatures, relationships).
   - This data provides ground truth for diagram and implementation-related detectors.
3. **Local dataset** of past docs/code/assignments
   - For training/validation of models, few-shot examples for LLMs.
4. **Detectors**  
   - A suite of specialized modules that identify specific issues.
   - Each returns `{code, evidence, confidence, location, ...}`.
5. **Rule engine**  
   - Maps detector output to a code table.
   - Applies default deduction, allows user override.
6. **Scoring + export** (JSON / plain text).
7. **CLI** prototype (GUI later).

### Detectors (WIP)

Automatically identify specific issues in student documentation. Each detector outputs `{code, evidence, confidence, location, ...}`.

| Detector                          | Approach                                                     |
|-----------------------------------|--------------------------------------------------------------|
| Document structure (STRUCT)       | TBD                                                          |
| Length/completeness (SHORT)       | TBD                                                          |
| Copied content (COPY)             | SBERT embeddings vs specs? (TBD)                             |
| Diagram Presence (NODIAGRAM)      | Heuristic image and vector graphics extraction.              |
| Table Presence (NOTABLE)          | Parse Markdown tables and use PDF table extraction tools.    |
| Diagram Quality (BADDIAGRAM)      | Vision API to classify type and compare against source code. |
| Table Quality (BADTABLE)          | Vision API to classify type and compare against source code? |
| Writing style (STYLE)             | Multilingual LLM                                             |
| Content appropriateness (CONTENT) | Multilingual LLM                                             |
| Generic Promptable (CUSTOM)       | single powerful LLM, custom prompt                           |
| Language mixing (LANG)            | cz/sk/en detection                                           |
| Terminology (TERM)                | Domain-specific, OOP focus for IPP                           |
| Format compliance (FORMAT)        | PDF/markdown requirements                                    |

## Rule engine

Convert raw detector findings into actionable grading deductions. Inputs are `{code, evidence, confidence, location, ...}` + error code definitions -> output = `{deduction, weight, reason, ...}`. The system is unified, with a single rule engine that applies different configurations (enabled detectors, penalty weights) for both IPP and IFJ.

| Feature             | Possibly approach                 | Notes                                 |
| ------------------- | --------------------------------- | ------------------------------------- |
| Mapping method      | Static YAML/JSON config           | Learned mapping out of scope for now? |
| Deduction weights   | Fixed vs. adaptive per doc?       | Allow per-project/ overrides.         |
| Thresholds          | Confidence cut-off per detector   | Manual tuning or learned threshorlds? |
| Conflict resolution | Deduplication logic               | One deduction per issue type?         |
| Grader overrides    | CLI flag / config file            | File-based override format?           |
| Batch scoring       | -                                 | Out of scope for now.                 |
| Explainability      | -                                 | Include evidence snippets in reports. |

- Possible feedback loop for tuning rule accuracy over time?

### Design diag

![Design (unchanged form v0.2)](img/design_v0_2.png)

## 6. Design questions

- Local models vs. OpenAI API for detectors
- How to handle image/diagram/table checks
- Evaluation strategy. how to measure the accuracy and effectiveness of the detectors, and the final grading (precision/recall against manual grading)
- Security/privacy
- Handling different languages (cz/sk/en)
- Possibility of constraining the documentation specification to help the automated evaluation process.

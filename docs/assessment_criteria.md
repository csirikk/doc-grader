# Detector -> Assessment Criterion Mapping

This document maps detector findings to assessment criteria used in IFJ/IPP project grading. Detectors are organized into categories for clarity in development.

## Assessment Criterion -> Detector Map

| AC                 | Detector -> Finding(s)                                                                                                                                                      | Scope | Notes                                         |
|--------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------|-----------------------------------------------|
| **DOCTYPE**        | DocumentInfoExtractor -> `wrong_doc_type`                                                                                                                                   | Both  | Expects PDF or Markdown                       |
| **FORMAT / FORM**  | DocumentInfoExtractor -> `format_violation`, TypographyAnalyzer -> `typography_violation`, CaptionAnalyzer -> `missing_caption` / `unreferenced_asset`                      | Both  | General layout & presentation                 |
| **STRUCT**         | StructureAnalyzer -> `poor_hierarchy` / `empty_section` / `heading_chain`, SectionAnalyzer -> `section_missing` / `section_misaligned`                                      | Both  | Document structure & organization             |
| **MISSING**        | DocumentInfoExtractor -> `document_missing`, SectionAnalyzer -> *all core sections absent*                                                                                  | Both  | Document or critical sections not provided    |
| **SHORT**          | LengthAnalyzer -> `too_short`                                                                                                                                               | Both  | Below minimum words/pages                     |
| **LONG**           | LengthAnalyzer -> `too_long`                                                                                                                                                | Both  | Above maximum pages                           |
| **LANG**           | LanguageAnalyzer **[LLM]** -> `mixed_languages` / `wrong_language`                                                                                                          | Both  | Improper language mixing (cs/sk/en)           |
| **CH / gram.**     | TextQualityAnalyzer **[LLM]** -> `spelling_errors` / `grammar_errors` / `punctuation_errors`                                                                                | Both  | Language mechanics                            |
| **MEZ**            | TextQualityAnalyzer **[LLM]** -> `spacing_errors`                                                                                                                           | Both  | Thin spaces, punctuation spacing              |
| **STYLE**          | TextQualityAnalyzer **[LLM]** -> `readability_low` / `convoluted_sentences` / `passive_voice_overuse`                                                                       | Both  | Unclear or poor writing style                 |
| **FILO**           | TextQualityAnalyzer **[LLM]** -> `philosophical` / `hand_wavy`                                                                                                              | Both  | Vague, non-concrete content                   |
| **HOV**            | TextQualityAnalyzer **[LLM]** -> `colloquial_language`                                                                                                                      | Both  | Informal, conversational tone                 |
| **TERM**           | TerminologyAnalyzer **[EMBEDDING+LLM]** -> `term_misuse` / `term_inconsistency`                                                                                             | Both  | Incorrect/inconsistent technical terms        |
| **CONTENT**        | SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic` / `section_superficial`, PlagiarismAnalyzer **[EMBEDDING+LLM]** -> `spec_copied`                           | Both  | Content relevance & appropriateness           |
| **COPY**           | PlagiarismAnalyzer **[EMBEDDING+LLM]** -> `spec_copied_uncited`                                                                                                             | Both  | Plagiarism from assignment spec               |
| **BIB / REFS**     | CitationAnalyzer -> `references_missing` / `citations_missing` / `broken_refs`                                                                                              | Both  | Bibliography & citation hygiene               |
| **1. STRANA**      | MetadataExtractor -> `header_missing:ifj`                                                                                                                                   | IFJ   | Mandatory first-page metadata (IFJ)           |
| **HEADER_MISSING** | MetadataExtractor -> `header_missing:ipp`                                                                                                                                   | IPP   | Mandatory header metadata (IPP)               |
| **BLOK**           | TypographyAnalyzer -> `not_block_justified`                                                                                                                                 | Both  | Block justification requirement               |
| **SAZBA**          | TypographyAnalyzer -> `typography_violation` / `code_not_monospace`                                                                                                         | Both  | Typesetting rules                             |
| **typ.**           | TypographyAnalyzer -> `typography_violation:minor`                                                                                                                          | Both  | Minor typography issues                       |
| **KAPTXT**         | StructureAnalyzer -> `heading_chain`                                                                                                                                        | Both  | Consecutive headings without content          |
| **KA**             | DiagramAnalyzer **[VISION+OCR]** -> `automaton_missing` / `automaton_incorrect` / `automaton_unreadable`                                                                    | IFJ   | Finite automaton diagram (lexer)              |
| **LL / LLT**       | TableAnalyzer **[VISION+LLM]** -> `ll_table_missing` / `ll_table_incorrect`                                                                                                 | IFJ   | LL(1) parsing table                           |
| **PT**             | TableAnalyzer **[VISION+LLM]** -> `precedence_table_missing` / `precedence_table_incorrect`                                                                                 | IFJ   | Precedence table                              |
| **SA / SAV / SéA** | SectionAnalyzer -> `section_missing:syntax_analysis`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:syntax_analysis`                                      | IFJ   | Syntax analysis section                       |
| **PSA**            | SectionAnalyzer -> `section_missing:precedence_analysis`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:precedence_analysis`                              | IFJ   | Precedence syntax analysis                    |
| **TS**             | SectionAnalyzer -> `section_missing:lexer`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:lexer`                                                          | IFJ   | Lexical analyzer (scanner) section            |
| **GK**             | SectionAnalyzer -> `section_missing:error_handling`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:error_handling`                                        | IFJ   | Error handling section                        |
| **RP**             | SectionAnalyzer -> `section_missing:team_work`                                                                                                                              | IFJ   | Division of work section                      |
| **UML / NOUML**    | DiagramAnalyzer **[VISION+OCR]** -> `uml_missing` / `uml_incomplete`                                                                                                        | IPP   | UML class diagram                             |
| **BADUML**         | DiagramAnalyzer **[VISION+OCR]** -> `uml_unreadable` / `uml_incorrect` / `uml_inconsistent`                                                                                 | IPP   | Poor quality UML                              |
| **IR**             | SectionAnalyzer -> `section_missing:internal_representation`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:internal_representation`                      | IPP   | Internal representation section               |
| **JAK**            | SectionAnalyzer -> `section_missing:implementation`, SectionContentAnalyzer **[EMBEDDING+LLM]** -> `section_offtopic:implementation` / `section_superficial:implementation` | IPP   | Implementation description ("jak to funguje") |
| **MDLINES**        | TypographyAnalyzer -> `markdown_line_length_exceeded`                                                                                                                       | IPP   | Markdown line length violations               |

---

## Detectors

### 1: EXTRACTION

Extractors use heuristic techniques to pull structured data from documents.

#### 1. DocumentInfoExtractor

- **Purpose**: Extract file metadata and validate document type
- **Inputs**: File path, type, IR root
- **Outputs**:
  - Document type (PDF/MD), page count, file size
  - Findings: `wrong_doc_type`, `format_violation`, `document_missing`

#### 2. StructureAnalyzer

- **Purpose**: Analyze document structure
- **Inputs**: IR blocks (headings, paragraphs)
- **Outputs**:
  - Section boundaries, TOC, heading hierarchy
  - Findings: `poor_hierarchy`, `empty_section`, `heading_chain`

#### 3. LengthAnalyzer

- **Purpose**: Calculate document metrics and detect length issues
- **Inputs**: IR blocks
- **Outputs**:
  - Word counts, paragraph counts, averages
  - Findings: `too_short`, `too_long`

#### 4. MetadataExtractor

- **Purpose**: Extract and validate first-page/header metadata
- **Inputs**: First N blocks from IR
- **Outputs**:
  - Student name, login, course, project title
  - Findings: `header_missing:ifj`, `header_missing:ipp`
- **Method**: Regex patterns for required fields, course-specific templates

**Notes**:

- Tolerant regex
- multiple pattern variants

---

### 2: VISUAL ANALYSIS

Process all images/tables.

#### 5. DiagramAnalyzer **[VISION+OCR]**

- **Purpose**: Identify, classify, and validate diagrams (finite automaton for IFJ, UML for IPP)
- **Inputs**: Figure blocks from IR, extracted images, pdf
- **AI Components**:
  - **Vision Model**: Classify diagram type
  - **OCR**: Extract text from diagram for validation, later check in code
- **Outputs**:
  - Diagram inventory with types
  - **IFJ findings**: `automaton_missing`, `automaton_incorrect`, `automaton_unreadable`
  - **IPP findings**: `uml_missing`, `uml_incomplete`, `uml_unreadable`, `uml_incorrect`, `uml_inconsistent`
- **Method**:

 1. Vision model classifies each figure
 2. OCR extracts text (state names, class names, methods)
 3. Heuristic validation (e.g., UML must have classes with attributes/methods)
 4. Context validation: caption mentions "automat", "UML" or other relevant terms?

- Require multiple signals (vision + OCR or vision + caption)

#### 6. TableAnalyzer **[VISION+LLM]**

- **Purpose**: Identify and validate tables (LL/precedence for IFJ, general quality for both)
- **Inputs**: Table blocks from IR, rendered table images (for PDF)
- **AI Components**:
  - **Vision Model**: Extract table structure if PDF (row/column detection)
  - **LLM**: Classify table type and validate correctness
- **Outputs**:
  - Table inventory with types
  - **IFJ findings**: `ll_table_missing`, `ll_table_incorrect`, `precedence_table_missing`, `precedence_table_incorrect`
  - **Both courses**: `table_unreadable`, `table_formatting_poor`
- **Method**:

 1. Extract table as structured data (CSV-like)
 2. LLM identifies if table is LL, precedence, or other
 3. For LL/precedence: LLM validates structure
 4. Quality checks: font size, alignment, header clarity
 Might require header keywords

#### 7. CaptionAnalyzer

- **Purpose**: Validate figure/table captions and cross-references
- **Inputs**: Figures, tables, surrounding text from IR
- **Outputs**:
  - Caption coverage metrics
  - Findings: `missing_caption`, `unreferenced_asset`, `caption_vague`
- **Method**:

 1. Check each figure/table has caption
 2. Search running text for references ("figure 1", "table 2")

**Notes**:

- Allow figures without captions if referenced inline?

---

### 3: TEXT ANALYSIS

Analyze text content with AI models.

#### 8. LanguageAnalyzer **[LLM]**

- **Purpose**: Detect language mixing and enforce language policy
- **Inputs**: Paragraph blocks from IR
- **AI Components**:
  - **FastText?**: Fast paragraph-level language ID (cs/sk/en)
  - **LLM**: Disambiguate mixed or ambiguous paragraphs
- **Outputs**:
  - Language distribution per paragraph
  - Findings: `mixed_languages`, `wrong_language`
- **Method**:

 1. FastText classifies each paragraph
 2. Calculate mixing percentage and switch frequency
 3. LLM reviews paragraphs with ambiguous/mixed detection

**Notes**:

- Allow English technical terms?
- Skip code blocks and quotes

#### 9. TextQualityAnalyzer **[LLM]**

- **Purpose**: Holistic text quality analysis (grammar, style, readability, tone)
- **Inputs**: Paragraph and sentence blocks
- **AI Components**:
  - **LLM**: Multi-aspect text quality scorer
- **Outputs**:
  - Quality scores per section/paragraph
  - Findings: `spelling_errors`, `grammar_errors`, `punctuation_errors`, `spacing_errors`, `readability_low`, `convoluted_sentences`, `passive_voice_overuse`, `philosophical`, `hand_wavy`, `colloquial_language`, ....
- **Method**:

- LLM evaluates each paragraph/section with an assessment prompt:

 1. Grammar (spelling, punctuation, ...)
 2. Readability
 3. Style (formality, concreteness, technical precision)

- Extract structured scores and specific error locations
- Aggregate findings by severity

**Notes**:

- Skip code blocks and quotes
- Whitelist technical vocabulary

#### 10. TypographyAnalyzer

- **Purpose**: Validate typography and formatting rules
- **Inputs**: IR with style metadata (fonts, spacing), PDF font info, MD fence markers, linter rules?
- **Outputs**:
  - Typography compliance metrics
  - Findings: `typography_violation`, `code_not_monospace`, `not_block_justified`, `markdown_line_length_exceeded`
- **Method**:
TBD

#### 11. SectionAnalyzer

- **Purpose**: Ensure required sections exist with appropriate content
- **Inputs**: Section boundaries from StructureAnalyzer, configurable
- **Outputs**:
  - Section inventory
  - Findings: `section_missing:*` (where * = section type like syntax_analysis, lexer, etc.)
- **Method**:

 1. Load required sections list (course-specific)
 2. Match headings to expected sections using synonym lists
 3. Flag missing sections

#### 12. SectionContentAnalyzer **[EMBEDDING+LLM]**

- **Purpose**: Validate that sections actually discuss expected topics (not just titled correctly)
- **Inputs**: Section text from SectionAnalyzer
- **AI Components**:
  - **SBERT**: Measure semantic similarity to reference content
  - **LLM**: Evaluate content substantiveness and topicality
- **Outputs**:
  - Content quality scores per section
  - Findings: `section_offtopic:*`, `section_superficial:*`
- **Method**:

 1. **Shortlisting**: SBERT compares section embeddings to reference exemplars (good syntax analysis sections from past years)
 2. **LLM Validation**: For low-similarity sections, prompt:

- Is content on-topic for this section?
- Is discussion substantive (not just bullet points)?
- Are key concepts covered?

**Notes**:

- Run after SectionAnalyzer
- Multiple reference examples per section type
- Confidence threshold for flagging
- Run SBERT on all sections, only invoke LLM for low scores.

#### 13. TerminologyAnalyzer **[EMBEDDING+LLM]**

- **Purpose**: Validate correct and consistent use of technical terminology
- **Inputs**: Extracted term candidates, domain glossary
- **AI Components**:
  - **SBERT**: Measure semantic similarity to canonical term definitions
  - **LLM**: Adjudicate context-dependent term usage
- **Outputs**:
  - Terminology usage report
  - Findings: `term_misuse`, `term_inconsistency`
- **Method**:

 1. Extract terminology candidates (NER or pattern matching)
 2. SBERT: Compare usage context to canonical definitions
 3. Detect inconsistencies (same concept, different terms)
 4. LLM: Evaluate contested cases (e.g., is "parser" vs "syntaktický analyzátor" acceptable?)

#### 14. PlagiarismAnalyzer **[EMBEDDING+LLM]**

- **Purpose**: Detect copying from assignment specification without citation. No inter student comparisons for now.
- **Inputs**: Student document chunks, assignment spec text
- **AI Components**:
  - **SBERT**: Find semantically similar chunks
  - **MinHash** (optional): Fast n-gram similarity screening
  - **LLM**: Distinguish citation vs. plagiarism
- **Outputs**:
  - Similarity scores per chunk
  - Findings: `spec_copied`
- **Method**:

 1. Chunk both documents (paragraph-level)
 2. SBERT: Find high-similarity pairs (high threshold)
 3. LLM: For each high-similarity pair, prompt:

- Is this properly cited/quoted?
- Is this paraphrased copying?
- Is this legitimate restatement of requirements?

**Notes**:

- Allow short quoted prompts with citation
- Ignore boilerplate (headings, standard phrases)

#### 15. CitationAnalyzer

- **Purpose**: Validate bibliography and citation hygiene
- **Inputs**: Bibliography section, citation markers in text
- **Outputs**:
  - Citation coverage metrics
  - Findings: `references_missing`, `citations_missing`, `broken_refs`
- **Method**:

 1. Detect bibliography section
 2. Extract citation markers ([1], \cite{}, etc.)
 3. Check each reference is cited, each citation has reference
 4. Validate URL/DOI accessibility (optional)

#### 16. CustomLLMEvaluator **[LLM]**

- **Purpose**: Ad-hoc evaluation with user-defined prompts
- **Inputs**: Grader-provided prompt + selected document sections
- **AI Components**:
  - **LLM**: Flexible few-shot evaluation
- **Outputs**:
  - Custom findings based on prompt
  - Findings: `custom:*` (mapped by RuleEngine)
- **Method**:

 1. Grader provides natural language assessment criteria
 2. LLM evaluates document with few-shot examples
 3. Return structured assessment

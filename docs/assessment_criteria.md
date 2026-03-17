# Analyser -> Assessment Criterion Mapping

This document maps Analyser findings to assessment criteria used in IFJ/IPP project grading. Analysers are organized into categories for clarity in development.

## Assessment Criterion -> Analyser Map

| AC            | Analyser           | Scope | Notes                                                                  |
|---------------|--------------------|-------|------------------------------------------------------------------------|
| **DOCTYPE**   | *parser*           | Both  | Not a PDF/MD / unreadable / wrong doc type                             |
| **FORMAT**    | *parser*           | Both  | Mechanically checkable submission constraints                          |
| **MISSING**   | *parser*           | Both  | Missing document                                                       |
| **STRUCT**    | StructureAnalyser  | IPP   | Insufficient document structure                                        |
| **strukt.**   | StructureAnalyser  | IFJ   | Insufficient document structure                                        |
| **SHORT**     | StructureAnalyser  | Both  | Too short overall (uses parser metrics)                                |
| **KAPTXT**    | StructureAnalyser  | Both  | Consecutive headings without content                                   |
| **1. strana** | StructureAnalyser  | IFJ   | Missing information on the first page                                  |
| **FORM**      | TypographyAnalyser | Both  | Bad visual formatting/polish (typography + captions/assets)            |
| **PRED**      | TypographyAnalyser | IPP   | One-letter prepositions at end of line                                 |
| **BLOK**      | TypographyAnalyser | Both  | Align-left instead of justified text                                   |
| **SAZBA**     | TypographyAnalyser | Both  | Insufficient typesetting                                               |
| **typ.**      | TypographyAnalyser | IFJ   | General typography issues                                              |
| **MDLINES**   | TypographyAnalyser | IPP   | Incorrect markdown paragraph line break formatting                     |
| **MEZ**       | TypographyAnalyser | Both  | Incorrect whitespace usage (around brackets)                           |
| **LANG**      | TextAnalyser       | Both  | Language mixing (cs/sk/en)                                             |
| **CH**        | TextAnalyser       | IPP   | Spelling/grammar mistakes                                              |
| **gram.**     | TextAnalyser       | IFJ   | Grammar mistakes                                                       |
| **ICH**       | TextAnalyser       | IPP   | First-person singular usage                                            |
| **TERM**      | TextAnalyser       | IPP   | Incorrect technical terms                                              |
| **term.**     | TextAnalyser       | IFJ   | Incorrect technical terms                                              |
| **COPY**      | IntegrityAnalyser  | IPP   | Copied/uncited text (spec/internet/other students)                     |
| **NOUML**     | AssetAnalyser      | IPP   | UML class diagram missing                                              |
| **BADUML**    | AssetAnalyser      | IPP   | Syntax errors, missing methods/interactions, or auto-generated garbage |
| **OWNDIF**    | AssetAnalyser      | IPP   | Diagram does not distinguish own vs library classes                    |
| **BW**        | AssetAnalyser      | IPP   | Dark-background diagram pasted into light doc                          |
| **LLT**       | AssetAnalyser      | IFJ   | Missing/insufficient LL table (incomplete coverage, ...)               |
| **LL**        | AssetAnalyser      | IFJ   | Errors in the LL table                                                 |
| **PT**        | AssetAnalyser      | IFJ   | Errors in precedence table                                             |
| **KA**        | AssetAnalyser      | IFJ   | Errors within FSM                                                      |
| **CONTENT**   | ContentAnalyser    | IPP   | Sections off-topic (time, feelings, subjectivity)                      |
| **SA**        | ContentAnalyser    | IFJ   | Insufficient syntax analysis description                               |
| **SAV**       | ContentAnalyser    | IFJ   | Insufficient expression parsing description                            |
| **SéA**       | ContentAnalyser    | IFJ   | Insufficient semantic analysis description                             |
| **PSA**       | ContentAnalyser    | IFJ   | Insufficient precedence syntax analysis description                    |
| **TS**        | ContentAnalyser    | IFJ   | Insufficient symbol table description                                  |
| **GK**        | ContentAnalyser    | IFJ   | Insufficient code generation description                               |
| **RP**        | ContentAnalyser    | IFJ   | Division of work section                                               |
| **IR**        | ContentAnalyser    | IPP   | Insufficient internal representation description                       |
| **JAK**       | ContentAnalyser    | IPP   | Insufficient implementation description                                |
| **NVPDOC**    | ContentAnalyser    | IPP   | NVP extension doc missing                                              |
| **STYLE**     | StyleAnalyser      | Both  | Unclear or poor writing style                                          |
| **HOV**       | StyleAnalyser      | Both  | Informal, conversational, slang words                                  |
| **NOOOP**     | DesignAnalyser     | IPP   | Code ignores OOP; functions merely wrapped in classes                  |
| **OOP**       | DesignAnalyser     | IPP   | Bonus when OOP usage is meaningful and well described                  |
| **NOSRP**     | DesignAnalyser     | IPP   | Violation of Single Responsibility Principle                           |
| **DP**        | DesignAnalyser     | IPP   | Bonus for good and well justified pattern usage                        |
| **BADDP**     | DesignAnalyser     | IPP   | Inappropriate use or bad implementation of a design pattern            |
| **SINGLETON** | DesignAnalyser     | IPP   | Singleton explicitly disallowed for NVP                                |
| **EXT**       | DesignAnalyser     | IPP   | Insufficient extensibility description                                 |
| **EX**        | DesignAnalyser     | IPP   | Bonus for particularly clean exception usage                           |
| **FILO**      | DesignAnalyser     | IPP   | Missing/insufficient design philosophy                                 |

## Analysers

### 1. StructureAnalyser

Document-level structural presence and completeness checks. Replaces the structural half of the old SectionAnalyser.

**ACs**:

- legacy: *STRUCT*, *strukt.*, *SHORT*, *KAPTXT*, *1. strana*

Ideas

- regex/similarity match against required headings list
- consecutive headings without content check
- analyse metrics for shortness (word count, char count, paragraph count)

### 2. ContentAnalyser

LLM-based content analyser. Technical adequacy and topical relevance of sections. Required domain topics presence and their content. Handles all required-section codes and off-topic penalties.

**ACs**:

- legacy: *CONTENT*, *SA*, *SAV*, *SéA*, *PSA*, *TS*, *GK*, *RP*, *IR*, *JAK*, *NVPDOC*

Ideas

need: 1. section presence check, 2. section content adequacy

- heuristic filter first? (čas, pocity, bavilo mě, já, etc.)
- then LLM check for content adequacy

### 3. TypographyAnalyser

Presentation geometry, canonical layout, PDF visual stylistic elements / markdown lint. Mechanical typography/layout checks (PDF + Markdown). Includes whitespace mechanics (MEZ) as a deterministic text-layer check.

**ACs**:

- legacy: *FORM*, *BLOK*, *SAZBA*, *MEZ*, *typ.*, *PRED*, *MDLINES*

Ideas

- deterministic *MEZ*, *MDLINES*
- deterministic EOL prepositions in tokens
- BLOK: right margin raggeddness, variance of line end x-coordinates?
- *typ.*, *SAZBA*, *FORM* general typograpghy rules
  - come up with heuristics for bbox gaps, fonts, md lint?
  - or offload to LLM...

### 4. TextAnalyser

LLM-based text analyser. Deterministic, objective aim, proofreading. Mostly objective deterministic checks: language detection, grammar, and terminology. Writing mechanics only; style and tone live in StyleAnalyser.

**ACs**:

- legacy: *LANG*, *CH*, *gram.*, *ICH*, *TERM*, *term.*

Ideas

- *LANG* langdetect -> bert
- regex for *ICH*
- grammar check tools for *CH*, *gram.*

### 5. IntegrityAnalyser

Authorship info presence and integrity checks around copied/uncited content, from spec only for now.

**ACs**:

- legacy: *COPY*

Ideas

- embed -> cosine similiarity?
- shingles -> jaccard similiarity?

### 6. AssetAnalyser

Figure/table inventory + presence/readability/suitability checks. Covers both UML diagrams (IPP) and formal automata/table assets (IFJ).

**ACs**:

- legacy: *NOUML*, *BADUML*, *OWNDIF*, *BW*, *LLT*, *LL*, *PT*, *KA*

Ideas

need: 1. presence, quality, semantic correctness?

- images, image type, captions extracted
- vision llm for general quality

### 7. StyleAnalyser

LLM-based writing style analyser. Nuanced, subjective aim, editorial. General writing style, clarity, and tone. LLM-backed; heuristic pre-filter to reduce inference cost.

**ACs**:

- legacy: *STYLE*, *HOV*

Ideas

- heuristic filter, llm

### 8. DesignAnalyser

LLM-based design analyser. Architecture, OOP principles. Quality of what is written from a design perspective. Object-oriented design quality and pattern usage. Evaluates architectural decisions described in the text, not source code directly.

**ACs**:

- legacy: *OOP*, *NOOOP*, *NOSRP*, *DP*, *BADDP*, *SINGLETON*, *EXT*, *EX*, *FILO*

Ideas

- heuristic keyword scan for explicit OOP/pattern mentions
- LLM check for design quality and SRP adherence
- *SINGLETON* deterministic regex: flag any mention of Singleton pattern

### 9. CustomAnalyser

Ad-hoc prompt-based checks isolated from deterministic scoring.

**ACs**:

- *custom:...*

Ideas

- llm model with custom prompt?

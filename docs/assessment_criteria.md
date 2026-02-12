# Analyser -> Assessment Criterion Mapping

This document maps Analyser findings to assessment criteria used in IFJ/IPP project grading. Analysers are organized into categories for clarity in development.

## Assessment Criterion -> Analyser Map

| AC            | Analyser           | Scope | Notes                                                                  |
|---------------|--------------------|-------|------------------------------------------------------------------------|
| **DOCTYPE**   | *parser*           | Both  | Not a PDF/MD / unreadable / wrong doc type                             |
| **FORMAT**    | *parser*           | Both  | Mechanically checkable submission constraints                          |
| **FORM**      | TypographyAnalyser | Both  | Bad visual formatting/polish (typography + captions/assets)            |
| **STRUCT**    | SectionAnalyser    | IPP   | Insufficient document structure                                        |
| **strukt.**   | SectionAnalyser    | IFJ   | Insufficient document structure                                        |
| **MISSING**   | *parser*           | Both  | Missing document                                                       |
| **SHORT**     | SectionAnalyser    | Both  | Too short overall (uses parser metrics)                                |
| **LANG**      | TextAnalyser       | Both  | Language mixing (cs/sk/en)                                             |
| **CH**        | TextAnalyser       | IPP   | Spelling/grammar mistakes                                              |
| **gram.**     | TextAnalyser       | IFJ   | Grammar mistakes                                                       |
| **MEZ**       | TextAnalyser       | Both  | Incorrect whitespace usage (around brackets)                           |
| **PRED**      | TypographyAnalyser | IPP   | One-letter prepositions at end of line                                 |
| **ICH**       | TextAnalyser       | IPP   | First-person singular usage                                            |
| **STYLE**     | TextAnalyser       | Both  | Unclear or poor writing style                                          |
| **FILO**      | TextAnalyser       | IPP   | Missing/insufficient design philosophy                                 |
| **HOV**       | TextAnalyser       | Both  | Informal, conversational, slang words                                  |
| **TERM**      | TextAnalyser       | IPP   | Incorrect technical terms                                              |
| **term.**     | TextAnalyser       | IFJ   | Incorrect technical terms                                              |
| **CONTENT**   | SectionAnalyser    | IPP   | Sections off-topic (time, feelings, subjectivity)                      |
| **COPY**      | IntegrityAnalyser  | IPP   | Copied/uncited text (spec/internet/other students)                     |
| **1. strana** | SectionAanlyser    | IFJ   | Missing information on the first page                                  |
| **BLOK**      | TypographyAnalyser | Both  | Align-left instead of justified text                                   |
| **SAZBA**     | TypographyAnalyser | Both  | Insufficient typesetting                                               |
| **typ.**      | TypographyAnalyser | IFJ   | General typography issues                                              |
| **KAPTXT**    | SectionAnalyser    | Both  | Consecutive headings without content                                   |
| **KA**        | AssetAnalyser      | IFJ   | Errors within FSM                                                      |
| **LLT**       | AssetAnalyser      | IFJ   | Missing/insufficient LL table (incomplete coverage, ...)               |
| **LL**        | AssetAnalyser      | IFJ   | Errors in the LL table                                                 |
| **PT**        | AssetAnalyser      | IFJ   | Errors in precedence table                                             |
| **SA**        | SectionAnalyser    | IFJ   | Insufficient syntax analysis description                               |
| **SAV**       | SectionAnalyser    | IFJ   | Insufficient expression parsing description                            |
| **SéA**       | SectionAnalyser    | IFJ   | Insufficient semantic analysis description                             |
| **PSA**       | SectionAnalyser    | IFJ   | Insufficient precedence syntax analysis description                    |
| **TS**        | SectionAnalyser    | IFJ   | Insufficient symbol table description                                  |
| **GK**        | SectionAnalyser    | IFJ   | Insufficient code generation description                               |
| **RP**        | SectionAnalyser    | IFJ   | Division of work section                                               |
| **NOUML**     | AssetAnalyser      | IPP   | UML class diagram missing                                              |
| **BADUML**    | AssetAnalyser      | IPP   | Syntax errors, missing methods/interactions, or auto-generated garbage |
| **OWNDIF**    | AssetAnalyser      | IPP   | Diagram does not distinguish own vs library classes                    |
| **BW**        | AssetAnalyser      | IPP   | Dark-background diagram pasted into light doc                          |
| **NOOOP**     | AssetAnalyser      | IPP   | Code ignores OOP; functions merely wrapped in classes                  |
| **NOSRP**     | AssetAnalyser      | IPP   | Violation of Single Responsibility Principle                           |
| **BADDP**     | AssetAnalyser      | IPP   | Inappropriate use or bad implementation of a design pattern            |
| **EXT**       | SectionAnalyser    | IPP   | Insufficient extensibility description                                 |
| **IR**        | SectionAnalyser    | IPP   | Insufficient internal representation description                       |
| **JAK**       | SectionAnalyser    | IPP   | Insufficient implementation description                                |
| **MDLINES**   | TypographyAnalyser | IPP   | Incorrect markdown paragraph line break formatting                     |
| **OOP**       | SectionAnalyser    | IPP   | Bonus when OOP usage is meaningful and well described                  |
| **EX**        | SectionAnalyser    | IPP   | Bonus for particularly clean exception usage                           |
| **DP**        | SectionAnalyser    | IPP   | Bonus for good and well justified pattern usage                        |
| **NVPDOC**    | SectionAnalyser    | IPP   | NVP extension doc missing                                              |
| **SINGLETON** | TextAnalyser       | IPP   | Singleton explicitly disallowed for NVP                                |

## Analysers

### 1. IntegrityAnalyser

Authorship info presence and integrity checks around copied/uncited content, from spec only for now.

**ACs**:

- legacy: *COPY*

Ideas

- embed -> cosine similiarity?
- shingles -> jaccard similiarity?

### 2. SectionAnalyser

Structure/section presence and section-level content adequacy. Section specific relevance to t.

**ACs**:

- legacy: *STRUCT*, *strukt.*, *KAPTXT*, required section codes (*KA*, *SA*, *SAV*, *SéA*, *PSA*, *TS*, *GK*, *RP*, *EXT*, *IR*, *JAK*, *NVPDOC*), *CONTENT*, *SHORT*

Ideas

need: 1. structure check, 2. section content check

- regex/similarity required headings
- consecutive headings without content check
- analyse metrics for shortness
- content:
  - heuristic filter first? (čas, pocity, bavilo mě, já, etc.)
  - then LLM check for content adequacy

### 3. TypographyAnalyser

Presenetation geometry, canonical layout, pdf visual stylistic elements / markdown lint. Mechanical typography/layout checks (PDF + Markdown).

**ACs**:

- legacy: *FORM*, *BLOK*, *SAZBA*, *MEZ*, *typ.*, *PRED*, *MDLINES*

Ideas

- deterministic *MEZ*, *MDLINES*
- deterministic EOL prepositions in tokens
- BLOK: right margin raggeddness, variance of line end x-coordinates?
- *typ.*, *SAZBA*, *FORM* general typograpghy rules
  - come up with heuristics for bbox gaps, fonts, md lint?
  - or offload to LLM...

### 4. AssetAnalyser

Figure/table inventory + presence/readability/suitability checks.

**ACs**:

- legacy: *NOUML*, *BADUML*, *OWNDIF*, *BW*, *NOOOP*, *LLT*, *LL*, *PT*

Ideas

need: 1. presence, quality, semantic correctness?

- images, image type, captions extracted
- vision llm for general quality

### 5. TextAnalyser

Mostly objective deterministic checks: Language mixing + writing mechanics + terminology.

**ACs**:

- legacy: *LANG*, *CH*, *gram.*, *ICH*, *TERM*, *term.*, *SINGLETON*

Ideas

- *LANG* langdetect -> bert
- whitespace regex
- regex
- grammar check tools

### 6. StyleAnalyser

General writing style and clarity.
**ACs**:

- legacy: *STYLE*, *FILO*, *HOV*,

Ideas

- heuristic filter, llm

### 7. CustomAnalyser

Ad-hoc prompt-based checks isolated from deterministic scoring.

**ACs**:

- *custom:...*

Ideas

- llm model with custom prompt?

# Detector to rubric code Map

TODO: change "rubric code" terminology to "assessment criterion"

| Rubric Code | Detector -> Finding | Notes |
|-------------|---------------------|-------|
| 1. strana   |                     |       |
| AUTHOR      |                     |       |
| BADDP       |                     |       |
| BADUML      |                     |       |
| BLOK        |                     |       |
| BW          |                     |       |
| CH          |                     |       |
| COMMENT     |                     |       |
| CONTENT     |                     |       |
| COPY        |                     |       |
| DECOMPOSE   |                     |       |
| DOCTYPE     |                     |       |
| DP          |                     |       |
| EX          |                     |       |
| EXT         |                     |       |
| FILO        |                     |       |
| FORM        |                     |       |
| FORMAT      |                     |       |
| GK          |                     |       |
| HOV         |                     |       |
| ICH         |                     |       |
| IR          |                     |       |
| JAK         |                     |       |
| KA          |                     |       |
| KAPTXT      |                     |       |
| LANG        |                     |       |
| LL          |                     |       |
| LLT         |                     |       |
| MISSING     |                     |       |
| MDLINES     |                     |       |
| MEZ         |                     |       |
| NOSRP       |                     |       |
| NOOOP       |                     |       |
| NOOP        |                     |       |
| NOUML       |                     |       |
| NVPDOC      |                     |       |
| NVP         |                     |       |
| OOP         |                     |       |
| OK          |                     |       |
| OWNDIF      |                     |       |
| PRED        |                     |       |
| PSA         |                     |       |
| RP          |                     |       |
| SA          |                     |       |
| SAV         |                     |       |
| SAZBA       |                     |       |
| SRCFORMAT   |                     |       |
| SéA         |                     |       |
| SHORT       | LENGTH -> too-short |       |
| SINGLETON   |                     |       |
| SPACETAB    |                     |       |
| STRUCT      |                     |       |
| STYLE       |                     |       |
| TERM        |                     |       |
| TS          |                     |       |
| typ.        |                     |       |
| gram.       |                     |       |
| strukt.     |                     |       |
| (others)    |                     |       |

## Detectors

### LENGTH

Findings:

- too-short -> SHORT
- too-long  -> (no rubric code) potential STYLE / CONTENT contributor, new rubric code?.

Heuristics (current): total words, paragraph count, paragraphs per heading, avg words per paragraph.

"""IPP assessment CSV parser."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

# --- CONSTANTS ---

DELIMITERS_LEFT = " \t\n\r,:;.(["
DELIMITERS_RIGHT = " \t\n\r,:;.)]"

IPP_CODES = {
    "DOCTYPE",
    "MISSING",
    "FORMAT",
    "FORM",
    "STRUCT",
    "SHORT",
    "CONTENT",
    "KAPTXT",
    "LANG",
    "CH",
    "ICH",
    "STYLE",
    "FILO",
    "HOV",
    "TERM",
    "BLOK",
    "PRED",
    "SAZBA",
    "COMMENT",
    "IR",
    "JAK",
    "AUTHOR",
    "SRCFORMAT",
    "BADUML",
    "NOUML",
    "WHY",
    "NVI",
    "PSR12",
    "STN9",
    "OOP",
    "NOOP",
    "NVP",
    "EX",
    "DECOMPOSE",
    "HOW",
    "SPACETAB",
    "EXT",
    "MEZ",
    "UML",
    "COPY",
    "NOSRP",
    "MDLINES",
    "BADDP",
    "OWNDIF",
    "NV",
    "NVPDOC",
    "BW",
    "OK",
    "SINGLETON",
    "STN0",
    "STN1",
    "STN2",
    "STN3",
    "STN4",
    "STN5",
    "STN6",
    "PSR1",
    "DP",
}

DOC_CODES = {
    "DOCTYPE",
    "MISSING",
    "FORMAT",
    "FORM",
    "STRUCT",
    "SHORT",
    "CONTENT",
    "KAPTXT",
    "LANG",
    "CH",
    "ICH",
    "STYLE",
    "FILO",
    "HOV",
    "TERM",
    "BLOK",
    "PRED",
    "SAZBA",
    "IR",
    "JAK",
    "BADUML",
    "NOUML",
    "WHY",
    "OOP",  # old: popis a terminologia oop
    "EX",
    "HOW",
    "SPACETAB",
    "EXT",
    "MEZ",
    "UML",
    "COPY",
    "MDLINES",
    "BADDP",  # old: dokumentacia neodpoveda skriptu
    "OWNDIF",
    "NV",  # old: navrhovy vzor
    "NVPDOC",
    "BW",  # old: ?
    "OK",
    "SINGLETON",
    "DP",
}

CODE_ALIASES = {
    "PŘED": "PRED",
    "BLOCK": "BLOK",
    "STYL": "STYLE",
    "SYLE": "STYLE",
    "STRUKT.": "STRUCT",
    "TYP.": "TYP",
    "GRAM.": "GRAM",
    "NOOOP": "NOOP",
    "SAZAB": "SAZBA",
    "COMMENTS": "COMMENT",
    "OO": "OOP",
    "TERM.": "TERM",
    "NVI": "NV",
}


# --- UTILITIES ---


def filter_doc_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Filter event rows to keep only documentation-related codes."""
    return df[df["code"].isin(DOC_CODES)].copy()


# --- REGEX ---


def make_code_token_regex() -> re.Pattern:
    """
    Creates a regex pattern to match all IPP codes and their aliases,
    case-insensitively, with word boundaries.
    """
    all_codes = set(IPP_CODES) | set(CODE_ALIASES.keys())

    # Sort by length desc to match longest code first
    sorted_codes = sorted(all_codes, key=len, reverse=True)

    long_patterns = []
    short_patterns = []

    for code in sorted_codes:
        # Match long codes or digit-containing codes case-insensitively
        if len(code) >= 3 or any(char.isdigit() for char in code):
            long_patterns.append(re.escape(code))
        else:
            short_patterns.append(re.escape(code))

    # Long patterns use case-insensitive flag
    parts = []
    if long_patterns:
        parts.append(f"(?i:{'|'.join(long_patterns)})")
    if short_patterns:
        parts.append("|".join(short_patterns))

    combined_pattern = "|".join(parts)

    # Look behind and ahead to match whole words
    return re.compile(rf"(?<![\w])({combined_pattern})(?![\w])")


CODE_TOKEN_RE = make_code_token_regex()
# Matches separators like / + & between codes, "STRUCT / SHORT"
GROUP_SEPARATOR_RE = re.compile(r"\s*[/\+&]\s*")
# Captures content inside parentheses, "(see below)" -> "see below"
PAREN_CONTENT_RE = re.compile(r"\s*\((?P<content>[^)]*)\)")
# Matches number at end of string, "text -10" -> sign="-", num="10"
PREFIX_NUMBER_RE = re.compile(r"(?P<sign>[+-])(?P<num>\d+)\s*$")
# Matches number with optional sign, "-10", "+5"
SUFFIX_NUMBER_RE = re.compile(r"(?P<sign>[+-])\s*(?P<num>\d+)")
# Matches number with/without mb inside parens, "-10mb", "-10"
PAREN_ANY_SIGNED_NUM_RE = re.compile(
    r"(?P<sign>[+-])\s*(?P<num>\d+)\s*(?:mb)?", re.IGNORECASE
)


def normalise_code_alias(code: str) -> str:
    """Normalise code to canonical uppercase form."""
    u = code.upper()
    return CODE_ALIASES.get(u, u)


def clean_comment(text: str) -> str | None:
    """
    Remove whitespace, outer punctuation, and surrounding parentheses.
    """
    if not text:
        return None

    text = " ".join(text.split())
    text = text.strip(" ,;:")

    if text.startswith("(") and text.endswith(")") and len(text) > 2:
        text = text[1:-1].strip(" ,;:")

    return text if text else None


def get_match_val(match: re.Match) -> int:
    """Helper to extract int value from signed number regex match."""
    val = int(match.group("num"))
    return -val if match.group("sign") == "-" else val


# --- PARSING ---


def extract_impact_from_parens(content: str) -> tuple[int | None, bool, str | None]:
    """
    Analyses content inside parentheses.
    Returns (impact_value, impact_has_sign, comment_text).
    Example: "-10mb comment" -> (-10, True, "comment")
    """
    matches = list(PAREN_ANY_SIGNED_NUM_RE.finditer(content))

    if len(matches) == 1:
        match = matches[0]
        val = get_match_val(match)

        start, end = match.span()
        before = content[:start]
        after = content[end:]

        raw_comment = before + " " + after
        return val, True, clean_comment(raw_comment)

    elif len(matches) == 0:
        if content.strip() == "0":
            return 0, False, None
        return None, False, clean_comment(content)

    else:
        # More than one number, treat entire content as comment
        return None, False, clean_comment(content)


def check_leading_parens(
    normalised_suffix: str,
) -> tuple[int, int | None, bool, str | None]:
    """
    Checks if suffix starts with parentheses and extracts impact.
    Returns: (match_end_idx, impact_value, has_sign, comment_str)
    Example: "(-10) comment" -> val=-10, comment="comment"
    """
    paren_match = PAREN_CONTENT_RE.match(normalised_suffix)
    if not paren_match:
        return 0, None, False, None

    inside = paren_match.group("content")
    val, has_sign, comment_text = extract_impact_from_parens(inside)

    return (
        paren_match.end(),
        val if (val is not None or has_sign) else None,
        has_sign,
        comment_text,
    )


def check_suffix(text: str, limit: int = 40) -> tuple[int | None, bool, str | None]:
    """Scan suffix for a signed number and return (value, has_sign, comment)."""
    valid_match = None

    # Search and validate boundaries
    for match in SUFFIX_NUMBER_RE.finditer(text):
        is_start_valid = (
            match.start() == 0 or text[match.start() - 1] in DELIMITERS_LEFT
        )
        is_end_valid = match.end() == len(text) or text[match.end()] in DELIMITERS_RIGHT

        if is_start_valid and is_end_valid:
            valid_match = match
            break

    # Match validation and limit check
    if not valid_match:
        return None, False, None
    if valid_match.start() > limit:
        return None, False, clean_comment(text)

    # Extraction and cleanup
    val = get_match_val(valid_match)
    start, end = valid_match.span()

    part_before = text[:start].rstrip(" ,;:")
    part_after = text[end:].lstrip(" ,;:")

    if part_after == ")" and part_before.endswith("("):
        part_before, part_after = part_before[:-1], ""

    return val, True, clean_comment(f"{part_before} {part_after}")


def check_prefix(
    target_idx: int, original_text: str, limit: int = 40
) -> tuple[int | None, bool]:
    """Scan prefix for a signed number and return (value, has_sign)."""
    prefix_start = max(0, target_idx - limit)
    text = original_text[prefix_start:target_idx]

    # Search
    match = PREFIX_NUMBER_RE.search(text)

    # Match validation
    if not match:
        return None, False

    # Validate boundaries
    preceding = text[: match.start()]
    is_at_start = match.start() == 0 and prefix_start == 0
    is_after_space = not preceding.strip() and prefix_start == 0
    is_after_delim = bool(re.search(r"[,;:\.\n]\s*$", preceding))

    if is_at_start or is_after_space or is_after_delim:
        return get_match_val(match), True

    return None, False


@dataclass
class Event:
    """
    Represents a single grading deduction/addition applied to one or more IPP codes.
    """

    codes: list[str]
    start_idx: int
    end_idx: int
    raw_span: str
    impact_value: int | None = None
    impact_has_sign: bool = False
    impact_source: str | None = None
    comment: str | None = None


def resolve_span_impact(event: Event, suffix_text: str, original_text: str) -> None:
    """
    Resolves the impact score and comment for an event.
    """
    paren_match_length, paren_impact, paren_has_sign, paren_comment = (
        check_leading_parens(suffix_text)
    )

    if paren_impact is not None:
        event.impact_value = paren_impact
        event.impact_has_sign = paren_has_sign
        event.impact_source = "paren"

        rest_of_text = clean_comment(suffix_text[paren_match_length:])

        parts = []
        if paren_comment:
            parts.append(paren_comment)
        if rest_of_text:
            parts.append(rest_of_text)

        event.comment = " ".join(parts) if parts else None
        return

    search_text = suffix_text[paren_match_length:]
    suffix_impact, suffix_has_sign, suffix_comment = check_suffix(search_text)

    if suffix_has_sign:
        event.impact_value = suffix_impact
        event.impact_has_sign = True
        event.impact_source = "suffix"

        parts = []
        if paren_match_length > 0 and paren_comment:
            parts.append(paren_comment)
        if suffix_comment:
            parts.append(suffix_comment)

        event.comment = " ".join(parts) if parts else None
        return

    prefix_impact, prefix_has_sign = check_prefix(event.start_idx, original_text)
    if prefix_has_sign:
        event.impact_value = prefix_impact
        event.impact_has_sign = prefix_has_sign
        event.impact_source = "prefix"

        clean_suf = clean_comment(suffix_text)
        event.comment = clean_suf if clean_suf else None
        return

    parts = []
    if paren_match_length > 0 and paren_comment:
        parts.append(paren_comment)

    rest = clean_comment(search_text)
    if rest:
        parts.append(rest)

    event.comment = " ".join(parts) if parts else None


def parse_comment(text: str) -> list[Event]:
    """
    Parses a full comment string into a list of Events.
    Example: "STRUCT -10 (comment), SHORT" -> [Event(STRUCT, -10), Event(SHORT)]
    """

    text = text.replace("−", "-").replace("–", "-").replace("—", "-")  # noqa: RUF001

    tokens = []
    paren_ranges = []
    stack = []
    for i, char in enumerate(text):
        if char == "(":
            stack.append(i)
        elif char == ")":
            if stack:
                start = stack.pop()
                paren_ranges.append((start, i))

    for match in CODE_TOKEN_RE.finditer(text):
        match_start = match.start()
        if any(start < match_start < end for start, end in paren_ranges):
            continue

        raw_code = match.group(1)
        code = normalise_code_alias(raw_code)
        if code in IPP_CODES:
            tokens.append({"code": code, "start": match.start(), "end": match.end()})

    if not tokens:
        return []

    events = []
    i = 0
    # Group consecutive codes (CODE1 / CODE2)
    while i < len(tokens):
        current_codes = [tokens[i]["code"]]
        group_start = tokens[i]["start"]
        group_end = tokens[i]["end"]

        j = i + 1
        while j < len(tokens):
            between = text[tokens[j - 1]["end"] : tokens[j]["start"]]
            if GROUP_SEPARATOR_RE.fullmatch(between):
                current_codes.append(tokens[j]["code"])
                group_end = tokens[j]["end"]
                j += 1
            else:
                break

        next_start = tokens[j]["start"] if j < len(tokens) else len(text)
        span_end = next_start

        # Prevent the next prefix impact from being absorbed into the current suffix
        if j < len(tokens):
            _, has_prefix = check_prefix(next_start, text)
            if has_prefix:
                pre_text = text[group_end:next_start]
                match = re.search(r"(?P<sign>[+-])(?P<num>\d+)\s*$", pre_text)
                if match:
                    span_end = group_end + match.start()

        event = Event(
            codes=current_codes,
            start_idx=group_start,
            end_idx=span_end,
            raw_span=text[group_start:span_end],
        )

        suffix_text = text[group_end:span_end]
        resolve_span_impact(event, suffix_text, text)
        events.append(event)

        i = j
    return events


def extract_rows_from_dataframe(
    df: pd.DataFrame, filename: str, year: str, task_variant: str
) -> Iterator[dict[str, Any]]:
    """
    Processes a DataFrame row by row, extracting Events from the comment column.
    """
    # Normalise
    for col in ["id", "points", "doc_type", "bonus_points"]:
        if col not in df.columns:
            df[col] = None
    df = df.replace({float("nan"): None, pd.NA: None})

    for row in df.itertuples(index=False):
        text = str(row.comment) if row.comment else ""

        events = parse_comment(text)

        for evt in events:
            is_shared = len(evt.codes) > 1

            for code in evt.codes:
                yield {
                    "id": row.id,
                    "year": year,
                    "task_variant": task_variant,
                    "code": code,
                    "impact": evt.impact_value,
                    "impact_given": evt.impact_value is not None,
                    "impact_has_sign": evt.impact_has_sign,
                    "impact_source": evt.impact_source,
                    "impact_shared": is_shared,
                    "comment": evt.comment,
                    "raw_text": evt.raw_span,
                    "source_file": filename,
                    "doc_points": row.points,
                    "doc_type": row.doc_type,
                    "bonus_points": row.bonus_points,
                }


def parse_document_tokens(
    df: pd.DataFrame, doc_base: Path, n_samples_per_type: int = 50
) -> pd.DataFrame:
    """
    Sample documents, parse their content via Docling and tokenise it.
    Returns a dataframe containing token counts for sampled MD and PDF documents.
    """
    import tiktoken
    from docling.document_converter import DocumentConverter

    tokenizer = tiktoken.get_encoding("cl100k_base")
    converter = DocumentConverter()

    recent_docs_df = (
        df[df["doc_type"].isin(["md", "pdf"])][["id", "source_file", "doc_type"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # Sample
    md_docs = recent_docs_df[recent_docs_df["doc_type"] == "md"].head(
        n_samples_per_type
    )
    pdf_docs = recent_docs_df[recent_docs_df["doc_type"] == "pdf"].head(
        n_samples_per_type
    )
    sampled_docs_df = pd.concat([md_docs, pdf_docs]).reset_index(drop=True)

    token_records = []

    for student_id, source_file, doc_type in sampled_docs_df.itertuples(index=False):
        cohort = Path(source_file).stem
        f = doc_base / cohort / f"{student_id}.{doc_type}"

        if not f.exists():
            continue

        try:
            conversion_result = converter.convert(f)
            text = conversion_result.document.export_to_markdown()
            tokens = tokenizer.encode(text)

            token_records.append(
                {
                    "id": student_id,
                    "cohort": cohort,
                    "format": doc_type,
                    "tokens": len(tokens),
                }
            )
        except Exception:
            continue

    return pd.DataFrame(token_records)


# --- MAIN ---


def main() -> None:
    root_dir = Path(__file__).parent.parent
    data_dir = root_dir / "data" / "raw" / "ipp_13_to_24" / "ipp_assessments"
    all_files = list(data_dir.glob("ipp*.csv"))

    print(f"Found {len(all_files)} files in {data_dir}")

    all_extracted_rows = []

    for file_path in all_files:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            continue

        if "comment" not in df.columns:
            print(f"Skipping {file_path}, no 'comment' column")
            continue

        filename = file_path.name
        match = re.search(r"\d{2}", filename)
        year = "20" + match.group(0) if match else "Unknown"
        task_variant = (
            filename.split("-")[1].split(".")[0] if "-" in filename else "Unknown"
        )

        all_extracted_rows.extend(
            extract_rows_from_dataframe(df, filename, year, task_variant)
        )

    if all_extracted_rows:
        output_df = pd.DataFrame(all_extracted_rows)
        output_path = root_dir / "data" / "clean_ipp_data.csv"
        output_df.to_csv(output_path, index=False)

        print(f"Processed {len(output_df)} rows. Saved to {output_path}")

        print("\nNumber of rows per code: ")
        print(output_df["code"].value_counts().head(10))

        print("\nAverage impact of codes: ")
        print(output_df.groupby("code")["impact"].mean().sort_values().head(10))
    else:
        print("No data extracted.")


if __name__ == "__main__":
    main()

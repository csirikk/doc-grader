"""IPP assessment csv parser and analysis helpers."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

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
    "COMMENT",
    "IR",
    "JAK",
    "BADUML",
    "NOUML",
    "WHY",
    "NVI",  # old: navrhovy vzor
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


def filter_doc_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Filter DataFrame to keep only documentation related codes."""
    return df[df["code"].isin(DOC_CODES)].copy()


# --- REGEX  ---


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
            p = "".join(
                f"[{char.upper()}{char.lower()}]" if char.isalpha() else re.escape(char)
                for char in code
            )
            long_patterns.append(p)
        else:
            short_patterns.append(re.escape(code))

    combined_pattern = "|".join(long_patterns + short_patterns)
    # Look behind and ahead to match whole words
    return re.compile(r"(?<![\w])(" + combined_pattern + r")(?![\w])")


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


def normalize_code_alias(code: str) -> str:
    """Normalize code to canonical uppercase form."""
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
    Analyzes content inside parentheses.
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
    normalized_suffix: str,
) -> tuple[int, int | None, bool, str | None]:
    """
    Checks if suffix starts with parentheses and extracts impact.
    Returns: (match_end_idx, impact_value, has_sign, comment_str)
    Example: "(-10) comment" -> val=-10, comment="comment"
    """
    paren_match = PAREN_CONTENT_RE.match(normalized_suffix)
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


def check_suffix(text: str) -> tuple[int | None, bool, str | None]:
    """
    Scan suffix for signed numbers from right to left.
    Returns: (impact_value, has_sign, comment_str)
    Example: "comment -10" -> val=-10, comment="comment"
    """
    matches = list(SUFFIX_NUMBER_RE.finditer(text))

    # Ensure the number is a standalone token by checking boundaries
    valid_matches = [
        match
        for match in matches
        if (match.start() == 0 or text[match.start() - 1] in DELIMITERS_LEFT)
        and (match.end() == len(text) or text[match.end()] in DELIMITERS_RIGHT)
    ]

    if not valid_matches:
        return None, False, None

    # If multiple numbers exist in the suffix, use the first
    valid_match = valid_matches[0]
    val = get_match_val(valid_match)

    match_start, match_end = valid_match.span()

    part_before = text[:match_start]
    part_after = text[match_end:]

    clean_before = part_before.rstrip(" ,;:")
    clean_after = part_after.lstrip(" ,;:")

    if clean_after == ")" and clean_before.endswith("("):
        clean_before = clean_before[:-1]
        clean_after = ""

    raw_comment = clean_before + " " + clean_after
    return val, True, clean_comment(raw_comment)


def check_prefix(target_idx: int, original_text: str) -> tuple[int | None, bool]:
    """
    Checks text immediately before the target index for a signed number.
    Returns (impact_value, impact_has_sign) or (None, False).
    Example: "text -10 CODE" with target_idx at "C" -> val=-10
    """
    prefix_limit = 60  # 60 chars should be good
    prefix_start = max(0, target_idx - prefix_limit)
    prefix_text = original_text[prefix_start:target_idx]

    match = PREFIX_NUMBER_RE.search(prefix_text)
    if not match:
        return None, False

    match_start = match.start()
    preceding = prefix_text[:match_start]

    is_valid = (
        (match_start == 0 and prefix_start == 0)
        or bool(re.search(r"[,;:\.\n]\s*$", preceding))
        or (not preceding.strip() and prefix_start == 0)
    )

    if is_valid:
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
    Chain of responsibility to find impact/comment.
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
        code = normalize_code_alias(raw_code)
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
    for row in df.itertuples(index=False):
        comment_val = getattr(row, "comment", None)
        text = str(comment_val) if not pd.isna(comment_val) else ""

        row_id = getattr(row, "id", None)
        points = None if pd.isna(v := getattr(row, "points", None)) else v
        doc_type = None if pd.isna(v := getattr(row, "doc_type", None)) else v
        bonus_points = None if pd.isna(v := getattr(row, "bonus_points", None)) else v

        events = parse_comment(text)

        for evt in events:
            is_shared = len(evt.codes) > 1

            for code in evt.codes:
                yield {
                    "id": row_id,
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
                    "points": points,
                    "doc_type": doc_type,
                    "bonus_points": bonus_points,
                }


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

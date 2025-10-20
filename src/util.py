"""Utility helpers."""

from pathlib import Path
import hashlib
from typing import Dict, Any, Sequence, Optional, List

_id_counters: Dict[str, int] = {}


def next_id(prefix: str) -> str:
    """Return the next sequential id for the given prefix."""
    n = _id_counters.get(prefix, 0) + 1
    _id_counters[prefix] = n
    return f"{prefix}-{n}"


def reset_id_counters(*prefixes: str) -> None:
    """Reset internal id counters.
    Without arguments resets all prefixes. If one or more `prefixes` are
    provided only those counters are cleared.
    """
    if not prefixes:
        _id_counters.clear()
        return
    for p in prefixes:
        _id_counters.pop(p, None)


def count_words(text: Optional[str]) -> int:
    if not text:
        return 0
    return len([w for w in text.split() if w])


def compute_doc_hash(path: str) -> str:
    with open(path, "rb") as f:
        return "sha256:" + hashlib.sha256(f.read()).hexdigest()


def norm(text: Optional[str]) -> str:
    """Normalize whitespace."""
    if not text:
        return ""
    return " ".join(text.split())


def summarize_document(doc) -> Dict[str, Any]:
    """Return a structured high-level overview of the document.

    {
      "counts": {               # raw block counts
         "total_blocks": int,
         "by_type": { str: int, ... }
      },
      "text": {
        "paragraphs": int,
        "paragraph_words": int,      # words in Paragraph blocks only
        "list_item_words": int,      # words in List items
        "total_words": int,
        "avg_words_per_paragraph": float | 0.0,
      },
      "structure": {
         "headings": int,
         "heading_levels": { str(level): int, ... },
         "paragraphs_per_heading": float | null,
         "first_heading": str | null,
      },
      "media": {
         "lists": int,
         "code_blocks": int,
         "tables": int,
         "figures": int,
         "quotes": int,
      }
    }
    """
    blocks = getattr(doc, "blocks", [])

    # Generic block type counts
    by_type: Dict[str, int] = {}
    for b in blocks:
        t = getattr(b, "type", type(b).__name__)
        by_type[t] = by_type.get(t, 0) + 1

    # Paragraphs
    paragraphs = [b for b in blocks if getattr(b, "type", None) == "Paragraph"]
    paragraph_word_total = 0
    for p in paragraphs:
        txt = getattr(p, "text", "") or ""
        paragraph_word_total += count_words(txt)

    # List items
    list_word_total = 0
    for b in blocks:
        if getattr(b, "type", None) == "List":
            for it in getattr(b, "items", []) or []:
                list_word_total += count_words(getattr(it, "text", None))

    total_words = paragraph_word_total + list_word_total
    para_count = len(paragraphs)
    avg_words = (paragraph_word_total / para_count) if para_count else 0.0

    # Headings
    headings = [b for b in blocks if getattr(b, "type", None) == "Heading"]
    heading_count = len(headings)
    heading_levels: Dict[str, int] = {}
    first_heading_text = None
    for h in headings:
        lvl = getattr(h, "level", None)
        if lvl is not None:
            heading_levels[str(lvl)] = heading_levels.get(str(lvl), 0) + 1
        if first_heading_text is None:
            first_heading_text = getattr(h, "text", None)
    paragraphs_per_heading = (
        round(para_count / heading_count, 2) if heading_count else None
    )

    # Media / other counts
    media = {
        "lists": by_type.get("List", 0),
        "code_blocks": by_type.get("CodeBlock", 0),
        "tables": by_type.get("Table", 0),
        "figures": by_type.get("Figure", 0),
        "quotes": by_type.get("Quote", 0),
    }

    return {
        "counts": {
            "total_blocks": len(blocks),
            "by_type": by_type,
        },
        "text": {
            "paragraphs": para_count,
            "paragraph_words": paragraph_word_total,
            "list_item_words": list_word_total,
            "total_words": total_words,
            "avg_words_per_paragraph": round(avg_words, 2),
        },
        "structure": {
            "headings": heading_count,
            "heading_levels": heading_levels,
            "paragraphs_per_heading": paragraphs_per_heading,
            "first_heading": first_heading_text,
        },
        "media": media,
    }


def format_findings(
    detector, findings: Sequence, *, detector_label: Optional[str] = None
) -> str:
    """Return a formatted multi-line string describing findings."""
    label = detector_label or getattr(detector, "code", "DET")
    lines: List[str] = [f"[{label}] Findings:"]
    if not findings:
        lines.append("(none)")
        return "\n".join(lines)

    for f in findings:
        fid = getattr(f, "finding_id", "?")
        title = getattr(f, "title", "?")
        severity = getattr(f, "severity_rank", "?")
        confidence = getattr(f, "confidence", None)
        lines.append(
            f"- {fid} | {title} | severity={severity} | confidence={confidence}"
        )

        msg = getattr(f, "message", "") or ""
        if msg:
            lines.append(f"  Message: {msg}")

        evidence = getattr(f, "evidence", []) or []
        stats = [e for e in evidence if getattr(e, "type", None) == "Stat"]
        if stats:
            lines.append("  Stats:")
            for s in sorted(stats, key=lambda s: getattr(s, "name", "")):
                name = getattr(s, "name", "?")
                value = getattr(s, "value", "?")
                lines.append(f"    {name}: {value}")
    return "\n".join(lines)


def write_findings_json(detector, findings: Sequence, outdir: Path) -> Sequence[Path]:
    """Write findings as JSON files with detector.write_findings and return paths."""
    return detector.write_findings(findings, outdir)

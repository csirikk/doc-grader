from pathlib import Path
import hashlib
from typing import Dict, Any, Sequence, Optional

_counters = {}

def next_id(prefix: str) -> str:
    """Return the next sequential id for the given prefix."""
    n = _counters.get(prefix, 0) + 1
    _counters[prefix] = n
    return f"{prefix}-{n}"

def doc_hash(path: str) -> str:
    with open(path, "rb") as f:
        return "sha256:" + hashlib.sha256(f.read()).hexdigest()

def summarize_document(doc) -> Dict[str, Any]:
    """Return a structured high-level overview of the document.

    {
      "counts": {               # raw block counts
         "total_blocks": int,
         "by_type": { str: int, ... }
      },
      "text": {
         "paragraphs": int,
         "words": int,                # paragraph word sum
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
    words = 0
    for p in paragraphs:
        txt = getattr(p, "text", "") or ""
        words += len([w for w in txt.split() if w])
    para_count = len(paragraphs)
    avg_words = (words / para_count) if para_count else 0.0

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
            "words": words,
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


def print_findings(detector, findings: Sequence, outdir: Path, *, detectorLabel: Optional[str] = None):
    label = detectorLabel or getattr(detector, "code", "DET")
    print(f"\n[{label}] Findings:")

    if not findings:
        print("(none)")
        return []

    for f in findings:
        fid = getattr(f, "finding_id", "?")
        title = getattr(f, "title", "?")
        severity = getattr(f, "severity", "?")
        confidence = getattr(f, "confidence", None)
        print(f"- {fid} | {title} | severity={severity} | confidence={confidence}")

        msg = getattr(f, "message", "") or ""
        print(f"  Message: {msg}")

        evidence = getattr(f, "evidence", []) or []
        stats = [e for e in evidence if getattr(e, 'type', None) == 'Stat']
        if stats:
            stats_sorted = sorted(stats, key=lambda s: getattr(s, 'name', ''))
            print("  Stats:")
            for s in stats_sorted:
                name = getattr(s, 'name', '?')
                value = getattr(s, 'value', '?')
                print(f"    {name}: {value}")

    paths = detector.write_findings(findings, outdir)
    print(f"\n[{label}] Written {len(paths)} finding file(s) to {outdir}/")
    return paths

"""4. Split the audit manifest and format fine-tuning JSONL files.

Takes audit_manifest.jsonl, splits records by student_id to avoid data leakage,
and writes one OpenAI vision fine-tuning JSONL per split (train, validation,
test) to data/vision-training/audit_jsonl/.
"""

from __future__ import annotations

import base64
import json
import logging
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from notebooks.baduml.models import StudentImageRecord

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


logger = logging.getLogger("__name__")

# OpenAI limits images to 10 MB in fine-tuning data.
_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SYSTEM_PROMPT = (
    "You are a professional UML grading assistant. Analyse the diagram based on "
    "syntax and structure, then classify it."
)
_USER_PROMPT = "Analyse this UML diagram."


def split(
    records: list[StudentImageRecord],
    ratios: tuple[float, float, float] = (0.8, 0.2, 0.0),
    seed: int = 42,
) -> dict[str, list[StudentImageRecord]]:
    """Split records into train, validation, and test sets by student_id."""
    groups: dict[str, list[StudentImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.student_id].append(record)

    student_ids = list(groups.keys())
    random.seed(seed)
    random.shuffle(student_ids)

    n = len(student_ids)
    train_end = int(n * ratios[0])
    val_end = int(n * (ratios[0] + ratios[1]))

    splits: dict[str, list[StudentImageRecord]] = {
        "train": [],
        "validation": [],
        "test": [],
    }
    for sid in student_ids[:train_end]:
        splits["train"].extend(groups[sid])
    for sid in student_ids[train_end:val_end]:
        splits["validation"].extend(groups[sid])
    for sid in student_ids[val_end:]:
        splits["test"].extend(groups[sid])

    for name, items in splits.items():
        logger.info("Split %s: %d images", name, len(items))

    return splits


def _encode_image(path: Path) -> str:
    """Return a base64 PNG data URL for the image at path."""
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _make_entry(image_ref: str, label: str, analysis: str) -> dict[str, object]:
    """Build a single OpenAI fine-tuning conversation entry."""
    assistant_text = (
        f"Analysis: {analysis} Classification: {label}" if analysis else label
    )
    return {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_ref, "detail": "high"},
                    },
                ],
            },
            {"role": "assistant", "content": assistant_text},
        ]
    }


def write_jsonl(records: list[StudentImageRecord], out_path: Path) -> int:
    """Write records to a JSONL fine-tuning file. Returns lines written."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    skipped = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for record in records:
            image_path = Path(record.image_path)
            if not image_path.is_file():
                logger.warning("Image not found, skipping: %s", image_path)
                skipped += 1
                continue
            size = image_path.stat().st_size
            if size > _MAX_IMAGE_BYTES:
                logger.warning(
                    "Image exceeds 10 MB limit (%d bytes), skipping: %s",
                    size,
                    image_path,
                )
                skipped += 1
                continue
            image_ref = _encode_image(image_path)
            entry = _make_entry(image_ref, record.label, record.analysis)
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
            count += 1
    if skipped:
        logger.info("Skipped %d image(s) in %s", skipped, out_path.name)
    return count


def run(
    splits: dict[str, list[StudentImageRecord]],
    output_dir: Path,
) -> None:
    """Write one JSONL file per split to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in splits.items():
        out_path = output_dir / f"{name}.jsonl"
        n = write_jsonl(records, out_path)
        logger.info("Wrote %d entries to %s", n, out_path)

"""4. Split the audit manifest and format fine-tuning JSONL files.

Author: Matúš Csirik

Takes audit_manifest.jsonl, splits records by student_id to avoid data leakage,
and writes one OpenAI vision fine-tuning JSONL per split (train, validation,
test) to data/vision-training/audit_jsonl/.
"""

import base64
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import StudentImageRecord


logger = logging.getLogger(__name__)

# OpenAI limits images to 10 MB in fine-tuning data.
_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SYSTEM_PROMPT = (
    "Classify this UML class diagram. "
    "GOODUML: Correct, readable diagram with standard notation, "
    "attributes, methods, and clear relationships. "
    "BADUML: Missing details, unreadable, or uses non-standard notation."
)
_USER_PROMPT = "Analyse this diagram for UML compliance."


def split(
    records: list[StudentImageRecord],
    ratios: tuple[float, float, float] = (0.8, 0.2, 0.0),
    seed: int = 42,
) -> dict[str, list[StudentImageRecord]]:
    """Split records into train, validation and test sets grouped by student.

    Args:
        records: List of StudentImageRecord objects to split.
        ratios: Tuple of (train, validation, test) ratios summing to <= 1.
        seed: Random seed for reproducible shuffling.

    Returns:
        A mapping with keys 'train', 'validation' and 'test' containing the
        selected records per split.
    """
    groups: dict[str, list[StudentImageRecord]] = defaultdict(list)
    for record in records:
        # Keep each student in exactly one split.
        groups[record.student_id].append(record)

    student_ids = list(groups.keys())
    random.seed(seed)
    random.shuffle(student_ids)

    n = len(student_ids)
    # Use integer cut points so split sizes are repeatable.
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


def _make_entry(image_ref: str, label: str) -> dict[str, object]:
    """Build a single OpenAI fine-tuning conversation entry."""
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
            {"role": "assistant", "content": label},
        ]
    }


def write_jsonl(records: list[StudentImageRecord], out_path: Path) -> int:
    """Write records to a JSONL fine-tuning file.

    Args:
        records: List of StudentImageRecord entries to write.
        out_path: Destination file path for the JSONL output.

    Returns:
        The number of written lines (entries).
    """
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
            entry = _make_entry(image_ref, record.label)
            fh.write(json.dumps(entry, ensure_ascii=True) + "\n")
            count += 1
    if skipped:
        logger.info("Skipped %d image(s) in %s", skipped, out_path.name)
    return count


def run(
    splits: dict[str, list[StudentImageRecord]],
    output_dir: Path,
) -> None:
    """Write one JSONL file per split to ``output_dir``.

    Args:
        splits: Mapping of split name to lists of StudentImageRecord.
        output_dir: Directory where the JSONL files will be written.

    Returns:
        None
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in splits.items():
        out_path = output_dir / f"{name}.jsonl"
        n = write_jsonl(records, out_path)
        logger.info("Wrote %d entries to %s", n, out_path)

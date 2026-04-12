"""2. Split student image records into train, validation, and test sets."""

from __future__ import annotations

import logging
import random
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from notebooks.vision.extractor import StudentImageRecord, load_manifest
from src.utils import configure_logging

logger = logging.getLogger(__name__)


def split(
    records: list[StudentImageRecord],
    ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),  # train : validation : test
    seed: int = 42,
) -> dict[str, list[StudentImageRecord]]:
    """Split records into train, validation, and test sets."""
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


def main() -> int:
    configure_logging(logging.INFO)
    project_root = Path(__file__).resolve().parents[2]
    manifest_path = project_root / "data" / "vision-training" / "manifest.jsonl"
    records = load_manifest(manifest_path)
    splits = split(records)
    logger.info(
        "Split sizes: train: %d  validation: %d  test: %d",
        len(splits["train"]),
        len(splits["validation"]),
        len(splits["test"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

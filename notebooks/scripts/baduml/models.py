"""Shared data model and manifest I/O for the vision training pipeline."""

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class StudentImageRecord:
    student_id: str
    image_path: str
    image_file: str
    label: str
    cohort_year: str
    task_variant: str
    source_doc: str
    analysis: str = field(default="")


def save_manifest(records: list[StudentImageRecord], path: Path) -> None:
    """Serialise records to a JSONL manifest at path.

    Each line is a JSON object produced from asdict(record). Uses
    ensure_ascii=True to keep outputs ASCII-only.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(asdict(rec), ensure_ascii=True) + "\n")
    logger.info("Wrote %d records to manifest %s", len(records), path)


def load_manifest(path: Path) -> list[StudentImageRecord]:
    """Read JSONL manifest and return only records where the image still exists."""
    records = []
    if not path.exists():
        logger.error("Manifest not found at %s", path)
        return []

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            data = json.loads(line)
            record = StudentImageRecord(**data)
            if Path(record.image_path).is_file():
                records.append(record)
            else:
                logger.debug("Skipping record, image missing: %s", record.image_file)

    return records

"""3. Format image splits into OpenAI fine-tuning JSONL files.

Encodes each image as a base64 PNG data URL and writes one JSONL file per split
(train.jsonl, validation.jsonl, test.jsonl).
"""

from __future__ import annotations

import base64
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from notebooks.vision.extractor import StudentImageRecord, load_manifest
from notebooks.vision.splitter import split
from src.utils import configure_logging

logger = logging.getLogger(__name__)

# OpenAI limits images sto 10 MB in fine-tuning data
_MAX_IMAGE_BYTES = 10 * 1024 * 1024

_SYSTEM_PROMPT = (
    "Classify this UML class diagram. "
    "GOODUML: Correct, readable diagram with standard notation, attributes, methods, and clear relationships. "
    "BADUML: Missing details, unreadable, or uses non-standard notation."
)

_LABEL_RESPONSE: dict[str, str] = {"BADUML": "BADUML", "GOODUML": "GOODUML"}

_USER_PROMPT = "Analyze this diagram for UML compliance."


def _encode_image(path: Path) -> str:
    """Return a base64 PNG data URL for the image at path."""
    data = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


def _make_entry(image_ref: str, label: str) -> dict:
    """Make a single conversation entry."""
    assistant_text = _LABEL_RESPONSE.get(label, label)
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
    """Write records to a JSONL file. Returns the number of lines written."""
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
    """Write one JSONL file per split to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, records in splits.items():
        out_path = output_dir / f"{name}.jsonl"
        n = write_jsonl(records, out_path)
        logger.info("Wrote %d entries to %s", n, out_path)


def main() -> int:
    configure_logging(logging.INFO)
    project_root = Path(__file__).resolve().parents[2]
    vision_dir = project_root / "data" / "vision-training"

    manifest_path = vision_dir / "manifest.jsonl"
    records = load_manifest(manifest_path)
    logger.info("Loaded %d images from %s", len(records), manifest_path)
    splits = split(records)
    run(splits, output_dir=vision_dir / "jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

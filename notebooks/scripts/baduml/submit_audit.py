"""2. Prepare and submit UML image audit requests to the OpenAI Batch API.

Assigns each image a UUID4 custom_id, writes audit_id_mapping.json so the
relationship between custom_id and source image is never lost, logs an
estimated Batch API cost, and (optionally --dry-run) uploads the requests JSONL
and submits a batch job.
"""

import base64
import json
import logging
import math
import mimetypes
import os
import uuid
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger("__name__")

RUBRIC = """
### UML Class Diagram Validation Rubric: "BADUML" Criteria

A diagram is classified as BADUML if it fails to meet the standard requirements 
for a UML Class Diagram in a software documentation context. Use the following 
categories to identify and classify errors:

1. Syntactic & Notational Errors
- Incorrect Relationship Symbols: Uses generic lines or arrows instead of specific 
UML connectors. Inheritance must be a hollow triangle, 
Composition/Aggregation must use a diamond-shaped end.
- Non-Standard Class Boxes: Fails to use the three-segment box 
(Name, Attributes, Methods). Using simple circles, squares, or flowchart 
symbols is an error.
- Missing Visibility Markers: Omits the +, -, or # prefixes for attributes and methods.

2. Content Deficiency
- Empty Class Boxes: Shows a class name but leaves the attribute or method sections 
entirely empty or omitted.
- Missing Relationships: Shows classes floating in space without association, 
dependency, or inheritance lines.
- Undefined Labels: Missing names or cardinalities (e.g., 1..*) on association lines 
where they are necessary for clarity.

3. Structural Inconsistency
- Model Mixing: Mixing UML Class notation with Database ERDs 
(PK/FK notation) or Flowcharts (decision diamonds).
- Logic Mismatch: The diagram represents a structure that contradicts the functional 
requirements of the project or lacks core classes described in the documentation.

4. Presentation
- Illegibility: The image is too blurry, pixelated, 
or chaotic for text and relationships to be clearly identified.
- Overlapping Elements: Lines crossing through class boxes 
or text in a way that makes the diagram impossible to trace.
- Incorrect Content: The image is not a diagram at all 
(e.g., a screenshot of code, terminal output, or a UI mockup) but was 
submitted as a UML diagram.
""".strip()

_USER_PROMPT = (
    "Analyse this UML diagram and classify it as GOODUML, BADUML, or INVALID "
    "based on the provided rubric. Return the analysis and classification in "
    "JSON format."
)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}

_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "uml_audit_result",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "classification": {
                    "type": "string",
                    "enum": ["GOODUML", "BADUML", "INVALID"],
                },
                "analysis": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["classification", "analysis", "confidence"],
        },
    },
}


def _calculate_image_tokens(width: int, height: int) -> int:
    """Calculate tokens for a high-detail image using OpenAI's resizing formula."""
    if max(width, height) > 2048:
        scale = 2048 / max(width, height)
        width = int(width * scale)
        height = int(height * scale)
    if min(width, height) > 768:
        scale = 768 / min(width, height)
        width = int(width * scale)
        height = int(height * scale)
    tiles_w = math.ceil(width / 512)
    tiles_h = math.ceil(height / 512)
    return (tiles_w * tiles_h * 170) + 85


def _log_cost_estimate(rows: list[tuple[str, Path]]) -> None:
    """Log estimated Batch API token count and cost for the image set."""
    total_image_tokens = 0
    for _, image_path in rows:
        try:
            with Image.open(image_path) as img:
                w, h = img.size
            total_image_tokens += _calculate_image_tokens(w, h)
        except Exception:
            logger.debug("Could not read image dimensions: %s", image_path)

    n = len(rows)
    text_tokens = n * 350
    output_tokens = n * 100
    total_input = text_tokens + total_image_tokens
    input_cost = (total_input / 1_000_000) * 1.25
    output_cost = (output_tokens / 1_000_000) * 5.00
    logger.info(
        "Cost estimate: %d images, %d input tokens, %d output tokens",
        n,
        total_input,
        output_tokens,
    )
    logger.info(
        "Cost estimate: input=$%.4f output=$%.4f total=$%.4f",
        input_cost,
        output_cost,
        input_cost + output_cost,
    )


def _encode_image(path: Path) -> str:
    """Return a base64 data URL for an image file."""
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = path.read_bytes()
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def _iter_images(images_dir: Path) -> list[tuple[str, Path]]:
    """Return [(label, image_path), ...] for BADUML and GOODUML source folders."""
    label_to_dir: dict[str, Path] = {
        "BADUML": images_dir / "baduml",
        "GOODUML": images_dir / "gooduml",
    }
    rows: list[tuple[str, Path]] = []
    for label, folder in label_to_dir.items():
        if not folder.is_dir():
            logger.warning("Image folder missing, skipping: %s", folder)
            continue
        for image_path in sorted(folder.rglob("*")):
            if image_path.suffix.lower() not in _IMAGE_EXTS:
                continue
            rows.append((label, image_path))
    return rows


def _build_request(
    *,
    custom_id: str,
    model: str,
    image_ref: str,
) -> dict[str, object]:
    system_prompt = (
        "You are an expert teaching assistant for UML class diagram review. "
        "Use the rubric exactly as provided. If the input is not a UML class "
        "diagram or is impossible to judge, return INVALID. "
        "Rubric:\n"
        f"{RUBRIC}"
    )
    return {
        "custom_id": custom_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": model,
            "temperature": 0,
            "response_format": _RESPONSE_FORMAT,
            "messages": [
                {"role": "system", "content": system_prompt},
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
            ],
        },
    }


def write_requests_jsonl(
    *,
    images_dir: Path,
    mapping_path: Path,
    out_path: Path,
    model: str,
) -> int:
    rows = _iter_images(images_dir)
    if not rows:
        logger.error("No input images found under %s", images_dir)
        return 0

    _log_cost_estimate(rows)

    mapping: dict[str, dict[str, str]] = {}
    valid_requests = []

    for label, image_path in rows:
        uid = str(uuid.uuid4())
        try:
            image_ref = _encode_image(image_path)
        except Exception:
            logger.exception("Failed to encode image, skipping: %s", image_path)
            continue  # Skip mapping this file entirely

        mapping[uid] = {"source_path": str(image_path), "label": label}
        valid_requests.append(
            _build_request(custom_id=uid, model=model, image_ref=image_ref)
        )

    # Write the clean mapping file
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    with mapping_path.open("w", encoding="utf-8") as fh:
        json.dump(mapping, fh, ensure_ascii=True, indent=2)

    # Write the batch requests
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for request in valid_requests:
            fh.write(json.dumps(request, ensure_ascii=True) + "\n")

    logger.info("Wrote %d requests to %s", len(valid_requests), out_path)
    return len(valid_requests)


def submit_batch(
    *,
    requests_path: Path,
    model: str,
    api_key_env: str,
) -> tuple[str, str] | None:
    """Upload JSONL file and submit a Batch API job."""
    from openai import OpenAI  # not needed for dry-run

    api_key = os.environ.get(api_key_env)
    if not api_key:
        logger.error("Missing API key in environment variable: %s", api_key_env)
        return None

    client = OpenAI(api_key=api_key)

    try:
        with requests_path.open("rb") as fh:
            uploaded = client.files.create(file=fh, purpose="batch")
        batch_job = client.batches.create(
            input_file_id=uploaded.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "task": "uml-diagram-audit",
                "model": model,
                "request_count_file": str(requests_path.name),
            },
        )
    except Exception:
        logger.exception("Batch submission failed.")
        return None

    logger.info("Batch job submitted. id=%s status=%s", batch_job.id, batch_job.status)
    return batch_job.id, str(batch_job.status)

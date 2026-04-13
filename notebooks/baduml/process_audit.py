"""3. Process OpenAI Batch audit results into a gold dataset.

Reads the Batch output JSONL and audit_id_mapping.json, copies audited images
into data/vision-training/gold/{baduml,gooduml}/, writes conflicts.csv for
cases where the AI classification differs from the original source label, and
produces gold_manifest.jsonl by filtering manifest.jsonl for the accepted images.
INVALID classifications are skipped.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from notebooks.baduml.models import StudentImageRecord, load_manifest, save_manifest
from src.utils import write_csv

logger = logging.getLogger("__name__")


def _extract_classification_analysis(entry: dict) -> tuple[str, str] | None:
    """Extract (classification, analysis) from a Batch API output entry."""
    try:
        raw_text = entry["response"]["body"]["choices"][0]["message"]["content"]
        payload = json.loads(raw_text)

        cls = payload.get("classification", "").strip().upper()
        analysis = payload.get("analysis", "").strip()

        if cls not in {"GOODUML", "BADUML", "INVALID"}:
            return None

        return cls, analysis

    except KeyError, IndexError, TypeError, json.JSONDecodeError, AttributeError:
        return None


def _unique_dest(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    i = 2
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def run(
    *,
    batch_results: Path,
    mapping_path: Path,
    manifest_path: Path,
    gold_dir: Path,
    conflicts_csv: Path,
    gold_manifest_path: Path,
) -> int:
    if not batch_results.is_file():
        logger.error("Batch results file missing: %s", batch_results)
        return 1
    if not mapping_path.is_file():
        logger.error(
            "Mapping file missing: %s. Run 02_prepare_audit.py first.", mapping_path
        )
        return 1

    with mapping_path.open("r", encoding="utf-8") as fh:
        id_mapping: dict[str, dict[str, str]] = json.load(fh)
    logger.info("Loaded %d entries from %s", len(id_mapping), mapping_path)

    (gold_dir / "gooduml").mkdir(parents=True, exist_ok=True)
    (gold_dir / "baduml").mkdir(parents=True, exist_ok=True)

    good_count = 0
    bad_count = 0
    invalid_count = 0
    unresolved_count = 0
    parse_failures = 0
    processed = 0
    conflicts: list[dict[str, str]] = []

    # Maps source image path string to (analysis, classification, dest_path).
    # Used to enrich the manifest after processing.
    source_to_result: dict[str, tuple[str, str, Path]] = {}

    with batch_results.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            raw = line.strip()
            if not raw:
                continue
            processed += 1

            try:
                entry = json.loads(raw)
            except Exception:
                parse_failures += 1
                logger.warning("Invalid JSON at line %d", line_no)
                continue

            custom_id = entry.get("custom_id")
            if not isinstance(custom_id, str):
                parse_failures += 1
                logger.warning("Missing custom_id at line %d", line_no)
                continue

            parsed = _extract_classification_analysis(entry)
            if parsed is None:
                parse_failures += 1
                logger.warning("Missing model payload for custom_id=%s", custom_id)
                continue

            classification, analysis = parsed

            if classification == "INVALID":
                invalid_count += 1
                continue

            entry_info = id_mapping.get(custom_id)
            if entry_info is None:
                unresolved_count += 1
                logger.warning("custom_id not found in mapping: %s", custom_id)
                continue

            source_path = Path(entry_info["source_path"])
            original_label = entry_info["label"]
            if not source_path.exists():
                unresolved_count += 1
                logger.warning("Source image missing on disk: %s", source_path)
                continue

            dest_dir = gold_dir / (
                "gooduml" if classification == "GOODUML" else "baduml"
            )
            dest_path = _unique_dest(dest_dir / source_path.name)
            shutil.copy2(source_path, dest_path)

            if classification == "GOODUML":
                good_count += 1
            else:
                bad_count += 1

            source_to_result[str(source_path)] = (analysis, classification, dest_path)

            if original_label.upper() != classification:
                conflicts.append(
                    {
                        "custom_id": custom_id,
                        "source_path": str(source_path),
                        "original_label": original_label,
                        "classification": classification,
                        "destination_file": str(dest_path),
                    }
                )

    write_csv(
        conflicts_csv,
        conflicts,
        fieldnames=[
            "custom_id",
            "source_path",
            "original_label",
            "classification",
            "destination_file",
        ],
    )

    # Build gold_manifest.jsonl by filtering the raw manifest to audited images.
    manifest_records = load_manifest(manifest_path) if manifest_path.is_file() else []
    if not manifest_records:
        logger.warning(
            "Raw manifest not found or empty at %s; gold manifest will be empty",
            manifest_path,
        )

    gold_records: list[StudentImageRecord] = []
    for rec in manifest_records:
        result = source_to_result.get(rec.image_path)
        if result is None:
            continue
        analysis, classification, dest_path = result
        gold_records.append(
            StudentImageRecord(
                student_id=rec.student_id,
                image_path=str(dest_path),
                image_file=dest_path.name,
                label=classification,
                cohort_year=rec.cohort_year,
                task_variant=rec.task_variant,
                source_doc=rec.source_doc,
                analysis=analysis,
            )
        )
    save_manifest(gold_records, gold_manifest_path)

    logger.info("Processed: %d", processed)
    logger.info("Gold GOODUML: %d", good_count)
    logger.info("Gold BADUML: %d", bad_count)
    logger.info("Discarded INVALID: %d", invalid_count)
    logger.info("Unresolved: %d", unresolved_count)
    logger.info("Parse failures: %d", parse_failures)
    logger.info("Conflicts: %d -> %s", len(conflicts), conflicts_csv)
    logger.info(
        "Gold manifest: %d records -> %s", len(gold_records), gold_manifest_path
    )
    return 0

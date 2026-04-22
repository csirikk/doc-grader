"""3. Process OpenAI Batch audit results into an audit dataset.

Author: Matúš Csirik

Reads the Batch output JSONL and audit_id_mapping.json, copies audited images
into data/vision-training/audit/{baduml,gooduml}/, writes conflicts.csv for
cases where the AI classification differs from the original source label, and
produces audit_manifest.jsonl by filtering manifest.jsonl for the accepted images.
INVALID classifications are skipped.
"""

import json
import logging
import shutil
from pathlib import Path

from doc_grader.utils import write_csv

from .models import (
    StudentImageRecord,
    load_manifest,
    save_manifest,
)

logger = logging.getLogger(__name__)


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
    """Return a non-colliding Path by appending an index if needed.

    If ``path`` does not exist it is returned unchanged. Otherwise a suffix
    ``_{n}`` is appended to the stem with an increasing counter until a
    free filename is found.
    """

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
    audit_dir: Path,
    conflicts_csv: Path,
    audit_manifest_path: Path,
) -> int:
    """Process a Batch audit results file and assemble an audit manifest.

    Args:
        batch_results: Path to the OpenAI Batch JSONL output.
        mapping_path: Path to the audit id mapping JSON.
        manifest_path: Path to the raw manifest JSONL produced earlier.
        audit_dir: Directory to place audited images into subfolders.
        conflicts_csv: CSV path to write conflict rows where labels differ.
        audit_manifest_path: Destination JSONL path for the filtered audit manifest.

    Returns:
        Exit code integer (0 on success, non-zero on failure).
    """

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

    (audit_dir / "gooduml").mkdir(parents=True, exist_ok=True)
    (audit_dir / "baduml").mkdir(parents=True, exist_ok=True)

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

            dest_dir = audit_dir / (
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

    # Build audit_manifest.jsonl by filtering the raw manifest to audited images.
    manifest_records = load_manifest(manifest_path) if manifest_path.is_file() else []
    if not manifest_records:
        logger.warning(
            "Raw manifest not found or empty at %s; audit manifest will be empty",
            manifest_path,
        )

    audit_records: list[StudentImageRecord] = []
    for rec in manifest_records:
        result = source_to_result.get(rec.image_path)
        if result is None:
            continue
        analysis, classification, dest_path = result
        audit_records.append(
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
    save_manifest(audit_records, audit_manifest_path)

    logger.info("Processed: %d", processed)
    logger.info("Audit GOODUML: %d", good_count)
    logger.info("Audit BADUML: %d", bad_count)
    logger.info("Discarded INVALID: %d", invalid_count)
    logger.info("Unresolved: %d", unresolved_count)
    logger.info("Parse failures: %d", parse_failures)
    logger.info("Conflicts: %d -> %s", len(conflicts), conflicts_csv)
    logger.info(
        "Audit manifest: %d records -> %s", len(audit_records), audit_manifest_path
    )
    return 0

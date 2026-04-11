from __future__ import annotations

import hashlib
import logging
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import dataset_parser
import pandas as pd

from src.parsers.parser import DocumentParser
from src.utils import configure_logging, write_csv

VALID_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}

VARIANT_MAPPING: dict[str, list[str]] = {
    "int": ["interpret", "int"],
    "par": ["parse", "parser"],
    "php": ["php"],
    "py": ["python", "py"],
}

logger = logging.getLogger(__name__)


def is_ignored(path_obj: Path) -> bool:
    return "__MACOSX" in path_obj.parts or path_obj.name.startswith(".")


def path_token(path_obj: Path) -> str:
    normalised = str(path_obj).lower().replace("\\", "/")
    digest = hashlib.blake2b(normalised.encode("utf-8"), digest_size=4).hexdigest()
    stem = re.sub(r"[^a-z0-9]+", "_", path_obj.stem.lower()).strip("_") or "file"
    return f"{stem}_{digest}"


def find_student_dir(
    *, ipp_dir: Path, year_str: str, variant_str: str, student_id: str
) -> tuple[Path | None, str | None]:
    if not year_str or year_str in ("Unknown", "nan"):
        return None, None

    cohort_dir = ipp_dir / f"ipp{year_str}"
    if not cohort_dir.exists():
        return None, None

    variant_key = variant_str.lower()
    possible_variants = VARIANT_MAPPING.get(variant_key)

    if not possible_variants:
        return None, None

    for variant_name in possible_variants:
        candidate = cohort_dir / variant_name / student_id
        if candidate.exists():
            return candidate, variant_name

    return None, None


def record_image(
    *,
    output_rows: list[dict[str, str]],
    student_id: str,
    assessment_variant: str,
    source_variant: str | None,
    image_file: str,
    cohort_year: str,
    label: str,
    source: str,
    verified_path: str,
    source_doc: str,
    extraction_method: str,
    doc_item_ref: str | None = None,
) -> None:
    output_rows.append(
        {
            "student_id": student_id,
            "assessment_variant": assessment_variant,
            "source_variant": source_variant or "",
            "image_file": image_file,
            "cohort_year": cohort_year,
            "label": label,
            "source": source,
            "verified_path": verified_path,
            "source_doc": source_doc,
            "extraction_method": extraction_method,
            "doc_item_ref": doc_item_ref or "",
        }
    )


def extract_docling_pdf_images(
    *,
    doc_parser: DocumentParser,
    pdf_path: Path,
    submission_dir: Path,
    output_dir: Path,
    output_rows: list[dict[str, str]],
    student_id: str,
    assessment_variant: str,
    source_variant: str | None,
    cohort_year: str,
    label: str,
    verified_path: str,
) -> int:
    parse_output = doc_parser.parse(pdf_path)
    if not parse_output.ir:
        return 0

    extracted = 0
    relative_pdf = pdf_path.relative_to(submission_dir)
    pdf_token = path_token(relative_pdf)

    for picture_index, (cref, picture_item) in enumerate(
        parse_output.ir.picture_items.items()
    ):
        image_obj = getattr(picture_item, "image", None)
        pil_image = getattr(image_obj, "pil_image", None) if image_obj else None
        if pil_image is None:
            continue

        image_name = f"{student_id}_{assessment_variant}_{pdf_token}_docling_{picture_index:03d}.png"
        image_path = output_dir / image_name
        pil_image.save(image_path, format="PNG")

        record_image(
            output_rows=output_rows,
            student_id=student_id,
            assessment_variant=assessment_variant,
            source_variant=source_variant,
            image_file=image_name,
            cohort_year=cohort_year,
            label=label,
            source="pdf",
            verified_path=verified_path,
            source_doc=pdf_path.name,
            extraction_method="docling_picture_item",
            doc_item_ref=cref,
        )
        extracted += 1

    return extracted


def copy_markdown_images(
    *,
    markdown_path: Path,
    submission_dir: Path,
    output_dir: Path,
    output_rows: list[dict[str, str]],
    student_id: str,
    assessment_variant: str,
    source_variant: str | None,
    cohort_year: str,
    label: str,
    verified_path: str,
) -> int:
    copied = 0
    seen_paths: set[Path] = set()

    try:
        markdown_text = markdown_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        logger.exception("Failed to read markdown file %s", markdown_path)
        return 0

    submission_root = submission_dir.resolve()
    relative_md = markdown_path.relative_to(submission_dir)
    md_token = path_token(relative_md)

    matches = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", markdown_text)
    for raw_uri in matches:
        clean_uri = unquote(raw_uri.strip().split()[0])
        if clean_uri.startswith(("http://", "https://", "data:")):
            continue

        candidate = (submission_root / Path(clean_uri)).resolve()
        if not candidate.is_relative_to(submission_root):
            continue

        if (
            not candidate.is_file()
            or candidate.suffix.lower() not in VALID_IMAGE_SUFFIXES
        ):
            continue

        if candidate in seen_paths:
            continue

        seen_paths.add(candidate)

        asset_token = path_token(relative_asset)
        image_name = f"{student_id}_{assessment_variant}_{md_token}_{asset_token}{candidate.suffix.lower()}"
        output_path = output_dir / image_name
        shutil.copy2(candidate, output_path)

        record_image(
            output_rows=output_rows,
            student_id=student_id,
            assessment_variant=assessment_variant,
            source_variant=source_variant,
            image_file=image_name,
            cohort_year=cohort_year,
            label=label,
            source="markdown",
            verified_path=verified_path,
            source_doc=markdown_path.name,
            extraction_method="manual_markdown_copy",
            doc_item_ref="",
        )
        copied += 1

    return copied


def extract_for_records(
    *,
    rows: pd.DataFrame,
    ipp_dir: Path,
    output_dir: Path,
    label: str,
    doc_parser: DocumentParser,
) -> tuple[list[dict[str, str]], int, int, int, set[str]]:
    records: list[dict[str, str]] = []
    extracted_count = 0
    missing_docs = 0
    no_images_found = 0
    success_docs: set[str] = set()

    for row in rows.to_dict("records"):
        student_id = str(row["id"])
        year = str(row.get("year", ""))
        variant = str(row.get("task_variant", ""))

        student_dir, source_variant = find_student_dir(
            ipp_dir=ipp_dir, year_str=year, variant_str=variant, student_id=student_id
        )
        if not student_dir:
            missing_docs += 1
            logger.warning(
                "Missing student path for %s %s -> %s", year, variant, student_id
            )
            continue

        verified_path = str(student_dir.relative_to(ipp_dir))
        found_any = False

        pdf_files = sorted(
            path for path in student_dir.rglob("*.pdf") if not is_ignored(path)
        )
        markdown_files = sorted(
            path for path in student_dir.rglob("*.md") if not is_ignored(path)
        )

        for pdf_path in pdf_files:
            extracted = extract_docling_pdf_images(
                doc_parser=doc_parser,
                pdf_path=pdf_path,
                submission_dir=student_dir,
                output_dir=output_dir,
                output_rows=records,
                student_id=student_id,
                assessment_variant=variant,
                source_variant=source_variant,
                cohort_year=year,
                label=label,
                verified_path=verified_path,
            )
            extracted_count += extracted
            if extracted > 0:
                found_any = True

        for markdown_path in markdown_files:
            copied = copy_markdown_images(
                markdown_path=markdown_path,
                submission_dir=student_dir,
                output_dir=output_dir,
                output_rows=records,
                student_id=student_id,
                assessment_variant=variant,
                source_variant=source_variant,
                cohort_year=year,
                label=label,
                verified_path=verified_path,
            )
            extracted_count += copied
            if copied > 0:
                found_any = True

        if found_any:
            success_docs.add(student_id)
        else:
            no_images_found += 1

    return records, extracted_count, missing_docs, no_images_found, success_docs


def main() -> int:
    configure_logging(logging.INFO)

    # Simpler setup without argparse
    data_dir = (PROJECT_ROOT / "data").resolve()
    csv_path = data_dir / "clean_ipp_data.csv"
    ipp_dir = data_dir / "ipp"
    vision_dir = data_dir / "vision-training"
    bad_dir = vision_dir / "baduml"
    good_dir = vision_dir / "gooduml"

    vision_dir.mkdir(parents=True, exist_ok=True)
    bad_dir.mkdir(exist_ok=True)
    good_dir.mkdir(exist_ok=True)

    if not csv_path.exists():
        logger.info("Clean data not found at %s. Running dataset_parser...", csv_path)
        dataset_parser.main()

    df = pd.read_csv(csv_path)
    baduml_df = df[df["code"] == "BADUML"].copy()
    logger.info("Found %d BADUML records", len(baduml_df))

    doc_parser = DocumentParser()
    bad_records, extracted_count, missing_docs, no_images_found, success_docs = (
        extract_for_records(
            rows=baduml_df,
            ipp_dir=ipp_dir,
            output_dir=bad_dir,
            label="BADUML",
            doc_parser=doc_parser,
        )
    )

    logger.info("Total BADUML records evaluated: %d", len(baduml_df))
    logger.info("Could not find document folders for %d BADUML records", missing_docs)
    logger.info("Records yielding at least one image: %d", len(success_docs))
    logger.info("Records yielding no images: %d", no_images_found)
    logger.info("Total images saved to %s: %d", bad_dir, extracted_count)

    if bad_records:
        bad_metadata_csv = vision_dir / "baduml_dataset.csv"
        write_csv(bad_metadata_csv, bad_records)
        logger.info("Dataset metadata saved to %s", bad_metadata_csv)

    target_good_docs = len(success_docs)
    logger.info(
        "Targeting %d high-scoring documents to balance the dataset", target_good_docs
    )

    invalid_ids = df.loc[df["code"].isin(["BADUML", "NOUML"]), "id"]

    unique_docs_df = df.loc[
        ~df["id"].isin(invalid_ids), ["id", "year", "task_variant", "doc_points"]
    ].drop_duplicates()
    good_docs_df = unique_docs_df.sort_values(by="doc_points", ascending=False)

    selected_good_docs = good_docs_df.head(target_good_docs)
    good_records, good_extracted_count, _, _, good_success_docs = extract_for_records(
        rows=selected_good_docs,
        ipp_dir=ipp_dir,
        output_dir=good_dir,
        label="GOODUML",
        doc_parser=doc_parser,
    )

    logger.info("Total documents evaluated to reach target: %d", len(good_success_docs))
    logger.info("Total GOODUML images saved to %s: %d", good_dir, good_extracted_count)

    if bad_records and good_records:
        combined_rows = bad_records + good_records
        combined_csv = vision_dir / "vision_training_dataset.csv"
        write_csv(combined_csv, combined_rows)
        logger.info("Combined dataset metadata saved to %s", combined_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

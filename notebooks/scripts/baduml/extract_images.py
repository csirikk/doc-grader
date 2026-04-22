"""1. Extract and preprocess images from student submissions.

Author: Matúš Csirik

Reads grading data from clean_ipp_data.csv, locates each student's submitted
documents, extracts images (from PDFs and Markdown files via the docling IR),
resizes and deduplicates images, and writes manifest.jsonl.
"""

import base64
import hashlib
import io
import logging
import shutil
from typing import TYPE_CHECKING
from urllib.parse import unquote

import pandas as pd
from PIL import Image

from doc_grader.parsers.parser import DocumentParser

from .models import StudentImageRecord

if TYPE_CHECKING:
    from pathlib import Path

MAX_IMAGE_DIM = 2048
MIN_IMAGE_SIDE = 128

VARIANT_MAPPING: dict[str, list[str]] = {
    "int": ["interpret", "int"],
    "par": ["parse", "parser"],
    "php": ["php"],
    "py": ["python", "py"],
}

logger = logging.getLogger(__name__)


def _is_ignored(path: Path) -> bool:
    return "__MACOSX" in path.parts or path.name.startswith(".")


def _path_token(path: Path) -> str:
    normalised = str(path).lower().replace("\\", "/")
    digest = hashlib.blake2b(normalised.encode("utf-8"), digest_size=4).hexdigest()
    stem = path.stem.lower()
    stem = "".join(c if c.isalnum() else "_" for c in stem).strip("_") or "file"
    return f"{stem}_{digest}"


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) > MAX_IMAGE_DIM:
        ratio = MAX_IMAGE_DIM / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
    return img


def _find_student_dir(
    ipp_dir: Path, year_str: str, variant_str: str, student_id: str
) -> tuple[Path | None, str | None]:
    if not year_str or year_str in ("Unknown", "nan"):
        return None, None
    cohort_dir = ipp_dir / f"ipp{year_str}"
    if not cohort_dir.exists():
        return None, None
    for variant_name in VARIANT_MAPPING.get(variant_str.lower()) or []:
        candidate = cohort_dir / variant_name / student_id
        if candidate.exists():
            return candidate, variant_name
    return None, None


def _save_image(img: Image.Image, path: Path, seen_hashes: set[str]) -> bool:
    """Encode img to PNG and write to disk. Returns True if saved, False if dupe."""
    h = hashlib.sha1(img.tobytes()).hexdigest()
    if h in seen_hashes:
        return False
    seen_hashes.add(h)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    path.write_bytes(buf.getvalue())
    return True


# --- Per-document extraction ---


_RASTER_EXTS = {".png", ".jpg", ".jpeg"}


def _pil_from_picture(
    pic: object, idx: int, md_image_uris: list[str], doc_dir: Path
) -> Image.Image | None:
    """Return a PIL image for a docling PictureItem, or None if unavailable.
    PDF: docling writes rendered bitmaps as base64 URIs.
    MD: resolve the path from md_image_uris[idx].
    """
    uri = str(getattr(getattr(pic, "image", None), "uri", None) or "")
    if uri.startswith("data:image/"):
        return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))

    if idx < len(md_image_uris):
        candidate = (doc_dir / unquote(md_image_uris[idx])).resolve()
        if candidate.suffix.lower() in _RASTER_EXTS and candidate.exists():
            pil = Image.open(candidate)
            pil.load()
            return pil

    return None


def _extract_document_images(
    *,
    doc_parser: DocumentParser,
    doc_path: Path,
    submission_dir: Path,
    output_dir: Path,
    student_id: str,
    assessment_variant: str,
    cohort_year: str,
    label: str,
    seen_hashes: set[str],
) -> list[StudentImageRecord]:
    """Extract images from a single document."""
    parse_output = doc_parser.parse(doc_path)
    if not parse_output.ir:
        return []

    ir = parse_output.ir
    doc_token = _path_token(doc_path.relative_to(submission_dir))
    records: list[StudentImageRecord] = []

    for i, pic in enumerate(ir.docling_doc.pictures):
        pil_image = _pil_from_picture(pic, i, ir.md_image_uris, doc_path.parent)
        if pil_image is None:
            continue

        img = pil_image.convert("RGB")
        w, h = img.size
        if min(w, h) < MIN_IMAGE_SIDE:
            continue
        img = _resize(img)

        image_name = f"{student_id}_{assessment_variant}_{doc_token}_{i:03d}.png"
        image_path = output_dir / image_name
        if not _save_image(img, image_path, seen_hashes):
            continue

        records.append(
            StudentImageRecord(
                student_id=student_id,
                image_path=str(image_path),
                image_file=image_name,
                label=label,
                cohort_year=cohort_year,
                task_variant=assessment_variant,
                source_doc=doc_path.name,
            )
        )

    return records


def _extract_standalone_images(
    *,
    submission_dir: Path,
    output_dir: Path,
    student_id: str,
    assessment_variant: str,
    cohort_year: str,
    label: str,
    seen_hashes: set[str],
) -> list[StudentImageRecord]:
    """Scan the submission directory for raster image files not in documents."""
    records: list[StudentImageRecord] = []
    for img_path in sorted(submission_dir.rglob("*")):
        if _is_ignored(img_path):
            continue
        if img_path.suffix.lower() not in _RASTER_EXTS:
            continue
        try:
            pil_image = Image.open(img_path)
            pil_image.load()
        except Exception:
            continue

        img = pil_image.convert("RGB")
        w, h = img.size
        if min(w, h) < MIN_IMAGE_SIDE:
            continue

        needs_resize = max(w, h) > MAX_IMAGE_DIM
        doc_token = _path_token(img_path.relative_to(submission_dir))

        if not needs_resize:
            hsh = hashlib.sha1(img.tobytes()).hexdigest()

            if hsh in seen_hashes:
                continue
            seen_hashes.add(hsh)
            image_name = (
                f"{student_id}_{assessment_variant}_{doc_token}"
                f"{img_path.suffix.lower()}"
            )
            image_path = output_dir / image_name
            shutil.copy2(img_path, image_path)
        else:
            img = _resize(img)
            image_name = f"{student_id}_{assessment_variant}_{doc_token}.png"
            image_path = output_dir / image_name

            # Using the updated _save_image logic which returns a boolean
            if not _save_image(img, image_path, seen_hashes):
                continue

        records.append(
            StudentImageRecord(
                student_id=student_id,
                image_path=str(image_path),
                image_file=image_name,
                label=label,
                cohort_year=cohort_year,
                task_variant=assessment_variant,
                source_doc=img_path.name,
            )
        )
        logger.debug("Standalone image: %s", img_path)

    return records


def extract_records(
    rows: pd.DataFrame,
    *,
    ipp_dir: Path,
    output_dir: Path,
    label: str,
    doc_parser: DocumentParser,
    seen_hashes: set[str],
) -> tuple[list[StudentImageRecord], set[str]]:
    """Extract and preprocess images for each row in the DataFrame.

    Args:
        rows: DataFrame with rows describing student submissions.
        ipp_dir: Root directory containing student submission folders.
        output_dir: Directory to write processed images into.
        label: Label to assign to produced records (e.g. 'BADUML' or 'GOODUML').
        doc_parser: DocumentParser instance used to extract images from docs.
        seen_hashes: Mutable set to track deduplicated image hashes.

    Returns:
        A tuple (records, success_ids) where ``records`` is a list of
        StudentImageRecord objects and ``success_ids`` is the set of student
        ids that yielded at least one image.
    """
    records: list[StudentImageRecord] = []
    success_ids: set[str] = set()
    output_dir.mkdir(parents=True, exist_ok=True)

    for row in rows.to_dict("records"):
        student_id = str(row["id"])
        year = str(row.get("year", ""))
        variant = str(row.get("task_variant", ""))

        student_dir, _ = _find_student_dir(ipp_dir, year, variant, student_id)
        if not student_dir:
            logger.warning(
                "No submission directory for %s %s -> %s", year, variant, student_id
            )
            continue

        found_any = False

        for doc_path in sorted(
            p
            for glob in ("*.pdf", "*.md")
            for p in student_dir.rglob(glob)
            if not _is_ignored(p)
        ):
            new = _extract_document_images(
                doc_parser=doc_parser,
                doc_path=doc_path,
                submission_dir=student_dir,
                output_dir=output_dir,
                student_id=student_id,
                assessment_variant=variant,
                cohort_year=year,
                label=label,
                seen_hashes=seen_hashes,
            )
            records.extend(new)
            if new:
                found_any = True

        if not found_any:
            # Pick up standalone raster files not linked from any document.
            new = _extract_standalone_images(
                submission_dir=student_dir,
                output_dir=output_dir,
                student_id=student_id,
                assessment_variant=variant,
                cohort_year=year,
                label=label,
                seen_hashes=seen_hashes,
            )
            records.extend(new)
            if new:
                found_any = True

        if found_any:
            success_ids.add(student_id)

    return records, success_ids


def run(*, csv_path: Path, ipp_dir: Path, output_dir: Path) -> list[StudentImageRecord]:
    """Run the extraction pipeline for the dataset described by ``csv_path``.

    Args:
        csv_path: Path to the CSV file listing grading rows.
        ipp_dir: Root directory containing student submission folders.
        output_dir: Base directory to place extracted image sets.

    Returns:
        A combined list of StudentImageRecord objects for both BADUML and GOODUML.
    """

    df = pd.read_csv(csv_path)
    doc_parser = DocumentParser()
    seen_hashes: set[str] = set()

    baduml_df = df[df["code"] == "BADUML"].copy()
    logger.info("Found %d BADUML records", len(baduml_df))

    bad_records, baduml_success = extract_records(
        baduml_df,
        ipp_dir=ipp_dir,
        output_dir=output_dir / "baduml",
        label="BADUML",
        doc_parser=doc_parser,
        seen_hashes=seen_hashes,
    )
    logger.info(
        "BADUML: %d images from %d students",
        len(bad_records),
        len(baduml_success),
    )

    # Exclude any student with a BADUML or NOUML finding from the good set.
    invalid_ids = df.loc[df["code"].isin(["BADUML", "NOUML"]), "id"]
    good_candidates = (
        df.loc[
            ~df["id"].isin(invalid_ids),
            ["id", "year", "task_variant", "doc_points"],
        ]
        .drop_duplicates()
        .sort_values("doc_points", ascending=False)
        .head(len(baduml_success))
    )
    logger.info("Targeting %d high-scoring documents for GOODUML", len(good_candidates))

    good_records, gooduml_success = extract_records(
        good_candidates,
        ipp_dir=ipp_dir,
        output_dir=output_dir / "gooduml",
        label="GOODUML",
        doc_parser=doc_parser,
        seen_hashes=seen_hashes,
    )
    logger.info(
        "GOODUML: %d images from %d students",
        len(good_records),
        len(gooduml_success),
    )

    return bad_records + good_records

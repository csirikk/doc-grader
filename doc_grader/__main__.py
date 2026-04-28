"""doc-grader: Intelligent Tool for Assessment of Student Project Documentations

Author: Matúš Csirik, 2026

Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""

import argparse
import json
import logging
import os
import sys
import time
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

# Analysers
from .analysers.asset_analyser import AssetAnalyser
from .analysers.content_analyser import ContentAnalyser
from .analysers.grammar_analyser import GrammarAnalyser
from .analysers.integrity_analyser import IntegrityAnalyser
from .analysers.structure_analyser import StructureAnalyser
from .llm_client import LLMClient, merge_usage
from .rule_engine import RuleEngine
from .schemas.config import AppConfig, load_app_config, load_rulebook
from .scorer import Scorer
from .utils import (
    build_doc_info,
    build_run_summary,
    compute_config_hash,
    configure_logging,
    findings_to_csv_rows,
    findings_to_grader_row,
    format_finding_short,
    log_json,
    merge_stage_timings,
    reset_id_counters,
    write_csv,
    write_json,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from schemas.llm import Rulebook

    from .analysers.base_analyser import BaseAnalyser
    from .schemas.document import Document
    from .schemas.finding import Finding

logger = logging.getLogger(__name__)

ANALYSER_LIST: dict[str, type[BaseAnalyser]] = {
    StructureAnalyser.analyser_id: StructureAnalyser,
    ContentAnalyser.analyser_id: ContentAnalyser,
    AssetAnalyser.analyser_id: AssetAnalyser,
    IntegrityAnalyser.analyser_id: IntegrityAnalyser,
    GrammarAnalyser.analyser_id: GrammarAnalyser,
}
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"
_DEFAULT_CONFIG = _CONFIG_DIR / "default.json"
_RULEBOOK_PATH = _CONFIG_DIR / "rulebook.json"


def discover_cases(
    inputs: list[str],
    *,
    expected_filename: str | None,
    allowed_extensions: list[str] | None,
) -> Iterator[tuple[Path, str]]:
    """Yield ``(doc_path, student_id)`` pairs for CLI inputs."""
    configured_extensions = allowed_extensions or [".pdf", ".md"]
    allowed_suffixes = {
        (extension if extension.startswith(".") else f".{extension}").lower()
        for extension in configured_extensions
    }

    for raw_input in inputs:
        path = Path(raw_input)

        if path.is_file():
            yield path, path.stem
            continue

        if not path.is_dir():
            logger.warning("Input not found or invalid: %s", path)
            continue

        pending_dirs = deque([path])
        while pending_dirs:
            candidate_dir = pending_dirs.popleft()
            files = sorted(
                candidate
                for candidate in candidate_dir.iterdir()
                if candidate.is_file()
            )
            doc = None

            if expected_filename is not None:
                doc = next(
                    (
                        candidate
                        for candidate in files
                        if candidate.stem == expected_filename
                    ),
                    None,
                )

            if doc is None:
                doc = next(
                    (
                        candidate
                        for candidate in files
                        if candidate.suffix.lower() in allowed_suffixes
                    ),
                    None,
                )

            if doc is not None:
                yield doc, candidate_dir.name
                if candidate_dir == path:
                    break
                continue

            if candidate_dir == path:
                subdirs = sorted(
                    (candidate for candidate in path.iterdir() if candidate.is_dir()),
                    key=lambda candidate: candidate.name,
                )
                if subdirs:
                    pending_dirs.extend(subdirs)
                else:
                    logger.warning("No document found in: %s", path)
                    missing_name = expected_filename or "missing_document"
                    yield path / missing_name, path.name
            else:
                logger.warning("No document found in: %s", candidate_dir)
                missing_name = expected_filename or "missing_document"
                yield (
                    candidate_dir / missing_name,
                    candidate_dir.name,
                )


def _load_app_config(config_path: str | None) -> AppConfig:
    """Load application config from JSON file, falling back to config/default.json."""
    return load_app_config(Path(config_path) if config_path else _DEFAULT_CONFIG)


def _run_analysers(
    ir: Document, config: AppConfig, rulebook: Rulebook, llm_client: Any | None = None
) -> tuple[list[Finding], dict, dict[str, float], dict[str, list[str]]]:
    findings: list[Finding] = []
    accumulated_usage: dict = {}
    stage_times: dict[str, float] = {}
    analyser_errors: dict[str, list[str]] = {}

    for analyser_cfg in config.analysers:
        if not analyser_cfg.enabled:
            continue

        analyser_class = ANALYSER_LIST.get(analyser_cfg.analyser_id)
        if analyser_class is None:
            logger.warning(
                "Analyser '%s' is enabled but not registered", analyser_cfg.analyser_id
            )
            continue

        analyser_params = analyser_cfg.params.copy()
        analyser_params.setdefault("course", config.course)
        analyser_params.setdefault("language", ir.language)
        analyser_params.setdefault("disabled_codes", config.disabled_codes)
        analyser_params["model"] = analyser_cfg.model
        analyser_params["temperature"] = analyser_cfg.temperature

        try:
            instance = analyser_class()
            _t0 = time.monotonic()
            result = instance.analyse(
                doc=ir,
                rulebook=rulebook,
                params=analyser_params,
                llm_client=llm_client,
            )
            stage_times[analyser_cfg.analyser_id] = round(time.monotonic() - _t0, 2)
            if result:
                findings.extend(result)
            analyser_usage = getattr(instance, "_accumulated_usage", None)
            if analyser_usage is not None:
                accumulated_usage = merge_usage(accumulated_usage, analyser_usage)
            # collect analyser diagnostics
            instance_diagnostics = getattr(instance, "_diagnostics", None)
            if instance_diagnostics:
                analyser_errors.setdefault(analyser_cfg.analyser_id, []).extend(
                    instance_diagnostics
                )
        except Exception:
            import traceback

            tb = traceback.format_exc()
            logger.exception("Error running analyser %s", analyser_cfg.analyser_id)
            analyser_errors.setdefault(analyser_cfg.analyser_id, []).append(tb)
        finally:
            if llm_client is not None and hasattr(llm_client, "consume_diagnostics"):
                try:
                    llm_diagnostics = llm_client.consume_diagnostics()
                except Exception:
                    llm_diagnostics = []
                    logger.debug(
                        "Could not consume LLM diagnostics for %s",
                        analyser_cfg.analyser_id,
                        exc_info=True,
                    )
                if llm_diagnostics:
                    analyser_errors.setdefault(analyser_cfg.analyser_id, []).extend(
                        llm_diagnostics
                    )

    return findings, accumulated_usage, stage_times, analyser_errors


def _run_id_from_config(config: AppConfig) -> str:
    if config.run_id:
        return config.run_id
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _config_for_hash(config: AppConfig) -> dict[str, Any]:
    payload = config.model_dump(mode="json", exclude_none=True)
    payload.pop("run_id", None)
    return payload


def _has_completed_outputs(file_outdir: Path) -> bool:
    """Return ``True`` when per-document final outputs already exist."""
    required_files = ("findings.json", "info.json")
    return all((file_outdir / filename).is_file() for filename in required_files)


def _load_existing_findings_for_csv(file_outdir: Path) -> list[Finding] | None:
    """Load existing findings from disk for CSV export reuse."""
    findings_path = file_outdir / "findings.json"
    if not findings_path.is_file():
        return None

    try:
        payload = json.loads(findings_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            logger.warning(
                "Cannot reuse findings from %s: expected a list payload", findings_path
            )
            return None

        from .schemas.finding import Finding

        return [Finding.model_validate(item) for item in payload]
    except Exception:
        logger.warning(
            "Cannot reuse findings from %s for CSV export",
            findings_path,
            exc_info=True,
        )
        return None


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point for the doc-grader pipeline.

    Args:
        argv: Optional list of command-line arguments. When omitted the
            arguments from ``sys.argv`` are used by ``argparse``.

    Returns:
        Process exit code (0 for success, non-zero for errors).
    """
    load_dotenv()
    arg_parser = argparse.ArgumentParser(prog="project")
    arg_parser.add_argument(
        "inputs", nargs="+", help="One or more paths to the input files (.md, .pdf)"
    )
    arg_parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    arg_parser.add_argument(
        "-o", "--out", default="out/default/", help="Output directory for findings"
    )
    arg_parser.add_argument(
        "-c",
        "--config",
        default=str(_DEFAULT_CONFIG),
        help="Path to JSON config file for analysers",
    )
    arg_parser.add_argument(
        "--csv-out",
        default=None,
        metavar="PATH",
        help=(
            "If provided, write a grader-style CSV (one row per doc) to this path."
            "Cols: points,comment,bonus_points,points_mentioned_in_comment,id,doc_type."
            "Points and bonus left empty; comment is built from findings."
        ),
    )
    arg_parser.add_argument(
        "--clean-csv-out",
        default=None,
        metavar="PATH",
        help=(
            "If provided, write all findings as a CSV to this path. "
            "Cols match the clean_ipp_data.csv schema from dataset_parser.py, "
            "enabling direct comparison with the ground-truth assessment dataset."
        ),
    )
    arg_parser.add_argument(
        "--skip-existing",
        action="store_true",
        help=(
            "Skip documents that already have findings.json and info.json "
            "in their output directory."
        ),
    )
    args = arg_parser.parse_args(argv)

    if args.debug:
        configure_logging(logging.DEBUG)
        logger.debug("Debug logging enabled")
    else:
        configure_logging(logging.INFO)

    try:
        config = _load_app_config(args.config)
        rulebook_path = (
            _PROJECT_ROOT / config.rulebook_path
            if config.rulebook_path
            else _RULEBOOK_PATH
        )
        if not rulebook_path.exists():
            logger.error("Rulebook file not found at %s", rulebook_path)
            return 2
        rulebook = load_rulebook(rulebook_path)

    except Exception:
        logger.exception("Failed to load config or rulebook")
        return 2

    llm_client = None
    from .analysers.base_analyser import BaseLLMAnalyser

    need_llm = config.judge or any(
        a_cfg.enabled
        and (ANALYSER_LIST.get(a_cfg.analyser_id) is not None)
        and issubclass(ANALYSER_LIST[a_cfg.analyser_id], BaseLLMAnalyser)
        for a_cfg in config.analysers
    )

    if need_llm:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("An LLM component is enabled but OPENAI_API_KEY is not set.")
            return 2
        llm_client = LLMClient()
        logger.info("LLMClient ready")

    run_id = _run_id_from_config(config)
    config_hash = compute_config_hash(_config_for_hash(config))

    base_outdir = Path(args.out)
    total_run_start = time.monotonic()
    exit_code = 0
    run_usage: dict = {}
    run_stage_timings: dict[str, dict[str, float | int]] = {}
    docs_discovered = 0
    docs_processed = 0
    docs_skipped = 0
    docs_parsed = 0
    docs_failed_parse = 0
    clean_csv_rows: list = []  # accumulated per-finding rows for --clean-csv-out
    grader_rows: list = []  # one row per document for --csv-out

    from .document_parser import DocumentParser

    # Discover all cases first so we can report a total for progress
    cases = list(
        discover_cases(
            args.inputs,
            expected_filename=config.expected_filename,
            allowed_extensions=config.allowed_extensions,
        )
    )
    total_cases = len(cases)
    docs_discovered = total_cases
    logger.info("Discovered %d documents to process", total_cases)

    logger.info("Initialising parser...")
    parser = DocumentParser()
    scorer = Scorer()

    for idx, (path, student_id) in enumerate(cases, start=1):
        logger.info(f"Processing [{idx}/{total_cases}] {path}")

        file_outdir = base_outdir / student_id

        if args.skip_existing and _has_completed_outputs(file_outdir):
            docs_skipped += 1
            logger.info(
                "Skipping already processed document: %s (student_id=%s)",
                path,
                student_id,
            )

            existing_findings = _load_existing_findings_for_csv(file_outdir)
            if args.clean_csv_out and existing_findings is not None:
                clean_csv_rows.extend(
                    findings_to_csv_rows(
                        path,
                        existing_findings,
                        student_id=student_id,
                        max_doc_points=config.max_doc_points,
                    )
                )
            if args.csv_out and existing_findings is not None:
                row = findings_to_grader_row(
                    path,
                    existing_findings,
                    max_doc_points=config.max_doc_points,
                )
                row["id"] = student_id
                grader_rows.append(row)

            if (args.clean_csv_out or args.csv_out) and existing_findings is None:
                logger.warning(
                    (
                        "Skipped %s but existing findings could not be loaded; "
                        "this document will be missing from current CSV outputs"
                    ),
                    path,
                )
            continue

        docs_processed += 1
        reset_id_counters()
        if llm_client:
            pass
        run_start = time.monotonic()
        rule_engine = RuleEngine()

        _parse_t0 = time.monotonic()
        parse_output = parser.parse(
            path,
            run_id=run_id,
            config_hash=config_hash,
            student_id=student_id,
            expected_filename=config.expected_filename,
            allowed_extensions=config.allowed_extensions,
        )
        _parse_elapsed = round(time.monotonic() - _parse_t0, 2)
        parser_findings = parse_output.parser_findings
        ir_doc = parse_output.ir
        doc_stage_times: dict[str, float] = {"parse": _parse_elapsed}

        logger.debug("Parsing done")

        doc_ref = parse_output.doc_ref
        input_payload = doc_ref.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )
        parse_payload = parse_output.parse_meta.model_dump(
            mode="json", by_alias=True, exclude_none=True
        )

        write_json(file_outdir / "parser_findings.json", parser_findings)

        if ir_doc is None:
            docs_failed_parse += 1
            write_json(file_outdir / "raw_findings.json", parser_findings)
            write_json(file_outdir / "findings.json", parser_findings)
            logger.debug(
                "Wrote raw_findings.json and findings.json (%d findings)",
                len(parser_findings),
            )
            info = build_doc_info(
                input_payload=input_payload,
                run_id=run_id,
                config_hash=config_hash,
                course=config.course,
                max_doc_points=config.max_doc_points,
                parse_payload=parse_payload,
                parser_findings_count=len(parser_findings),
                finding_count=len(parser_findings),
                usage_by_model={},
                stage_times=doc_stage_times,
                elapsed_seconds=time.monotonic() - run_start,
            )
            write_json(file_outdir / "info.json", info)
            run_stage_timings = merge_stage_timings(run_stage_timings, doc_stage_times)
            clean_csv_rows.extend(
                findings_to_csv_rows(
                    path,
                    parser_findings,
                    student_id=student_id,
                    max_doc_points=config.max_doc_points,
                )
            )
            row = findings_to_grader_row(
                path, parser_findings, max_doc_points=config.max_doc_points
            )
            row["id"] = student_id
            grader_rows.append(row)

            logger.warning("Parsing failed for %s", path)
            continue

        docs_parsed += 1
        write_json(file_outdir / "docling.json", ir_doc.docling_doc)
        write_json(file_outdir / "ir.json", ir_doc)

        (
            analyser_findings,
            doc_usage,
            analyser_stage_times,
            analyser_errors,
        ) = _run_analysers(ir_doc, config, rulebook, llm_client)
        doc_stage_times.update(analyser_stage_times)

        if parser_findings:
            analyser_findings = parser_findings + analyser_findings

        write_json(file_outdir / "raw_findings.json", analyser_findings)
        logger.debug("Wrote raw_findings.json (%d findings)", len(analyser_findings))

        if llm_client and config.judge:
            judge_batch = rule_engine.prepare_judge_batch(analyser_findings)
            if judge_batch:
                logger.info("Running judge model on %d findings...", len(judge_batch))
                _judge_t0 = time.monotonic()
                judge_response, judge_usage = llm_client.judge_findings(
                    judge_batch,
                    ir_doc,
                    rulebook,
                    model=config.judge_model,
                    temperature=config.judge_temperature,
                )
                doc_stage_times["judge"] = round(time.monotonic() - _judge_t0, 2)
                doc_usage = merge_usage(doc_usage, judge_usage)
                if judge_response:
                    rule_engine.apply_judge_response(judge_batch, judge_response)
                if hasattr(llm_client, "consume_diagnostics"):
                    try:
                        judge_diagnostics = llm_client.consume_diagnostics()
                    except Exception:
                        judge_diagnostics = []
                        logger.debug(
                            "Could not consume judge LLM diagnostics",
                            exc_info=True,
                        )
                    if judge_diagnostics:
                        analyser_errors.setdefault("judge", []).extend(
                            judge_diagnostics
                        )
            judged_approved = sum(
                1 for f in analyser_findings if f.judge_status == "judged_approved"
            )
            judged_adjusted = sum(
                1 for f in analyser_findings if f.judge_status == "judged_adjusted"
            )
            judged_dismissed = sum(
                1 for f in analyser_findings if f.judge_status == "judged_dismissed"
            )
            not_judged = sum(
                1 for f in analyser_findings if f.judge_status == "not_to_be_judged"
            )
            logger.info(
                ("Judge: approved=%d adjusted=%d dismissed=%d not_judged=%d"),
                judged_approved,
                judged_adjusted,
                judged_dismissed,
                not_judged,
            )
            # Note: judged_findings.json contains raw violation-intensity
            # severity values -- calibrated severity only appears in findings.json.
            write_json(file_outdir / "judged_findings.json", analyser_findings)
            logger.debug("Wrote judged_findings.json")

        _rule_engine_t0 = time.monotonic()
        final_findings, re_summary = rule_engine.process(analyser_findings)
        doc_stage_times["rule_engine"] = round(time.monotonic() - _rule_engine_t0, 2)

        _score_t0 = time.monotonic()
        scorer.score(final_findings, rulebook, max_doc_points=config.max_doc_points)
        doc_stage_times["score"] = round(time.monotonic() - _score_t0, 2)
        write_json(file_outdir / "findings.json", final_findings)
        logger.debug("Wrote findings.json (%d final findings)", len(final_findings))

        clean_csv_rows.extend(
            findings_to_csv_rows(
                path,
                final_findings,
                student_id=student_id,
                max_doc_points=config.max_doc_points,
            )
        )
        row = findings_to_grader_row(
            path, final_findings, max_doc_points=config.max_doc_points
        )
        row["id"] = student_id
        grader_rows.append(row)

        info = build_doc_info(
            input_payload=input_payload,
            run_id=run_id,
            config_hash=config_hash,
            course=config.course,
            max_doc_points=config.max_doc_points,
            parse_payload=parse_payload,
            parser_findings_count=len(parser_findings),
            finding_count=len(final_findings),
            usage_by_model=doc_usage,
            stage_times=doc_stage_times,
            elapsed_seconds=time.monotonic() - run_start,
            document_stats={
                "total_words": ir_doc.total_words,
                "total_paragraphs": ir_doc.total_paragraphs,
                "total_pictures": ir_doc.total_pictures,
            },
            analyser_errors=analyser_errors,
            extra_summary=re_summary,
        )
        write_json(file_outdir / "info.json", info)
        run_usage = merge_usage(run_usage, doc_usage)
        run_stage_timings = merge_stage_timings(run_stage_timings, doc_stage_times)

        for finding in final_findings:
            logger.info("\n%s\n", format_finding_short(finding))

        log_json(logger, "LLM token usage", info["usage"])

    if args.clean_csv_out:
        csv_path = Path(args.clean_csv_out)
        # write per-finding clean dataset CSV (preserve canonical column order)
        from .utils import CSV_COLUMNS

        write_csv(csv_path, clean_csv_rows, fieldnames=CSV_COLUMNS)
        logger.info(
            "Clean CSV with %d finding rows written to %s",
            len(clean_csv_rows),
            csv_path,
        )

    if args.csv_out:
        csv_path = Path(args.csv_out)
        grader_fieldnames = ["id", "doc_type", "points", "comment"]
        write_csv(csv_path, grader_rows, fieldnames=grader_fieldnames)
        logger.info("Grader CSV with %d rows written to %s", len(grader_rows), csv_path)

    run_summary = build_run_summary(
        run_id=run_id,
        config_hash=config_hash,
        config_path=Path(args.config),
        output_dir=base_outdir,
        counts={
            "n_documents": docs_discovered,
            "n_processed_documents": docs_processed,
            "n_skipped_documents": docs_skipped,
            "n_parsed_documents": docs_parsed,
            "n_parse_failures": docs_failed_parse,
            "n_grader_rows": len(grader_rows),
            "n_clean_csv_rows": len(clean_csv_rows),
        },
        usage_by_model=run_usage,
        stage_timings=run_stage_timings,
        elapsed_seconds=time.monotonic() - total_run_start,
    )
    write_json(base_outdir / "run_summary.json", run_summary)

    run_usage_summary = run_summary["usage"]
    total_cost = run_usage_summary["total_cost_eur"]
    logger.info(
        (
            "Run LLM cost summary: docs=%d processed=%d skipped=%d parsed=%d "
            "parse_failures=%d "
            "prompt_tokens=%d completion_tokens=%d cached_tokens=%d cost_eur=%s"
        ),
        docs_discovered,
        docs_processed,
        docs_skipped,
        docs_parsed,
        docs_failed_parse,
        run_usage_summary["total_prompt_tokens"],
        run_usage_summary["total_completion_tokens"],
        run_usage_summary["total_cached_tokens"],
        f"{total_cost:.6f}" if total_cost is not None else "n/a",
    )
    log_json(logger, "Run LLM usage", run_usage_summary)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

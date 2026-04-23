"""doc-grader: Intelligent Tool for Assessment of Student Project Documentations

Author: Matúš Csirik, 2026

Licensed under the GNU General Public License v3.0 (GPL-3.0).
"""

import argparse
import logging
import os
import sys
import time
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
from .llm_client import LLMClient, merge_usage, summarise_usage
from .rule_engine import RuleEngine
from .schemas.config import AppConfig, load_app_config, load_rulebook
from .scorer import Scorer
from .utils import (
    compute_config_hash,
    configure_logging,
    findings_to_csv_rows,
    findings_to_grader_row,
    format_finding_short,
    log_json,
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


def _load_app_config(config_path: str | None) -> AppConfig:
    """Load application config from JSON file, falling back to config/default.json."""
    return load_app_config(Path(config_path) if config_path else _DEFAULT_CONFIG)


def _run_analysers(
    ir: Document, config: AppConfig, rulebook: Rulebook, llm_client: Any | None = None
) -> tuple[list[Finding], dict, dict[str, float]]:
    findings: list[Finding] = []
    accumulated_usage: dict = {}
    stage_times: dict[str, float] = {}

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
        except Exception:
            logger.exception("Error running analyser %s", analyser_cfg.analyser_id)

    return findings, accumulated_usage, stage_times


def _run_id_from_config(config: AppConfig) -> str:
    if config.run_id:
        return config.run_id
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _config_for_hash(config: AppConfig) -> dict[str, Any]:
    payload = config.model_dump(mode="json", exclude_none=True)
    payload.pop("run_id", None)
    return payload


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
    exit_code = 0
    clean_csv_rows: list = []  # accumulated per-finding rows for --clean-csv-out
    grader_rows: list = []  # one row per document for --csv-out

    from .document_parser import DocumentParser

    logger.info("Initialising parser...")
    parser = DocumentParser()
    scorer = Scorer()

    def discover_cases(inputs: list[str]) -> Iterator[tuple[Path, str]]:
        """Yields (doc_path, student_id) per target."""

        def get_primary_doc(directory: Path) -> Path | None:
            """Grabs the first doc file."""
            for pattern in ("*.pdf", "*.md"):
                if match := next(directory.glob(pattern), None):
                    return match
            return None

        for raw_input in inputs:
            path = Path(raw_input)

            # Single doc file
            if path.is_file() and path.suffix.lower() in {".pdf", ".md"}:
                yield path, path.stem
                continue

            if not path.is_dir():
                logger.warning("Input not found or invalid: %s", path)
                continue

            # If the directory itself contains a primary document, prefer it
            if doc := get_primary_doc(path):
                yield doc, path.name
                continue

            # Otherwise check for subdirectories containing documents
            subdirs = [p for p in path.iterdir() if p.is_dir()]
            if subdirs:
                for sd in sorted(subdirs, key=lambda p: p.name):
                    if doc := get_primary_doc(sd):
                        yield doc, sd.name
                    else:
                        logger.warning("No document found in: %s", sd)
            else:
                logger.warning("No document found in: %s", path)

    for doc_path, student_id in discover_cases(args.inputs):
        reset_id_counters()
        if llm_client:
            pass
        run_start = time.monotonic()
        path = doc_path
        file_outdir = base_outdir / student_id
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

        logger.debug("Parsing done")

        doc_ref = parse_output.doc_ref

        info = {
            "input": doc_ref.model_dump(mode="json", by_alias=True, exclude_none=True),
            "run": {"run_id": run_id, "config_hash": config_hash},
            "config": {
                "course": config.course,
                "max_doc_points": config.max_doc_points,
            },
            "parse": parse_output.parse_meta.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            "counts": {"n_parser_findings": len(parser_findings), "n_findings": 0},
        }

        write_json(file_outdir / "parser_findings.json", parser_findings)

        if ir_doc is None:
            write_json(file_outdir / "raw_findings.json", parser_findings)
            write_json(file_outdir / "findings.json", parser_findings)
            logger.debug(
                "Wrote raw_findings.json and findings.json (%d findings)",
                len(parser_findings),
            )
            info["counts"]["n_findings"] = len(parser_findings)
            info["usage"] = summarise_usage({})
            info["elapsed_seconds"] = round(time.monotonic() - run_start, 2)
            write_json(file_outdir / "info.json", info)
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

        write_json(file_outdir / "docling.json", ir_doc.docling_doc)
        write_json(file_outdir / "ir.json", ir_doc)

        analyser_findings, doc_usage, analyser_stage_times = _run_analysers(
            ir_doc, config, rulebook, llm_client
        )

        if parser_findings:
            analyser_findings = parser_findings + analyser_findings

        write_json(file_outdir / "raw_findings.json", analyser_findings)
        logger.debug("Wrote raw_findings.json (%d findings)", len(analyser_findings))

        if llm_client:
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
                analyser_stage_times["judge"] = round(time.monotonic() - _judge_t0, 2)
                doc_usage = merge_usage(doc_usage, judge_usage)
                if judge_response:
                    rule_engine.apply_judge_response(judge_batch, judge_response)
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

        final_findings, re_summary = rule_engine.process(analyser_findings)
        scorer.score(final_findings, rulebook, max_doc_points=config.max_doc_points)
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

        info["counts"]["n_findings"] = len(final_findings)
        info.update(re_summary)
        info["document"] = {
            "total_words": ir_doc.total_words,
            "total_paragraphs": ir_doc.total_paragraphs,
            "total_pictures": ir_doc.total_pictures,
        }
        info["stage_times"] = {"parse": _parse_elapsed, **analyser_stage_times}
        info["usage"] = summarise_usage(doc_usage)
        info["elapsed_seconds"] = round(time.monotonic() - run_start, 2)
        write_json(file_outdir / "info.json", info)

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
        grader_fieldnames = [
            "points",
            "comment",
            "bonus_points",
            "points_mentioned_in_comment",
            "id",
            "doc_type",
        ]
        write_csv(csv_path, grader_rows, fieldnames=grader_fieldnames)
        logger.info("Grader CSV with %d rows written to %s", len(grader_rows), csv_path)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

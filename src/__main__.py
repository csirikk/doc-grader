"""CLI entry point."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

# Analysers
from .analysers.content_analyser import ContentAnalyser
from .analysers.design_analyser import DesignAnalyser
from .analysers.structure_analyser import StructureAnalyser
from .analysers.style_analyser import StyleAnalyser
from .analysers.text_analyser import TextAnalyser
from .llm_client import LLMClient
from .schemas.config import AppConfig, load_config, load_rulebook
from .utils import (
    compute_config_hash,
    configure_logging,
    findings_to_csv_rows,
    format_finding_short,
    log_json,
    reset_id_counters,
    write_csv,
    write_json,
)

if TYPE_CHECKING:
    from schemas.llm import Rulebook

    from .analysers.base_analyser import BaseAnalyser
    from .schemas.finding import Finding
    from .schemas.ir import Document

logger = logging.getLogger(__name__)

ANALYSER_LIST: dict[str, type[BaseAnalyser]] = {
    StructureAnalyser.analyser_id: StructureAnalyser,
    StyleAnalyser.analyser_id: StyleAnalyser,
    TextAnalyser.analyser_id: TextAnalyser,
    ContentAnalyser.analyser_id: ContentAnalyser,
    DesignAnalyser.analyser_id: DesignAnalyser,
}


_DEFAULT_CONFIG = Path(__file__).parent.parent / "config" / "default.json"


def _load_app_config(config_path: str | None) -> AppConfig:
    """Load application config from JSON file, falling back to config/default.json."""
    return load_config(Path(config_path) if config_path else _DEFAULT_CONFIG)


def _run_analysers(
    ir: Document, config: AppConfig, rulebook: Rulebook, llm_client: Any | None = None
) -> list[Finding]:
    from .analysers.base_analyser import BaseLLMAnalyser

    findings: list[Finding] = []

    llm_analysers: dict[str, BaseLLMAnalyser] = {}
    all_llm_rules = []
    llm_params = {}

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
        if "course" not in analyser_params:
            analyser_params["course"] = config.course

        try:
            analyser_instance = analyser_class()

            if isinstance(analyser_instance, BaseLLMAnalyser):
                llm_analysers[analyser_cfg.analyser_id] = analyser_instance
                llm_params[analyser_cfg.analyser_id] = analyser_params
                all_llm_rules.extend(
                    analyser_instance.get_rules(rulebook, params=analyser_params)
                )
            else:
                result = analyser_instance.analyse(ir, params=analyser_params)
                if result:
                    findings.extend(result)
        except Exception:
            logger.exception("Error running analyser %s", analyser_cfg.analyser_id)

    if llm_analysers and llm_client:
        for analyser_id, instance in llm_analysers.items():
            params = llm_params.get(analyser_id)
            rules = instance.get_rules(rulebook, params=params)
            if not rules:
                continue
            try:
                llm_findings = llm_client.analyse_document(ir, rules, rulebook)
                result = instance.process_llm_findings(ir, llm_findings, params)
                if result:
                    findings.extend(result)
            except Exception:
                logger.exception("Error running LLM analysis for %s", analyser_id)

    return findings


def _run_judge(
    findings: list[Finding],
    ir: Document,
    rulebook: Rulebook,
    llm_client: Any,
) -> None:
    """Run the judge model on proposed LLM findings, modifying them in-place."""

    llm_findings = [f for f in findings if f.confidence is not None]

    for f in findings:
        if f.confidence is None:
            f.status = "approved"

    if not llm_findings:
        logger.info("No LLM findings to judge.")
        return

    try:
        llm_client.judge_findings(llm_findings, ir, rulebook)
    except Exception:
        logger.exception("Judge pass failed, LLM findings left as 'proposed'")


def _run_id_from_config(config: AppConfig) -> str:
    if config.run_id:
        return config.run_id
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _config_for_hash(config: AppConfig) -> dict[str, Any]:
    payload = config.model_dump(mode="json", exclude_none=True)
    payload.pop("run_id", None)
    return payload


def main(argv: list[str] | None = None) -> int:
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
        default="config/default.json",
        help="Path to JSON config file for analysers",
    )
    arg_parser.add_argument(
        "--csv-out",
        default=None,
        metavar="PATH",
        help=(
            "If provided, write all findings as a CSV to this path. "
            "Columns match the clean_ipp_data.csv schema from dataset_parser.py, "
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
        rulebook_path = Path("config/rulebook.json")
        if not rulebook_path.exists():
            logger.error("Rulebook file not found at %s", rulebook_path)
            return 2
        rulebook = load_rulebook(rulebook_path)

    except Exception as e:
        logger.error("Failed to load config or rulebook: %s", e)
        return 2

    llm_client = None
    from .analysers.base_analyser import BaseLLMAnalyser

    llm_needed = any(
        a.enabled and issubclass(ANALYSER_LIST[a.analyser_id], BaseLLMAnalyser)
        for a in config.analysers
        if a.analyser_id in ANALYSER_LIST
    )
    if llm_needed:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.error("An LLM Analyser is enabled but OPENAI_API_KEY is not set.")
            return 2
        llm_client = LLMClient()
        logger.info("LLMClient ready")

    run_id = _run_id_from_config(config)
    config_hash = compute_config_hash(_config_for_hash(config))

    base_outdir = Path(args.out)
    exit_code = 0
    csv_rows: list = []  # accumulated across all input documents for --csv-out

    from .parsers.parser import DocumentParser

    logger.info("Initializing parser...")
    parser = DocumentParser()

    for raw_path in args.inputs:
        reset_id_counters()
        path = Path(raw_path)
        file_outdir = base_outdir / path.stem

        parse_output = parser.parse(path, run_id=run_id, config_hash=config_hash)
        parser_findings = parse_output.parser_findings
        ir_doc = parse_output.ir

        log_json(logger, "Parse output", parse_output)

        doc_ref = parse_output.doc_ref

        info = {
            "input": doc_ref.model_dump(mode="json", by_alias=True, exclude_none=True),
            "run": {
                "run_id": run_id,
                "config_hash": config_hash,
            },
            "parse": parse_output.parse_meta.model_dump(
                mode="json", by_alias=True, exclude_none=True
            ),
            "counts": {
                "n_parser_findings": len(parser_findings),
                "n_findings": 0,
            },
        }

        write_json(file_outdir / "parser_findings.json", parser_findings)

        if ir_doc is None:
            write_json(file_outdir / "info.json", info)
            logger.warning("Parsing failed for %s", path)
            exit_code = 1
            continue

        write_json(file_outdir / "docling.json", ir_doc.docling_doc)
        write_json(file_outdir / "ir.json", ir_doc)

        analyser_findings = _run_analysers(ir_doc, config, rulebook, llm_client)

        if llm_client:
            logger.info("Running judge model on %d findings...", len(analyser_findings))
            _run_judge(analyser_findings, ir_doc, rulebook, llm_client)
            approved = sum(1 for f in analyser_findings if f.status == "approved")
            dismissed = sum(1 for f in analyser_findings if f.status == "dismissed")
            logger.info(
                "Judge complete: %d approved, %d dismissed", approved, dismissed
            )

        write_json(file_outdir / "findings.json", analyser_findings)

        csv_rows.extend(findings_to_csv_rows(path, analyser_findings))

        info["counts"]["n_findings"] = len(analyser_findings)
        write_json(file_outdir / "info.json", info)

        log_json(logger, "IR Document", ir_doc)
        for finding in analyser_findings:
            log_json(logger, f"Finding: {finding.title}", finding)
            logger.info("\n%s\n", format_finding_short(finding))

    if args.csv_out:
        csv_path = Path(args.csv_out)
        write_csv(csv_path, csv_rows)
        logger.info("CSV with %d finding rows written to %s", len(csv_rows), csv_path)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

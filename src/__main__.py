"""CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .schemas.config import AppConfig, load_config
from .utils import (
    compute_config_hash,
    configure_logging,
    log_model_json,
    reset_id_counters,
    write_json,
)

if TYPE_CHECKING:
    from .schemas.finding import Finding
    from .schemas.ir import Document

logger = logging.getLogger(__name__)

ANALYSER_LIST: dict[str, Any] = {}


def _load_app_config(config_path: str | None) -> AppConfig:
    if not config_path:
        return AppConfig()
    return load_config(Path(config_path))


def _run_analysers(ir: Document, config: AppConfig) -> list[Finding]:
    findings: list[Finding] = []

    for analyser_cfg in config.analysers:
        if not analyser_cfg.enabled:
            continue

        analyser = ANALYSER_LIST.get(analyser_cfg.analyser_id)
        if analyser is None:
            logger.warning(
                "Analyser '%s' is enabled but not registered",
                analyser_cfg.analyser_id,
            )
            continue

        result = analyser.analyse(ir, analyser_cfg.params)
        if result:
            findings.extend(result)

    return findings


def _run_id_from_config(config: AppConfig) -> str:
    if config.run_id:
        return config.run_id
    return datetime.now(UTC).strftime("run-%Y%m%dT%H%M%SZ")


def _config_for_hash(config: AppConfig) -> dict[str, Any]:
    payload = config.model_dump(mode="json", exclude_none=True)
    payload.pop("run_id", None)
    return payload


def main(argv: list[str] | None = None) -> int:
    arg_parser = argparse.ArgumentParser(prog="project")
    arg_parser.add_argument(
        "inputs", nargs="+", help="One or more input paths (.md, .markdown, .pdf)"
    )
    arg_parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    arg_parser.add_argument(
        "-o", "--out", default="out/default/", help="Output directory for findings"
    )
    arg_parser.add_argument(
        "-c", "--config", help="Path to JSON config file for analysers", default=None
    )
    args = arg_parser.parse_args(argv)

    if args.debug:
        configure_logging(logging.DEBUG)
        logger.debug("Debug logging enabled")
    else:
        configure_logging(logging.INFO)

    try:
        config = _load_app_config(args.config)
    except Exception as e:
        logger.error("Failed to load config: %s", e)
        return 2

    run_id = _run_id_from_config(config)
    config_hash = compute_config_hash(_config_for_hash(config))

    base_outdir = Path(args.out)
    exit_code = 0

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

        log_model_json(logger, "Parse output", parse_output)

        doc_ref = parse_output.document_ref

        info = {
            "input": doc_ref.model_dump(mode="json"),
            "run": {
                "run_id": run_id,
                "config_hash": config_hash,
            },
            "parse": parse_output.parse_meta.model_dump(mode="json"),
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

        analyser_findings = _run_analysers(ir_doc, config)
        write_json(file_outdir / "findings.json", analyser_findings)

        info["counts"]["n_findings"] = len(analyser_findings)
        write_json(file_outdir / "info.json", info)

        log_model_json(logger, "IR Document", ir_doc)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

"""CLI entry point."""

import argparse
from pathlib import Path
import json
from typing import List, Optional

from .parsers import parse
from .detectors.caption_analyzer import CaptionAnalyzer
from .detectors.typography_analyzer import TypographyAnalyzer
from .detectors.length_analyzer import LengthAnalyzer
from .detectors.document_info_extractor import DocumentInfoExtractor
from .detectors.metadata_extractor import MetadataExtractor
from .detectors.structure_analyzer import StructureAnalyzer
from .detectors.section_analyzer import SectionAnalyzer
from .detectors.language_analyzer import LanguageAnalyzer
from .detectors.base_detector import BaseDetector
from .schemas.config import load_config, AppConfig, DetectorConfig
from .schemas.ir import Document
from .util import (
    compute_doc_hash,
    summarize_document,
    format_findings,
    write_findings_json,
)
from .rule_engine import RuleEngine
from .logger import (
    set_debug,
    debug,
    debug_dump_ir_json,
    debug_dump_finding_json,
    dump_config_json,
)


def _run_pipeline(
    doc: Document,
    *,
    file_path: Path,
    outdir: Path,
    detectors: Optional[List[BaseDetector]] = None,
) -> int:
    doc_hash = compute_doc_hash(doc.source_path)
    print("=" * 80)
    print(f"File: {doc.source_path}")
    print(f"Hash: {doc_hash}")
    summary = summarize_document(doc)
    print("IR Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    debug_dump_ir_json(doc)

    detectors = detectors or [LengthAnalyzer()]
    per_detector_findings: List[List] = []
    for det in detectors:
        debug("running detector %s on %s", det.code, doc.source_path)
        findings = det.detect(doc, doc_hash)
        for f in findings:
            debug_dump_finding_json(f)
        print()
        print(format_findings(det, findings))
        paths = write_findings_json(det, findings, outdir)
        print(f"\n[{det.code}] Written {len(paths)} finding file(s) to {outdir}/")
        per_detector_findings.append(findings)

    engine = RuleEngine()
    aggregated, agg_summary = engine.process(per_detector_findings)
    print()
    print(format_findings(detector_label="AGG", detector=engine, findings=aggregated))
    if agg_summary:
        print("\n[AGG] Summary:")
        from pprint import pprint as _pprint

        _pprint(agg_summary)
    all_findings = len(aggregated)

    print("=" * 80)
    print(f"Done.\nTotal findings: {all_findings}")
    debug("finished processing %s with %d findings", doc.source_path, all_findings)
    return all_findings


def parse_input_to_document(path: Path) -> Optional[Document]:
    if not path.exists():
        print(f"Missing file: {path}")
        return None
    try:
        return parse(path)
    except Exception as e:
        print(f"Error parsing {path}: {e}")
        debug("Exception while parsing %s: %s", path, e)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="project")
    parser.add_argument(
        "inputs", nargs="+", help="One or more input paths (.md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--out", default="out/findings/", help="Output directory for findings"
    )
    parser.add_argument(
        "-c", "--config", help="Path to JSON config file for detectors", default=None
    )
    args = parser.parse_args(argv)

    base_outdir = Path(args.out)
    if args.debug:
        set_debug(True)
        debug("debug logging enabled")
    detectors: List[BaseDetector] = []
    if args.config:
        config_path = Path(args.config)
        if not config_path.exists():
            raise SystemExit(f"Config file not found: {config_path}")
        app_config: AppConfig = load_config(config_path)
        run_id = app_config.run_id
        global_course = app_config.course
        detector_list = {
            "LENGTH": LengthAnalyzer,
            "DOCINFO": DocumentInfoExtractor,
            "METADATA": MetadataExtractor,
            "STRUCT": StructureAnalyzer,
            "SECTION": SectionAnalyzer,
            "TYPO": TypographyAnalyzer,
            "CAPTION": CaptionAnalyzer,
            "LANG": LanguageAnalyzer,
        }

        for detector_cfg in app_config.detectors:
            dump_config_json(detector_cfg)
            if not detector_cfg.enabled:
                continue

            detector_class = detector_list.get(detector_cfg.code.upper())
            if not detector_class:
                print(f"[warn] Unknown detector code in config: {detector_cfg.code}")
                continue
            params = detector_cfg.params.copy()

            # Set course if applicable
            if global_course:
                if detector_cfg.code.upper() == "METADATA":
                    params["expected_course"] = global_course
                elif detector_cfg.code.upper() == "SECTION":
                    params["course"] = global_course

            detectors.append(detector_class(run_id=run_id, params=params))
    else:
        detectors.append(DocumentInfoExtractor())
        detectors.append(MetadataExtractor())
        detectors.append(StructureAnalyzer())
        detectors.append(SectionAnalyzer())
        detectors.append(LengthAnalyzer())
        detectors.append(TypographyAnalyzer())
        detectors.append(LanguageAnalyzer())
        detectors.append(CaptionAnalyzer())

    # Run pre-parsing detectors on all files first
    pre_parse_findings: List[List] = []
    for raw in args.inputs:
        path = Path(raw)
        if not path.exists():
            print(f"File not found: {path}")
            continue

        # Per-file output directory = base_outdir / <filename stem>
        file_outdir = base_outdir / path.stem

        # Run detectors that work before parsing
        for det in detectors:
            if det.runs_before_parsing:
                debug("running pre-parse detector %s on %s", det.code, path)
                findings = det.detect_file(path)
                for f in findings:
                    debug_dump_finding_json(f)
                print()
                print(format_findings(det, findings))
                paths = write_findings_json(det, findings, file_outdir)
                print(
                    f"\n[{det.code}] Written {len(paths)} finding file(s) to {file_outdir}/"
                )
                pre_parse_findings.append(findings)

    # Parse and run regular detectors
    for raw in args.inputs:
        path = Path(raw)
        doc = parse_input_to_document(path)
        if doc is None:
            print(f"Skipping unsupported file type: {path}")
            continue
        file_outdir = base_outdir / path.stem
        _run_pipeline(doc, file_path=path, outdir=file_outdir, detectors=detectors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

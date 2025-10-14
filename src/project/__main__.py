"""CLI entry point."""

import argparse
from pathlib import Path
import json
from typing import List, Optional

from .parsers import parse
from .detectors.length_detector import LengthDetector
from .detectors.base_detector import BaseDetector
from .schemas.config import load_config, AppConfig, DetectorConfig
from .schemas.ir import Document
from .util import compute_doc_hash, summarize_document, format_findings, write_findings_json
from .rule_engine import RuleEngine
from .logger import set_debug, debug, debug_dump_ir_json, debug_dump_finding_json, dump_config_json


def _run_pipeline(doc: Document, *, outdir: Path, detectors: Optional[List[BaseDetector]] = None) -> int:
    doc_hash = compute_doc_hash(doc.source_path)
    print("=" * 80)
    print(f"File: {doc.source_path}")
    print(f"Hash: {doc_hash}")
    summary = summarize_document(doc)
    print("IR Summary:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    debug_dump_ir_json(doc)

    detectors = detectors or [LengthDetector()]
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
        "inputs",
        nargs="+",
        help="One or more input paths (.md, .markdown, .pdf)"
    )
    parser.add_argument(
        "-d", "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--out", default="test/findings_out", help="Output directory for findings"
    )
    parser.add_argument(
        "-c", "--config", help="Path to JSON config file for detectors", default=None
    )
    args = parser.parse_args(argv)

    outdir = Path(args.out)
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
        detector_list = {
            "LENGTH": LengthDetector,
        }
        for detector_cfg in app_config.detectors:
            dump_config_json(detector_cfg)
            if not detector_cfg.enabled:
                continue
            detector_class = detector_list.get(detector_cfg.code.upper())
            if not detector_class:
                print(f"[warn] Unknown detector code in config: {detector_cfg.code}")
                continue
            detectors.append(detector_class(run_id=run_id, params=detector_cfg.params))
    else:
        detectors.append(LengthDetector())
    for raw in args.inputs:
        path = Path(raw)
        doc = parse_input_to_document(path)
        if doc is None:
            print(f"Skipping unsupported file type: {path}")
            continue
        _run_pipeline(doc, outdir=outdir, detectors=detectors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

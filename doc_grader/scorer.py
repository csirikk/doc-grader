"""Calibrated severity scoring for doc-grader findings.

impact = -(per_code_weight * severity * max_doc_points)

- ``per_code_weight`` is the absolute median normalised impact observed for that
  code in the historical IPP assessment dataset
- ``max_doc_points`` is the maximum documentation score for this run

"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas.finding import Finding

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
_DEFAULT_WEIGHTS_PATH = _CONFIG_DIR / "severity_weights.json"


class Scorer:
    """Post-processes final findings to compute calibrated impact scores."""

    def __init__(self, weights_path: Path = _DEFAULT_WEIGHTS_PATH) -> None:
        self._weights: dict[str, float] = {}
        if not weights_path.exists():
            logger.warning(
                "Severity weights file not found at %s. Impact will not be set.",
                weights_path,
            )
            return
        try:
            with weights_path.open(encoding="ascii") as fh:
                raw: dict = json.load(fh)
            self._weights = {str(k): float(v) for k, v in raw.items()}
            logger.info(
                "Scorer loaded %d severity weights from %s",
                len(self._weights),
                weights_path,
            )
        except Exception:
            logger.exception(
                "Failed to load severity weights from %s. Scorer will be a no-op.",
                weights_path,
            )

    def score(self, findings: list[Finding], max_doc_points: int | None = None) -> None:
        """Compute impact for each finding in-place."""
        if not self._weights:
            return

        for finding in findings:
            weight = self._weights.get(finding.ac_code)

            if weight is None:
                logger.warning(
                    "No weight for %s (%s), impact left as None.",
                    finding.finding_id,
                    finding.ac_code,
                )
                continue

            if weight == 0.0:
                finding.impact = 0.0
                logger.debug(
                    "Zero weight for %s (%s), impact=0.0.",
                    finding.finding_id,
                    finding.ac_code,
                )
                continue

            severity = finding.severity if finding.severity is not None else 1.0
            normalised = weight * severity

            if max_doc_points is not None:
                finding.impact = round(-normalised * max_doc_points, 4)
            else:
                finding.impact = round(-normalised, 6)

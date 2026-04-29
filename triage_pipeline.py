"""
triage_pipeline.py — Senior Training OS · Triage Pipeline
==========================================================
Batch ingestion pipeline for Legacy shadow JSONL files.

Classification rules:
  accepted  — passes Layer A validation AND is_noise=False
  review    — passes Layer A but has missing Layer B fields OR is_noise=True
  rejected  — fails Layer A validation (malformed JSON, missing required fields)

Noise tolerance: a file with up to 30% review events completes without exception.

Requirements: 10.1–10.8
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from shadow_schema import Shadow_Schema_Validator
from triage_models import IngestionReport, RejectedEvent, ReviewEvent

logger = logging.getLogger(__name__)

# Maximum fraction of review events before raising an exception
_MAX_REVIEW_FRACTION = 0.30
# Log progress every N events
_LOG_INTERVAL = 10


class Triage_Pipeline:
    """
    Batch ingestion pipeline that classifies shadow events and produces
    IngestionReport records.

    Usage::

        pipeline = Triage_Pipeline()
        report   = pipeline.ingest_shadow_file("shadow_exports/capture.jsonl")
        reports  = pipeline.ingest_shadow_directory("shadow_exports/")
    """

    def __init__(self) -> None:
        self._validator = Shadow_Schema_Validator()

    # ──────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────

    def ingest_shadow_file(self, path: str) -> IngestionReport:
        """
        Read a shadow JSONL file, classify each event, and return a report.

        Args:
            path: Path to the shadow JSONL file.

        Returns:
            IngestionReport with counts and per-event details.

        Raises:
            FileNotFoundError: If the file does not exist.
            RuntimeError: If the review fraction exceeds 30%.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Shadow JSONL file not found: {path}")

        report = IngestionReport(
            source_file=str(path),
            ingested_at=datetime.now(timezone.utc).isoformat(),
        )

        with file_path.open(encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                report.total_events += 1
                classification, identifier, reason_or_issues = self._classify_line(
                    raw_line, line_no
                )

                if classification == "accepted":
                    report.accepted_count += 1
                elif classification == "review":
                    report.review_count += 1
                    report.review_events.append(
                        ReviewEvent(identifier=identifier, issues=reason_or_issues)
                    )
                else:  # rejected
                    report.rejected_count += 1
                    report.rejected_events.append(
                        RejectedEvent(
                            identifier=identifier,
                            failure_reason=reason_or_issues[0] if reason_or_issues else "unknown",
                        )
                    )

                # Progress logging every _LOG_INTERVAL events
                if report.total_events % _LOG_INTERVAL == 0:
                    logger.info(
                        "Triage progress",
                        extra={
                            "source_file": path,
                            "processed": report.total_events,
                            "accepted": report.accepted_count,
                            "review": report.review_count,
                            "rejected": report.rejected_count,
                        },
                    )

        # Noise tolerance check
        if report.total_events > 0:
            review_fraction = report.review_count / report.total_events
            if review_fraction > _MAX_REVIEW_FRACTION:
                raise RuntimeError(
                    f"Triage aborted: review fraction {review_fraction:.1%} exceeds "
                    f"tolerance of {_MAX_REVIEW_FRACTION:.0%} for file '{path}'"
                )

        logger.info(
            "Triage complete",
            extra={
                "source_file": path,
                "total": report.total_events,
                "accepted": report.accepted_count,
                "review": report.review_count,
                "rejected": report.rejected_count,
            },
        )
        return report

    def ingest_shadow_directory(self, directory: str) -> list[IngestionReport]:
        """
        Process all *.jsonl files in a directory and return one report per file.

        Args:
            directory: Path to the directory containing shadow JSONL files.

        Returns:
            List of IngestionReport, one per file processed.
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise FileNotFoundError(f"Directory not found: {directory}")

        reports: list[IngestionReport] = []
        jsonl_files = sorted(dir_path.glob("*.jsonl"))

        logger.info(
            "Starting directory ingestion",
            extra={"directory": directory, "file_count": len(jsonl_files)},
        )

        for jsonl_file in jsonl_files:
            try:
                report = self.ingest_shadow_file(str(jsonl_file))
                reports.append(report)
            except RuntimeError as exc:
                logger.error(
                    "File ingestion failed — skipping",
                    extra={"file": str(jsonl_file), "error": str(exc)},
                )

        return reports

    # ──────────────────────────────────────────────────────────
    # Classification logic
    # ──────────────────────────────────────────────────────────

    def _classify_line(
        self,
        raw_line: str,
        line_no: int,
    ) -> tuple[str, str, list[str]]:
        """
        Classify a single raw JSONL line.

        Returns:
            (classification, identifier, reasons)
            - classification: 'accepted' | 'review' | 'rejected'
            - identifier:     id_acao string or line number string
            - reasons:        list of issue strings (empty for accepted)
        """
        # Parse JSON
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            return "rejected", f"line:{line_no}", [f"JSON parse error: {exc}"]

        identifier = str(event.get("id_acao", f"line:{line_no}"))

        # Layer A validation
        if not self._validator.validate_layer_a(event):
            errors = self._validator.get_validation_errors()
            logger.warning(
                "Event rejected: Layer A validation failed",
                extra={"id_acao": identifier, "errors": errors},
            )
            return "rejected", identifier, errors

        # Noise check
        if event.get("is_noise", False):
            return "review", identifier, ["is_noise=True"]

        # Layer B completeness check
        missing_b = self._validator.compute_missing_signals(event)
        if missing_b:
            return "review", identifier, [f"missing Layer B: {', '.join(missing_b)}"]

        return "accepted", identifier, []

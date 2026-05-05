"""
triage_models.py — Senior Training OS · Triage Pipeline Data Models
====================================================================
Defines IngestionReport — the structured result of a batch shadow JSONL
ingestion run.

Requirements: 10.5
"""

from dataclasses import dataclass, field


@dataclass
class RejectedEvent:
    """A shadow event that failed Layer A validation."""
    identifier: str          # id_acao or line number if id_acao missing
    failure_reason: str      # human-readable description of the failure


@dataclass
class ReviewEvent:
    """A shadow event that passed Layer A but has quality issues."""
    identifier: str          # id_acao
    issues: list[str] = field(default_factory=list)  # missing/problematic fields


@dataclass
class IngestionReport:
    """
    Structured result of a single shadow JSONL file ingestion run.

    Attributes:
        source_file:     Path to the ingested file.
        ingested_at:     ISO 8601 timestamp of when ingestion ran.
        total_events:    Total number of lines processed.
        accepted_count:  Events that passed all validations.
        review_count:    Events that need human review.
        rejected_count:  Events that failed Layer A validation.
        rejected_events: List of RejectedEvent records.
        review_events:   List of ReviewEvent records.
    """
    source_file: str
    ingested_at: str
    total_events: int = 0
    accepted_count: int = 0
    review_count: int = 0
    rejected_count: int = 0
    rejected_events: list[RejectedEvent] = field(default_factory=list)
    review_events: list[ReviewEvent] = field(default_factory=list)

    def summary(self) -> str:
        """Return a one-line human-readable summary."""
        return (
            f"{self.source_file} | total={self.total_events} "
            f"accepted={self.accepted_count} "
            f"review={self.review_count} "
            f"rejected={self.rejected_count}"
        )

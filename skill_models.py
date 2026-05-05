"""
skill_models.py — Senior Training OS · Evolved KnownSkill Data Model
=====================================================================
Defines the evolved KnownSkill contract with full provenance and governance metadata.

This module provides:
  - KnownSkill dataclass with all required fields for the Next-Legacy Diamond Integration
  - Full provenance tracking (origin, source_stage)
  - Success/failure tracking
  - Promotion state management
  - Review flags
  - Temporal tracking (created_at, last_seen, last_validated_at)

Requirements: 4.1
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KnownSkill:
    """
    Evolved contract representing a reusable, promoted skill.
    
    This dataclass carries full provenance and governance metadata to support:
    - Provenance tracking (origin, source_stage)
    - Success/failure tracking
    - Promotion state management
    - Review flags
    - Temporal tracking (created_at, last_seen, last_validated_at)
    
    The KnownSkill contract is the central data model for skills that have been
    promoted through the promotion gate system and are ready for reuse by the
    Next system's planner and execution engine.
    
    Attributes:
        skill_id: Unique identifier for this skill
        skill_name: Human-readable name for this skill
        semantic_action: Semantic action from controlled vocabulary (fill, search, confirm, etc.)
        business_entity: Business domain entity (pasta, documento, campo, menu, etc.)
        screen_family: Screen classification (ged_list, ged_form, sign_inbox, etc.)
        component_family: Component classification (toolbar_button, context_menu_item, etc.)
        pattern: UI interaction pattern (menu_navigation, form_fill, button_click, etc.)
        expected_effect: Most common expected_effect from contributing events
        selector: Primary CSS selector for execution
        fallback_selectors: Alternative selectors for resilience
        success_count: Number of successful executions
        failure_count: Number of failed executions
        average_confidence: Average confidence across contributing events (0.0 to 1.0)
        promotion_state: Current maturity level (raw_shadow, reviewed_shadow, skill_candidate, promoted_skill)
        source_stage: Origin of this skill (legacy_import, dual_shadow, runtime_learning, hitl_promoted)
        review_required: True if needs human review
        provenance: Original event ID, source file, and contributing events
        created_at: ISO 8601 timestamp of skill creation
        last_seen: ISO 8601 timestamp of last execution or observation
        last_validated_at: ISO 8601 timestamp of last validation, or None if never validated
    
    Example:
        >>> skill = KnownSkill(
        ...     skill_id="skill_001",
        ...     skill_name="Open GED Document",
        ...     semantic_action="open",
        ...     business_entity="documento",
        ...     screen_family="ged_list",
        ...     component_family="table_row",
        ...     pattern="table_selection",
        ...     expected_effect="document opens in viewer",
        ...     selector="tr.documento-row",
        ...     fallback_selectors=["tr[data-tipo='documento']", "tr.row-documento"],
        ...     success_count=15,
        ...     failure_count=2,
        ...     average_confidence=0.85,
        ...     promotion_state="promoted_skill",
        ...     source_stage="dual_shadow",
        ...     review_required=False,
        ...     provenance={
        ...         "original_event_id": 42,
        ...         "source_file": "shadow_exports/capture_2024_01_15.jsonl",
        ...         "contributing_events": [...]
        ...     },
        ...     created_at="2024-01-15T10:30:00Z",
        ...     last_seen="2024-01-20T14:22:00Z",
        ...     last_validated_at="2024-01-18T09:00:00Z"
        ... )
    """

    # Core identification
    skill_id: str
    skill_name: str

    # Semantic classification
    semantic_action: str
    business_entity: str
    screen_family: str
    component_family: str
    pattern: str

    # Effect specification
    expected_effect: str

    # Execution data
    selector: str
    fallback_selectors: list[str] = field(default_factory=list)

    # Quality metrics
    success_count: int = 0
    failure_count: int = 0
    average_confidence: float = 0.0

    # Governance
    promotion_state: str = "raw_shadow"  # raw_shadow, reviewed_shadow, skill_candidate, promoted_skill
    source_stage: str = "dual_shadow"    # legacy_import, dual_shadow, runtime_learning, hitl_promoted
    review_required: bool = False

    # Provenance
    provenance: dict = field(default_factory=dict)

    # Timestamps
    created_at: str = ""
    last_seen: str = ""
    last_validated_at: Optional[str] = None

    def __post_init__(self):
        """
        Validates field values after initialization.
        
        Raises:
            ValueError: If any required field is empty or invalid
        """
        # Validate required string fields are non-empty
        required_fields = [
            "skill_id", "skill_name", "semantic_action", "business_entity",
            "screen_family", "component_family", "pattern", "expected_effect",
            "selector", "created_at", "last_seen"
        ]

        for field_name in required_fields:
            value = getattr(self, field_name)
            if not value:
                raise ValueError(f"KnownSkill.{field_name} cannot be empty")

        # Validate promotion_state is from allowed values
        allowed_promotion_states = {
            "raw_shadow",
            "reviewed_shadow",
            "skill_candidate",
            "promoted_skill"
        }
        if self.promotion_state not in allowed_promotion_states:
            raise ValueError(
                f"KnownSkill.promotion_state must be one of {allowed_promotion_states}, "
                f"got '{self.promotion_state}'"
            )

        # Validate source_stage is from allowed values
        allowed_source_stages = {
            "legacy_import",
            "dual_shadow",
            "runtime_learning",
            "hitl_promoted"
        }
        if self.source_stage not in allowed_source_stages:
            raise ValueError(
                f"KnownSkill.source_stage must be one of {allowed_source_stages}, "
                f"got '{self.source_stage}'"
            )

        # Validate average_confidence is in valid range
        if not (0.0 <= self.average_confidence <= 1.0):
            raise ValueError(
                f"KnownSkill.average_confidence must be between 0.0 and 1.0, "
                f"got {self.average_confidence}"
            )

        # Validate counts are non-negative
        if self.success_count < 0:
            raise ValueError(
                f"KnownSkill.success_count must be non-negative, got {self.success_count}"
            )
        if self.failure_count < 0:
            raise ValueError(
                f"KnownSkill.failure_count must be non-negative, got {self.failure_count}"
            )

    def get_success_rate(self) -> float:
        """
        Calculates the success rate of this skill.
        
        Returns:
            float: Success rate as a value between 0.0 and 1.0.
                   Returns 0.0 if there are no executions.
        
        Example:
            >>> skill = KnownSkill(..., success_count=7, failure_count=3)
            >>> skill.get_success_rate()
            0.7
        """
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.0
        return self.success_count / total

    def is_promoted(self) -> bool:
        """
        Checks if this skill has been promoted to Level 3 (promoted_skill).
        
        Returns:
            bool: True if promotion_state is 'promoted_skill', False otherwise
        
        Example:
            >>> skill = KnownSkill(..., promotion_state="promoted_skill")
            >>> skill.is_promoted()
            True
        """
        return self.promotion_state == "promoted_skill"

    def is_skill_candidate(self) -> bool:
        """
        Checks if this skill is at Level 2 (skill_candidate).
        
        Returns:
            bool: True if promotion_state is 'skill_candidate', False otherwise
        
        Example:
            >>> skill = KnownSkill(..., promotion_state="skill_candidate")
            >>> skill.is_skill_candidate()
            True
        """
        return self.promotion_state == "skill_candidate"

    def needs_review(self) -> bool:
        """
        Checks if this skill requires human review.
        
        A skill needs review if:
        - review_required flag is True, OR
        - failure_count exceeds success_count
        
        Returns:
            bool: True if review is needed, False otherwise
        
        Example:
            >>> skill = KnownSkill(..., success_count=2, failure_count=5, review_required=False)
            >>> skill.needs_review()
            True
        """
        return self.review_required or (self.failure_count > self.success_count)

    def get_provenance_summary(self) -> str:
        """
        Returns a human-readable summary of this skill's provenance.
        
        Returns:
            str: Provenance summary including source_stage, original event, and source file
        
        Example:
            >>> skill = KnownSkill(
            ...     source_stage="dual_shadow",
            ...     provenance={
            ...         "original_event_id": 42,
            ...         "source_file": "shadow_exports/capture_2024_01_15.jsonl"
            ...     }
            ... )
            >>> skill.get_provenance_summary()
            'dual_shadow | event_id: 42 | source: shadow_exports/capture_2024_01_15.jsonl'
        """
        event_id = self.provenance.get("original_event_id", "unknown")
        source_file = self.provenance.get("source_file", "unknown")
        return f"{self.source_stage} | event_id: {event_id} | source: {source_file}"

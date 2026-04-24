"""
observed_action_models.py — Senior Training OS · ObservedAction Contract
=========================================================================
Defines the ObservedAction dataclass — the canonical contract representing
a single observed user interaction enriched with semantic, contextual, and
quality signals.

This is the primary ingestion contract between the Legacy dual-capture output
and the Next system's planner/policy pipeline.

Requirements: 6.1–6.8
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawTarget:
    """
    Raw element identification data captured from the Legacy system.

    Attributes:
        selector:    Primary CSS / aria selector hint.
        iframe_hint: Iframe context, if the element lives inside one.
        html_hint:   Snippet of the element's outer HTML.
        coords:      Relative coordinates dict {x_pct, y_pct, w_pct, h_pct}.
        valor_input: Value typed/selected, if any.
    """
    selector: str = ""
    iframe_hint: Optional[str] = None
    html_hint: str = ""
    coords: dict = field(default_factory=dict)
    valor_input: str = ""


@dataclass
class Provenance:
    """
    Traceability metadata linking an ObservedAction back to its origin.

    Attributes:
        original_event_id: The id_acao from the Legacy shadow event.
        source_file:       Path to the shadow JSONL file.
        captured_at:       ISO 8601 timestamp from the Legacy capture.
    """
    original_event_id: int = 0
    source_file: str = ""
    captured_at: str = ""


@dataclass
class ObservedAction:
    """
    Canonical contract for a single observed user interaction.

    Populated by ObservedAction_Adapter from a Legacy dual-capture shadow event.
    Consumed by IntentInterpreter, Planner, and SkillMemory.

    Attributes:
        action_id:        Unique identifier (mirrors id_acao from Legacy).
        action_type:      Raw action string (e.g. 'clique', 'digitacao').
        raw_target:       Element identification data (RawTarget).
        screen_before:    Base64 screenshot reference before the action.
        state_change:     Inferred description of what changed after the action.
        artifacts:        Additional context dict (html_hint, coords, etc.).
        confidence:       Normalised confidence score 0.0–1.0.
        is_noise:         True if the event was flagged as noise.
        review_required:  True if human review is needed.
        screen_family:    Screen classification (ged_list, ged_form, …).
        component_family: Component classification (toolbar_button, …).
        pattern:          UI interaction pattern (menu_navigation, …).
        business_entity:  Business domain entity (pasta, documento, …).
        business_target:  Label / description of the target element.
        semantic_action:  Semantic intent from controlled vocabulary.
        intencao_semantica: Human-readable intent string.
        expected_effect:  What was expected to change after the action.
        observed_effect:  What actually changed (inferred from screenshot delta).
        provenance:       Traceability back to the Legacy shadow event.
    """

    # Core identification
    action_id: int = 0
    action_type: str = ""

    # Element data
    raw_target: RawTarget = field(default_factory=RawTarget)

    # Screen evidence
    screen_before: Optional[str] = None   # base64 screenshot reference
    state_change: Optional[str] = None    # inferred state delta

    # Additional context
    artifacts: dict = field(default_factory=dict)

    # Quality signals
    confidence: float = 0.0
    is_noise: bool = False
    review_required: bool = False

    # Semantic classification (Layer B)
    screen_family: str = "unknown"
    component_family: str = "unknown"
    pattern: str = "unknown"
    business_entity: str = ""
    business_target: str = ""
    semantic_action: str = ""
    intencao_semantica: str = ""

    # Effect axis
    expected_effect: str = ""
    observed_effect: Optional[str] = None

    # Traceability
    provenance: Provenance = field(default_factory=Provenance)

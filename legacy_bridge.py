"""
legacy_bridge.py — Senior Training OS · LegacyBridge
=====================================================
Formal bridge between the Legacy dual-capture system (poc-robo-ator-senior)
and the Next system (senior-training-os-next CIL module).

Responsibilities:
  - Read and validate shadow JSONL files from shadow_exports/
  - Map validated events to ObservedAction contracts
  - Lookup events by id_acao or skill_candidate_id
  - Deliver rich comparative context to ShadowModeRunner

Requirements: 1.1, 1.4, 5.1–5.6, 8.3
"""

import json
import logging
from pathlib import Path
from typing import Optional

from shadow_schema import Shadow_Schema_Validator
from observed_action_adapter import ObservedAction_Adapter
from observed_action_models import ObservedAction

logger = logging.getLogger(__name__)


class LegacyBridge:
    """
    Official bridge between Legacy shadow JSONL and Next contracts.

    Usage::

        bridge = LegacyBridge()
        events = bridge.read_shadow_file("shadow_exports/capture_2024.jsonl")
        obs    = bridge.map_to_observed_action(events[0], source_file="...")
        ctx    = bridge.deliver_comparative_context(events[0], obs)
    """

    def __init__(self) -> None:
        self._validator = Shadow_Schema_Validator()
        self._adapter   = ObservedAction_Adapter()

    # ──────────────────────────────────────────────────────────
    # 6.1 — Read and validate shadow JSONL
    # ──────────────────────────────────────────────────────────

    def read_shadow_file(self, path: str) -> list[dict]:
        """
        Read a shadow JSONL file, validate each line against the canonical
        schema, and return a list of validated event dicts.

        Lines that fail Layer A validation are logged as warnings and skipped.

        Args:
            path: Path to the shadow JSONL file (relative or absolute).

        Returns:
            List of validated event dicts.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"Shadow JSONL file not found: {path}")

        validated: list[dict] = []
        rejected = 0

        with file_path.open(encoding="utf-8") as fh:
            for line_no, raw_line in enumerate(fh, start=1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Shadow JSONL parse error — line skipped",
                        extra={"path": path, "line_no": line_no, "error": str(exc)},
                    )
                    rejected += 1
                    continue

                if not self._validator.validate_layer_a(event):
                    errors = self._validator.get_validation_errors()
                    logger.warning(
                        "Shadow event failed Layer A validation — skipped",
                        extra={
                            "path": path,
                            "line_no": line_no,
                            "id_acao": event.get("id_acao", "unknown"),
                            "errors": errors,
                        },
                    )
                    rejected += 1
                    continue

                validated.append(event)

        logger.info(
            "Shadow file read complete",
            extra={
                "path": path,
                "accepted": len(validated),
                "rejected": rejected,
            },
        )
        return validated

    # ──────────────────────────────────────────────────────────
    # 6.2 — Mapping and lookup
    # ──────────────────────────────────────────────────────────

    def map_to_observed_action(
        self,
        shadow_event: dict,
        source_file: str = "",
    ) -> ObservedAction:
        """
        Convert a validated shadow event to a fully-populated ObservedAction.

        Delegates to ObservedAction_Adapter for the actual field mapping.

        Args:
            shadow_event: A validated shadow event dict.
            source_file:  Path to the originating JSONL file (for provenance).

        Returns:
            A fully-populated ObservedAction instance.
        """
        return self._adapter.adapt(shadow_event, source_file=source_file)

    def lookup_by_event_id(
        self,
        event_id: int,
        source_file: str,
    ) -> Optional[dict]:
        """
        Retrieve a specific shadow event by its id_acao from a given file.

        Args:
            event_id:    The id_acao to look up.
            source_file: Path to the shadow JSONL file.

        Returns:
            The matching event dict, or None if not found.
        """
        try:
            events = self.read_shadow_file(source_file)
        except FileNotFoundError:
            logger.warning(
                "lookup_by_event_id: file not found",
                extra={"event_id": event_id, "source_file": source_file},
            )
            return None

        for event in events:
            if event.get("id_acao") == event_id:
                return event

        logger.debug(
            "lookup_by_event_id: event not found",
            extra={"event_id": event_id, "source_file": source_file},
        )
        return None

    def lookup_by_skill_candidate_id(
        self,
        skill_id: str,
        skill_memory=None,
    ) -> Optional[dict]:
        """
        Retrieve the originating shadow event for a given skill candidate.

        Uses the skill's provenance metadata (original_event_id + source_file)
        to locate the event in the shadow JSONL file.

        Args:
            skill_id:     The KnownSkill.skill_id to look up.
            skill_memory: A SkillMemory instance to resolve the skill.

        Returns:
            The originating shadow event dict, or None if not found.
        """
        if skill_memory is None:
            logger.warning(
                "lookup_by_skill_candidate_id: no skill_memory provided",
                extra={"skill_id": skill_id},
            )
            return None

        skill = skill_memory.get(skill_id)
        if skill is None:
            logger.warning(
                "lookup_by_skill_candidate_id: skill not found in memory",
                extra={"skill_id": skill_id},
            )
            return None

        original_event_id = skill.provenance.get("original_event_id")
        source_file = skill.provenance.get("source_file", "")

        if not original_event_id or not source_file:
            logger.warning(
                "lookup_by_skill_candidate_id: incomplete provenance",
                extra={"skill_id": skill_id, "provenance": skill.provenance},
            )
            return None

        return self.lookup_by_event_id(original_event_id, source_file)

    # ──────────────────────────────────────────────────────────
    # 6.3 — Comparative context delivery
    # ──────────────────────────────────────────────────────────

    def deliver_comparative_context(
        self,
        shadow_event: dict,
        mapped_action: Optional[ObservedAction] = None,
        source_file: str = "",
    ) -> dict:
        """
        Build a rich comparative context dict for ShadowModeRunner.

        The context includes the original shadow event, the mapped ObservedAction,
        inferred screen/component families, and the effect axis.

        Args:
            shadow_event:  The original shadow event dict.
            mapped_action: Pre-computed ObservedAction (computed if None).
            source_file:   Path to the originating JSONL file.

        Returns:
            A dict with keys:
              - original_shadow
              - mapped_action
              - screen_family
              - component_family
              - expected_effect
              - observed_effect
        """
        if mapped_action is None:
            mapped_action = self.map_to_observed_action(shadow_event, source_file)

        context = {
            "original_shadow": shadow_event,
            "mapped_action": mapped_action,
            "screen_family": mapped_action.screen_family,
            "component_family": mapped_action.component_family,
            "expected_effect": mapped_action.expected_effect,
            "observed_effect": mapped_action.observed_effect,
        }

        logger.debug(
            "Comparative context delivered",
            extra={
                "action_id": mapped_action.action_id,
                "screen_family": context["screen_family"],
                "expected_effect": context["expected_effect"],
                "observed_effect": context["observed_effect"],
            },
        )
        return context

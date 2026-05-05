"""
skill_memory.py — Senior Training OS · SkillMemory Storage and Retrieval
=========================================================================
Implements the storage and retrieval layer for KnownSkill records.

Retrieval modes:
  - 'exact'   : strict fingerprint match (screen_family + component_family + semantic_action + pattern)
  - 'family'  : match by screen_family + component_family
  - 'pattern' : match by pattern_detectado (pattern) + semantic_action

Only skills with promotion_state in ['skill_candidate', 'promoted_skill'] are
returned by retrieve() in 'family' and 'pattern' modes.

Requirements: 4.2, 4.3, 4.4, 4.5, 4.6
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from skill_models import KnownSkill

logger = logging.getLogger(__name__)

# Promotion states eligible for retrieval in family/pattern modes
_RETRIEVABLE_STATES = {"skill_candidate", "promoted_skill"}


class SkillMemory:
    """
    In-memory storage and retrieval layer for KnownSkill records.

    Skills are stored in a dict keyed by skill_id.  Retrieval supports three
    modes so the planner can find the best match for a given context.
    """

    def __init__(self) -> None:
        self._store: dict[str, KnownSkill] = {}

    # ──────────────────────────────────────────────────────────
    # Storage
    # ──────────────────────────────────────────────────────────

    def store(self, skill: KnownSkill) -> None:
        """
        Persist a KnownSkill.  Overwrites any existing record with the same
        skill_id.

        When source_stage is 'legacy_import' the original id_acao is preserved
        in provenance (Requirement 4.2).

        Args:
            skill: A fully-populated KnownSkill instance.
        """
        self._store[skill.skill_id] = skill
        logger.info(
            "Skill stored",
            extra={
                "skill_id": skill.skill_id,
                "source_stage": skill.source_stage,
                "promotion_state": skill.promotion_state,
            },
        )

    def get(self, skill_id: str) -> Optional[KnownSkill]:
        """Return the skill with the given id, or None."""
        return self._store.get(skill_id)

    def all(self) -> list[KnownSkill]:
        """Return all stored skills."""
        return list(self._store.values())

    # ──────────────────────────────────────────────────────────
    # Retrieval
    # ──────────────────────────────────────────────────────────

    def retrieve(
        self,
        mode: str,
        screen_family: str = "",
        component_family: str = "",
        semantic_action: str = "",
        pattern: str = "",
    ) -> list[KnownSkill]:
        """
        Retrieve skills matching the given context.

        Modes
        -----
        'exact'
            Strict fingerprint: screen_family + component_family +
            semantic_action + pattern must all match.
            Returns skills at any promotion_state.

        'family'
            Match by screen_family + component_family.
            Returns only skills with promotion_state in
            {'skill_candidate', 'promoted_skill'}.

        'pattern'
            Match by pattern + semantic_action.
            Returns only skills with promotion_state in
            {'skill_candidate', 'promoted_skill'}.

        Args:
            mode:             One of 'exact', 'family', 'pattern'.
            screen_family:    Screen family to match.
            component_family: Component family to match.
            semantic_action:  Semantic action to match.
            pattern:          Pattern (pattern_detectado) to match.

        Returns:
            List of matching KnownSkill records, sorted by promotion_state
            descending (promoted_skill first) then by success_count descending.

        Raises:
            ValueError: If mode is not one of the three supported values.
        """
        if mode == "exact":
            results = [
                s for s in self._store.values()
                if (
                    s.screen_family == screen_family
                    and s.component_family == component_family
                    and s.semantic_action == semantic_action
                    and s.pattern == pattern
                )
            ]
        elif mode == "family":
            results = [
                s for s in self._store.values()
                if (
                    s.screen_family == screen_family
                    and s.component_family == component_family
                    and s.promotion_state in _RETRIEVABLE_STATES
                )
            ]
        elif mode == "pattern":
            results = [
                s for s in self._store.values()
                if (
                    s.pattern == pattern
                    and s.semantic_action == semantic_action
                    and s.promotion_state in _RETRIEVABLE_STATES
                )
            ]
        else:
            raise ValueError(
                f"SkillMemory.retrieve() mode must be 'exact', 'family', or 'pattern', got '{mode}'"
            )

        # Sort: promoted_skill first, then by success_count desc
        _rank = {"promoted_skill": 0, "skill_candidate": 1, "reviewed_shadow": 2, "raw_shadow": 3}
        results.sort(key=lambda s: (_rank.get(s.promotion_state, 9), -s.success_count))

        logger.debug(
            "SkillMemory.retrieve",
            extra={
                "mode": mode,
                "screen_family": screen_family,
                "component_family": component_family,
                "semantic_action": semantic_action,
                "pattern": pattern,
                "results_count": len(results),
            },
        )
        return results

    # ──────────────────────────────────────────────────────────
    # Success / failure tracking  (Requirements 4.3, 4.4)
    # ──────────────────────────────────────────────────────────

    def increment_success(self, skill_id: str) -> bool:
        """
        Increment success_count and update last_seen for the given skill.

        Args:
            skill_id: ID of the skill to update.

        Returns:
            True if the skill was found and updated, False otherwise.
        """
        skill = self._store.get(skill_id)
        if skill is None:
            logger.warning("increment_success: skill not found", extra={"skill_id": skill_id})
            return False

        skill.success_count += 1
        skill.last_seen = datetime.now(timezone.utc).isoformat()
        logger.debug(
            "Skill success recorded",
            extra={"skill_id": skill_id, "success_count": skill.success_count},
        )
        return True

    def increment_failure(self, skill_id: str) -> bool:
        """
        Increment failure_count, update last_seen, and set review_required=True
        if failure_count exceeds success_count.

        Args:
            skill_id: ID of the skill to update.

        Returns:
            True if the skill was found and updated, False otherwise.
        """
        skill = self._store.get(skill_id)
        if skill is None:
            logger.warning("increment_failure: skill not found", extra={"skill_id": skill_id})
            return False

        skill.failure_count += 1
        skill.last_seen = datetime.now(timezone.utc).isoformat()

        if skill.failure_count > skill.success_count:
            skill.review_required = True
            logger.warning(
                "Skill flagged for review: failures exceed successes",
                extra={
                    "skill_id": skill_id,
                    "success_count": skill.success_count,
                    "failure_count": skill.failure_count,
                },
            )
        else:
            logger.debug(
                "Skill failure recorded",
                extra={"skill_id": skill_id, "failure_count": skill.failure_count},
            )
        return True

    # ──────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────

    def store_from_events(
        self,
        skill: KnownSkill,
        contributing_events: list[dict],
    ) -> None:
        """
        Store a KnownSkill, computing expected_effect from the most common
        value across contributing shadow events (Requirement 8.6).

        Args:
            skill:               The KnownSkill to store.
            contributing_events: List of shadow event dicts that produced this skill.
        """
        if contributing_events:
            # Tally expected_effect values
            counts: dict[str, int] = {}
            for ev in contributing_events:
                val = ev.get("expected_effect", "")
                if val:
                    counts[val] = counts.get(val, 0) + 1
            if counts:
                most_common = max(counts, key=lambda k: counts[k])
                skill.expected_effect = most_common

        self.store(skill)

    def count(self) -> int:
        """Return the total number of stored skills."""
        return len(self._store)

    def clear(self) -> None:
        """Remove all stored skills (useful for testing)."""
        self._store.clear()

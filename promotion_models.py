"""
Promotion models for the Next-Legacy Diamond Integration.

This module defines the PromotionBenchmark data model that determines when a skill
candidate can be promoted to Level 3 (promoted skill).

Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class PromotionBenchmark:
    """
    Quantified thresholds for Level 2 → Level 3 promotion.
    Defined in docs/SKILL_PROMOTION_POLICY.md.
    
    This benchmark evaluates whether a skill candidate has sufficient quality,
    consistency, and reliability to be promoted to a reusable promoted skill.
    """
    
    min_success_rate: float = 0.70              # 70% success rate
    min_semantic_consistency_events: int = 3    # 3 distinct events
    min_pattern_stability: float = 0.80         # 80% pattern consistency
    min_average_confidence: float = 0.60        # 0.6 average confidence
    max_hitl_correction_rate: float = 0.20      # 20% HITL correction rate
    min_effect_coherence: float = 0.60          # 60% effect coherence
    
    def evaluate(self, skill_candidate: Any) -> tuple[bool, list[str]]:
        """
        Evaluates all benchmark criteria against a skill candidate.
        
        This method checks all six promotion criteria:
        1. Success rate >= 70%
        2. Semantic target consistency across >= 3 events
        3. Pattern stability >= 80%
        4. Average confidence >= 0.6
        5. Post-HITL correction rate < 20% (if HITL performed)
        6. Expected/observed effect coherence >= 60%
        
        Args:
            skill_candidate: A KnownSkill object with the following expected attributes:
                - success_count: int
                - failure_count: int
                - provenance: dict with 'contributing_events' list
                - average_confidence: float
                - pattern: str (pattern_detectado value)
                
        Returns:
            tuple[bool, list[str]]: A tuple containing:
                - passes: True if all criteria are met, False otherwise
                - failing_criteria: List of criterion names that failed (empty if all pass)
        
        Example:
            >>> benchmark = PromotionBenchmark()
            >>> passes, failures = benchmark.evaluate(skill_candidate)
            >>> if not passes:
            ...     print(f"Failed criteria: {', '.join(failures)}")
        """
        failing_criteria = []
        
        # Criterion 1: Success rate >= 70%
        # Requirement 7.1: success_count / (success_count + failure_count) >= 0.70
        total_executions = skill_candidate.success_count + skill_candidate.failure_count
        if total_executions > 0:
            success_rate = skill_candidate.success_count / total_executions
            if success_rate < self.min_success_rate:
                failing_criteria.append("min_success_rate")
        else:
            # No executions means we can't evaluate success rate
            failing_criteria.append("min_success_rate")
        
        # Criterion 2: Semantic target consistency across >= 3 events
        # Requirement 7.2: semantic_action consistent across at least 3 distinct events
        contributing_events = skill_candidate.provenance.get('contributing_events', [])
        if len(contributing_events) < self.min_semantic_consistency_events:
            failing_criteria.append("min_semantic_consistency_events")
        
        # Criterion 3: Pattern stability >= 80%
        # Requirement 7.3: pattern_detectado same value across >= 80% of events
        if contributing_events:
            # Count how many events have the same pattern as the skill's primary pattern
            primary_pattern = skill_candidate.pattern
            matching_pattern_count = sum(
                1 for event in contributing_events 
                if event.get('pattern_detectado') == primary_pattern
            )
            pattern_stability = matching_pattern_count / len(contributing_events)
            if pattern_stability < self.min_pattern_stability:
                failing_criteria.append("min_pattern_stability")
        else:
            failing_criteria.append("min_pattern_stability")
        
        # Criterion 4: Average confidence >= 0.6
        # Requirement 7.4: minimum average confidence of 0.6
        if skill_candidate.average_confidence < self.min_average_confidence:
            failing_criteria.append("min_average_confidence")
        
        # Criterion 5: Post-HITL correction rate < 20% (if HITL performed)
        # Requirement 7.5: fewer than 1 in 5 HITL reviews resulted in correction
        hitl_reviews = sum(
            1 for event in contributing_events 
            if event.get('hitl_reviewed', False)
        )
        if hitl_reviews > 0:
            hitl_corrections = sum(
                1 for event in contributing_events 
                if event.get('hitl_corrected', False)
            )
            hitl_correction_rate = hitl_corrections / hitl_reviews
            if hitl_correction_rate >= self.max_hitl_correction_rate:
                failing_criteria.append("max_hitl_correction_rate")
        
        # Criterion 6: Expected/observed effect coherence >= 60%
        # Requirement 7.6: expected_effect and observed_effect coherent for >= 60% of events
        events_with_effects = [
            event for event in contributing_events
            if event.get('expected_effect') and event.get('observed_effect')
        ]
        if events_with_effects:
            coherent_count = sum(
                1 for event in events_with_effects
                if self._effects_are_coherent(
                    event.get('expected_effect', ''),
                    event.get('observed_effect', '')
                )
            )
            effect_coherence = coherent_count / len(events_with_effects)
            if effect_coherence < self.min_effect_coherence:
                failing_criteria.append("min_effect_coherence")
        else:
            # If no events have both effects, we can't evaluate coherence
            failing_criteria.append("min_effect_coherence")
        
        # Return True if no criteria failed, False otherwise
        passes = len(failing_criteria) == 0
        return passes, failing_criteria
    
    def _effects_are_coherent(self, expected: str, observed: str) -> bool:
        """
        Determines if expected and observed effects are coherent.
        
        Effects are considered coherent if:
        - Both are non-empty
        - They are not contradictory (basic heuristic check)
        
        Args:
            expected: The expected effect string
            observed: The observed effect string
            
        Returns:
            bool: True if effects are coherent, False otherwise
        """
        # Both must be non-empty
        if not expected or not observed:
            return False
        
        # Basic contradiction detection: if observed explicitly negates expected
        # This is a simple heuristic - could be enhanced with more sophisticated logic
        expected_lower = expected.lower()
        observed_lower = observed.lower()
        
        # Check for explicit negation patterns
        # Each tuple represents opposing actions/states
        negation_patterns = [
            ('open', 'close'),
            ('open', 'closed'),
            ('open', 'hide'),
            ('open', 'hidden'),
            ('close', 'open'),
            ('show', 'hide'),
            ('show', 'hidden'),
            ('hide', 'show'),
            ('add', 'remove'),
            ('remove', 'add'),
            ('create', 'delete'),
            ('delete', 'create'),
            ('enable', 'disable'),
            ('disable', 'enable'),
        ]
        
        for pattern_a, pattern_b in negation_patterns:
            if pattern_a in expected_lower and pattern_b in observed_lower:
                return False
            if pattern_b in expected_lower and pattern_a in observed_lower:
                return False
        
        # If no contradictions detected, consider them coherent
        return True

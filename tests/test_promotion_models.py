"""
Tests for promotion_models.py

Tests the PromotionBenchmark data model and its evaluate() method.
"""

# Import the module under test
import sys
from dataclasses import dataclass
from typing import Any

import pytest

sys.path.insert(0, '.')
from promotion_models import PromotionBenchmark


# Mock KnownSkill for testing
@dataclass
class MockKnownSkill:
    """Mock KnownSkill for testing purposes."""
    success_count: int
    failure_count: int
    average_confidence: float
    pattern: str
    provenance: dict


class TestPromotionBenchmark:
    """Test suite for PromotionBenchmark."""

    def test_default_thresholds(self):
        """Test that default thresholds match requirements."""
        benchmark = PromotionBenchmark()

        assert benchmark.min_success_rate == 0.70
        assert benchmark.min_semantic_consistency_events == 3
        assert benchmark.min_pattern_stability == 0.80
        assert benchmark.min_average_confidence == 0.60
        assert benchmark.max_hitl_correction_rate == 0.20
        assert benchmark.min_effect_coherence == 0.60

    def test_evaluate_all_criteria_pass(self):
        """Test evaluation when all criteria pass."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,  # 80% success rate
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'modal opens',
                        'observed_effect': 'modal opened successfully',
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'modal opens',
                        'observed_effect': 'modal displayed',
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'modal opens',
                        'observed_effect': 'modal shown',
                    },
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is True
        assert failing == []

    def test_evaluate_fails_success_rate(self):
        """Test evaluation fails when success rate is below threshold."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=6,
            failure_count=5,  # ~55% success rate
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_success_rate" in failing

    def test_evaluate_fails_no_executions(self):
        """Test evaluation fails when there are no executions."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=0,
            failure_count=0,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_success_rate" in failing

    def test_evaluate_fails_semantic_consistency(self):
        """Test evaluation fails when fewer than 3 contributing events."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_semantic_consistency_events" in failing

    def test_evaluate_fails_pattern_stability(self):
        """Test evaluation fails when pattern stability is below 80%."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'button_click', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'form_fill', 'expected_effect': 'open', 'observed_effect': 'opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_pattern_stability" in failing

    def test_evaluate_fails_average_confidence(self):
        """Test evaluation fails when average confidence is below threshold."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.50,  # Below 0.60 threshold
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'open', 'observed_effect': 'opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_average_confidence" in failing

    def test_evaluate_fails_hitl_correction_rate(self):
        """Test evaluation fails when HITL correction rate is too high."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': True,
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': True,
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': False,
                    },
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "max_hitl_correction_rate" in failing  # 2/3 = 66% > 20%

    def test_evaluate_passes_hitl_within_threshold(self):
        """Test evaluation passes when HITL correction rate is within threshold."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': False,
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': False,
                    },
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'open',
                        'observed_effect': 'opened',
                        'hitl_reviewed': True,
                        'hitl_corrected': False,
                    },
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is True
        assert failing == []

    def test_evaluate_fails_effect_coherence(self):
        """Test evaluation fails when effect coherence is below threshold."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'modal opens', 'observed_effect': 'modal closed'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'modal opens', 'observed_effect': 'modal hidden'},
                    {'pattern_detectado': 'menu_navigation', 'expected_effect': 'modal opens', 'observed_effect': 'modal opened'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_effect_coherence" in failing  # Only 1/3 = 33% coherent

    def test_evaluate_fails_missing_effects(self):
        """Test evaluation fails when events lack effect data."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'menu_navigation'},
                    {'pattern_detectado': 'menu_navigation'},
                    {'pattern_detectado': 'menu_navigation'},
                ]
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_effect_coherence" in failing

    def test_effects_are_coherent_basic(self):
        """Test basic coherence detection."""
        benchmark = PromotionBenchmark()

        # Coherent cases
        assert benchmark._effects_are_coherent('modal opens', 'modal opened') is True
        assert benchmark._effects_are_coherent('row deleted', 'row removed from list') is True

        # Non-coherent cases (contradictions)
        assert benchmark._effects_are_coherent('modal opens', 'modal closed') is False
        assert benchmark._effects_are_coherent('show panel', 'hide panel') is False
        assert benchmark._effects_are_coherent('add item', 'remove item') is False

        # Empty cases
        assert benchmark._effects_are_coherent('', 'something') is False
        assert benchmark._effects_are_coherent('something', '') is False
        assert benchmark._effects_are_coherent('', '') is False

    def test_evaluate_multiple_failures(self):
        """Test evaluation with multiple failing criteria."""
        benchmark = PromotionBenchmark()

        skill = MockKnownSkill(
            success_count=3,
            failure_count=7,  # 30% success rate - FAIL
            average_confidence=0.40,  # Below 0.60 - FAIL
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {'pattern_detectado': 'button_click', 'expected_effect': 'open', 'observed_effect': 'closed'},
                ]  # Only 1 event - FAIL semantic consistency, pattern stability, effect coherence
            }
        )

        passes, failing = benchmark.evaluate(skill)

        assert passes is False
        assert "min_success_rate" in failing
        assert "min_semantic_consistency_events" in failing
        assert "min_pattern_stability" in failing
        assert "min_average_confidence" in failing
        assert "min_effect_coherence" in failing

    def test_custom_thresholds(self):
        """Test that custom thresholds can be set."""
        benchmark = PromotionBenchmark(
            min_success_rate=0.80,
            min_semantic_consistency_events=5,
            min_pattern_stability=0.90,
            min_average_confidence=0.70,
            max_hitl_correction_rate=0.10,
            min_effect_coherence=0.70
        )

        assert benchmark.min_success_rate == 0.80
        assert benchmark.min_semantic_consistency_events == 5
        assert benchmark.min_pattern_stability == 0.90
        assert benchmark.min_average_confidence == 0.70
        assert benchmark.max_hitl_correction_rate == 0.10
        assert benchmark.min_effect_coherence == 0.70


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

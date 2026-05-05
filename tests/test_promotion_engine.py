"""
Tests for promotion_engine.py

Tests the Promotion_Gate_Engine class and its promotion logic.
"""

# Import the module under test
import sys
from dataclasses import dataclass
from typing import Any

import pytest

sys.path.insert(0, '.')
from promotion_engine import Promotion_Gate_Engine
from promotion_models import PromotionBenchmark


# Mock KnownSkill for testing Level 3 promotion
@dataclass
class MockKnownSkill:
    """Mock KnownSkill for testing purposes."""
    skill_id: str
    success_count: int
    failure_count: int
    average_confidence: float
    pattern: str
    provenance: dict


class TestPromotionGateEngine:
    """Test suite for Promotion_Gate_Engine."""

    def test_initialization(self):
        """Test that engine initializes with default benchmark."""
        engine = Promotion_Gate_Engine()

        assert engine.benchmark is not None
        assert isinstance(engine.benchmark, PromotionBenchmark)

    def test_evaluate_promotion_readiness_level_0(self):
        """Test evaluation returns Level 0 for records that don't meet Level 1 criteria."""
        engine = Promotion_Gate_Engine()

        # Record with missing screen_family
        record = {
            "id_acao": 1,
            "screen_family": "",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        level, state = engine.evaluate_promotion_readiness(record)

        assert level == 0
        assert state == "raw_shadow"

    def test_evaluate_promotion_readiness_level_1(self):
        """Test evaluation returns Level 1 for records that meet Level 1 criteria."""
        engine = Promotion_Gate_Engine()

        # Record that meets all Level 1 criteria
        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        level, state = engine.evaluate_promotion_readiness(record)

        assert level == 1
        assert state == "reviewed_shadow"

    def test_promote_to_level_1_success(self):
        """Test Level 1 promotion succeeds with valid record."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is True

    def test_promote_to_level_1_fails_empty_screen_family(self):
        """Test Level 1 promotion fails with empty screen_family."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_fails_unknown_screen_family(self):
        """Test Level 1 promotion fails with unknown screen_family."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "unknown",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_fails_empty_component_family(self):
        """Test Level 1 promotion fails with empty component_family."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_fails_unknown_component_family(self):
        """Test Level 1 promotion fails with unknown component_family."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "unknown",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_fails_is_noise_true(self):
        """Test Level 1 promotion fails when is_noise is true."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": True,
            "confianca_captura": "alta",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_fails_baixa_confianca(self):
        """Test Level 1 promotion fails with baixa confianca_captura."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "baixa",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_1_succeeds_media_confianca(self):
        """Test Level 1 promotion succeeds with media confianca_captura."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "media",
            "intencao_semantica": "Open document"
        }

        result = engine.promote_to_level_1(record)

        assert result is True

    def test_promote_to_level_1_fails_empty_intencao(self):
        """Test Level 1 promotion fails with empty intencao_semantica."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": "ged_list",
            "component_family": "toolbar_button",
            "is_noise": False,
            "confianca_captura": "alta",
            "intencao_semantica": ""
        }

        result = engine.promote_to_level_1(record)

        assert result is False

    def test_promote_to_level_2_success(self):
        """Test Level 2 promotion succeeds with valid record and history."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 3,
            "semantic_action": "fill",
            "business_entity": "documento",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        history = [
            {
                "id_acao": 1,
                "pattern_detectado": "form_fill",
                "business_target": "Document Name Field"
            }
        ]

        result = engine.promote_to_level_2(record, history)

        assert result is True

    def test_promote_to_level_2_fails_navigate_action(self):
        """Test Level 2 promotion fails with navigate semantic_action."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "semantic_action": "navigate",
            "business_entity": "documento",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        result = engine.promote_to_level_2(record, [])

        assert result is False

    def test_promote_to_level_2_fails_unknown_action(self):
        """Test Level 2 promotion fails with unknown semantic_action."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "semantic_action": "unknown",
            "business_entity": "documento",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        result = engine.promote_to_level_2(record, [])

        assert result is False

    def test_promote_to_level_2_fails_empty_business_entity(self):
        """Test Level 2 promotion fails with empty business_entity."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "semantic_action": "fill",
            "business_entity": "",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        result = engine.promote_to_level_2(record, [])

        assert result is False

    def test_promote_to_level_2_fails_insufficient_pattern_frequency(self):
        """Test Level 2 promotion fails with insufficient pattern frequency."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "semantic_action": "fill",
            "business_entity": "documento",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        # Empty history means only 1 occurrence (current record)
        result = engine.promote_to_level_2(record, [])

        assert result is False

    def test_promote_to_level_2_counts_current_record(self):
        """Test Level 2 promotion counts current record in pattern frequency."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 2,
            "semantic_action": "fill",
            "business_entity": "documento",
            "screen_family": "ged_form",
            "pattern_detectado": "form_fill",
            "business_target": "Document Name Field"
        }

        history = [
            {
                "id_acao": 1,
                "pattern_detectado": "form_fill",
                "business_target": "Document Name Field"
            }
        ]

        result = engine.promote_to_level_2(record, history)

        # Current record + 1 history = 2 occurrences, should pass
        assert result is True

    def test_promote_to_level_3_success(self):
        """Test Level 3 promotion succeeds with valid skill candidate."""
        engine = Promotion_Gate_Engine()

        skill = MockKnownSkill(
            skill_id="skill_001",
            success_count=8,
            failure_count=2,
            average_confidence=0.75,
            pattern="menu_navigation",
            provenance={
                'contributing_events': [
                    {
                        'pattern_detectado': 'menu_navigation',
                        'expected_effect': 'modal opens',
                        'observed_effect': 'modal opened',
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

        result = engine.promote_to_level_3(skill)

        assert result is True

    def test_promote_to_level_3_fails_low_success_rate(self):
        """Test Level 3 promotion fails with low success rate."""
        engine = Promotion_Gate_Engine()

        skill = MockKnownSkill(
            skill_id="skill_002",
            success_count=3,
            failure_count=7,
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

        result = engine.promote_to_level_3(skill)

        assert result is False

    def test_promote_to_level_3_custom_benchmark(self):
        """Test Level 3 promotion with custom benchmark."""
        engine = Promotion_Gate_Engine()

        custom_benchmark = PromotionBenchmark(
            min_success_rate=0.90,  # Higher threshold
            min_semantic_consistency_events=5
        )

        skill = MockKnownSkill(
            skill_id="skill_003",
            success_count=8,
            failure_count=2,  # 80% success rate
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

        result = engine.promote_to_level_3(skill, custom_benchmark)

        # Should fail because 80% < 90% and only 3 events < 5
        assert result is False

    def test_record_gate_failure(self):
        """Test gate failure recording."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1,
            "screen_family": ""
        }

        engine.record_gate_failure(record, 1, "screen_family")

        assert "gate_failure_reason" in record
        assert record["gate_failure_reason"] == "Level 1: screen_family"

    def test_record_gate_failure_multiple_calls(self):
        """Test gate failure recording overwrites previous failures."""
        engine = Promotion_Gate_Engine()

        record = {
            "id_acao": 1
        }

        engine.record_gate_failure(record, 1, "screen_family")
        assert record["gate_failure_reason"] == "Level 1: screen_family"

        engine.record_gate_failure(record, 2, "pattern_frequency")
        assert record["gate_failure_reason"] == "Level 2: pattern_frequency"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

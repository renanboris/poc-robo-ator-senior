"""
test_skill_models.py — Unit tests for KnownSkill data model
============================================================
Tests the evolved KnownSkill contract with full provenance and governance metadata.

**Validates: Requirements 4.1**
"""

import pytest
from datetime import datetime
from skill_models import KnownSkill


class TestKnownSkillCreation:
    """Tests for KnownSkill instantiation and validation."""
    
    def test_create_minimal_known_skill(self):
        """Test creating a KnownSkill with all required fields."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Open GED Document",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="document opens in viewer",
            selector="tr.documento-row",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.skill_id == "skill_001"
        assert skill.skill_name == "Open GED Document"
        assert skill.semantic_action == "open"
        assert skill.business_entity == "documento"
        assert skill.screen_family == "ged_list"
        assert skill.component_family == "table_row"
        assert skill.pattern == "table_selection"
        assert skill.expected_effect == "document opens in viewer"
        assert skill.selector == "tr.documento-row"
        assert skill.fallback_selectors == []
        assert skill.success_count == 0
        assert skill.failure_count == 0
        assert skill.average_confidence == 0.0
        assert skill.promotion_state == "raw_shadow"
        assert skill.source_stage == "dual_shadow"
        assert skill.review_required is False
        assert skill.provenance == {}
        assert skill.created_at == "2024-01-15T10:30:00Z"
        assert skill.last_seen == "2024-01-15T10:30:00Z"
        assert skill.last_validated_at is None
    
    def test_create_full_known_skill(self):
        """Test creating a KnownSkill with all fields populated."""
        skill = KnownSkill(
            skill_id="skill_002",
            skill_name="Delete GED Document",
            semantic_action="delete",
            business_entity="documento",
            screen_family="ged_list",
            component_family="context_menu_item",
            pattern="menu_navigation",
            expected_effect="document removed from list",
            selector="li.menu-item-delete",
            fallback_selectors=["li[data-action='delete']", "li.delete-action"],
            success_count=15,
            failure_count=2,
            average_confidence=0.85,
            promotion_state="promoted_skill",
            source_stage="hitl_promoted",
            review_required=False,
            provenance={
                "original_event_id": 42,
                "source_file": "shadow_exports/capture_2024_01_15.jsonl",
                "contributing_events": [
                    {"id_acao": 42, "pattern_detectado": "menu_navigation"},
                    {"id_acao": 58, "pattern_detectado": "menu_navigation"},
                    {"id_acao": 73, "pattern_detectado": "menu_navigation"}
                ]
            },
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-20T14:22:00Z",
            last_validated_at="2024-01-18T09:00:00Z"
        )
        
        assert skill.skill_id == "skill_002"
        assert skill.fallback_selectors == ["li[data-action='delete']", "li.delete-action"]
        assert skill.success_count == 15
        assert skill.failure_count == 2
        assert skill.average_confidence == 0.85
        assert skill.promotion_state == "promoted_skill"
        assert skill.source_stage == "hitl_promoted"
        assert skill.provenance["original_event_id"] == 42
        assert len(skill.provenance["contributing_events"]) == 3
        assert skill.last_validated_at == "2024-01-18T09:00:00Z"


class TestKnownSkillValidation:
    """Tests for KnownSkill field validation."""
    
    def test_empty_skill_id_raises_error(self):
        """Test that empty skill_id raises ValueError."""
        with pytest.raises(ValueError, match="skill_id cannot be empty"):
            KnownSkill(
                skill_id="",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_empty_selector_raises_error(self):
        """Test that empty selector raises ValueError."""
        with pytest.raises(ValueError, match="selector cannot be empty"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="",
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_invalid_promotion_state_raises_error(self):
        """Test that invalid promotion_state raises ValueError."""
        with pytest.raises(ValueError, match="promotion_state must be one of"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                promotion_state="invalid_state",
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_invalid_source_stage_raises_error(self):
        """Test that invalid source_stage raises ValueError."""
        with pytest.raises(ValueError, match="source_stage must be one of"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                source_stage="invalid_stage",
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_invalid_confidence_below_zero_raises_error(self):
        """Test that average_confidence below 0.0 raises ValueError."""
        with pytest.raises(ValueError, match="average_confidence must be between 0.0 and 1.0"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                average_confidence=-0.1,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_invalid_confidence_above_one_raises_error(self):
        """Test that average_confidence above 1.0 raises ValueError."""
        with pytest.raises(ValueError, match="average_confidence must be between 0.0 and 1.0"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                average_confidence=1.5,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_negative_success_count_raises_error(self):
        """Test that negative success_count raises ValueError."""
        with pytest.raises(ValueError, match="success_count must be non-negative"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                success_count=-5,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
    
    def test_negative_failure_count_raises_error(self):
        """Test that negative failure_count raises ValueError."""
        with pytest.raises(ValueError, match="failure_count must be non-negative"):
            KnownSkill(
                skill_id="skill_001",
                skill_name="Test Skill",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                failure_count=-3,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )


class TestKnownSkillMethods:
    """Tests for KnownSkill helper methods."""
    
    def test_get_success_rate_with_executions(self):
        """Test success rate calculation with executions."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            success_count=7,
            failure_count=3,
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.get_success_rate() == 0.7
    
    def test_get_success_rate_with_no_executions(self):
        """Test success rate calculation with no executions."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.get_success_rate() == 0.0
    
    def test_get_success_rate_perfect(self):
        """Test success rate calculation with 100% success."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            success_count=10,
            failure_count=0,
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.get_success_rate() == 1.0
    
    def test_is_promoted_true(self):
        """Test is_promoted returns True for promoted_skill."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            promotion_state="promoted_skill",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.is_promoted() is True
    
    def test_is_promoted_false(self):
        """Test is_promoted returns False for non-promoted states."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            promotion_state="skill_candidate",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.is_promoted() is False
    
    def test_is_skill_candidate_true(self):
        """Test is_skill_candidate returns True for skill_candidate."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            promotion_state="skill_candidate",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.is_skill_candidate() is True
    
    def test_is_skill_candidate_false(self):
        """Test is_skill_candidate returns False for other states."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            promotion_state="promoted_skill",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.is_skill_candidate() is False
    
    def test_needs_review_flag_true(self):
        """Test needs_review returns True when review_required flag is set."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            review_required=True,
            success_count=10,
            failure_count=2,
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.needs_review() is True
    
    def test_needs_review_failure_exceeds_success(self):
        """Test needs_review returns True when failures exceed successes."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            review_required=False,
            success_count=2,
            failure_count=5,
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.needs_review() is True
    
    def test_needs_review_false(self):
        """Test needs_review returns False when no review needed."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            review_required=False,
            success_count=10,
            failure_count=2,
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        assert skill.needs_review() is False
    
    def test_get_provenance_summary(self):
        """Test provenance summary generation."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            source_stage="dual_shadow",
            provenance={
                "original_event_id": 42,
                "source_file": "shadow_exports/capture_2024_01_15.jsonl"
            },
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        summary = skill.get_provenance_summary()
        assert summary == "dual_shadow | event_id: 42 | source: shadow_exports/capture_2024_01_15.jsonl"
    
    def test_get_provenance_summary_missing_fields(self):
        """Test provenance summary with missing provenance fields."""
        skill = KnownSkill(
            skill_id="skill_001",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="test effect",
            selector="tr.test",
            source_stage="runtime_learning",
            created_at="2024-01-15T10:30:00Z",
            last_seen="2024-01-15T10:30:00Z"
        )
        
        summary = skill.get_provenance_summary()
        assert summary == "runtime_learning | event_id: unknown | source: unknown"


class TestKnownSkillPromotionStates:
    """Tests for different promotion states."""
    
    def test_all_promotion_states_valid(self):
        """Test that all four promotion states are valid."""
        states = ["raw_shadow", "reviewed_shadow", "skill_candidate", "promoted_skill"]
        
        for state in states:
            skill = KnownSkill(
                skill_id=f"skill_{state}",
                skill_name=f"Test {state}",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                promotion_state=state,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
            assert skill.promotion_state == state


class TestKnownSkillSourceStages:
    """Tests for different source stages."""
    
    def test_all_source_stages_valid(self):
        """Test that all four source stages are valid."""
        stages = ["legacy_import", "dual_shadow", "runtime_learning", "hitl_promoted"]
        
        for stage in stages:
            skill = KnownSkill(
                skill_id=f"skill_{stage}",
                skill_name=f"Test {stage}",
                semantic_action="open",
                business_entity="documento",
                screen_family="ged_list",
                component_family="table_row",
                pattern="table_selection",
                expected_effect="test effect",
                selector="tr.test",
                source_stage=stage,
                created_at="2024-01-15T10:30:00Z",
                last_seen="2024-01-15T10:30:00Z"
            )
            assert skill.source_stage == stage

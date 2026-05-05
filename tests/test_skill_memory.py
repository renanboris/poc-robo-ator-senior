"""
test_skill_memory.py — Unit Tests for SkillMemory
==================================================
Tests the storage and retrieval functionality of the SkillMemory class.

Requirements: 4.5, 4.6
"""

import pytest
import os
import json
from datetime import datetime, timezone
from skill_memory import SkillMemory
from skill_models import KnownSkill


@pytest.fixture
def temp_storage_path(tmp_path):
    """Provides a temporary storage path for tests."""
    return str(tmp_path / "test_skill_memory.json")


@pytest.fixture
def skill_memory(temp_storage_path):
    """Provides a fresh SkillMemory instance for each test."""
    return SkillMemory(storage_path=temp_storage_path)


@pytest.fixture
def sample_skill():
    """Provides a sample KnownSkill for testing."""
    return KnownSkill(
        skill_id="skill_001",
        skill_name="Open GED Document",
        semantic_action="open",
        business_entity="documento",
        screen_family="ged_list",
        component_family="table_row",
        pattern="table_selection",
        expected_effect="document opens in viewer",
        selector="tr.documento-row",
        fallback_selectors=["tr[data-tipo='documento']", "tr.row-documento"],
        success_count=15,
        failure_count=2,
        average_confidence=0.85,
        promotion_state="promoted_skill",
        source_stage="dual_shadow",
        review_required=False,
        provenance={
            "original_event_id": 42,
            "source_file": "shadow_exports/capture_2024_01_15.jsonl",
            "contributing_events": [42, 43, 44]
        },
        created_at="2024-01-15T10:30:00Z",
        last_seen="2024-01-20T14:22:00Z",
        last_validated_at="2024-01-18T09:00:00Z"
    )


@pytest.fixture
def skill_candidate():
    """Provides a skill candidate (Level 2) for testing."""
    return KnownSkill(
        skill_id="skill_002",
        skill_name="Delete GED Document",
        semantic_action="delete",
        business_entity="documento",
        screen_family="ged_list",
        component_family="context_menu_item",
        pattern="context_menu_action",
        expected_effect="document removed from list",
        selector="li.menu-delete",
        promotion_state="skill_candidate",
        source_stage="dual_shadow",
        created_at="2024-01-15T11:00:00Z",
        last_seen="2024-01-15T11:00:00Z"
    )


@pytest.fixture
def raw_shadow_skill():
    """Provides a raw shadow skill (Level 0) for testing."""
    return KnownSkill(
        skill_id="skill_003",
        skill_name="Unknown Action",
        semantic_action="navigate",
        business_entity="unknown",
        screen_family="unknown",
        component_family="unknown",
        pattern="unknown",
        expected_effect="unknown",
        selector="div",
        promotion_state="raw_shadow",
        source_stage="dual_shadow",
        created_at="2024-01-15T12:00:00Z",
        last_seen="2024-01-15T12:00:00Z"
    )


class TestSkillMemoryStore:
    """Tests for the store() method."""
    
    def test_store_skill(self, skill_memory, sample_skill):
        """Test storing a skill successfully."""
        skill_memory.store(sample_skill)
        
        # Verify skill is in memory
        retrieved = skill_memory.get_by_id("skill_001")
        assert retrieved is not None
        assert retrieved.skill_id == "skill_001"
        assert retrieved.skill_name == "Open GED Document"
    
    def test_store_persists_to_disk(self, skill_memory, sample_skill, temp_storage_path):
        """Test that store() persists to disk."""
        skill_memory.store(sample_skill)
        
        # Verify file exists
        assert os.path.exists(temp_storage_path)
        
        # Verify content
        with open(temp_storage_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert "skill_001" in data
        assert data["skill_001"]["skill_name"] == "Open GED Document"
    
    def test_store_overwrites_existing_skill(self, skill_memory, sample_skill):
        """Test that storing a skill with the same ID overwrites the existing one."""
        skill_memory.store(sample_skill)
        
        # Modify and store again
        sample_skill.skill_name = "Modified Name"
        skill_memory.store(sample_skill)
        
        # Verify updated
        retrieved = skill_memory.get_by_id("skill_001")
        assert retrieved.skill_name == "Modified Name"
    
    def test_store_multiple_skills(self, skill_memory, sample_skill, skill_candidate):
        """Test storing multiple skills."""
        skill_memory.store(sample_skill)
        skill_memory.store(skill_candidate)
        
        assert skill_memory.count() == 2
        assert skill_memory.get_by_id("skill_001") is not None
        assert skill_memory.get_by_id("skill_002") is not None


class TestSkillMemoryRetrieveExact:
    """Tests for retrieve() with mode='exact'."""
    
    def test_retrieve_exact_success(self, skill_memory, sample_skill):
        """Test exact retrieval by fingerprint (skill_id)."""
        skill_memory.store(sample_skill)
        
        results = skill_memory.retrieve(mode='exact', fingerprint='skill_001')
        
        assert len(results) == 1
        assert results[0].skill_id == "skill_001"
    
    def test_retrieve_exact_not_found(self, skill_memory, sample_skill):
        """Test exact retrieval when skill doesn't exist."""
        skill_memory.store(sample_skill)
        
        results = skill_memory.retrieve(mode='exact', fingerprint='nonexistent')
        
        assert len(results) == 0
    
    def test_retrieve_exact_filters_raw_shadow(self, skill_memory, raw_shadow_skill):
        """Test that exact retrieval filters out raw_shadow skills."""
        skill_memory.store(raw_shadow_skill)
        
        results = skill_memory.retrieve(mode='exact', fingerprint='skill_003')
        
        # raw_shadow should be filtered out
        assert len(results) == 0
    
    def test_retrieve_exact_missing_fingerprint(self, skill_memory):
        """Test that exact mode raises error without fingerprint."""
        with pytest.raises(ValueError, match="requires 'fingerprint'"):
            skill_memory.retrieve(mode='exact')


class TestSkillMemoryRetrieveFamily:
    """Tests for retrieve() with mode='family'."""
    
    def test_retrieve_family_success(self, skill_memory, sample_skill, skill_candidate):
        """Test family retrieval by screen_family and component_family."""
        skill_memory.store(sample_skill)
        skill_memory.store(skill_candidate)
        
        results = skill_memory.retrieve(
            mode='family',
            screen_family='ged_list',
            component_family='table_row'
        )
        
        assert len(results) == 1
        assert results[0].skill_id == "skill_001"
    
    def test_retrieve_family_multiple_matches(self, skill_memory):
        """Test family retrieval with multiple matching skills."""
        skill1 = KnownSkill(
            skill_id="skill_a",
            skill_name="Skill A",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="opens",
            selector="tr",
            promotion_state="promoted_skill",
            source_stage="dual_shadow",
            created_at="2024-01-15T10:00:00Z",
            last_seen="2024-01-15T10:00:00Z"
        )
        skill2 = KnownSkill(
            skill_id="skill_b",
            skill_name="Skill B",
            semantic_action="select",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="selects",
            selector="tr",
            promotion_state="skill_candidate",
            source_stage="dual_shadow",
            created_at="2024-01-15T10:00:00Z",
            last_seen="2024-01-15T10:00:00Z"
        )
        
        skill_memory.store(skill1)
        skill_memory.store(skill2)
        
        results = skill_memory.retrieve(
            mode='family',
            screen_family='ged_list',
            component_family='table_row'
        )
        
        assert len(results) == 2
    
    def test_retrieve_family_filters_raw_shadow(self, skill_memory, sample_skill, raw_shadow_skill):
        """Test that family retrieval filters out non-promoted skills."""
        # Set raw_shadow_skill to match family but wrong promotion state
        raw_shadow_skill.screen_family = "ged_list"
        raw_shadow_skill.component_family = "table_row"
        
        skill_memory.store(sample_skill)
        skill_memory.store(raw_shadow_skill)
        
        results = skill_memory.retrieve(
            mode='family',
            screen_family='ged_list',
            component_family='table_row'
        )
        
        # Only promoted_skill should be returned
        assert len(results) == 1
        assert results[0].skill_id == "skill_001"
    
    def test_retrieve_family_missing_screen_family(self, skill_memory):
        """Test that family mode raises error without screen_family."""
        with pytest.raises(ValueError, match="requires 'screen_family'"):
            skill_memory.retrieve(mode='family', component_family='table_row')
    
    def test_retrieve_family_missing_component_family(self, skill_memory):
        """Test that family mode raises error without component_family."""
        with pytest.raises(ValueError, match="requires 'component_family'"):
            skill_memory.retrieve(mode='family', screen_family='ged_list')


class TestSkillMemoryRetrievePattern:
    """Tests for retrieve() with mode='pattern'."""
    
    def test_retrieve_pattern_success(self, skill_memory, sample_skill, skill_candidate):
        """Test pattern retrieval by pattern and semantic_action."""
        skill_memory.store(sample_skill)
        skill_memory.store(skill_candidate)
        
        results = skill_memory.retrieve(
            mode='pattern',
            pattern='table_selection',
            semantic_action='open'
        )
        
        assert len(results) == 1
        assert results[0].skill_id == "skill_001"
    
    def test_retrieve_pattern_multiple_matches(self, skill_memory):
        """Test pattern retrieval with multiple matching skills."""
        skill1 = KnownSkill(
            skill_id="skill_a",
            skill_name="Skill A",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="opens",
            selector="tr",
            promotion_state="promoted_skill",
            source_stage="dual_shadow",
            created_at="2024-01-15T10:00:00Z",
            last_seen="2024-01-15T10:00:00Z"
        )
        skill2 = KnownSkill(
            skill_id="skill_b",
            skill_name="Skill B",
            semantic_action="open",
            business_entity="pasta",
            screen_family="ged_tree",
            component_family="tree_node",
            pattern="table_selection",
            expected_effect="opens",
            selector="div",
            promotion_state="skill_candidate",
            source_stage="dual_shadow",
            created_at="2024-01-15T10:00:00Z",
            last_seen="2024-01-15T10:00:00Z"
        )
        
        skill_memory.store(skill1)
        skill_memory.store(skill2)
        
        results = skill_memory.retrieve(
            mode='pattern',
            pattern='table_selection',
            semantic_action='open'
        )
        
        assert len(results) == 2
    
    def test_retrieve_pattern_filters_raw_shadow(self, skill_memory, sample_skill, raw_shadow_skill):
        """Test that pattern retrieval filters out non-promoted skills."""
        # Set raw_shadow_skill to match pattern but wrong promotion state
        raw_shadow_skill.pattern = "table_selection"
        raw_shadow_skill.semantic_action = "open"
        
        skill_memory.store(sample_skill)
        skill_memory.store(raw_shadow_skill)
        
        results = skill_memory.retrieve(
            mode='pattern',
            pattern='table_selection',
            semantic_action='open'
        )
        
        # Only promoted_skill should be returned
        assert len(results) == 1
        assert results[0].skill_id == "skill_001"
    
    def test_retrieve_pattern_missing_pattern(self, skill_memory):
        """Test that pattern mode raises error without pattern."""
        with pytest.raises(ValueError, match="requires 'pattern'"):
            skill_memory.retrieve(mode='pattern', semantic_action='open')
    
    def test_retrieve_pattern_missing_semantic_action(self, skill_memory):
        """Test that pattern mode raises error without semantic_action."""
        with pytest.raises(ValueError, match="requires 'semantic_action'"):
            skill_memory.retrieve(mode='pattern', pattern='table_selection')


class TestSkillMemoryRetrieveValidation:
    """Tests for retrieve() validation."""
    
    def test_retrieve_invalid_mode(self, skill_memory):
        """Test that invalid mode raises error."""
        with pytest.raises(ValueError, match="Invalid retrieval mode"):
            skill_memory.retrieve(mode='invalid')


class TestSkillMemoryIncrementSuccess:
    """Tests for increment_success() method."""
    
    def test_increment_success(self, skill_memory, sample_skill):
        """Test incrementing success count."""
        skill_memory.store(sample_skill)
        initial_count = sample_skill.success_count
        
        skill_memory.increment_success("skill_001")
        
        updated = skill_memory.get_by_id("skill_001")
        assert updated.success_count == initial_count + 1
    
    def test_increment_success_updates_last_seen(self, skill_memory, sample_skill):
        """Test that increment_success updates last_seen timestamp."""
        skill_memory.store(sample_skill)
        initial_last_seen = sample_skill.last_seen
        
        skill_memory.increment_success("skill_001")
        
        updated = skill_memory.get_by_id("skill_001")
        assert updated.last_seen != initial_last_seen
    
    def test_increment_success_persists(self, skill_memory, sample_skill, temp_storage_path):
        """Test that increment_success persists to disk."""
        skill_memory.store(sample_skill)
        skill_memory.increment_success("skill_001")
        
        # Load fresh instance
        new_memory = SkillMemory(storage_path=temp_storage_path)
        updated = new_memory.get_by_id("skill_001")
        
        assert updated.success_count == sample_skill.success_count + 1
    
    def test_increment_success_nonexistent_skill(self, skill_memory):
        """Test that increment_success raises error for nonexistent skill."""
        with pytest.raises(KeyError, match="not found"):
            skill_memory.increment_success("nonexistent")


class TestSkillMemoryIncrementFailure:
    """Tests for increment_failure() method."""
    
    def test_increment_failure(self, skill_memory, sample_skill):
        """Test incrementing failure count."""
        skill_memory.store(sample_skill)
        initial_count = sample_skill.failure_count
        
        skill_memory.increment_failure("skill_001")
        
        updated = skill_memory.get_by_id("skill_001")
        assert updated.failure_count == initial_count + 1
    
    def test_increment_failure_updates_last_seen(self, skill_memory, sample_skill):
        """Test that increment_failure updates last_seen timestamp."""
        skill_memory.store(sample_skill)
        initial_last_seen = sample_skill.last_seen
        
        skill_memory.increment_failure("skill_001")
        
        updated = skill_memory.get_by_id("skill_001")
        assert updated.last_seen != initial_last_seen
    
    def test_increment_failure_sets_review_required(self, skill_memory):
        """Test that increment_failure sets review_required when failures exceed successes."""
        skill = KnownSkill(
            skill_id="skill_test",
            skill_name="Test Skill",
            semantic_action="open",
            business_entity="documento",
            screen_family="ged_list",
            component_family="table_row",
            pattern="table_selection",
            expected_effect="opens",
            selector="tr",
            success_count=2,
            failure_count=1,
            promotion_state="promoted_skill",
            source_stage="dual_shadow",
            created_at="2024-01-15T10:00:00Z",
            last_seen="2024-01-15T10:00:00Z"
        )
        
        skill_memory.store(skill)
        
        # Increment failure twice to exceed successes
        skill_memory.increment_failure("skill_test")
        skill_memory.increment_failure("skill_test")
        
        updated = skill_memory.get_by_id("skill_test")
        assert updated.failure_count == 3
        assert updated.success_count == 2
        assert updated.review_required is True
    
    def test_increment_failure_persists(self, skill_memory, sample_skill, temp_storage_path):
        """Test that increment_failure persists to disk."""
        skill_memory.store(sample_skill)
        skill_memory.increment_failure("skill_001")
        
        # Load fresh instance
        new_memory = SkillMemory(storage_path=temp_storage_path)
        updated = new_memory.get_by_id("skill_001")
        
        assert updated.failure_count == sample_skill.failure_count + 1
    
    def test_increment_failure_nonexistent_skill(self, skill_memory):
        """Test that increment_failure raises error for nonexistent skill."""
        with pytest.raises(KeyError, match="not found"):
            skill_memory.increment_failure("nonexistent")


class TestSkillMemoryPersistence:
    """Tests for persistence and loading."""
    
    def test_load_from_existing_file(self, temp_storage_path, sample_skill):
        """Test loading skills from an existing file."""
        # Create and store skill
        memory1 = SkillMemory(storage_path=temp_storage_path)
        memory1.store(sample_skill)
        
        # Create new instance and verify it loads
        memory2 = SkillMemory(storage_path=temp_storage_path)
        retrieved = memory2.get_by_id("skill_001")
        
        assert retrieved is not None
        assert retrieved.skill_name == "Open GED Document"
    
    def test_load_nonexistent_file(self, temp_storage_path):
        """Test that loading from nonexistent file initializes empty."""
        memory = SkillMemory(storage_path=temp_storage_path)
        
        assert memory.count() == 0
    
    def test_load_corrupted_file(self, temp_storage_path):
        """Test that loading from corrupted file initializes empty."""
        # Create corrupted file
        with open(temp_storage_path, 'w') as f:
            f.write("not valid json{{{")
        
        memory = SkillMemory(storage_path=temp_storage_path)
        
        assert memory.count() == 0


class TestSkillMemoryUtilityMethods:
    """Tests for utility methods."""
    
    def test_get_by_id(self, skill_memory, sample_skill):
        """Test get_by_id method."""
        skill_memory.store(sample_skill)
        
        retrieved = skill_memory.get_by_id("skill_001")
        
        assert retrieved is not None
        assert retrieved.skill_id == "skill_001"
    
    def test_get_by_id_not_found(self, skill_memory):
        """Test get_by_id returns None for nonexistent skill."""
        retrieved = skill_memory.get_by_id("nonexistent")
        
        assert retrieved is None
    
    def test_list_all(self, skill_memory, sample_skill, skill_candidate, raw_shadow_skill):
        """Test list_all returns all skills."""
        skill_memory.store(sample_skill)
        skill_memory.store(skill_candidate)
        skill_memory.store(raw_shadow_skill)
        
        all_skills = skill_memory.list_all()
        
        assert len(all_skills) == 3
    
    def test_count(self, skill_memory, sample_skill, skill_candidate):
        """Test count method."""
        assert skill_memory.count() == 0
        
        skill_memory.store(sample_skill)
        assert skill_memory.count() == 1
        
        skill_memory.store(skill_candidate)
        assert skill_memory.count() == 2
    
    def test_count_by_promotion_state(self, skill_memory, sample_skill, skill_candidate, raw_shadow_skill):
        """Test count_by_promotion_state method."""
        skill_memory.store(sample_skill)
        skill_memory.store(skill_candidate)
        skill_memory.store(raw_shadow_skill)
        
        assert skill_memory.count_by_promotion_state('promoted_skill') == 1
        assert skill_memory.count_by_promotion_state('skill_candidate') == 1
        assert skill_memory.count_by_promotion_state('raw_shadow') == 1
        assert skill_memory.count_by_promotion_state('reviewed_shadow') == 0

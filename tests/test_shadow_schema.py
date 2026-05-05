"""
tests/test_shadow_schema.py — Tests for shadow_schema.py
=========================================================
Tests the three-layer shadow schema data model and validation logic.
"""

import pytest

from shadow_schema import (
    BUSINESS_ENTITIES,
    COMPONENT_FAMILIES,
    CONFIDENCE_LEVELS,
    PATTERNS_DETECTADO,
    SCREEN_FAMILIES,
    SEMANTIC_ACTIONS,
    Shadow_Schema_Validator,
)


def test_controlled_vocabularies():
    """Test that controlled vocabularies are defined correctly."""
    assert "fill" in SEMANTIC_ACTIONS
    assert "search" in SEMANTIC_ACTIONS
    assert "confirm" in SEMANTIC_ACTIONS

    assert "pasta" in BUSINESS_ENTITIES
    assert "documento" in BUSINESS_ENTITIES

    assert "menu_navigation" in PATTERNS_DETECTADO
    assert "form_fill" in PATTERNS_DETECTADO

    assert "ged_list" in SCREEN_FAMILIES
    assert "ged_form" in SCREEN_FAMILIES

    assert "toolbar_button" in COMPONENT_FAMILIES
    assert "form_input" in COMPONENT_FAMILIES

    assert "alta" in CONFIDENCE_LEVELS
    assert "media" in CONFIDENCE_LEVELS
    assert "baixa" in CONFIDENCE_LEVELS


def test_validate_layer_a_valid():
    """Test Layer A validation with valid event."""
    validator = Shadow_Schema_Validator()

    event = {
        "id_acao": 1,
        "captured_at": "2024-01-15T10:30:00Z",
        "acao": "clique",
        "capture_scope": "shell",
        "seletor_hint": "[aria-label='GED']",
        "iframe_hint": None,
        "html_hint": "<a>GED</a>",
        "coordenadas_relativas": {
            "x_pct": 0.5,
            "y_pct": 0.5,
            "w_pct": 0.1,
            "h_pct": 0.1
        },
        "screenshot_referencia": None,
        "valor_input": "",
        "page_title": "Senior X",
        "url_hint": "https://platform.senior.com.br"
    }

    assert validator.validate_layer_a(event) is True
    assert len(validator.get_validation_errors()) == 0


def test_validate_layer_a_missing_id_acao():
    """Test Layer A validation with missing id_acao."""
    validator = Shadow_Schema_Validator()

    event = {
        "captured_at": "2024-01-15T10:30:00Z",
        "acao": "clique",
        "capture_scope": "shell",
        "seletor_hint": "[aria-label='GED']",
        "iframe_hint": None,
        "html_hint": "<a>GED</a>",
        "coordenadas_relativas": {
            "x_pct": 0.5,
            "y_pct": 0.5,
            "w_pct": 0.1,
            "h_pct": 0.1
        },
        "screenshot_referencia": None,
        "valor_input": "",
        "page_title": "Senior X",
        "url_hint": "https://platform.senior.com.br"
    }

    assert validator.validate_layer_a(event) is False
    assert "Missing required field: id_acao" in validator.get_validation_errors()


def test_validate_layer_a_invalid_capture_scope():
    """Test Layer A validation with invalid capture_scope."""
    validator = Shadow_Schema_Validator()

    event = {
        "id_acao": 1,
        "captured_at": "2024-01-15T10:30:00Z",
        "acao": "clique",
        "capture_scope": "invalid_scope",
        "seletor_hint": "[aria-label='GED']",
        "iframe_hint": None,
        "html_hint": "<a>GED</a>",
        "coordenadas_relativas": {
            "x_pct": 0.5,
            "y_pct": 0.5,
            "w_pct": 0.1,
            "h_pct": 0.1
        },
        "screenshot_referencia": None,
        "valor_input": "",
        "page_title": "Senior X",
        "url_hint": "https://platform.senior.com.br"
    }

    assert validator.validate_layer_a(event) is False
    assert "capture_scope must be 'shell' or 'module_iframe'" in validator.get_validation_errors()


def test_validate_layer_b_valid():
    """Test Layer B validation with valid event."""
    validator = Shadow_Schema_Validator()

    event = {
        "semantic_action": "fill",
        "business_entity": "campo",
        "business_target": "Nome do usuário",
        "pattern_detectado": "form_fill",
        "intencao_semantica": "Preencher campo de nome",
        "screen_family": "ged_form",
        "component_family": "form_input",
        "expected_effect": "Campo preenchido com o valor correto"
    }

    assert validator.validate_layer_b(event) is True
    assert len(validator.get_validation_errors()) == 0


def test_validate_layer_b_invalid_semantic_action():
    """Test Layer B validation with invalid semantic_action."""
    validator = Shadow_Schema_Validator()

    event = {
        "semantic_action": "invalid_action",
        "business_entity": "campo",
        "business_target": "Nome do usuário",
        "pattern_detectado": "form_fill",
        "intencao_semantica": "Preencher campo de nome",
        "screen_family": "ged_form",
        "component_family": "form_input",
        "expected_effect": "Campo preenchido com o valor correto"
    }

    assert validator.validate_layer_b(event) is False
    assert "semantic_action 'invalid_action' not in controlled vocabulary" in validator.get_validation_errors()


def test_validate_layer_c_valid():
    """Test Layer C validation with valid event."""
    validator = Shadow_Schema_Validator()

    event = {
        "confianca_captura": "alta",
        "is_noise": False,
        "missing_signals": [],
        "observed_effect": None,
        "promotion_readiness": True,
        "review_required": False
    }

    assert validator.validate_layer_c(event) is True
    assert len(validator.get_validation_errors()) == 0


def test_validate_layer_c_invalid_confianca():
    """Test Layer C validation with invalid confianca_captura."""
    validator = Shadow_Schema_Validator()

    event = {
        "confianca_captura": "invalid_level",
        "is_noise": False,
        "missing_signals": [],
        "observed_effect": None,
        "promotion_readiness": True,
        "review_required": False
    }

    assert validator.validate_layer_c(event) is False
    assert "confianca_captura 'invalid_level' not in controlled vocabulary" in validator.get_validation_errors()


def test_compute_promotion_readiness_ready():
    """Test promotion readiness computation for ready event."""
    validator = Shadow_Schema_Validator()

    event = {
        "screen_family": "ged_form",
        "component_family": "form_input",
        "is_noise": False,
        "confianca_captura": "alta",
        "intencao_semantica": "Preencher campo de nome"
    }

    assert validator.compute_promotion_readiness(event) is True


def test_compute_promotion_readiness_not_ready_noise():
    """Test promotion readiness computation for noisy event."""
    validator = Shadow_Schema_Validator()

    event = {
        "screen_family": "ged_form",
        "component_family": "form_input",
        "is_noise": True,
        "confianca_captura": "alta",
        "intencao_semantica": "Preencher campo de nome"
    }

    assert validator.compute_promotion_readiness(event) is False


def test_compute_promotion_readiness_not_ready_unknown_screen():
    """Test promotion readiness computation for unknown screen_family."""
    validator = Shadow_Schema_Validator()

    event = {
        "screen_family": "unknown",
        "component_family": "form_input",
        "is_noise": False,
        "confianca_captura": "alta",
        "intencao_semantica": "Preencher campo de nome"
    }

    assert validator.compute_promotion_readiness(event) is False


def test_compute_promotion_readiness_not_ready_low_confidence():
    """Test promotion readiness computation for low confidence."""
    validator = Shadow_Schema_Validator()

    event = {
        "screen_family": "ged_form",
        "component_family": "form_input",
        "is_noise": False,
        "confianca_captura": "baixa",
        "intencao_semantica": "Preencher campo de nome"
    }

    assert validator.compute_promotion_readiness(event) is False


def test_compute_missing_signals_none():
    """Test missing signals computation with no missing fields."""
    validator = Shadow_Schema_Validator()

    event = {
        "semantic_action": "fill",
        "business_entity": "campo",
        "business_target": "Nome do usuário",
        "pattern_detectado": "form_fill",
        "intencao_semantica": "Preencher campo de nome",
        "screen_family": "ged_form",
        "component_family": "form_input",
        "expected_effect": "Campo preenchido com o valor correto"
    }

    missing = validator.compute_missing_signals(event)
    assert len(missing) == 0


def test_compute_missing_signals_some():
    """Test missing signals computation with some missing fields."""
    validator = Shadow_Schema_Validator()

    event = {
        "semantic_action": "fill",
        "business_entity": "",
        "business_target": "Nome do usuário",
        "pattern_detectado": "unknown",
        "intencao_semantica": "Preencher campo de nome",
        "screen_family": "ged_form",
        "component_family": "form_input",
        "expected_effect": "Campo preenchido com o valor correto"
    }

    missing = validator.compute_missing_signals(event)
    assert "business_entity" in missing
    assert "pattern_detectado" in missing
    assert len(missing) == 2


def test_validate_full_event_valid():
    """Test full event validation with valid event."""
    validator = Shadow_Schema_Validator()

    event = {
        # Layer A
        "id_acao": 1,
        "captured_at": "2024-01-15T10:30:00Z",
        "acao": "clique",
        "capture_scope": "shell",
        "seletor_hint": "[aria-label='GED']",
        "iframe_hint": None,
        "html_hint": "<a>GED</a>",
        "coordenadas_relativas": {
            "x_pct": 0.5,
            "y_pct": 0.5,
            "w_pct": 0.1,
            "h_pct": 0.1
        },
        "screenshot_referencia": None,
        "valor_input": "",
        "page_title": "Senior X",
        "url_hint": "https://platform.senior.com.br",

        # Layer B
        "semantic_action": "fill",
        "business_entity": "campo",
        "business_target": "Nome do usuário",
        "pattern_detectado": "form_fill",
        "intencao_semantica": "Preencher campo de nome",
        "screen_family": "ged_form",
        "component_family": "form_input",
        "expected_effect": "Campo preenchido com o valor correto",

        # Layer C
        "confianca_captura": "alta",
        "is_noise": False,
        "missing_signals": [],
        "observed_effect": None,
        "promotion_readiness": True,
        "review_required": False
    }

    assert validator.validate_full_event(event) is True
    assert len(validator.get_validation_errors()) == 0

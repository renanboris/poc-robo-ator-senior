"""
shadow_schema.py — Senior Training OS · Canonical Shadow Schema
================================================================
Defines the three-layer shadow schema data model and validation logic.

This module provides:
  - Layer A: Raw observation fields
  - Layer B: Interpretation fields
  - Layer C: Quality evidence fields
  - Controlled vocabularies for semantic fields
  - Shadow_Schema_Validator class for validation

Layers:
  Layer A (Raw Observation): What happened, where, how it was seen
  Layer B (Interpretation): Semantic meaning, goal, entity, pattern
  Layer C (Quality Evidence): Confidence, noise, missing signals, promotion readiness
"""

import logging
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass
from datetime import datetime

# Configure logger for shadow schema validation
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# CONTROLLED VOCABULARIES
# ──────────────────────────────────────────────────────────────

# Semantic actions (Layer B)
SEMANTIC_ACTIONS: Set[str] = {
    "fill",
    "search",
    "confirm",
    "delete",
    "save",
    "open",
    "navigate",
    "select",
    "close"
}

# Business entities (Layer B)
BUSINESS_ENTITIES: Set[str] = {
    "pasta",
    "documento",
    "campo",
    "menu",
    "selecao",
    "elemento",
    "cliente",
    "pedido"
}

# Interaction patterns (Layer B)
PATTERNS_DETECTADO: Set[str] = {
    "menu_navigation",
    "form_fill",
    "button_click",
    "table_selection",
    "breadcrumb_navigation",
    "toolbar_action",
    "modal_action",
    "tree_item_open",
    "search_debounce",
    "unknown"
}

# Screen families (Layer B)
SCREEN_FAMILIES: Set[str] = {
    "ged_list",
    "ged_form",
    "ged_tree",
    "sign_inbox",
    "sign_envelope",
    "erp_form",
    "erp_list",
    "modal_confirm",
    "modal_form",
    "shell_navigation",
    "unknown"
}

# Component families (Layer B)
COMPONENT_FAMILIES: Set[str] = {
    "toolbar_button",
    "context_menu_item",
    "tree_node",
    "form_input",
    "checkbox_row",
    "table_row",
    "modal_button",
    "unknown"
}

# Confidence levels (Layer C)
CONFIDENCE_LEVELS: Set[str] = {
    "alta",
    "media",
    "baixa"
}


# ──────────────────────────────────────────────────────────────
# LAYER DEFINITIONS
# ──────────────────────────────────────────────────────────────

@dataclass
class LayerA:
    """
    Layer A: Raw Observation
    Fields captured directly from user interaction without interpretation.
    """
    # Required fields
    id_acao: int
    captured_at: str  # ISO 8601 timestamp
    acao: str
    capture_scope: str  # "shell" or "module_iframe"
    
    # Element identification
    seletor_hint: str
    iframe_hint: Optional[str]
    html_hint: str
    
    # Position and context
    coordenadas_relativas: Dict[str, float]  # {x_pct, y_pct, w_pct, h_pct}
    screenshot_referencia: Optional[str]  # Base64 screenshot
    
    # Input data
    valor_input: str
    
    # Page context
    page_title: str
    url_hint: str


@dataclass
class LayerB:
    """
    Layer B: Interpretation
    Fields derived from semantic analysis and pattern recognition.
    """
    # Semantic classification
    semantic_action: str  # From SEMANTIC_ACTIONS vocabulary
    business_entity: str  # From BUSINESS_ENTITIES vocabulary
    business_target: str  # Label/description of target element
    
    # Pattern and intent
    pattern_detectado: str  # From PATTERNS_DETECTADO vocabulary
    intencao_semantica: str  # Human-readable intent
    
    # Screen classification
    screen_family: str  # From SCREEN_FAMILIES vocabulary
    component_family: str  # From COMPONENT_FAMILIES vocabulary
    
    # Expected outcome
    expected_effect: str  # What should change


@dataclass
class LayerC:
    """
    Layer C: Quality Evidence
    Fields indicating confidence, noise, and promotion readiness.
    """
    # Confidence indicators
    confianca_captura: str  # From CONFIDENCE_LEVELS vocabulary
    is_noise: bool
    
    # Quality signals
    missing_signals: List[str]  # List of missing Layer B fields
    observed_effect: Optional[str]  # What actually changed (inferred from screenshot delta)
    
    # Promotion readiness
    promotion_readiness: bool  # True if ready for Level 1 promotion
    review_required: bool  # True if human review needed


# ──────────────────────────────────────────────────────────────
# VALIDATOR
# ──────────────────────────────────────────────────────────────

class Shadow_Schema_Validator:
    """
    Validates shadow events against the canonical three-layer schema.
    
    Validation rules:
      - Layer A: All required fields must be present and non-empty
      - Layer B: Fields must use controlled vocabularies
      - Layer C: Confidence and quality indicators must be valid
    """
    
    def __init__(self):
        self.validation_errors: List[str] = []
    
    def validate_layer_a(self, event: Dict[str, Any]) -> bool:
        """
        Validates Layer A (raw observation) fields.
        
        Required fields:
          - id_acao (int)
          - captured_at (ISO 8601 string)
          - acao (non-empty string)
          - capture_scope ("shell" or "module_iframe")
          - seletor_hint (non-empty string)
          - html_hint (non-empty string)
          - coordenadas_relativas (dict with x_pct, y_pct, w_pct, h_pct)
          - valor_input (string, can be empty)
          - page_title (non-empty string)
          - url_hint (non-empty string)
        
        Returns:
            True if all Layer A validations pass, False otherwise
        """
        self.validation_errors = []
        event_id = event.get("id_acao", "unknown")
        missing_fields = []
        
        # Check id_acao
        if "id_acao" not in event:
            self.validation_errors.append("Missing required field: id_acao")
            missing_fields.append("id_acao")
        elif not isinstance(event["id_acao"], int):
            self.validation_errors.append("id_acao must be an integer")
        
        # Check captured_at
        if "captured_at" not in event:
            self.validation_errors.append("Missing required field: captured_at")
            missing_fields.append("captured_at")
        elif not event["captured_at"]:
            self.validation_errors.append("captured_at cannot be empty")
        else:
            # Validate ISO 8601 format
            try:
                datetime.fromisoformat(event["captured_at"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                self.validation_errors.append("captured_at must be valid ISO 8601 timestamp")
        
        # Check acao
        if "acao" not in event:
            self.validation_errors.append("Missing required field: acao")
            missing_fields.append("acao")
        elif not event["acao"]:
            self.validation_errors.append("acao cannot be empty")
        
        # Check capture_scope
        if "capture_scope" not in event:
            self.validation_errors.append("Missing required field: capture_scope")
            missing_fields.append("capture_scope")
        elif event.get("capture_scope") not in {"shell", "module_iframe"}:
            self.validation_errors.append("capture_scope must be 'shell' or 'module_iframe'")
        
        # Check seletor_hint
        if "seletor_hint" not in event:
            self.validation_errors.append("Missing required field: seletor_hint")
            missing_fields.append("seletor_hint")
        elif not event["seletor_hint"]:
            self.validation_errors.append("seletor_hint cannot be empty")
        
        # Check html_hint
        if "html_hint" not in event:
            self.validation_errors.append("Missing required field: html_hint")
            missing_fields.append("html_hint")
        
        # Check coordenadas_relativas
        if "coordenadas_relativas" not in event:
            self.validation_errors.append("Missing required field: coordenadas_relativas")
            missing_fields.append("coordenadas_relativas")
        else:
            coords = event["coordenadas_relativas"]
            required_coords = {"x_pct", "y_pct", "w_pct", "h_pct"}
            if not isinstance(coords, dict):
                self.validation_errors.append("coordenadas_relativas must be a dict")
            elif not required_coords.issubset(coords.keys()):
                missing = required_coords - coords.keys()
                self.validation_errors.append(f"coordenadas_relativas missing keys: {missing}")
                missing_fields.extend([f"coordenadas_relativas.{k}" for k in missing])
        
        # Check valor_input (can be empty)
        if "valor_input" not in event:
            self.validation_errors.append("Missing required field: valor_input")
            missing_fields.append("valor_input")
        
        # Check page_title
        if "page_title" not in event:
            self.validation_errors.append("Missing required field: page_title")
            missing_fields.append("page_title")
        
        # Check url_hint
        if "url_hint" not in event:
            self.validation_errors.append("Missing required field: url_hint")
            missing_fields.append("url_hint")
        
        # Log validation failures with structured context
        if self.validation_errors:
            logger.warning(
                "Layer A validation failed",
                extra={
                    "event_id_acao": event_id,
                    "layer": "A",
                    "missing_fields": missing_fields,
                    "validation_errors": self.validation_errors
                }
            )
        
        return len(self.validation_errors) == 0
    
    def validate_layer_b(self, event: Dict[str, Any]) -> bool:
        """
        Validates Layer B (interpretation) fields.
        
        Required fields with controlled vocabularies:
          - semantic_action (from SEMANTIC_ACTIONS)
          - business_entity (from BUSINESS_ENTITIES)
          - business_target (non-empty string)
          - pattern_detectado (from PATTERNS_DETECTADO)
          - intencao_semantica (non-empty string)
          - screen_family (from SCREEN_FAMILIES)
          - component_family (from COMPONENT_FAMILIES)
          - expected_effect (non-empty string)
        
        Sets promotion_readiness based on field completeness.
        
        Returns:
            True if all Layer B validations pass, False otherwise
        """
        self.validation_errors = []
        event_id = event.get("id_acao", "unknown")
        missing_fields = []
        
        # Check semantic_action
        if "semantic_action" not in event:
            self.validation_errors.append("Missing required field: semantic_action")
            missing_fields.append("semantic_action")
        elif event["semantic_action"] not in SEMANTIC_ACTIONS:
            self.validation_errors.append(
                f"semantic_action '{event['semantic_action']}' not in controlled vocabulary"
            )
        
        # Check business_entity
        if "business_entity" not in event:
            self.validation_errors.append("Missing required field: business_entity")
            missing_fields.append("business_entity")
        elif event["business_entity"] not in BUSINESS_ENTITIES:
            self.validation_errors.append(
                f"business_entity '{event['business_entity']}' not in controlled vocabulary"
            )
        
        # Check business_target
        if "business_target" not in event:
            self.validation_errors.append("Missing required field: business_target")
            missing_fields.append("business_target")
        elif not event["business_target"]:
            self.validation_errors.append("business_target cannot be empty")
        
        # Check pattern_detectado
        if "pattern_detectado" not in event:
            self.validation_errors.append("Missing required field: pattern_detectado")
            missing_fields.append("pattern_detectado")
        elif event["pattern_detectado"] not in PATTERNS_DETECTADO:
            self.validation_errors.append(
                f"pattern_detectado '{event['pattern_detectado']}' not in controlled vocabulary"
            )
        
        # Check intencao_semantica
        if "intencao_semantica" not in event:
            self.validation_errors.append("Missing required field: intencao_semantica")
            missing_fields.append("intencao_semantica")
        elif not event["intencao_semantica"]:
            self.validation_errors.append("intencao_semantica cannot be empty")
        
        # Check screen_family
        if "screen_family" not in event:
            self.validation_errors.append("Missing required field: screen_family")
            missing_fields.append("screen_family")
        elif event["screen_family"] not in SCREEN_FAMILIES:
            self.validation_errors.append(
                f"screen_family '{event['screen_family']}' not in controlled vocabulary"
            )
        
        # Check component_family
        if "component_family" not in event:
            self.validation_errors.append("Missing required field: component_family")
            missing_fields.append("component_family")
        elif event["component_family"] not in COMPONENT_FAMILIES:
            self.validation_errors.append(
                f"component_family '{event['component_family']}' not in controlled vocabulary"
            )
        
        # Check expected_effect
        if "expected_effect" not in event:
            self.validation_errors.append("Missing required field: expected_effect")
            missing_fields.append("expected_effect")
        elif not event["expected_effect"]:
            self.validation_errors.append("expected_effect cannot be empty")
        
        # Compute and set promotion_readiness based on Layer B completeness
        promotion_readiness = self.compute_promotion_readiness(event)
        if "promotion_readiness" not in event:
            event["promotion_readiness"] = promotion_readiness
        
        # Log validation failures with structured context
        if self.validation_errors:
            logger.warning(
                "Layer B validation failed",
                extra={
                    "event_id_acao": event_id,
                    "layer": "B",
                    "missing_fields": missing_fields,
                    "validation_errors": self.validation_errors,
                    "promotion_readiness": promotion_readiness
                }
            )
        
        return len(self.validation_errors) == 0
    
    def validate_layer_c(self, event: Dict[str, Any]) -> bool:
        """
        Validates Layer C (quality evidence) fields.
        
        Required fields:
          - confianca_captura (from CONFIDENCE_LEVELS)
          - is_noise (boolean)
          - missing_signals (list of strings)
          - observed_effect (optional string)
          - promotion_readiness (boolean)
          - review_required (boolean)
        
        Returns:
            True if all Layer C validations pass, False otherwise
        """
        self.validation_errors = []
        event_id = event.get("id_acao", "unknown")
        missing_fields = []
        
        # Check confianca_captura
        if "confianca_captura" not in event:
            self.validation_errors.append("Missing required field: confianca_captura")
            missing_fields.append("confianca_captura")
        elif event["confianca_captura"] not in CONFIDENCE_LEVELS:
            self.validation_errors.append(
                f"confianca_captura '{event['confianca_captura']}' not in controlled vocabulary"
            )
        
        # Check is_noise
        if "is_noise" not in event:
            self.validation_errors.append("Missing required field: is_noise")
            missing_fields.append("is_noise")
        elif not isinstance(event["is_noise"], bool):
            self.validation_errors.append("is_noise must be a boolean")
        
        # Check missing_signals
        if "missing_signals" not in event:
            self.validation_errors.append("Missing required field: missing_signals")
            missing_fields.append("missing_signals")
        elif not isinstance(event["missing_signals"], list):
            self.validation_errors.append("missing_signals must be a list")
        
        # Check observed_effect (optional)
        if "observed_effect" in event and event["observed_effect"] is not None:
            if not isinstance(event["observed_effect"], str):
                self.validation_errors.append("observed_effect must be a string or None")
        
        # Check promotion_readiness
        if "promotion_readiness" not in event:
            self.validation_errors.append("Missing required field: promotion_readiness")
            missing_fields.append("promotion_readiness")
        elif not isinstance(event["promotion_readiness"], bool):
            self.validation_errors.append("promotion_readiness must be a boolean")
        
        # Check review_required
        if "review_required" not in event:
            self.validation_errors.append("Missing required field: review_required")
            missing_fields.append("review_required")
        elif not isinstance(event["review_required"], bool):
            self.validation_errors.append("review_required must be a boolean")
        
        # Log validation failures with structured context
        if self.validation_errors:
            logger.warning(
                "Layer C validation failed",
                extra={
                    "event_id_acao": event_id,
                    "layer": "C",
                    "missing_fields": missing_fields,
                    "validation_errors": self.validation_errors
                }
            )
        
        return len(self.validation_errors) == 0
    
    def validate_full_event(self, event: Dict[str, Any]) -> bool:
        """
        Validates a complete shadow event against all three layers.
        
        Args:
            event: Shadow event dictionary
        
        Returns:
            True if all validations pass, False otherwise
        """
        layer_a_valid = self.validate_layer_a(event)
        layer_b_valid = self.validate_layer_b(event)
        layer_c_valid = self.validate_layer_c(event)
        
        return layer_a_valid and layer_b_valid and layer_c_valid
    
    def compute_promotion_readiness(self, event: Dict[str, Any]) -> bool:
        """
        Computes promotion_readiness based on Layer B field completeness.
        
        Promotion readiness criteria:
          - Non-empty screen_family (not "unknown")
          - Non-empty component_family (not "unknown")
          - is_noise = false
          - confianca_captura in ['media', 'alta']
          - Non-empty intencao_semantica
        
        Args:
            event: Shadow event dictionary
        
        Returns:
            True if event is ready for Level 1 promotion, False otherwise
        """
        # Check screen_family
        screen_family = event.get("screen_family", "")
        if not screen_family or screen_family == "unknown":
            return False
        
        # Check component_family
        component_family = event.get("component_family", "")
        if not component_family or component_family == "unknown":
            return False
        
        # Check is_noise
        if event.get("is_noise", True):
            return False
        
        # Check confianca_captura
        confianca = event.get("confianca_captura", "")
        if confianca not in {"media", "alta"}:
            return False
        
        # Check intencao_semantica
        intencao = event.get("intencao_semantica", "")
        if not intencao:
            return False
        
        return True
    
    def compute_missing_signals(self, event: Dict[str, Any]) -> List[str]:
        """
        Computes list of missing Layer B fields.
        
        Args:
            event: Shadow event dictionary
        
        Returns:
            List of missing or empty Layer B field names
        """
        missing = []
        
        layer_b_fields = [
            "semantic_action",
            "business_entity",
            "business_target",
            "pattern_detectado",
            "intencao_semantica",
            "screen_family",
            "component_family",
            "expected_effect"
        ]
        
        for field in layer_b_fields:
            value = event.get(field, "")
            if not value or value == "unknown":
                missing.append(field)
        
        return missing
    
    def get_validation_errors(self) -> List[str]:
        """
        Returns the list of validation errors from the last validation.
        
        Returns:
            List of validation error messages
        """
        return self.validation_errors

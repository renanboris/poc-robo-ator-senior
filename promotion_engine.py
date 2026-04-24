"""
Promotion Gate Engine for the Next-Legacy Diamond Integration.

This module implements the four-level promotion gate system that classifies
shadow records and skill candidates by maturity level.

Promotion Levels:
- Level 0: raw_shadow (just ingested)
- Level 1: reviewed_shadow (sufficient context, low noise, plausible intent)
- Level 2: skill_candidate (clear pattern + semantic action)
- Level 3: promoted_skill (passes benchmark policy)

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""

import logging
from typing import Any, Dict, Tuple

from promotion_models import PromotionBenchmark

# Configure logger for promotion gate operations
logger = logging.getLogger(__name__)


class Promotion_Gate_Engine:
    """
    Implements the four-level promotion gate system defined in docs/PROMOTION_GATES.md.
    
    This engine evaluates shadow records and skill candidates to determine their
    maturity level and eligibility for promotion to higher levels.
    
    Levels:
    - Level 0: raw_shadow (just ingested)
    - Level 1: reviewed_shadow (sufficient context)
    - Level 2: skill_candidate (clear pattern + semantic action)
    - Level 3: promoted_skill (passes benchmark policy)
    """
    
    def __init__(self):
        """Initialize the Promotion Gate Engine."""
        self.benchmark = PromotionBenchmark()
    
    def evaluate_promotion_readiness(
        self, 
        shadow_record: Dict[str, Any]
    ) -> Tuple[int, str]:
        """
        Evaluates which promotion level a record qualifies for.
        
        This method checks the record against all promotion gate criteria
        and returns the highest level the record qualifies for.
        
        Args:
            shadow_record: Shadow event dict or ObservedAction dict with fields:
                - screen_family: str
                - component_family: str
                - is_noise: bool
                - confianca_captura: str
                - intencao_semantica: str
                - semantic_action: str (for Level 2)
                - business_entity: str (for Level 2)
                - pattern_detectado: str (for Level 2)
                
        Returns:
            tuple[int, str]: A tuple containing:
                - level: 0-3 indicating the promotion level
                - promotion_state: One of 'raw_shadow', 'reviewed_shadow', 
                  'skill_candidate', or 'promoted_skill'
        
        Example:
            >>> engine = Promotion_Gate_Engine()
            >>> level, state = engine.evaluate_promotion_readiness(shadow_event)
            >>> print(f"Record qualifies for Level {level}: {state}")
        """
        # Start at Level 0 (raw_shadow)
        level = 0
        promotion_state = "raw_shadow"
        
        # Check Level 0 → Level 1 criteria
        if self.promote_to_level_1(shadow_record):
            level = 1
            promotion_state = "reviewed_shadow"
            
            logger.debug(
                "Record promoted to Level 1",
                extra={
                    "event_id": shadow_record.get("id_acao", "unknown"),
                    "level": level,
                    "promotion_state": promotion_state
                }
            )
        else:
            logger.debug(
                "Record remains at Level 0",
                extra={
                    "event_id": shadow_record.get("id_acao", "unknown"),
                    "level": level,
                    "promotion_state": promotion_state
                }
            )
        
        # Note: Level 1 → Level 2 and Level 2 → Level 3 promotions
        # are implemented in promote_to_level_2() and promote_to_level_3()
        # which are called separately with additional context (history, benchmark)
        
        return level, promotion_state
    
    def promote_to_level_1(self, record: Dict[str, Any]) -> bool:
        """
        Evaluates Level 0 → Level 1 promotion criteria.
        
        Level 1 criteria (Requirement 3.3):
        - Non-empty screen_family (not "unknown")
        - Non-empty component_family (not "unknown")
        - is_noise = false
        - confianca_captura in ['media', 'alta']
        - Non-empty intencao_semantica
        
        Args:
            record: Shadow event dict with Layer B and Layer C fields
            
        Returns:
            bool: True if promotion succeeds, False otherwise
        
        Example:
            >>> engine = Promotion_Gate_Engine()
            >>> can_promote = engine.promote_to_level_1(shadow_event)
            >>> if can_promote:
            ...     print("Record is ready for Level 1")
        """
        event_id = record.get("id_acao", "unknown")
        
        # Criterion 1: Non-empty screen_family (not "unknown")
        screen_family = record.get("screen_family", "")
        if not screen_family or screen_family == "unknown":
            logger.debug(
                "Level 1 promotion failed: screen_family is empty or unknown",
                extra={
                    "event_id": event_id,
                    "screen_family": screen_family,
                    "criterion": "screen_family"
                }
            )
            return False
        
        # Criterion 2: Non-empty component_family (not "unknown")
        component_family = record.get("component_family", "")
        if not component_family or component_family == "unknown":
            logger.debug(
                "Level 1 promotion failed: component_family is empty or unknown",
                extra={
                    "event_id": event_id,
                    "component_family": component_family,
                    "criterion": "component_family"
                }
            )
            return False
        
        # Criterion 3: is_noise = false
        is_noise = record.get("is_noise", True)
        if is_noise:
            logger.debug(
                "Level 1 promotion failed: is_noise is true",
                extra={
                    "event_id": event_id,
                    "is_noise": is_noise,
                    "criterion": "is_noise"
                }
            )
            return False
        
        # Criterion 4: confianca_captura in ['media', 'alta']
        confianca_captura = record.get("confianca_captura", "")
        if confianca_captura not in {"media", "alta"}:
            logger.debug(
                "Level 1 promotion failed: confianca_captura not in ['media', 'alta']",
                extra={
                    "event_id": event_id,
                    "confianca_captura": confianca_captura,
                    "criterion": "confianca_captura"
                }
            )
            return False
        
        # Criterion 5: Non-empty intencao_semantica
        intencao_semantica = record.get("intencao_semantica", "")
        if not intencao_semantica:
            logger.debug(
                "Level 1 promotion failed: intencao_semantica is empty",
                extra={
                    "event_id": event_id,
                    "intencao_semantica": intencao_semantica,
                    "criterion": "intencao_semantica"
                }
            )
            return False
        
        # All criteria passed
        logger.info(
            "Level 1 promotion criteria met",
            extra={
                "event_id": event_id,
                "screen_family": screen_family,
                "component_family": component_family,
                "confianca_captura": confianca_captura
            }
        )
        return True
    
    def promote_to_level_2(
        self, 
        record: Dict[str, Any], 
        history: list[Dict[str, Any]]
    ) -> bool:
        """
        Evaluates Level 1 → Level 2 promotion criteria.
        
        Level 2 criteria (Requirement 3.4):
        - Clear semantic_action (not 'navigate' or 'unknown')
        - Non-empty business_entity
        - Non-empty screen_family
        - At least 2 occurrences of same pattern_detectado for same business_target
        
        Args:
            record: Current shadow record at Level 1
            history: Historical records for pattern frequency analysis
            
        Returns:
            bool: True if promotion succeeds, False otherwise
        
        Example:
            >>> engine = Promotion_Gate_Engine()
            >>> can_promote = engine.promote_to_level_2(record, history)
            >>> if can_promote:
            ...     print("Record is ready for Level 2")
        """
        event_id = record.get("id_acao", "unknown")
        
        # Criterion 1: Clear semantic_action (not 'navigate' or 'unknown')
        semantic_action = record.get("semantic_action", "")
        if not semantic_action or semantic_action in {"navigate", "unknown"}:
            logger.debug(
                "Level 2 promotion failed: semantic_action is unclear",
                extra={
                    "event_id": event_id,
                    "semantic_action": semantic_action,
                    "criterion": "semantic_action"
                }
            )
            return False
        
        # Criterion 2: Non-empty business_entity
        business_entity = record.get("business_entity", "")
        if not business_entity:
            logger.debug(
                "Level 2 promotion failed: business_entity is empty",
                extra={
                    "event_id": event_id,
                    "business_entity": business_entity,
                    "criterion": "business_entity"
                }
            )
            return False
        
        # Criterion 3: Non-empty screen_family
        screen_family = record.get("screen_family", "")
        if not screen_family or screen_family == "unknown":
            logger.debug(
                "Level 2 promotion failed: screen_family is empty or unknown",
                extra={
                    "event_id": event_id,
                    "screen_family": screen_family,
                    "criterion": "screen_family"
                }
            )
            return False
        
        # Criterion 4: At least 2 occurrences of same pattern_detectado for same business_target
        pattern_detectado = record.get("pattern_detectado", "")
        business_target = record.get("business_target", "")
        
        if not pattern_detectado or not business_target:
            logger.debug(
                "Level 2 promotion failed: pattern_detectado or business_target is empty",
                extra={
                    "event_id": event_id,
                    "pattern_detectado": pattern_detectado,
                    "business_target": business_target,
                    "criterion": "pattern_frequency"
                }
            )
            return False
        
        # Count occurrences of same pattern + business_target in history
        matching_count = sum(
            1 for hist_record in history
            if (hist_record.get("pattern_detectado") == pattern_detectado and
                hist_record.get("business_target") == business_target)
        )
        
        # Include current record in count
        matching_count += 1
        
        if matching_count < 2:
            logger.debug(
                "Level 2 promotion failed: insufficient pattern frequency",
                extra={
                    "event_id": event_id,
                    "pattern_detectado": pattern_detectado,
                    "business_target": business_target,
                    "matching_count": matching_count,
                    "criterion": "pattern_frequency"
                }
            )
            return False
        
        # All criteria passed
        logger.info(
            "Level 2 promotion criteria met",
            extra={
                "event_id": event_id,
                "semantic_action": semantic_action,
                "business_entity": business_entity,
                "pattern_detectado": pattern_detectado,
                "matching_count": matching_count
            }
        )
        return True
    
    def promote_to_level_3(
        self, 
        skill_candidate: Any, 
        benchmark: PromotionBenchmark | None = None
    ) -> bool:
        """
        Evaluates Level 2 → Level 3 promotion criteria.
        
        Level 3 criteria (from Promotion_Benchmark, Requirement 3.5):
        - Success rate >= 70%
        - Semantic target consistency across >= 3 events
        - Pattern stability >= 80%
        - Average confidence >= 0.6
        - Post-HITL correction rate < 20% (if HITL performed)
        - Expected/observed effect coherence >= 60%
        
        This method delegates to PromotionBenchmark.evaluate() for the actual
        evaluation logic.
        
        Args:
            skill_candidate: KnownSkill object at Level 2
            benchmark: Optional PromotionBenchmark instance (uses default if None)
            
        Returns:
            bool: True if promotion succeeds, False otherwise
        
        Example:
            >>> engine = Promotion_Gate_Engine()
            >>> can_promote = engine.promote_to_level_3(skill_candidate)
            >>> if can_promote:
            ...     print("Skill is ready for Level 3")
        """
        if benchmark is None:
            benchmark = self.benchmark
        
        skill_id = getattr(skill_candidate, 'skill_id', 'unknown')
        
        # Delegate to PromotionBenchmark for evaluation
        passes, failing_criteria = benchmark.evaluate(skill_candidate)
        
        if passes:
            logger.info(
                "Level 3 promotion criteria met",
                extra={
                    "skill_id": skill_id,
                    "promotion_state": "promoted_skill"
                }
            )
        else:
            logger.debug(
                "Level 3 promotion failed",
                extra={
                    "skill_id": skill_id,
                    "failing_criteria": failing_criteria
                }
            )
        
        return passes
    
    def record_gate_failure(
        self, 
        record: Dict[str, Any], 
        level: int, 
        reason: str
    ) -> None:
        """
        Records specific failing criterion in gate_failure_reason field.
        
        This method mutates the record dict to add a gate_failure_reason field
        that captures which criterion failed during promotion evaluation.
        
        Args:
            record: Shadow record or skill candidate dict
            level: Target promotion level that failed (1, 2, or 3)
            reason: Specific criterion that failed (e.g., "screen_family", 
                   "pattern_frequency", "min_success_rate")
        
        Example:
            >>> engine = Promotion_Gate_Engine()
            >>> engine.record_gate_failure(record, 1, "screen_family")
            >>> print(record['gate_failure_reason'])
            'Level 1: screen_family'
        """
        gate_failure_reason = f"Level {level}: {reason}"
        record["gate_failure_reason"] = gate_failure_reason
        
        event_id = record.get("id_acao") or record.get("skill_id", "unknown")
        
        logger.warning(
            "Promotion gate failure recorded",
            extra={
                "event_id": event_id,
                "target_level": level,
                "failing_criterion": reason,
                "gate_failure_reason": gate_failure_reason
            }
        )

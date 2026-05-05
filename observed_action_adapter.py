"""
observed_action_adapter.py — Senior Training OS · ObservedAction Adapter
=========================================================================
Converts a Legacy dual-capture shadow event (dict) into a fully-populated
ObservedAction contract.

Field mapping (shadow JSONL → ObservedAction):
  elemento_alvo.seletor_hint          → raw_target.selector
  elemento_alvo.iframe_hint           → raw_target.iframe_hint
  elemento_alvo.html_hint             → raw_target.html_hint  + artifacts["html_hint"]
  elemento_alvo.coordenadas_relativas → raw_target.coords     + artifacts["coords"]
  elemento_alvo.screenshot_referencia → screen_before
  valor_input                         → raw_target.valor_input
  confianca_captura                   → confidence  (alta→0.9, media→0.6, baixa→0.3)
  is_noise=True                       → confidence=0.1, review_required=True
  id_acao + source_file + captured_at → provenance
  validacao_esperada.alvo             → expected_effect
  (screenshot delta inference)        → observed_effect

Requirements: 6.1–6.8, 8.2, 8.4
"""

import logging
from typing import Optional

from observed_action_models import ObservedAction, Provenance, RawTarget

logger = logging.getLogger(__name__)

# Confidence mapping from Legacy vocabulary to normalised float
_CONFIDENCE_MAP: dict[str, float] = {
    "alta": 0.9,
    "media": 0.6,
    "baixa": 0.3,
}
_NOISE_CONFIDENCE = 0.1


class ObservedAction_Adapter:
    """
    Converts a Legacy shadow event dict into an ObservedAction.

    Usage::

        adapter = ObservedAction_Adapter()
        obs = adapter.adapt(shadow_event, source_file="shadow_exports/foo.jsonl")
    """

    def adapt(
        self,
        shadow_event: dict,
        source_file: str = "",
    ) -> ObservedAction:
        """
        Map a shadow event dict to an ObservedAction.

        Args:
            shadow_event: A single event dict produced by shadow_builder.py.
            source_file:  Path to the originating JSONL file (for provenance).

        Returns:
            A fully-populated ObservedAction instance.
        """
        elem = shadow_event.get("elemento_alvo", {})
        validacao = shadow_event.get("validacao_esperada", {})
        is_noise: bool = bool(shadow_event.get("is_noise", False))

        # ── Raw target ────────────────────────────────────────
        raw_target = RawTarget(
            selector=elem.get("seletor_hint", ""),
            iframe_hint=elem.get("iframe_hint"),
            html_hint=elem.get("html_hint", ""),
            coords=elem.get("coordenadas_relativas", {}),
            valor_input=shadow_event.get("valor_input", ""),
        )

        # ── Confidence ────────────────────────────────────────
        confidence, review_required = self._map_confidence(
            shadow_event.get("confianca_captura", "baixa"),
            is_noise,
        )

        # ── Expected / observed effect ────────────────────────
        expected_effect: str = (
            validacao.get("alvo", "")
            or shadow_event.get("expected_effect", "")
        )
        observed_effect: Optional[str] = self._infer_observed_effect(
            shadow_event, expected_effect
        )
        if observed_effect is None:
            review_required = True

        # ── State change ──────────────────────────────────────
        state_change = self._infer_state_change(expected_effect, observed_effect)

        # ── Artifacts ─────────────────────────────────────────
        artifacts: dict = {}
        if elem.get("html_hint"):
            artifacts["html_hint"] = elem["html_hint"]
        if elem.get("coordenadas_relativas"):
            artifacts["coords"] = elem["coordenadas_relativas"]

        # ── Provenance ────────────────────────────────────────
        provenance = Provenance(
            original_event_id=shadow_event.get("id_acao", 0),
            source_file=source_file,
            captured_at=shadow_event.get("captured_at", ""),
        )

        obs = ObservedAction(
            action_id=shadow_event.get("id_acao", 0),
            action_type=shadow_event.get("acao", ""),
            raw_target=raw_target,
            screen_before=elem.get("screenshot_referencia"),
            state_change=state_change,
            artifacts=artifacts,
            confidence=confidence,
            is_noise=is_noise,
            review_required=review_required,
            screen_family=shadow_event.get("screen_family", "unknown"),
            component_family=shadow_event.get("component_family", "unknown"),
            pattern=shadow_event.get("pattern_detectado", "unknown"),
            business_entity=shadow_event.get("business_entity", ""),
            business_target=shadow_event.get("business_target", ""),
            semantic_action=shadow_event.get("semantic_action", ""),
            intencao_semantica=shadow_event.get("intencao_semantica", ""),
            expected_effect=expected_effect,
            observed_effect=observed_effect,
            provenance=provenance,
        )

        logger.debug(
            "ObservedAction adapted",
            extra={
                "action_id": obs.action_id,
                "confidence": obs.confidence,
                "is_noise": obs.is_noise,
                "review_required": obs.review_required,
                "screen_family": obs.screen_family,
            },
        )
        return obs

    # ──────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────

    def _map_confidence(
        self,
        confianca_captura: str,
        is_noise: bool,
    ) -> tuple[float, bool]:
        """
        Map Legacy confidence vocabulary to a normalised float.

        Special case: if is_noise is True, confidence is forced to 0.1 and
        review_required is set to True regardless of confianca_captura.

        Returns:
            (confidence: float, review_required: bool)
        """
        if is_noise:
            return _NOISE_CONFIDENCE, True

        confidence = _CONFIDENCE_MAP.get(confianca_captura, _CONFIDENCE_MAP["baixa"])
        return confidence, False

    def _infer_observed_effect(
        self,
        shadow_event: dict,
        expected_effect: str,
    ) -> Optional[str]:
        """
        Attempt to infer observed_effect from the shadow event.

        Strategy:
        1. Use explicit observed_effect field if present.
        2. If a screenshot_referencia exists, return a placeholder indicating
           that visual inference is needed (downstream vision engine handles it).
        3. Otherwise return None (triggers review_required).

        Args:
            shadow_event:    The raw shadow event dict.
            expected_effect: The expected effect string for context.

        Returns:
            Inferred observed_effect string, or None if inference is not possible.
        """
        # Explicit field takes priority
        explicit = shadow_event.get("observed_effect")
        if explicit:
            return str(explicit)

        # Screenshot available — mark for visual inference
        elem = shadow_event.get("elemento_alvo", {})
        screenshot = elem.get("screenshot_referencia")
        if screenshot:
            # Return a sentinel that downstream vision can replace
            return f"__pending_visual_inference__:{expected_effect}"

        return None

    def _infer_state_change(
        self,
        expected_effect: Optional[str],
        observed_effect: Optional[str],
    ) -> Optional[str]:
        """
        Derive a state_change description from the effect axis.

        If both effects are present and non-pending, returns a delta string.
        Otherwise returns None.

        Args:
            expected_effect: What was expected to change.
            observed_effect: What actually changed.

        Returns:
            State change description string, or None.
        """
        if not expected_effect or not observed_effect:
            return None

        if observed_effect.startswith("__pending_visual_inference__"):
            return None

        if expected_effect.lower() == observed_effect.lower():
            return f"confirmed: {observed_effect}"

        return f"expected='{expected_effect}' | observed='{observed_effect}'"

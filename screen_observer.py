"""
screen_observer.py — Senior Training OS · ScreenObserver
=========================================================
Classifies screens and UI components into controlled-vocabulary families
so that LegacyBridge and SkillMemory can use screen_family and
component_family as reliable retrieval and promotion signals.

Requirements: 11.1–11.4
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Controlled vocabularies
# ──────────────────────────────────────────────────────────────

SCREEN_FAMILIES: set[str] = {
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
    "unknown",
}

COMPONENT_FAMILIES: set[str] = {
    "toolbar_button",
    "context_menu_item",
    "tree_node",
    "form_input",
    "checkbox_row",
    "table_row",
    "modal_button",
    "unknown",
}

# ──────────────────────────────────────────────────────────────
# Heuristic rules
# ──────────────────────────────────────────────────────────────

# (pattern_in_title_or_url, screen_family)  — first match wins
_SCREEN_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ged.*list|lista.*ged|documentos.*lista", re.I), "ged_list"),
    (re.compile(r"ged.*form|formulario.*ged|novo.*documento|editar.*documento", re.I), "ged_form"),
    (re.compile(r"ged.*tree|arvore.*ged|pastas", re.I), "ged_tree"),
    (re.compile(r"sign.*inbox|caixa.*entrada.*assinatura|assinaturas.*pendentes", re.I), "sign_inbox"),
    (re.compile(r"sign.*envelope|envelope.*assinatura", re.I), "sign_envelope"),
    (re.compile(r"erp.*form|formulario.*erp|cadastro|manutencao", re.I), "erp_form"),
    (re.compile(r"erp.*list|lista.*erp|consulta", re.I), "erp_list"),
    (re.compile(r"confirmar|confirmacao|confirm|excluir\?|deletar\?", re.I), "modal_confirm"),
    (re.compile(r"modal.*form|formulario.*modal|popup.*form", re.I), "modal_form"),
    (re.compile(r"senior.*x|shell|menu.*principal|home|inicio", re.I), "shell_navigation"),
]

# (selector_pattern, component_family)  — first match wins
_COMPONENT_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"toolbar|btn-toolbar|action-bar", re.I), "toolbar_button"),
    (re.compile(r"context.?menu|menu-item|dropdown-item", re.I), "context_menu_item"),
    (re.compile(r"tree.?node|tree.?item|treeview", re.I), "tree_node"),
    (re.compile(r"input|textarea|select|combobox|datepicker", re.I), "form_input"),
    (re.compile(r"checkbox|check-row|row-check", re.I), "checkbox_row"),
    (re.compile(r"tr\.|table.?row|grid.?row|data.?row", re.I), "table_row"),
    (re.compile(r"modal.*btn|btn.*modal|dialog.*button|popup.*btn", re.I), "modal_button"),
]


class ScreenObserver:
    """
    Classifies screens and UI components into controlled-vocabulary families.

    Usage::

        observer = ScreenObserver()
        family, review = observer.classify_screen(page_title="GED - Lista de Documentos")
        comp_family    = observer.infer_component_family(seletor_hint="input.nome-campo")
    """

    # ──────────────────────────────────────────────────────────
    # Screen classification  (Requirements 11.1–11.3)
    # ──────────────────────────────────────────────────────────

    def classify_screen(
        self,
        page_title: str = "",
        url_hint: str = "",
        screenshot: Optional[str] = None,  # reserved for future vision-based inference
    ) -> tuple[str, bool]:
        """
        Assign a screen_family from the controlled vocabulary.

        Heuristics are applied to page_title and url_hint.  When no rule
        matches, 'unknown' is returned and review_required is set to True.

        Args:
            page_title:  Page title string from the shadow event.
            url_hint:    URL hint string from the shadow event.
            screenshot:  Reserved — not used in current heuristic implementation.

        Returns:
            (screen_family: str, review_required: bool)
        """
        combined = f"{page_title} {url_hint}"

        for pattern, family in _SCREEN_RULES:
            if pattern.search(combined):
                logger.debug(
                    "Screen classified",
                    extra={"screen_family": family, "combined": combined[:80]},
                )
                return family, False

        logger.debug(
            "Screen classification unknown",
            extra={"combined": combined[:80]},
        )
        return "unknown", True

    # ──────────────────────────────────────────────────────────
    # Component classification  (Requirement 11.4)
    # ──────────────────────────────────────────────────────────

    def infer_component_family(
        self,
        seletor_hint: str = "",
        tag: str = "",
        label: str = "",
    ) -> str:
        """
        Infer a component_family from selector, tag, and label hints.

        Args:
            seletor_hint: CSS / aria selector hint from the shadow event.
            tag:          HTML tag name (e.g. 'input', 'button', 'tr').
            label:        Visible label or aria-label of the element.

        Returns:
            component_family string from the controlled vocabulary.
        """
        combined = f"{seletor_hint} {tag} {label}"

        for pattern, family in _COMPONENT_RULES:
            if pattern.search(combined):
                logger.debug(
                    "Component classified",
                    extra={"component_family": family, "combined": combined[:80]},
                )
                return family

        logger.debug(
            "Component classification unknown",
            extra={"combined": combined[:80]},
        )
        return "unknown"

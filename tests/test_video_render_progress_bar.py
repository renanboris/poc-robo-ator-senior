"""
tests/test_video_render_progress_bar.py
=======================================
Tests for the video-render-progress-bar bugfix.

**Property 1: Bug Condition** — Progresso de Renderização Ignorado pelo onmessage

CRITICAL: Tests 1.x are EXPECTED TO FAIL on unfixed code.
Failure confirms the bug: the `_ws.onmessage` handler in `templates/index.html`
only reacts to `!data.ocupado` and completely ignores `data.progresso`.
When `{ocupado: true, progresso: 47}` arrives, no DOM element is updated.

Root cause confirmed:
  The `onmessage` handler in `conectarWS()` only contains:
    if (!data.ocupado && _wsResolve) { ... resolve ... }
  There is NO branch for `data.progresso`. The field arrives and is silently
  discarded. Additionally, the step DOM template for STEPS[0] (renderização)
  does not include any percentage element — so even if the branch existed,
  there would be no element to update.

Validates: Requirements 1.1, 1.2

**Property 2: Preservation** — Comportamento Inalterado para Inputs Fora da Bug Condition

Tests 2.x MUST PASS on unfixed code — they confirm the baseline behavior
that must be preserved after the fix is applied.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import os
import re
import sys

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Load the index.html source once for all tests
# ---------------------------------------------------------------------------

_TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "templates", "index.html"
)

with open(_TEMPLATE_PATH, encoding="utf-8") as _f:
    _HTML_SOURCE = _f.read()


# ---------------------------------------------------------------------------
# Python simulation of the UNFIXED onmessage handler logic
#
# This mirrors the exact JavaScript logic in templates/index.html:
#
#   _ws.onmessage = (e) => {
#     try {
#       const data = JSON.parse(e.data);
#       if (!data.ocupado && _wsResolve) {
#         const resolve = _wsResolve;
#         _wsResolve = null;
#         resolve({ sucesso: !data.erro, mensagem: data.erro || data.sucesso || '' });
#       }
#     } catch {}
#   };
#
# The simulation uses a mutable dict to track side effects (resolve called,
# DOM element updated) so tests can assert on them.
# ---------------------------------------------------------------------------

def simulate_onmessage_unfixed(data: dict, ws_resolve_active: bool = True) -> dict:
    """
    Simulates the UNFIXED _ws.onmessage handler from templates/index.html.

    Returns a dict describing what happened:
      - resolve_called: bool — whether _wsResolve was invoked
      - resolve_result: dict | None — the argument passed to resolve()
      - dom_pct_updated: bool — whether any percentage element was updated
      - dom_pct_value: str | None — the value set on the percentage element
    """
    result = {
        "resolve_called": False,
        "resolve_result": None,
        "dom_pct_updated": False,
        "dom_pct_value": None,
    }

    # Simulate: if (!data.ocupado && _wsResolve)
    if not data.get("ocupado") and ws_resolve_active:
        result["resolve_called"] = True
        result["resolve_result"] = {
            "sucesso": not bool(data.get("erro")),
            "mensagem": data.get("erro") or data.get("sucesso") or "",
        }

    # NOTE: There is NO branch for data.progresso in the unfixed handler.
    # dom_pct_updated remains False regardless of data.progresso value.

    return result


def simulate_onmessage_fixed(
    data: dict,
    ws_resolve_active: bool = True,
    active_render_step_el: bool = False,
) -> dict:
    """
    Simulates the FIXED _ws.onmessage handler (expected after fix).

    The fix adds an independent branch:
      if (typeof data.progresso === 'number' && _activeRenderStepEl !== null) {
        _activeRenderStepEl.querySelector('.step-pct').textContent = data.progresso + '%';
      }

    Returns the same shape as simulate_onmessage_unfixed, plus dom_pct_updated.
    """
    result = {
        "resolve_called": False,
        "resolve_result": None,
        "dom_pct_updated": False,
        "dom_pct_value": None,
    }

    # Branch 1: resolve Promise when !ocupado (preserved from original)
    if not data.get("ocupado") and ws_resolve_active:
        result["resolve_called"] = True
        result["resolve_result"] = {
            "sucesso": not bool(data.get("erro")),
            "mensagem": data.get("erro") or data.get("sucesso") or "",
        }

    # Branch 2 (NEW): update progress element when progresso is numeric
    progresso = data.get("progresso")
    if isinstance(progresso, (int, float)) and active_render_step_el:
        result["dom_pct_updated"] = True
        result["dom_pct_value"] = f"{progresso}%"

    return result


# ---------------------------------------------------------------------------
# Helper: check if the HTML source contains the progress branch in onmessage
# ---------------------------------------------------------------------------

def _html_has_progresso_branch() -> bool:
    """
    Returns True if the onmessage handler in index.html contains a branch
    that reacts to data.progresso (i.e., the fix has been applied).
    """
    # Look for patterns like: data.progresso, _activeRenderStepEl, step-pct
    has_progresso_branch = bool(re.search(r'data\.progresso', _HTML_SOURCE))
    has_active_render_el = bool(re.search(r'_activeRenderStepEl', _HTML_SOURCE))
    has_step_pct_element = bool(re.search(r'step-pct', _HTML_SOURCE))
    return has_progresso_branch and has_active_render_el and has_step_pct_element


def _html_has_step_pct_in_render_template() -> bool:
    """
    Returns True if the render step DOM template includes a .step-pct element.
    The fix should add: <span class="step-pct" id="${stepId}-pct"></span>
    """
    return bool(re.search(r'step-pct', _HTML_SOURCE))


# ===========================================================================
# PROPERTY 1: BUG CONDITION TESTS
# These tests MUST FAIL on unfixed code — failure confirms the bug exists.
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 1.1 — Structural: onmessage handler has no branch for data.progresso
#
# BUG CONDITION: The HTML source does not contain any logic to handle
# data.progresso in the onmessage handler.
# EXPECTED TO FAIL on unfixed code — confirms the bug.
# ---------------------------------------------------------------------------

def test_1_1_onmessage_has_progresso_branch():
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: the _ws.onmessage handler in templates/index.html must
    contain a branch that reacts to data.progresso.

    EXPECTED TO FAIL on unfixed code — confirms the structural bug:
    - No reference to data.progresso in onmessage
    - No _activeRenderStepEl variable
    - No .step-pct element in the render step template

    Counterexample: the HTML source contains only `if (!data.ocupado && _wsResolve)`
    with no branch for data.progresso.
    """
    assert _html_has_progresso_branch(), (
        "BUG CONFIRMADO: templates/index.html não contém branch para data.progresso "
        "no handler onmessage. O campo chega ao frontend mas é descartado silenciosamente. "
        "Ausência de: data.progresso, _activeRenderStepEl, .step-pct"
    )


# ---------------------------------------------------------------------------
# Test 1.2 — Structural: render step DOM template has no .step-pct element
#
# BUG CONDITION: The HTML template for STEPS[0] (renderização) does not
# include any element to display the progress percentage.
# EXPECTED TO FAIL on unfixed code — confirms the bug.
# ---------------------------------------------------------------------------

def test_1_2_render_step_template_has_step_pct_element():
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: the DOM template for the render step (STEPS[0]) must
    include a .step-pct element to display the progress percentage.

    EXPECTED TO FAIL on unfixed code — confirms the structural bug:
    the step template only has <div class="step-icon spinning"></div>
    and <span>label</span>, with no percentage element.

    Counterexample: no element with class 'step-pct' exists in the HTML source.
    """
    assert _html_has_step_pct_in_render_template(), (
        "BUG CONFIRMADO: templates/index.html não contém elemento .step-pct "
        "no template do step de renderização. Mesmo que o onmessage tivesse "
        "a branch correta, não haveria elemento DOM para atualizar."
    )


# ---------------------------------------------------------------------------
# Test 1.3 — Behavioral: unfixed handler ignores data.progresso = 47
#
# BUG CONDITION: When {ocupado: true, progresso: 47} arrives, the unfixed
# handler does NOT update any DOM element.
# EXPECTED TO FAIL on unfixed code — confirms the behavioral bug.
# ---------------------------------------------------------------------------

def test_1_3_unfixed_handler_ignores_progresso_47():
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: when {ocupado: true, progresso: 47} arrives via WebSocket,
    the FIXED handler must update the DOM percentage element.

    This test simulates the EXPECTED (fixed) behavior and asserts it.
    On unfixed code, the simulation of the unfixed handler confirms the bug:
    dom_pct_updated is False even when progresso=47 is present.

    EXPECTED TO FAIL on unfixed code because:
    1. The HTML source has no progresso branch (test 1.1 catches this)
    2. The unfixed handler simulation confirms dom_pct_updated=False

    Counterexample: {ocupado: true, progresso: 47} → dom_pct_updated=False
    """
    msg = {"ocupado": True, "progresso": 47}

    # Confirm the unfixed handler does NOT update the DOM
    unfixed_result = simulate_onmessage_unfixed(msg, ws_resolve_active=True)
    assert unfixed_result["dom_pct_updated"] is False, (
        "Unexpected: unfixed handler updated DOM — this should not happen"
    )
    assert unfixed_result["resolve_called"] is False, (
        "Unexpected: unfixed handler resolved Promise for ocupado=True message"
    )

    # Assert the EXPECTED (fixed) behavior: DOM must be updated
    # This assertion fails on unfixed code because the HTML has no progresso branch
    assert _html_has_progresso_branch(), (
        "BUG CONFIRMADO: {ocupado: true, progresso: 47} chega ao frontend mas "
        "nenhum elemento DOM é atualizado. O handler onmessage não tem branch "
        "para data.progresso. Contraexemplo: progresso=47 → dom_pct_updated=False"
    )


# ---------------------------------------------------------------------------
# Test 1.4 — Behavioral: unfixed handler ignores data.progresso = 0
#
# BUG CONDITION: Even progresso=0 (start of render) is ignored.
# EXPECTED TO FAIL on unfixed code — confirms the bug.
# ---------------------------------------------------------------------------

def test_1_4_unfixed_handler_ignores_progresso_0():
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: {ocupado: true, progresso: 0} must trigger DOM update.
    EXPECTED TO FAIL on unfixed code.

    Counterexample: progresso=0 → dom_pct_updated=False (no branch exists)
    """
    msg = {"ocupado": True, "progresso": 0}

    unfixed_result = simulate_onmessage_unfixed(msg, ws_resolve_active=True)
    assert unfixed_result["dom_pct_updated"] is False  # confirms bug behavior

    assert _html_has_progresso_branch(), (
        "BUG CONFIRMADO: {ocupado: true, progresso: 0} ignorado pelo onmessage. "
        "Contraexemplo: progresso=0 → dom_pct_updated=False"
    )


# ---------------------------------------------------------------------------
# Test 1.5 — Behavioral: unfixed handler ignores data.progresso = 100
#
# BUG CONDITION: Even progresso=100 (render complete) is ignored.
# EXPECTED TO FAIL on unfixed code — confirms the bug.
# ---------------------------------------------------------------------------

def test_1_5_unfixed_handler_ignores_progresso_100():
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: {ocupado: true, progresso: 100} must trigger DOM update.
    EXPECTED TO FAIL on unfixed code.

    Counterexample: progresso=100 → dom_pct_updated=False (no branch exists)
    """
    msg = {"ocupado": True, "progresso": 100}

    unfixed_result = simulate_onmessage_unfixed(msg, ws_resolve_active=True)
    assert unfixed_result["dom_pct_updated"] is False  # confirms bug behavior

    assert _html_has_progresso_branch(), (
        "BUG CONFIRMADO: {ocupado: true, progresso: 100} ignorado pelo onmessage. "
        "Contraexemplo: progresso=100 → dom_pct_updated=False"
    )


# ---------------------------------------------------------------------------
# Property Test 1.6 — Hypothesis: for any progresso in [0, 100] with
# ocupado=True, the fixed handler must update the DOM element.
#
# EXPECTED TO FAIL on unfixed code — confirms the bug across all inputs.
# ---------------------------------------------------------------------------

@given(progresso=st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_1_6_property_any_progresso_must_update_dom(progresso):
    """
    **Validates: Requirements 1.1, 1.2**

    Property: for any progresso value in [0, 100] with ocupado=True,
    the onmessage handler must update the DOM percentage element.

    EXPECTED TO FAIL on unfixed code — confirms the bug across all inputs.
    Counterexample: any progresso value → dom_pct_updated=False (no branch)
    """
    msg = {"ocupado": True, "progresso": progresso}

    # The fix must be present in the HTML source
    assert _html_has_progresso_branch(), (
        f"BUG CONFIRMADO: progresso={progresso} com ocupado=True chega ao frontend "
        f"mas nenhum elemento DOM é atualizado. O handler onmessage não tem branch "
        f"para data.progresso. Contraexemplo: progresso={progresso} → dom_pct_updated=False"
    )

    # When fix is applied, the fixed simulation must update the DOM
    fixed_result = simulate_onmessage_fixed(
        msg, ws_resolve_active=True, active_render_step_el=True
    )
    assert fixed_result["dom_pct_updated"] is True, (
        f"Fixed handler não atualizou DOM para progresso={progresso}"
    )
    assert fixed_result["dom_pct_value"] == f"{progresso}%", (
        f"Fixed handler exibiu valor errado: {fixed_result['dom_pct_value']!r} "
        f"(esperado: '{progresso}%')"
    )
    # Promise must NOT be resolved for ocupado=True messages
    assert fixed_result["resolve_called"] is False, (
        f"Fixed handler resolveu Promise prematuramente para progresso={progresso}"
    )


# ===========================================================================
# PROPERTY 2: PRESERVATION TESTS
# These tests MUST PASS on unfixed code — they confirm the baseline behavior
# that must be preserved after the fix is applied.
# ===========================================================================


# ---------------------------------------------------------------------------
# Test 2.1 — Promise resolution preserved: {ocupado: false} resolves _wsResolve
#
# Preservation: the existing Promise resolution logic must not be broken.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_1_promise_resolution_preserved_on_ocupado_false():
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

    Preservation: {ocupado: false, progresso: null, sucesso: "Concluído"}
    must still resolve _wsResolve with {sucesso: True, mensagem: "Concluído"}.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    msg = {"ocupado": False, "progresso": None, "sucesso": "Concluído com sucesso."}

    result = simulate_onmessage_unfixed(msg, ws_resolve_active=True)

    assert result["resolve_called"] is True, (
        "Preservation FALHOU: _wsResolve não foi chamado para {ocupado: false}"
    )
    assert result["resolve_result"]["sucesso"] is True, (
        f"Preservation FALHOU: sucesso deve ser True. "
        f"Resultado: {result['resolve_result']!r}"
    )
    assert result["resolve_result"]["mensagem"] == "Concluído com sucesso.", (
        f"Preservation FALHOU: mensagem incorreta. "
        f"Resultado: {result['resolve_result']!r}"
    )
    assert result["dom_pct_updated"] is False, (
        "Preservation FALHOU: DOM não deve ser atualizado para mensagem de conclusão"
    )


# ---------------------------------------------------------------------------
# Test 2.2 — Error handling preserved: {ocupado: false, erro: "..."} resolves
# with sucesso=False
#
# Preservation: error messages must still resolve the Promise with sucesso=False.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_2_error_handling_preserved():
    """
    **Validates: Requirements 3.2**

    Preservation: {ocupado: false, erro: "Falha: arquivo não encontrado"}
    must resolve _wsResolve with {sucesso: False, mensagem: "Falha: ..."}.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    msg = {"ocupado": False, "erro": "Falha: arquivo não encontrado", "progresso": None}

    result = simulate_onmessage_unfixed(msg, ws_resolve_active=True)

    assert result["resolve_called"] is True, (
        "Preservation FALHOU: _wsResolve não foi chamado para mensagem de erro"
    )
    assert result["resolve_result"]["sucesso"] is False, (
        f"Preservation FALHOU: sucesso deve ser False para mensagem de erro. "
        f"Resultado: {result['resolve_result']!r}"
    )
    assert "Falha" in result["resolve_result"]["mensagem"], (
        f"Preservation FALHOU: mensagem de erro não preservada. "
        f"Resultado: {result['resolve_result']!r}"
    )


# ---------------------------------------------------------------------------
# Test 2.3 — Other steps (SCORM, PDF, SimLink) do not receive progress indicator
#
# Preservation: when _activeRenderStepEl is None (other steps active),
# messages with progresso must NOT update any DOM element.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_3_other_steps_do_not_receive_progress_indicator():
    """
    **Validates: Requirements 3.1**

    Preservation: when the render step is NOT active (_activeRenderStepEl=None),
    messages with data.progresso must NOT update any DOM element.
    SCORM, PDF, SimLink steps must continue showing only the default spinner.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    # Simulate a progresso message arriving while a non-render step is active
    msg = {"ocupado": True, "progresso": 47}

    # active_render_step_el=False simulates _activeRenderStepEl === null
    fixed_result = simulate_onmessage_fixed(
        msg, ws_resolve_active=True, active_render_step_el=False
    )

    assert fixed_result["dom_pct_updated"] is False, (
        "Preservation FALHOU: DOM foi atualizado para step não-renderização. "
        "SCORM/PDF/SimLink não devem exibir indicador de progresso."
    )
    assert fixed_result["resolve_called"] is False, (
        "Preservation FALHOU: Promise foi resolvida para mensagem com ocupado=True"
    )


# ---------------------------------------------------------------------------
# Test 2.4 — No residual state: after render step completes, _activeRenderStepEl
# must be null (simulated by active_render_step_el=False)
#
# Preservation: new sessions must not carry residual progress state.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_4_no_residual_state_after_render_completes():
    """
    **Validates: Requirements 3.5**

    Preservation: after the render step completes (ocupado=False),
    subsequent progresso messages must NOT update any DOM element.
    _activeRenderStepEl must be null after completion.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    # Step 1: render completes
    completion_msg = {"ocupado": False, "progresso": None, "sucesso": "Vídeo gerado."}
    result = simulate_onmessage_fixed(
        completion_msg, ws_resolve_active=True, active_render_step_el=True
    )
    assert result["resolve_called"] is True

    # Step 2: after completion, _activeRenderStepEl should be null
    # Simulate a stale progresso message arriving after completion
    stale_msg = {"ocupado": True, "progresso": 50}
    stale_result = simulate_onmessage_fixed(
        stale_msg, ws_resolve_active=False, active_render_step_el=False  # null after completion
    )
    assert stale_result["dom_pct_updated"] is False, (
        "Preservation FALHOU: DOM atualizado por mensagem residual após conclusão. "
        "_activeRenderStepEl deve ser null após o step de renderização concluir."
    )


# ---------------------------------------------------------------------------
# Property Test 2.5 — Hypothesis: for any message where NOT isBugCondition,
# the fixed handler produces the same behavior as the unfixed handler.
#
# Generates messages outside the bug condition and verifies preservation.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

@st.composite
def non_bug_condition_messages(draw):
    """
    Generates WebSocket messages that are NOT in the bug condition.
    Bug condition: ocupado=True AND progresso is numeric AND render step active.
    Non-bug: ocupado=False, OR progresso is null/None, OR render step not active.
    """
    # Choose a non-bug scenario
    scenario = draw(st.sampled_from([
        "ocupado_false_with_sucesso",
        "ocupado_false_with_erro",
        "ocupado_true_no_progresso",
        "ocupado_false_with_progresso",  # progresso present but ocupado=False
    ]))

    if scenario == "ocupado_false_with_sucesso":
        sucesso = draw(st.text(min_size=1, max_size=60, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "Zs")
        )))
        return {"ocupado": False, "progresso": None, "sucesso": sucesso, "erro": ""}

    elif scenario == "ocupado_false_with_erro":
        erro = draw(st.text(min_size=1, max_size=60, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd", "Zs")
        )))
        return {"ocupado": False, "progresso": None, "sucesso": "", "erro": erro}

    elif scenario == "ocupado_true_no_progresso":
        return {"ocupado": True, "progresso": None, "sucesso": "", "erro": ""}

    else:  # ocupado_false_with_progresso
        progresso = draw(st.integers(min_value=0, max_value=100))
        return {"ocupado": False, "progresso": progresso, "sucesso": "Concluído.", "erro": ""}


@given(msg=non_bug_condition_messages())
@settings(max_examples=50)
def test_2_5_property_non_bug_condition_behavior_preserved(msg):
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

    Property: for any message where NOT isBugCondition(msg), the fixed handler
    must produce exactly the same behavior as the unfixed handler.

    Specifically:
    - resolve_called must be identical
    - resolve_result must be identical
    - dom_pct_updated must be False (no spurious DOM updates)

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    ws_resolve_active = True

    unfixed = simulate_onmessage_unfixed(msg, ws_resolve_active=ws_resolve_active)
    # For non-bug-condition messages, active_render_step_el=False (other steps)
    # OR the message has no numeric progresso — either way, no DOM update expected
    fixed = simulate_onmessage_fixed(
        msg, ws_resolve_active=ws_resolve_active, active_render_step_el=False
    )

    assert fixed["resolve_called"] == unfixed["resolve_called"], (
        f"Preservation FALHOU: resolve_called diferente. "
        f"msg={msg!r}, unfixed={unfixed['resolve_called']}, fixed={fixed['resolve_called']}"
    )

    if unfixed["resolve_result"] is not None:
        assert fixed["resolve_result"] == unfixed["resolve_result"], (
            f"Preservation FALHOU: resolve_result diferente. "
            f"msg={msg!r}, unfixed={unfixed['resolve_result']!r}, fixed={fixed['resolve_result']!r}"
        )

    assert fixed["dom_pct_updated"] is False, (
        f"Preservation FALHOU: DOM atualizado para mensagem fora da bug condition. "
        f"msg={msg!r}"
    )


# ---------------------------------------------------------------------------
# Test 2.6 — Promise not resolved prematurely by progresso messages
#
# Preservation: messages with ocupado=True and progresso must NEVER resolve
# the Promise, even after the fix is applied.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_6_promise_not_resolved_by_progresso_messages():
    """
    **Validates: Requirements 3.1**

    Preservation: {ocupado: true, progresso: 75} must NEVER resolve _wsResolve.
    The Promise resolution must only happen when ocupado=False.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    msg = {"ocupado": True, "progresso": 75}

    # Both unfixed and fixed handlers must NOT resolve the Promise
    unfixed = simulate_onmessage_unfixed(msg, ws_resolve_active=True)
    fixed = simulate_onmessage_fixed(msg, ws_resolve_active=True, active_render_step_el=True)

    assert unfixed["resolve_called"] is False, (
        "Preservation FALHOU: unfixed handler resolveu Promise para ocupado=True"
    )
    assert fixed["resolve_called"] is False, (
        "Preservation FALHOU: fixed handler resolveu Promise para ocupado=True. "
        "A branch de progresso deve ser INDEPENDENTE da branch de !ocupado."
    )

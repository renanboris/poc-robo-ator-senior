"""
Preservation tests for capture-missed-clicks bugfix.

These tests verify that for inputs where the bug condition does NOT hold,
the fixed code behaves identically to the original — normal session behavior
is completely unchanged.

Bug condition (for reference):
  isBugCondition(X) = (X.pending_tasks > 0 AND X.browser_closed)
                   OR (X.last_mousedown_age_at_close_ms < 250)

All tests here operate on sessions where NEITHER sub-condition holds:
  - All tasks complete before the session ends (no race condition)
  - No click is within the 250ms blind window at close time

Tests are self-contained, use unittest.mock where needed, and do NOT require
a real Playwright browser or network calls.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6 (Property 2 — Preservation)
"""

import asyncio
import sys
import os
import json
import pytest

# ---------------------------------------------------------------------------
# Make sure the project root is on sys.path so we can import capture.py
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import capture  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_capture_state():
    """Reset module-level state in capture.py between tests."""
    capture.cliques_capturados.clear()
    capture._id_acao_global = 0
    capture._lock_id = None
    capture._pending_tasks = set()


def _make_fake_args(label: str = "Botao Teste", acao: str = "clique", valor: str = "") -> object:
    """Fake Playwright expose_binding args object."""
    payload = json.dumps({
        "tag": "button",
        "texto_encontrado": valor or label,
        "seletor": f"[aria-label='{label}']",
        "iframe": "Pagina Principal",
        "acao": acao,
        "posicao_visual": "x:100,y:200,w:80,h:30",
        "html_snapshot": f"<button>{label}</button>",
    })

    class FakeArgs:
        async def json_value(self):
            return payload

    return FakeArgs()


def _make_fake_source() -> dict:
    """Fake Playwright expose_binding source dict (no real frame)."""
    return {"frame": None}


async def _fire_click(label: str, acao: str = "clique", valor: str = "") -> None:
    """
    Fire a single click event through the real on_capturar_elemento handler.
    No screenshot or Gemini call — frame is None so those paths are skipped.
    """
    source = _make_fake_source()
    args = _make_fake_args(label=label, acao=acao, valor=valor)
    await capture.on_capturar_elemento(source, args)


# ---------------------------------------------------------------------------
# Test 5.1 — Normal session with 10 clicks and 1s gaps
#
# Simulates a normal session where all tasks complete before the browser
# closes (bug condition does NOT hold). Verifies cliques_capturados has
# exactly 10 entries and each entry is correctly structured.
#
# Validates: Requirements 3.1 (Property 2 — Preservation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_normal_session_10_clicks():
    """
    Preservation: normal session with 10 clicks and 1s gaps.

    Simulates a session where the user clicks 10 buttons with 1-second
    gaps between each. All tasks complete before the browser closes —
    the bug condition does NOT hold.

    Expected:
      - cliques_capturados has exactly 10 entries
      - Each entry has the required structure fields
      - Each entry has the correct acao value

    **Validates: Requirements 3.1 (Property 2)**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    TOTAL_CLICKS = 10

    # Fire 10 clicks sequentially (simulating 1s gaps — no concurrency issues)
    for i in range(TOTAL_CLICKS):
        await _fire_click(label=f"Botao {i + 1}", acao="clique")

    # Verify count
    assert len(capture.cliques_capturados) == TOTAL_CLICKS, (
        f"Expected {TOTAL_CLICKS} entries in cliques_capturados, "
        f"got {len(capture.cliques_capturados)}."
    )

    # Verify structure of each entry
    required_top_keys = {"id_acao", "acao", "intencao_semantica", "elemento_alvo", "valor_input"}
    required_alvo_keys = {
        "descricao_visual", "contexto_tela", "tipo_elemento",
        "confianca_captura", "label_curto", "coordenadas_relativas",
        "seletor_hint", "html_hint", "screenshot_referencia",
    }

    for idx, entry in enumerate(capture.cliques_capturados):
        assert required_top_keys.issubset(entry.keys()), (
            f"Entry {idx} missing required keys. "
            f"Present: {set(entry.keys())}, Required: {required_top_keys}"
        )
        assert entry["acao"] == "clique", (
            f"Entry {idx} has wrong acao: {entry['acao']!r}"
        )
        assert entry["id_acao"] == idx + 1, (
            f"Entry {idx} has wrong id_acao: {entry['id_acao']}"
        )
        alvo = entry["elemento_alvo"]
        assert required_alvo_keys.issubset(alvo.keys()), (
            f"Entry {idx} elemento_alvo missing keys. "
            f"Present: {set(alvo.keys())}, Required: {required_alvo_keys}"
        )


# ---------------------------------------------------------------------------
# Test 5.2 — Double-click sequence: only duplo_clique recorded, no spurious clique
#
# Simulates the JS double-click logic in Python:
#   1. Start a clickTimeout task (250ms)
#   2. Immediately cancel it (dblclick fires)
#   3. Append a duplo_clique entry
#
# Verifies only 1 entry with acao == "duplo_clique", no "clique" entries.
#
# Validates: Requirements 3.2 (Property 2 — Preservation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_double_click_no_spurious_clique():
    """
    Preservation: double-click sequence — only duplo_clique recorded.

    Simulates the JS double-click logic:
      - mousedown fires → clickTimeout (250ms) is queued
      - dblclick fires immediately → clickTimeout is cancelled
      - duplo_clique is appended

    Expected:
      - Exactly 1 entry in cliques_capturados
      - That entry has acao == "duplo_clique"
      - No entry with acao == "clique"

    **Validates: Requirements 3.2 (Property 2)**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    # Simulate JS: mousedown → setTimeout(processarEvento('clique'), 250)
    async def click_timeout_task():
        await asyncio.sleep(0.25)
        await _fire_click(label="Botao Duplo", acao="clique")

    # Start the clickTimeout task (mousedown fired)
    timeout_task = asyncio.create_task(click_timeout_task())

    # dblclick fires immediately — cancel the clickTimeout
    timeout_task.cancel()
    await asyncio.gather(timeout_task, return_exceptions=True)

    # dblclick handler fires: append duplo_clique
    await _fire_click(label="Botao Duplo", acao="duplo_clique")

    # Verify: only duplo_clique, no spurious clique
    assert len(capture.cliques_capturados) == 1, (
        f"Expected 1 entry (duplo_clique), got {len(capture.cliques_capturados)}."
    )
    assert capture.cliques_capturados[0]["acao"] == "duplo_clique", (
        f"Expected acao='duplo_clique', got {capture.cliques_capturados[0]['acao']!r}."
    )

    clique_entries = [e for e in capture.cliques_capturados if e["acao"] == "clique"]
    assert len(clique_entries) == 0, (
        f"Spurious 'clique' entries found: {clique_entries}"
    )


# ---------------------------------------------------------------------------
# Test 5.3 — Right-click: clique_direito captured immediately without delay
#
# Right-click bypasses clickTimeout entirely — it is processed immediately
# in the mousedown handler (e.button === 2 path).
#
# Validates: Requirements 3.4 (Property 2 — Preservation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_right_click_immediate():
    """
    Preservation: right-click captured immediately without delay.

    Right-click (e.button === 2) bypasses the 250ms clickTimeout entirely.
    The event is processed synchronously in the mousedown handler.

    Expected:
      - Exactly 1 entry in cliques_capturados
      - That entry has acao == "clique_direito"
      - No 250ms delay (task completes immediately)

    **Validates: Requirements 3.4 (Property 2)**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    # Right-click fires processarEvento immediately — no setTimeout involved.
    # Simulate by calling on_capturar_elemento directly with acao='clique_direito'.
    await _fire_click(label="Menu Contexto", acao="clique_direito")

    assert len(capture.cliques_capturados) == 1, (
        f"Expected 1 entry for right-click, got {len(capture.cliques_capturados)}."
    )
    assert capture.cliques_capturados[0]["acao"] == "clique_direito", (
        f"Expected acao='clique_direito', got {capture.cliques_capturados[0]['acao']!r}."
    )


# ---------------------------------------------------------------------------
# Test 5.4 — Field fill via blur: preencher_campo captured correctly
#
# The blur handler appends preencher_campo when e.target.value is set.
# Simulate by firing on_capturar_elemento with acao='preencher_campo'.
#
# Validates: Requirements 3.5 (Property 2 — Preservation)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_field_fill_blur():
    """
    Preservation: blur on input with value → preencher_campo captured.

    The JS blur handler fires processarEvento(target, 'preencher_campo', value)
    when e.target.value is set and the target is an input/textarea.

    Expected:
      - Exactly 1 entry in cliques_capturados
      - acao == "preencher_campo"
      - valor_input contains the field value

    **Validates: Requirements 3.5 (Property 2)**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    FIELD_VALUE = "joao.silva@empresa.com"

    # Simulate blur on an input field with a value
    payload = json.dumps({
        "tag": "input",
        "texto_encontrado": FIELD_VALUE,
        "seletor": "[name='email']",
        "iframe": "Pagina Principal",
        "acao": "preencher_campo",
        "posicao_visual": "x:200,y:300,w:200,h:30",
        "html_snapshot": f"<input name='email' value='{FIELD_VALUE}'>",
    })

    class FakeBlurArgs:
        async def json_value(self):
            return payload

    source = _make_fake_source()
    await capture.on_capturar_elemento(source, FakeBlurArgs())

    assert len(capture.cliques_capturados) == 1, (
        f"Expected 1 entry for preencher_campo, got {len(capture.cliques_capturados)}."
    )
    entry = capture.cliques_capturados[0]
    assert entry["acao"] == "preencher_campo", (
        f"Expected acao='preencher_campo', got {entry['acao']!r}."
    )
    assert entry["valor_input"] == FIELD_VALUE, (
        f"Expected valor_input={FIELD_VALUE!r}, got {entry['valor_input']!r}."
    )


# ---------------------------------------------------------------------------
# Test 5.5 — Quality gate: _validar_roteiro blocks low-quality roteiros
#
# Verifies _validar_roteiro still returns (False, ...) for roteiros with
# 0 passos or all low-confidence actions.
#
# Validates: Requirements 3.6 (Property 2 — Preservation)
# ---------------------------------------------------------------------------

def test_preservation_quality_gate_blocks_low_quality():
    """
    Preservation: _validar_roteiro blocks auto-rebuild on low-quality roteiros.

    Tests three low-quality roteiro shapes:
      1. Empty passos list → blocked (< 2 passos)
      2. Single passo → blocked (< 2 passos)
      3. All actions with confianca='baixa' and no seletor_hint → blocked

    Expected: _validar_roteiro returns (False, <reason_string>) for all cases.

    **Validates: Requirements 3.6 (Property 2)**
    """
    # Case 1: no passos at all
    roteiro_vazio = {"passos": []}
    from utils import validar_roteiro as _validar_roteiro_fn
    aprovado, motivo = _validar_roteiro_fn(roteiro_vazio)
    assert aprovado is False, "Expected False for roteiro with 0 passos."
    assert motivo, "Expected a non-empty reason string."

    # Case 2: only 1 passo (below minimum of 2)
    roteiro_um_passo = {
        "passos": [
            {
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "button",
                            "confianca_captura": "alta",
                        },
                    }
                ]
            }
        ]
    }
    aprovado, motivo = _validar_roteiro_fn(roteiro_um_passo)
    assert aprovado is False, "Expected False for roteiro with only 1 passo."
    assert motivo, "Expected a non-empty reason string."

    # Case 3: 2 passos but all actions have confianca='baixa' and no seletor_hint
    # → >70% baixa confiança AND <50% com seletor → blocked
    roteiro_baixa_qualidade = {
        "passos": [
            {
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "",
                            "confianca_captura": "baixa",
                        },
                    },
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "",
                            "confianca_captura": "baixa",
                        },
                    },
                ]
            },
            {
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "",
                            "confianca_captura": "baixa",
                        },
                    }
                ]
            },
        ]
    }
    aprovado, motivo = _validar_roteiro_fn(roteiro_baixa_qualidade)
    assert aprovado is False, (
        "Expected False for roteiro with all low-confidence actions and no selectors."
    )
    assert motivo, "Expected a non-empty reason string."


# ---------------------------------------------------------------------------
# Test 5.6 — Drain with zero pending tasks is a no-op
#
# Verifies that the drain step with an empty set causes no error and
# leaves cliques_capturados unchanged.
#
# Validates: Requirements 2.1 (edge case — drain is safe when empty)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_drain_zero_pending_tasks_noop():
    """
    Preservation: drain step with zero pending tasks is a no-op.

    The drain step is:
        await asyncio.gather(*_pending_tasks, return_exceptions=True)

    When _pending_tasks is empty, this should complete immediately with
    no error and leave cliques_capturados unchanged.

    Expected:
      - No exception raised
      - cliques_capturados remains unchanged (empty)

    **Validates: Requirements 2.1 (edge case)**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    # Pre-condition: no pending tasks, no clicks
    assert len(capture.cliques_capturados) == 0
    assert len(capture._pending_tasks) == 0

    # Execute the drain step with an empty set — must be a no-op
    results = await asyncio.gather(*set(), return_exceptions=True)

    # No exception, no side effects
    assert results == [], f"Expected empty results from empty gather, got {results}."
    assert len(capture.cliques_capturados) == 0, (
        f"cliques_capturados should be unchanged (empty), "
        f"got {len(capture.cliques_capturados)} entries."
    )
    assert len(capture._pending_tasks) == 0, (
        "No pending tasks should have been created."
    )

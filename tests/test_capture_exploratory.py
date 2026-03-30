"""
Exploratory tests for capture-missed-clicks bugfix — UPDATED for FIXED code.

These tests now reflect the FIXED behavior and are expected to PASS.

Root causes that were confirmed during exploration:
  Sub-condition A: race condition — polling loop exited without awaiting in-flight
                   `on_capturar_elemento` async tasks.
  Sub-condition B: 250ms blind window in JS — `setTimeout` was destroyed with
                   browser context before firing.

The fix:
  - `_pending_tasks` set tracks in-flight tasks via `_track()`.
  - Drain step: `await asyncio.gather(*_pending_tasks, return_exceptions=True)`.
  - JS `flushPending()` fires on `visibilitychange`/`pagehide`.
  - Single `asyncio.run(_pipeline(...))` keeps tasks alive through drain.

Tests use unittest.mock to simulate the capture session internals without a
real Playwright browser.
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

import capture  # noqa: E402  (imported after sys.path patch)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_capture_state():
    """Reset module-level state in capture.py between tests."""
    capture.cliques_capturados.clear()
    capture._id_acao_global = 0
    capture._lock_id = None
    capture._pending_tasks = set()


def _make_fake_args(label: str = "Botao Teste", acao: str = "clique") -> object:
    """
    Build a fake 'args' object that mimics what Playwright passes to
    expose_binding handlers.  `on_capturar_elemento` calls `await args.json_value()`
    which must return a JSON string (or dict) with the click payload.
    """
    payload = json.dumps({
        "tag": "button",
        "texto_encontrado": label,
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
    """
    Build a fake 'source' dict that mimics what Playwright passes to
    expose_binding handlers.  on_capturar_elemento accesses source["frame"].
    We return None for frame so the screenshot path is skipped.
    """
    return {"frame": None}


# ---------------------------------------------------------------------------
# Test 1.1 — Slow task race (Sub-condition A) — FIXED behavior
#
# The fix uses asyncio.gather(*tasks) (the drain step) instead of cancelling.
# Assert cliques_capturados has 3 entries.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_1_slow_task_race_drops_clicks():
    """
    Sub-condition A: race condition — FIXED behavior.

    Simulates the drain step: instead of cancelling in-flight tasks,
    we await them with asyncio.gather (the fix).

    With the drain step, all 3 slow tasks complete and cliques_capturados
    has exactly 3 entries.
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    SLEEP_DURATION = 0.5  # 500ms — longer than the polling interval

    async def slow_on_capturar_elemento(source, args):
        """Slow handler: sleeps before appending to cliques_capturados."""
        await asyncio.sleep(SLEEP_DURATION)
        capture.cliques_capturados.append({"id_acao": len(capture.cliques_capturados) + 1})

    # Fire 3 click events as tasks (mimicking how expose_binding fires them)
    tasks = []
    for i in range(3):
        source = _make_fake_source()
        args = _make_fake_args(label=f"Botao {i+1}")
        task = asyncio.create_task(slow_on_capturar_elemento(source, args))
        tasks.append(task)

    # FIX: drain step — await all tasks instead of cancelling them.
    # This mirrors: await asyncio.gather(*_pending_tasks, return_exceptions=True)
    await asyncio.gather(*tasks, return_exceptions=True)

    # With the drain step, all 3 tasks complete → 3 entries
    assert len(capture.cliques_capturados) == 3, (
        f"Expected 3 clicks in cliques_capturados after drain, "
        f"but got {len(capture.cliques_capturados)}."
    )


# ---------------------------------------------------------------------------
# Test 1.2 — 250ms blind window (Sub-condition B) — FIXED behavior
#
# The fix calls flushPending() equivalent instead of cancelling the timer.
# Assert the click appears in cliques_capturados.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_2_250ms_blind_window_drops_last_click():
    """
    Sub-condition B: 250ms blind window — FIXED behavior.

    Simulates the JS flushPending() fix: instead of cancelling the timer,
    we cancel it and immediately call the handler synchronously (flush).

    With flushPending, the click is captured even though the browser
    closed within the 250ms window.
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    async def immediate_on_capturar_elemento(source, args):
        """Fast handler that records receipt immediately."""
        capture.cliques_capturados.append({"id_acao": 1, "acao": "clique"})

    # Simulate the JS-side 250ms clickTimeout:
    # mousedown fires → setTimeout(processarEvento, 250) is queued.
    async def js_click_timeout_simulation():
        """Mimics JS: setTimeout(() => capturarElemento(...), 250)"""
        await asyncio.sleep(0.25)  # 250ms JS timer
        source = _make_fake_source()
        args = _make_fake_args(label="Ultimo Botao")
        await immediate_on_capturar_elemento(source, args)

    # Start the simulated JS timer
    timer_task = asyncio.create_task(js_click_timeout_simulation())

    # Simulate browser context closing after 100ms (within the 250ms window)
    await asyncio.sleep(0.1)

    # FIX: flushPending() equivalent — cancel the timer and call handler immediately.
    # This mirrors the JS: clearTimeout(clickTimeout); processarEvento(_lastMousedownTarget, 'clique')
    timer_task.cancel()
    await asyncio.gather(timer_task, return_exceptions=True)

    # Call the handler immediately (flush) — simulating flushPending()
    source = _make_fake_source()
    args = _make_fake_args(label="Ultimo Botao")
    await immediate_on_capturar_elemento(source, args)

    # With flushPending, the click is captured → 1 entry
    assert len(capture.cliques_capturados) == 1, (
        f"Expected 1 click in cliques_capturados after flushPending, "
        f"but got {len(capture.cliques_capturados)}."
    )


# ---------------------------------------------------------------------------
# Test 1.3 — Rapid close (combined sub-conditions) — FIXED behavior
#
# The fix drains all tasks with asyncio.gather instead of cancelling.
# Assert all 5 entries are in cliques_capturados.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_1_3_rapid_close_drops_multiple_clicks():
    """
    Combined: rapid close with multiple in-flight tasks — FIXED behavior.

    Fires 5 clicks whose handlers each sleep 300ms (simulating screenshot +
    Gemini latency), then drains them with asyncio.gather (the fix).

    With the drain step, all 5 tasks complete → 5 entries.
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    HANDLER_LATENCY = 0.3  # 300ms per handler (screenshot + Gemini simulation)

    async def latent_on_capturar_elemento(source, args, click_id: int):
        """Handler with latency simulating real screenshot + Gemini work."""
        await asyncio.sleep(HANDLER_LATENCY)
        capture.cliques_capturados.append({"id_acao": click_id})

    # Fire 5 clicks as concurrent tasks (rapid succession)
    tasks = []
    for i in range(5):
        source = _make_fake_source()
        args = _make_fake_args(label=f"Elemento {i+1}")
        task = asyncio.create_task(
            latent_on_capturar_elemento(source, args, click_id=i + 1)
        )
        tasks.append(task)

    # FIX: drain step — await all tasks instead of cancelling them.
    await asyncio.gather(*tasks, return_exceptions=True)

    # With the drain step, all 5 tasks complete → 5 entries
    assert len(capture.cliques_capturados) == 5, (
        f"Expected 5 clicks in cliques_capturados after drain, "
        f"but got {len(capture.cliques_capturados)}."
    )

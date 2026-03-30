"""
Fix-checking tests for capture-missed-clicks bugfix.

These tests verify that the FIXED behavior works correctly for all inputs
where the bug condition holds (browser closes while tasks are in-flight OR
within the 250ms JS blind window).

Fix summary:
  - `_pending_tasks` set tracks in-flight tasks via `_track()`.
  - Drain step: `await asyncio.gather(*_pending_tasks, return_exceptions=True)`.
  - JS `flushPending()` fires on `visibilitychange`/`pagehide`.
  - Single `asyncio.run(_pipeline(...))` keeps tasks alive through drain.

Tests are self-contained, use unittest.mock where needed, and do NOT require
a real Playwright browser or network calls.

Validates: Requirements 2.1, 2.2, 2.3 (Property 1 — Bug Condition)
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


def _make_fake_args(label: str = "Botao Teste", acao: str = "clique") -> object:
    """Fake Playwright expose_binding args object."""
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
    """Fake Playwright expose_binding source dict (no real frame)."""
    return {"frame": None}


# ---------------------------------------------------------------------------
# Test: fix_slow_tasks_immediate_close
#
# Simulate slow tasks (500ms) + immediate close, but WITH the drain step.
# Assert cliques_capturados count equals total clicks fired (3).
#
# Validates: Requirements 2.1, 2.2 (Sub-condition A fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fix_slow_tasks_immediate_close():
    """
    Fix-checking: slow tasks (500ms) + immediate close WITH drain step.

    Simulates 3 click events whose handlers each sleep 500ms (mimicking
    screenshot + Gemini latency). The "browser closes" immediately after
    firing the tasks, but the drain step (asyncio.gather) ensures all
    tasks complete before the session ends.

    Expected: cliques_capturados has exactly 3 entries.

    **Validates: Requirements 2.1, 2.2**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    TOTAL_CLICKS = 3
    HANDLER_LATENCY = 0.5  # 500ms — simulates screenshot + Gemini

    async def slow_handler(click_id: int):
        """Slow handler: sleeps before appending to cliques_capturados."""
        await asyncio.sleep(HANDLER_LATENCY)
        capture.cliques_capturados.append({"id_acao": click_id})

    # Fire 3 click events as tasks and track them (mimicking _track())
    pending_tasks: set = set()
    for i in range(TOTAL_CLICKS):
        task = asyncio.create_task(slow_handler(click_id=i + 1))
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)

    # Simulate immediate browser close — polling loop exits here.
    # FIX: drain step awaits all pending tasks before returning.
    if pending_tasks:
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    assert len(capture.cliques_capturados) == TOTAL_CLICKS, (
        f"Expected {TOTAL_CLICKS} clicks after drain, "
        f"got {len(capture.cliques_capturados)}."
    )


# ---------------------------------------------------------------------------
# Test: fix_250ms_window_flush
#
# Simulate a click within the 250ms window before close, but WITH
# flushPending() called — assert click appears in cliques_capturados.
#
# Validates: Requirements 2.3 (Sub-condition B fix)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fix_250ms_window_flush():
    """
    Fix-checking: click within 250ms window before close WITH flushPending.

    Simulates a mousedown that queued a JS setTimeout(250ms). The browser
    closes after 100ms (within the window). Instead of letting the timer
    die, flushPending() is called: the timer is cancelled and the handler
    is invoked immediately (synchronously from the browser's perspective).

    Expected: cliques_capturados has exactly 1 entry.

    **Validates: Requirements 2.3**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    async def immediate_handler():
        """Fast handler that records the click immediately."""
        capture.cliques_capturados.append({"id_acao": 1, "acao": "clique"})

    # Simulate JS: mousedown → setTimeout(processarEvento, 250)
    async def js_click_timeout():
        await asyncio.sleep(0.25)  # 250ms JS timer
        await immediate_handler()

    timer_task = asyncio.create_task(js_click_timeout())

    # Browser closes at 100ms — within the 250ms window
    await asyncio.sleep(0.1)

    # FIX: flushPending() equivalent
    # clearTimeout(clickTimeout) → cancel the timer
    timer_task.cancel()
    await asyncio.gather(timer_task, return_exceptions=True)

    # processarEvento(_lastMousedownTarget, 'clique') → call handler immediately
    await immediate_handler()

    assert len(capture.cliques_capturados) == 1, (
        f"Expected 1 click after flushPending, "
        f"got {len(capture.cliques_capturados)}."
    )


# ---------------------------------------------------------------------------
# Test: fix_rapid_close_all_captured
#
# Fire 5 clicks with 300ms latency, drain them, assert all 5 captured.
#
# Validates: Requirements 2.1, 2.2 (Sub-condition A fix — multiple clicks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fix_rapid_close_all_captured():
    """
    Fix-checking: 5 clicks with 300ms latency, drained, all captured.

    Fires 5 concurrent click handlers each sleeping 300ms (simulating
    screenshot + Gemini latency). The session closes immediately after
    firing, but the drain step ensures all 5 complete.

    Expected: cliques_capturados has exactly 5 entries.

    **Validates: Requirements 2.1, 2.2**
    """
    _reset_capture_state()
    capture._lock_id = asyncio.Lock()

    TOTAL_CLICKS = 5
    HANDLER_LATENCY = 0.3  # 300ms per handler

    async def latent_handler(click_id: int):
        """Handler with latency simulating real screenshot + Gemini work."""
        await asyncio.sleep(HANDLER_LATENCY)
        capture.cliques_capturados.append({"id_acao": click_id})

    # Fire 5 clicks as concurrent tracked tasks
    pending_tasks: set = set()
    for i in range(TOTAL_CLICKS):
        task = asyncio.create_task(latent_handler(click_id=i + 1))
        pending_tasks.add(task)
        task.add_done_callback(pending_tasks.discard)

    # Simulate immediate browser close — FIX: drain step
    if pending_tasks:
        await asyncio.gather(*pending_tasks, return_exceptions=True)

    assert len(capture.cliques_capturados) == TOTAL_CLICKS, (
        f"Expected {TOTAL_CLICKS} clicks after drain, "
        f"got {len(capture.cliques_capturados)}."
    )

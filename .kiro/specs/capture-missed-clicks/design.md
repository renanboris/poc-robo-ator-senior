# capture-missed-clicks Bugfix Design

## Overview

During a capture session in `capture.py`, clicks performed immediately before the browser is closed are silently dropped and never appear in the generated roteiro. Two independent root causes combine to produce this loss:

1. **Race condition on session close** — the main polling loop exits as soon as `page.is_closed()` returns `True`, without waiting for in-flight `on_capturar_elemento` async tasks (screenshot + Gemini call) to finish. Any click whose processing is still running at that moment is discarded.

2. **250ms blind window in JS** — the `mousedown` listener uses `setTimeout(..., 250)` to distinguish single from double clicks. If the browser is closed within that window after the last click, the `setTimeout` never fires and the event is never sent to Python via `capturarElemento`.

The fix must drain all pending async tasks before handing off to `orquestrador_pos_captura`, and must flush any pending `clickTimeout` on the JS side before the browser context is destroyed.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — a capture session where one or more clicks are silently lost because the browser closes before their processing completes or before the JS timer fires.
- **Property (P)**: The desired behavior — every click received by the `capturarElemento` binding, and every click whose `mousedown` fired before browser close, must appear in `cliques_capturados` when `orquestrador_pos_captura` is called.
- **Preservation**: All existing capture behaviors (double-click distinction, iframe injection, right-click, field fill, quality gate) that must remain unchanged by the fix.
- **`on_capturar_elemento`**: The async Python function in `capture.py` that handles each captured click event — takes a screenshot and calls Gemini before appending to `cliques_capturados`.
- **`capturar_cliques_na_tela`**: The main async function in `capture.py` that drives the Playwright session and the polling loop.
- **`orquestrador_pos_captura`**: The async function called after the session ends to invoke Aura and generate the roteiro.
- **`clickTimeout`**: The JS-side `setTimeout` handle (250ms) used to distinguish single from double clicks inside the injected radar script.
- **`_pending_tasks`**: The set of asyncio Tasks wrapping `on_capturar_elemento` calls that must be tracked and awaited on session close.

---

## Bug Details

### Bug Condition

The bug manifests in two distinct sub-conditions that can occur independently or together:

**Sub-condition A — Race condition**: The polling loop in `capturar_cliques_na_tela` exits immediately when `page.is_closed()` is `True`. At that point, one or more `asyncio.Task` objects wrapping `on_capturar_elemento` may still be running (waiting for `page.screenshot()` or the Gemini API). Those tasks are abandoned and their results never reach `cliques_capturados`.

**Sub-condition B — 250ms blind window**: The injected JS radar uses `setTimeout(..., 250)` to defer single-click processing. If the browser is closed within 250ms of the last `mousedown`, the timer is garbage-collected by the browser before it fires, so `window.capturarElemento` is never called for that click.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type CaptureSession
  OUTPUT: boolean

  // Sub-condition A: tasks in-flight when browser closes
  subA ← (X.pending_on_capturar_tasks > 0) AND (X.browser_closed = true)

  // Sub-condition B: last click within 250ms blind window at close time
  subB ← (X.last_mousedown_age_at_close_ms < 250) AND (X.browser_closed = true)

  RETURN subA OR subB
END FUNCTION
```

### Examples

- **Example A1**: User clicks "Salvar" and immediately closes the browser. `on_capturar_elemento` is mid-screenshot when the loop exits. `cliques_capturados` has N-1 entries instead of N. The roteiro is missing the last step.
- **Example A2**: User performs 3 rapid clicks then closes the browser. All 3 tasks are in-flight. `cliques_capturados` ends up empty. `orquestrador_pos_captura` receives an empty list and the quality gate blocks the roteiro.
- **Example B1**: User clicks a button and closes the browser 100ms later. The 250ms `clickTimeout` never fires. Python never receives the event. The click is invisible to the entire pipeline.
- **Edge case**: User double-clicks then closes immediately. The `dblclick` handler fires synchronously (no timeout), so the double-click is captured correctly — only the single-click path is affected by sub-condition B.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Mouse clicks during a normal session (browser not closed immediately after) must continue to be captured with screenshot and Gemini analysis exactly as before.
- Double-click detection via `clickTimeout` cancellation must continue to work correctly.
- Right-click events must continue to be processed immediately without delay.
- Iframe radar injection on `frameattached` and `framenavigated` must continue to work.
- `digitar_e_enter` and `preencher_campo` events must continue to be captured correctly.
- The `_validar_roteiro` quality gate must continue to run before auto-rebuild.
- The `ROTEIRO_GERADO:` protocol line must continue to be printed for `app.py` to parse.

**Scope:**
All inputs that do NOT involve the browser closing while tasks are in-flight or within the 250ms JS window should be completely unaffected by this fix. This includes:
- All clicks captured and fully processed during a normal session
- All non-click events (keyboard, blur, right-click)
- All iframe-originated events
- The entire post-capture pipeline (Aura, roteiro save, quality gate, auto-rebuild)

---

## Hypothesized Root Cause

Based on code inspection of `capture.py`:

1. **No task tracking in `capturar_cliques_na_tela`**: The `expose_binding` callback fires `on_capturar_elemento` as a coroutine, but the polling loop has no reference to the resulting asyncio Tasks. When the loop exits, Python's event loop may cancel or abandon those tasks before they complete. There is no `asyncio.gather` or `asyncio.wait` call before `orquestrador_pos_captura` is invoked.

2. **JS `clickTimeout` has no flush path**: The radar script has no `beforeunload`, `visibilitychange`, or `pagehide` listener that would call `processarEvento` immediately when the page is about to be destroyed. The 250ms timer simply dies with the browser context.

3. **`iniciar_esteira_de_producao` calls `asyncio.run` twice**: `capturar_cliques_na_tela()` and `orquestrador_pos_captura()` run in separate `asyncio.run()` calls. Any tasks created inside the first event loop are destroyed when that loop closes, before the second `asyncio.run()` starts. This makes the race condition structurally guaranteed for any task still running at loop teardown.

4. **No grace period after `page.is_closed()`**: The loop breaks immediately on `page.is_closed()` with no sleep or drain step, giving zero time for in-flight tasks to complete naturally.

---

## Correctness Properties

Property 1: Bug Condition — All Received Clicks Are Persisted

_For any_ capture session where the bug condition holds (browser closes while tasks are in-flight OR within the 250ms JS window), the fixed `capturar_cliques_na_tela` function SHALL ensure that every click event received by the `capturarElemento` binding before browser close is fully processed and present in `cliques_capturados` when `orquestrador_pos_captura` is called.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation — Normal Session Behavior Unchanged

_For any_ capture session where the bug condition does NOT hold (browser closes after all tasks complete and outside the 250ms window), the fixed code SHALL produce exactly the same `cliques_capturados` contents and downstream roteiro as the original code, preserving all existing capture, processing, and post-capture pipeline behavior.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `capture.py`

**Change 1 — Task tracking set**

Add a module-level (or session-scoped) `set` to track all asyncio Tasks created for `on_capturar_elemento`:

```python
_pending_tasks: set[asyncio.Task] = set()
```

Wrap each `on_capturar_elemento` invocation in a tracked task. Since `expose_binding` calls the handler directly as a coroutine, wrap it at the call site or use a thin wrapper that registers and deregisters from `_pending_tasks`.

**Change 2 — Drain pending tasks before exiting the loop**

After the polling loop exits (browser closed), add a drain step before returning from `capturar_cliques_na_tela`:

```python
if _pending_tasks:
    await asyncio.gather(*_pending_tasks, return_exceptions=True)
```

This ensures every in-flight screenshot + Gemini call completes before the function returns.

**Change 3 — JS flush on page close**

Add a `visibilitychange` / `pagehide` listener inside the injected radar script that immediately calls `processarEvento` for any pending `clickTimeout`:

```javascript
const flushPending = () => {
    if (clickTimeout !== null) {
        clearTimeout(clickTimeout);
        clickTimeout = null;
        // re-fire the last captured target synchronously
        if (_lastMousedownTarget) {
            processarEvento(_lastMousedownTarget, 'clique');
        }
    }
};
document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') flushPending();
});
window.addEventListener('pagehide', flushPending);
```

This requires storing the last `mousedown` target in a `_lastMousedownTarget` variable inside the radar script.

**Change 4 — Single asyncio.run with task drain**

Refactor `iniciar_esteira_de_producao` to run both `capturar_cliques_na_tela` and `orquestrador_pos_captura` inside a single `asyncio.run()` call, so tasks created during capture are still alive when the drain step runs:

```python
async def _pipeline(nome_aula, objetivo):
    await capturar_cliques_na_tela()
    if cliques_capturados:
        return await orquestrador_pos_captura(nome_aula, objetivo)
    return None

caminho_roteiro_gerado = asyncio.run(_pipeline(nome_aula, objetivo))
```

**Change 5 — Graceful TargetClosedError handling in drain**

The drain step may encounter `TargetClosedError` for tasks that try to screenshot after the browser is gone. These are already handled inside `on_capturar_elemento` with a `return` guard. Ensure `return_exceptions=True` in `gather` so one failed task does not cancel the others.

---

## Testing Strategy

### Validation Approach

Two-phase approach: first surface counterexamples on unfixed code to confirm root cause, then verify the fix and preservation.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis.

**Test Plan**: Write async unit tests that simulate the race condition by injecting slow `on_capturar_elemento` coroutines and immediately triggering the "browser closed" condition. Run on UNFIXED code to observe that clicks are dropped.

**Test Cases**:
1. **Slow task race test**: Inject a mock `on_capturar_elemento` that sleeps 500ms. Fire 3 click events. Immediately set `page.is_closed()` to `True`. Assert `cliques_capturados` has 3 entries — will FAIL on unfixed code.
2. **250ms window test**: Fire a `mousedown` event in the JS radar. Destroy the page context after 100ms. Assert the click event was received by Python — will FAIL on unfixed code.
3. **Rapid close test**: Fire 5 clicks in quick succession and close immediately. Assert all 5 are in `cliques_capturados` — will FAIL on unfixed code.
4. **Empty session test**: Close browser without any clicks. Assert `cliques_capturados` is empty and `orquestrador_pos_captura` is not called — should PASS on both versions.

**Expected Counterexamples**:
- `cliques_capturados` has fewer entries than clicks fired
- Possible causes: tasks abandoned at loop exit, JS timer destroyed with browser context

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result ← capturar_cliques_na_tela_fixed(X)
  ASSERT len(cliques_capturados) = X.total_clicks_received_by_binding
  ASSERT no_click_silently_dropped(result)
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT capturar_cliques_na_tela_original(X) = capturar_cliques_na_tela_fixed(X)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many session configurations automatically
- It catches edge cases around task timing that manual tests miss
- It provides strong guarantees that normal-session behavior is unchanged

**Test Cases**:
1. **Normal session preservation**: Simulate 10 clicks with 1s gaps, close browser after all tasks complete. Verify `cliques_capturados` is identical before and after fix.
2. **Double-click preservation**: Simulate a double-click sequence. Verify only `duplo_clique` is recorded, not a spurious `clique`.
3. **Right-click preservation**: Simulate right-click. Verify `clique_direito` is captured immediately.
4. **Field fill preservation**: Simulate `blur` on an input with a value. Verify `preencher_campo` is captured.
5. **Quality gate preservation**: Verify `_validar_roteiro` still runs and blocks auto-rebuild on low-quality roteiros.

### Unit Tests

- Test that `_pending_tasks` is populated when `on_capturar_elemento` is invoked
- Test that the drain step awaits all tasks before returning
- Test that `TargetClosedError` in a drained task does not prevent other tasks from completing
- Test the JS `flushPending` function fires `processarEvento` when `visibilitychange` fires with `hidden`
- Test edge case: drain with zero pending tasks is a no-op

### Property-Based Tests

- Generate random numbers of concurrent slow tasks (0–20) and verify all complete before `orquestrador_pos_captura` is called
- Generate random click sequences with random close timing and verify `cliques_capturados` count matches received events
- Generate random non-click events and verify they are unaffected by the task drain change

### Integration Tests

- Full capture session: perform 5 clicks, close browser, verify roteiro has 5 steps
- Rapid close: perform 1 click and close within 100ms, verify the click appears in the roteiro
- Normal session end-to-end: verify roteiro save, quality gate, and auto-rebuild all still work correctly after fix

# capture-missed-clicks — Task List

## Tasks

- [x] 1. Exploratory testing on unfixed code
  - [x] 1.1 Write async unit test: slow task race — inject a mock `on_capturar_elemento` that sleeps 500ms, fire 3 click events, trigger browser close, assert `cliques_capturados` has 3 entries (expected to FAIL on unfixed code, confirming root cause A)
  - [x] 1.2 Write unit test: 250ms blind window — simulate `mousedown` in JS radar, destroy page context after 100ms, assert click event was received by Python (expected to FAIL on unfixed code, confirming root cause B)
  - [x] 1.3 Write unit test: rapid close — fire 5 clicks in quick succession and close immediately, assert all 5 are in `cliques_capturados` (expected to FAIL on unfixed code)
  - [x] 1.4 Run exploratory tests on unfixed code and document observed failures to confirm root cause analysis

- [x] 2. Fix sub-condition A — drain pending async tasks on session close
  - [x] 2.1 Add `_pending_tasks: set[asyncio.Task]` module-level set to `capture.py` for tracking in-flight tasks
  - [x] 2.2 Wrap `on_capturar_elemento` invocations in tracked asyncio Tasks that register/deregister from `_pending_tasks`
  - [x] 2.3 Add drain step after the polling loop exits: `await asyncio.gather(*_pending_tasks, return_exceptions=True)` before returning from `capturar_cliques_na_tela`
  - [x] 2.4 Refactor `iniciar_esteira_de_producao` to run `capturar_cliques_na_tela` and `orquestrador_pos_captura` inside a single `asyncio.run()` call so tasks created during capture are still alive during the drain step

- [x] 3. Fix sub-condition B — flush JS clickTimeout on page close
  - [x] 3.1 Add `_lastMousedownTarget` variable to the radar script to store the last `mousedown` target
  - [x] 3.2 Add `flushPending` function inside the radar script that clears `clickTimeout` and calls `processarEvento` synchronously for the stored target
  - [x] 3.3 Attach `flushPending` to `document visibilitychange` (when `hidden`) and `window pagehide` events inside the radar script

- [x] 4. Fix checking — verify the fix works for all buggy inputs
  - [x] 4.1 Run the exploratory tests from task 1 against the fixed code and assert they now PASS (Property 1)
  - [x] 4.2 Write and run fix-checking test: simulate slow tasks + immediate close, assert `cliques_capturados` count equals total clicks fired
  - [x] 4.3 Write and run fix-checking test: simulate click within 250ms window before close, assert click appears in `cliques_capturados`

- [x] 5. Preservation checking — verify normal session behavior is unchanged
  - [x] 5.1 Write preservation test: normal session with 10 clicks and 1s gaps — verify `cliques_capturados` is identical before and after fix (Property 2)
  - [x] 5.2 Write preservation test: double-click sequence — verify only `duplo_clique` is recorded, no spurious `clique`
  - [x] 5.3 Write preservation test: right-click — verify `clique_direito` is captured immediately without delay
  - [x] 5.4 Write preservation test: field fill via `blur` — verify `preencher_campo` is captured correctly
  - [x] 5.5 Write preservation test: `_validar_roteiro` quality gate still blocks auto-rebuild on low-quality roteiros
  - [x] 5.6 Write preservation test: drain with zero pending tasks is a no-op (no error, no behavior change)

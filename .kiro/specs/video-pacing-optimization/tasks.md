# Implementation Plan: Video Pacing Optimization

## Overview

This plan implements pacing optimization for Senior Training OS video generation by modifying two core modules: `cursor_engine.py` (duration/step calculations, pacing profiles) and `main.py` (concurrent narration+movement, action classification, intelligent pauses). The approach introduces pure functions for testability, a data-driven pacing profile system, and asyncio-based concurrency for narration overlap.

## Tasks

- [x] 1. Introduce PacingProfile dataclass and profile resolution
  - [x] 1.1 Create PacingProfile dataclass and PROFILES dictionary in cursor_engine.py
    - Add `PacingProfile` frozen dataclass with fields: name, cursor_base_ms, cursor_min_ms, cursor_max_ms, safe_pause_min, safe_pause_max, steps_per_pixel, steps_min, steps_max
    - Define PROFILES dict with "fast", "normal", and "conservative" entries using constants from the design
    - Place after existing constants block, before the Bézier math section
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 1.2 Implement resolve_pacing_profile function in cursor_engine.py
    - Add `resolve_pacing_profile(configuracao_gravacao: dict) -> PacingProfile` function
    - Default to "fast" when key is missing, log warning and fall back to "fast" for invalid values
    - _Requirements: 8.5, 8.6_

  - [x]* 1.3 Write property test for profile resolution (Property 10)
    - **Property 10: Profile resolution correctness**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

- [x] 2. Implement new cursor duration and step-count calculations
  - [x] 2.1 Implement calcular_duracao_movimento pure function in cursor_engine.py
    - Add `calcular_duracao_movimento(distance: float, profile: PacingProfile) -> int`
    - Return 0 for distance < 3 (skip signal)
    - Apply formula: `base = profile.cursor_base_ms * (distance / 400) ** 0.55`
    - Clamp to [cursor_min_ms, cursor_max_ms], apply random factor 0.92–1.08, re-clamp
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 2.2 Implement calcular_passos_movimento pure function in cursor_engine.py
    - Add `calcular_passos_movimento(distance: float, profile: PacingProfile) -> int`
    - Formula: `clamp(distance * profile.steps_per_pixel, profile.steps_min, profile.steps_max)`
    - _Requirements: 2.1, 2.2, 2.3_

  - [x]* 2.3 Write property tests for duration calculation (Properties 1, 2, 3, 11)
    - **Property 1: Duration bounds hold for all distances and profiles**
    - **Property 2: Short-distance duration cap**
    - **Property 3: Trivial distance produces zero duration**
    - **Property 11: Duration formula matches specification**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

  - [x]* 2.4 Write property test for step count calculation (Property 5)
    - **Property 5: Step count formula correctness**
    - **Validates: Requirements 2.1, 2.2, 2.3**

- [x] 3. Refactor mover_cursor_humanizado to use PacingProfile
  - [x] 3.1 Modify mover_cursor_humanizado to accept optional profile parameter
    - Add `profile: Optional[PacingProfile] = None` parameter
    - When profile is provided and duracao_ms is None, use `calcular_duracao_movimento` instead of module-level constants
    - Use `calcular_passos_movimento` for step count when profile is provided
    - Preserve existing behavior when profile is None (backward compatibility)
    - Enforce minimum inter-step delay of 8ms in the animation loop
    - Preserve existing Bézier curve generation, overshoot (15% chance, ≤5px), and jitter (≤2px)
    - Preserve the `window.updateRoboCursor` call per step, continuing on failure
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 2.1, 2.2, 2.3, 2.4, 5.2, 5.3, 5.5_

  - [x]* 3.2 Write property tests for animation constraints (Properties 4, 6, 12)
    - **Property 4: Overshoot magnitude and jitter are bounded**
    - **Property 6: Cubic-in-out easing is monotonic and bounded**
    - **Property 12: Minimum inter-step delay**
    - **Validates: Requirements 1.7, 2.4, 5.3**

- [x] 4. Checkpoint - Cursor engine changes
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement action classification and pause calculation in main.py
  - [x] 5.1 Add ActionClassification enum and classificar_acao function in main.py
    - Create `ActionClassification` enum with SAFE and SENSITIVE values
    - Implement `classificar_acao(acao_tec: dict, passo: dict) -> ActionClassification` as a pure function
    - Classification rules: duplo_clique → SENSITIVE; tipo_passo in (navigation, navegacao, page_refresh) → SENSITIVE; pause_sugerida > 3.0 → SENSITIVE; aguarda_carregamento == True → SENSITIVE; else → SAFE
    - If multiple rules match, SENSITIVE takes precedence (any match returns SENSITIVE)
    - _Requirements: 4.3, 4.4, 4.5, 4.6, 4.7_

  - [x] 5.2 Add calcular_pausa_pos_acao function in main.py
    - Implement `calcular_pausa_pos_acao(classification, pause_sugerida, profile) -> float`
    - SENSITIVE → return unmodified pause_sugerida
    - SAFE → return random.uniform(profile.safe_pause_min, profile.safe_pause_max)
    - _Requirements: 4.1, 4.2, 7.2, 7.5_

  - [x]* 5.3 Write property tests for action classification and pause (Properties 7, 8, 9)
    - **Property 7: Action classification correctness**
    - **Property 8: Safe action pause is bounded**
    - **Property 9: Sensitive action pause preserves pause_sugerida**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.2, 7.5**

- [x] 6. Implement concurrent narration and cursor movement
  - [x] 6.1 Create _executar_acao_com_narracao coroutine in main.py
    - Implement concurrent execution using asyncio.gather/create_task
    - When micro_narracao is present and action is NOT clique_direito: start narration + cursor move concurrently
    - Wait for cursor move to complete; wait for narration with 15s timeout (proceed on timeout)
    - When narration is absent or action is clique_direito: execute cursor move only, skip narration
    - If narration audio fails to load/play, proceed with movement and click without waiting
    - Execute click action after both tasks complete
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6_

  - [x] 6.2 Preserve sequential behavior for anchor narrations
    - Ensure pedagogia.ancora narrations play fully and complete before proceeding to step actions
    - Do not apply concurrent overlap to anchor narrations
    - _Requirements: 3.4_

- [x] 7. Integrate pacing profile into execution loop
  - [x] 7.1 Modify executar_roteiro to resolve and apply pacing profile
    - Read `pacing_profile` from `configuracao_gravacao` at execution start
    - Call `resolve_pacing_profile` to get the PacingProfile instance
    - Pass profile to `mover_cursor_humanizado` and pause calculation throughout the execution loop
    - Apply profile consistently to all steps within the same execution run
    - Replace the current pause formula `min(pause_sugerida * 0.3, 0.8)` with `calcular_pausa_pos_acao` using the action classification
    - _Requirements: 8.5, 8.7_

  - [x] 7.2 Integrate action classification into the execution loop
    - Call `classificar_acao` for each action before applying post-action pause
    - Use classification result with `calcular_pausa_pos_acao` to determine actual pause duration
    - Ensure sensitive actions (double-click, navigation, page refresh, high pause_sugerida) get full pause_sugerida
    - Ensure safe actions get the profile-bounded short pause
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

- [x] 8. Preserve screen capture, double-click, and page load timing
  - [x] 8.1 Enforce screen capture timing constraints
    - Ensure minimum 16ms inter-action interval between consecutive visual state changes during recording
    - Ensure 200ms wait after cursor movement completes before screenshot/screen mapping operations
    - _Requirements: 5.1, 5.4_

  - [x] 8.2 Preserve double-click and complex interaction timing
    - Do NOT reduce inter-click interval for double-click actions
    - Ensure context menu follow-up click executes within 500ms after right-click
    - Do NOT reduce overshoot correction phase duration for any click action
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 8.3 Preserve page load and refresh wait behavior
    - Maintain 30-second timeout on wait_for_load_state("load") for navigation/refresh
    - Do NOT reduce waits tied to wait_for_load_state or wait_for calls
    - Log timeout events and proceed without retry when 30s timeout is exceeded
    - _Requirements: 7.1, 7.3, 7.4, 7.5_

- [x] 9. Checkpoint - Full integration
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Unit and integration tests
  - [x]* 10.1 Write unit tests for narration and timing edge cases
    - Test: anchor narration remains sequential (Req 3.4)
    - Test: right-click skips micro-narration (Req 3.5)
    - Test: audio failure does not block execution (Req 3.6)
    - Test: double-click inter-click interval unchanged (Req 6.1)
    - Test: context menu follow-up within 500ms (Req 6.2)
    - Test: default profile is "fast" when key is missing (Req 8.5)
    - Test: page load timeout logs and proceeds (Req 7.4)
    - _Requirements: 3.4, 3.5, 3.6, 6.1, 6.2, 7.4, 8.5_

  - [x]* 10.2 Write integration tests for concurrent execution flow
    - Test: concurrent narration + cursor movement coordination (Req 3.1, 3.2, 3.3)
    - Test: screenshot waits 200ms after cursor movement completes (Req 5.4)
    - Test: page navigation waits are preserved during pacing optimization (Req 7.1, 7.3)
    - Test: full execution with "fast" profile applies correct constants throughout
    - _Requirements: 3.1, 3.2, 3.3, 5.4, 7.1, 7.3, 8.7_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation modifies only `cursor_engine.py` and `main.py` — no new files needed beyond tests
- Backward compatibility is preserved: when no profile is passed, existing behavior is unchanged
- Hypothesis is already available in the project (`.hypothesis/` directory exists)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "2.4", "3.1"] },
    { "id": 3, "tasks": ["3.2", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "6.1", "6.2"] },
    { "id": 5, "tasks": ["7.1", "7.2"] },
    { "id": 6, "tasks": ["8.1", "8.2", "8.3"] },
    { "id": 7, "tasks": ["10.1", "10.2"] }
  ]
}
```

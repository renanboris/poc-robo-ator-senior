# Requirements Document

## Introduction

This feature optimizes the pacing of automatically generated training videos produced by Senior Training OS. The current system produces videos that feel robotic and slow — cursor movements take too long, pauses between steps accumulate unnecessarily, and narration blocks cursor movement sequentially. The result is videos that take roughly 2x longer than they should, violating the microlearning philosophy of "short, fast content — watch again if needed." This optimization must reduce total video duration without compromising screen capture quality, screenshot operations, double-click reliability, or page load/refresh stability.

## Glossary

- **Cursor_Engine**: The module (`cursor_engine.py`) responsible for humanized cursor movement using Bézier curves, controlling duration, steps, overshoot, and jitter.
- **Execution_Engine**: The module (`main.py`) responsible for replaying the roteiro, coordinating narration, cursor movement, pauses, and screen recording.
- **Narration_Audio**: The TTS-generated audio (via edge-tts or ElevenLabs) that accompanies each step or action in the video.
- **Pause_Sugerida**: The per-step pause value defined in the roteiro JSON, currently defaulting to 2.5 seconds with a formula `min(pause_sugerida * 0.3, 0.8)` applied at runtime.
- **Speed_Ramp**: A technique where cursor movement accelerates through uninteresting space and decelerates near points of interest.
- **Overlap_Window**: The time period during which narration audio plays concurrently with cursor movement, rather than sequentially.
- **Safe_Action**: An action (single click, navigation, typing) that does not require extended timing for reliability.
- **Sensitive_Action**: An action (double-click, page refresh wait, screenshot capture, screen mapping) that requires preserved or extended timing to function correctly.
- **Dead_Air**: Periods in the video where nothing meaningful happens — no narration, no cursor movement, no visual change.

## Requirements

### Requirement 1: Reduce Cursor Movement Duration

**User Story:** As a training consumer, I want cursor movements to feel natural and brisk, so that I do not lose attention waiting for the cursor to reach its target.

#### Acceptance Criteria

1. WHEN a cursor movement is initiated, THE Cursor_Engine SHALL calculate the base duration using the formula `base_ms = 600 * (distance / 400) ^ 0.55`, where distance is the Euclidean pixel distance between origin and target.
2. THE Cursor_Engine SHALL enforce a minimum movement duration of 300ms regardless of calculated duration.
3. THE Cursor_Engine SHALL enforce a maximum movement duration of 1400ms regardless of calculated duration.
4. THE Cursor_Engine SHALL apply a randomization factor between 0.92 and 1.08 to the calculated duration, clamping the final result to the 300ms–1400ms bounds.
5. WHEN the distance between origin and target is less than 150 pixels, THE Cursor_Engine SHALL complete the movement within 450ms (before randomization factor is applied).
6. IF the distance between origin and target is less than 3 pixels, THEN THE Cursor_Engine SHALL skip the movement entirely without animating.
7. THE Cursor_Engine SHALL preserve the existing Bézier curve control-point generation, overshoot chance of 15% for distances greater than 60 pixels, overshoot magnitude up to 5 pixels, and per-step jitter of up to 2 pixels.

### Requirement 2: Reduce Step Count for Cursor Animation

**User Story:** As a training consumer, I want smooth but efficient cursor animations, so that the video feels responsive without visible frame skipping.

#### Acceptance Criteria

1. THE Cursor_Engine SHALL use a minimum of 12 animation steps per movement.
2. THE Cursor_Engine SHALL use a maximum of 50 animation steps per movement.
3. THE Cursor_Engine SHALL calculate intermediate step counts using a ratio of 0.06 steps per pixel of movement distance, clamped to the minimum and maximum bounds.
4. THE Cursor_Engine SHALL apply the cubic-in-out easing function for time parameterization of Bézier interpolation across all animation steps, regardless of step count.

### Requirement 3: Overlap Narration with Cursor Movement

**User Story:** As a training consumer, I want narration to play while the cursor is already moving, so that the video feels like a real instructor demonstrating software.

#### Acceptance Criteria

1. WHEN an action has a non-empty micro_narracao field, THE Execution_Engine SHALL start audio playback and cursor movement within the same execution step, such that both are in progress simultaneously.
2. WHEN narration finishes before cursor movement completes, THE Execution_Engine SHALL continue cursor movement to completion without inserting any pause between narration end and movement end.
3. WHEN cursor movement finishes before narration completes, THE Execution_Engine SHALL wait for narration to finish before executing the click action, up to a maximum wait of 15 seconds, after which it SHALL proceed with the click regardless.
4. THE Execution_Engine SHALL preserve the sequential behavior for anchor narrations (pedagogia.ancora), playing them fully and waiting for audio completion before proceeding to the step's actions.
5. IF the current action is a clique_direito, THEN THE Execution_Engine SHALL skip micro-narration playback for that action and execute the click without narration delay, so that the subsequent context menu item can be clicked within the 500ms menu dismissal window defined in Requirement 6.
6. IF narration audio fails to load or play, THEN THE Execution_Engine SHALL proceed with cursor movement and click execution without waiting for audio.

### Requirement 4: Eliminate Excessive Inter-Action Pauses

**User Story:** As a training consumer, I want minimal dead air between actions, so that the video maintains engagement and respects my time.

#### Acceptance Criteria

1. WHEN a safe action completes, THE Execution_Engine SHALL apply a post-action pause of no less than 0.1 seconds and no more than 0.3 seconds before proceeding to the next action.
2. WHEN a sensitive action completes, THE Execution_Engine SHALL apply the unmodified pause_sugerida value from the roteiro (bypassing the reduction formula) to allow UI stabilization.
3. THE Execution_Engine SHALL classify double-click actions as sensitive actions requiring preserved timing.
4. THE Execution_Engine SHALL classify an action as sensitive when the roteiro step's tipo_passo field indicates navigation, or when the action is immediately followed by a wait_for_load_state call in the execution flow.
5. WHEN the roteiro specifies a pause_sugerida value greater than 3.0 seconds, THE Execution_Engine SHALL treat the step as containing a sensitive action regardless of action type.
6. IF an action matches both safe and sensitive classification rules, THEN THE Execution_Engine SHALL apply the sensitive action pause (the higher pause value takes precedence).
7. THE Execution_Engine SHALL classify any action not matching criteria 3, 4, or 5 as a safe action.

### Requirement 5: Preserve Screen Capture and Mapping Quality

**User Story:** As a system operator, I want the pacing optimization to preserve the reliability of screen capture, so that video output remains correct and complete.

#### Acceptance Criteria

1. WHILE a screen recording is active, THE Execution_Engine SHALL enforce a minimum inter-action interval of 16ms (one frame at 60fps) between any two consecutive visual state changes to allow the video encoder to capture all transitions in the 1920x1080 recording.
2. THE Cursor_Engine SHALL invoke the per-frame DOM update call (`window.updateRoboCursor`) exactly once per animation step, for every step in the movement sequence, to ensure the neon cursor position is rendered in the recording.
3. WHILE the cursor is moving, THE Cursor_Engine SHALL maintain a minimum inter-step delay of 8ms to prevent frame dropping in the 1920x1080 video capture.
4. IF a screenshot or screen mapping operation is scheduled, THEN THE Execution_Engine SHALL complete the currently active cursor movement in full and wait 200ms after the final cursor position is reached before the capture operation begins.
5. IF the `window.updateRoboCursor` call fails during a cursor movement step, THEN THE Cursor_Engine SHALL continue the remaining movement steps without interruption and without retrying the failed DOM update.

### Requirement 6: Preserve Double-Click and Complex Interaction Timing

**User Story:** As a system operator, I want double-click and complex interactions to retain their timing requirements, so that the ERP application registers them correctly.

#### Acceptance Criteria

1. WHEN a double-click action is executed, THE Execution_Engine SHALL preserve the existing inter-click interval without reduction.
2. WHEN a context menu item must be clicked after a right-click, THE Execution_Engine SHALL execute the follow-up click within 500ms to prevent menu dismissal.
3. THE Execution_Engine SHALL NOT reduce the overshoot correction phase duration for any click action.

### Requirement 7: Preserve Page Load and Refresh Wait Behavior

**User Story:** As a system operator, I want page load waits to remain intact, so that the robot does not interact with elements before the UI has stabilized.

#### Acceptance Criteria

1. WHEN a navigation or page refresh occurs, THE Execution_Engine SHALL wait for the page load state to reach "load" with a timeout of 30 seconds before proceeding with the next action.
2. WHEN the roteiro step includes an explicit wait indicator (pause_sugerida >= 3.0s or action type is "navigation" or "page_refresh"), THE Execution_Engine SHALL apply the unmodified pause_sugerida value as the wait duration, bypassing the reduction formula.
3. THE Execution_Engine SHALL NOT reduce any wait that is explicitly tied to a `wait_for_load_state` or `wait_for` call in the execution flow.
4. IF the page load state does not reach "load" within the 30-second timeout, THEN THE Execution_Engine SHALL log the timeout event and proceed with the next action without retrying the wait.
5. WHEN the pacing optimization reduces inter-action pauses, THE Execution_Engine SHALL preserve the original duration of any wait that guards a page navigation, page refresh, or UI state transition triggered by a prior action.

### Requirement 8: Configurable Pacing Profile

**User Story:** As a system operator, I want to control the pacing aggressiveness, so that I can tune the optimization for different training contexts without code changes.

#### Acceptance Criteria

1. THE Execution_Engine SHALL support a pacing profile parameter within the roteiro `configuracao_gravacao` section, accepting the values "fast", "normal", and "conservative".
2. WHERE the pacing profile is "fast", THE Cursor_Engine SHALL use the reduced duration constants (base 600ms, min 300ms, max 1400ms) and THE Execution_Engine SHALL use 0.3s inter-action pauses for safe actions.
3. WHERE the pacing profile is "normal", THE Cursor_Engine SHALL use moderate duration constants (base 900ms, min 400ms, max 1800ms) and THE Execution_Engine SHALL use 0.5s inter-action pauses for safe actions.
4. WHERE the pacing profile is "conservative", THE Cursor_Engine SHALL use the current duration constants (base 1200ms, min 500ms, max 2500ms) and THE Execution_Engine SHALL apply the pause formula `min(pause_sugerida * 0.3, 0.8)` for safe actions.
5. THE Execution_Engine SHALL default to the "fast" pacing profile when no profile is specified in the roteiro.
6. IF the pacing profile parameter contains a value other than "fast", "normal", or "conservative", THEN THE Execution_Engine SHALL fall back to the "fast" profile and log a warning message indicating the invalid value received.
7. WHEN the Execution_Engine reads the pacing profile at the start of roteiro execution, THE Execution_Engine SHALL apply that profile consistently to all steps within the same execution run.

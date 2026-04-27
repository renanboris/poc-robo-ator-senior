# Bugfix Requirements Document

## Introduction

The coordinates layer (`2_coords_capturadas`) in `vision_engine.py` executes clicks BEFORE verifying element identity, causing it to always report success even when clicking the wrong element. This prevents fallback layers (3, 4, 5) from executing and causes the Brain to learn incorrect coordinates, breaking automation reliability for workflows that have worked for months.

**Impact:**
- High: Breaks automation reliability for production workflows
- High: Prevents self-healing (layers 3, 4, 5 never execute)
- High: Brain learns wrong coordinates, degrading future executions
- High: Roteiros that worked reliably suddenly fail

**Root Cause:**
The order of operations is inverted. Identity verification happens AFTER the click at line ~1970, but the click is executed at line ~1965. If identity fails, the wrong click has already been executed and the function returns True because the click didn't throw an exception.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `coords_relativas` and `label_curto` are present THEN the system executes `_clicar_por_coordenadas()` immediately at line ~1965

1.2 WHEN the click completes without exception THEN the system performs identity verification AFTER the click has already been executed

1.3 WHEN identity verification fails (wrong element clicked) THEN the system has already executed the wrong click and cannot undo it

1.4 WHEN the click doesn't throw an exception THEN the system returns True (success) regardless of whether the correct element was clicked

1.5 WHEN the coordinates layer returns True THEN fallback layers 3, 4, and 5 are never reached

1.6 WHEN a wrong click is reported as successful THEN the Brain learns incorrect coordinates for that action

1.7 WHEN the Brain has incorrect coordinates THEN future executions of the same action fail with low success rates (e.g., 9.3% as shown in logs)

### Expected Behavior (Correct)

2.1 WHEN `coords_relativas` and `label_curto` are present THEN the system SHALL calculate target coordinates from `coords_relativas`

2.2 WHEN target coordinates are calculated THEN the system SHALL verify element identity at those coordinates BEFORE executing any click

2.3 WHEN identity verification succeeds (element matches `label_curto`) THEN the system SHALL execute the click and return True

2.4 WHEN identity verification fails (element does not match `label_curto`) THEN the system SHALL skip the click, register telemetry failure, and escalate to the next fallback layer

2.5 WHEN the coordinates layer escalates to the next layer THEN layers 3, 4, and 5 SHALL have the opportunity to execute

2.6 WHEN a click is executed THEN the system SHALL only return True if BOTH identity verification AND click execution succeed

2.7 WHEN the Brain receives success feedback THEN it SHALL only be for clicks that hit the correct element

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `label_curto` is empty or None THEN the system SHALL CONTINUE TO use fail-open behavior (accept the click without identity verification)

3.2 WHEN identity verification encounters an exception THEN the system SHALL CONTINUE TO use fail-open behavior (accept the click)

3.3 WHEN an iframe is cross-origin THEN the system SHALL CONTINUE TO use fail-open behavior (accept the click)

3.4 WHEN `iframe_hint` is provided and valid THEN the system SHALL CONTINUE TO use it for context resolution

3.5 WHEN coordinates are adjusted for iframe offset THEN the system SHALL CONTINUE TO apply the adjustment correctly

3.6 WHEN telemetry is registered THEN the system SHALL CONTINUE TO record success/failure for the `2_coords_capturadas` layer

3.7 WHEN the winning strategy is registered THEN the system SHALL CONTINUE TO record `2_coords_capturadas` as the resolver

3.8 WHEN other layers (Sniper, Hint, Brain, Brute Force) execute THEN the system SHALL CONTINUE TO operate with their existing behavior unchanged

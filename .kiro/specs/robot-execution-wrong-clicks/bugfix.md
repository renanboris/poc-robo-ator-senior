# Bugfix Requirements Document

## Introduction

The robot is clicking on wrong elements inside iframes due to three critical bugs in the iframe detection and resolution logic in `vision_engine.py`. Despite iframe detection being implemented, the system fails to correctly resolve iframe contexts, adjust coordinates, and identify target elements, resulting in a 4.2% success rate (1/24 attempts) and escalation to Gemini Vision which hits rate limits.

## Bug Analysis

### Current Behavior (Defect)

**Bug 1: iframe_hint Resolution Failure**

1.1 WHEN `iframe_hint` is provided (e.g., "ci") THEN `_resolver_contexto()` returns a `FrameLocator` object instead of a `Frame` object

1.2 WHEN the code checks `hasattr(contexto, 'url')` to detect if the context is a Frame THEN the check fails because `FrameLocator` does not have a `url` attribute

1.3 WHEN the Frame detection check fails THEN the system logs "iframe_hint não resolveu para Frame - usando detecção automática" and falls back to automatic detection, ignoring the provided iframe_hint

**Bug 2: Coordinate Adjustment Incorrect**

1.4 WHEN automatic iframe detection is triggered as fallback THEN `_resolver_elemento_em_iframe()` is called with the original page coordinates

1.5 WHEN `_resolver_elemento_em_iframe()` executes `elementFromPoint` THEN it executes in the main page context instead of inside the detected iframe context

1.6 WHEN coordinates are adjusted for the iframe THEN the Y coordinate remains unchanged (e.g., 732 → 732) suggesting `bbox.top = 0`, which indicates incorrect bounding box detection or coordinate transformation

**Bug 3: Wrong Element Found**

1.7 WHEN `elementFromPoint` is executed after coordinate adjustment THEN it returns a parent container element instead of the specific target button

1.8 WHEN the element text is retrieved THEN it contains multiple elements' text (e.g., "SIGN\nCaixa de Entrada\nFILTRAR DADOS\nNome do envelo") instead of the target element text ("Acompanhar assinaturas")

1.9 WHEN identity verification compares expected vs found text THEN verification fails because the wrong element was identified

1.10 WHEN identity verification fails THEN the system escalates to Gemini Vision (layer 2), which hits rate limit (429 error)

### Expected Behavior (Correct)

**Bug 1 Fix: iframe_hint Resolution**

2.1 WHEN `iframe_hint` is provided (e.g., "ci") and is not a generic value THEN `_resolver_contexto()` SHALL return a usable `Frame` object (not `FrameLocator`)

2.2 WHEN the code checks if the context is a Frame THEN it SHALL correctly identify `Frame` objects and use them for subsequent operations

2.3 WHEN a valid `Frame` is resolved from `iframe_hint` THEN the system SHALL NOT fall back to automatic detection

**Bug 2 Fix: Coordinate Adjustment**

2.4 WHEN iframe context is resolved THEN the system SHALL obtain the correct iframe bounding box from the main page context

2.5 WHEN coordinates are adjusted for iframe context THEN both X and Y coordinates SHALL be correctly transformed relative to the iframe's position (e.g., if iframe is at (65, 0), then (1633, 732) → (1568, 732) for X, and Y should also adjust if iframe.top ≠ 0)

2.6 WHEN `elementFromPoint` is executed THEN it SHALL execute in the correct iframe context using the adjusted coordinates

**Bug 3 Fix: Correct Element Identification**

2.7 WHEN `elementFromPoint` is executed with adjusted coordinates in the correct iframe context THEN it SHALL return the specific target element, not a parent container

2.8 WHEN the element text is retrieved THEN it SHALL match the expected target element text (e.g., "Acompanhar assinaturas")

2.9 WHEN identity verification compares expected vs found text THEN verification SHALL succeed for the correct element

2.10 WHEN identity verification succeeds THEN the system SHALL NOT escalate to Gemini Vision and SHALL report success

### Unchanged Behavior (Regression Prevention)

**Preserve Existing Functionality**

3.1 WHEN `iframe_hint` is not provided or is a generic value ("Pagina Principal", "Página Principal", "iframe-cross-origin") THEN the system SHALL CONTINUE TO use automatic iframe detection

3.2 WHEN automatic iframe detection encounters a cross-origin iframe THEN the system SHALL CONTINUE TO apply fail-open behavior and accept the click without identity verification

3.3 WHEN `label_curto` is empty or not provided THEN the system SHALL CONTINUE TO skip identity verification (fail-open)

3.4 WHEN coordinates are used in the main page context (no iframe) THEN the system SHALL CONTINUE TO execute `elementFromPoint` directly without coordinate adjustment

3.5 WHEN nested iframes are detected THEN the system SHALL CONTINUE TO recursively resolve elements up to `max_depth` levels

3.6 WHEN `max_depth` is reached during recursive iframe resolution THEN the system SHALL CONTINUE TO return the current element without further recursion

3.7 WHEN iframe resolution fails due to exceptions THEN the system SHALL CONTINUE TO log warnings and return safe fallback values

3.8 WHEN the robot executes clicks outside of iframes THEN the system SHALL CONTINUE TO work correctly without regression

# Robot Execution Wrong Clicks Bugfix Design

## Overview

The robot is clicking on wrong elements inside iframes due to three critical bugs in the iframe detection and resolution logic in `vision_engine.py`. The system has iframe detection implemented but fails at three critical points: (1) `_resolver_contexto()` returns `FrameLocator` instead of `Frame`, causing context resolution to fail, (2) coordinates are not adjusted correctly for iframe context, and (3) `elementFromPoint` finds parent containers instead of target elements. This results in a 4.2% success rate (1/24 attempts) and escalation to Gemini Vision which hits rate limits. The fix will ensure iframe_hint correctly resolves to Frame objects, coordinates are properly adjusted for iframe context, and the correct target element is identified for identity verification.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when iframe_hint is provided and the robot needs to click inside an iframe
- **Property (P)**: The desired behavior when iframe_hint is provided - the system should resolve the correct Frame, adjust coordinates, and identify the target element
- **Preservation**: Existing automatic iframe detection, fail-open behavior for cross-origin iframes, and non-iframe click behavior that must remain unchanged by the fix
- **_resolver_contexto()**: The function in `vision_engine.py` (lines 597-625) that resolves iframe context from iframe_hint
- **_resolver_elemento_em_iframe()**: The function in `vision_engine.py` (lines 1267-1468) that recursively detects iframes and adjusts coordinates
- **iframe_hint**: The metadata field that identifies which iframe contains the target element (e.g., "ci" for Senior X's content iframe)
- **FrameLocator**: Playwright's lazy iframe selector that does not provide direct access to Frame properties like `url`
- **Frame**: Playwright's actual frame object that provides `url`, `name`, and `evaluate()` methods for executing JavaScript in the frame context

## Bug Details

### Bug Condition

The bug manifests when the robot attempts to click inside an iframe using captured coordinates and iframe_hint metadata. The `_resolver_contexto()` function returns a `FrameLocator` object instead of a `Frame` object, causing the subsequent `hasattr(contexto, 'url')` check to fail. This triggers fallback to automatic detection, which then fails to adjust coordinates correctly and identifies the wrong element.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ClickAction with iframe_hint and coords_relativas
  OUTPUT: boolean
  
  RETURN input.iframe_hint IS NOT NULL
         AND input.iframe_hint NOT IN ['Pagina Principal', 'Página Principal', 'iframe-cross-origin']
         AND input.coords_relativas IS NOT NULL
         AND targetElementIsInsideIframe(input.iframe_hint)
END FUNCTION
```

### Examples

- **Example 1**: Click on "Acompanhar assinaturas" button inside Senior X's "ci" iframe at coordinates (1633, 732)
  - **Expected**: System resolves "ci" iframe, adjusts coordinates to (1568, 732), finds button element with text "Acompanhar assinaturas", identity verification succeeds
  - **Actual**: System returns FrameLocator, falls back to automatic detection, coordinates remain (1633, 732), finds parent container with text "SIGN\nCaixa de Entrada\nFILTRAR DADOS\n...", identity verification fails, escalates to Gemini Vision

- **Example 2**: Click on "Filtrar" button inside "ci" iframe at coordinates (800, 400)
  - **Expected**: System resolves "ci" iframe, adjusts coordinates relative to iframe position, finds "Filtrar" button, verification succeeds
  - **Actual**: FrameLocator returned, automatic detection triggered, wrong coordinates used, wrong element found, verification fails

- **Example 3**: Click on button in nested iframe (iframe inside iframe)
  - **Expected**: System resolves outer iframe from iframe_hint, then recursively resolves inner iframe, adjusts coordinates through both transformations, finds correct element
  - **Actual**: FrameLocator returned for outer iframe, automatic detection may or may not work depending on iframe accessibility

- **Edge Case**: Click on element in cross-origin iframe with iframe_hint
  - **Expected**: System attempts to resolve iframe_hint, detects cross-origin restriction, applies fail-open behavior (accepts click without verification)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Automatic iframe detection must continue to work when iframe_hint is not provided or is generic
- Fail-open behavior for cross-origin iframes must continue to work (accept click without verification)
- Clicks in main page context (no iframe) must continue to work without coordinate adjustment
- Recursive iframe resolution for nested iframes must continue to work up to max_depth
- Error handling and logging for iframe resolution failures must continue to work
- Identity verification skip when label_curto is empty must continue to work

**Scope:**
All inputs that do NOT involve a specific iframe_hint (non-generic values) should be completely unaffected by this fix. This includes:
- Clicks with no iframe_hint provided
- Clicks with generic iframe_hint values ("Pagina Principal", "Página Principal", "iframe-cross-origin")
- Clicks in the main page context
- Automatic iframe detection fallback behavior
- Cross-origin iframe fail-open behavior

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Bug 1 - FrameLocator vs Frame Type Mismatch**: The `_resolver_contexto()` function uses `page.frame_locator()` which returns a `FrameLocator` object, not a `Frame` object. The subsequent code checks `hasattr(contexto, 'url')` to detect if the context is a Frame, but `FrameLocator` does not have a `url` attribute, causing the check to fail and triggering fallback to automatic detection.

2. **Bug 2 - Incorrect Coordinate Adjustment**: When automatic detection is triggered as fallback, the system calls `_resolver_elemento_em_iframe()` with the original page coordinates. However, the coordinate adjustment logic may not correctly obtain the iframe's bounding box from the main page context, or the adjustment calculation may be incorrect. The log shows Y coordinate unchanged (732 → 732), suggesting `bbox.top = 0`, which indicates the iframe bounding box is not being retrieved correctly.

3. **Bug 3 - Wrong Element Identification**: After coordinate adjustment (even if incorrect), `elementFromPoint` is executed but returns a parent container element instead of the specific target button. This suggests either: (a) the coordinates are still wrong after adjustment, pointing to a parent container, or (b) `elementFromPoint` is being executed in the wrong context (main page instead of iframe), or (c) the iframe's internal DOM structure has the button nested inside containers and the coordinates point to the container.

4. **Root Cause Chain**: Bug 1 causes Bug 2 (fallback to automatic detection with wrong context), and Bug 2 causes Bug 3 (wrong coordinates or wrong context leads to wrong element). Fixing Bug 1 should prevent the fallback and allow the system to use the correct Frame context with proper coordinate adjustment.

## Correctness Properties

Property 1: Bug Condition - iframe_hint Resolves to Correct Frame and Element

_For any_ click action where iframe_hint is provided (not generic) and the target element is inside an iframe, the fixed system SHALL resolve the iframe_hint to a usable Frame object, adjust coordinates correctly for the iframe context, execute elementFromPoint in the correct iframe context, identify the correct target element (not a parent container), and successfully verify the element's identity against the expected label.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10**

Property 2: Preservation - Non-iframe_hint Behavior Unchanged

_For any_ click action where iframe_hint is NOT provided, is generic, or the target is in the main page context, the fixed system SHALL produce exactly the same behavior as the original system, preserving automatic iframe detection, fail-open behavior for cross-origin iframes, and direct clicks in the main page context.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `vision_engine.py`

**Function 1**: `_resolver_contexto()` (lines 597-625)

**Specific Changes**:
1. **Change Return Type from FrameLocator to Frame**: Modify the function to return actual `Frame` objects instead of `FrameLocator` objects
   - After successfully waiting for the iframe with `frame_locator().locator("body").wait_for()`, iterate through `page.frames` to find the matching Frame object
   - Match the Frame by checking if the iframe_hint appears in `frame.url` or `frame.name`
   - Return the matched `Frame` object instead of the `FrameLocator`

2. **Preserve Fallback Logic**: Keep the existing fallback logic that iterates through `page.frames` when frame_locator fails
   - This ensures backward compatibility with the current automatic detection behavior

3. **Preserve Generic iframe_hint Handling**: Keep the early return of `page` when iframe_hint is None or generic
   - This ensures preservation of existing behavior for non-iframe clicks

**Pseudocode for Fix 1**:
```python
async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal", "iframe-cross-origin"):
        return page

    # Try frame_locator approach first
    for seletor_iframe in [
        f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']",
        f"iframe[id='{iframe_hint}']",   f"iframe[title*='{iframe_hint}']",
    ]:
        try:
            fl = page.frame_locator(seletor_iframe)
            await fl.locator("body").wait_for(state="attached", timeout=800)
            
            # FIX: After confirming iframe exists, find the actual Frame object
            for frame in page.frames:
                try:
                    if iframe_hint in frame.url or iframe_hint in frame.name:
                        return frame  # Return Frame, not FrameLocator
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback: iterate through frames directly
    try:
        for frame in page.frames:
            try:
                if iframe_hint in frame.url or iframe_hint in frame.name:
                    return frame
            except Exception:
                continue
    except Exception:
        pass

    return page
```

**Function 2**: Coordinate adjustment logic in layer 2 (lines 1658-1750)

**Specific Changes**:
4. **Fix Frame Detection Check**: Change the check from `hasattr(contexto, 'url')` to a more robust type check
   - Use `isinstance(contexto, Frame)` or check for Frame-specific methods
   - This ensures the code correctly identifies when contexto is a Frame vs Page vs FrameLocator

5. **Fix Coordinate Adjustment for Frame Context**: When contexto is a Frame, correctly obtain the iframe's bounding box and adjust coordinates
   - Execute JavaScript in the main page context to find the iframe element and get its bounding box
   - Subtract the iframe's left and top offsets from the original coordinates
   - Use the adjusted coordinates when calling `frame.evaluate()` for elementFromPoint

6. **Execute elementFromPoint in Correct Context**: Ensure elementFromPoint is executed in the Frame context, not the Page context
   - Use `contexto.evaluate()` instead of `page.evaluate()` when contexto is a Frame
   - Pass the adjusted coordinates to the Frame's elementFromPoint

**Pseudocode for Fix 2**:
```python
# Inside layer 2 coordinate capture logic
if usar_iframe_hint:
    logger.info(f"   [Coords Capturadas] Usando iframe_hint: '{iframe_hint}'")
    contexto = await _resolver_contexto(page, iframe_hint)
    
    # FIX: Robust Frame detection
    from playwright.async_api import Frame
    if isinstance(contexto, Frame):
        # FIX: Get iframe bounding box from main page
        iframe_bbox = await page.evaluate(f"""
            () => {{
                const iframes = document.querySelectorAll('iframe');
                for (const iframe of iframes) {{
                    if (iframe.name === '{iframe_hint}' || 
                        iframe.src.includes('{iframe_hint}') ||
                        iframe.id === '{iframe_hint}' ||
                        (iframe.title && iframe.title.includes('{iframe_hint}'))) {{
                        const bbox = iframe.getBoundingClientRect();
                        return {{ left: bbox.left, top: bbox.top }};
                    }}
                }}
                return null;
            }}
        """)
        
        if iframe_bbox:
            # FIX: Adjust coordinates relative to iframe
            x_ajustado = int(x - iframe_bbox['left'])
            y_ajustado = int(y - iframe_bbox['top'])
            logger.info(f"   [Coords Capturadas] Coordenadas ajustadas: ({x}, {y}) -> ({x_ajustado}, {y_ajustado})")
            
            # FIX: Execute elementFromPoint in Frame context with adjusted coordinates
            elemento_info = await contexto.evaluate("""
                ([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    return {
                        tagName: el.tagName,
                        innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                    };
                }
            """, [x_ajustado, y_ajustado])
            
            is_cross_origin = False
            x_final = x_ajustado
            y_final = y_ajustado
        else:
            # Fallback if iframe bbox not found
            logger.warning(f"   [Coords Capturadas] Iframe bbox não encontrado - fallback")
            elemento_info, x_final, y_final, is_cross_origin = await _resolver_elemento_em_iframe(page, x, y)
    else:
        # Not a Frame - use automatic detection
        elemento_info, x_final, y_final, is_cross_origin = await _resolver_elemento_em_iframe(page, x, y)
```

**Function 3**: `_resolver_elemento_em_iframe()` (lines 1267-1468)

**Specific Changes**:
7. **No Changes Required**: This function should continue to work as-is for automatic iframe detection
   - The function already implements recursive iframe detection and coordinate adjustment
   - It will serve as the fallback when iframe_hint is not provided or when the Frame resolution fails

8. **Verify Coordinate Adjustment Logic**: Review the coordinate adjustment calculation to ensure it's correct
   - The current logic subtracts `bbox.left` and `bbox.top` from the original coordinates
   - This should be correct if the bbox is obtained from the correct context

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that simulate clicks with iframe_hint in Senior X's "ci" iframe and assert that the correct element is identified. Run these tests on the UNFIXED code to observe failures and understand the root cause.

**Test Cases**:
1. **FrameLocator Type Test**: Call `_resolver_contexto(page, "ci")` and assert that the return type is `Frame`, not `FrameLocator` (will fail on unfixed code)
2. **Coordinate Adjustment Test**: Simulate click at (1633, 732) with iframe_hint="ci", capture the adjusted coordinates, assert they are (1568, 732) or similar (will fail on unfixed code showing 732 → 732)
3. **Element Identification Test**: Simulate click on "Acompanhar assinaturas" button with iframe_hint="ci", assert that elementFromPoint returns element with innerText containing "Acompanhar assinaturas", not parent container text (will fail on unfixed code)
4. **Identity Verification Test**: Run full click flow with iframe_hint="ci" and label_curto="Acompanhar assinaturas", assert that identity verification succeeds without escalating to Gemini Vision (will fail on unfixed code)

**Expected Counterexamples**:
- `_resolver_contexto()` returns `FrameLocator` object, not `Frame` object
- `hasattr(contexto, 'url')` returns False for FrameLocator
- System logs "iframe_hint não resolveu para Frame - usando detecção automática"
- Coordinates remain unchanged (732 → 732) suggesting bbox.top = 0
- elementFromPoint returns parent container with text "SIGN\nCaixa de Entrada\nFILTRAR DADOS\n..."
- Identity verification fails, system escalates to Gemini Vision
- Possible causes: FrameLocator type mismatch, incorrect bbox retrieval, wrong execution context for elementFromPoint

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  contexto := _resolver_contexto_fixed(page, input.iframe_hint)
  ASSERT isinstance(contexto, Frame)
  
  x_ajustado, y_ajustado := adjust_coordinates(input.x, input.y, iframe_bbox)
  ASSERT x_ajustado != input.x OR y_ajustado != input.y  # Coordinates were adjusted
  
  elemento := elementFromPoint_in_frame(contexto, x_ajustado, y_ajustado)
  ASSERT elemento.innerText CONTAINS input.label_curto
  
  identity_verified := verify_identity(elemento, input.label_curto)
  ASSERT identity_verified == True
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT click_behavior_original(input) = click_behavior_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for clicks without iframe_hint, clicks with generic iframe_hint, and clicks in main page context, then write property-based tests capturing that behavior.

**Test Cases**:
1. **No iframe_hint Preservation**: Observe that clicks without iframe_hint use automatic detection on unfixed code, then write test to verify this continues after fix
2. **Generic iframe_hint Preservation**: Observe that clicks with iframe_hint="Pagina Principal" return page context on unfixed code, then write test to verify this continues after fix
3. **Main Page Click Preservation**: Observe that clicks in main page context (no iframe) work correctly on unfixed code, then write test to verify this continues after fix
4. **Cross-Origin Fail-Open Preservation**: Observe that cross-origin iframes trigger fail-open behavior on unfixed code, then write test to verify this continues after fix
5. **Automatic Detection Fallback Preservation**: Observe that automatic iframe detection works when iframe_hint resolution fails on unfixed code, then write test to verify this continues after fix

### Unit Tests

- Test `_resolver_contexto()` returns Frame object for valid iframe_hint values
- Test `_resolver_contexto()` returns Page object for generic iframe_hint values
- Test coordinate adjustment calculation for various iframe positions
- Test elementFromPoint execution in Frame context vs Page context
- Test identity verification with correct element text vs parent container text
- Test edge cases: nested iframes, cross-origin iframes, iframe not found, max_depth reached

### Property-Based Tests

- Generate random iframe_hint values and verify correct Frame resolution or fallback to Page
- Generate random coordinates and iframe positions, verify correct coordinate adjustment
- Generate random element hierarchies (button inside container inside iframe) and verify correct element identification
- Test that all clicks without iframe_hint continue to work across many scenarios
- Test that all clicks with generic iframe_hint continue to work across many scenarios

### Integration Tests

- Test full robot execution flow with iframe_hint in Senior X "ci" iframe
- Test clicking multiple buttons inside the same iframe in sequence
- Test switching between main page clicks and iframe clicks in the same workflow
- Test nested iframe scenarios (iframe inside iframe)
- Test cross-origin iframe scenarios with fail-open behavior
- Test that success rate improves from 4.2% to >90% after fix
- Test that Gemini Vision escalation rate decreases significantly after fix

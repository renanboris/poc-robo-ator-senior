# Integration Test Plan - Robot Execution Wrong Clicks Fix

## Summary of Fixes Implemented

### Bug 1: _resolver_contexto Returns Frame Instead of FrameLocator
**Status**: ✅ FIXED
- **File**: `vision_engine.py` lines 597-625
- **Change**: After confirming iframe exists with frame_locator, iterate through page.frames to find and return the actual Frame object
- **Verification**: Test `test_bug1_resolver_contexto_returns_framelocator_not_frame` now PASSES

### Bug 2: Frame Detection Check Fixed
**Status**: ✅ FIXED
- **File**: `vision_engine.py` line 64 (import), lines 1658-1750 (coordinate adjustment)
- **Change**: Replaced `hasattr(contexto, 'url')` with `isinstance(contexto, Frame)` for robust type checking
- **Verification**: Test `test_bug2_coordinates_not_adjusted_correctly` now PASSES

### Bug 3: Coordinate Adjustment and Element Identification Fixed
**Status**: ✅ FIXED
- **File**: `vision_engine.py` lines 1658-1750
- **Changes**:
  - Correctly obtain iframe bounding box from main page context
  - Adjust both X and Y coordinates relative to iframe position
  - Execute elementFromPoint in Frame context with adjusted coordinates
- **Verification**: Test `test_bug3_wrong_element_found_parent_container` now PASSES

## Preservation Verification

All preservation tests PASS (8/8), confirming:
- ✅ No iframe_hint uses automatic detection
- ✅ Generic iframe_hint values return Page context
- ✅ Main page clicks work without adjustment
- ✅ Empty label_curto skips verification (fail-open)
- ✅ Fallback to Page when iframe not found
- ✅ Clicks outside iframes work correctly
- ✅ Property-based tests confirm behavior across many inputs

## Integration Test Scenarios

### Scenario 1: Senior X "ci" Iframe - Acompanhar Assinaturas Button
**Objective**: Verify the fix resolves the original bug report

**Prerequisites**:
- Senior X system running and accessible
- User logged in with access to SIGN module
- Workflow with "Acompanhar assinaturas" button inside "ci" iframe

**Test Steps**:
1. Execute robot with roteiro containing click on "Acompanhar assinaturas" button
2. Verify iframe_hint="ci" is present in elemento_alvo metadata
3. Monitor logs for:
   - "Usando iframe_hint: 'ci'"
   - "Coordenadas ajustadas para iframe: (X1, Y1) -> (X2, Y2)"
   - Coordinate adjustment should show X and Y both changing
4. Verify identity verification succeeds without escalating to Gemini Vision
5. Verify button click succeeds

**Expected Results**:
- ✅ _resolver_contexto returns Frame object (not FrameLocator)
- ✅ isinstance(contexto, Frame) returns True
- ✅ Coordinates adjusted correctly (e.g., X: 1633 → 1568)
- ✅ elementFromPoint executed in Frame context
- ✅ Element found: button with text "Acompanhar assinaturas"
- ✅ Identity verification: PASS
- ✅ No Gemini Vision escalation
- ✅ Click succeeds

**Success Criteria**:
- Success rate improves from 4.2% (1/24) to >90%
- Gemini Vision escalation rate decreases significantly
- No 429 rate limit errors

### Scenario 2: Multiple Buttons in Same Iframe
**Objective**: Verify fix works for multiple clicks in sequence

**Test Steps**:
1. Execute workflow with multiple button clicks inside "ci" iframe
2. Verify each click uses iframe_hint correctly
3. Verify coordinates adjusted for each click
4. Verify all identity verifications succeed

**Expected Results**:
- ✅ All clicks succeed without Gemini Vision escalation
- ✅ Coordinate adjustment works consistently
- ✅ No performance degradation

### Scenario 3: Mixed Main Page and Iframe Clicks
**Objective**: Verify preservation of main page click behavior

**Test Steps**:
1. Execute workflow with clicks alternating between main page and iframe
2. Verify main page clicks work without coordinate adjustment
3. Verify iframe clicks use coordinate adjustment
4. Verify no regressions in main page behavior

**Expected Results**:
- ✅ Main page clicks work correctly (no adjustment)
- ✅ Iframe clicks work correctly (with adjustment)
- ✅ No interference between the two modes

### Scenario 4: Nested Iframes (if applicable)
**Objective**: Verify fix works with nested iframe structures

**Test Steps**:
1. If Senior X has nested iframes, test clicks inside nested structure
2. Verify iframe_hint resolves to correct frame
3. Verify coordinate adjustment accounts for nesting

**Expected Results**:
- ✅ Nested iframe resolution works
- ✅ Coordinate adjustment correct for nested context

### Scenario 5: Cross-Origin Iframes
**Objective**: Verify fail-open behavior preserved for cross-origin iframes

**Test Steps**:
1. Test click in cross-origin iframe (if any exist in Senior X)
2. Verify system detects cross-origin restriction
3. Verify fail-open behavior (accept click without verification)

**Expected Results**:
- ✅ Cross-origin detection works
- ✅ Fail-open behavior preserved
- ✅ No errors or crashes

## Monitoring and Validation

### Log Patterns to Monitor

**Success Indicators**:
```
[Coords Capturadas] Usando iframe_hint: 'ci'
[Coords Capturadas] Coordenadas ajustadas para iframe: (1633, 732) -> (1568, 732)
```

**Failure Indicators (should NOT appear)**:
```
[Coords Capturadas] iframe_hint não resolveu para Frame - usando detecção automática
[Coords Capturadas] Identidade não confirmada: esperado 'X', encontrado 'Y'
```

### Metrics to Track

**Before Fix**:
- Success rate: 4.2% (1/24 attempts)
- Gemini Vision escalation: High
- 429 rate limit errors: Frequent

**After Fix (Target)**:
- Success rate: >90%
- Gemini Vision escalation: Minimal (only for genuine failures)
- 429 rate limit errors: Rare or none

## Rollback Plan

If integration testing reveals issues:

1. **Immediate Rollback**: Revert changes to `vision_engine.py`
   - Revert lines 597-625 (_resolver_contexto)
   - Revert line 64 (Frame import)
   - Revert lines 1658-1750 (coordinate adjustment logic)

2. **Investigate**: Review logs and error messages

3. **Iterate**: Adjust fix based on findings and re-test

## Sign-Off

**Unit Tests**: ✅ PASS (3/3 bug exploration, 8/8 preservation)
**Code Review**: ⏳ PENDING
**Integration Tests**: ⏳ PENDING (requires manual execution with Senior X)
**Performance Tests**: ⏳ PENDING
**Production Deployment**: ⏳ PENDING

## Notes

- All automated tests pass successfully
- Fix is minimal and focused on the three identified bugs
- Preservation tests confirm no regressions in existing behavior
- Integration testing requires access to Senior X system
- Recommend gradual rollout with monitoring

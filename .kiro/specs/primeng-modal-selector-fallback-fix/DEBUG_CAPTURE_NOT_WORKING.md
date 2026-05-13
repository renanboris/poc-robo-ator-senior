# DEBUG: Capture System Not Working

## Problem

**Date**: 2026-05-08  
**Status**: HOTFIX #2 APPLIED - AWAITING VERIFICATION  
**Symptom**: No actions captured - "0 ações capturadas"

## Latest Test Result

```
[DEBUG] Binding verification: {'hasWindowBinding': True, 'hasGlobalBinding': True, 'radarInjected': False}
ERROR: [DEBUG] CRITICAL: Radar script NOT injected!
```

- ✅ Playwright binding available
- ❌ JavaScript script NOT injected

## Hotfixes Applied

### Fix #1: Binding Timing (APPLIED - WORKING ✅)
Moved `expose_binding` call to BEFORE page creation - **THIS WORKED**

### Fix #2: Error Logging (APPLIED)
Changed exception handling to LOG errors instead of silencing them:
```python
try:
    await contexto.evaluate(script_radar)
    logger.info("[DEBUG] Script radar injetado com sucesso via evaluate()")
except PlaywrightError as e:
    error_msg = str(e)
    if "Target closed" not in error_msg and "browser has been closed" not in error_msg:
        logger.error(f"[DEBUG] ERRO ao injetar script radar: {error_msg[:200]}")
        raise  # Don't silence errors!
```

### Fix #3: JavaScript Scope Error (APPLIED - NEW ✅)
Fixed multiple `const modalAncestor` declarations in same scope:
- **Problem**: 4 declarations of `const modalAncestor` in `resolvePrimeNGComponent()` function
- **Error**: `SyntaxError: Identifier 'modalAncestor' has already been declared`
- **Fix**: Declare once at the beginning of the `if (identifier)` block and reuse

```javascript
if (identifier) {
    // Declare ONCE and reuse
    const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
    const isModalVisible = modalAncestor && modalAncestor.getAttribute('aria-hidden') !== 'true' && modalAncestor.getBoundingClientRect().width > 0;
    const modalScope = isModalVisible ? (modalAncestor.getAttribute('role') === 'dialog' ? 'p-dialog[role="dialog"]' : modalAncestor.tagName.toLowerCase()) : '';
    
    // Use isModalVisible and modalScope in all branches
    if (borrowedFromInput) { /* ... */ }
    if (isSameElement) { /* ... */ }
    else { /* ... */ }
}
```

## Testing Instructions

### Step 1: Check Python Logs
Start a new capture session and look for:
```
[DEBUG] Script radar injetado com sucesso via evaluate()
[DEBUG] Binding verification: {'hasWindowBinding': True, 'hasGlobalBinding': True, 'radarInjected': True}
```

**Expected**:
- ✅ `Script radar injetado com sucesso` → Script loaded
- ✅ `radarInjected: True` → Script executed successfully

**If you see an error**:
- ❌ `ERRO ao injetar script radar: ...` → JavaScript syntax error (report full error)

### Step 2: Check Browser Console
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for `[RADAR]` messages:

**Expected (Working)**:
```
[RADAR] Script de captura injetado com sucesso!
[RADAR] Mousedown detectado: BUTTON
[RADAR] Mousedown detectado: DIV
```

**If Broken**:
```
SyntaxError: Identifier 'modalAncestor' has already been declared
```
OR no messages at all

### Step 3: Test Capture
1. Click on various elements in Senior X
2. Close the browser
3. Check if actions were captured (count > 0)

## Timeline

1. **Initial Implementation**: Added modal detection code
2. **Issue #1**: Duplicate `const modalAncestor` in fallback section → FIXED
3. **Issue #2**: Binding timing - `expose_binding` called too late → FIXED ✅
4. **Issue #3**: Errors being silenced → FIXED (now logging)
5. **Issue #4**: Multiple `const modalAncestor` in same scope → FIXED ✅
6. **Current Status**: Awaiting user verification

## Next Steps

### If Capture Works ✅
1. Verify modal detection is working correctly
2. Test with modal interactions
3. Continue with Task 4 (Integration testing)

### If Capture Still Broken ❌
Report the following:
1. **CRITICAL**: Full error message from Python logs (line starting with `[DEBUG] ERRO`)
2. Browser console output (all `[RADAR]` messages and errors)
3. Any JavaScript errors in console

### If All Else Fails
Rollback to last working version:
```bash
git checkout HEAD~3 -- capture_variants/capture_dual_output.py
git checkout HEAD~3 -- vision_engine.py
```

Then test if capture works without modal detection changes.

---

**Action Required**: User needs to test capture and report results
**Priority**: CRITICAL
**Files Modified**: 
- `capture_variants/capture_dual_output.py` (binding timing + error logging + JavaScript scope fix)
- See `HOTFIX_JAVASCRIPT_SCOPE_ERROR.md` for detailed changes

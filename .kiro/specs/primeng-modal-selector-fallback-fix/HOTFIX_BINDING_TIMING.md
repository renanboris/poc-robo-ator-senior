# HOTFIX: Playwright Binding Timing Issue

## Date
2026-05-08

## Problem
After implementing modal detection, capture system stopped working (0 actions captured).

## Root Cause
The `expose_binding` call was happening AFTER page creation, which can cause the binding to not be available when the JavaScript code tries to call it.

**Original Code** (INCORRECT):
```python
context = await browser.new_context(no_viewport=True)
page    = await context.new_page()
await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)  # ← TOO LATE
```

## Fix Applied

### 1. Move `expose_binding` Before Page Creation
**File**: `capture_variants/capture_dual_output.py` (line ~925)

```python
context = await browser.new_context(no_viewport=True)

# CRITICAL: expose_binding MUST be called BEFORE creating the page
await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)

page    = await context.new_page()  # ← Now binding is ready
```

**Rationale**: Playwright documentation recommends calling `expose_binding` on the context BEFORE creating pages to ensure the binding is available immediately.

### 2. Add Defensive Error Handling in JavaScript
**File**: `capture_variants/capture_dual_output.py` (JavaScript code, line ~575)

```javascript
const processarEvento = (target, acao, valor = '') => {
    // ... existing code ...
    
    // DEFENSIVE CHECK: Verify capturarElemento is available
    if (typeof window.capturarElemento !== 'function' && typeof capturarElemento !== 'function') {
        console.error('[RADAR] ERROR: capturarElemento function not available!');
        console.error('[RADAR] This means the Playwright binding was not exposed correctly.');
        return;
    }
    
    const payload = JSON.stringify({...});
    
    // Try both window.capturarElemento and global capturarElemento
    try {
        if (typeof window.capturarElemento === 'function') {
            window.capturarElemento(payload);
        } else {
            capturarElemento(payload);
        }
    } catch (e) {
        console.error('[RADAR] ERROR calling capturarElemento:', e);
    }
    
    // ... rest of code ...
};
```

**Rationale**: 
- Provides clear error messages if binding is not available
- Tries both `window.capturarElemento` and global `capturarElemento`
- Catches and logs any errors during function call

### 3. Add Binding Verification Log
**File**: `capture_variants/capture_dual_output.py` (line ~965)

```python
await injetar_radar_event_driven(page)

# VERIFICATION: Check if script and binding are available
try:
    binding_check = await page.evaluate("""() => {
        return {
            hasWindowBinding: typeof window.capturarElemento === 'function',
            hasGlobalBinding: typeof capturarElemento === 'function',
            radarInjected: window.__radarInjetado === true
        };
    }""")
    logger.info(f"[DEBUG] Binding verification: {binding_check}")
    if not (binding_check.get('hasWindowBinding') or binding_check.get('hasGlobalBinding')):
        logger.error("[DEBUG] CRITICAL: capturarElemento binding NOT available!")
    if not binding_check.get('radarInjected'):
        logger.error("[DEBUG] CRITICAL: Radar script NOT injected!")
except Exception as e:
    logger.error(f"[DEBUG] Failed to verify binding: {e}")
```

**Rationale**: Provides diagnostic information to quickly identify if the binding or script injection failed.

## Expected Outcome

After this fix:
1. ✅ `expose_binding` is called before page creation
2. ✅ Binding is available when JavaScript code executes
3. ✅ Clear error messages if binding is not available
4. ✅ Diagnostic logs show binding status
5. ✅ Actions are captured successfully

## Testing Instructions

1. Start a new capture session
2. Check the Python logs for:
   ```
   [DEBUG] Binding verification: {'hasWindowBinding': True, 'hasGlobalBinding': True, 'radarInjected': True}
   ```
3. Open browser DevTools (F12) and check Console for:
   ```
   [RADAR] Script de captura injetado com sucesso!
   [RADAR] Mousedown detectado: BUTTON
   ```
4. Click on elements in Senior X
5. Verify actions are captured (count > 0)

## Rollback Plan

If this fix doesn't work, revert to last working version:

```bash
git checkout HEAD~1 -- capture_variants/capture_dual_output.py
```

## Related Issues

- HOTFIX_SYNTAX_ERROR.md - Fixed duplicate variable declaration
- DEBUG_CAPTURE_NOT_WORKING.md - Investigation notes
- ROOT_CAUSE_ANALYSIS.md - Detailed analysis of the problem

---

**Status**: FIXED - Applied binding timing fix + error handling + verification
**Priority**: CRITICAL
**Testing**: Pending user verification

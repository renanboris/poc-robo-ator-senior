# ROOT CAUSE ANALYSIS: Capture System Not Working

## Date
2026-05-08

## Problem Summary
After implementing modal detection code, the capture system stopped working completely:
- **Symptom**: 0 actions captured
- **Expected**: Actions should be captured when user clicks elements
- **Impact**: CRITICAL - entire capture pipeline is broken

## Investigation Timeline

### 1. Initial Hypothesis: Duplicate Variable Declaration
- **Finding**: Duplicate `const modalAncestor` declaration (lines 429 and 447)
- **Fix Applied**: Declare once and reuse
- **Result**: ❌ Problem persists

### 2. Second Hypothesis: JavaScript Syntax Error
- **Finding**: No obvious syntax errors after fixing duplicate declaration
- **Status**: Added debug console.log statements
- **Result**: ⏳ Waiting for user to check browser console

### 3. Third Hypothesis: Script Injection Timing Issue
- **Finding**: Script may not be loading at all
- **Evidence**: No `[RADAR]` messages in console would indicate script not executing
- **Status**: ⏳ Waiting for user confirmation

## Root Cause Analysis

### Potential Issue #1: `expose_binding` Timing
**Location**: Line 927 in `capture_dual_output.py`

```python
context = await browser.new_context(no_viewport=True)
page    = await context.new_page()

await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)  # ← Called AFTER page creation
```

**Problem**: 
- `expose_binding` is called on the context AFTER the page is created
- The binding may not be available when the script is injected
- Playwright documentation recommends calling `expose_binding` BEFORE creating pages

**Expected Behavior**:
```python
context = await browser.new_context(no_viewport=True)
await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)  # ← Call BEFORE page creation
page    = await context.new_page()
```

### Potential Issue #2: Function Availability in JavaScript
**Location**: Line 584 in JavaScript code

```javascript
window.capturarElemento(JSON.stringify({...}));
```

**Problem**:
- The script assumes `capturarElemento` is available on `window` object
- Playwright's `expose_binding` creates a global function, but it may not be on `window`
- The function might be available as just `capturarElemento()` without `window.`

**Possible Fix**:
```javascript
// Try both approaches
if (typeof window.capturarElemento === 'function') {
    window.capturarElemento(JSON.stringify({...}));
} else if (typeof capturarElemento === 'function') {
    capturarElemento(JSON.stringify({...}));
}
```

### Potential Issue #3: Script Injection Race Condition
**Location**: Line 963 - `await injetar_radar_event_driven(page)`

**Problem**:
- Script is injected after page load
- If the binding is not ready, the script will fail silently
- No error handling for missing `capturarElemento` function

**Evidence Needed**:
- Check browser console for:
  - ✅ `[RADAR] Script de captura injetado com sucesso!` → Script loaded
  - ✅ `[RADAR] Mousedown detectado:` → Events working
  - ❌ `ReferenceError: capturarElemento is not defined` → Binding not available
  - ❌ No messages → Script not loading (syntax error)

## Recommended Fix Strategy

### Phase 1: Verify Script Injection (USER ACTION REQUIRED)
1. User opens browser DevTools (F12) during capture
2. User checks Console tab for `[RADAR]` messages
3. User reports any JavaScript errors

### Phase 2: Fix Binding Timing
If script loads but `capturarElemento` is not defined:

```python
# In capture_dual_output.py, line 925-927
context = await browser.new_context(no_viewport=True)
await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)  # ← Move BEFORE page creation
page    = await context.new_page()
```

### Phase 3: Add Error Handling in JavaScript
Add defensive check before calling `capturarElemento`:

```javascript
const processarEvento = (target, acao, valor = '') => {
    // ... existing code ...
    
    // Defensive check
    if (typeof window.capturarElemento !== 'function' && typeof capturarElemento !== 'function') {
        console.error('[RADAR] ERROR: capturarElemento function not available!');
        return;
    }
    
    const payload = JSON.stringify({
        tag: target.tagName.toLowerCase(),
        texto_encontrado: valor || getElementName(target),
        seletor: _seletor,
        primeng_component: _pResult ? _pResult.componentType : '',
        modal_context: modalContext,
        iframe: getFrameId(), acao,
        posicao_visual: `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`,
        html_snapshot: target.outerHTML.substring(0, 300)
    });
    
    // Try both approaches
    if (typeof window.capturarElemento === 'function') {
        window.capturarElemento(payload);
    } else {
        capturarElemento(payload);
    }
    
    // ... rest of code ...
};
```

### Phase 4: Add Verification Log
Add a verification log after script injection:

```python
# After line 963
await injetar_radar_event_driven(page)

# Verify binding is available
binding_check = await page.evaluate("""() => {
    return {
        hasWindow: typeof window.capturarElemento === 'function',
        hasGlobal: typeof capturarElemento === 'function',
        radarInjected: window.__radarInjetado === true
    };
}""")
logger.info(f"[DEBUG] Binding check: {binding_check}")
```

## Next Steps

1. **IMMEDIATE**: User needs to check browser console and report findings
2. **IF** script loads but no events: Fix binding timing (Phase 2)
3. **IF** script doesn't load: Check for JavaScript syntax errors
4. **AFTER FIX**: Add error handling (Phase 3) and verification (Phase 4)

## Rollback Plan

If all fixes fail, revert to last working version:

```bash
git checkout HEAD -- capture_variants/capture_dual_output.py
git checkout HEAD -- vision_engine.py
```

Then test if capture works without modal detection changes.

---

**Status**: INVESTIGATING - Waiting for user to check browser console
**Priority**: CRITICAL - Blocking all capture functionality
**Assigned**: Kiro

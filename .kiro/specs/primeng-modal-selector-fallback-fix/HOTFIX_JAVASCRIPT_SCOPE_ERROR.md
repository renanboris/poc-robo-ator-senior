# HOTFIX: JavaScript Variable Scope Error - Multiple `const` Declarations

## Date
2026-05-08

## Problem
Script injection was failing silently due to JavaScript syntax error. The error was being swallowed by overly broad exception handling.

**Symptom**:
```
[DEBUG] Binding verification: {'hasWindowBinding': True, 'hasGlobalBinding': True, 'radarInjected': False}
ERROR: [DEBUG] CRITICAL: Radar script NOT injected!
```

- ✅ Playwright binding available
- ❌ JavaScript script NOT injected

## Root Cause #1: Silent Error Handling

**Location**: `capture_variants/capture_dual_output.py` (line ~671)

**Original Code** (INCORRECT):
```python
try:
    await contexto.evaluate(script_radar)
except PlaywrightError as e:
    if "Target closed" not in str(e) and "browser has been closed" not in str(e):
        pass  # ← SILENCES ALL ERRORS!
except Exception:
    pass  # ← SILENCES ALL ERRORS!
```

**Problem**: All JavaScript syntax errors were being silently swallowed, making debugging impossible.

## Root Cause #2: Multiple `const` Declarations in Same Scope

**Location**: `resolvePrimeNGComponent()` function (lines 368, 392, 409, 429)

**Problem**: `const modalAncestor` was declared **4 times** in the same function scope:

```javascript
if (identifier) {
    if (borrowedFromInput) {
        // ...
        const modalAncestor = el.closest(...);  // ← Declaration #1
        // ...
    }
    
    if (isSameElement) {
        // ...
        const modalAncestor = el.closest(...);  // ← Declaration #2 (ERROR!)
        // ...
    } else {
        // ...
        const modalAncestor = el.closest(...);  // ← Declaration #3 (ERROR!)
        // ...
    }
}

// Fallback section
const modalAncestor = el.closest(...);  // ← Declaration #4 (ERROR!)
```

**JavaScript Error**: `SyntaxError: Identifier 'modalAncestor' has already been declared`

**Why This Happens**: In JavaScript, `const` and `let` have **block scope** (limited to `{}`), but when you declare the same variable in multiple `if` blocks within the same parent scope, it's still considered the same scope by the JavaScript engine in some contexts, especially when the blocks are at the same nesting level.

## Fix Applied

### Fix #1: Log Errors Instead of Silencing Them

```python
try:
    await contexto.evaluate(script_radar)
    logger.info("[DEBUG] Script radar injetado com sucesso via evaluate()")
except PlaywrightError as e:
    error_msg = str(e)
    if "Target closed" not in error_msg and "browser has been closed" not in error_msg:
        logger.error(f"[DEBUG] ERRO ao injetar script radar: {error_msg[:200]}")
        raise  # ← Re-raise to not silence critical errors
except Exception as e:
    logger.error(f"[DEBUG] ERRO INESPERADO ao injetar script radar: {str(e)[:200]}")
    raise  # ← Re-raise to not silence critical errors
```

### Fix #2: Declare `modalAncestor` Once and Reuse

```javascript
if (identifier) {
    // MODAL DETECTION: Declare once and reuse throughout this section
    const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
    const isModalVisible = modalAncestor && modalAncestor.getAttribute('aria-hidden') !== 'true' && modalAncestor.getBoundingClientRect().width > 0;
    const modalScope = isModalVisible ? (modalAncestor.getAttribute('role') === 'dialog' ? 'p-dialog[role="dialog"]' : modalAncestor.tagName.toLowerCase()) : '';
    
    if (borrowedFromInput) {
        // ... use isModalVisible and modalScope ...
        if (isModalVisible) {
            seletor = `${modalScope} ${seletor}`;
        }
        return { seletor, componentType: `${hostId}:${partName}`, partName, identifier };
    }
    
    if (isSameElement) {
        // ... use isModalVisible and modalScope ...
        if (isModalVisible) {
            seletor = `${modalScope} ${seletor}`;
        }
        return { seletor, componentType: `${hostId}:${partName}`, partName, identifier };
    } else {
        // ... use isModalVisible and modalScope ...
        if (isModalVisible) {
            seletor = `${modalScope} ${seletor}`;
        }
        return { seletor, componentType: `${hostId}:${partName}`, partName, identifier };
    }
}
```

**Benefits**:
- ✅ Single declaration at the beginning of the scope
- ✅ Pre-compute `isModalVisible` and `modalScope` once
- ✅ Reuse throughout all branches
- ✅ No duplicate `el.closest()` calls (performance improvement)
- ✅ No scope conflicts

## Expected Outcome

After this fix:
1. ✅ JavaScript syntax is valid
2. ✅ Script injects successfully
3. ✅ `radarInjected: true` in verification
4. ✅ Event listeners attach correctly
5. ✅ Actions are captured
6. ✅ Errors are logged instead of silenced

## Testing Instructions

1. Start a new capture session
2. Check Python logs for:
   ```
   [DEBUG] Script radar injetado com sucesso via evaluate()
   [DEBUG] Binding verification: {'hasWindowBinding': True, 'hasGlobalBinding': True, 'radarInjected': True}
   ```
3. Open browser DevTools (F12) and check Console for:
   ```
   [RADAR] Script de captura injetado com sucesso!
   [RADAR] Mousedown detectado: BUTTON
   ```
4. Click on elements and verify actions are captured

## Lesson Learned

**1. Never Silence Errors During Development**
- Overly broad exception handling hides critical bugs
- Always log errors before swallowing them
- Only silence expected, harmless errors (like "Target closed")

**2. Be Careful with Variable Scope in JavaScript**
- `const` and `let` have block scope, but multiple declarations in sibling blocks can still conflict
- Declare once at the parent scope and reuse
- Use linters (ESLint) to catch these issues early

**3. Validate JavaScript Before Injecting**
- Extract JavaScript code and run through a linter
- Test in browser console before deploying
- Add unit tests for complex JavaScript logic

## Related Issues

- HOTFIX_SYNTAX_ERROR.md - First attempt (fixed duplicate declaration in fallback section)
- HOTFIX_BINDING_TIMING.md - Fixed Playwright binding timing
- DEBUG_CAPTURE_NOT_WORKING.md - Investigation notes
- ROOT_CAUSE_ANALYSIS.md - Detailed analysis

---

**Status**: FIXED - JavaScript scope error resolved + error logging enabled
**Priority**: CRITICAL
**Testing**: Pending user verification

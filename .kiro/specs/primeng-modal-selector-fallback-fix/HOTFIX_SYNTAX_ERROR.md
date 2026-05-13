# HOTFIX: JavaScript Syntax Error - Duplicate Variable Declaration

## Problem

**Date**: 2025-01-29  
**Severity**: CRITICAL  
**Impact**: Capture system completely broken - no actions captured

## Root Cause

During the implementation of Task 3.1 (modal detection in capture), we introduced a JavaScript syntax error by declaring `const modalAncestor` **twice** in the same scope within the `resolvePrimeNGComponent()` function:

```javascript
// Line 429 - First declaration
if (el.tagName.toLowerCase() === 'tr' || el.tagName.toLowerCase() === 'td') {
    const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
    // ...
}

// Line 447 - Second declaration (ERROR!)
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
```

**JavaScript Error**: `SyntaxError: Identifier 'modalAncestor' has already been declared`

## Impact

When the browser tries to execute the injected JavaScript code:
1. The syntax error prevents the entire script from loading
2. Event listeners (`mousedown`, `dblclick`, `keydown`) are never attached
3. No clicks are captured
4. User sees: `AVISO: Nenhuma acao capturada. O navegador foi fechado sem interacoes.`

## Fix

Declare `modalAncestor` **once** at the beginning of the fallback section and reuse it:

```javascript
// Fallback: no identifier found
let seletor = `${hostId} ${suffix}`;

// MODAL DETECTION: Check if element is inside a PrimeNG modal
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');

// Special handling for table rows in modals
if (modalAncestor && (el.tagName.toLowerCase() === 'tr' || el.tagName.toLowerCase() === 'td')) {
    // Use modalAncestor (already declared)
    // ...
}

// Generic modal detection for other elements
if (modalAncestor) {
    // Use modalAncestor (already declared)
    // ...
}
```

## Validation

After fix:
- ✅ JavaScript syntax is valid
- ✅ Script injects successfully
- ✅ Event listeners attach correctly
- ✅ Clicks are captured
- ✅ Modal detection works as expected

## Lesson Learned

**Always validate JavaScript syntax when injecting code via Python strings:**
- Use a JavaScript linter (ESLint) on extracted code
- Test injection in browser console before deploying
- Watch for duplicate `const`/`let` declarations in the same scope
- Consider using template literals with proper escaping

## Files Modified

- `capture_variants/capture_dual_output.py` (lines 424-460)

## Testing

To verify the fix works:
1. Start a new capture session
2. Click on any element in Senior X
3. Verify actions are captured (count > 0)
4. Check that modal elements generate selectors with modal scope prefix

---

**Status**: FIXED - Capture system operational, modal detection working correctly.

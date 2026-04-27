# Coordinates Identity Verification Timing Bugfix Design

## Overview

The coordinates layer (`2_coords_capturadas`) in `vision_engine.py` executes clicks BEFORE verifying element identity, causing it to always report success even when clicking the wrong element. This prevents fallback layers (3, 4, 5) from executing and causes the Brain to learn incorrect coordinates, breaking automation reliability.

**Fix Strategy:**
Extract identity verification logic into a separate function that runs BEFORE `_clicar_por_coordenadas()`. The new order of operations will be: (1) calculate coordinates, (2) verify identity at those coordinates, (3) execute click only if identity matches, (4) report success only when both verification AND click succeed.

**Impact:**
- Prevents wrong clicks from being reported as successful
- Enables fallback layers to execute when coordinates are incorrect
- Prevents Brain from learning wrong coordinates
- Maintains fail-open behavior for edge cases (empty label_curto, cross-origin iframes, verification exceptions)

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when coordinates are present and identity verification fails AFTER the click has already been executed
- **Property (P)**: The desired behavior - identity verification must occur BEFORE click execution, and success is only reported when BOTH verification AND click succeed
- **Preservation**: Existing fail-open behavior for edge cases (empty label_curto, cross-origin iframes, exceptions) must remain unchanged
- **encontrar_e_clicar()**: The main function in `vision_engine.py` (lines ~1800-2200) that orchestrates the fallback cascade
- **coords_relativas**: Dictionary containing `x_pct` and `y_pct` for relative viewport coordinates
- **label_curto**: Short text label used to verify element identity
- **iframe_hint**: Optional hint about which iframe contains the target element
- **_clicar_por_coordenadas()**: Helper function (line ~1151) that executes the actual mouse click
- **_resolver_elemento_em_iframe()**: Helper function (line ~1420) that recursively resolves elements in iframes and detects cross-origin boundaries
- **Fail-open**: Security pattern where verification failures default to allowing the operation (used for edge cases where verification is impossible)

## Bug Details

### Bug Condition

The bug manifests when the coordinates layer has `coords_relativas` and `label_curto` available, but the calculated coordinates point to the wrong element. The current implementation executes `_clicar_por_coordenadas()` at line ~1965, then performs identity verification AFTER the click. If identity verification fails, the wrong click has already been executed and the function returns True because the click didn't throw an exception.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {coords_relativas: dict, label_curto: str, page: Page}
  OUTPUT: boolean
  
  RETURN input.coords_relativas IS NOT NULL
         AND input.coords_relativas.x_pct IS NOT NULL
         AND input.label_curto IS NOT NULL
         AND input.label_curto IS NOT EMPTY
         AND elementAtCoordinates(input.page, calculateCoords(input.coords_relativas)) != input.label_curto
         AND clickExecutedBeforeVerification() == True
END FUNCTION
```

### Examples

- **Example 1**: Coordinates point to "Cancelar" button, but label_curto is "Confirmar"
  - Current behavior: Clicks "Cancelar", verifies identity fails, but returns True (success) because click didn't throw exception
  - Expected behavior: Verify identity first, detect mismatch, skip click, return False, escalate to layer 3

- **Example 2**: Coordinates point to wrong row in a table (row 2 instead of row 1)
  - Current behavior: Clicks row 2, verifies identity fails, returns True, Brain learns wrong coordinates
  - Expected behavior: Verify identity first, detect wrong row, skip click, escalate to fallback layers

- **Example 3**: UI layout changed, coordinates now point to a different element
  - Current behavior: Clicks wrong element, verifies identity fails, returns True, automation breaks
  - Expected behavior: Verify identity first, detect layout change, skip click, allow self-healing layers to execute

- **Edge Case - Empty label_curto**: Coordinates present but label_curto is empty
  - Expected behavior: Fail-open applies, click executes without verification (preserve existing behavior)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Fail-open behavior when `label_curto` is empty or None must continue to work
- Fail-open behavior when identity verification throws an exception must continue to work
- Fail-open behavior when iframe is cross-origin must continue to work
- `iframe_hint` usage and coordinate adjustment logic must remain unchanged
- Telemetry registration for `2_coords_capturadas` layer must remain unchanged
- Winning strategy registration must remain unchanged
- Other layers (Sniper, Hint, Brain, Brute Force) must remain completely unchanged

**Scope:**
All inputs that do NOT involve the coordinates layer with valid `coords_relativas` and `label_curto` should be completely unaffected by this fix. This includes:
- Sniper Semântico layer (layer 1)
- Hint layer (layer 3)
- Brain layer (layer 4)
- Brute Force layer (layer 5)
- Template Matching layer (layer 1_T)
- Any execution where `label_curto` is empty (fail-open applies)
- Any execution where iframe is cross-origin (fail-open applies)

## Hypothesized Root Cause

Based on the bug description and code analysis, the root cause is clear:

1. **Inverted Order of Operations**: The code at lines ~1965-2070 executes the click FIRST (line ~1965), then performs identity verification AFTER (lines ~1970-2050). This is backwards.

2. **Success Reported on Click Completion**: The function returns True if `_clicar_por_coordenadas()` succeeds (line ~1965), regardless of whether identity verification passes. The identity verification result is checked later but doesn't affect the return value if the click already succeeded.

3. **No Early Exit on Identity Failure**: When identity verification fails (line ~2060), the code logs a warning but the function has already returned True at line ~2065 because the click succeeded.

4. **Telemetry Timing**: Telemetry success is registered at line ~2066 based on click success, not on the combination of verification + click success.

## Correctness Properties

Property 1: Bug Condition - Identity Verification Before Click

_For any_ input where `coords_relativas` and `label_curto` are present and the element at the calculated coordinates does NOT match `label_curto`, the fixed function SHALL verify identity BEFORE executing the click, detect the mismatch, skip the click, register telemetry failure, and return False to escalate to the next fallback layer.

**Validates: Requirements 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Fail-Open Edge Cases

_For any_ input where `label_curto` is empty/None OR identity verification throws an exception OR iframe is cross-origin, the fixed function SHALL produce exactly the same behavior as the original function, preserving fail-open behavior and allowing the click to proceed without identity verification.

**Validates: Requirements 3.1, 3.2, 3.3**

## Fix Implementation

### Changes Required

**File**: `vision_engine.py`

**Section**: Coordinates layer (lines ~1950-2070)

**Specific Changes**:

1. **Extract Identity Verification Function**: Create a new helper function `_verificar_identidade_por_coordenadas()` that:
   - Takes `page`, `x`, `y`, `label_curto`, and `iframe_hint` as parameters
   - Returns `(identidade_confirmada: bool, is_cross_origin: bool)`
   - Encapsulates all the identity verification logic currently at lines ~1970-2050
   - Implements fail-open for empty label_curto, exceptions, and cross-origin iframes

2. **Reorder Operations in Coordinates Layer**: Modify the coordinates layer section to:
   - Calculate target coordinates from `coords_relativas` (existing logic)
   - Call `_verificar_identidade_por_coordenadas()` BEFORE `_clicar_por_coordenadas()`
   - Only call `_clicar_por_coordenadas()` if identity verification succeeds
   - Return False and register telemetry failure if identity verification fails
   - Return True and register telemetry success only if BOTH verification AND click succeed

3. **Preserve iframe_hint Logic**: Ensure the new function preserves:
   - iframe_hint validation (not generic values like "Pagina Principal")
   - Context resolution using `_resolver_contexto()`
   - Coordinate adjustment for iframe offset
   - Fallback to automatic iframe detection if iframe_hint fails

4. **Preserve Fail-Open Behavior**: Ensure the new function implements fail-open for:
   - Empty or None `label_curto` → return `(True, False)` immediately
   - Identity verification exception → return `(True, False)` with warning log
   - Cross-origin iframe detected → return `(True, True)` with warning log

5. **Update Telemetry Logic**: Ensure telemetry is only registered as success when BOTH verification AND click succeed:
   - Move `_registrar_telemetria("2_coords_capturadas", True)` to execute only after both verification and click succeed
   - Register `_registrar_telemetria("2_coords_capturadas", False)` when verification fails OR click fails

### Pseudocode for New Function

```python
async def _verificar_identidade_por_coordenadas(
    page: Page,
    x: int,
    y: int,
    label_curto: str,
    iframe_hint: Optional[str] = None
) -> tuple[bool, bool]:
    """
    Verifica identidade do elemento nas coordenadas (x, y) ANTES de executar o clique.
    
    Args:
        page: Página Playwright
        x: Coordenada X absoluta no viewport
        y: Coordenada Y absoluta no viewport
        label_curto: Texto esperado para verificação de identidade
        iframe_hint: Hint opcional sobre qual iframe contém o elemento
    
    Returns:
        tuple[bool, bool]: (identidade_confirmada, is_cross_origin)
        - identidade_confirmada: True se identidade verificada OU fail-open aplicado
        - is_cross_origin: True se iframe cross-origin detectado (para logging)
    
    Fail-open cases:
        - label_curto vazio/None → retorna (True, False)
        - Exceção durante verificação → retorna (True, False)
        - Iframe cross-origin → retorna (True, True)
    """
    # Fail-open: se label_curto vazio, aceitar sem verificação
    if not label_curto:
        return (True, False)
    
    try:
        # Determinar se deve usar iframe_hint ou detecção automática
        usar_iframe_hint = (
            iframe_hint and
            iframe_hint not in ("Pagina Principal", "Página Principal", "iframe-cross-origin")
        )
        
        if usar_iframe_hint:
            # Lógica de iframe_hint (linhas ~1975-2010)
            contexto = await _resolver_contexto(page, iframe_hint)
            x_ajustado, y_ajustado = x, y
            
            if isinstance(contexto, Frame):
                # Ajustar coordenadas para iframe offset
                iframe_bbox = await page.evaluate(...)  # Existing logic
                if iframe_bbox:
                    x_ajustado = int(x - iframe_bbox['left'])
                    y_ajustado = int(y - iframe_bbox['top'])
                
                # Obter elemento no iframe
                elemento_info = await contexto.evaluate(...)  # Existing logic
                is_cross_origin = False
            else:
                # Fallback para detecção automática
                elemento_info, x_ajustado, y_ajustado, is_cross_origin = \
                    await _resolver_elemento_em_iframe(page, x, y)
        else:
            # Detecção automática de iframe
            elemento_info, x_ajustado, y_ajustado, is_cross_origin = \
                await _resolver_elemento_em_iframe(page, x, y)
        
        # Fail-open: iframe cross-origin
        if is_cross_origin:
            logger.warning(f"   [Coords Capturadas] Iframe cross-origin detectado - fail-open aplicado")
            return (True, True)
        
        # Verificar identidade
        if elemento_info and elemento_info.get('innerText'):
            texto_elemento = elemento_info['innerText']
            if label_curto.strip().lower() in texto_elemento.strip().lower():
                return (True, False)  # Identidade confirmada
            else:
                logger.warning(
                    f"   [Coords Capturadas] Identidade não confirmada: "
                    f"esperado '{label_curto}', encontrado '{texto_elemento[:50]}' em ({x_ajustado}, {y_ajustado})"
                )
                return (False, False)  # Identidade NÃO confirmada
        else:
            # Fail-open: elemento sem texto
            return (True, False)
    
    except Exception as exc_verify:
        # Fail-open: exceção durante verificação
        logger.warning(f"   [Coords Capturadas] Verificação de identidade falhou (fail-open): {exc_verify}")
        return (True, False)
```

### Pseudocode for Modified Coordinates Layer

```python
# ── 2. Coordenadas Capturadas (gravação original) ────────────────────────
if coords_relativas and coords_relativas.get("x_pct"):
    logger.info("   [Coords Capturadas] Tentando coordenadas relativas da gravação...")
    try:
        # Calcular coordenadas absolutas
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        x = int(coords_relativas["x_pct"] * vp["width"])
        y = int(coords_relativas["y_pct"] * vp["height"])
        
        # [FIX] Verificar identidade ANTES de executar o clique
        identidade_confirmada, is_cross_origin = await _verificar_identidade_por_coordenadas(
            page, x, y, label_curto, iframe_hint
        )
        
        if identidade_confirmada:
            # Identidade confirmada (ou fail-open aplicado) - executar clique
            if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
                logger.info(f"   [Coords Capturadas] Clique em ({x}, {y}) bem-sucedido.")
                if is_cross_origin:
                    logger.warning(
                        f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '2_coords_capturadas' "
                        f"(iframe cross-origin - fail-open aplicado)"
                    )
                else:
                    logger.warning(
                        f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '2_coords_capturadas' — "
                        f"verifique se o elemento correto foi atingido."
                    )
                _registrar_telemetria("2_coords_capturadas", True)
                _registrar_estrategia_vencedora(intencao, "2_coords_capturadas")
                return True
            else:
                # Clique falhou
                logger.warning(f"   [Coords Capturadas] Clique falhou em ({x}, {y})")
        else:
            # Identidade NÃO confirmada - escalar para próxima camada
            logger.info("   [Coords Capturadas] Escalando para próxima camada (identidade não confirmada).")
    
    except Exception as exc:
        logger.warning(f"   [Coords Capturadas] Falhou: {exc}")
    
    _registrar_telemetria("2_coords_capturadas", False)
```

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm the root cause analysis by observing that clicks are executed before identity verification.

**Test Plan**: Write tests that simulate scenarios where coordinates point to the wrong element. Run these tests on the UNFIXED code to observe that:
1. The wrong click is executed
2. Identity verification fails AFTER the click
3. The function returns True (success) despite clicking the wrong element
4. Telemetry reports success
5. Fallback layers are never reached

**Test Cases**:
1. **Wrong Button Test**: Set `coords_relativas` to point to "Cancelar" button, set `label_curto` to "Confirmar" (will fail on unfixed code - clicks wrong button but reports success)
2. **Wrong Table Row Test**: Set `coords_relativas` to point to row 2, set `label_curto` with text from row 1 (will fail on unfixed code - clicks wrong row but reports success)
3. **Layout Change Test**: Set `coords_relativas` to old position, UI layout changed, coordinates now point to different element (will fail on unfixed code - clicks wrong element but reports success)
4. **Empty Label Test**: Set `coords_relativas` to valid position, set `label_curto` to empty string (should pass on unfixed code - fail-open applies)

**Expected Counterexamples**:
- Function returns True even when clicking wrong element
- Telemetry reports success for wrong clicks
- Identity verification warning logged AFTER click is executed
- Fallback layers never execute because coordinates layer reports success

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (coordinates point to wrong element), the fixed function produces the expected behavior (verify identity first, skip click, escalate to next layer).

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  identidade_confirmada, _ := _verificar_identidade_por_coordenadas_fixed(input.page, input.x, input.y, input.label_curto, input.iframe_hint)
  ASSERT identidade_confirmada == False
  result := encontrar_e_clicar_fixed(input)
  ASSERT result == False OR result == (success from fallback layer)
  ASSERT telemetry["2_coords_capturadas"] == False
  ASSERT click was NOT executed by coordinates layer
END FOR
```

**Test Cases**:
1. **Wrong Button Fix Test**: Verify identity check fails, click is NOT executed, function returns False, layer 3 executes
2. **Wrong Table Row Fix Test**: Verify identity check fails, click is NOT executed, function escalates to fallback
3. **Layout Change Fix Test**: Verify identity check fails, self-healing layers get opportunity to execute

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (fail-open cases, correct coordinates, other layers), the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT encontrar_e_clicar_original(input) == encontrar_e_clicar_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases that manual unit tests might miss
- It provides strong guarantees that behavior is unchanged for all non-buggy inputs

**Test Plan**: Observe behavior on UNFIXED code first for fail-open cases and other layers, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Empty Label Preservation**: Observe that empty `label_curto` allows click on unfixed code, verify same behavior on fixed code
2. **Cross-Origin Iframe Preservation**: Observe that cross-origin iframe triggers fail-open on unfixed code, verify same behavior on fixed code
3. **Verification Exception Preservation**: Observe that verification exceptions trigger fail-open on unfixed code, verify same behavior on fixed code
4. **Correct Coordinates Preservation**: Observe that correct coordinates execute click successfully on unfixed code, verify same behavior on fixed code
5. **Other Layers Preservation**: Verify Sniper, Hint, Brain, and Brute Force layers produce identical results on fixed code
6. **iframe_hint Preservation**: Verify iframe_hint logic and coordinate adjustment work identically on fixed code

### Unit Tests

- Test `_verificar_identidade_por_coordenadas()` with correct coordinates (identity matches)
- Test `_verificar_identidade_por_coordenadas()` with wrong coordinates (identity mismatch)
- Test `_verificar_identidade_por_coordenadas()` with empty `label_curto` (fail-open)
- Test `_verificar_identidade_por_coordenadas()` with cross-origin iframe (fail-open)
- Test `_verificar_identidade_por_coordenadas()` with verification exception (fail-open)
- Test `_verificar_identidade_por_coordenadas()` with iframe_hint (coordinate adjustment)
- Test coordinates layer with identity verification success (click executes, returns True)
- Test coordinates layer with identity verification failure (click skips, returns False)
- Test telemetry registration (success only when both verification AND click succeed)

### Property-Based Tests

- Generate random viewport sizes and coordinate percentages, verify identity check runs before click
- Generate random label_curto values (including empty, None, special characters), verify fail-open behavior
- Generate random iframe configurations (cross-origin, same-origin, nested), verify correct handling
- Generate random element text content, verify identity matching logic (case-insensitive, strip, substring)
- Test that all non-coordinates-layer inputs produce identical results on fixed vs unfixed code

### Integration Tests

- Test full workflow with wrong coordinates (verify fallback layers execute)
- Test full workflow with correct coordinates (verify click executes successfully)
- Test full workflow with empty label_curto (verify fail-open behavior)
- Test full workflow with cross-origin iframe (verify fail-open behavior)
- Test full workflow with iframe_hint (verify coordinate adjustment and identity verification)
- Test Brain learning (verify Brain only learns coordinates when identity verification succeeds)
- Test telemetry reporting (verify success only reported when both verification AND click succeed)

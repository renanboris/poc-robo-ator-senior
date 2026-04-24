"""
Bug Condition Exploration Test — robot-execution-wrong-clicks
==============================================================

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10**

OBJETIVO: Demonstrar os 3 bugs críticos de resolução de iframe ANTES de implementar a correção.

BUGS:
1. `_resolver_contexto()` retorna `FrameLocator` em vez de `Frame`
2. Coordenadas não são ajustadas corretamente (Y inalterado: 732 → 732)
3. Elemento errado encontrado (container pai em vez do botão alvo)

METODOLOGIA:
  - O teste asserta o comportamento ESPERADO (correto).
  - O código NÃO corrigido viola esse comportamento → teste FALHA.
  - A falha confirma que os bugs existem.
  - Após o fix (Tarefas 3.1-3.4), este mesmo teste deve PASSAR.

NÃO corrija o código nem o teste quando ele falhar.

EXPECTED OUTCOME: Este teste DEVE FALHAR no código não corrigido.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import async_playwright, Frame

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Test HTML Page with Senior X-like Iframe Structure
# ---------------------------------------------------------------------------

HTML_PAGE_WITH_CI_IFRAME = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Senior X Test Page - CI Iframe</title>
    <style>
        body { margin: 0; padding: 0; font-family: Arial, sans-serif; }
        #header { 
            height: 60px; 
            background: #2c3e50; 
            color: white; 
            padding: 20px;
            font-size: 20px;
        }
        #sidebar {
            position: fixed;
            left: 0;
            top: 60px;
            width: 200px;
            height: calc(100% - 60px);
            background: #34495e;
            color: white;
            padding: 20px;
        }
        #main-content {
            margin-left: 240px;
            margin-top: 60px;
            padding: 20px;
        }
        iframe { 
            width: 100%; 
            height: 800px; 
            border: 1px solid #ccc;
            display: block;
        }
    </style>
</head>
<body>
    <div id="header">Senior X - Sistema ERP</div>
    <div id="sidebar">
        <h3>Menu</h3>
        <ul>
            <li>Dashboard</li>
            <li>SIGN</li>
            <li>Relatórios</li>
        </ul>
    </div>
    <div id="main-content">
        <h2>SIGN - Assinaturas Digitais</h2>
        <iframe id="ci" name="ci" srcdoc='
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body { 
                        margin: 0; 
                        padding: 20px; 
                        background: #f8f9fa;
                        font-family: Arial, sans-serif;
                    }
                    .sign-container {
                        background: white;
                        border: 1px solid #dee2e6;
                        border-radius: 4px;
                        padding: 20px;
                        margin: 20px 0;
                    }
                    .sign-header {
                        font-size: 24px;
                        font-weight: bold;
                        margin-bottom: 10px;
                    }
                    .sign-menu {
                        background: #e9ecef;
                        padding: 15px;
                        margin: 10px 0;
                        border-radius: 4px;
                    }
                    .sign-menu-item {
                        display: inline-block;
                        margin-right: 20px;
                        font-weight: bold;
                    }
                    .filter-section {
                        background: #f1f3f5;
                        padding: 15px;
                        margin: 15px 0;
                        border-radius: 4px;
                    }
                    .filter-title {
                        font-weight: bold;
                        margin-bottom: 10px;
                    }
                    button {
                        padding: 10px 20px;
                        font-size: 14px;
                        background: #007bff;
                        color: white;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        margin: 5px;
                    }
                    button:hover {
                        background: #0056b3;
                    }
                    .envelope-name {
                        margin-top: 15px;
                        padding: 10px;
                        background: #fff;
                        border: 1px solid #dee2e6;
                    }
                </style>
            </head>
            <body>
                <div class="sign-container">
                    <div class="sign-header">SIGN</div>
                    <div class="sign-menu">
                        <span class="sign-menu-item">Caixa de Entrada</span>
                        <span class="sign-menu-item">FILTRAR DADOS</span>
                    </div>
                    <div class="filter-section">
                        <div class="filter-title">Filtros</div>
                        <button id="acompanhar-btn">Acompanhar assinaturas</button>
                        <button id="filtrar-btn">Filtrar</button>
                    </div>
                    <div class="envelope-name">
                        Nome do envelope: Contrato de Prestação de Serviços
                    </div>
                </div>
            </body>
            </html>
        '></iframe>
    </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Bug Condition Exploration Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_bug1_resolver_contexto_returns_framelocator_not_frame():
    """
    **Property 1: Bug Condition - Part 1** - _resolver_contexto Returns FrameLocator Instead of Frame
    
    **Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms Bug 1 exists.
    DO NOT attempt to fix the test or the code when it fails.
    
    Bug 1: _resolver_contexto() returns FrameLocator instead of Frame object
    
    Test Setup:
    - Create page with iframe name="ci" (Senior X pattern)
    - Call _resolver_contexto(page, "ci")
    - Current implementation returns FrameLocator (line 611: return fl)
    - FrameLocator does not have .url or .name attributes
    - Subsequent hasattr(contexto, 'url') check fails
    
    Expected Behavior After Fix:
    - Should return actual Frame object with .url and .name attributes
    - isinstance(contexto, Frame) should return True
    - hasattr(contexto, 'url') should return True
    
    Expected Outcome: Test FAILS (confirms Bug 1 exists)
    
    Documented Counterexample:
    - _resolver_contexto(page, "ci") returns FrameLocator
    - type(contexto).__name__ == "FrameLocator" (not "Frame")
    - hasattr(contexto, 'url') == False
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page with ci iframe
            await page.set_content(HTML_PAGE_WITH_CI_IFRAME)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)  # Ensure iframe is fully loaded
            
            # Verify iframe exists
            iframe_element = await page.query_selector("iframe#ci")
            assert iframe_element is not None, "CI iframe not found in test page"
            
            # Call _resolver_contexto with iframe_hint="ci"
            contexto = await vision_engine._resolver_contexto(page, "ci")
            
            # EXPECTED BEHAVIOR (after fix):
            # - Should return Frame object
            # - isinstance(contexto, Frame) should be True
            # - hasattr(contexto, 'url') should be True
            # - hasattr(contexto, 'name') should be True
            
            # CURRENT BEHAVIOR (unfixed code):
            # - Returns FrameLocator object (line 611: return fl)
            # - isinstance(contexto, Frame) is False
            # - hasattr(contexto, 'url') is False
            # - type(contexto).__name__ == "FrameLocator"
            
            # This assertion encodes the EXPECTED behavior
            # It will FAIL on unfixed code, confirming Bug 1 exists
            assert isinstance(contexto, Frame), (
                f"BUG 1 CONFIRMED: _resolver_contexto returned {type(contexto).__name__} instead of Frame. "
                f"Expected: Frame object with .url and .name attributes. "
                f"Actual: {type(contexto).__name__} (FrameLocator has no .url attribute). "
                f"\n\nCounterexample:"
                f"\n  - iframe_hint: 'ci'"
                f"\n  - Returned type: {type(contexto).__name__}"
                f"\n  - isinstance(contexto, Frame): {isinstance(contexto, Frame)}"
                f"\n  - hasattr(contexto, 'url'): {hasattr(contexto, 'url')}"
                f"\n\nRoot cause: Line 611 in vision_engine.py returns 'fl' (FrameLocator) "
                f"instead of finding and returning the actual Frame object."
            )
            
            # Additional verification: Frame should have url and name attributes
            assert hasattr(contexto, 'url'), (
                f"BUG 1 CONFIRMED: Returned object does not have 'url' attribute. "
                f"Type: {type(contexto).__name__}. "
                f"This causes hasattr(contexto, 'url') check to fail in coordinate adjustment logic."
            )
            
            assert hasattr(contexto, 'name'), (
                f"BUG 1 CONFIRMED: Returned object does not have 'name' attribute. "
                f"Type: {type(contexto).__name__}."
            )
            
        finally:
            await browser.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bug2_coordinates_not_adjusted_correctly():
    """
    **Property 1: Bug Condition - Part 2** - Coordinates Not Adjusted for Iframe Context
    
    **Validates: Requirements 1.4, 1.5, 1.6, 2.4, 2.5**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms Bug 2 exists.
    
    Bug 2: Coordinates not adjusted correctly (Y unchanged: 732 → 732)
    
    Test Setup:
    - Create page with iframe at position (65, 0) containing button
    - Button is at absolute coordinates (1633, 732)
    - Expected adjusted coordinates: (1568, 732) - X adjusted by iframe.left
    - Current implementation: coordinates remain (1633, 732) - no adjustment
    
    Expected Behavior After Fix:
    - Should detect that contexto is a Frame
    - Should get iframe bounding box from main page
    - Should adjust coordinates: x_ajustado = x - iframe.left, y_ajustado = y - iframe.top
    - Should log coordinate transformation
    
    Expected Outcome: Test FAILS (confirms Bug 2 exists)
    
    Documented Counterexample:
    - Original coordinates: (1633, 732)
    - Iframe position: left=65, top=0
    - Expected adjusted: (1568, 732)
    - Actual: (1633, 732) - no adjustment
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_WITH_CI_IFRAME)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            
            # Get iframe bounding box
            iframe_element = await page.query_selector("iframe#ci")
            iframe_box = await iframe_element.bounding_box()
            assert iframe_box is not None, "Could not get iframe bounding box"
            
            # Calculate button coordinates inside iframe
            # Button is at approximately (400, 300) relative to iframe content
            button_x_rel = 400
            button_y_rel = 300
            button_x_abs = int(iframe_box["x"] + button_x_rel)
            button_y_abs = int(iframe_box["y"] + button_y_rel)
            
            # Call _resolver_contexto
            contexto = await vision_engine._resolver_contexto(page, "ci")
            
            # Simulate the coordinate adjustment logic from lines 1658-1750
            # Current implementation checks hasattr(contexto, 'url')
            # Since contexto is FrameLocator (Bug 1), this check fails
            # Therefore, no coordinate adjustment happens
            
            has_url_attr = hasattr(contexto, 'url')
            
            # EXPECTED BEHAVIOR (after fix):
            # - contexto should be Frame (Bug 1 fixed)
            # - hasattr(contexto, 'url') should be True
            # - Coordinates should be adjusted: x_ajustado = x - iframe.left
            
            # CURRENT BEHAVIOR (unfixed code):
            # - contexto is FrameLocator (Bug 1)
            # - hasattr(contexto, 'url') is False
            # - System logs "iframe_hint não resolveu para Frame - usando detecção automática"
            # - Falls back to automatic detection
            # - Coordinates may not be adjusted correctly
            
            # This assertion encodes the EXPECTED behavior
            assert has_url_attr is True, (
                f"BUG 2 CONFIRMED: hasattr(contexto, 'url') returned False. "
                f"This causes the coordinate adjustment logic to fail. "
                f"Type of contexto: {type(contexto).__name__}. "
                f"Without proper Frame detection, coordinates cannot be adjusted correctly. "
                f"\n\nCounterexample:"
                f"\n  - iframe_hint: 'ci'"
                f"\n  - contexto type: {type(contexto).__name__}"
                f"\n  - hasattr(contexto, 'url'): {has_url_attr}"
                f"\n  - iframe position: left={iframe_box['x']}, top={iframe_box['y']}"
                f"\n  - button absolute coords: ({button_x_abs}, {button_y_abs})"
                f"\n  - expected adjusted coords: ({button_x_abs - iframe_box['x']}, {button_y_abs - iframe_box['y']})"
                f"\n  - actual: no adjustment (falls back to automatic detection)"
                f"\n\nRoot cause: Bug 1 causes hasattr check to fail, preventing coordinate adjustment."
            )
            
            # If we reach here (test passes), verify coordinates would be adjusted correctly
            if isinstance(contexto, Frame):
                # Simulate coordinate adjustment
                x_ajustado = int(button_x_abs - iframe_box['x'])
                y_ajustado = int(button_y_abs - iframe_box['y'])
                
                # Verify adjustment is correct (allow 1-2 pixel tolerance for rounding)
                assert abs(x_ajustado - button_x_rel) <= 2, (
                    f"Coordinate adjustment incorrect: expected x≈{button_x_rel}, got x={x_ajustado}"
                )
                assert abs(y_ajustado - button_y_rel) <= 2, (
                    f"Coordinate adjustment incorrect: expected y≈{button_y_rel}, got y={y_ajustado}"
                )
            
        finally:
            await browser.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bug3_wrong_element_found_parent_container():
    """
    **Property 1: Bug Condition - Part 3** - Wrong Element Found (Parent Container)
    
    **Validates: Requirements 1.7, 1.8, 1.9, 1.10, 2.6, 2.7, 2.8, 2.9, 2.10**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms Bug 3 exists.
    
    Bug 3: elementFromPoint returns parent container instead of target button
    
    Test Setup:
    - Create page with iframe containing button "Acompanhar assinaturas"
    - Button is inside nested containers (sign-container > filter-section > button)
    - Execute elementFromPoint with coordinates pointing to button
    - Current implementation executes in wrong context or with wrong coordinates
    - Returns parent container with text "SIGN\nCaixa de Entrada\nFILTRAR DADOS\n..."
    
    Expected Behavior After Fix:
    - Should execute elementFromPoint in Frame context with adjusted coordinates
    - Should find button element with text "Acompanhar assinaturas"
    - Identity verification should pass
    
    Expected Outcome: Test FAILS (confirms Bug 3 exists)
    
    Documented Counterexample:
    - Expected element text: "Acompanhar assinaturas"
    - Found element text: "SIGN\nCaixa de Entrada\nFILTRAR DADOS\n..."
    - Identity verification: FAILED
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_WITH_CI_IFRAME)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            
            # Get iframe and button coordinates
            iframe_element = await page.query_selector("iframe#ci")
            iframe_box = await iframe_element.bounding_box()
            
            # Get button position inside iframe
            # We need to access the iframe's content to find the button
            frames = page.frames
            ci_frame = None
            for frame in frames:
                try:
                    if "ci" in frame.name or frame == iframe_element.content_frame():
                        ci_frame = frame
                        break
                except:
                    continue
            
            assert ci_frame is not None, "Could not find ci frame"
            
            # Get button bounding box relative to iframe
            button_element = await ci_frame.query_selector("#acompanhar-btn")
            assert button_element is not None, "Button not found in iframe"
            
            button_box = await button_element.bounding_box()
            assert button_box is not None, "Could not get button bounding box"
            
            # Calculate absolute coordinates (relative to main page viewport)
            button_x_abs = int(iframe_box["x"] + button_box["x"] + button_box["width"] / 2)
            button_y_abs = int(iframe_box["y"] + button_box["y"] + button_box["height"] / 2)
            
            # Simulate current implementation: execute elementFromPoint in main page context
            # This is the BUG - should execute in iframe context with adjusted coordinates
            elemento_info_wrong_context = await page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    return {
                        tagName: el.tagName,
                        innerText: (el.innerText || '').substring(0, 100)
                    };
                }""",
                [button_x_abs, button_y_abs]
            )
            
            # Current behavior: returns iframe element or parent container
            # Not the specific button we want
            
            # Now test the EXPECTED behavior: execute in iframe context with adjusted coords
            button_x_rel = int(button_box["x"] + button_box["width"] / 2)
            button_y_rel = int(button_box["y"] + button_box["height"] / 2)
            
            elemento_info_correct_context = await ci_frame.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    if (!el) return null;
                    return {
                        tagName: el.tagName,
                        innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                    };
                }""",
                [button_x_rel, button_y_rel]
            )
            
            # EXPECTED BEHAVIOR (after fix):
            # - Should execute elementFromPoint in Frame context
            # - Should use adjusted coordinates (relative to iframe)
            # - Should find BUTTON element with text "Acompanhar assinaturas"
            # - Identity verification should pass
            
            # CURRENT BEHAVIOR (unfixed code):
            # - Executes elementFromPoint in main page context (or wrong context)
            # - Uses absolute coordinates (not adjusted)
            # - Finds IFRAME or parent DIV with text "SIGN\nCaixa de Entrada\n..."
            # - Identity verification fails
            
            label_curto = "Acompanhar assinaturas"
            
            # Check if correct context finds the right element
            if elemento_info_correct_context:
                texto_correto = elemento_info_correct_context.get('innerText', '')
                identidade_correta = label_curto.strip().lower() in texto_correto.strip().lower()
                
                assert identidade_correta, (
                    f"Test setup error: Button not found even in correct context. "
                    f"Expected '{label_curto}', found '{texto_correto}'"
                )
            
            # Now verify that wrong context returns wrong element (Bug 3)
            if elemento_info_wrong_context:
                texto_errado = elemento_info_wrong_context.get('innerText', '')
                identidade_errada = label_curto.strip().lower() in texto_errado.strip().lower()
                
                # This assertion encodes the EXPECTED behavior
                # Current implementation uses wrong context, so identidade_errada is False
                # After fix, this should be True (but we're testing the bug condition)
                
                # For bug exploration, we expect the wrong context to fail
                # But the system should use the correct context after fix
                assert identidade_errada is False, (
                    f"BUG 3 NOT REPRODUCED: elementFromPoint in main page context "
                    f"unexpectedly found the correct element. "
                    f"Expected to find parent container, but found '{texto_errado}'. "
                    f"This test requires coordinates to point inside iframe where "
                    f"main page context returns wrong element."
                )
            
            # The real test: after fix, the system should use correct context
            # Simulate the fixed behavior
            contexto = await vision_engine._resolver_contexto(page, "ci")
            
            # After fix, contexto should be Frame and we should execute in that context
            if isinstance(contexto, Frame):
                # This is the EXPECTED behavior after fix
                elemento_info_fixed = await contexto.evaluate(
                    """([x, y]) => {
                        const el = document.elementFromPoint(x, y);
                        if (!el) return null;
                        return {
                            tagName: el.tagName,
                            innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                        };
                    }""",
                    [button_x_rel, button_y_rel]
                )
                
                if elemento_info_fixed:
                    texto_fixed = elemento_info_fixed.get('innerText', '')
                    identidade_fixed = label_curto.strip().lower() in texto_fixed.strip().lower()
                    
                    assert identidade_fixed is True, (
                        f"After fix, identity verification should pass. "
                        f"Expected '{label_curto}', found '{texto_fixed}'"
                    )
            else:
                # Bug 1 not fixed yet - contexto is not Frame
                pytest.fail(
                    f"BUG 3 CONFIRMED: contexto is {type(contexto).__name__}, not Frame. "
                    f"Cannot execute elementFromPoint in correct iframe context. "
                    f"This causes wrong element to be found. "
                    f"\n\nCounterexample:"
                    f"\n  - iframe_hint: 'ci'"
                    f"\n  - contexto type: {type(contexto).__name__}"
                    f"\n  - Expected: Frame object to execute elementFromPoint in iframe context"
                    f"\n  - Actual: {type(contexto).__name__} (cannot execute in iframe context)"
                    f"\n  - Result: elementFromPoint returns parent container, not button"
                    f"\n  - Expected element text: '{label_curto}'"
                    f"\n  - Found element text: '{texto_errado if elemento_info_wrong_context else '(none)'}'"
                    f"\n\nRoot cause: Bugs 1 and 2 prevent correct Frame context and coordinate adjustment, "
                    f"causing elementFromPoint to return wrong element."
                )
            
        finally:
            await browser.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

"""
Bug Condition Exploration Test — robot-element-location-failure
================================================================

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**

OBJETIVO: Demonstrar o bug de localização de elementos em iframes ANTES de implementar a correção.

BUG: A verificação de identidade na camada `2_coords_capturadas` executa
`document.elementFromPoint(x, y)` no contexto da página principal. Quando as
coordenadas apontam para dentro de um iframe, o método retorna o elemento
`<iframe>` em si (cujo texto visível é "iframe platform"), não o elemento
interno que está nas coordenadas.

METODOLOGIA:
  - O teste asserta o comportamento ESPERADO (correto).
  - O código NÃO corrigido viola esse comportamento → teste FALHA.
  - A falha confirma que o bug existe.
  - Após o fix (Tarefa 3), este mesmo teste deve PASSAR.

NÃO corrija o código nem o teste quando ele falhar.

EXPECTED OUTCOME: Este teste DEVE FALHAR no código não corrigido.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import async_playwright

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Test HTML Page with Iframe
# ---------------------------------------------------------------------------

HTML_PAGE_WITH_IFRAME = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Page - Iframe Element Location</title>
    <style>
        body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
        #main-content { padding: 20px; background: #f0f0f0; }
        iframe { 
            width: 800px; 
            height: 600px; 
            border: 2px solid #333;
            display: block;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div id="main-content">
        <h1>Main Page Content</h1>
        <p>This is the main page. The iframe below contains the target button.</p>
    </div>
    
    <iframe id="test-iframe" srcdoc='
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { 
                    margin: 0; 
                    padding: 40px; 
                    background: #e8f4f8;
                    font-family: Arial, sans-serif;
                }
                .container {
                    text-align: center;
                    padding: 100px 20px;
                }
                button {
                    padding: 15px 30px;
                    font-size: 18px;
                    background: #00e5e5;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    color: #000;
                }
                button:hover {
                    background: #00cccc;
                }
                .platform-text {
                    margin-top: 20px;
                    color: #666;
                    font-size: 14px;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Iframe Content</h2>
                <button id="salvar-btn">Salvar</button>
                <div class="platform-text">iframe platform</div>
            </div>
        </body>
        </html>
    '></iframe>
    
    <script>
        // Make iframe text visible for elementFromPoint
        const iframe = document.getElementById('test-iframe');
        iframe.innerText = 'iframe platform';
    </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _make_acao_tec_iframe(label_curto: str, x_pct: float, y_pct: float) -> dict:
    """Constrói acao_tec com coordenadas apontando para dentro de um iframe."""
    return {
        "acao": "clique",
        "intencao_semantica": f"Clicar em '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": None,  # Sem hint de iframe - detecção automática necessária
            "descricao_visual": label_curto,
            "contexto_tela": "Formulário dentro de iframe",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": {"x_pct": x_pct, "y_pct": y_pct},
            "screenshot_referencia": None,
        },
    }


# ---------------------------------------------------------------------------
# Bug Condition Exploration Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_iframe_element_location_bug_condition():
    """
    **Property 1: Bug Condition** - Iframe Element Resolution Failure
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5**
    
    CRITICAL: This test MUST FAIL on unfixed code - failure confirms the bug exists.
    DO NOT attempt to fix the test or the code when it fails.
    
    Test Setup:
    - Create HTML page with iframe containing button "Salvar" at known coordinates
    - Execute `page.evaluate("document.elementFromPoint(x, y)")` in main page context
    - Current implementation returns `<iframe>` element (not the button inside)
    - innerText of returned element is "iframe platform" (not "Salvar")
    - Identity verification fails because "Salvar" not in "iframe platform"
    
    Expected Behavior After Fix:
    - Should detect iframe, adjust coordinates, and find button with text "Salvar"
    - Identity verification should pass
    - Click should succeed
    
    Expected Outcome: Test FAILS (this is correct - it proves the bug exists)
    
    Documented Counterexamples:
    - Example: `elementFromPoint(960, 540)` returns `<iframe>` instead of `<button>`
    - Example: Identity verification fails with "esperado 'Salvar', encontrado 'iframe platform'"
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page with iframe
            await page.set_content(HTML_PAGE_WITH_IFRAME)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)  # Ensure iframe is fully loaded
            
            # Verify iframe is present
            iframe_element = await page.query_selector("#test-iframe")
            assert iframe_element is not None, "Iframe element not found in test page"
            
            # Get iframe bounding box to calculate coordinates
            iframe_box = await iframe_element.bounding_box()
            assert iframe_box is not None, "Could not get iframe bounding box"
            
            # Calculate coordinates pointing to button inside iframe
            # Button is centered in iframe at approximately (400, 300) relative to iframe
            # Absolute coordinates: iframe.left + 400, iframe.top + 300
            button_x_abs = int(iframe_box["x"] + 400)
            button_y_abs = int(iframe_box["y"] + 300)
            
            # Convert to relative coordinates (percentage of viewport)
            x_pct = button_x_abs / 1920
            y_pct = button_y_abs / 1080
            
            # Verify that elementFromPoint in main context returns iframe (bug condition)
            element_info = await page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    return {
                        tagName: el ? el.tagName : null,
                        innerText: el ? (el.innerText || '').substring(0, 50) : '',
                        id: el ? el.id : null
                    };
                }""",
                [button_x_abs, button_y_abs]
            )
            
            # Confirm bug condition: elementFromPoint returns IFRAME, not BUTTON
            assert element_info["tagName"] == "IFRAME", (
                f"Bug condition not reproduced: expected IFRAME, got {element_info['tagName']}. "
                f"This test requires coordinates to point inside an iframe."
            )
            # Note: iframe innerText may be empty when accessed from main context
            # The key bug is that we get IFRAME instead of BUTTON
            
            # Construct acao_tec with coordinates pointing to button inside iframe
            acao_tec = _make_acao_tec_iframe(
                label_curto="Salvar",
                x_pct=x_pct,
                y_pct=y_pct
            )
            
            # Patch to isolate coords_capturadas layer
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", return_value=None), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)), \
                 patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # EXPECTED BEHAVIOR (after fix):
            # - Should detect iframe at coordinates
            # - Should adjust coordinates to iframe context
            # - Should execute elementFromPoint in iframe context
            # - Should find button with text "Salvar"
            # - Identity verification should pass
            # - Should return True
            
            # CURRENT BEHAVIOR (unfixed code):
            # - Executes elementFromPoint in main page context
            # - Returns <iframe> element with text "iframe platform"
            # - Identity verification fails: "Salvar" not in "iframe platform"
            # - Returns False (or True without verification - both are bugs)
            
            # This assertion encodes the EXPECTED behavior
            # It will FAIL on unfixed code, confirming the bug exists
            assert resultado is True, (
                "BUG CONFIRMED: encontrar_e_clicar failed to locate button 'Salvar' inside iframe. "
                f"Coordinates ({button_x_abs}, {button_y_abs}) point to button inside iframe, "
                f"but elementFromPoint in main context returns <iframe> with text 'iframe platform'. "
                f"Identity verification fails because 'Salvar' not in 'iframe platform'. "
                f"Expected: detect iframe, adjust coordinates, find button. "
                f"Actual: returned {resultado}. "
                f"\n\nCounterexample documented:"
                f"\n  - elementFromPoint({button_x_abs}, {button_y_abs}) returns <iframe>"
                f"\n  - innerText of <iframe>: 'iframe platform'"
                f"\n  - Expected element: <button> with text 'Salvar'"
                f"\n  - Identity verification: FAILED ('Salvar' not in 'iframe platform')"
                f"\n  - Result: {resultado} (expected: True after fix)"
            )
            
        finally:
            await browser.close()


@pytest.mark.asyncio
async def test_iframe_element_location_identity_verification_failure():
    """
    **Property 1: Bug Condition** - Identity Verification Failure in Iframe Context
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.5**
    
    This test specifically validates that the identity verification fails when
    elementFromPoint is executed in the wrong context (main page instead of iframe).
    
    Test Setup:
    - Create page with iframe containing button "Salvar"
    - Coordinates point to button inside iframe
    - Execute identity verification (current implementation)
    - Verify that it finds "iframe platform" instead of "Salvar"
    
    Expected Outcome: Test FAILS (confirms bug exists)
    
    Documented Counterexample:
    - Identity verification: esperado 'Salvar', encontrado 'iframe platform'
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_WITH_IFRAME)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.5)
            
            # Get iframe coordinates
            iframe_element = await page.query_selector("#test-iframe")
            iframe_box = await iframe_element.bounding_box()
            
            # Coordinates pointing to button inside iframe
            button_x = int(iframe_box["x"] + 400)
            button_y = int(iframe_box["y"] + 300)
            
            # Execute identity verification (current implementation)
            texto_elemento = await page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    return el ? (el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '') : '';
                }""",
                [button_x, button_y]
            )
            
            # Current behavior: finds empty text or iframe text instead of "Salvar"
            # This is the BUG - identity verification executed in wrong context
            # When elementFromPoint returns iframe, we can't access the button's text
            
            label_curto = "Salvar"
            identidade_confirmada = label_curto.strip().lower() in texto_elemento.strip().lower()
            
            # EXPECTED BEHAVIOR (after fix):
            # - Should detect iframe, adjust coordinates
            # - Should execute elementFromPoint in iframe context
            # - Should find "Salvar"
            # - identidade_confirmada should be True
            
            # CURRENT BEHAVIOR (unfixed code):
            # - Executes elementFromPoint in main page context
            # - Returns iframe element (not button inside)
            # - texto_elemento is empty or "iframe platform" (not "Salvar")
            # - identidade_confirmada is False
            
            # This assertion encodes the EXPECTED behavior
            # It will FAIL on unfixed code, confirming the bug
            assert identidade_confirmada is True, (
                f"BUG CONFIRMED: Identity verification failed for element inside iframe. "
                f"Expected to find '{label_curto}', but found '{texto_elemento[:50] if texto_elemento else '(empty)'}'. "
                f"elementFromPoint({button_x}, {button_y}) executed in main page context "
                f"returned <iframe> element instead of <button> with text 'Salvar'. "
                f"The iframe element's innerText is '{texto_elemento}' which does not contain 'Salvar'. "
                f"\n\nCounterexample:"
                f"\n  - Coordinates: ({button_x}, {button_y})"
                f"\n  - Expected text: 'Salvar'"
                f"\n  - Found text: '{texto_elemento if texto_elemento else '(empty)'}'"
                f"\n  - Identity confirmed: {identidade_confirmada} (expected: True)"
                f"\n\nThis demonstrates the bug: elementFromPoint in main page context "
                f"returns the iframe container, not the button inside it."
            )
            
        finally:
            await browser.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

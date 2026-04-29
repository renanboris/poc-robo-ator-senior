"""
Preservation Property Tests — robot-element-location-failure
=============================================================

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

OBJETIVO: Confirmar o baseline a preservar ANTES do fix.

Property 2 (Preservation): Para todo `acao_tec` onde `NOT isBugCondition(acao_tec)`
(coordenadas NÃO apontam para dentro de iframes), o comportamento de `encontrar_e_clicar`
é idêntico entre o código original e o código corrigido.

METODOLOGIA:
  - Observar comportamento no código NÃO CORRIGIDO para entradas não-buggy
  - Escrever testes baseados em propriedades capturando esse comportamento
  - Executar testes no código NÃO CORRIGIDO
  - EXPECTED OUTCOME: Todos os testes PASSAM (confirma baseline correto)
  - Após o fix (Tarefa 3), estes mesmos testes devem continuar PASSANDO

RESULTADO ESPERADO: Todos os testes PASSAM no código NÃO corrigido.
Isso confirma que o baseline está correto e que o fix não deve regredir esses casos.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from playwright.async_api import async_playwright

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Test HTML Pages - Non-Iframe Elements
# ---------------------------------------------------------------------------

HTML_PAGE_MAIN_CONTENT = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Page - Main Content</title>
    <style>
        body { margin: 0; padding: 20px; font-family: Arial, sans-serif; }
        .container { padding: 40px; }
        button {
            padding: 15px 30px;
            font-size: 18px;
            background: #00e5e5;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            color: #000;
            margin: 10px;
        }
        button:hover { background: #00cccc; }
        input {
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ccc;
            border-radius: 4px;
            margin: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Main Page Content</h1>
        <p>Elements outside iframes for preservation testing</p>
        <button id="salvar-btn">Salvar</button>
        <button id="cancelar-btn">Cancelar</button>
        <button id="confirmar-btn">Confirmar</button>
        <input type="text" id="nome-input" placeholder="Digite seu nome" />
    </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _make_acao_tec_main_page(label_curto: str, x_pct: float, y_pct: float, acao: str = "clique") -> dict:
    """Constrói acao_tec com coordenadas apontando para elemento na página principal (fora de iframe)."""
    return {
        "acao": acao,
        "intencao_semantica": f"Clicar em '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Página principal",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": {"x_pct": x_pct, "y_pct": y_pct},
            "screenshot_referencia": None,
        },
    }


def _make_acao_tec_empty_label(x_pct: float, y_pct: float) -> dict:
    """Constrói acao_tec com label_curto vazio (fail-open case)."""
    return {
        "acao": "clique",
        "intencao_semantica": "Clicar em elemento sem label",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": "",  # Empty label - fail-open case
            "seletor_hint": "",
            "iframe_hint": None,
            "descricao_visual": "Elemento sem label",
            "contexto_tela": "Página principal",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": {"x_pct": x_pct, "y_pct": y_pct},
            "screenshot_referencia": None,
        },
    }


# ---------------------------------------------------------------------------
# Preservation Test 1: Non-Iframe Element Behavior
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_preservation_non_iframe_element_identity_verification():
    """
    **Property 2: Preservation** - Non-Iframe Element Behavior
    
    **Validates: Requirements 3.1, 3.4**
    
    Test Setup:
    - Create HTML page with button "Salvar" in main page (outside iframe)
    - Coordinates point to button at (100, 100)
    - Execute identity verification (current implementation)
    - Verify that elementFromPoint returns <button> with correct text
    - Verify that identity verification passes
    - Verify that telemetry registers success for 2_coords_capturadas
    
    Expected Outcome: Test PASSES (confirms baseline behavior to preserve)
    
    Preservation Property:
    - For all coordinates pointing to elements outside iframes, identity verification
      behaves exactly as before (no iframe detection needed)
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page with main content (no iframes)
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)
            
            # Get button coordinates
            button = await page.query_selector("#salvar-btn")
            assert button is not None, "Button not found in test page"
            
            button_box = await button.bounding_box()
            assert button_box is not None, "Could not get button bounding box"
            
            # Calculate center coordinates
            button_x = int(button_box["x"] + button_box["width"] / 2)
            button_y = int(button_box["y"] + button_box["height"] / 2)
            
            # Convert to relative coordinates
            x_pct = button_x / 1920
            y_pct = button_y / 1080
            
            # Verify that elementFromPoint returns button (not iframe)
            element_info = await page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    return {
                        tagName: el ? el.tagName : null,
                        innerText: el ? (el.innerText || '').trim() : '',
                        id: el ? el.id : null
                    };
                }""",
                [button_x, button_y]
            )
            
            # Confirm baseline behavior: elementFromPoint returns BUTTON (not IFRAME)
            assert element_info["tagName"] == "BUTTON", (
                f"Baseline behavior changed: expected BUTTON, got {element_info['tagName']}"
            )
            assert "Salvar" in element_info["innerText"], (
                f"Baseline behavior changed: expected 'Salvar' in text, got '{element_info['innerText']}'"
            )
            
            # Construct acao_tec
            acao_tec = _make_acao_tec_main_page(
                label_curto="Salvar",
                x_pct=x_pct,
                y_pct=y_pct
            )
            
            # Track telemetry calls
            telemetry_calls = []
            
            def mock_registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = ""):
                telemetry_calls.append({"camada": camada, "acertou": acertou})
            
            # Patch to isolate coords_capturadas layer
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", side_effect=mock_registrar_telemetria), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)), \
                 patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # PRESERVATION PROPERTY:
            # - elementFromPoint returns button (not iframe)
            # - Identity verification passes (text matches)
            # - Telemetry registers success for 2_coords_capturadas
            # - Result is True
            
            assert resultado is True, (
                f"Preservation property violated: encontrar_e_clicar should succeed for "
                f"non-iframe element. Expected: True, Got: {resultado}"
            )
            
            # Verify telemetry was called with success
            success_telemetry = [t for t in telemetry_calls if t["camada"] == "2_coords_capturadas" and t["acertou"]]
            assert len(success_telemetry) > 0, (
                f"Preservation property violated: telemetry should register success for "
                f"2_coords_capturadas. Telemetry calls: {telemetry_calls}"
            )
            
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Preservation Test 2: Fail-Open Behavior - Empty Label
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_preservation_fail_open_empty_label():
    """
    **Property 2: Preservation** - Fail-Open Behavior (Empty Label)
    
    **Validates: Requirements 3.3**
    
    Test Setup:
    - Create HTML page with button in main page
    - Coordinates point to button
    - label_curto is empty (fail-open case)
    - Execute identity verification
    - Verify that identity verification is skipped
    - Verify that click is accepted
    
    Expected Outcome: Test PASSES (confirms baseline fail-open behavior)
    
    Preservation Property:
    - For all clicks with empty label_curto, identity verification is skipped
      and click is accepted (fail-open behavior unchanged)
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)
            
            # Get button coordinates
            button = await page.query_selector("#salvar-btn")
            button_box = await button.bounding_box()
            
            button_x = int(button_box["x"] + button_box["width"] / 2)
            button_y = int(button_box["y"] + button_box["height"] / 2)
            
            x_pct = button_x / 1920
            y_pct = button_y / 1080
            
            # Construct acao_tec with EMPTY label_curto
            acao_tec = _make_acao_tec_empty_label(x_pct=x_pct, y_pct=y_pct)
            
            # Track telemetry calls
            telemetry_calls = []
            
            def mock_registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = ""):
                telemetry_calls.append({"camada": camada, "acertou": acertou})
            
            # Patch to isolate coords_capturadas layer
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", side_effect=mock_registrar_telemetria), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)), \
                 patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # PRESERVATION PROPERTY (Fail-Open):
            # - When label_curto is empty, identity verification is skipped
            # - Click is accepted without verification
            # - Result is True
            
            assert resultado is True, (
                f"Preservation property violated: fail-open behavior should accept click "
                f"when label_curto is empty. Expected: True, Got: {resultado}"
            )
            
            # Verify telemetry registered success
            success_telemetry = [t for t in telemetry_calls if t["camada"] == "2_coords_capturadas" and t["acertou"]]
            assert len(success_telemetry) > 0, (
                f"Preservation property violated: telemetry should register success for "
                f"fail-open case. Telemetry calls: {telemetry_calls}"
            )
            
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Preservation Test 3: Fail-Open Behavior - Exception Handling
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_preservation_fail_open_exception():
    """
    **Property 2: Preservation** - Fail-Open Behavior (Exception)
    
    **Validates: Requirements 3.3**
    
    Test Setup:
    - Mock page.evaluate to throw exception
    - Coordinates point to valid element
    - Execute identity verification
    - Verify that exception is caught
    - Verify that fail-open is applied (click accepted)
    
    Expected Outcome: Test PASSES (confirms baseline fail-open behavior)
    
    Preservation Property:
    - When page.evaluate throws exception, fail-open is applied
      and click is accepted (behavior unchanged)
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)
            
            # Get button coordinates
            button = await page.query_selector("#salvar-btn")
            button_box = await button.bounding_box()
            
            button_x = int(button_box["x"] + button_box["width"] / 2)
            button_y = int(button_box["y"] + button_box["height"] / 2)
            
            x_pct = button_x / 1920
            y_pct = button_y / 1080
            
            # Construct acao_tec
            acao_tec = _make_acao_tec_main_page(
                label_curto="Salvar",
                x_pct=x_pct,
                y_pct=y_pct
            )
            
            # Track telemetry calls
            telemetry_calls = []
            
            def mock_registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = ""):
                telemetry_calls.append({"camada": camada, "acertou": acertou})
            
            # Mock page.evaluate to throw exception during identity verification
            original_evaluate = page.evaluate
            
            async def mock_evaluate_with_exception(script, *args, **kwargs):
                # Only throw exception for elementFromPoint calls (identity verification)
                if "elementFromPoint" in str(script):
                    raise Exception("Simulated page.evaluate exception")
                return await original_evaluate(script, *args, **kwargs)
            
            # Patch to isolate coords_capturadas layer and inject exception
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", side_effect=mock_registrar_telemetria), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)), \
                 patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)), \
                 patch.object(page, "evaluate", side_effect=mock_evaluate_with_exception):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # PRESERVATION PROPERTY (Fail-Open on Exception):
            # - When page.evaluate throws exception, exception is caught
            # - Fail-open is applied: click is accepted
            # - Result is True
            
            assert resultado is True, (
                f"Preservation property violated: fail-open behavior should accept click "
                f"when page.evaluate throws exception. Expected: True, Got: {resultado}"
            )
            
            # Verify telemetry registered success
            success_telemetry = [t for t in telemetry_calls if t["camada"] == "2_coords_capturadas" and t["acertou"]]
            assert len(success_telemetry) > 0, (
                f"Preservation property violated: telemetry should register success for "
                f"fail-open case. Telemetry calls: {telemetry_calls}"
            )
            
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Property-Based Test: Non-Iframe Elements at Various Coordinates
# ---------------------------------------------------------------------------

@pytest.mark.integration
@given(
    x_offset=st.integers(min_value=50, max_value=200),
    y_offset=st.integers(min_value=50, max_value=150),
)
@settings(
    max_examples=10,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@pytest.mark.asyncio
async def test_preservation_property_non_iframe_coordinates(x_offset, y_offset):
    """
    **Property 2: Preservation** - Non-Iframe Element Behavior (Property-Based)
    
    **Validates: Requirements 3.1, 3.4**
    
    Property: For all coordinates pointing to elements outside iframes,
    identity verification behaves exactly as before (no iframe detection needed).
    
    This property-based test generates many coordinate variations to ensure
    the baseline behavior is preserved across the input space.
    
    Expected Outcome: Test PASSES for all generated coordinates (confirms baseline)
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.2)
            
            # Get button coordinates with offset
            button = await page.query_selector("#salvar-btn")
            button_box = await button.bounding_box()
            
            # Apply offset within button bounds
            button_x = int(button_box["x"] + min(x_offset, button_box["width"] - 10))
            button_y = int(button_box["y"] + min(y_offset, button_box["height"] - 10))
            
            x_pct = button_x / 1920
            y_pct = button_y / 1080
            
            # Verify elementFromPoint returns button
            element_info = await page.evaluate(
                """([x, y]) => {
                    const el = document.elementFromPoint(x, y);
                    return {
                        tagName: el ? el.tagName : null,
                        innerText: el ? (el.innerText || '').trim() : ''
                    };
                }""",
                [button_x, button_y]
            )
            
            # Skip if coordinates don't hit the button (edge case)
            if element_info["tagName"] != "BUTTON":
                return
            
            # Construct acao_tec
            acao_tec = _make_acao_tec_main_page(
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
            
            # PRESERVATION PROPERTY:
            # For all coordinates pointing to non-iframe elements,
            # behavior is unchanged (identity verification passes, click succeeds)
            assert resultado is True, (
                f"Preservation property violated at coordinates ({button_x}, {button_y}): "
                f"Expected: True, Got: {resultado}"
            )
            
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Preservation Test 4: Fail-Open Behavior - Invalid Coordinates
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_preservation_fail_open_invalid_coordinates():
    """
    **Property 2: Preservation** - Fail-Open Behavior (Invalid Coordinates)
    
    **Validates: Requirements 3.3**
    
    Test Setup:
    - Create HTML page with button in main page
    - Coordinates point OUTSIDE viewport (invalid coordinates)
    - Execute identity verification
    - Verify that exception is caught (coordinates invalid)
    - Verify that fail-open is applied (click accepted)
    
    Expected Outcome: Test PASSES (confirms baseline fail-open behavior)
    
    Preservation Property:
    - When coordinates are invalid and page.evaluate throws exception or returns null,
      fail-open is applied and click is accepted (behavior unchanged)
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)
            
            # Construct acao_tec with INVALID coordinates (outside viewport)
            # This triggers fail-open behavior
            acao_tec = _make_acao_tec_main_page(
                label_curto="Salvar",
                x_pct=2.0,  # Invalid: outside viewport
                y_pct=2.0   # Invalid: outside viewport
            )
            
            # Track telemetry calls
            telemetry_calls = []
            
            def mock_registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = ""):
                telemetry_calls.append({"camada": camada, "acertou": acertou})
            
            # Patch to isolate coords_capturadas layer
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", side_effect=mock_registrar_telemetria), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)), \
                 patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # PRESERVATION PROPERTY (Fail-Open on Invalid Coordinates):
            # - When coordinates are invalid (outside viewport), elementFromPoint returns null or throws
            # - Fail-open is applied: click is accepted
            # - Result is True
            
            assert resultado is True, (
                f"Preservation property violated: fail-open behavior should accept click "
                f"when coordinates are invalid. Expected: True, Got: {resultado}"
            )
            
            # Verify telemetry registered success (fail-open accepted the click)
            success_telemetry = [t for t in telemetry_calls if t["camada"] == "2_coords_capturadas" and t["acertou"]]
            assert len(success_telemetry) > 0, (
                f"Preservation property violated: telemetry should register success for "
                f"fail-open case. Telemetry calls: {telemetry_calls}"
            )
            
        finally:
            await browser.close()


# ---------------------------------------------------------------------------
# Preservation Test 5: Fallback Layers Triggered When Coords Fail
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.asyncio
async def test_preservation_fallback_layers_when_coords_unavailable():
    """
    **Property 2: Preservation** - Fallback Layers Triggered When Coords Unavailable
    
    **Validates: Requirements 3.2, 3.5**
    
    Test Setup:
    - Create HTML page with button "Salvar" in main page
    - NO coordinates provided (coords_relativas is None)
    - Verify that coords_capturadas is skipped
    - Verify that fallback layers (Sniper) are triggered
    - Verify that Sniper succeeds
    
    Expected Outcome: Test PASSES (confirms fallback layers work)
    
    Preservation Property:
    - When coords_capturadas is not available (no coordinates),
      other fallback layers (Sniper) are triggered and work correctly
    """
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()
        
        try:
            # Load test page
            await page.set_content(HTML_PAGE_MAIN_CONTENT)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(0.3)
            
            # Construct acao_tec WITHOUT coordinates (will skip coords_capturadas)
            acao_tec = {
                "acao": "clique",
                "intencao_semantica": "Clicar em 'Salvar'",
                "valor_input": "",
                "elemento_alvo": {
                    "label_curto": "Salvar",
                    "seletor_hint": "",
                    "iframe_hint": None,
                    "descricao_visual": "Salvar",
                    "contexto_tela": "Página principal",
                    "tipo_elemento": "button",
                    "html_hint": "",
                    "coordenadas_relativas": None,  # NO coordinates - will skip coords_capturadas
                    "screenshot_referencia": None,
                },
            }
            
            # Track which layers were called
            layers_called = []
            
            def mock_registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = ""):
                layers_called.append({"camada": camada, "acertou": acertou})
            
            # Patch to allow fallback layers to execute
            with patch.object(vision_engine, "_consultar_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_falha_cache", return_value=None), \
                 patch.object(vision_engine, "_registrar_telemetria", side_effect=mock_registrar_telemetria), \
                 patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None), \
                 patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)):
                
                # Execute encontrar_e_clicar
                resultado = await vision_engine.encontrar_e_clicar(page, acao_tec)
            
            # PRESERVATION PROPERTY:
            # - coords_capturadas is skipped (no coordinates)
            # - Fallback layers (Sniper) are triggered
            # - Sniper succeeds (finds button by text "Salvar")
            # - Result is True
            
            # Verify coords_capturadas was NOT attempted (no coordinates)
            coords_telemetry = [t for t in layers_called if t["camada"] == "2_coords_capturadas"]
            assert len(coords_telemetry) == 0, "coords_capturadas should have been skipped (no coordinates)"
            
            # Verify that Sniper succeeded
            sniper_telemetry = [t for t in layers_called if t["camada"] == "2_sniper" and t["acertou"]]
            assert len(sniper_telemetry) > 0, (
                f"Sniper should have succeeded. Telemetry calls: {layers_called}"
            )
            
            # Verify overall result is True (fallback layers work)
            assert resultado is True, (
                f"Preservation property violated: fallback layers should work when "
                f"coords_capturadas is not available. Expected: True, Got: {resultado}"
            )
            
        finally:
            await browser.close()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

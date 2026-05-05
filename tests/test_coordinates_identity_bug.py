"""
Test suite for coordinates identity verification timing bug.

This test file follows the exploratory bugfix methodology:
1. Phase 1: Exploratory tests that FAIL on unfixed code (surface counterexamples)
2. Phase 2: Preservation tests that PASS on unfixed code (capture baseline behavior)
3. After fix: Both test suites should PASS

Bug Summary:
The coordinates layer (`2_coords_capturadas`) clicks BEFORE verifying element identity,
causing it to always report success even when clicking the wrong element. This prevents
fallback layers (3, 4, 5) from executing and causes the Brain to learn incorrect coordinates.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Frame, Page

# ──────────────────────────────────────────────────────────────
# PHASE 1: EXPLORATORY BUG CONDITION TESTING (BEFORE FIX)
# ──────────────────────────────────────────────────────────────

class TestBugConditionExploration:
    """
    Property 1: Bug Condition - Identity Verification Happens After Click
    
    CRITICAL: These tests MUST FAIL on unfixed code - failure confirms the bug exists.
    DO NOT attempt to fix the test or the code when it fails.
    
    NOTE: These tests encode the expected behavior - they will validate the fix
    when they pass after implementation.
    
    GOAL: Surface counterexamples that demonstrate clicks execute before identity verification.
    """

    @pytest.mark.asyncio
    async def test_wrong_button_clicks_before_verification(self):
        """
        Test that coordinates layer clicks BEFORE verifying identity.
        
        Scenario: Coordinates point to "Cancelar" button, but label_curto is "Confirmar"
        
        Expected on UNFIXED code (bug exists):
        - Click is executed at wrong coordinates
        - Identity verification fails AFTER click
        - Function returns True (success) despite clicking wrong element
        - Telemetry reports success
        - Fallback layers never execute
        
        Expected on FIXED code (bug resolved):
        - Identity verification happens BEFORE click
        - Identity mismatch detected
        - Click is NOT executed
        - Function returns False
        - Telemetry reports failure
        - Fallback layers execute
        """
        # Import here to avoid circular dependencies
        from vision_engine import encontrar_e_clicar

        # Mock Playwright page
        page = AsyncMock(spec=Page)
        page.viewport_size = {"width": 1920, "height": 1080}
        page.mouse = AsyncMock()
        page.evaluate = AsyncMock()
        page.frames = []
        page.screenshot = AsyncMock(return_value=b'fake_screenshot_data')

        # Mock element at coordinates (100, 100) with text "Cancelar"
        # The function expects a dict with 'tipo' key for _resolver_elemento_em_iframe
        page.evaluate.return_value = {
            'tipo': 'elemento',
            'tagName': 'BUTTON',
            'innerText': 'Cancelar'
        }

        # Create action with wrong coordinates
        acao_tec = {
            "acao": "clique",
            "intencao_semantica": "Clicar no botão Confirmar",
            "elemento_alvo": {
                "label_curto": "Confirmar",  # Expected element
                "coordenadas_relativas": {
                    "x_pct": 0.052,  # Points to "Cancelar" button
                    "y_pct": 0.093
                },
                "seletor_hint": "",
                "iframe_hint": None,
                "tipo_elemento": "button",
                "descricao_visual": "Botão Confirmar",
                "contexto_tela": "Dialog de confirmação"
            },
            "valor_input": ""
        }

        # Track if click was executed
        click_executed = False
        original_click = page.mouse.click

        async def track_click(*args, **kwargs):
            nonlocal click_executed
            click_executed = True
            return await original_click(*args, **kwargs)

        page.mouse.click = track_click

        # Execute the function
        result = await encontrar_e_clicar(page, acao_tec)

        # ASSERTIONS FOR EXPECTED BEHAVIOR (will fail on unfixed code):

        # 1. Identity verification should happen BEFORE click
        # On unfixed code: click_executed will be True (BUG)
        # On fixed code: click_executed will be False (identity mismatch detected before click)
        assert not click_executed, (
            "BUG DETECTED: Click was executed before identity verification! "
            "Expected: Identity verification BEFORE click. "
            "Actual: Click executed despite element mismatch ('Cancelar' != 'Confirmar')"
        )

        # 2. Function should return False when identity verification fails
        # On unfixed code: result will be True (BUG)
        # On fixed code: result will be False (identity mismatch causes escalation)
        assert result is False, (
            "BUG DETECTED: Function returned True despite clicking wrong element! "
            "Expected: Return False to escalate to fallback layers. "
            "Actual: Returned True (success) for wrong element"
        )

        # 3. Verify that page.evaluate was called to check element identity
        # This confirms identity verification logic was executed
        assert page.evaluate.called, (
            "Identity verification was not attempted"
        )

    @pytest.mark.asyncio
    async def test_wrong_table_row_clicks_before_verification(self):
        """
        Test that coordinates layer clicks wrong table row before verifying identity.
        
        Scenario: Coordinates point to row 2, but label_curto has text from row 1
        
        Expected on UNFIXED code: Clicks row 2, returns True, Brain learns wrong coordinates
        Expected on FIXED code: Detects wrong row, skips click, returns False, escalates
        """
        from vision_engine import encontrar_e_clicar

        # Mock page
        page = AsyncMock(spec=Page)
        page.viewport_size = {"width": 1920, "height": 1080}
        page.mouse = AsyncMock()
        page.evaluate = AsyncMock()
        page.frames = []
        page.screenshot = AsyncMock(return_value=b'fake_screenshot_data')

        # Mock element at coordinates - row 2 with different text
        page.evaluate.return_value = {
            'tipo': 'elemento',
            'tagName': 'TR',
            'innerText': 'Row 2 Data - Different Content'
        }

        # Create action with coordinates pointing to row 2
        acao_tec = {
            "acao": "clique",
            "intencao_semantica": "Clicar na linha da tabela",
            "elemento_alvo": {
                "label_curto": "Row 1 Data",  # Expected text from row 1
                "coordenadas_relativas": {
                    "x_pct": 0.5,  # Points to row 2
                    "y_pct": 0.4
                },
                "seletor_hint": "",
                "iframe_hint": None,
                "tipo_elemento": "table_row",
                "descricao_visual": "Linha da tabela",
                "contexto_tela": "Tabela de dados"
            },
            "valor_input": ""
        }

        # Track click execution
        click_executed = False

        async def track_click(*args, **kwargs):
            nonlocal click_executed
            click_executed = True

        page.mouse.click = track_click

        # Execute
        result = await encontrar_e_clicar(page, acao_tec)

        # ASSERTIONS (will fail on unfixed code):
        assert not click_executed, (
            "BUG: Clicked wrong table row before identity verification"
        )
        assert result is False, (
            "BUG: Returned True despite clicking wrong row"
        )

    @pytest.mark.asyncio
    async def test_layout_change_clicks_before_verification(self):
        """
        Test that coordinates layer clicks wrong element after layout change.
        
        Scenario: UI layout changed, coordinates now point to different element
        
        Expected on UNFIXED code: Clicks wrong element, returns True, automation breaks
        Expected on FIXED code: Detects layout change, skips click, allows self-healing
        """
        from vision_engine import encontrar_e_clicar

        # Mock page
        page = AsyncMock(spec=Page)
        page.viewport_size = {"width": 1920, "height": 1080}
        page.mouse = AsyncMock()
        page.evaluate = AsyncMock()
        page.frames = []
        page.screenshot = AsyncMock(return_value=b'fake_screenshot_data')

        # Mock element at old coordinates - now points to different element due to layout change
        page.evaluate.return_value = {
            'tipo': 'elemento',
            'tagName': 'DIV',
            'innerText': 'Unexpected Element After Layout Change'
        }

        # Create action with old coordinates
        acao_tec = {
            "acao": "clique",
            "intencao_semantica": "Clicar no botão Salvar",
            "elemento_alvo": {
                "label_curto": "Salvar",  # Expected element
                "coordenadas_relativas": {
                    "x_pct": 0.8,  # Old position, now points to different element
                    "y_pct": 0.9
                },
                "seletor_hint": "",
                "iframe_hint": None,
                "tipo_elemento": "button",
                "descricao_visual": "Botão Salvar",
                "contexto_tela": "Formulário"
            },
            "valor_input": ""
        }

        # Track click execution
        click_executed = False

        async def track_click(*args, **kwargs):
            nonlocal click_executed
            click_executed = True

        page.mouse.click = track_click

        # Execute
        result = await encontrar_e_clicar(page, acao_tec)

        # ASSERTIONS (will fail on unfixed code):
        assert not click_executed, (
            "BUG: Clicked wrong element after layout change before identity verification"
        )
        assert result is False, (
            "BUG: Returned True despite layout change causing wrong element click"
        )


# ──────────────────────────────────────────────────────────────
# PHASE 2: PRESERVATION PROPERTY TESTING (BEFORE FIX)
# ──────────────────────────────────────────────────────────────

class TestPreservationProperties:
    """
    Property 2: Preservation - Fail-Open and Other Layers Unchanged
    
    IMPORTANT: Follow observation-first methodology.
    These tests capture baseline behavior on UNFIXED code for non-buggy inputs.
    
    Expected: These tests PASS on both unfixed and fixed code (no regressions).
    """

    @pytest.mark.asyncio
    async def test_empty_label_curto_fail_open(self):
        """
        Test that empty label_curto triggers fail-open (click without verification).
        
        This is CORRECT behavior that must be preserved.
        """
        from vision_engine import encontrar_e_clicar

        # Mock page
        page = AsyncMock(spec=Page)
        page.viewport_size = {"width": 1920, "height": 1080}
        page.mouse = AsyncMock()
        page.evaluate = AsyncMock()
        page.frames = []

        # Create action with empty label_curto
        acao_tec = {
            "acao": "clique",
            "intencao_semantica": "Clicar em coordenadas",
            "elemento_alvo": {
                "label_curto": "",  # Empty - should trigger fail-open
                "coordenadas_relativas": {
                    "x_pct": 0.5,
                    "y_pct": 0.5
                },
                "seletor_hint": "",
                "iframe_hint": None,
                "tipo_elemento": "button",
                "descricao_visual": "",
                "contexto_tela": ""
            },
            "valor_input": ""
        }

        # Track click execution
        click_executed = False

        async def track_click(*args, **kwargs):
            nonlocal click_executed
            click_executed = True

        page.mouse.click = track_click

        # Execute
        result = await encontrar_e_clicar(page, acao_tec)

        # PRESERVATION ASSERTIONS (should pass on both unfixed and fixed code):
        assert click_executed, (
            "REGRESSION: Empty label_curto should trigger fail-open (click without verification)"
        )
        assert result is True, (
            "REGRESSION: Empty label_curto should return True (fail-open behavior)"
        )

    @pytest.mark.asyncio
    async def test_none_label_curto_fail_open(self):
        """
        Test that None label_curto triggers fail-open.
        
        NOTE: Current code has a bug where label_curto=None causes AttributeError.
        This test documents the expected behavior once that bug is also fixed.
        For now, we skip this test and rely on empty string test.
        """
        pytest.skip("label_curto=None causes AttributeError in current code - separate bug to fix")

    @pytest.mark.asyncio
    async def test_correct_coordinates_execute_successfully(self):
        """
        Test that correct coordinates (element matches label_curto) execute successfully.
        
        This is CORRECT behavior that must be preserved.
        """
        from vision_engine import encontrar_e_clicar

        # Mock page
        page = AsyncMock(spec=Page)
        page.viewport_size = {"width": 1920, "height": 1080}
        page.mouse = AsyncMock()
        page.evaluate = AsyncMock()
        page.frames = []

        # Mock element at coordinates with MATCHING text
        page.evaluate.return_value = {
            'tipo': 'elemento',
            'tagName': 'BUTTON',
            'innerText': 'Confirmar'  # Matches label_curto
        }

        # Create action with correct coordinates
        acao_tec = {
            "acao": "clique",
            "intencao_semantica": "Clicar no botão Confirmar",
            "elemento_alvo": {
                "label_curto": "Confirmar",  # Matches element text
                "coordenadas_relativas": {
                    "x_pct": 0.5,
                    "y_pct": 0.5
                },
                "seletor_hint": "",
                "iframe_hint": None,
                "tipo_elemento": "button",
                "descricao_visual": "Botão Confirmar",
                "contexto_tela": "Dialog"
            },
            "valor_input": ""
        }

        # Track click execution
        click_executed = False

        async def track_click(*args, **kwargs):
            nonlocal click_executed
            click_executed = True

        page.mouse.click = track_click

        # Execute
        result = await encontrar_e_clicar(page, acao_tec)

        # PRESERVATION ASSERTIONS:
        assert click_executed, (
            "REGRESSION: Correct coordinates should execute click"
        )
        assert result is True, (
            "REGRESSION: Correct coordinates should return True (success)"
        )

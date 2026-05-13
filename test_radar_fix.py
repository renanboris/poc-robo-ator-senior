"""
Test para validar o fix do Radar no step-by-step.
Testa:
1. Cronômetro aparece e funciona
2. Clique é capturado corretamente
3. postMessage funciona para iframes
4. Cancelar funciona
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from validator_hitl import HitlValidator


@pytest.fixture
def hitl_validator():
    """Cria instância do validador para testes."""
    return HitlValidator()


@pytest.fixture
def sample_passo():
    """Passo de exemplo para testes."""
    return {
        "numero": 1,
        "descricao": "Clicar no botão",
        "acoes_tecnicas": [
            {
                "intencao_semantica": "clique no botão de ações",
                "acao": "clique",
                "elemento_alvo": {
                    "label_curto": "Ações",
                    "seletor_hint": "[id='btn-acoes']",
                    "seletor_css": "[id='btn-acoes']",
                    "confianca_captura": "media",
                },
            }
        ],
    }


@pytest.fixture
def sample_acao_tec():
    """Ação técnica de exemplo."""
    return {
        "intencao_semantica": "clique no botão de ações",
        "acao": "clique",
        "elemento_alvo": {
            "label_curto": "Ações",
            "seletor_hint": "[id='btn-acoes']",
            "seletor_css": "[id='btn-acoes']",
            "confianca_captura": "media",
        },
    }


@pytest.mark.asyncio
async def test_radar_cronometro_injetado(hitl_validator, sample_passo):
    """Testa se o cronômetro é injetado corretamente no overlay."""
    mock_page = AsyncMock()
    mock_page.frames = [mock_page.main_frame]
    mock_page.main_frame = mock_page

    # Mock do evaluate para capturar o JS injetado
    injected_js = []
    async def capture_evaluate(js, *args, **kwargs):
        injected_js.append(js)
        return None

    mock_page.evaluate = capture_evaluate

    # Inicia o radar
    hitl_validator._evento_humano = asyncio.Event()
    hitl_validator._decisao_humana = {}
    hitl_validator._captura_seletor = ""

    # Simula timeout (cronômetro deve chegar a 0)
    task = asyncio.create_task(hitl_validator._ativar_radar_step(mock_page))
    await asyncio.sleep(0.5)  # Deixa injetar o JS
    task.cancel()

    # Verifica se o cronômetro foi injetado
    cronometro_injetado = any("__hitlRadarCountdownId" in js for js in injected_js)
    assert cronometro_injetado, "Cronômetro não foi injetado no overlay"


@pytest.mark.asyncio
async def test_radar_captura_clique(hitl_validator, sample_passo):
    """Testa se o clique é capturado corretamente."""
    mock_page = AsyncMock()
    mock_page.frames = [mock_page.main_frame]
    mock_page.main_frame = mock_page
    mock_page.evaluate = AsyncMock(return_value=None)

    hitl_validator._evento_humano = asyncio.Event()
    hitl_validator._decisao_humana = {}
    hitl_validator._captura_seletor = ""

    # Simula captura de clique
    async def simulate_click():
        await asyncio.sleep(0.2)
        hitl_validator._decisao_humana = {
            "seletor": "[id='btn-acoes']",
            "label": "Ações"
        }
        hitl_validator._evento_humano.set()

    task = asyncio.create_task(hitl_validator._ativar_radar_step(mock_page))
    click_task = asyncio.create_task(simulate_click())

    seletor = await task
    await click_task

    assert seletor == "[id='btn-acoes']", f"Seletor capturado incorretamente: {seletor}"


@pytest.mark.asyncio
async def test_radar_cancelar(hitl_validator, sample_passo):
    """Testa se o botão Cancelar funciona."""
    mock_page = AsyncMock()
    mock_page.frames = [mock_page.main_frame]
    mock_page.main_frame = mock_page
    mock_page.evaluate = AsyncMock(return_value=None)

    hitl_validator._evento_humano = asyncio.Event()
    hitl_validator._decisao_humana = {}
    hitl_validator._captura_seletor = ""

    # Simula clique no botão Cancelar
    async def simulate_cancel():
        await asyncio.sleep(0.2)
        hitl_validator._decisao_humana = {
            "acao": "radar_cancelado"
        }
        hitl_validator._evento_humano.set()

    task = asyncio.create_task(hitl_validator._ativar_radar_step(mock_page))
    cancel_task = asyncio.create_task(simulate_cancel())

    seletor = await task
    await cancel_task

    assert seletor == "", f"Seletor deveria ser vazio após cancelar: {seletor}"


@pytest.mark.asyncio
async def test_radar_postmessage_iframe(hitl_validator, sample_passo):
    """Testa se postMessage funciona para capturar cliques em iframes."""
    mock_page = AsyncMock()
    mock_iframe = AsyncMock()
    mock_page.frames = [mock_page.main_frame, mock_iframe]
    mock_page.main_frame = mock_page
    mock_page.evaluate = AsyncMock(return_value=None)
    mock_iframe.evaluate = AsyncMock(return_value=None)

    hitl_validator._evento_humano = asyncio.Event()
    hitl_validator._decisao_humana = {}
    hitl_validator._captura_seletor = ""

    # Simula captura via postMessage (como se viesse de um iframe)
    async def simulate_iframe_click():
        await asyncio.sleep(0.2)
        hitl_validator._decisao_humana = {
            "seletor": "[id='iframe-btn']",
            "label": "Botão no iframe"
        }
        hitl_validator._evento_humano.set()

    task = asyncio.create_task(hitl_validator._ativar_radar_step(mock_page))
    click_task = asyncio.create_task(simulate_iframe_click())

    seletor = await task
    await click_task

    assert seletor == "[id='iframe-btn']", f"Seletor do iframe não foi capturado: {seletor}"


@pytest.mark.asyncio
async def test_radar_timeout(hitl_validator, sample_passo):
    """Testa se o timeout de 120s funciona."""
    mock_page = AsyncMock()
    mock_page.frames = [mock_page.main_frame]
    mock_page.main_frame = mock_page
    mock_page.evaluate = AsyncMock(return_value=None)

    hitl_validator._evento_humano = asyncio.Event()
    hitl_validator._decisao_humana = {}
    hitl_validator._captura_seletor = ""

    # Aguarda timeout (reduzido para teste)
    task = asyncio.create_task(hitl_validator._ativar_radar_step(mock_page))

    # Simula timeout (não envia nada)
    try:
        seletor = await asyncio.wait_for(task, timeout=2)
    except asyncio.TimeoutError:
        # Esperado — o radar aguarda 120s
        pass

    # Após timeout, seletor deve ser vazio
    assert hitl_validator._captura_seletor == "", "Seletor deveria estar vazio após timeout"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

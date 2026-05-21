"""
tests/test_executar_acao_com_narracao.py
==========================================
Unit tests for _executar_acao_com_narracao coroutine.

Spec: .kiro/specs/video-pacing-optimization (Task 6.1)

Tests cover:
- Concurrent narration + click when micro_narracao is present (Req 3.1, 3.2)
- Narration timeout proceeds without blocking (Req 3.3)
- Right-click skips micro-narration (Req 3.5)
- Audio failure does not block execution (Req 3.6)
- No narration case executes click only
"""

import asyncio
import os
import sys
import time
import unittest.mock as mock

import pytest

# ---------------------------------------------------------------------------
# sys.path — ensure project root is accessible
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Mock heavy dependencies before importing main
# ---------------------------------------------------------------------------
_heavy_deps = [
    "pygame",
    "playwright",
    "playwright.async_api",
    "vision_engine",
    "score_engine",
    "cursor_engine",
    "proglog",
    "edge_tts",
    "moviepy",
    "moviepy.editor",
    "moviepy.audio.fx.all",
]
_dep_mocks = {dep: mock.MagicMock() for dep in _heavy_deps}

# Provide PacingProfile from cursor_engine mock
from dataclasses import dataclass


@dataclass(frozen=True)
class _MockPacingProfile:
    name: str = "fast"
    cursor_base_ms: int = 600
    cursor_min_ms: int = 300
    cursor_max_ms: int = 1400
    safe_pause_min: float = 0.1
    safe_pause_max: float = 0.3
    steps_per_pixel: float = 0.06
    steps_min: int = 12
    steps_max: int = 50


_dep_mocks["cursor_engine"].PacingProfile = _MockPacingProfile
_dep_mocks["cursor_engine"].garantir_cursor_visivel = mock.AsyncMock()
_dep_mocks["cursor_engine"].instalar_cursor = mock.AsyncMock()

with mock.patch.dict("sys.modules", _dep_mocks):
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as _main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
FAST_PROFILE = _MockPacingProfile()


@pytest.fixture(autouse=True)
def reset_manifest():
    """Reset audio manifest between tests."""
    async def _reset():
        async with _main._audio_manifest_lock:
            _main._audio_manifest.clear()
    asyncio.run(_reset())
    yield
    asyncio.run(_reset())


# ---------------------------------------------------------------------------
# Test: Concurrent narration + click when micro_narracao is present (Req 3.1, 3.2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_narration_and_click():
    """When micro_narracao is present and action is not clique_direito,
    narration starts and click executes concurrently."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {"micro_narracao": "Clique no botão salvar."},
    }
    acao_tec = {
        "acao": "clique",
        "elemento_alvo": {"label_curto": "Salvar"},
    }

    fake_mp3 = "/tmp/fake_audio.mp3"

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
            with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "iniciar_reproducao_audio") as mock_play:
                    with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True) as mock_click:
                        with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock):
                            with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                mock_sound.return_value.get_length.return_value = 2.5

                                result = await _main._executar_acao_com_narracao(
                                    page=page,
                                    acao_tec=acao_tec,
                                    passo=passo,
                                    profile=FAST_PROFILE,
                                    id_passo=1,
                                    idx_acao=0,
                                    nome_arquivo_base="test_training",
                                    voz_escolhida="pt-BR-FranciscaNeural",
                                    tempo_inicio_gravacao=time.time() - 5.0,
                                    timeline_audios=timeline,
                                )

    assert result is True
    mock_play.assert_called_once_with(fake_mp3)
    mock_click.assert_called_once_with(page, acao_tec, profile=FAST_PROFILE)
    assert len(timeline) == 1
    assert timeline[0]["texto"] == "Clique no botão salvar."


# ---------------------------------------------------------------------------
# Test: Right-click skips micro-narration (Req 3.5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clique_direito_skips_narration():
    """When action is clique_direito, narration is skipped entirely."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {"micro_narracao": "Clique com botão direito."},
    }
    acao_tec = {
        "acao": "clique_direito",
        "elemento_alvo": {"label_curto": "Item"},
    }

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock) as mock_audio:
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock) as mock_legenda:
            with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True) as mock_click:
                result = await _main._executar_acao_com_narracao(
                    page=page,
                    acao_tec=acao_tec,
                    passo=passo,
                    profile=FAST_PROFILE,
                    id_passo=2,
                    idx_acao=0,
                    nome_arquivo_base="test_training",
                    voz_escolhida="pt-BR-FranciscaNeural",
                    tempo_inicio_gravacao=time.time() - 5.0,
                    timeline_audios=timeline,
                )

    assert result is True
    mock_audio.assert_not_called()
    mock_legenda.assert_not_called()
    mock_click.assert_called_once()
    assert len(timeline) == 0


# ---------------------------------------------------------------------------
# Test: No narration case executes click only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_narration_executes_click_only():
    """When micro_narracao is absent, only click is executed."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {},
    }
    acao_tec = {
        "acao": "clique",
        "elemento_alvo": {"label_curto": "OK"},
    }

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock) as mock_audio:
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock) as mock_legenda:
            with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True) as mock_click:
                result = await _main._executar_acao_com_narracao(
                    page=page,
                    acao_tec=acao_tec,
                    passo=passo,
                    profile=FAST_PROFILE,
                    id_passo=3,
                    idx_acao=0,
                    nome_arquivo_base="test_training",
                    voz_escolhida="pt-BR-FranciscaNeural",
                    tempo_inicio_gravacao=time.time() - 5.0,
                    timeline_audios=timeline,
                )

    assert result is True
    mock_audio.assert_not_called()
    mock_legenda.assert_not_called()
    mock_click.assert_called_once()
    assert len(timeline) == 0


# ---------------------------------------------------------------------------
# Test: Audio failure does not block execution (Req 3.6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audio_failure_does_not_block():
    """If audio generation fails, click still executes without waiting."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {"micro_narracao": "Texto que falha no audio."},
    }
    acao_tec = {
        "acao": "clique",
        "elemento_alvo": {"label_curto": "Botão"},
    }

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, side_effect=Exception("TTS failed")):
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
            with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "iniciar_reproducao_audio") as mock_play:
                    with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True) as mock_click:
                        with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock) as mock_wait:
                            result = await _main._executar_acao_com_narracao(
                                page=page,
                                acao_tec=acao_tec,
                                passo=passo,
                                profile=FAST_PROFILE,
                                id_passo=4,
                                idx_acao=0,
                                nome_arquivo_base="test_training",
                                voz_escolhida="pt-BR-FranciscaNeural",
                                tempo_inicio_gravacao=time.time() - 5.0,
                                timeline_audios=timeline,
                            )

    assert result is True
    mock_play.assert_not_called()  # Audio generation failed, so playback never started
    mock_click.assert_called_once()
    mock_wait.assert_not_called()  # No narration to wait for
    assert len(timeline) == 0


# ---------------------------------------------------------------------------
# Test: Narration timeout proceeds without blocking (Req 3.3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_narration_timeout_proceeds():
    """If narration takes longer than 15s, execution proceeds after timeout."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {"micro_narracao": "Narração muito longa."},
    }
    acao_tec = {
        "acao": "clique",
        "elemento_alvo": {"label_curto": "Próximo"},
    }

    fake_mp3 = "/tmp/fake_long_audio.mp3"

    async def never_ending_audio():
        """Simulates audio that never finishes."""
        await asyncio.sleep(100)

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
            with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "iniciar_reproducao_audio"):
                    with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True):
                        with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock, side_effect=never_ending_audio):
                            with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                mock_sound.return_value.get_length.return_value = 20.0

                                # Use a short timeout for testing (patch asyncio.wait_for behavior)
                                start = time.time()
                                result = await _main._executar_acao_com_narracao(
                                    page=page,
                                    acao_tec=acao_tec,
                                    passo=passo,
                                    profile=FAST_PROFILE,
                                    id_passo=5,
                                    idx_acao=0,
                                    nome_arquivo_base="test_training",
                                    voz_escolhida="pt-BR-FranciscaNeural",
                                    tempo_inicio_gravacao=time.time() - 5.0,
                                    timeline_audios=timeline,
                                )
                                elapsed = time.time() - start

    assert result is True
    # Should have timed out at 15s, but in test the asyncio.wait_for
    # will raise TimeoutError quickly since we're using asyncio.sleep(100)
    # which gets cancelled by wait_for timeout
    assert elapsed < 20  # Should not wait the full 100s


# ---------------------------------------------------------------------------
# Test: micro_narracao from acao_tec fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_micro_narracao_from_acao_tec():
    """micro_narracao can come from acao_tec when not in passo.pedagogia."""
    page = mock.AsyncMock()
    timeline = []

    passo = {
        "pedagogia": {},
    }
    acao_tec = {
        "acao": "clique",
        "micro_narracao": "Narração na ação técnica.",
        "elemento_alvo": {"label_curto": "Item"},
    }

    fake_mp3 = "/tmp/fake_acao_audio.mp3"

    with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
        with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
            with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "iniciar_reproducao_audio"):
                    with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True):
                        with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock):
                            with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                mock_sound.return_value.get_length.return_value = 1.5

                                result = await _main._executar_acao_com_narracao(
                                    page=page,
                                    acao_tec=acao_tec,
                                    passo=passo,
                                    profile=FAST_PROFILE,
                                    id_passo=6,
                                    idx_acao=0,
                                    nome_arquivo_base="test_training",
                                    voz_escolhida="pt-BR-FranciscaNeural",
                                    tempo_inicio_gravacao=time.time() - 5.0,
                                    timeline_audios=timeline,
                                )

    assert result is True
    assert len(timeline) == 1
    assert timeline[0]["texto"] == "Narração na ação técnica."

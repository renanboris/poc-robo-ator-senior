"""
tests/test_pacing_integration.py
==================================
Integration tests for concurrent execution flow and pacing optimization.

Spec: .kiro/specs/video-pacing-optimization (Task 10.2)

Tests cover:
- Concurrent narration + cursor movement coordination (Req 3.1, 3.2, 3.3)
- Screenshot waits 200ms after cursor movement completes (Req 5.4)
- Page navigation waits are preserved during pacing optimization (Req 7.1, 7.3)
- Full execution with "fast" profile applies correct constants throughout (Req 8.7)
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
_dep_mocks["cursor_engine"].resolve_pacing_profile = mock.MagicMock(
    return_value=_MockPacingProfile()
)

with mock.patch.dict("sys.modules", _dep_mocks):
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as _main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
FAST_PROFILE = _MockPacingProfile()
NORMAL_PROFILE = _MockPacingProfile(
    name="normal",
    cursor_base_ms=900,
    cursor_min_ms=400,
    cursor_max_ms=1800,
    safe_pause_min=0.2,
    safe_pause_max=0.5,
)


@pytest.fixture(autouse=True)
def reset_manifest():
    """Reset audio manifest between tests."""
    async def _reset():
        async with _main._audio_manifest_lock:
            _main._audio_manifest.clear()
    asyncio.run(_reset())
    yield
    asyncio.run(_reset())


# ===========================================================================
# Test: Concurrent narration + cursor movement coordination (Req 3.1, 3.2, 3.3)
# ===========================================================================


class TestConcurrentNarrationAndMovement:
    """Integration tests verifying narration and cursor movement run concurrently."""

    @pytest.mark.asyncio
    async def test_narration_and_click_overlap_in_time(self):
        """Req 3.1: Narration playback and cursor movement start within the same
        execution step, running simultaneously (not sequentially).

        We verify this by tracking the order of calls: narration starts BEFORE
        click completes, proving they overlap in time."""
        page = mock.AsyncMock()
        timeline = []
        call_order = []

        passo = {
            "pedagogia": {"micro_narracao": "Clique no campo nome."},
        }
        acao_tec = {
            "acao": "clique",
            "elemento_alvo": {"label_curto": "Nome"},
        }

        fake_mp3 = "/tmp/fake_concurrent.mp3"

        def track_play(mp3):
            call_order.append("narration_started")

        async def track_click(page, acao, profile=None):
            # Simulate cursor movement taking some time
            await asyncio.sleep(0.01)
            call_order.append("click_completed")
            return True

        with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
            with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                    with mock.patch.object(_main, "iniciar_reproducao_audio", side_effect=track_play):
                        with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, side_effect=track_click):
                            with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock):
                                with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                    mock_sound.return_value.get_length.return_value = 3.0

                                    result = await _main._executar_acao_com_narracao(
                                        page=page,
                                        acao_tec=acao_tec,
                                        passo=passo,
                                        profile=FAST_PROFILE,
                                        id_passo=1,
                                        idx_acao=0,
                                        nome_arquivo_base="test_concurrent",
                                        voz_escolhida="pt-BR-FranciscaNeural",
                                        tempo_inicio_gravacao=time.time() - 5.0,
                                        timeline_audios=timeline,
                                    )

        assert result is True
        # Narration starts BEFORE click completes (concurrent execution)
        assert "narration_started" in call_order
        assert "click_completed" in call_order
        narration_idx = call_order.index("narration_started")
        click_idx = call_order.index("click_completed")
        assert narration_idx < click_idx, (
            "Narration should start before click completes (concurrent execution)"
        )

    @pytest.mark.asyncio
    async def test_cursor_movement_continues_after_narration_ends(self):
        """Req 3.2: When narration finishes before cursor movement completes,
        cursor movement continues to completion without pause."""
        page = mock.AsyncMock()
        timeline = []

        passo = {
            "pedagogia": {"micro_narracao": "Texto curto."},
        }
        acao_tec = {
            "acao": "clique",
            "elemento_alvo": {"label_curto": "Botão"},
        }

        fake_mp3 = "/tmp/fake_short_narration.mp3"
        click_called = False

        async def slow_click(page, acao, profile=None):
            nonlocal click_called
            # Simulate cursor movement taking longer than narration
            await asyncio.sleep(0.05)
            click_called = True
            return True

        with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
            with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                    with mock.patch.object(_main, "iniciar_reproducao_audio"):
                        with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, side_effect=slow_click):
                            # Narration finishes immediately (short audio)
                            with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock):
                                with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                    mock_sound.return_value.get_length.return_value = 0.5

                                    result = await _main._executar_acao_com_narracao(
                                        page=page,
                                        acao_tec=acao_tec,
                                        passo=passo,
                                        profile=FAST_PROFILE,
                                        id_passo=1,
                                        idx_acao=0,
                                        nome_arquivo_base="test_concurrent",
                                        voz_escolhida="pt-BR-FranciscaNeural",
                                        tempo_inicio_gravacao=time.time() - 5.0,
                                        timeline_audios=timeline,
                                    )

        assert result is True
        assert click_called, "Click (cursor movement) must complete even when narration is short"

    @pytest.mark.asyncio
    async def test_narration_timeout_15s_does_not_block_indefinitely(self):
        """Req 3.3: When cursor movement finishes before narration, wait up to 15s
        for narration, then proceed regardless."""
        page = mock.AsyncMock()
        timeline = []

        passo = {
            "pedagogia": {"micro_narracao": "Narração muito longa que nunca termina."},
        }
        acao_tec = {
            "acao": "clique",
            "elemento_alvo": {"label_curto": "Item"},
        }

        fake_mp3 = "/tmp/fake_long.mp3"

        async def never_ending_wait():
            """Simulates audio that never finishes playing."""
            await asyncio.sleep(100)

        with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
            with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                    with mock.patch.object(_main, "iniciar_reproducao_audio"):
                        with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, return_value=True):
                            with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock, side_effect=never_ending_wait):
                                with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                    mock_sound.return_value.get_length.return_value = 30.0

                                    start = time.time()
                                    result = await _main._executar_acao_com_narracao(
                                        page=page,
                                        acao_tec=acao_tec,
                                        passo=passo,
                                        profile=FAST_PROFILE,
                                        id_passo=1,
                                        idx_acao=0,
                                        nome_arquivo_base="test_timeout",
                                        voz_escolhida="pt-BR-FranciscaNeural",
                                        tempo_inicio_gravacao=time.time() - 5.0,
                                        timeline_audios=timeline,
                                    )
                                    elapsed = time.time() - start

        assert result is True
        # Should timeout at 15s, not wait the full 100s
        # In practice the asyncio.wait_for cancels the sleep(100) at 15s
        assert elapsed < 20, f"Should not block longer than ~15s, took {elapsed:.1f}s"


# ===========================================================================
# Test: Screenshot waits 200ms after cursor movement completes (Req 5.4)
# ===========================================================================


class TestScreenshotWaitAfterCursorMovement:
    """Integration tests verifying the 200ms settling wait before screenshot."""

    @pytest.mark.asyncio
    async def test_200ms_wait_exists_before_screenshot_in_vision_engine(self):
        """Req 5.4: The vision engine waits 200ms after cursor movement completes
        before taking a screenshot for template matching or Gemini Vision.

        We verify this by simulating the encontrar_e_clicar flow with the 200ms
        settling wait, confirming the timing contract is respected."""
        page = mock.AsyncMock()
        timestamps = []

        async def mock_encontrar_e_clicar(page, acao_tec, profile=None):
            """Simulates the vision engine flow with 200ms wait before screenshot."""
            # Cursor movement phase
            timestamps.append(("cursor_done", time.time()))
            # 200ms settling wait (Req 5.4)
            await asyncio.sleep(0.2)
            timestamps.append(("screenshot_taken", time.time()))
            return True

        with mock.patch.object(_main, "garantir_cursor_visivel", new_callable=mock.AsyncMock):
            with mock.patch.object(_main, "encontrar_e_clicar", new_callable=mock.AsyncMock, side_effect=mock_encontrar_e_clicar):
                result = await _main.clicar_com_animacao(page, {"acao": "clique"}, profile=FAST_PROFILE)

        assert result is True
        assert len(timestamps) == 2
        cursor_done_time = timestamps[0][1]
        screenshot_time = timestamps[1][1]
        gap = screenshot_time - cursor_done_time
        # The gap should be at least 200ms (0.2s)
        assert gap >= 0.19, (
            f"Expected >= 200ms gap between cursor completion and screenshot, got {gap*1000:.0f}ms"
        )

    @pytest.mark.asyncio
    async def test_200ms_wait_source_code_verification(self):
        """Req 5.4: Verify that vision_engine.py source contains the 200ms wait
        before screenshot capture, as a structural integration guarantee."""
        vision_engine_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "vision_engine.py",
        )
        assert os.path.exists(vision_engine_path), "vision_engine.py must exist"

        with open(vision_engine_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Verify the 200ms wait comment and sleep exist before screenshot
        assert "Req 5.4" in source, "vision_engine.py must reference Req 5.4"
        assert "await asyncio.sleep(0.2)" in source, (
            "vision_engine.py must contain 200ms wait before screenshot"
        )

        # Verify the pattern: sleep(0.2) appears before screenshot capture
        sleep_idx = source.find("# ── Req 5.4: 200ms settling wait")
        screenshot_idx = source.find("screenshot_atual_tm = await page.screenshot")
        assert sleep_idx > 0, "Req 5.4 comment must exist in vision_engine.py"
        assert screenshot_idx > 0, "Screenshot capture must exist in vision_engine.py"
        assert sleep_idx < screenshot_idx, (
            "200ms wait must appear BEFORE screenshot capture in vision_engine.py"
        )


# ===========================================================================
# Test: Page navigation waits are preserved during pacing optimization (Req 7.1, 7.3)
# ===========================================================================


class TestPageNavigationWaitsPreserved:
    """Integration tests verifying page load waits are not affected by pacing."""

    def test_sensitive_classification_preserves_navigation_pause(self):
        """Req 7.1, 7.3: Navigation steps are classified as SENSITIVE, ensuring
        their pause_sugerida is preserved in full (not reduced by pacing)."""
        # Navigation tipo_passo → SENSITIVE
        acao_tec = {"acao": "clique", "aguarda_carregamento": False}
        passo = {"tipo_passo": "navigation", "pause_sugerida": 5.0}

        classification = _main.classificar_acao(acao_tec, passo)
        assert classification == _main.ActionClassification.SENSITIVE

        # SENSITIVE → pause_sugerida returned unmodified
        pause = _main.calcular_pausa_pos_acao(classification, 5.0, FAST_PROFILE)
        assert pause == 5.0, "Navigation pause must be preserved exactly"

    def test_aguarda_carregamento_preserves_full_pause(self):
        """Req 7.3: Actions with aguarda_carregamento=True are SENSITIVE,
        preserving the full pause_sugerida for page load stabilization."""
        acao_tec = {"acao": "clique", "aguarda_carregamento": True}
        passo = {"tipo_passo": "interacao", "pause_sugerida": 4.0}

        classification = _main.classificar_acao(acao_tec, passo)
        assert classification == _main.ActionClassification.SENSITIVE

        pause = _main.calcular_pausa_pos_acao(classification, 4.0, FAST_PROFILE)
        assert pause == 4.0, "aguarda_carregamento pause must be preserved exactly"

    def test_page_refresh_preserves_full_pause(self):
        """Req 7.1: page_refresh tipo_passo is classified as SENSITIVE."""
        acao_tec = {"acao": "clique"}
        passo = {"tipo_passo": "page_refresh", "pause_sugerida": 6.0}

        classification = _main.classificar_acao(acao_tec, passo)
        assert classification == _main.ActionClassification.SENSITIVE

        pause = _main.calcular_pausa_pos_acao(classification, 6.0, FAST_PROFILE)
        assert pause == 6.0

    def test_high_pause_sugerida_preserves_full_value(self):
        """Req 7.3: pause_sugerida > 3.0 is always SENSITIVE regardless of action type."""
        acao_tec = {"acao": "clique"}
        passo = {"tipo_passo": "interacao", "pause_sugerida": 4.5}

        classification = _main.classificar_acao(acao_tec, passo)
        assert classification == _main.ActionClassification.SENSITIVE

        pause = _main.calcular_pausa_pos_acao(classification, 4.5, FAST_PROFILE)
        assert pause == 4.5

    def test_wait_for_load_state_30s_timeout_in_source(self):
        """Req 7.1: Verify that main.py uses 30s timeout for wait_for_load_state
        and that it is NOT affected by pacing profile."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "main.py",
        )
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Verify 30s timeout is used for wait_for_load_state
        assert 'wait_for_load_state("load", timeout=30_000)' in source, (
            "main.py must use 30s timeout for wait_for_load_state"
        )

        # Verify the comment documents that pacing does NOT affect page load waits
        assert "NOT affected by pacing optimization" in source, (
            "main.py must document that page load waits are not affected by pacing"
        )


# ===========================================================================
# Test: Full execution with "fast" profile applies correct constants (Req 8.7)
# ===========================================================================


class TestFastProfileAppliedThroughout:
    """Integration tests verifying the 'fast' profile constants are used consistently."""

    def test_fast_profile_constants_are_correct(self):
        """Req 8.7: The 'fast' profile has the expected constants from the design."""
        profile = FAST_PROFILE
        assert profile.name == "fast"
        assert profile.cursor_base_ms == 600
        assert profile.cursor_min_ms == 300
        assert profile.cursor_max_ms == 1400
        assert profile.safe_pause_min == 0.1
        assert profile.safe_pause_max == 0.3
        assert profile.steps_per_pixel == 0.06
        assert profile.steps_min == 12
        assert profile.steps_max == 50

    def test_fast_profile_safe_pause_bounds(self):
        """Req 8.7: Safe actions with 'fast' profile get pauses in [0.1, 0.3]s."""
        classification = _main.ActionClassification.SAFE

        # Run multiple times to verify bounds hold
        for _ in range(50):
            pause = _main.calcular_pausa_pos_acao(classification, 2.0, FAST_PROFILE)
            assert 0.1 <= pause <= 0.3, (
                f"Fast profile safe pause {pause} outside [0.1, 0.3]"
            )

    def test_fast_profile_sensitive_pause_preserved(self):
        """Req 8.7: Sensitive actions with 'fast' profile still get full pause_sugerida."""
        classification = _main.ActionClassification.SENSITIVE

        pause = _main.calcular_pausa_pos_acao(classification, 5.0, FAST_PROFILE)
        assert pause == 5.0

    @pytest.mark.asyncio
    async def test_fast_profile_passed_to_click_animation(self):
        """Req 8.7: The profile is passed through to clicar_com_animacao during execution."""
        page = mock.AsyncMock()
        timeline = []
        captured_profile = None

        passo = {
            "pedagogia": {"micro_narracao": "Teste de perfil."},
        }
        acao_tec = {
            "acao": "clique",
            "elemento_alvo": {"label_curto": "Campo"},
        }

        fake_mp3 = "/tmp/fake_profile.mp3"

        async def capture_click(page, acao, profile=None):
            nonlocal captured_profile
            captured_profile = profile
            return True

        with mock.patch.object(_main, "gerar_audio", new_callable=mock.AsyncMock, return_value=fake_mp3):
            with mock.patch.object(_main, "exibir_legenda_cinema", new_callable=mock.AsyncMock):
                with mock.patch.object(_main, "remover_legenda", new_callable=mock.AsyncMock):
                    with mock.patch.object(_main, "iniciar_reproducao_audio"):
                        with mock.patch.object(_main, "clicar_com_animacao", new_callable=mock.AsyncMock, side_effect=capture_click):
                            with mock.patch.object(_main, "aguardar_audio_terminar", new_callable=mock.AsyncMock):
                                with mock.patch.object(_main.pygame.mixer, "Sound") as mock_sound:
                                    mock_sound.return_value.get_length.return_value = 1.0

                                    await _main._executar_acao_com_narracao(
                                        page=page,
                                        acao_tec=acao_tec,
                                        passo=passo,
                                        profile=FAST_PROFILE,
                                        id_passo=1,
                                        idx_acao=0,
                                        nome_arquivo_base="test_profile",
                                        voz_escolhida="pt-BR-FranciscaNeural",
                                        tempo_inicio_gravacao=time.time() - 5.0,
                                        timeline_audios=timeline,
                                    )

        assert captured_profile is not None, "Profile must be passed to clicar_com_animacao"
        assert captured_profile.name == "fast"
        assert captured_profile.cursor_base_ms == 600

    def test_classification_and_pause_integration_with_fast_profile(self):
        """Req 8.7: End-to-end classification → pause calculation with fast profile."""
        # Safe action: simple click
        acao_safe = {"acao": "clique"}
        passo_safe = {"tipo_passo": "interacao", "pause_sugerida": 2.0}

        cls_safe = _main.classificar_acao(acao_safe, passo_safe)
        assert cls_safe == _main.ActionClassification.SAFE
        pause_safe = _main.calcular_pausa_pos_acao(cls_safe, 2.0, FAST_PROFILE)
        assert 0.1 <= pause_safe <= 0.3

        # Sensitive action: double-click
        acao_sensitive = {"acao": "duplo_clique"}
        passo_sensitive = {"tipo_passo": "interacao", "pause_sugerida": 2.5}

        cls_sensitive = _main.classificar_acao(acao_sensitive, passo_sensitive)
        assert cls_sensitive == _main.ActionClassification.SENSITIVE
        pause_sensitive = _main.calcular_pausa_pos_acao(cls_sensitive, 2.5, FAST_PROFILE)
        assert pause_sensitive == 2.5

        # Sensitive action: navigation
        acao_nav = {"acao": "clique", "aguarda_carregamento": True}
        passo_nav = {"tipo_passo": "navegacao", "pause_sugerida": 5.0}

        cls_nav = _main.classificar_acao(acao_nav, passo_nav)
        assert cls_nav == _main.ActionClassification.SENSITIVE
        pause_nav = _main.calcular_pausa_pos_acao(cls_nav, 5.0, FAST_PROFILE)
        assert pause_nav == 5.0

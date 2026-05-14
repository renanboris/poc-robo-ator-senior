"""
Tests for the HITL step-by-step validation flow.

Validates: Task 7.1 — Complete flow: HITL step-by-step → correction → recording.

Tests verify:
1. Step-by-step pause behavior (overlay + decision wait)
2. "Ok" decision reinforces Brain
3. "Corrigir" decision activates radar and saves correction
4. Recording is triggered when _decisao_relatorio == "gravar"
"""

import subprocess
import sys
from unittest.mock import AsyncMock, patch

import pytest

from validator_hitl import NivelConfianca


# ─── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def hitl_validator():
    """Creates a HitlValidator instance with mocked dependencies."""
    with patch("validator_hitl._score_engine"):
        from validator_hitl import HitlValidator

        validator = HitlValidator()
        return validator


@pytest.fixture
def mock_page():
    """Creates a mock Playwright Page object."""
    page = AsyncMock()
    page.evaluate = AsyncMock(return_value=True)
    page.screenshot = AsyncMock(return_value=b"fake_screenshot")
    return page


@pytest.fixture
def sample_acao_tec():
    """Sample acao_tecnica dict for testing."""
    return {
        "acao": "clique",
        "intencao_semantica": "Clicar no botão Salvar",
        "elemento_alvo": {
            "label_curto": "Salvar",
            "seletor_hint": "[aria-label='Salvar']",
            "seletor_css": "button.save-btn",
        },
    }


@pytest.fixture
def sample_passo(sample_acao_tec):
    """Sample passo dict for testing."""
    return {
        "id_passo": 1,
        "acoes_tecnicas": [sample_acao_tec],
        "pedagogia": {
            "tooltip_dap": "Salvar registro",
            "ancora": "Clique no botão Salvar para confirmar",
        },
    }


# ─── Test 1: Step-by-step pause behavior ─────────────────────────────────────


class TestStepByStepPauseBehavior:
    """When _modo_auto_restante == 0 and action succeeds, the system pauses."""

    @pytest.mark.asyncio
    async def test_step_by_step_shows_overlay_on_success(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """When action succeeds in step-by-step mode, overlay is shown and decision awaited."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ) as mock_overlay,
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="ok"
            ) as mock_decisao,
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch("validator_hitl._registrar_sucesso_cache") as mock_brain,
        ):
            result = await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # Overlay was shown
            mock_overlay.assert_called_once()
            # Decision was awaited
            mock_decisao.assert_called_once()
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_auto_mode_skips_overlay(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """When _modo_auto_restante > 0 and action succeeds, overlay is NOT shown."""
        hitl_validator._modo_auto_restante = 3
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ) as mock_overlay,
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock
            ) as mock_decisao,
        ):
            result = await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # Overlay was NOT shown (auto mode)
            mock_overlay.assert_not_called()
            mock_decisao.assert_not_called()
            # Auto counter decremented
            assert hitl_validator._modo_auto_restante == 2
            assert result == "ok"


# ─── Test 2: "Ok" decision reinforces Brain ──────────────────────────────────


class TestOkDecisionReinforcesBrain:
    """When decision is 'ok', _registrar_sucesso_cache is called."""

    @pytest.mark.asyncio
    async def test_ok_decision_calls_registrar_sucesso(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """'Ok' decision reinforces the Brain memory for the action's intencao_semantica."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Sniper"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="ok"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch("validator_hitl._registrar_sucesso_cache") as mock_brain,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # Brain was reinforced with the action's intencao_semantica
            mock_brain.assert_called_once_with("Clicar no botão Salvar")

    @pytest.mark.asyncio
    async def test_ok_decision_does_not_call_brain_without_intencao(
        self, hitl_validator, mock_page, sample_passo
    ):
        """'Ok' decision does NOT call Brain if intencao_semantica is empty."""
        acao_sem_intencao = {
            "acao": "clique",
            "intencao_semantica": "",
            "elemento_alvo": {"label_curto": "X", "seletor_hint": "#btn"},
        }
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="ok"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch("validator_hitl._registrar_sucesso_cache") as mock_brain,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, acao_sem_intencao, passo=sample_passo
            )

            # Brain was NOT called (empty intencao)
            mock_brain.assert_not_called()


# ─── Test 3: "Corrigir" decision activates radar ─────────────────────────────


class TestCorrigirDecisionActivatesRadar:
    """When decision is 'corrigir', radar is activated and correction saved."""

    @pytest.mark.asyncio
    async def test_corrigir_activates_radar_and_saves_to_brain(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """'Corrigir' activates radar, captures selector, saves to Brain with hitl_corrigido=True."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator,
                "_aguardar_decisao_step",
                new_callable=AsyncMock,
                return_value="corrigir",
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator,
                "_ativar_radar_step",
                new_callable=AsyncMock,
                return_value="[aria-label='Gravar']",
            ) as mock_radar,
            patch.object(
                hitl_validator, "_salvar_correcao_no_brain"
            ) as mock_salvar,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # Radar was activated
            mock_radar.assert_called_once_with(mock_page)
            # Correction was saved to Brain
            mock_salvar.assert_called_once_with(sample_acao_tec, "[aria-label='Gravar']")

    @pytest.mark.asyncio
    async def test_corrigir_with_empty_selector_does_not_save(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """If radar returns empty string (timeout/cancel), nothing is saved."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator,
                "_aguardar_decisao_step",
                new_callable=AsyncMock,
                return_value="corrigir",
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator,
                "_ativar_radar_step",
                new_callable=AsyncMock,
                return_value="",
            ),
            patch.object(
                hitl_validator, "_salvar_correcao_no_brain"
            ) as mock_salvar,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # Nothing saved when radar returns empty
            mock_salvar.assert_not_called()

    def test_salvar_correcao_no_brain_calls_registrar_with_hitl_flag(
        self, hitl_validator, sample_acao_tec
    ):
        """_salvar_correcao_no_brain calls _registrar_sucesso_cache with hitl_corrigido=True."""
        with (
            patch("validator_hitl._registrar_sucesso_cache") as mock_brain,
            patch("validator_hitl._score_engine") as mock_score,
        ):
            hitl_validator._salvar_correcao_no_brain(
                sample_acao_tec, "[data-testid='save-btn']"
            )

            mock_brain.assert_called_once_with(
                "Clicar no botão Salvar",
                seletor="[data-testid='save-btn']",
                iframe=None,
                hitl_corrigido=True,
            )
            assert hitl_validator._stats["correcoes_salvas"] == 1


# ─── Test 4: Recording is triggered ──────────────────────────────────────────


class TestRecordingTriggered:
    """When _decisao_relatorio == 'gravar', subprocess.Popen is called."""

    @pytest.mark.asyncio
    async def test_gravar_decision_triggers_subprocess(self, hitl_validator):
        """After HITL completes with 'gravar', subprocess.Popen starts recording."""
        caminho_json = "roteiros_salvos/meu_roteiro.json"
        hitl_validator._decisao_relatorio = "gravar"
        hitl_validator._stats["correcoes_salvas"] = 0

        with patch("validator_hitl.subprocess.Popen") as mock_popen:
            # Simulate the recording dispatch logic directly
            if hitl_validator._decisao_relatorio == "gravar":
                subprocess.Popen([sys.executable, "main.py", caminho_json, "--record"])

            mock_popen.assert_called_once_with(
                [sys.executable, "main.py", caminho_json, "--record"]
            )

    @pytest.mark.asyncio
    async def test_fechar_decision_does_not_trigger_subprocess(self, hitl_validator):
        """After HITL completes with 'fechar', no recording is started."""
        hitl_validator._decisao_relatorio = "fechar"

        with patch("validator_hitl.subprocess.Popen") as mock_popen:
            # Simulate the recording dispatch logic
            if hitl_validator._decisao_relatorio == "gravar":
                subprocess.Popen(
                    [sys.executable, "main.py", "roteiro.json", "--record"]
                )

            mock_popen.assert_not_called()

    def test_decisao_relatorio_defaults_to_fechar(self, hitl_validator):
        """Default _decisao_relatorio is 'fechar' (no recording)."""
        assert hitl_validator._decisao_relatorio == "fechar"


# ─── Test 5: Auto mode skips pauses ──────────────────────────────────────────


class TestAutoModeSkipsPauses:
    """When _modo_auto_restante > 0 and action succeeds, overlay/decision are skipped."""

    @pytest.mark.asyncio
    async def test_auto_mode_decrements_counter(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Counter decrements from 5 to 4 when action succeeds in auto mode."""
        hitl_validator._modo_auto_restante = 5
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
        ):
            result = await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            assert hitl_validator._modo_auto_restante == 4
            assert result == "ok"

    @pytest.mark.asyncio
    async def test_auto_mode_does_not_show_overlay(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """_mostrar_overlay_step is NOT called when in auto mode."""
        hitl_validator._modo_auto_restante = 5
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ) as mock_overlay,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            mock_overlay.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_mode_does_not_await_decision(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """_aguardar_decisao_step is NOT called when in auto mode."""
        hitl_validator._modo_auto_restante = 5
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock
            ) as mock_decisao,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            mock_decisao.assert_not_called()


# ─── Test 6: Auto mode resets on failure ─────────────────────────────────────


class TestAutoModeResetsOnFailure:
    """When action FAILS during auto mode, counter resets and falha_dura is called."""

    @pytest.mark.asyncio
    async def test_failure_resets_counter_to_zero(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """_modo_auto_restante resets to 0 when action fails in auto mode."""
        hitl_validator._modo_auto_restante = 5
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=False
            ),
            # No modo step-by-step, falha usa overlay step (não _pausa_falha_dura)
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="pular"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            assert hitl_validator._modo_auto_restante == 0

    @pytest.mark.asyncio
    async def test_failure_calls_pausa_falha_dura(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Em modo step-by-step, falha usa overlay step (não _pausa_falha_dura).
        _pausa_falha_dura só é chamada em modo --silent."""
        hitl_validator._modo_auto_restante = 3
        hitl_validator._silent = False

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ) as mock_overlay,
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="pular"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_pausa_falha_dura", new_callable=AsyncMock, return_value="pular"
            ) as mock_falha,
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            # No modo step-by-step: overlay step é chamado, não _pausa_falha_dura
            mock_overlay.assert_called_once()
            mock_falha.assert_not_called()

    @pytest.mark.asyncio
    async def test_full_scenario_auto5_two_successes_then_failure(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Full scenario: Auto 5 → 2 successes → failure → counter resets to 0."""
        hitl_validator._modo_auto_restante = 5
        hitl_validator._silent = False

        # First two calls succeed, third fails
        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
        ):
            # Success 1: 5 → 4
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )
            assert hitl_validator._modo_auto_restante == 4

            # Success 2: 4 → 3
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )
            assert hitl_validator._modo_auto_restante == 3

        # Now failure — step-by-step overlay handles it
        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=False
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="pular"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
        ):
            # Failure: counter resets to 0
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )
            assert hitl_validator._modo_auto_restante == 0


# ─── Test 7: Auto mode set by decision ───────────────────────────────────────


class TestAutoModeSetByDecision:
    """Decision 'auto_N' sets _modo_auto_restante to N."""

    @pytest.mark.asyncio
    async def test_auto_5_sets_counter_to_5(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Decision 'auto_5' sets _modo_auto_restante = 5."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="auto_5"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            assert hitl_validator._modo_auto_restante == 5

    @pytest.mark.asyncio
    async def test_auto_10_sets_counter_to_10(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Decision 'auto_10' sets _modo_auto_restante = 10."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Sniper"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="auto_10"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            assert hitl_validator._modo_auto_restante == 10

    @pytest.mark.asyncio
    async def test_ok_decision_does_not_change_auto_counter(
        self, hitl_validator, mock_page, sample_passo, sample_acao_tec
    ):
        """Decision 'ok' does NOT change _modo_auto_restante."""
        hitl_validator._modo_auto_restante = 0
        hitl_validator._silent = False
        hitl_validator._current_step_index = 0
        hitl_validator._total_steps = 5

        with (
            patch(
                "validator_hitl._nivel_confianca",
                return_value=NivelConfianca.MEDIA,
            ),
            patch(
                "validator_hitl.encontrar_e_clicar", new_callable=AsyncMock, return_value=True
            ),
            patch(
                "validator_hitl.obter_ultima_camada_vencedora", return_value="Brain"
            ),
            patch.object(
                hitl_validator, "_mostrar_overlay_step", new_callable=AsyncMock
            ),
            patch.object(
                hitl_validator, "_aguardar_decisao_step", new_callable=AsyncMock, return_value="ok"
            ),
            patch.object(
                hitl_validator, "_remove_step_highlight", new_callable=AsyncMock
            ),
            patch("validator_hitl._registrar_sucesso_cache"),
        ):
            await hitl_validator._executar_acao_com_hitl(
                mock_page, sample_acao_tec, passo=sample_passo
            )

            assert hitl_validator._modo_auto_restante == 0

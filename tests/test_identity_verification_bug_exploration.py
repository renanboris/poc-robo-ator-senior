"""
test_identity_verification_bug_exploration.py

Bug Condition Exploration Tests — Verificacao de Identidade (3 Cenarios de Falso Positivo)
===========================================================================================

OBJETIVO: Demonstrar os 3 bugs de falso positivo ANTES do fix.

Bug 1 (Cenario A): Sniper executa candidatos CSS posicionais sem verificacao de identidade.
Bug 2 (Cenario B): _verificar_identidade_por_coordenadas usa substring matching.
Bug 3 (Cenario C): _verificar_identidade_elemento usa substring matching.

RESULTADO ESPERADO: Estes testes PASSAM no codigo nao corrigido (confirmando que o bug existe).
Apos o fix, estes testes devem FALHAR (confirmando que o bug foi corrigido).

Validates: Requirements 1.1, 1.2, 1.3 (bugfix.md)
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402
from vision_engine import (
    _contem_indice_posicional,
    _verificar_identidade_por_coordenadas,
    _verificar_identidade_elemento,
)


# ===========================================================================
# HELPERS
# ===========================================================================

def _make_acao_tec(seletor_hint: str, label_curto: str, acao: str = "clique") -> dict:
    return {
        "acao": acao,
        "intencao_semantica": f"Selecionar item '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": seletor_hint,
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Modal de selecao",
            "tipo_elemento": "span",
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


def _make_page_mock_sniper(inner_text_do_elemento: str) -> MagicMock:
    """
    Mock de page onde o locator posicional retorna inner_text_do_elemento.
    Brain e Gemini Vision sao desativados para isolar o comportamento da camada Hint.
    """
    locator_mock = AsyncMock()
    locator_mock.wait_for = AsyncMock(return_value=None)
    locator_mock.inner_text = AsyncMock(return_value=inner_text_do_elemento)
    locator_mock.click = AsyncMock(return_value=None)
    locator_mock.is_visible = AsyncMock(return_value=True)
    locator_mock.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_mock.bounding_box = AsyncMock(
        return_value={"x": 100, "y": 200, "width": 80, "height": 30}
    )
    locator_mock.hover = AsyncMock(return_value=None)
    locator_mock.evaluate = AsyncMock(return_value=None)
    locator_mock.dblclick = AsyncMock(return_value=None)

    locator_container = MagicMock()
    locator_container.first = locator_mock

    page_mock = AsyncMock()
    page_mock.locator = MagicMock(return_value=locator_container)
    page_mock.frames = []
    page_mock.main_frame = MagicMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.evaluate = AsyncMock(return_value=0)
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot")

    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    return page_mock


def _patches_isolamento_sniper():
    """
    Patches que desativam Brain, Sniper semantico e Gemini Vision,
    forcando o orquestrador a chegar na camada Hint (seletor_hint posicional).
    """
    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_tentar_candidato", new=_sniper_falha_hint_sucesso),
        patch.object(
            vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)
        ),
        patch.object(
            vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)
        ),
        # Desativa menu de contexto para nao desviar o fluxo para Gemini
        patch.object(
            vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)
        ),
    ]


async def _sniper_falha_hint_sucesso(page, candidato, acao, valor, timeout_ms=3500):
    """
    Mock de _tentar_candidato:
    - Falha para candidatos do Sniper semantico
    - Sucede para candidatos posicionais (camada Hint) — simulando o bug
    """
    seletor = candidato.seletor or ""
    if _contem_indice_posicional(seletor):
        return True  # Bug: executa sem verificar identidade
    return False


# ===========================================================================
# BUG 1 — Sniper: candidatos CSS posicionais sem verificacao de identidade
# ===========================================================================

class TestBug1SniperCandidatoPosicionalSemVerificacao:
    """
    Cenario A: O Sniper executa candidatos CSS posicionais via _tentar_candidato()
    sem verificar se o elemento encontrado corresponde ao label_curto esperado.

    Comportamento BUGGY (codigo nao corrigido):
      - Sniper tenta span:nth-child(1), elemento tem texto "EMPRESA 1"
      - Nenhuma verificacao de identidade
      - Retorna True (FALSO POSITIVO)

    Comportamento CORRETO (apos fix):
      - Sniper tenta span:nth-child(1), elemento tem texto "EMPRESA 1"
      - Verifica: "1" == "empresa 1" -> False -> rejeita candidato
      - Retorna False (escala para proxima camada)

    Estes testes PASSAM no codigo nao corrigido (confirmando o bug).
    Apos o fix, devem FALHAR.
    """

    @pytest.mark.asyncio
    async def test_sniper_nth_child_aceita_empresa_1_quando_label_e_1(self):
        """
        **Validates: Requirements 1.1 (bugfix.md)**

        Caso real do bug: seletor_hint = '[role="dialog"] span:nth-child(1)',
        label_curto = '1', mas o elemento na posicao tem texto 'EMPRESA 1'.

        No codigo NAO corrigido: a acao e executada em 'EMPRESA 1' sem verificacao.
        Este teste PASSA — confirmando que o bug existe.

        Contraexemplo documentado:
          seletor_hint = '[role="dialog"] span:nth-child(1)'
          label_curto  = '1'
          texto real   = 'EMPRESA 1'
          resultado    = True (FALSO POSITIVO — bug confirmado)
        """
        acao_tec = _make_acao_tec(
            seletor_hint='[role="dialog"] span:nth-child(1)',
            label_curto="1",
        )
        page_mock = _make_page_mock_sniper(inner_text_do_elemento="EMPRESA 1")

        patches = _patches_isolamento_sniper()
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        # No codigo BUGADO: retorna True (falso positivo)
        # No codigo CORRIGIDO: retorna False (identidade nao confirmada)
        # Este assert PASSA no codigo bugado — confirmando o bug
        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo) no codigo nao corrigido, "
            "mas encontrar_e_clicar retornou False. "
            "Isso indica que o bug ja foi corrigido ou o mock nao esta isolando corretamente."
        )

    @pytest.mark.asyncio
    async def test_sniper_nth_of_type_aceita_texto_errado(self):
        """
        **Validates: Requirements 1.1 (bugfix.md)**

        Variacao: seletor com :nth-of-type, label_curto='Sim',
        elemento tem texto 'Sim, confirmar operacao'.

        No codigo NAO corrigido: executa sem verificacao.
        Este teste PASSA — confirmando o bug.
        """
        acao_tec = _make_acao_tec(
            seletor_hint="p-dialog li:nth-of-type(2) span",
            label_curto="Sim",
        )
        page_mock = _make_page_mock_sniper(inner_text_do_elemento="Sim, confirmar operacao")

        patches = _patches_isolamento_sniper()
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo) no codigo nao corrigido."
        )

    def test_contem_indice_posicional_detecta_nth_child(self):
        """
        Verifica que _contem_indice_posicional detecta :nth-child corretamente.
        Esta funcao e a base para a verificacao que o fix deve adicionar.
        """
        assert _contem_indice_posicional('[role="dialog"] span:nth-child(1)') is True
        assert _contem_indice_posicional('p-dialog li:nth-of-type(2) span') is True
        assert _contem_indice_posicional('[aria-label="Salvar"]') is False
        assert _contem_indice_posicional('[name="e070emp"] button') is False

    def test_sniper_atual_nao_tem_funcao_e_candidato_posicional(self):
        """
        Demonstra que o Sniper atual nao tem verificacao de identidade para
        candidatos posicionais — a funcao _e_candidato_posicional nao existe ainda.

        Este teste documenta a ausencia do fix: o codigo do Sniper para candidatos
        CSS (bloco else) chama _tentar_candidato diretamente sem verificar identidade.
        Apos o fix, _e_candidato_posicional sera criada e este teste falhara.
        """
        assert not hasattr(vision_engine, '_e_candidato_posicional'), (
            "Fix ja aplicado: _e_candidato_posicional existe. "
            "Este teste de bug condition nao e mais valido."
        )


# ===========================================================================
# BUG 2 — _verificar_identidade_por_coordenadas: substring matching
# ===========================================================================

class TestBug2CoordenadasSubstringMatching:
    """
    Cenario B: _verificar_identidade_por_coordenadas usa substring matching
    (label_curto in texto_elemento), aceitando falsos positivos onde o label
    e apenas parte de um texto maior.

    Comportamento BUGGY (codigo nao corrigido):
      - label_curto='1', texto_elemento='EMPRESA 1'
      - '1' in 'empresa 1' -> True (FALSO POSITIVO)
      - Retorna (True, False)

    Comportamento CORRETO (apos fix):
      - '1' == 'empresa 1' -> False
      - Retorna (False, False)

    Estes testes PASSAM no codigo nao corrigido (confirmando o bug).
    Apos o fix, devem FALHAR.
    """

    @pytest.mark.asyncio
    async def test_label_1_aceito_em_empresa_1(self):
        """
        **Validates: Requirements 1.3 (bugfix.md)**

        Caso real do bug: label_curto='1', elemento tem texto 'EMPRESA 1'.
        Substring matching: '1' in 'empresa 1' -> True (FALSO POSITIVO).

        No codigo NAO corrigido: retorna (True, False).
        Este teste PASSA — confirmando o bug.

        Contraexemplo documentado:
          label_curto    = '1'
          texto_elemento = 'EMPRESA 1'
          resultado      = (True, False) — FALSO POSITIVO (bug confirmado)
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento(page, x, y):
            return {"tagName": "SPAN", "innerText": "EMPRESA 1"}, x, y, False

        with patch.object(vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=960,
                y=324,
                label_curto="1",
                iframe_hint=None,
            )

        # No codigo BUGADO: retorna (True, False) — substring matching aceita '1' in 'EMPRESA 1'
        # No codigo CORRIGIDO: retorna (False, False) — match exato rejeita
        assert resultado == (True, False), (
            f"BUG NAO CONFIRMADO: esperava (True, False) no codigo nao corrigido, "
            f"mas obteve {resultado}. "
            f"Isso indica que o fix ja foi aplicado (match exato implementado)."
        )

    @pytest.mark.asyncio
    async def test_label_sim_aceito_em_sim_confirmar(self):
        """
        **Validates: Requirements 1.3 (bugfix.md)**

        Variacao: label_curto='Sim', texto='Sim, confirmar operacao'.
        Substring matching: 'sim' in 'sim, confirmar operacao' -> True (FALSO POSITIVO).
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento(page, x, y):
            return {"tagName": "BUTTON", "innerText": "Sim, confirmar operacao"}, x, y, False

        with patch.object(vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=400,
                label_curto="Sim",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"BUG NAO CONFIRMADO: esperava (True, False), obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_label_salvar_aceito_em_salvar_e_fechar(self):
        """
        **Validates: Requirements 1.3 (bugfix.md)**

        Variacao: label_curto='Salvar', texto='Salvar e Fechar'.
        Substring matching: 'salvar' in 'salvar e fechar' -> True (FALSO POSITIVO).
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento(page, x, y):
            return {"tagName": "BUTTON", "innerText": "Salvar e Fechar"}, x, y, False

        with patch.object(vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=800,
                y=600,
                label_curto="Salvar",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"BUG NAO CONFIRMADO: esperava (True, False), obteve {resultado}."
        )

    @pytest.mark.asyncio
    @given(
        label=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
        ),
        sufixo=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")),
        ),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_substring_matching_aceita_falso_positivo(
        self, label: str, sufixo: str
    ):
        """
        **Validates: Requirements 1.3 (bugfix.md)**

        Property: Para qualquer (label, sufixo) onde label nao e vazio e sufixo nao e vazio,
        o texto_elemento = label + ' ' + sufixo e aceito pelo codigo nao corrigido
        (substring matching), mas deveria ser rejeitado (match exato).

        Este teste PASSA no codigo nao corrigido — confirmando o bug para qualquer variacao.
        """
        if not label.strip() or not sufixo.strip():
            return  # pula casos degenerados

        texto_elemento = label + " " + sufixo  # label e substring de texto_elemento

        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento(page, x, y):
            return {"tagName": "SPAN", "innerText": texto_elemento}, x, y, False

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=100,
                y=100,
                label_curto=label,
                iframe_hint=None,
            )

        # No codigo BUGADO: retorna (True, False) — substring matching aceita
        # No codigo CORRIGIDO: retorna (False, False) — match exato rejeita
        assert resultado == (True, False), (
            f"BUG NAO CONFIRMADO: esperava (True, False) para label={label!r}, "
            f"texto={texto_elemento!r}, mas obteve {resultado}."
        )


# ===========================================================================
# BUG 3 — _verificar_identidade_elemento: substring matching
# ===========================================================================

class TestBug3VerificarIdentidadeElementoSubstringMatching:
    """
    Cenario C: _verificar_identidade_elemento usa substring matching
    (needle in texto.strip().lower()), aceitando falsos positivos.

    Comportamento BUGGY (codigo nao corrigido):
      - label_curto='Sim', texto='Sim, confirmar'
      - 'sim' in 'sim, confirmar' -> True (FALSO POSITIVO)
      - Retorna True

    Comportamento CORRETO (apos fix):
      - 'sim' == 'sim, confirmar' -> False
      - Retorna False

    Estes testes PASSAM no codigo nao corrigido (confirmando o bug).
    Apos o fix, devem FALHAR.
    """

    @pytest.mark.asyncio
    async def test_sim_aceito_em_sim_confirmar(self):
        """
        **Validates: Requirements 1.2 (bugfix.md)**

        Caso: label_curto='Sim', elemento tem texto 'Sim, confirmar'.
        Substring matching: 'sim' in 'sim, confirmar' -> True (FALSO POSITIVO).

        No codigo NAO corrigido: retorna True.
        Este teste PASSA — confirmando o bug.

        Contraexemplo documentado:
          label_curto    = 'Sim'
          texto_elemento = 'Sim, confirmar'
          resultado      = True — FALSO POSITIVO (bug confirmado)
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="Sim, confirmar")

        resultado = await _verificar_identidade_elemento(locator_mock, "Sim")

        # No codigo BUGADO: retorna True — substring matching aceita 'sim' in 'sim, confirmar'
        # No codigo CORRIGIDO: retorna False — match exato rejeita
        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo) no codigo nao corrigido, "
            "mas _verificar_identidade_elemento retornou False. "
            "Isso indica que o fix ja foi aplicado."
        )

    @pytest.mark.asyncio
    async def test_1_aceito_em_empresa_1(self):
        """
        **Validates: Requirements 1.2 (bugfix.md)**

        Caso real do bug: label_curto='1', elemento tem texto 'EMPRESA 1'.
        Substring matching: '1' in 'empresa 1' -> True (FALSO POSITIVO).
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="EMPRESA 1")

        resultado = await _verificar_identidade_elemento(locator_mock, "1")

        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo) no codigo nao corrigido."
        )

    @pytest.mark.asyncio
    async def test_salvar_aceito_em_salvar_e_fechar(self):
        """
        **Validates: Requirements 1.2 (bugfix.md)**

        Caso: label_curto='Salvar', elemento tem texto 'Salvar e Fechar'.
        Substring matching: 'salvar' in 'salvar e fechar' -> True (FALSO POSITIVO).
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="Salvar e Fechar")

        resultado = await _verificar_identidade_elemento(locator_mock, "Salvar")

        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo) no codigo nao corrigido."
        )

    @pytest.mark.asyncio
    async def test_substring_matching_via_pai_tambem_aceita_falso_positivo(self):
        """
        **Validates: Requirements 1.2 (bugfix.md)**

        Caso: texto do elemento nao bate, mas texto do pai contem o label como substring.
        O codigo atual tenta o pai com o mesmo substring matching.
        """
        locator_mock = AsyncMock()
        # Elemento principal nao tem o texto
        locator_mock.inner_text = AsyncMock(return_value="Outro texto")

        # Pai tem o label como substring
        pai_mock = AsyncMock()
        pai_mock.inner_text = AsyncMock(return_value="Confirmar Pedido")
        locator_mock.locator = MagicMock(return_value=pai_mock)

        resultado = await _verificar_identidade_elemento(locator_mock, "Confirmar")

        # No codigo BUGADO: retorna True — 'confirmar' in 'confirmar pedido' -> True
        # No codigo CORRIGIDO: retorna False — 'confirmar' != 'confirmar pedido'
        assert resultado is True, (
            "BUG NAO CONFIRMADO: esperava True (falso positivo via pai) no codigo nao corrigido."
        )

    @pytest.mark.asyncio
    @given(
        label=st.text(
            min_size=3,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll")),
        ),
        sufixo=st.text(
            min_size=2,
            max_size=15,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Zs")),
        ),
    )
    @settings(max_examples=30, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_verificar_identidade_elemento_substring_matching(
        self, label: str, sufixo: str
    ):
        """
        **Validates: Requirements 1.2 (bugfix.md)**

        Property: Para qualquer (label, sufixo) onde label nao e vazio e sufixo nao e vazio,
        o texto_elemento = label + ' ' + sufixo e aceito pelo codigo nao corrigido
        (substring matching), mas deveria ser rejeitado (match exato).

        Este teste PASSA no codigo nao corrigido — confirmando o bug para qualquer variacao.
        """
        if not label.strip() or not sufixo.strip():
            return

        texto_elemento = label + " " + sufixo

        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value=texto_elemento)

        resultado = await _verificar_identidade_elemento(locator_mock, label)

        # No codigo BUGADO: retorna True — substring matching aceita
        # No codigo CORRIGIDO: retorna False — match exato rejeita
        assert resultado is True, (
            f"BUG NAO CONFIRMADO: esperava True para label={label!r}, "
            f"texto={texto_elemento!r}, mas obteve {resultado}."
        )

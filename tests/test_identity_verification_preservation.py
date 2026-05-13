"""
test_identity_verification_preservation.py

Preservation Tests — Verificacao de Identidade (Comportamentos que NAO devem mudar)
=====================================================================================

OBJETIVO: Capturar comportamentos de fail-open e candidatos semanticos que devem
permanecer INALTERADOS antes e depois do fix.

Estes testes devem PASSAR tanto no codigo nao corrigido quanto no codigo corrigido.
Sao o contrato de que o fix nao introduz regressoes.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5 (bugfix.md)
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402
from vision_engine import (
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
            "contexto_tela": "Tela principal",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


def _make_page_mock_semantico(inner_text_do_elemento: str = "Salvar") -> MagicMock:
    """
    Mock de page onde o locator semantico retorna inner_text_do_elemento.
    Sniper semantico pode acertar — simula candidato de alta confianca.
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


def _patches_isolamento_sniper_semantico(seletor_semantico: str):
    """
    Patches que fazem o Sniper acertar para o candidato semantico especificado
    e falham para todos os outros. Brain e Gemini desativados.
    """
    async def _tentar_candidato_semantico(page, candidato, acao, valor, timeout_ms=3500):
        """Acerta apenas para o seletor semantico especificado."""
        if candidato.seletor == seletor_semantico:
            return True
        return False

    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_tentar_candidato", new=_tentar_candidato_semantico),
        patch.object(
            vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)
        ),
        patch.object(
            vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)
        ),
        patch.object(
            vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)
        ),
    ]


# ===========================================================================
# TASK 2.1 — Fail-open em _verificar_identidade_por_coordenadas()
# ===========================================================================

class TestFailOpenVerificarIdentidadePorCoordenadas:
    """
    Preservation: comportamentos de fail-open em _verificar_identidade_por_coordenadas()
    devem permanecer INALTERADOS antes e depois do fix.

    Validates: Requirements 3.1, 3.2, 3.3 (bugfix.md)
    """

    @pytest.mark.asyncio
    async def test_label_vazio_retorna_true_false_sem_verificacao(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: label_curto vazio -> fail-open -> (True, False) sem verificacao.

        Este comportamento NAO deve mudar apos o fix.
        O sistema nao deve tentar verificar identidade quando nao ha label para comparar.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        # Mesmo que o elemento tenha qualquer texto, fail-open deve ser aplicado
        resultado = await _verificar_identidade_por_coordenadas(
            page=page_mock,
            x=500,
            y=300,
            label_curto="",
            iframe_hint=None,
        )

        assert resultado == (True, False), (
            f"REGRESSAO: label_curto vazio deve retornar (True, False) sem verificacao, "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_label_none_retorna_true_false_sem_verificacao(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: label_curto None -> fail-open -> (True, False) sem verificacao.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        resultado = await _verificar_identidade_por_coordenadas(
            page=page_mock,
            x=500,
            y=300,
            label_curto=None,
            iframe_hint=None,
        )

        assert resultado == (True, False), (
            f"REGRESSAO: label_curto None deve retornar (True, False) sem verificacao, "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_iframe_cross_origin_retorna_true_true(self):
        """
        **Validates: Requirements 3.2 (bugfix.md)**

        Preservation: iframe cross-origin -> fail-open -> (True, True).

        Quando o iframe e cross-origin, nao e possivel inspecionar o DOM.
        O sistema deve aceitar sem verificacao e sinalizar cross-origin com True.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento_cross_origin(page, x, y):
            # Simula deteccao de cross-origin
            return None, x, y, True  # is_cross_origin=True

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento_cross_origin
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=300,
                label_curto="Confirmar",
                iframe_hint=None,
            )

        assert resultado == (True, True), (
            f"REGRESSAO: iframe cross-origin deve retornar (True, True), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_elemento_sem_texto_retorna_true_false(self):
        """
        **Validates: Requirements 3.3 (bugfix.md)**

        Preservation: elemento sem texto (innerText='') -> fail-open -> (True, False).

        Elementos como checkboxes, icones, ou elementos puramente visuais podem
        nao ter texto. O sistema deve aceitar sem verificacao.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento_sem_texto(page, x, y):
            return {"tagName": "INPUT", "innerText": ""}, x, y, False

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento_sem_texto
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=300,
                label_curto="Confirmar",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"REGRESSAO: elemento sem texto deve retornar (True, False), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_elemento_none_retorna_true_false(self):
        """
        **Validates: Requirements 3.3 (bugfix.md)**

        Preservation: elemento_info None (nao encontrado) -> fail-open -> (True, False).
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento_none(page, x, y):
            return None, x, y, False

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento_none
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=300,
                label_curto="Confirmar",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"REGRESSAO: elemento None deve retornar (True, False), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_excecao_durante_verificacao_retorna_true_false(self):
        """
        **Validates: Requirements 3.3 (bugfix.md)**

        Preservation: excecao durante verificacao -> fail-open -> (True, False).

        Se qualquer excecao ocorrer durante a verificacao de identidade,
        o sistema deve aceitar sem verificacao (fail-open) para nao bloquear
        a execucao em casos de instabilidade do DOM.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento_excecao(page, x, y):
            raise RuntimeError("DOM instavel — elemento nao acessivel")

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento_excecao
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=300,
                label_curto="Confirmar",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"REGRESSAO: excecao durante verificacao deve retornar (True, False) (fail-open), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_match_exato_aceito_antes_e_depois_do_fix(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: quando label_curto == texto_elemento (match exato),
        deve retornar (True, False) tanto antes quanto depois do fix.

        Este e o caso de sucesso legitimo — nao deve ser afetado pelo fix.
        """
        page_mock = AsyncMock()
        page_mock.frames = []

        async def mock_resolver_elemento_match_exato(page, x, y):
            return {"tagName": "BUTTON", "innerText": "Confirmar"}, x, y, False

        with patch.object(
            vision_engine, "_resolver_elemento_em_iframe", new=mock_resolver_elemento_match_exato
        ):
            resultado = await _verificar_identidade_por_coordenadas(
                page=page_mock,
                x=500,
                y=300,
                label_curto="Confirmar",
                iframe_hint=None,
            )

        assert resultado == (True, False), (
            f"REGRESSAO: match exato deve retornar (True, False), "
            f"mas obteve {resultado}."
        )


# ===========================================================================
# TASK 2.1 — Fail-open em _verificar_identidade_elemento()
# ===========================================================================

class TestFailOpenVerificarIdentidadeElemento:
    """
    Preservation: comportamentos de fail-open em _verificar_identidade_elemento()
    devem permanecer INALTERADOS antes e depois do fix.

    Validates: Requirements 3.1, 3.3 (bugfix.md)
    """

    @pytest.mark.asyncio
    async def test_label_vazio_retorna_true(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: label_curto vazio -> fail-open -> True.
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="Qualquer texto")

        resultado = await _verificar_identidade_elemento(locator_mock, "")

        assert resultado is True, (
            f"REGRESSAO: label_curto vazio deve retornar True (fail-open), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_excecao_ao_ler_texto_retorna_true(self):
        """
        **Validates: Requirements 3.3 (bugfix.md)**

        Preservation: excecao ao ler inner_text -> fail-open -> True.

        Elementos como checkboxes, icones SVG, ou elementos em iframes podem
        nao ter inner_text acessivel. O sistema deve aceitar sem verificacao.
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(side_effect=Exception("Elemento nao acessivel"))

        resultado = await _verificar_identidade_elemento(locator_mock, "Confirmar")

        assert resultado is True, (
            f"REGRESSAO: excecao ao ler texto deve retornar True (fail-open), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_match_exato_retorna_true(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: texto_elemento == label_curto (match exato) -> True.
        Este e o caso de sucesso legitimo — deve funcionar antes e depois do fix.
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="Salvar")

        resultado = await _verificar_identidade_elemento(locator_mock, "Salvar")

        assert resultado is True, (
            f"REGRESSAO: match exato deve retornar True, mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_match_exato_case_insensitive_retorna_true(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: match exato case-insensitive deve funcionar.
        label_curto='salvar', texto='SALVAR' -> True (normalizacao strip+lower).
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="SALVAR")

        resultado = await _verificar_identidade_elemento(locator_mock, "salvar")

        assert resultado is True, (
            f"REGRESSAO: match exato case-insensitive deve retornar True, "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_match_exato_com_espacos_retorna_true(self):
        """
        **Validates: Requirements 3.1 (bugfix.md)**

        Preservation: match exato com espacos extras deve funcionar apos strip.
        label_curto='Salvar', texto='  Salvar  ' -> True (strip aplicado).
        """
        locator_mock = AsyncMock()
        locator_mock.inner_text = AsyncMock(return_value="  Salvar  ")

        resultado = await _verificar_identidade_elemento(locator_mock, "Salvar")

        assert resultado is True, (
            f"REGRESSAO: match exato com espacos deve retornar True apos strip, "
            f"mas obteve {resultado}."
        )


# ===========================================================================
# TASK 2.2 — Candidatos semanticos de alta confianca no Sniper
# ===========================================================================

class TestCandidatosSemanticosAltaConfiancaSniper:
    """
    Preservation: candidatos semanticos de alta confianca no Sniper
    ([aria-label=], [name=], [data-testid=]) devem ser executados SEM
    verificacao adicional de identidade.

    Validates: Requirements 3.4 (bugfix.md)
    """

    @pytest.mark.asyncio
    async def test_aria_label_salvar_aceito_sem_verificacao_adicional(self):
        """
        **Validates: Requirements 3.4 (bugfix.md)**

        Preservation: seletor [aria-label='Salvar'] e semantico e especifico.
        O Sniper deve executar sem verificacao adicional de identidade.

        Cenario: label_curto='Salvar', seletor='[aria-label="Salvar"]'
        Resultado esperado: True (acerto direto, sem verificacao extra)
        """
        acao_tec = _make_acao_tec(
            seletor_hint="[aria-label='Salvar']",
            label_curto="Salvar",
        )
        page_mock = _make_page_mock_semantico(inner_text_do_elemento="Salvar")

        patches = _patches_isolamento_sniper_semantico("[aria-label='Salvar']")
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        assert resultado is True, (
            f"REGRESSAO: candidato [aria-label='Salvar'] deve ser aceito pelo Sniper "
            f"sem verificacao adicional, mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_name_e070emp_button_aceito_sem_verificacao_adicional(self):
        """
        **Validates: Requirements 3.4 (bugfix.md)**

        Preservation: seletor [name='e070emp'] button e semantico (atributo name).
        O Sniper deve executar sem verificacao adicional de identidade.

        Cenario real do log: Acao 1 (Lupa de empresa) — SUCESSO legitimo.
        label_curto pode ser generico (ex: 'Pesquisar') ou especifico.
        """
        acao_tec = _make_acao_tec(
            seletor_hint="[name='e070emp'] button",
            label_curto="Pesquisar",
        )
        page_mock = _make_page_mock_semantico(inner_text_do_elemento="Pesquisar")

        patches = _patches_isolamento_sniper_semantico("[name='e070emp'] button")
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        assert resultado is True, (
            f"REGRESSAO: candidato [name='e070emp'] button deve ser aceito pelo Sniper "
            f"sem verificacao adicional, mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_data_testid_btn_confirm_aceito_sem_verificacao_adicional(self):
        """
        **Validates: Requirements 3.4 (bugfix.md)**

        Preservation: seletor [data-testid='btn-confirm'] e semantico de teste.
        O Sniper deve executar sem verificacao adicional de identidade.
        """
        acao_tec = _make_acao_tec(
            seletor_hint="[data-testid='btn-confirm']",
            label_curto="Confirmar",
        )
        page_mock = _make_page_mock_semantico(inner_text_do_elemento="Confirmar")

        patches = _patches_isolamento_sniper_semantico("[data-testid='btn-confirm']")
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        assert resultado is True, (
            f"REGRESSAO: candidato [data-testid='btn-confirm'] deve ser aceito pelo Sniper "
            f"sem verificacao adicional, mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_aria_label_nao_posicional_nao_requer_verificacao(self):
        """
        **Validates: Requirements 3.4 (bugfix.md)**

        Preservation: seletores com [aria-label=] nao sao posicionais.
        _contem_indice_posicional deve retornar False para eles.
        """
        from vision_engine import _contem_indice_posicional

        assert _contem_indice_posicional("[aria-label='Salvar']") is False, (
            "REGRESSAO: [aria-label='Salvar'] nao deve ser detectado como posicional."
        )
        assert _contem_indice_posicional("[name='e070emp'] button") is False, (
            "REGRESSAO: [name='e070emp'] button nao deve ser detectado como posicional."
        )
        assert _contem_indice_posicional("[data-testid='btn-confirm']") is False, (
            "REGRESSAO: [data-testid='btn-confirm'] nao deve ser detectado como posicional."
        )


# ===========================================================================
# TASK 2.3 — Candidatos text= no Sniper (match exato ja implementado)
# ===========================================================================

class TestCandidatosTextSniper:
    """
    Preservation: candidatos text= no Sniper ja tem match exato implementado.
    Este comportamento deve permanecer INALTERADO antes e depois do fix.

    Validates: Requirements 3.5 (bugfix.md)
    """

    @pytest.mark.asyncio
    async def test_text_salvar_com_elemento_salvar_aceito(self):
        """
        **Validates: Requirements 3.5 (bugfix.md)**

        Preservation: text="Salvar" com elemento "Salvar" -> aceito (match exato).

        O Sniper ja tem match exato para candidatos text=.
        Este comportamento deve permanecer inalterado.
        """
        acao_tec = _make_acao_tec(
            seletor_hint="[aria-label='Salvar']",  # hint nao posicional
            label_curto="Salvar",
        )
        page_mock = _make_page_mock_semantico(inner_text_do_elemento="Salvar")

        # Mock do get_by_text para simular candidato text= com match exato
        locator_mock = AsyncMock()
        locator_mock.wait_for = AsyncMock(return_value=None)
        locator_mock.inner_text = AsyncMock(return_value="Salvar")
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

        page_mock.get_by_text = MagicMock(return_value=locator_container)

        patches = [
            patch.object(vision_engine, "_consultar_cache", return_value=None),
            patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
            patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
            patch.object(
                vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)
            ),
            patch.object(
                vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)
            ),
            patch.object(
                vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)
            ),
            # Faz _tentar_candidato falhar para todos exceto text= (que e tratado diretamente)
            patch.object(
                vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)
            ),
            patch.object(
                vision_engine, "_executar_acao", new=AsyncMock(return_value=None)
            ),
        ]
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        # O candidato text="Salvar" com elemento "Salvar" deve ser aceito
        assert resultado is True, (
            f"REGRESSAO: text='Salvar' com elemento 'Salvar' deve ser aceito (match exato), "
            f"mas obteve {resultado}."
        )

    @pytest.mark.asyncio
    async def test_text_salvar_com_elemento_salvar_e_fechar_rejeitado(self):
        """
        **Validates: Requirements 3.5 (bugfix.md)**

        Preservation: text="Salvar" com elemento "Salvar e Fechar" -> rejeitado.

        O match exato ja implementado para candidatos text= deve rejeitar
        elementos onde o texto nao corresponde exatamente ao label_curto.
        Este comportamento deve permanecer inalterado.
        """
        acao_tec = _make_acao_tec(
            seletor_hint="[aria-label='Salvar']",
            label_curto="Salvar",
        )
        page_mock = _make_page_mock_semantico(inner_text_do_elemento="Salvar e Fechar")

        # Mock do get_by_text para simular candidato text= com texto diferente
        locator_mock = AsyncMock()
        locator_mock.wait_for = AsyncMock(return_value=None)
        locator_mock.inner_text = AsyncMock(return_value="Salvar e Fechar")
        locator_mock.click = AsyncMock(return_value=None)
        locator_mock.is_visible = AsyncMock(return_value=True)

        locator_container = MagicMock()
        locator_container.first = locator_mock

        page_mock.get_by_text = MagicMock(return_value=locator_container)

        patches = [
            patch.object(vision_engine, "_consultar_cache", return_value=None),
            patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
            patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
            patch.object(
                vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)
            ),
            patch.object(
                vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)
            ),
            patch.object(
                vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)
            ),
            # Todos os candidatos CSS falham
            patch.object(
                vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)
            ),
        ]
        for p in patches:
            p.start()

        try:
            resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
        finally:
            for p in patches:
                p.stop()

        # O candidato text="Salvar" com elemento "Salvar e Fechar" deve ser rejeitado
        # O sistema deve escalar para Gemini (que tambem falha no mock) -> False
        assert resultado is False, (
            f"REGRESSAO: text='Salvar' com elemento 'Salvar e Fechar' deve ser rejeitado "
            f"(match exato), mas obteve {resultado}."
        )

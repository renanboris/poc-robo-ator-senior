"""
Exploratory Bug Condition Tests — Positional Selector Wrong Item Deletion
=========================================================================

**Validates: Requirements 1.1, 1.2, 1.3**

OBJETIVO: Demonstrar o bug ANTES do fix.

Bug Condition (C): `seletor_hint` contém índice posicional (ex: `item#file_1`,
`tr:nth-child(2)`, `li:nth-of-type(3)`) e a camada Hint é acionada sem verificar
se o elemento encontrado corresponde ao `label_curto` esperado.

RESULTADO ESPERADO: Estes testes FALHAM no código não corrigido.
A falha confirma que o bug existe — o robô clica no elemento errado sem aviso.

NÃO corrija o código nem os testes quando eles falharem.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path para importar vision_engine.py da raiz do projeto
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — construção de mocks e acao_tec
# ---------------------------------------------------------------------------

def _make_acao_tec(seletor_hint: str, label_curto: str, acao: str = "clique") -> dict:
    """Constrói um acao_tec mínimo para testar a camada Hint."""
    return {
        "acao": acao,
        "intencao_semantica": f"Selecionar item '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": seletor_hint,
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Lista de itens",
            "tipo_elemento": "checkbox",
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


def _make_page_mock(inner_text_do_elemento: str) -> MagicMock:
    """
    Cria um mock de `page` do Playwright onde:
    - `page.locator(seletor).first` retorna um locator visível
    - `inner_text()` do locator retorna `inner_text_do_elemento`
    - `click()` é rastreável via AsyncMock
    - Brain DB, Sniper e Vision são desativados para isolar a camada Hint
    """
    # Locator mock — simula elemento encontrado pelo seletor posicional
    locator_mock = AsyncMock()
    locator_mock.wait_for = AsyncMock(return_value=None)
    locator_mock.inner_text = AsyncMock(return_value=inner_text_do_elemento)
    locator_mock.click = AsyncMock(return_value=None)
    locator_mock.is_visible = AsyncMock(return_value=True)
    locator_mock.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_mock.bounding_box = AsyncMock(return_value={"x": 100, "y": 200, "width": 80, "height": 30})
    locator_mock.hover = AsyncMock(return_value=None)
    locator_mock.evaluate = AsyncMock(return_value=None)
    locator_mock.dblclick = AsyncMock(return_value=None)

    # Locator container — .first retorna o locator_mock
    locator_container = MagicMock()
    locator_container.first = locator_mock

    # page mock
    page_mock = AsyncMock()
    page_mock.locator = MagicMock(return_value=locator_container)
    page_mock.frames = []
    page_mock.main_frame = MagicMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.evaluate = AsyncMock(return_value=0)
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot")

    # frame_locator — simula falha para não entrar em iframes
    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    return page_mock


# ---------------------------------------------------------------------------
# Patches para isolar a camada Hint (desativar Brain, Sniper, Vision)
# ---------------------------------------------------------------------------

def _patches_isolamento():
    """
    Retorna lista de patches que desativam Brain, Sniper semântico e Gemini Vision,
    forçando o orquestrador a chegar na camada 3 (Hint).
    """
    return [
        # Brain: sem memória
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        # Brain: registros são no-ops
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        # Sniper: todos os candidatos falham → força camada Hint
        patch.object(vision_engine, "_tentar_candidato", new=_sniper_falha_hint_sucesso),
        # Gemini Vision: desativado
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        # Scroll: no-op
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
    ]


# Controle de chamadas para distinguir Sniper vs Hint
_hint_foi_chamado = False
_hint_seletor_usado = None


async def _sniper_falha_hint_sucesso(page, candidato, acao, valor, timeout_ms=3500):
    """
    Mock de `_tentar_candidato`:
    - Falha para todos os candidatos do Sniper (seletor != seletor_hint posicional)
    - Sucede quando o seletor é posicional (camada Hint) — simulando o bug
    """
    global _hint_foi_chamado, _hint_seletor_usado
    seletor = candidato.seletor or ""
    # Seletores posicionais chegam na camada Hint — simula sucesso (bug: clica sem verificar)
    if _e_posicional(seletor):
        _hint_foi_chamado = True
        _hint_seletor_usado = seletor
        return True  # Bug: executa sem verificar identidade
    return False  # Sniper falha


def _e_posicional(seletor: str) -> bool:
    """Detecta seletores posicionais — espelho da função que o fix irá adicionar."""
    import re
    padroes = [
        r"#\w*\d+",
        r":nth-child\(\d+\)",
        r":nth-of-type\(\d+\)",
        r"item#\w+\d+",
    ]
    return any(re.search(p, seletor) for p in padroes)


# ---------------------------------------------------------------------------
# Caso 1 — Caso real do bug: item#file_1 aponta para "Jurídico" em vez de "GED 102"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caso_real_file1_clica_juridico_em_vez_de_ged102():
    """
    **Validates: Requirements 1.1, 1.2**

    Reproduz o bug real: seletor_hint = "item#file_1 .ui-chkbox .ui-chkbox-box",
    label_curto = "GED 102", mas o elemento na posição file_1 tem texto "Jurídico".

    No código NÃO corrigido: a ação é executada em "Jurídico" sem verificação.
    Este teste FALHA — confirmando que o bug existe.

    Contraexemplo documentado:
      seletor_hint = "item#file_1 .ui-chkbox .ui-chkbox-box"
      label_curto  = "GED 102"
      texto real   = "Jurídico"
      resultado    = ação executada no item errado (bug confirmado)
    """
    global _hint_foi_chamado, _hint_seletor_usado
    _hint_foi_chamado = False
    _hint_seletor_usado = None

    acao_tec = _make_acao_tec(
        seletor_hint="item#file_1 .ui-chkbox .ui-chkbox-box",
        label_curto="GED 102",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Jurídico")

    patches = _patches_isolamento()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O código NÃO corrigido executa a ação sem verificar identidade.
    # O comportamento CORRETO seria: NÃO executar (retornar False ou escalar).
    # Este assert FALHA no código bugado — confirmando o bug.
    assert not resultado, (
        "BUG CONFIRMADO: encontrar_e_clicar executou a ação no elemento errado "
        "('Jurídico') sem verificar que label_curto='GED 102'. "
        "O seletor posicional 'item#file_1' apontou para o item errado."
    )


# ---------------------------------------------------------------------------
# Caso 2 — nth-child aponta para linha errada: "Abrir Período" em vez de "Fechar Período"
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_item_row3_clica_abrir_periodo_em_vez_de_fechar():
    """
    **Validates: Requirements 1.1, 1.2**

    Caso 2: seletor posicional com padrão item#rowN (não frágil, chega na camada Hint).
    seletor_hint = "item#row3 .btn-action",
    label_curto  = "Fechar Período",
    elemento na posição tem texto "Abrir Período".

    NOTA: seletores como "tr:nth-child(2) .btn-delete" são bloqueados antes da camada
    Hint pelo filtro _e_seletor_fragil (tag "tr" é frágil). O bug se manifesta apenas
    quando o seletor posicional não é classificado como frágil — como "item#row3 .btn-action".

    No código NÃO corrigido: a ação é executada em "Abrir Período" sem verificação.
    Este teste FALHA — confirmando que o bug existe.

    Contraexemplo documentado:
      seletor_hint = "item#row3 .btn-action"
      label_curto  = "Fechar Período"
      texto real   = "Abrir Período"
      resultado    = ação executada no item errado (bug confirmado)
    """
    global _hint_foi_chamado, _hint_seletor_usado
    _hint_foi_chamado = False
    _hint_seletor_usado = None

    acao_tec = _make_acao_tec(
        seletor_hint="item#row3 .btn-action",
        label_curto="Fechar Período",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Abrir Período")

    patches = _patches_isolamento()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO seria: NÃO executar (identidade não bate).
    # Este assert FALHA no código bugado — confirmando o bug.
    assert not resultado, (
        "BUG CONFIRMADO: encontrar_e_clicar executou a ação no elemento errado "
        "('Abrir Período') sem verificar que label_curto='Fechar Período'. "
        "O seletor posicional 'item#row3' apontou para o item errado."
    )


# ---------------------------------------------------------------------------
# Property-Based Test — Hypothesis gera variações de índices posicionais
# ---------------------------------------------------------------------------

# Estratégias para gerar seletores posicionais variados
_st_file_index = st.integers(min_value=1, max_value=99).map(lambda n: f"item#file_{n} .ui-chkbox .ui-chkbox-box")
_st_row_index = st.integers(min_value=1, max_value=99).map(lambda n: f"item#row{n} .action-btn")
_st_nth_child = st.integers(min_value=1, max_value=20).map(lambda n: f"tr:nth-child({n}) .btn-delete")
_st_nth_of_type = st.integers(min_value=1, max_value=20).map(lambda n: f"li:nth-of-type({n}) input[type='checkbox']")

_st_seletor_posicional = st.one_of(
    _st_file_index,
    _st_row_index,
    _st_nth_child,
    _st_nth_of_type,
)

# Labels esperados (item correto) — diferentes do texto que o mock retorna
_st_label_esperado = st.sampled_from([
    "GED 102", "Fechar Período", "Logística", "Jurídico", "Financeiro",
    "RH", "Compras", "Vendas", "Produção", "TI",
])

# Texto errado que o elemento na posição realmente tem
_st_texto_errado = st.sampled_from([
    "Jurídico", "Abrir Período", "Marketing", "Contabilidade", "Suprimentos",
    "Operações", "Qualidade", "Engenharia", "Projetos", "Compliance",
])


@pytest.mark.asyncio
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(
    seletor=_st_seletor_posicional,
    label_esperado=_st_label_esperado,
    texto_errado=_st_texto_errado,
)
async def test_property_seletor_posicional_clica_item_errado(
    seletor: str,
    label_esperado: str,
    texto_errado: str,
):
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Property: Para qualquer seletor posicional onde o elemento na posição
    tem texto diferente do label_curto esperado, o código NÃO corrigido
    executa a ação sem verificação de identidade.

    Este teste FALHA no código não corrigido — confirmando que o bug
    se manifesta para qualquer variação de índice posicional.

    Hypothesis gera automaticamente contraexemplos com diferentes padrões:
    - item#file_N .ui-chkbox .ui-chkbox-box
    - item#rowN .action-btn
    - tr:nth-child(N) .btn-delete
    - li:nth-of-type(N) input[type='checkbox']
    """
    # Garante que label_esperado != texto_errado para o teste ser válido
    if label_esperado == texto_errado:
        return  # pula caso degenerado

    global _hint_foi_chamado, _hint_seletor_usado
    _hint_foi_chamado = False
    _hint_seletor_usado = None

    acao_tec = _make_acao_tec(seletor_hint=seletor, label_curto=label_esperado)
    page_mock = _make_page_mock(inner_text_do_elemento=texto_errado)

    patches = _patches_isolamento()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO seria: NÃO executar (identidade não bate).
    # Este assert FALHA no código bugado — confirmando o bug para cada variação.
    assert not resultado, (
        f"BUG CONFIRMADO: seletor posicional '{seletor}' executou ação no elemento "
        f"com texto '{texto_errado}' sem verificar label_curto='{label_esperado}'. "
        f"Contraexemplo: seletor={seletor!r}, label={label_esperado!r}, texto_real={texto_errado!r}"
    )

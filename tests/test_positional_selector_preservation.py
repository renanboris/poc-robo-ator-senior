"""
Preservation Tests — Positional Selector Wrong Item Deletion
=============================================================

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

OBJETIVO: Confirmar o baseline a preservar ANTES do fix.

Property 2 (Preservation): Para todo `acao_tec` onde `NOT isBugCondition(acao_tec)`
(seletor_hint NÃO contém índice posicional), o comportamento de `encontrar_e_clicar`
é idêntico entre o código original e o código corrigido.

RESULTADO ESPERADO: Todos os testes PASSAM no código NÃO corrigido.
Isso confirma que o baseline está correto e que o fix não deve regredir esses casos.
"""

import asyncio
import os
import re
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path para importar vision_engine.py da raiz do projeto
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers — mesma estrutura do test_positional_selector_bug.py
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
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


def _make_page_mock(inner_text_do_elemento: str = "Qualquer Texto") -> MagicMock:
    """
    Cria um mock de `page` do Playwright onde:
    - `page.locator(seletor).first` retorna um locator visível
    - `inner_text()` do locator retorna `inner_text_do_elemento`
    - `click()` é rastreável via AsyncMock
    """
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


# ---------------------------------------------------------------------------
# Patches para isolar a camada Hint (desativar Brain, Sniper, Vision)
# Mesma estrutura do test_positional_selector_bug.py
# ---------------------------------------------------------------------------

def _patches_isolamento_nao_posicional():
    """
    Retorna lista de patches que desativam Brain, Sniper semântico e Gemini Vision,
    forçando o orquestrador a chegar na camada 3 (Hint).
    Para seletores NÃO-posicionais, a camada Hint deve executar normalmente.

    Inclui patch de _detectar_menu_contexto_ativo retornando None (sem menu ativo),
    para que o orquestrador não entre no fluxo de menu de contexto.
    """
    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_tentar_candidato", new=_sniper_falha_hint_sucesso_nao_posicional),
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
        patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)),
    ]


async def _sniper_falha_hint_sucesso_nao_posicional(page, candidato, acao, valor, timeout_ms=3500):
    """
    Mock de `_tentar_candidato` para seletores NÃO-posicionais:
    - Falha para todos os candidatos do Sniper (seletores gerados internamente)
    - Sucede quando o seletor é o hint original (camada Hint) — comportamento normal

    Para seletores não-posicionais, a camada Hint deve executar sem validação adicional.
    Para seletores posicionais com label_curto vazio, a camada Hint também executa
    normalmente (sem validação de identidade — requisito 3.3).
    """
    seletor = candidato.seletor or ""
    # Seletores hint chegam na camada 3 — simula sucesso normal
    # Inclui: seletores com atributos ([...]), text=, e seletores posicionais
    # (quando label_curto está vazio, o hint posicional também chega aqui)
    if _e_seletor_hint_direto(seletor) or _e_posicional(seletor):
        return True  # Comportamento normal: executa sem validação de identidade
    return False  # Sniper falha para forçar chegada na camada Hint


def _e_seletor_hint_direto(seletor: str) -> bool:
    """
    Detecta se o seletor é um hint direto (não gerado pelo Sniper).
    Seletores hint começam com [ (atributo), text= ou são IDs semânticos.
    """
    if not seletor:
        return False
    return (
        seletor.startswith("[")
        or seletor.startswith("text=")
        or seletor.startswith("'")
        or seletor.startswith('"')
    )


# ---------------------------------------------------------------------------
# Função espelho de isBugCondition — para verificar que seletores são NÃO-posicionais
# ---------------------------------------------------------------------------

def _e_posicional(seletor: str) -> bool:
    """Detecta seletores posicionais — espelho da função que o fix irá adicionar."""
    padroes = [
        r"#\w*\d+",
        r":nth-child\(\d+\)",
        r":nth-of-type\(\d+\)",
        r"item#\w+\d+",
    ]
    return any(re.search(p, seletor) for p in padroes)


# ---------------------------------------------------------------------------
# Caso 1 — aria-label semântico: deve passar pela camada Hint sem validação
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_aria_label_excluir_passa_sem_validacao():
    """
    **Validates: Requirements 3.1**

    Seletor não-posicional: [aria-label='Excluir']
    Deve passar pela camada Hint normalmente, sem validação de identidade.

    RESULTADO ESPERADO: Passa (baseline preservado).
    """
    assert not _e_posicional("[aria-label='Excluir']"), "Seletor não deve ser posicional"

    acao_tec = _make_acao_tec(
        seletor_hint="[aria-label='Excluir']",
        label_curto="Excluir",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Excluir")

    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado, (
        "REGRESSÃO: seletor não-posicional '[aria-label='Excluir']' deveria executar "
        "normalmente pela camada Hint, mas retornou False."
    )


# ---------------------------------------------------------------------------
# Caso 2 — ID semântico: [id='menu-item-Senior Flow']
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_id_semantico_menu_item_passa_sem_validacao():
    """
    **Validates: Requirements 3.1**

    Seletor não-posicional: [id='menu-item-Senior Flow']
    O ID contém texto semântico, não índice posicional.
    Deve passar pela camada Hint normalmente.

    RESULTADO ESPERADO: Passa (baseline preservado).
    """
    seletor = "[id='menu-item-Senior Flow']"
    assert not _e_posicional(seletor), "Seletor não deve ser posicional"

    acao_tec = _make_acao_tec(
        seletor_hint=seletor,
        label_curto="Senior Flow",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Senior Flow")

    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado, (
        "REGRESSÃO: seletor não-posicional '[id='menu-item-Senior Flow']' deveria "
        "executar normalmente, mas retornou False."
    )


# ---------------------------------------------------------------------------
# Caso 3 — data-testid com número no valor (não índice posicional)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_data_testid_com_numero_no_valor_nao_e_posicional():
    """
    **Validates: Requirements 3.1**

    Seletor: [data-testid='item-102']
    O número 102 faz parte do VALOR do atributo, não é índice posicional CSS.
    Não deve ser tratado como seletor posicional.

    RESULTADO ESPERADO: Passa (baseline preservado).
    """
    seletor = "[data-testid='item-102']"
    assert not _e_posicional(seletor), (
        f"Seletor '{seletor}' NÃO deve ser classificado como posicional — "
        "o número é parte do valor do atributo, não índice CSS."
    )

    acao_tec = _make_acao_tec(
        seletor_hint=seletor,
        label_curto="GED 102",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="GED 102")

    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado, (
        "REGRESSÃO: seletor '[data-testid='item-102']' deveria executar normalmente "
        "(número no valor do atributo, não índice posicional), mas retornou False."
    )


# ---------------------------------------------------------------------------
# Caso 4 — text= seletor: text='Confirmar'
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_text_confirmar_passa_sem_validacao():
    """
    **Validates: Requirements 3.1**

    Seletor não-posicional: text='Confirmar'
    Deve passar pela camada Hint normalmente.

    RESULTADO ESPERADO: Passa (baseline preservado).
    """
    seletor = "text='Confirmar'"
    assert not _e_posicional(seletor), "Seletor text= não deve ser posicional"

    acao_tec = _make_acao_tec(
        seletor_hint=seletor,
        label_curto="Confirmar",
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Confirmar")

    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado, (
        "REGRESSÃO: seletor 'text='Confirmar'' deveria executar normalmente, "
        "mas retornou False."
    )


# ---------------------------------------------------------------------------
# Caso 5 — label_curto vazio com seletor posicional: sem validação de identidade
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_label_curto_vazio_com_seletor_posicional_escala_normalmente():
    """
    **Validates: Requirements 3.3**

    Quando label_curto está vazio, mesmo com seletor posicional,
    o sistema NÃO deve tentar validação de identidade — deve continuar
    o comportamento atual (escalar para Sniper/Vision sem validar).

    Este teste verifica que o comportamento atual é preservado para label_curto="".

    RESULTADO ESPERADO: Passa (baseline preservado — sem validação quando label vazio).
    """
    seletor = "item#file_1 .ui-chkbox .ui-chkbox-box"
    assert _e_posicional(seletor), "Seletor deve ser posicional para este teste"

    acao_tec = _make_acao_tec(
        seletor_hint=seletor,
        label_curto="",  # label vazio — sem validação de identidade
    )
    page_mock = _make_page_mock(inner_text_do_elemento="Qualquer Texto")

    # Para label_curto vazio, o comportamento atual é: camada Hint executa normalmente
    # (sem validação). O fix NÃO deve alterar esse comportamento.
    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Com label_curto vazio, o comportamento atual é executar normalmente via Hint.
    # O fix deve preservar isso (requisito 3.3).
    assert resultado, (
        "REGRESSÃO: com label_curto='', o sistema deveria executar normalmente "
        "via camada Hint (sem validação de identidade), mas retornou False."
    )


# ---------------------------------------------------------------------------
# Property-Based Test — Hypothesis gera seletores semânticos aleatórios
# ---------------------------------------------------------------------------

# Estratégias para gerar seletores NÃO-posicionais
_st_aria_label = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" -_"),
    min_size=3, max_size=30,
).map(lambda s: f"[aria-label='{s}']")

_st_data_testid = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll"), whitelist_characters="-_"),
    min_size=3, max_size=20,
).map(lambda s: f"[data-testid='{s}']")

_st_id_semantico = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll"), whitelist_characters="-_"),
    min_size=3, max_size=20,
).map(lambda s: f"[id='{s}']")

_st_text_selector = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
    min_size=3, max_size=25,
).map(lambda s: f"text='{s}'")

_st_seletor_semantico = st.one_of(
    _st_aria_label,
    _st_data_testid,
    _st_id_semantico,
    _st_text_selector,
)


@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(seletor=_st_seletor_semantico)
def test_property_seletores_semanticos_nao_sao_posicionais(seletor: str):
    """
    **Validates: Requirements 3.1, 3.2**

    Property: Para qualquer seletor semântico gerado (aria-label, data-testid,
    id semântico, text=), a função `_e_posicional` (isBugCondition) deve retornar
    False.

    Isso garante que o fix não irá tratar seletores semânticos como posicionais,
    preservando o comportamento original para todos esses casos.

    Hypothesis gera automaticamente variações de seletores semânticos.
    """
    assert not _e_posicional(seletor), (
        f"REGRESSÃO: seletor semântico '{seletor}' foi classificado incorretamente "
        f"como posicional. O fix não deve afetar seletores semânticos."
    )


# ---------------------------------------------------------------------------
# Property-Based Test — Seletores com números em valores de atributos
# ---------------------------------------------------------------------------

_st_testid_com_numero = st.integers(min_value=1, max_value=9999).map(
    lambda n: f"[data-testid='item-{n}']"
)

_st_id_com_numero_no_valor = st.integers(min_value=1, max_value=9999).map(
    lambda n: f"[id='row-id-{n}']"
)

_st_seletor_com_numero_em_valor = st.one_of(
    _st_testid_com_numero,
    _st_id_com_numero_no_valor,
)


@settings(
    max_examples=30,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=5000,
)
@given(seletor=_st_seletor_com_numero_em_valor)
def test_property_numero_em_valor_de_atributo_nao_e_posicional(seletor: str):
    """
    **Validates: Requirements 3.1**

    Property: Seletores onde o número aparece como VALOR de um atributo
    (ex: [data-testid='item-102'], [id='row-id-5']) NÃO devem ser classificados
    como posicionais.

    O número faz parte do identificador semântico, não é um índice CSS posicional.
    Hypothesis gera variações com diferentes números para confirmar isso.
    """
    assert not _e_posicional(seletor), (
        f"REGRESSÃO: seletor '{seletor}' foi classificado como posicional, "
        f"mas o número é parte do valor do atributo, não índice CSS. "
        f"O fix não deve afetar esses seletores."
    )


# ---------------------------------------------------------------------------
# Property-Based Test — Comportamento idêntico para seletores não-posicionais
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=10000,
)
@given(
    seletor=_st_seletor_semantico,
    label=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters=" "),
        min_size=2, max_size=20,
    ),
)
async def test_property_comportamento_identico_para_nao_posicionais(
    seletor: str,
    label: str,
):
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

    Property: Para todo acao_tec onde NOT isBugCondition(acao_tec)
    (seletor_hint não contém índice posicional), o comportamento de
    `encontrar_e_clicar` deve ser idêntico ao original.

    Este teste verifica que seletores semânticos passam pela camada Hint
    normalmente, sem validação adicional de identidade.

    RESULTADO ESPERADO: Passa (confirma baseline a preservar).
    """
    # Garante que o seletor gerado não é posicional
    assume(not _e_posicional(seletor))

    acao_tec = _make_acao_tec(seletor_hint=seletor, label_curto=label.strip() or "Item")
    page_mock = _make_page_mock(inner_text_do_elemento=label.strip() or "Item")

    patches = _patches_isolamento_nao_posicional()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado, (
        f"REGRESSÃO: seletor não-posicional '{seletor}' com label='{label}' "
        f"deveria executar normalmente pela camada Hint, mas retornou False. "
        f"O fix não deve alterar o comportamento para seletores semânticos."
    )

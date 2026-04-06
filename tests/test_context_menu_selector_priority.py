"""
Exploratory Bug Condition Tests — Context Menu Selector Priority
================================================================

**Validates: Requirements 1.1, 1.2, 1.3**

OBJETIVO: Demonstrar o bug ANTES do fix.

Bug Condition (C): Um menu de contexto (`.p-contextmenu`) está visível como overlay
na tela E o label do elemento alvo também existe na tela principal subjacente E a
busca não está restrita ao escopo do menu.

O `encontrar_e_clicar` em `vision_engine.py` ignora o overlay e clica no elemento
da tela principal em vez do item do menu de contexto.

Root causes confirmados:
  1. Brain (camada 0): sem consciência de overlay — usa seletor memorizado mesmo
     quando menu de contexto está ativo e o seletor aponta para a tela principal.
  2. Sniper (camada 2): sem escopo — busca em todo o DOM, encontra elemento da
     tela principal antes do item do menu.

RESULTADO ESPERADO: Estes testes FALHAM no código não corrigido.
A falha confirma que o bug existe.

NÃO corrija o código nem os testes quando eles falharem.
"""

import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path para importar vision_engine.py da raiz do projeto
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — construção de acao_tec e mocks
# ---------------------------------------------------------------------------

def _make_acao_tec(label_curto: str, acao: str = "clique", tipo_elemento: str = "menu_item") -> dict:
    """Constrói um acao_tec mínimo para testar o cenário de menu de contexto."""
    return {
        "acao": acao,
        "intencao_semantica": f"Clicar em '{label_curto}' no menu de contexto",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Menu de contexto ativo",
            "tipo_elemento": tipo_elemento,
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


def _make_page_mock_with_context_menu(label_curto: str) -> tuple[MagicMock, dict]:
    """
    Cria um mock de `page` simulando o estado de bug:
    - Elemento com `label_curto` existe na tela principal (toolbar)
    - `.p-contextmenu` está visível com item de mesmo texto

    Retorna (page_mock, estado) onde estado rastreia qual elemento foi clicado.
    """
    estado = {
        "clicou_tela_principal": False,
        "clicou_dentro_menu": False,
        "elemento_clicado": None,
    }

    # --- Locator do elemento da TELA PRINCIPAL (toolbar) ---
    locator_tela_principal = AsyncMock()
    locator_tela_principal.wait_for = AsyncMock(return_value=None)
    locator_tela_principal.inner_text = AsyncMock(return_value=label_curto)
    locator_tela_principal.is_visible = AsyncMock(return_value=True)
    locator_tela_principal.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_tela_principal.bounding_box = AsyncMock(
        return_value={"x": 50, "y": 50, "width": 120, "height": 32}
    )
    locator_tela_principal.hover = AsyncMock(return_value=None)
    locator_tela_principal.evaluate = AsyncMock(return_value=None)

    async def _click_tela_principal(**kwargs):
        estado["clicou_tela_principal"] = True
        estado["elemento_clicado"] = "tela_principal"

    locator_tela_principal.click = AsyncMock(side_effect=_click_tela_principal)

    # --- Locator do item DENTRO DO MENU DE CONTEXTO ---
    locator_menu_item = AsyncMock()
    locator_menu_item.wait_for = AsyncMock(return_value=None)
    locator_menu_item.inner_text = AsyncMock(return_value=label_curto)
    locator_menu_item.is_visible = AsyncMock(return_value=True)
    locator_menu_item.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_menu_item.bounding_box = AsyncMock(
        return_value={"x": 200, "y": 300, "width": 180, "height": 36}
    )
    locator_menu_item.hover = AsyncMock(return_value=None)
    locator_menu_item.evaluate = AsyncMock(return_value=None)

    async def _click_menu_item(**kwargs):
        estado["clicou_dentro_menu"] = True
        estado["elemento_clicado"] = "menu_item"

    locator_menu_item.click = AsyncMock(side_effect=_click_menu_item)

    # _buscar_em_escopo_menu chama get_by_role/get_by_text/locator no menu_locator
    # (que é locator_menu_item retornado por _detectar_menu_contexto_ativo).
    # Essas chamadas devem retornar locator_menu_item para que wait_for e click funcionem.
    locator_menu_item.get_by_role = MagicMock(return_value=locator_menu_item)
    locator_menu_item.get_by_text = MagicMock(return_value=locator_menu_item)
    locator_menu_item.locator = MagicMock(return_value=locator_menu_item)
    locator_menu_item.last = locator_menu_item

    # --- Container do locator (wraps .first) ---
    # page.locator(seletor).first retorna o locator correto por seletor
    def _make_locator_container(locator_mock):
        container = MagicMock()
        container.first = locator_mock
        container.count = AsyncMock(return_value=1)
        return container

    tela_principal_container = _make_locator_container(locator_tela_principal)
    menu_item_container = _make_locator_container(locator_menu_item)

    # page.locator() — retorna tela_principal por padrão (simula Sniper sem escopo)
    def _page_locator(seletor, **kwargs):
        # Seletores de menu de contexto retornam container do menu
        if ".p-contextmenu" in seletor or 'role="menu"' in seletor:
            return menu_item_container
        # Qualquer outro seletor retorna elemento da tela principal
        return tela_principal_container

    # --- page mock ---
    page_mock = AsyncMock()
    page_mock.locator = MagicMock(side_effect=_page_locator)
    page_mock.frames = []
    page_mock.main_frame = MagicMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.evaluate = AsyncMock(return_value=0)
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot")

    # get_by_text / get_by_role — retornam elemento da tela principal (sem escopo)
    page_mock.get_by_text = MagicMock(return_value=tela_principal_container)
    page_mock.get_by_role = MagicMock(return_value=tela_principal_container)
    page_mock.get_by_label = MagicMock(return_value=tela_principal_container)

    # frame_locator — falha para não entrar em iframes
    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    return page_mock, estado


def _patches_base():
    """Patches comuns: desativa Brain, Gemini Vision e scroll."""
    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
    ]


# ===========================================================================
# Teste 1.1 — Estrutural: `encontrar_e_clicar` não tem detecção de menu de contexto
# ===========================================================================

def test_estrutural_sem_funcao_detectar_menu_contexto_ativo():
    """
    **Validates: Requirements 1.1**

    Verifica que `vision_engine.py` NÃO contém a função `_detectar_menu_contexto_ativo`.

    Esta função é a que o fix irá adicionar. Sua ausência confirma que o código
    ainda não foi corrigido.

    RESULTADO ESPERADO: FALHA após o fix ser aplicado (a função existirá).
    No código não corrigido: PASSA (a função não existe).

    NOTA: Este teste é um marcador estrutural — ele PASSA no código bugado
    e FALHA após o fix. Isso é intencional para confirmar que o fix foi aplicado.
    Para confirmar o BUG, veja os testes 1.3 e 1.4.
    """
    assert not hasattr(vision_engine, "_detectar_menu_contexto_ativo"), (
        "FIX DETECTADO: `_detectar_menu_contexto_ativo` foi adicionada ao vision_engine. "
        "O fix foi aplicado — este teste estrutural agora falha como esperado."
    )


# ===========================================================================
# Teste 1.2 — Estrutural: Brain não tem consciência de overlay
# ===========================================================================

def test_estrutural_brain_sem_consciencia_de_overlay():
    """
    **Validates: Requirements 1.2**

    Verifica que o código-fonte de `encontrar_e_clicar` em `vision_engine.py`
    NÃO contém verificação de menu de contexto antes de usar o resultado do Brain.

    A ausência desta verificação é a root cause 2 do bug: o Brain usa o seletor
    memorizado sem checar se um menu de contexto está ativo.

    RESULTADO ESPERADO: FALHA após o fix ser aplicado.
    No código não corrigido: PASSA (a verificação não existe).
    """
    import inspect
    source = inspect.getsource(vision_engine.encontrar_e_clicar)

    # O fix irá adicionar uma chamada a `_detectar_menu_contexto_ativo` antes
    # ou dentro da lógica do Brain. No código bugado, isso não existe.
    assert "_detectar_menu_contexto_ativo" not in source, (
        "FIX DETECTADO: `encontrar_e_clicar` agora contém verificação de menu de contexto. "
        "O Brain tem consciência de overlay — fix aplicado."
    )


# ===========================================================================
# Teste 1.3 — Comportamental: orquestrador sem camada de menu de contexto
# ===========================================================================

@pytest.mark.asyncio
async def test_comportamental_clica_tela_principal_em_vez_de_menu():
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Simula o estado de bug:
    - DOM: botão "Nova Pasta" na tela principal (toolbar) + `.p-contextmenu` visível
      com item "Nova Pasta" (role=menuitem)
    - Brain: sem memória (desativado)
    - Sniper: sem escopo de menu — encontra elemento da tela principal primeiro

    Comportamento ESPERADO (correto/fixado):
      Quando `context_menu_active=True`, o clique deve ocorrer DENTRO do menu,
      não na tela principal.

    Comportamento ATUAL (bugado):
      O Sniper encontra "Nova Pasta" na tela principal e clica lá.
      `estado["clicou_tela_principal"]` = True
      `estado["clicou_dentro_menu"]` = False

    Este teste FALHA no código não corrigido — confirmando o bug.

    Contraexemplo documentado:
      label_curto = "Nova Pasta"
      context_menu_active = True
      elemento_clicado = "tela_principal"  (deveria ser "menu_item")
    """
    label_curto = "Nova Pasta"
    page_mock, estado = _make_page_mock_with_context_menu(label_curto)

    patches = _patches_base()
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec(label_curto=label_curto)
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO: quando menu de contexto está ativo,
    # o clique deve ocorrer DENTRO do menu.
    # No código bugado: clica na tela principal → este assert FALHA.
    assert estado["clicou_dentro_menu"], (
        f"BUG CONFIRMADO: encontrar_e_clicar clicou em '{estado['elemento_clicado']}' "
        f"em vez de clicar dentro do .p-contextmenu. "
        f"label_curto='{label_curto}', context_menu_active=True. "
        f"O Sniper encontrou o elemento na tela principal sem verificar o overlay."
    )
    assert not estado["clicou_tela_principal"], (
        f"BUG CONFIRMADO: clique ocorreu na tela principal (toolbar) "
        f"em vez do item do menu de contexto."
    )


@pytest.mark.asyncio
async def test_comportamental_brain_usa_seletor_tela_principal_com_menu_ativo():
    """
    **Validates: Requirements 1.2**

    Simula o estado de bug com Brain pré-populado:
    - Brain tem memória: seletor `text="Renomear"` apontando para tela principal
    - Menu de contexto está ativo com item "Renomear"

    Comportamento ESPERADO (correto/fixado):
      Brain deve verificar se o seletor memorizado está dentro do menu ativo.
      Como não está, deve pular o Brain e deixar a camada de menu tratar.

    Comportamento ATUAL (bugado):
      Brain usa o seletor memorizado diretamente → clica na tela principal.

    Este teste FALHA no código não corrigido — confirmando root cause 2.

    Contraexemplo documentado:
      label_curto = "Renomear"
      brain_seletor = 'text="Renomear"' (aponta para tela principal)
      context_menu_active = True
      resultado = clique na tela principal (deveria ser no menu)
    """
    label_curto = "Renomear"
    page_mock, estado = _make_page_mock_with_context_menu(label_curto)

    # Brain com memória de seletor da tela principal
    from vision_engine import EntradaCache
    cache_com_seletor = EntradaCache(
        seletor='text="Renomear"',
        coords=None,
        iframe_src=None,
        hits=5,
        falhas_consecutivas=0,
    )

    patches = [
        # Brain retorna seletor da tela principal
        patch.object(vision_engine, "_consultar_cache", return_value=cache_com_seletor),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
    ]
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec(label_curto=label_curto)
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO: Brain deve ser ignorado quando menu está ativo
    # e o seletor não aponta para dentro do menu.
    # No código bugado: Brain usa seletor memorizado → clica na tela principal.
    assert estado["clicou_dentro_menu"], (
        f"BUG CONFIRMADO (root cause 2 — Brain sem consciência de overlay): "
        f"Brain usou seletor memorizado 'text=\"Renomear\"' apontando para a tela principal "
        f"sem verificar que um menu de contexto está ativo. "
        f"elemento_clicado='{estado['elemento_clicado']}' (deveria ser 'menu_item'). "
        f"Contraexemplo: label='{label_curto}', brain_seletor='text=\"Renomear\"', "
        f"context_menu_active=True"
    )


# ===========================================================================
# Teste 1.4 — Hypothesis property: para qualquer label_curto com menu ativo,
#             o clique deve ocorrer dentro do menu
# ===========================================================================

# Estratégia: labels típicos de menus de contexto no GED
_st_label_menu = st.sampled_from([
    "Nova Pasta",
    "Renomear",
    "Excluir",
    "Mover para",
    "Copiar para",
    "Compartilhar",
    "Propriedades",
    "Abrir",
    "Download",
    "Visualizar",
])


@pytest.mark.asyncio
@settings(
    max_examples=10,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=10000,
)
@given(label_curto=_st_label_menu)
async def test_property_menu_ativo_clique_deve_ser_dentro_do_menu(label_curto: str):
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Property: Para qualquer `label_curto`, quando um menu de contexto está ativo
    como overlay, `encontrar_e_clicar` DEVE clicar no item dentro do menu,
    não no elemento da tela principal subjacente.

    Pseudocódigo da propriedade:
      FOR ALL label_curto:
        IF context_menu_active = True AND element_exists_in_main_page(label_curto):
          ASSERT clicked_inside_menu = True

    No código NÃO corrigido: não existe verificação de menu de contexto →
    o Sniper encontra o elemento na tela principal → `clicked_inside_menu = False`.

    Este teste FALHA no código não corrigido — confirmando o bug para qualquer
    variação de label_curto.

    Hypothesis documenta o contraexemplo mínimo encontrado.
    """
    page_mock, estado = _make_page_mock_with_context_menu(label_curto)

    patches = _patches_base()
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec(label_curto=label_curto)
        await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Property: quando menu de contexto está ativo, o clique deve ser dentro do menu.
    # No código bugado: clica na tela principal → FALHA aqui.
    assert estado["clicou_dentro_menu"], (
        f"BUG CONFIRMADO (property): label_curto='{label_curto}', "
        f"context_menu_active=True → clique ocorreu em '{estado['elemento_clicado']}' "
        f"em vez de dentro do .p-contextmenu. "
        f"O orquestrador não tem camada de detecção de menu de contexto ativo."
    )


# ===========================================================================
# PRESERVATION TESTS (Task 2) — Property 2: Comportamento sem Menu de Contexto
# ===========================================================================
"""
**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

OBJETIVO: Confirmar o comportamento BASELINE quando NENHUM menu de contexto está ativo.

Estes testes DEVEM PASSAR no código não corrigido — eles documentam o que
deve ser preservado após o fix.

Eles também DEVEM PASSAR após o fix (confirma ausência de regressões).
"""


# ---------------------------------------------------------------------------
# Helpers específicos para cenários de preservação (sem menu ativo)
# ---------------------------------------------------------------------------

def _make_page_mock_sem_menu(label_curto: str, acao: str = "clique") -> tuple[MagicMock, dict]:
    """
    Cria um mock de `page` simulando o estado NORMAL (sem menu de contexto ativo):
    - Elemento com `label_curto` existe na tela principal
    - Nenhum `.p-contextmenu` visível

    Retorna (page_mock, estado) onde estado rastreia qual elemento foi clicado.
    """
    estado = {
        "clicou_tela_principal": False,
        "elemento_clicado": None,
        "click_count": 0,
    }

    # --- Locator do elemento da TELA PRINCIPAL ---
    locator_tela_principal = AsyncMock()
    locator_tela_principal.wait_for = AsyncMock(return_value=None)
    locator_tela_principal.inner_text = AsyncMock(return_value=label_curto)
    locator_tela_principal.is_visible = AsyncMock(return_value=True)
    locator_tela_principal.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_tela_principal.bounding_box = AsyncMock(
        return_value={"x": 50, "y": 50, "width": 120, "height": 32}
    )
    locator_tela_principal.hover = AsyncMock(return_value=None)
    locator_tela_principal.evaluate = AsyncMock(return_value=None)

    async def _click_tela_principal(**kwargs):
        estado["clicou_tela_principal"] = True
        estado["elemento_clicado"] = "tela_principal"
        estado["click_count"] += 1

    if acao == "clique_direito":
        locator_tela_principal.click = AsyncMock(side_effect=_click_tela_principal)
    else:
        locator_tela_principal.click = AsyncMock(side_effect=_click_tela_principal)
        locator_tela_principal.dblclick = AsyncMock(side_effect=_click_tela_principal)

    # --- Container (wraps .first) ---
    container_tela_principal = MagicMock()
    container_tela_principal.first = locator_tela_principal
    container_tela_principal.count = AsyncMock(return_value=1)

    # --- page mock sem menu ativo ---
    page_mock = AsyncMock()

    def _page_locator(seletor, **kwargs):
        # Seletores de menu de contexto: retornam locator NÃO visível (sem menu ativo)
        # Cobre todos os seletores usados por _detectar_menu_contexto_ativo:
        #   ".p-contextmenu", "[role='menu']", ".context-menu",
        #   "ul[class*='contextmenu']", ".p-menu-list"
        _menu_keywords = [
            ".p-contextmenu",
            "role='menu'",
            'role="menu"',
            ".context-menu",
            ".p-menu-list",
            "contextmenu",
        ]
        if any(s in seletor for s in _menu_keywords):
            locator_menu_inativo = AsyncMock()
            locator_menu_inativo.is_visible = AsyncMock(return_value=False)
            locator_menu_inativo.wait_for = AsyncMock(side_effect=Exception("menu not visible"))
            container_inativo = MagicMock()
            container_inativo.first = locator_menu_inativo
            return container_inativo
        # Qualquer outro seletor retorna elemento da tela principal
        return container_tela_principal

    page_mock.locator = MagicMock(side_effect=_page_locator)
    page_mock.frames = []
    page_mock.main_frame = MagicMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.evaluate = AsyncMock(return_value=0)
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot")
    page_mock.keyboard = AsyncMock()
    page_mock.mouse = AsyncMock()

    page_mock.get_by_text = MagicMock(return_value=container_tela_principal)
    page_mock.get_by_role = MagicMock(return_value=container_tela_principal)
    page_mock.get_by_label = MagicMock(return_value=container_tela_principal)

    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    return page_mock, estado


def _make_acao_tec_simples(
    label_curto: str,
    acao: str = "clique",
    tipo_elemento: str = "button",
    iframe_hint: str = None,
) -> dict:
    """Constrói um acao_tec para cenários sem menu de contexto ativo."""
    return {
        "acao": acao,
        "intencao_semantica": f"Clicar em '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": iframe_hint,
            "descricao_visual": label_curto,
            "contexto_tela": "Tela principal",
            "tipo_elemento": tipo_elemento,
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


# ===========================================================================
# Teste 2.1 — `encontrar_e_clicar` sem menu ativo funciona normalmente
# ===========================================================================

@pytest.mark.asyncio
async def test_2_1_clique_simples_sem_menu_ativo_funciona():
    """
    **Validates: Requirements 3.1**

    Preservation Test 2.1: Clique simples em botão da tela principal sem menu ativo.

    Simula:
    - DOM com um botão "Salvar" na tela principal
    - Nenhum `.p-contextmenu` visível
    - Brain: desativado (sem memória)

    ESPERADO: `encontrar_e_clicar` localiza e clica no elemento da tela principal.
    DEVE PASSAR no código não corrigido (confirma baseline).
    DEVE PASSAR após o fix (confirma ausência de regressão).
    """
    label_curto = "Salvar"
    page_mock, estado = _make_page_mock_sem_menu(label_curto)

    patches = _patches_base()
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec_simples(label_curto=label_curto)
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Preservation: sem menu ativo, o clique deve ocorrer na tela principal
    assert resultado is True, (
        f"REGRESSÃO: encontrar_e_clicar retornou False para clique simples sem menu ativo. "
        f"label_curto='{label_curto}', context_menu_active=False."
    )
    assert estado["clicou_tela_principal"], (
        f"REGRESSÃO: encontrar_e_clicar não clicou no elemento da tela principal. "
        f"label_curto='{label_curto}', context_menu_active=False. "
        f"elemento_clicado='{estado['elemento_clicado']}'"
    )


# ===========================================================================
# Teste 2.2 — Brain com memória válida é acionado quando sem menu ativo
# ===========================================================================

@pytest.mark.asyncio
async def test_2_2_brain_com_memoria_valida_acionado_sem_menu_ativo():
    """
    **Validates: Requirements 3.3**

    Preservation Test 2.2: Brain com memória válida é a primeira estratégia
    quando não há menu de contexto ativo.

    Simula:
    - Brain tem memória: seletor `text="Salvar"` apontando para tela principal
    - Nenhum menu de contexto ativo

    ESPERADO: Brain é acionado como primeira estratégia e o clique ocorre.
    DEVE PASSAR no código não corrigido (confirma baseline do Brain).
    DEVE PASSAR após o fix (Brain preservado quando sem menu ativo).
    """
    label_curto = "Salvar"
    page_mock, estado = _make_page_mock_sem_menu(label_curto)

    from vision_engine import EntradaCache
    cache_valido = EntradaCache(
        seletor='text="Salvar"',
        coords=None,
        iframe_src=None,
        hits=3,
        falhas_consecutivas=0,
    )

    brain_foi_consultado = {"value": False}
    brain_seletor_usado = {"value": None}

    def _mock_consultar_cache(intencao):
        brain_foi_consultado["value"] = True
        return cache_valido

    patches = [
        patch.object(vision_engine, "_consultar_cache", side_effect=_mock_consultar_cache),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
    ]
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec_simples(label_curto=label_curto)
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Preservation: Brain deve ser consultado como primeira estratégia
    assert brain_foi_consultado["value"], (
        "REGRESSÃO: Brain não foi consultado. O fix pode ter removido a camada 0 do orquestrador."
    )
    # Preservation: o clique deve ocorrer (Brain ou Sniper encontra o elemento)
    assert resultado is True, (
        f"REGRESSÃO: encontrar_e_clicar retornou False mesmo com Brain tendo memória válida. "
        f"label_curto='{label_curto}', context_menu_active=False."
    )


# ===========================================================================
# Teste 2.3 — `clique_direito` não é afetado pelo fix
# ===========================================================================

@pytest.mark.asyncio
async def test_2_3_clique_direito_nao_afetado_pelo_fix():
    """
    **Validates: Requirements 3.2**

    Preservation Test 2.3: A ação `clique_direito` é executada normalmente.

    Verifica que:
    1. `encontrar_e_clicar` aceita `acao="clique_direito"` sem erros
    2. O clique direito é executado no elemento encontrado
    3. O fix NÃO altera o comportamento de `clique_direito`

    DEVE PASSAR no código não corrigido (confirma baseline).
    DEVE PASSAR após o fix (confirma que clique_direito não foi alterado).
    """
    label_curto = "arquivo.pdf"
    page_mock, estado = _make_page_mock_sem_menu(label_curto, acao="clique_direito")

    patches = _patches_base()
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec_simples(label_curto=label_curto, acao="clique_direito")
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Preservation: clique_direito deve funcionar normalmente
    assert resultado is True, (
        f"REGRESSÃO: encontrar_e_clicar retornou False para acao='clique_direito'. "
        f"label_curto='{label_curto}'. O fix pode ter quebrado o fluxo de clique_direito."
    )
    assert estado["clicou_tela_principal"], (
        f"REGRESSÃO: clique_direito não executou o clique no elemento. "
        f"label_curto='{label_curto}', elemento_clicado='{estado['elemento_clicado']}'"
    )


# ===========================================================================
# Teste 2.4 — Hypothesis property: sem menu ativo, comportamento idêntico ao original
# ===========================================================================

# Estratégia: labels_curtos variados para cobrir diferentes tipos de elementos
_st_label_curto = st.one_of(
    # Labels típicos de botões e links
    st.sampled_from([
        "Salvar",
        "Cancelar",
        "Confirmar",
        "Fechar",
        "Novo",
        "Editar",
        "Pesquisar",
        "Filtrar",
        "Exportar",
        "Importar",
    ]),
    # Labels com caracteres especiais (acentos, espaços)
    st.sampled_from([
        "Próximo",
        "Anterior",
        "Adicionar Item",
        "Nova Pasta",
        "Mover para",
    ]),
)

_st_acao_sem_menu = st.sampled_from([
    "clique",
    "clique_direito",
    "duplo_clique",
])

_st_tipo_elemento = st.sampled_from([
    "button",
    "link",
    "tab",
    "checkbox",
])


@pytest.mark.asyncio
@settings(
    max_examples=15,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=15000,
)
@given(
    label_curto=_st_label_curto,
    acao=_st_acao_sem_menu,
    tipo_elemento=_st_tipo_elemento,
)
async def test_2_4_property_sem_menu_ativo_comportamento_identico_ao_original(
    label_curto: str,
    acao: str,
    tipo_elemento: str,
):
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

    Property 2: Para qualquer `AcaoTecnica` onde `isBugCondition` retorna `False`
    (menu de contexto NÃO está ativo), `encontrar_e_clicar` deve:
    1. Retornar True (encontrar e executar o elemento)
    2. Clicar no elemento da tela principal (não em nenhum menu)
    3. Não ser afetado pela presença ou ausência da nova camada de detecção de menu

    Pseudocódigo da propriedade:
      FOR ALL (label_curto, acao, tipo_elemento):
        IF context_menu_active = False:
          ASSERT encontrar_e_clicar(page, acao_tec) = True
          ASSERT clicou_tela_principal = True

    DEVE PASSAR no código não corrigido (confirma baseline).
    DEVE PASSAR após o fix (confirma preservation property).
    """
    page_mock, estado = _make_page_mock_sem_menu(label_curto, acao=acao)

    patches = _patches_base()
    for p in patches:
        p.start()

    try:
        acao_tec = _make_acao_tec_simples(
            label_curto=label_curto,
            acao=acao,
            tipo_elemento=tipo_elemento,
        )
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # Property: sem menu ativo, o clique deve ocorrer na tela principal
    assert resultado is True, (
        f"REGRESSÃO (preservation property): encontrar_e_clicar retornou False "
        f"sem menu de contexto ativo. "
        f"label_curto='{label_curto}', acao='{acao}', tipo_elemento='{tipo_elemento}', "
        f"context_menu_active=False."
    )
    assert estado["clicou_tela_principal"], (
        f"REGRESSÃO (preservation property): clique não ocorreu na tela principal. "
        f"label_curto='{label_curto}', acao='{acao}', tipo_elemento='{tipo_elemento}', "
        f"context_menu_active=False, elemento_clicado='{estado['elemento_clicado']}'"
    )

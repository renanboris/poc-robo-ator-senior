"""
Bug Condition Exploration Tests — robot-execution-wrong-clicks
==============================================================

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

OBJETIVO: Demonstrar o bug ANTES de implementar a correção.

Dois vetores simultâneos em vision_engine.py:

  Vetor 1 — Camada 2_coords_capturadas:
    O clique é executado nas coordenadas calculadas e o sistema retorna True
    sem verificar se o elemento presente naquelas coordenadas corresponde ao
    label_curto esperado.

  Vetor 2 — Camada 2_sniper (candidatos de texto parcial):
    Candidatos com exact=False são aceitos e executados sem passar por
    _verificar_identidade_elemento(), permitindo falsos positivos semânticos.

METODOLOGIA:
  - Os testes assertam o comportamento ESPERADO (correto).
  - O código NÃO corrigido viola esse comportamento → testes FALHAM.
  - A falha confirma que o bug existe.
  - Após o fix (Tarefa 3), estes mesmos testes devem PASSAR.

NÃO corrija o código nem os testes quando eles falharem.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers — construção de acao_tec
# ---------------------------------------------------------------------------

def _make_acao_tec_coords(label_curto: str, x_pct: float = 0.5, y_pct: float = 0.5) -> dict:
    """Constrói acao_tec com coordenadas relativas para testar camada 2_coords_capturadas."""
    return {
        "acao": "clique",
        "intencao_semantica": f"Clicar em '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Formulário",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": {"x_pct": x_pct, "y_pct": y_pct},
        },
    }


def _make_acao_tec_sniper(label_curto: str) -> dict:
    """Constrói acao_tec sem coordenadas para testar camada 2_sniper."""
    return {
        "acao": "clique",
        "intencao_semantica": f"Clicar em '{label_curto}'",
        "valor_input": "",
        "elemento_alvo": {
            "label_curto": label_curto,
            "seletor_hint": "",
            "iframe_hint": None,
            "descricao_visual": label_curto,
            "contexto_tela": "Diálogo",
            "tipo_elemento": "button",
            "html_hint": "",
            "coordenadas_relativas": None,
        },
    }


# ---------------------------------------------------------------------------
# Helpers — construção de page mocks
# ---------------------------------------------------------------------------

def _make_page_mock_coords(texto_elemento_nas_coords: str) -> MagicMock:
    """
    Cria mock de page para testar camada 2_coords_capturadas.

    page.evaluate() retorna:
      - 0 para window.scrollY (scroll)
      - texto_elemento_nas_coords para document.elementFromPoint(x, y)
        (simulando o elemento errado nas coordenadas calculadas)

    page.mouse.click() é rastreável via AsyncMock.
    """
    page_mock = AsyncMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.frames = []
    page_mock.main_frame = MagicMock()

    # page.evaluate: distingue chamadas por conteúdo do script
    async def evaluate_side_effect(script, *args, **kwargs):
        script_str = script if isinstance(script, str) else str(script)
        # Chamada de scroll (window.scrollY)
        if "scrollY" in script_str or "scrollTo" in script_str:
            return 0
        # Chamada de elementFromPoint — retorna texto do elemento errado
        if "elementFromPoint" in script_str:
            return texto_elemento_nas_coords
        return None

    page_mock.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    page_mock.mouse = AsyncMock()
    page_mock.mouse.click = AsyncMock(return_value=None)
    page_mock.mouse.dblclick = AsyncMock(return_value=None)
    page_mock.keyboard = AsyncMock()
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")

    # frame_locator — falha para não entrar em iframes
    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    # locator — retorna mock que falha (Sniper não deve resolver)
    locator_mock = AsyncMock()
    locator_mock.wait_for = AsyncMock(side_effect=Exception("elemento não encontrado"))
    locator_mock.first = locator_mock
    locator_container = MagicMock()
    locator_container.first = locator_mock
    page_mock.locator = MagicMock(return_value=locator_container)

    # get_by_text, get_by_role, get_by_label, get_by_placeholder, get_by_title — falham
    for method in ("get_by_text", "get_by_role", "get_by_label", "get_by_placeholder", "get_by_title"):
        mock_method = MagicMock()
        mock_method.first = locator_mock
        setattr(page_mock, method, MagicMock(return_value=mock_method))

    return page_mock


def _make_page_mock_sniper_texto_parcial(
    texto_elemento_visivel: str,
    label_curto: str,
) -> MagicMock:
    """
    Cria mock de page para testar camada 2_sniper com candidato de texto parcial.

    Simula uma página onde get_by_text(label_curto, exact=False) encontra
    um elemento cujo texto é texto_elemento_visivel (diferente do label_curto exato).

    Candidatos de alta confiança (aria-label exato, role+name, etc.) falham,
    forçando o Sniper a chegar no candidato de texto parcial.
    """
    page_mock = AsyncMock()
    page_mock.viewport_size = {"width": 1920, "height": 1080}
    page_mock.frames = []
    page_mock.main_frame = MagicMock()

    async def evaluate_side_effect(script, *args, **kwargs):
        script_str = script if isinstance(script, str) else str(script)
        if "scrollY" in script_str or "scrollTo" in script_str:
            return 0
        return None

    page_mock.evaluate = AsyncMock(side_effect=evaluate_side_effect)
    page_mock.mouse = AsyncMock()
    page_mock.mouse.click = AsyncMock(return_value=None)
    page_mock.keyboard = AsyncMock()
    page_mock.wait_for_load_state = AsyncMock(return_value=None)
    page_mock.screenshot = AsyncMock(return_value=b"fake_screenshot_bytes")

    # frame_locator — falha para não entrar em iframes
    frame_locator_mock = MagicMock()
    frame_locator_body = AsyncMock()
    frame_locator_body.wait_for = AsyncMock(side_effect=Exception("no iframe"))
    frame_locator_mock.locator = MagicMock(return_value=frame_locator_body)
    page_mock.frame_locator = MagicMock(return_value=frame_locator_mock)

    # Locator que simula o elemento errado encontrado por texto parcial
    locator_errado = AsyncMock()
    locator_errado.wait_for = AsyncMock(return_value=None)  # visível!
    locator_errado.inner_text = AsyncMock(return_value=texto_elemento_visivel)
    locator_errado.click = AsyncMock(return_value=None)
    locator_errado.is_visible = AsyncMock(return_value=True)
    locator_errado.scroll_into_view_if_needed = AsyncMock(return_value=None)
    locator_errado.bounding_box = AsyncMock(
        return_value={"x": 100, "y": 200, "width": 120, "height": 30}
    )
    locator_errado.hover = AsyncMock(return_value=None)
    locator_errado.evaluate = AsyncMock(return_value=None)
    locator_errado.dblclick = AsyncMock(return_value=None)
    locator_errado.locator = MagicMock(return_value=locator_errado)  # para ".." (pai)

    # Locator que falha (para candidatos de alta confiança)
    locator_falha = AsyncMock()
    locator_falha.wait_for = AsyncMock(side_effect=Exception("elemento não encontrado"))
    locator_falha.first = locator_falha

    # page.locator: retorna locator_falha por padrão (seletores CSS como aria-label, etc.)
    locator_container_falha = MagicMock()
    locator_container_falha.first = locator_falha
    page_mock.locator = MagicMock(return_value=locator_container_falha)

    # get_by_text: retorna o locator_errado (simula texto parcial encontrado)
    locator_container_errado = MagicMock()
    locator_container_errado.first = locator_errado
    page_mock.get_by_text = MagicMock(return_value=locator_container_errado)

    # get_by_role, get_by_label, get_by_placeholder, get_by_title — falham
    for method in ("get_by_role", "get_by_label", "get_by_placeholder", "get_by_title"):
        mock_method = MagicMock()
        mock_method.first = locator_falha
        setattr(page_mock, method, MagicMock(return_value=mock_method))

    return page_mock


# ---------------------------------------------------------------------------
# Patches comuns para isolar camadas específicas
# ---------------------------------------------------------------------------

def _patches_isolar_camada_coords():
    """
    Desativa Brain, Template Matching, Sniper e Vision.
    Deixa apenas 2_coords_capturadas ativa.
    """
    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_registrar_telemetria", return_value=None),
        patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None),
        # Template Matching: sem screenshot de referência → não ativa
        # Sniper: _tentar_candidato sempre falha → força escalada para próxima camada
        patch.object(vision_engine, "_tentar_candidato", new=AsyncMock(return_value=False)),
        # Gemini Vision: desativado
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        # Scroll: no-op
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
        # Menu de contexto: não ativo
        patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)),
    ]


def _patches_isolar_camada_sniper():
    """
    Desativa Brain, Template Matching, 2_coords_capturadas e Vision.
    Deixa o Sniper ativo (usa _tentar_candidato real).
    """
    return [
        patch.object(vision_engine, "_consultar_cache", return_value=None),
        patch.object(vision_engine, "_registrar_sucesso_cache", return_value=None),
        patch.object(vision_engine, "_registrar_falha_cache", return_value=None),
        patch.object(vision_engine, "_registrar_telemetria", return_value=None),
        patch.object(vision_engine, "_registrar_estrategia_vencedora", return_value=None),
        # Gemini Vision: desativado
        patch.object(vision_engine, "_gemini_localizar_elemento", new=AsyncMock(return_value=None)),
        # Scroll: no-op
        patch.object(vision_engine, "_scroll_para_area_esperada", new=AsyncMock(return_value=0)),
        # Menu de contexto: não ativo
        patch.object(vision_engine, "_detectar_menu_contexto_ativo", new=AsyncMock(return_value=None)),
        # _clicar_por_coordenadas: falha (sem coords_relativas no acao_tec do Sniper)
        # Não precisa de patch — coordenadas_relativas=None já pula a camada
    ]


# ===========================================================================
# CENÁRIO A — Coords deslocadas (camada 2_coords_capturadas)
# ===========================================================================

@pytest.mark.asyncio
async def test_cenario_a_coords_deslocadas_elemento_errado():
    """
    **Validates: Requirements 1.1, 1.2**

    Cenário A — Coords deslocadas: camada 2_coords_capturadas.

    Situação:
      - label_curto = "Salvar"
      - coordenadas_relativas = {"x_pct": 0.5, "y_pct": 0.5}
      - page.evaluate("document.elementFromPoint(x, y)") retorna "Cancelar"
        (elemento errado nas coordenadas calculadas — deslocamento de resolução)

    Comportamento do código NÃO corrigido:
      - Calcula x=960, y=540 a partir das coords relativas
      - Chama _clicar_por_coordenadas → retorna True (clique mecânico sem exceção)
      - Retorna True imediatamente SEM verificar o elemento nas coordenadas
      - Aceita "Cancelar" como se fosse "Salvar" → FALSO POSITIVO

    Comportamento ESPERADO (correto):
      - Verificar o elemento nas coordenadas via page.evaluate("elementFromPoint")
      - "Cancelar" não contém "Salvar" → rejeitar e escalar para próxima camada
      - Retornar False (nenhuma camada conseguiu resolver)

    Este teste FALHA no código não corrigido → confirma que o bug existe.

    Contraexemplo documentado:
      label_curto = "Salvar"
      coords = {"x_pct": 0.5, "y_pct": 0.5} → x=960, y=540
      texto_elemento_nas_coords = "Cancelar"
      resultado_nao_corrigido = True  ← BUG: aceita elemento errado
      resultado_esperado = False
    """
    acao_tec = _make_acao_tec_coords(label_curto="Salvar", x_pct=0.5, y_pct=0.5)
    page_mock = _make_page_mock_coords(texto_elemento_nas_coords="Cancelar")

    patches = _patches_isolar_camada_coords()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO é rejeitar o elemento errado e retornar False.
    # O código NÃO corrigido retorna True (aceita "Cancelar" como "Salvar").
    # Este assert FALHA no código bugado — confirmando o bug.
    assert resultado is False, (
        "BUG CONFIRMADO (Cenário A): encontrar_e_clicar retornou True ao clicar em "
        "'Cancelar' quando label_curto='Salvar'. A camada 2_coords_capturadas não "
        "verificou a identidade do elemento nas coordenadas calculadas. "
        "Contraexemplo: coords=(0.5, 0.5) → (960, 540), texto_real='Cancelar', "
        "label_esperado='Salvar', resultado=True (deveria ser False)."
    )


@pytest.mark.asyncio
async def test_cenario_a_coords_deslocadas_elemento_completamente_diferente():
    """
    **Validates: Requirements 1.1, 1.2**

    Variação do Cenário A com elemento ainda mais distante semanticamente.

    Situação:
      - label_curto = "Confirmar Pedido"
      - page.evaluate retorna "Menu Principal" (elemento de navegação)

    O código NÃO corrigido clica em "Menu Principal" e reporta sucesso.
    O comportamento CORRETO é rejeitar e retornar False.
    """
    acao_tec = _make_acao_tec_coords(
        label_curto="Confirmar Pedido", x_pct=0.017, y_pct=0.711
    )
    page_mock = _make_page_mock_coords(texto_elemento_nas_coords="Menu Principal")

    patches = _patches_isolar_camada_coords()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado is False, (
        "BUG CONFIRMADO (Cenário A variação): encontrar_e_clicar retornou True ao "
        "clicar em 'Menu Principal' quando label_curto='Confirmar Pedido'. "
        "Contraexemplo: coords=(0.017, 0.711), texto_real='Menu Principal', "
        "label_esperado='Confirmar Pedido', resultado=True (deveria ser False)."
    )


# ===========================================================================
# CENÁRIO B — Sniper falso positivo (texto parcial)
# ===========================================================================

@pytest.mark.asyncio
async def test_cenario_b_sniper_falso_positivo_novo_documento():
    """
    **Validates: Requirements 1.3, 1.4**

    Cenário B — Sniper falso positivo: candidato text=X com exact=False.

    Situação:
      - label_curto = "Novo Documento"
      - Página contém "Novo Documento de Texto" visível ANTES de "Novo Documento"
      - Sniper gera candidato: text="Novo Documento" com exact=False
      - get_by_text("Novo Documento", exact=False).first retorna "Novo Documento de Texto"
        (primeiro elemento visível que contém o texto parcial)

    Comportamento do código NÃO corrigido:
      - _tentar_candidato chama get_by_text("Novo Documento", exact=False).first
      - Elemento "Novo Documento de Texto" está visível → wait_for passa
      - Executa clique em "Novo Documento de Texto" → retorna True
      - Não verifica se o elemento encontrado É "Novo Documento" (exato)
      - FALSO POSITIVO: clicou no item errado

    Comportamento ESPERADO (correto):
      - Verificar identidade: "Novo Documento de Texto" não é "Novo Documento"
      - Rejeitar candidato e continuar tentando
      - Retornar False (nenhuma camada conseguiu resolver)

    Este teste FALHA no código não corrigido → confirma que o bug existe.

    Contraexemplo documentado:
      label_curto = "Novo Documento"
      texto_elemento_encontrado = "Novo Documento de Texto"
      resultado_nao_corrigido = True  ← BUG: aceita elemento errado
      resultado_esperado = False
    """
    acao_tec = _make_acao_tec_sniper(label_curto="Novo Documento")
    page_mock = _make_page_mock_sniper_texto_parcial(
        texto_elemento_visivel="Novo Documento de Texto",
        label_curto="Novo Documento",
    )

    patches = _patches_isolar_camada_sniper()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO é rejeitar o falso positivo e retornar False.
    # O código NÃO corrigido retorna True (aceita "Novo Documento de Texto").
    # Este assert FALHA no código bugado — confirmando o bug.
    assert resultado is False, (
        "BUG CONFIRMADO (Cenário B): encontrar_e_clicar retornou True ao encontrar "
        "'Novo Documento de Texto' quando label_curto='Novo Documento'. "
        "O Sniper aceitou o candidato de texto parcial sem verificar identidade. "
        "Contraexemplo: label='Novo Documento', texto_real='Novo Documento de Texto', "
        "resultado=True (deveria ser False)."
    )


@pytest.mark.asyncio
async def test_cenario_b_sniper_falso_positivo_novo_documento_planilha():
    """
    **Validates: Requirements 1.3, 1.4**

    Variação do Cenário B: "Novo Documento de Planilha" encontrado antes de "Novo Documento".

    Contraexemplo documentado:
      label_curto = "Novo Documento"
      texto_elemento_encontrado = "Novo Documento de Planilha"
      resultado_nao_corrigido = True  ← BUG
      resultado_esperado = False
    """
    acao_tec = _make_acao_tec_sniper(label_curto="Novo Documento")
    page_mock = _make_page_mock_sniper_texto_parcial(
        texto_elemento_visivel="Novo Documento de Planilha",
        label_curto="Novo Documento",
    )

    patches = _patches_isolar_camada_sniper()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado is False, (
        "BUG CONFIRMADO (Cenário B variação): encontrar_e_clicar retornou True ao "
        "encontrar 'Novo Documento de Planilha' quando label_curto='Novo Documento'. "
        "Contraexemplo: label='Novo Documento', texto_real='Novo Documento de Planilha', "
        "resultado=True (deveria ser False)."
    )


# ===========================================================================
# CENÁRIO C — Sniper múltiplos candidatos ambíguos
# ===========================================================================

@pytest.mark.asyncio
async def test_cenario_c_sniper_multiplos_candidatos_ambiguos():
    """
    **Validates: Requirements 1.3, 1.4**

    Cenário C — Sniper múltiplos candidatos ambíguos.

    Situação:
      - label_curto = "Excluir Pasta"
      - Página contém "Excluir Arquivo" visível ANTES de "Excluir Pasta"
      - Sniper gera candidato: text="Excluir Pasta" com exact=False
      - get_by_text("Excluir Pasta", exact=False).first retorna "Excluir Arquivo"
        (primeiro elemento visível que contém "Excluir" — texto parcial coincide)

    Comportamento do código NÃO corrigido:
      - Candidato text="Excluir Pasta" exact=False → get_by_text encontra "Excluir Arquivo"
      - "Excluir Arquivo" contém "Excluir" mas NÃO contém "Excluir Pasta" completo
      - Porém exact=False faz get_by_text("Excluir Pasta") encontrar qualquer elemento
        que contenha "Excluir Pasta" como substring — "Excluir Arquivo" NÃO contém
        "Excluir Pasta" como substring, então este cenário testa o caso onde o mock
        simula que o primeiro elemento visível retornado pelo Playwright é "Excluir Arquivo"
        (comportamento real do Playwright quando há múltiplos elementos com texto similar)
      - O código não verifica se o elemento encontrado É "Excluir Pasta" → FALSO POSITIVO

    Comportamento ESPERADO (correto):
      - Verificar identidade: "Excluir Arquivo" não contém "Excluir Pasta"
      - Rejeitar candidato e continuar tentando
      - Retornar False (nenhuma camada conseguiu resolver)

    Este teste FALHA no código não corrigido → confirma que o bug existe.

    Contraexemplo documentado:
      label_curto = "Excluir Pasta"
      texto_elemento_encontrado = "Excluir Arquivo"
      resultado_nao_corrigido = True  ← BUG: aceita elemento errado
      resultado_esperado = False
    """
    acao_tec = _make_acao_tec_sniper(label_curto="Excluir Pasta")
    page_mock = _make_page_mock_sniper_texto_parcial(
        texto_elemento_visivel="Excluir Arquivo",
        label_curto="Excluir Pasta",
    )

    patches = _patches_isolar_camada_sniper()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    # O comportamento CORRETO é rejeitar o elemento errado e retornar False.
    # O código NÃO corrigido retorna True (aceita "Excluir Arquivo" como "Excluir Pasta").
    # Este assert FALHA no código bugado — confirmando o bug.
    assert resultado is False, (
        "BUG CONFIRMADO (Cenário C): encontrar_e_clicar retornou True ao encontrar "
        "'Excluir Arquivo' quando label_curto='Excluir Pasta'. "
        "O Sniper aceitou o candidato de texto parcial sem verificar identidade. "
        "Contraexemplo: label='Excluir Pasta', texto_real='Excluir Arquivo', "
        "resultado=True (deveria ser False)."
    )


@pytest.mark.asyncio
async def test_cenario_c_sniper_fechar_periodo_vs_abrir_periodo():
    """
    **Validates: Requirements 1.3, 1.4**

    Variação do Cenário C: "Fechar Período" vs "Abrir Período".

    Situação:
      - label_curto = "Fechar Período"
      - Página contém "Abrir Período" visível (texto parcialmente coincidente com "Período")
      - Sniper com exact=False encontra "Abrir Período" primeiro

    Contraexemplo documentado:
      label_curto = "Fechar Período"
      texto_elemento_encontrado = "Abrir Período"
      resultado_nao_corrigido = True  ← BUG
      resultado_esperado = False
    """
    acao_tec = _make_acao_tec_sniper(label_curto="Fechar Período")
    page_mock = _make_page_mock_sniper_texto_parcial(
        texto_elemento_visivel="Abrir Período",
        label_curto="Fechar Período",
    )

    patches = _patches_isolar_camada_sniper()
    for p in patches:
        p.start()

    try:
        resultado = await vision_engine.encontrar_e_clicar(page_mock, acao_tec)
    finally:
        for p in patches:
            p.stop()

    assert resultado is False, (
        "BUG CONFIRMADO (Cenário C variação): encontrar_e_clicar retornou True ao "
        "encontrar 'Abrir Período' quando label_curto='Fechar Período'. "
        "Contraexemplo: label='Fechar Período', texto_real='Abrir Período', "
        "resultado=True (deveria ser False)."
    )

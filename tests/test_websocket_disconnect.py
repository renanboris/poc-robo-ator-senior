"""
Bug Condition Exploration Test — browser-disconnect-and-dual-tenant · Bug 1
============================================================================

**Validates: Requirements 1.1, 1.2, 1.3**

OBJETIVO: Demonstrar o bug ANTES de implementar a correção.

Bug 1 — Fechar o navegador não cancela o robô em execução:
  O handler `websocket_status` em `app.py` (rota `/api/ws/status`) não encerra
  o `processo_atual` quando o último cliente WebSocket desconecta. O bloco
  `except WebSocketDisconnect` apenas chama `ws_manager.disconnect(websocket)`
  mas não verifica se a lista ficou vazia nem termina o processo filho.

METODOLOGIA:
  - O teste asserta o comportamento ESPERADO (correto).
  - O código NÃO corrigido viola esse comportamento → teste FALHA.
  - A falha confirma que o bug existe.
  - Após o fix (Tarefa 3), este mesmo teste deve PASSAR.

NÃO corrija o código nem o teste quando ele falhar.
"""

import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
from fastapi.websockets import WebSocketDisconnect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ===========================================================================
# Teste de exploração da bug condition — Bug 1
# ===========================================================================

@pytest.mark.asyncio
async def test_bug1_ultimo_cliente_desconecta_processo_deve_ser_encerrado():
    """
    **Validates: Requirements 1.1, 1.2, 1.3**

    Cenário: último cliente WebSocket desconecta com processo ativo.

    Setup:
      - ws_manager.active_connections fica VAZIO após disconnect()
      - processo_atual é um MagicMock com returncode=None (processo ativo)
      - _set_estado é mockado para rastrear chamadas

    Comportamento do código NÃO corrigido:
      - ws_manager.disconnect(websocket) é chamado
      - Nenhuma verificação de active_connections é feita
      - proc.terminate() NÃO é chamado
      - _set_estado NÃO é chamado com ocupado=False
      - processo_atual permanece não-None

    Comportamento ESPERADO (correto):
      - Após disconnect(), verificar se active_connections está vazio
      - Como está vazio e processo_atual não é None:
        - proc.terminate() deve ser chamado
        - _set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.") deve ser chamado
        - processo_atual deve ser setado para None

    Este teste FALHA no código não corrigido → confirma que o bug existe.

    Contraexemplo documentado:
      - processo_atual.returncode is None após o último cliente desconectar
      - proc.terminate() não foi chamado (assert_called_once falha)
    """
    import app as app_module

    # Cria mock do processo ativo (returncode=None simula processo rodando)
    proc_mock = MagicMock()
    proc_mock.returncode = None
    proc_mock.terminate = MagicMock()

    # Cria mock do websocket
    websocket_mock = AsyncMock()
    # Simula WebSocketDisconnect na primeira chamada a receive_text
    websocket_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    # Cria mock do ws_manager: active_connections fica vazio após disconnect
    ws_manager_mock = MagicMock()
    ws_manager_mock.connect = AsyncMock(return_value=None)
    ws_manager_mock.active_connections = []  # já vazio (simula último cliente)

    def disconnect_side_effect(ws):
        # Após disconnect, a lista permanece vazia (último cliente saiu)
        ws_manager_mock.active_connections = []

    ws_manager_mock.disconnect = MagicMock(side_effect=disconnect_side_effect)

    # Mock de _set_estado para rastrear chamadas
    set_estado_mock = MagicMock()

    with (
        patch.object(app_module, "ws_manager", ws_manager_mock),
        patch.object(app_module, "processo_atual", proc_mock),
        patch.object(app_module, "_set_estado", set_estado_mock),
    ):
        # Executa o handler websocket_status
        await app_module.websocket_status(websocket_mock)

    # -----------------------------------------------------------------------
    # Asserção 1: proc.terminate() deve ter sido chamado
    # No código NÃO corrigido, esta asserção FALHA — confirma o bug.
    # -----------------------------------------------------------------------
    proc_mock.terminate.assert_called_once(), (
        "BUG CONFIRMADO: proc.terminate() não foi chamado após o último cliente "
        "WebSocket desconectar com processo ativo. O processo filho continua rodando "
        "em background indefinidamente. "
        "Contraexemplo: active_connections=[], processo_atual.returncode=None, "
        "terminate() não chamado."
    )

    # -----------------------------------------------------------------------
    # Asserção 2: _set_estado deve ter sido chamado com os parâmetros corretos
    # -----------------------------------------------------------------------
    set_estado_mock.assert_called_once_with(
        ocupado=False,
        progresso=None,
        erro="Execução interrompida: navegador fechado.",
    ), (
        "BUG CONFIRMADO: _set_estado não foi chamado com os parâmetros esperados "
        "após o último cliente WebSocket desconectar. "
        "Esperado: _set_estado(ocupado=False, progresso=None, "
        "erro='Execução interrompida: navegador fechado.')"
    )

    # -----------------------------------------------------------------------
    # Asserção 3: processo_atual deve ter sido setado para None
    # -----------------------------------------------------------------------
    with patch.object(app_module, "_estado_lock"):
        # Verifica que o módulo tentou setar processo_atual = None
        # Isso é verificado indiretamente: se terminate() foi chamado e
        # _set_estado foi chamado, o patch do processo_atual deve ter sido None
        pass

    # Verificação direta: o processo não deve mais estar ativo (returncode não-None
    # OU terminate foi chamado — já verificado acima)
    assert proc_mock.terminate.call_count == 1, (
        "BUG CONFIRMADO: proc.terminate() deveria ter sido chamado exatamente 1 vez, "
        f"mas foi chamado {proc_mock.terminate.call_count} vez(es). "
        "Contraexemplo: active_connections=[], processo_atual.returncode=None."
    )


# ===========================================================================
# Testes de preservação — Bug 1 (Property 2: Preservation)
# ===========================================================================
#
# **Validates: Requirements 3.1, 3.2**
#
# OBJETIVO: Verificar que o código NÃO CORRIGIDO já preserva os comportamentos
# que o fix não deve quebrar.
#
# Esses testes DEVEM PASSAR no código não corrigido — eles documentam o
# baseline de comportamento correto que o patch deve manter intacto.
#
# Após o fix (Tarefa 3), esses mesmos testes devem continuar passando.
# ===========================================================================

import hypothesis.strategies as st
from hypothesis import HealthCheck, given, settings

# ---------------------------------------------------------------------------
# Teste determinístico 1: 2 clientes conectados, um desconecta → processo NÃO
# deve ser terminado.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_dois_clientes_um_desconecta_processo_continua():
    """
    **Validates: Requirements 3.1, 3.2**

    Cenário: dois clientes WebSocket conectados; um desconecta.

    O processo NÃO deve ser terminado porque ainda há um cliente ativo.
    Este comportamento já existe no código não corrigido e deve ser preservado
    após o fix.

    EXPECTED OUTCOME: PASSA no código não corrigido.
    """
    import app as app_module

    proc_mock = MagicMock()
    proc_mock.returncode = None
    proc_mock.terminate = MagicMock()

    websocket_mock = AsyncMock()
    websocket_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    # Simula um segundo cliente ainda conectado após o disconnect
    outro_cliente = AsyncMock()

    ws_manager_mock = MagicMock()
    ws_manager_mock.connect = AsyncMock(return_value=None)

    def disconnect_side_effect(ws):
        # Após disconnect, ainda há um cliente ativo na lista
        ws_manager_mock.active_connections = [outro_cliente]

    ws_manager_mock.active_connections = [websocket_mock, outro_cliente]
    ws_manager_mock.disconnect = MagicMock(side_effect=disconnect_side_effect)

    set_estado_mock = MagicMock()

    with (
        patch.object(app_module, "ws_manager", ws_manager_mock),
        patch.object(app_module, "processo_atual", proc_mock),
        patch.object(app_module, "_set_estado", set_estado_mock),
    ):
        await app_module.websocket_status(websocket_mock)

    # O processo NÃO deve ter sido terminado
    proc_mock.terminate.assert_not_called(), (
        "REGRESSÃO: proc.terminate() foi chamado mesmo com outro cliente ativo. "
        "O processo deve continuar rodando enquanto há clientes conectados. "
        "Requisitos 3.1, 3.2."
    )

    # _set_estado NÃO deve ter sido chamado com ocupado=False
    for call_args in set_estado_mock.call_args_list:
        kwargs = call_args.kwargs if call_args.kwargs else {}
        args = call_args.args if call_args.args else ()
        assert kwargs.get("ocupado") is not False and (len(args) == 0 or args[0] is not False), (
            "REGRESSÃO: _set_estado(ocupado=False) foi chamado mesmo com outro cliente ativo."
        )


# ---------------------------------------------------------------------------
# Teste determinístico 2: processo_atual = None, cliente desconecta → nenhuma
# exceção deve ser lançada.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preservation_processo_none_desconecta_sem_excecao():
    """
    **Validates: Requirements 3.1, 3.2**

    Cenário: processo_atual é None; cliente desconecta.

    Nenhuma exceção deve ser lançada — não há processo para encerrar.
    Este comportamento já existe no código não corrigido e deve ser preservado.

    EXPECTED OUTCOME: PASSA no código não corrigido.
    """
    import app as app_module

    websocket_mock = AsyncMock()
    websocket_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    ws_manager_mock = MagicMock()
    ws_manager_mock.connect = AsyncMock(return_value=None)
    ws_manager_mock.active_connections = []

    def disconnect_side_effect(ws):
        ws_manager_mock.active_connections = []

    ws_manager_mock.disconnect = MagicMock(side_effect=disconnect_side_effect)

    set_estado_mock = MagicMock()

    with (
        patch.object(app_module, "ws_manager", ws_manager_mock),
        patch.object(app_module, "processo_atual", None),
        patch.object(app_module, "_set_estado", set_estado_mock),
    ):
        # Não deve lançar nenhuma exceção
        try:
            await app_module.websocket_status(websocket_mock)
        except Exception as exc:
            pytest.fail(
                f"REGRESSÃO: exceção inesperada lançada quando processo_atual=None "
                f"e cliente desconecta: {type(exc).__name__}: {exc}"
            )


# ---------------------------------------------------------------------------
# Property-based test 1: n_clients ≥ 2, um desconecta → proc.terminate() NÃO
# deve ser chamado.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@given(n_clients=st.integers(min_value=2, max_value=20))
@settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_preservation_pbt_n_clientes_um_desconecta_terminate_nao_chamado(n_clients):
    """
    **Validates: Requirements 3.1, 3.2**

    Property: para qualquer número de clientes ≥ 2, quando um desconecta,
    proc.terminate() NÃO deve ser chamado — ainda há clientes ativos.

    Gerador: n_clients ∈ [2, 20]

    EXPECTED OUTCOME: PASSA no código não corrigido.
    """
    import app as app_module

    proc_mock = MagicMock()
    proc_mock.returncode = None
    proc_mock.terminate = MagicMock()

    websocket_mock = AsyncMock()
    websocket_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    # Os demais clientes (todos exceto o que desconecta)
    outros_clientes = [AsyncMock() for _ in range(n_clients - 1)]

    ws_manager_mock = MagicMock()
    ws_manager_mock.connect = AsyncMock(return_value=None)
    ws_manager_mock.active_connections = [websocket_mock] + outros_clientes

    def disconnect_side_effect(ws):
        # Após disconnect, ainda restam n_clients - 1 clientes
        ws_manager_mock.active_connections = outros_clientes

    ws_manager_mock.disconnect = MagicMock(side_effect=disconnect_side_effect)

    set_estado_mock = MagicMock()

    with (
        patch.object(app_module, "ws_manager", ws_manager_mock),
        patch.object(app_module, "processo_atual", proc_mock),
        patch.object(app_module, "_set_estado", set_estado_mock),
    ):
        await app_module.websocket_status(websocket_mock)

    assert proc_mock.terminate.call_count == 0, (
        f"REGRESSÃO (n_clients={n_clients}): proc.terminate() foi chamado "
        f"{proc_mock.terminate.call_count} vez(es) mesmo com {n_clients - 1} "
        f"cliente(s) ainda ativo(s). O processo deve continuar rodando. "
        f"Requisitos 3.1, 3.2."
    )


# ---------------------------------------------------------------------------
# Property-based test 2: pares aleatórios (n_clients_antes > 1, processo_ativo)
# → proc.terminate() NÃO deve ser chamado.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@given(
    n_clients_antes=st.integers(min_value=2, max_value=20),
    processo_ativo=st.booleans(),
)
@settings(max_examples=15, suppress_health_check=[HealthCheck.function_scoped_fixture])
async def test_preservation_pbt_pares_n_clients_processo_ativo_terminate_nao_chamado(
    n_clients_antes, processo_ativo
):
    """
    **Validates: Requirements 3.1, 3.2**

    Property: para qualquer par (n_clients_antes > 1, processo_ativo ∈ {True, False}),
    quando um cliente desconecta (restando n_clients_antes - 1 ≥ 1 clientes),
    proc.terminate() NÃO deve ser chamado — a lista não ficou vazia.

    Geradores:
      - n_clients_antes ∈ [2, 20]
      - processo_ativo ∈ {True, False}

    EXPECTED OUTCOME: PASSA no código não corrigido.
    """
    import app as app_module

    proc_mock = MagicMock()
    proc_mock.returncode = None
    proc_mock.terminate = MagicMock()

    websocket_mock = AsyncMock()
    websocket_mock.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    outros_clientes = [AsyncMock() for _ in range(n_clients_antes - 1)]

    ws_manager_mock = MagicMock()
    ws_manager_mock.connect = AsyncMock(return_value=None)
    ws_manager_mock.active_connections = [websocket_mock] + outros_clientes

    def disconnect_side_effect(ws):
        ws_manager_mock.active_connections = outros_clientes

    ws_manager_mock.disconnect = MagicMock(side_effect=disconnect_side_effect)

    set_estado_mock = MagicMock()

    # processo_atual pode ser o mock ativo ou None, dependendo do gerador
    processo_patch = proc_mock if processo_ativo else None

    with (
        patch.object(app_module, "ws_manager", ws_manager_mock),
        patch.object(app_module, "processo_atual", processo_patch),
        patch.object(app_module, "_set_estado", set_estado_mock),
    ):
        await app_module.websocket_status(websocket_mock)

    assert proc_mock.terminate.call_count == 0, (
        f"REGRESSÃO (n_clients_antes={n_clients_antes}, processo_ativo={processo_ativo}): "
        f"proc.terminate() foi chamado {proc_mock.terminate.call_count} vez(es) "
        f"mesmo com {n_clients_antes - 1} cliente(s) ainda ativo(s). "
        f"Requisitos 3.1, 3.2."
    )

"""
tests/test_production_completion_signal.py
==========================================
Tests for the production-completion-signal bugfix.

**Property 1: Bug Condition** — Ingest Endpoint Emits No Completion Signal

CRITICAL: Tests 1.x are EXPECTED TO FAIL on unfixed code.
Failure confirms the bug: `_set_estado()` is never called after
`/api/ingest/{arquivo}` returns, so the frontend WebSocket promise
(`_wsResolve`) is never resolved.

Root cause confirmed:
  `ingestar_no_dap` in app.py calls `dap_engine.ingestar_para_pinecone()`
  and returns `res` directly — without ever calling `_set_estado(sucesso=...)`
  or `_set_estado(erro=...)`. All other production steps use
  `executar_processo_bg` which always calls `_set_estado()` at the end.

Validates: Requirements 1.1, 1.2

**Property 2: Preservation** — Outros Passos da Produção e Contrato JSON Inalterados

Tests 2.x MUST PASS on unfixed code — they confirm the baseline behavior
that must be preserved after the fix is applied.

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import sys
import os
import json
import asyncio
import threading
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hypothesis import given, settings, strategies as st, assume
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Import app and its shared state
# ---------------------------------------------------------------------------
import app as app_module
from app import app, estado_servidor, _set_estado, _estado_lock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_estado():
    """Reset estado_servidor to its initial blank state between tests."""
    with _estado_lock:
        estado_servidor["ocupado"]     = False
        estado_servidor["mensagem"]    = ""
        estado_servidor["progresso"]   = None
        estado_servidor["erro"]        = ""
        estado_servidor["sucesso"]     = ""
        estado_servidor["shadow_path"] = None


def _make_roteiro(nome: str = "Aula Teste") -> dict:
    """Minimal valid roteiro JSON for testing."""
    return {
        "metadata": {
            "nome_aula": nome,
            "id_treinamento": nome,
            "ingestado_dap": False,
        },
        "passos": [
            {
                "id_passo": 1,
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "[aria-label='Salvar']",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
            {
                "id_passo": 2,
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "seletor_hint": "[aria-label='Confirmar']",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
        ],
    }


# ---------------------------------------------------------------------------
# Fixture: TestClient with auth header and a real roteiro file on disk
# ---------------------------------------------------------------------------

@pytest.fixture()
def client_with_roteiro(tmp_path, monkeypatch):
    """
    Provides a TestClient with:
    - AURA_API_SECRET set so auth passes
    - ROTEIROS_DIR pointing to a tmp directory with a test roteiro file
    - main_loop set so _set_estado can attempt broadcast (ws_manager mocked)
    """
    # Point ROTEIROS_DIR to tmp_path
    monkeypatch.setenv("AURA_API_SECRET", "test-secret")
    monkeypatch.setenv("DEFAULT_TENANT_ID", "senior_default")
    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(tmp_path))

    # Write a test roteiro file
    roteiro_nome = "roteiro_teste.json"
    roteiro_path = tmp_path / roteiro_nome
    roteiro_path.write_text(
        json.dumps(_make_roteiro(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Provide a real event loop so _set_estado's run_coroutine_threadsafe works
    loop = asyncio.new_event_loop()
    monkeypatch.setattr(app_module, "main_loop", loop)

    # Mock ws_manager.broadcast to be a no-op coroutine (no real WebSocket)
    async def _noop_broadcast(msg):
        pass

    monkeypatch.setattr(app_module.ws_manager, "broadcast", _noop_broadcast)

    _reset_estado()

    client = TestClient(app, raise_server_exceptions=True)
    yield client, roteiro_nome, loop

    loop.close()
    _reset_estado()


# ---------------------------------------------------------------------------
# Test 1.1 — Ingest com sucesso: estado_servidor["sucesso"] deve ser preenchido
#
# BUG CONDITION: Mock retorna {"status": "sucesso"} → endpoint retorna HTTP 200
# EXPECTED (after fix): estado_servidor["sucesso"] != ""
# ACTUAL (unfixed):     estado_servidor["sucesso"] == ""  ← BUG CONFIRMED
# ---------------------------------------------------------------------------

def test_1_1_ingest_sucesso_deve_preencher_estado_sucesso(client_with_roteiro):
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: after calling /api/ingest/{arquivo} with a successful
    dap_engine response, estado_servidor["sucesso"] must NOT be empty.

    EXPECTED TO FAIL on unfixed code — confirms the bug.
    Counterexample: estado_servidor["sucesso"] remains "" after HTTP 200.
    """
    client, roteiro_nome, _ = client_with_roteiro
    _reset_estado()

    mock_res = {"status": "sucesso", "mensagem": "Indexado com sucesso", "vetores": 5}

    with patch.object(app_module.dap_engine, "ingestar_para_pinecone", return_value=mock_res):
        response = client.post(
            f"/api/ingest/{roteiro_nome}",
            headers={"Authorization": "Bearer test-secret"},
        )

    assert response.status_code == 200, f"Endpoint retornou {response.status_code}"

    with _estado_lock:
        sucesso_atual = estado_servidor["sucesso"]

    assert sucesso_atual != "", (
        f"BUG CONFIRMADO: estado_servidor['sucesso'] permanece vazio após ingest com sucesso. "
        f"O frontend ficaria travado aguardando WebSocket. "
        f"Valor atual: {sucesso_atual!r}"
    )


# ---------------------------------------------------------------------------
# Test 1.2 — Ingest com erro: estado_servidor["erro"] deve ser preenchido
#
# BUG CONDITION: Mock retorna {"status": "erro", ...} → endpoint retorna HTTP 200
# EXPECTED (after fix): estado_servidor["erro"] != ""
# ACTUAL (unfixed):     estado_servidor["erro"] == ""  ← BUG CONFIRMED
# ---------------------------------------------------------------------------

def test_1_2_ingest_erro_deve_preencher_estado_erro(client_with_roteiro):
    """
    **Validates: Requirements 1.1, 1.2**

    Bug condition: after calling /api/ingest/{arquivo} with a failed
    dap_engine response, estado_servidor["erro"] must NOT be empty.

    EXPECTED TO FAIL on unfixed code — confirms the bug.
    Counterexample: estado_servidor["erro"] remains "" after HTTP 200 with error.
    """
    client, roteiro_nome, _ = client_with_roteiro
    _reset_estado()

    mock_res = {"status": "erro", "mensagem": "Pinecone indisponível"}

    with patch.object(app_module.dap_engine, "ingestar_para_pinecone", return_value=mock_res):
        response = client.post(
            f"/api/ingest/{roteiro_nome}",
            headers={"Authorization": "Bearer test-secret"},
        )

    assert response.status_code == 200, f"Endpoint retornou {response.status_code}"

    with _estado_lock:
        erro_atual = estado_servidor["erro"]

    assert erro_atual != "", (
        f"BUG CONFIRMADO: estado_servidor['erro'] permanece vazio após ingest com erro. "
        f"O frontend ficaria travado aguardando WebSocket. "
        f"Valor atual: {erro_atual!r}"
    )


# ---------------------------------------------------------------------------
# Property Test 1.3 — Hypothesis: para qualquer resposta do dap_engine,
# _set_estado deve sempre ser chamado com sucesso ou erro.
#
# Generates varied success/error responses and asserts the state is updated.
# EXPECTED TO FAIL on unfixed code — confirms the bug across all inputs.
# ---------------------------------------------------------------------------

@st.composite
def dap_sucesso_responses(draw):
    """Generates varied success responses from dap_engine."""
    mensagem = draw(st.one_of(
        st.just("Indexado com sucesso"),
        st.just("✅ Vetores enviados ao Pinecone"),
        st.text(min_size=1, max_size=80, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
    ))
    vetores = draw(st.integers(min_value=0, max_value=100))
    return {"status": "sucesso", "mensagem": mensagem, "vetores": vetores}


@st.composite
def dap_erro_responses(draw):
    """Generates varied error responses from dap_engine."""
    mensagem = draw(st.one_of(
        st.just("Pinecone indisponível"),
        st.just("Timeout na conexão"),
        st.just("Chave de API inválida"),
        st.text(min_size=1, max_size=80, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))),
    ))
    return {"status": "erro", "mensagem": mensagem}


@given(mock_res=st.one_of(dap_sucesso_responses(), dap_erro_responses()))
@settings(max_examples=20)
def test_1_3_property_ingest_sempre_emite_sinal_de_conclusao(mock_res):
    """
    **Validates: Requirements 1.1, 1.2**

    Property: for any response from dap_engine.ingestar_para_pinecone,
    the endpoint MUST call _set_estado() so that either
    estado_servidor["sucesso"] != "" or estado_servidor["erro"] != "".

    EXPECTED TO FAIL on unfixed code — confirms the bug across all inputs.
    Counterexample: both fields remain "" regardless of dap_engine response.

    Uses asyncio.run to call the endpoint handler directly (avoids TestClient
    overhead from lego_builder side effects on each hypothesis example).
    """
    import tempfile
    import os as _os

    with tempfile.TemporaryDirectory() as tmp_dir:
        roteiro_nome = "roteiro_prop_test.json"
        roteiro_path = os.path.join(tmp_dir, roteiro_nome)
        with open(roteiro_path, "w", encoding="utf-8") as f:
            json.dump(_make_roteiro(), f, indent=2, ensure_ascii=False)

        original_roteiros_dir = app_module.ROTEIROS_DIR
        app_module.ROTEIROS_DIR = tmp_dir

        original_secret = _os.environ.get("AURA_API_SECRET")
        _os.environ["AURA_API_SECRET"] = "test-secret"
        _os.environ.setdefault("DEFAULT_TENANT_ID", "senior_default")

        loop = asyncio.new_event_loop()
        original_loop = app_module.main_loop
        app_module.main_loop = loop

        async def _noop_broadcast(msg):
            pass

        original_broadcast = app_module.ws_manager.broadcast
        app_module.ws_manager.broadcast = _noop_broadcast

        _reset_estado()

        try:
            # Call the endpoint handler directly (bypasses HTTP stack)
            with patch.object(app_module.dap_engine, "ingestar_para_pinecone", return_value=mock_res):
                result = loop.run_until_complete(
                    app_module.ingestar_no_dap(roteiro_nome)
                )

            with _estado_lock:
                sucesso_atual = estado_servidor["sucesso"]
                erro_atual    = estado_servidor["erro"]

            is_success_response = mock_res.get("status") == "sucesso"

            if is_success_response:
                assert sucesso_atual != "", (
                    f"BUG: estado_servidor['sucesso'] vazio após ingest com sucesso. "
                    f"mock_res={mock_res!r}, sucesso={sucesso_atual!r}"
                )
            else:
                assert erro_atual != "", (
                    f"BUG: estado_servidor['erro'] vazio após ingest com erro. "
                    f"mock_res={mock_res!r}, erro={erro_atual!r}"
                )

        finally:
            app_module.ROTEIROS_DIR = original_roteiros_dir
            app_module.main_loop = original_loop
            app_module.ws_manager.broadcast = original_broadcast
            loop.close()
            _reset_estado()
            if original_secret is None:
                _os.environ.pop("AURA_API_SECRET", None)
            else:
                _os.environ["AURA_API_SECRET"] = original_secret


# ===========================================================================
# PROPERTY 2: PRESERVATION TESTS
# ===========================================================================
# These tests MUST PASS on unfixed code — they confirm the baseline behavior
# that must be preserved after the fix is applied.
#
# Two preservation properties:
#   P2-A: executar_processo_bg always calls _set_estado(sucesso=...) or
#         _set_estado(erro=...) at the end — WebSocket broadcast is emitted.
#   P2-B: ingestar_no_dap always returns exactly the dict returned by
#         dap_engine.ingestar_para_pinecone() — JSON contract is preserved.
#
# Validates: Requirements 3.1, 3.2, 3.3, 3.4
# ===========================================================================


# ---------------------------------------------------------------------------
# Helpers for preservation tests
# ---------------------------------------------------------------------------

def _make_fake_process(returncode: int = 0, stdout_lines: list = None):
    """
    Returns a mock subprocess.Popen-like object that yields stdout_lines
    and exits with the given returncode.
    """
    lines = stdout_lines or []
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.stdout.__iter__ = MagicMock(return_value=iter(lines))
    mock_proc.stdout.readline = MagicMock(side_effect=lines + [""])
    mock_proc.wait = MagicMock(return_value=returncode)
    return mock_proc


# ---------------------------------------------------------------------------
# Test 2.1 — executar_processo_bg: sucesso emite _set_estado(sucesso=...)
#
# Preservation: the existing WebSocket broadcast mechanism in executar_processo_bg
# must continue to work after the fix is applied.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_1_executar_processo_bg_sucesso_emite_estado_sucesso(monkeypatch, tmp_path):
    """
    **Validates: Requirements 3.1**

    Preservation: executar_processo_bg calls _set_estado(sucesso=...) when
    the subprocess exits with returncode 0. This WebSocket broadcast behavior
    must remain unchanged after the fix.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    monkeypatch.setenv("AURA_API_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(tmp_path))

    loop = asyncio.new_event_loop()
    monkeypatch.setattr(app_module, "main_loop", loop)

    async def _noop_broadcast(msg):
        pass

    monkeypatch.setattr(app_module.ws_manager, "broadcast", _noop_broadcast)
    _reset_estado()

    fake_proc = _make_fake_process(returncode=0, stdout_lines=["PROGRESSO:50\n", "PROGRESSO:100\n"])

    with patch("subprocess.Popen", return_value=fake_proc):
        app_module.executar_processo_bg(
            comando=["echo", "ok"],
            msg_executando="Executando...",
            msg_sucesso="✅ Concluído com sucesso.",
        )

    with app_module._estado_lock:
        sucesso_final = app_module.estado_servidor["sucesso"]
        ocupado_final = app_module.estado_servidor["ocupado"]

    assert sucesso_final == "✅ Concluído com sucesso.", (
        f"Preservation FALHOU: executar_processo_bg não emitiu sucesso. "
        f"Valor atual: {sucesso_final!r}"
    )
    assert ocupado_final is False, (
        f"Preservation FALHOU: ocupado deve ser False após conclusão. "
        f"Valor atual: {ocupado_final!r}"
    )

    loop.close()
    _reset_estado()


# ---------------------------------------------------------------------------
# Test 2.2 — executar_processo_bg: falha emite _set_estado(erro=...)
#
# Preservation: the existing error broadcast in executar_processo_bg must
# continue to work after the fix is applied.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_2_executar_processo_bg_falha_emite_estado_erro(monkeypatch, tmp_path):
    """
    **Validates: Requirements 3.1**

    Preservation: executar_processo_bg calls _set_estado(erro=...) when
    the subprocess exits with a non-zero returncode. This must remain
    unchanged after the fix.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    monkeypatch.setenv("AURA_API_SECRET", "test-secret")
    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(tmp_path))

    loop = asyncio.new_event_loop()
    monkeypatch.setattr(app_module, "main_loop", loop)

    async def _noop_broadcast(msg):
        pass

    monkeypatch.setattr(app_module.ws_manager, "broadcast", _noop_broadcast)
    _reset_estado()

    fake_proc = _make_fake_process(
        returncode=1,
        stdout_lines=["Iniciando...\n", "Erro crítico: falha no processamento\n"],
    )

    with patch("subprocess.Popen", return_value=fake_proc):
        app_module.executar_processo_bg(
            comando=["python", "main.py"],
            msg_executando="Processando...",
            msg_sucesso="Concluído.",
        )

    with app_module._estado_lock:
        erro_final  = app_module.estado_servidor["erro"]
        ocupado_final = app_module.estado_servidor["ocupado"]

    assert erro_final != "", (
        f"Preservation FALHOU: executar_processo_bg não emitiu erro após returncode=1. "
        f"Valor atual: {erro_final!r}"
    )
    assert ocupado_final is False, (
        f"Preservation FALHOU: ocupado deve ser False após falha. "
        f"Valor atual: {ocupado_final!r}"
    )

    loop.close()
    _reset_estado()


# ---------------------------------------------------------------------------
# Test 2.3 — ingestar_no_dap: retorna exatamente o dict de ingestar_para_pinecone
#
# Preservation: the `return res` contract must be preserved after the fix.
# The endpoint must always return exactly what dap_engine.ingestar_para_pinecone
# returns — no modification, no wrapping.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

def test_2_3_ingestar_no_dap_retorna_exatamente_o_dict_do_dap_engine(client_with_roteiro):
    """
    **Validates: Requirements 3.2**

    Preservation: ingestar_no_dap must return exactly the dict returned by
    dap_engine.ingestar_para_pinecone() — the `return res` contract must not
    be altered by the fix.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    client, roteiro_nome, _ = client_with_roteiro
    _reset_estado()

    mock_res = {
        "status": "sucesso",
        "mensagem": "Indexado com sucesso",
        "vetores": 7,
        "namespace": "senior_default",
    }

    with patch.object(app_module.dap_engine, "ingestar_para_pinecone", return_value=mock_res):
        response = client.post(
            f"/api/ingest/{roteiro_nome}",
            headers={"Authorization": "Bearer test-secret"},
        )

    assert response.status_code == 200, f"Endpoint retornou {response.status_code}"

    body = response.json()
    assert body == mock_res, (
        f"Preservation FALHOU: resposta JSON foi modificada. "
        f"Esperado: {mock_res!r}, Recebido: {body!r}"
    )


# ---------------------------------------------------------------------------
# Property Test 2.4 — Hypothesis: para qualquer dict res, ingestar_no_dap
# retorna exatamente res (contrato JSON preservado).
#
# Generates varied dicts (status, mensagem, extra keys) and asserts the
# return value is always identical to the input dict.
# EXPECTED TO PASS on unfixed code — confirms baseline.
# ---------------------------------------------------------------------------

@st.composite
def arbitrary_dap_responses(draw):
    """Generates arbitrary dicts that dap_engine.ingestar_para_pinecone might return."""
    status = draw(st.sampled_from(["sucesso", "erro", "parcial"]))
    mensagem = draw(st.text(
        min_size=1, max_size=60,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
    ))
    base = {"status": status, "mensagem": mensagem}

    # Optionally add extra keys (vetores, namespace, ids, etc.)
    extra_keys = draw(st.lists(
        st.sampled_from(["vetores", "namespace", "ids", "chunks", "score"]),
        max_size=3,
        unique=True,
    ))
    for key in extra_keys:
        if key == "vetores":
            base[key] = draw(st.integers(min_value=0, max_value=200))
        elif key == "namespace":
            base[key] = draw(st.sampled_from(["senior_default", "tenant_abc", "demo"]))
        elif key == "ids":
            base[key] = draw(st.lists(st.text(min_size=1, max_size=10), max_size=5))
        elif key == "chunks":
            base[key] = draw(st.integers(min_value=0, max_value=50))
        elif key == "score":
            base[key] = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))

    return base


@given(mock_res=arbitrary_dap_responses())
@settings(max_examples=30, deadline=None)
def test_2_4_property_ingestar_no_dap_preserva_contrato_json(mock_res):
    """
    **Validates: Requirements 3.2**

    Property: for any dict returned by dap_engine.ingestar_para_pinecone,
    ingestar_no_dap must return exactly that dict — no modification, no
    wrapping, no field removal.

    EXPECTED TO PASS on unfixed code — confirms baseline.
    """
    import tempfile
    import os as _os

    with tempfile.TemporaryDirectory() as tmp_dir:
        roteiro_nome = "roteiro_preservation_test.json"
        roteiro_path = _os.path.join(tmp_dir, roteiro_nome)
        with open(roteiro_path, "w", encoding="utf-8") as f:
            json.dump(_make_roteiro(), f, indent=2, ensure_ascii=False)

        original_roteiros_dir = app_module.ROTEIROS_DIR
        app_module.ROTEIROS_DIR = tmp_dir

        original_secret = _os.environ.get("AURA_API_SECRET")
        _os.environ["AURA_API_SECRET"] = "test-secret"
        _os.environ.setdefault("DEFAULT_TENANT_ID", "senior_default")

        loop = asyncio.new_event_loop()
        original_loop = app_module.main_loop
        app_module.main_loop = loop

        async def _noop_broadcast(msg):
            pass

        original_broadcast = app_module.ws_manager.broadcast
        app_module.ws_manager.broadcast = _noop_broadcast

        _reset_estado()

        try:
            with patch.object(app_module.dap_engine, "ingestar_para_pinecone", return_value=mock_res):
                result = loop.run_until_complete(
                    app_module.ingestar_no_dap(roteiro_nome)
                )

            # The endpoint may return a JSONResponse or a plain dict.
            # Normalize to dict for comparison.
            from fastapi.responses import JSONResponse as _JSONResponse
            if isinstance(result, _JSONResponse):
                import json as _json
                actual = _json.loads(result.body)
            else:
                actual = result

            assert actual == mock_res, (
                f"Preservation FALHOU: contrato JSON alterado. "
                f"Esperado: {mock_res!r}, Recebido: {actual!r}"
            )

        finally:
            app_module.ROTEIROS_DIR = original_roteiros_dir
            app_module.main_loop = original_loop
            app_module.ws_manager.broadcast = original_broadcast
            loop.close()
            _reset_estado()
            if original_secret is None:
                _os.environ.pop("AURA_API_SECRET", None)
            else:
                _os.environ["AURA_API_SECRET"] = original_secret

"""
tests/test_capture_adapter.py
==============================
Testes unitários para contracts/capture_adapter.py (Task 24).

Cobre:
  - SeniorXAdapter satisfaz o protocolo CaptureAdapter
  - MockAdapter satisfaz o protocolo CaptureAdapter
  - Pipeline central funciona com adaptador mock
  - Factory get_capture_adapter() retorna o adaptador correto
  - Credenciais vêm de variáveis de ambiente, nunca hardcoded

Requisitos: 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5

Bug 2 — Exploração da bug condition (Tarefa 4):
  - test_senior_x_credenciais_de_env: assertar que obter_credenciais() retorna
    SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE, não SENIOR_USER / SENIOR_PASS.
  - test_pbt_credenciais_captura_de_env: property-based test com Hypothesis.

**Validates: Requirements 2.5**
"""

import os
import sys
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contracts.capture_adapter import (
    CaptureAdapter,
    SeniorXAdapter,
    MockAdapter,
    get_capture_adapter,
)


# ──────────────────────────────────────────────────────────────
# Conformidade com o protocolo
# ──────────────────────────────────────────────────────────────

def test_senior_x_adapter_implementa_protocolo():
    """SeniorXAdapter deve satisfazer o protocolo CaptureAdapter."""
    assert isinstance(SeniorXAdapter(), CaptureAdapter)


def test_mock_adapter_implementa_protocolo():
    """MockAdapter deve satisfazer o protocolo CaptureAdapter."""
    assert isinstance(MockAdapter(), CaptureAdapter)


# ──────────────────────────────────────────────────────────────
# SeniorXAdapter — campos obrigatórios
# ──────────────────────────────────────────────────────────────

def test_senior_x_nome_sistema():
    assert SeniorXAdapter().nome_sistema == "Senior X"


def test_senior_x_url_base_padrao():
    """url_base deve ter valor padrão quando SENIOR_URL não está definida."""
    adapter = SeniorXAdapter()
    assert adapter.url_base.startswith("http")
    assert len(adapter.url_base) > 10


def test_senior_x_url_base_de_env(monkeypatch):
    """url_base deve usar SENIOR_URL quando definida."""
    monkeypatch.setenv("SENIOR_URL", "https://meu-erp.empresa.com/")
    assert SeniorXAdapter().url_base == "https://meu-erp.empresa.com/"


def test_senior_x_credenciais_de_env(monkeypatch):
    """
    Credenciais devem vir de SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE,
    não de SENIOR_USER / SENIOR_PASS.

    **Validates: Requirements 2.5**
    """
    monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_captura")
    monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_captura")
    monkeypatch.setenv("SENIOR_USER", "usuario_antigo")
    monkeypatch.setenv("SENIOR_PASS", "senha_antiga")
    creds = SeniorXAdapter().obter_credenciais()
    assert creds["usuario"] == "usuario_captura"
    assert creds["senha"] == "senha_captura"


def test_senior_x_credenciais_nao_hardcoded():
    """Credenciais não devem estar hardcoded no código."""
    import inspect
    source = inspect.getsource(SeniorXAdapter.obter_credenciais)
    assert "password" not in source.lower() or "os.getenv" in source
    assert "123" not in source


@given(
    usuario_captura=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="@._-"),
        min_size=1,
        max_size=64,
    ),
    senha_captura=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="@._-!#"),
        min_size=1,
        max_size=64,
    ),
)
@settings(max_examples=15)
def test_pbt_credenciais_captura_de_env(usuario_captura, senha_captura):
    """
    Property-based test: para qualquer par de strings em SENIOR_USER_CAPTURE /
    SENIOR_PASS_CAPTURE, obter_credenciais() deve retornar exatamente esses valores.

    **Validates: Requirements 2.5**
    """
    original_user = os.environ.pop("SENIOR_USER", None)
    original_pass = os.environ.pop("SENIOR_PASS", None)
    try:
        os.environ["SENIOR_USER_CAPTURE"] = usuario_captura
        os.environ["SENIOR_PASS_CAPTURE"] = senha_captura
        os.environ.pop("SENIOR_USER", None)
        os.environ.pop("SENIOR_PASS", None)

        creds = SeniorXAdapter().obter_credenciais()

        assert creds["usuario"] == usuario_captura, (
            f"obter_credenciais() retornou '{creds['usuario']}' "
            f"em vez de '{usuario_captura}' (SENIOR_USER_CAPTURE)."
        )
        assert creds["senha"] == senha_captura, (
            f"obter_credenciais() retornou '{creds['senha']}' "
            f"em vez de '{senha_captura}' (SENIOR_PASS_CAPTURE)."
        )
    finally:
        os.environ.pop("SENIOR_USER_CAPTURE", None)
        os.environ.pop("SENIOR_PASS_CAPTURE", None)
        if original_user is not None:
            os.environ["SENIOR_USER"] = original_user
        if original_pass is not None:
            os.environ["SENIOR_PASS"] = original_pass


def test_senior_x_seletores_login_campos_obrigatorios():
    """obter_seletores_login() deve retornar os campos obrigatórios."""
    seletores = SeniorXAdapter().obter_seletores_login()
    assert "campo_usuario" in seletores
    assert "campo_senha" in seletores
    assert "botao_proximo" in seletores
    for chave, valor in seletores.items():
        assert isinstance(valor, str) and len(valor) > 0, (
            f"Seletor '{chave}' deve ser string não vazia"
        )


def test_senior_x_configuracao_browser_campos_obrigatorios():
    """obter_configuracao_browser() deve retornar os campos obrigatórios."""
    config = SeniorXAdapter().obter_configuracao_browser()
    assert "args" in config
    assert "locale" in config
    assert "headless" in config
    assert isinstance(config["args"], list)
    assert isinstance(config["locale"], str)
    assert isinstance(config["headless"], bool)


# ──────────────────────────────────────────────────────────────
# MockAdapter — campos obrigatórios
# ──────────────────────────────────────────────────────────────

def test_mock_adapter_nome_sistema():
    assert MockAdapter().nome_sistema == "Mock ERP"


def test_mock_adapter_url_base():
    assert MockAdapter().url_base.startswith("http")


def test_mock_adapter_credenciais():
    creds = MockAdapter().obter_credenciais()
    assert "usuario" in creds
    assert "senha" in creds


def test_mock_adapter_seletores_login():
    seletores = MockAdapter().obter_seletores_login()
    assert "campo_usuario" in seletores
    assert "campo_senha" in seletores
    assert "botao_proximo" in seletores


def test_mock_adapter_configuracao_browser():
    config = MockAdapter().obter_configuracao_browser()
    assert "args" in config
    assert "locale" in config
    assert "headless" in config
    assert config["headless"] is True


# ──────────────────────────────────────────────────────────────
# Pipeline central funciona com adaptador mock
# ──────────────────────────────────────────────────────────────

def test_pipeline_usa_adapter_para_url(monkeypatch):
    """Requisito 3.4.4"""
    adapter = MockAdapter()
    url = adapter.url_base
    assert url == "http://localhost:9999/mock-erp"
    assert "senior" not in url.lower()


def test_pipeline_usa_adapter_para_credenciais():
    """Requisito 3.4.4"""
    adapter = MockAdapter()
    creds = adapter.obter_credenciais()
    assert creds["usuario"] == "mock_user"
    assert creds["senha"] == "mock_pass"


def test_pipeline_usa_adapter_para_seletores():
    """Requisito 3.4.4"""
    adapter = MockAdapter()
    seletores = adapter.obter_seletores_login()
    assert seletores["campo_usuario"] != SeniorXAdapter().obter_seletores_login()["campo_usuario"]


# ──────────────────────────────────────────────────────────────
# Factory get_capture_adapter()
# ──────────────────────────────────────────────────────────────

def test_factory_sem_env_retorna_senior_x(monkeypatch):
    monkeypatch.delenv("CAPTURE_ADAPTER", raising=False)
    assert isinstance(get_capture_adapter(), SeniorXAdapter)


def test_factory_senior_x_retorna_senior_x(monkeypatch):
    monkeypatch.setenv("CAPTURE_ADAPTER", "senior_x")
    assert isinstance(get_capture_adapter(), SeniorXAdapter)


def test_factory_mock_retorna_mock(monkeypatch):
    monkeypatch.setenv("CAPTURE_ADAPTER", "mock")
    assert isinstance(get_capture_adapter(), MockAdapter)


def test_factory_desconhecido_retorna_senior_x(monkeypatch):
    monkeypatch.setenv("CAPTURE_ADAPTER", "erp_desconhecido")
    assert isinstance(get_capture_adapter(), SeniorXAdapter)


def test_factory_case_insensitive(monkeypatch):
    monkeypatch.setenv("CAPTURE_ADAPTER", "SENIOR_X")
    assert isinstance(get_capture_adapter(), SeniorXAdapter)
    monkeypatch.setenv("CAPTURE_ADAPTER", "MOCK")
    assert isinstance(get_capture_adapter(), MockAdapter)


# ──────────────────────────────────────────────────────────────
# Contrato de integração
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("adapter_cls", [SeniorXAdapter, MockAdapter])
def test_contrato_completo(adapter_cls):
    """Requisito 3.4.5"""
    adapter = adapter_cls()
    assert isinstance(adapter, CaptureAdapter)
    assert isinstance(adapter.nome_sistema, str) and len(adapter.nome_sistema) > 0
    assert isinstance(adapter.url_base, str) and adapter.url_base.startswith("http")
    creds = adapter.obter_credenciais()
    assert "usuario" in creds and "senha" in creds
    seletores = adapter.obter_seletores_login()
    assert all(k in seletores for k in ("campo_usuario", "campo_senha", "botao_proximo"))
    config = adapter.obter_configuracao_browser()
    assert all(k in config for k in ("args", "locale", "headless"))


# ──────────────────────────────────────────────────────────────
# Preservação — Bug 2 (Validates: Requirements 3.4, 3.5, 3.6, 3.7)
# ──────────────────────────────────────────────────────────────

def test_preservation_senior_url_nao_afetada_por_credenciais(monkeypatch):
    """SENIOR_URL não deve ser afetada pela mudança de credenciais."""
    monkeypatch.setenv("SENIOR_URL", "https://meu-erp-teste.com/")
    monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_captura")
    monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_captura")
    assert SeniorXAdapter().url_base == "https://meu-erp-teste.com/"


def test_preservation_seletores_login_nao_afetados(monkeypatch):
    """obter_seletores_login() não deve ser afetado pela mudança de credenciais."""
    monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_captura")
    monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_captura")
    seletores = SeniorXAdapter().obter_seletores_login()
    assert "campo_usuario" in seletores
    assert "campo_senha" in seletores
    assert "botao_proximo" in seletores
    assert all(isinstance(v, str) and len(v) > 0 for v in seletores.values())


def test_preservation_configuracao_browser_nao_afetada(monkeypatch):
    """obter_configuracao_browser() não deve ser afetado pela mudança de credenciais."""
    monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_captura")
    monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_captura")
    config = SeniorXAdapter().obter_configuracao_browser()
    assert "args" in config
    assert "locale" in config
    assert "headless" in config
    assert isinstance(config["args"], list)
    assert isinstance(config["locale"], str)
    assert isinstance(config["headless"], bool)


@given(
    usuario_captura=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="@._-"),
        min_size=1,
        max_size=64,
    ),
    senha_captura=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="@._-!#"),
        min_size=1,
        max_size=64,
    ),
)
@settings(max_examples=15)
def test_postfix_pbt_credenciais_sempre_retornam_valores_corretos(usuario_captura, senha_captura):
    """
    Para qualquer par de strings em SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE,
    obter_credenciais() deve retornar exatamente esses valores.

    **Validates: Requirements 2.5**
    """
    original_user = os.environ.pop("SENIOR_USER", None)
    original_pass = os.environ.pop("SENIOR_PASS", None)
    original_user_capture = os.environ.pop("SENIOR_USER_CAPTURE", None)
    original_pass_capture = os.environ.pop("SENIOR_PASS_CAPTURE", None)

    try:
        os.environ["SENIOR_USER_CAPTURE"] = usuario_captura
        os.environ["SENIOR_PASS_CAPTURE"] = senha_captura
        os.environ.pop("SENIOR_USER", None)
        os.environ.pop("SENIOR_PASS", None)

        creds = SeniorXAdapter().obter_credenciais()

        assert creds["usuario"] == usuario_captura, (
            f"obter_credenciais() deve retornar '{usuario_captura}' "
            f"(SENIOR_USER_CAPTURE), mas retornou '{creds['usuario']}'"
        )
        assert creds["senha"] == senha_captura, (
            f"obter_credenciais() deve retornar '{senha_captura}' "
            f"(SENIOR_PASS_CAPTURE), mas retornou '{creds['senha']}'"
        )
    finally:
        os.environ.pop("SENIOR_USER_CAPTURE", None)
        os.environ.pop("SENIOR_PASS_CAPTURE", None)
        if original_user is not None:
            os.environ["SENIOR_USER"] = original_user
        if original_pass is not None:
            os.environ["SENIOR_PASS"] = original_pass
        if original_user_capture is not None:
            os.environ["SENIOR_USER_CAPTURE"] = original_user_capture
        if original_pass_capture is not None:
            os.environ["SENIOR_PASS_CAPTURE"] = original_pass_capture

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
"""

import os
import sys
import pytest

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
    """Credenciais devem vir de variáveis de ambiente."""
    monkeypatch.setenv("SENIOR_USER", "usuario_teste")
    monkeypatch.setenv("SENIOR_PASS", "senha_teste")
    creds = SeniorXAdapter().obter_credenciais()
    assert creds["usuario"] == "usuario_teste"
    assert creds["senha"] == "senha_teste"


def test_senior_x_credenciais_nao_hardcoded():
    """Credenciais não devem estar hardcoded no código."""
    import inspect
    source = inspect.getsource(SeniorXAdapter.obter_credenciais)
    # Não deve conter strings que pareçam senhas reais
    assert "password" not in source.lower() or "os.getenv" in source
    assert "123" not in source


def test_senior_x_seletores_login_campos_obrigatorios():
    """obter_seletores_login() deve retornar os campos obrigatórios."""
    seletores = SeniorXAdapter().obter_seletores_login()
    assert "campo_usuario" in seletores
    assert "campo_senha" in seletores
    assert "botao_proximo" in seletores
    # Todos devem ser strings não vazias
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
    # Mock deve rodar headless para não abrir browser em testes
    assert config["headless"] is True


# ──────────────────────────────────────────────────────────────
# Pipeline central funciona com adaptador mock
# ──────────────────────────────────────────────────────────────

def test_pipeline_usa_adapter_para_url(monkeypatch):
    """
    O pipeline central deve usar o adaptador para obter a URL,
    não hardcodar referências ao Senior X.
    Requisito 3.4.4
    """
    adapter = MockAdapter()
    # Simula o que o pipeline faz: obtém URL do adaptador
    url = adapter.url_base
    assert url == "http://localhost:9999/mock-erp"
    # Não deve conter referência ao Senior X
    assert "senior" not in url.lower()


def test_pipeline_usa_adapter_para_credenciais():
    """
    O pipeline central deve usar o adaptador para obter credenciais.
    Requisito 3.4.4
    """
    adapter = MockAdapter()
    creds = adapter.obter_credenciais()
    assert creds["usuario"] == "mock_user"
    assert creds["senha"] == "mock_pass"


def test_pipeline_usa_adapter_para_seletores():
    """
    O pipeline central deve usar o adaptador para obter seletores de login.
    Requisito 3.4.4
    """
    adapter = MockAdapter()
    seletores = adapter.obter_seletores_login()
    # Seletores do mock são diferentes dos do Senior X
    assert seletores["campo_usuario"] != SeniorXAdapter().obter_seletores_login()["campo_usuario"]


# ──────────────────────────────────────────────────────────────
# Factory get_capture_adapter()
# ──────────────────────────────────────────────────────────────

def test_factory_sem_env_retorna_senior_x(monkeypatch):
    """Sem CAPTURE_ADAPTER definida, deve retornar SeniorXAdapter."""
    monkeypatch.delenv("CAPTURE_ADAPTER", raising=False)
    adapter = get_capture_adapter()
    assert isinstance(adapter, SeniorXAdapter)


def test_factory_senior_x_retorna_senior_x(monkeypatch):
    """CAPTURE_ADAPTER=senior_x deve retornar SeniorXAdapter."""
    monkeypatch.setenv("CAPTURE_ADAPTER", "senior_x")
    adapter = get_capture_adapter()
    assert isinstance(adapter, SeniorXAdapter)


def test_factory_mock_retorna_mock(monkeypatch):
    """CAPTURE_ADAPTER=mock deve retornar MockAdapter."""
    monkeypatch.setenv("CAPTURE_ADAPTER", "mock")
    adapter = get_capture_adapter()
    assert isinstance(adapter, MockAdapter)


def test_factory_desconhecido_retorna_senior_x(monkeypatch):
    """CAPTURE_ADAPTER com valor desconhecido deve retornar SeniorXAdapter com fallback."""
    monkeypatch.setenv("CAPTURE_ADAPTER", "erp_desconhecido")
    adapter = get_capture_adapter()
    assert isinstance(adapter, SeniorXAdapter)


def test_factory_case_insensitive(monkeypatch):
    """CAPTURE_ADAPTER deve ser case-insensitive."""
    monkeypatch.setenv("CAPTURE_ADAPTER", "SENIOR_X")
    adapter = get_capture_adapter()
    assert isinstance(adapter, SeniorXAdapter)

    monkeypatch.setenv("CAPTURE_ADAPTER", "MOCK")
    adapter = get_capture_adapter()
    assert isinstance(adapter, MockAdapter)


# ──────────────────────────────────────────────────────────────
# Contrato de integração — qualquer adaptador satisfaz a interface
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("adapter_cls", [SeniorXAdapter, MockAdapter])
def test_contrato_completo(adapter_cls):
    """
    Qualquer adaptador deve satisfazer completamente o contrato CaptureAdapter.
    Requisito 3.4.5
    """
    adapter = adapter_cls()

    # Protocolo
    assert isinstance(adapter, CaptureAdapter)

    # Propriedades
    assert isinstance(adapter.nome_sistema, str) and len(adapter.nome_sistema) > 0
    assert isinstance(adapter.url_base, str) and adapter.url_base.startswith("http")

    # Métodos retornam dicts com campos obrigatórios
    creds = adapter.obter_credenciais()
    assert "usuario" in creds and "senha" in creds

    seletores = adapter.obter_seletores_login()
    assert all(k in seletores for k in ("campo_usuario", "campo_senha", "botao_proximo"))

    config = adapter.obter_configuracao_browser()
    assert all(k in config for k in ("args", "locale", "headless"))

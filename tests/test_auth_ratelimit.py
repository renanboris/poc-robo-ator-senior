"""
tests/test_auth_ratelimit.py — Autenticação e Rate Limiting

Feature: training-os-roadmap
Task 18: Implementar autenticação e rate limiting
**Validates: Requirements NFR-1.1, NFR-1.2, NFR-1.3, NFR-1.4, NFR-1.5**

Testa diretamente as funções `verificar_rate_limit()` e `verificar_token()` de app.py,
sem subir servidor HTTP.
"""

import os
import time
import unittest.mock as mock

import pytest

# Pula graciosamente se fastapi não estiver instalado no ambiente de teste
pytest.importorskip("fastapi", reason="fastapi não instalado — testes de auth/rate-limit ignorados")

from fastapi import HTTPException
from hypothesis import given, settings
from hypothesis import strategies as st

# Importa as funções e o cache diretamente de app
import app as app_module
from app import _rate_limit_cache, verificar_rate_limit, verificar_token

# ---------------------------------------------------------------------------
# Fixture: limpa o cache entre testes para evitar contaminação
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def limpar_cache():
    """Garante que _rate_limit_cache está vazio antes e depois de cada teste."""
    _rate_limit_cache.clear()
    yield
    _rate_limit_cache.clear()


# ---------------------------------------------------------------------------
# Testes unitários — verificar_rate_limit()
# ---------------------------------------------------------------------------

def test_rate_limit_menos_de_20_requisicoes_nao_lanca_excecao():
    """
    verificar_rate_limit() com menos de 20 req não lança exceção.
    Validates: NFR-1.4
    """
    ip = "192.168.1.1"
    for _ in range(20):
        # Nenhuma das 20 primeiras deve lançar
        verificar_rate_limit(ip)


def test_rate_limit_21a_requisicao_lanca_http_429():
    """
    verificar_rate_limit() com 21ª req lança HTTPException 429.
    Validates: NFR-1.4, NFR-1.5
    """
    ip = "10.0.0.1"
    for _ in range(20):
        verificar_rate_limit(ip)

    with pytest.raises(HTTPException) as exc_info:
        verificar_rate_limit(ip)

    assert exc_info.value.status_code == 429


def test_rate_limit_reseta_apos_60_segundos():
    """
    verificar_rate_limit() reseta após 60 segundos (mock de time.time).
    Validates: NFR-1.4
    """
    ip = "172.16.0.1"
    tempo_base = 1_000_000.0

    # Simula 20 requisições no tempo base
    with mock.patch("app.time") as mock_time:
        mock_time.time.return_value = tempo_base
        for _ in range(20):
            verificar_rate_limit(ip)

        # 21ª no mesmo instante deve falhar
        with pytest.raises(HTTPException) as exc_info:
            verificar_rate_limit(ip)
        assert exc_info.value.status_code == 429

        # Avança 61 segundos — janela expirada
        mock_time.time.return_value = tempo_base + 61.0

        # Agora deve aceitar novamente (sem lançar)
        verificar_rate_limit(ip)


def test_rate_limit_ips_distintos_sao_independentes():
    """
    Cada IP tem seu próprio contador — esgotar um não afeta outro.
    Validates: NFR-1.4
    """
    ip_a = "1.1.1.1"
    ip_b = "2.2.2.2"

    for _ in range(20):
        verificar_rate_limit(ip_a)

    # ip_a está no limite, ip_b ainda não
    with pytest.raises(HTTPException):
        verificar_rate_limit(ip_a)

    # ip_b deve funcionar normalmente
    verificar_rate_limit(ip_b)


# ---------------------------------------------------------------------------
# Testes unitários — verificar_token()
# ---------------------------------------------------------------------------

def test_verificar_token_valido_nao_lanca_excecao():
    """
    verificar_token() com token válido não lança exceção.
    Validates: NFR-1.1, NFR-1.2
    """
    with mock.patch.dict(os.environ, {"AURA_API_SECRET": "meu-segredo"}):
        resultado = verificar_token("Bearer meu-segredo")
    assert resultado == "Bearer meu-segredo"


def test_verificar_token_invalido_lanca_http_401():
    """
    verificar_token() com token inválido lança HTTPException 401.
    Validates: NFR-1.1, NFR-1.3
    """
    with mock.patch.dict(os.environ, {"AURA_API_SECRET": "meu-segredo"}):
        with pytest.raises(HTTPException) as exc_info:
            verificar_token("Bearer token-errado")
    assert exc_info.value.status_code == 401


def test_verificar_token_ausente_lanca_http_401():
    """
    verificar_token() sem token lança HTTPException 401.
    Validates: NFR-1.1, NFR-1.3
    """
    with mock.patch.dict(os.environ, {"AURA_API_SECRET": "meu-segredo"}):
        with pytest.raises(HTTPException) as exc_info:
            verificar_token(None)
    assert exc_info.value.status_code == 401


def test_verificar_token_string_vazia_lanca_http_401():
    """
    verificar_token() com string vazia lança HTTPException 401.
    Validates: NFR-1.1, NFR-1.3
    """
    with mock.patch.dict(os.environ, {"AURA_API_SECRET": "meu-segredo"}):
        with pytest.raises(HTTPException) as exc_info:
            verificar_token("")
    assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# Property 15: Rate limiting por IP
# ---------------------------------------------------------------------------

@given(
    ip=st.from_regex(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", fullmatch=True),
    requisicoes_extras=st.integers(min_value=1, max_value=20),
)
@settings(max_examples=30)
def test_property_15_rate_limiting_por_ip(ip, requisicoes_extras):
    """
    **Property 15: Rate limiting por IP**
    **Validates: Requirements NFR-1.4**

    Para qualquer IP que faça mais de 20 requisições em 60 segundos,
    verificar que a 21ª retorna HTTP 429.

    Usa mock de time.time para manter todas as requisições dentro da janela de 60s.
    """
    _rate_limit_cache.clear()

    tempo_fixo = 2_000_000.0

    with mock.patch("app.time") as mock_time:
        mock_time.time.return_value = tempo_fixo

        # Faz exatamente 20 requisições — todas devem passar
        for i in range(20):
            verificar_rate_limit(ip)

        # A 21ª deve ser bloqueada com 429
        with pytest.raises(HTTPException) as exc_info:
            verificar_rate_limit(ip)

        assert exc_info.value.status_code == 429, (
            f"IP {ip}: esperado HTTP 429 na 21ª requisição, "
            f"obteve {exc_info.value.status_code}"
        )

        # Requisições adicionais (extras) também devem retornar 429
        for _ in range(requisicoes_extras):
            with pytest.raises(HTTPException) as exc_extra:
                verificar_rate_limit(ip)
            assert exc_extra.value.status_code == 429

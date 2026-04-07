"""
tests/test_brain_backend.py
============================
Testes unitários para brain_backend.py (Task 14).

Cobre:
  - set + get round-trip
  - query por tenant (isolamento)
  - modo degradado quando DB indisponível (NullBrainBackend)
  - seletor frágil não é persistido
  - memória obsoleta é apagada ao consultar

Requisitos: 2.4.1, 2.4.2, 2.4.4
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import brain_backend
from brain_backend import (
    SQLiteBrainBackend,
    NullBrainBackend,
    EntradaBrain,
    BrainBackend,
    MAX_FALHAS_CACHE,
)


# ──────────────────────────────────────────────────────────────
# Fixture: banco isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def backend(tmp_path):
    """SQLiteBrainBackend com banco temporário isolado por teste."""
    db = str(tmp_path / "brain_test.db")
    return SQLiteBrainBackend(db_path=db)


# ──────────────────────────────────────────────────────────────
# Conformidade com o protocolo
# ──────────────────────────────────────────────────────────────

def test_sqlite_backend_implementa_protocolo(backend):
    assert isinstance(backend, BrainBackend)


def test_null_backend_implementa_protocolo():
    assert isinstance(NullBrainBackend(), BrainBackend)


# ──────────────────────────────────────────────────────────────
# set + get round-trip
# ──────────────────────────────────────────────────────────────

def test_set_get_roundtrip(backend):
    """set() seguido de get() deve retornar a entrada corretamente."""
    entrada = EntradaBrain(
        intencao="Clicar no botão Salvar",
        seletor="[aria-label='Salvar']",
        tenant_id="tenant_a",
    )
    backend.set(entrada)
    resultado = backend.get("Clicar no botão Salvar", tenant_id="tenant_a")

    assert resultado is not None
    assert resultado.intencao == "Clicar no botão Salvar"
    assert resultado.seletor == "[aria-label='Salvar']"
    assert resultado.tenant_id == "tenant_a"
    assert resultado.hits >= 1


def test_get_retorna_none_para_intencao_inexistente(backend):
    resultado = backend.get("intencao que nao existe", tenant_id="t1")
    assert resultado is None


def test_set_incrementa_hits_em_atualizacao(backend):
    """Chamar set() múltiplas vezes deve incrementar hits."""
    e = EntradaBrain(intencao="Abrir menu", seletor="[aria-label='Menu']", tenant_id="t1")
    backend.set(e)
    backend.set(e)
    backend.set(e)
    resultado = backend.get("Abrir menu", tenant_id="t1")
    assert resultado.hits == 3


def test_set_com_coords(backend):
    """set() deve persistir e get() deve recuperar coordenadas."""
    e = EntradaBrain(
        intencao="Ícone de pesquisa",
        coords={"x_pct": 0.9, "y_pct": 0.05},
        tenant_id="t1",
    )
    backend.set(e)
    resultado = backend.get("Ícone de pesquisa", tenant_id="t1")
    assert resultado.coords == {"x_pct": 0.9, "y_pct": 0.05}


def test_seletor_fragil_nao_persistido(backend):
    """Seletores que não começam com prefixos válidos não devem ser salvos."""
    e = EntradaBrain(
        intencao="Clicar em span",
        seletor="span.alguma-classe",
        tenant_id="t1",
    )
    backend.set(e)
    resultado = backend.get("Clicar em span", tenant_id="t1")
    assert resultado is not None
    assert resultado.seletor is None


def test_memoria_obsoleta_apagada(backend):
    """Entrada com falhas_consecutivas >= MAX_FALHAS_CACHE deve ser apagada ao consultar."""
    import sqlite3
    e = EntradaBrain(intencao="Ação obsoleta", seletor="[aria-label='X']", tenant_id="t1")
    backend.set(e)

    # Força falhas ao limite
    with sqlite3.connect(backend.db_path) as conn:
        conn.execute(
            "UPDATE memoria_semantica SET falhas_consecutivas = ? WHERE intencao = ?",
            (MAX_FALHAS_CACHE, "Ação obsoleta"),
        )

    resultado = backend.get("Ação obsoleta", tenant_id="t1")
    assert resultado is None


# ──────────────────────────────────────────────────────────────
# query por tenant — isolamento
# ──────────────────────────────────────────────────────────────

def test_query_retorna_apenas_do_tenant(backend):
    """query() deve retornar apenas entradas do tenant especificado."""
    backend.set(EntradaBrain(intencao="Ação A", seletor="[aria-label='A']", tenant_id="tenant_a"))
    backend.set(EntradaBrain(intencao="Ação B", seletor="[aria-label='B']", tenant_id="tenant_b"))

    resultado_a = backend.query("tenant_a")
    resultado_b = backend.query("tenant_b")

    assert all(e.tenant_id == "tenant_a" for e in resultado_a)
    assert all(e.tenant_id == "tenant_b" for e in resultado_b)
    assert len(resultado_a) == 1
    assert len(resultado_b) == 1


def test_query_tenant_sem_entradas_retorna_lista_vazia(backend):
    resultado = backend.query("tenant_sem_dados")
    assert resultado == []


def test_isolamento_entre_tenants(backend):
    """Entrada gravada para tenant A não deve aparecer em consultas do tenant B."""
    backend.set(EntradaBrain(intencao="Segredo do tenant A", seletor="[id='secret']", tenant_id="tenant_a"))
    resultado_b = backend.query("tenant_b")
    intencoes_b = [e.intencao for e in resultado_b]
    assert "Segredo do tenant A" not in intencoes_b


def test_get_nao_retorna_entrada_de_outro_tenant(backend):
    """get() com tenant_id diferente não deve retornar entrada de outro tenant."""
    backend.set(EntradaBrain(intencao="Ação compartilhada", seletor="[aria-label='X']", tenant_id="tenant_a"))
    resultado = backend.get("Ação compartilhada", tenant_id="tenant_b")
    assert resultado is None


# ──────────────────────────────────────────────────────────────
# NullBrainBackend — modo degradado
# ──────────────────────────────────────────────────────────────

def test_null_backend_get_retorna_none():
    nb = NullBrainBackend()
    assert nb.get("qualquer coisa") is None


def test_null_backend_set_nao_lanca_excecao():
    nb = NullBrainBackend()
    nb.set(EntradaBrain(intencao="teste"))  # não deve lançar


def test_null_backend_query_retorna_lista_vazia():
    nb = NullBrainBackend()
    assert nb.query("qualquer_tenant") == []


# ──────────────────────────────────────────────────────────────
# get_brain_backend factory
# ──────────────────────────────────────────────────────────────

def test_factory_sem_env_retorna_sqlite(monkeypatch):
    monkeypatch.delenv("BRAIN_BACKEND_URL", raising=False)
    b = brain_backend.get_brain_backend()
    assert isinstance(b, SQLiteBrainBackend)


def test_factory_com_env_retorna_null(monkeypatch):
    monkeypatch.setenv("BRAIN_BACKEND_URL", "http://remote-brain:8080")
    b = brain_backend.get_brain_backend()
    assert isinstance(b, NullBrainBackend)

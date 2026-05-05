"""
tests/test_vision_engine.py — Testes de regressão para vision_engine.py
Requisitos: 1.3.6

Testa o Brain (SQLite) com DB temporário via monkeypatch.
Não requer Playwright nem browser.
"""
import json
import os
import sqlite3

import pytest

import vision_engine


@pytest.fixture(autouse=True)
def brain_temporario(tmp_path, monkeypatch):
    """Redireciona o Brain para um banco SQLite temporário em cada teste."""
    db_temp = str(tmp_path / "brain_test.db")
    monkeypatch.setattr(vision_engine, "DB_PATH", db_temp)
    vision_engine._init_db()
    yield db_temp


# ──────────────────────────────────────────────────────────────
# Testes do Brain (cache semântico)
# ──────────────────────────────────────────────────────────────

def test_consultar_cache_retorna_none_quando_vazio():
    """Brain vazio deve retornar None para qualquer intenção."""
    resultado = vision_engine._consultar_cache("Acessar menu principal")
    assert resultado is None


def test_registrar_e_consultar_sucesso_cache():
    """Após registrar sucesso, o Brain deve retornar a entrada corretamente."""
    intencao = "Clicar no botão Salvar"
    seletor = "[aria-label='Salvar']"

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)
    entrada = vision_engine._consultar_cache(intencao)

    assert entrada is not None
    assert entrada.seletor == seletor
    assert entrada.hits >= 1


def test_registrar_sucesso_incrementa_hits():
    """Registrar sucesso múltiplas vezes deve incrementar o contador de hits."""
    intencao = "Abrir relatório"
    seletor = "[data-testid='btn-relatorio']"

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)
    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)
    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)

    entrada = vision_engine._consultar_cache(intencao)
    assert entrada is not None
    assert entrada.hits == 3


def test_registrar_falha_incrementa_falhas_consecutivas():
    """Registrar falha deve incrementar falhas_consecutivas."""
    intencao = "Fechar modal"
    seletor = "[aria-label='Fechar']"

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)
    vision_engine._registrar_falha_cache(intencao)

    db_path = vision_engine.DB_PATH
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT falhas_consecutivas FROM memoria_semantica WHERE intencao = ?",
            (intencao,),
        ).fetchone()

    assert row is not None
    assert row[0] == 1


def test_memoria_obsoleta_apagada_apos_max_falhas():
    """Memória com falhas_consecutivas >= MAX_FALHAS_CACHE deve ser apagada ao consultar."""
    intencao = "Navegar para configurações"
    seletor = "[aria-label='Configurações']"

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)

    # Força falhas_consecutivas ao limite máximo diretamente no DB
    db_path = vision_engine.DB_PATH
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE memoria_semantica SET falhas_consecutivas = ? WHERE intencao = ?",
            (vision_engine.MAX_FALHAS_CACHE, intencao),
        )

    # Consulta deve retornar None e apagar a entrada
    resultado = vision_engine._consultar_cache(intencao)
    assert resultado is None

    # Confirma que foi removida do banco
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM memoria_semantica WHERE intencao = ?", (intencao,)
        ).fetchone()
    assert row is None


def test_registrar_sucesso_reseta_falhas_consecutivas():
    """Registrar sucesso após falhas deve zerar falhas_consecutivas."""
    intencao = "Salvar formulário"
    seletor = "[aria-label='Salvar']"

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)
    vision_engine._registrar_falha_cache(intencao)
    vision_engine._registrar_falha_cache(intencao)
    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor)

    db_path = vision_engine.DB_PATH
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT falhas_consecutivas FROM memoria_semantica WHERE intencao = ?",
            (intencao,),
        ).fetchone()

    assert row is not None
    assert row[0] == 0


def test_registrar_sucesso_com_coords():
    """Brain deve armazenar e recuperar coordenadas relativas."""
    intencao = "Clicar no ícone de pesquisa"
    coords = {"x_pct": 0.9, "y_pct": 0.05}

    vision_engine._registrar_sucesso_cache(intencao, coords=coords)
    entrada = vision_engine._consultar_cache(intencao)

    assert entrada is not None
    assert entrada.coords == coords


def test_seletor_fragil_nao_salvo_no_brain():
    """Seletores que não começam com prefixos válidos não devem ser persistidos."""
    intencao = "Clicar em span genérico"
    seletor_fragil = "span.alguma-classe"  # não começa com prefixo válido

    vision_engine._registrar_sucesso_cache(intencao, seletor=seletor_fragil)
    entrada = vision_engine._consultar_cache(intencao)

    # A entrada pode existir, mas o seletor frágil deve ter sido descartado
    if entrada is not None:
        assert entrada.seletor is None


# ──────────────────────────────────────────────────────────────
# Testes de telemetria de camadas
# ──────────────────────────────────────────────────────────────

def test_registrar_telemetria_acerto():
    """Registrar acerto deve incrementar coluna 'acertos' na tabela telemetria_camadas."""
    vision_engine._registrar_telemetria("brain", acertou=True)

    db_path = vision_engine.DB_PATH
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = 'brain'"
        ).fetchone()

    assert row is not None
    assert row[0] >= 1  # acertos
    assert row[1] == 0  # falhas


def test_registrar_telemetria_falha():
    """Registrar falha deve incrementar coluna 'falhas' na tabela telemetria_camadas."""
    vision_engine._registrar_telemetria("sniper", acertou=False)

    db_path = vision_engine.DB_PATH
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = 'sniper'"
        ).fetchone()

    assert row is not None
    assert row[0] == 0   # acertos
    assert row[1] >= 1   # falhas


# ──────────────────────────────────────────────────────────────
# Testes de análise de seletores (Sniper)
# ──────────────────────────────────────────────────────────────

def test_seletor_fragil_tag_generica():
    """Tags genéricas como 'span', 'div', 'button' devem ser detectadas como frágeis."""
    assert vision_engine._e_seletor_fragil("span") is True
    assert vision_engine._e_seletor_fragil("div.alguma-classe") is True
    assert vision_engine._e_seletor_fragil("button") is True


def test_seletor_robusto_nao_fragil():
    """Seletores com aria-label, data-testid ou text= não devem ser frágeis."""
    assert vision_engine._e_seletor_fragil("[aria-label='Salvar']") is False
    assert vision_engine._e_seletor_fragil("[data-testid='btn-salvar']") is False
    assert vision_engine._e_seletor_fragil("text=Salvar") is False


def test_seletor_vazio_e_fragil():
    """Seletor vazio deve ser considerado frágil."""
    assert vision_engine._e_seletor_fragil("") is True
    assert vision_engine._e_seletor_fragil(None) is True


def test_contem_indice_posicional_detecta_ids_numericos():
    """IDs com números como #file_1 devem ser detectados como posicionais."""
    assert vision_engine._contem_indice_posicional("#file_1") is True
    assert vision_engine._contem_indice_posicional("tr:nth-child(2)") is True
    assert vision_engine._contem_indice_posicional("li:nth-of-type(3)") is True


def test_contem_indice_posicional_nao_detecta_atributos():
    """Números dentro de valores de atributos não devem ser detectados como posicionais."""
    assert vision_engine._contem_indice_posicional("[data-testid='item-102']") is False

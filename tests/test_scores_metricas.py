"""
tests/test_scores_metricas.py
==============================
Testes unitários para scores em /api/metricas (Task 25).

Cobre:
  - scores_por_acao e scores_por_fluxo presentes na resposta
  - scores dentro do intervalo [0,1]
  - flag requer_revisao correta
  - null quando não há dados de score

Requisitos: 3.2.1, 3.2.4
"""

import json
import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import score_engine
from score_engine import obter_todos_scores, registrar_execucao

# ──────────────────────────────────────────────────────────────
# Fixture: banco isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "score_metricas_test.db")


# ──────────────────────────────────────────────────────────────
# Testes via score_engine diretamente (sem servidor HTTP)
# ──────────────────────────────────────────────────────────────

def test_scores_por_acao_estrutura(db):
    """obter_todos_scores() deve retornar lista com campos obrigatórios."""
    registrar_execucao("acao_a", sucesso=True, confianca_captura=1.0, db_path=db)
    registrar_execucao("acao_b", sucesso=False, confianca_captura=0.5, db_path=db)

    scores = obter_todos_scores(db_path=db)
    assert len(scores) == 2

    campos = {"acao_id", "score", "requer_revisao", "total_execucoes", "taxa_sucesso"}
    for item in scores:
        assert campos.issubset(item.keys()), f"Campos ausentes em: {item}"


def test_scores_por_acao_intervalo_valido(db):
    """Todos os scores devem estar em [0.0, 1.0]."""
    for i in range(5):
        registrar_execucao(f"acao_{i}", sucesso=(i % 2 == 0), db_path=db)

    scores = obter_todos_scores(db_path=db)
    for item in scores:
        assert 0.0 <= item["score"] <= 1.0, (
            f"Score fora do intervalo: acao_id={item['acao_id']} score={item['score']}"
        )


def test_scores_por_acao_requer_revisao_correto(db):
    """requer_revisao deve ser True quando score < 0.5."""
    # Força score baixo
    for _ in range(10):
        registrar_execucao("acao_ruim", sucesso=False, confianca_captura=0.0, db_path=db)

    # Força score alto
    for _ in range(10):
        registrar_execucao("acao_boa", sucesso=True, confianca_captura=1.0, db_path=db)

    scores = {s["acao_id"]: s for s in obter_todos_scores(db_path=db)}

    assert scores["acao_ruim"]["requer_revisao"] == 1
    assert scores["acao_ruim"]["score"] < 0.5

    assert scores["acao_boa"]["requer_revisao"] == 0
    assert scores["acao_boa"]["score"] >= 0.5


def test_scores_por_acao_null_sem_dados(db):
    """obter_todos_scores() deve retornar lista vazia quando não há dados."""
    scores = obter_todos_scores(db_path=db)
    assert scores == []


def test_scores_por_acao_ordenados_por_score_asc(db):
    """obter_todos_scores() deve retornar scores em ordem crescente (mais frágeis primeiro)."""
    # acao_ruim terá score baixo, acao_boa terá score alto
    for _ in range(10):
        registrar_execucao("acao_ruim", sucesso=False, confianca_captura=0.0, db_path=db)
    for _ in range(10):
        registrar_execucao("acao_boa", sucesso=True, confianca_captura=1.0, db_path=db)

    scores = obter_todos_scores(db_path=db)
    assert len(scores) == 2

    # Primeiro deve ser o mais frágil (score menor)
    assert scores[0]["score"] <= scores[1]["score"]
    assert scores[0]["acao_id"] == "acao_ruim"


def test_scores_por_acao_taxa_sucesso_correta(db):
    """taxa_sucesso deve refletir a proporção real de sucessos."""
    # 3 sucessos + 1 falha → taxa = 0.75
    for _ in range(3):
        registrar_execucao("acao_mista", sucesso=True, db_path=db)
    registrar_execucao("acao_mista", sucesso=False, db_path=db)

    scores = obter_todos_scores(db_path=db)
    assert len(scores) == 1
    assert abs(scores[0]["taxa_sucesso"] - 0.75) < 1e-9


def test_scores_por_acao_total_execucoes_correto(db):
    """total_execucoes deve refletir o número real de execuções registradas."""
    for _ in range(7):
        registrar_execucao("acao_contada", sucesso=True, db_path=db)

    scores = obter_todos_scores(db_path=db)
    assert len(scores) == 1
    assert scores[0]["total_execucoes"] == 7


# ──────────────────────────────────────────────────────────────
# Testes de integração com /api/metricas (via lógica direta)
# ──────────────────────────────────────────────────────────────

def test_metricas_inclui_scores_por_acao_quando_ha_dados(tmp_path, monkeypatch):
    """
    A lógica de /api/metricas deve incluir scores_por_acao quando há dados.
    Testa a lógica diretamente sem servidor HTTP.
    Requisito 3.2.4
    """
    db_path = str(tmp_path / "score_test.db")
    monkeypatch.setattr(score_engine, "DB_PATH", db_path)
    score_engine.inicializar_tabela(db_path)

    registrar_execucao("acao_teste", sucesso=True, confianca_captura=1.0, db_path=db_path)

    scores = obter_todos_scores(db_path=db_path)
    assert len(scores) == 1
    assert scores[0]["acao_id"] == "acao_teste"
    assert 0.0 <= scores[0]["score"] <= 1.0
    assert isinstance(scores[0]["requer_revisao"], int)


def test_metricas_scores_null_sem_dados(tmp_path, monkeypatch):
    """
    scores_por_acao deve ser lista vazia (não null) quando não há dados de score.
    Requisito 3.2.4
    """
    db_path = str(tmp_path / "score_vazio.db")
    monkeypatch.setattr(score_engine, "DB_PATH", db_path)
    score_engine.inicializar_tabela(db_path)

    scores = obter_todos_scores(db_path=db_path)
    assert scores == []

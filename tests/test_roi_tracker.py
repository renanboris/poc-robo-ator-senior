"""
tests/test_roi_tracker.py
==========================
Testes unitários para roi_tracker.py (Task 23).

Cobre:
  - Todos os campos presentes na resposta de calcular_metricas_roi()
  - Campos null quando não há dados
  - Cálculo correto do índice de reuso de memória
  - Tempo médio de criação calculado corretamente
  - Taxa de correção HITL calculada corretamente
  - Redução estimada de suporte calculada corretamente

Requisitos: 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6, 3.3.7
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import roi_tracker
from roi_tracker import (
    calcular_metricas_roi,
    inicializar_tabela,
    registrar_acao_gerada,
    registrar_consulta_aura,
    registrar_edicao_hitl,
    registrar_fim_criacao,
    registrar_inicio_criacao,
)

# ──────────────────────────────────────────────────────────────
# Fixture: banco isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    return str(tmp_path / "roi_test.db")


# ──────────────────────────────────────────────────────────────
# Campos obrigatórios na resposta
# ──────────────────────────────────────────────────────────────

CAMPOS_ROI = {
    "tempo_medio_criacao_segundos",
    "taxa_correcao_hitl",
    "indice_reuso_memoria",
    "reducao_suporte_estimada",
    "total_treinamentos_rastreados",
}


def test_calcular_metricas_roi_campos_obrigatorios(db):
    """Todos os campos obrigatórios devem estar presentes na resposta."""
    resultado = calcular_metricas_roi(db_path=db)
    for campo in CAMPOS_ROI:
        assert campo in resultado, f"Campo obrigatório ausente: {campo}"


def test_calcular_metricas_roi_null_sem_dados(db):
    """Todos os campos devem ser null quando não há dados registrados."""
    resultado = calcular_metricas_roi(db_path=db)
    for campo in CAMPOS_ROI:
        assert resultado[campo] is None, (
            f"Campo '{campo}' deveria ser null sem dados, obteve {resultado[campo]}"
        )


def test_nunca_retorna_zero_para_campo_sem_dados(db):
    """Campos sem dados devem ser null, nunca 0."""
    resultado = calcular_metricas_roi(db_path=db)
    for campo in CAMPOS_ROI:
        assert resultado[campo] != 0, (
            f"Campo '{campo}' retornou 0 em vez de null quando não há dados"
        )


# ──────────────────────────────────────────────────────────────
# Tempo médio de criação
# ──────────────────────────────────────────────────────────────

def test_tempo_criacao_calculado_corretamente(db):
    """tempo_medio_criacao_segundos deve refletir o tempo real entre início e fim."""
    import time

    registrar_inicio_criacao("treinamento_1", db_path=db)
    time.sleep(0.05)  # 50ms de espera
    registrar_fim_criacao("treinamento_1", db_path=db)

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["tempo_medio_criacao_segundos"] is not None
    assert resultado["tempo_medio_criacao_segundos"] >= 0.04  # pelo menos 40ms


def test_tempo_criacao_media_de_multiplos(db):
    """tempo_medio_criacao_segundos deve ser a média de múltiplos treinamentos."""
    import sqlite3

    # Insere diretamente com tempos conhecidos
    with sqlite3.connect(db) as conn:
        conn.execute(roi_tracker._CREATE_TABLE_SQL)
        conn.execute(
            "INSERT INTO roi_eventos (id_treinamento, tempo_criacao_segundos) VALUES (?, ?)",
            ("t1", 100.0),
        )
        conn.execute(
            "INSERT INTO roi_eventos (id_treinamento, tempo_criacao_segundos) VALUES (?, ?)",
            ("t2", 200.0),
        )

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["tempo_medio_criacao_segundos"] == pytest.approx(150.0, abs=0.01)
    assert resultado["total_treinamentos_rastreados"] == 2


def test_tempo_criacao_null_sem_fim_registrado(db):
    """Se apenas o início foi registrado (sem fim), tempo deve ser null."""
    registrar_inicio_criacao("treinamento_sem_fim", db_path=db)
    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["tempo_medio_criacao_segundos"] is None


# ──────────────────────────────────────────────────────────────
# Taxa de correção HITL
# ──────────────────────────────────────────────────────────────

def test_taxa_hitl_calculada_corretamente(db):
    """taxa_correcao_hitl deve ser a média de edições por roteiro."""
    registrar_edicao_hitl("t1", db_path=db)
    registrar_edicao_hitl("t1", db_path=db)  # 2 edições para t1
    registrar_edicao_hitl("t2", db_path=db)  # 1 edição para t2
    # Média = (2 + 1) / 2 = 1.5

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["taxa_correcao_hitl"] is not None
    assert resultado["taxa_correcao_hitl"] == pytest.approx(1.5, abs=0.01)


def test_taxa_hitl_null_sem_edicoes(db):
    """taxa_correcao_hitl deve ser null quando não há edições HITL registradas."""
    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["taxa_correcao_hitl"] is None


# ──────────────────────────────────────────────────────────────
# Índice de reuso de memória
# ──────────────────────────────────────────────────────────────

def test_indice_reuso_calculado_corretamente(db):
    """indice_reuso_memoria deve ser acoes_reutilizadas / acoes_geradas."""
    # 3 ações geradas, 2 reutilizadas → índice = 2/3 ≈ 0.6667
    registrar_acao_gerada("t1", reutilizada=True, db_path=db)
    registrar_acao_gerada("t1", reutilizada=True, db_path=db)
    registrar_acao_gerada("t1", reutilizada=False, db_path=db)

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["indice_reuso_memoria"] is not None
    assert resultado["indice_reuso_memoria"] == pytest.approx(2 / 3, abs=0.001)


def test_indice_reuso_zero_sem_reutilizacao(db):
    """indice_reuso_memoria deve ser 0.0 quando nenhuma ação foi reutilizada."""
    registrar_acao_gerada("t1", reutilizada=False, db_path=db)
    registrar_acao_gerada("t1", reutilizada=False, db_path=db)

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["indice_reuso_memoria"] is not None
    assert resultado["indice_reuso_memoria"] == pytest.approx(0.0, abs=0.001)


def test_indice_reuso_null_sem_acoes(db):
    """indice_reuso_memoria deve ser null quando não há ações registradas."""
    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["indice_reuso_memoria"] is None


# ──────────────────────────────────────────────────────────────
# Redução estimada de suporte
# ──────────────────────────────────────────────────────────────

def test_reducao_suporte_calculada_corretamente(db):
    """reducao_suporte_estimada deve ser consultas_cache / total_consultas."""
    # 3 cache hits + 1 miss → 3/4 = 0.75
    registrar_consulta_aura(cache_hit=True, db_path=db)
    registrar_consulta_aura(cache_hit=True, db_path=db)
    registrar_consulta_aura(cache_hit=True, db_path=db)
    registrar_consulta_aura(cache_hit=False, db_path=db)

    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["reducao_suporte_estimada"] is not None
    assert resultado["reducao_suporte_estimada"] == pytest.approx(0.75, abs=0.001)


def test_reducao_suporte_null_sem_consultas(db):
    """reducao_suporte_estimada deve ser null quando não há consultas Aura."""
    resultado = calcular_metricas_roi(db_path=db)
    assert resultado["reducao_suporte_estimada"] is None


# ──────────────────────────────────────────────────────────────
# Operações não lançam exceção com DB inválido
# ──────────────────────────────────────────────────────────────

def test_operacoes_nao_lancam_excecao_com_db_invalido():
    """Todas as operações devem ser silenciosas em caso de falha de DB."""
    db_invalido = "/caminho/invalido/roi.db"
    registrar_inicio_criacao("t1", db_path=db_invalido)
    registrar_fim_criacao("t1", db_path=db_invalido)
    registrar_edicao_hitl("t1", db_path=db_invalido)
    registrar_acao_gerada("t1", reutilizada=True, db_path=db_invalido)
    registrar_consulta_aura(cache_hit=True, db_path=db_invalido)
    resultado = calcular_metricas_roi(db_path=db_invalido)
    # Deve retornar dict com nulls, não lançar exceção
    assert isinstance(resultado, dict)

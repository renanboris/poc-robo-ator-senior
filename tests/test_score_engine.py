"""
tests/test_score_engine.py
==========================
Testes unitários e property-based tests para score_engine.py (Task 20).

Cobre:
  - Criação de tabela e operações básicas
  - calcular_score(), registrar_execucao(), marcar_requer_revisao()
  - obter_score(), obter_todos_scores()
  - Property 12: 0.0 <= score(A) <= 1.0 para qualquer histórico
  - Property 13: após execução bem-sucedida, score(N+1) >= score(N)
  - Property 14: calcular_score é determinístico

Requisitos: 3.2.1, 3.2.2, 3.2.3, 3.2.5
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hypothesis import given, settings, strategies as st, HealthCheck

import score_engine
from score_engine import (
    inicializar_tabela,
    calcular_score,
    registrar_execucao,
    marcar_requer_revisao,
    obter_score,
    obter_todos_scores,
    _calcular_score_formula,
)


# ──────────────────────────────────────────────────────────────
# Fixture: banco isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    """Caminho para banco SQLite temporário isolado por teste."""
    return str(tmp_path / "score_test.db")


# ──────────────────────────────────────────────────────────────
# Testes unitários — inicialização e operações básicas
# ──────────────────────────────────────────────────────────────

def test_inicializar_tabela_cria_tabela(db):
    """inicializar_tabela() deve criar a tabela sem erros."""
    inicializar_tabela(db)
    import sqlite3
    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scores_confiabilidade'"
        ).fetchone()
    assert row is not None


def test_inicializar_tabela_idempotente(db):
    """Chamar inicializar_tabela() duas vezes não deve lançar exceção."""
    inicializar_tabela(db)
    inicializar_tabela(db)  # segunda chamada — não deve falhar


def test_obter_score_retorna_none_para_acao_inexistente(db):
    """obter_score() deve retornar None para ação que não existe."""
    assert obter_score("acao_inexistente", db_path=db) is None


def test_calcular_score_retorna_none_para_acao_inexistente(db):
    """calcular_score() deve retornar None para ação que não existe."""
    assert calcular_score("acao_inexistente", db_path=db) is None


# ──────────────────────────────────────────────────────────────
# Testes unitários — registrar_execucao
# ──────────────────────────────────────────────────────────────

def test_registrar_execucao_cria_registro_sucesso(db):
    """Primeira execução bem-sucedida deve criar registro com taxa_sucesso=1.0."""
    registrar_execucao("acao_1", sucesso=True, db_path=db)
    score = obter_score("acao_1", db_path=db)
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_registrar_execucao_cria_registro_falha(db):
    """Primeira execução com falha deve criar registro com taxa_sucesso=0.0."""
    registrar_execucao("acao_falha", sucesso=False, db_path=db)
    score = obter_score("acao_falha", db_path=db)
    assert score is not None
    # Com taxa_sucesso=0.0, confianca=1.0, total=1 → score = 0*0.6 + 1*0.3 + 0.1*0.1 = 0.31
    assert score < 0.5


def test_registrar_execucao_incrementa_total(db):
    """Cada chamada a registrar_execucao deve incrementar total_execucoes."""
    import sqlite3
    registrar_execucao("acao_x", sucesso=True, db_path=db)
    registrar_execucao("acao_x", sucesso=True, db_path=db)
    registrar_execucao("acao_x", sucesso=True, db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT total_execucoes FROM scores_confiabilidade WHERE acao_id = ?",
            ("acao_x",),
        ).fetchone()
    assert row[0] == 3


def test_registrar_execucao_media_movel(db):
    """taxa_sucesso deve ser atualizada com média móvel correta."""
    import sqlite3
    # 2 sucessos + 1 falha → taxa = (1+1+0)/3 = 0.667
    registrar_execucao("acao_mm", sucesso=True, db_path=db)
    registrar_execucao("acao_mm", sucesso=True, db_path=db)
    registrar_execucao("acao_mm", sucesso=False, db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT taxa_sucesso FROM scores_confiabilidade WHERE acao_id = ?",
            ("acao_mm",),
        ).fetchone()

    assert abs(row[0] - (2 / 3)) < 1e-9


def test_registrar_execucao_nao_lanca_excecao_com_db_invalido():
    """registrar_execucao() nunca deve lançar exceção — falha silenciosa."""
    # Usa um caminho inválido para forçar erro de DB
    registrar_execucao("acao_x", sucesso=True, db_path="/caminho/invalido/brain.db")
    # Se chegou aqui, não lançou exceção — correto


# ──────────────────────────────────────────────────────────────
# Testes unitários — requer_revisao
# ──────────────────────────────────────────────────────────────

def test_requer_revisao_ativado_quando_score_baixo(db):
    """requer_revisao deve ser 1 quando score < 0.5."""
    import sqlite3
    # Muitas falhas para forçar score baixo
    for _ in range(10):
        registrar_execucao("acao_ruim", sucesso=False, confianca_captura=0.0, db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT requer_revisao, score FROM scores_confiabilidade WHERE acao_id = ?",
            ("acao_ruim",),
        ).fetchone()

    assert row[0] == 1, f"requer_revisao deveria ser 1, score={row[1]}"
    assert row[1] < 0.5


def test_requer_revisao_desativado_quando_score_alto(db):
    """requer_revisao deve ser 0 quando score >= 0.5."""
    import sqlite3
    for _ in range(10):
        registrar_execucao("acao_boa", sucesso=True, confianca_captura=1.0, db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT requer_revisao, score FROM scores_confiabilidade WHERE acao_id = ?",
            ("acao_boa",),
        ).fetchone()

    assert row[0] == 0, f"requer_revisao deveria ser 0, score={row[1]}"
    assert row[1] >= 0.5


def test_marcar_requer_revisao_funciona(db):
    """marcar_requer_revisao() deve atualizar o campo corretamente."""
    import sqlite3
    # Cria registro com score baixo manualmente
    registrar_execucao("acao_rev", sucesso=False, confianca_captura=0.0, db_path=db)
    marcar_requer_revisao("acao_rev", db_path=db)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT requer_revisao FROM scores_confiabilidade WHERE acao_id = ?",
            ("acao_rev",),
        ).fetchone()
    assert row[0] == 1


def test_marcar_requer_revisao_acao_inexistente_nao_lanca(db):
    """marcar_requer_revisao() para ação inexistente não deve lançar exceção."""
    marcar_requer_revisao("acao_que_nao_existe", db_path=db)


# ──────────────────────────────────────────────────────────────
# Testes unitários — obter_todos_scores
# ──────────────────────────────────────────────────────────────

def test_obter_todos_scores_retorna_lista_vazia_sem_dados(db):
    """obter_todos_scores() deve retornar lista vazia quando não há dados."""
    resultado = obter_todos_scores(db_path=db)
    assert resultado == []


def test_obter_todos_scores_retorna_todos_registros(db):
    """obter_todos_scores() deve retornar todos os registros existentes."""
    registrar_execucao("acao_a", sucesso=True, db_path=db)
    registrar_execucao("acao_b", sucesso=False, db_path=db)
    registrar_execucao("acao_c", sucesso=True, db_path=db)

    resultado = obter_todos_scores(db_path=db)
    assert len(resultado) == 3
    ids = {r["acao_id"] for r in resultado}
    assert ids == {"acao_a", "acao_b", "acao_c"}


def test_obter_todos_scores_campos_obrigatorios(db):
    """Cada item de obter_todos_scores() deve ter todos os campos obrigatórios."""
    registrar_execucao("acao_campos", sucesso=True, db_path=db)
    resultado = obter_todos_scores(db_path=db)
    assert len(resultado) == 1
    item = resultado[0]
    campos = {"acao_id", "taxa_sucesso", "confianca_captura", "total_execucoes",
              "score", "requer_revisao", "ultima_atualizacao"}
    assert campos.issubset(item.keys())


# ──────────────────────────────────────────────────────────────
# Testes unitários — fórmula do score
# ──────────────────────────────────────────────────────────────

def test_formula_score_maximo():
    """Score máximo: taxa=1.0, confianca=1.0, execucoes=10 → score=1.0."""
    assert _calcular_score_formula(1.0, 1.0, 10) == pytest.approx(1.0)


def test_formula_score_minimo():
    """Score mínimo: taxa=0.0, confianca=0.0, execucoes=0 → score=0.0."""
    assert _calcular_score_formula(0.0, 0.0, 0) == pytest.approx(0.0)


def test_formula_fator_execucoes_satura_em_10():
    """fator_execucoes deve saturar em 1.0 com 10 ou mais execuções."""
    score_10 = _calcular_score_formula(1.0, 1.0, 10)
    score_100 = _calcular_score_formula(1.0, 1.0, 100)
    assert score_10 == pytest.approx(1.0)
    assert score_100 == pytest.approx(1.0)
    assert score_10 == score_100


def test_formula_pesos_corretos():
    """Verifica os pesos: 0.6 taxa + 0.3 confianca + 0.1 fator."""
    # taxa=0.5, confianca=0.5, execucoes=5 (fator=0.5)
    # score = 0.5*0.6 + 0.5*0.3 + 0.5*0.1 = 0.3 + 0.15 + 0.05 = 0.5
    score = _calcular_score_formula(0.5, 0.5, 5)
    assert abs(score - 0.5) < 1e-9


# ──────────────────────────────────────────────────────────────
# Property 12: 0.0 <= score(A) <= 1.0 para qualquer histórico
# Validates: Requisito 3.2.1
# ──────────────────────────────────────────────────────────────

@st.composite
def historico_execucoes(draw):
    """Gera uma sequência de execuções com resultados e confiancas variados."""
    n = draw(st.integers(min_value=1, max_value=30))
    execucoes = draw(st.lists(
        st.tuples(
            st.booleans(),                          # sucesso
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),  # confianca_captura
        ),
        min_size=n, max_size=n,
    ))
    return execucoes


@given(historico_execucoes())
@settings(max_examples=200, deadline=None)
def test_property_12_score_invariante_entre_zero_e_um(execucoes):
    """
    **Validates: Requisito 3.2.1**
    Property 12: Para qualquer ação com qualquer histórico de execuções,
    0.0 <= score(A) <= 1.0 deve ser sempre verdadeiro.
    """
    import tempfile, os, sqlite3
    # Usa arquivo temporário explícito para evitar PermissionError no Windows
    tmp_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        acao_id = "acao_prop12"
        for sucesso, confianca in execucoes:
            registrar_execucao(acao_id, sucesso=sucesso, confianca_captura=confianca, db_path=db_path)

        score = obter_score(acao_id, db_path=db_path)
        assert score is not None
        assert 0.0 <= score <= 1.0, f"Score fora do intervalo: {score}"
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────
# Property 13: após execução bem-sucedida, score(N+1) >= score(N)
# Validates: Requisito 3.2.3
# ──────────────────────────────────────────────────────────────

@st.composite
def historico_com_sucesso_final(draw):
    """
    Gera um histórico de execuções mistas seguido de uma execução bem-sucedida.
    Usa a mesma confianca_captura em todo o histórico para garantir monotonicidade.
    Retorna (historico_inicial, confianca_fixa).
    """
    n = draw(st.integers(min_value=0, max_value=20))
    # Confiança fixa para todo o histórico — garante que a variável de controle
    # seja apenas o resultado (sucesso/falha), não a confiança
    confianca_fixa = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    historico = draw(st.lists(
        st.booleans(),  # apenas sucesso/falha, confiança é fixa
        min_size=n, max_size=n,
    ))
    return historico, confianca_fixa


@given(historico_com_sucesso_final())
@settings(max_examples=100, deadline=None)
def test_property_13_monotonicidade_com_sucesso(dados):
    """
    **Validates: Requisito 3.2.3**
    Property 13: Para qualquer ação A com confianca_captura fixa, registrar uma
    execução bem-sucedida deve resultar em score(A, N+1) >= score(A, N).

    A monotonicidade é garantida quando confianca_captura é constante, pois
    o único componente que muda é taxa_sucesso (que aumenta com sucesso) e
    fator_execucoes (que nunca decresce).
    """
    import tempfile, os
    historico, confianca_fixa = dados

    tmp_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(tmp_fd)
    try:
        acao_id = "acao_prop13"

        # Aplica histórico inicial com confiança fixa
        for sucesso in historico:
            registrar_execucao(acao_id, sucesso=sucesso, confianca_captura=confianca_fixa, db_path=db_path)

        score_antes = obter_score(acao_id, db_path=db_path)

        # Registra execução bem-sucedida com a mesma confiança
        registrar_execucao(acao_id, sucesso=True, confianca_captura=confianca_fixa, db_path=db_path)
        score_depois = obter_score(acao_id, db_path=db_path)

        assert score_depois is not None
        assert 0.0 <= score_depois <= 1.0

        if score_antes is not None:
            assert score_depois >= score_antes - 1e-9, (
                f"Score regrediu após sucesso: antes={score_antes:.4f} depois={score_depois:.4f} "
                f"confianca={confianca_fixa:.4f}"
            )
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────
# Property 14: calcular_score é determinístico
# Validates: Requisito 3.2.2
# ──────────────────────────────────────────────────────────────

@st.composite
def componentes_score(draw):
    """Gera componentes válidos para o cálculo do score."""
    taxa_sucesso = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    confianca = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    total_execucoes = draw(st.integers(min_value=0, max_value=100))
    return taxa_sucesso, confianca, total_execucoes


@given(componentes_score())
@settings(max_examples=100)
def test_property_14_score_deterministico(componentes):
    """
    **Validates: Requisito 3.2.2**
    Property 14: calcular_score é uma função determinística — chamadas com os
    mesmos componentes devem sempre retornar o mesmo resultado.
    """
    taxa_sucesso, confianca, total_execucoes = componentes

    score1 = _calcular_score_formula(taxa_sucesso, confianca, total_execucoes)
    score2 = _calcular_score_formula(taxa_sucesso, confianca, total_execucoes)

    assert score1 == score2, (
        f"Score não é determinístico: {score1} != {score2} "
        f"para taxa={taxa_sucesso}, confianca={confianca}, execucoes={total_execucoes}"
    )
    assert 0.0 <= score1 <= 1.0
    assert 0.0 <= score2 <= 1.0

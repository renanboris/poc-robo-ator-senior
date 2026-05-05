"""
tests/test_score_integration.py
================================
Testes unitários para integração do Score de Confiabilidade com o Executor
(main.py) e com a Biblioteca de Ações (lego_builder.py).

Cobre:
  1. Após execução bem-sucedida, score da ação deve ser >= score anterior
  2. Após execução com falha, score deve ser <= score anterior (ou igual se já era 0)
  3. requer_revisao deve ser True quando score < 0.5
  4. lego_builder.construir_biblioteca() deve incluir _score_confiabilidade nas entradas

Requisitos: 3.2.3, 3.2.5
"""

import json
import os
import sqlite3
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import score_engine
from lego_builder import construir_biblioteca
from score_engine import obter_score, obter_todos_scores, registrar_execucao

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db(tmp_path):
    """Banco SQLite isolado por teste."""
    return str(tmp_path / "score_integration_test.db")


@pytest.fixture()
def roteiros_dir(tmp_path):
    """Diretório temporário com um roteiro de referência."""
    d = tmp_path / "roteiros_salvos"
    d.mkdir()
    roteiro = {
        "metadata": {"nome_aula": "Teste", "id_treinamento": "teste_integracao"},
        "configuracao_gravacao": {"gravar_video": False, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"},
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo 1", "tooltip_dap": ""},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "clicar_botao_salvar",
                        "micro_narracao": "Clique em Salvar",
                        "elemento_alvo": {
                            "label_curto": "Salvar",
                            "seletor_hint": "button[data-action='save']",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "pedagogia": {"ancora": "Fim", "tooltip_dap": ""},
                "acoes_tecnicas": [],
            },
        ],
    }
    (d / "roteiro_teste.json").write_text(json.dumps(roteiro), encoding="utf-8")
    return str(d)


@pytest.fixture()
def biblioteca_file(tmp_path):
    """Caminho para o arquivo de biblioteca temporário."""
    return str(tmp_path / "biblioteca_acoes.json")


# ──────────────────────────────────────────────────────────────
# Teste 1: Execução bem-sucedida incrementa (ou mantém) o score
# ──────────────────────────────────────────────────────────────

def test_execucao_bem_sucedida_score_nao_decresce(db):
    """
    Após execução bem-sucedida, score da ação deve ser >= score anterior.
    Requisito 3.2.3
    """
    acao_id = "clicar_botao_confirmar"

    # Estabelece um histórico misto para ter um score inicial
    for _ in range(3):
        registrar_execucao(acao_id, sucesso=True, confianca_captura=0.7, db_path=db)
    registrar_execucao(acao_id, sucesso=False, confianca_captura=0.7, db_path=db)

    score_antes = obter_score(acao_id, db_path=db)
    assert score_antes is not None

    # Registra execução bem-sucedida
    registrar_execucao(acao_id, sucesso=True, confianca_captura=0.7, db_path=db)
    score_depois = obter_score(acao_id, db_path=db)

    assert score_depois is not None
    assert score_depois >= score_antes - 1e-9, (
        f"Score regrediu após sucesso: antes={score_antes:.4f} depois={score_depois:.4f}"
    )


def test_primeira_execucao_bem_sucedida_cria_score(db):
    """
    Primeira execução bem-sucedida deve criar registro com score > 0.
    Requisito 3.2.3
    """
    acao_id = "acao_nova_sucesso"
    assert obter_score(acao_id, db_path=db) is None

    registrar_execucao(acao_id, sucesso=True, confianca_captura=1.0, db_path=db)

    score = obter_score(acao_id, db_path=db)
    assert score is not None
    assert score > 0.0


# ──────────────────────────────────────────────────────────────
# Teste 2: Execução com falha não aumenta o score
# ──────────────────────────────────────────────────────────────

def test_execucao_com_falha_score_nao_aumenta(db):
    """
    Após execução com falha, score deve ser <= score anterior.
    Requisito 3.2.3
    """
    acao_id = "clicar_botao_cancelar"

    # Histórico de sucessos para ter score alto
    for _ in range(5):
        registrar_execucao(acao_id, sucesso=True, confianca_captura=1.0, db_path=db)

    score_antes = obter_score(acao_id, db_path=db)
    assert score_antes is not None

    # Registra execução com falha
    registrar_execucao(acao_id, sucesso=False, confianca_captura=1.0, db_path=db)
    score_depois = obter_score(acao_id, db_path=db)

    assert score_depois is not None
    assert score_depois <= score_antes + 1e-9, (
        f"Score aumentou após falha: antes={score_antes:.4f} depois={score_depois:.4f}"
    )


def test_score_zero_permanece_zero_ou_sobe_apos_falha(db):
    """
    Ação com score já muito baixo: após nova falha, score deve ser <= score anterior.
    Requisito 3.2.3
    """
    acao_id = "acao_muito_ruim"

    # Força score baixo com muitas falhas
    for _ in range(10):
        registrar_execucao(acao_id, sucesso=False, confianca_captura=0.0, db_path=db)

    score_antes = obter_score(acao_id, db_path=db)
    assert score_antes is not None
    assert score_antes <= 0.1  # deve ser muito baixo

    # Nova falha — score não deve aumentar
    registrar_execucao(acao_id, sucesso=False, confianca_captura=0.0, db_path=db)
    score_depois = obter_score(acao_id, db_path=db)

    assert score_depois is not None
    assert score_depois <= score_antes + 1e-9


# ──────────────────────────────────────────────────────────────
# Teste 3: requer_revisao ativado quando score < 0.5
# ──────────────────────────────────────────────────────────────

def test_requer_revisao_true_quando_score_baixo(db):
    """
    requer_revisao deve ser True quando score < 0.5.
    Requisito 3.2.5
    """
    acao_id = "acao_fragil"

    # Muitas falhas para forçar score < 0.5
    for _ in range(10):
        registrar_execucao(acao_id, sucesso=False, confianca_captura=0.0, db_path=db)

    score = obter_score(acao_id, db_path=db)
    assert score is not None
    assert score < 0.5

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT requer_revisao FROM scores_confiabilidade WHERE acao_id = ?",
            (acao_id,),
        ).fetchone()

    assert row is not None
    assert bool(row["requer_revisao"]) is True, (
        f"requer_revisao deveria ser True para score={score:.4f}"
    )


def test_requer_revisao_false_quando_score_alto(db):
    """
    requer_revisao deve ser False quando score >= 0.5.
    Requisito 3.2.5
    """
    acao_id = "acao_confiavel"

    for _ in range(10):
        registrar_execucao(acao_id, sucesso=True, confianca_captura=1.0, db_path=db)

    score = obter_score(acao_id, db_path=db)
    assert score is not None
    assert score >= 0.5

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT requer_revisao FROM scores_confiabilidade WHERE acao_id = ?",
            (acao_id,),
        ).fetchone()

    assert row is not None
    assert bool(row["requer_revisao"]) is False, (
        f"requer_revisao deveria ser False para score={score:.4f}"
    )


def test_requer_revisao_transicao_baixo_para_alto(db):
    """
    requer_revisao deve ser atualizado dinamicamente conforme o score muda.
    Requisito 3.2.5
    """
    acao_id = "acao_recuperando"

    # Começa com falhas → requer_revisao=True
    for _ in range(10):
        registrar_execucao(acao_id, sucesso=False, confianca_captura=0.0, db_path=db)

    score_baixo = obter_score(acao_id, db_path=db)
    assert score_baixo < 0.5

    # Muitos sucessos → score sobe acima de 0.5
    for _ in range(50):
        registrar_execucao(acao_id, sucesso=True, confianca_captura=1.0, db_path=db)

    score_alto = obter_score(acao_id, db_path=db)
    assert score_alto >= 0.5

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT requer_revisao FROM scores_confiabilidade WHERE acao_id = ?",
            (acao_id,),
        ).fetchone()

    assert bool(row["requer_revisao"]) is False


# ──────────────────────────────────────────────────────────────
# Teste 4: lego_builder inclui _score_confiabilidade nas entradas
# ──────────────────────────────────────────────────────────────

def test_construir_biblioteca_inclui_score_confiabilidade(roteiros_dir, biblioteca_file, monkeypatch):
    """
    construir_biblioteca() deve incluir _score_confiabilidade em cada entrada.
    Requisito 3.2.5
    """
    resultado = construir_biblioteca(
        roteiros_dir=roteiros_dir,
        biblioteca_file=biblioteca_file,
    )

    assert resultado["status"] == "sucesso", f"Rebuild falhou: {resultado}"

    with open(biblioteca_file, encoding="utf-8") as f:
        biblioteca = json.load(f)

    assert len(biblioteca) > 0, "Biblioteca vazia após rebuild"

    for chave, entrada in biblioteca.items():
        assert "_score_confiabilidade" in entrada, (
            f"Campo '_score_confiabilidade' ausente na entrada '{chave}'"
        )
        assert "_requer_revisao" in entrada, (
            f"Campo '_requer_revisao' ausente na entrada '{chave}'"
        )


def test_construir_biblioteca_score_none_sem_historico(roteiros_dir, biblioteca_file):
    """
    Quando não há histórico de execuções, _score_confiabilidade deve ser None.
    Requisito 3.2.5
    """
    # Garante que não há banco de score para esta ação
    resultado = construir_biblioteca(
        roteiros_dir=roteiros_dir,
        biblioteca_file=biblioteca_file,
    )

    assert resultado["status"] == "sucesso"

    with open(biblioteca_file, encoding="utf-8") as f:
        biblioteca = json.load(f)

    for chave, entrada in biblioteca.items():
        # Sem execuções registradas, score deve ser None
        assert entrada["_score_confiabilidade"] is None, (
            f"Score deveria ser None para ação sem histórico: '{chave}' = {entrada['_score_confiabilidade']}"
        )
        assert entrada["_requer_revisao"] is False


def test_construir_biblioteca_score_preenchido_com_historico(roteiros_dir, biblioteca_file, tmp_path):
    """
    Quando há histórico de execuções no banco padrão, _score_confiabilidade deve ser float em [0,1].
    Verifica que o campo é populado corretamente quando obter_score retorna um valor.
    Requisito 3.2.5
    """
    from unittest.mock import MagicMock, patch

    import score_engine as se

    acao_id = "clicar_botao_salvar"
    score_simulado = 0.85

    # Simula obter_score retornando um valor conhecido
    mock_obter = MagicMock(return_value=score_simulado)

    with patch("score_engine.obter_score", mock_obter):
        resultado = construir_biblioteca(
            roteiros_dir=roteiros_dir,
            biblioteca_file=biblioteca_file,
        )

    assert resultado["status"] == "sucesso"

    with open(biblioteca_file, encoding="utf-8") as f:
        biblioteca = json.load(f)

    entrada = biblioteca.get(acao_id)
    assert entrada is not None, f"Ação '{acao_id}' não encontrada na biblioteca"
    assert entrada["_score_confiabilidade"] == score_simulado
    assert 0.0 <= entrada["_score_confiabilidade"] <= 1.0
    assert isinstance(entrada["_requer_revisao"], bool)
    assert entrada["_requer_revisao"] is False  # 0.85 >= 0.5

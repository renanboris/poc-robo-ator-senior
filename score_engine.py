"""
score_engine.py — Senior Training OS · Engine de Score de Confiabilidade
=========================================================================
Task 20: Implementar tabela e engine de Score de Confiabilidade.

Expõe:
  - inicializar_tabela()          — cria tabela scores_confiabilidade em brain.db
  - calcular_score(acao_id)       — média ponderada de taxa_sucesso, confianca_captura
                                    e fator_execucoes
  - registrar_execucao(acao_id, sucesso, confianca_captura) — atualiza taxa_sucesso
                                    e total_execucoes, recalcula score
  - marcar_requer_revisao(acao_id) — marca requer_revisao=1 quando score < 0.5
  - obter_score(acao_id)          — retorna score atual ou None se não existir
  - obter_todos_scores()          — retorna lista de todos os scores para /api/metricas

Schema da tabela scores_confiabilidade:
  acao_id TEXT PRIMARY KEY
  taxa_sucesso REAL DEFAULT 1.0
  confianca_captura REAL DEFAULT 1.0
  total_execucoes INTEGER DEFAULT 0
  score REAL DEFAULT 1.0
  requer_revisao INTEGER DEFAULT 0
  ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Fórmula do score:
  score = (taxa_sucesso * 0.6) + (confianca_captura * 0.3) + (fator_execucoes * 0.1)
  fator_execucoes = min(total_execucoes / 10.0, 1.0)

Requisitos: 3.2.1, 3.2.2, 3.2.3, 3.2.5
"""

import sqlite3
from typing import Optional

from utils import configurar_logging

logger = configurar_logging(__name__)

DB_PATH = "brain.db"

# ──────────────────────────────────────────────────────────────
# Schema
# ──────────────────────────────────────────────────────────────

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scores_confiabilidade (
    acao_id TEXT PRIMARY KEY,
    taxa_sucesso REAL DEFAULT 1.0,
    confianca_captura REAL DEFAULT 1.0,
    total_execucoes INTEGER DEFAULT 0,
    score REAL DEFAULT 1.0,
    requer_revisao INTEGER DEFAULT 0,
    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


# ──────────────────────────────────────────────────────────────
# Inicialização
# ──────────────────────────────────────────────────────────────

def inicializar_tabela(db_path: str = DB_PATH) -> None:
    """Cria a tabela scores_confiabilidade se ainda não existir."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(_CREATE_TABLE_SQL)
    except Exception as e:
        logger.error(f"[score_engine] Erro ao inicializar tabela: {e}")


# ──────────────────────────────────────────────────────────────
# Fórmula do score
# ──────────────────────────────────────────────────────────────

def _calcular_score_formula(
    taxa_sucesso: float,
    confianca_captura: float,
    total_execucoes: int,
) -> float:
    """
    Calcula o score de confiabilidade a partir dos componentes.

    score = (taxa_sucesso * 0.6) + (confianca_captura * 0.3) + (fator_execucoes * 0.1)
    fator_execucoes = min(total_execucoes / 10.0, 1.0)

    Garante que o resultado esteja sempre em [0.0, 1.0].
    """
    fator_execucoes = min(total_execucoes / 10.0, 1.0)
    score = (taxa_sucesso * 0.6) + (confianca_captura * 0.3) + (fator_execucoes * 0.1)
    # Clamp defensivo para garantir invariante 0.0 <= score <= 1.0
    return max(0.0, min(1.0, score))


# ──────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────

def calcular_score(acao_id: str, db_path: str = DB_PATH) -> Optional[float]:
    """
    Retorna o score de confiabilidade calculado para a ação.

    Lê os componentes do banco e aplica a fórmula de média ponderada.
    Retorna None se a ação não existir na tabela.

    Requisito 3.2.1: score baseado em taxa_sucesso, confianca_captura e execuções.
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT taxa_sucesso, confianca_captura, total_execucoes "
                "FROM scores_confiabilidade WHERE acao_id = ?",
                (acao_id,),
            ).fetchone()

        if row is None:
            return None

        return _calcular_score_formula(
            row["taxa_sucesso"],
            row["confianca_captura"],
            row["total_execucoes"],
        )
    except Exception as e:
        logger.error(f"[score_engine] Erro ao calcular score para '{acao_id}': {e}")
        return None


def registrar_execucao(
    acao_id: str,
    sucesso: bool,
    confianca_captura: float = 1.0,
    db_path: str = DB_PATH,
) -> None:
    """
    Registra o resultado de uma execução e atualiza o score da ação.

    - Se não existir: cria com taxa_sucesso=1.0 (sucesso) ou 0.0 (falha).
    - Se existir: atualiza taxa_sucesso com média móvel:
        nova = (antiga * n + resultado) / (n + 1)
    - Incrementa total_execucoes.
    - Recalcula score e atualiza requer_revisao = (score < 0.5).

    Falhas nunca interrompem o pipeline — todas as exceções são capturadas.

    Requisitos: 3.2.3, 3.2.5
    """
    try:
        inicializar_tabela(db_path)
        resultado_num = 1.0 if sucesso else 0.0

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT taxa_sucesso, total_execucoes "
                "FROM scores_confiabilidade WHERE acao_id = ?",
                (acao_id,),
            ).fetchone()

            if row is None:
                # Primeira execução: cria o registro
                nova_taxa = resultado_num
                novo_total = 1
                novo_score = _calcular_score_formula(nova_taxa, confianca_captura, novo_total)
                requer_revisao = 1 if novo_score < 0.5 else 0

                conn.execute(
                    """
                    INSERT INTO scores_confiabilidade
                        (acao_id, taxa_sucesso, confianca_captura, total_execucoes,
                         score, requer_revisao, ultima_atualizacao)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (acao_id, nova_taxa, confianca_captura, novo_total,
                     novo_score, requer_revisao),
                )
            else:
                # Atualiza com média móvel
                n = row["total_execucoes"]
                taxa_antiga = row["taxa_sucesso"]
                nova_taxa = (taxa_antiga * n + resultado_num) / (n + 1)
                novo_total = n + 1
                novo_score = _calcular_score_formula(nova_taxa, confianca_captura, novo_total)
                requer_revisao = 1 if novo_score < 0.5 else 0

                conn.execute(
                    """
                    UPDATE scores_confiabilidade
                    SET taxa_sucesso = ?,
                        confianca_captura = ?,
                        total_execucoes = ?,
                        score = ?,
                        requer_revisao = ?,
                        ultima_atualizacao = CURRENT_TIMESTAMP
                    WHERE acao_id = ?
                    """,
                    (nova_taxa, confianca_captura, novo_total,
                     novo_score, requer_revisao, acao_id),
                )

        logger.info(
            f"[score_engine] Execução registrada: acao_id='{acao_id}' "
            f"sucesso={sucesso} score={novo_score:.3f} requer_revisao={bool(requer_revisao)}"
        )
    except Exception as e:
        logger.error(f"[score_engine] Erro ao registrar execução para '{acao_id}': {e}")


def marcar_requer_revisao(acao_id: str, db_path: str = DB_PATH) -> None:
    """
    Marca a ação como requer_revisao=1 quando score < 0.5.

    Chamado automaticamente por registrar_execucao, mas pode ser invocado
    manualmente para forçar a marcação.

    Requisito 3.2.3
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT score FROM scores_confiabilidade WHERE acao_id = ?",
                (acao_id,),
            ).fetchone()

            if row is None:
                logger.warning(
                    f"[score_engine] marcar_requer_revisao: acao_id '{acao_id}' não encontrada."
                )
                return

            requer_revisao = 1 if row["score"] < 0.5 else 0
            conn.execute(
                "UPDATE scores_confiabilidade SET requer_revisao = ? WHERE acao_id = ?",
                (requer_revisao, acao_id),
            )
    except Exception as e:
        logger.error(f"[score_engine] Erro ao marcar requer_revisao para '{acao_id}': {e}")


def obter_score(acao_id: str, db_path: str = DB_PATH) -> Optional[float]:
    """
    Retorna o score atual da ação ou None se não existir.

    Diferente de calcular_score(), retorna o valor já persistido no banco
    sem recalcular.

    Requisito 3.2.1
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT score FROM scores_confiabilidade WHERE acao_id = ?",
                (acao_id,),
            ).fetchone()

        return row["score"] if row is not None else None
    except Exception as e:
        logger.error(f"[score_engine] Erro ao obter score para '{acao_id}': {e}")
        return None


def obter_todos_scores(db_path: str = DB_PATH) -> list[dict]:
    """
    Retorna lista de todos os scores para o endpoint /api/metricas.

    Cada item contém:
      acao_id, taxa_sucesso, confianca_captura, total_execucoes,
      score, requer_revisao, ultima_atualizacao

    Requisito 3.2.4
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT acao_id, taxa_sucesso, confianca_captura, total_execucoes,
                       score, requer_revisao, ultima_atualizacao
                FROM scores_confiabilidade
                ORDER BY score ASC
                """
            ).fetchall()

        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[score_engine] Erro ao obter todos os scores: {e}")
        return []

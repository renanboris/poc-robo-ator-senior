"""
roi_tracker.py — Senior Training OS · Rastreamento de Métricas de ROI
======================================================================
Task 23: Implementar métricas de ROI em /api/metricas.

Expõe:
  - inicializar_tabela()           — cria tabela roi_eventos em brain.db
  - registrar_inicio_criacao(id)   — marca início da captura de um treinamento
  - registrar_fim_criacao(id)      — marca fim (primeiro artefato gerado)
  - registrar_edicao_hitl(id)      — incrementa contador de edições HITL
  - registrar_acao_gerada(id, reusada) — registra se ação veio da biblioteca ou foi criada do zero
  - registrar_consulta_aura(cache_hit) — registra se consulta Aura usou cache/RAG ou Gemini Vision
  - calcular_metricas_roi()        — retorna dict com todas as métricas de ROI

Schema da tabela roi_eventos:
  id_treinamento TEXT PRIMARY KEY
  inicio_criacao REAL (timestamp Unix)
  fim_criacao REAL (timestamp Unix)
  tempo_criacao_segundos REAL (calculado)
  edicoes_hitl INTEGER DEFAULT 0
  acoes_geradas INTEGER DEFAULT 0
  acoes_reutilizadas INTEGER DEFAULT 0
  consultas_aura INTEGER DEFAULT 0
  consultas_aura_cache INTEGER DEFAULT 0
  ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP

Requisitos: 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6, 3.3.7
"""

import sqlite3
import time
from typing import Optional

from utils import configurar_logging

logger = configurar_logging(__name__)

DB_PATH = "brain.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS roi_eventos (
    id_treinamento TEXT PRIMARY KEY,
    inicio_criacao REAL,
    fim_criacao REAL,
    tempo_criacao_segundos REAL,
    edicoes_hitl INTEGER DEFAULT 0,
    acoes_geradas INTEGER DEFAULT 0,
    acoes_reutilizadas INTEGER DEFAULT 0,
    consultas_aura INTEGER DEFAULT 0,
    consultas_aura_cache INTEGER DEFAULT 0,
    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
"""


def inicializar_tabela(db_path: str = DB_PATH) -> None:
    """Cria a tabela roi_eventos se ainda não existir."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(_CREATE_TABLE_SQL)
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao inicializar tabela: {e}")


def registrar_inicio_criacao(id_treinamento: str, db_path: str = DB_PATH) -> None:
    """Marca o início da captura de um treinamento (timestamp Unix)."""
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO roi_eventos (id_treinamento, inicio_criacao, ultima_atualizacao)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id_treinamento) DO UPDATE SET
                    inicio_criacao = excluded.inicio_criacao,
                    ultima_atualizacao = CURRENT_TIMESTAMP
                """,
                (id_treinamento, time.time()),
            )
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao registrar início de criação: {e}")


def registrar_fim_criacao(id_treinamento: str, db_path: str = DB_PATH) -> None:
    """Marca o fim da criação (primeiro artefato gerado) e calcula tempo_criacao_segundos."""
    try:
        inicializar_tabela(db_path)
        agora = time.time()
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT inicio_criacao FROM roi_eventos WHERE id_treinamento = ?",
                (id_treinamento,),
            ).fetchone()

            tempo = None
            if row and row["inicio_criacao"]:
                tempo = round(agora - row["inicio_criacao"], 2)

            conn.execute(
                """
                INSERT INTO roi_eventos (id_treinamento, fim_criacao, tempo_criacao_segundos, ultima_atualizacao)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id_treinamento) DO UPDATE SET
                    fim_criacao = excluded.fim_criacao,
                    tempo_criacao_segundos = excluded.tempo_criacao_segundos,
                    ultima_atualizacao = CURRENT_TIMESTAMP
                """,
                (id_treinamento, agora, tempo),
            )
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao registrar fim de criação: {e}")


def registrar_edicao_hitl(id_treinamento: str, db_path: str = DB_PATH) -> None:
    """Incrementa o contador de edições HITL para o treinamento."""
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """
                INSERT INTO roi_eventos (id_treinamento, edicoes_hitl, ultima_atualizacao)
                VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(id_treinamento) DO UPDATE SET
                    edicoes_hitl = edicoes_hitl + 1,
                    ultima_atualizacao = CURRENT_TIMESTAMP
                """,
                (id_treinamento,),
            )
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao registrar edição HITL: {e}")


def registrar_acao_gerada(id_treinamento: str, reutilizada: bool, db_path: str = DB_PATH) -> None:
    """
    Registra se uma ação foi recuperada da biblioteca (reutilizada=True)
    ou criada do zero (reutilizada=False).
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            if reutilizada:
                conn.execute(
                    """
                    INSERT INTO roi_eventos (id_treinamento, acoes_geradas, acoes_reutilizadas, ultima_atualizacao)
                    VALUES (?, 1, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(id_treinamento) DO UPDATE SET
                        acoes_geradas = acoes_geradas + 1,
                        acoes_reutilizadas = acoes_reutilizadas + 1,
                        ultima_atualizacao = CURRENT_TIMESTAMP
                    """,
                    (id_treinamento,),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO roi_eventos (id_treinamento, acoes_geradas, ultima_atualizacao)
                    VALUES (?, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(id_treinamento) DO UPDATE SET
                        acoes_geradas = acoes_geradas + 1,
                        ultima_atualizacao = CURRENT_TIMESTAMP
                    """,
                    (id_treinamento,),
                )
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao registrar ação gerada: {e}")


def registrar_consulta_aura(cache_hit: bool, db_path: str = DB_PATH) -> None:
    """
    Registra uma consulta à Aura.
    cache_hit=True: respondida via cache/RAG sem acionar Gemini Vision.
    cache_hit=False: precisou acionar Gemini Vision.
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            if cache_hit:
                conn.execute(
                    """
                    INSERT INTO roi_eventos (id_treinamento, consultas_aura, consultas_aura_cache, ultima_atualizacao)
                    VALUES ('_global', 1, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(id_treinamento) DO UPDATE SET
                        consultas_aura = consultas_aura + 1,
                        consultas_aura_cache = consultas_aura_cache + 1,
                        ultima_atualizacao = CURRENT_TIMESTAMP
                    """
                )
            else:
                conn.execute(
                    """
                    INSERT INTO roi_eventos (id_treinamento, consultas_aura, ultima_atualizacao)
                    VALUES ('_global', 1, CURRENT_TIMESTAMP)
                    ON CONFLICT(id_treinamento) DO UPDATE SET
                        consultas_aura = consultas_aura + 1,
                        ultima_atualizacao = CURRENT_TIMESTAMP
                    """
                )
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao registrar consulta Aura: {e}")


def calcular_metricas_roi(db_path: str = DB_PATH) -> dict:
    """
    Calcula e retorna todas as métricas de ROI.

    Retorna null para campos sem dados (nunca zero quando não há dados).

    Campos retornados:
      tempo_medio_criacao_segundos  — média do tempo captura→artefato
      taxa_correcao_hitl            — média de edições HITL por roteiro
      indice_reuso_memoria          — proporção de ações reutilizadas vs. criadas
      reducao_suporte_estimada      — proporção de consultas Aura respondidas sem Gemini
      total_treinamentos_rastreados — quantos treinamentos têm dados de ROI

    Requisitos: 3.3.1–3.3.7
    """
    try:
        inicializar_tabela(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Tempo médio de criação (apenas registros com tempo calculado)
            row_tempo = conn.execute(
                """
                SELECT AVG(tempo_criacao_segundos) as media,
                       COUNT(*) as total
                FROM roi_eventos
                WHERE tempo_criacao_segundos IS NOT NULL
                  AND id_treinamento != '_global'
                """
            ).fetchone()

            tempo_medio = None
            total_rastreados = 0
            if row_tempo and row_tempo["total"] > 0:
                tempo_medio = round(row_tempo["media"], 2) if row_tempo["media"] is not None else None
                total_rastreados = row_tempo["total"]

            # Taxa de correção HITL (média de edições por roteiro)
            row_hitl = conn.execute(
                """
                SELECT AVG(edicoes_hitl) as media, COUNT(*) as total
                FROM roi_eventos
                WHERE id_treinamento != '_global'
                  AND edicoes_hitl > 0
                """
            ).fetchone()

            taxa_hitl = None
            if row_hitl and row_hitl["total"] > 0:
                taxa_hitl = round(row_hitl["media"], 2) if row_hitl["media"] is not None else None

            # Índice de reuso de memória
            row_reuso = conn.execute(
                """
                SELECT SUM(acoes_geradas) as total_geradas,
                       SUM(acoes_reutilizadas) as total_reutilizadas
                FROM roi_eventos
                WHERE id_treinamento != '_global'
                """
            ).fetchone()

            indice_reuso = None
            if row_reuso and row_reuso["total_geradas"] and row_reuso["total_geradas"] > 0:
                indice_reuso = round(
                    row_reuso["total_reutilizadas"] / row_reuso["total_geradas"], 4
                )

            # Redução estimada de suporte (consultas Aura via cache/RAG)
            row_aura = conn.execute(
                """
                SELECT SUM(consultas_aura) as total,
                       SUM(consultas_aura_cache) as cache
                FROM roi_eventos
                WHERE id_treinamento = '_global'
                """
            ).fetchone()

            reducao_suporte = None
            if row_aura and row_aura["total"] and row_aura["total"] > 0:
                reducao_suporte = round(row_aura["cache"] / row_aura["total"], 4)

        return {
            "tempo_medio_criacao_segundos":  tempo_medio,
            "taxa_correcao_hitl":            taxa_hitl,
            "indice_reuso_memoria":          indice_reuso,
            "reducao_suporte_estimada":      reducao_suporte,
            "total_treinamentos_rastreados": total_rastreados if total_rastreados > 0 else None,
        }
    except Exception as e:
        logger.error(f"[roi_tracker] Erro ao calcular métricas de ROI: {e}")
        return {
            "tempo_medio_criacao_segundos":  None,
            "taxa_correcao_hitl":            None,
            "indice_reuso_memoria":          None,
            "reducao_suporte_estimada":      None,
            "total_treinamentos_rastreados": None,
        }

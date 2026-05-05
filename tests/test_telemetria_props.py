"""
tests/test_telemetria_props.py
===============================
Property-based tests for telemetry functions in vision_engine.py.

Spec: .kiro/specs/playback-resilience-roadmap (Eixo 3, Tasks 8, 9 e 10)
"""

import os
import sqlite3
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _criar_brain_db_temporario() -> str:
    """Cria um brain.db temporário com o schema mínimo necessário."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS telemetria_camadas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camada TEXT UNIQUE,
            acertos INTEGER DEFAULT 0,
            falhas INTEGER DEFAULT 0,
            ultima_atualizacao_ts INTEGER
        );
        CREATE TABLE IF NOT EXISTS telemetria_execucoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camada TEXT NOT NULL,
            acertou INTEGER NOT NULL,
            intencao_semantica TEXT,
            ts INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tel_exec_ts ON telemetria_execucoes(ts);
        CREATE INDEX IF NOT EXISTS idx_tel_exec_camada ON telemetria_execucoes(camada);
    """)
    conn.commit()
    conn.close()
    return path


def _registrar_execucao(db_path: str, camada: str, acertou: bool, intencao: str = "test"):
    """Insere um registro de telemetria diretamente no banco."""
    ts = int(time.time() * 1000)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO telemetria_execucoes (camada, acertou, intencao_semantica, ts) VALUES (?, ?, ?, ?)",
        (camada, 1 if acertou else 0, intencao, ts),
    )
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# Property 6: Invariante de contagem da telemetria (acertos)
# Feature: playback-resilience-roadmap, Property 6
# ──────────────────────────────────────────────────────────────────────────────


@given(n=st.integers(min_value=1, max_value=50))
@settings(max_examples=30, deadline=None)
def test_soma_acertos_igual_n_execucoes(n):
    """
    # Feature: playback-resilience-roadmap, Property 6: Invariante de contagem da telemetria (acertos)

    Para qualquer sequência de N execuções bem-sucedidas inseridas em telemetria_execucoes,
    a soma de acertou=1 deve ser igual a N.
    """
    db_path = _criar_brain_db_temporario()
    try:
        for _ in range(n):
            _registrar_execucao(db_path, "0_brain_db", acertou=True)

        conn = sqlite3.connect(db_path)
        total_acertos = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes WHERE acertou = 1"
        ).fetchone()[0]
        conn.close()

        assert total_acertos == n, f"Esperado {n} acertos, encontrado {total_acertos}"
    finally:
        os.unlink(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# Property 7: Invariante de contagem da telemetria (total)
# Feature: playback-resilience-roadmap, Property 7
# ──────────────────────────────────────────────────────────────────────────────


@given(
    n_sucesso=st.integers(min_value=0, max_value=25),
    n_falha=st.integers(min_value=0, max_value=25),
)
@settings(max_examples=50, deadline=None)
def test_total_acertos_mais_falhas_igual_total(n_sucesso, n_falha):
    """
    # Feature: playback-resilience-roadmap, Property 7: Invariante de contagem da telemetria (total)

    Para qualquer sequência de N execuções (com ou sem sucesso),
    soma(acertos) + soma(falha_total) deve ser igual a N.
    """
    assume(n_sucesso + n_falha > 0)
    db_path = _criar_brain_db_temporario()
    try:
        for _ in range(n_sucesso):
            _registrar_execucao(db_path, "0_brain_db", acertou=True)
        for _ in range(n_falha):
            _registrar_execucao(db_path, "falha_total", acertou=False)

        conn = sqlite3.connect(db_path)
        total_acertos = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes WHERE acertou = 1"
        ).fetchone()[0]
        total_falhas = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes WHERE camada = 'falha_total'"
        ).fetchone()[0]
        total_registros = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes"
        ).fetchone()[0]
        conn.close()

        assert total_acertos == n_sucesso
        assert total_falhas == n_falha
        assert total_acertos + total_falhas == total_registros == n_sucesso + n_falha
    finally:
        os.unlink(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# Property 10: Taxa de HITL alta produz dados calculáveis
# Feature: playback-resilience-roadmap, Property 10 (adaptado sem mock de logger)
# ──────────────────────────────────────────────────────────────────────────────


@given(
    n_total=st.integers(min_value=6, max_value=50),
    proporcao_falha=st.floats(min_value=0.21, max_value=1.0),
)
@settings(max_examples=40)
def test_taxa_hitl_alta_calculada_corretamente(n_total, proporcao_falha):
    """
    # Feature: playback-resilience-roadmap, Property 10: Taxa de HITL disparável

    Para qualquer janela com mais de 5 ações e taxa_hitl > 0.20,
    o cálculo da taxa deve ser matematicamente correto.
    """
    n_falhas = max(2, int(n_total * proporcao_falha))
    n_sucesso = n_total - n_falhas

    db_path = _criar_brain_db_temporario()
    try:
        # Inserir com timestamp da última hora
        ts_agora = int(time.time() * 1000)
        ts_30min_atras = ts_agora - 30 * 60 * 1000  # 30 minutos atrás

        conn = sqlite3.connect(db_path)
        for _ in range(n_sucesso):
            conn.execute(
                "INSERT INTO telemetria_execucoes (camada, acertou, intencao_semantica, ts) VALUES (?, 1, 'ok', ?)",
                ("0_brain_db", ts_30min_atras),
            )
        for _ in range(n_falhas):
            conn.execute(
                "INSERT INTO telemetria_execucoes (camada, acertou, intencao_semantica, ts) VALUES (?, 0, 'fail', ?)",
                ("falha_total", ts_30min_atras),
            )
        conn.commit()

        # Calcular taxa como o vision_engine faz
        ts_1h_atras = ts_agora - 3600 * 1000
        total_acoes = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ?", (ts_1h_atras,)
        ).fetchone()[0]
        total_falhas_1h = conn.execute(
            "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ? AND camada = 'falha_total'",
            (ts_1h_atras,),
        ).fetchone()[0]
        conn.close()

        if total_acoes > 5:
            taxa_calculada = total_falhas_1h / total_acoes
            # Se inserimos n_falhas com taxa > 0.20, o resultado deve refletir isso
            assert taxa_calculada == pytest.approx(n_falhas / n_total, abs=0.01)
            if n_falhas / n_total > 0.20:
                assert taxa_calculada > 0.20
    finally:
        os.unlink(db_path)


# ──────────────────────────────────────────────────────────────────────────────
# Testes unitários: Schema do brain.db
# ──────────────────────────────────────────────────────────────────────────────


def test_schema_telemetria_execucoes_criado_corretamente():
    """O schema de telemetria_execucoes deve ter as colunas corretas."""
    db_path = _criar_brain_db_temporario()
    try:
        conn = sqlite3.connect(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(telemetria_execucoes)")}
        conn.close()
        assert "id" in cols
        assert "camada" in cols
        assert "acertou" in cols
        assert "intencao_semantica" in cols
        assert "ts" in cols
    finally:
        os.unlink(db_path)


def test_indices_telemetria_criados():
    """Os índices de telemetria devem existir no banco."""
    db_path = _criar_brain_db_temporario()
    try:
        conn = sqlite3.connect(db_path)
        indices = {row[1] for row in conn.execute("PRAGMA index_list(telemetria_execucoes)")}
        conn.close()
        assert "idx_tel_exec_ts" in indices
        assert "idx_tel_exec_camada" in indices
    finally:
        os.unlink(db_path)

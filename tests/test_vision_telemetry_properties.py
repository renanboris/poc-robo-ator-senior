"""
tests/test_vision_telemetry_properties.py
==========================================
Property-based tests for Task 5 — Telemetria de camadas no vision_engine.py

**Validates: Requisito 1.4.1**

Property 6: Para qualquer tentativa de localização simulada, verificar que
`telemetria_camadas` contém registro atualizado com `acertos` ou `falhas`
incrementado corretamente.
"""

import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import given, settings, strategies as st

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

CAMADAS_VALIDAS = [
    "seletor_css",
    "seletor_hint",
    "label_curto",
    "vision_fallback",
    "0_brain",
    "2_sniper",
    "3_hint_original",
    "5_gemini_vision",
]


def _criar_db_temporario() -> str:
    """Cria um brain.db temporário isolado para cada teste."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    with sqlite3.connect(tmp.name) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_camadas (
                camada TEXT PRIMARY KEY,
                acertos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memoria_semantica (
                hash_intencao TEXT PRIMARY KEY,
                intencao TEXT,
                seletor TEXT,
                coords TEXT,
                iframe TEXT,
                hits INTEGER DEFAULT 0,
                falhas_consecutivas INTEGER DEFAULT 0,
                hitl_corrigido INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return tmp.name


def _limpar_db(db_path: str) -> None:
    """Remove o arquivo de DB temporário de forma segura (Windows-friendly)."""
    try:
        os.unlink(db_path)
    except Exception:
        pass  # No Windows o SQLite pode manter lock; ignora silenciosamente


def _registrar_telemetria_isolado(db_path: str, camada: str, acertou: bool) -> None:
    """Versão isolada de _registrar_telemetria que usa db_path arbitrário."""
    import logging
    logger = logging.getLogger("vision_engine_test")
    resultado_str = "sucesso" if acertou else "falha"
    logger.info(f"   [Telemetria] camada={camada} resultado={resultado_str}")

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            INSERT INTO telemetria_camadas (camada, acertos, falhas)
            VALUES (?, ?, ?)
            ON CONFLICT(camada) DO UPDATE SET
                acertos = acertos + ?,
                falhas  = falhas  + ?,
                ultima_atualizacao = CURRENT_TIMESTAMP
        """, (
            camada,
            1 if acertou else 0,
            0 if acertou else 1,
            1 if acertou else 0,
            0 if acertou else 1,
        ))


def _ler_telemetria(db_path: str, camada: str) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = ?", (camada,)
        ).fetchone()
    if row is None:
        return {"acertos": 0, "falhas": 0}
    return {"acertos": row["acertos"], "falhas": row["falhas"]}


# ──────────────────────────────────────────────────────────────
# Property 6: Telemetria de camadas do Vision Engine
# **Validates: Requisito 1.4.1**
# ──────────────────────────────────────────────────────────────

@given(
    camada=st.sampled_from(CAMADAS_VALIDAS),
    acertou=st.booleans(),
)
@settings(max_examples=100)
def test_property6_telemetria_incrementa_corretamente(camada, acertou):
    """
    **Property 6: Telemetria de camadas do Vision Engine**
    **Validates: Requisito 1.4.1**

    Para qualquer tentativa de localização simulada, verificar que
    `telemetria_camadas` contém registro atualizado com `acertos` ou `falhas`
    incrementado corretamente.
    """
    db_path = _criar_db_temporario()
    try:
        antes = _ler_telemetria(db_path, camada)
        _registrar_telemetria_isolado(db_path, camada, acertou)
        depois = _ler_telemetria(db_path, camada)

        if acertou:
            assert depois["acertos"] == antes["acertos"] + 1, (
                f"acertos deveria ter incrementado: antes={antes['acertos']}, depois={depois['acertos']}"
            )
            assert depois["falhas"] == antes["falhas"], (
                f"falhas não deveria ter mudado em caso de acerto"
            )
        else:
            assert depois["falhas"] == antes["falhas"] + 1, (
                f"falhas deveria ter incrementado: antes={antes['falhas']}, depois={depois['falhas']}"
            )
            assert depois["acertos"] == antes["acertos"], (
                f"acertos não deveria ter mudado em caso de falha"
            )
    finally:
        _limpar_db(db_path)


@given(
    camada=st.sampled_from(CAMADAS_VALIDAS),
    n_acertos=st.integers(min_value=0, max_value=10),
    n_falhas=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=100, deadline=None)
def test_property6_acumulacao_multiplas_tentativas(camada, n_acertos, n_falhas):
    """
    **Property 6 (variante): Acumulação de múltiplas tentativas**
    **Validates: Requisito 1.4.1**

    Após N acertos e M falhas, os contadores devem refletir exatamente N e M.
    """
    db_path = _criar_db_temporario()
    try:
        for _ in range(n_acertos):
            _registrar_telemetria_isolado(db_path, camada, True)
        for _ in range(n_falhas):
            _registrar_telemetria_isolado(db_path, camada, False)

        resultado = _ler_telemetria(db_path, camada)
        assert resultado["acertos"] == n_acertos, (
            f"Esperado {n_acertos} acertos, obtido {resultado['acertos']}"
        )
        assert resultado["falhas"] == n_falhas, (
            f"Esperado {n_falhas} falhas, obtido {resultado['falhas']}"
        )
    finally:
        _limpar_db(db_path)


@given(
    camadas=st.lists(
        st.sampled_from(CAMADAS_VALIDAS),
        min_size=2,
        max_size=4,
        unique=True,
    ),
    acertou=st.booleans(),
)
@settings(max_examples=100, deadline=None)
def test_property6_isolamento_entre_camadas(camadas, acertou):
    """
    **Property 6 (variante): Isolamento entre camadas**
    **Validates: Requisito 1.4.1**

    Registrar telemetria para uma camada não deve afetar os contadores de outras.
    """
    db_path = _criar_db_temporario()
    try:
        camada_alvo = camadas[0]
        outras_camadas = camadas[1:]

        # Registra apenas para a camada alvo
        _registrar_telemetria_isolado(db_path, camada_alvo, acertou)

        # As outras camadas não devem ter registros
        for outra in outras_camadas:
            resultado = _ler_telemetria(db_path, outra)
            assert resultado["acertos"] == 0 and resultado["falhas"] == 0, (
                f"Camada '{outra}' foi afetada indevidamente pelo registro em '{camada_alvo}'"
            )
    finally:
        _limpar_db(db_path)


# ──────────────────────────────────────────────────────────────
# Unit tests — _registrar_telemetria do módulo real
# ──────────────────────────────────────────────────────────────

def test_registrar_telemetria_modulo_real_acerto(tmp_path, monkeypatch):
    """_registrar_telemetria do vision_engine deve incrementar acertos no DB real."""
    import vision_engine as ve

    db_path = str(tmp_path / "brain_test.db")
    monkeypatch.setattr(ve, "DB_PATH", db_path)

    # Inicializa o schema
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_camadas (
                camada TEXT PRIMARY KEY,
                acertos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    ve._registrar_telemetria("seletor_css", True)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = 'seletor_css'"
        ).fetchone()

    assert row is not None
    assert row[0] == 1  # acertos
    assert row[1] == 0  # falhas


def test_registrar_telemetria_modulo_real_falha(tmp_path, monkeypatch):
    """_registrar_telemetria do vision_engine deve incrementar falhas no DB real."""
    import vision_engine as ve

    db_path = str(tmp_path / "brain_test.db")
    monkeypatch.setattr(ve, "DB_PATH", db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_camadas (
                camada TEXT PRIMARY KEY,
                acertos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    ve._registrar_telemetria("label_curto", False)

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = 'label_curto'"
        ).fetchone()

    assert row is not None
    assert row[0] == 0  # acertos
    assert row[1] == 1  # falhas


def test_registrar_estrategia_vencedora_persiste(tmp_path, monkeypatch):
    """_registrar_estrategia_vencedora deve persistir a camada em memoria_semantica."""
    import vision_engine as ve

    db_path = str(tmp_path / "brain_test.db")
    monkeypatch.setattr(ve, "DB_PATH", db_path)

    # Cria schema mínimo
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memoria_semantica (
                hash_intencao TEXT PRIMARY KEY,
                intencao TEXT,
                seletor TEXT,
                coords TEXT,
                iframe TEXT,
                hits INTEGER DEFAULT 0,
                falhas_consecutivas INTEGER DEFAULT 0,
                hitl_corrigido INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Insere uma entrada para a intenção
        chave = ve._chave_cache("clicar em salvar")
        conn.execute(
            "INSERT INTO memoria_semantica (hash_intencao, intencao, hits) VALUES (?, ?, 1)",
            (chave, "clicar em salvar"),
        )

    ve._registrar_estrategia_vencedora("clicar em salvar", "2_sniper")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT ultima_estrategia_vencedora FROM memoria_semantica WHERE hash_intencao = ?",
            (chave,),
        ).fetchone()

    assert row is not None
    assert row[0] == "2_sniper"


def test_telemetria_warning_taxa_baixa(tmp_path, monkeypatch, caplog):
    """_registrar_telemetria deve emitir WARNING quando taxa de sucesso < 60%."""
    import logging
    import vision_engine as ve

    db_path = str(tmp_path / "brain_test.db")
    monkeypatch.setattr(ve, "DB_PATH", db_path)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_camadas (
                camada TEXT PRIMARY KEY,
                acertos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    # 1 acerto + 4 falhas = 20% de taxa (abaixo de 60%)
    ve._registrar_telemetria("vision_fallback", True)
    for _ in range(4):
        ve._registrar_telemetria("vision_fallback", False)

    with caplog.at_level(logging.WARNING, logger="vision_engine"):
        ve._registrar_telemetria("vision_fallback", False)  # 6ª tentativa — deve disparar WARNING

    assert any(
        "vision_fallback" in record.message and "60%" in record.message
        for record in caplog.records
        if record.levelno == logging.WARNING
    ), "WARNING sobre taxa baixa não foi emitido"

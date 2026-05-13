"""
Tests for HITL Brain protection: memories corrected by the analyst (hitl_corrigido=1)
should never have their failure counter incremented, and should survive automatic
Brain cleanup (TTL and positional selector invalidation).

Validates: Task 4.2 — _registrar_falha_cache() skips increment for HITL-corrected memories.
Validates: Task 7.3 — HITL-corrected memories survive Brain cleanup logic.
"""

import sqlite3
import tempfile
import os
from unittest.mock import patch

import pytest


@pytest.fixture
def brain_db(tmp_path):
    """Creates a temporary Brain DB with the memoria_semantica table."""
    db_path = str(tmp_path / "test_brain.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE memoria_semantica (
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
    return db_path


def _insert_memory(db_path: str, hash_intencao: str, intencao: str, hitl_corrigido: int = 0, falhas: int = 0):
    """Helper to insert a memory entry."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO memoria_semantica (hash_intencao, intencao, seletor, hitl_corrigido, falhas_consecutivas) VALUES (?, ?, ?, ?, ?)",
            (hash_intencao, intencao, "#some-selector", hitl_corrigido, falhas),
        )


def _get_falhas(db_path: str, hash_intencao: str) -> int:
    """Helper to read falhas_consecutivas for a memory."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT falhas_consecutivas FROM memoria_semantica WHERE hash_intencao = ?",
            (hash_intencao,),
        ).fetchone()
        return row[0] if row else -1


class TestRegistrarFalhaCacheHITLProtection:
    """Tests that _registrar_falha_cache skips increment for HITL-corrected memories."""

    def test_normal_memory_increments_failure(self, brain_db):
        """Normal memories (hitl_corrigido=0) should have falhas incremented."""
        import vision_engine
        from vision_engine import _chave_cache

        intencao = "Clicar no botão Salvar"
        chave = _chave_cache(intencao)
        _insert_memory(brain_db, chave, intencao, hitl_corrigido=0, falhas=0)

        with patch.object(vision_engine, "DB_PATH", brain_db):
            vision_engine._registrar_falha_cache(intencao)

        assert _get_falhas(brain_db, chave) == 1

    def test_hitl_corrected_memory_does_not_increment(self, brain_db):
        """HITL-corrected memories (hitl_corrigido=1) should NOT have falhas incremented."""
        import vision_engine
        from vision_engine import _chave_cache

        intencao = "Clicar no campo Código do Fornecedor"
        chave = _chave_cache(intencao)
        _insert_memory(brain_db, chave, intencao, hitl_corrigido=1, falhas=0)

        with patch.object(vision_engine, "DB_PATH", brain_db):
            vision_engine._registrar_falha_cache(intencao)

        # Should remain at 0 — HITL-corrected memories are protected
        assert _get_falhas(brain_db, chave) == 0

    def test_hitl_corrected_memory_stays_protected_after_multiple_failures(self, brain_db):
        """Even after multiple failure calls, HITL-corrected memories stay at 0 falhas."""
        import vision_engine
        from vision_engine import _chave_cache

        intencao = "Selecionar aba Financeiro"
        chave = _chave_cache(intencao)
        _insert_memory(brain_db, chave, intencao, hitl_corrigido=1, falhas=0)

        with patch.object(vision_engine, "DB_PATH", brain_db):
            for _ in range(5):
                vision_engine._registrar_falha_cache(intencao)

        assert _get_falhas(brain_db, chave) == 0

    def test_normal_memory_accumulates_failures(self, brain_db):
        """Normal memories accumulate failures normally."""
        import vision_engine
        from vision_engine import _chave_cache

        intencao = "Clicar em Incluir"
        chave = _chave_cache(intencao)
        _insert_memory(brain_db, chave, intencao, hitl_corrigido=0, falhas=1)

        with patch.object(vision_engine, "DB_PATH", brain_db):
            vision_engine._registrar_falha_cache(intencao)
            vision_engine._registrar_falha_cache(intencao)

        assert _get_falhas(brain_db, chave) == 3

    def test_nonexistent_memory_does_not_crash(self, brain_db):
        """Calling _registrar_falha_cache for a non-existent memory should not crash."""
        import vision_engine

        intencao = "Ação que não existe no Brain"

        with patch.object(vision_engine, "DB_PATH", brain_db):
            # Should not raise
            vision_engine._registrar_falha_cache(intencao)


class TestHITLBrainCleanupSurvival:
    """Tests that HITL-corrected memories survive the Brain's automatic cleanup logic.

    The cleanup queries in _init_db() perform two operations:
    1. DELETE old memories (>90 days, hits < 2, hitl_corrigido=0)
    2. UPDATE to nullify positional selectors (:nth-child, :nth-of-type) for non-HITL memories

    Memories with hitl_corrigido=1 must be protected from BOTH operations.

    Validates: Task 7.3 — Testar persistência: correção HITL sobrevive a limpeza do Brain
    """

    TTL_CLEANUP_SQL = """
        DELETE FROM memoria_semantica
        WHERE ultima_atualizacao < datetime('now', '-90 days')
          AND hits < 2
          AND (hitl_corrigido IS NULL OR hitl_corrigido = 0)
    """

    POSITIONAL_CLEANUP_SQL = """
        UPDATE memoria_semantica
        SET seletor = NULL
        WHERE seletor IS NOT NULL
          AND (
            seletor LIKE '%:nth-child(%'
            OR seletor LIKE '%:nth-of-type(%'
          )
          AND seletor NOT LIKE '%.ui-chkbox%'
          AND seletor NOT LIKE '%p-checkbox%'
          AND (hitl_corrigido IS NULL OR hitl_corrigido = 0)
    """

    def _insert_memory_with_timestamp(
        self, db_path: str, hash_intencao: str, intencao: str,
        seletor: str = "#some-selector", hitl_corrigido: int = 0,
        hits: int = 1, days_old: int = 0
    ):
        """Helper to insert a memory with a specific age (days_old days in the past)."""
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                """INSERT INTO memoria_semantica
                   (hash_intencao, intencao, seletor, hitl_corrigido, hits, ultima_atualizacao)
                   VALUES (?, ?, ?, ?, ?, datetime('now', ?))""",
                (hash_intencao, intencao, seletor, hitl_corrigido, hits, f'-{days_old} days'),
            )

    def _memory_exists(self, db_path: str, hash_intencao: str) -> bool:
        """Check if a memory entry exists in the DB."""
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM memoria_semantica WHERE hash_intencao = ?",
                (hash_intencao,),
            ).fetchone()
            return row is not None

    def _get_seletor(self, db_path: str, hash_intencao: str) -> str | None:
        """Get the seletor value for a memory entry."""
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT seletor FROM memoria_semantica WHERE hash_intencao = ?",
                (hash_intencao,),
            ).fetchone()
            return row[0] if row else None

    # ── TTL Cleanup Tests ──────────────────────────────────────────────────

    def test_hitl_memory_survives_ttl_cleanup(self, brain_db):
        """HITL-corrected memories (hitl_corrigido=1) older than 90 days should NOT be deleted."""
        self._insert_memory_with_timestamp(
            brain_db, "hitl_old_001", "Clicar no botão Salvar",
            hitl_corrigido=1, hits=1, days_old=120,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.TTL_CLEANUP_SQL)

        assert self._memory_exists(brain_db, "hitl_old_001"), \
            "HITL-corrected memory was deleted by TTL cleanup — it should be protected!"

    def test_normal_old_memory_is_cleaned_by_ttl(self, brain_db):
        """Normal memories (hitl_corrigido=0) older than 90 days with hits < 2 should be deleted."""
        self._insert_memory_with_timestamp(
            brain_db, "normal_old_001", "Clicar em Incluir",
            hitl_corrigido=0, hits=1, days_old=120,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.TTL_CLEANUP_SQL)

        assert not self._memory_exists(brain_db, "normal_old_001"), \
            "Normal old memory was NOT deleted by TTL cleanup — it should have been removed!"

    # ── Positional Selector Cleanup Tests ──────────────────────────────────

    def test_hitl_memory_positional_selector_survives_cleanup(self, brain_db):
        """HITL-corrected memories with positional selectors should NOT have their selector nullified."""
        positional_selector = "tr:nth-child(2) > td > button"
        self._insert_memory_with_timestamp(
            brain_db, "hitl_pos_001", "Clicar na segunda linha da tabela",
            seletor=positional_selector, hitl_corrigido=1, hits=5, days_old=10,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.POSITIONAL_CLEANUP_SQL)

        result = self._get_seletor(brain_db, "hitl_pos_001")
        assert result == positional_selector, \
            f"HITL-corrected positional selector was nullified! Got: {result}"

    def test_normal_positional_selector_is_cleaned(self, brain_db):
        """Normal memories with positional selectors should have their selector nullified."""
        positional_selector = "div:nth-child(3) > span.label"
        self._insert_memory_with_timestamp(
            brain_db, "normal_pos_001", "Clicar no terceiro item",
            seletor=positional_selector, hitl_corrigido=0, hits=5, days_old=10,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.POSITIONAL_CLEANUP_SQL)

        result = self._get_seletor(brain_db, "normal_pos_001")
        assert result is None, \
            f"Normal positional selector was NOT nullified! Got: {result}"

    # ── Additional edge cases ──────────────────────────────────────────────

    def test_hitl_memory_with_nth_of_type_survives(self, brain_db):
        """HITL-corrected memories with :nth-of-type selectors are also protected."""
        selector = "li:nth-of-type(4) > a"
        self._insert_memory_with_timestamp(
            brain_db, "hitl_nthtype_001", "Clicar no quarto link do menu",
            seletor=selector, hitl_corrigido=1, hits=3, days_old=5,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.POSITIONAL_CLEANUP_SQL)

        result = self._get_seletor(brain_db, "hitl_nthtype_001")
        assert result == selector, \
            f"HITL :nth-of-type selector was nullified! Got: {result}"

    def test_normal_memory_with_nth_of_type_is_cleaned(self, brain_db):
        """Normal memories with :nth-of-type selectors should be nullified."""
        selector = "li:nth-of-type(2) > span"
        self._insert_memory_with_timestamp(
            brain_db, "normal_nthtype_001", "Clicar no segundo item",
            seletor=selector, hitl_corrigido=0, hits=3, days_old=5,
        )

        with sqlite3.connect(brain_db) as conn:
            conn.execute(self.POSITIONAL_CLEANUP_SQL)

        result = self._get_seletor(brain_db, "normal_nthtype_001")
        assert result is None, \
            f"Normal :nth-of-type selector was NOT nullified! Got: {result}"

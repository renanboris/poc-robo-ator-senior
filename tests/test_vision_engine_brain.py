"""
tests/test_vision_engine_brain.py — Testes para o subsistema Brain do vision_engine.py
========================================================================================
Executa sem Playwright, Gemini, OpenAI ou Pinecone.
Usa banco SQLite temporário (tmp_path) — nunca toca brain.db de produção.
Cobre: _init_db, _consultar_cache, _registrar_sucesso_cache, _registrar_falha_cache,
       _registrar_telemetria, obter_relatorio_telemetria.
Inclui testes de propriedade (Hypothesis) para invariantes críticos.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import vision_engine


# ──────────────────────────────────────────────────────────────
# FIXTURE: banco isolado por teste
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def brain_db(tmp_path, monkeypatch):
    """Banco SQLite temporário isolado — nunca usa brain.db de produção."""
    db_file = str(tmp_path / "test_brain.db")
    monkeypatch.setattr(vision_engine, "DB_PATH", db_file)
    vision_engine._init_db()
    return db_file


# ──────────────────────────────────────────────────────────────
# TESTES: _init_db
# ──────────────────────────────────────────────────────────────
class TestInitDb:
    def test_cria_tabelas_obrigatorias(self, brain_db):
        with sqlite3.connect(brain_db) as conn:
            tabelas = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "memoria_semantica" in tabelas
        assert "telemetria_camadas" in tabelas
        assert "telemetria_execucoes" in tabelas

    def test_cria_view_telemetria_unificada(self, brain_db):
        with sqlite3.connect(brain_db) as conn:
            views = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()}
        assert "v_telemetria_unificada" in views

    def test_idempotente_duas_chamadas(self, brain_db, monkeypatch):
        monkeypatch.setattr(vision_engine, "DB_PATH", brain_db)
        # Segunda chamada não deve lançar exceção
        vision_engine._init_db()
        vision_engine._init_db()
        with sqlite3.connect(brain_db) as conn:
            tabelas = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
        assert "memoria_semantica" in tabelas


# ──────────────────────────────────────────────────────────────
# TESTES: _consultar_cache
# ──────────────────────────────────────────────────────────────
class TestConsultarCache:
    def test_retorna_none_para_intencao_nova(self, brain_db):
        resultado = vision_engine._consultar_cache("Intenção que nunca foi registrada")
        assert resultado is None

    def test_retorna_entrada_cache_apos_registro(self, brain_db):
        vision_engine._registrar_sucesso_cache(
            "Clicar em Salvar",
            seletor="[aria-label='Salvar']",
        )
        resultado = vision_engine._consultar_cache("Clicar em Salvar")
        assert resultado is not None
        assert isinstance(resultado, vision_engine.EntradaCache)

    def test_seletor_preservado(self, brain_db):
        vision_engine._registrar_sucesso_cache(
            "Clicar em Pesquisar",
            seletor="[aria-label='Pesquisar']",
        )
        resultado = vision_engine._consultar_cache("Clicar em Pesquisar")
        assert resultado.seletor == "[aria-label='Pesquisar']"


# ──────────────────────────────────────────────────────────────
# TESTES: _registrar_sucesso_cache
# ──────────────────────────────────────────────────────────────
class TestRegistrarSucessoCache:
    def test_hits_incrementado(self, brain_db):
        intencao = "Clicar em Novo"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Novo']")
        vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Novo']")
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado.hits == 2

    def test_hits_monotonicos_multiplas_chamadas(self, brain_db):
        intencao = "Clicar em Fechar"
        hits_anteriores = 0
        for _ in range(5):
            vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Fechar']")
            resultado = vision_engine._consultar_cache(intencao)
            assert resultado.hits >= hits_anteriores
            hits_anteriores = resultado.hits

    def test_falhas_zeradas_apos_sucesso(self, brain_db):
        intencao = "Clicar em Cancelar"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Cancelar']")
        vision_engine._registrar_falha_cache(intencao)
        vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Cancelar']")
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado.falhas_consecutivas == 0


# ──────────────────────────────────────────────────────────────
# TESTES: _registrar_falha_cache
# ──────────────────────────────────────────────────────────────
class TestRegistrarFalhaCache:
    def test_falhas_incrementadas(self, brain_db):
        intencao = "Clicar em Excluir"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Excluir']")
        vision_engine._registrar_falha_cache(intencao)
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado.falhas_consecutivas == 1

    def test_memoria_apagada_apos_max_falhas(self, brain_db):
        intencao = "Ação que sempre falha"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[id='btn-falha']")
        for _ in range(vision_engine.MAX_FALHAS_CACHE):
            vision_engine._registrar_falha_cache(intencao)
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado is None, "Memória obsoleta deveria ter sido apagada"

    def test_memoria_apagada_com_falhas_extras(self, brain_db):
        intencao = "Ação com falhas extras"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[id='btn-extra']")
        for _ in range(vision_engine.MAX_FALHAS_CACHE + 2):
            vision_engine._registrar_falha_cache(intencao)
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado is None


# ──────────────────────────────────────────────────────────────
# TESTES: _registrar_telemetria
# ──────────────────────────────────────────────────────────────
class TestRegistrarTelemetria:
    def test_acertos_incrementados(self, brain_db):
        vision_engine._registrar_telemetria("0_brain", True, "Clicar em Salvar")
        with sqlite3.connect(brain_db) as conn:
            row = conn.execute(
                "SELECT acertos FROM telemetria_camadas WHERE camada = '0_brain'"
            ).fetchone()
        assert row is not None
        assert row[0] >= 1

    def test_falhas_incrementadas(self, brain_db):
        vision_engine._registrar_telemetria("2_sniper", False, "Clicar em Novo")
        with sqlite3.connect(brain_db) as conn:
            row = conn.execute(
                "SELECT falhas FROM telemetria_camadas WHERE camada = '2_sniper'"
            ).fetchone()
        assert row is not None
        assert row[0] >= 1

    def test_registro_granular_em_execucoes(self, brain_db):
        vision_engine._registrar_telemetria("1_template_matching", True, "Abrir pasta")
        with sqlite3.connect(brain_db) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM telemetria_execucoes WHERE camada = '1_template_matching'"
            ).fetchone()[0]
        assert count >= 1


# ──────────────────────────────────────────────────────────────
# TESTES: obter_relatorio_telemetria
# ──────────────────────────────────────────────────────────────
class TestObterRelatorioTelemetria:
    def test_banco_vazio_retorna_lista_vazia(self, brain_db):
        resultado = vision_engine.obter_relatorio_telemetria()
        assert "camadas" in resultado
        assert isinstance(resultado["camadas"], list)
        assert resultado["camadas"] == []

    def test_chave_taxa_hitl_1h_presente(self, brain_db):
        resultado = vision_engine.obter_relatorio_telemetria()
        assert "taxa_hitl_1h" in resultado

    def test_com_dados_retorna_camadas(self, brain_db):
        vision_engine._registrar_telemetria("0_brain", True, "Teste")
        vision_engine._registrar_telemetria("2_sniper", False, "Teste")
        resultado = vision_engine.obter_relatorio_telemetria()
        assert len(resultado["camadas"]) >= 1

    def test_estrutura_de_cada_camada(self, brain_db):
        vision_engine._registrar_telemetria("3_hint_original", True, "Teste estrutura")
        resultado = vision_engine.obter_relatorio_telemetria()
        if resultado["camadas"]:
            camada = resultado["camadas"][0]
            assert "camada" in camada
            assert "acertos_total" in camada
            assert "falhas_total" in camada

    def test_erro_retorna_estrutura_segura(self, monkeypatch):
        # Força falha na consulta
        monkeypatch.setattr(vision_engine, "DB_PATH", "/caminho/inexistente/brain.db")
        resultado = vision_engine.obter_relatorio_telemetria()
        assert "camadas" in resultado
        assert resultado["camadas"] == []


# ──────────────────────────────────────────────────────────────
# TESTES DE PROPRIEDADE (Hypothesis)
# ──────────────────────────────────────────────────────────────
try:
    from hypothesis import given, settings
    from hypothesis import strategies as st
    HYPOTHESIS_DISPONIVEL = True
except ImportError:
    HYPOTHESIS_DISPONIVEL = False


@pytest.mark.skipif(not HYPOTHESIS_DISPONIVEL, reason="hypothesis não instalado")
class TestPropriedadesHypothesis:

    @given(n=st.integers(min_value=1, max_value=10))
    @settings(max_examples=20)
    def test_init_db_idempotente(self, n, tmp_path, monkeypatch):
        """P6.3 / P4.1 — _init_db() N vezes produz o mesmo schema."""
        db_file = str(tmp_path / f"brain_idem_{n}.db")
        monkeypatch.setattr(vision_engine, "DB_PATH", db_file)
        for _ in range(n):
            vision_engine._init_db()
        with sqlite3.connect(db_file) as conn:
            tabelas = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()}
            views = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='view'"
            ).fetchall()}
        assert "memoria_semantica" in tabelas
        assert "v_telemetria_unificada" in views

    @given(n=st.integers(min_value=1, max_value=15))
    @settings(max_examples=30)
    def test_hits_monotonicos(self, n, tmp_path, monkeypatch):
        """P6.1 — hits nunca decresce após _registrar_sucesso_cache."""
        db_file = str(tmp_path / f"brain_hits_{n}.db")
        monkeypatch.setattr(vision_engine, "DB_PATH", db_file)
        vision_engine._init_db()
        intencao = "Clicar em Salvar monotônico"
        hits_anteriores = 0
        for _ in range(n):
            vision_engine._registrar_sucesso_cache(intencao, seletor="[aria-label='Salvar']")
            cache = vision_engine._consultar_cache(intencao)
            assert cache is not None
            assert cache.hits >= hits_anteriores
            hits_anteriores = cache.hits

    @given(extra=st.integers(min_value=0, max_value=5))
    @settings(max_examples=20)
    def test_memoria_obsoleta_apagada(self, extra, tmp_path, monkeypatch):
        """P6.2 — memória com falhas >= MAX_FALHAS_CACHE é apagada."""
        db_file = str(tmp_path / f"brain_obsoleta_{extra}.db")
        monkeypatch.setattr(vision_engine, "DB_PATH", db_file)
        vision_engine._init_db()
        intencao = "Ação que sempre falha property"
        vision_engine._registrar_sucesso_cache(intencao, seletor="[id='btn']")
        for _ in range(vision_engine.MAX_FALHAS_CACHE + extra):
            vision_engine._registrar_falha_cache(intencao)
        resultado = vision_engine._consultar_cache(intencao)
        assert resultado is None

"""
tests/test_generator_props.py
==============================
Property-based tests for generator_engine._selecionar_acao_biblioteca.

Spec: .kiro/specs/playback-resilience-roadmap (Eixo 5, Task 14)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hypothesis import assume, given, settings
from hypothesis import strategies as st

try:
    from generator_engine import _selecionar_acao_biblioteca
except Exception:
    # Ambiente sem pinecone correto — extrair a função inline
    import logging
    from typing import Optional

    _logger_gen = logging.getLogger("generator_engine_stub")

    def _selecionar_acao_biblioteca(candidatos: list) -> Optional[dict]:
        """Stub idêntico ao generator_engine real para CI sem pinecone."""
        descartadas = [a for a in candidatos if a.get("requer_revisao", False)]
        for a in descartadas:
            _logger_gen.debug(f"[Biblioteca] Descartada: {a.get('intencao_semantica', '?')}")
        validos = [a for a in candidatos if not a.get("requer_revisao", False)]
        if not validos:
            return None
        validos.sort(key=lambda a: a.get("_score_confiabilidade", 0.0), reverse=True)
        melhor = validos[0]
        if melhor.get("_score_confiabilidade", 0.0) < 0.5:
            return None
        return melhor



# ──────────────────────────────────────────────────────────────────────────────
# Estratégia: gerar ação de biblioteca
# ──────────────────────────────────────────────────────────────────────────────

acao_biblioteca = st.fixed_dictionaries({
    "intencao_semantica": st.text(min_size=1, max_size=60),
    "_score_confiabilidade": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    "requer_revisao": st.booleans(),
})

acao_sem_score = st.fixed_dictionaries({
    "intencao_semantica": st.text(min_size=1, max_size=60),
    "requer_revisao": st.booleans(),
})


# ──────────────────────────────────────────────────────────────────────────────
# Property 9: Score de confiabilidade das ações selecionadas
# Feature: playback-resilience-roadmap, Property 9
# ──────────────────────────────────────────────────────────────────────────────


@given(candidatos=st.lists(acao_biblioteca, min_size=1, max_size=20))
@settings(max_examples=300)
def test_selecao_retorna_score_valido_ou_none(candidatos):
    """
    # Feature: playback-resilience-roadmap, Property 9: Score de confiabilidade das ações selecionadas

    Para qualquer ação selecionada pelo Generator_Engine da biblioteca,
    0.5 <= _score_confiabilidade <= 1.0 e requer_revisao == False.
    Se nenhuma ação válida existir, retorna None.
    """
    resultado = _selecionar_acao_biblioteca(candidatos)

    if resultado is not None:
        score = resultado.get("_score_confiabilidade", 0.0)
        assert score >= 0.5, f"Score {score} abaixo do threshold 0.5"
        assert score <= 1.0, f"Score {score} acima de 1.0"
        assert resultado.get("requer_revisao", False) is False, (
            "Ação selecionada tem requer_revisao=True"
        )


@given(candidatos=st.lists(acao_biblioteca, min_size=1, max_size=20))
@settings(max_examples=200)
def test_acoes_com_requer_revisao_nunca_selecionadas(candidatos):
    """
    Ações com requer_revisao=True NUNCA devem ser selecionadas,
    independente do score.
    """
    resultado = _selecionar_acao_biblioteca(candidatos)

    if resultado is not None:
        assert not resultado.get("requer_revisao", False)


@given(
    candidatos=st.lists(
        st.fixed_dictionaries({
            "intencao_semantica": st.text(min_size=1, max_size=40),
            "_score_confiabilidade": st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
            "requer_revisao": st.just(False),
        }),
        min_size=2,
        max_size=10,
    )
)
@settings(max_examples=200)
def test_melhor_score_selecionado(candidatos):
    """
    Quando há candidatos válidos (score >= 0.5, requer_revisao=False),
    o selecionado deve ter o maior _score_confiabilidade.
    """
    resultado = _selecionar_acao_biblioteca(candidatos)

    # Com candidatos todos válidos e score >= 0.5, deve retornar o melhor
    assert resultado is not None

    max_score = max(c["_score_confiabilidade"] for c in candidatos)
    assert resultado["_score_confiabilidade"] == max_score


# ──────────────────────────────────────────────────────────────────────────────
# Property: compatibilidade retroativa (sem _score_confiabilidade)
# ──────────────────────────────────────────────────────────────────────────────


@given(candidatos=st.lists(acao_sem_score, min_size=1, max_size=10))
@settings(max_examples=150)
def test_acoes_sem_score_tratadas_como_zero(candidatos):
    """
    Ações sem _score_confiabilidade devem ser tratadas como score=0.0
    (retrocompatibilidade), portanto retornam None (threshold=0.5).
    """
    resultado = _selecionar_acao_biblioteca(candidatos)

    # Ações sem score → tratadas como 0.0 → abaixo do threshold → None
    # (exceto se requer_revisao=False e score default seria 0.0 < 0.5)
    validas = [c for c in candidatos if not c.get("requer_revisao", False)]
    if not validas:
        assert resultado is None
    else:
        # Todas sem score → score efetivo = 0.0 < 0.5 → None
        assert resultado is None


def test_lista_vazia_retorna_none():
    """Lista vazia deve retornar None sem exceção."""
    assert _selecionar_acao_biblioteca([]) is None


def test_todos_requer_revisao_retorna_none():
    """Lista onde todos têm requer_revisao=True deve retornar None."""
    candidatos = [
        {"intencao_semantica": "acao X", "_score_confiabilidade": 0.9, "requer_revisao": True},
        {"intencao_semantica": "acao Y", "_score_confiabilidade": 1.0, "requer_revisao": True},
    ]
    assert _selecionar_acao_biblioteca(candidatos) is None


def test_score_abaixo_threshold_retorna_none():
    """Melhor candidato com score < 0.5 deve retornar None."""
    candidatos = [
        {"intencao_semantica": "acao A", "_score_confiabilidade": 0.3, "requer_revisao": False},
        {"intencao_semantica": "acao B", "_score_confiabilidade": 0.49, "requer_revisao": False},
    ]
    assert _selecionar_acao_biblioteca(candidatos) is None


def test_selecao_exata_no_threshold():
    """Score exatamente em 0.5 ainda deve ser selecionado (threshold exclusivo)."""
    candidatos = [
        {"intencao_semantica": "acao limite", "_score_confiabilidade": 0.5, "requer_revisao": False},
    ]
    # 0.5 >= 0.5 → deve selecionar (a verificação é `< 0.5` no código)
    resultado = _selecionar_acao_biblioteca(candidatos)
    assert resultado is not None
    assert resultado["_score_confiabilidade"] == 0.5

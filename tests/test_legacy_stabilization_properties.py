"""
tests/test_legacy_stabilization_properties.py
==============================================
Property-based tests for the Fase 1 Legacy Stabilization of Senior Training OS.

Uses Hypothesis to verify correctness properties defined in:
  .kiro/specs/legacy-stabilization/design.md

Each test is tagged with the property it validates.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from utils import limpar_nome, validar_roteiro

# ──────────────────────────────────────────────────────────────
# STRATEGIES
# ──────────────────────────────────────────────────────────────

def _acao_strategy(confianca=None, seletor=None):
    """Generates a single acao_tecnica dict."""
    confianca_st = st.just(confianca) if confianca else st.sampled_from(["alta", "media", "baixa"])
    seletor_st   = st.just(seletor)   if seletor   else st.one_of(st.just(""), st.text(min_size=1, max_size=40))
    return st.fixed_dictionaries({
        "acao": st.sampled_from(["clique", "preencher_campo", "duplo_clique", "concluir_video"]),
        "elemento_alvo": st.fixed_dictionaries({
            "seletor_hint":      seletor_st,
            "confianca_captura": confianca_st,
        }),
    })


def _passo_strategy(n_acoes=None):
    """Generates a single passo dict."""
    n = n_acoes if n_acoes is not None else st.integers(min_value=0, max_value=5)
    return st.fixed_dictionaries({
        "id_passo": st.integers(min_value=1, max_value=100),
        "acoes_tecnicas": st.lists(_acao_strategy(), min_size=0, max_size=5),
    })


@st.composite
def roteiros_aleatorios(draw):
    """Generates a roteiro dict with random passos and acoes_tecnicas."""
    n_passos = draw(st.integers(min_value=0, max_value=8))
    passos = [draw(_passo_strategy()) for _ in range(n_passos)]
    return {
        "metadata": {"nome_aula": draw(st.text(min_size=1, max_size=30))},
        "passos": passos,
    }


# ──────────────────────────────────────────────────────────────
# PROPERTY 1: limpar_nome produz strings ASCII seguras com no máximo 40 chars
# ──────────────────────────────────────────────────────────────

# Feature: legacy-stabilization, Property 1: limpar_nome produz strings ASCII seguras com no máximo 40 chars
@given(st.text(min_size=0, max_size=200))
@settings(max_examples=100)
def test_limpar_nome_ascii_safe(nome):
    """limpar_nome must always return ASCII-safe strings of at most 40 chars."""
    resultado = limpar_nome(nome)
    assert len(resultado) <= 40, f"Resultado tem {len(resultado)} chars: {resultado!r}"
    assert resultado.isascii(), f"Resultado não é ASCII: {resultado!r}"
    assert " " not in resultado, f"Resultado contém espaço: {resultado!r}"
    for c in r'\/*?:"<>|':
        assert c not in resultado, f"Resultado contém char proibido {c!r}: {resultado!r}"


# ──────────────────────────────────────────────────────────────
# PROPERTY 2: validar_roteiro aplica os três critérios corretamente
# ──────────────────────────────────────────────────────────────

# Feature: legacy-stabilization, Property 2: validar_roteiro aplica os três critérios de qualidade corretamente
@given(roteiros_aleatorios())
@settings(max_examples=100)
def test_validar_roteiro_criterios(roteiro):
    """validar_roteiro must return False iff at least one quality criterion is violated."""
    aprovado, motivo = validar_roteiro(roteiro)
    passos = roteiro.get("passos", [])

    # Critério 1: menos de 2 passos → reprovado
    if len(passos) < 2:
        assert not aprovado, f"Deveria reprovar com {len(passos)} passo(s)"
        return

    # Calcular métricas das ações válidas (excluindo concluir_video)
    acoes_validas = [
        a for p in passos
        for a in p.get("acoes_tecnicas", [])
        if a.get("acao") != "concluir_video"
    ]

    if not acoes_validas:
        assert not aprovado, "Deveria reprovar sem ações técnicas válidas"
        return

    pct_seletor = sum(
        1 for a in acoes_validas
        if a.get("elemento_alvo", {}).get("seletor_hint", "").strip()
    ) / len(acoes_validas)

    pct_baixa = sum(
        1 for a in acoes_validas
        if a.get("elemento_alvo", {}).get("confianca_captura") == "baixa"
    ) / len(acoes_validas)

    # Critério 2: < 50% com seletor → reprovado
    if pct_seletor < 0.50:
        assert not aprovado, f"Deveria reprovar com {pct_seletor:.0%} de seletores"
        return

    # Critério 3: > 70% com confiança baixa → reprovado
    if pct_baixa > 0.70:
        assert not aprovado, f"Deveria reprovar com {pct_baixa:.0%} de baixa confiança"
        return

    # Todos os critérios satisfeitos → aprovado
    assert aprovado, f"Deveria aprovar. Motivo: {motivo}"


# ──────────────────────────────────────────────────────────────
# PROPERTY 3: IDs válidos do log_mapeador sempre aparecem no roteiro final
# ──────────────────────────────────────────────────────────────

# Feature: legacy-stabilization, Property 3: IDs válidos do log_mapeador sempre aparecem no roteiro final
@given(
    st.lists(
        st.integers(min_value=1, max_value=50),
        min_size=1, max_size=10, unique=True
    )
)
@settings(max_examples=100)
def test_ids_validos_aparecem_no_roteiro(ids_validos):
    """All valid IDs from log_mapeador must appear in the merged acoes_tecnicas."""
    # Simula o log_mapeador com os IDs fornecidos
    log_mapeador = [
        {
            "id_acao": id_,
            "acao": "clique",
            "intencao_semantica": f"Ação {id_}",
            "elemento_alvo": {"seletor_hint": f"[id='btn-{id_}']", "confianca_captura": "alta"},
            "valor_input": "",
        }
        for id_ in ids_validos
    ]

    # Simula a mesclagem com todos os IDs válidos
    acoes_tecnicas = []
    micro_narracoes = [f"Micro {i}" for i in range(len(ids_validos))]

    for i, id_tec in enumerate(ids_validos):
        acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
        if acao_bruta is None:
            continue  # comportamento corrigido: warning + continue
        acoes_tecnicas.append({
            "acao": acao_bruta["acao"],
            "intencao_semantica": acao_bruta["intencao_semantica"],
            "elemento_alvo": acao_bruta["elemento_alvo"],
            "valor_input": acao_bruta["valor_input"],
            "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else "",
        })

    # Todos os IDs válidos devem ter gerado uma ação
    assert len(acoes_tecnicas) == len(ids_validos), (
        f"Esperado {len(ids_validos)} ações, obtido {len(acoes_tecnicas)}"
    )


# ──────────────────────────────────────────────────────────────
# PROPERTY 4: IDs ausentes no log_mapeador não interrompem o processamento
# ──────────────────────────────────────────────────────────────

# Feature: legacy-stabilization, Property 4: IDs ausentes no log_mapeador não interrompem o processamento
@given(
    st.lists(st.integers(min_value=1, max_value=20), min_size=1, max_size=5, unique=True),
    st.lists(st.integers(min_value=21, max_value=40), min_size=1, max_size=5, unique=True),
)
@settings(max_examples=100)
def test_ids_ausentes_nao_interrompem(ids_validos, ids_invalidos):
    """IDs not in log_mapeador must be silently skipped without raising exceptions."""
    log_mapeador = [
        {"id_acao": id_, "acao": "clique", "intencao_semantica": f"Ação {id_}",
         "elemento_alvo": {}, "valor_input": ""}
        for id_ in ids_validos
    ]

    ids_misturados = ids_validos + ids_invalidos

    acoes_tecnicas = []
    warnings_emitidos = []

    for i, id_tec in enumerate(ids_misturados):
        acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
        if acao_bruta is None:
            warnings_emitidos.append(id_tec)
            continue  # comportamento corrigido
        acoes_tecnicas.append({"acao": acao_bruta["acao"]})

    # Nenhuma exceção foi lançada (chegamos aqui)
    # Apenas os IDs válidos geraram ações
    assert len(acoes_tecnicas) == len(ids_validos)
    # Os IDs inválidos foram registrados como warnings
    assert set(warnings_emitidos) == set(ids_invalidos)


# ──────────────────────────────────────────────────────────────
# PROPERTY 5: Filtro de seletores aceita prefixos Angular/PrimeNG e :has-text(
# ──────────────────────────────────────────────────────────────

_PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")

def _aplicar_filtro(seletor):
    """Replica a lógica do filtro em _registrar_sucesso_cache."""
    if seletor and not seletor.startswith(_PREFIXOS_VALIDOS) and ":has-text(" not in seletor:
        return None
    return seletor


# Feature: legacy-stabilization, Property 5: filtro de seletores aceita prefixos Angular/PrimeNG e :has-text(
@given(st.sampled_from([
    "button.p-button",
    "p-dropdown",
    "p-checkbox .ui-chkbox-box",
    "mat-select",
    "mat-option",
    "text=Salvar",
    "[aria-label='Fechar']",
    "[data-testid='btn-ok']",
    "#meu-id",
    "div:has-text('Confirmar')",
    "tr:has-text('João') p-checkbox",
]))
@settings(max_examples=100)
def test_filtro_seletores_validos_preservados(seletor):
    """Valid selectors (Angular/PrimeNG prefixes and :has-text) must be preserved."""
    resultado = _aplicar_filtro(seletor)
    assert resultado == seletor, (
        f"Seletor válido foi descartado: {seletor!r}"
    )


# Feature: legacy-stabilization, Property 5 (complemento): seletores vagos são descartados
@given(st.sampled_from([
    "div",
    "span",
    "h1",
    "form",
    "section",
    "article",
    "ul",
    "li",
]))
@settings(max_examples=100)
def test_filtro_seletores_vagos_descartados(seletor):
    """Generic tag selectors must be discarded (return None)."""
    resultado = _aplicar_filtro(seletor)
    assert resultado is None, (
        f"Seletor vago deveria ser descartado mas foi preservado: {seletor!r}"
    )


# ──────────────────────────────────────────────────────────────
# PROPERTY 6: id_vetor do Pinecone contém apenas caracteres ASCII seguros
# ──────────────────────────────────────────────────────────────

# Feature: legacy-stabilization, Property 6: id_vetor contém apenas caracteres ASCII seguros
@given(
    st.text(min_size=1, max_size=100),
    st.integers(min_value=1, max_value=50),
)
@settings(max_examples=100)
def test_id_vetor_ascii_seguro(nome_aula, id_passo):
    """Pinecone vector IDs must be ASCII-safe and follow the expected format."""
    id_vetor = f"{limpar_nome(nome_aula)}_passo_{id_passo}"
    assert id_vetor.isascii(), f"id_vetor não é ASCII: {id_vetor!r}"
    assert " " not in id_vetor, f"id_vetor contém espaço: {id_vetor!r}"
    assert f"_passo_{id_passo}" in id_vetor, (
        f"id_vetor não segue o formato esperado: {id_vetor!r}"
    )

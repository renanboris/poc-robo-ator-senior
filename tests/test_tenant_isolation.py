"""
tests/test_tenant_isolation.py
================================
Property-Based Tests para isolamento por tenant (Task 15).

Property 9: Isolamento de tenant no Brain
  Para quaisquer dois tenants A e B distintos, uma entrada gravada para A
  nao deve ser retornada em consultas ao Brain para B.
  Validates: Requisito 2.5.4

Property 10: Isolamento de tenant no Pinecone
  Para qualquer requisicao com tenant_id T, upsert e query ao Pinecone
  devem usar exclusivamente o namespace de T (mock do cliente Pinecone).
  Validates: Requisito 2.5.3
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

from brain_backend import SQLiteBrainBackend, EntradaBrain


# ──────────────────────────────────────────────────────────────
# Estrategias Hypothesis
# ──────────────────────────────────────────────────────────────

tenant_id_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd"), whitelist_characters="_-"),
    min_size=1,
    max_size=30,
)

intencao_strategy = st.text(min_size=1, max_size=80)

seletor_strategy = st.one_of(
    st.just(""),
    st.text(min_size=1, max_size=20).map(lambda s: "[aria-label='" + s + "']"),
)


# ──────────────────────────────────────────────────────────────
# Property 9: Isolamento de tenant no Brain
# ──────────────────────────────────────────────────────────────

@given(
    tenant_a=tenant_id_strategy,
    tenant_b=tenant_id_strategy,
    intencao=intencao_strategy,
    seletor=seletor_strategy,
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_9_brain_tenant_isolation(tenant_a, tenant_b, intencao, seletor):
    """
    **Property 9: Isolamento de tenant no Brain**

    Para quaisquer dois tenants A e B distintos, uma entrada gravada para A
    nao deve ser retornada em consultas ao Brain para B.

    Validates: Requisito 2.5.4
    """
    assume(tenant_a != tenant_b)

    import tempfile, os
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        backend = SQLiteBrainBackend(db_path=db_path)

        entrada_a = EntradaBrain(
            intencao=intencao,
            seletor=seletor if seletor else None,
            tenant_id=tenant_a,
        )
        backend.set(entrada_a)

        resultado_get = backend.get(intencao, tenant_id=tenant_b)
        assert resultado_get is None, (
            "get() para tenant '" + tenant_b + "' retornou entrada do tenant '" + tenant_a + "'"
        )

        resultado_query = backend.query(tenant_b)
        intencoes_b = [e.intencao for e in resultado_query]
        assert intencao not in intencoes_b, (
            "query() para tenant '" + tenant_b + "' retornou intencao do tenant '" + tenant_a + "'"
        )
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


@given(
    tenant_a=tenant_id_strategy,
    tenant_b=tenant_id_strategy,
    intencoes=st.lists(intencao_strategy, min_size=1, max_size=5, unique=True),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
def test_property_9_brain_multiple_entries_isolation(tenant_a, tenant_b, intencoes):
    """
    **Property 9 (variante multi-entrada): Isolamento de tenant no Brain**

    Multiplas entradas gravadas para tenant A nao devem aparecer em
    consultas para tenant B.

    Validates: Requisito 2.5.4
    """
    assume(tenant_a != tenant_b)

    import tempfile, os
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        backend = SQLiteBrainBackend(db_path=db_path)

        for intencao in intencoes:
            backend.set(EntradaBrain(
                intencao=intencao,
                seletor="[aria-label='Teste']",
                tenant_id=tenant_a,
            ))

        resultado_b = backend.query(tenant_b)
        intencoes_b = {e.intencao for e in resultado_b}

        for intencao in intencoes:
            assert intencao not in intencoes_b, (
                "Entrada '" + intencao + "' do tenant '" + tenant_a + "' vazou para tenant '" + tenant_b + "'"
            )
    finally:
        try:
            os.unlink(db_path)
        except Exception:
            pass


# ──────────────────────────────────────────────────────────────
# Property 10: Isolamento de tenant no Pinecone
# ──────────────────────────────────────────────────────────────

@given(
    tenant_id=tenant_id_strategy,
    nome_aula=st.text(min_size=1, max_size=40),
    n_passos=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=100, deadline=None)
def test_property_10_pinecone_upsert_uses_tenant_namespace(tenant_id, nome_aula, n_passos):
    """
    **Property 10: Isolamento de tenant no Pinecone (upsert)**

    Para qualquer requisicao com tenant_id T, o upsert ao Pinecone deve
    usar exclusivamente o namespace correspondente a T.

    Validates: Requisito 2.5.3
    """
    import dap_engine

    passos = []
    for i in range(n_passos):
        passos.append({
            "id_passo": i + 1,
            "pedagogia": {
                "ancora": "Instrucao do passo " + str(i + 1),
                "tooltip_dap": "Dica " + str(i + 1),
            },
            "acoes_tecnicas": [
                {
                    "seletor_css": "[aria-label='acao_" + str(i) + "']",
                    "elemento_alvo": {"seletor_hint": "[aria-label='acao_" + str(i) + "']"},
                }
            ],
        })

    roteiro = {
        "metadata": {"nome_aula": nome_aula},
        "passos": passos,
    }

    mock_index = MagicMock()
    mock_openai = MagicMock()
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 3072)]
    )

    with patch.object(dap_engine, "pinecone_index", mock_index), \
         patch.object(dap_engine, "client_openai", mock_openai):
        dap_engine.ingestar_para_pinecone(roteiro, tenant_id=tenant_id)

    assert mock_index.upsert.called, "upsert() nao foi chamado"

    for c in mock_index.upsert.call_args_list:
        kwargs = c.kwargs if c.kwargs else {}
        namespace_usado = kwargs.get("namespace")
        assert namespace_usado == tenant_id, (
            "upsert() usou namespace='" + str(namespace_usado) + "' em vez de '" + tenant_id + "'"
        )


@given(
    tenant_id=tenant_id_strategy,
    prompt=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100, deadline=None)
def test_property_10_pinecone_query_uses_tenant_namespace(tenant_id, prompt):
    """
    **Property 10: Isolamento de tenant no Pinecone (query)**

    Para qualquer requisicao com tenant_id T, a query ao Pinecone deve
    usar exclusivamente o namespace correspondente a T.

    Validates: Requisito 2.5.3
    """
    import dap_engine

    mock_index = MagicMock()
    mock_index.query.return_value = MagicMock(matches=[])

    mock_openai = MagicMock()
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 3072)]
    )

    with patch.object(dap_engine, "pinecone_index", mock_index), \
         patch.object(dap_engine, "client_openai", mock_openai):
        dap_engine.buscar_contexto(prompt, tenant_id=tenant_id)

    assert mock_index.query.called, "query() nao foi chamado"

    for c in mock_index.query.call_args_list:
        kwargs = c.kwargs if c.kwargs else {}
        namespace_usado = kwargs.get("namespace")
        assert namespace_usado == tenant_id, (
            "query() usou namespace='" + str(namespace_usado) + "' em vez de '" + tenant_id + "'"
        )


@given(
    tenant_a=tenant_id_strategy,
    tenant_b=tenant_id_strategy,
    prompt=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100, deadline=None)
def test_property_10_pinecone_namespaces_never_cross(tenant_a, tenant_b, prompt):
    """
    **Property 10 (variante cross-tenant): Isolamento de tenant no Pinecone**

    Duas chamadas com tenants distintos nunca devem usar o mesmo namespace
    uma da outra.

    Validates: Requisito 2.5.3
    """
    assume(tenant_a != tenant_b)

    import dap_engine

    namespaces_usados = []

    def mock_query(**kwargs):
        namespaces_usados.append(kwargs.get("namespace"))
        return MagicMock(matches=[])

    mock_index = MagicMock()
    mock_index.query.side_effect = mock_query

    mock_openai = MagicMock()
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=[0.1] * 3072)]
    )

    with patch.object(dap_engine, "pinecone_index", mock_index), \
         patch.object(dap_engine, "client_openai", mock_openai):
        dap_engine.buscar_contexto(prompt, tenant_id=tenant_a)
        dap_engine.buscar_contexto(prompt, tenant_id=tenant_b)

    assert len(namespaces_usados) == 2
    assert namespaces_usados[0] == tenant_a, (
        "Primeira query usou namespace='" + str(namespaces_usados[0]) + "' em vez de '" + tenant_a + "'"
    )
    assert namespaces_usados[1] == tenant_b, (
        "Segunda query usou namespace='" + str(namespaces_usados[1]) + "' em vez de '" + tenant_b + "'"
    )

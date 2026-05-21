"""
Preservation Tests — aura-dap-rag-optimization
================================================
These tests PASS on UNFIXED code, establishing the baseline behavior
that MUST NOT regress after the identity detector and query normalizer
are implemented.

Tests verify:
  - Formal queries proceed through the full pipeline (embedding + namespace search + Vision)
  - Non-identity queries are NOT intercepted as identity questions
  - Cache is served BEFORE any other processing
  - AI Gate bypass activates for high-confidence RAG results (score > 0.80 with selector)
  - Queries mentioning "Aura" or "nome" in non-identity contexts are NOT short-circuited

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import hashlib
import json
import os
import sys
import unittest.mock as mock

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path — ensure project root is accessible
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Mock heavy dependencies before importing dap_engine
# ---------------------------------------------------------------------------
_heavy_deps = [
    "google",
    "google.genai",
    "google.genai.types",
    "openai",
    "pinecone",
    "guardrails",
    "navigation_fallback",
]

_dep_mocks = {}
for dep in _heavy_deps:
    _dep_mocks[dep] = mock.MagicMock()

# Setup specific mock attributes needed by dap_engine at import time
_dep_mocks["google.genai"].Client = mock.MagicMock()
_dep_mocks["google.genai.types"].Schema = mock.MagicMock()
_dep_mocks["google.genai.types"].Type = mock.MagicMock()
_dep_mocks["google.genai.types"].Part = mock.MagicMock()
_dep_mocks["google.genai.types"].GenerateContentConfig = mock.MagicMock()
_dep_mocks["guardrails"].GuardrailConfig = mock.MagicMock()
_dep_mocks["guardrails"].GuardrailConfig.from_env = mock.MagicMock(return_value=mock.MagicMock(
    enable_sql_injection=False,
    enable_prompt_injection=False,
    enable_offensive_content=False,
    enable_competitor_filter=False,
    enable_vector_store_only=False,
))
_dep_mocks["guardrails"].GuardrailEngine = mock.MagicMock()
_dep_mocks["guardrails"].SecurityEventLogger = mock.MagicMock()
_dep_mocks["navigation_fallback"].get_navigation_fallback_engine = mock.MagicMock()


# We need to mock the OpenAI and Pinecone clients at module level
with mock.patch.dict("sys.modules", _dep_mocks):
    # Also mock dotenv to avoid loading .env
    with mock.patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key",
        "GOOGLE_API_KEY": "test-key",
        "PINECONE_API_KEY": "test-key",
        "PINECONE_INDEX_NAME": "test-index",
    }):
        if "dap_engine" in sys.modules:
            del sys.modules["dap_engine"]
        import dap_engine


# ---------------------------------------------------------------------------
# Hypothesis Strategies
# ---------------------------------------------------------------------------

# Strategy for generating formal Portuguese queries (no abbreviations, no informal markers, no identity patterns)
_FORMAL_QUERY_TEMPLATES = [
    "Como acessar o módulo de {module}?",
    "O que é {module}?",
    "Como configurar o {module} no sistema?",
    "Qual o procedimento para {action} no {module}?",
    "Onde encontro a opção de {action}?",
    "Como faço para {action} no sistema?",
    "Preciso de ajuda com {module}.",
    "Gostaria de saber como funciona o {module}.",
    "Pode me explicar o processo de {action}?",
    "Qual a diferença entre {module} e {module2}?",
]

_MODULES = [
    "folha de pagamento", "gestão de pessoas", "contas a pagar",
    "contas a receber", "patrimônio", "contabilidade", "fiscal",
    "compras", "estoque", "faturamento", "financeiro", "recursos humanos",
    "ponto eletrônico", "benefícios", "treinamento", "recrutamento",
]

_ACTIONS = [
    "cadastrar funcionário", "gerar relatório", "emitir nota fiscal",
    "aprovar requisição", "consultar saldo", "fechar período",
    "importar dados", "exportar planilha", "configurar parâmetros",
    "acessar dashboard", "visualizar histórico", "alterar cadastro",
]

# Identity patterns that should NOT be in formal queries
_IDENTITY_PATTERNS_LOWER = [
    "quem é vc", "quem é você", "quem e voce", "qual seu nome",
    "qual é seu nome", "qual o seu nome", "o que vc faz",
    "o que você faz", "o que voce faz", "quem te criou",
    "como vc se chama", "como você se chama", "vc é quem",
    "me fala sobre vc", "se apresenta", "se apresente",
]

# Informal markers that should NOT be in formal queries
_INFORMAL_MARKERS = {"vc", "q ", "pq", "tb", "oq"}

# Known abbreviations that should NOT be in formal queries for preservation tests
_KNOWN_ABBREVIATIONS = {"hcm", "bpm", "ged", "konviva"}


@st.composite
def formal_portuguese_queries(draw):
    """Generate random formal Portuguese queries that are NOT identity questions
    and do NOT contain abbreviations or informal markers."""
    template = draw(st.sampled_from(_FORMAL_QUERY_TEMPLATES))
    module = draw(st.sampled_from(_MODULES))
    module2 = draw(st.sampled_from(_MODULES))
    action = draw(st.sampled_from(_ACTIONS))

    query = template.format(module=module, module2=module2, action=action)

    # Ensure it doesn't accidentally match identity patterns
    query_lower = query.lower()
    for pattern in _IDENTITY_PATTERNS_LOWER:
        assume(pattern not in query_lower)

    # Ensure no informal markers
    for marker in _INFORMAL_MARKERS:
        assume(marker not in query_lower)

    # Ensure no known abbreviations as standalone words
    words_lower = set(query_lower.split())
    for abbr in _KNOWN_ABBREVIATIONS:
        assume(abbr not in words_lower)

    return query


@st.composite
def non_identity_queries_with_aura_or_nome(draw):
    """Generate queries that mention 'Aura' or 'nome' but are NOT identity questions."""
    templates = [
        "Como configurar o nome do módulo?",
        "Qual o nome do relatório de folha?",
        "Onde altero o nome do funcionário?",
        "Como a Aura pode me ajudar com relatórios?",
        "Preciso mudar o nome do departamento.",
        "Qual o nome do campo de cadastro?",
        "Como usar a Aura para navegar no sistema?",
        "Onde fica o nome da empresa no cadastro?",
        "A Aura consegue gerar relatórios?",
        "Preciso alterar o nome do cargo.",
    ]
    return draw(st.sampled_from(templates))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_embedding():
    """Mock gerar_embedding to return a deterministic vector."""
    fake_embedding = [0.1] * 3072
    with mock.patch.object(dap_engine, "gerar_embedding", return_value=fake_embedding) as m:
        yield m


@pytest.fixture
def mock_pinecone_high_score():
    """Mock buscar_contexto_multi_namespace to return a high-confidence result with selector."""
    result = {
        "texto_rag": "MANUAL: Folha de Pagamento\nINSTRUCAO: Acesse o menu Gestão de Pessoas\nDICA: Clique no ícone de folha",
        "seletor_direto": "#menu-folha-pagamento",
        "score": 0.92,
        "melhor_aula": "Folha de Pagamento - Acesso",
        "_namespace_origem": "senior_default",
    }
    with mock.patch.object(dap_engine, "buscar_contexto_multi_namespace", return_value=result) as m:
        yield m


@pytest.fixture
def mock_pinecone_low_score():
    """Mock buscar_contexto_multi_namespace to return a low-confidence result (no selector)."""
    result = {
        "texto_rag": "DOCUMENTACAO: Informações gerais\nCONTEUDO: Texto genérico sobre o sistema",
        "seletor_direto": None,
        "score": 0.55,
        "melhor_aula": "Documentação Geral",
        "_namespace_origem": "faq",
    }
    with mock.patch.object(dap_engine, "buscar_contexto_multi_namespace", return_value=result) as m:
        yield m


@pytest.fixture
def mock_gemini_vision():
    """Mock Gemini Vision client to return a deterministic response."""
    mock_response = mock.MagicMock()
    mock_response.text = json.dumps({
        "analise_interna": "Análise da tela",
        "mensagem": "Aqui está a resposta sobre o módulo.",
        "elemento_id": None,
        "seletor_css": None,
        "sugestoes": ["Como configurar?", "Próximo passo"],
    })
    mock_client = mock.MagicMock()
    mock_client.models.generate_content.return_value = mock_response
    with mock.patch.object(dap_engine, "gemini_client", mock_client) as m:
        yield mock_client


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client to be non-None (enables pipeline)."""
    mock_client = mock.MagicMock()
    with mock.patch.object(dap_engine, "client_openai", mock_client):
        yield mock_client


@pytest.fixture
def mock_pinecone_index():
    """Mock Pinecone index to be non-None (enables pipeline)."""
    mock_idx = mock.MagicMock()
    with mock.patch.object(dap_engine, "pinecone_index", mock_idx):
        yield mock_idx


@pytest.fixture
def mock_cache_miss():
    """Mock cache to always miss."""
    with mock.patch.object(dap_engine, "_cache_get", return_value=None) as m:
        yield m


@pytest.fixture
def mock_cache_set():
    """Mock cache set to track calls."""
    with mock.patch.object(dap_engine, "_cache_set") as m:
        yield m


@pytest.fixture
def mock_guardrail_config_disabled():
    """Mock guardrail config with vector_store_only disabled."""
    mock_config = mock.MagicMock()
    mock_config.enable_vector_store_only = False
    with mock.patch.object(dap_engine, "_guardrail_config", mock_config):
        yield mock_config


# Standard test parameters
_FAKE_IMAGE_B64 = "data:image/jpeg;base64," + "AAAA" * 100
_FAKE_URL = "https://senior.com.br/modulo/folha"
_FAKE_DOM = "<div id='menu-folha-pagamento'>Folha de Pagamento</div>"
_FAKE_USER = "TestUser"
_FAKE_TENANT = "senior_default"
_FAKE_HISTORICO = []


# ===========================================================================
# Test a: Formal Query Pipeline Test
# ===========================================================================

@given(query=formal_portuguese_queries())
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_formal_query_full_pipeline_executes(
    query,
    mock_embedding,
    mock_pinecone_low_score,
    mock_gemini_vision,
    mock_openai_client,
    mock_pinecone_index,
    mock_cache_miss,
    mock_cache_set,
    mock_guardrail_config_disabled,
):
    """
    **Validates: Requirements 3.1, 3.2**

    For formal Portuguese queries (no abbreviations, no informal markers, no identity patterns),
    verify the full pipeline executes: embedding is called, namespace search is called,
    and Vision is called (since we mock low-score results that don't trigger AI Gate).
    """
    # Reset mocks for each example
    mock_embedding.reset_mock()
    mock_pinecone_low_score.reset_mock()
    mock_gemini_vision.models.generate_content.reset_mock()

    result = dap_engine._analisar_sync(
        image_b64=_FAKE_IMAGE_B64,
        url=_FAKE_URL,
        prompt_usuario=query,
        dom_context=_FAKE_DOM,
        user_name=_FAKE_USER,
        tenant_id=_FAKE_TENANT,
        historico=_FAKE_HISTORICO,
    )

    # Pipeline must execute: embedding called (via buscar_contexto_multi_namespace)
    mock_pinecone_low_score.assert_called_once()

    # Vision must be called (low score, no selector → no AI Gate bypass)
    mock_gemini_vision.models.generate_content.assert_called_once()

    # Result must have expected structure
    assert "mensagem" in result
    assert "sugestoes" in result


# ===========================================================================
# Test b: Non-Identity Preservation Test
# ===========================================================================

@given(query=formal_portuguese_queries())
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_non_identity_queries_not_intercepted(
    query,
    mock_embedding,
    mock_pinecone_low_score,
    mock_gemini_vision,
    mock_openai_client,
    mock_pinecone_index,
    mock_cache_miss,
    mock_cache_set,
    mock_guardrail_config_disabled,
):
    """
    **Validates: Requirements 3.5**

    For queries like "O que é folha de pagamento?" — verify they are NOT intercepted
    as identity questions and proceed through RAG normally.
    The pipeline must reach buscar_contexto_multi_namespace (proving no short-circuit).
    """
    mock_pinecone_low_score.reset_mock()

    result = dap_engine._analisar_sync(
        image_b64=_FAKE_IMAGE_B64,
        url=_FAKE_URL,
        prompt_usuario=query,
        dom_context=_FAKE_DOM,
        user_name=_FAKE_USER,
        tenant_id=_FAKE_TENANT,
        historico=_FAKE_HISTORICO,
    )

    # The query MUST reach the RAG search (not short-circuited)
    mock_pinecone_low_score.assert_called_once()

    # Result must NOT be a canned identity response
    assert result.get("source_reference") != "identity_detector"


# ===========================================================================
# Test c: Cache Preservation Test
# ===========================================================================

def test_cache_served_before_any_processing(
    mock_openai_client,
    mock_pinecone_index,
    mock_guardrail_config_disabled,
):
    """
    **Validates: Requirements 3.4**

    For cached queries — verify cache is served before any other processing.
    When cache hits, embedding, namespace search, and Vision must NOT be called.
    """
    cached_response = {
        "mensagem": "Resposta do cache",
        "elemento_id": None,
        "seletor_css": None,
        "sugestoes": ["Próximo passo"],
        "confidence_score": 0.85,
        "source_reference": "Cache Test",
    }

    with mock.patch.object(dap_engine, "_cache_get", return_value=cached_response) as mock_cache:
        with mock.patch.object(dap_engine, "buscar_contexto_multi_namespace") as mock_rag:
            with mock.patch.object(dap_engine, "gemini_client") as mock_vision:
                result = dap_engine._analisar_sync(
                    image_b64=_FAKE_IMAGE_B64,
                    url=_FAKE_URL,
                    prompt_usuario="Como acessar o módulo de folha de pagamento?",
                    dom_context=_FAKE_DOM,
                    user_name=_FAKE_USER,
                    tenant_id=_FAKE_TENANT,
                    historico=_FAKE_HISTORICO,
                )

    # Cache must be checked
    mock_cache.assert_called_once()

    # RAG must NOT be called (cache hit short-circuits)
    mock_rag.assert_not_called()

    # Vision must NOT be called
    mock_vision.models.generate_content.assert_not_called()

    # Result must be the cached response
    assert result == cached_response


# ===========================================================================
# Test d: AI Gate Preservation Test
# ===========================================================================

def test_ai_gate_bypass_activates_for_high_confidence(
    mock_embedding,
    mock_pinecone_high_score,
    mock_openai_client,
    mock_pinecone_index,
    mock_cache_miss,
    mock_cache_set,
    mock_guardrail_config_disabled,
):
    """
    **Validates: Requirements 3.3**

    For high-confidence RAG results (score > 0.80 with selector) — verify AI Gate
    bypass activates and Vision is NOT called.
    """
    # Ensure gemini_client exists but should NOT be called
    mock_vision = mock.MagicMock()
    with mock.patch.object(dap_engine, "gemini_client", mock_vision):
        result = dap_engine._analisar_sync(
            image_b64=_FAKE_IMAGE_B64,
            url=_FAKE_URL,
            prompt_usuario="Como acessar o módulo de folha de pagamento?",
            dom_context=_FAKE_DOM,
            user_name=_FAKE_USER,
            tenant_id=_FAKE_TENANT,
            historico=_FAKE_HISTORICO,
        )

    # Vision must NOT be called (AI Gate bypasses it)
    mock_vision.models.generate_content.assert_not_called()

    # Result must contain the RAG-based response
    assert "mensagem" in result
    assert result.get("seletor_css") == "#menu-folha-pagamento"
    assert result.get("confidence_score") == 0.92
    assert result.get("source_reference") == "Folha de Pagamento - Acesso"

    # Cache must be set with the AI Gate result
    mock_cache_set.assert_called_once()


# ===========================================================================
# Test e: Non-Identity with "Aura"/"nome" Test
# ===========================================================================

@given(query=non_identity_queries_with_aura_or_nome())
@settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_non_identity_queries_with_aura_or_nome_not_short_circuited(
    query,
    mock_embedding,
    mock_pinecone_low_score,
    mock_gemini_vision,
    mock_openai_client,
    mock_pinecone_index,
    mock_cache_miss,
    mock_cache_set,
    mock_guardrail_config_disabled,
):
    """
    **Validates: Requirements 3.5**

    For queries mentioning "Aura" or "nome" in non-identity contexts
    (e.g., "Como configurar o nome do módulo?") — verify they are NOT
    short-circuited and proceed through the full pipeline.
    """
    mock_pinecone_low_score.reset_mock()
    mock_gemini_vision.models.generate_content.reset_mock()

    result = dap_engine._analisar_sync(
        image_b64=_FAKE_IMAGE_B64,
        url=_FAKE_URL,
        prompt_usuario=query,
        dom_context=_FAKE_DOM,
        user_name=_FAKE_USER,
        tenant_id=_FAKE_TENANT,
        historico=_FAKE_HISTORICO,
    )

    # The query MUST reach the RAG search (not short-circuited as identity)
    mock_pinecone_low_score.assert_called_once()

    # Vision must be called (low score → no AI Gate bypass)
    mock_gemini_vision.models.generate_content.assert_called_once()

    # Result must NOT be a canned identity response
    assert result.get("source_reference") != "identity_detector"
    assert "mensagem" in result

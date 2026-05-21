"""
Bug Condition Exploration Tests — aura-dap-rag-optimization
============================================================

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**

OBJETIVO: Demonstrar os bugs ANTES de implementar a correção.

Bug Condition 1 — Identity Questions Waste API Calls:
  Perguntas de identidade/meta ("Quem é vc?", "Qual seu nome?") disparam
  o pipeline completo (OpenAI embedding + Pinecone multi-namespace + Gemini Vision)
  quando deveriam retornar resposta instantânea sem nenhuma chamada externa.

Bug Condition 2 — Informal/Short Queries Fail Retrieval:
  Queries informais/abreviadas ("O que é o HCM?", "Só quero q vc me fale o que é o Konviva")
  são passadas diretamente ao embedding sem normalização, produzindo vetores
  com baixa similaridade contra conteúdo formalmente indexado.

METODOLOGIA:
  - Os testes assertam o comportamento ESPERADO (correto, pós-fix).
  - O código NÃO corrigido viola esse comportamento → testes FALHAM.
  - A falha confirma que os bugs existem.
  - Após o fix (Tarefa 3), estes mesmos testes devem PASSAR.

NÃO corrija o código nem os testes quando eles falharem.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path — garante que o root do projeto está acessível
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Strategies — Identity patterns and informal queries
# ---------------------------------------------------------------------------

IDENTITY_PATTERNS = [
    "Quem é vc?",
    "Quem é você?",
    "quem e voce",
    "Qual seu nome?",
    "Qual é seu nome?",
    "Qual o seu nome?",
    "O que vc faz?",
    "O que você faz?",
    "O que voce faz?",
    "Quem te criou?",
    "Como vc se chama?",
    "Como você se chama?",
    "vc é quem?",
    "Me fala sobre vc",
    "Se apresenta",
    "Se apresente",
]

INFORMAL_QUERIES_WITH_ABBREVIATIONS = [
    ("O que é o HCM?", ["gestão de pessoas", "human capital management"]),
    ("Só quero q vc me fale o que é o Konviva", ["konviva", "plataforma", "educação"]),
    ("Me explica o BPM", ["business process management", "gestão", "processos"]),
    ("O que é o GED?", ["gestão eletrônica", "documentos"]),
]

identity_pattern_strategy = st.sampled_from(IDENTITY_PATTERNS)

informal_query_strategy = st.sampled_from(
    [q for q, _ in INFORMAL_QUERIES_WITH_ABBREVIATIONS]
)


# ---------------------------------------------------------------------------
# Fixtures — Common mock setup for dap_engine
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_dap_dependencies():
    """Mock all external API dependencies in dap_engine."""
    with patch("dap_engine.gerar_embedding") as mock_embed, \
         patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
         patch("dap_engine.gemini_client") as mock_gemini, \
         patch("dap_engine._cache_get", return_value=None), \
         patch("dap_engine._cache_set"):

        # Configure mock_embed to return a fake embedding vector
        mock_embed.return_value = [0.1] * 3072

        # Configure mock_busca to return None (no context found)
        mock_busca.return_value = None

        # Configure gemini_client to return a valid response
        mock_response = MagicMock()
        mock_response.text = '{"analise_interna": "test", "mensagem": "Olá! Sou a Aura.", "elemento_id": null, "seletor_css": null, "sugestoes": ["O que posso fazer?"]}'
        mock_gemini.models.generate_content.return_value = mock_response

        yield {
            "gerar_embedding": mock_embed,
            "buscar_contexto_multi_namespace": mock_busca,
            "gemini_client": mock_gemini,
        }


# ===========================================================================
# Bug Condition 1 — Identity Questions Short-Circuit
# ===========================================================================
# These tests assert the EXPECTED behavior (post-fix):
#   - gerar_embedding() is NOT called
#   - buscar_contexto_multi_namespace() is NOT called
#   - Gemini Vision generate_content() is NOT called
#   - Response contains identity keywords and non-empty sugestoes
#
# On UNFIXED code, these will FAIL because identity questions currently
# trigger the full pipeline.
# ===========================================================================


class TestBugCondition1_IdentityShortCircuit:
    """
    Property 1: Bug Condition - Identity Questions Short-Circuit

    For all identity patterns from isBugCondition_Identity, calling _analisar_sync()
    should NOT trigger any external API calls and should return a canned identity response.

    **Validates: Requirements 2.1, 2.4**
    """

    @given(identity_prompt=identity_pattern_strategy)
    @settings(max_examples=16, deadline=None)
    def test_identity_no_embedding_call(self, identity_prompt):
        """
        Identity questions must NOT call gerar_embedding().
        On unfixed code, this FAILS because the full pipeline runs.

        **Validates: Requirements 1.1, 2.1**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Olá!", "elemento_id": null, "seletor_css": null, "sugestoes": ["Ajuda?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=identity_prompt,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # EXPECTED: gerar_embedding NOT called (identity short-circuit)
            mock_embed.assert_not_called(), (
                f"BUG CONDITION 1 CONFIRMED: gerar_embedding() was called for "
                f"identity question '{identity_prompt}'. Expected short-circuit."
            )

    @given(identity_prompt=identity_pattern_strategy)
    @settings(max_examples=16, deadline=None)
    def test_identity_no_namespace_search(self, identity_prompt):
        """
        Identity questions must NOT call buscar_contexto_multi_namespace().
        On unfixed code, this FAILS because the full pipeline runs.

        **Validates: Requirements 1.1, 2.1**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Olá!", "elemento_id": null, "seletor_css": null, "sugestoes": ["Ajuda?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=identity_prompt,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # EXPECTED: buscar_contexto_multi_namespace NOT called
            mock_busca.assert_not_called(), (
                f"BUG CONDITION 1 CONFIRMED: buscar_contexto_multi_namespace() was called for "
                f"identity question '{identity_prompt}'. Expected short-circuit."
            )

    @given(identity_prompt=identity_pattern_strategy)
    @settings(max_examples=16, deadline=None)
    def test_identity_no_vision_call(self, identity_prompt):
        """
        Identity questions must NOT call Gemini Vision generate_content().
        On unfixed code, this FAILS because Vision is the fallback.

        **Validates: Requirements 1.4, 2.4**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Olá!", "elemento_id": null, "seletor_css": null, "sugestoes": ["Ajuda?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=identity_prompt,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # EXPECTED: Gemini Vision NOT called (identity short-circuit)
            mock_gemini.models.generate_content.assert_not_called(), (
                f"BUG CONDITION 1 CONFIRMED: Gemini Vision was called for "
                f"identity question '{identity_prompt}'. Expected short-circuit."
            )

    @given(identity_prompt=identity_pattern_strategy)
    @settings(max_examples=16, deadline=None)
    def test_identity_response_contains_keywords_and_sugestoes(self, identity_prompt):
        """
        Identity questions must return a response with identity keywords
        (e.g., "Aura", "assistente") and non-empty sugestoes.
        On unfixed code, this may FAIL because the response comes from Vision.

        **Validates: Requirements 2.1, 2.4**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Olá!", "elemento_id": null, "seletor_css": null, "sugestoes": ["Ajuda?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=identity_prompt,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # EXPECTED: Response contains identity keywords
            mensagem = result.get("mensagem", "").lower()
            identity_keywords = ["aura", "assistente", "ajud"]
            has_identity_keyword = any(kw in mensagem for kw in identity_keywords)
            assert has_identity_keyword, (
                f"BUG CONDITION 1 CONFIRMED: Response for identity question "
                f"'{identity_prompt}' does not contain identity keywords. "
                f"Got: '{result.get('mensagem', '')}'"
            )

            # EXPECTED: sugestoes is non-empty
            sugestoes = result.get("sugestoes", [])
            assert len(sugestoes) > 0, (
                f"BUG CONDITION 1 CONFIRMED: Response for identity question "
                f"'{identity_prompt}' has empty sugestoes."
            )


# ===========================================================================
# Bug Condition 2 — Query Normalization Improves Embedding Input
# ===========================================================================
# These tests assert the EXPECTED behavior (post-fix):
#   - The text passed to gerar_embedding() is longer than the raw input
#   - The normalized text contains expanded abbreviation terms
#   - All original query words are preserved in the normalized text
#
# On UNFIXED code, these will FAIL because queries are passed raw to embedding.
# ===========================================================================


class TestBugCondition2_QueryNormalization:
    """
    Property 2: Bug Condition - Query Normalization Improves Embedding Input

    For all queries matching isBugCondition_Normalization, the text passed to
    gerar_embedding() should be normalized (longer, with expanded terms).

    **Validates: Requirements 2.2, 2.3**
    """

    @pytest.mark.parametrize(
        "query,expected_terms",
        INFORMAL_QUERIES_WITH_ABBREVIATIONS,
        ids=[q for q, _ in INFORMAL_QUERIES_WITH_ABBREVIATIONS],
    )
    def test_normalization_expands_query(self, query, expected_terms):
        """
        Informal/abbreviated queries must be normalized before embedding.
        The text passed to gerar_embedding() should be longer than the raw input.
        On unfixed code, this FAILS because raw text is passed directly.

        **Validates: Requirements 1.2, 1.3, 2.2, 2.3**
        """
        captured_embedding_input = []

        def capture_embedding(text):
            captured_embedding_input.append(text)
            return [0.1] * 3072

        with patch("dap_engine.gerar_embedding", side_effect=capture_embedding) as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Info sobre o módulo.", "elemento_id": null, "seletor_css": null, "sugestoes": ["Mais info?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=query,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # The embedding function is called via buscar_contexto_multi_namespace
            # which internally calls gerar_embedding. Since we mock buscar_contexto_multi_namespace
            # directly, we need to check what text reaches it instead.
            # Actually, buscar_contexto_multi_namespace is mocked, so we check
            # if the normalization happened BEFORE the call.
            # The normalized text should be passed to buscar_contexto_multi_namespace.
            if mock_busca.called:
                actual_text = mock_busca.call_args[0][0]  # First positional arg
            else:
                # If buscar_contexto_multi_namespace wasn't called, check gerar_embedding
                if captured_embedding_input:
                    actual_text = captured_embedding_input[0]
                else:
                    pytest.fail(
                        f"BUG CONDITION 2 CONFIRMED: Neither gerar_embedding nor "
                        f"buscar_contexto_multi_namespace was called with normalized text "
                        f"for query '{query}'."
                    )
                    return

            # EXPECTED: Normalized text is longer than raw input
            assert len(actual_text) > len(query), (
                f"BUG CONDITION 2 CONFIRMED: Text passed to embedding "
                f"(len={len(actual_text)}) is NOT longer than raw query "
                f"(len={len(query)}). Query: '{query}', Actual: '{actual_text}'"
            )

    @pytest.mark.parametrize(
        "query,expected_terms",
        INFORMAL_QUERIES_WITH_ABBREVIATIONS,
        ids=[q for q, _ in INFORMAL_QUERIES_WITH_ABBREVIATIONS],
    )
    def test_normalization_contains_expanded_terms(self, query, expected_terms):
        """
        The normalized text must contain expanded abbreviation terms.
        On unfixed code, this FAILS because no expansion happens.

        **Validates: Requirements 1.2, 2.2**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Info.", "elemento_id": null, "seletor_css": null, "sugestoes": ["Mais?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=query,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # Get the text that was passed to buscar_contexto_multi_namespace
            if mock_busca.called:
                actual_text = mock_busca.call_args[0][0].lower()
            else:
                pytest.fail(
                    f"BUG CONDITION 2 CONFIRMED: buscar_contexto_multi_namespace "
                    f"was not called for query '{query}'."
                )
                return

            # EXPECTED: Normalized text contains expanded terms
            for term in expected_terms:
                assert term.lower() in actual_text, (
                    f"BUG CONDITION 2 CONFIRMED: Expanded term '{term}' not found "
                    f"in text passed to embedding. Query: '{query}', "
                    f"Actual text: '{actual_text}'"
                )

    @pytest.mark.parametrize(
        "query,expected_terms",
        INFORMAL_QUERIES_WITH_ABBREVIATIONS,
        ids=[q for q, _ in INFORMAL_QUERIES_WITH_ABBREVIATIONS],
    )
    def test_normalization_preserves_original_words(self, query, expected_terms):
        """
        All original query words must be preserved in the normalized text.
        Normalization is additive only — never removes original words.
        On unfixed code, this may pass trivially (raw text = original words).

        **Validates: Requirements 2.2, 2.3**
        """
        with patch("dap_engine.gerar_embedding") as mock_embed, \
             patch("dap_engine.buscar_contexto_multi_namespace") as mock_busca, \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"):

            mock_embed.return_value = [0.1] * 3072
            mock_busca.return_value = None

            mock_response = MagicMock()
            mock_response.text = '{"analise_interna": "test", "mensagem": "Info.", "elemento_id": null, "seletor_css": null, "sugestoes": ["Mais?"]}'
            mock_gemini.models.generate_content.return_value = mock_response

            import dap_engine
            result = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/dashboard",
                prompt_usuario=query,
                dom_context="<div>Dashboard</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

            # Get the text that was passed to buscar_contexto_multi_namespace
            if mock_busca.called:
                actual_text = mock_busca.call_args[0][0].lower()
            else:
                pytest.fail(
                    f"BUG CONDITION 2 CONFIRMED: buscar_contexto_multi_namespace "
                    f"was not called for query '{query}'."
                )
                return

            # EXPECTED: All original words are preserved
            # Strip punctuation for comparison
            import re
            original_words = re.findall(r'\w+', query.lower())
            for word in original_words:
                if len(word) > 1:  # Skip single-char words like "é"
                    assert word in actual_text, (
                        f"BUG CONDITION 2 CONFIRMED: Original word '{word}' "
                        f"not preserved in normalized text. Query: '{query}', "
                        f"Actual text: '{actual_text}'"
                    )

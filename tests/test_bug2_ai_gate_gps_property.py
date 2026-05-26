"""
Bug 2 — Property Tests: AI Gate GPS enrichment (Fix Checking & Preservation)
=============================================================================

# Feature: aura-gps-feedback-bugs, Property 3: AI Gate inclui GPS enrichment
# Feature: aura-gps-feedback-bugs, Property 4: Preservation — Caminho Gemini Vision não é alterado

**Validates: Requirements 2.4, 2.5 (Property 3) / 3.5, 3.6, 3.7 (Property 4)**

OBJETIVO:
  - Property 3 (Fix Checking): Para todo `busca_rag` com `score > 0.80` e
    `seletor_direto` presente, verificar que `_enriquecer_com_gps` é sempre
    chamado e `gps_passos` aparece no resultado quando roteiro GPS disponível.
  - Property 4 (Preservation): Para todo `busca_rag` com `score <= 0.80` ou
    `seletor_direto=None`, verificar que `_analisar_sync` não quebra e produz
    resultado válido (mensagem presente).

METODOLOGIA:
  - Usa pytest + hypothesis com @given e settings(max_examples=100).
  - Executa no código CORRIGIDO — EXPECTED OUTCOME: ambos os testes PASSAM.
  - Mocks seguem o mesmo padrão de test_bug2_ai_gate_gps_exploration.py.
"""

import builtins
import io
import json
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
# Strategies — geradores de dados para as propriedades
# ---------------------------------------------------------------------------

# Scores no intervalo (0.80, 1.0] — ativam o AI Gate
_score_ai_gate_ativo = st.floats(
    min_value=0.801,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False,
)

# Scores no intervalo [0.0, 0.80] — NÃO ativam o AI Gate
_score_ai_gate_inativo = st.floats(
    min_value=0.0,
    max_value=0.80,
    allow_nan=False,
    allow_infinity=False,
)

# Seletores CSS válidos (simples, sem caracteres problemáticos)
_seletor_css = st.one_of(
    st.just("#btn-sign"),
    st.just("#btn-ged"),
    st.just("#btn-bpm"),
    st.just("#menu-senior-flow"),
    st.just(".btn-primary"),
    st.just("[data-action='submit']"),
    st.builds(
        lambda n: f"#btn-{n}",
        st.integers(min_value=1, max_value=999),
    ),
)

# Prompts de usuário (strings não vazias, tamanho razoável)
_prompt_usuario = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs"),
        whitelist_characters="?!.,áéíóúàèìòùâêîôûãõçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ -_",
    ),
    min_size=3,
    max_size=80,
).filter(lambda s: s.strip())


# ---------------------------------------------------------------------------
# Helpers — mock factories (mesmo padrão do exploration test)
# ---------------------------------------------------------------------------

def _make_busca_rag_high_score(score: float, seletor: str) -> dict:
    """Resultado RAG que ativa o AI Gate (score > 0.80, seletor presente)."""
    return {
        "score": score,
        "seletor_direto": seletor,
        "melhor_aula": "aula_sign",
        "texto_rag": "INSTRUCAO: Clique no elemento alvo",
    }


def _make_busca_rag_low_score(score: float) -> dict:
    """Resultado RAG que NÃO ativa o AI Gate (score <= 0.80, sem seletor)."""
    return {
        "score": score,
        "seletor_direto": None,
        "melhor_aula": "aula_sign",
        "texto_rag": "INSTRUCAO: Clique no elemento alvo",
    }


def _make_busca_rag_no_seletor(score: float) -> dict:
    """Resultado RAG com score alto mas seletor_direto=None — AI Gate NÃO ativa."""
    return {
        "score": score,
        "seletor_direto": None,
        "melhor_aula": "aula_sign",
        "texto_rag": "INSTRUCAO: Clique no elemento alvo",
    }


def _make_fallback_engine_with_gps() -> MagicMock:
    """
    Mock de NavigationFallbackEngine com roteiro GPS disponível.
    Roteiro contém 2+ passos — condição mínima para GPS enrichment.
    """
    engine = MagicMock()
    engine.indexer.search.return_value = [
        {"roteiro_name": "roteiro_sign_studio"}
    ]
    engine.path_extractor.extract_navigation_path.return_value = {
        "steps": [
            {"ordem": 1, "instrucao": "Acesse o menu Senior Flow", "seletor": "#menu-senior-flow"},
            {"ordem": 2, "instrucao": "Clique em Sign Studio", "seletor": "#btn-sign"},
        ]
    }
    return engine


def _make_roteiro_json() -> dict:
    """Roteiro JSON mínimo válido para ser 'lido do disco'."""
    return {
        "metadata": {"nome_aula": "roteiro_sign_studio"},
        "passos": [
            {"id_passo": 1, "pedagogia": {"ancora": "Acesse o menu Senior Flow"}},
            {"id_passo": 2, "pedagogia": {"ancora": "Clique em Sign Studio"}},
        ]
    }


def _make_open_mock(roteiro_data: dict) -> MagicMock:
    """
    Cria um mock de builtins.open que retorna o roteiro_data como JSON.
    Segue o mesmo padrão do exploration test.
    """
    roteiro_json_str = json.dumps(roteiro_data)
    mock_open = MagicMock(
        return_value=MagicMock(
            __enter__=MagicMock(return_value=io.StringIO(roteiro_json_str)),
            __exit__=MagicMock(return_value=False),
        )
    )
    return mock_open


def _make_gemini_response() -> MagicMock:
    """Mock de resposta do Gemini Vision (usado no caminho de score baixo)."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "analise_interna": "Usuário quer acessar o sistema",
        "mensagem": "Para acessar, clique no menu indicado.",
        "elemento_id": "btn-sign",
        "seletor_css": "#btn-sign",
        "sugestoes": ["Próximo passo", "O que mais posso fazer?"],
    })
    return mock_response


# ===========================================================================
# Property 3: Fix Checking — AI Gate inclui GPS enrichment
# ===========================================================================

class TestProperty3FixChecking:
    """
    Property 3: Fix Checking — AI Gate inclui GPS enrichment

    # Feature: aura-gps-feedback-bugs, Property 3: AI Gate inclui GPS enrichment

    Para todo `busca_rag` com `score > 0.80` e `seletor_direto` presente,
    `_analisar_sync` DEVE executar `_enriquecer_com_gps` e adicionar `gps_passos`
    ao resultado quando um roteiro GPS relevante for encontrado.

    Executa no código CORRIGIDO — EXPECTED OUTCOME: Teste PASSA.

    **Validates: Requirements 2.4, 2.5**
    """

    @given(
        score=_score_ai_gate_ativo,
        seletor=_seletor_css,
        prompt=_prompt_usuario,
    )
    @settings(max_examples=100, deadline=None)
    def test_property3_ai_gate_ativo_inclui_gps_passos(
        self, score: float, seletor: str, prompt: str
    ):
        """
        Property 3: Para todo score > 0.80 com seletor_direto presente,
        `gps_passos` deve estar no resultado quando roteiro GPS disponível.

        Nota: prompts que ativam identity/greeting detectors são excluídos via
        `assume()` — esses short-circuits são comportamento correto e não
        relacionados ao Bug 2.

        **Validates: Requirements 2.4, 2.5**
        """
        import dap_engine as _dap

        # Excluir prompts que ativam short-circuits (identity/greeting detectors)
        # Esses caminhos retornam antes do AI Gate — comportamento correto, fora do escopo do Bug 2
        assume(not _dap._is_identity_question(prompt))
        assume(not _dap._is_simple_greeting(prompt))

        busca_rag = _make_busca_rag_high_score(score=score, seletor=seletor)
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        mock_open = _make_open_mock(roteiro_data)

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client"), \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open), \
             patch("json.load", return_value=roteiro_data):

            import dap_engine

            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario=prompt,
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Property 3: gps_passos deve estar presente quando AI Gate ativa e roteiro disponível
        assert "gps_passos" in resultado, (
            f"Property 3 FALHOU: 'gps_passos' ausente no resultado do AI Gate. "
            f"score={score:.4f}, seletor='{seletor}', prompt='{prompt[:40]}'. "
            f"Chaves presentes: {list(resultado.keys())}"
        )

        # Verifica que gps_passos é uma lista com pelo menos 2 passos
        assert isinstance(resultado["gps_passos"], list), (
            f"Property 3 FALHOU: 'gps_passos' não é uma lista. "
            f"Tipo obtido: {type(resultado['gps_passos'])}"
        )
        assert len(resultado["gps_passos"]) >= 2, (
            f"Property 3 FALHOU: 'gps_passos' tem menos de 2 passos. "
            f"Passos obtidos: {len(resultado['gps_passos'])}"
        )

    @given(
        score=_score_ai_gate_ativo,
        seletor=_seletor_css,
    )
    @settings(max_examples=50, deadline=None)
    def test_property3_ai_gate_ativo_mantem_seletor_css(
        self, score: float, seletor: str
    ):
        """
        Property 3 (complementar): O AI Gate deve manter o seletor_css correto
        mesmo após o GPS enrichment ser executado.

        **Validates: Requirements 2.4, 2.5**
        """
        busca_rag = _make_busca_rag_high_score(score=score, seletor=seletor)
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        mock_open = _make_open_mock(roteiro_data)

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client"), \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open), \
             patch("json.load", return_value=roteiro_data):

            import dap_engine

            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario="Como acessar o sistema?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # O seletor_css deve ser o mesmo que veio do RAG
        assert resultado.get("seletor_css") == seletor, (
            f"Property 3 FALHOU: seletor_css alterado pelo GPS enrichment. "
            f"Esperado: '{seletor}', obtido: '{resultado.get('seletor_css')}'"
        )

        # confidence_score deve ser preservado
        assert resultado.get("confidence_score", 0) > 0.80, (
            f"Property 3 FALHOU: confidence_score não reflete o score do AI Gate. "
            f"score={score:.4f}, confidence_score={resultado.get('confidence_score')}"
        )

    @given(score=_score_ai_gate_ativo, seletor=_seletor_css)
    @settings(max_examples=30, deadline=None)
    def test_property3_idempotencia_gps_enrichment(
        self, score: float, seletor: str
    ):
        """
        Property 3 (idempotência): Chamar _enriquecer_com_gps duas vezes não
        duplica gps_passos — a função é idempotente.

        **Validates: Requirements 2.4, 2.5**
        """
        import dap_engine

        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        mock_open = _make_open_mock(roteiro_data)

        resultado = {
            "mensagem": "Teste",
            "seletor_css": seletor,
            "confidence_score": score,
        }

        with patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", mock_open), \
             patch("json.load", return_value=roteiro_data):

            # Primeira chamada — deve adicionar gps_passos
            dap_engine._enriquecer_com_gps(resultado, "Como acessar o sistema?", "senior_default")
            passos_apos_primeira = resultado.get("gps_passos", [])
            len_apos_primeira = len(passos_apos_primeira)

            # Segunda chamada — deve ser idempotente (não duplicar)
            dap_engine._enriquecer_com_gps(resultado, "Como acessar o sistema?", "senior_default")
            passos_apos_segunda = resultado.get("gps_passos", [])
            len_apos_segunda = len(passos_apos_segunda)

        assert len_apos_primeira == len_apos_segunda, (
            f"Property 3 FALHOU: _enriquecer_com_gps não é idempotente. "
            f"Passos após 1ª chamada: {len_apos_primeira}, após 2ª: {len_apos_segunda}"
        )


# ===========================================================================
# Property 4: Preservation — Caminho Gemini Vision não é alterado
# ===========================================================================

class TestProperty4Preservation:
    """
    Property 4: Preservation — Caminho Gemini Vision não é alterado

    # Feature: aura-gps-feedback-bugs, Property 4: Preservation

    Para todo `busca_rag` com `score <= 0.80` ou `seletor_direto=None`,
    `_analisar_sync` deve produzir resultado válido sem quebrar.
    O caminho do Gemini Vision não deve ser afetado pela correção do Bug 2.

    Executa no código CORRIGIDO — EXPECTED OUTCOME: Teste PASSA.

    **Validates: Requirements 3.5, 3.6, 3.7**
    """

    @given(
        score=_score_ai_gate_inativo,
        prompt=_prompt_usuario,
    )
    @settings(max_examples=100, deadline=None)
    def test_property4_score_baixo_nao_quebra(
        self, score: float, prompt: str
    ):
        """
        Property 4: Para todo score <= 0.80, _analisar_sync não quebra e
        retorna resultado com 'mensagem' (caminho Gemini Vision).

        **Validates: Requirements 3.5, 3.6**
        """
        busca_rag = _make_busca_rag_low_score(score=score)
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        gemini_response = _make_gemini_response()

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("json.load", return_value=roteiro_data):

            mock_gemini.models.generate_content.return_value = gemini_response

            import dap_engine

            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario=prompt,
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Property 4: resultado deve ser válido (mensagem presente)
        assert "mensagem" in resultado, (
            f"Property 4 FALHOU: 'mensagem' ausente no resultado com score={score:.4f}. "
            f"Chaves presentes: {list(resultado.keys())}"
        )
        assert isinstance(resultado["mensagem"], str), (
            f"Property 4 FALHOU: 'mensagem' não é string. "
            f"Tipo obtido: {type(resultado['mensagem'])}"
        )
        assert len(resultado["mensagem"]) > 0, (
            f"Property 4 FALHOU: 'mensagem' está vazia. score={score:.4f}"
        )

    @given(
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        prompt=_prompt_usuario,
    )
    @settings(max_examples=100, deadline=None)
    def test_property4_seletor_none_nao_ativa_ai_gate(
        self, score: float, prompt: str
    ):
        """
        Property 4: Para todo busca_rag com seletor_direto=None (independente do score),
        o AI Gate NÃO ativa e _analisar_sync não quebra.

        **Validates: Requirements 3.5, 3.7**
        """
        # seletor_direto=None — AI Gate não ativa independente do score
        busca_rag = _make_busca_rag_no_seletor(score=score)
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        gemini_response = _make_gemini_response()

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("json.load", return_value=roteiro_data):

            mock_gemini.models.generate_content.return_value = gemini_response

            import dap_engine

            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario=prompt,
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Property 4: resultado deve ser válido (mensagem presente)
        assert "mensagem" in resultado, (
            f"Property 4 FALHOU: 'mensagem' ausente com seletor_direto=None, score={score:.4f}. "
            f"Chaves presentes: {list(resultado.keys())}"
        )

        # Quando seletor_direto=None, o AI Gate NÃO ativa — Gemini Vision executa
        # O resultado NÃO deve ter seletor_css vindo do AI Gate (pode ter do Gemini)
        # Verificamos apenas que o resultado é válido e não quebrou
        assert isinstance(resultado["mensagem"], str) and len(resultado["mensagem"]) > 0, (
            f"Property 4 FALHOU: 'mensagem' inválida com seletor_direto=None. "
            f"score={score:.4f}, mensagem='{resultado.get('mensagem')}'"
        )

    @given(score=_score_ai_gate_inativo)
    @settings(max_examples=50, deadline=None)
    def test_property4_score_baixo_ai_gate_nao_ativa(self, score: float):
        """
        Property 4: Para score <= 0.80, o AI Gate NÃO ativa — Gemini Vision
        deve ser chamado (mock_gemini.models.generate_content chamado 1x).

        **Validates: Requirements 3.5, 3.6**
        """
        busca_rag = _make_busca_rag_low_score(score=score)
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()
        gemini_response = _make_gemini_response()

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client") as mock_gemini, \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("json.load", return_value=roteiro_data):

            mock_gemini.models.generate_content.return_value = gemini_response

            import dap_engine

            dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario="Como acessar o sistema?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Property 4: Gemini Vision deve ter sido chamado (AI Gate inativo)
        mock_gemini.models.generate_content.assert_called_once(), (
            f"Property 4 FALHOU: Gemini Vision não foi chamado com score={score:.4f}. "
            f"Isso indica que o AI Gate ativou indevidamente."
        )

    @given(score=_score_ai_gate_ativo, seletor=_seletor_css)
    @settings(max_examples=30, deadline=None)
    def test_property4_ai_gate_sem_roteiro_nao_adiciona_gps_passos(
        self, score: float, seletor: str
    ):
        """
        Property 4: Quando AI Gate ativa mas NÃO há roteiro GPS disponível,
        o resultado NÃO deve conter 'gps_passos' — sem degradação.

        **Validates: Requirements 3.7**
        """
        busca_rag = _make_busca_rag_high_score(score=score, seletor=seletor)

        # Engine sem roteiro GPS (search retorna lista vazia)
        fallback_engine_sem_roteiro = MagicMock()
        fallback_engine_sem_roteiro.indexer.search.return_value = []

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client"), \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine_sem_roteiro):

            import dap_engine

            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/test",
                prompt_usuario="Como acessar o sistema?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Property 4: sem roteiro GPS, gps_passos NÃO deve estar presente
        assert "gps_passos" not in resultado, (
            f"Property 4 FALHOU: 'gps_passos' presente mesmo sem roteiro GPS disponível. "
            f"score={score:.4f}, seletor='{seletor}'. "
            f"Chaves presentes: {list(resultado.keys())}"
        )

        # O resultado deve ser válido (mensagem presente)
        assert "mensagem" in resultado, (
            f"Property 4 FALHOU: 'mensagem' ausente quando sem roteiro GPS. "
            f"Chaves presentes: {list(resultado.keys())}"
        )

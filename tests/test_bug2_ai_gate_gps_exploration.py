"""
Bug 2 — Exploration Test: AI Gate suprime `gps_passos` (Bug Condition)
=======================================================================

**Validates: Requirements 2.1, 2.2**

OBJETIVO: Demonstrar que `resultado_rapido` NÃO contém `gps_passos` quando o
AI Gate ativa (score > 0.80 e seletor_direto presente) e um roteiro GPS está
disponível — ANTES de implementar a correção.

Bug Condition (isBugCondition_AIGate):
  WHEN busca_rag.score > 0.80 AND busca_rag.seletor_direto != None
  THEN _analisar_sync retorna resultado_rapido sem executar o bloco de GPS enrichment
  → resultado não contém "gps_passos"

METODOLOGIA:
  - O teste asserta o comportamento ESPERADO (correto, pós-fix):
      "gps_passos" IN resultado quando AI Gate ativa e roteiro GPS disponível.
  - O código NÃO corrigido viola esse comportamento → teste FALHA.
  - A falha confirma que o bug existe (causa raiz: `return resultado_rapido`
    na seção 4 ocorre antes do bloco de GPS enrichment).
  - Após o fix (Tarefa 5), este mesmo teste deve PASSAR.

NÃO corrija o código nem o teste quando ele falhar.

Counterexample documentado:
  score=0.92, seletor_direto="#btn-sign", roteiro GPS com 2+ passos disponível
  → "gps_passos" not in resultado  (confirma o bug)
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# sys.path — garante que o root do projeto está acessível
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers — mock factories
# ---------------------------------------------------------------------------

def _make_busca_rag_high_score(score: float = 0.92, seletor: str = "#btn-sign") -> dict:
    """Retorna um resultado RAG que ativa o AI Gate (score > 0.80, seletor presente)."""
    return {
        "score": score,
        "seletor_direto": seletor,
        "melhor_aula": "aula_sign",
        "texto_rag": "INSTRUCAO: Clique em Sign",
    }


def _make_busca_rag_low_score(score: float = 0.65) -> dict:
    """Retorna um resultado RAG que NÃO ativa o AI Gate (score <= 0.80)."""
    return {
        "score": score,
        "seletor_direto": None,
        "melhor_aula": "aula_sign",
        "texto_rag": "INSTRUCAO: Clique em Sign",
    }


def _make_fallback_engine_with_gps() -> MagicMock:
    """
    Retorna um mock de NavigationFallbackEngine com roteiro GPS disponível.
    O roteiro contém pelo menos 2 passos — condição mínima para GPS enrichment.
    """
    engine = MagicMock()

    # indexer.search retorna um resultado com roteiro disponível
    engine.indexer.search.return_value = [
        {"roteiro_name": "roteiro_sign_studio"}
    ]

    # path_extractor.extract_navigation_path retorna um caminho com 2+ passos
    engine.path_extractor.extract_navigation_path.return_value = {
        "steps": [
            {"ordem": 1, "instrucao": "Acesse o menu Senior Flow", "seletor": "#menu-senior-flow"},
            {"ordem": 2, "instrucao": "Clique em Sign Studio", "seletor": "#btn-sign"},
        ]
    }

    return engine


def _make_roteiro_json() -> dict:
    """Retorna um roteiro JSON mínimo válido para ser 'lido do disco'."""
    return {
        "metadata": {"nome_aula": "roteiro_sign_studio"},
        "passos": [
            {"id_passo": 1, "pedagogia": {"ancora": "Acesse o menu Senior Flow"}},
            {"id_passo": 2, "pedagogia": {"ancora": "Clique em Sign Studio"}},
        ]
    }


def _make_gemini_response() -> MagicMock:
    """Retorna um mock de resposta do Gemini Vision (usado no caminho de score baixo)."""
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "analise_interna": "Usuário quer acessar Sign Studio",
        "mensagem": "Para acessar o Sign Studio, clique no menu Senior Flow.",
        "elemento_id": "btn-sign",
        "seletor_css": "#btn-sign",
        "sugestoes": ["Próximo passo", "O que mais posso fazer?"],
    })
    return mock_response


# ---------------------------------------------------------------------------
# Patch context manager helper
# ---------------------------------------------------------------------------

def _base_patches(busca_rag_result, fallback_engine=None, roteiro_data=None):
    """
    Retorna um dict de patches comuns para os testes de _analisar_sync.
    Isola todas as dependências externas (Pinecone, OpenAI, Gemini, cache, disco).
    """
    patches = {
        "buscar_contexto_multi_namespace": patch(
            "dap_engine.buscar_contexto_multi_namespace",
            return_value=busca_rag_result,
        ),
        "cache_get": patch("dap_engine._cache_get", return_value=None),
        "cache_set": patch("dap_engine._cache_set"),
        "gemini_client": patch("dap_engine.gemini_client"),
        "get_navigation_fallback_engine": patch(
            "dap_engine.get_navigation_fallback_engine",
            return_value=fallback_engine,
        ),
    }

    if roteiro_data is not None:
        # Mock open() para simular leitura do arquivo de roteiro do disco
        import builtins
        import io
        roteiro_json_str = json.dumps(roteiro_data)
        mock_open = MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=io.StringIO(roteiro_json_str)),
                __exit__=MagicMock(return_value=False),
            )
        )
        patches["open"] = patch("builtins.open", mock_open)

    return patches


# ===========================================================================
# Property 3: Bug Condition — AI Gate retorna resultado_rapido sem gps_passos
# ===========================================================================

class TestBug2AIGateGPSExploration:
    """
    Property 3: Bug Condition — AI Gate suprime gps_passos

    WHEN score > 0.80 AND seletor_direto presente AND roteiro GPS disponível
    THEN _analisar_sync DEVE retornar resultado com "gps_passos"
         (comportamento esperado pós-fix)

    No código NÃO corrigido, "gps_passos" está AUSENTE → teste FALHA.
    A falha confirma o bug.

    **Validates: Requirements 2.1, 2.2**
    """

    def test_ai_gate_ativo_deve_incluir_gps_passos(self):
        """
        CASO BUG: score=0.92, seletor_direto="#btn-sign", roteiro GPS disponível.

        Comportamento esperado (pós-fix): "gps_passos" IN resultado.
        Comportamento atual (bug): "gps_passos" NOT IN resultado.

        COUNTEREXAMPLE DOCUMENTADO:
          score=0.92, seletor_direto="#btn-sign", roteiro com 2 passos disponível
          → "gps_passos" not in resultado  (confirma o bug)

        Causa raiz: `return resultado_rapido` na seção 4 ocorre antes do bloco
        de GPS enrichment (que só existe na seção 5 — caminho Gemini Vision).

        **Validates: Requirements 2.1, 2.2**
        """
        busca_rag = _make_busca_rag_high_score(score=0.92, seletor="#btn-sign")
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client"), \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("builtins.open", MagicMock(
                 return_value=MagicMock(
                     __enter__=MagicMock(return_value=MagicMock(
                         read=MagicMock(return_value=json.dumps(roteiro_data))
                     )),
                     __exit__=MagicMock(return_value=False),
                 )
             )):

            import dap_engine

            # Patch json.load para retornar o roteiro_data quando chamado
            with patch("json.load", return_value=roteiro_data):
                resultado = dap_engine._analisar_sync(
                    image_b64="data:image/jpeg;base64,/9j/4AAQ",
                    url="https://senior.com/sign-studio",
                    prompt_usuario="Como acessar o Sign Studio?",
                    dom_context="<div>Dashboard Senior X</div>",
                    user_name="TestUser",
                    tenant_id="senior_default",
                    historico=[],
                )

        # COMPORTAMENTO ESPERADO (pós-fix): gps_passos deve estar presente
        # No código NÃO corrigido, esta assertion FALHA — confirmando o bug.
        assert "gps_passos" in resultado, (
            "BUG 2 CONFIRMADO: 'gps_passos' ausente no resultado do AI Gate. "
            f"Counterexample: score=0.92, seletor_direto='#btn-sign', roteiro GPS disponível. "
            f"Causa raiz: `return resultado_rapido` na seção 4 ocorre antes do bloco de GPS enrichment. "
            f"Resultado obtido: {list(resultado.keys())}"
        )

    def test_ai_gate_ativo_score_limite_deve_incluir_gps_passos(self):
        """
        CASO BUG: score=0.81 (logo acima do limiar), seletor presente, roteiro GPS disponível.

        Verifica que o bug ocorre em qualquer score > 0.80, não apenas em 0.92.

        **Validates: Requirements 2.1, 2.2**
        """
        busca_rag = _make_busca_rag_high_score(score=0.81, seletor="#btn-ged")
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()

        import io
        roteiro_json_str = json.dumps(roteiro_data)
        mock_open = MagicMock(
            return_value=MagicMock(
                __enter__=MagicMock(return_value=io.StringIO(roteiro_json_str)),
                __exit__=MagicMock(return_value=False),
            )
        )

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
                url="https://senior.com/ged",
                prompt_usuario="Como acessar o GED?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        assert "gps_passos" in resultado, (
            "BUG 2 CONFIRMADO: 'gps_passos' ausente no resultado do AI Gate (score=0.81). "
            f"Resultado obtido: {list(resultado.keys())}"
        )

    def test_ai_gate_ativo_resultado_rapido_tem_seletor_css(self):
        """
        Verifica que o AI Gate de fato ativa e retorna seletor_css correto.
        Este teste confirma que estamos no caminho certo (AI Gate ativo).

        **Validates: Requirements 2.1**
        """
        busca_rag = _make_busca_rag_high_score(score=0.92, seletor="#btn-sign")
        fallback_engine = _make_fallback_engine_with_gps()
        roteiro_data = _make_roteiro_json()

        with patch("dap_engine.buscar_contexto_multi_namespace", return_value=busca_rag), \
             patch("dap_engine._cache_get", return_value=None), \
             patch("dap_engine._cache_set"), \
             patch("dap_engine.gemini_client"), \
             patch("dap_engine.get_navigation_fallback_engine", return_value=fallback_engine), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("json.load", return_value=roteiro_data):

            import dap_engine
            resultado = dap_engine._analisar_sync(
                image_b64="data:image/jpeg;base64,/9j/4AAQ",
                url="https://senior.com/sign-studio",
                prompt_usuario="Como acessar o Sign Studio?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Confirma que o AI Gate ativou (seletor_css presente e confidence_score alto)
        assert resultado.get("seletor_css") == "#btn-sign", (
            f"AI Gate não ativou corretamente. seletor_css esperado: '#btn-sign', "
            f"obtido: {resultado.get('seletor_css')}"
        )
        assert resultado.get("confidence_score", 0) > 0.80, (
            f"confidence_score esperado > 0.80, obtido: {resultado.get('confidence_score')}"
        )


# ===========================================================================
# Preservation: score baixo (AI Gate inativo) — gps_passos pode estar presente
# ===========================================================================

class TestBug2AIGateInativo_Preservation:
    """
    Verifica que o caminho com score baixo (AI Gate inativo) não é afetado.
    Quando score=0.65, o Gemini Vision executa e o GPS enrichment pode adicionar
    gps_passos normalmente — este caminho NÃO deve falhar.

    **Validates: Requirements 3.5, 3.6**
    """

    def test_score_baixo_ai_gate_inativo_nao_falha(self):
        """
        CASO PRESERVATION: score=0.65 (AI Gate inativo).

        O Gemini Vision executa normalmente. O GPS enrichment no caminho Vision
        pode adicionar gps_passos. Este teste NÃO deve falhar no código atual.

        **Validates: Requirements 3.5, 3.6**
        """
        busca_rag = _make_busca_rag_low_score(score=0.65)
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
                url="https://senior.com/sign-studio",
                prompt_usuario="Como acessar o Sign Studio?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Com score baixo, o AI Gate NÃO ativa — Gemini Vision executa
        # O GPS enrichment no caminho Vision pode adicionar gps_passos
        # Este teste verifica que o caminho Vision funciona normalmente
        assert "mensagem" in resultado, (
            f"Caminho Vision falhou: 'mensagem' ausente no resultado. "
            f"Resultado: {resultado}"
        )

        # Nota: gps_passos PODE estar presente (GPS enrichment no caminho Vision funciona)
        # Não assertamos sua presença aqui — apenas que o caminho não quebra
        # O importante é que este teste PASSA no código atual (sem bug neste caminho)

    def test_score_exatamente_0_80_ai_gate_inativo(self):
        """
        CASO LIMITE: score=0.80 (exatamente no limiar — AI Gate NÃO ativa).

        O AI Gate só ativa com score ESTRITAMENTE maior que 0.80.
        Este teste confirma o comportamento do limiar.

        **Validates: Requirements 3.5**
        """
        # score=0.80 com seletor presente — AI Gate NÃO deve ativar (condição: > 0.80)
        busca_rag = {
            "score": 0.80,
            "seletor_direto": "#btn-sign",
            "melhor_aula": "aula_sign",
            "texto_rag": "INSTRUCAO: Clique em Sign",
        }
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
                url="https://senior.com/sign-studio",
                prompt_usuario="Como acessar o Sign Studio?",
                dom_context="<div>Dashboard Senior X</div>",
                user_name="TestUser",
                tenant_id="senior_default",
                historico=[],
            )

        # Com score=0.80, o AI Gate NÃO ativa — Gemini Vision executa
        # O resultado deve vir do Gemini Vision (mensagem do mock)
        assert "mensagem" in resultado, (
            f"Resultado inválido para score=0.80: {resultado}"
        )
        # Confirma que o Gemini foi chamado (AI Gate inativo)
        mock_gemini.models.generate_content.assert_called_once()

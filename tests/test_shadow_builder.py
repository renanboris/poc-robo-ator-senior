"""
tests/test_shadow_builder.py — Testes para shadow_builder.py
=============================================================
Executa sem Playwright, Gemini, OpenAI ou Pinecone.
Cobre: inferir_acao_semantica, inferir_entidade_negocio, inferir_padrao_interacao,
       classificar_ruido, _montar_evento_shadow, _salvar_shadow_jsonl.
Inclui testes de propriedade (Hypothesis) para invariantes críticos.
"""

import json
import os
import sys
import tempfile

import pytest

# Garante que o diretório raiz está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shadow_builder import (
    _montar_evento_shadow,
    _salvar_shadow_jsonl,
    classificar_ruido,
    inferir_acao_semantica,
    inferir_entidade_negocio,
    inferir_padrao_interacao,
)

# ──────────────────────────────────────────────────────────────
# VOCABULÁRIO CONTROLADO
# ──────────────────────────────────────────────────────────────
VOCABULARIO = {"fill", "search", "confirm", "delete", "save", "open", "navigate", "select", "close"}

# ──────────────────────────────────────────────────────────────
# FIXTURE
# ──────────────────────────────────────────────────────────────
@pytest.fixture
def params_shadow_minimos():
    return {
        "id_acao": 1,
        "acao": "clique",
        "label": "Salvar",
        "dados": {
            "seletor": "[aria-label='Salvar']",
            "tag": "button",
            "html_snapshot": "<button aria-label='Salvar'>Salvar</button>",
        },
        "analise": {
            "intencao": "Salvar registro",
            "descricao_visual": "Botão Salvar",
            "contexto_tela": "Formulário",
            "tipo_elemento": "button",
            "confianca": "alta",
        },
        "iframe_id": None,
        "coords": {"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05},
        "screenshot_b64": None,
        "page_title": "Senior X",
        "page_url": "https://platform.senior.com.br",
        "vp_w": 1920,
        "vp_h": 1080,
        "valor_input": "",
    }


# ──────────────────────────────────────────────────────────────
# TESTES: inferir_acao_semantica
# ──────────────────────────────────────────────────────────────
class TestInferirAcaoSemantica:
    def test_fill_preencher_campo(self):
        assert inferir_acao_semantica("preencher_campo", "Nome", "", "input") == "fill"

    def test_search_pesquisar(self):
        assert inferir_acao_semantica("clique", "Pesquisar", "", "button") == "search"

    def test_search_digitar_e_enter_com_filtro(self):
        assert inferir_acao_semantica("digitar_e_enter", "filtro", "", "input") == "search"

    def test_confirm_label_sim(self):
        assert inferir_acao_semantica("clique", "sim", "", "button") == "confirm"

    def test_confirm_label_ok(self):
        assert inferir_acao_semantica("clique", "ok", "", "button") == "confirm"

    def test_delete_excluir(self):
        assert inferir_acao_semantica("clique", "Excluir", "", "button") == "delete"

    def test_delete_remover(self):
        assert inferir_acao_semantica("clique", "Remover item", "", "button") == "delete"

    def test_save_salvar(self):
        assert inferir_acao_semantica("clique", "Salvar", "", "button") == "save"

    def test_open_duplo_clique(self):
        assert inferir_acao_semantica("duplo_clique", "Pasta GED", "", "div") == "open"

    def test_open_clique_direito(self):
        assert inferir_acao_semantica("clique_direito", "Arquivo", "", "span") == "open"

    def test_open_criar(self):
        assert inferir_acao_semantica("clique", "Criar nova pasta", "", "button") == "open"

    def test_navigate_clique_generico(self):
        assert inferir_acao_semantica("clique", "Menu Principal", "", "a") == "navigate"

    def test_hints_acao_save(self):
        resultado = inferir_acao_semantica("", "", "", "", hints={"acao": "clique", "text_hint": "Salvar"})
        assert resultado == "save"

    def test_hints_acao_fill(self):
        resultado = inferir_acao_semantica("", "", "", "", hints={"acao": "preencher_campo", "text_hint": "Nome"})
        assert resultado == "fill"

    def test_retorno_sempre_no_vocabulario(self):
        casos = [
            ("clique", "qualquer coisa", "", "div"),
            ("", "", "", ""),
            ("duplo_clique", "", "", ""),
        ]
        for acao, label, seletor, tag in casos:
            resultado = inferir_acao_semantica(acao, label, seletor, tag)
            assert resultado in VOCABULARIO, f"Resultado '{resultado}' fora do vocabulário para ({acao}, {label})"


# ──────────────────────────────────────────────────────────────
# TESTES: inferir_entidade_negocio
# ──────────────────────────────────────────────────────────────
class TestInferirEntidadeNegocio:
    def test_pasta(self):
        assert inferir_entidade_negocio("Criar pasta", "", "button") == "pasta"

    def test_documento_ged(self):
        assert inferir_entidade_negocio("Documento GED", "", "div") == "documento"

    def test_documento_document(self):
        assert inferir_entidade_negocio("document upload", "", "input") == "documento"

    def test_menu(self):
        assert inferir_entidade_negocio("menu lateral", "", "nav") == "menu"

    def test_campo_input(self):
        assert inferir_entidade_negocio("Nome", "", "input") == "campo"

    def test_campo_textarea(self):
        assert inferir_entidade_negocio("Descrição", "", "textarea") == "campo"

    def test_selecao_checkbox(self):
        assert inferir_entidade_negocio("Checkbox de: Item 1", "p-checkbox", "div") == "selecao"

    def test_elemento_fallback(self):
        assert inferir_entidade_negocio("Botão genérico", "", "button") == "elemento"

    def test_hints_pasta(self):
        resultado = inferir_entidade_negocio("", "", "", hints={"text_hint": "Nova pasta"})
        assert resultado == "pasta"


# ──────────────────────────────────────────────────────────────
# TESTES: classificar_ruido
# ──────────────────────────────────────────────────────────────
class TestClassificarRuido:
    def test_breadcrumb_e_ruido(self):
        assert classificar_ruido("Home", "ui-breadcrumb", "clique", "li", "shell") is True

    def test_fa_home_e_ruido(self):
        assert classificar_ruido("", ".fa-home", "clique", "i", "shell") is True

    def test_enter_sem_valor_e_ruido(self):
        assert classificar_ruido("", "", "digitar_e_enter", "input", "shell", valor_input="") is True

    def test_icone_sem_label_e_ruido(self):
        assert classificar_ruido("", "", "clique", "i", "shell") is True

    def test_icone_svg_sem_label_e_ruido(self):
        assert classificar_ruido("svg", "", "clique", "svg", "shell") is True

    def test_clique_normal_nao_e_ruido(self):
        assert classificar_ruido("Salvar", "[aria-label='Salvar']", "clique", "button", "shell") is False

    def test_preencher_campo_nao_e_ruido(self):
        assert classificar_ruido("Nome", "", "preencher_campo", "input", "shell", valor_input="João") is False

    def test_hints_breadcrumb(self):
        resultado = classificar_ruido("", "", "", "", "shell", hints={"seletor_css": "ui-breadcrumb", "acao": "clique"})
        assert resultado is True

    def test_hints_clique_normal(self):
        resultado = classificar_ruido("", "", "", "", "shell", hints={"text_hint": "Salvar", "acao": "clique", "seletor_css": "[aria-label='Salvar']"})
        assert resultado is False


# ──────────────────────────────────────────────────────────────
# TESTES: _montar_evento_shadow
# ──────────────────────────────────────────────────────────────
CHAVES_OBRIGATORIAS = {
    "id_acao", "captured_at", "acao", "capture_scope", "is_noise",
    "intencao_semantica", "semantic_action", "business_entity",
    "business_target", "pattern_detectado", "elemento_alvo", "technical",
}


class TestMontarEventoShadow:
    def test_campos_obrigatorios_presentes(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        faltando = CHAVES_OBRIGATORIAS - set(resultado.keys())
        assert not faltando, f"Chaves faltando: {faltando}"

    def test_id_acao_preservado(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["id_acao"] == 1

    def test_acao_preservada(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["acao"] == "clique"

    def test_semantic_action_no_vocabulario(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["semantic_action"] in VOCABULARIO

    def test_capture_scope_shell_sem_iframe(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["capture_scope"] == "shell"

    def test_capture_scope_module_iframe_com_iframe(self, params_shadow_minimos):
        params = dict(params_shadow_minimos)
        params["iframe_id"] = "modulo-ged"
        resultado = _montar_evento_shadow(**params)
        assert resultado["capture_scope"] == "module_iframe"

    def test_is_noise_false_para_clique_normal(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["is_noise"] is False

    def test_elemento_alvo_tem_label_curto(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        assert resultado["elemento_alvo"]["label_curto"] == "Salvar"

    def test_technical_tem_campos_basicos(self, params_shadow_minimos):
        resultado = _montar_evento_shadow(**params_shadow_minimos)
        tech = resultado["technical"]
        assert "acao" in tech
        assert "tag" in tech
        assert "x_pct" in tech
        assert "y_pct" in tech


# ──────────────────────────────────────────────────────────────
# TESTES: _salvar_shadow_jsonl
# ──────────────────────────────────────────────────────────────
class TestSalvarShadowJsonl:
    def test_cria_arquivo(self, params_shadow_minimos, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        eventos = [_montar_evento_shadow(**params_shadow_minimos)]
        caminho = _salvar_shadow_jsonl("Aula Teste", "Objetivo", eventos)
        assert caminho is not None
        assert os.path.exists(caminho)

    def test_cada_linha_e_json_valido(self, params_shadow_minimos, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        params2 = dict(params_shadow_minimos)
        params2["id_acao"] = 2
        eventos = [
            _montar_evento_shadow(**params_shadow_minimos),
            _montar_evento_shadow(**params2),
        ]
        caminho = _salvar_shadow_jsonl("Aula Teste", "Objetivo", eventos)
        with open(caminho, encoding="utf-8") as f:
            linhas = f.readlines()
        assert len(linhas) == 2
        for linha in linhas:
            parsed = json.loads(linha)
            assert isinstance(parsed, dict)

    def test_ordenado_por_id_acao(self, params_shadow_minimos, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        # Cria eventos em ordem inversa
        params3 = dict(params_shadow_minimos); params3["id_acao"] = 3
        params1 = dict(params_shadow_minimos); params1["id_acao"] = 1
        params2 = dict(params_shadow_minimos); params2["id_acao"] = 2
        eventos = [
            _montar_evento_shadow(**params3),
            _montar_evento_shadow(**params1),
            _montar_evento_shadow(**params2),
        ]
        caminho = _salvar_shadow_jsonl("Aula Ordem", "Objetivo", eventos)
        with open(caminho, encoding="utf-8") as f:
            ids = [json.loads(l)["id_acao"] for l in f.readlines()]
        assert ids == sorted(ids), f"Eventos não ordenados: {ids}"

    def test_retorna_none_em_falha(self, monkeypatch):
        # Força falha ao tentar criar o diretório em caminho inválido
        import shadow_builder as sb
        original = sb.os.makedirs
        def makedirs_falha(*a, **kw):
            raise PermissionError("sem permissão")
        monkeypatch.setattr(sb.os, "makedirs", makedirs_falha)
        resultado = _salvar_shadow_jsonl("Aula", "Obj", [{"id_acao": 1}])
        assert resultado is None


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

    @given(
        acao=st.text(max_size=50),
        label=st.text(max_size=100),
        seletor=st.text(max_size=200),
        tag=st.text(max_size=20),
        valor_input=st.text(max_size=100),
    )
    @settings(max_examples=200)
    def test_vocabulario_controlado_sempre(self, acao, label, seletor, tag, valor_input):
        """P2.1 / P5.1 — inferir_acao_semantica sempre retorna valor do vocabulário."""
        resultado = inferir_acao_semantica(acao, label, seletor, tag, valor_input)
        assert resultado in VOCABULARIO

    @given(
        acao=st.text(max_size=50),
        label=st.text(max_size=100),
        seletor=st.text(max_size=200),
        tag=st.text(max_size=20),
        valor_input=st.text(max_size=100),
    )
    @settings(max_examples=100)
    def test_determinismo(self, acao, label, seletor, tag, valor_input):
        """P2.2 — mesmos inputs produzem sempre o mesmo resultado."""
        r1 = inferir_acao_semantica(acao, label, seletor, tag, valor_input)
        r2 = inferir_acao_semantica(acao, label, seletor, tag, valor_input)
        assert r1 == r2

    @given(
        id_acao=st.integers(min_value=1, max_value=9999),
        acao=st.sampled_from(["clique", "preencher_campo", "digitar_e_enter", "duplo_clique"]),
        label=st.text(min_size=1, max_size=40),
    )
    @settings(max_examples=100)
    def test_campos_obrigatorios_property(self, id_acao, acao, label):
        """P5.2 / P6 — _montar_evento_shadow sempre retorna as 12 chaves obrigatórias."""
        params = {
            "id_acao": id_acao, "acao": acao, "label": label,
            "dados": {"seletor": "", "tag": "button", "html_snapshot": ""},
            "analise": {"intencao": f"{acao} em {label}", "descricao_visual": label,
                        "contexto_tela": "Tela", "tipo_elemento": "button", "confianca": "media"},
            "iframe_id": None,
            "coords": {"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05},
            "screenshot_b64": None, "page_title": "Senior X",
            "page_url": "https://x.senior.com.br",
            "vp_w": 1920, "vp_h": 1080, "valor_input": "",
        }
        resultado = _montar_evento_shadow(**params)
        faltando = CHAVES_OBRIGATORIAS - set(resultado.keys())
        assert not faltando

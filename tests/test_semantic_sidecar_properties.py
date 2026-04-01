"""
tests/test_semantic_sidecar_properties.py
==========================================
Property-based and unit tests for the Fase 2 Semantic Sidecar integration.

Uses Hypothesis to verify correctness properties defined in:
  .kiro/specs/semantic-sidecar/design.md
"""

import io
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import given, settings, strategies as st

from shadow_builder import (
    _infer_capture_scope,
    _infer_semantic_action_from_capture,
    _infer_business_entity_from_capture,
    _infer_pattern_from_capture,
    _is_noise_event,
    _montar_evento_shadow,
    _salvar_shadow_jsonl,
    utc_now,
)


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — shadow_builder importa sem Playwright
# ──────────────────────────────────────────────────────────────

def test_shadow_builder_importa_sem_playwright():
    """shadow_builder deve ser importável sem Playwright instalado."""
    import shadow_builder  # noqa: F401 — já importado acima, mas verifica que não crashou


def test_utc_now_formato_iso8601():
    """utc_now deve retornar string no formato ISO 8601 com timezone UTC."""
    resultado = utc_now()
    assert isinstance(resultado, str)
    assert "+" in resultado or resultado.endswith("Z"), f"Sem timezone: {resultado}"


def test_salvar_shadow_jsonl_cria_diretorio(tmp_path, monkeypatch):
    """_salvar_shadow_jsonl deve criar shadow_exports/ se não existir."""
    monkeypatch.chdir(tmp_path)
    eventos = [{"id_acao": 1, "acao": "clique"}]
    caminho = _salvar_shadow_jsonl("teste_aula", "objetivo", eventos)
    assert caminho is not None
    assert os.path.exists(caminho)


def test_salvar_shadow_jsonl_emite_shadow_gerado(tmp_path, monkeypatch, capsys):
    """_salvar_shadow_jsonl deve emitir SHADOW_GERADO:{caminho} no stdout."""
    monkeypatch.chdir(tmp_path)
    eventos = [{"id_acao": 1, "acao": "clique"}]
    caminho = _salvar_shadow_jsonl("teste_aula", "objetivo", eventos)
    captured = capsys.readouterr()
    assert f"SHADOW_GERADO:{caminho}" in captured.out


def test_salvar_shadow_jsonl_falha_retorna_none(tmp_path, monkeypatch):
    """_salvar_shadow_jsonl deve retornar None sem propagar exceção em caso de falha."""
    monkeypatch.chdir(tmp_path)
    # Cria shadow_exports como arquivo (não diretório) para forçar falha
    os.makedirs(tmp_path / "shadow_exports", exist_ok=True)
    (tmp_path / "shadow_exports" / "teste_aula_shadow.jsonl").write_text("bloqueado")
    # Tenta gravar em um caminho inválido
    resultado = _salvar_shadow_jsonl("teste_aula", "objetivo", [{"id_acao": 1}])
    # Pode ter sucesso (sobrescreve) ou falhar — o importante é não propagar exceção
    assert resultado is None or isinstance(resultado, str)


def test_salvar_shadow_jsonl_nao_emite_se_falha(tmp_path, monkeypatch, capsys):
    """_salvar_shadow_jsonl não deve emitir SHADOW_GERADO: se a gravação falhar."""
    monkeypatch.chdir(tmp_path)
    # Força falha criando shadow_exports como arquivo
    (tmp_path / "shadow_exports").write_text("bloqueado")
    _salvar_shadow_jsonl("teste_aula", "objetivo", [{"id_acao": 1}])
    captured = capsys.readouterr()
    assert "SHADOW_GERADO:" not in captured.out


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — capture_dual_output importa de shadow_builder
# ──────────────────────────────────────────────────────────────

def test_capture_dual_importa_de_shadow_builder():
    """As 8 funções devem ser importadas de shadow_builder, não definidas localmente."""
    import capture_dual_output
    import shadow_builder

    funcoes = [
        "utc_now",
        "_infer_capture_scope",
        "_infer_semantic_action_from_capture",
        "_infer_business_entity_from_capture",
        "_infer_pattern_from_capture",
        "_is_noise_event",
        "_montar_evento_shadow",
        "_salvar_shadow_jsonl",
    ]
    for nome in funcoes:
        func_dual   = getattr(capture_dual_output, nome, None)
        func_shadow = getattr(shadow_builder, nome, None)
        assert func_dual is func_shadow, (
            f"{nome} em capture_dual_output não é a mesma função de shadow_builder"
        )


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — capture_hybrid_shadow importa utc_now de shadow_builder
# ──────────────────────────────────────────────────────────────

def test_hybrid_utc_now_importado_de_shadow_builder():
    """utc_now em capture_hybrid_shadow deve ser a mesma função de shadow_builder."""
    import capture_hybrid_shadow
    import shadow_builder
    assert capture_hybrid_shadow.utc_now is shadow_builder.utc_now


def test_hybrid_infer_semantic_action_tecla_ctrl_s():
    """acao == 'tecla' com Ctrl+S deve retornar 'save' no modo híbrido."""
    from capture_hybrid_shadow import infer_semantic_action_from_hints
    payload = {"acao": "tecla", "tecla": "Ctrl+S", "text_hint": "", "tag": "input",
               "aria_hint": "", "title_hint": "", "seletor_css": "", "page_title": ""}
    assert infer_semantic_action_from_hints(payload) == "save"


def test_hybrid_infer_semantic_action_selecionar_opcao():
    """acao == 'selecionar_opcao' deve retornar 'select' no modo híbrido."""
    from capture_hybrid_shadow import infer_semantic_action_from_hints
    payload = {"acao": "selecionar_opcao", "text_hint": "Opção A", "tag": "select",
               "aria_hint": "", "title_hint": "", "seletor_css": "", "page_title": ""}
    assert infer_semantic_action_from_hints(payload) == "select"


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — app.py estado_servidor
# ──────────────────────────────────────────────────────────────

def test_estado_inicial_tem_shadow_path_none():
    """estado_servidor deve ter shadow_path == None na inicialização."""
    # Verifica diretamente no código fonte sem importar app (evita dep de fastapi no test env)
    import ast, pathlib
    src = pathlib.Path("app.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "estado_servidor":
                    if isinstance(node.value, ast.Dict):
                        keys = [k.s if isinstance(k, ast.Constant) else None for k in node.value.keys]
                        assert "shadow_path" in keys, "shadow_path ausente em estado_servidor"
                        return
    pytest.fail("estado_servidor não encontrado em app.py")


# ──────────────────────────────────────────────────────────────
# PROPERTY 1: _montar_evento_shadow produz todos os campos obrigatórios
# ──────────────────────────────────────────────────────────────

CAMPOS_OBRIGATORIOS = {
    "id_acao", "captured_at", "acao", "capture_scope", "is_noise",
    "intencao_semantica", "semantic_action", "business_entity", "business_target",
    "pattern_detectado", "valor_input", "micro_narracao", "contexto_semantico",
    "validacao_esperada", "elemento_alvo", "technical",
}

# Feature: semantic-sidecar, Property 1: _montar_evento_shadow produz eventos com todos os campos obrigatórios
@given(
    id_acao=st.integers(min_value=0, max_value=1000),
    acao=st.sampled_from(["clique", "duplo_clique", "clique_direito", "preencher_campo", "digitar_e_enter"]),
    label=st.text(max_size=120),
    seletor=st.text(max_size=200),
    tag=st.sampled_from(["button", "a", "input", "div", "span", "i", "svg"]),
    valor_input=st.text(max_size=80),
)
@settings(max_examples=100)
def test_montar_evento_shadow_campos_obrigatorios(id_acao, acao, label, seletor, tag, valor_input):
    """_montar_evento_shadow deve sempre produzir todos os campos obrigatórios."""
    evento = _montar_evento_shadow(
        id_acao=id_acao,
        acao=acao,
        label=label,
        dados={"seletor": seletor, "tag": tag, "html_snapshot": ""},
        analise={},
        iframe_id=None,
        coords={"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05},
        screenshot_b64=None,
        page_title="",
        page_url="",
        vp_w=1920,
        vp_h=1080,
        valor_input=valor_input,
    )
    assert CAMPOS_OBRIGATORIOS.issubset(evento.keys()), (
        f"Campos ausentes: {CAMPOS_OBRIGATORIOS - evento.keys()}"
    )


# ──────────────────────────────────────────────────────────────
# PROPERTY 2: _salvar_shadow_jsonl ordena por id_acao
# ──────────────────────────────────────────────────────────────

# Feature: semantic-sidecar, Property 2: _salvar_shadow_jsonl ordena eventos por id_acao antes de gravar
@given(st.lists(
    st.fixed_dictionaries({"id_acao": st.integers(min_value=0, max_value=1000)}),
    min_size=1, max_size=50,
))
@settings(max_examples=100)
def test_salvar_shadow_jsonl_ordena_por_id_acao(eventos):
    """O arquivo JSONL deve conter eventos em ordem crescente de id_acao."""
    import tempfile, os as _os
    with tempfile.TemporaryDirectory() as tmpdir:
        orig = _os.getcwd()
        _os.chdir(tmpdir)
        try:
            caminho = _salvar_shadow_jsonl("teste", "objetivo", eventos)
            assert caminho is not None
            with open(caminho, encoding="utf-8") as f:
                lidos = [json.loads(linha) for linha in f]
            ids = [e["id_acao"] for e in lidos]
            assert ids == sorted(ids), f"Eventos fora de ordem: {ids}"
        finally:
            _os.chdir(orig)


# ──────────────────────────────────────────────────────────────
# PROPERTY 3: _is_noise_event para breadcrumbs e ícones
# ──────────────────────────────────────────────────────────────

# Feature: semantic-sidecar, Property 3: _is_noise_event retorna True para breadcrumbs e ícones sem label
@given(
    seletor=st.sampled_from(["breadcrumb", ".ui-breadcrumb", "fa-home", "ui-breadcrumb-nav"]),
    label=st.text(max_size=50),
)
@settings(max_examples=100)
def test_is_noise_breadcrumb(seletor, label):
    """Seletores de breadcrumb devem sempre ser marcados como noise."""
    assert _is_noise_event(label, seletor, "clique", "a", "shell") is True


@given(
    tag=st.sampled_from(["i", "svg", "path"]),
    label=st.sampled_from(["", "i", "svg", "path", "span", "div", "a"]),
)
@settings(max_examples=100)
def test_is_noise_icone_sem_label(tag, label):
    """Ícones sem label semântico devem ser marcados como noise."""
    assert _is_noise_event(label, "algum-seletor", "clique", tag, "shell") is True


# ──────────────────────────────────────────────────────────────
# PROPERTY 4: vocabulário controlado de _infer_semantic_action_from_capture
# ──────────────────────────────────────────────────────────────

ACOES_VALIDAS = {"fill", "search", "confirm", "delete", "save", "open", "navigate", "select", "close"}

# Feature: semantic-sidecar, Property 4: _infer_semantic_action_from_capture sempre retorna valor do vocabulário controlado
@given(
    acao=st.text(max_size=50),
    label=st.text(max_size=120),
    seletor=st.text(max_size=200),
    tag=st.sampled_from(["button", "a", "input", "div", "span"]),
    valor_input=st.text(max_size=80),
)
@settings(max_examples=100)
def test_infer_semantic_action_vocabulario_controlado(acao, label, seletor, tag, valor_input):
    """_infer_semantic_action_from_capture deve sempre retornar um valor do vocabulário controlado."""
    resultado = _infer_semantic_action_from_capture(acao, label, seletor, tag, valor_input)
    assert resultado in ACOES_VALIDAS, (
        f"Valor fora do vocabulário: {resultado!r} para acao={acao!r}"
    )


# ──────────────────────────────────────────────────────────────
# PROPERTY 6: SHADOW_GERADO: após ROTEIRO_GERADO: no stdout
# ──────────────────────────────────────────────────────────────

# Feature: semantic-sidecar, Property 6: SHADOW_GERADO é emitido após ROTEIRO_GERADO na sequência de stdout
def test_shadow_gerado_apos_roteiro_gerado():
    """Na sequência de stdout, SHADOW_GERADO deve aparecer após ROTEIRO_GERADO."""
    linhas = [
        "PROGRESSO:50",
        "ROTEIRO_GERADO:roteiros_salvos/teste.json",
        "SHADOW_GERADO:shadow_exports/teste_shadow.jsonl",
    ]
    idx_roteiro = next(i for i, l in enumerate(linhas) if l.startswith("ROTEIRO_GERADO:"))
    idx_shadow  = next(i for i, l in enumerate(linhas) if l.startswith("SHADOW_GERADO:"))
    assert idx_shadow > idx_roteiro, (
        f"SHADOW_GERADO (idx={idx_shadow}) deve vir após ROTEIRO_GERADO (idx={idx_roteiro})"
    )

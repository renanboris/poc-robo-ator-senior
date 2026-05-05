"""
tests/test_vision_quality_properties.py
=========================================
Property-based and unit tests for Fase 3 — Melhoria de Vision e Seletores.

Uses Hypothesis to verify correctness properties defined in:
  .kiro/specs/vision-quality/design.md
"""

import base64
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from utils import limpar_nome, validar_roteiro, validar_roteiro_ia
from validator import _e_acao_navegacao
from vision_engine import _resolver_screenshot_ref

# ──────────────────────────────────────────────────────────────
# PROPERTY 1: _resolver_screenshot_ref retorna bytes para referência válida
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 1: _resolver_screenshot_ref retorna bytes para qualquer referência válida
@given(data=st.binary(min_size=1, max_size=1024))
@settings(max_examples=100)
def test_resolver_retorna_bytes_para_base64_valido(data):
    """_resolver_screenshot_ref deve decodificar base64 válido para bytes."""
    b64 = base64.b64encode(data).decode()
    resultado = _resolver_screenshot_ref(b64)
    assert resultado == data


@given(data=st.binary(min_size=1, max_size=1024))
@settings(max_examples=100)
def test_resolver_retorna_bytes_para_path_valido(data):
    """_resolver_screenshot_ref deve ler bytes de path existente em disco."""
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        resultado = _resolver_screenshot_ref(path)
        assert resultado == data
    finally:
        os.unlink(path)


def test_resolver_retorna_none_para_none():
    """_resolver_screenshot_ref deve retornar None para None."""
    assert _resolver_screenshot_ref(None) is None


def test_resolver_retorna_none_para_path_inexistente():
    """_resolver_screenshot_ref deve retornar None para path que não existe."""
    assert _resolver_screenshot_ref("/caminho/que/nao/existe.jpg") is None


def test_resolver_retorna_none_para_base64_invalido():
    """_resolver_screenshot_ref deve retornar None para base64 corrompido."""
    assert _resolver_screenshot_ref("!!!base64_invalido!!!") is None


def test_resolver_nao_lanca_excecao_para_string_vazia():
    """_resolver_screenshot_ref não deve lançar exceção para string vazia."""
    resultado = _resolver_screenshot_ref("")
    assert resultado is None


# ──────────────────────────────────────────────────────────────
# PROPERTY 3: lego_builder remove screenshot_referencia independentemente do formato
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 3: lego_builder remove screenshot_referencia independentemente do formato
@given(ref=st.one_of(
    st.just("audios_gerados/Aula/screenshots/acao_1.jpg"),
    st.binary(min_size=10, max_size=100).map(lambda b: base64.b64encode(b).decode()),
))
@settings(max_examples=50)
def test_lego_remove_screenshot_ref(ref):
    """lego_builder deve remover screenshot_referencia independentemente do formato."""
    from lego_builder import construir_biblioteca

    roteiro = {"passos": [{"acoes_tecnicas": [{
        "acao": "clique",
        "intencao_semantica": "clicar em salvar",
        "elemento_alvo": {"label_curto": "Salvar", "screenshot_referencia": ref},
    }]}]}

    with tempfile.TemporaryDirectory() as tmpdir:
        roteiros_dir = os.path.join(tmpdir, "roteiros_salvos")
        os.makedirs(roteiros_dir)
        roteiro_path = os.path.join(roteiros_dir, "teste.json")
        with open(roteiro_path, "w", encoding="utf-8") as f:
            json.dump(roteiro, f)

        lib_path = os.path.join(tmpdir, "lib.json")
        resultado = construir_biblioteca(roteiros_dir, lib_path)
        assert resultado["status"] == "sucesso"

        with open(lib_path, encoding="utf-8") as f:
            lib = json.load(f)

        for peca in lib.values():
            assert "screenshot_referencia" not in peca.get("elemento_alvo", {}), (
                f"screenshot_referencia não foi removido da peça: {peca}"
            )


# ──────────────────────────────────────────────────────────────
# PROPERTY 4: _e_acao_navegacao classifica por palavras-chave
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 4: _e_acao_navegacao classifica corretamente por palavras-chave
@given(
    keyword=st.sampled_from(["menu", "breadcrumb", "fa-home", "home", "sidebar", "nav-item"]),
    prefix=st.text(max_size=10, alphabet=st.characters(blacklist_categories=("Cs",))),
    suffix=st.text(max_size=10, alphabet=st.characters(blacklist_categories=("Cs",))),
)
@settings(max_examples=100)
def test_acao_navegacao_detecta_palavras_chave_no_label(keyword, prefix, suffix):
    """Ações com palavras-chave de navegação no label devem ser classificadas como navegação."""
    acao = {"elemento_alvo": {"label_curto": f"{prefix}{keyword}{suffix}", "seletor_hint": ""}}
    assert _e_acao_navegacao(acao) is True


@given(
    keyword=st.sampled_from(["menu", "breadcrumb", "fa-home", "home", "sidebar", "nav-item"]),
    prefix=st.text(max_size=10, alphabet=st.characters(blacklist_categories=("Cs",))),
)
@settings(max_examples=100)
def test_acao_navegacao_detecta_palavras_chave_no_seletor(keyword, prefix):
    """Ações com palavras-chave de navegação no seletor devem ser classificadas como navegação."""
    acao = {"elemento_alvo": {"label_curto": "", "seletor_hint": f"{prefix}-{keyword}-btn"}}
    assert _e_acao_navegacao(acao) is True


@given(
    label=st.text(
        alphabet=st.characters(blacklist_categories=("Cs",)),
        max_size=30,
    )
)
@settings(max_examples=100)
def test_acao_sem_palavras_chave_nao_e_navegacao(label):
    """Ações sem palavras-chave de navegação não devem ser classificadas como navegação."""
    palavras = ["menu", "breadcrumb", "fa-home", "home", "inicio", "módulo",
                "apps-menu", "menu-item", "nav-item", "sidebar"]
    assume(not any(k in label.lower() for k in palavras))
    acao = {"elemento_alvo": {"label_curto": label, "seletor_hint": ""}}
    assert _e_acao_navegacao(acao) is False


# ──────────────────────────────────────────────────────────────
# PROPERTY 5: validar_roteiro_ia reprova roteiros com menos de 2 passos
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 5: validar_roteiro_ia reprova roteiros com menos de 2 passos
@given(n=st.integers(min_value=0, max_value=1))
@settings(max_examples=100)
def test_reprova_poucos_passos(n):
    """validar_roteiro_ia deve reprovar roteiros com 0 ou 1 passo."""
    roteiro = {"passos": [{"id_passo": i} for i in range(n)]}
    ok, motivo = validar_roteiro_ia(roteiro)
    assert ok is False
    assert "passo" in motivo.lower()


# ──────────────────────────────────────────────────────────────
# PROPERTY 6: validar_roteiro_ia reprova roteiros sem âncora pedagógica
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 6: validar_roteiro_ia reprova roteiros sem âncora pedagógica
@given(n=st.integers(min_value=2, max_value=5))
@settings(max_examples=100)
def test_reprova_sem_ancora(n):
    """validar_roteiro_ia deve reprovar roteiros onde todos os passos têm ancora vazia."""
    passos = [
        {
            "id_passo": i,
            "is_conclusao": False,
            "pedagogia": {"ancora": ""},
            "acoes_tecnicas": [{"acao": "clique", "elemento_alvo": {"label_curto": "X"}}],
        }
        for i in range(n)
    ]
    ok, motivo = validar_roteiro_ia({"passos": passos})
    assert ok is False
    assert "ancora" in motivo.lower() or "pedagóg" in motivo.lower()


# ──────────────────────────────────────────────────────────────
# PROPERTY 7: validar_roteiro_ia reprova roteiros sem elemento_alvo
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 7: validar_roteiro_ia reprova roteiros sem elemento_alvo em nenhuma ação
@given(n=st.integers(min_value=2, max_value=5))
@settings(max_examples=100)
def test_reprova_sem_elemento_alvo(n):
    """validar_roteiro_ia deve reprovar roteiros onde nenhuma ação tem elemento_alvo."""
    passos = [
        {
            "id_passo": i,
            "is_conclusao": False,
            "pedagogia": {"ancora": "Introdução"},
            "acoes_tecnicas": [{"acao": "clique", "elemento_alvo": {}}],
        }
        for i in range(n)
    ]
    ok, motivo = validar_roteiro_ia({"passos": passos})
    assert ok is False
    assert "elemento" in motivo.lower()


# ──────────────────────────────────────────────────────────────
# PROPERTY 8: validar_roteiro_ia reprova passo não-conclusão sem ações
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 8: validar_roteiro_ia reprova roteiros com passo não-conclusão sem ações
def test_reprova_passo_sem_acoes():
    """validar_roteiro_ia deve reprovar roteiro com passo não-conclusão sem ações."""
    passos = [
        {
            "id_passo": 1,
            "is_conclusao": False,
            "pedagogia": {"ancora": "Introdução"},
            "acoes_tecnicas": [{"acao": "clique", "elemento_alvo": {"label_curto": "X"}}],
        },
        {
            "id_passo": 2,
            "is_conclusao": False,
            "pedagogia": {"ancora": "Passo vazio"},
            "acoes_tecnicas": [],  # vazio — deve reprovar
        },
        {
            "id_passo": 3,
            "is_conclusao": True,
            "pedagogia": {"ancora": "Fim"},
            "acoes_tecnicas": [{"acao": "concluir_video"}],
        },
    ]
    ok, motivo = validar_roteiro_ia({"passos": passos})
    assert ok is False
    assert "2" in motivo  # menciona o id do passo problemático


# ──────────────────────────────────────────────────────────────
# PROPERTY 9: validar_roteiro_ia aprova roteiros bem formados
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 9: validar_roteiro_ia aprova roteiros bem formados
@given(n=st.integers(min_value=2, max_value=5))
@settings(max_examples=100)
def test_aprova_roteiro_bem_formado(n):
    """validar_roteiro_ia deve aprovar roteiros com conteúdo pedagógico e técnico."""
    passos = [
        {
            "id_passo": i,
            "is_conclusao": False,
            "pedagogia": {"ancora": "Introdução ao passo"},
            "acoes_tecnicas": [
                {"acao": "clique", "elemento_alvo": {"label_curto": "Botão", "seletor_hint": ""}}
            ],
        }
        for i in range(n - 1)
    ] + [
        {
            "id_passo": n,
            "is_conclusao": True,
            "pedagogia": {"ancora": "Parabéns!"},
            "acoes_tecnicas": [{"acao": "concluir_video"}],
        }
    ]
    ok, msg = validar_roteiro_ia({"passos": passos})
    assert ok is True, f"Deveria aprovar mas reprovou: {msg}"
    assert "OK" in msg


# ──────────────────────────────────────────────────────────────
# PROPERTY 10: validar_roteiro não-regressão
# ──────────────────────────────────────────────────────────────

# Feature: vision-quality, Property 10: validar_roteiro não-regressão
@given(n=st.integers(min_value=2, max_value=5))
@settings(max_examples=100)
def test_validar_roteiro_nao_regride(n):
    """validar_roteiro deve continuar aprovando roteiros capturados válidos."""
    passos = [
        {
            "id_passo": i,
            "acoes_tecnicas": [{
                "acao": "clique",
                "elemento_alvo": {
                    "seletor_hint": f"[data-id='{i}']",
                    "confianca_captura": "alta",
                },
            }],
        }
        for i in range(n)
    ]
    ok, _ = validar_roteiro({"passos": passos})
    assert ok is True


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — validar_roteiro_ia interface
# ──────────────────────────────────────────────────────────────

def test_validar_roteiro_ia_existe_em_utils():
    """validar_roteiro_ia deve estar disponível em utils."""
    from utils import validar_roteiro_ia as fn
    assert callable(fn)


def test_validar_roteiro_ia_assinatura():
    """validar_roteiro_ia deve aceitar dict e retornar tuple[bool, str]."""
    ok, msg = validar_roteiro_ia({})
    assert isinstance(ok, bool)
    assert isinstance(msg, str)


def test_generator_usa_validar_roteiro_ia():
    """generator_engine deve importar e usar validar_roteiro_ia."""
    import ast
    import pathlib
    src = pathlib.Path("generator_engine.py").read_text(encoding="utf-8")
    assert "validar_roteiro_ia" in src, "generator_engine.py não usa validar_roteiro_ia"
    # Verifica que o import está presente
    tree = ast.parse(src)
    imports_utils = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "utils"
    ]
    nomes_importados = [
        alias.name
        for imp in imports_utils
        for alias in imp.names
    ]
    assert "validar_roteiro_ia" in nomes_importados


# ──────────────────────────────────────────────────────────────
# UNIT TESTS — validator.py
# ──────────────────────────────────────────────────────────────

def test_e_acao_navegacao_menu():
    """Ação com 'menu' no label deve ser classificada como navegação."""
    acao = {"elemento_alvo": {"label_curto": "Menu principal", "seletor_hint": ""}}
    assert _e_acao_navegacao(acao) is True


def test_e_acao_navegacao_breadcrumb():
    """Ação com 'breadcrumb' no seletor deve ser classificada como navegação."""
    acao = {"elemento_alvo": {"label_curto": "Início", "seletor_hint": ".ui-breadcrumb"}}
    assert _e_acao_navegacao(acao) is True


def test_e_acao_nao_navegacao_salvar():
    """Ação 'Salvar' não deve ser classificada como navegação."""
    acao = {"elemento_alvo": {"label_curto": "Salvar", "seletor_hint": "[id='btn-salvar']"}}
    assert _e_acao_navegacao(acao) is False


def test_e_acao_nao_navegacao_campo():
    """Campo de formulário não deve ser classificado como navegação."""
    acao = {"elemento_alvo": {"label_curto": "Nome do cliente", "seletor_hint": "[name='nome']"}}
    assert _e_acao_navegacao(acao) is False


def test_e_acao_navegacao_elemento_alvo_ausente():
    """Ação sem elemento_alvo não deve lançar exceção."""
    acao = {}
    resultado = _e_acao_navegacao(acao)
    assert isinstance(resultado, bool)

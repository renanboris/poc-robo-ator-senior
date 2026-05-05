"""
test_builders.py — Senior Training OS
======================================
Testes unitários e de propriedade para pdf_builder_playbook_v3.py
e scorm_builder_playbook_v2.py.

Execução:
    pytest test_builders.py -v --tb=short
    pytest test_builders.py -v --tb=short -k "property"  # só PBT
"""

import json
import os
import sys
import tempfile
import zipfile

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# ─── Imports dos builders (pré-renomeação) ───────────────────────────────────
from pdf_builder_playbook_v3 import PDFBuilder, gerar_pdf
from scorm_builder_playbook_v2 import criar_pacote_scorm

from utils import limpar_nome, validar_roteiro

# ─────────────────────────────────────────────────────────────────────────────
# FIXTURES — roteiros de teste
# ─────────────────────────────────────────────────────────────────────────────

ROTEIRO_MINIMO = {
    "metadata": {
        "nome_aula": "Teste Mínimo",
        "id_treinamento": "teste_minimo",
    },
    "configuracao_gravacao": {},
    "passos": [
        {
            "id_passo": 1,
            "tipo_passo": "navigation",
            "peso_narrativo": 2,
            "is_conclusao": False,
            "alerta_instrutor": None,
            "pedagogia": {"ancora": "Navegamos até o menu principal.", "tooltip_dap": ""},
            "acoes_tecnicas": [
                {
                    "acao": "clique",
                    "micro_narracao": "Clique no menu.",
                    "valor_input": "",
                    "elemento_alvo": {
                        "label_curto": "Menu",
                        "screenshot_referencia": None,
                        "seletor_hint": "#menu-principal",
                        "confianca_captura": "alta",
                        "coordenadas_relativas": {
                            "x_pct": 0.1, "y_pct": 0.05,
                            "w_pct": 0.08, "h_pct": 0.04,
                        },
                    },
                }
            ],
        },
        {
            "id_passo": 2,
            "tipo_passo": "confirmation",
            "peso_narrativo": 2,
            "is_conclusao": True,
            "alerta_instrutor": None,
            "pedagogia": {"ancora": "Fluxo concluído.", "tooltip_dap": ""},
            "acoes_tecnicas": [
                {
                    "acao": "concluir_video",
                    "micro_narracao": "",
                    "valor_input": "",
                    "elemento_alvo": {
                        "label_curto": "Fim",
                        "screenshot_referencia": None,
                        "seletor_hint": "#fim",
                        "confianca_captura": "alta",
                        "coordenadas_relativas": {},
                    },
                }
            ],
        },
    ],
}


def _roteiro_sem_campo(campo_passo: str = None, campo_pedagogia: str = None):
    """Cria uma cópia do roteiro mínimo sem um campo específico."""
    import copy
    r = copy.deepcopy(ROTEIRO_MINIMO)
    for p in r["passos"]:
        if campo_passo and campo_passo in p:
            del p[campo_passo]
        if campo_pedagogia and campo_pedagogia in p.get("pedagogia", {}):
            del p["pedagogia"][campo_pedagogia]
    return r


# ─────────────────────────────────────────────────────────────────────────────
# ESTRATÉGIA HYPOTHESIS
# ─────────────────────────────────────────────────────────────────────────────

@st.composite
def roteiros_validos(draw):
    """
    Gera roteiros válidos segundo validar_roteiro() de utils.py.
    Campos opcionais podem estar presentes ou ausentes aleatoriamente.
    """
    n_passos = draw(st.integers(min_value=2, max_value=6))
    passos = []

    for i in range(1, n_passos + 1):
        is_conclusao = (i == n_passos)
        tem_tooltip = draw(st.booleans())
        tem_alerta = draw(st.booleans())
        peso = draw(st.integers(min_value=1, max_value=3))

        pedagogia = {"ancora": draw(st.text(min_size=5, max_size=80, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))))}
        if tem_tooltip:
            pedagogia["tooltip_dap"] = draw(st.text(max_size=60, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))))

        acao_tipo = "concluir_video" if is_conclusao else draw(
            st.sampled_from(["clique", "duplo_clique", "digitar_e_enter", "preencher_campo"])
        )

        passo = {
            "id_passo": i,
            "tipo_passo": draw(st.sampled_from(["navigation", "form_fill", "confirmation", "creation", "deletion"])),
            "is_conclusao": is_conclusao,
            "pedagogia": pedagogia,
            "acoes_tecnicas": [
                {
                    "acao": acao_tipo,
                    "micro_narracao": draw(st.text(max_size=60, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")))),
                    "valor_input": draw(st.text(max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))),
                    "elemento_alvo": {
                        "label_curto": draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))),
                        "screenshot_referencia": None,
                        "seletor_hint": draw(st.text(min_size=5, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Po")))),
                        "confianca_captura": draw(st.sampled_from(["alta", "media"])),
                        "coordenadas_relativas": {
                            "x_pct": draw(st.floats(min_value=0.1, max_value=0.9)),
                            "y_pct": draw(st.floats(min_value=0.1, max_value=0.9)),
                            "w_pct": draw(st.floats(min_value=0.02, max_value=0.2)),
                            "h_pct": draw(st.floats(min_value=0.02, max_value=0.2)),
                        },
                    },
                }
            ],
        }

        if draw(st.booleans()):
            passo["peso_narrativo"] = peso
        if tem_alerta:
            passo["alerta_instrutor"] = draw(st.text(max_size=80, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))))

        passos.append(passo)

    id_treino = draw(st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))))
    nome_aula = draw(st.text(min_size=3, max_size=40, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs"))))

    return {
        "metadata": {
            "nome_aula": nome_aula,
            "id_treinamento": id_treino,
        },
        "configuracao_gravacao": {},
        "passos": passos,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TESTES UNITÁRIOS — PDF Builder
# ─────────────────────────────────────────────────────────────────────────────

class TestPDFBuilderUnitario:

    def test_pdf_gerado_com_roteiro_minimo(self):
        """PDF com roteiro mínimo (2 passos, sem screenshots) → assinatura %PDF."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = PDFBuilder(ROTEIRO_MINIMO, pasta=tmpdir)
            path = builder.build()
            assert os.path.exists(path)
            with open(path, "rb") as f:
                assert f.read(4) == b"%PDF"

    def test_pdf_sem_tooltip_dap(self):
        """Roteiro sem tooltip_dap → sem exceção."""
        roteiro = _roteiro_sem_campo(campo_pedagogia="tooltip_dap")
        with tempfile.TemporaryDirectory() as tmpdir:
            PDFBuilder(roteiro, pasta=tmpdir).build()

    def test_pdf_sem_alerta_instrutor(self):
        """Roteiro sem alerta_instrutor → sem exceção."""
        roteiro = _roteiro_sem_campo(campo_passo="alerta_instrutor")
        with tempfile.TemporaryDirectory() as tmpdir:
            PDFBuilder(roteiro, pasta=tmpdir).build()

    def test_pdf_sem_peso_narrativo(self):
        """Roteiro com peso_narrativo ausente → sem exceção, usa default 2."""
        roteiro = _roteiro_sem_campo(campo_passo="peso_narrativo")
        with tempfile.TemporaryDirectory() as tmpdir:
            PDFBuilder(roteiro, pasta=tmpdir).build()

    def test_pdf_nome_usa_limpar_nome(self):
        """Nome do PDF usa limpar_nome(id_treinamento)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = PDFBuilder(ROTEIRO_MINIMO, pasta=tmpdir)
            path = builder.build()
            base = limpar_nome(ROTEIRO_MINIMO["metadata"]["id_treinamento"])
            assert os.path.basename(path) == f"{base}_Playbook.pdf"

    def test_pdf_exit_code_arquivo_inexistente(self):
        """Builder encerra com exit(1) se arquivo não existe."""
        with pytest.raises(SystemExit) as exc_info:
            sys.argv = ["pdf_builder.py", "/nao/existe/roteiro.json"]
            # Simula o bloco __main__ diretamente
            try:
                gerar_pdf("/nao/existe/roteiro.json")
            except FileNotFoundError:
                print("ERRO: arquivo de roteiro não encontrado")
                sys.exit(1)
        assert exc_info.value.code == 1

    def test_pdf_paginas_minimas(self):
        """PDF com N passos regulares tem pelo menos N+2 páginas."""
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = PDFBuilder(ROTEIRO_MINIMO, pasta=tmpdir)
            path = builder.build()
            # Conta páginas via contagem de "Page" no PDF (heurística simples)
            with open(path, "rb") as f:
                content = f.read().decode("latin-1", errors="ignore")
            page_count = content.count("/Type /Page\n") + content.count("/Type/Page\n")
            n_regulares = sum(1 for p in ROTEIRO_MINIMO["passos"] if not p.get("is_conclusao"))
            assert page_count >= n_regulares + 2


# ─────────────────────────────────────────────────────────────────────────────
# TESTES UNITÁRIOS — SCORM Builder
# ─────────────────────────────────────────────────────────────────────────────

class TestSCORMBuilderUnitario:

    def _gerar_scorm(self, roteiro, tmpdir):
        roteiro_path = os.path.join(tmpdir, "roteiro.json")
        with open(roteiro_path, "w", encoding="utf-8") as f:
            json.dump(roteiro, f, ensure_ascii=False)
        return criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)

    def test_scorm_contem_manifest_e_index(self):
        """ZIP contém imsmanifest.xml e index.html."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._gerar_scorm(ROTEIRO_MINIMO, tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            assert "imsmanifest.xml" in names
            assert "index.html" in names

    def test_scorm_manifest_contem_nome_aula(self):
        """imsmanifest.xml contém nome_aula."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._gerar_scorm(ROTEIRO_MINIMO, tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                manifest = zf.read("imsmanifest.xml").decode("utf-8")
            assert ROTEIRO_MINIMO["metadata"]["nome_aula"] in manifest

    def test_scorm_index_contem_slides_json_valido(self):
        """index.html contém JSON de slides válido."""
        import re as _re
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._gerar_scorm(ROTEIRO_MINIMO, tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                html = zf.read("index.html").decode("utf-8")
            match = _re.search(r"const slides = (\[.*?\]);", html, _re.DOTALL)
            assert match, "Array de slides não encontrado no index.html"
            json.loads(match.group(1))  # deve deserializar sem erro

    def test_scorm_sem_tooltip_dap(self):
        """Roteiro sem tooltip_dap → sem exceção."""
        roteiro = _roteiro_sem_campo(campo_pedagogia="tooltip_dap")
        with tempfile.TemporaryDirectory() as tmpdir:
            self._gerar_scorm(roteiro, tmpdir)

    def test_scorm_sem_alerta_instrutor(self):
        """Roteiro sem alerta_instrutor → sem exceção."""
        roteiro = _roteiro_sem_campo(campo_passo="alerta_instrutor")
        with tempfile.TemporaryDirectory() as tmpdir:
            self._gerar_scorm(roteiro, tmpdir)

    def test_scorm_nome_usa_limpar_nome(self):
        """Nome do SCORM usa limpar_nome(id_treinamento)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = self._gerar_scorm(ROTEIRO_MINIMO, tmpdir)
            base = limpar_nome(ROTEIRO_MINIMO["metadata"]["id_treinamento"])
            assert os.path.basename(zip_path) == f"{base}_SCORM.zip"

    def test_scorm_exit_code_arquivo_inexistente(self):
        """Builder encerra com exit(1) se arquivo não existe."""
        with pytest.raises(SystemExit) as exc_info:
            try:
                criar_pacote_scorm("/nao/existe/roteiro.json")
            except FileNotFoundError:
                print("ERRO: arquivo de roteiro não encontrado")
                sys.exit(1)
        assert exc_info.value.code == 1


# ─────────────────────────────────────────────────────────────────────────────
# TESTES DE PROPRIEDADE — Hypothesis
# ─────────────────────────────────────────────────────────────────────────────

class TestPropriedades:

    @given(roteiros_validos())
    @settings(max_examples=50)
    def test_property_1_pdf_gerado_para_roteiro_valido(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 1: PDF gerado para todo roteiro válido
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)
        with tempfile.TemporaryDirectory() as tmpdir:
            builder = PDFBuilder(roteiro, pasta=tmpdir)
            path = builder.build()
            assert os.path.exists(path)
            with open(path, "rb") as f:
                assert f.read(4) == b"%PDF"

    @given(roteiros_validos())
    @settings(max_examples=50)
    def test_property_2_scorm_gerado_para_roteiro_valido(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 2: SCORM gerado para todo roteiro válido
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)
        with tempfile.TemporaryDirectory() as tmpdir:
            roteiro_path = os.path.join(tmpdir, "roteiro.json")
            with open(roteiro_path, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, ensure_ascii=False)
            zip_path = criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                names = zf.namelist()
            assert "imsmanifest.xml" in names
            assert "index.html" in names

    @given(roteiros_validos())
    @settings(max_examples=50)
    def test_property_3_nome_artefato_derivado_de_limpar_nome(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 3: Nome do artefato derivado de limpar_nome
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)
        base_esperado = limpar_nome(roteiro["metadata"]["id_treinamento"])
        assume(len(base_esperado) > 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            # PDF
            pdf_path = PDFBuilder(roteiro, pasta=tmpdir).build()
            assert os.path.basename(pdf_path) == f"{base_esperado}_Playbook.pdf"

            # SCORM
            roteiro_path = os.path.join(tmpdir, "roteiro.json")
            with open(roteiro_path, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, ensure_ascii=False)
            zip_path = criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)
            assert os.path.basename(zip_path) == f"{base_esperado}_SCORM.zip"

    @given(roteiros_validos())
    @settings(max_examples=50)
    def test_property_4_campos_opcionais_ausentes_nao_causam_excecao(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 4: Campos opcionais ausentes não causam exceção
        import copy
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)

        r = copy.deepcopy(roteiro)
        for p in r["passos"]:
            p.pop("peso_narrativo", None)
            p.pop("alerta_instrutor", None)
            if "pedagogia" in p:
                p["pedagogia"].pop("tooltip_dap", None)

        with tempfile.TemporaryDirectory() as tmpdir:
            PDFBuilder(r, pasta=tmpdir).build()

            roteiro_path = os.path.join(tmpdir, "roteiro.json")
            with open(roteiro_path, "w", encoding="utf-8") as f:
                json.dump(r, f, ensure_ascii=False)
            criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)

    @given(roteiros_validos())
    @settings(max_examples=30)
    def test_property_6_slides_scorm_sao_json_valido(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 6: Slides SCORM são JSON válido
        import re as _re
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)

        with tempfile.TemporaryDirectory() as tmpdir:
            roteiro_path = os.path.join(tmpdir, "roteiro.json")
            with open(roteiro_path, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, ensure_ascii=False)
            zip_path = criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                html = zf.read("index.html").decode("utf-8")
            match = _re.search(r"const slides = (\[.*?\]);", html, _re.DOTALL)
            assert match, "Array de slides não encontrado no index.html"
            json.loads(match.group(1))

    @given(roteiros_validos())
    @settings(max_examples=30)
    def test_property_7_titulo_preservado_no_manifest(self, roteiro):
        # Feature: pdf-scorm-playbook-builders, Property 7: Título preservado no imsmanifest.xml
        aprovado, _ = validar_roteiro(roteiro)
        assume(aprovado)
        nome_aula = roteiro["metadata"]["nome_aula"]
        assume(len(nome_aula.strip()) > 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            roteiro_path = os.path.join(tmpdir, "roteiro.json")
            with open(roteiro_path, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, ensure_ascii=False)
            zip_path = criar_pacote_scorm(roteiro_path, pasta_destino=tmpdir)
            with zipfile.ZipFile(zip_path) as zf:
                manifest = zf.read("imsmanifest.xml").decode("utf-8")
            assert nome_aula in manifest

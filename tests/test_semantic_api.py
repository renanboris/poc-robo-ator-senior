"""
tests/test_semantic_api.py
===========================
Testes unitários para o endpoint GET /api/renderizacoes/{fluxo_id}
e para a propagação de atualizações no HITL.

Cobre:
  1. Endpoint retorna estrutura correta para fluxo existente
  2. Endpoint retorna 404 para fluxo inexistente
  3. renderizacoes reflete corretamente quais arquivos existem
  4. score_fluxo é calculado como média dos scores das ações

Requisitos: 3.1.1, 3.1.2, 3.1.3, 3.1.4
"""

import os
import sys
import json
import pytest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Pula graciosamente se fastapi não estiver instalado no ambiente de teste
pytest.importorskip("fastapi", reason="fastapi não instalado — testes de API semântica ignorados")

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as app_module
from app import app

client = TestClient(app, raise_server_exceptions=True)

# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _roteiro_minimo(id_treinamento: str, nome_aula: str, hitl_validado: bool = False) -> dict:
    return {
        "metadata": {
            "nome_aula": nome_aula,
            "id_treinamento": id_treinamento,
            "hitl_validado": hitl_validado,
            "ingestado_dap": False,
        },
        "configuracao_gravacao": {
            "gravar_video": False,
            "pasta_destino": "videos_gerados",
            "voz_ia": "pt-BR-FranciscaNeural",
        },
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo 1", "tooltip_dap": ""},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "clicar_botao_salvar",
                        "micro_narracao": "Clique em Salvar",
                        "elemento_alvo": {
                            "label_curto": "Salvar",
                            "seletor_hint": "button[data-action='save']",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "pedagogia": {"ancora": "Fim", "tooltip_dap": ""},
                "acoes_tecnicas": [],
            },
        ],
    }


# ──────────────────────────────────────────────────────────────
# Teste 1: Estrutura correta para fluxo existente
# ──────────────────────────────────────────────────────────────

def test_renderizacoes_estrutura_correta(tmp_path, monkeypatch):
    """
    Endpoint retorna estrutura JSON completa para fluxo existente.
    Requisitos: 3.1.1, 3.1.4
    """
    roteiros_dir = tmp_path / "roteiros_salvos"
    roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A01"
    roteiro = _roteiro_minimo(fluxo_id, "GED - Módulo 01 - Aula 01", hitl_validado=True)
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    with patch("score_engine.obter_score", return_value=None):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    data = resp.json()

    # Campos obrigatórios presentes
    assert "fluxo_id" in data
    assert "nome_aula" in data
    assert "renderizacoes" in data
    assert "hitl_validado" in data
    assert "score_fluxo" in data

    # Valores corretos
    assert data["fluxo_id"] == fluxo_id
    assert data["nome_aula"] == "GED - Módulo 01 - Aula 01"
    assert data["hitl_validado"] is True

    # Estrutura de renderizacoes
    renders = data["renderizacoes"]
    for chave in ("video", "scorm", "pdf", "simlink", "dap"):
        assert chave in renders, f"Chave '{chave}' ausente em renderizacoes"
        assert "disponivel" in renders[chave]
        assert "url" in renders[chave]


# ──────────────────────────────────────────────────────────────
# Teste 2: 404 para fluxo inexistente
# ──────────────────────────────────────────────────────────────

def test_renderizacoes_404_fluxo_inexistente(tmp_path, monkeypatch):
    """
    Endpoint retorna 404 quando o fluxo_id não corresponde a nenhum roteiro.
    Requisitos: 3.1.4
    """
    roteiros_dir = tmp_path / "roteiros_salvos"
    roteiros_dir.mkdir()

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))

    resp = client.get("/api/renderizacoes/FLUXO_INEXISTENTE_XYZ")
    assert resp.status_code == 404
    assert "erro" in resp.json()


# ──────────────────────────────────────────────────────────────
# Teste 3: renderizacoes reflete quais arquivos existem
# ──────────────────────────────────────────────────────────────

def test_renderizacoes_reflete_arquivos_existentes(tmp_path, monkeypatch):
    """
    renderizacoes.video.disponivel = True apenas quando o MP4 existe.
    renderizacoes.pdf.disponivel = True apenas quando o PDF existe.
    Outros artefatos ausentes devem ter disponivel=False e url=None.
    Requisitos: 3.1.1, 3.1.4
    """
    from utils import limpar_nome

    roteiros_dir = tmp_path / "roteiros_salvos"; roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A02"
    base = limpar_nome(fluxo_id)
    roteiro = _roteiro_minimo(fluxo_id, "GED - Módulo 01 - Aula 02")
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    # Cria apenas o MP4 e o PDF — SCORM, SimLink e DAP ausentes
    (videos_dir / f"{base}.mp4").write_bytes(b"fake_mp4")
    (pdf_dir / f"{base}_Playbook.pdf").write_bytes(b"fake_pdf")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    with patch("score_engine.obter_score", return_value=None):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    renders = resp.json()["renderizacoes"]

    # Presentes
    assert renders["video"]["disponivel"] is True
    assert renders["video"]["url"] is not None
    assert renders["pdf"]["disponivel"] is True
    assert renders["pdf"]["url"] is not None

    # Ausentes
    assert renders["scorm"]["disponivel"] is False
    assert renders["scorm"]["url"] is None
    assert renders["simlink"]["disponivel"] is False
    assert renders["simlink"]["url"] is None
    assert renders["dap"]["disponivel"] is False
    assert renders["dap"]["url"] is None


def test_renderizacoes_dap_disponivel_quando_ingestado(tmp_path, monkeypatch):
    """
    renderizacoes.dap.disponivel = True quando metadata.ingestado_dap = True.
    Requisitos: 3.1.1
    """
    roteiros_dir = tmp_path / "roteiros_salvos"; roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A03"
    roteiro = _roteiro_minimo(fluxo_id, "GED - Módulo 01 - Aula 03")
    roteiro["metadata"]["ingestado_dap"] = True
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    with patch("score_engine.obter_score", return_value=None):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    assert resp.json()["renderizacoes"]["dap"]["disponivel"] is True


# ──────────────────────────────────────────────────────────────
# Teste 4: score_fluxo calculado como média dos scores das ações
# ──────────────────────────────────────────────────────────────

def test_score_fluxo_media_dos_scores_das_acoes(tmp_path, monkeypatch):
    """
    score_fluxo deve ser a média dos scores das ações com intencao_semantica.
    Requisitos: 3.1.4, 3.2.2
    """
    roteiros_dir = tmp_path / "roteiros_salvos"; roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A04"
    roteiro = {
        "metadata": {
            "nome_aula": "GED - Módulo 01 - Aula 04",
            "id_treinamento": fluxo_id,
            "hitl_validado": False,
            "ingestado_dap": False,
        },
        "configuracao_gravacao": {
            "gravar_video": False,
            "pasta_destino": "videos_gerados",
            "voz_ia": "pt-BR-FranciscaNeural",
        },
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo 1", "tooltip_dap": ""},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "acao_a",
                        "elemento_alvo": {"seletor_hint": "#btn-a", "confianca_captura": "alta"},
                    },
                    {
                        "acao": "clique",
                        "intencao_semantica": "acao_b",
                        "elemento_alvo": {"seletor_hint": "#btn-b", "confianca_captura": "alta"},
                    },
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "pedagogia": {"ancora": "Fim", "tooltip_dap": ""},
                "acoes_tecnicas": [],
            },
        ],
    }
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    # Simula scores: acao_a=0.8, acao_b=0.6 → média=0.7
    scores_mock = {"acao_a": 0.8, "acao_b": 0.6}

    with patch("score_engine.obter_score", side_effect=lambda k, **kw: scores_mock.get(k)):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["score_fluxo"] is not None
    assert abs(data["score_fluxo"] - 0.7) < 1e-3, (
        f"score_fluxo esperado ~0.7, obtido {data['score_fluxo']}"
    )


def test_score_fluxo_null_sem_scores(tmp_path, monkeypatch):
    """
    score_fluxo deve ser null quando nenhuma ação tem score registrado.
    Requisitos: 3.1.4
    """
    roteiros_dir = tmp_path / "roteiros_salvos"; roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A05"
    roteiro = _roteiro_minimo(fluxo_id, "GED - Módulo 01 - Aula 05")
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    with patch("score_engine.obter_score", return_value=None):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    assert resp.json()["score_fluxo"] is None


def test_score_fluxo_null_sem_acoes_com_intencao(tmp_path, monkeypatch):
    """
    score_fluxo deve ser null quando as ações não têm intencao_semantica.
    Requisitos: 3.1.4
    """
    roteiros_dir = tmp_path / "roteiros_salvos"; roteiros_dir.mkdir()
    videos_dir   = tmp_path / "videos_prontos";  videos_dir.mkdir()
    scorm_dir    = tmp_path / "scorm_exports";   scorm_dir.mkdir()
    pdf_dir      = tmp_path / "documentacao_pdf"; pdf_dir.mkdir()
    sim_dir      = tmp_path / "sim_links";        sim_dir.mkdir()

    fluxo_id = "GED_M01_A06"
    roteiro = {
        "metadata": {
            "nome_aula": "GED - Módulo 01 - Aula 06",
            "id_treinamento": fluxo_id,
            "hitl_validado": False,
            "ingestado_dap": False,
        },
        "configuracao_gravacao": {
            "gravar_video": False,
            "pasta_destino": "videos_gerados",
            "voz_ia": "pt-BR-FranciscaNeural",
        },
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo 1", "tooltip_dap": ""},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "",  # sem intenção semântica
                        "elemento_alvo": {"seletor_hint": "#btn", "confianca_captura": "alta"},
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "pedagogia": {"ancora": "Fim", "tooltip_dap": ""},
                "acoes_tecnicas": [],
            },
        ],
    }
    (roteiros_dir / f"{fluxo_id}.json").write_text(json.dumps(roteiro), encoding="utf-8")

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR",   str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR",    str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR",      str(pdf_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    with patch("score_engine.obter_score", return_value=0.9):
        resp = client.get(f"/api/renderizacoes/{fluxo_id}")

    assert resp.status_code == 200
    assert resp.json()["score_fluxo"] is None

"""
tests/test_hitl_dashboard_integration.py
=========================================
Testes de integração: Dashboard API reporta status hitl_validado e
endpoint POST /api/marcar-hitl-validado marca o roteiro corretamente.

**Validates: Requirements 6.1, 6.3, 6.4**

Cobre:
  1. API /api/roteiros retorna hitl_validado=true para roteiro validado
  2. API /api/roteiros retorna hitl_validado=false para roteiro não validado
  3. POST /api/marcar-hitl-validado marca o arquivo com metadata correto
  4. POST /api/marcar-hitl-validado retorna 404 para arquivo inexistente
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("fastapi", reason="fastapi não instalado — testes de dashboard HITL ignorados")

from fastapi.testclient import TestClient

import app as app_module
from app import app

client = TestClient(app, raise_server_exceptions=True)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _roteiro_valido(nome_aula: str, hitl_validado: bool = False) -> dict:
    """Cria um roteiro mínimo que passa no validar_roteiro (>= 2 passos, >= 50% seletores)."""
    roteiro = {
        "metadata": {
            "nome_aula": nome_aula,
            "id_treinamento": nome_aula.replace(" ", "_"),
            "origem": "manual",
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
                            "seletor_hint": "button#salvar",
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
    if hitl_validado:
        roteiro["metadata"]["hitl_validado"] = True
        roteiro["metadata"]["hitl_validado_em"] = "2025-01-15T10:30:00"
    return roteiro


def _setup_dirs(tmp_path, monkeypatch):
    """Cria diretórios temporários e faz monkeypatch nos módulos do app."""
    roteiros_dir = tmp_path / "roteiros_salvos"
    roteiros_dir.mkdir()
    videos_dir = tmp_path / "videos_prontos"
    videos_dir.mkdir()
    scorm_dir = tmp_path / "scorm_exports"
    scorm_dir.mkdir()
    pdf_dir = tmp_path / "documentacao_pdf"
    pdf_dir.mkdir()
    audios_dir = tmp_path / "audios_gerados"
    audios_dir.mkdir()
    sim_dir = tmp_path / "sim_links"
    sim_dir.mkdir()

    monkeypatch.setattr(app_module, "ROTEIROS_DIR", str(roteiros_dir))
    monkeypatch.setattr(app_module, "VIDEOS_DIR", str(videos_dir))
    monkeypatch.setattr(app_module, "SCORM_DIR", str(scorm_dir))
    monkeypatch.setattr(app_module, "PDF_DIR", str(pdf_dir))
    monkeypatch.setattr(app_module, "AUDIOS_DIR", str(audios_dir))
    monkeypatch.setattr(app_module, "SIM_LINKS_DIR", str(sim_dir))

    return roteiros_dir


# ──────────────────────────────────────────────────────────────
# Teste 1: API retorna hitl_validado=true para roteiro validado
# ──────────────────────────────────────────────────────────────

def test_api_roteiros_retorna_hitl_validado_true(tmp_path, monkeypatch):
    """
    GET /api/roteiros retorna hitl_validado: true para roteiro com metadata.hitl_validado = true.
    Validates: Requirement 6.4
    """
    roteiros_dir = _setup_dirs(tmp_path, monkeypatch)

    roteiro = _roteiro_valido("Login Senior X", hitl_validado=True)
    (roteiros_dir / "Login_Senior_X.json").write_text(
        json.dumps(roteiro, ensure_ascii=False), encoding="utf-8"
    )

    resp = client.get("/api/roteiros")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    assert data[0]["hitl_validado"] is True


# ──────────────────────────────────────────────────────────────
# Teste 2: API retorna hitl_validado=false para roteiro não validado
# ──────────────────────────────────────────────────────────────

def test_api_roteiros_retorna_hitl_validado_false(tmp_path, monkeypatch):
    """
    GET /api/roteiros retorna hitl_validado: false para roteiro sem o campo.
    Validates: Requirement 6.1
    """
    roteiros_dir = _setup_dirs(tmp_path, monkeypatch)

    roteiro = _roteiro_valido("Cadastro Fornecedor", hitl_validado=False)
    (roteiros_dir / "Cadastro_Fornecedor.json").write_text(
        json.dumps(roteiro, ensure_ascii=False), encoding="utf-8"
    )

    resp = client.get("/api/roteiros")
    assert resp.status_code == 200

    data = resp.json()
    assert len(data) == 1
    assert data[0]["hitl_validado"] is False


# ──────────────────────────────────────────────────────────────
# Teste 3: POST /api/marcar-hitl-validado marca o arquivo
# ──────────────────────────────────────────────────────────────

def test_marcar_hitl_validado_marca_arquivo(tmp_path, monkeypatch):
    """
    POST /api/marcar-hitl-validado/{arquivo} marca metadata.hitl_validado = true
    e metadata.hitl_validado_em é preenchido com timestamp ISO.
    Validates: Requirement 6.3
    """
    roteiros_dir = _setup_dirs(tmp_path, monkeypatch)

    nome_arquivo = "Fluxo_Financeiro.json"
    roteiro = _roteiro_valido("Fluxo Financeiro", hitl_validado=False)
    caminho = roteiros_dir / nome_arquivo
    caminho.write_text(json.dumps(roteiro, ensure_ascii=False), encoding="utf-8")

    # Mock lego_builder.construir_biblioteca para não executar rebuild real
    from unittest.mock import patch
    with patch("lego_builder.construir_biblioteca", return_value={"status": "sucesso", "total_acoes_novas": 0, "total_acoes_lidas": 0}):
        resp = client.post(f"/api/marcar-hitl-validado/{nome_arquivo}")

    assert resp.status_code == 200

    # Verifica que o arquivo foi atualizado
    with open(str(caminho), "r", encoding="utf-8") as f:
        dados_atualizados = json.load(f)

    assert dados_atualizados["metadata"]["hitl_validado"] is True
    assert "hitl_validado_em" in dados_atualizados["metadata"]
    # Verifica que hitl_validado_em é um timestamp ISO válido
    ts = dados_atualizados["metadata"]["hitl_validado_em"]
    assert len(ts) > 10  # formato ISO mínimo: "2025-01-15T..."
    assert "T" in ts


# ──────────────────────────────────────────────────────────────
# Teste 4: POST /api/marcar-hitl-validado retorna 404 para arquivo inexistente
# ──────────────────────────────────────────────────────────────

def test_marcar_hitl_validado_404_arquivo_inexistente(tmp_path, monkeypatch):
    """
    POST /api/marcar-hitl-validado/{arquivo} retorna 404 quando o arquivo não existe.
    Validates: Requirement 6.3
    """
    roteiros_dir = _setup_dirs(tmp_path, monkeypatch)

    resp = client.post("/api/marcar-hitl-validado/roteiro_fantasma_xyz.json")
    assert resp.status_code == 404

    data = resp.json()
    assert "erro" in data

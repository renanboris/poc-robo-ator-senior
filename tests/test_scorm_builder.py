"""
tests/test_scorm_builder.py — Testes de regressão para scorm_builder.py
Requisitos: 1.3.5
"""
import json
import os
import zipfile

import pytest

scorm_builder = pytest.importorskip(
    "scorm_builder",
    reason="scorm_builder não disponível ou dependência ausente",
)

ROTEIRO_REFERENCIA = {
    "metadata": {
        "nome_aula": "Teste Regressão",
        "id_treinamento": "Teste_Regressao",
        "gerado_por_ia": False,
        "hitl_validado": True,
    },
    "configuracao_gravacao": {
        "gravar_video": True,
        "pasta_destino": "videos_gerados",
        "voz_ia": "pt-BR-FranciscaNeural",
    },
    "passos": [
        {
            "id_passo": 1,
            "tipo_passo": "operacao",
            "peso_narrativo": 2,
            "pause_sugerida": 2.5,
            "pedagogia": {"ancora": "Clique no menu principal", "tooltip_dap": "Menu"},
            "is_conclusao": False,
            "acoes_tecnicas": [
                {
                    "acao": "clique",
                    "intencao_semantica": "Acessar menu principal",
                    "micro_narracao": "Clique no menu",
                    "elemento_alvo": {
                        "label_curto": "Menu",
                        "seletor_hint": "[aria-label='Menu principal']",
                        "confianca_captura": "alta",
                    },
                }
            ],
        },
        {
            "id_passo": 2,
            "tipo_passo": "confirmation",
            "peso_narrativo": 3,
            "pause_sugerida": 3.0,
            "pedagogia": {"ancora": "Concluído!", "tooltip_dap": "Fim"},
            "is_conclusao": True,
            "acoes_tecnicas": [{"acao": "concluir_video"}],
        },
    ],
}


@pytest.fixture
def roteiro_json(tmp_path):
    """Cria um arquivo JSON de roteiro de referência em diretório temporário."""
    caminho = str(tmp_path / "roteiro_teste.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(ROTEIRO_REFERENCIA, f, ensure_ascii=False)
    return caminho


def test_criar_pacote_scorm_sem_erro(roteiro_json, tmp_path):
    """Geração de SCORM para roteiro de referência deve concluir sem exceção."""
    pasta_destino = str(tmp_path / "scorm_exports")
    resultado = scorm_builder.criar_pacote_scorm(roteiro_json, pasta_destino=pasta_destino)
    assert resultado is not None


def test_criar_pacote_scorm_gera_arquivo_zip(roteiro_json, tmp_path):
    """O arquivo gerado deve ser um ZIP válido."""
    pasta_destino = str(tmp_path / "scorm_exports")
    caminho_zip = scorm_builder.criar_pacote_scorm(roteiro_json, pasta_destino=pasta_destino)

    assert os.path.exists(caminho_zip), f"Arquivo ZIP não encontrado: {caminho_zip}"
    assert caminho_zip.endswith(".zip")
    assert zipfile.is_zipfile(caminho_zip)


def test_criar_pacote_scorm_contem_imsmanifest(roteiro_json, tmp_path):
    """O ZIP deve conter o arquivo imsmanifest.xml obrigatório do SCORM 1.2."""
    pasta_destino = str(tmp_path / "scorm_exports")
    caminho_zip = scorm_builder.criar_pacote_scorm(roteiro_json, pasta_destino=pasta_destino)

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        nomes = zf.namelist()

    assert "imsmanifest.xml" in nomes


def test_criar_pacote_scorm_contem_index_html(roteiro_json, tmp_path):
    """O ZIP deve conter o arquivo index.html (player SCORM)."""
    pasta_destino = str(tmp_path / "scorm_exports")
    caminho_zip = scorm_builder.criar_pacote_scorm(roteiro_json, pasta_destino=pasta_destino)

    with zipfile.ZipFile(caminho_zip, "r") as zf:
        nomes = zf.namelist()

    assert "index.html" in nomes


def test_criar_pacote_scorm_nome_baseado_em_id_treinamento(roteiro_json, tmp_path):
    """O nome do arquivo ZIP deve ser derivado do id_treinamento do roteiro."""
    pasta_destino = str(tmp_path / "scorm_exports")
    caminho_zip = scorm_builder.criar_pacote_scorm(roteiro_json, pasta_destino=pasta_destino)

    nome_arquivo = os.path.basename(caminho_zip)
    assert "Teste_Regressao" in nome_arquivo


def test_criar_pacote_scorm_independente_entre_chamadas(tmp_path):
    """Duas chamadas independentes com roteiros diferentes não devem interferir entre si."""
    roteiro_a = {
        "metadata": {"nome_aula": "Aula A", "id_treinamento": "Aula_A"},
        "configuracao_gravacao": {},
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo A"},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "Ação A",
                        "elemento_alvo": {"label_curto": "Botão A"},
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "acoes_tecnicas": [{"acao": "concluir_video"}],
            },
        ],
    }
    roteiro_b = {
        "metadata": {"nome_aula": "Aula B", "id_treinamento": "Aula_B"},
        "configuracao_gravacao": {},
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "pedagogia": {"ancora": "Passo B"},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "Ação B",
                        "elemento_alvo": {"label_curto": "Botão B"},
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "acoes_tecnicas": [{"acao": "concluir_video"}],
            },
        ],
    }

    pasta = str(tmp_path / "scorm_exports")

    caminho_a = str(tmp_path / "roteiro_a.json")
    caminho_b = str(tmp_path / "roteiro_b.json")
    with open(caminho_a, "w", encoding="utf-8") as f:
        json.dump(roteiro_a, f)
    with open(caminho_b, "w", encoding="utf-8") as f:
        json.dump(roteiro_b, f)

    zip_a = scorm_builder.criar_pacote_scorm(caminho_a, pasta_destino=pasta)
    zip_b = scorm_builder.criar_pacote_scorm(caminho_b, pasta_destino=pasta)

    assert os.path.exists(zip_a)
    assert os.path.exists(zip_b)
    assert zip_a != zip_b

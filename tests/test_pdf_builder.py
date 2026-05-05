"""
tests/test_pdf_builder.py — Testes de regressão para pdf_builder.py
Requisitos: 1.3.5
"""
import json
import os

import pytest

reportlab = pytest.importorskip(
    "reportlab",
    reason="reportlab não instalado — testes de PDF ignorados",
)
PIL = pytest.importorskip(
    "PIL",
    reason="Pillow não instalado — testes de PDF ignorados",
)

from pdf_builder import PDFBuilder

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


def test_pdf_builder_gera_arquivo_sem_erro(tmp_path):
    """PDFBuilder deve gerar o arquivo PDF sem lançar exceção."""
    pasta = str(tmp_path / "documentacao_pdf")
    builder = PDFBuilder(ROTEIRO_REFERENCIA, pasta=pasta)
    builder.build()

    assert os.path.exists(builder.out_path), f"PDF não gerado em: {builder.out_path}"


def test_pdf_builder_arquivo_nao_vazio(tmp_path):
    """O arquivo PDF gerado não deve estar vazio."""
    pasta = str(tmp_path / "documentacao_pdf")
    builder = PDFBuilder(ROTEIRO_REFERENCIA, pasta=pasta)
    builder.build()

    tamanho = os.path.getsize(builder.out_path)
    assert tamanho > 0, "PDF gerado está vazio"


def test_pdf_builder_nome_baseado_em_id_treinamento(tmp_path):
    """O nome do PDF deve ser derivado do id_treinamento do roteiro."""
    pasta = str(tmp_path / "documentacao_pdf")
    builder = PDFBuilder(ROTEIRO_REFERENCIA, pasta=pasta)
    builder.build()

    nome_arquivo = os.path.basename(builder.out_path)
    assert "Teste_Regressao" in nome_arquivo
    assert nome_arquivo.endswith(".pdf")


def test_pdf_builder_cria_pasta_destino(tmp_path):
    """PDFBuilder deve criar a pasta de destino se não existir."""
    pasta = str(tmp_path / "nova_pasta" / "documentacao_pdf")
    assert not os.path.exists(pasta)

    builder = PDFBuilder(ROTEIRO_REFERENCIA, pasta=pasta)
    builder.build()

    assert os.path.isdir(pasta)


def test_pdf_builder_roteiro_multiplos_passos(tmp_path):
    """PDFBuilder deve processar roteiro com múltiplos passos sem erro."""
    roteiro = {
        "metadata": {
            "nome_aula": "Aula Multi-Passo",
            "id_treinamento": "Aula_Multi_Passo",
        },
        "configuracao_gravacao": {},
        "passos": [
            {
                "id_passo": i,
                "tipo_passo": "operacao",
                "peso_narrativo": 2,
                "pause_sugerida": 2.0,
                "pedagogia": {"ancora": f"Passo {i}", "tooltip_dap": f"Dica {i}"},
                "is_conclusao": False,
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": f"Ação do passo {i}",
                        "micro_narracao": f"Clique no elemento {i}",
                        "elemento_alvo": {
                            "label_curto": f"Elemento {i}",
                            "seletor_hint": f"[data-testid='elem-{i}']",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            }
            for i in range(1, 5)
        ] + [
            {
                "id_passo": 5,
                "tipo_passo": "confirmation",
                "peso_narrativo": 3,
                "pause_sugerida": 3.0,
                "pedagogia": {"ancora": "Concluído!", "tooltip_dap": "Fim"},
                "is_conclusao": True,
                "acoes_tecnicas": [{"acao": "concluir_video"}],
            }
        ],
    }

    pasta = str(tmp_path / "documentacao_pdf")
    builder = PDFBuilder(roteiro, pasta=pasta)
    builder.build()

    assert os.path.exists(builder.out_path)
    assert os.path.getsize(builder.out_path) > 0


def test_pdf_builder_independente_entre_chamadas(tmp_path):
    """Duas instâncias independentes não devem compartilhar estado."""
    roteiro_a = {
        "metadata": {"nome_aula": "Aula A", "id_treinamento": "Aula_A"},
        "configuracao_gravacao": {},
        "passos": [
            {
                "id_passo": 1,
                "tipo_passo": "operacao",
                "peso_narrativo": 2,
                "pause_sugerida": 2.0,
                "pedagogia": {"ancora": "Passo A", "tooltip_dap": ""},
                "is_conclusao": False,
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
                "tipo_passo": "confirmation",
                "peso_narrativo": 3,
                "pause_sugerida": 3.0,
                "pedagogia": {"ancora": "Fim A", "tooltip_dap": ""},
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
                "tipo_passo": "operacao",
                "peso_narrativo": 2,
                "pause_sugerida": 2.0,
                "pedagogia": {"ancora": "Passo B", "tooltip_dap": ""},
                "is_conclusao": False,
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
                "tipo_passo": "confirmation",
                "peso_narrativo": 3,
                "pause_sugerida": 3.0,
                "pedagogia": {"ancora": "Fim B", "tooltip_dap": ""},
                "is_conclusao": True,
                "acoes_tecnicas": [{"acao": "concluir_video"}],
            },
        ],
    }

    pasta = str(tmp_path / "documentacao_pdf")
    builder_a = PDFBuilder(roteiro_a, pasta=pasta)
    builder_b = PDFBuilder(roteiro_b, pasta=pasta)

    builder_a.build()
    builder_b.build()

    assert os.path.exists(builder_a.out_path)
    assert os.path.exists(builder_b.out_path)
    assert builder_a.out_path != builder_b.out_path

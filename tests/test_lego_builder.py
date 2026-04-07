"""
tests/test_lego_builder.py — Testes de regressão para lego_builder.py
Requisitos: 1.3.4
"""
import json
import os
import pytest

from lego_builder import construir_biblioteca


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


def _escrever_roteiro(pasta: str, nome: str, roteiro: dict) -> str:
    caminho = os.path.join(pasta, nome)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(roteiro, f, ensure_ascii=False)
    return caminho


def test_construir_biblioteca_retorna_sucesso(tmp_path):
    """Rebuild com roteiro válido deve retornar status 'sucesso'."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)
    _escrever_roteiro(roteiros_dir, "roteiro_teste.json", ROTEIRO_REFERENCIA)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    resultado = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    assert resultado["status"] == "sucesso"


def test_construir_biblioteca_extrai_intencao_semantica(tmp_path):
    """Ações com intencao_semantica devem ser extraídas para a biblioteca."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)
    _escrever_roteiro(roteiros_dir, "roteiro_teste.json", ROTEIRO_REFERENCIA)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    resultado = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    assert resultado["total_acoes_novas"] >= 1

    with open(biblioteca_file, "r", encoding="utf-8") as f:
        biblioteca = json.load(f)

    assert "acessar menu principal" in biblioteca


def test_construir_biblioteca_ignora_concluir_video(tmp_path):
    """Ações 'concluir_video' não devem ser incluídas na biblioteca."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)
    _escrever_roteiro(roteiros_dir, "roteiro_teste.json", ROTEIRO_REFERENCIA)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    with open(biblioteca_file, "r", encoding="utf-8") as f:
        biblioteca = json.load(f)

    for chave, acao in biblioteca.items():
        assert acao.get("acao") != "concluir_video", (
            f"concluir_video não deve estar na biblioteca (chave: {chave})"
        )


def test_construir_biblioteca_sem_roteiros_retorna_erro(tmp_path):
    """Pasta vazia deve retornar status 'erro'."""
    roteiros_dir = str(tmp_path / "roteiros_vazios")
    os.makedirs(roteiros_dir)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    resultado = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    assert resultado["status"] == "erro"


def test_construir_biblioteca_pasta_inexistente_retorna_erro(tmp_path):
    """Pasta inexistente deve retornar status 'erro'."""
    resultado = construir_biblioteca(
        roteiros_dir=str(tmp_path / "nao_existe"),
        biblioteca_file=str(tmp_path / "biblioteca.json"),
    )
    assert resultado["status"] == "erro"


def test_construir_biblioteca_idempotente(tmp_path):
    """Executar rebuild duas vezes sobre os mesmos roteiros deve produzir o mesmo resultado."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)
    _escrever_roteiro(roteiros_dir, "roteiro_teste.json", ROTEIRO_REFERENCIA)

    biblioteca_file = str(tmp_path / "biblioteca.json")

    resultado1 = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)
    with open(biblioteca_file, "r", encoding="utf-8") as f:
        biblioteca1 = json.load(f)

    resultado2 = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)
    with open(biblioteca_file, "r", encoding="utf-8") as f:
        biblioteca2 = json.load(f)

    assert resultado1["total_acoes_novas"] == resultado2["total_acoes_novas"]
    assert biblioteca1 == biblioteca2


def test_construir_biblioteca_adiciona_source(tmp_path):
    """Cada ação na biblioteca deve ter o campo _source com o nome do arquivo de origem."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)
    _escrever_roteiro(roteiros_dir, "roteiro_teste.json", ROTEIRO_REFERENCIA)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    with open(biblioteca_file, "r", encoding="utf-8") as f:
        biblioteca = json.load(f)

    for chave, acao in biblioteca.items():
        assert "_source" in acao, f"Ação '{chave}' não tem campo _source"


def test_construir_biblioteca_multiplos_roteiros(tmp_path):
    """Múltiplos roteiros devem ser processados e suas ações unificadas."""
    roteiros_dir = str(tmp_path / "roteiros")
    os.makedirs(roteiros_dir)

    roteiro2 = {
        "metadata": {"nome_aula": "Teste 2", "id_treinamento": "Teste_2"},
        "configuracao_gravacao": {},
        "passos": [
            {
                "id_passo": 1,
                "is_conclusao": False,
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "Abrir relatório financeiro",
                        "elemento_alvo": {"label_curto": "Relatório"},
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

    _escrever_roteiro(roteiros_dir, "roteiro_a.json", ROTEIRO_REFERENCIA)
    _escrever_roteiro(roteiros_dir, "roteiro_b.json", roteiro2)

    biblioteca_file = str(tmp_path / "biblioteca.json")
    resultado = construir_biblioteca(roteiros_dir=roteiros_dir, biblioteca_file=biblioteca_file)

    assert resultado["total_roteiros"] == 2
    assert resultado["total_acoes_novas"] >= 2

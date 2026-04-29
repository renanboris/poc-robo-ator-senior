"""
tests/test_generator_engine.py — Testes de regressão para generator_engine.py
Requisitos: 1.3.3

Testa apenas _validar_estrutura_roteiro() — sem chamar a API Gemini.
"""
import pytest

from generator_engine import _validar_estrutura_roteiro


def test_estrutura_valida_retorna_none():
    """Roteiro com metadata e passos preenchidos deve passar na validação."""
    roteiro = {
        "metadata": {"nome_aula": "Teste"},
        "passos": [{"id_passo": 1}],
    }
    assert _validar_estrutura_roteiro(roteiro) is None


def test_ausencia_metadata_retorna_erro():
    """Roteiro sem campo 'metadata' deve retornar mensagem de erro."""
    roteiro = {"passos": [{"id_passo": 1}]}
    resultado = _validar_estrutura_roteiro(roteiro)
    assert resultado is not None
    assert "metadata" in resultado.lower()


def test_ausencia_passos_retorna_erro():
    """Roteiro sem campo 'passos' deve retornar mensagem de erro."""
    roteiro = {"metadata": {"nome_aula": "Teste"}}
    resultado = _validar_estrutura_roteiro(roteiro)
    assert resultado is not None
    assert "passos" in resultado.lower()


def test_passos_lista_vazia_retorna_erro():
    """Roteiro com 'passos' como lista vazia deve retornar mensagem de erro."""
    roteiro = {"metadata": {"nome_aula": "Teste"}, "passos": []}
    resultado = _validar_estrutura_roteiro(roteiro)
    assert resultado is not None


def test_passos_nao_lista_retorna_erro():
    """Roteiro com 'passos' não sendo lista deve retornar mensagem de erro."""
    roteiro = {"metadata": {"nome_aula": "Teste"}, "passos": "nao_e_lista"}
    resultado = _validar_estrutura_roteiro(roteiro)
    assert resultado is not None


def test_entrada_nao_dict_retorna_erro():
    """Entrada que não é dicionário deve retornar mensagem de erro."""
    assert _validar_estrutura_roteiro("string") is not None
    assert _validar_estrutura_roteiro(None) is not None
    assert _validar_estrutura_roteiro([]) is not None
    assert _validar_estrutura_roteiro(42) is not None


def test_roteiro_completo_com_configuracao_gravacao_retorna_none():
    """Roteiro completo com todos os campos obrigatórios deve passar."""
    roteiro = {
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
                "is_conclusao": False,
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "Acessar menu principal",
                        "elemento_alvo": {
                            "label_curto": "Menu",
                            "seletor_hint": "[aria-label='Menu principal']",
                        },
                    }
                ],
            },
            {
                "id_passo": 2,
                "tipo_passo": "confirmation",
                "is_conclusao": True,
                "acoes_tecnicas": [{"acao": "concluir_video"}],
            },
        ],
    }
    assert _validar_estrutura_roteiro(roteiro) is None


def test_campos_extras_nao_causam_erro():
    """Campos desconhecidos no roteiro não devem causar erro na validação estrutural."""
    roteiro = {
        "metadata": {"nome_aula": "Teste"},
        "passos": [{"id_passo": 1}],
        "campo_desconhecido": "valor_qualquer",
        "outro_campo": 123,
    }
    assert _validar_estrutura_roteiro(roteiro) is None

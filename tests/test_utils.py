"""
Testes unitários para o módulo utils.py

Cobre as funções:
- limpar_nome()
- validar_roteiro()
- safe_write_json()
- safe_resolve_path()
- com_retry()

Executa sem dependências externas além de pytest e stdlib.
"""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest

from utils import (
    limpar_nome,
    validar_roteiro,
    safe_write_json,
    safe_resolve_path,
    com_retry,
)


# ============================================================================
# TESTES PARA limpar_nome()
# ============================================================================


class TestLimparNome:
    """Testes para a função limpar_nome()."""

    def test_remove_acentos(self):
        """Verifica remoção de acentos."""
        assert limpar_nome("Criação") == "Criacao"
        assert limpar_nome("Ação") == "Acao"
        assert limpar_nome("Café") == "Cafe"
        assert limpar_nome("Pão") == "Pao"

    def test_remove_caracteres_proibidos(self):
        """Verifica remoção de caracteres proibidos do SO."""
        assert limpar_nome("GED: M01/A01") == "GED_M01A01"
        assert limpar_nome("Arquivo<teste>") == "Arquivoteste"
        assert limpar_nome("Nome*com?caracteres") == "Nomecomcaracteres"
        assert limpar_nome('Aspas"duplas') == "Aspasduplas"
        assert limpar_nome("Pipe|teste") == "Pipeteste"
        assert limpar_nome("Barra\\invertida") == "Barrainvertida"

    def test_espacos_para_underscore(self):
        """Verifica conversão de espaços em underscores."""
        assert limpar_nome("Criação de Pasta") == "Criacao_de_Pasta"
        assert limpar_nome("Nome com vários espaços") == "Nome_com_varios_espacos"
        assert limpar_nome("  Espaços nas extremidades  ") == "Espacos_nas_extremidades"

    def test_limite_40_caracteres(self):
        """Verifica limite de 40 caracteres."""
        nome_longo = "A" * 50
        resultado = limpar_nome(nome_longo)
        assert len(resultado) <= 40
        assert resultado == "A" * 40

    def test_sem_underscore_nas_extremidades(self):
        """Verifica que não há underscores nas extremidades."""
        assert not limpar_nome("_teste_").startswith("_")
        assert not limpar_nome("_teste_").endswith("_")
        assert limpar_nome("_teste_") == "teste"

    def test_combinacao_acentos_caracteres_proibidos(self):
        """Verifica combinação de acentos e caracteres proibidos."""
        assert limpar_nome("GED: M01/A01 <Setup>") == "GED_M01A01_Setup"
        assert limpar_nome("Ação/Reação*Teste") == "AcaoReacaoTeste"

    def test_string_vazia(self):
        """Verifica comportamento com string vazia."""
        resultado = limpar_nome("")
        assert resultado == ""

    def test_apenas_caracteres_proibidos(self):
        """Verifica string contendo apenas caracteres proibidos."""
        resultado = limpar_nome("/*?:<>|\\")
        assert resultado == ""

    def test_idempotencia(self):
        """Verifica que aplicar duas vezes produz o mesmo resultado."""
        nome = "Criação de Pasta com Acentos"
        primeira = limpar_nome(nome)
        segunda = limpar_nome(primeira)
        assert primeira == segunda


# ============================================================================
# TESTES PARA validar_roteiro()
# ============================================================================


class TestValidarRoteiro:
    """Testes para a função validar_roteiro()."""

    @pytest.fixture
    def roteiro_valido(self):
        """Roteiro válido com 2 passos e ações com seletor."""
        return {
            "passos": [
                {
                    "id_passo": 1,
                    "acoes_tecnicas": [
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "[aria-label='Salvar']",
                                "confianca_captura": "alta",
                            },
                        },
                        {
                            "acao": "preencher_campo",
                            "elemento_alvo": {
                                "seletor_hint": "input[name='email']",
                                "confianca_captura": "media",
                            },
                        },
                    ],
                },
                {
                    "id_passo": 2,
                    "is_conclusao": True,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
            ]
        }

    def test_roteiro_valido(self, roteiro_valido):
        """Verifica aprovação de roteiro válido."""
        aprovado, motivo = validar_roteiro(roteiro_valido)
        assert aprovado is True
        assert "OK" in motivo

    def test_menos_de_2_passos(self):
        """Verifica reprovação com menos de 2 passos."""
        roteiro = {"passos": [{"id_passo": 1, "acoes_tecnicas": []}]}
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False
        assert "1 passo" in motivo

    def test_zero_passos(self):
        """Verifica reprovação com zero passos."""
        roteiro = {"passos": []}
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False
        assert "0 passo" in motivo

    def test_menos_de_50_pct_seletores(self):
        """Verifica reprovação com menos de 50% de seletores preenchidos."""
        roteiro = {
            "passos": [
                {
                    "id_passo": 1,
                    "acoes_tecnicas": [
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "[aria-label='Salvar']",
                                "confianca_captura": "alta",
                            },
                        },
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "",  # Sem seletor
                                "confianca_captura": "alta",
                            },
                        },
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "",  # Sem seletor
                                "confianca_captura": "alta",
                            },
                        },
                    ],
                },
                {
                    "id_passo": 2,
                    "is_conclusao": True,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
            ]
        }
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False
        assert "seletor CSS" in motivo

    def test_mais_de_70_pct_baixa_confianca(self):
        """Verifica reprovação com mais de 70% de confiança baixa."""
        roteiro = {
            "passos": [
                {
                    "id_passo": 1,
                    "acoes_tecnicas": [
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "[aria-label='Salvar']",
                                "confianca_captura": "baixa",
                            },
                        },
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "button",
                                "confianca_captura": "baixa",
                            },
                        },
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "div",
                                "confianca_captura": "baixa",
                            },
                        },
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "span",
                                "confianca_captura": "alta",
                            },
                        },
                    ],
                },
                {
                    "id_passo": 2,
                    "is_conclusao": True,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
            ]
        }
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False
        assert "confiança baixa" in motivo

    def test_ignora_acao_concluir_video(self):
        """Verifica que ações 'concluir_video' são ignoradas nos cálculos."""
        roteiro = {
            "passos": [
                {
                    "id_passo": 1,
                    "acoes_tecnicas": [
                        {
                            "acao": "clique",
                            "elemento_alvo": {
                                "seletor_hint": "[aria-label='Salvar']",
                                "confianca_captura": "alta",
                            },
                        },
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        },
                    ],
                },
                {
                    "id_passo": 2,
                    "is_conclusao": True,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
            ]
        }
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is True

    def test_nenhuma_acao_tecnica_valida(self):
        """Verifica reprovação quando não há ações técnicas válidas."""
        roteiro = {
            "passos": [
                {
                    "id_passo": 1,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
                {
                    "id_passo": 2,
                    "is_conclusao": True,
                    "acoes_tecnicas": [
                        {
                            "acao": "concluir_video",
                            "elemento_alvo": {},
                        }
                    ],
                },
            ]
        }
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False
        assert "nenhuma ação técnica" in motivo.lower()

    def test_roteiro_malformado_sem_passos(self):
        """Verifica comportamento com roteiro sem chave 'passos'."""
        roteiro = {}
        aprovado, motivo = validar_roteiro(roteiro)
        assert aprovado is False

    def test_roteiro_malformado_passos_nao_lista(self):
        """Verifica que lança AttributeError quando 'passos' não é lista."""
        roteiro = {"passos": "não é lista"}
        # A função não trata esse caso especial — lança AttributeError
        with pytest.raises(AttributeError):
            validar_roteiro(roteiro)


# ============================================================================
# TESTES PARA safe_write_json()
# ============================================================================


class TestSafeWriteJson:
    """Testes para a função safe_write_json()."""

    def test_cria_arquivo_com_conteudo_correto(self, tmp_path):
        """Verifica que o arquivo é criado com conteúdo correto."""
        caminho = tmp_path / "teste.json"
        dados = {"chave": "valor", "numero": 42}
        safe_write_json(str(caminho), dados)

        assert caminho.exists()
        with open(caminho, "r") as f:
            conteudo = json.load(f)
        assert conteudo == dados

    def test_cria_diretorio_automaticamente(self, tmp_path):
        """Verifica que o diretório é criado automaticamente."""
        caminho = tmp_path / "subdir" / "outro" / "teste.json"
        dados = {"teste": "dados"}
        safe_write_json(str(caminho), dados)

        assert caminho.exists()
        with open(caminho, "r") as f:
            conteudo = json.load(f)
        assert conteudo == dados

    def test_sem_arquivo_temporario_residual(self, tmp_path):
        """Verifica que não há arquivo .json.tmp residual após sucesso."""
        caminho = tmp_path / "teste.json"
        dados = {"teste": "dados"}
        safe_write_json(str(caminho), dados)

        # Verifica que não há arquivo temporário
        tmp_files = list(tmp_path.glob("*.json.tmp"))
        assert len(tmp_files) == 0

    def test_sobrescreve_arquivo_existente(self, tmp_path):
        """Verifica que sobrescreve arquivo existente atomicamente."""
        caminho = tmp_path / "teste.json"
        dados_antigos = {"antigo": "valor"}
        dados_novos = {"novo": "valor"}

        safe_write_json(str(caminho), dados_antigos)
        safe_write_json(str(caminho), dados_novos)

        with open(caminho, "r") as f:
            conteudo = json.load(f)
        assert conteudo == dados_novos

    def test_falha_com_dados_nao_serializaveis(self, tmp_path):
        """Verifica que lança exceção com dados não-JSON."""
        caminho = tmp_path / "teste.json"
        dados = {"funcao": lambda x: x}  # Não é serializável

        with pytest.raises(TypeError):
            safe_write_json(str(caminho), dados)

    def test_arquivo_nao_corrompido_apos_falha(self, tmp_path):
        """Verifica que arquivo original não é corrompido se escrita falhar."""
        caminho = tmp_path / "teste.json"
        dados_originais = {"original": "dados"}
        dados_invalidos = {"funcao": lambda x: x}

        # Escreve dados válidos
        safe_write_json(str(caminho), dados_originais)

        # Tenta escrever dados inválidos
        with pytest.raises(TypeError):
            safe_write_json(str(caminho), dados_invalidos)

        # Verifica que arquivo original está intacto
        with open(caminho, "r") as f:
            conteudo = json.load(f)
        assert conteudo == dados_originais

    def test_json_valido_por_linha(self, tmp_path):
        """Verifica que o JSON gerado é válido."""
        caminho = tmp_path / "teste.json"
        dados = {"lista": [1, 2, 3], "dict": {"nested": True}}
        safe_write_json(str(caminho), dados)

        # Tenta fazer parse do arquivo
        with open(caminho, "r") as f:
            conteudo = json.load(f)
        assert conteudo == dados


# ============================================================================
# TESTES PARA safe_resolve_path()
# ============================================================================


class TestSafeResolvePath:
    """Testes para a função safe_resolve_path()."""

    def test_caminho_valido_aceito(self, tmp_path):
        """Verifica que caminho válido dentro da base é aceito."""
        base = str(tmp_path)
        resultado = safe_resolve_path(base, "arquivo.json")
        assert resultado.startswith(base)
        assert "arquivo.json" in resultado

    def test_caminho_com_subdiretorio(self, tmp_path):
        """Verifica que caminho com subdiretório é aceito."""
        base = str(tmp_path)
        resultado = safe_resolve_path(base, "subdir/arquivo.json")
        assert resultado.startswith(base)
        assert "subdir" in resultado

    def test_path_traversal_com_ponto_ponto_lanca_erro(self, tmp_path):
        """Verifica que path traversal com ../ lança ValueError."""
        base = str(tmp_path)
        with pytest.raises(ValueError) as exc_info:
            safe_resolve_path(base, "../arquivo.json")
        assert "fora do diretório base" in str(exc_info.value)

    def test_path_traversal_multiplo_lanca_erro(self, tmp_path):
        """Verifica que múltiplos ../ lançam ValueError."""
        base = str(tmp_path)
        with pytest.raises(ValueError):
            safe_resolve_path(base, "../../etc/passwd")

    def test_path_absoluto_fora_da_base_lanca_erro(self, tmp_path):
        """Verifica que caminho absoluto fora da base lança ValueError."""
        base = str(tmp_path)
        with pytest.raises(ValueError):
            safe_resolve_path(base, "/etc/passwd")

    def test_retorna_caminho_absoluto(self, tmp_path):
        """Verifica que retorna caminho absoluto."""
        base = str(tmp_path)
        resultado = safe_resolve_path(base, "arquivo.json")
        assert os.path.isabs(resultado)

    def test_base_relativa_convertida_para_absoluta(self):
        """Verifica que base relativa é convertida para absoluta."""
        resultado = safe_resolve_path(".", "arquivo.json")
        assert os.path.isabs(resultado)


# ============================================================================
# TESTES PARA com_retry()
# ============================================================================


class TestComRetry:
    """Testes para a função com_retry()."""

    def test_sucesso_na_primeira_tentativa(self):
        """Verifica sucesso na primeira tentativa."""
        chamadas = []

        def funcao_sucesso():
            chamadas.append(1)
            return "sucesso"

        resultado = com_retry(funcao_sucesso, tentativas=3, delays=[0, 0, 0])
        assert resultado == "sucesso"
        assert len(chamadas) == 1

    def test_sucesso_apos_falhas(self):
        """Verifica sucesso após falhas iniciais."""
        chamadas = []

        def funcao_com_falhas():
            chamadas.append(1)
            if len(chamadas) < 3:
                raise ValueError("Falha temporária")
            return "sucesso"

        resultado = com_retry(funcao_com_falhas, tentativas=3, delays=[0, 0, 0])
        assert resultado == "sucesso"
        assert len(chamadas) == 3

    def test_esgota_tentativas(self):
        """Verifica que lança exceção após esgotar tentativas."""
        chamadas = []

        def funcao_sempre_falha():
            chamadas.append(1)
            raise ValueError("Sempre falha")

        with pytest.raises(ValueError) as exc_info:
            com_retry(funcao_sempre_falha, tentativas=3, delays=[0, 0, 0])
        assert "Sempre falha" in str(exc_info.value)
        assert len(chamadas) == 3

    def test_respeita_numero_tentativas(self):
        """Verifica que respeita o número de tentativas."""
        chamadas = []

        def funcao_falha():
            chamadas.append(1)
            raise ValueError("Falha")

        with pytest.raises(ValueError):
            com_retry(funcao_falha, tentativas=5, delays=[0, 0, 0, 0, 0])
        assert len(chamadas) == 5

    def test_captura_excecoes_especificas(self):
        """Verifica que captura apenas exceções especificadas."""
        chamadas = []

        def funcao_lanca_tipo_erro():
            chamadas.append(1)
            raise TypeError("Tipo erro")

        # Especifica que só captura ValueError, não TypeError
        with pytest.raises(TypeError):
            com_retry(
                funcao_lanca_tipo_erro,
                tentativas=3,
                delays=[0, 0, 0],
                excecoes=(ValueError,),
            )
        assert len(chamadas) == 1  # Não faz retry

    def test_captura_multiplas_excecoes(self):
        """Verifica que captura múltiplas exceções especificadas."""
        chamadas = []

        def funcao_falha():
            chamadas.append(1)
            if len(chamadas) == 1:
                raise ValueError("Erro 1")
            elif len(chamadas) == 2:
                raise TypeError("Erro 2")
            return "sucesso"

        resultado = com_retry(
            funcao_falha,
            tentativas=3,
            delays=[0, 0, 0],
            excecoes=(ValueError, TypeError),
        )
        assert resultado == "sucesso"
        assert len(chamadas) == 3

    def test_delays_padrao(self):
        """Verifica que usa delays padrão se não especificado."""
        chamadas = []
        tempos = []

        def funcao_com_falhas():
            tempos.append(time.time())
            chamadas.append(1)
            if len(chamadas) < 2:
                raise ValueError("Falha")
            return "sucesso"

        # Usa delays padrão [1, 2, 4] — vai esperar ~1s entre tentativas
        # Para não deixar o teste lento, vamos apenas verificar que não lança erro
        resultado = com_retry(funcao_com_falhas, tentativas=2)
        assert resultado == "sucesso"

    def test_delays_customizados(self):
        """Verifica que usa delays customizados."""
        chamadas = []

        def funcao_com_falhas():
            chamadas.append(1)
            if len(chamadas) < 2:
                raise ValueError("Falha")
            return "sucesso"

        # Usa delays customizados [0, 0] para não esperar
        resultado = com_retry(
            funcao_com_falhas, tentativas=2, delays=[0, 0]
        )
        assert resultado == "sucesso"

    def test_retorna_valor_da_funcao(self):
        """Verifica que retorna o valor correto da função."""
        def funcao_retorna_dict():
            return {"chave": "valor", "numero": 42}

        resultado = com_retry(funcao_retorna_dict, tentativas=1, delays=[0])
        assert resultado == {"chave": "valor", "numero": 42}

    def test_lambda_com_argumentos(self):
        """Verifica que funciona com lambda que tem argumentos capturados."""
        valor_externo = 10

        def funcao_com_valor():
            return valor_externo * 2

        resultado = com_retry(funcao_com_valor, tentativas=1, delays=[0])
        assert resultado == 20

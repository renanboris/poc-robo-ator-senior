"""
tests/test_versioning_properties.py — Property-Based Tests para Versionamento de Roteiros
===========================================================================================
Property 11: Preservação de versões de roteiro
**Validates: Requirements 2.6.1, 2.6.2**

Para qualquer sequência de N >= 2 escritas sobre o mesmo roteiro, verificar que pelo menos
as 2 versões mais recentes distintas são preservadas.
"""

import json
import os
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from utils import (
    salvar_versao_roteiro,
    restaurar_versao_roteiro,
    listar_versoes_roteiro,
)
from utils import validar_roteiro


# ---------------------------------------------------------------------------
# Estratégias Hypothesis
# ---------------------------------------------------------------------------

acao_tecnica_strategy = st.fixed_dictionaries({
    "acao": st.sampled_from(["clique", "digitar_e_enter", "preencher_campo"]),
    "intencao_semantica": st.text(min_size=1, max_size=50),
    "elemento_alvo": st.fixed_dictionaries({
        "seletor_hint": st.text(min_size=1, max_size=80),
        "confianca_captura": st.sampled_from(["alta", "media"]),
    }),
})

passo_strategy = st.fixed_dictionaries({
    "id_passo": st.integers(min_value=1, max_value=100),
    "is_conclusao": st.just(False),
    "pedagogia": st.fixed_dictionaries({
        "ancora": st.text(min_size=1, max_size=100),
        "tooltip_dap": st.text(max_size=50),
    }),
    "acoes_tecnicas": st.lists(acao_tecnica_strategy, min_size=1, max_size=3),
})

passo_conclusao_strategy = st.fixed_dictionaries({
    "id_passo": st.integers(min_value=101, max_value=200),
    "is_conclusao": st.just(True),
    "pedagogia": st.fixed_dictionaries({
        "ancora": st.text(min_size=1, max_size=100),
        "tooltip_dap": st.text(max_size=50),
    }),
    "acoes_tecnicas": st.lists(acao_tecnica_strategy, min_size=1, max_size=2),
})


def roteiro_valido_strategy():
    """Gera roteiros que passam em validar_roteiro()."""
    return st.builds(
        lambda passos_normais, passo_final, nome: {
            "metadata": {
                "nome_aula": nome,
                "id_treinamento": nome[:20].replace(" ", "_"),
            },
            "configuracao_gravacao": {
                "gravar_video": True,
                "pasta_destino": "videos_gerados",
                "voz_ia": "pt-BR-FranciscaNeural",
            },
            "passos": passos_normais + [passo_final],
        },
        passos_normais=st.lists(passo_strategy, min_size=1, max_size=4),
        passo_final=passo_conclusao_strategy,
        nome=st.text(min_size=3, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"))),
    )


# ---------------------------------------------------------------------------
# Property 11: Preservação de versões de roteiro
# ---------------------------------------------------------------------------

@given(
    roteiros=st.lists(roteiro_valido_strategy(), min_size=2, max_size=6),
)
@settings(max_examples=50)
def test_property_11_preservacao_versoes_roteiro(roteiros):
    """
    Property 11: Preservação de versões de roteiro
    **Validates: Requirements 2.6.1, 2.6.2**

    Para qualquer sequência de N >= 2 escritas sobre o mesmo roteiro,
    verificar que pelo menos as 2 versões mais recentes distintas são preservadas.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro_teste.json")

        # Executa N escritas sequenciais sobre o mesmo arquivo
        for roteiro in roteiros:
            salvar_versao_roteiro(caminho, roteiro)

        # Após N >= 2 escritas, deve haver pelo menos 2 versões preservadas:
        # o arquivo ativo (versão mais recente) + pelo menos 1 backup
        versoes_backup = listar_versoes_roteiro(caminho)

        # O arquivo ativo deve existir
        assert os.path.exists(caminho), "Arquivo ativo deve existir após escritas"

        # Deve haver pelo menos 1 backup (versão anterior preservada)
        assert len(versoes_backup) >= 1, (
            f"Após {len(roteiros)} escritas, deve haver pelo menos 1 backup. "
            f"Backups encontrados: {versoes_backup}"
        )

        # O backup mais recente deve ser um JSON válido e legível
        backup_mais_recente = versoes_backup[0]
        assert os.path.exists(backup_mais_recente), "Backup mais recente deve existir"

        with open(backup_mais_recente, "r", encoding="utf-8") as f:
            dados_backup = json.load(f)
        assert isinstance(dados_backup, dict), "Backup deve ser um dicionário JSON válido"
        assert "passos" in dados_backup, "Backup deve conter campo 'passos'"

        # O arquivo ativo deve ser o último roteiro escrito
        with open(caminho, "r", encoding="utf-8") as f:
            dados_ativos = json.load(f)
        assert dados_ativos == roteiros[-1], (
            "O arquivo ativo deve conter o último roteiro escrito"
        )

        # Máximo de 2 backups mantidos (política de retenção)
        assert len(versoes_backup) <= 2, (
            f"Deve manter no máximo 2 backups, mas encontrou {len(versoes_backup)}: {versoes_backup}"
        )


# ---------------------------------------------------------------------------
# Testes unitários complementares
# ---------------------------------------------------------------------------

def _roteiro_minimo(nome: str = "Teste") -> dict:
    """Cria um roteiro mínimo válido para testes unitários."""
    return {
        "metadata": {"nome_aula": nome, "id_treinamento": nome},
        "configuracao_gravacao": {
            "gravar_video": True,
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
                        "intencao_semantica": "Clicar no botão",
                        "elemento_alvo": {
                            "seletor_hint": "#btn-ok",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
            {
                "id_passo": 2,
                "is_conclusao": True,
                "pedagogia": {"ancora": "Conclusão", "tooltip_dap": ""},
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "intencao_semantica": "Finalizar",
                        "elemento_alvo": {
                            "seletor_hint": "#btn-fim",
                            "confianca_captura": "alta",
                        },
                    }
                ],
            },
        ],
    }


def test_salvar_versao_sem_arquivo_anterior():
    """Primeira escrita não cria backup (não havia versão anterior)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro.json")
        backup = salvar_versao_roteiro(caminho, _roteiro_minimo())
        assert backup == "", "Primeira escrita não deve criar backup"
        assert os.path.exists(caminho)


def test_salvar_versao_cria_backup_na_segunda_escrita():
    """Segunda escrita deve criar backup da versão anterior."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro.json")
        salvar_versao_roteiro(caminho, _roteiro_minimo("V1"))
        backup = salvar_versao_roteiro(caminho, _roteiro_minimo("V2"))
        assert backup != "", "Segunda escrita deve criar backup"
        assert os.path.exists(backup)
        # Backup deve conter a versão anterior (V1)
        with open(backup) as f:
            dados = json.load(f)
        assert dados["metadata"]["nome_aula"] == "V1"


def test_listar_versoes_retorna_mais_recente_primeiro():
    """listar_versoes_roteiro deve retornar backups do mais recente ao mais antigo."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro.json")
        for i in range(3):
            salvar_versao_roteiro(caminho, _roteiro_minimo(f"V{i}"))
        versoes = listar_versoes_roteiro(caminho)
        # Deve ter no máximo 2 backups (política de retenção)
        assert len(versoes) <= 2
        # Deve estar em ordem decrescente (mais recente primeiro)
        if len(versoes) >= 2:
            assert versoes[0] >= versoes[1], "Versões devem estar em ordem decrescente"


def test_restaurar_versao_valida():
    """Restaurar um backup válido deve funcionar e validar o roteiro."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro.json")
        roteiro_v1 = _roteiro_minimo("V1")
        salvar_versao_roteiro(caminho, roteiro_v1)
        salvar_versao_roteiro(caminho, _roteiro_minimo("V2"))

        versoes = listar_versoes_roteiro(caminho)
        assert len(versoes) >= 1

        sucesso, motivo = restaurar_versao_roteiro(versoes[0], caminho)
        assert sucesso, f"Restauração deve ter sucesso: {motivo}"

        with open(caminho) as f:
            dados_restaurados = json.load(f)
        assert dados_restaurados["metadata"]["nome_aula"] == "V1"


def test_restaurar_versao_inexistente_retorna_falso():
    """Tentar restaurar arquivo inexistente deve retornar (False, motivo)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho_destino = os.path.join(tmpdir, "roteiro.json")
        sucesso, motivo = restaurar_versao_roteiro("/nao/existe.bak.20240101_120000", caminho_destino)
        assert not sucesso
        assert "não encontrado" in motivo.lower()


def test_maximo_dois_backups_mantidos():
    """Após muitas escritas, deve manter no máximo 2 backups."""
    with tempfile.TemporaryDirectory() as tmpdir:
        caminho = os.path.join(tmpdir, "roteiro.json")
        for i in range(6):
            salvar_versao_roteiro(caminho, _roteiro_minimo(f"V{i}"))
        versoes = listar_versoes_roteiro(caminho)
        assert len(versoes) <= 2, f"Deve manter no máximo 2 backups, encontrou {len(versoes)}"

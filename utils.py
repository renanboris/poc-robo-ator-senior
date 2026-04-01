"""
utils.py — Senior Training OS · Utilitários Compartilhados
===========================================================
FIX Bug #DRY-01: limpar_nome estava duplicada em 6 arquivos diferentes.
FIX Bug #PINECONE-01: Normalização ASCII pura para evitar crashes no banco vetorial.
FIX Bug #DRY-02: validar_roteiro centralizada — era duplicada em capture.py e app.py.

Esta é agora a ÚNICA fonte de verdade. Todos os módulos devem importar daqui:

    from utils import limpar_nome, validar_roteiro
"""

import re
import unicodedata

def limpar_nome(nome: str) -> str:
    """
    Sanitiza uma string para uso seguro como nome de arquivo/pasta e IDs Vetoriais.
    Remove acentos (garantindo ASCII puro), caracteres proibidos no Windows/Mac/Linux
    e limita a 40 chars.
    """
    # 1. Normaliza a string e arranca os acentos (Ex: "Criação" -> "Criacao")
    nome_norm = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('utf-8')

    # 2. Remove os caracteres proibidos de Sistema Operacional e formata os espaços
    return re.sub(r'[\\/*?:"<>|]', "", nome_norm).replace(" ", "_")[:40].strip("_")


def validar_roteiro(roteiro: dict) -> tuple[bool, str]:
    """
    Portão de qualidade centralizado para roteiros do Senior Training OS.
    Fonte canônica — não duplicar em outros módulos.

    Critérios mínimos:
      - >= 2 passos (1 real + 1 conclusão)
      - >= 50% das ações técnicas válidas com seletor_hint preenchido
      - <= 70% das ações técnicas válidas com confianca_captura == 'baixa'

    Ações com acao == 'concluir_video' são ignoradas nos cálculos.

    Retorna (aprovado: bool, motivo: str).
    """
    passos = roteiro.get("passos", [])
    if len(passos) < 2:
        return False, f"Apenas {len(passos)} passo(s) — mapeamento insuficiente."

    total_acoes = acoes_com_seletor = acoes_baixa_conf = 0

    for passo in passos:
        for acao in passo.get("acoes_tecnicas", []):
            if acao.get("acao") == "concluir_video":
                continue
            total_acoes += 1
            alvo = acao.get("elemento_alvo", {})
            if alvo.get("seletor_hint", "").strip():
                acoes_com_seletor += 1
            if alvo.get("confianca_captura") == "baixa":
                acoes_baixa_conf += 1

    if total_acoes == 0:
        return False, "Nenhuma ação técnica válida encontrada."

    pct_seletor = acoes_com_seletor / total_acoes
    pct_baixa   = acoes_baixa_conf  / total_acoes

    if pct_seletor < 0.50:
        return False, f"Apenas {pct_seletor:.0%} das ações tem seletor CSS válido."
    if pct_baixa > 0.70:
        return False, f"{pct_baixa:.0%} das ações com confiança baixa."

    return True, (
        f"OK — {len(passos)} passos, {total_acoes} ações, "
        f"{pct_seletor:.0%} com seletor, {pct_baixa:.0%} baixa confiança."
    )
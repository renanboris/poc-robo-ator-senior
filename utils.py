"""
utils.py — Senior Training OS · Utilitários Compartilhados
===========================================================
FIX Bug #DRY-01: limpar_nome estava duplicada em 6 arquivos diferentes.
FIX Bug #PINECONE-01: Normalização ASCII pura para evitar crashes no banco vetorial.

Esta é agora a ÚNICA fonte de verdade. Todos os módulos devem importar daqui:

    from utils import limpar_nome
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
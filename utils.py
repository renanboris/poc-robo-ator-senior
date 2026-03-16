"""
utils.py — Senior Training OS · Utilitários Compartilhados
===========================================================
FIX Bug #DRY-01: limpar_nome estava duplicada em 6 arquivos diferentes
(app.py, main.py, capture.py, generator_engine.py, scorm_builder.py, pdf_builder.py).

Esta é agora a ÚNICA fonte de verdade. Todos os módulos devem importar daqui:

    from utils import limpar_nome

Remova as definições locais de limpar_nome dos outros módulos.
"""

import re


def limpar_nome(nome: str) -> str:
    """
    Sanitiza uma string para uso seguro como nome de arquivo/pasta.
    Remove caracteres proibidos no Windows/Mac/Linux e limita a 40 chars.
    """
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

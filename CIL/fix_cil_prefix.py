"""
fix_cil_prefix.py — Remove o prefixo 'CIL.' dos imports
Execute em C:\\GenUCS\\CIL:
    python fix_cil_prefix.py
"""
import os
import re

ARQUIVOS = [
    "main_cil.py",
    "core/vision_engine_cil.py",
    "core/screen_fingerprint.py",
    "core/screen_reader.py",
    "core/planner_cil.py",
    "capture/capture_semantic.py",
    "knowledge/pattern_engine.py",
]

for arq in ARQUIVOS:
    if not os.path.exists(arq):
        continue
    with open(arq, encoding="utf-8") as f:
        txt = f.read()

    # Remove prefixo CIL. de qualquer import
    novo = re.sub(r'\bCIL\.(core|capture|knowledge)\.', r'\1.', txt)

    # Garante que sys.path aponta para a pasta CIL (onde está main_cil.py)
    if arq == "main_cil.py" and "sys.path.insert" not in novo:
        novo = "import sys, os\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n" + novo

    if novo != txt:
        with open(arq, "w", encoding="utf-8") as f:
            f.write(novo)
        print(f"✅ Corrigido: {arq}")
    else:
        print(f"   OK:        {arq}")

print("\nPronto. Teste: python main_cil.py")

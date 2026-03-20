"""
fix_imports.py — Corrige imports para a nova estrutura de pastas CIL
=====================================================================
Execute UMA VEZ na raiz do projeto CIL:
    cd C:\\GenUCS\\CIL
    python fix_imports.py
"""

import os
import re

# Mapeamento: nome do módulo antigo → novo caminho de import
MAPA_IMPORTS = {
    # core
    "vision_engine_cil":  "core.vision_engine_cil",
    "screen_fingerprint": "core.screen_fingerprint",
    "screen_reader":      "core.screen_reader",
    "planner_cil":        "core.planner_cil",
    # capture
    "capture_semantic":   "capture.capture_semantic",
    # knowledge
    "pattern_engine":     "knowledge.pattern_engine",
}

# Caminhos de dados que precisam ser ajustados nos arquivos
MAPA_CAMINHOS = {
    '"brain_v2.db"':             '"data/brain_v2.db"',
    "'brain_v2.db'":             "'data/brain_v2.db'",
    '"patterns_registry.json"':  '"knowledge/patterns_registry.json"',
    "'patterns_registry.json'":  "'knowledge/patterns_registry.json'",
    '"relatorio_auto_cura.json"':'"data/relatorio_auto_cura.json"',
    "'relatorio_auto_cura.json'":"'data/relatorio_auto_cura.json'",
    '"diagnostico_falhas/"':     '"data/diagnostico_falhas/"',
    '"relatorios_execucao/"':    '"data/relatorios_execucao/"',
    '"roteiros_salvos"':         '"data/roteiros"',
    "'roteiros_salvos'":         "'data/roteiros'",
}

# Arquivos a processar (relativos à raiz do CIL)
ARQUIVOS = [
    "main_cil.py",
    "core/vision_engine_cil.py",
    "core/screen_fingerprint.py",
    "core/screen_reader.py",
    "core/planner_cil.py",
    "capture/capture_semantic.py",
    "knowledge/pattern_engine.py",
]


def corrigir_arquivo(caminho: str) -> tuple[int, list[str]]:
    """Corrige imports e caminhos num arquivo. Retorna (nº mudanças, lista de mudanças)."""
    if not os.path.exists(caminho):
        print(f"  ⚠  Não encontrado: {caminho}")
        return 0, []

    with open(caminho, encoding="utf-8") as f:
        original = f.read()

    novo = original
    mudancas = []

    # 1. Corrige imports: "from X import" e "import X"
    for modulo_antigo, modulo_novo in MAPA_IMPORTS.items():
        # from modulo_antigo import ...
        padrao = rf'\bfrom\s+{re.escape(modulo_antigo)}\s+import\b'
        substituicao = f'from {modulo_novo} import'
        if re.search(padrao, novo):
            novo = re.sub(padrao, substituicao, novo)
            mudancas.append(f"from {modulo_antigo} → from {modulo_novo}")

        # import modulo_antigo (sem from)
        padrao2 = rf'^import\s+{re.escape(modulo_antigo)}\s*$'
        substituicao2 = f'import {modulo_novo}'
        if re.search(padrao2, novo, re.MULTILINE):
            novo = re.sub(padrao2, substituicao2, novo, flags=re.MULTILINE)
            mudancas.append(f"import {modulo_antigo} → import {modulo_novo}")

    # 2. Corrige caminhos de arquivos de dados
    for caminho_antigo, caminho_novo in MAPA_CAMINHOS.items():
        if caminho_antigo in novo:
            novo = novo.replace(caminho_antigo, caminho_novo)
            mudancas.append(f"{caminho_antigo} → {caminho_novo}")

    if novo != original:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(novo)

    return len(mudancas), mudancas


def criar_pastas_data():
    """Cria as pastas de dados se não existirem."""
    for pasta in ["data", "data/roteiros", "data/diagnostico_falhas", "data/relatorios_execucao"]:
        os.makedirs(pasta, exist_ok=True)
    print("✅ Pastas data/ criadas")


def renomear_registry_se_necessario():
    """Renomeia patterns_registry.py → .json se necessário."""
    if os.path.exists("knowledge/patterns_registry.py") and \
       not os.path.exists("knowledge/patterns_registry.json"):
        os.rename("knowledge/patterns_registry.py", "knowledge/patterns_registry.json")
        print("✅ Renomeado: patterns_registry.py → patterns_registry.json")


def garantir_init_py():
    """Garante que todos os __init__.py existem."""
    for pasta in ["core", "capture", "knowledge"]:
        init = f"{pasta}/__init__.py"
        if not os.path.exists(init):
            open(init, "w").close()
            print(f"✅ Criado: {init}")


def adicionar_raiz_ao_syspath():
    """
    Adiciona um bloco no início de main_cil.py para garantir que
    a raiz do CIL está no sys.path, resolvendo imports relativos.
    """
    if not os.path.exists("main_cil.py"):
        return

    with open("main_cil.py", encoding="utf-8") as f:
        conteudo = f.read()

    bloco_syspath = '''\
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
'''

    if "sys.path.insert" not in conteudo:
        with open("main_cil.py", "w", encoding="utf-8") as f:
            f.write(bloco_syspath + conteudo)
        print("✅ sys.path adicionado ao main_cil.py")


if __name__ == "__main__":
    print("=" * 55)
    print("CIL — Ajuste de imports para nova estrutura de pastas")
    print("=" * 55)
    print()

    # Verificar que estamos na pasta certa
    if not os.path.exists("main_cil.py") and not os.path.exists("core"):
        print("❌ Execute este script da RAIZ da pasta CIL")
        print("   cd C:\\GenUCS\\CIL")
        print("   python fix_imports.py")
        exit(1)

    criar_pastas_data()
    renomear_registry_se_necessario()
    garantir_init_py()
    adicionar_raiz_ao_syspath()

    print()
    print("Corrigindo imports e caminhos:")
    print("-" * 40)

    total_mudancas = 0
    for arquivo in ARQUIVOS:
        n, mudancas = corrigir_arquivo(arquivo)
        if mudancas:
            print(f"\n  📄 {arquivo} ({n} mudança{'s' if n>1 else ''}):")
            for m in mudancas:
                print(f"     • {m}")
        else:
            print(f"  ✅ {arquivo} — sem mudanças necessárias")
        total_mudancas += n

    print()
    print("=" * 55)
    print(f"✅ Concluído — {total_mudancas} substituição(ões) feita(s)")
    print()
    print("Próximos passos:")
    print("  1. Mova brain_v2.db para data/brain_v2.db (se existir)")
    print("  2. Mova roteiros/*.json para data/roteiros/")
    print("  3. Teste: python main_cil.py data/roteiros/Teste09_-_GED.json")

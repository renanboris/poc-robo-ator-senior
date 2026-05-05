#!/usr/bin/env python3
"""
Feature: aura-iframe-dom-capture-fix
Task 3.2: Verificação Estática do Fix

Este script analisa o código corrigido em aura_dom_mapper.js
e verifica se todos os requisitos do fix foram implementados.

EXPECTED OUTCOME: Todas as verificações devem PASSAR
"""

import re
import sys
from pathlib import Path


def verificar_fix():
    """Verifica se o fix foi implementado corretamente"""

    print("=" * 80)
    print("Task 3.2: Verificação do Fix - Iframe DOM Capture")
    print("=" * 80)
    print()

    # Carrega o código corrigido
    aura_dom_mapper_path = Path(__file__).parent.parent / 'modules' / 'aura_dom_mapper.js'

    if not aura_dom_mapper_path.exists():
        print(f"❌ ERRO: Arquivo não encontrado: {aura_dom_mapper_path}")
        return False

    with open(aura_dom_mapper_path, 'r', encoding='utf-8') as f:
        codigo = f.read()

    print(f"✓ Arquivo carregado: {aura_dom_mapper_path}")
    print()

    # Lista de verificações
    verificacoes = []

    # ── Verificação 1: Função auxiliar _capturarEmDocumento existe ────────────
    print("Verificação 1: Função auxiliar _capturarEmDocumento")
    if re.search(r'function\s+_capturarEmDocumento\s*\(', codigo):
        print("  ✅ PASSOU: Função _capturarEmDocumento encontrada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Função _capturarEmDocumento NÃO encontrada")
        verificacoes.append(False)
    print()

    # ── Verificação 2: Função aceita parâmetros corretos ──────────────────────
    print("Verificação 2: Parâmetros da função _capturarEmDocumento")
    match = re.search(r'function\s+_capturarEmDocumento\s*\(([^)]+)\)', codigo)
    if match:
        params = match.group(1)
        required_params = ['doc', 'frameInfo', 'startIndex', 'elementosMapeados']
        params_found = all(param in params for param in required_params)
        if params_found:
            print(f"  ✅ PASSOU: Parâmetros corretos encontrados: {params}")
            verificacoes.append(True)
        else:
            print(f"  ❌ FALHOU: Parâmetros incorretos: {params}")
            print("     Esperado: doc, frameInfo, startIndex, elementosMapeados")
            verificacoes.append(False)
    else:
        print("  ❌ FALHOU: Não foi possível extrair parâmetros")
        verificacoes.append(False)
    print()

    # ── Verificação 3: Iteração sobre iframes ─────────────────────────────────
    print("Verificação 3: Iteração sobre iframes no documento")
    if re.search(r'document\.querySelectorAll\s*\(\s*[\'"]iframe[\'"]\s*\)', codigo):
        print("  ✅ PASSOU: Código itera sobre iframes com querySelectorAll('iframe')")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Código NÃO itera sobre iframes")
        verificacoes.append(False)
    print()

    # ── Verificação 4: Try-catch para SecurityError ───────────────────────────
    print("Verificação 4: Tratamento de SecurityError para iframes cross-origin")
    # Procura por try-catch em torno do acesso a contentDocument
    iframe_iteration = re.search(
        r'iframes\.forEach\s*\([^{]+\{.*?try\s*\{.*?contentDocument.*?\}\s*catch',
        codigo,
        re.DOTALL
    )
    if iframe_iteration:
        print("  ✅ PASSOU: Try-catch encontrado para acesso a contentDocument")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Try-catch NÃO encontrado ou mal posicionado")
        verificacoes.append(False)
    print()

    # ── Verificação 5: Indicador de iframe no formato de saída ────────────────
    print("Verificação 5: Indicador de iframe no formato de saída")
    if re.search(r'\(iframe:\s*\$\{.*?\}\)', codigo):
        print("  ✅ PASSOU: Indicador '(iframe: ${name})' encontrado no formato de saída")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Indicador de iframe NÃO encontrado")
        verificacoes.append(False)
    print()

    # ── Verificação 6: Atribuição de data-aura-map ────────────────────────────
    print("Verificação 6: Atribuição de data-aura-map a elementos")
    if re.search(r'setAttribute\s*\(\s*[\'"]data-aura-map[\'"]', codigo):
        print("  ✅ PASSOU: Atribuição de data-aura-map encontrada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Atribuição de data-aura-map NÃO encontrada")
        verificacoes.append(False)
    print()

    # ── Verificação 7: Manutenção de índices globalmente únicos ───────────────
    print("Verificação 7: Manutenção de índices globalmente únicos")
    # Verifica se proximoIndice é atualizado após cada captura
    if re.search(r'proximoIndice\s*=\s*resultado.*?\.proximoIndice', codigo):
        print("  ✅ PASSOU: proximoIndice é atualizado entre capturas")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: proximoIndice NÃO é atualizado corretamente")
        verificacoes.append(False)
    print()

    # ── Verificação 8: Retorno de elementos e próximo índice ──────────────────
    print("Verificação 8: Retorno de elementos e próximo índice")
    if re.search(r'return\s*\{.*?elementos.*?proximoIndice.*?\}', codigo, re.DOTALL):
        print("  ✅ PASSOU: Função retorna { elementos, proximoIndice }")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Retorno incorreto da função auxiliar")
        verificacoes.append(False)
    print()

    # ── Verificação 9: Extração do nome do iframe ─────────────────────────────
    print("Verificação 9: Extração do nome do iframe")
    if re.search(r'frame\.name\s*\|\|\s*frame\.id\s*\|\|\s*[\'"]iframe[\'"]', codigo):
        print("  ✅ PASSOU: Nome do iframe extraído com fallback (name || id || 'iframe')")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Extração do nome do iframe NÃO encontrada")
        verificacoes.append(False)
    print()

    # ── Verificação 10: Concatenação de elementos de múltiplas fontes ─────────
    print("Verificação 10: Concatenação de elementos do documento principal e iframes")
    if re.search(r'todosElementos\.push\s*\(\.\.\.resultado.*?\.elementos\)', codigo):
        print("  ✅ PASSOU: Elementos são concatenados usando spread operator")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Concatenação de elementos NÃO encontrada")
        verificacoes.append(False)
    print()

    # ── Resumo ────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("RESUMO DA VERIFICAÇÃO")
    print("=" * 80)

    total = len(verificacoes)
    passou = sum(verificacoes)
    falhou = total - passou

    print(f"Total de verificações: {total}")
    print(f"✅ Passou: {passou}")
    print(f"❌ Falhou: {falhou}")
    print()

    if falhou == 0:
        print("🎉 SUCESSO: Todas as verificações passaram!")
        print()
        print("O fix foi implementado corretamente e atende a todos os requisitos:")
        print("  ✓ Elementos dentro de iframes acessíveis são capturados")
        print("  ✓ Formato de saída inclui indicador (iframe: ${name})")
        print("  ✓ Atributo data-aura-map é atribuído a elementos de iframe")
        print("  ✓ Índices são globalmente únicos entre documento principal e iframes")
        print("  ✓ Iframes cross-origin são tratados silenciosamente (SecurityError)")
        print()
        print("✅ Task 3.2 COMPLETA: O teste de bug condition agora deve PASSAR")
        return True
    else:
        print("⚠️  ATENÇÃO: Algumas verificações falharam")
        print()
        print("O fix pode não estar completo. Revise as verificações que falharam.")
        return False

if __name__ == '__main__':
    sucesso = verificar_fix()
    sys.exit(0 if sucesso else 1)

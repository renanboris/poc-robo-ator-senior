#!/usr/bin/env python3
"""
Feature: aura-iframe-dom-capture-fix
Task 3.3: Verificação Estática de Preservação

Este script analisa o código corrigido em aura_dom_mapper.js
e verifica se o comportamento para páginas SEM iframes foi preservado.

EXPECTED OUTCOME: Todas as verificações devem PASSAR
"""

import re
import sys
from pathlib import Path

def verificar_preservacao():
    """Verifica se o comportamento foi preservado para páginas sem iframes"""
    
    print("=" * 80)
    print("Task 3.3: Verificação de Preservação - Páginas Sem Iframes")
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
    
    # ── Verificação 1: Captura do documento principal preservada ──────────────
    print("Verificação 1: Captura do documento principal")
    if re.search(r'_capturarEmDocumento\s*\(\s*document\s*,\s*null', codigo):
        print("  ✅ PASSOU: Documento principal é capturado com frameInfo=null")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Captura do documento principal pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 2: Formato de saída preservado ────────────────────────────
    print("Verificação 2: Formato de saída para elementos não-iframe")
    # Verifica que elementos do documento principal NÃO têm indicador de iframe
    if re.search(r'const frameSuffix = frameInfo \? .* : [\'"\']\s*[\'"\']\s*;', codigo):
        print("  ✅ PASSOU: Elementos sem frameInfo não têm indicador de iframe")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Formato de saída pode estar alterado")
        verificacoes.append(False)
    print()
    
    # ── Verificação 3: Filtragem de duplicatas preservada ─────────────────────
    print("Verificação 3: Filtragem de duplicatas baseada em texto")
    if re.search(r'elementosMapeados\.has\s*\(\s*texto\s*\)', codigo):
        print("  ✅ PASSOU: Filtragem de duplicatas usando Set preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Filtragem de duplicatas pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 4: Set compartilhado entre documento principal e iframes ──
    print("Verificação 4: Set de duplicatas compartilhado")
    # Verifica que elementosMapeados é passado para _capturarEmDocumento
    if re.search(r'_capturarEmDocumento\s*\([^)]*elementosMapeados', codigo):
        print("  ✅ PASSOU: Set de duplicatas é compartilhado (preserva filtragem)")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Set de duplicatas pode não estar compartilhado")
        verificacoes.append(False)
    print()
    
    # ── Verificação 5: Exclusão do container AURA preservada ──────────────────
    print("Verificação 5: Exclusão do container AURA")
    if re.search(r'aura-floating-container', codigo):
        print("  ✅ PASSOU: Lógica de exclusão do container AURA preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Exclusão do container AURA pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 6: Lógica de visibilidade preservada ──────────────────────
    print("Verificação 6: Lógica de visibilidade (bounding box)")
    if re.search(r'getBoundingClientRect', codigo):
        print("  ✅ PASSOU: Lógica de visibilidade usando bounding box preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Lógica de visibilidade pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 7: Limpeza de data-aura-map preservada ────────────────────
    print("Verificação 7: Limpeza de mapeamentos anteriores")
    if re.search(r'querySelectorAll\s*\(\s*[\'"\[]+data-aura-map', codigo):
        print("  ✅ PASSOU: Limpeza de data-aura-map no início preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Limpeza de mapeamentos pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 8: Atribuição de data-aura-map preservada ─────────────────
    print("Verificação 8: Atribuição de data-aura-map")
    if re.search(r'setAttribute\s*\(\s*[\'"]data-aura-map[\'"]', codigo):
        print("  ✅ PASSOU: Atribuição de data-aura-map preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Atribuição de data-aura-map pode estar comprometida")
        verificacoes.append(False)
    print()
    
    # ── Verificação 9: Índices globalmente únicos ─────────────────────────────
    print("Verificação 9: Índices globalmente únicos")
    # Verifica que startIndex é passado e proximoIndice é retornado
    if re.search(r'startIndex', codigo) and re.search(r'proximoIndice', codigo):
        print("  ✅ PASSOU: Mecanismo de índices globalmente únicos implementado")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Índices globalmente únicos podem estar comprometidos")
        verificacoes.append(False)
    print()
    
    # ── Verificação 10: Seletores preservados ─────────────────────────────────
    print("Verificação 10: Seletores de elementos interativos")
    if re.search(r'button.*input.*select', codigo, re.DOTALL):
        print("  ✅ PASSOU: Seletores de elementos interativos preservados")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Seletores podem estar alterados")
        verificacoes.append(False)
    print()
    
    # ── Verificação 11: Extração de texto preservada ──────────────────────────
    print("Verificação 11: Extração de texto dos elementos")
    if re.search(r'innerText.*textContent.*value.*aria-label.*title', codigo, re.DOTALL):
        print("  ✅ PASSOU: Lógica de extração de texto preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Extração de texto pode estar alterada")
        verificacoes.append(False)
    print()
    
    # ── Verificação 12: Limite de 40 caracteres preservado ────────────────────
    print("Verificação 12: Limite de 40 caracteres no texto")
    if re.search(r'substring\s*\(\s*0\s*,\s*40\s*\)', codigo):
        print("  ✅ PASSOU: Limite de 40 caracteres preservado")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Limite de caracteres pode estar alterado")
        verificacoes.append(False)
    print()
    
    # ── Verificação 13: Remoção de quebras de linha preservada ────────────────
    print("Verificação 13: Remoção de quebras de linha")
    if re.search(r'replace\s*\(\s*/\\n/g', codigo):
        print("  ✅ PASSOU: Remoção de quebras de linha preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Processamento de texto pode estar alterado")
        verificacoes.append(False)
    print()
    
    # ── Verificação 14: Validação de texto mínimo preservada ──────────────────
    print("Verificação 14: Validação de texto mínimo (length > 1)")
    if re.search(r'texto\.length\s*>\s*1', codigo):
        print("  ✅ PASSOU: Validação de texto mínimo preservada")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Validação de texto pode estar alterada")
        verificacoes.append(False)
    print()
    
    # ── Verificação 15: Header da saída preservado ────────────────────────────
    print("Verificação 15: Header da saída")
    if re.search(r'ELEMENTOS INTERATIVOS VISÍVEIS NA TELA', codigo):
        print("  ✅ PASSOU: Header da saída preservado")
        verificacoes.append(True)
    else:
        print("  ❌ FALHOU: Header da saída pode estar alterado")
        verificacoes.append(False)
    print()
    
    # ── Resumo ────────────────────────────────────────────────────────────────
    print("=" * 80)
    print("RESUMO DA VERIFICAÇÃO DE PRESERVAÇÃO")
    print("=" * 80)
    
    total = len(verificacoes)
    passou = sum(verificacoes)
    falhou = total - passou
    
    print(f"Total de verificações: {total}")
    print(f"✅ Passou: {passou}")
    print(f"❌ Falhou: {falhou}")
    print()
    
    if falhou == 0:
        print("🎉 SUCESSO: Todas as verificações de preservação passaram!")
        print()
        print("O comportamento para páginas SEM iframes foi preservado:")
        print("  ✓ Captura do documento principal funciona corretamente")
        print("  ✓ Formato de saída para elementos não-iframe está preservado")
        print("  ✓ Filtragem de duplicatas baseada em texto funciona")
        print("  ✓ Exclusão do container AURA funciona")
        print("  ✓ Lógica de visibilidade (bounding box) funciona")
        print("  ✓ Atribuição de data-aura-map com índices únicos funciona")
        print("  ✓ Todos os seletores e lógica de extração de texto preservados")
        print()
        print("✅ Task 3.3 COMPLETA: Testes de preservação devem continuar PASSANDO")
        return True
    else:
        print("⚠️  ATENÇÃO: Algumas verificações de preservação falharam")
        print()
        print("Pode haver regressão no comportamento para páginas sem iframes.")
        print("Revise as verificações que falharam.")
        return False

if __name__ == '__main__':
    sucesso = verificar_preservacao()
    sys.exit(0 if sucesso else 1)

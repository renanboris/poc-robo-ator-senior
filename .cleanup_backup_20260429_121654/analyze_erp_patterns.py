#!/usr/bin/env python3
"""
Análise dos padrões de URL do ERP baseado no mapeamento manual do usuário.
"""

import re
import json
from urllib.parse import unquote
from collections import defaultdict

def analyze_manual_mapping():
    """Analisa o mapeamento manual para entender os padrões de URL."""
    
    # Ler o arquivo de mapeamento manual
    with open('links_doc_erp.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extrair todas as URLs
    url_pattern = r'https://documentacao\.senior\.com\.br/seniorxplatform/manual-do-usuario/erp/[^*\s]+'
    urls = re.findall(url_pattern, content)
    
    print(f"📊 Total de URLs encontradas no mapeamento manual: {len(urls)}")
    
    # Analisar padrões de fragmentos
    fragments = []
    modules = defaultdict(list)
    
    for url in urls:
        # Extrair fragmento (parte após #)
        if '#' in url:
            fragment = url.split('#')[1]
            # Decodificar URL encoding
            fragment = unquote(fragment)
            fragments.append(fragment)
            
            # Identificar módulo principal
            parts = fragment.split('/')
            if parts:
                module = parts[0]
                modules[module].append(fragment)
    
    print(f"\n📂 Módulos identificados:")
    for module, paths in modules.items():
        print(f"  {module}: {len(paths)} URLs")
        
        # Mostrar alguns exemplos
        for path in paths[:3]:
            print(f"    - {path}")
        if len(paths) > 3:
            print(f"    ... e mais {len(paths) - 3}")
        print()
    
    # Analisar estrutura hierárquica
    print("🏗️ Estrutura hierárquica identificada:")
    hierarchy = defaultdict(lambda: defaultdict(list))
    
    for fragment in fragments:
        parts = fragment.split('/')
        if len(parts) >= 2:
            level1 = parts[0]
            level2 = parts[1] if len(parts) > 1 else 'root'
            level3 = parts[2] if len(parts) > 2 else 'root'
            
            hierarchy[level1][level2].append(level3)
    
    for level1, level2_dict in hierarchy.items():
        print(f"\n{level1}/")
        for level2, level3_list in level2_dict.items():
            unique_level3 = list(set(level3_list))
            print(f"  ├── {level2}/ ({len(unique_level3)} itens)")
            for level3 in unique_level3[:5]:
                if level3 != 'root':
                    print(f"  │   ├── {level3}")
            if len(unique_level3) > 5:
                print(f"  │   └── ... e mais {len(unique_level3) - 5}")
    
    # Gerar padrões para descoberta automática
    patterns = generate_discovery_patterns(modules)
    
    # Salvar análise
    analysis = {
        'total_urls': len(urls),
        'total_fragments': len(fragments),
        'modules': dict(modules),
        'hierarchy': dict(hierarchy),
        'discovery_patterns': patterns,
        'sample_urls': urls[:20]
    }
    
    with open('erp_pattern_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Análise salva em 'erp_pattern_analysis.json'")
    
    return analysis

def generate_discovery_patterns(modules):
    """Gera padrões para descoberta automática baseado nos módulos identificados."""
    
    patterns = {}
    
    for module, paths in modules.items():
        # Identificar subpadrões comuns
        subpatterns = defaultdict(int)
        
        for path in paths:
            parts = path.split('/')
            if len(parts) >= 2:
                subpattern = '/'.join(parts[:2])
                subpatterns[subpattern] += 1
        
        # Manter apenas padrões que aparecem múltiplas vezes
        common_patterns = [pattern for pattern, count in subpatterns.items() if count >= 2]
        patterns[module] = common_patterns
    
    return patterns

def compare_with_current_discovery():
    """Compara com as URLs atualmente descobertas pelo sistema."""
    
    print("\n🔍 Comparando com descoberta atual...")
    
    # URLs que nosso sistema atual descobriu (baseado no log anterior)
    current_erp_urls = [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/index.htm",
        # Adicionar outras URLs descobertas pelo sistema atual
    ]
    
    # URLs do mapeamento manual
    with open('links_doc_erp.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    manual_urls = re.findall(r'https://documentacao\.senior\.com\.br/seniorxplatform/manual-do-usuario/erp/[^*\s]+', content)
    
    print(f"URLs descobertas pelo sistema atual: {len(current_erp_urls)}")
    print(f"URLs no mapeamento manual: {len(manual_urls)}")
    print(f"URLs faltando: {len(manual_urls) - len(current_erp_urls)}")
    
    # Identificar URLs faltando
    current_set = set(current_erp_urls)
    manual_set = set(manual_urls)
    missing_urls = manual_set - current_set
    
    print(f"\n❌ Exemplos de URLs faltando:")
    for url in list(missing_urls)[:10]:
        print(f"  - {url}")
    
    return missing_urls

def suggest_improvements():
    """Sugere melhorias para o sistema de descoberta."""
    
    print("\n💡 SUGESTÕES DE MELHORIA:")
    
    print("\n1. 🎯 Navegação Hierárquica Profunda:")
    print("   - Implementar descoberta recursiva até 4-5 níveis de profundidade")
    print("   - Explorar cada módulo sistematicamente (suprimentos, financas, etc.)")
    
    print("\n2. 🔗 Interpretação de Fragmentos:")
    print("   - Melhorar parsing de URLs com fragmentos (#)")
    print("   - Decodificar corretamente parâmetros TocPath")
    
    print("\n3. 📋 Mapeamento de Módulos:")
    print("   - Usar lista conhecida de módulos do ERP")
    print("   - Explorar subpáginas comuns (cadastros, processos, consultas, relatórios)")
    
    print("\n4. 🤖 JavaScript Navigation:")
    print("   - Aguardar carregamento completo do SPA")
    print("   - Extrair dados de navegação do JavaScript")
    print("   - Simular cliques em menus de navegação")
    
    print("\n5. 📊 Validação Inteligente:")
    print("   - Validar URLs em lotes para melhor performance")
    print("   - Usar cache para evitar re-validação")

if __name__ == "__main__":
    print("🔍 ANÁLISE DOS PADRÕES DE URL DO ERP SENIOR X")
    print("=" * 50)
    
    # Analisar mapeamento manual
    analysis = analyze_manual_mapping()
    
    # Comparar com descoberta atual
    missing_urls = compare_with_current_discovery()
    
    # Sugerir melhorias
    suggest_improvements()
    
    print(f"\n✅ Análise concluída!")
    print(f"📄 Detalhes salvos em 'erp_pattern_analysis.json'")
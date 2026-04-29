"""Analyze sitemap structure to understand what was actually captured."""

import sys
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler
from ingestion_pipeline.extractor import SemanticExtractor

print("=" * 100)
print("ANÁLISE DETALHADA DO SITEMAP")
print("=" * 100)

# Crawl sitemap
crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")
urls = crawler.crawl()

print(f"\nTotal de URLs no sitemap: {len(urls)}")

# Agrupar por nivel_1 e nivel_2
extractor = SemanticExtractor(extraction_backend="crawl4ai")
hierarchy = defaultdict(lambda: defaultdict(list))

for url in urls:
    breadcrumbs = extractor.extract_breadcrumbs(url)
    nivel_1 = breadcrumbs['nivel_1']
    nivel_2 = breadcrumbs['nivel_2']
    
    if nivel_1 and nivel_2:
        hierarchy[nivel_1][nivel_2].append(url)
    elif nivel_1:
        hierarchy[nivel_1]['_root'].append(url)

# Mostrar estrutura hierárquica
print("\n" + "=" * 100)
print("ESTRUTURA HIERÁRQUICA DO SITEMAP")
print("=" * 100)

# Focar nas áreas importantes
important_nivel1 = ['senior-flow', 'seniorxplatform', 'bpm']

for nivel_1 in sorted(hierarchy.keys()):
    if nivel_1 not in important_nivel1:
        continue
    
    print(f"\n📁 {nivel_1.upper()}")
    print("-" * 100)
    
    for nivel_2 in sorted(hierarchy[nivel_1].keys()):
        urls_list = hierarchy[nivel_1][nivel_2]
        print(f"\n  📂 {nivel_2} ({len(urls_list)} URLs)")
        
        # Mostrar primeiras 5 URLs como exemplo
        for url in urls_list[:5]:
            print(f"     • {url}")
        
        if len(urls_list) > 5:
            print(f"     ... e mais {len(urls_list) - 5} URLs")

# Verificar se existem URLs relacionadas aos tópicos importantes
print("\n" + "=" * 100)
print("BUSCA POR TÓPICOS IMPORTANTES")
print("=" * 100)

search_terms = {
    "Senior Flow": ["senior-flow"],
    "GED": ["ged"],
    "SIGN": ["sign"],
    "BPM": ["bpm"],
    "Connect": ["connect"],
    "ERP": ["erp"],
}

for topic, terms in search_terms.items():
    print(f"\n🔍 Buscando: {topic}")
    print("-" * 100)
    
    found_urls = []
    for url in urls:
        url_lower = url.lower()
        if any(term in url_lower for term in terms):
            found_urls.append(url)
    
    if found_urls:
        print(f"✅ Encontradas {len(found_urls)} URLs relacionadas:")
        for url in found_urls[:10]:
            breadcrumbs = extractor.extract_breadcrumbs(url)
            print(f"   • {url}")
            print(f"     Namespace: {breadcrumbs['nivel_2']}")
        
        if len(found_urls) > 10:
            print(f"   ... e mais {len(found_urls) - 10} URLs")
    else:
        print(f"❌ Nenhuma URL encontrada")

print("\n" + "=" * 100)

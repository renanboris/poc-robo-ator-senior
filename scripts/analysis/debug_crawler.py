"""Debug why crawler only found 126 URLs when sitemap has 710."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler

print("=" * 100)
print("DEBUG DO CRAWLER")
print("=" * 100)

crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")

print("\n1. Crawling sitemap...")
urls = crawler.crawl()

print(f"\nTotal de URLs retornadas pelo crawler: {len(urls)}")

# Verificar se há filtros sendo aplicados
print("\n2. Verificando filtros do crawler...")
print(f"   Filtro de extensões: {crawler.allowed_extensions if hasattr(crawler, 'allowed_extensions') else 'N/A'}")

# Mostrar algumas URLs que foram capturadas
print("\n3. Primeiras 20 URLs capturadas:")
for i, url in enumerate(urls[:20], 1):
    print(f"   {i}. {url}")

# Verificar se as URLs importantes estão na lista
print("\n4. Verificando URLs importantes...")
important_urls_partial = [
    "senior-flow",
    "ged",
    "sign-studio",
    "bpm",
    "senior-connect",
]

for term in important_urls_partial:
    matching = [url for url in urls if term in url.lower()]
    if matching:
        print(f"\n✅ URLs contendo '{term}': {len(matching)}")
        for url in matching[:5]:
            print(f"   • {url}")
        if len(matching) > 5:
            print(f"   ... e mais {len(matching) - 5}")
    else:
        print(f"\n❌ Nenhuma URL contendo '{term}'")

print("\n" + "=" * 100)

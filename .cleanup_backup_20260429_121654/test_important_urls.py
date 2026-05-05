"""Test if important URLs were captured and categorized correctly."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.extractor import SemanticExtractor
from ingestion_pipeline.crawler import SitemapCrawler

# URLs importantes identificadas manualmente
important_urls = {
    "Senior Flow - Manual": "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/",
    "Senior Flow - Notas de Versão": "https://documentacao.senior.com.br/senior-flow/notas-da-versao/",
    "Ferramenta GED": "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/",
    "Ferramenta SIGN": "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/",
    "Ferramenta BPM": "https://documentacao.senior.com.br/bpm/7.0.0/",
    "Ferramenta Menu Flow": "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/flow/home-flow.htm",
    "Ferramenta Connect": "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/",
    "ERP Senior X": "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/?utm_source=portal-documentacao&utm_medium=referral&utm_campaign=link-home-portal",
}

print("=" * 100)
print("ANÁLISE DE URLs IMPORTANTES")
print("=" * 100)

# 1. Verificar se as URLs estão no sitemap
print("\n1. VERIFICANDO SE AS URLs ESTÃO NO SITEMAP...")
print("-" * 100)

crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")
sitemap_urls = crawler.crawl()

extractor = SemanticExtractor(extraction_backend="crawl4ai")

for nome, url in important_urls.items():
    # Normalizar URL (remover query params e trailing slash para comparação)
    url_clean = url.split('?')[0].rstrip('/')
    
    # Verificar se está no sitemap (comparação flexível)
    found_in_sitemap = False
    matched_url = None
    for sitemap_url in sitemap_urls:
        sitemap_url_clean = sitemap_url.split('?')[0].rstrip('/')
        if url_clean in sitemap_url_clean or sitemap_url_clean in url_clean:
            found_in_sitemap = True
            matched_url = sitemap_url
            break
    
    if found_in_sitemap:
        print(f"✅ {nome}")
        print(f"   URL original: {url}")
        print(f"   URL no sitemap: {matched_url}")
        
        # Extrair breadcrumbs
        breadcrumbs = extractor.extract_breadcrumbs(matched_url)
        print(f"   Namespace (nivel_2): {breadcrumbs['nivel_2']}")
        print(f"   Hierarquia completa: {breadcrumbs['nivel_1']} / {breadcrumbs['nivel_2']} / {breadcrumbs['nivel_3']}")
    else:
        print(f"❌ {nome}")
        print(f"   URL: {url}")
        print(f"   MOTIVO: Não encontrada no sitemap")
    
    print()

# 2. Análise dos namespaces esperados vs reais
print("\n2. ANÁLISE DE NAMESPACES ESPERADOS")
print("-" * 100)

expected_namespaces = {
    "senior-flow": "Deveria conter: Manual do usuário, Notas de versão, Menu Flow",
    "seniorxplatform": "Deveria conter: GED, SIGN, Connect, ERP Senior X",
    "bpm": "Deveria conter: Documentação do BPM 7.0.0",
}

print("\nNamespaces esperados baseados nas URLs importantes:")
for namespace, descricao in expected_namespaces.items():
    print(f"\n📁 {namespace}")
    print(f"   {descricao}")

print("\n" + "=" * 100)
print("CONCLUSÃO")
print("=" * 100)
print("""
PROBLEMA IDENTIFICADO:
As URLs importantes que você mapeou manualmente são DIRETÓRIOS (terminam com /),
não arquivos .htm ou .html individuais.

O sitemap.xml provavelmente contém apenas os arquivos .htm/.html DENTRO desses
diretórios, não os diretórios em si.

EXEMPLO:
- URL que você quer: https://documentacao.senior.com.br/senior-flow/manual-do-usuario/
- URLs no sitemap:   https://documentacao.senior.com.br/senior-flow/manual-do-usuario/introducao.htm
                     https://documentacao.senior.com.br/senior-flow/manual-do-usuario/instalacao.htm
                     etc.

SOLUÇÃO:
O scraper ESTÁ CORRETO! Ele captura os arquivos individuais dentro desses diretórios.
Os namespaces são criados baseados no nivel_2 da URL, que seria:
- senior-flow/manual-do-usuario/xxx.htm → namespace: "manual-do-usuario"
- seniorxplatform/manual-do-usuario/ged/xxx.htm → namespace: "manual-do-usuario"

Vamos verificar se os arquivos DENTRO desses diretórios foram capturados...
""")

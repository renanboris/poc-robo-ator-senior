"""Investigate if there are multiple sitemaps or a sitemap index."""

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

base_url = "https://documentacao.senior.com.br"

print("=" * 100)
print("INVESTIGAÇÃO DE SITEMAPS")
print("=" * 100)

# 1. Check robots.txt
print("\n1. Verificando robots.txt...")
print("-" * 100)

try:
    response = requests.get(f"{base_url}/robots.txt", timeout=10)
    if response.status_code == 200:
        print("✅ robots.txt encontrado:")
        print(response.text[:500])
        
        # Look for sitemap references
        if "sitemap" in response.text.lower():
            print("\n📍 Sitemaps mencionados no robots.txt:")
            for line in response.text.split('\n'):
                if 'sitemap' in line.lower():
                    print(f"   {line}")
    else:
        print(f"❌ robots.txt não encontrado (status: {response.status_code})")
except Exception as e:
    print(f"❌ Erro ao buscar robots.txt: {e}")

# 2. Check sitemap_index.xml
print("\n\n2. Verificando sitemap_index.xml...")
print("-" * 100)

try:
    response = requests.get(f"{base_url}/sitemap_index.xml", timeout=10)
    if response.status_code == 200:
        print("✅ sitemap_index.xml encontrado!")
        
        # Parse XML
        root = ET.fromstring(response.content)
        
        # Find all sitemap URLs
        ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
        sitemaps = root.findall('.//ns:sitemap/ns:loc', ns)
        
        if sitemaps:
            print(f"\n📍 Encontrados {len(sitemaps)} sitemaps:")
            for sitemap in sitemaps:
                print(f"   • {sitemap.text}")
        else:
            print("⚠️  Nenhum sitemap encontrado no índice")
    else:
        print(f"❌ sitemap_index.xml não encontrado (status: {response.status_code})")
except Exception as e:
    print(f"❌ Erro ao buscar sitemap_index.xml: {e}")

# 3. Try common sitemap variations
print("\n\n3. Testando variações comuns de sitemap...")
print("-" * 100)

sitemap_variations = [
    "sitemap.xml",
    "sitemap_index.xml",
    "sitemap-index.xml",
    "sitemap_products.xml",
    "sitemap_pages.xml",
    "sitemap_docs.xml",
]

for sitemap_name in sitemap_variations:
    try:
        response = requests.get(f"{base_url}/{sitemap_name}", timeout=5)
        if response.status_code == 200:
            # Count URLs
            root = ET.fromstring(response.content)
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = root.findall('.//ns:url/ns:loc', ns)
            sitemaps = root.findall('.//ns:sitemap/ns:loc', ns)
            
            if urls:
                print(f"✅ {sitemap_name}: {len(urls)} URLs")
            elif sitemaps:
                print(f"✅ {sitemap_name}: {len(sitemaps)} sitemaps (índice)")
            else:
                print(f"⚠️  {sitemap_name}: encontrado mas vazio")
        else:
            print(f"❌ {sitemap_name}: não encontrado")
    except Exception as e:
        print(f"❌ {sitemap_name}: erro ({str(e)[:50]})")

# 4. Check if important URLs are accessible
print("\n\n4. Verificando se as URLs importantes são acessíveis...")
print("-" * 100)

important_urls = [
    "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/",
    "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/",
    "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/",
    "https://documentacao.senior.com.br/bpm/7.0.0/",
]

for url in important_urls:
    try:
        response = requests.get(url, timeout=10, allow_redirects=True)
        if response.status_code == 200:
            print(f"✅ {url}")
            print(f"   Status: {response.status_code}, Tamanho: {len(response.content)} bytes")
        else:
            print(f"❌ {url}")
            print(f"   Status: {response.status_code}")
    except Exception as e:
        print(f"❌ {url}")
        print(f"   Erro: {str(e)[:100]}")

print("\n" + "=" * 100)

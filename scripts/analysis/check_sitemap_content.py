"""Check if sitemap contains .htm files inside important directories."""

import requests
from bs4 import BeautifulSoup

sitemap_url = "https://documentacao.senior.com.br/sitemap.xml"

print("=" * 100)
print("ANÁLISE COMPLETA DO SITEMAP (710 URLs)")
print("=" * 100)

# Fetch sitemap
response = requests.get(sitemap_url, timeout=30)
soup = BeautifulSoup(response.text, 'lxml-xml')

# Extract all URLs
loc_tags = soup.find_all('loc')
all_urls = [loc.get_text().strip() for loc in loc_tags]

print(f"\nTotal de URLs no sitemap: {len(all_urls)}")

# Categorize URLs
html_files = [url for url in all_urls if url.endswith('.htm') or url.endswith('.html')]
directories = [url for url in all_urls if url.endswith('/')]
other = [url for url in all_urls if not (url.endswith('.htm') or url.endswith('.html') or url.endswith('/'))]

print("\nCategorização:")
print(f"  • Arquivos .htm/.html: {len(html_files)}")
print(f"  • Diretórios (/): {len(directories)}")
print(f"  • Outros: {len(other)}")

# Check for important paths
print("\n" + "=" * 100)
print("BUSCA POR CAMINHOS IMPORTANTES")
print("=" * 100)

important_paths = {
    "Senior Flow": "senior-flow",
    "GED": "/ged/",
    "SIGN": "sign-studio",
    "BPM": "/bpm/",
    "Connect": "senior-connect",
    "ERP": "/erp/",
}

for name, path in important_paths.items():
    matching = [url for url in all_urls if path in url.lower()]

    if matching:
        print(f"\n✅ {name} ({path}): {len(matching)} URLs")

        # Separate by type
        htm_files = [url for url in matching if url.endswith('.htm') or url.endswith('.html')]
        dirs = [url for url in matching if url.endswith('/')]

        print(f"   • Arquivos .htm: {len(htm_files)}")
        print(f"   • Diretórios: {len(dirs)}")

        # Show first 10 examples
        print("\n   Exemplos:")
        for url in matching[:10]:
            print(f"     • {url}")

        if len(matching) > 10:
            print(f"     ... e mais {len(matching) - 10}")
    else:
        print(f"\n❌ {name} ({path}): Nenhuma URL encontrada")

# Show some "other" URLs to understand what they are
if other:
    print("\n" + "=" * 100)
    print(f"EXEMPLOS DE 'OUTROS' ({len(other)} URLs)")
    print("=" * 100)
    for url in other[:20]:
        print(f"  • {url}")

print("\n" + "=" * 100)

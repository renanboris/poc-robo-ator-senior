#!/usr/bin/env python3
"""
Correção rápida para adicionar URLs do ERP baseadas no mapeamento manual.
"""

import re

from ingestion_pipeline.crawler import SitemapCrawler


def extract_erp_urls_from_manual_mapping():
    """Extrai URLs do mapeamento manual e as converte para o formato correto."""

    # Ler o mapeamento manual
    with open('links_doc_erp.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # Extrair URLs
    url_pattern = r'https://documentacao\.senior\.com\.br/seniorxplatform/manual-do-usuario/erp/[^*\s]+'
    raw_urls = re.findall(url_pattern, content)

    # Converter para URLs limpas
    clean_urls = []
    base_url = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/"

    for url in raw_urls:
        if '#' in url:
            # Extrair fragmento e limpar
            fragment = url.split('#')[1]
            # Remover parâmetros UTM
            fragment = fragment.split('?utm_')[0]
            # Decodificar URL encoding básico
            fragment = fragment.replace('%20', ' ').replace('%C3%A3', 'ã').replace('%C3%A7', 'ç')

            # Reconstruir URL limpa
            clean_url = base_url + '#' + fragment
            clean_urls.append(clean_url)

    # Remover duplicatas
    unique_urls = list(set(clean_urls))

    print(f"✅ Extraídas {len(unique_urls)} URLs únicas do mapeamento manual")
    return unique_urls

def patch_sitemap_crawler():
    """Adiciona as URLs do mapeamento manual ao SitemapCrawler."""

    # Extrair URLs do mapeamento manual
    manual_urls = extract_erp_urls_from_manual_mapping()

    # Adicionar método ao SitemapCrawler
    def get_enhanced_erp_urls(self):
        """Retorna URLs do ERP baseadas no mapeamento manual."""
        return manual_urls

    # Patch do método get_important_urls
    original_get_important_urls = SitemapCrawler.get_important_urls

    def enhanced_get_important_urls(self):
        """Versão aprimorada que inclui URLs do mapeamento manual."""
        # URLs importantes originais
        original_urls = original_get_important_urls(self)

        # URLs do mapeamento manual
        manual_urls = extract_erp_urls_from_manual_mapping()

        # Combinar e remover duplicatas
        all_urls = list(set(original_urls + manual_urls))

        print(f"📈 URLs importantes: {len(original_urls)} originais + {len(manual_urls)} manuais = {len(all_urls)} total")
        return all_urls

    # Aplicar patch
    SitemapCrawler.get_important_urls = enhanced_get_important_urls

    print("🔧 SitemapCrawler atualizado com URLs do mapeamento manual")

if __name__ == "__main__":
    # Aplicar correção
    patch_sitemap_crawler()

    # Testar
    crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")
    urls = crawler.get_important_urls()

    print("\n📊 RESULTADO:")
    print(f"Total de URLs importantes: {len(urls)}")

    # Contar URLs do ERP
    erp_urls = [url for url in urls if 'erp' in url]
    print(f"URLs do ERP: {len(erp_urls)}")

    # Mostrar alguns exemplos
    print("\n📋 Exemplos de URLs do ERP:")
    for url in erp_urls[:10]:
        print(f"  - {url}")

    if len(erp_urls) > 10:
        print(f"  ... e mais {len(erp_urls) - 10}")

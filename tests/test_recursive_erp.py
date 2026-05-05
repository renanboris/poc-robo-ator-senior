#!/usr/bin/env python3
"""
Teste da descoberta recursiva do ERP.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ingestion_pipeline.crawler import SitemapCrawler


async def test_recursive_erp():
    """Testa descoberta recursiva do ERP."""
    print("=" * 80)
    print("TESTE: DESCOBERTA RECURSIVA DO ERP")
    print("=" * 80)

    # Initialize crawler
    sitemap_url = "https://documentacao.senior.com.br/sitemap.xml"
    crawler = SitemapCrawler(sitemap_url)

    # Test ERP recursive discovery
    erp_base_url = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/"

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            print("\n🔍 Descoberta recursiva do ERP...")
            discovered_urls = await crawler._discover_spa_urls_recursive(browser, erp_base_url, max_depth=2)

            await browser.close()

            print("\n📊 RESULTADO:")
            print(f"   URLs descobertas: {len(discovered_urls)}")

            # Group by category
            categories = {}
            for url in discovered_urls:
                if 'cadastros' in url:
                    categories.setdefault('Cadastros', []).append(url)
                elif 'mercado' in url:
                    categories.setdefault('Mercado', []).append(url)
                elif 'financas' in url:
                    categories.setdefault('Finanças', []).append(url)
                elif 'suprimentos' in url:
                    categories.setdefault('Suprimentos', []).append(url)
                elif 'contratos' in url:
                    categories.setdefault('Contratos', []).append(url)
                elif 'banking' in url.lower():
                    categories.setdefault('Banking', []).append(url)
                elif 'controladoria' in url:
                    categories.setdefault('Controladoria', []).append(url)
                elif 'custos' in url:
                    categories.setdefault('Custos', []).append(url)
                else:
                    categories.setdefault('Outros', []).append(url)

            print("\n📊 POR CATEGORIA:")
            for category, urls in sorted(categories.items()):
                print(f"   • {category}: {len(urls)} URLs")
                for url in urls[:5]:  # Show first 5
                    filename = url.split('/')[-1]
                    print(f"      - {filename}")
                if len(urls) > 5:
                    print(f"      ... e mais {len(urls) - 5}")

            print("\n🎯 TODAS AS URLs:")
            for i, url in enumerate(discovered_urls, 1):
                print(f"   {i:2d}. {url}")

    except ImportError:
        print("❌ Playwright não disponível")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_recursive_erp())

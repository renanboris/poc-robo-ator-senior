#!/usr/bin/env python3
"""
Teste de uma página de gestão específica para ver se contém mais links.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler


async def test_gestao_page():
    """Testa uma página de gestão específica."""
    print("=" * 80)
    print("TESTE: PÁGINA DE GESTÃO ESPECÍFICA")
    print("=" * 80)

    # Test specific gestao pages
    gestao_urls = [
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/cadastros/menu-cadastro.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/mercado/gestao-mercado.htm",
        "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/financas/gestao-financas.htm",
    ]

    crawler = SitemapCrawler("dummy")

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for url in gestao_urls:
                print(f"\n🔍 Testando: {url}")

                try:
                    discovered = await crawler._discover_spa_urls_single(browser, url)
                    print(f"   URLs descobertas: {len(discovered)}")

                    for i, found_url in enumerate(discovered[:10], 1):
                        print(f"   {i:2d}. {found_url}")

                    if len(discovered) > 10:
                        print(f"       ... e mais {len(discovered) - 10}")

                except Exception as e:
                    print(f"   ❌ Erro: {e}")

            await browser.close()

    except ImportError:
        print("❌ Playwright não disponível")
    except Exception as e:
        print(f"❌ Erro: {e}")


if __name__ == "__main__":
    asyncio.run(test_gestao_page())

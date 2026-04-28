#!/usr/bin/env python3
"""
Teste da descoberta automática de SPAs.

Este script testa o novo crawler inteligente que descobre automaticamente
todas as URLs de documentação em SPAs (Single Page Applications).
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler


async def test_spa_discovery():
    """Testa a descoberta automática de SPAs."""
    print("=" * 100)
    print("TESTE DE DESCOBERTA AUTOMÁTICA DE SPAs")
    print("=" * 100)
    
    # Initialize crawler
    sitemap_url = "https://documentacao.senior.com.br/sitemap.xml"
    crawler = SitemapCrawler(sitemap_url)
    
    print(f"\n🔍 Testando descoberta de SPAs...")
    
    try:
        # Test SPA discovery only
        spa_urls = await crawler.discover_spa_urls()
        
        print(f"\n📊 RESULTADO DA DESCOBERTA:")
        print(f"   URLs descobertas: {len(spa_urls)}")
        
        if spa_urls:
            print(f"\n🎯 PRIMEIRAS 20 URLs DESCOBERTAS:")
            for i, url in enumerate(spa_urls[:20], 1):
                print(f"  {i:2d}. {url}")
            
            if len(spa_urls) > 20:
                print(f"      ... e mais {len(spa_urls) - 20} URLs")
            
            # Analyze by product
            print(f"\n📊 ANÁLISE POR PRODUTO:")
            products = {}
            for url in spa_urls:
                if 'senior-flow' in url:
                    products['Senior Flow'] = products.get('Senior Flow', 0) + 1
                elif 'ged' in url:
                    products['GED'] = products.get('GED', 0) + 1
                elif 'sign-studio' in url:
                    products['SIGN Studio'] = products.get('SIGN Studio', 0) + 1
                elif 'bpm' in url:
                    products['BPM'] = products.get('BPM', 0) + 1
                elif 'senior-connect' in url:
                    products['Senior Connect'] = products.get('Senior Connect', 0) + 1
                elif 'erp' in url:
                    products['ERP'] = products.get('ERP', 0) + 1
                else:
                    products['Outros'] = products.get('Outros', 0) + 1
            
            for product, count in sorted(products.items(), key=lambda x: x[1], reverse=True):
                print(f"   • {product}: {count} URLs")
        
        else:
            print("   ❌ Nenhuma URL descoberta")
    
    except Exception as e:
        print(f"   ❌ Erro durante descoberta: {e}")
        import traceback
        traceback.print_exc()


async def test_full_crawl():
    """Testa o crawl completo (sitemap + importantes + SPAs)."""
    print("\n" + "=" * 100)
    print("TESTE DE CRAWL COMPLETO")
    print("=" * 100)
    
    # Initialize crawler
    sitemap_url = "https://documentacao.senior.com.br/sitemap.xml"
    crawler = SitemapCrawler(sitemap_url)
    
    print(f"\n🔍 Executando crawl completo...")
    
    try:
        # Full crawl
        all_urls = crawler.crawl()
        
        print(f"\n📊 RESULTADO DO CRAWL COMPLETO:")
        print(f"   Total de URLs: {len(all_urls)}")
        
        # Analyze sources
        sitemap_count = 0
        important_count = 0
        spa_count = 0
        
        # Get individual counts (approximate)
        important_urls = crawler.get_important_urls()
        important_count = len(important_urls)
        
        # Estimate sitemap vs SPA
        for url in all_urls:
            if url in important_urls:
                continue  # Already counted
            elif any(base in url for base in [
                'senior-flow/manual-do-usuario',
                'senior-flow/notas-da-versao',
                'seniorxplatform/manual-do-usuario/ged',
                'seniorxplatform/manual-do-usuario/sign-studio',
                'bpm/7.0.0',
                'seniorxplatform/manual-do-usuario/senior-connect',
                'seniorxplatform/manual-do-usuario/erp'
            ]):
                spa_count += 1
            else:
                sitemap_count += 1
        
        print(f"   • Sitemap: ~{sitemap_count} URLs")
        print(f"   • Importantes: {important_count} URLs")
        print(f"   • SPAs: ~{spa_count} URLs")
        
        # Show sample URLs
        print(f"\n🎯 AMOSTRA DE URLs (primeiras 15):")
        for i, url in enumerate(all_urls[:15], 1):
            print(f"  {i:2d}. {url}")
        
        if len(all_urls) > 15:
            print(f"      ... e mais {len(all_urls) - 15} URLs")
    
    except Exception as e:
        print(f"   ❌ Erro durante crawl: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Função principal."""
    print("Verificando dependências...")
    
    try:
        from playwright.async_api import async_playwright
        print("✅ Playwright disponível")
    except ImportError:
        print("❌ Playwright não encontrado")
        print("   Instale com: py -m pip install playwright")
        print("   Depois execute: py -m playwright install chromium")
        return
    
    # Test SPA discovery
    await test_spa_discovery()
    
    # Test full crawl
    await test_full_crawl()
    
    print(f"\n" + "=" * 100)
    print("TESTE CONCLUÍDO")
    print("=" * 100)


if __name__ == "__main__":
    asyncio.run(main())
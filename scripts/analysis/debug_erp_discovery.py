#!/usr/bin/env python3
"""
Debug da descoberta de URLs do ERP.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler


async def debug_erp_discovery():
    """Debug específico do ERP."""
    print("=" * 80)
    print("DEBUG: DESCOBERTA DE URLs DO ERP")
    print("=" * 80)
    
    # Initialize crawler
    sitemap_url = "https://documentacao.senior.com.br/sitemap.xml"
    crawler = SitemapCrawler(sitemap_url)
    
    # Test ERP SPA specifically
    erp_base_url = "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/"
    
    print(f"\n🔍 Descobrindo URLs no ERP: {erp_base_url}")
    
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Visible browser for debugging
            page = await browser.new_page()
            
            try:
                print("   📱 Carregando página...")
                await page.goto(erp_base_url, wait_until="networkidle", timeout=60000)
                
                print("   ⏳ Aguardando JavaScript...")
                await page.wait_for_timeout(5000)  # Wait longer
                
                print("   🔍 Extraindo conteúdo...")
                content = await page.content()
                
                # Save content for inspection
                with open("erp_page_content.html", "w", encoding="utf-8") as f:
                    f.write(content)
                print("   💾 Conteúdo salvo em: erp_page_content.html")
                
                # Look for navigation structure
                print("   🧭 Analisando estrutura de navegação...")
                
                # Check for common navigation patterns
                nav_selectors = [
                    "nav", ".nav", ".navigation", ".menu",
                    ".sidebar", ".toc", ".table-of-contents",
                    "[role='navigation']", ".tree", ".sitemap"
                ]
                
                for selector in nav_selectors:
                    elements = await page.query_selector_all(selector)
                    if elements:
                        print(f"      ✅ Encontrado: {selector} ({len(elements)} elementos)")
                        
                        # Get text content of first element
                        if elements:
                            text = await elements[0].text_content()
                            if text and len(text) > 50:
                                print(f"         Conteúdo: {text[:100]}...")
                    else:
                        print(f"      ❌ Não encontrado: {selector}")
                
                # Look for links
                print("   🔗 Analisando links...")
                links = await page.query_selector_all("a[href]")
                print(f"      Total de links: {len(links)}")
                
                htm_links = []
                for link in links[:20]:  # First 20 links
                    href = await link.get_attribute("href")
                    text = await link.text_content()
                    if href and ".htm" in href:
                        htm_links.append((href, text.strip()[:50] if text else ""))
                
                print(f"      Links .htm encontrados: {len(htm_links)}")
                for href, text in htm_links[:10]:
                    print(f"         • {href} ({text})")
                
                # Look for JavaScript variables
                print("   📜 Analisando JavaScript...")
                js_result = await page.evaluate("""
                    () => {
                        const result = {
                            scripts: [],
                            variables: [],
                            htm_references: []
                        };
                        
                        // Check scripts
                        const scripts = document.querySelectorAll('script');
                        scripts.forEach((script, i) => {
                            const text = script.textContent || '';
                            if (text.length > 100) {
                                result.scripts.push({
                                    index: i,
                                    length: text.length,
                                    preview: text.substring(0, 200)
                                });
                                
                                // Look for .htm references
                                const htmMatches = text.match(/[^\\s"']+\\.htm[^\\s"']*/g);
                                if (htmMatches) {
                                    result.htm_references.push(...htmMatches);
                                }
                            }
                        });
                        
                        // Check for common navigation variables
                        const navVars = ['toc', 'menu', 'navigation', 'sitemap', 'tree'];
                        navVars.forEach(varName => {
                            if (window[varName]) {
                                result.variables.push(varName);
                            }
                        });
                        
                        return result;
                    }
                """)
                
                print(f"      Scripts encontrados: {len(js_result['scripts'])}")
                for script in js_result['scripts'][:3]:
                    print(f"         Script {script['index']}: {script['length']} chars")
                    print(f"            Preview: {script['preview'][:100]}...")
                
                print(f"      Variáveis de navegação: {js_result['variables']}")
                print(f"      Referências .htm no JS: {len(set(js_result['htm_references']))}")
                
                unique_htm_refs = list(set(js_result['htm_references']))
                for ref in unique_htm_refs[:10]:
                    print(f"         • {ref}")
                
                # Try to click on navigation elements to reveal more content
                print("   🖱️ Tentando expandir navegação...")
                
                expand_selectors = [
                    "button", ".expand", ".toggle", ".accordion",
                    "[aria-expanded='false']", ".collapsed"
                ]
                
                for selector in expand_selectors:
                    try:
                        elements = await page.query_selector_all(selector)
                        if elements:
                            print(f"      Tentando clicar em: {selector} ({len(elements)} elementos)")
                            # Click first few elements
                            for i, element in enumerate(elements[:3]):
                                try:
                                    await element.click()
                                    await page.wait_for_timeout(1000)
                                    print(f"         ✅ Clicou no elemento {i+1}")
                                except Exception as e:
                                    print(f"         ❌ Erro ao clicar no elemento {i+1}: {e}")
                    except Exception as e:
                        print(f"      ❌ Erro com seletor {selector}: {e}")
                
                # Check if more content appeared
                print("   🔍 Verificando conteúdo após cliques...")
                new_links = await page.query_selector_all("a[href*='.htm']")
                print(f"      Links .htm após expansão: {len(new_links)}")
                
                # Extract final URLs
                discovered_urls = await crawler._discover_spa_urls_single(browser, erp_base_url)
                print(f"\n📊 RESULTADO FINAL:")
                print(f"   URLs descobertas: {len(discovered_urls)}")
                
                for i, url in enumerate(discovered_urls[:20], 1):
                    print(f"   {i:2d}. {url}")
                
                if len(discovered_urls) > 20:
                    print(f"       ... e mais {len(discovered_urls) - 20}")
                
            finally:
                await browser.close()
    
    except ImportError:
        print("❌ Playwright não disponível")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(debug_erp_discovery())
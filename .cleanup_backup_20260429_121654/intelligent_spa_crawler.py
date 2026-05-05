"""Intelligent SPA crawler that discovers all .htm files automatically."""

import asyncio
import re
from typing import List, Set
from urllib.parse import unquote, urljoin

import requests
from playwright.async_api import async_playwright


class IntelligentSPACrawler:
    """Crawler that automatically discovers all documentation URLs in SPAs."""

    def __init__(self):
        self.discovered_urls: Set[str] = set()

        # Base URLs to crawl (SPAs)
        self.spa_base_urls = [
            "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/",
            "https://documentacao.senior.com.br/senior-flow/notas-da-versao/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/",
            "https://documentacao.senior.com.br/bpm/7.0.0/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/",
        ]

    async def discover_spa_urls(self, base_url: str) -> List[str]:
        """Discover all .htm URLs in a SPA using Playwright."""
        print(f"\n🔍 Descobrindo URLs em: {base_url}")

        discovered = []

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # Navigate to SPA
                await page.goto(base_url, wait_until="networkidle", timeout=30000)

                # Wait for JavaScript to load content
                await page.wait_for_timeout(3000)

                # Method 1: Extract from page content
                content = await page.content()

                # Find all href patterns with .htm
                htm_patterns = [
                    r'href=["\']([^"\']*\.htm[^"\']*)["\']',  # href="file.htm"
                    r'#([^"\']*\.htm[^"\']*)',  # #path/file.htm
                    r'([^"\'\s]*\.htm)',  # any .htm reference
                ]

                for pattern in htm_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    for match in matches:
                        # Clean and resolve URL
                        if match.startswith('#'):
                            # Fragment URL
                            file_path = match[1:]  # Remove #
                            file_path = unquote(file_path)  # Decode %20 etc
                            full_url = urljoin(base_url, file_path)
                        elif match.startswith('http'):
                            # Absolute URL
                            full_url = match
                        else:
                            # Relative URL
                            full_url = urljoin(base_url, match)

                        # Only include URLs under the base
                        if full_url.startswith(base_url) and full_url.endswith('.htm'):
                            discovered.append(full_url)

                # Method 2: Execute JavaScript to find navigation links
                try:
                    js_links = await page.evaluate(r"""
                        () => {
                            const links = [];
                            
                            // Find all links
                            const anchors = document.querySelectorAll('a[href]');
                            anchors.forEach(a => {
                                const href = a.getAttribute('href');
                                if (href && href.includes('.htm')) {
                                    links.push(href);
                                }
                            });
                            
                            // Find navigation data in JavaScript variables
                            const scripts = document.querySelectorAll('script');
                            scripts.forEach(script => {
                                const text = script.textContent || '';
                                
                                // Look for common patterns
                                const patterns = [
                                    /["']([^"']*\.htm[^"']*)["']/g,
                                    /url:\s*["']([^"']*\.htm[^"']*)["']/g,
                                    /path:\s*["']([^"']*\.htm[^"']*)["']/g,
                                ];
                                
                                patterns.forEach(pattern => {
                                    let match;
                                    while ((match = pattern.exec(text)) !== null) {
                                        links.push(match[1]);
                                    }
                                });
                            });
                            
                            return [...new Set(links)]; // Remove duplicates
                        }
                    """)

                    # Process JavaScript-discovered links
                    for link in js_links:
                        if link.startswith('#'):
                            file_path = link[1:]
                            file_path = unquote(file_path)
                            full_url = urljoin(base_url, file_path)
                        elif link.startswith('http'):
                            full_url = link
                        else:
                            full_url = urljoin(base_url, link)

                        if full_url.startswith(base_url) and full_url.endswith('.htm'):
                            discovered.append(full_url)

                except Exception as e:
                    print(f"    ⚠️ JavaScript execution failed: {e}")

            except Exception as e:
                print(f"    ❌ Failed to load {base_url}: {e}")

            finally:
                await browser.close()

        # Remove duplicates and sort
        unique_discovered = list(set(discovered))
        unique_discovered.sort()

        print(f"    ✅ Descobertas {len(unique_discovered)} URLs")

        # Show first few examples
        for url in unique_discovered[:5]:
            print(f"      • {url}")
        if len(unique_discovered) > 5:
            print(f"      ... e mais {len(unique_discovered) - 5}")

        return unique_discovered

    def validate_discovered_urls(self, urls: List[str]) -> List[str]:
        """Validate that discovered URLs are accessible."""
        print(f"\n🔍 Validando {len(urls)} URLs descobertas...")

        valid_urls = []

        for i, url in enumerate(urls):
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                if response.status_code == 200:
                    valid_urls.append(url)
                    if i < 10:  # Show first 10
                        print(f"    ✅ {url}")
                elif i < 10:
                    print(f"    ❌ {url} (Status: {response.status_code})")
            except Exception as e:
                if i < 10:
                    print(f"    ❌ {url} (Erro: {str(e)[:50]})")

        if len(urls) > 10:
            print(f"    ... validando mais {len(urls) - 10} URLs...")

        print(f"    📊 {len(valid_urls)}/{len(urls)} URLs válidas ({len(valid_urls)/len(urls)*100:.1f}%)")

        return valid_urls

    async def crawl_all_spas(self) -> List[str]:
        """Crawl all SPA base URLs and discover documentation."""
        print("=" * 100)
        print("CRAWLER INTELIGENTE DE SPAs - DESCOBERTA AUTOMÁTICA")
        print("=" * 100)

        all_discovered = []

        for base_url in self.spa_base_urls:
            try:
                discovered = await self.discover_spa_urls(base_url)
                all_discovered.extend(discovered)
            except Exception as e:
                print(f"❌ Erro em {base_url}: {e}")

        # Remove duplicates
        unique_urls = list(set(all_discovered))
        unique_urls.sort()

        print("\n" + "=" * 100)
        print("RESUMO DA DESCOBERTA")
        print("=" * 100)
        print(f"URLs descobertas: {len(unique_urls)}")

        # Validate URLs
        valid_urls = self.validate_discovered_urls(unique_urls)

        print("\n📋 RESULTADO FINAL:")
        print(f"   URLs descobertas: {len(unique_urls)}")
        print(f"   URLs válidas: {len(valid_urls)}")
        print(f"   Taxa de sucesso: {len(valid_urls)/len(unique_urls)*100:.1f}%")

        return valid_urls


# Test the intelligent crawler
async def main():
    crawler = IntelligentSPACrawler()
    discovered_urls = await crawler.crawl_all_spas()

    print("\n🎯 PRIMEIRAS 20 URLs VÁLIDAS:")
    for i, url in enumerate(discovered_urls[:20], 1):
        print(f"  {i}. {url}")

    if len(discovered_urls) > 20:
        print(f"  ... e mais {len(discovered_urls) - 20} URLs")

    # Analyze by product
    print("\n📊 ANÁLISE POR PRODUTO:")
    products = {}
    for url in discovered_urls:
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

if __name__ == "__main__":
    asyncio.run(main())

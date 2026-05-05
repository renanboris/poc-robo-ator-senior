"""Enhanced crawler that discovers .htm files in important directories."""

import re
import time
from typing import List, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class EnhancedSitemapCrawler:
    """Enhanced crawler that discovers documentation in important directories."""

    def __init__(self, sitemap_url: str):
        self.sitemap_url = sitemap_url
        self.discovered_urls: Set[str] = set()

        # URLs importantes para crawl recursivo
        self.important_base_urls = [
            "https://documentacao.senior.com.br/senior-flow/manual-do-usuario/",
            "https://documentacao.senior.com.br/senior-flow/notas-da-versao/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/ged/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/sign-studio/",
            "https://documentacao.senior.com.br/bpm/7.0.0/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/senior-connect/",
            "https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/erp/",
        ]

    def fetch_sitemap_urls(self) -> List[str]:
        """Fetch URLs from sitemap.xml."""
        print("Fetching sitemap URLs...")

        try:
            response = requests.get(self.sitemap_url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml-xml')
            loc_tags = soup.find_all('loc')
            urls = [loc.get_text().strip() for loc in loc_tags]

            # Filter to .htm/.html only
            html_urls = [url for url in urls if url.endswith('.htm') or url.endswith('.html')]

            print(f"Found {len(html_urls)} HTML URLs in sitemap")
            return html_urls

        except Exception as e:
            print(f"Error fetching sitemap: {e}")
            return []

    def discover_htm_files_in_directory(self, base_url: str, max_depth: int = 3) -> List[str]:
        """Recursively discover .htm files in a directory."""
        print(f"\nDiscovering files in: {base_url}")

        discovered = []
        visited = set()
        to_visit = [(base_url, 0)]  # (url, depth)

        while to_visit:
            current_url, depth = to_visit.pop(0)

            if depth > max_depth or current_url in visited:
                continue

            visited.add(current_url)

            try:
                print(f"  Scanning: {current_url} (depth {depth})")
                response = requests.get(current_url, timeout=10)

                if response.status_code != 200:
                    continue

                # Parse HTML to find links
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find all links
                links = soup.find_all('a', href=True)

                for link in links:
                    href = link['href']

                    # Skip external links, anchors, and javascript
                    if href.startswith(('http://', 'https://', 'javascript:', 'mailto:', '#')):
                        if not href.startswith(base_url):
                            continue

                    # Resolve relative URLs
                    full_url = urljoin(current_url, href)

                    # Only process URLs under the base directory
                    if not full_url.startswith(base_url):
                        continue

                    # If it's an .htm/.html file, add to discovered
                    if full_url.endswith('.htm') or full_url.endswith('.html'):
                        if full_url not in discovered:
                            discovered.append(full_url)
                            print(f"    ✅ Found: {full_url}")

                    # If it's a directory (ends with /), add to visit queue
                    elif full_url.endswith('/') and depth < max_depth:
                        to_visit.append((full_url, depth + 1))

                # Also try to find .htm files by scanning the directory listing
                # Look for patterns like: href="file.htm"
                htm_pattern = r'href=["\']([^"\']*\.htm[^"\']*)["\']'
                htm_matches = re.findall(htm_pattern, response.text, re.IGNORECASE)

                for match in htm_matches:
                    full_url = urljoin(current_url, match)
                    if full_url.startswith(base_url) and full_url not in discovered:
                        discovered.append(full_url)
                        print(f"    ✅ Pattern match: {full_url}")

                # Small delay to be respectful
                time.sleep(0.1)

            except Exception as e:
                print(f"    ❌ Error scanning {current_url}: {str(e)[:100]}")
                continue

        print(f"  Discovered {len(discovered)} files in {base_url}")
        return discovered

    def crawl_enhanced(self) -> List[str]:
        """Enhanced crawl: sitemap + recursive discovery."""
        print("=" * 100)
        print("ENHANCED CRAWLER - DESCOBRINDO DOCUMENTAÇÃO COMPLETA")
        print("=" * 100)

        all_urls = []

        # 1. Get URLs from sitemap
        sitemap_urls = self.fetch_sitemap_urls()
        all_urls.extend(sitemap_urls)
        print(f"\n✅ Sitemap: {len(sitemap_urls)} URLs")

        # 2. Discover URLs in important directories
        print(f"\n🔍 Descobrindo arquivos em {len(self.important_base_urls)} diretórios importantes...")

        for base_url in self.important_base_urls:
            try:
                discovered = self.discover_htm_files_in_directory(base_url)

                # Add new URLs (avoid duplicates)
                new_urls = [url for url in discovered if url not in all_urls]
                all_urls.extend(new_urls)

                print(f"✅ {base_url}: +{len(new_urls)} novas URLs")

            except Exception as e:
                print(f"❌ {base_url}: Erro - {e}")

        # 3. Remove duplicates and sort
        unique_urls = list(set(all_urls))
        unique_urls.sort()

        print("\n" + "=" * 100)
        print("RESULTADO FINAL")
        print("=" * 100)
        print(f"URLs do sitemap: {len(sitemap_urls)}")
        print(f"URLs descobertas: {len(unique_urls) - len(sitemap_urls)}")
        print(f"Total de URLs: {len(unique_urls)}")

        return unique_urls


# Test the enhanced crawler
if __name__ == "__main__":
    crawler = EnhancedSitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")
    urls = crawler.crawl_enhanced()

    print("\n📋 PRIMEIRAS 20 URLs DESCOBERTAS:")
    for i, url in enumerate(urls[:20], 1):
        print(f"  {i}. {url}")

    if len(urls) > 20:
        print(f"  ... e mais {len(urls) - 20} URLs")

    # Check if important URLs were found
    print("\n🎯 VERIFICAÇÃO DE URLs IMPORTANTES:")
    important_terms = ["senior-flow", "ged", "sign-studio", "bpm", "senior-connect", "erp"]

    for term in important_terms:
        matching = [url for url in urls if term in url.lower()]
        if matching:
            print(f"✅ {term}: {len(matching)} URLs encontradas")
        else:
            print(f"❌ {term}: Nenhuma URL encontrada")

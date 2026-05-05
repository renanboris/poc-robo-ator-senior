"""Test sitemap URL structure to identify modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ingestion_pipeline.crawler import SitemapCrawler
from ingestion_pipeline.extractor import SemanticExtractor

# Crawl sitemap
crawler = SitemapCrawler("https://documentacao.senior.com.br/sitemap.xml")
urls = crawler.crawl()

print(f"Total URLs: {len(urls)}\n")

# Extract unique nivel_2 values
extractor = SemanticExtractor(extraction_backend="crawl4ai")
nivel_2_counts = {}

for url in urls[:50]:  # Sample first 50 URLs
    breadcrumbs = extractor.extract_breadcrumbs(url)
    nivel_2 = breadcrumbs["nivel_2"]

    if nivel_2:
        nivel_2_counts[nivel_2] = nivel_2_counts.get(nivel_2, 0) + 1

print("Unique nivel_2 values (from first 50 URLs):")
for nivel_2, count in sorted(nivel_2_counts.items(), key=lambda x: x[1], reverse=True):
    print(f"  {nivel_2}: {count} URLs")

# Show some example URLs
print("\nExample URLs:")
for url in urls[:10]:
    breadcrumbs = extractor.extract_breadcrumbs(url)
    print(f"  {url}")
    print(f"    nivel_1: {breadcrumbs['nivel_1']}, nivel_2: {breadcrumbs['nivel_2']}, nivel_3: {breadcrumbs['nivel_3']}")

"""Demo script for SitemapCrawler.

This script demonstrates the usage of the SitemapCrawler class
to discover documentation URLs from a sitemap.xml file.

Usage:
    python -m ingestion_pipeline.demo_crawler
"""

import logging
from ingestion_pipeline.crawler import SitemapCrawler
from ingestion_pipeline.utils import setup_logging


def main():
    """Run SitemapCrawler demo."""
    # Setup logging
    setup_logging(level="INFO", json_format=False)
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 60)
    logger.info("SitemapCrawler Demo")
    logger.info("=" * 60)
    
    # Example sitemap URL (replace with actual sitemap URL)
    sitemap_url = "https://docs.senior.com.br/sitemap.xml"
    
    logger.info(f"\nCrawling sitemap: {sitemap_url}")
    
    # Create crawler instance
    crawler = SitemapCrawler(sitemap_url)
    
    # Execute crawl
    try:
        urls = crawler.crawl()
        
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Crawl Results")
        logger.info(f"{'=' * 60}")
        logger.info(f"Total documentation URLs discovered: {len(urls)}")
        
        if urls:
            logger.info(f"\nFirst 10 URLs:")
            for i, url in enumerate(urls[:10], 1):
                logger.info(f"  {i}. {url}")
            
            if len(urls) > 10:
                logger.info(f"\n  ... and {len(urls) - 10} more URLs")
        else:
            logger.info("\nNo URLs discovered (check sitemap URL or network connection)")
    
    except Exception as e:
        logger.error(f"\nCrawl failed: {e}")
        return 1
    
    logger.info(f"\n{'=' * 60}")
    logger.info("Demo completed")
    logger.info(f"{'=' * 60}")
    
    return 0


if __name__ == "__main__":
    exit(main())

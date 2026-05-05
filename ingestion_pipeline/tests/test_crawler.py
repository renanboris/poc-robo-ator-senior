"""Unit tests for SitemapCrawler."""

from unittest.mock import Mock, patch

import pytest
import requests

from ingestion_pipeline.crawler import SitemapCrawler


class TestSitemapCrawler:
    """Test suite for SitemapCrawler class."""

    def test_init(self):
        """Test crawler initialization."""
        sitemap_url = "https://example.com/sitemap.xml"
        crawler = SitemapCrawler(sitemap_url)
        assert crawler.sitemap_url == sitemap_url

    def test_parse_sitemap(self):
        """Test XML parsing extracts URLs correctly."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/senior-x/hcm/admissao</loc>
            </url>
            <url>
                <loc>https://example.com/produto/erp/financeiro</loc>
            </url>
            <url>
                <loc>https://example.com/termos-de-uso</loc>
            </url>
        </urlset>
        """

        urls = crawler.parse_sitemap(xml_content)

        assert len(urls) == 3
        assert "https://example.com/senior-x/hcm/admissao" in urls
        assert "https://example.com/produto/erp/financeiro" in urls
        assert "https://example.com/termos-de-uso" in urls

    def test_filter_urls_include_patterns(self):
        """Test URL filtering includes /senior-x/* and /produto/* patterns."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        urls = [
            "https://example.com/senior-x/hcm/admissao",
            "https://example.com/produto/erp/financeiro",
            "https://example.com/blog/article",
            "https://example.com/senior-x/ged/documentos",
        ]

        filtered = crawler.filter_urls(urls)

        assert len(filtered) == 3
        assert "https://example.com/senior-x/hcm/admissao" in filtered
        assert "https://example.com/produto/erp/financeiro" in filtered
        assert "https://example.com/senior-x/ged/documentos" in filtered
        assert "https://example.com/blog/article" not in filtered

    def test_filter_urls_exclude_keywords(self):
        """Test URL filtering excludes non-documentation pages."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        urls = [
            "https://example.com/senior-x/hcm/admissao",
            "https://example.com/termos-de-uso",
            "https://example.com/politica-privacidade",
            "https://example.com/contato",
            "https://example.com/home",
            "https://example.com/sobre",
            "https://example.com/produto/erp/financeiro",
        ]

        filtered = crawler.filter_urls(urls)

        assert len(filtered) == 2
        assert "https://example.com/senior-x/hcm/admissao" in filtered
        assert "https://example.com/produto/erp/financeiro" in filtered
        assert "https://example.com/termos-de-uso" not in filtered
        assert "https://example.com/politica-privacidade" not in filtered
        assert "https://example.com/contato" not in filtered
        assert "https://example.com/home" not in filtered
        assert "https://example.com/sobre" not in filtered

    def test_filter_urls_case_insensitive(self):
        """Test URL filtering is case-insensitive."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        urls = [
            "https://example.com/Senior-X/HCM/Admissao",
            "https://example.com/PRODUTO/ERP/Financeiro",
            "https://example.com/Termos-De-Uso",
        ]

        filtered = crawler.filter_urls(urls)

        assert len(filtered) == 2
        assert "https://example.com/Senior-X/HCM/Admissao" in filtered
        assert "https://example.com/PRODUTO/ERP/Financeiro" in filtered
        assert "https://example.com/Termos-De-Uso" not in filtered

    @patch('ingestion_pipeline.crawler.requests.get')
    def test_fetch_sitemap_success(self, mock_get):
        """Test successful sitemap fetch."""
        mock_response = Mock()
        mock_response.text = "<urlset></urlset>"
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        crawler = SitemapCrawler("https://example.com/sitemap.xml")
        xml_content = crawler.fetch_sitemap()

        assert xml_content == "<urlset></urlset>"
        mock_get.assert_called_once()

    @patch('ingestion_pipeline.crawler.requests.get')
    def test_fetch_sitemap_retry_on_failure(self, mock_get):
        """Test sitemap fetch retries on transient failures."""
        # First two calls fail, third succeeds
        mock_get.side_effect = [
            requests.RequestException("Network error"),
            requests.RequestException("Timeout"),
            Mock(text="<urlset></urlset>", raise_for_status=Mock())
        ]

        crawler = SitemapCrawler("https://example.com/sitemap.xml")
        xml_content = crawler.fetch_sitemap()

        assert xml_content == "<urlset></urlset>"
        assert mock_get.call_count == 3

    @patch('ingestion_pipeline.crawler.requests.get')
    def test_fetch_sitemap_fails_after_retries(self, mock_get):
        """Test sitemap fetch raises exception after all retries fail."""
        mock_get.side_effect = requests.RequestException("Persistent error")

        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        with pytest.raises(requests.RequestException):
            crawler.fetch_sitemap()

        assert mock_get.call_count == 3

    @patch('ingestion_pipeline.crawler.requests.get')
    def test_crawl_full_workflow(self, mock_get):
        """Test complete crawl workflow: fetch → parse → filter."""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
            <url>
                <loc>https://example.com/senior-x/hcm/admissao</loc>
            </url>
            <url>
                <loc>https://example.com/produto/erp/financeiro</loc>
            </url>
            <url>
                <loc>https://example.com/termos-de-uso</loc>
            </url>
            <url>
                <loc>https://example.com/blog/article</loc>
            </url>
        </urlset>
        """

        mock_response = Mock()
        mock_response.text = xml_content
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        crawler = SitemapCrawler("https://example.com/sitemap.xml")
        urls = crawler.crawl()

        assert len(urls) == 2
        assert "https://example.com/senior-x/hcm/admissao" in urls
        assert "https://example.com/produto/erp/financeiro" in urls
        assert "https://example.com/termos-de-uso" not in urls
        assert "https://example.com/blog/article" not in urls

    @patch('ingestion_pipeline.crawler.requests.get')
    def test_crawl_returns_empty_on_failure(self, mock_get):
        """Test crawl returns empty list on fatal failure."""
        mock_get.side_effect = requests.RequestException("Fatal error")

        crawler = SitemapCrawler("https://example.com/sitemap.xml")
        urls = crawler.crawl()

        assert urls == []

    def test_parse_sitemap_handles_malformed_xml(self):
        """Test parse_sitemap handles malformed XML gracefully."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        malformed_xml = "This is not valid XML"
        urls = crawler.parse_sitemap(malformed_xml)

        assert urls == []

    def test_filter_urls_empty_list(self):
        """Test filter_urls handles empty input list."""
        crawler = SitemapCrawler("https://example.com/sitemap.xml")

        filtered = crawler.filter_urls([])

        assert filtered == []

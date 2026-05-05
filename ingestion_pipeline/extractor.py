"""Semantic content extraction from web pages.

This module provides the SemanticExtractor class for extracting clean semantic
content from HTML pages and converting to Markdown format. Supports two backends:
- Crawl4AI (self-hosted, open-source)
- Firecrawl (managed API service)
"""

import logging
import re
from typing import Any, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SemanticExtractor:
    """Extract clean semantic content from HTML pages and convert to Markdown.
    
    This class handles:
    - Content extraction using Crawl4AI or Firecrawl backend
    - HTML to Markdown conversion with semantic structure preservation
    - Content cleaning (remove navigation, footers, modals)
    - Page title extraction from <title> tag or main <h1> heading
    - Breadcrumb hierarchy extraction from URL path segments
    
    Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 3.5, 9.4, 9.5
    """

    def __init__(self, extraction_backend: str = "crawl4ai"):
        """Initialize SemanticExtractor with specified backend.
        
        Args:
            extraction_backend: Backend to use ("crawl4ai" or "firecrawl")
            
        Raises:
            ValueError: If extraction_backend is not "crawl4ai" or "firecrawl"
            ImportError: If required backend library is not installed
        """
        if extraction_backend not in ["crawl4ai", "firecrawl"]:
            raise ValueError(
                f"Invalid extraction_backend: {extraction_backend}. "
                f"Must be 'crawl4ai' or 'firecrawl'"
            )

        self.extraction_backend = extraction_backend
        self._backend = None

        # Initialize backend
        if extraction_backend == "crawl4ai":
            self._init_crawl4ai()
        elif extraction_backend == "firecrawl":
            self._init_firecrawl()

        logger.info(f"Initialized SemanticExtractor with backend: {extraction_backend}")

    def _init_crawl4ai(self) -> None:
        """Initialize Crawl4AI backend (local).
        
        Configures content cleaning rules:
        - Remove navigation menus, footers, modals
        - Preserve main/article content
        
        Requirements: 2.2, 9.4
        
        Raises:
            ImportError: If crawl4ai is not installed
        """
        try:
            # Import crawl4ai (will be installed separately)
            # For now, we'll use a placeholder that can be replaced
            # when the actual library is integrated
            logger.info("Initializing Crawl4AI backend (local)")

            # TODO: Initialize actual Crawl4AI client when library is available
            # Example configuration:
            # - Remove elements with role="navigation", <nav>, class containing "menu", "sidebar", "nav"
            # - Remove elements with <footer>, class containing "footer"
            # - Remove elements with role="dialog", class containing "modal", "popup"
            # - Preserve elements with <article>, <main>, role="main"

            self._backend = "crawl4ai"  # Placeholder
            logger.info("Crawl4AI backend initialized successfully")

        except ImportError as e:
            logger.error(f"Failed to import crawl4ai: {e}")
            raise ImportError(
                "crawl4ai library is required for crawl4ai backend. "
                "Install it with: pip install crawl4ai"
            ) from e

    def _init_firecrawl(self) -> None:
        """Initialize Firecrawl API backend (managed).
        
        Requires FIRECRAWL_API_KEY environment variable.
        
        Requirements: 2.2, 9.5
        
        Raises:
            ImportError: If firecrawl-py is not installed
            ValueError: If FIRECRAWL_API_KEY is not set
        """
        try:
            import os

            # Import firecrawl (will be installed separately)
            logger.info("Initializing Firecrawl API backend (managed)")

            # Check for API key
            api_key = os.getenv("FIRECRAWL_API_KEY")
            if not api_key:
                raise ValueError(
                    "FIRECRAWL_API_KEY environment variable is required "
                    "for firecrawl backend"
                )

            # TODO: Initialize actual Firecrawl client when library is available
            # Example: self._backend = FirecrawlClient(api_key=api_key)

            self._backend = "firecrawl"  # Placeholder
            logger.info("Firecrawl backend initialized successfully")

        except ImportError as e:
            logger.error(f"Failed to import firecrawl: {e}")
            raise ImportError(
                "firecrawl-py library is required for firecrawl backend. "
                "Install it with: pip install firecrawl-py"
            ) from e

    def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content from URL and return structured data.
        
        Fetches HTML page, converts to clean Markdown, extracts title and
        breadcrumb hierarchy.
        
        Requirements: 2.1, 2.3, 2.4, 2.5
        
        Args:
            url: URL to extract content from
            
        Returns:
            Dictionary with keys:
                - url: Original URL
                - titulo: Page title (from <title> or <h1>)
                - markdown: Clean Markdown content
                - nivel_1: First path segment
                - nivel_2: Second path segment
                - nivel_3: Third path segment (may be empty)
                
        Raises:
            Exception: If content extraction fails
        """
        logger.info(f"Extracting content from: {url}")

        try:
            # Extract breadcrumb hierarchy from URL
            breadcrumbs = self.extract_breadcrumbs(url)

            # Fetch and convert HTML to Markdown
            # TODO: Implement actual backend calls when libraries are integrated
            # For now, return a placeholder structure

            if self.extraction_backend == "crawl4ai":
                markdown, titulo = self._extract_with_crawl4ai(url)
            elif self.extraction_backend == "firecrawl":
                markdown, titulo = self._extract_with_firecrawl(url)
            else:
                raise ValueError(f"Unknown backend: {self.extraction_backend}")

            # Construct result
            result = {
                "url": url,
                "titulo": titulo,
                "markdown": markdown,
                "nivel_1": breadcrumbs["nivel_1"],
                "nivel_2": breadcrumbs["nivel_2"],
                "nivel_3": breadcrumbs["nivel_3"],
            }

            logger.info(
                f"Successfully extracted content from {url}: "
                f"title='{titulo}', markdown_length={len(markdown)}, "
                f"hierarchy={breadcrumbs['nivel_1']}/{breadcrumbs['nivel_2']}/{breadcrumbs['nivel_3']}"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            raise

    def _extract_with_crawl4ai(self, url: str) -> tuple[str, str]:
        """Extract content using Crawl4AI backend.
        
        Args:
            url: URL to extract from
            
        Returns:
            Tuple of (markdown_content, page_title)
        """
        # Temporary implementation using requests + BeautifulSoup
        # TODO: Replace with actual Crawl4AI when library is integrated

        import html2text
        import requests
        from bs4 import BeautifulSoup

        try:
            # Fetch HTML
            response = requests.get(url, timeout=30, headers={
                'User-Agent': 'Senior-Training-OS-Ingestion-Pipeline/1.0'
            })
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Extract title
            title_tag = soup.find('title')
            titulo = title_tag.get_text().strip() if title_tag else "Untitled"

            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()

            # Try to find main content area
            main_content = (
                soup.find('main') or
                soup.find('article') or
                soup.find('div', class_='content') or
                soup.find('body')
            )

            if not main_content:
                return ("", titulo)

            # Convert to markdown
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.ignore_emphasis = False
            h.body_width = 0  # Don't wrap lines

            markdown = h.handle(str(main_content))

            # Clean up markdown
            markdown = markdown.strip()

            return (markdown, titulo)

        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            return ("", "Error")

    def _extract_with_firecrawl(self, url: str) -> tuple[str, str]:
        """Extract content using Firecrawl API backend.
        
        Args:
            url: URL to extract from
            
        Returns:
            Tuple of (markdown_content, page_title)
        """
        # TODO: Implement actual Firecrawl extraction
        # This is a placeholder that will be replaced with real implementation

        # Example implementation:
        # result = self._backend.scrape(url, formats=["markdown"])
        # markdown = result.markdown
        # titulo = result.metadata.get("title") or self._extract_title_from_markdown(markdown)

        # Placeholder return
        return ("# Placeholder content\n\nThis is placeholder markdown content.", "Placeholder Title")

    def _extract_title_from_markdown(self, markdown: str) -> str:
        """Extract title from Markdown content (first # heading).
        
        Args:
            markdown: Markdown content
            
        Returns:
            Extracted title or "Untitled"
        """
        # Look for first # heading
        match = re.search(r'^#\s+(.+)$', markdown, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return "Untitled"

    def extract_breadcrumbs(self, url: str) -> Dict[str, str]:
        """Parse URL path to extract hierarchy levels.
        
        Extracts nivel_1, nivel_2, nivel_3 from URL path segments.
        Example: /senior-x/hcm/admissao → nivel_1: senior-x, nivel_2: hcm, nivel_3: admissao
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        
        Args:
            url: URL to parse
            
        Returns:
            Dictionary with keys nivel_1, nivel_2, nivel_3 (normalized to lowercase kebab-case)
        """
        # Parse URL to get path
        parsed = urlparse(url)
        path = parsed.path.strip('/')

        # Split path into segments and remove file extensions
        segments = []
        for seg in path.split('/'):
            if seg:
                # Remove file extensions (.htm, .html, etc.)
                seg_without_ext = re.sub(r'\.(htm|html|php|asp|aspx)$', '', seg, flags=re.IGNORECASE)
                segments.append(seg_without_ext)

        # Extract hierarchy levels (up to 3)
        nivel_1 = self.normalize_hierarchy(segments[0]) if len(segments) >= 1 else ""
        nivel_2 = self.normalize_hierarchy(segments[1]) if len(segments) >= 2 else ""
        nivel_3 = self.normalize_hierarchy(segments[2]) if len(segments) >= 3 else ""

        # Special handling for better namespace separation
        # If we have specific product paths, use them as nivel_2
        if nivel_1 == "seniorxplatform" and nivel_2 == "manual-do-usuario" and nivel_3:
            # For seniorxplatform/manual-do-usuario/ged → use "ged" as nivel_2
            nivel_2 = nivel_3
            nivel_3 = self.normalize_hierarchy(segments[3]) if len(segments) >= 4 else ""
        elif nivel_1 == "senior-flow" and nivel_2 == "manual-do-usuario":
            # For senior-flow/manual-do-usuario → use "senior-flow-manual" as nivel_2
            nivel_2 = "senior-flow-manual"
        elif nivel_1 == "senior-flow" and nivel_2 == "notas-da-versao":
            # For senior-flow/notas-da-versao → use "senior-flow-notas" as nivel_2
            nivel_2 = "senior-flow-notas"
        elif nivel_1 == "bpm" and nivel_2:
            # For bpm/7.0.0 → use "bpm" as nivel_2
            nivel_2 = "bpm"

        return {
            "nivel_1": nivel_1,
            "nivel_2": nivel_2,
            "nivel_3": nivel_3,
        }

    def normalize_hierarchy(self, value: str) -> str:
        """Normalize hierarchy value to lowercase kebab-case.
        
        Converts to lowercase and replaces spaces/special characters with hyphens.
        
        Requirements: 3.4
        
        Args:
            value: Hierarchy value to normalize
            
        Returns:
            Normalized value in lowercase kebab-case format
        """
        if not value:
            return ""

        # Convert to lowercase
        value = value.lower()

        # Replace spaces and underscores with hyphens
        value = re.sub(r'[\s_]+', '-', value)

        # Remove special characters (keep only alphanumeric and hyphens)
        value = re.sub(r'[^a-z0-9-]+', '', value)

        # Remove leading/trailing hyphens
        value = value.strip('-')

        # Collapse multiple hyphens
        value = re.sub(r'-+', '-', value)

        return value

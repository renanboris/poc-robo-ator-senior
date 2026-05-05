"""Unit tests for SemanticExtractor."""

import pytest

from ingestion_pipeline.extractor import SemanticExtractor


class TestSemanticExtractorInit:
    """Test SemanticExtractor initialization."""

    def test_init_with_crawl4ai_backend(self):
        """Verify initialization with crawl4ai backend."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        assert extractor.extraction_backend == "crawl4ai"
        assert extractor._backend is not None

    def test_init_with_firecrawl_backend_missing_key(self, monkeypatch):
        """Verify initialization fails when FIRECRAWL_API_KEY is missing."""
        # Remove FIRECRAWL_API_KEY from environment
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)

        with pytest.raises(ValueError, match="FIRECRAWL_API_KEY"):
            SemanticExtractor(extraction_backend="firecrawl")

    def test_init_with_invalid_backend(self):
        """Verify initialization fails with invalid backend."""
        with pytest.raises(ValueError, match="Invalid extraction_backend"):
            SemanticExtractor(extraction_backend="invalid")


class TestExtractBreadcrumbs:
    """Test breadcrumb hierarchy extraction from URLs."""

    def test_extract_breadcrumbs_three_levels(self):
        """Verify extraction of 3-level hierarchy."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x/hcm/admissao"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == "hcm"
        assert result["nivel_3"] == "admissao"

    def test_extract_breadcrumbs_two_levels(self):
        """Verify extraction with only 2 levels (nivel_3 empty)."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/produto/erp"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "produto"
        assert result["nivel_2"] == "erp"
        assert result["nivel_3"] == ""

    def test_extract_breadcrumbs_one_level(self):
        """Verify extraction with only 1 level (nivel_2 and nivel_3 empty)."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == ""
        assert result["nivel_3"] == ""

    def test_extract_breadcrumbs_with_trailing_slash(self):
        """Verify extraction handles trailing slash correctly."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x/hcm/admissao/"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == "hcm"
        assert result["nivel_3"] == "admissao"

    def test_extract_breadcrumbs_with_query_params(self):
        """Verify extraction ignores query parameters."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x/hcm/admissao?version=2.0"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == "hcm"
        assert result["nivel_3"] == "admissao"

    def test_extract_breadcrumbs_more_than_three_levels(self):
        """Verify extraction only takes first 3 levels."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x/hcm/admissao/colaborador/dados"

        result = extractor.extract_breadcrumbs(url)

        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == "hcm"
        assert result["nivel_3"] == "admissao"


class TestNormalizeHierarchy:
    """Test hierarchy value normalization."""

    def test_normalize_lowercase(self):
        """Verify normalization converts to lowercase."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("Senior-X")

        assert result == "senior-x"

    def test_normalize_spaces_to_hyphens(self):
        """Verify normalization converts spaces to hyphens."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("human resources")

        assert result == "human-resources"

    def test_normalize_underscores_to_hyphens(self):
        """Verify normalization converts underscores to hyphens."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("senior_x_hcm")

        assert result == "senior-x-hcm"

    def test_normalize_remove_special_chars(self):
        """Verify normalization removes special characters."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("senior@x#module!")

        assert result == "seniorxmodule"

    def test_normalize_collapse_multiple_hyphens(self):
        """Verify normalization collapses multiple hyphens."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("senior---x")

        assert result == "senior-x"

    def test_normalize_strip_leading_trailing_hyphens(self):
        """Verify normalization strips leading/trailing hyphens."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("-senior-x-")

        assert result == "senior-x"

    def test_normalize_empty_string(self):
        """Verify normalization handles empty string."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("")

        assert result == ""

    def test_normalize_already_normalized(self):
        """Verify normalization is idempotent."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")

        result = extractor.normalize_hierarchy("senior-x")

        assert result == "senior-x"


class TestExtractContent:
    """Test content extraction from URLs."""

    def test_extract_content_structure(self):
        """Verify extract_content returns correct structure."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/senior-x/hcm/admissao"

        result = extractor.extract_content(url)

        # Verify all required fields are present
        assert "url" in result
        assert "titulo" in result
        assert "markdown" in result
        assert "nivel_1" in result
        assert "nivel_2" in result
        assert "nivel_3" in result

        # Verify URL is preserved
        assert result["url"] == url

        # Verify hierarchy is extracted
        assert result["nivel_1"] == "senior-x"
        assert result["nivel_2"] == "hcm"
        assert result["nivel_3"] == "admissao"

    def test_extract_content_with_two_level_url(self):
        """Verify extract_content handles URLs with fewer than 3 levels."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        url = "https://docs.senior.com.br/produto/erp"

        result = extractor.extract_content(url)

        assert result["nivel_1"] == "produto"
        assert result["nivel_2"] == "erp"
        assert result["nivel_3"] == ""


class TestExtractTitleFromMarkdown:
    """Test title extraction from Markdown content."""

    def test_extract_title_from_markdown_with_h1(self):
        """Verify title extraction from first # heading."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        markdown = "# Admissão de Colaboradores\n\nConteúdo da página..."

        result = extractor._extract_title_from_markdown(markdown)

        assert result == "Admissão de Colaboradores"

    def test_extract_title_from_markdown_multiple_headings(self):
        """Verify extraction uses first # heading only."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        markdown = "# First Title\n\n## Second Title\n\n# Third Title"

        result = extractor._extract_title_from_markdown(markdown)

        assert result == "First Title"

    def test_extract_title_from_markdown_no_heading(self):
        """Verify fallback to 'Untitled' when no heading found."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        markdown = "Just some content without headings."

        result = extractor._extract_title_from_markdown(markdown)

        assert result == "Untitled"

    def test_extract_title_from_markdown_with_whitespace(self):
        """Verify title extraction strips whitespace."""
        extractor = SemanticExtractor(extraction_backend="crawl4ai")
        markdown = "#   Title with spaces   \n\nContent..."

        result = extractor._extract_title_from_markdown(markdown)

        assert result == "Title with spaces"

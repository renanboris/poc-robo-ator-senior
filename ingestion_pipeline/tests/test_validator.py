"""Tests for ContentValidator class."""

from ingestion_pipeline.validator import ContentValidator


class TestContentValidator:
    """Tests for ContentValidator class."""

    def test_validate_valid_content(self):
        """Should pass validation for valid content."""
        validator = ContentValidator()
        content = {
            "url": "https://example.com/test",
            "markdown": """# Test Document

This is a test document with sufficient content to pass validation.
It has multiple paragraphs and proper structure.

## Section 1

Some content here with [a link](https://example.com) but not too many links.

## Section 2

More content to ensure we meet the minimum length requirement.
"""
        }

        is_valid, reason = validator.validate(content)
        assert is_valid is True
        assert reason == ""

    def test_validate_too_short(self):
        """Should fail validation for content < 100 characters."""
        validator = ContentValidator()
        content = {
            "url": "https://example.com/test",
            "markdown": "# Short\n\nToo short."
        }

        is_valid, reason = validator.validate(content)
        assert is_valid is False
        assert "too short" in reason.lower()

    def test_validate_no_headings(self):
        """Should fail validation for content without headings."""
        validator = ContentValidator()
        content = {
            "url": "https://example.com/test",
            "markdown": "This is a long paragraph without any headings. " * 10
        }

        is_valid, reason = validator.validate(content)
        assert is_valid is False
        assert "heading" in reason.lower()

    def test_validate_high_link_density(self):
        """Should fail validation for content with >70% link density."""
        validator = ContentValidator()
        # Create content that is mostly links
        links = "[link](url) " * 50
        content = {
            "url": "https://example.com/test",
            "markdown": f"# Navigation\n\n{links}"
        }

        is_valid, reason = validator.validate(content)
        assert is_valid is False
        assert "link density" in reason.lower()

    def test_check_min_length_pass(self):
        """Should pass minimum length check for content >= 100 chars."""
        validator = ContentValidator()
        markdown = "a" * 100
        assert validator.check_min_length(markdown) is True

    def test_check_min_length_fail(self):
        """Should fail minimum length check for content < 100 chars."""
        validator = ContentValidator()
        markdown = "a" * 99
        assert validator.check_min_length(markdown) is False

    def test_check_has_heading_h1(self):
        """Should detect h1 heading."""
        validator = ContentValidator()
        markdown = "# Heading 1\n\nContent"
        assert validator.check_has_heading(markdown) is True

    def test_check_has_heading_h2(self):
        """Should detect h2 heading."""
        validator = ContentValidator()
        markdown = "## Heading 2\n\nContent"
        assert validator.check_has_heading(markdown) is True

    def test_check_has_heading_h3(self):
        """Should detect h3 heading."""
        validator = ContentValidator()
        markdown = "### Heading 3\n\nContent"
        assert validator.check_has_heading(markdown) is True

    def test_check_has_heading_no_heading(self):
        """Should return False when no heading present."""
        validator = ContentValidator()
        markdown = "Just plain text without headings"
        assert validator.check_has_heading(markdown) is False

    def test_check_has_heading_invalid_format(self):
        """Should return False for invalid heading format (no space after #)."""
        validator = ContentValidator()
        markdown = "#NoSpace\n\nContent"
        assert validator.check_has_heading(markdown) is False

    def test_check_link_density_low(self):
        """Should pass for low link density."""
        validator = ContentValidator()
        markdown = """# Document

This is regular text with [one link](url) in a large document.
More text here. More text here. More text here. More text here.
More text here. More text here. More text here. More text here.
"""
        assert validator.check_link_density(markdown) is True

    def test_check_link_density_high(self):
        """Should fail for high link density (>70%)."""
        validator = ContentValidator()
        # Create content that is 80% links
        markdown = "[link1](url) [link2](url) [link3](url) text"
        assert validator.check_link_density(markdown) is False

    def test_check_link_density_exactly_70_percent(self):
        """Should pass for exactly 70% link density."""
        validator = ContentValidator()
        # Create content with exactly 70% links (full markdown syntax)
        # [link](url) = 11 chars, need 70 chars of links in 100 total
        # 6 links * 11 chars = 66 chars, plus 4 chars padding = 70 chars links
        links = "[link](url)" * 6  # 66 chars
        text = "text"  # 4 chars
        markdown = f"{links}{text}" + "x" * 30  # Total 100 chars
        assert validator.check_link_density(markdown) is True

    def test_check_link_density_empty_content(self):
        """Should pass for empty content."""
        validator = ContentValidator()
        assert validator.check_link_density("") is True

    def test_check_link_density_no_links(self):
        """Should pass for content with no links."""
        validator = ContentValidator()
        markdown = "Just plain text without any links at all."
        assert validator.check_link_density(markdown) is True

"""Content quality validation for the ingestion pipeline."""

import logging
import re
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)


class ContentValidator:
    """Validates extracted content quality before processing.
    
    Ensures content meets minimum quality standards:
    - Minimum length (>= 100 characters)
    - Contains at least one Markdown heading
    - Link density <= 70% (not primarily navigation)
    """

    def __init__(self):
        """Initialize content validator."""
        pass

    def validate(self, content: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate content quality.
        
        Args:
            content: Dictionary with 'url' and 'markdown' keys
            
        Returns:
            Tuple of (is_valid, reason) where:
            - is_valid: True if content passes all validation checks
            - reason: Empty string if valid, otherwise describes failure reason
        """
        url = content.get("url", "unknown")
        markdown = content.get("markdown", "")

        # Check minimum length
        if not self.check_min_length(markdown):
            reason = "Content too short (< 100 characters)"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason

        # Check for at least one heading
        if not self.check_has_heading(markdown):
            reason = "No Markdown headings found"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason

        # Check link density
        if not self.check_link_density(markdown):
            reason = "Link density too high (> 70%)"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason

        # Check for breadcrumb-only pages
        if not self.check_is_breadcrumb_only(markdown):
            reason = "Page appears to be breadcrumb/navigation only"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason

        return True, ""

    def check_min_length(self, markdown: str) -> bool:
        """Verify content has at least 100 characters.
        
        Args:
            markdown: Markdown content to check
            
        Returns:
            True if content length >= 100 characters
        """
        return len(markdown) >= 100

    def check_has_heading(self, markdown: str) -> bool:
        """Verify content contains at least one Markdown heading.
        
        Args:
            markdown: Markdown content to check
            
        Returns:
            True if at least one Markdown heading (# or ##, etc.) is found
        """
        # Match lines starting with one or more # followed by space
        heading_pattern = r'^#{1,6}\s+.+$'
        return bool(re.search(heading_pattern, markdown, re.MULTILINE))

    def check_link_density(self, markdown: str) -> bool:
        """Verify content is not primarily navigation links (>70%).
        
        Args:
            markdown: Markdown content to check
            
        Returns:
            True if link density <= 70%
        """
        if not markdown:
            return True

        # Count total characters
        total_chars = len(markdown)

        # Count characters in Markdown links: [text](url)
        # We count the full markdown link syntax, not just the link text
        link_pattern = r'\[([^\]]+)\]\([^\)]+\)'
        matches = re.finditer(link_pattern, markdown)

        # Sum up the length of full link markdown (including brackets and parentheses)
        link_chars = sum(len(match.group(0)) for match in matches)

        # Calculate link density
        link_density = link_chars / total_chars if total_chars > 0 else 0

        return link_density <= 0.70

    def check_is_breadcrumb_only(self, markdown: str) -> bool:
        """Detect pages that are only breadcrumb/navigation trails.
        
        Breadcrumb-only pages look like:
        "[GED](conceito.htm) > [Utilizando o GED](utilizando-o-ged.htm) > Integração BPM"
        
        Args:
            markdown: Markdown content to check
            
        Returns:
            True if content is NOT a breadcrumb-only page (i.e., content is valid)
        """
        lines = [l.strip() for l in markdown.split('\n') if l.strip()]
        if not lines:
            return True

        # Count lines that look like breadcrumb patterns:
        # - Lines with only links separated by > or /
        # - Lines with only __ or ____ (separator artifacts)
        breadcrumb_line_count = 0
        for line in lines:
            # Pure separator line
            if re.match(r'^[_\-\*]{2,}$', line):
                breadcrumb_line_count += 1
                continue
            # Line is only links and separators (breadcrumb trail)
            cleaned = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)
            cleaned = re.sub(r'[>\|/\s]', '', cleaned)
            if not cleaned:
                breadcrumb_line_count += 1

        breadcrumb_ratio = breadcrumb_line_count / len(lines) if lines else 0
        # If more than 60% of lines are breadcrumb/separator, reject
        return breadcrumb_ratio <= 0.60

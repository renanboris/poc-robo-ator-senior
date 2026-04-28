"""Content quality validation for the ingestion pipeline."""

import logging
import re
from typing import Tuple, Dict, Any

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
            reason = f"Content too short (< 100 characters)"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason
        
        # Check for at least one heading
        if not self.check_has_heading(markdown):
            reason = f"No Markdown headings found"
            logger.warning(f"Validation failed for {url}: {reason}")
            return False, reason
        
        # Check link density
        if not self.check_link_density(markdown):
            reason = f"Link density too high (> 70%)"
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

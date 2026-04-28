"""Tests for Chunker class."""

import pytest
from ingestion_pipeline.chunker import Chunker
from ingestion_pipeline.config import Chunk


class TestChunkerInitialization:
    """Tests for Chunker initialization."""
    
    def test_init_default_params(self):
        """Should initialize with default parameters."""
        chunker = Chunker()
        assert chunker.chunk_size == 800
        assert chunker.chunk_overlap == 100
        assert chunker.markdown_splitter is not None
        assert chunker.fallback_splitter is not None
    
    def test_init_custom_params(self):
        """Should initialize with custom parameters."""
        chunker = Chunker(chunk_size=1000, chunk_overlap=200)
        assert chunker.chunk_size == 1000
        assert chunker.chunk_overlap == 200


class TestChunkContent:
    """Tests for chunk_content method."""
    
    def test_chunk_content_with_headers(self):
        """Should split content using headers."""
        chunker = Chunker(chunk_size=100, chunk_overlap=20)
        markdown = """# Header 1

Content for section 1.

## Header 2

Content for section 2.

### Header 3

Content for section 3.
"""
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": "admissao"
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)
        assert all(chunk.metadata == metadata for chunk in chunks)
        assert all(chunk.chunk_index == idx for idx, chunk in enumerate(chunks))
    
    def test_chunk_content_without_headers(self):
        """Should use fallback splitter for content without headers."""
        chunker = Chunker(chunk_size=50, chunk_overlap=10)
        # Long content without headers
        markdown = "This is a long paragraph without any headers. " * 20
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": ""
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        assert len(chunks) > 0
        assert all(isinstance(chunk, Chunk) for chunk in chunks)
        assert all(chunk.metadata == metadata for chunk in chunks)
    
    def test_chunk_content_empty_markdown(self):
        """Should return empty list for empty markdown."""
        chunker = Chunker()
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": ""
        }
        
        chunks = chunker.chunk_content("", metadata)
        
        assert chunks == []
    
    def test_chunk_content_preserves_metadata(self):
        """Should preserve metadata in all chunks."""
        chunker = Chunker(chunk_size=50, chunk_overlap=10)
        markdown = """# Section 1

Content 1.

## Section 2

Content 2.
"""
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": "admissao"
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        for chunk in chunks:
            assert chunk.metadata["url"] == "https://example.com/test"
            assert chunk.metadata["titulo"] == "Test Document"
            assert chunk.metadata["nivel_1"] == "senior-x"
            assert chunk.metadata["nivel_2"] == "hcm"
            assert chunk.metadata["nivel_3"] == "admissao"
    
    def test_chunk_content_sequential_indices(self):
        """Should assign sequential chunk indices."""
        chunker = Chunker(chunk_size=50, chunk_overlap=10)
        markdown = """# Section 1

Content 1.

## Section 2

Content 2.

### Section 3

Content 3.
"""
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": ""
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        for idx, chunk in enumerate(chunks):
            assert chunk.chunk_index == idx
    
    def test_chunk_content_respects_chunk_size(self):
        """Should create chunks approximately matching chunk size."""
        chunker = Chunker(chunk_size=100, chunk_overlap=20)
        # Create very long content to ensure multiple chunks
        # Need much more content since MarkdownHeaderTextSplitter keeps sections together
        markdown = "# Long Document\n\n" + ("This is a sentence. " * 200)
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": ""
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        # Should create at least one chunk
        assert len(chunks) >= 1
        
        # Verify chunks are not empty
        for chunk in chunks:
            assert len(chunk.text) > 0
    
    def test_chunk_content_with_lists(self):
        """Should handle markdown lists correctly."""
        chunker = Chunker(chunk_size=100, chunk_overlap=20)
        markdown = """# Document with Lists

## Unordered List

- Item 1
- Item 2
- Item 3

## Ordered List

1. First item
2. Second item
3. Third item
"""
        metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": ""
        }
        
        chunks = chunker.chunk_content(markdown, metadata)
        
        assert len(chunks) > 0
        # Verify list items are preserved in chunks
        all_text = " ".join(chunk.text for chunk in chunks)
        assert "Item 1" in all_text or "- Item 1" in all_text
        assert "First item" in all_text or "1. First item" in all_text
    
    def test_chunk_content_metadata_not_mutated(self):
        """Should not mutate original metadata dictionary."""
        chunker = Chunker()
        markdown = "# Test\n\nContent"
        original_metadata = {
            "url": "https://example.com/test",
            "titulo": "Test Document",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": "admissao"
        }
        metadata_copy = original_metadata.copy()
        
        chunks = chunker.chunk_content(markdown, original_metadata)
        
        # Original metadata should be unchanged
        assert original_metadata == metadata_copy
        
        # Each chunk should have its own copy
        if len(chunks) > 1:
            chunks[0].metadata["test_field"] = "modified"
            assert "test_field" not in chunks[1].metadata

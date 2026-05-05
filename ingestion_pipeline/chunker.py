"""Content chunking for the ingestion pipeline."""

import logging
from typing import Dict, List

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from .config import Chunk

logger = logging.getLogger(__name__)


class Chunker:
    """Splits Markdown content into semantic chunks for embedding.
    
    Uses LangChain's MarkdownHeaderTextSplitter for semantic splitting
    based on headers, with fallback to RecursiveCharacterTextSplitter
    for content without headers.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 100):
        """Initialize chunker with LangChain text splitters.
        
        Args:
            chunk_size: Target chunk size in tokens (approximately 4 chars per token)
            chunk_overlap: Overlap between chunks in tokens
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Initialize MarkdownHeaderTextSplitter for semantic splitting
        # Split on headers from h1 to h3
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        self.markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False  # Keep headers in chunks for context
        )

        # Initialize fallback RecursiveCharacterTextSplitter
        # Convert tokens to approximate character count (1 token ≈ 4 chars)
        char_chunk_size = chunk_size * 4
        char_chunk_overlap = chunk_overlap * 4

        self.fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=char_chunk_size,
            chunk_overlap=char_chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]  # Preserve semantic boundaries
        )

        logger.info(
            f"Initialized Chunker with chunk_size={chunk_size} tokens, "
            f"chunk_overlap={chunk_overlap} tokens"
        )

    def chunk_content(self, markdown: str, metadata: Dict[str, str]) -> List[Chunk]:
        """Split content into chunks with metadata.
        
        Args:
            markdown: Markdown content to split
            metadata: Metadata dictionary containing url, titulo, nivel_1, nivel_2, nivel_3
            
        Returns:
            List of Chunk objects with text, chunk_index, and metadata
        """
        if not markdown:
            logger.warning(f"Empty markdown content for URL: {metadata.get('url', 'unknown')}")
            return []

        chunks = []

        try:
            # Try semantic splitting with MarkdownHeaderTextSplitter first
            md_chunks = self.markdown_splitter.split_text(markdown)

            # If we got chunks, use them
            if md_chunks:
                logger.debug(
                    f"Split content using MarkdownHeaderTextSplitter: "
                    f"{len(md_chunks)} chunks for {metadata.get('url', 'unknown')}"
                )

                for idx, chunk_text in enumerate(md_chunks):
                    # Extract text from Document object if needed
                    if hasattr(chunk_text, 'page_content'):
                        text = chunk_text.page_content
                    else:
                        text = str(chunk_text)

                    chunks.append(Chunk(
                        text=text,
                        chunk_index=idx,
                        metadata=metadata.copy()
                    ))
            else:
                # Fallback to RecursiveCharacterTextSplitter
                logger.debug(
                    f"No headers found, using RecursiveCharacterTextSplitter "
                    f"for {metadata.get('url', 'unknown')}"
                )
                fallback_chunks = self.fallback_splitter.split_text(markdown)

                for idx, text in enumerate(fallback_chunks):
                    chunks.append(Chunk(
                        text=text,
                        chunk_index=idx,
                        metadata=metadata.copy()
                    ))

                logger.debug(
                    f"Split content using RecursiveCharacterTextSplitter: "
                    f"{len(fallback_chunks)} chunks"
                )

        except Exception as e:
            # If markdown splitting fails, fallback to recursive splitter
            logger.warning(
                f"MarkdownHeaderTextSplitter failed for {metadata.get('url', 'unknown')}: {e}. "
                f"Using fallback splitter."
            )

            fallback_chunks = self.fallback_splitter.split_text(markdown)

            for idx, text in enumerate(fallback_chunks):
                chunks.append(Chunk(
                    text=text,
                    chunk_index=idx,
                    metadata=metadata.copy()
                ))

            logger.debug(f"Fallback split created {len(fallback_chunks)} chunks")

        logger.info(
            f"Created {len(chunks)} chunks for {metadata.get('url', 'unknown')}"
        )

        return chunks

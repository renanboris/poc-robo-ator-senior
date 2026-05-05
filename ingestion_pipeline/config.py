"""Configuration management for the ingestion pipeline."""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the Web Knowledge Ingestion Pipeline.
    
    All configuration values are loaded from environment variables.
    Required variables must be set or initialization will fail.
    """

    # API Keys (required)
    openai_api_key: str
    pinecone_api_key: str
    pinecone_index_name: str

    # Optional API Keys
    firecrawl_api_key: Optional[str] = None

    # Extraction settings
    extraction_backend: str = "crawl4ai"  # "crawl4ai" or "firecrawl"

    # Chunking settings
    chunk_size: int = 800  # Approximate tokens
    chunk_overlap: int = 100  # Approximate tokens

    # Embedding settings
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072

    # Injection settings
    batch_size: int = 100

    # Retry settings
    max_retries: int = 3
    retry_delays: List[int] = field(default_factory=lambda: [1, 2, 4])

    # Incremental mode settings
    cache_file: str = ".ingestion_cache.json"

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create configuration from environment variables.
        
        Returns:
            PipelineConfig instance with values from environment
            
        Raises:
            ValueError: If required environment variables are missing
        """
        # Check required variables
        required_vars = {
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "PINECONE_API_KEY": os.getenv("PINECONE_API_KEY"),
            "PINECONE_INDEX_NAME": os.getenv("PINECONE_INDEX_NAME"),
        }

        missing = [key for key, value in required_vars.items() if not value]
        if missing:
            error_msg = (
                f"Missing required environment variables: {', '.join(missing)}\n"
                f"Please set these variables in your .env file or environment."
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        return cls(
            openai_api_key=required_vars["OPENAI_API_KEY"],
            pinecone_api_key=required_vars["PINECONE_API_KEY"],
            pinecone_index_name=required_vars["PINECONE_INDEX_NAME"],
            firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY"),
            extraction_backend=os.getenv("EXTRACTION_BACKEND", "crawl4ai"),
        )

    def validate(self) -> None:
        """Validate configuration values.
        
        Raises:
            ValueError: If configuration values are invalid
        """
        if self.extraction_backend not in ["crawl4ai", "firecrawl"]:
            raise ValueError(
                f"Invalid extraction_backend: {self.extraction_backend}. "
                f"Must be 'crawl4ai' or 'firecrawl'"
            )

        if self.extraction_backend == "firecrawl" and not self.firecrawl_api_key:
            raise ValueError(
                "FIRECRAWL_API_KEY environment variable is required when "
                "using firecrawl backend"
            )

        if self.chunk_size < 100:
            raise ValueError(f"chunk_size must be at least 100, got {self.chunk_size}")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError(
                f"chunk_overlap ({self.chunk_overlap}) must be less than "
                f"chunk_size ({self.chunk_size})"
            )

        if self.embedding_dimensions not in [1536, 3072]:
            raise ValueError(
                f"embedding_dimensions must be 1536 or 3072, got {self.embedding_dimensions}"
            )


@dataclass
class ExtractedContent:
    """Represents extracted content from a web page.
    
    Attributes:
        url: Original source URL
        titulo: Page title (from <title> or <h1>)
        markdown: Clean Markdown content
        nivel_1: First path segment (e.g., "senior-x")
        nivel_2: Second path segment (e.g., "hcm")
        nivel_3: Third path segment (e.g., "admissao")
    """
    url: str
    titulo: str
    markdown: str
    nivel_1: str
    nivel_2: str
    nivel_3: str = ""

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation of the extracted content
        """
        return {
            "url": self.url,
            "titulo": self.titulo,
            "markdown": self.markdown,
            "nivel_1": self.nivel_1,
            "nivel_2": self.nivel_2,
            "nivel_3": self.nivel_3,
        }


@dataclass
class Chunk:
    """Represents a semantic chunk of documentation content.
    
    Attributes:
        text: Chunk text content
        chunk_index: Sequential index within document
        metadata: Dictionary containing url, titulo, nivel_1, nivel_2, nivel_3
    """
    text: str
    chunk_index: int
    metadata: Dict[str, str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization.
        
        Returns:
            Dictionary representation of the chunk
        """
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "metadata": self.metadata,
        }


@dataclass
class Vector:
    """Represents a vector for Pinecone injection.
    
    Attributes:
        id: Unique vector ID (format: {nivel_2}_{titulo_sanitized}_{chunk_index})
        values: Embedding vector (3072-dimensional float list)
        metadata: Dictionary containing url, nivel_1, nivel_2, titulo, text
        namespace: Pinecone namespace (derived from nivel_2)
    """
    id: str
    values: List[float]
    metadata: Dict[str, str]
    namespace: str

    def to_pinecone_format(self) -> Dict[str, Any]:
        """Convert to Pinecone upsert format.
        
        Returns:
            Dictionary in Pinecone upsert format with id, values, and metadata
        """
        return {
            "id": self.id,
            "values": self.values,
            "metadata": self.metadata,
        }


@dataclass
class PipelineReport:
    """Summary report of pipeline execution.
    
    Attributes:
        start_time: Pipeline start timestamp
        end_time: Pipeline end timestamp
        duration_seconds: Total execution duration
        urls_discovered: Number of URLs found in sitemap
        urls_fetched: Number of URLs successfully fetched
        urls_validated: Number of URLs passing quality validation
        chunks_created: Number of chunks created
        embeddings_generated: Number of embeddings generated
        vectors_injected: Number of vectors successfully injected
        failed_fetches: Number of failed URL fetches
        failed_validations: Number of failed content validations
        failed_embeddings: Number of failed embedding generations
        failed_upserts: Number of failed vector upserts
        skipped_low_quality: Number of URLs skipped due to low quality
        urls_skipped_cached: Number of URLs skipped due to cache (incremental mode)
    """
    # Timing
    start_time: datetime
    end_time: datetime
    duration_seconds: float

    # Stage metrics
    urls_discovered: int
    urls_fetched: int
    urls_validated: int
    chunks_created: int
    embeddings_generated: int
    vectors_injected: int

    # Failure counts
    failed_fetches: int
    failed_validations: int
    failed_embeddings: int
    failed_upserts: int
    skipped_low_quality: int

    # Incremental mode
    urls_skipped_cached: int = 0
    urls_skipped_module_filter: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/display.
        
        Returns:
            Dictionary representation of the pipeline report
        """
        return {
            "timing": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_seconds": self.duration_seconds,
            },
            "stage_metrics": {
                "urls_discovered": self.urls_discovered,
                "urls_fetched": self.urls_fetched,
                "urls_validated": self.urls_validated,
                "chunks_created": self.chunks_created,
                "embeddings_generated": self.embeddings_generated,
                "vectors_injected": self.vectors_injected,
            },
            "failure_counts": {
                "failed_fetches": self.failed_fetches,
                "failed_validations": self.failed_validations,
                "failed_embeddings": self.failed_embeddings,
                "failed_upserts": self.failed_upserts,
                "skipped_low_quality": self.skipped_low_quality,
            },
            "incremental": {
                "urls_skipped_cached": self.urls_skipped_cached,
                "urls_skipped_module_filter": self.urls_skipped_module_filter,
            },
        }

    def print_summary(self) -> None:
        """Print human-readable summary to console."""
        print("\n" + "=" * 60)
        print("PIPELINE EXECUTION SUMMARY")
        print("=" * 60)

        print("\nTiming:")
        print(f"   Start: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   End:   {self.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   Duration: {self.duration_seconds:.2f} seconds")

        print("\nStage Metrics:")
        print(f"   URLs Discovered:      {self.urls_discovered}")
        print(f"   URLs Fetched:         {self.urls_fetched}")
        print(f"   URLs Validated:       {self.urls_validated}")
        print(f"   Chunks Created:       {self.chunks_created}")
        print(f"   Embeddings Generated: {self.embeddings_generated}")
        print(f"   Vectors Injected:     {self.vectors_injected}")

        print("\nFailure Counts:")
        print(f"   Failed Fetches:       {self.failed_fetches}")
        print(f"   Failed Validations:   {self.failed_validations}")
        print(f"   Failed Embeddings:    {self.failed_embeddings}")
        print(f"   Failed Upserts:       {self.failed_upserts}")
        print(f"   Skipped Low Quality:  {self.skipped_low_quality}")

        if self.urls_skipped_cached > 0:
            print("\nIncremental Mode:")
            print(f"   URLs Skipped (Cached): {self.urls_skipped_cached}")

        if self.urls_skipped_module_filter > 0:
            print("\nModule Filter:")
            print(f"   URLs Skipped (Filter): {self.urls_skipped_module_filter}")

        # Calculate success rate
        if self.urls_discovered > 0:
            success_rate = (self.urls_validated / self.urls_discovered) * 100
            print(f"\nSuccess Rate: {success_rate:.1f}%")

        print("=" * 60)

        # Calculate success rate
        total_urls = self.urls_discovered
        successful_urls = self.urls_validated
        if total_urls > 0:
            success_rate = (successful_urls / total_urls) * 100
            print(f"\n📊 Success Rate: {success_rate:.1f}%")

        print("\n" + "=" * 60 + "\n")

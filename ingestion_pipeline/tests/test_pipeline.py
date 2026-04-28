"""Tests for the IngestionPipeline orchestrator."""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from ingestion_pipeline.pipeline import IngestionPipeline
from ingestion_pipeline.config import PipelineConfig


@pytest.fixture
def mock_config():
    """Create a mock PipelineConfig."""
    return PipelineConfig(
        openai_api_key="test-openai-key",
        pinecone_api_key="test-pinecone-key",
        pinecone_index_name="test-index",
        extraction_backend="crawl4ai",
        chunk_size=800,
        chunk_overlap=100,
        embedding_model="text-embedding-3-large",
        embedding_dimensions=3072,
        batch_size=100,
        max_retries=3,
        retry_delays=[1, 2, 4],
        cache_file=".test_cache.json"
    )


class TestPipelineInitialization:
    """Test IngestionPipeline initialization."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_init(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test pipeline initialization."""
        pipeline = IngestionPipeline(mock_config)
        
        assert pipeline.config == mock_config
        assert pipeline.extractor is not None
        assert pipeline.validator is not None
        assert pipeline.chunker is not None
        assert pipeline.embedder is not None
        assert pipeline.injector is not None
        assert pipeline.cache == {}


class TestCacheManagement:
    """Test cache loading and saving."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_load_cache_file_not_exists(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config,
        tmp_path
    ):
        """Test loading cache when file doesn't exist."""
        mock_config.cache_file = str(tmp_path / "nonexistent.json")
        pipeline = IngestionPipeline(mock_config)
        
        pipeline.load_cache()
        
        assert pipeline.cache == {}
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_load_cache_file_exists(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config,
        tmp_path
    ):
        """Test loading cache from existing file."""
        cache_file = tmp_path / "test_cache.json"
        cache_data = {
            "https://example.com/test": {
                "content_hash": "abc123",
                "last_updated": "2024-01-01T00:00:00",
                "vector_count": 5
            }
        }
        
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)
        
        mock_config.cache_file = str(cache_file)
        pipeline = IngestionPipeline(mock_config)
        
        pipeline.load_cache()
        
        assert pipeline.cache == cache_data
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_save_cache(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config,
        tmp_path
    ):
        """Test saving cache to file."""
        cache_file = tmp_path / "test_cache.json"
        mock_config.cache_file = str(cache_file)
        pipeline = IngestionPipeline(mock_config)
        
        pipeline.cache = {
            "https://example.com/test": {
                "content_hash": "abc123",
                "last_updated": "2024-01-01T00:00:00",
                "vector_count": 5
            }
        }
        
        pipeline.save_cache()
        
        assert cache_file.exists()
        
        with open(cache_file, 'r') as f:
            saved_cache = json.load(f)
        
        assert saved_cache == pipeline.cache


class TestContentHashing:
    """Test content hash computation."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_compute_content_hash(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test content hash computation."""
        pipeline = IngestionPipeline(mock_config)
        
        markdown = "# Test Content\n\nThis is a test."
        hash1 = pipeline._compute_content_hash(markdown)
        hash2 = pipeline._compute_content_hash(markdown)
        
        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_compute_content_hash_different_content(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test that different content produces different hashes."""
        pipeline = IngestionPipeline(mock_config)
        
        markdown1 = "# Test Content 1"
        markdown2 = "# Test Content 2"
        
        hash1 = pipeline._compute_content_hash(markdown1)
        hash2 = pipeline._compute_content_hash(markdown2)
        
        assert hash1 != hash2


class TestCacheChecking:
    """Test cache checking logic."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_is_cached_url_not_in_cache(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test cache check when URL is not cached."""
        pipeline = IngestionPipeline(mock_config)
        
        result = pipeline._is_cached(
            "https://example.com/test",
            "# Test Content"
        )
        
        assert result is False
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_is_cached_content_unchanged(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test cache check when content is unchanged."""
        pipeline = IngestionPipeline(mock_config)
        
        markdown = "# Test Content"
        content_hash = pipeline._compute_content_hash(markdown)
        
        pipeline.cache = {
            "https://example.com/test": {
                "content_hash": content_hash,
                "last_updated": "2024-01-01T00:00:00",
                "vector_count": 5
            }
        }
        
        result = pipeline._is_cached("https://example.com/test", markdown)
        
        assert result is True
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_is_cached_content_changed(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test cache check when content has changed."""
        pipeline = IngestionPipeline(mock_config)
        
        old_markdown = "# Old Content"
        new_markdown = "# New Content"
        old_hash = pipeline._compute_content_hash(old_markdown)
        
        pipeline.cache = {
            "https://example.com/test": {
                "content_hash": old_hash,
                "last_updated": "2024-01-01T00:00:00",
                "vector_count": 5
            }
        }
        
        result = pipeline._is_cached("https://example.com/test", new_markdown)
        
        assert result is False


class TestCacheUpdate:
    """Test cache update logic."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_update_cache(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test cache update."""
        pipeline = IngestionPipeline(mock_config)
        
        url = "https://example.com/test"
        markdown = "# Test Content"
        vector_count = 5
        
        pipeline._update_cache(url, markdown, vector_count)
        
        assert url in pipeline.cache
        assert "content_hash" in pipeline.cache[url]
        assert "last_updated" in pipeline.cache[url]
        assert pipeline.cache[url]["vector_count"] == vector_count
        
        # Verify hash is correct
        expected_hash = pipeline._compute_content_hash(markdown)
        assert pipeline.cache[url]["content_hash"] == expected_hash


class TestRunStage:
    """Test stage execution with error handling."""
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_run_stage_success(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test successful stage execution."""
        pipeline = IngestionPipeline(mock_config)
        
        def stage_func(input_data):
            return ["result1", "result2"]
        
        result = pipeline.run_stage("test_stage", stage_func, None)
        
        assert result == ["result1", "result2"]
    
    @patch('ingestion_pipeline.pipeline.VectorInjector')
    @patch('ingestion_pipeline.pipeline.EmbeddingGenerator')
    @patch('ingestion_pipeline.pipeline.Chunker')
    @patch('ingestion_pipeline.pipeline.ContentValidator')
    @patch('ingestion_pipeline.pipeline.SemanticExtractor')
    def test_run_stage_failure(
        self,
        mock_extractor,
        mock_validator,
        mock_chunker,
        mock_embedder,
        mock_injector,
        mock_config
    ):
        """Test stage execution failure."""
        pipeline = IngestionPipeline(mock_config)
        
        def stage_func(input_data):
            raise Exception("Stage failed")
        
        with pytest.raises(Exception, match="Stage failed"):
            pipeline.run_stage("test_stage", stage_func, None)

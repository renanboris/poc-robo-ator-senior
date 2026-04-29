"""Tests for configuration management.

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**
"""

import os
import pytest
from ingestion_pipeline.config import (
    PipelineConfig,
    ExtractedContent,
    Chunk,
    Vector,
    PipelineReport
)


class TestPipelineConfigValidation:
    """Test configuration validation and environment variable handling."""
    
    def test_from_env_with_all_required_vars(self, monkeypatch):
        """Test configuration loads successfully with all required environment variables."""
        # Set required environment variables
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        
        config = PipelineConfig.from_env()
        
        assert config.openai_api_key == "sk-test-key"
        assert config.pinecone_api_key == "pc-test-key"
        assert config.pinecone_index_name == "test-index"
        assert config.extraction_backend == "crawl4ai"  # Default
    
    def test_from_env_missing_openai_key(self, monkeypatch):
        """Test configuration fails when OPENAI_API_KEY is missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        
        with pytest.raises(ValueError) as exc_info:
            PipelineConfig.from_env()
        
        assert "OPENAI_API_KEY" in str(exc_info.value)
        assert "Missing required environment variables" in str(exc_info.value)
    
    def test_from_env_missing_pinecone_key(self, monkeypatch):
        """Test configuration fails when PINECONE_API_KEY is missing."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.delenv("PINECONE_API_KEY", raising=False)
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        
        with pytest.raises(ValueError) as exc_info:
            PipelineConfig.from_env()
        
        assert "PINECONE_API_KEY" in str(exc_info.value)
    
    def test_from_env_missing_pinecone_index_name(self, monkeypatch):
        """Test configuration fails when PINECONE_INDEX_NAME is missing."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.delenv("PINECONE_INDEX_NAME", raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            PipelineConfig.from_env()
        
        assert "PINECONE_INDEX_NAME" in str(exc_info.value)
    
    def test_from_env_missing_multiple_vars(self, monkeypatch):
        """Test configuration fails with descriptive error when multiple vars are missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("PINECONE_API_KEY", raising=False)
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        
        with pytest.raises(ValueError) as exc_info:
            PipelineConfig.from_env()
        
        error_msg = str(exc_info.value)
        assert "OPENAI_API_KEY" in error_msg
        assert "PINECONE_API_KEY" in error_msg


class TestBackendSelection:
    """Test backend selection between Crawl4AI and Firecrawl."""
    
    def test_default_backend_is_crawl4ai(self, monkeypatch):
        """Test default extraction backend is crawl4ai."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        monkeypatch.delenv("EXTRACTION_BACKEND", raising=False)
        
        config = PipelineConfig.from_env()
        
        assert config.extraction_backend == "crawl4ai"
    
    def test_backend_selection_crawl4ai(self, monkeypatch):
        """Test explicit selection of crawl4ai backend."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        monkeypatch.setenv("EXTRACTION_BACKEND", "crawl4ai")
        
        config = PipelineConfig.from_env()
        
        assert config.extraction_backend == "crawl4ai"
    
    def test_backend_selection_firecrawl(self, monkeypatch):
        """Test explicit selection of firecrawl backend."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        monkeypatch.setenv("EXTRACTION_BACKEND", "firecrawl")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "fc-test-key")
        
        config = PipelineConfig.from_env()
        
        assert config.extraction_backend == "firecrawl"
        assert config.firecrawl_api_key == "fc-test-key"
    
    def test_validate_invalid_backend(self):
        """Test validation fails with invalid backend name."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            extraction_backend="invalid-backend"
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "Invalid extraction_backend" in str(exc_info.value)
        assert "crawl4ai" in str(exc_info.value)
        assert "firecrawl" in str(exc_info.value)
    
    def test_validate_firecrawl_without_api_key(self):
        """Test validation fails when firecrawl backend is selected without API key."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            extraction_backend="firecrawl",
            firecrawl_api_key=None
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "FIRECRAWL_API_KEY" in str(exc_info.value)


class TestChunkingParameters:
    """Test chunking parameter validation."""
    
    def test_default_chunking_parameters(self):
        """Test default chunking parameters are set correctly."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index"
        )
        
        assert config.chunk_size == 800
        assert config.chunk_overlap == 100
    
    def test_validate_chunk_size_too_small(self):
        """Test validation fails when chunk_size is too small."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            chunk_size=50
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "chunk_size must be at least 100" in str(exc_info.value)
    
    def test_validate_chunk_overlap_exceeds_size(self):
        """Test validation fails when chunk_overlap >= chunk_size."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            chunk_size=500,
            chunk_overlap=500
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "chunk_overlap" in str(exc_info.value)
        assert "must be less than" in str(exc_info.value)


class TestRetrySettings:
    """Test retry configuration."""
    
    def test_default_retry_settings(self):
        """Test default retry settings are configured correctly."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index"
        )
        
        assert config.max_retries == 3
        assert config.retry_delays == [1, 2, 4]
    
    def test_custom_retry_settings(self):
        """Test custom retry settings can be configured."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            max_retries=5,
            retry_delays=[1, 2, 4, 8, 16]
        )
        
        assert config.max_retries == 5
        assert config.retry_delays == [1, 2, 4, 8, 16]


class TestEmbeddingConfiguration:
    """Test embedding model configuration."""
    
    def test_default_embedding_settings(self):
        """Test default embedding settings match design spec."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index"
        )
        
        assert config.embedding_model == "text-embedding-3-large"
        assert config.embedding_dimensions == 3072
    
    def test_validate_invalid_embedding_dimensions(self):
        """Test validation fails with invalid embedding dimensions."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index",
            embedding_dimensions=2048
        )
        
        with pytest.raises(ValueError) as exc_info:
            config.validate()
        
        assert "embedding_dimensions must be 1536 or 3072" in str(exc_info.value)


class TestOptionalConfiguration:
    """Test optional configuration parameters."""
    
    def test_optional_firecrawl_api_key(self, monkeypatch):
        """Test firecrawl_api_key is optional when using crawl4ai backend."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setenv("PINECONE_API_KEY", "pc-test-key")
        monkeypatch.setenv("PINECONE_INDEX_NAME", "test-index")
        monkeypatch.setenv("EXTRACTION_BACKEND", "crawl4ai")
        monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
        
        config = PipelineConfig.from_env()
        
        assert config.firecrawl_api_key is None
        config.validate()  # Should not raise
    
    def test_batch_size_default(self):
        """Test default batch size for vector injection."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index"
        )
        
        assert config.batch_size == 100
    
    def test_cache_file_default(self):
        """Test default cache file path for incremental mode."""
        config = PipelineConfig(
            openai_api_key="sk-test",
            pinecone_api_key="pc-test",
            pinecone_index_name="test-index"
        )
        
        assert config.cache_file == ".ingestion_cache.json"



class TestExtractedContent:
    """Test ExtractedContent dataclass."""
    
    def test_extracted_content_creation(self):
        """Test creating ExtractedContent with all fields."""
        content = ExtractedContent(
            url="https://docs.senior.com.br/senior-x/hcm/admissao",
            titulo="Admissão de Colaborador",
            markdown="# Admissão\n\nConteúdo sobre admissão...",
            nivel_1="senior-x",
            nivel_2="hcm",
            nivel_3="admissao"
        )
        
        assert content.url == "https://docs.senior.com.br/senior-x/hcm/admissao"
        assert content.titulo == "Admissão de Colaborador"
        assert content.markdown == "# Admissão\n\nConteúdo sobre admissão..."
        assert content.nivel_1 == "senior-x"
        assert content.nivel_2 == "hcm"
        assert content.nivel_3 == "admissao"
    
    def test_extracted_content_default_nivel_3(self):
        """Test ExtractedContent with default empty nivel_3."""
        content = ExtractedContent(
            url="https://docs.senior.com.br/senior-x/hcm",
            titulo="HCM",
            markdown="# HCM\n\nConteúdo...",
            nivel_1="senior-x",
            nivel_2="hcm"
        )
        
        assert content.nivel_3 == ""
    
    def test_extracted_content_to_dict(self):
        """Test converting ExtractedContent to dictionary."""
        content = ExtractedContent(
            url="https://docs.senior.com.br/senior-x/hcm/admissao",
            titulo="Admissão de Colaborador",
            markdown="# Admissão\n\nConteúdo...",
            nivel_1="senior-x",
            nivel_2="hcm",
            nivel_3="admissao"
        )
        
        result = content.to_dict()
        
        assert result == {
            "url": "https://docs.senior.com.br/senior-x/hcm/admissao",
            "titulo": "Admissão de Colaborador",
            "markdown": "# Admissão\n\nConteúdo...",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "nivel_3": "admissao"
        }


class TestChunk:
    """Test Chunk dataclass."""
    
    def test_chunk_creation(self):
        """Test creating Chunk with all fields."""
        chunk = Chunk(
            text="Este é o conteúdo do chunk...",
            chunk_index=0,
            metadata={
                "url": "https://docs.senior.com.br/senior-x/hcm/admissao",
                "titulo": "Admissão de Colaborador",
                "nivel_1": "senior-x",
                "nivel_2": "hcm",
                "nivel_3": "admissao"
            }
        )
        
        assert chunk.text == "Este é o conteúdo do chunk..."
        assert chunk.chunk_index == 0
        assert chunk.metadata["url"] == "https://docs.senior.com.br/senior-x/hcm/admissao"
        assert chunk.metadata["nivel_2"] == "hcm"
    
    def test_chunk_to_dict(self):
        """Test converting Chunk to dictionary."""
        chunk = Chunk(
            text="Conteúdo do chunk",
            chunk_index=2,
            metadata={
                "url": "https://example.com",
                "titulo": "Título",
                "nivel_1": "produto",
                "nivel_2": "modulo",
                "nivel_3": "funcionalidade"
            }
        )
        
        result = chunk.to_dict()
        
        assert result["text"] == "Conteúdo do chunk"
        assert result["chunk_index"] == 2
        assert result["metadata"]["nivel_2"] == "modulo"


class TestVector:
    """Test Vector dataclass."""
    
    def test_vector_creation(self):
        """Test creating Vector with all fields."""
        vector = Vector(
            id="hcm_admissao-colaborador_0",
            values=[0.1, 0.2, 0.3],
            metadata={
                "url": "https://docs.senior.com.br/senior-x/hcm/admissao",
                "nivel_1": "senior-x",
                "nivel_2": "hcm",
                "titulo": "Admissão de Colaborador",
                "text": "Conteúdo do chunk..."
            },
            namespace="hcm"
        )
        
        assert vector.id == "hcm_admissao-colaborador_0"
        assert len(vector.values) == 3
        assert vector.namespace == "hcm"
        assert vector.metadata["nivel_2"] == "hcm"
    
    def test_vector_to_pinecone_format(self):
        """Test converting Vector to Pinecone upsert format."""
        vector = Vector(
            id="hcm_admissao_0",
            values=[0.1, 0.2, 0.3],
            metadata={
                "url": "https://example.com",
                "nivel_1": "senior-x",
                "nivel_2": "hcm",
                "titulo": "Título",
                "text": "Texto"
            },
            namespace="hcm"
        )
        
        result = vector.to_pinecone_format()
        
        assert result["id"] == "hcm_admissao_0"
        assert result["values"] == [0.1, 0.2, 0.3]
        assert result["metadata"]["nivel_2"] == "hcm"
        assert "namespace" not in result  # Namespace is not in the upsert format


class TestPipelineReport:
    """Test PipelineReport dataclass."""
    
    def test_pipeline_report_creation(self):
        """Test creating PipelineReport with all fields."""
        from datetime import datetime
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 30, 0)
        
        report = PipelineReport(
            start_time=start,
            end_time=end,
            duration_seconds=1800.0,
            urls_discovered=100,
            urls_fetched=95,
            urls_validated=90,
            chunks_created=450,
            embeddings_generated=450,
            vectors_injected=450,
            failed_fetches=5,
            failed_validations=5,
            failed_embeddings=0,
            failed_upserts=0,
            skipped_low_quality=5,
            urls_skipped_cached=0
        )
        
        assert report.urls_discovered == 100
        assert report.urls_fetched == 95
        assert report.vectors_injected == 450
        assert report.duration_seconds == 1800.0
    
    def test_pipeline_report_to_dict(self):
        """Test converting PipelineReport to dictionary."""
        from datetime import datetime
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 30, 0)
        
        report = PipelineReport(
            start_time=start,
            end_time=end,
            duration_seconds=1800.0,
            urls_discovered=100,
            urls_fetched=95,
            urls_validated=90,
            chunks_created=450,
            embeddings_generated=450,
            vectors_injected=450,
            failed_fetches=5,
            failed_validations=5,
            failed_embeddings=0,
            failed_upserts=0,
            skipped_low_quality=5
        )
        
        result = report.to_dict()
        
        assert "timing" in result
        assert "stage_metrics" in result
        assert "failure_counts" in result
        assert "incremental" in result
        assert result["stage_metrics"]["urls_discovered"] == 100
        assert result["failure_counts"]["failed_fetches"] == 5
    
    def test_pipeline_report_print_summary(self, capsys):
        """Test printing PipelineReport summary."""
        from datetime import datetime
        
        start = datetime(2024, 1, 15, 10, 0, 0)
        end = datetime(2024, 1, 15, 10, 30, 0)
        
        report = PipelineReport(
            start_time=start,
            end_time=end,
            duration_seconds=1800.0,
            urls_discovered=100,
            urls_fetched=95,
            urls_validated=90,
            chunks_created=450,
            embeddings_generated=450,
            vectors_injected=450,
            failed_fetches=5,
            failed_validations=5,
            failed_embeddings=0,
            failed_upserts=0,
            skipped_low_quality=5
        )
        
        report.print_summary()
        
        captured = capsys.readouterr()
        assert "PIPELINE EXECUTION SUMMARY" in captured.out
        assert "URLs Discovered:      100" in captured.out
        assert "Vectors Injected:     450" in captured.out
        assert "Success Rate: 90.0%" in captured.out

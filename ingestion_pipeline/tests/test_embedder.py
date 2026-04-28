"""Tests for EmbeddingGenerator class."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from ingestion_pipeline.embedder import EmbeddingGenerator


class TestEmbeddingGeneratorInitialization:
    """Tests for EmbeddingGenerator initialization."""
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_init_default_params(self, mock_openai):
        """Should initialize with default parameters."""
        generator = EmbeddingGenerator()
        
        assert generator.model == "text-embedding-3-large"
        assert generator.dimensions == 3072
        mock_openai.assert_called_once()
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_init_custom_params(self, mock_openai):
        """Should initialize with custom parameters."""
        generator = EmbeddingGenerator(
            model="text-embedding-3-small",
            dimensions=1536
        )
        
        assert generator.model == "text-embedding-3-small"
        assert generator.dimensions == 1536
        mock_openai.assert_called_once()


class TestGenerateEmbedding:
    """Tests for generate_embedding method."""
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_success(self, mock_openai):
        """Should generate embedding successfully."""
        # Mock OpenAI client response
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 3072)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator()
        text = "This is a test document for embedding generation."
        
        embedding = generator.generate_embedding(text)
        
        assert len(embedding) == 3072
        assert all(isinstance(val, float) for val in embedding)
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-large",
            input=text,
            dimensions=3072
        )
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_empty_text(self, mock_openai):
        """Should return zero vector for empty text."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator()
        
        embedding = generator.generate_embedding("")
        
        assert len(embedding) == 3072
        assert all(val == 0.0 for val in embedding)
        # Should not call API for empty text
        mock_client.embeddings.create.assert_not_called()
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_whitespace_only(self, mock_openai):
        """Should return zero vector for whitespace-only text."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator()
        
        embedding = generator.generate_embedding("   \n\t  ")
        
        assert len(embedding) == 3072
        assert all(val == 0.0 for val in embedding)
        # Should not call API for whitespace-only text
        mock_client.embeddings.create.assert_not_called()
    
    @patch('ingestion_pipeline.embedder.retry_with_backoff')
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_with_retry(self, mock_openai, mock_retry):
        """Should use retry logic for API calls."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 3072)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        # Mock retry_with_backoff to return the embedding
        mock_retry.return_value = [0.1] * 3072
        
        generator = EmbeddingGenerator()
        text = "Test text"
        
        embedding = generator.generate_embedding(text)
        
        # Verify retry_with_backoff was called with correct parameters
        mock_retry.assert_called_once()
        call_kwargs = mock_retry.call_args[1]
        assert call_kwargs['max_retries'] == 3
        assert call_kwargs['delays'] == [1, 2, 4]
        assert call_kwargs['exceptions'] == (Exception,)
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_api_failure(self, mock_openai):
        """Should raise exception after retries exhausted."""
        # Mock OpenAI client to raise exception
        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API Error")
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator()
        text = "Test text"
        
        with pytest.raises(Exception, match="API Error"):
            generator.generate_embedding(text)
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_long_text(self, mock_openai):
        """Should handle long text correctly."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 3072)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator()
        # Create long text (> 100 chars for preview truncation)
        text = "This is a very long text. " * 50
        
        embedding = generator.generate_embedding(text)
        
        assert len(embedding) == 3072
        # Verify full text was sent to API (not truncated)
        mock_client.embeddings.create.assert_called_once()
        call_args = mock_client.embeddings.create.call_args
        assert call_args[1]['input'] == text
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_custom_dimensions(self, mock_openai):
        """Should use custom dimensions when specified."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create.return_value = mock_response
        mock_openai.return_value = mock_client
        
        generator = EmbeddingGenerator(dimensions=1536)
        text = "Test text"
        
        embedding = generator.generate_embedding(text)
        
        assert len(embedding) == 1536
        mock_client.embeddings.create.assert_called_once_with(
            model="text-embedding-3-large",
            input=text,
            dimensions=1536
        )
    
    @patch('ingestion_pipeline.embedder.OpenAI')
    def test_generate_embedding_returns_zero_vector_on_empty(self, mock_openai):
        """Should return zero vector with correct dimensions for empty text."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # Test with custom dimensions
        generator = EmbeddingGenerator(dimensions=1536)
        
        embedding = generator.generate_embedding("")
        
        assert len(embedding) == 1536
        assert all(val == 0.0 for val in embedding)

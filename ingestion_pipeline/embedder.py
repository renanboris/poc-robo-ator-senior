"""Embedding generation for the ingestion pipeline."""

import logging
import os
from typing import List
from openai import OpenAI

from .utils import retry_with_backoff

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generates vector embeddings using OpenAI API.
    
    Uses text-embedding-3-large model with 3072 dimensions
    for semantic similarity search.
    """
    
    def __init__(self, model: str = "text-embedding-3-large", dimensions: int = 3072):
        """Initialize with OpenAI client.
        
        Args:
            model: OpenAI embedding model name
            dimensions: Embedding vector dimensions (1536 or 3072)
        """
        self.model = model
        self.dimensions = dimensions
        
        # Initialize OpenAI client with API key from environment
        # The OpenAI client automatically reads OPENAI_API_KEY from environment
        api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            logger.error("OPENAI_API_KEY not found in environment!")
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        logger.info(f"OPENAI_API_KEY found: {api_key[:10]}...{api_key[-4:]}")
        
        try:
            self.client = OpenAI(api_key=api_key)
            logger.info(
                f"Initialized EmbeddingGenerator with model={model}, "
                f"dimensions={dimensions}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector with retry logic.
        
        Args:
            text: Text content to embed
            
        Returns:
            3072-dimensional float vector
            
        Raises:
            Exception: If embedding generation fails after all retries
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding generation")
            return [0.0] * self.dimensions
        
        # Truncate text preview for logging
        text_preview = text[:100] + "..." if len(text) > 100 else text
        
        def _generate():
            """Internal function for retry wrapper."""
            try:
                logger.debug(f"Calling OpenAI API with model={self.model}, dimensions={self.dimensions}")
                response = self.client.embeddings.create(
                    model=self.model,
                    input=text,
                    dimensions=self.dimensions
                )
                logger.debug(f"OpenAI API response received successfully")
                return response.data[0].embedding
            except Exception as e:
                logger.error(
                    f"Embedding generation failed for text: '{text_preview}'. "
                    f"Error type: {type(e).__name__}, Error: {e}"
                )
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        
        try:
            # Call with retry logic: up to 3 attempts with exponential backoff [1, 2, 4]
            embedding = retry_with_backoff(
                func=_generate,
                max_retries=3,
                delays=[1, 2, 4],
                exceptions=(Exception,)
            )
            
            logger.debug(
                f"Successfully generated embedding for text: '{text_preview}'"
            )
            
            return embedding
        
        except Exception as e:
            # Log final failure with chunk text preview
            logger.error(
                f"Failed to generate embedding after retries for text: '{text_preview}'. "
                f"Error: {e}"
            )
            raise

"""Vector injection to Pinecone for the ingestion pipeline."""

import logging
import re
from typing import Any, Dict, List

from pinecone import Pinecone

from .config import Vector
from .utils import retry_with_backoff, sanitize_filename

logger = logging.getLogger(__name__)


class VectorInjector:
    """Injects vectors to Pinecone with namespace segregation.
    
    Derives namespace from nivel_2 metadata field and constructs
    unique vector IDs in the format: {nivel_2}_{titulo_sanitized}_{chunk_index}
    """

    def __init__(self, api_key: str, index_name: str):
        """Initialize with Pinecone client.
        
        Args:
            api_key: Pinecone API key
            index_name: Name of the Pinecone index
        """
        self.api_key = api_key
        self.index_name = index_name

        # Initialize Pinecone client
        self.pc = Pinecone(api_key=api_key)

        # Connect to the index
        self.index = self.pc.Index(index_name)

        logger.info(f"Initialized VectorInjector with index={index_name}")

    def _derive_namespace(self, nivel_2: str) -> str:
        """Derive namespace from nivel_2 metadata field.
        
        Args:
            nivel_2: Second hierarchy level (module name)
            
        Returns:
            Normalized namespace string (fallback to "senior_default" if empty)
        """
        if not nivel_2 or not nivel_2.strip():
            return "senior_default"

        # Normalize: lowercase, replace spaces/special chars with underscores
        namespace = nivel_2.lower()
        namespace = re.sub(r'[^a-z0-9]+', '_', namespace)
        namespace = namespace.strip('_')
        namespace = re.sub(r'_+', '_', namespace)

        return namespace if namespace else "senior_default"

    def _generate_vector_id(
        self,
        nivel_2: str,
        titulo: str,
        chunk_index: int
    ) -> str:
        """Generate unique vector ID.
        
        Format: {nivel_2}_{titulo_sanitized}_{chunk_index}
        
        Args:
            nivel_2: Second hierarchy level (module name)
            titulo: Page title
            chunk_index: Sequential chunk index
            
        Returns:
            Unique vector ID string
        """
        # Sanitize nivel_2 and titulo
        nivel_2_clean = sanitize_filename(nivel_2) if nivel_2 else "default"
        titulo_clean = sanitize_filename(titulo) if titulo else "untitled"

        # Construct ID
        vector_id = f"{nivel_2_clean}_{titulo_clean}_{chunk_index}"

        return vector_id

    def inject_vector(
        self,
        embedding: List[float],
        metadata: Dict[str, Any],
        chunk_index: int
    ) -> bool:
        """Upsert single vector to Pinecone with retry logic.
        
        Args:
            embedding: Embedding vector (3072-dimensional float list)
            metadata: Dictionary containing url, nivel_1, nivel_2, titulo, text
            chunk_index: Sequential chunk index
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Derive namespace from nivel_2
            namespace = self._derive_namespace(metadata.get("nivel_2", ""))

            # Generate vector ID
            vector_id = self._generate_vector_id(
                nivel_2=metadata.get("nivel_2", ""),
                titulo=metadata.get("titulo", ""),
                chunk_index=chunk_index
            )

            # Construct metadata payload
            vector_metadata = {
                "url": metadata.get("url", ""),
                "nivel_1": metadata.get("nivel_1", ""),
                "nivel_2": metadata.get("nivel_2", ""),
                "titulo": metadata.get("titulo", ""),
                "text": metadata.get("text", ""),
            }

            # Create Vector object
            vector = Vector(
                id=vector_id,
                values=embedding,
                metadata=vector_metadata,
                namespace=namespace
            )

            # Upsert with retry logic
            def _upsert():
                """Internal function for retry wrapper."""
                self.index.upsert(
                    vectors=[vector.to_pinecone_format()],
                    namespace=namespace
                )

            retry_with_backoff(
                func=_upsert,
                max_retries=3,
                delays=[1, 2, 4],
                exceptions=(Exception,)
            )

            logger.info(
                f"Successfully upserted vector: id={vector_id}, namespace={namespace}"
            )

            return True

        except Exception as e:
            logger.error(
                f"Failed to upsert vector after retries: "
                f"nivel_2={metadata.get('nivel_2')}, "
                f"titulo={metadata.get('titulo')}, "
                f"chunk_index={chunk_index}. "
                f"Error: {e}"
            )
            return False

    def inject_batch(
        self,
        vectors: List[Dict[str, Any]],
        batch_size: int = 100
    ) -> Dict[str, int]:
        """Batch upsert vectors to Pinecone.
        
        Args:
            vectors: List of dicts with 'embedding', 'metadata', 'chunk_index' keys
            batch_size: Number of vectors per upsert call (default: 100)
            
        Returns:
            Dictionary with 'success' and 'failed' counts
        """
        success_count = 0
        failed_count = 0

        # Group vectors by namespace for efficient batching
        vectors_by_namespace: Dict[str, List[Dict[str, Any]]] = {}

        for vector_data in vectors:
            embedding = vector_data.get("embedding", [])
            metadata = vector_data.get("metadata", {})
            chunk_index = vector_data.get("chunk_index", 0)

            # Derive namespace
            namespace = self._derive_namespace(metadata.get("nivel_2", ""))

            # Generate vector ID
            vector_id = self._generate_vector_id(
                nivel_2=metadata.get("nivel_2", ""),
                titulo=metadata.get("titulo", ""),
                chunk_index=chunk_index
            )

            # Construct metadata payload
            vector_metadata = {
                "url": metadata.get("url", ""),
                "nivel_1": metadata.get("nivel_1", ""),
                "nivel_2": metadata.get("nivel_2", ""),
                "titulo": metadata.get("titulo", ""),
                "text": metadata.get("text", ""),
            }

            # Create Vector object
            vector = Vector(
                id=vector_id,
                values=embedding,
                metadata=vector_metadata,
                namespace=namespace
            )

            # Group by namespace
            if namespace not in vectors_by_namespace:
                vectors_by_namespace[namespace] = []

            vectors_by_namespace[namespace].append({
                "vector": vector,
                "chunk_index": chunk_index
            })

        # Process each namespace
        for namespace, namespace_vectors in vectors_by_namespace.items():
            logger.info(
                f"Processing {len(namespace_vectors)} vectors for namespace={namespace}"
            )

            # Process in batches
            for i in range(0, len(namespace_vectors), batch_size):
                batch = namespace_vectors[i:i + batch_size]

                try:
                    # Prepare batch for upsert
                    pinecone_vectors = [
                        item["vector"].to_pinecone_format()
                        for item in batch
                    ]

                    # Upsert with retry logic
                    def _upsert_batch():
                        """Internal function for retry wrapper."""
                        self.index.upsert(
                            vectors=pinecone_vectors,
                            namespace=namespace
                        )

                    retry_with_backoff(
                        func=_upsert_batch,
                        max_retries=3,
                        delays=[1, 2, 4],
                        exceptions=(Exception,)
                    )

                    success_count += len(batch)

                    logger.info(
                        f"Successfully upserted batch of {len(batch)} vectors "
                        f"to namespace={namespace}"
                    )

                except Exception as e:
                    failed_count += len(batch)

                    logger.error(
                        f"Failed to upsert batch after retries: "
                        f"namespace={namespace}, batch_size={len(batch)}. "
                        f"Error: {e}"
                    )

        return {
            "success": success_count,
            "failed": failed_count
        }

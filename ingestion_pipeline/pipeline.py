"""Pipeline orchestration for the ingestion pipeline."""

import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .chunker import Chunker
from .config import PipelineConfig, PipelineReport
from .crawler import SitemapCrawler
from .embedder import EmbeddingGenerator
from .extractor import SemanticExtractor
from .injector import VectorInjector
from .utils import log_error, log_stage_complete, log_stage_start, log_url_processing
from .validator import ContentValidator

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates the Web Knowledge Ingestion Pipeline.
    
    Executes 5 sequential stages:
    1. Discovery: Crawl sitemap → List[URL]
    2. Extraction: Fetch pages → List[ExtractedContent]
    3. Validation: Filter quality → List[ValidContent]
    4. Chunking: Split content → List[Chunk]
    5. Embedding: Generate vectors → List[Vector]
    6. Injection: Upsert to Pinecone → Report
    """

    def __init__(self, config: PipelineConfig):
        """Initialize pipeline with configuration.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config

        # Initialize components
        self.crawler: Optional[SitemapCrawler] = None
        self.extractor = SemanticExtractor(extraction_backend=config.extraction_backend)
        self.validator = ContentValidator()
        self.chunker = Chunker(
            chunk_size=config.chunk_size,
            chunk_overlap=config.chunk_overlap
        )
        self.embedder = EmbeddingGenerator(
            model=config.embedding_model,
            dimensions=config.embedding_dimensions
        )
        self.injector = VectorInjector(
            api_key=config.pinecone_api_key,
            index_name=config.pinecone_index_name
        )

        # Cache for incremental mode
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_file = Path(config.cache_file)

        logger.info("Initialized IngestionPipeline with all components")

    def load_cache(self) -> None:
        """Load cache from file for incremental mode.
        
        Cache structure: URL → {content_hash, last_updated, vector_count}
        """
        if not self.cache_file.exists():
            logger.info("No cache file found, starting with empty cache")
            self.cache = {}
            return

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                self.cache = json.load(f)

            logger.info(f"Loaded cache with {len(self.cache)} entries")

        except Exception as e:
            logger.error(f"Failed to load cache: {e}. Starting with empty cache")
            self.cache = {}

    def save_cache(self) -> None:
        """Save cache to file atomically."""
        try:
            # Write to temporary file first
            temp_file = self.cache_file.with_suffix('.tmp')

            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self.cache_file)

            logger.info(f"Saved cache with {len(self.cache)} entries")

        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _compute_content_hash(self, markdown: str) -> str:
        """Compute SHA-256 hash of Markdown content.
        
        Args:
            markdown: Markdown content
            
        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(markdown.encode('utf-8')).hexdigest()

    def _is_cached(self, url: str, markdown: str) -> bool:
        """Check if URL content is cached and unchanged.
        
        Args:
            url: URL to check
            markdown: Current Markdown content
            
        Returns:
            True if cached and unchanged, False otherwise
        """
        if url not in self.cache:
            return False

        cached_entry = self.cache[url]
        current_hash = self._compute_content_hash(markdown)
        cached_hash = cached_entry.get("content_hash", "")

        return current_hash == cached_hash

    def _update_cache(
        self,
        url: str,
        markdown: str,
        vector_count: int
    ) -> None:
        """Update cache entry for URL.
        
        Args:
            url: URL to update
            markdown: Markdown content
            vector_count: Number of vectors created
        """
        content_hash = self._compute_content_hash(markdown)

        self.cache[url] = {
            "content_hash": content_hash,
            "last_updated": datetime.now().isoformat(),
            "vector_count": vector_count
        }

    def run_stage(
        self,
        stage_name: str,
        stage_func: callable,
        input_data: Any
    ) -> Any:
        """Execute single stage with error handling.
        
        Args:
            stage_name: Name of the stage
            stage_func: Function to execute
            input_data: Input data for the stage
            
        Returns:
            Stage output data
        """
        log_stage_start(stage_name)
        start_time = time.time()

        try:
            output_data = stage_func(input_data)
            duration = time.time() - start_time

            # Count output items
            count = len(output_data) if isinstance(output_data, list) else 1
            log_stage_complete(stage_name, count, duration)

            return output_data

        except Exception as e:
            duration = time.time() - start_time
            log_error(
                message=f"Stage {stage_name} failed after {duration:.2f}s",
                stage=stage_name,
                error=e
            )
            raise

    async def run(
        self,
        sitemap_url: str,
        incremental: bool = False,
        module_filter: Optional[str] = None
    ) -> PipelineReport:
        """Execute full pipeline and return summary report.
        
        Args:
            sitemap_url: URL of the sitemap.xml
            incremental: Enable incremental mode (skip unchanged URLs)
            module_filter: Optional module name to filter URLs (e.g., 'hcm', 'financeiro')
            
        Returns:
            PipelineReport with execution metrics
        """
        start_time = datetime.now()

        # Initialize metrics
        metrics = {
            "urls_discovered": 0, "urls_fetched": 0, "urls_validated": 0,
            "chunks_created": 0, "embeddings_generated": 0, "vectors_injected": 0,
            "failed_fetches": 0, "failed_validations": 0, "failed_embeddings": 0,
            "failed_upserts": 0, "skipped_low_quality": 0, "urls_skipped_cached": 0,
            "urls_skipped_module_filter": 0, "processed_count": 0
        }

        # Load cache if incremental mode
        if incremental:
            self.load_cache()

        try:
            # Stage 1: Discovery
            logger.info(f"Starting pipeline for sitemap: {sitemap_url}")
            self.crawler = SitemapCrawler(sitemap_url)
            urls = self.crawler.crawl()  # Call directly without run_stage
            metrics["urls_discovered"] = len(urls)
            logger.info(f"Discovery completed: {metrics['urls_discovered']} URLs found")

            # Apply module filter if specified
            if module_filter:
                logger.info(f"Applying module filter: {module_filter}")
                filtered_urls = []
                for url in urls:
                    # Extract nivel_2 from URL to check if it matches the filter
                    breadcrumbs = self.extractor.extract_breadcrumbs(url)

                    if module_filter.lower() in url.lower():
                        filtered_urls.append(url)
                    else:
                        metrics["urls_skipped_module_filter"] += 1

                urls = filtered_urls
                logger.info(f"Module filter applied: {len(urls)} URLs match module '{module_filter}'")

            # Stage 2-6: Process each URL asynchronously
            all_vectors = []
            total_urls = len(urls)
            
            semaphore = asyncio.Semaphore(5)  # Limite de 5 browsers simultâneos para não explodir memória
            print_lock = asyncio.Lock()

            async def process_url(idx: int, url: str):
                async with semaphore:
                    short_url = url.split('/')[-1] if '/' in url else url
                    
                    try:
                        # Stage 2: Extraction (async)
                        content = await self.extractor.extract_content(url)

                        if not content:
                            async with print_lock:
                                metrics["processed_count"] += 1
                                pct = (metrics["processed_count"] / total_urls) * 100
                                print(f"\r[{metrics['processed_count']}/{total_urls}] ({pct:.0f}%) ❌ FALHOU (sem conteúdo): {short_url[:50]:<50}", end="", flush=True)
                            metrics["failed_fetches"] += 1
                            return None

                        metrics["urls_fetched"] += 1

                        # Check cache in incremental mode
                        if incremental and self._is_cached(url, content["markdown"]):
                            log_url_processing(url, "cache", "skipped")
                            async with print_lock:
                                metrics["processed_count"] += 1
                                pct = (metrics["processed_count"] / total_urls) * 100
                                print(f"\r[{metrics['processed_count']}/{total_urls}] ({pct:.0f}%) ⏭️  CACHE SKIP: {short_url[:50]:<50}", end="", flush=True)
                            metrics["urls_skipped_cached"] += 1
                            return None

                        # Stage 3: Validation (sync -> thread)
                        is_valid, reason = await asyncio.to_thread(self.validator.validate, content)

                        if not is_valid:
                            async with print_lock:
                                metrics["processed_count"] += 1
                                pct = (metrics["processed_count"] / total_urls) * 100
                                print(f"\r[{metrics['processed_count']}/{total_urls}] ({pct:.0f}%) ⚠️  SKIP ({reason[:20]}): {short_url[:40]:<40}", end="", flush=True)
                            metrics["failed_validations"] += 1
                            metrics["skipped_low_quality"] += 1
                            return None

                        metrics["urls_validated"] += 1

                        # Stage 4: Chunking (sync -> thread)
                        chunks = await asyncio.to_thread(
                            self.chunker.chunk_content,
                            markdown=content["markdown"],
                            metadata={
                                "url": content["url"],
                                "titulo": content["titulo"],
                                "nivel_1": content["nivel_1"],
                                "nivel_2": content["nivel_2"],
                                "nivel_3": content.get("nivel_3", ""),
                            }
                        )

                        metrics["chunks_created"] += len(chunks)
                        
                        async with print_lock:
                            metrics["processed_count"] += 1
                            pct = (metrics["processed_count"] / total_urls) * 100
                            print(f"\r[{metrics['processed_count']}/{total_urls}] ({pct:.0f}%) ✅ {content['titulo'][:30]} → {len(chunks)} chunks".ljust(80), end="", flush=True)

                        # Stage 5: Embedding
                        url_vectors = []
                        for chunk in chunks:
                            try:
                                embedding = await asyncio.to_thread(self.embedder.generate_embedding, chunk.text)
                                metrics["embeddings_generated"] += 1

                                url_vectors.append({
                                    "embedding": embedding,
                                    "metadata": {
                                        **chunk.metadata,
                                        "text": chunk.text
                                    },
                                    "chunk_index": chunk.chunk_index
                                })

                            except Exception as e:
                                metrics["failed_embeddings"] += 1
                                log_error(
                                    message="Embedding generation failed",
                                    stage="embedding",
                                    error=e,
                                    url=url,
                                    chunk_index=chunk.chunk_index
                                )

                        # Update cache
                        if incremental:
                            self._update_cache(url, content["markdown"], len(chunks))
                            
                        return url_vectors

                    except Exception as e:
                        metrics["failed_fetches"] += 1
                        async with print_lock:
                            metrics["processed_count"] += 1
                            pct = (metrics["processed_count"] / total_urls) * 100
                            print(f"\r[{metrics['processed_count']}/{total_urls}] ({pct:.0f}%) 💥 ERRO: {str(e)[:40]:<40}", end="", flush=True)
                        log_error(
                            message="URL processing failed",
                            stage="extraction",
                            error=e,
                            url=url
                        )
                        return None

            # Execute tasks concurrently
            tasks = [process_url(idx, url) for idx, url in enumerate(urls, 1)]
            results = await asyncio.gather(*tasks)
            
            # Aggregate vectors
            for res in results:
                if res:
                    all_vectors.extend(res)

            # Final newline after progress
            print(f"\n\n📊 Extração concluída: {metrics['urls_validated']} válidas, {metrics['failed_fetches']} falhas, {metrics['skipped_low_quality']} baixa qualidade")

            # Stage 6: Injection (batch)
            if all_vectors:
                print(f"💉 Injetando {len(all_vectors)} vetores no Pinecone...")
                logger.info(f"Injecting {len(all_vectors)} vectors to Pinecone")

                injection_result = await asyncio.to_thread(
                    self.injector.inject_batch,
                    vectors=all_vectors,
                    batch_size=self.config.batch_size
                )

                metrics["vectors_injected"] = injection_result["success"]
                metrics["failed_upserts"] = injection_result["failed"]

            # Save cache if incremental mode
            if incremental:
                self.save_cache()

        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            raise

        finally:
            # Generate report
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            report = PipelineReport(
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                urls_discovered=metrics["urls_discovered"],
                urls_fetched=metrics["urls_fetched"],
                urls_validated=metrics["urls_validated"],
                chunks_created=metrics["chunks_created"],
                embeddings_generated=metrics["embeddings_generated"],
                vectors_injected=metrics["vectors_injected"],
                failed_fetches=metrics["failed_fetches"],
                failed_validations=metrics["failed_validations"],
                failed_embeddings=metrics["failed_embeddings"],
                failed_upserts=metrics["failed_upserts"],
                skipped_low_quality=metrics["skipped_low_quality"],
                urls_skipped_cached=metrics["urls_skipped_cached"],
                urls_skipped_module_filter=metrics["urls_skipped_module_filter"]
            )

            return report

# Implementation Plan: Web Knowledge Ingestion Pipeline (RAG)

## Overview

This implementation plan creates a Python-based ETL pipeline that automates the extraction, transformation, and injection of documentation content from the Senior documentation portal into the Pinecone vector database. The pipeline consists of 7 core components orchestrated through 5 sequential stages: Discovery → Extraction → Processing → Embedding → Injection.

The implementation integrates with the existing Training OS infrastructure, using the same Pinecone index and OpenAI embedding model as `dap_engine.py`, while adding namespace segregation for module-scoped retrieval.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create `ingestion_pipeline/` directory with module structure
  - Create `__init__.py`, `__main__.py`, `config.py`, `utils.py`
  - Create `requirements.txt` with core dependencies: `openai>=1.0.0`, `pinecone-client>=3.0.0`, `langchain>=0.1.0`, `beautifulsoup4>=4.12.0`, `lxml>=4.9.0`, `requests>=2.31.0`, `python-dotenv>=1.0.0`
  - Add development dependencies: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`, `pytest-mock>=3.11.0`
  - Create `.env.example` with required environment variables
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [ ] 2. Implement configuration and data models
  - [x] 2.1 Create configuration dataclasses in `config.py`
    - Implement `PipelineConfig` with API keys, chunking parameters, retry settings
    - Add validation for required environment variables
    - Add support for both Crawl4AI and Firecrawl backend selection
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [x] 2.2 Create data models in `config.py`
    - Implement `ExtractedContent` dataclass with url, titulo, markdown, nivel_1, nivel_2, nivel_3
    - Implement `Chunk` dataclass with text, chunk_index, metadata
    - Implement `Vector` dataclass with id, values, metadata, namespace
    - Implement `PipelineReport` dataclass with timing, stage metrics, failure counts
    - _Requirements: 2.5, 3.5, 4.5, 6.3_

- [ ] 3. Implement shared utilities
  - [x] 3.1 Create retry logic with exponential backoff in `utils.py`
    - Implement `retry_with_backoff()` function accepting callable, max_retries, delays, exceptions
    - Support configurable retry delays (default: [1, 2, 4] seconds)
    - Log retry attempts with attempt number and delay
    - _Requirements: 5.3, 6.5, 10.3, 10.4_
  
  - [x] 3.2 Create structured logging setup in `utils.py`
    - Configure JSON-formatted logging with timestamp, level, stage, context
    - Set up log rotation (10MB per file, keep last 5 files)
    - Add helper functions for logging with context (url, chunk_index, stage_name)
    - _Requirements: 10.1, 10.2, 10.4, 12.1, 12.2, 12.4_
  
  - [ ]* 3.3 Write unit tests for retry logic
    - Test successful execution after transient failures
    - Test exhaustion of retry attempts
    - Test exponential backoff timing
    - _Requirements: 10.3, 10.4_

- [ ] 4. Implement Sitemap Crawler component
  - [x] 4.1 Create `SitemapCrawler` class in `crawler.py`
    - Implement `__init__()` accepting sitemap_url
    - Implement `fetch_sitemap()` with retry logic for HTTP requests
    - Implement `parse_sitemap()` using BeautifulSoup/lxml to extract URLs from XML
    - Implement `filter_urls()` to include `/senior-x/*` and `/produto/*` patterns
    - Implement `filter_urls()` to exclude URLs with keywords: termos-de-uso, politica-privacidade, contato, home, sobre
    - Implement `crawl()` orchestrating fetch → parse → filter
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_
  
  - [ ]* 4.2 Write unit tests for URL filtering
    - Test inclusion of valid documentation URLs
    - Test exclusion of non-documentation pages
    - Test handling of malformed URLs
    - _Requirements: 1.3, 1.4_

- [ ] 5. Implement Semantic Extractor component
  - [x] 5.1 Create `SemanticExtractor` class in `extractor.py`
    - Implement `__init__()` accepting extraction_backend parameter (crawl4ai or firecrawl)
    - Implement backend initialization for Crawl4AI (local) or Firecrawl API (managed)
    - Configure content cleaning rules: remove navigation, footers, modals, preserve main/article
    - _Requirements: 2.1, 2.2, 9.4, 9.5_
  
  - [x] 5.2 Implement content extraction in `extractor.py`
    - Implement `extract_content()` fetching HTML and converting to Markdown
    - Extract page title from `<title>` tag or main `<h1>` heading
    - Preserve semantic structure: headings, lists, code blocks
    - Return structured dict with url, titulo, markdown fields
    - _Requirements: 2.1, 2.3, 2.4, 2.5_
  
  - [x] 5.3 Implement breadcrumb hierarchy extraction in `extractor.py`
    - Implement `extract_breadcrumbs()` parsing URL path segments
    - Extract nivel_1 (first segment), nivel_2 (second segment), nivel_3 (third segment)
    - Implement `normalize_hierarchy()` converting to lowercase kebab-case
    - Handle URLs with fewer than 3 hierarchy levels (leave empty)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [ ]* 5.4 Write unit tests for breadcrumb extraction
    - Test 3-level URL hierarchy extraction
    - Test 2-level URL hierarchy (nivel_3 empty)
    - Test hierarchy normalization (lowercase, kebab-case)
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 6. Implement Content Validator component
  - [x] 6.1 Create `ContentValidator` class in `validator.py`
    - Implement `validate()` returning (is_valid, reason) tuple
    - Implement `check_min_length()` verifying content >= 100 characters
    - Implement `check_has_heading()` verifying at least one Markdown heading exists
    - Implement `check_link_density()` verifying link density <= 70%
    - Log validation failures with URL and reason
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ]* 6.2 Write unit tests for content validation
    - Test minimum length validation
    - Test heading presence validation
    - Test link density calculation and threshold
    - _Requirements: 13.1, 13.2, 13.4_

- [ ] 7. Implement Chunker component
  - [x] 7.1 Create `Chunker` class in `chunker.py`
    - Implement `__init__()` with chunk_size=800 and chunk_overlap=100 parameters
    - Initialize LangChain `MarkdownHeaderTextSplitter` for semantic splitting
    - Initialize fallback `RecursiveCharacterTextSplitter` for content without headers
    - _Requirements: 4.1, 4.2, 4.3_
  
  - [x] 7.2 Implement content chunking in `chunker.py`
    - Implement `chunk_content()` accepting markdown and metadata
    - Split content using MarkdownHeaderTextSplitter, fallback to RecursiveCharacterTextSplitter
    - Preserve semantic boundaries (respect headers and list structures)
    - Return list of chunks with text, chunk_index, metadata
    - _Requirements: 4.1, 4.4, 4.5_
  
  - [ ]* 7.3 Write unit tests for chunking
    - Test semantic splitting with Markdown headers
    - Test fallback splitting for content without headers
    - Test chunk size and overlap configuration
    - _Requirements: 4.2, 4.3, 4.4_

- [x] 8. Checkpoint - Ensure all tests pass
  - Run pytest suite for all implemented components
  - Verify no regressions in existing functionality
  - Ensure all tests pass, ask the user if questions arise

- [ ] 9. Implement Embedding Generator component
  - [x] 9.1 Create `EmbeddingGenerator` class in `embedder.py`
    - Implement `__init__()` with model="text-embedding-3-large" and dimensions=3072
    - Initialize OpenAI client with API key from environment
    - _Requirements: 5.1, 5.2, 9.1_
  
  - [x] 9.2 Implement embedding generation in `embedder.py`
    - Implement `generate_embedding()` calling OpenAI API with retry logic
    - Configure retry: up to 3 attempts with exponential backoff [1, 2, 4]
    - Log embedding failures with chunk text preview (first 100 chars)
    - Return 3072-dimensional float vector
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
  
  - [ ]* 9.3 Write unit tests for embedding generation
    - Test successful embedding generation (mocked OpenAI API)
    - Test retry logic on transient failures
    - Test error logging with chunk preview
    - _Requirements: 5.3, 5.4_

- [ ] 10. Implement Vector Injector component
  - [x] 10.1 Create `VectorInjector` class in `injector.py`
    - Implement `__init__()` accepting index_name parameter
    - Initialize Pinecone client with API key from environment
    - Connect to specified Pinecone index
    - _Requirements: 6.4, 9.2, 9.3_
  
  - [x] 10.2 Implement namespace derivation and vector ID generation in `injector.py`
    - Implement helper function to derive namespace from nivel_2 (fallback to "senior_default")
    - Normalize namespace: lowercase, replace spaces/special chars with underscores
    - Implement vector ID format: `{nivel_2}_{titulo_sanitized}_{chunk_index}`
    - Sanitize titulo for ID: lowercase, remove special chars, replace spaces with hyphens
    - _Requirements: 6.1, 6.2_
  
  - [x] 10.3 Implement vector injection in `injector.py`
    - Implement `inject_vector()` upserting single vector to Pinecone with namespace
    - Construct metadata payload with fields: url, nivel_1, nivel_2, titulo, text
    - Implement `inject_batch()` for batch upsert (100 vectors per call)
    - Add retry logic: up to 3 attempts with exponential backoff [1, 2, 4]
    - Log successful upserts with namespace and vector ID
    - Log upsert failures with vector ID and error message
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [ ]* 10.4 Write unit tests for vector injection
    - Test namespace derivation from nivel_2
    - Test vector ID generation and sanitization
    - Test metadata payload construction
    - Test batch upsert logic (mocked Pinecone)
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 11. Implement Pipeline Orchestrator
  - [x] 11.1 Create `IngestionPipeline` class in `pipeline.py`
    - Implement `__init__()` accepting PipelineConfig
    - Initialize all components: SitemapCrawler, SemanticExtractor, ContentValidator, Chunker, EmbeddingGenerator, VectorInjector
    - Set up structured logging for pipeline execution
    - _Requirements: 8.1, 8.2_
  
  - [x] 11.2 Implement stage execution with error handling in `pipeline.py`
    - Implement `run_stage()` executing single stage with try-catch error handling
    - Log stage transitions with timestamps
    - Track success/failure counts per stage
    - Continue processing on item-level failures (never abort entire pipeline)
    - _Requirements: 8.3, 8.4, 10.1, 10.2, 10.5, 12.1, 12.2_
  
  - [x] 11.3 Implement full pipeline execution in `pipeline.py`
    - Implement `run()` orchestrating all 5 stages sequentially
    - Stage 1 (Discovery): Crawl sitemap → List[URL]
    - Stage 2 (Extraction): Fetch pages → List[ExtractedContent]
    - Stage 3 (Validation): Filter quality → List[ValidContent]
    - Stage 4 (Chunking): Split content → List[Chunk]
    - Stage 5 (Embedding): Generate vectors → List[Vector]
    - Stage 6 (Injection): Upsert to Pinecone → Report
    - _Requirements: 8.2, 8.3_
  
  - [x] 11.4 Implement pipeline reporting in `pipeline.py`
    - Generate PipelineReport with timing, stage metrics, failure counts
    - Implement `PipelineReport.print_summary()` for human-readable console output
    - Log total duration, URLs processed, chunks created, vectors injected
    - Log failure counts per stage
    - _Requirements: 8.5, 12.3, 12.5_

- [ ] 12. Implement incremental update support
  - [x] 12.1 Create cache management in `pipeline.py`
    - Implement cache file structure: URL → {content_hash, last_updated, vector_count}
    - Implement `load_cache()` reading from `.ingestion_cache.json`
    - Implement `save_cache()` writing updated cache atomically
    - _Requirements: 11.2, 11.3_
  
  - [x] 12.2 Implement incremental mode logic in `pipeline.py`
    - Add `incremental` parameter to `run()` method
    - Compute SHA-256 hash of Markdown content for each URL
    - Compare content hash with cached hash
    - Skip processing if hash matches (log "cached")
    - Process and update cache if hash mismatches or URL is new
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_
  
  - [ ]* 12.3 Write unit tests for incremental mode
    - Test cache loading and saving
    - Test content hash computation
    - Test URL skipping on cache hit
    - Test cache update on cache miss
    - _Requirements: 11.3, 11.4, 11.5_

- [x] 13. Checkpoint - Ensure all tests pass
  - Run pytest suite for pipeline orchestrator and incremental mode
  - Verify error handling and resilience
  - Ensure all tests pass, ask the user if questions arise

- [ ] 14. Implement CLI interface
  - [x] 14.1 Create CLI entrypoint in `__main__.py`
    - Implement argument parser accepting sitemap URL as positional argument
    - Add `--incremental` flag for incremental mode
    - Add `--dry-run` flag for simulation without upserting
    - Add `--backend` option to choose extraction backend (crawl4ai or firecrawl)
    - Add `--list-namespaces` command to query and list Pinecone namespaces
    - Add `--delete-namespace` command to delete vectors in specified namespace
    - _Requirements: 8.1, 14.1, 14.2, 14.4_
  
  - [x] 14.2 Implement namespace management commands in `__main__.py`
    - Implement `list_namespaces()` querying Pinecone index stats and printing namespaces with vector counts
    - Implement `delete_namespace()` with confirmation prompt before deletion
    - Implement dry-run mode logging operations without executing
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 14.3 Wire CLI to pipeline execution in `__main__.py`
    - Load configuration from environment variables
    - Validate required environment variables (exit with error if missing)
    - Instantiate IngestionPipeline with config
    - Execute pipeline with user-provided arguments
    - Print summary report to console
    - _Requirements: 8.1, 8.2, 8.5, 9.6_

- [ ] 15. Implement Aura DAP integration
  - [x] 15.1 Update `dap_engine.py` to support namespace parameter
    - Add optional `namespace` parameter to `buscar_contexto()` function signature
    - Pass namespace to Pinecone query operation when provided
    - Use default namespace "senior_default" when namespace is None
    - Preserve existing retrieval logic (score thresholding, top-k selection)
    - Include source URL from metadata in response context
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 15.2 Write integration tests for Aura DAP namespace retrieval
    - Test retrieval with namespace parameter
    - Test retrieval without namespace (default behavior)
    - Test source URL inclusion in response
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [x] 16. Create integration tests
  - [x] 16.1 Create test fixtures in `tests/test_integration.py`
    - Create sample sitemap.xml with 5-10 representative URLs
    - Set up test namespace in Pinecone for isolated testing
    - Create test configuration with test API keys and index name
    - _Requirements: 15.1, 15.2_
  
  - [x] 16.2 Write end-to-end integration test
    - Test full pipeline execution with sample sitemap
    - Verify all stages execute without errors
    - Verify vectors are injected into test namespace
    - Verify metadata payloads contain all required fields
    - Query test namespace and verify retrieval works
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [x] 16.3 Write error recovery integration test
    - Inject failures at each stage (mocked transient errors)
    - Verify pipeline continues processing remaining items
    - Verify failure counts are tracked correctly
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [x] 16.4 Write incremental mode integration test
    - Run pipeline twice with same sitemap
    - Verify cached URLs are skipped on second run
    - Verify cache file is updated correctly
    - _Requirements: 11.2, 11.3, 11.4, 11.5_
  
  - [x] 16.5 Write namespace segregation integration test
    - Process URLs with different nivel_2 values
    - Verify vectors are segregated by namespace
    - Query each namespace independently and verify isolation
    - _Requirements: 6.1, 6.4, 7.2_

- [ ] 17. Create documentation
  - [x] 17.1 Create README.md for ingestion_pipeline module
    - Document installation steps (dependencies, Playwright/Crawl4AI setup)
    - Document environment variable configuration
    - Document CLI usage with examples
    - Document extraction backend options (Crawl4AI vs Firecrawl)
    - Document incremental mode and cache management
    - _Requirements: 8.1, 9.1, 9.2, 9.3, 9.4, 9.5, 11.2_
  
  - [x] 17.2 Create ARCHITECTURE.md documenting pipeline design
    - Document 5-stage pipeline architecture
    - Document component responsibilities and interfaces
    - Document data flow and error handling strategy
    - Document integration with existing Training OS infrastructure
    - _Requirements: 8.2, 8.3, 8.4_
  
  - [x] 17.3 Update main project README.md
    - Add section describing Web Knowledge Ingestion Pipeline
    - Link to ingestion_pipeline/README.md for detailed documentation
    - Document Aura DAP namespace parameter usage
    - _Requirements: 7.1, 7.2, 8.1_

- [x] 18. Final checkpoint and validation
  - Run full test suite (unit + integration tests)
  - Execute pipeline against sample sitemap in test namespace
  - Verify Aura DAP can retrieve vectors from test namespace
  - Clean up test namespace after validation
  - Ensure all tests pass, ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at reasonable breaks
- Integration tests validate end-to-end correctness with real dependencies
- The pipeline integrates with existing `dap_engine.py` for namespace-scoped retrieval
- Python 3.10+ is required for dataclass features and type hints
- Crawl4AI is recommended for self-hosted extraction (no API costs)
- Firecrawl API is an alternative for simpler setup (pay-per-use)

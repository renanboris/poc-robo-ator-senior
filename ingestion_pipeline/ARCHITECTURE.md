# Architecture: Web Knowledge Ingestion Pipeline

## Overview

The Web Knowledge Ingestion Pipeline is a Python-based ETL system that automates the extraction, transformation, and injection of documentation content from web sources into the Pinecone vector database. This document describes the architectural design, component interactions, data flow, and error handling strategies.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Web Knowledge Ingestion Pipeline             │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 1: Discovery                                              │
│  ┌──────────────┐                                                │
│  │ Sitemap      │  Fetch sitemap.xml                             │
│  │ Crawler      │  Parse XML, extract URLs                       │
│  │              │  Filter documentation pages                    │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    List[URL]                                                     │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 2: Extraction                                             │
│  ┌──────────────┐                                                │
│  │ Semantic     │  Fetch HTML pages                              │
│  │ Extractor    │  Extract clean content as Markdown             │
│  │              │  Extract breadcrumb hierarchy                  │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    List[ExtractedContent]                                        │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 3: Validation                                             │
│  ┌──────────────┐                                                │
│  │ Content      │  Check minimum length                          │
│  │ Validator    │  Check heading presence                        │
│  │              │  Check link density                            │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    List[ValidContent]                                            │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 4: Chunking                                               │
│  ┌──────────────┐                                                │
│  │ Chunker      │  Split Markdown by headers                     │
│  │              │  Preserve semantic boundaries                  │
│  │              │  ~800 tokens, 100 token overlap                │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    List[Chunk]                                                   │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 5: Embedding                                              │
│  ┌──────────────┐                                                │
│  │ Embedding    │  Generate embeddings via OpenAI                │
│  │ Generator    │  text-embedding-3-large (3072 dims)            │
│  │              │  Retry with exponential backoff                │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    List[Vector]                                                  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│  Stage 6: Injection                                              │
│  ┌──────────────┐                                                │
│  │ Vector       │  Derive namespace from nivel_2                 │
│  │ Injector     │  Generate unique vector IDs                    │
│  │              │  Batch upsert to Pinecone (100/batch)          │
│  └──────────────┘                                                │
│         │                                                         │
│         ▼                                                         │
│    PipelineReport                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Sitemap Crawler (`crawler.py`)

**Responsibility**: Discover documentation URLs from sitemap.xml

**Key Methods**:
- `fetch_sitemap()`: HTTP fetch with retry logic
- `parse_sitemap()`: XML parsing using BeautifulSoup/lxml
- `filter_urls()`: Apply inclusion/exclusion rules
- `crawl()`: Orchestrate fetch → parse → filter

**URL Filtering Rules**:
- **Include**: `/senior-x/*`, `/produto/*`
- **Exclude**: `termos-de-uso`, `politica-privacidade`, `contato`, `home`, `sobre`

**Error Handling**:
- Retry HTTP requests up to 3 times with exponential backoff
- Log fetch failures, return empty list on fatal error
- Never crash the pipeline

### 2. Semantic Extractor (`extractor.py`)

**Responsibility**: Extract clean semantic content from HTML pages

**Key Methods**:
- `extract_content()`: Fetch HTML, convert to Markdown
- `extract_breadcrumbs()`: Parse URL path to hierarchy levels
- `normalize_hierarchy()`: Lowercase, kebab-case normalization

**Backend Options**:
1. **Crawl4AI** (default): Self-hosted, no API costs
2. **Firecrawl**: Managed service, pay-per-use

**Content Cleaning**:
- Remove: navigation menus, footers, modals, sidebars
- Preserve: main article content, headings, lists, code blocks

**Output Structure**:
```python
{
    "url": str,
    "titulo": str,
    "markdown": str,
    "nivel_1": str,  # e.g., "senior-x"
    "nivel_2": str,  # e.g., "hcm"
    "nivel_3": str   # e.g., "admissao"
}
```

### 3. Content Validator (`validator.py`)

**Responsibility**: Validate extracted content quality

**Validation Rules**:
1. Minimum length: ≥100 characters
2. Heading presence: At least one Markdown heading
3. Link density: ≤70% (prevent navigation-heavy pages)

**Failure Handling**:
- Log warning with URL and reason
- Skip vector injection for failed content
- Increment `skipped_low_quality` counter
- Continue processing remaining URLs

### 4. Chunker (`chunker.py`)

**Responsibility**: Split Markdown content into semantic chunks

**Strategy**:
- Primary: `MarkdownHeaderTextSplitter` (LangChain)
- Fallback: `RecursiveCharacterTextSplitter` (no headers)
- Chunk size: ~800 tokens (~3200 characters)
- Overlap: ~100 tokens (~400 characters)

**Semantic Boundaries**:
- Respect Markdown headers
- Preserve list structures
- Include parent heading context in each chunk

### 5. Embedding Generator (`embedder.py`)

**Responsibility**: Generate vector embeddings using OpenAI

**Configuration**:
- Model: `text-embedding-3-large`
- Dimensions: 3072
- Retry: 3 attempts, exponential backoff [1s, 2s, 4s]

**Error Handling**:
- Log failures with chunk text preview (first 100 chars)
- Skip failed chunks, continue processing
- Increment `failed_embeddings` counter

### 6. Vector Injector (`injector.py`)

**Responsibility**: Upsert vectors to Pinecone with namespace segregation

**Namespace Derivation**:
```python
namespace = nivel_2.lower().replace(/[^a-z0-9]+/, '_')
# Example: "HCM Admissão" → "hcm_admissao"
# Fallback: "senior_default" if nivel_2 is empty
```

**Vector ID Format**:
```
{nivel_2}_{titulo_sanitized}_{chunk_index}
# Example: "hcm_admissao-colaborador_0"
```

**Metadata Payload**:
```python
{
    "url": str,
    "nivel_1": str,
    "nivel_2": str,
    "titulo": str,
    "text": str
}
```

**Batch Upsert**:
- Group vectors by namespace
- Batch size: 100 vectors per upsert call
- Retry: 3 attempts, exponential backoff [1s, 2s, 4s]

### 7. Pipeline Orchestrator (`pipeline.py`)

**Responsibility**: Coordinate pipeline execution and manage state

**Execution Flow**:
1. Load configuration from environment
2. Initialize all components
3. Execute stages sequentially
4. Track success/failure counts per stage
5. Generate summary report

**Error Handling Strategy**:
- Catch exceptions at stage level
- Log error with context (URL, chunk index, stage name)
- Continue processing remaining items
- Never abort entire pipeline due to single item failure

**Incremental Mode**:
- Load cache from `.ingestion_cache.json`
- Compute SHA-256 hash of Markdown content
- Compare with cached hash
- Skip processing if match, update cache if mismatch

## Data Flow

### URL → Vector Transformation

```
URL: https://docs.senior.com.br/senior-x/hcm/admissao

    ↓ [Extraction]

ExtractedContent:
  url: "https://docs.senior.com.br/senior-x/hcm/admissao"
  titulo: "Admissão de Colaborador"
  markdown: "# Admissão\n\nPara admitir um colaborador..."
  nivel_1: "senior-x"
  nivel_2: "hcm"
  nivel_3: "admissao"

    ↓ [Validation]

✓ Valid (length: 1234 chars, has heading, link density: 15%)

    ↓ [Chunking]

Chunks:
  [0] "# Admissão\n\nPara admitir um colaborador..."
  [1] "## Documentos Necessários\n\n- CPF\n- RG..."
  [2] "## Processo de Admissão\n\n1. Cadastro..."

    ↓ [Embedding]

Vectors:
  [0] embedding: [0.123, -0.456, ...] (3072 dims)
  [1] embedding: [0.789, -0.012, ...] (3072 dims)
  [2] embedding: [-0.345, 0.678, ...] (3072 dims)

    ↓ [Injection]

Pinecone:
  namespace: "hcm"
  vectors:
    - id: "hcm_admissao-colaborador_0"
      values: [0.123, -0.456, ...]
      metadata: {url, nivel_1, nivel_2, titulo, text}
    - id: "hcm_admissao-colaborador_1"
      values: [0.789, -0.012, ...]
      metadata: {url, nivel_1, nivel_2, titulo, text}
    - id: "hcm_admissao-colaborador_2"
      values: [-0.345, 0.678, ...]
      metadata: {url, nivel_1, nivel_2, titulo, text}
```

## Integration with Existing System

### Pinecone Index

- **Shared Index**: Uses same index as `dap_engine.py`
- **Index Name**: Configured via `PINECONE_INDEX_NAME` env var
- **Embedding Model**: Same as existing system (`text-embedding-3-large`, 3072 dims)

### Namespace Convention

- **Roteiro-based vectors**: Use `tenant_id` as namespace (e.g., `"senior_default"`)
- **Web-based vectors**: Use `nivel_2` as namespace (e.g., `"hcm"`, `"financeiro"`)
- **Isolation**: Namespaces provide logical segregation for scoped retrieval

### Aura DAP Integration

The `dap_engine.py` module is updated to support namespace-scoped retrieval:

```python
# Before (existing behavior)
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default"
)

# After (new namespace parameter)
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default",
    namespace="hcm"  # Query HCM documentation namespace
)
```

**Backward Compatibility**: The `namespace` parameter is optional. If not provided, the function uses `tenant_id` as before.

### Metadata Schema Compatibility

**Roteiro-based metadata** (existing):
```python
{
    "aula": str,
    "passo": int,
    "texto": str,
    "tooltip": str,
    "seletor": str
}
```

**Web-based metadata** (new):
```python
{
    "url": str,
    "nivel_1": str,
    "nivel_2": str,
    "titulo": str,
    "text": str
}
```

The `buscar_contexto()` function now handles both formats:
- Detects format based on presence of `aula` or `url` field
- Formats context appropriately for each type
- Includes `source_url` in response when available (web documentation)

## Error Handling

### Retry Strategy

All external API calls use exponential backoff retry:

```python
def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    delays: List[int] = [1, 2, 4],
    exceptions: Tuple = (Exception,)
) -> Any:
    """Execute function with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            if attempt == max_retries - 1:
                raise
            delay = delays[attempt]
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
```

### Error Categories

1. **Transient Errors** (retry):
   - Network timeouts
   - API rate limits (429)
   - Temporary service unavailability (503)

2. **Permanent Errors** (skip and continue):
   - Invalid URL (404)
   - Malformed content
   - Content validation failure
   - Parsing errors

3. **Fatal Errors** (abort pipeline):
   - Missing required environment variables
   - Invalid Pinecone index name
   - Authentication failures (401, 403)

### Logging Strategy

Structured logging with context:

```python
logger.error(
    f"[{stage_name}] {error_type}: {error_message}",
    extra={
        "url": url,
        "chunk_index": chunk_index,
        "stage": stage_name,
        "error_type": type(error).__name__
    }
)
```

## Performance Considerations

### Bottlenecks

1. **Content Extraction**: Slowest stage (network I/O, HTML parsing)
2. **Embedding Generation**: API rate limits (3000 requests/minute)
3. **Pinecone Upsert**: Batch size and network latency

### Optimization Strategies

1. **Parallel Extraction**: Process multiple URLs concurrently (future enhancement)
2. **Batch Embedding**: Generate embeddings in batches (future enhancement)
3. **Batch Upsert**: Upsert vectors in batches of 100
4. **Incremental Mode**: Skip unchanged URLs using content hash cache

### Expected Performance

For typical Senior documentation sitemap with ~500 URLs:

| Stage      | Duration  | Notes                          |
|------------|-----------|--------------------------------|
| Discovery  | ~5s       | Single HTTP request            |
| Extraction | ~10min    | Sequential, network-bound      |
| Validation | ~30s      | CPU-bound, fast                |
| Chunking   | ~30s      | CPU-bound, fast                |
| Embedding  | ~5min     | API-bound, rate limited        |
| Injection  | ~2min     | Batched, network-bound         |
| **Total**  | **~18min**| End-to-end execution           |

## Monitoring and Observability

### Metrics Tracked

**Stage Metrics**:
- URLs discovered
- URLs fetched
- URLs validated
- Chunks created
- Embeddings generated
- Vectors injected

**Failure Counts**:
- Failed fetches
- Failed validations
- Failed embeddings
- Failed upserts
- Skipped low quality

**Incremental Mode**:
- URLs skipped (cached)

### Summary Report

```
============================================================
PIPELINE EXECUTION SUMMARY
============================================================

⏱️  Timing:
   Start: 2024-01-15 10:00:00
   End:   2024-01-15 10:18:23
   Duration: 1103.45 seconds

✅ Stage Metrics:
   URLs Discovered:      487
   URLs Fetched:         485
   URLs Validated:       478
   Chunks Created:       5,234
   Embeddings Generated: 5,234
   Vectors Injected:     5,234

❌ Failure Counts:
   Failed Fetches:       2
   Failed Validations:   7
   Failed Embeddings:    0
   Failed Upserts:       0
   Skipped Low Quality:  7

📊 Success Rate: 98.2%
============================================================
```

## Future Enhancements

### Phase 2: Advanced Features

1. **Change Detection**: Monitor sitemap for new/updated/deleted pages
2. **Multi-Language Support**: Detect page language, use language-specific models
3. **Image Extraction**: Extract and index images with vision embeddings
4. **Link Graph**: Build knowledge graph from internal links

### Phase 3: Scalability

1. **Distributed Processing**: Use Celery or Ray for parallel processing
2. **Cloud Storage**: Store extracted content in S3 for audit
3. **Streaming Pipeline**: Use Kafka or RabbitMQ for event-driven architecture
4. **Monitoring Dashboard**: Grafana dashboard for real-time metrics

## References

- [Crawl4AI Documentation](https://github.com/unclecode/crawl4ai)
- [Firecrawl API Documentation](https://docs.firecrawl.dev/)
- [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [Pinecone Upsert Documentation](https://docs.pinecone.io/docs/upsert-data)

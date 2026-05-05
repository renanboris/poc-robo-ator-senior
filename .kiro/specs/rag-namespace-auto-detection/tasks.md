# Implementation Plan: RAG Namespace Auto-Detection

## Overview

This implementation plan breaks down the automatic namespace detection feature into discrete coding tasks. The system will extract module/theme information from URLs, metadata, and text to automatically pass the correct namespace to Pinecone queries, improving RAG retrieval accuracy for module-specific documentation.

The implementation follows a bottom-up approach: core detection logic first, then integration points, then configuration and testing.

## Tasks

- [x] 1. Create namespace detector core module
  - Create `namespace_detector.py` in root directory (alongside `utils.py`, `dap_engine.py`)
  - Implement module-level imports and logging setup
  - Define module-level cache variables for configuration (`_keyword_mapping_cache`, `_keyword_mapping_mtime`)
  - Add comprehensive docstrings following project conventions
  - _Requirements: 8.1, 8.5_

- [ ] 2. Implement URL-based namespace extraction
  - [x] 2.1 Implement `_extrair_namespace_de_url()` function
    - Import and reuse `Extractor.extract_breadcrumbs()` from `ingestion_pipeline/extractor.py`
    - Import and reuse `Extractor.normalize_hierarchy()` for normalization
    - Handle URL parsing with `urlparse()` from standard library
    - Return normalized namespace (lowercase kebab-case) or None
    - Add error handling: catch exceptions and return None (never raise)
    - Add logging for successful extraction and failures
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 2.2 Write unit tests for URL extraction
    - Test pattern `/senior-x/{module}/{feature}` → extracts `{module}`
    - Test pattern `/senior-x/{product}/manual-do-usuario/{module}` → extracts `{module}`
    - Test pattern `/seniorxplatform/manual-do-usuario/ged` → extracts `ged`
    - Test pattern `/senior-flow/manual-do-usuario` → extracts `senior-flow-manual`
    - Test pattern `/bpm/7.0.0/configuracao` → extracts `bpm`
    - Test invalid URLs → returns None
    - Test URLs without module → returns None
    - Test malformed URLs → returns None
    - Test empty string → returns None
    - Test None input → returns None
    - _Requirements: 13.1_

- [ ] 3. Implement metadata-based namespace extraction
  - [x] 3.1 Implement `_extrair_namespace_de_metadata()` function
    - Check for explicit `metadata['module']` field (priority 1)
    - Extract from `metadata['source_url']` using URL extraction (priority 2)
    - Extract from `metadata['nome_aula']` using keyword matching (priority 3)
    - Validate dict type before accessing keys
    - Return normalized namespace or None
    - Add error handling: catch KeyError and return None
    - Add logging for each extraction path
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_
  
  - [ ]* 3.2 Write unit tests for metadata extraction
    - Test `{"module": "hcm"}` → returns `hcm`
    - Test `{"source_url": "...senior-x/ged/..."}` → returns `ged`
    - Test `{"nome_aula": "Criar pasta no GED"}` → returns `ged`
    - Test empty metadata `{}` → returns None
    - Test metadata without hints → returns None
    - Test priority order: module > source_url > nome_aula
    - Test invalid metadata types → returns None
    - _Requirements: 13.2_

- [ ] 4. Implement keyword-based namespace extraction
  - [x] 4.1 Implement `_carregar_mapeamento_keywords()` function
    - Try loading from `namespace_keywords.json` file (priority 1)
    - Try loading from `NAMESPACE_KEYWORDS` environment variable (priority 2)
    - Fallback to hardcoded default mapping (priority 3)
    - Implement caching: check `_keyword_mapping_cache` before loading
    - Implement cache invalidation: check file mtime for changes
    - Parse JSON safely with try-except
    - Add logging for configuration source and namespace count
    - Define hardcoded default mapping with 5+ modules (hcm, financeiro, ged, compras, estoque)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.4_
  
  - [x] 4.2 Implement `_extrair_namespace_de_keywords()` function
    - Load keyword mapping using `_carregar_mapeamento_keywords()`
    - Normalize input text to lowercase
    - Iterate through namespace-keyword mappings
    - Perform case-insensitive substring matching
    - Return first matched namespace (short-circuit on match)
    - Return None if no keywords match
    - Add logging for matched keyword and namespace
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [ ]* 4.3 Write unit tests for keyword matching
    - Test "Criar admissão no HCM" → returns `hcm`
    - Test "Configurar contas a pagar" → returns `financeiro`
    - Test "Gerenciar documentos no GED" → returns `ged`
    - Test "Processar requisição de compras" → returns `compras`
    - Test "Movimentar estoque" → returns `estoque`
    - Test case insensitivity: "ADMISSÃO", "admissão", "Admissão"
    - Test multiple keyword matches (first wins)
    - Test no keyword matches → returns None
    - Test empty string → returns None
    - Test None input → returns None
    - _Requirements: 13.3_
  
  - [ ]* 4.4 Write unit tests for configuration loading
    - Test loading from JSON file (mock file existence)
    - Test loading from environment variable (mock env var)
    - Test fallback to hardcoded defaults
    - Test invalid JSON handling → uses defaults
    - Test cache behavior: second call uses cached value
    - Test cache invalidation: file change triggers reload
    - _Requirements: 13.3_

- [ ] 5. Implement main namespace detection function
  - [x] 5.1 Implement `detectar_namespace()` function
    - Accept `contexto: dict` parameter with optional keys: url, metadata, objetivo, nome_aula
    - Implement priority order: URL > metadata > keywords > None
    - Try URL extraction if `contexto.get('url')` exists
    - Try metadata extraction if `contexto.get('metadata')` exists
    - Try keyword matching on `contexto.get('objetivo')` or `contexto.get('nome_aula')`
    - Return normalized namespace string or None
    - Add comprehensive logging for detection source
    - Never raise exceptions: wrap all calls in try-except
    - _Requirements: 8.1, 8.2, 8.3, 8.4_
  
  - [ ]* 5.2 Write unit tests for priority order
    - Test URL takes precedence over metadata
    - Test metadata takes precedence over keywords
    - Test keywords are last resort
    - Test fallback to None when all methods fail
    - Test empty context dict → returns None
    - Test context with multiple hints → uses highest priority
    - _Requirements: 13.1, 13.2, 13.3_
  
  - [ ]* 5.3 Write unit tests for error handling
    - Test invalid input types (string, list, None) → returns None
    - Test missing keys in context → returns None
    - Test malformed URLs → returns None
    - Test import errors (mock extractor import failure) → returns None
    - _Requirements: 13.5_

- [ ] 6. Checkpoint - Ensure all tests pass
  - Run unit test suite: `pytest test_namespace_detector.py -v`
  - Verify all URL extraction tests pass
  - Verify all metadata extraction tests pass
  - Verify all keyword matching tests pass
  - Verify all priority order tests pass
  - Verify all error handling tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Integrate namespace detection into Generator Engine
  - [x] 7.1 Modify `generator_engine.py` to use namespace detection
    - Locate `gerar_roteiro_ia_sync()` function (around line 66)
    - Import `detectar_namespace` from `namespace_detector`
    - After `logger.info(f"Buscando manual para: {objetivo}")`, create contexto dict: `{"objetivo": objetivo}`
    - Call `namespace_detectado = detectar_namespace(contexto_deteccao)`
    - If namespace detected, log with INFO level: `[Namespace] Detectado: {namespace} (fonte: objetivo)`
    - If namespace detected, call `buscar_contexto(objetivo, tenant_id, namespace=namespace_detectado)`
    - If not detected, log with INFO level: `[Namespace] Não detectado, usando tenant_id: {tenant_id}`
    - If not detected, call `buscar_contexto(objetivo, tenant_id)` (existing behavior)
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 10.1, 10.2_
  
  - [ ]* 7.2 Write integration test for Generator Engine
    - Test roteiro generation with URL in objetivo
    - Verify namespace passed to `buscar_contexto()`
    - Verify Pinecone query uses correct namespace
    - Verify fallback when no namespace detected
    - Mock Pinecone to verify namespace parameter
    - _Requirements: 13.4_

- [ ] 8. Integrate namespace detection into Capture Engine
  - [x] 8.1 Modify `capture.py` to use namespace detection
    - Locate `_buscar_pinecone_sync()` function (around line 60)
    - Import `detectar_namespace` from `namespace_detector`
    - After checking API keys, create contexto dict: `{"objetivo": objetivo_aula}`
    - Call `namespace_detectado = detectar_namespace(contexto_deteccao)`
    - If namespace detected, set `namespace_query = namespace_detectado` and log with INFO level
    - If not detected, set `namespace_query = os.getenv("DEFAULT_TENANT_ID", "senior_default")` and log with INFO level
    - Pass `namespace=namespace_query` to `index.query()` (replace hardcoded tenant_id)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 10.1, 10.2_
  
  - [ ]* 8.2 Write integration test for Capture Engine
    - Test capture workflow with module keywords in objetivo_aula
    - Verify namespace detection in `_buscar_pinecone_sync()`
    - Verify Pinecone query uses correct namespace
    - Verify fallback behavior
    - Mock Pinecone to verify namespace parameter
    - _Requirements: 13.4_

- [ ] 9. Checkpoint - Ensure integration tests pass
  - Run integration test suite: `pytest test_namespace_integration.py -v`
  - Verify Generator Engine integration works correctly
  - Verify Capture Engine integration works correctly
  - Verify backward compatibility: existing flows work without namespace
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Create namespace keywords configuration file
  - [x] 10.1 Create `namespace_keywords.json` template in root directory
    - Define mapping for `hcm` module (10+ keywords: recursos humanos, admissao, folha, rh, colaborador, etc.)
    - Define mapping for `financeiro` module (10+ keywords: contas a pagar, tesouraria, financas, etc.)
    - Define mapping for `ged` module (8+ keywords: documentos, arquivos, pastas, ged, etc.)
    - Define mapping for `compras` module (7+ keywords: compras, requisicao, fornecedor, etc.)
    - Define mapping for `estoque` module (7+ keywords: estoque, inventario, armazem, etc.)
    - Add JSON comment explaining format and usage
    - Use lowercase for all keywords (case-insensitive matching)
    - Include Portuguese characters (ã, ç, é, etc.)
    - _Requirements: 9.1, 9.2, 14.3_
  
  - [ ]* 10.2 Test configuration file loading
    - Verify JSON is valid and parseable
    - Verify all namespaces load correctly
    - Verify keyword matching works with file-based config
    - Test file modification triggers cache invalidation
    - _Requirements: 9.4_

- [ ] 11. Add fallback and error handling
  - [x] 11.1 Verify fallback chain in `dap_engine.py`
    - Review `buscar_contexto()` function signature
    - Verify namespace parameter is optional (already exists)
    - Verify fallback to tenant_id when namespace is None
    - Verify fallback to "senior_default" when tenant_id is None/empty
    - Add logging for fallback events with WARNING level
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 10.3, 10.4_
  
  - [ ]* 11.2 Write tests for fallback behavior
    - Test namespace=None → uses tenant_id
    - Test namespace=None and tenant_id=None → uses "senior_default"
    - Test exception during detection → falls back gracefully
    - Test missing namespace_detector module → system continues
    - Verify no exceptions propagate to caller
    - _Requirements: 13.5_

- [ ] 12. Add observability and logging
  - [x] 12.1 Add comprehensive logging throughout namespace_detector.py
    - Log successful detection with source: `[Namespace] Detectado: {namespace} (fonte: {source})`
    - Log detection failure: `[Namespace] Não detectado, usando tenant_id: {tenant_id}`
    - Log fallback events: `[Namespace] Fallback: {reason}`
    - Log configuration loading: `[Namespace] Config carregado: {source} ({count} namespaces)`
    - Log detection errors: `[Namespace] Erro na detecção: {error}`
    - Log import errors: `[Namespace] Falha ao importar extractor: {error}`
    - Use INFO level for successful operations
    - Use WARNING level for fallbacks and detection failures
    - Use ERROR level for import failures
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 13. Checkpoint - Verify backward compatibility
  - Test existing roteiro generation without namespace hints
  - Verify system behaves exactly as before when no namespace detected
  - Verify `buscar_contexto()` signature unchanged
  - Verify existing unit tests pass without modification
  - Verify existing integration tests pass without modification
  - Ensure all tests pass, ask the user if questions arise.
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [ ] 14. Performance optimization and validation
  - [x] 14.1 Implement performance optimizations
    - Verify configuration caching is working (module-level cache)
    - Verify lazy loading: import namespace_detector only when needed
    - Verify efficient keyword matching: short-circuit on first match
    - Verify no external API calls or database queries
    - Add performance logging: log detection time for monitoring
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ]* 14.2 Write performance tests
    - Test detection completes in <10ms for typical inputs
    - Test 1000 iterations average time
    - Test configuration loads once and caches
    - Test no external calls during detection
    - Verify performance budget met
    - _Requirements: 12.1, 12.5_

- [ ] 15. Documentation and examples
  - [x] 15.1 Update README.md with namespace detection feature
    - Add section explaining automatic namespace detection
    - Document detection priority order: URL > metadata > keywords > fallback
    - Provide examples of valid URL patterns and extracted namespaces
    - Document keyword-to-namespace mapping configuration format
    - Explain relationship between ingestion namespaces and retrieval namespaces
    - Add troubleshooting section for common issues
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [x] 15.2 Add code examples and usage documentation
    - Document how to call `detectar_namespace()` with examples
    - Show example context dictionaries for each detection method
    - Document environment variable configuration option
    - Document how to customize keyword mappings
    - Add examples of log output for debugging
    - _Requirements: 14.1, 14.3, 14.4_

- [x] 16. Final validation and deployment preparation
  - Run full test suite: `pytest -v`
  - Verify all unit tests pass (30+ test cases)
  - Verify all integration tests pass (10+ scenarios)
  - Verify performance tests pass
  - Review all logging output for clarity
  - Verify no breaking changes to existing APIs
  - Test end-to-end: capture → generate → verify namespace used
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- The implementation reuses existing `Extractor` logic for consistency
- No breaking changes: namespace detection is transparent enhancement
- Configuration is optional: system works with hardcoded defaults
- Performance budget: <10ms detection time, no external calls
- Backward compatible: existing flows work without modification

## Implementation Strategy

1. **Bottom-up approach**: Build core detection logic first, then integrate
2. **Incremental testing**: Test each component before moving to next
3. **Reuse existing code**: Leverage `Extractor` from ingestion pipeline
4. **Graceful degradation**: System continues working if detection fails
5. **Observability first**: Comprehensive logging for debugging and monitoring

## Success Criteria

- [ ] Namespace detection works for URLs, metadata, and keywords
- [ ] Generator Engine automatically uses detected namespaces
- [ ] Capture Engine automatically uses detected namespaces
- [ ] System falls back gracefully when detection fails
- [ ] All tests pass (unit, integration, performance)
- [ ] No breaking changes to existing functionality
- [ ] Documentation is complete and clear
- [ ] Performance budget met (<10ms detection time)

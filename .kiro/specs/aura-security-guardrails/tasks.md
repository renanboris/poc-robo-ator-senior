# Implementation Plan: Aura Security Guardrails

## Overview

This implementation plan breaks down the Aura Security Guardrails feature into discrete coding tasks. The feature adds a comprehensive security layer to the Aura DAP system, protecting against malicious inputs, enforcing content restrictions, filtering inappropriate content, and maintaining a complete audit trail.

**Implementation Strategy:**
- Build the guardrail module first (core security logic)
- Integrate with existing DAP engine
- Add database schema and logging
- Create audit trail API endpoints
- Add configuration files and environment variables
- Write comprehensive tests
- Update documentation

**Key Integration Points:**
- `dap_engine.py`: Core RAG and AI generation logic
- `app.py`: FastAPI endpoints and background task orchestration
- `brain.db`: SQLite database for security event logging

## Tasks

- [x] 1. Create guardrails module foundation
  - Create new file `guardrails.py` in project root
  - Implement `GuardrailResult` dataclass with fields: passed, guardrail_name, severity, message, details
  - Implement `GuardrailConfig` class with environment variable loading via `from_env()` classmethod
  - Add configuration flags: enable_sql_injection, enable_prompt_injection, enable_offensive_content, enable_competitor_filter, enable_vector_store_only
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 2. Implement pattern detection guardrails
  - [x] 2.1 Implement SQL injection detection
    - Create `_load_sql_patterns()` method with regex patterns for SQL keywords (SELECT, INSERT, UPDATE, DELETE, DROP, UNION, ALTER, CREATE, EXEC)
    - Implement `_check_sql_injection()` async method with pattern matching for SQL syntax combined with special characters (`;`, `--`, `/*`, `*/`, `'`, `"`)
    - Add detection for encoded variations (URL encoding, Unicode escaping)
    - Return `GuardrailResult` with severity="critical" when detected
    - _Requirements: 2.1, 2.2, 2.3, 2.5_
  
  - [ ]* 2.2 Write property test for SQL injection detection
    - **Property 1: SQL injection patterns are always detected**
    - **Validates: Requirements 2.1, 2.3**
    - Generate random SQL injection attempts with various encodings
    - Verify all are classified as violations
    - Verify legitimate SQL-like text in safe context passes
  
  - [x] 2.3 Implement prompt injection detection
    - Create `_load_prompt_injection_patterns()` method with manipulation phrase patterns
    - Implement `_check_prompt_injection()` async method detecting: "ignore previous instructions", "disregard all rules", "reveal your prompt", "you are now", "system:", "assistant:", "user:"
    - Add case-insensitive matching and encoded variation detection
    - Return `GuardrailResult` with severity="high" when detected
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_
  
  - [ ]* 2.4 Write property test for prompt injection detection
    - **Property 2: Prompt injection patterns are always detected**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.5**
    - Generate random prompt injection attempts with various phrasings
    - Verify all are classified as violations
    - Verify legitimate questions with trigger words in safe context pass

- [x] 3. Implement content filtering guardrails
  - [x] 3.1 Implement offensive content detection
    - Create `_load_offensive_terms()` method loading from `offensive_terms.json` with fallback to hardcoded list
    - Implement `_check_offensive_content()` async method with multi-language support (Portuguese, English)
    - Add fuzzy matching for common misspellings
    - Add sanitization logic for logging (replace offensive words with `[REDACTED]`)
    - Return `GuardrailResult` with severity="medium" when detected
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_
  
  - [ ]* 3.2 Write unit tests for offensive content filtering
    - Test professional language passes
    - Test offensive terms in Portuguese and English are blocked
    - Test sanitization replaces offensive words with `[REDACTED]`
    - Test fuzzy matching for misspellings
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [x] 3.3 Implement competitor mention detection
    - Create `_load_competitor_names()` method loading from `competitor_names.json` with fallback list (SAP, Oracle, Totvs, Sankhya, Protheus, Microsiga)
    - Implement `_check_competitor_mention()` async method with case-insensitive matching
    - Add product variant detection (e.g., "SAP S/4HANA", "Oracle EBS")
    - Return `GuardrailResult` with severity="low" when detected
    - _Requirements: 5.1, 5.4, 5.5_
  
  - [ ]* 3.4 Write unit tests for competitor mention detection
    - Test Senior X questions pass without triggering
    - Test direct competitor mentions are detected
    - Test product variants are detected
    - Test case-insensitive matching
    - _Requirements: 5.1, 5.5_

- [x] 4. Implement GuardrailEngine orchestration
  - Implement `GuardrailEngine.__init__()` accepting `GuardrailConfig` and loading all pattern files
  - Implement `validate_prompt()` async method executing all enabled guardrails in parallel using `asyncio.gather()`
  - Add logic to filter and return only failed guardrail results
  - Add error handling for individual guardrail failures (log warning, skip check, continue with others)
  - Add timeout handling for guardrail checks (>100ms logs warning)
  - _Requirements: 2.1, 3.1, 4.1, 5.1, 8.2, 9.3, 9.4_

- [ ]* 4.1 Write property test for parallel guardrail execution
  - **Property 3: All enabled guardrails execute in parallel**
  - **Validates: Requirements 9.3, 9.4**
  - Generate prompts violating multiple guardrails
  - Verify all violations are detected and returned
  - Verify execution time is <200ms for all guardrails combined

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement security event logging system
  - [x] 6.1 Create SecurityEventLogger class
    - Implement `SecurityEventLogger.__init__()` accepting db_path parameter (default="brain.db")
    - Implement `_init_table()` method creating `aura_security_events` table with schema: id, event_type, timestamp, tenant_id, user_id, prompt_hash, guardrail_triggered, severity_level, details
    - Create indexes: idx_security_events_tenant (tenant_id, timestamp), idx_security_events_type (event_type, timestamp)
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [x] 6.2 Implement async event logging
    - Implement `log_event()` async method accepting: event_type, tenant_id, prompt, guardrail_name, severity, user_id (optional), details (optional)
    - Add SHA-256 hashing for prompt (never store full prompt)
    - Add timestamp generation (milliseconds since epoch)
    - Add JSON serialization for details field
    - Use `asyncio.to_thread()` for database write to avoid blocking
    - Add error handling with logging (don't raise exceptions - logging failures should not block requests)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 6.3 Write unit tests for security event logging
    - Test event is persisted to database with correct schema
    - Test prompt is hashed (SHA-256) and not stored in plaintext
    - Test multiple violations log separate events
    - Test database connection failure is handled gracefully
    - Test logging completes within 100ms
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 7. Integrate guardrails into DAP engine
  - [ ] 7.1 Add guardrail imports and initialization to dap_engine.py
    - Add imports: `from guardrails import GuardrailEngine, GuardrailConfig, SecurityEventLogger`
    - Add module-level initialization: `_guardrail_config = GuardrailConfig.from_env()`
    - Add module-level initialization: `_guardrail_engine = GuardrailEngine(_guardrail_config)`
    - Add module-level initialization: `_security_logger = SecurityEventLogger()`
    - _Requirements: 8.1, 8.5_
  
  - [ ] 7.2 Integrate guardrail validation into analisar_tela_dap()
    - Add guardrail validation as STEP 1 in `analisar_tela_dap()` before cache check
    - Call `_guardrail_engine.validate_prompt(prompt_usuario, tenant_id)` and await result
    - If violations exist, log all violations using `_security_logger.log_event()` in loop
    - If violations exist, return error response with highest severity violation message
    - Add `_severity_rank()` helper function to rank severity levels (critical > high > medium > low)
    - Add new response fields: "blocked": True, "guardrail": violation.guardrail_name
    - _Requirements: 2.2, 2.4, 3.2, 3.4, 4.2, 5.2, 7.1, 7.5, 10.1, 10.2, 10.3_
  
  - [ ] 7.3 Enforce vector store content restriction
    - After guardrail validation, check if `busca_rag` is None or score < SCORE_THRESHOLD (0.45)
    - If true, return fallback response: "I don't have information about this in my knowledge base. Try asking about Senior X modules, features, or tasks."
    - Add response fields: "confidence_score": score, "source_reference": None
    - Add suggested questions: ["Show me Senior X modules", "How do I..."]
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 10.4_
  
  - [ ] 7.4 Add source traceability to responses
    - After AI generation (existing AI Gate or Gemini Vision logic), add metadata to `resultado_final`
    - Add field: "confidence_score": busca_rag["score"]
    - Add field: "source_reference": busca_rag.get("melhor_aula")
    - If "source_url" exists in busca_rag, add field: "source_url": busca_rag["source_url"]
    - _Requirements: 1.5, 1.6, 6.1, 6.2, 6.3, 6.4, 6.5_
  
  - [ ]* 7.5 Write integration tests for DAP engine guardrails
    - Test valid prompt passes all guardrails and generates response
    - Test SQL injection attempt is blocked and logged
    - Test prompt injection attempt is blocked and logged
    - Test offensive content is blocked and logged
    - Test low confidence query returns fallback response
    - Test response includes source traceability metadata
    - _Requirements: 1.1, 2.2, 3.2, 4.2, 6.1, 7.1_

- [-] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Create audit trail API endpoints
  - [ ] 9.1 Implement security events query endpoint
    - Add `@app.get("/api/security/events")` endpoint in app.py
    - Add authentication via `token: str = Depends(verificar_token)`
    - Add query parameters: tenant_id (required), start_date (optional), end_date (optional), event_type (optional)
    - Implement SQL query with WHERE clause filtering by tenant_id, date range, and event_type
    - Add tenant isolation enforcement (only return events for requesting tenant)
    - Return JSON array of security events with pagination support (limit 100 per page)
    - Add response time requirement: <2s for queries spanning up to 30 days
    - _Requirements: 11.3, 11.4, 12.1, 12.2_
  
  - [ ] 9.2 Implement security events export endpoint
    - Add `@app.get("/api/security/events/export")` endpoint in app.py
    - Add authentication via `token: str = Depends(verificar_token)`
    - Add query parameters: tenant_id (required), start_date (required), end_date (required)
    - Implement SQL query fetching all events in date range for tenant
    - Return JSON file download with all events (no pagination)
    - Add tenant isolation enforcement
    - _Requirements: 11.5, 12.2_
  
  - [ ] 9.3 Implement security events archive endpoint
    - Add `@app.post("/api/security/archive")` endpoint in app.py
    - Add authentication via `token: str = Depends(verificar_token)`
    - Implement logic to move events older than 90 days to `aura_security_events_archive` table
    - Use SQL transaction to ensure atomic move (INSERT INTO archive + DELETE FROM main)
    - Add logging for number of events archived
    - Return JSON response with archive statistics
    - _Requirements: 11.1, 11.2_
  
  - [ ]* 9.4 Write integration tests for audit trail API
    - Test query endpoint returns only events for requesting tenant
    - Test query endpoint filters by date range correctly
    - Test query endpoint filters by event_type correctly
    - Test export endpoint generates valid JSON file
    - Test archive endpoint moves old events to archive table
    - Test authentication is required for all endpoints
    - _Requirements: 11.3, 11.4, 11.5, 12.1, 12.2_

- [ ] 10. Create configuration files and environment variables
  - [ ] 10.1 Create offensive_terms.json configuration file
    - Create `offensive_terms.json` in project root
    - Add structure: `{"pt": [...], "en": [...]}`
    - Add initial Portuguese offensive terms list (minimum 10 terms)
    - Add initial English offensive terms list (minimum 10 terms)
    - Add comments in file header explaining purpose and update process
    - _Requirements: 4.5_
  
  - [ ] 10.2 Create competitor_names.json configuration file
    - Create `competitor_names.json` in project root
    - Add structure: `{"competitors": [{"name": "...", "variants": [...]}, ...]}`
    - Add default competitors: SAP (variants: SAP S/4HANA, SAP ERP, SAP Business One), Oracle (variants: Oracle EBS, Oracle Cloud, Oracle Fusion), Totvs (variants: Protheus, RM, Datasul), Sankhya (variants: Sankhya W), Microsiga
    - Add comments in file header explaining purpose and update process
    - _Requirements: 5.5_
  
  - [ ] 10.3 Add environment variables to .env.example
    - Add section header: `# Guardrail Configuration`
    - Add variables: ENABLE_SQL_INJECTION_CHECK=true, ENABLE_PROMPT_INJECTION_CHECK=true, ENABLE_OFFENSIVE_CONTENT_FILTER=true, ENABLE_COMPETITOR_FILTER=true, ENABLE_VECTOR_STORE_ONLY=true
    - Add section header: `# Audit Configuration`
    - Add variable: SECURITY_EVENT_RETENTION_DAYS=90
    - Add comments explaining each variable's purpose
    - _Requirements: 8.3, 11.1_

- [ ] 11. Add database migration for security events table
  - [ ] 11.1 Add migration to app.py lifespan
    - Add migration code in `lifespan()` function after existing migrations
    - Create `aura_security_events` table if not exists with schema from design
    - Create indexes: idx_security_events_tenant, idx_security_events_type
    - Create `aura_security_events_archive` table if not exists with same schema plus archived_at field
    - Add logging: "Migração aura_security_events: OK"
    - Add error handling with warning log (don't block startup)
    - _Requirements: 7.2, 11.1, 11.2_
  
  - [ ]* 11.2 Write migration test
    - Test migration creates tables successfully
    - Test migration is idempotent (can run multiple times)
    - Test indexes are created correctly
    - _Requirements: 7.2_

- [ ] 12. Update error messages for user feedback
  - Add helper function `_get_user_message()` in guardrails.py mapping guardrail names to user-friendly messages
  - Map "sql_injection" → "Your request contains patterns that cannot be processed. Please rephrase your question."
  - Map "prompt_injection" → "I can only help with Senior X questions. Please ask about specific features or tasks."
  - Map "offensive_content" → "Please keep your questions professional. How can I help you with Senior X?"
  - Map "competitor_mention" → "I can help you with Senior X features. What would you like to accomplish?"
  - Update `GuardrailResult` to use these messages when violations are detected
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 13. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Add performance monitoring and logging
  - [ ] 14.1 Add guardrail execution time logging
    - Add timing measurement in `GuardrailEngine.validate_prompt()` using `time.time()`
    - Log warning if total execution time >200ms
    - Log warning if individual guardrail check >100ms
    - Add execution time to response metadata for monitoring
    - _Requirements: 9.1, 9.3, 9.4_
  
  - [ ] 14.2 Add security event metrics logging
    - Add logging in `SecurityEventLogger.log_event()` for each event type
    - Log format: "[SECURITY] {event_type} blocked for tenant {tenant_id} - {guardrail_name} ({severity})"
    - Add counter for events per tenant (in-memory, reset on restart)
    - _Requirements: 7.1, 7.5_

- [ ] 15. Update documentation
  - [ ] 15.1 Update README.md with guardrails section
    - Add "Security Guardrails" section explaining the feature
    - Document environment variables and their defaults
    - Document configuration files (offensive_terms.json, competitor_names.json)
    - Add examples of blocked vs. allowed prompts
    - Document audit trail API endpoints
    - _Requirements: 8.3, 8.5_
  
  - [ ] 15.2 Add inline code documentation
    - Add docstrings to all public methods in guardrails.py
    - Add docstrings to SecurityEventLogger methods
    - Add comments explaining complex regex patterns
    - Add comments explaining severity ranking logic
    - _Requirements: All_

- [ ] 16. Final integration and validation
  - [ ] 16.1 Test end-to-end flow with all guardrails enabled
    - Submit valid prompt → verify response with source traceability
    - Submit SQL injection → verify blocked + logged
    - Submit prompt injection → verify blocked + logged
    - Submit offensive content → verify blocked + logged
    - Submit competitor mention → verify handled appropriately
    - Submit low confidence query → verify fallback response
    - Query security events API → verify events are logged correctly
    - _Requirements: 1.1, 2.2, 3.2, 4.2, 5.2, 6.1, 7.1, 11.3_
  
  - [ ] 16.2 Test multi-tenant isolation
    - Create events for Tenant A and Tenant B
    - Query events as Tenant A → verify only Tenant A events returned
    - Query events as Tenant B → verify only Tenant B events returned
    - Submit prompt as Tenant A → verify only Tenant A namespace searched
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_
  
  - [ ] 16.3 Test configuration management
    - Disable SQL injection check → verify check is skipped
    - Disable all content guardrails → verify Vector Store restriction still enforced
    - Re-enable all guardrails → verify all checks execute
    - _Requirements: 8.1, 8.2, 8.4_
  
  - [ ]* 16.4 Performance validation
    - Measure response time with all guardrails enabled (should be <3s for 95% of requests)
    - Measure cache hit response time (should be <500ms)
    - Measure guardrail execution time (should be <200ms)
    - Measure security event logging time (should be <100ms)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 17. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows
- Performance tests validate response time requirements

## Implementation Order Rationale

1. **Foundation First**: Build guardrails module with core detection logic
2. **Content Filtering**: Implement all pattern detection guardrails
3. **Orchestration**: Wire guardrails together with parallel execution
4. **Logging**: Add security event persistence
5. **Integration**: Connect guardrails to DAP engine
6. **Audit Trail**: Add API endpoints for querying events
7. **Configuration**: Add config files and environment variables
8. **Database**: Add migration for security events table
9. **Polish**: Add error messages, monitoring, documentation
10. **Validation**: End-to-end testing and performance validation

This order ensures each layer builds on the previous one, with checkpoints to validate progress before moving forward.

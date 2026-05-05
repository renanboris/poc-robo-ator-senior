# Implementation Plan: AURA Smart Navigation Fallback

## Overview

This implementation plan breaks down the AURA Smart Navigation Fallback feature into discrete, actionable coding tasks. The feature adds intelligent fallback navigation when UI elements are not visible in the DOM, leveraging saved roteiros to provide step-by-step guided navigation.

The implementation follows a layered approach:
1. Core infrastructure (database, indexing, file watching)
2. Component implementation (indexer, extractor, executor, engine)
3. Integration with existing DAP engine
4. Extension enhancements for visual feedback
5. Testing and validation

## Tasks

- [x] 1. Set up navigation fallback infrastructure
  - Create `navigation_fallback.py` module in project root
  - Define SQLite schema for navigation index
  - Implement database initialization and migration logic
  - Set up configuration constants (timeouts, cache size, index path)
  - _Requirements: 7.1, 7.2, 8.5_

- [ ] 2. Implement RoteiroIndexer component
  - [x] 2.1 Create RoteiroIndexer class with SQLite backend
    - Implement `__init__()` with database connection and cache initialization
    - Create SQLite table with FTS5 support for full-text search
    - Implement LRU cache with configurable size (default 100 entries)
    - _Requirements: 7.1, 7.2, 7.3_
  
  - [~] 2.2 Implement index building functionality
    - Write `build_index()` to scan `roteiros_salvos/` directory
    - Parse each roteiro JSON and extract navigation paths
    - Populate SQLite index with navigation metadata
    - Add progress logging for index build process
    - _Requirements: 7.1, 8.1, 8.2_
  
  - [ ]* 2.3 Write property test for index building
    - **Property 1: Index completeness**
    - **Validates: Requirements 7.1, 8.1**
    - For all valid roteiro files in a directory, building the index then querying for each roteiro's target element SHALL return at least one result
  
  - [~] 2.4 Implement search functionality with ranking
    - Write `search()` method with query normalization
    - Implement FTS5 full-text search with score ranking
    - Add cache lookup before database query
    - Return results sorted by confidence score and path length
    - _Requirements: 7.2, 7.5_
  
  - [ ]* 2.5 Write property test for search consistency
    - **Property 2: Search determinism**
    - **Validates: Requirements 7.2, 7.5**
    - Searching for the same normalized query twice SHALL return results in the same order
  
  - [~] 2.6 Implement incremental index updates
    - Write `update_index()` for single roteiro file updates
    - Implement cache invalidation for modified roteiros
    - Add file change detection logic
    - _Requirements: 7.4_
  
  - [ ]* 2.7 Write unit tests for cache behavior
    - Test cache hit/miss scenarios
    - Test LRU eviction policy
    - Test cache invalidation on file changes
    - _Requirements: 7.3, 7.4_

- [ ] 3. Checkpoint - Verify indexer functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement NavigationPathExtractor component
  - [~] 4.1 Create NavigationPathExtractor class
    - Implement `extract_navigation_path()` to parse roteiro JSON
    - Write `_parse_step()` to extract navigation information from each passo
    - Handle `ancora`, `acao`, and `pedagogia.tooltip_dap` fields
    - _Requirements: 8.1, 8.2, 8.3_
  
  - [~] 4.2 Implement breadcrumb generation
    - Write `_build_breadcrumb()` to create human-readable paths
    - Extract hierarchical navigation sequences (e.g., "Senior Flow > SIGN > Nova Gestão")
    - Handle edge cases (missing labels, empty steps)
    - _Requirements: 2.3, 8.4_
  
  - [ ]* 4.3 Write property test for parsing round-trip
    - **Property 6: Round-trip consistency**
    - **Validates: Requirements 8.6**
    - For all valid roteiro files, parsing then reconstructing the navigation path SHALL preserve the original sequence
  
  - [~] 4.4 Implement selector hint extraction
    - Extract `seletor_css` and `elemento_alvo.seletor_hint` from actions
    - Build selector hint strings for each navigation step
    - Add coordinate extraction for fallback positioning
    - _Requirements: 8.2, 8.3_
  
  - [ ]* 4.5 Write unit tests for malformed roteiro handling
    - Test parsing with missing fields
    - Test parsing with invalid JSON structure
    - Test parsing with empty passos array
    - Verify no crashes occur with malformed input
    - _Requirements: 8.5_

- [ ] 5. Implement GuidedNavigationExecutor component
  - [~] 5.1 Create GuidedNavigationExecutor class
    - Implement `__init__()` with state tracking
    - Define navigation state machine (idle, executing, waiting, completed, failed)
    - Set up step execution tracking
    - _Requirements: 4.1, 4.2_
  
  - [~] 5.2 Implement step-by-step navigation execution
    - Write `execute_navigation()` to orchestrate full navigation sequence
    - Implement `execute_step()` for single step execution
    - Add element highlighting via extension communication
    - Track completed steps and partial progress
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  
  - [~] 5.3 Implement DOM stabilization waiting
    - Write `_wait_for_dom_stabilization()` with configurable timeout
    - Detect DOM changes after interactions
    - Implement exponential backoff for DOM checks
    - _Requirements: 4.4_
  
  - [ ]* 5.4 Write property test for navigation state transitions
    - **Property 3: State machine validity**
    - **Validates: Requirements 4.1, 4.6**
    - Navigation state SHALL only transition through valid paths (idle → executing → waiting → completed OR idle → executing → failed)
  
  - [~] 5.5 Implement error handling and recovery
    - Detect element not found errors
    - Handle timeout scenarios
    - Detect UI structure mismatches
    - Return detailed error information with partial progress
    - _Requirements: 6.1, 6.2, 6.3, 6.4_
  
  - [ ]* 5.6 Write unit tests for failure scenarios
    - Test element not found handling
    - Test timeout handling
    - Test UI structure mismatch detection
    - Test partial navigation completion tracking
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 6. Checkpoint - Verify executor functionality
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Implement NavigationFallbackEngine orchestrator
  - [~] 7.1 Create NavigationFallbackEngine class
    - Implement `__init__()` with component initialization
    - Wire together RoteiroIndexer, NavigationPathExtractor, and GuidedNavigationExecutor
    - Set up logging and metrics tracking
    - _Requirements: 9.1, 9.4_
  
  - [~] 7.2 Implement invisible element handling
    - Write `handle_invisible_element()` as main entry point
    - Coordinate between indexer search and path extraction
    - Format conversational navigation offers
    - Return structured response with navigation path and confirmation requirement
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3_
  
  - [~] 7.3 Implement guided navigation execution
    - Write `execute_guided_navigation()` to handle user confirmation
    - Coordinate with GuidedNavigationExecutor for step execution
    - Track navigation success/failure metrics
    - Return execution results with detailed status
    - _Requirements: 4.1, 4.5, 10.1, 10.2_
  
  - [ ]* 7.4 Write property test for fallback hierarchy
    - **Property 4: Fallback strategy correctness**
    - **Validates: Requirements 2.4, 3.4**
    - When no navigation path is found in roteiros, the system SHALL fall back to general knowledge response without crashing
  
  - [ ]* 7.5 Write integration tests for end-to-end flow
    - Test complete flow from query to navigation offer
    - Test user confirmation handling (accept/decline)
    - Test navigation success scenarios
    - Test navigation failure scenarios with graceful degradation
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.5, 4.6_

- [ ] 8. Integrate with existing DAP engine
  - [~] 8.1 Implement element visibility check in dap_engine.py
    - Write `_check_element_visibility()` function
    - Extract element keywords from user query
    - Search for keywords in DOM context
    - Enforce 500ms timeout requirement
    - _Requirements: 1.1, 1.2, 1.3, 1.4_
  
  - [ ]* 8.2 Write property test for visibility check performance
    - **Property 5: Visibility check latency**
    - **Validates: Requirements 1.4**
    - Element visibility check SHALL complete within 500ms for 95% of queries
  
  - [~] 8.3 Modify analisar_tela_dap() for fallback activation
    - Add visibility check before existing direct highlight flow
    - Initialize NavigationFallbackEngine when element not visible
    - Call `handle_invisible_element()` for fallback strategy
    - Preserve existing direct highlight behavior for visible elements
    - _Requirements: 1.2, 1.3, 5.1, 5.2, 5.3, 9.1, 9.2_
  
  - [~] 8.4 Format fallback responses for DAP contract
    - Return navigation path in DAP response format
    - Add `requires_confirmation` flag for user confirmation flow
    - Include confidence score and source reference for traceability
    - Preserve existing response structure for backward compatibility
    - _Requirements: 3.1, 3.2, 9.2, 9.3_
  
  - [ ]* 8.5 Write integration tests for DAP engine integration
    - Test fallback activation when element not visible
    - Test direct highlight preservation for visible elements
    - Test response format compatibility
    - Test no performance regression for direct highlight flow
    - _Requirements: 5.1, 5.2, 5.3, 9.1, 9.2, 9.3_

- [ ] 9. Checkpoint - Verify DAP integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Implement extension enhancements for visual feedback
  - [~] 10.1 Create NavigationHighlighter class in extension
    - Create `extension/modules/navigation_highlighter.js`
    - Implement constructor with highlight style configuration
    - Define highlight border, shadow, and z-index styles
    - _Requirements: 4.2, 4.5_
  
  - [~] 10.2 Implement step highlighting functionality
    - Write `highlightStep()` to highlight current navigation element
    - Support both CSS selector and data-aura-map ID lookup
    - Apply visual highlight styles to target element
    - Store current highlight reference for cleanup
    - _Requirements: 4.2, 4.5_
  
  - [~] 10.3 Implement step tooltip display
    - Write `showStepTooltip()` to display step information
    - Position tooltip near highlighted element
    - Show breadcrumb path and step description
    - Auto-hide tooltip after configurable duration
    - _Requirements: 4.2_
  
  - [~] 10.4 Implement highlight cleanup
    - Write `clearHighlight()` to remove current highlight
    - Remove tooltip elements
    - Reset highlight state
    - _Requirements: 4.2, 4.5_
  
  - [ ]* 10.5 Write unit tests for extension components
    - Test highlight application and removal
    - Test tooltip positioning and display
    - Test selector lookup fallback strategies
    - _Requirements: 4.2, 4.5_

- [ ] 11. Implement file watching for incremental updates
  - [~] 11.1 Add watchdog dependency for file monitoring
    - Add `watchdog` to project dependencies
    - Install and verify watchdog library
    - _Requirements: 7.4_
  
  - [~] 11.2 Implement roteiro directory watcher
    - Write `watch_roteiros_directory()` in RoteiroIndexer
    - Create FileSystemEventHandler for roteiro changes
    - Trigger incremental index updates on file modifications
    - Invalidate cache for modified roteiros
    - _Requirements: 7.4_
  
  - [~] 11.3 Start file watcher on application startup
    - Initialize file watcher in NavigationFallbackEngine
    - Start observer thread for background monitoring
    - Add graceful shutdown for observer thread
    - _Requirements: 7.4_
  
  - [ ]* 11.4 Write unit tests for file watching
    - Test index update on file modification
    - Test cache invalidation on file changes
    - Test observer startup and shutdown
    - _Requirements: 7.4_

- [ ] 12. Implement performance optimizations
  - [~] 12.1 Add query normalization for cache efficiency
    - Write `_normalize_query()` to standardize search queries
    - Convert to lowercase and remove accents
    - Remove stop words and apply stemming
    - Use normalized query as cache key
    - _Requirements: 7.3, 7.5_
  
  - [~] 12.2 Implement parallel roteiro search
    - Write `search_parallel()` using asyncio.gather
    - Search multiple roteiros concurrently
    - Aggregate and rank results by confidence score
    - _Requirements: 7.2, 7.5_
  
  - [ ]* 12.3 Write performance tests for index operations
    - Measure index build time for 1000 roteiros (target: < 5 seconds)
    - Measure lookup time for various queries (target: < 200ms for 95%)
    - Measure cache hit rate (target: > 80% for frequent queries)
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

- [ ] 13. Checkpoint - Verify performance targets
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implement user confirmation flow handling
  - [~] 14.1 Add confirmation response parsing
    - Implement affirmative response detection ("sim", "yes", "pode", "quero", "vamos")
    - Implement negative response detection ("não", "no", "agora não", "depois")
    - Handle ambiguous responses with clarification request
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [~] 14.2 Integrate confirmation flow in DAP engine
    - Track conversation state for pending navigation offers
    - Detect confirmation responses in follow-up messages
    - Trigger guided navigation on affirmative confirmation
    - Return to conversation on negative confirmation
    - _Requirements: 10.1, 10.2, 10.3, 10.4_
  
  - [ ]* 14.3 Write unit tests for confirmation parsing
    - Test affirmative response detection
    - Test negative response detection
    - Test ambiguous response handling
    - Test confirmation state tracking
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 15. Add logging and monitoring
  - [~] 15.1 Implement navigation metrics tracking
    - Add metrics for fallback activations
    - Track navigation success/failure counts
    - Measure average navigation time
    - Track cache hit rate and index size
    - _Requirements: 9.4_
  
  - [~] 15.2 Add structured logging for navigation events
    - Log fallback activation with query and tenant_id
    - Log navigation path selection with confidence score
    - Log each navigation step execution
    - Log navigation failures with error details
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 9.4_
  
  - [~] 15.3 Create monitoring dashboard endpoint
    - Add `/api/navigation/metrics` endpoint in app.py
    - Return navigation metrics as JSON
    - Include cache statistics and index size
    - _Requirements: 9.4_

- [ ] 16. Add configuration and deployment support
  - [~] 16.1 Add configuration constants to .env.example
    - Add `NAVIGATION_FALLBACK_ENABLED` flag
    - Add `ROTEIRO_INDEX_DB` path configuration
    - Add `ROTEIRO_INDEX_CACHE_SIZE` setting
    - Add `NAVIGATION_STEP_TIMEOUT_MS` setting
    - Add `ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS` setting
    - _Requirements: 1.4, 4.4, 7.1, 7.3_
  
  - [~] 16.2 Implement database migration script
    - Write `migrate_to_navigation_index()` function
    - Create navigation index database on first run
    - Populate index from existing roteiros
    - Add migration logging
    - _Requirements: 7.1_
  
  - [~] 16.3 Add feature flag support
    - Check `NAVIGATION_FALLBACK_ENABLED` before activation
    - Gracefully disable feature if flag is false
    - Log feature status on startup
    - _Requirements: 9.1_

- [ ] 17. Final integration and wiring
  - [~] 17.1 Initialize NavigationFallbackEngine on app startup
    - Create global NavigationFallbackEngine instance in dap_engine.py
    - Build initial index on startup
    - Start file watcher for incremental updates
    - Log initialization status
    - _Requirements: 7.1, 7.4, 9.1_
  
  - [~] 17.2 Wire extension communication for highlights
    - Implement WebSocket or HTTP endpoint for highlight commands
    - Send highlight commands from GuidedNavigationExecutor to extension
    - Handle highlight acknowledgment from extension
    - _Requirements: 4.2, 4.5_
  
  - [ ]* 17.3 Write end-to-end integration tests
    - Test complete flow from invisible element detection to guided navigation
    - Test user confirmation and navigation execution
    - Test failure handling and graceful degradation
    - Test performance requirements (visibility check < 500ms, lookup < 200ms)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 3.1, 3.2, 4.1, 4.2, 4.5, 7.2, 7.5_

- [ ] 18. Final checkpoint - Complete system validation
  - Ensure all tests pass, ask the user if questions arise.
  - Verify no performance regression for existing direct highlight flow
  - Verify all acceptance criteria met
  - Verify all time-critical operations meet performance targets

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical breaks
- Property tests validate universal correctness properties from the design
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end flows across components
- Performance tests validate time-critical operations meet targets

## Testing Strategy Summary

### Property-Based Tests (Optional)
1. **Property 1: Index completeness** - Validates that all roteiros are indexed
2. **Property 2: Search determinism** - Validates consistent search results
3. **Property 3: State machine validity** - Validates navigation state transitions
4. **Property 4: Fallback strategy correctness** - Validates graceful degradation
5. **Property 5: Visibility check latency** - Validates performance requirement
6. **Property 6: Round-trip consistency** - Validates parsing preserves sequences

### Unit Tests (Optional)
- Cache behavior (hit/miss, LRU eviction, invalidation)
- Malformed roteiro handling (missing fields, invalid JSON)
- Failure scenarios (element not found, timeout, structure mismatch)
- Extension components (highlight, tooltip, cleanup)
- File watching (index update, cache invalidation)
- Confirmation parsing (affirmative, negative, ambiguous)

### Integration Tests (Optional)
- End-to-end navigation flow
- DAP engine integration
- Extension integration
- Performance validation

## Performance Targets

- **Element visibility check**: < 500ms (Requirement 1.4)
- **Index lookup**: < 200ms for 95% of queries (Requirement 7.5)
- **Navigation step timeout**: 2 seconds (Requirement 4.4)
- **Index build time**: < 5 seconds for 1000 roteiros (Design target)
- **Cache hit rate**: > 80% for frequent queries (Design target)

## Deployment Checklist

1. Add configuration to `.env` file
2. Run database migration to create navigation index
3. Verify index builds successfully from existing roteiros
4. Test fallback activation with invisible elements
5. Test direct highlight preservation for visible elements
6. Monitor performance metrics after deployment
7. Verify no regression in existing DAP functionality

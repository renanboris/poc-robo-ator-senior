# Requirements Document

## Introduction

This document specifies requirements for implementing automatic namespace detection for RAG (Retrieval-Augmented Generation) queries in the Senior Training OS platform. The system currently has a web knowledge ingestion pipeline that indexes documentation into Pinecone using module-based namespaces (e.g., "hcm", "financeiro"), but roteiro generation and capture workflows do not leverage these namespaces, resulting in poor retrieval accuracy.

The automatic namespace detection feature will extract module/theme information from available context (URLs, roteiro metadata, workflow objectives) and automatically pass the correct namespace to `buscar_contexto()` calls, enabling the RAG system to find relevant web documentation when generating or capturing roteiros.

## Glossary

- **RAG_System**: The Retrieval-Augmented Generation system that combines Pinecone vector search with LLM generation
- **Namespace**: A Pinecone index partition that isolates vectors by module/domain (e.g., "hcm", "financeiro", "ged")
- **Namespace_Detector**: The component responsible for extracting and mapping module information to Pinecone namespaces
- **Generator_Engine**: The module that generates roteiros from user objectives using AI and RAG context
- **Capture_Engine**: The module that records user workflows and converts them to roteiros
- **DAP_Engine**: The Digital Adoption Platform engine that provides RAG retrieval via `buscar_contexto()`
- **Nivel_2**: The second path segment in Senior X documentation URLs, used as the namespace identifier
- **Extractor**: The ingestion pipeline component that derives namespaces from URL structure
- **Tenant_ID**: The default namespace fallback representing the organization identifier

## Requirements

### Requirement 1: Namespace Detection from URLs

**User Story:** As a system architect, I want the RAG system to automatically detect the correct namespace from Senior X URLs, so that roteiro generation finds relevant module-specific documentation.

#### Acceptance Criteria

1. WHEN a Senior X URL is provided in the context, THE Namespace_Detector SHALL extract the nivel_2 segment from the URL path
2. WHEN the URL follows the pattern `/senior-x/{module}/{feature}`, THE Namespace_Detector SHALL return `{module}` as the namespace
3. WHEN the URL follows the pattern `/senior-x/{product}/manual-do-usuario/{module}`, THE Namespace_Detector SHALL return `{module}` as the namespace
4. WHEN the URL contains no recognizable module pattern, THE Namespace_Detector SHALL return None
5. THE Namespace_Detector SHALL normalize namespace values to lowercase kebab-case format

### Requirement 2: Namespace Detection from Roteiro Metadata

**User Story:** As a training author, I want the system to detect namespaces from existing roteiro metadata, so that related roteiros benefit from module-specific context.

#### Acceptance Criteria

1. WHEN a roteiro contains a `source_url` field in metadata, THE Namespace_Detector SHALL extract the namespace from that URL
2. WHEN a roteiro contains a `module` field in metadata, THE Namespace_Detector SHALL use that value as the namespace
3. WHEN a roteiro `nome_aula` contains Senior X module keywords, THE Namespace_Detector SHALL map those keywords to namespaces
4. WHEN multiple namespace indicators exist, THE Namespace_Detector SHALL prioritize explicit `module` field over URL extraction over keyword matching
5. THE Namespace_Detector SHALL return None if no namespace indicators are found in metadata

### Requirement 3: Namespace Detection from Workflow Objectives

**User Story:** As a workflow mapper, I want the system to infer namespaces from workflow objectives, so that capture sessions retrieve relevant documentation without manual configuration.

#### Acceptance Criteria

1. WHEN a workflow objective contains Senior X module names (e.g., "HCM", "Financeiro", "GED"), THE Namespace_Detector SHALL map those names to corresponding namespaces
2. WHEN a workflow objective contains feature keywords associated with specific modules, THE Namespace_Detector SHALL infer the namespace from the keyword mapping
3. THE Namespace_Detector SHALL maintain a configurable keyword-to-namespace mapping table
4. WHEN multiple module keywords appear in the objective, THE Namespace_Detector SHALL select the first matched namespace
5. THE Namespace_Detector SHALL perform case-insensitive keyword matching

### Requirement 4: Namespace Fallback Strategy

**User Story:** As a system reliability engineer, I want the namespace detection to gracefully fall back to tenant_id when detection fails, so that the system continues to function even without module-specific context.

#### Acceptance Criteria

1. WHEN the Namespace_Detector returns None, THE RAG_System SHALL use tenant_id as the namespace
2. WHEN namespace detection raises an exception, THE RAG_System SHALL log the error and fall back to tenant_id
3. THE RAG_System SHALL NOT fail or block execution when namespace detection is unavailable
4. WHEN tenant_id is also unavailable, THE RAG_System SHALL use "senior_default" as the final fallback
5. THE RAG_System SHALL log all namespace fallback events for observability

### Requirement 5: Integration with Generator Engine

**User Story:** As a roteiro generator, I want automatic namespace detection integrated into the generation workflow, so that generated roteiros include relevant module-specific documentation context.

#### Acceptance Criteria

1. WHEN `gerar_roteiro_ia_sync()` calls `buscar_contexto()`, THE Generator_Engine SHALL detect the namespace from the objetivo parameter
2. WHEN a namespace is detected, THE Generator_Engine SHALL pass it to `buscar_contexto()` via the namespace parameter
3. WHEN no namespace is detected, THE Generator_Engine SHALL omit the namespace parameter (allowing default behavior)
4. THE Generator_Engine SHALL log the detected namespace for debugging and observability
5. THE Generator_Engine SHALL preserve backward compatibility with existing roteiro generation flows

### Requirement 6: Integration with Capture Engine

**User Story:** As a workflow capture operator, I want automatic namespace detection during capture sessions, so that the RAG context includes relevant module documentation.

#### Acceptance Criteria

1. WHEN `buscar_contexto_pinecone()` is called in capture.py, THE Capture_Engine SHALL detect the namespace from the objetivo_aula parameter
2. WHEN the capture session includes a Senior X URL in context, THE Capture_Engine SHALL extract the namespace from that URL
3. WHEN a namespace is detected, THE Capture_Engine SHALL pass it to the underlying `buscar_contexto()` call
4. THE Capture_Engine SHALL log the detected namespace for session diagnostics
5. THE Capture_Engine SHALL maintain the same fallback behavior as Generator_Engine

### Requirement 7: Reuse Nivel_2 Extraction Logic

**User Story:** As a system maintainer, I want namespace detection to reuse the existing nivel_2 extraction logic from the ingestion pipeline, so that namespace derivation is consistent across ingestion and retrieval.

#### Acceptance Criteria

1. THE Namespace_Detector SHALL use the same URL parsing logic as `Extractor.extract_breadcrumbs()`
2. THE Namespace_Detector SHALL apply the same normalization rules as `Extractor.normalize_hierarchy()`
3. WHEN special URL patterns exist (e.g., seniorxplatform/manual-do-usuario/ged), THE Namespace_Detector SHALL apply the same special handling as the Extractor
4. THE Namespace_Detector SHALL NOT duplicate the nivel_2 extraction code
5. THE Namespace_Detector SHALL call shared utility functions for URL parsing and normalization

### Requirement 8: Namespace Detection API

**User Story:** As a developer, I want a clean API for namespace detection, so that I can easily integrate it into different parts of the system.

#### Acceptance Criteria

1. THE Namespace_Detector SHALL provide a function `detectar_namespace(contexto: dict) -> Optional[str]`
2. THE contexto parameter SHALL accept keys: `url`, `objetivo`, `metadata`, `nome_aula`
3. THE function SHALL return a normalized namespace string or None
4. THE function SHALL NOT raise exceptions for invalid input
5. THE function SHALL be importable from a shared module (e.g., `utils.py` or `namespace_detector.py`)

### Requirement 9: Keyword-to-Namespace Mapping Configuration

**User Story:** As a system administrator, I want to configure keyword-to-namespace mappings without code changes, so that I can adapt the system to new modules or terminology.

#### Acceptance Criteria

1. THE Namespace_Detector SHALL load keyword mappings from a configuration file (JSON or environment variable)
2. THE configuration file SHALL map keywords to namespace values (e.g., `{"hcm": ["recursos humanos", "admissao", "folha"], "financeiro": ["contas a pagar", "tesouraria"]}`)
3. WHEN the configuration file is missing, THE Namespace_Detector SHALL use a hardcoded default mapping
4. THE Namespace_Detector SHALL reload the configuration file when it changes (or on next detection call)
5. THE configuration file SHALL support case-insensitive keyword matching

### Requirement 10: Observability and Logging

**User Story:** As a system operator, I want detailed logging of namespace detection decisions, so that I can diagnose retrieval accuracy issues.

#### Acceptance Criteria

1. WHEN a namespace is detected, THE Namespace_Detector SHALL log the detection source (URL, metadata, keyword)
2. WHEN namespace detection fails, THE Namespace_Detector SHALL log the reason for failure
3. WHEN a fallback occurs, THE RAG_System SHALL log the fallback chain (detected → tenant_id → senior_default)
4. THE logs SHALL include the original context input and the final namespace used
5. THE logs SHALL use INFO level for successful detection and WARNING level for fallbacks

### Requirement 11: Backward Compatibility

**User Story:** As a system maintainer, I want namespace detection to be backward compatible, so that existing workflows continue to function without modification.

#### Acceptance Criteria

1. WHEN namespace detection is disabled or unavailable, THE RAG_System SHALL behave exactly as it does today
2. THE `buscar_contexto()` function signature SHALL remain unchanged (namespace parameter is already optional)
3. WHEN no namespace is detected, THE RAG_System SHALL use the existing tenant_id behavior
4. THE integration SHALL NOT require changes to existing roteiro JSON files
5. THE integration SHALL NOT break existing unit tests or integration tests

### Requirement 12: Performance and Efficiency

**User Story:** As a performance engineer, I want namespace detection to add minimal latency to RAG queries, so that user experience is not degraded.

#### Acceptance Criteria

1. THE Namespace_Detector SHALL complete detection in less than 10 milliseconds for typical inputs
2. THE Namespace_Detector SHALL NOT make external API calls or database queries
3. THE Namespace_Detector SHALL cache compiled regex patterns for URL parsing
4. THE Namespace_Detector SHALL NOT load configuration files on every detection call
5. THE Namespace_Detector SHALL use efficient string matching algorithms for keyword detection

### Requirement 13: Testing and Validation

**User Story:** As a quality assurance engineer, I want comprehensive tests for namespace detection, so that I can verify correctness across different input scenarios.

#### Acceptance Criteria

1. THE test suite SHALL include unit tests for URL-based detection with 10+ URL patterns
2. THE test suite SHALL include unit tests for metadata-based detection with 5+ metadata structures
3. THE test suite SHALL include unit tests for keyword-based detection with 10+ objective phrases
4. THE test suite SHALL include integration tests verifying end-to-end namespace propagation to Pinecone queries
5. THE test suite SHALL include tests for fallback behavior and error handling

### Requirement 14: Documentation and Examples

**User Story:** As a developer, I want clear documentation and examples for namespace detection, so that I can understand and extend the feature.

#### Acceptance Criteria

1. THE documentation SHALL explain the namespace detection priority order (URL > metadata > keyword > fallback)
2. THE documentation SHALL provide examples of valid URL patterns and their extracted namespaces
3. THE documentation SHALL document the keyword-to-namespace mapping configuration format
4. THE documentation SHALL include code examples showing how to call `detectar_namespace()`
5. THE documentation SHALL explain the relationship between ingestion namespaces and retrieval namespaces

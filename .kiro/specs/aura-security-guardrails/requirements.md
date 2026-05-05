# Requirements Document

## Introduction

This document defines the security guardrails for the Aura DAP (Digital Adoption Platform) system. Aura is an AI assistant that helps users navigate the Senior X ERP system. Currently, Aura can generate responses using external AI knowledge, which poses security and content control risks. This feature implements comprehensive security controls to ensure Aura only responds based on indexed documentation, blocks malicious inputs, filters inappropriate content, and maintains a complete audit trail of security events.

## Glossary

- **Aura_DAP**: The Digital Adoption Platform AI assistant that guides users through Senior X ERP
- **Vector_Store**: Pinecone database containing indexed documentation and roteiros (training workflows)
- **RAG_Engine**: Retrieval-Augmented Generation system that searches the Vector_Store for relevant context
- **Gemini_Client**: Google Gemini AI model used for response generation
- **OpenAI_Client**: OpenAI service used for embeddings and vector search
- **Confidence_Score**: Numerical value (0.0-1.0) indicating relevance of retrieved content
- **Source_Reference**: Metadata linking a response to its origin in the Vector_Store
- **Injection_Attack**: Malicious input attempting to manipulate AI behavior or execute unauthorized commands
- **Tenant_ID**: Identifier for multi-tenant isolation in the Vector_Store
- **Namespace**: Logical partition in Pinecone for organizing content by module or tenant
- **Security_Event**: Logged incident of blocked content or detected attack attempt
- **Guardrail**: Security control that validates and filters inputs or outputs
- **Fallback_Response**: Predefined message returned when no valid content is found

## Requirements

### Requirement 1: Vector Store Content Restriction

**User Story:** As a system administrator, I want Aura to only respond based on indexed documentation in the Vector_Store, so that users receive accurate and controlled information.

#### Acceptance Criteria

1. WHEN Aura receives a user prompt, THE RAG_Engine SHALL search the Vector_Store for relevant content before generating a response
2. WHEN the RAG_Engine returns results with Confidence_Score below 0.45, THE Aura_DAP SHALL return a Fallback_Response stating "I don't have information about this in my knowledge base"
3. WHEN the RAG_Engine returns no results, THE Aura_DAP SHALL return a Fallback_Response stating "I don't have information about this in my knowledge base"
4. THE Aura_DAP SHALL NOT generate responses using external AI knowledge when Vector_Store content is unavailable
5. WHEN Aura generates a response, THE Aura_DAP SHALL include Source_Reference metadata linking to the Vector_Store origin
6. WHEN Aura generates a response, THE Aura_DAP SHALL include the Confidence_Score in the response metadata

### Requirement 2: SQL Injection Detection and Blocking

**User Story:** As a security engineer, I want Aura to detect and block SQL injection attempts, so that the database remains protected from malicious queries.

#### Acceptance Criteria

1. WHEN a user prompt contains SQL keywords combined with special characters, THE Aura_DAP SHALL classify it as a potential SQL injection attempt
2. WHEN a SQL injection attempt is detected, THE Aura_DAP SHALL block the request and return an error message
3. THE Aura_DAP SHALL detect SQL injection patterns including: SELECT, INSERT, UPDATE, DELETE, DROP, UNION, OR 1=1, semicolon-terminated statements, comment sequences (-- or /*), and encoded SQL syntax
4. WHEN a SQL injection attempt is blocked, THE Aura_DAP SHALL log a Security_Event with the full prompt and timestamp
5. THE Aura_DAP SHALL NOT execute or pass SQL injection attempts to downstream systems

### Requirement 3: Prompt Injection Detection and Blocking

**User Story:** As a security engineer, I want Aura to detect and block prompt injection attempts, so that users cannot manipulate the AI's behavior or bypass security controls.

#### Acceptance Criteria

1. WHEN a user prompt contains instructions to ignore previous instructions, THE Aura_DAP SHALL classify it as a prompt injection attempt
2. WHEN a user prompt contains instructions to reveal system prompts or internal configuration, THE Aura_DAP SHALL classify it as a prompt injection attempt
3. WHEN a user prompt contains role-switching instructions (e.g., "you are now a different assistant"), THE Aura_DAP SHALL classify it as a prompt injection attempt
4. WHEN a prompt injection attempt is detected, THE Aura_DAP SHALL block the request and return an error message
5. THE Aura_DAP SHALL detect prompt injection patterns including: "ignore previous instructions", "disregard all rules", "reveal your prompt", "you are now", "system:", "assistant:", and encoded variations
6. WHEN a prompt injection attempt is blocked, THE Aura_DAP SHALL log a Security_Event with the full prompt and timestamp

### Requirement 4: Offensive Content Filtering

**User Story:** As a compliance officer, I want Aura to filter offensive language and inappropriate content, so that the platform maintains professional standards.

#### Acceptance Criteria

1. WHEN a user prompt contains profanity or offensive language, THE Aura_DAP SHALL classify it as inappropriate content
2. WHEN inappropriate content is detected, THE Aura_DAP SHALL block the request and return a professional error message
3. THE Aura_DAP SHALL detect offensive content in multiple languages including Portuguese and English
4. WHEN offensive content is blocked, THE Aura_DAP SHALL log a Security_Event with a sanitized version of the prompt (offensive words redacted)
5. THE Aura_DAP SHALL maintain a configurable blocklist of offensive terms that can be updated without code changes

### Requirement 5: Competitor Mention Handling

**User Story:** As a product manager, I want Aura to detect and appropriately handle mentions of competitor products, so that responses remain focused on Senior X capabilities.

#### Acceptance Criteria

1. WHEN a user prompt mentions a competitor product or company, THE Aura_DAP SHALL detect the competitor reference
2. WHEN a competitor is mentioned, THE Aura_DAP SHALL search the Vector_Store for Senior X equivalent functionality
3. WHEN Senior X equivalent functionality is found, THE Aura_DAP SHALL respond with Senior X capabilities without directly comparing to competitors
4. WHEN no Senior X equivalent is found, THE Aura_DAP SHALL return a neutral response stating "I can help you with Senior X features. What would you like to accomplish?"
5. THE Aura_DAP SHALL maintain a configurable list of competitor names including: SAP, Oracle, Totvs, Sankhya, and their product variants

### Requirement 6: Response Traceability

**User Story:** As an auditor, I want every Aura response to be traceable to its source in the Vector_Store, so that content accuracy can be verified.

#### Acceptance Criteria

1. WHEN Aura generates a response, THE Aura_DAP SHALL include the Source_Reference identifying the Vector_Store document
2. WHEN Aura generates a response, THE Aura_DAP SHALL include the Confidence_Score indicating retrieval relevance
3. WHEN Aura generates a response from multiple Vector_Store sources, THE Aura_DAP SHALL include all Source_Reference entries ranked by Confidence_Score
4. WHEN Aura uses the AI Gate bypass (Confidence_Score > 0.80), THE Aura_DAP SHALL still include Source_Reference and Confidence_Score in the response
5. THE Aura_DAP SHALL include the source_url field when the response originates from web documentation in the Vector_Store

### Requirement 7: Security Event Logging

**User Story:** As a security analyst, I want all blocked attempts and security events to be logged, so that I can monitor threats and analyze attack patterns.

#### Acceptance Criteria

1. WHEN any Guardrail blocks a request, THE Aura_DAP SHALL create a Security_Event record in the database
2. THE Security_Event SHALL include: event_type, timestamp, tenant_id, user_id (anonymized), prompt_hash, guardrail_triggered, and severity_level
3. WHEN a Security_Event is created, THE Aura_DAP SHALL persist it to the aura_security_events table in brain.db within 100 milliseconds
4. THE Aura_DAP SHALL NOT log full prompts containing sensitive information, instead storing a SHA-256 hash
5. WHEN multiple Guardrails trigger on the same prompt, THE Aura_DAP SHALL log separate Security_Event records for each violation

### Requirement 8: Guardrail Configuration Management

**User Story:** As a system administrator, I want to enable or disable specific guardrails without code changes, so that I can adapt security controls to operational needs.

#### Acceptance Criteria

1. THE Aura_DAP SHALL read guardrail configuration from environment variables on startup
2. WHEN a Guardrail is disabled via configuration, THE Aura_DAP SHALL skip that validation check
3. THE Aura_DAP SHALL support configuration flags for: ENABLE_SQL_INJECTION_CHECK, ENABLE_PROMPT_INJECTION_CHECK, ENABLE_OFFENSIVE_CONTENT_FILTER, ENABLE_COMPETITOR_FILTER, and ENABLE_VECTOR_STORE_ONLY
4. WHEN all content guardrails are disabled, THE Aura_DAP SHALL still enforce Vector_Store content restriction (Requirement 1)
5. WHEN configuration changes are detected, THE Aura_DAP SHALL log the configuration state at startup

### Requirement 9: Performance Preservation

**User Story:** As a user, I want Aura to respond quickly even with security guardrails enabled, so that my workflow is not disrupted.

#### Acceptance Criteria

1. WHEN all Guardrails are enabled, THE Aura_DAP SHALL respond to user prompts within 3 seconds for 95% of requests
2. WHEN the Vector_Store cache hits (existing query), THE Aura_DAP SHALL respond within 500 milliseconds
3. THE Aura_DAP SHALL execute all Guardrail checks in parallel before calling the Gemini_Client
4. WHEN a Guardrail blocks a request, THE Aura_DAP SHALL return the error response within 200 milliseconds
5. THE Aura_DAP SHALL NOT introduce additional database queries per request beyond the Security_Event logging

### Requirement 10: Clear User Feedback

**User Story:** As a user, I want to understand why my request was blocked, so that I can rephrase my question appropriately.

#### Acceptance Criteria

1. WHEN a SQL injection attempt is blocked, THE Aura_DAP SHALL return the message "Your request contains patterns that cannot be processed. Please rephrase your question."
2. WHEN a prompt injection attempt is blocked, THE Aura_DAP SHALL return the message "I can only help with Senior X questions. Please ask about specific features or tasks."
3. WHEN offensive content is blocked, THE Aura_DAP SHALL return the message "Please keep your questions professional. How can I help you with Senior X?"
4. WHEN no Vector_Store content is found, THE Aura_DAP SHALL return the message "I don't have information about this in my knowledge base. Try asking about Senior X modules, features, or tasks."
5. WHEN a competitor is mentioned without Senior X equivalent, THE Aura_DAP SHALL return the message "I can help you with Senior X features. What would you like to accomplish?"

### Requirement 11: Audit Trail Retention

**User Story:** As a compliance officer, I want security events to be retained for audit purposes, so that we can demonstrate security controls to auditors.

#### Acceptance Criteria

1. THE Aura_DAP SHALL retain Security_Event records in brain.db for a minimum of 90 days
2. WHEN Security_Event records exceed 90 days old, THE Aura_DAP SHALL archive them to a separate audit_archive table
3. THE Aura_DAP SHALL provide an API endpoint to query Security_Event records by date range, event_type, and tenant_id
4. WHEN the audit API is called, THE Aura_DAP SHALL return results within 2 seconds for queries spanning up to 30 days
5. THE Aura_DAP SHALL support exporting Security_Event records to JSON format for external audit tools

### Requirement 12: Multi-Tenant Isolation

**User Story:** As a platform operator, I want security events and guardrails to respect tenant boundaries, so that one tenant's data does not leak to another.

#### Acceptance Criteria

1. WHEN logging a Security_Event, THE Aura_DAP SHALL include the Tenant_ID from the request context
2. WHEN querying Security_Event records, THE Aura_DAP SHALL filter results by the requesting Tenant_ID
3. THE Aura_DAP SHALL enforce Vector_Store Namespace isolation per Tenant_ID
4. WHEN a user from Tenant A queries Aura, THE RAG_Engine SHALL only search the Vector_Store Namespace for Tenant A
5. THE Aura_DAP SHALL NOT allow cross-tenant access to Security_Event logs or Vector_Store content

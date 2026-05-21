# Aura DAP RAG Optimization Bugfix Design

## Overview

The Aura DAP engine (`dap_engine.py`) wastes expensive API calls on two categories of queries that should be handled earlier in the pipeline. Identity/meta questions ("Quem é vc?", "Qual seu nome?") trigger the full RAG + Vision pipeline when they should return instant canned responses. Informal/abbreviated queries ("O que é o HCM?") produce poor embeddings because the raw text doesn't match formally-indexed content in Pinecone.

The fix introduces two lightweight pre-processing stages at the top of `_analisar_sync()` — an identity detector and a query normalizer — both executing BEFORE any external API call. This preserves the entire existing pipeline for all other queries while eliminating unnecessary costs and improving retrieval quality.

## Glossary

- **Bug_Condition (C)**: Two conditions: (1) identity/meta questions that waste API calls, (2) informal/short queries that fail retrieval
- **Property (P)**: (1) Identity questions return instant canned responses with zero API calls; (2) Informal queries are normalized before embedding to improve Pinecone retrieval
- **Preservation**: All existing behavior for non-identity, formally-phrased queries must remain unchanged — cache, RAG search, AI Gate, Vision fallback all operate identically
- **`_analisar_sync()`**: The main pipeline function in `dap_engine.py` that orchestrates cache → RAG → AI Gate → Vision
- **`buscar_contexto_multi_namespace()`**: Function that generates one OpenAI embedding then queries all active Pinecone namespaces in parallel threads
- **`gerar_embedding()`**: Calls OpenAI `text-embedding-3-large` (3072 dims) to produce a vector from text
- **Identity Pattern**: A regex or keyword match identifying questions about Aura's identity, name, purpose, or capabilities
- **Query Normalization**: Expanding abbreviations and adding context keywords to improve embedding similarity against formally-indexed content

## Bug Details

### Bug Condition

The bug manifests in two related scenarios within `_analisar_sync()`:

1. **Identity waste**: When a user asks an identity/meta question, the system proceeds past the cache check (which misses because these are first-time questions) and calls `buscar_contexto_multi_namespace()` — generating an OpenAI embedding and querying 26+ Pinecone namespaces — then falls through to Gemini Vision. Total wasted cost: ~$0.01-0.03 per query.

2. **Retrieval failure**: When a user asks an informal/abbreviated query, the raw text is passed directly to `gerar_embedding()`. The resulting vector has poor cosine similarity against formally-indexed content, causing all namespace queries to return below `SCORE_THRESHOLD` (0.45), effectively returning no context.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type UserQuery (prompt_usuario string)
  OUTPUT: boolean
  
  RETURN isBugCondition_Identity(input) OR isBugCondition_Normalization(input)
END FUNCTION

FUNCTION isBugCondition_Identity(input)
  INPUT: input of type UserQuery
  OUTPUT: boolean
  
  normalized_prompt = input.prompt_usuario.lower().strip()
  RETURN normalized_prompt matches any identity pattern IN [
    "quem é vc", "quem é você", "quem e voce", "qual seu nome",
    "qual é seu nome", "qual o seu nome", "o que vc faz",
    "o que você faz", "o que voce faz", "quem te criou",
    "como vc se chama", "como você se chama", "vc é quem",
    "me fala sobre vc", "se apresenta", "se apresente"
  ]
END FUNCTION

FUNCTION isBugCondition_Normalization(input)
  INPUT: input of type UserQuery
  OUTPUT: boolean
  
  RETURN input.prompt_usuario contains known_abbreviation IN MODULE_ALIASES
         OR input.prompt_usuario contains informal_markers ("q ", "vc", "pq", "tb")
         AND NOT isBugCondition_Identity(input)
END FUNCTION
```

### Examples

- **Identity waste**: User asks "Quem é vc?" → System generates embedding, queries 26 namespaces (all return score < 0.45), then calls Gemini Vision with screenshot just to produce a self-introduction. Expected: instant canned response, zero API calls.
- **Identity waste**: User asks "Qual seu nome?" → Same expensive pipeline triggered. Expected: instant response "Sou a Aura, sua assistente virtual..."
- **Retrieval failure**: User asks "O que é o HCM?" → Embedding of "O que é o HCM?" has low similarity to indexed content about "Gestão de Pessoas - Human Capital Management". Expected: normalize to "HCM Gestão de Pessoas Human Capital Management" before embedding.
- **Retrieval failure**: User asks "Só quero q vc me fale o que é o Konviva" → Raw informal text produces poor embedding. Expected: normalize to "Konviva plataforma educação corporativa LMS" before embedding.
- **Non-bug (preservation)**: User asks "Como acessar o módulo de folha de pagamento?" → Formal query, no abbreviations, not identity. Should proceed through full pipeline unchanged.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Cache check (SQLite with DOM hash) must continue to be the FIRST check in the pipeline
- RAG search via `buscar_contexto_multi_namespace()` must continue to work identically for non-identity, non-abbreviated queries
- Vector store content restriction guardrail must continue to operate as before
- AI Gate bypass (score > 0.80 with direct selector) must continue to activate for high-confidence results
- Gemini Vision fallback with conversational memory must continue to work for queries that need it
- All response structures (mensagem, elemento_id, seletor_css, sugestoes, confidence_score, source_reference) must remain unchanged
- Thread-safe parallel namespace querying must remain unchanged
- Retry logic with exponential backoff for Gemini API must remain unchanged

**Scope:**
All inputs that do NOT match identity patterns AND do NOT contain known abbreviations/informal markers should be completely unaffected by this fix. This includes:
- Navigation questions with formal phrasing ("Como acessar o módulo de folha?")
- Technical questions that already match indexed content well
- Queries that hit the cache
- Any query where the existing pipeline already produces good results

## Hypothesized Root Cause

Based on the bug description and code analysis, the root causes are:

1. **Missing early-exit for identity questions**: The `_analisar_sync()` function has no pre-processing stage between the cache check and the RAG search. Identity questions always miss the cache (unique phrasing, no DOM context match) and proceed to the expensive pipeline. There is no pattern-matching layer to intercept these trivially-answerable queries.

2. **No query normalization before embedding**: The `texto_busca_rag` variable is constructed directly from `historico[-1]['texto'] + prompt_usuario` and passed raw to `buscar_contexto_multi_namespace()`, which calls `gerar_embedding()` on it directly. Abbreviations like "HCM" produce embeddings in a different vector space region than the formally-indexed "Gestão de Pessoas Human Capital Management" content.

3. **Architectural gap**: The pipeline was designed assuming all queries need the full RAG + Vision treatment. No lightweight classification layer exists to route queries to cheaper response paths.

4. **Language-specific challenge**: Brazilian Portuguese informal writing uses heavy abbreviation ("vc" = "você", "q" = "que", "pq" = "porque") and module aliases ("HCM" = "Gestão de Pessoas") that diverge significantly from the formal documentation language used during Pinecone ingestion.

## Correctness Properties

Property 1: Bug Condition - Identity Questions Short-Circuit

_For any_ input where the identity bug condition holds (isBugCondition_Identity returns true), the fixed `_analisar_sync()` function SHALL return a canned identity response immediately after the cache check, WITHOUT calling `gerar_embedding()`, `buscar_contexto_multi_namespace()`, or the Gemini Vision API. The response SHALL include a personality-appropriate message and non-empty suggestions list.

**Validates: Requirements 2.1, 2.4**

Property 2: Bug Condition - Query Normalization Improves Embedding Input

_For any_ input where the normalization bug condition holds (isBugCondition_Normalization returns true), the fixed pipeline SHALL expand abbreviations and add context keywords to the query text BEFORE passing it to `gerar_embedding()`. The normalized text SHALL contain more tokens than the original and SHALL include the expanded form of any recognized abbreviation.

**Validates: Requirements 2.2, 2.3**

Property 3: Preservation - Non-Identity Formal Queries Unchanged

_For any_ input where neither bug condition holds (NOT isBugCondition_Identity AND NOT isBugCondition_Normalization), the fixed function SHALL produce exactly the same result as the original function, preserving the full pipeline behavior including cache, RAG search, AI Gate, and Vision fallback.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

Property 4: Preservation - Normalization Is Additive Only

_For any_ input processed by the query normalizer, the original query terms SHALL still be present in the normalized output. Normalization SHALL only ADD context — never remove or replace the user's original words.

**Validates: Requirements 3.2, 3.5**

## Fix Implementation

### Changes Required

Assuming our root cause analysis is correct:

**File**: `dap_engine.py`

**Function**: `_analisar_sync()`

**Specific Changes**:

1. **Add identity detection constants** (module-level):
   - Define `_IDENTITY_PATTERNS`: list of regex patterns matching identity/meta questions in Portuguese
   - Define `_IDENTITY_RESPONSE`: canned response dict with personality-appropriate message and suggestions
   - Define `_is_identity_question(prompt: str) -> bool` helper function

2. **Add module alias map** (module-level):
   - Define `_MODULE_ALIASES`: dict mapping abbreviations to expanded forms (e.g., `"hcm" → "HCM Gestão de Pessoas Human Capital Management"`, `"bpm" → "BPM Business Process Management gestão processos"`, `"ged" → "GED Gestão Eletrônica de Documentos"`, etc.)
   - Define `_INFORMAL_MARKERS`: set of common informal abbreviations to detect (`"vc"`, `"q "`, `"pq"`, `"tb"`, `"oq"`)
   - Define `_normalizar_query(prompt: str) -> str` helper function

3. **Insert identity short-circuit** in `_analisar_sync()`:
   - AFTER the cache check (step 1) and BEFORE the RAG search (step 2)
   - Call `_is_identity_question(prompt_usuario)`
   - If true: log the interception, build response with user_name personalization, cache it, return immediately

4. **Insert query normalization** in `_analisar_sync()`:
   - AFTER identity check and BEFORE `buscar_contexto_multi_namespace()` call
   - Call `_normalizar_query(texto_busca_rag)` to expand abbreviations and add context
   - Pass the normalized text to `buscar_contexto_multi_namespace()` instead of raw text
   - Log when normalization modifies the query for observability

5. **Preserve pipeline ordering**:
   - Cache check remains FIRST (unchanged)
   - Identity detection is NEW step 1.5
   - Query normalization is NEW step 1.7
   - RAG search becomes step 2 (uses normalized text)
   - All subsequent steps (guardrail, AI Gate, Vision) remain unchanged

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on unfixed code, then verify the fix works correctly and preserves existing behavior.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE implementing the fix. Confirm or refute the root cause analysis. If we refute, we will need to re-hypothesize.

**Test Plan**: Write tests that mock the OpenAI and Pinecone clients, then call `_analisar_sync()` with identity/informal queries. Observe that the mocked APIs are called (proving the expensive pipeline runs). Run these tests on the UNFIXED code to observe the wasteful behavior.

**Test Cases**:
1. **Identity Pipeline Waste Test**: Call `_analisar_sync()` with "Quem é vc?" and assert that `gerar_embedding()` IS called (will demonstrate waste on unfixed code)
2. **Identity Vision Waste Test**: Call `_analisar_sync()` with "Qual seu nome?" and assert that Gemini Vision IS called (will demonstrate waste on unfixed code)
3. **Informal Query Retrieval Failure Test**: Call `buscar_contexto_multi_namespace()` with "O que é o HCM?" and observe score < SCORE_THRESHOLD (will demonstrate retrieval failure on unfixed code)
4. **Abbreviation Embedding Mismatch Test**: Compare embedding similarity of "HCM" vs "HCM Gestão de Pessoas Human Capital Management" against indexed content (will demonstrate the gap)

**Expected Counterexamples**:
- Identity questions trigger full pipeline (embedding + 26 namespace queries + Vision)
- Informal queries return no context or very low scores from Pinecone
- Possible causes: no early-exit path, no normalization layer

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed function produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition_Identity(input) DO
  result := _analisar_sync_fixed(input)
  ASSERT gerar_embedding NOT called
  ASSERT buscar_contexto_multi_namespace NOT called
  ASSERT gemini_client.generate_content NOT called
  ASSERT result.mensagem contains identity keywords
  ASSERT result.sugestoes is not empty
END FOR

FOR ALL input WHERE isBugCondition_Normalization(input) DO
  normalized := _normalizar_query(input.prompt)
  ASSERT len(normalized) > len(input.prompt)
  ASSERT all original words still present in normalized
  ASSERT expanded abbreviation terms present in normalized
END FOR
```

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed function produces the same result as the original function.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT _analisar_sync_original(input) = _analisar_sync_fixed(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the input domain
- It catches edge cases where normalization might accidentally modify formal queries
- It provides strong guarantees that the identity detector doesn't false-positive on legitimate questions
- It verifies that normalization is truly additive (never removes original terms)

**Test Plan**: Observe behavior on UNFIXED code first for formal queries and non-identity questions, then write property-based tests capturing that behavior.

**Test Cases**:
1. **Formal Query Preservation**: Verify that "Como acessar o módulo de folha de pagamento?" passes through normalization unchanged
2. **Non-Identity Preservation**: Verify that "O que é folha de pagamento?" is NOT intercepted by identity detector
3. **Cache Preservation**: Verify that cached responses are still served before any new logic runs
4. **AI Gate Preservation**: Verify that high-confidence RAG results still trigger AI Gate bypass
5. **Pipeline Order Preservation**: Verify that the sequence cache → identity → normalize → RAG → guardrail → AI Gate → Vision is maintained

### Unit Tests

- Test `_is_identity_question()` with known identity patterns (positive cases)
- Test `_is_identity_question()` with non-identity questions that mention "Aura" or "nome" in other contexts (negative cases)
- Test `_normalizar_query()` with known abbreviations (expansion verification)
- Test `_normalizar_query()` with formal queries (passthrough verification)
- Test `_normalizar_query()` with mixed informal + abbreviation queries
- Test identity response structure (mensagem, sugestoes, confidence_score fields)

### Property-Based Tests

- Generate random Portuguese strings and verify `_is_identity_question()` only returns true for actual identity patterns (low false-positive rate)
- Generate random queries with injected abbreviations and verify `_normalizar_query()` always expands them while preserving original text
- Generate random formal queries (no abbreviations, no informal markers) and verify `_normalizar_query()` returns them unchanged
- Generate random identity-like but non-identity queries and verify they are NOT short-circuited

### Integration Tests

- Test full `_analisar_sync()` flow with identity question and mocked APIs — verify zero external calls
- Test full `_analisar_sync()` flow with informal query and mocked Pinecone — verify normalized text reaches embedding
- Test full `_analisar_sync()` flow with formal query — verify identical behavior to unfixed code
- Test that identity responses are cached correctly for subsequent identical queries
- Test that normalized queries produce better Pinecone scores than raw queries (with real or realistic mock data)

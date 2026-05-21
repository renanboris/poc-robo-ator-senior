# Implementation Plan

## Overview

This plan fixes two bugs in the Aura DAP engine (`dap_engine.py`): (1) identity/meta questions wasting expensive API calls, and (2) informal/abbreviated queries producing poor embeddings. The fix introduces an identity detector that short-circuits the pipeline and a query normalizer that expands abbreviations before embedding. The implementation follows the exploratory bugfix workflow: write tests first to confirm the bugs, then implement the fix, then verify.

## Tasks

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Identity Questions Waste API Calls & Informal Queries Fail Retrieval
  - **CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior - it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate both bug conditions exist
  - **Scoped PBT Approach**: Scope the property to concrete failing cases:
    - Identity queries: "Quem é vc?", "Qual seu nome?", "O que vc faz?" with any user context
    - Informal queries: "O que é o HCM?", "Só quero q vc me fale o que é o Konviva" with any session state
  - **Test file**: `tests/test_dap_bug_condition.py`
  - **Setup**: Mock `gerar_embedding()`, `buscar_contexto_multi_namespace()`, and Gemini Vision client
  - **Bug Condition 1 (Identity)**: For all identity patterns from `isBugCondition_Identity`, call `_analisar_sync()` and assert:
    - `gerar_embedding()` is NOT called (expected behavior from design)
    - `buscar_contexto_multi_namespace()` is NOT called
    - Gemini Vision `generate_content()` is NOT called
    - Response contains identity keywords and non-empty `sugestoes`
  - **Bug Condition 2 (Normalization)**: For all queries matching `isBugCondition_Normalization`, assert:
    - The text passed to `gerar_embedding()` is longer than the raw input (normalized)
    - The normalized text contains expanded abbreviation terms
    - All original query words are preserved in the normalized text
  - Run test on UNFIXED code
  - **EXPECTED OUTCOME**: Test FAILS (this is correct - it proves the bugs exist)
  - Document counterexamples found:
    - Identity: "Quem é vc?" triggers embedding + 26 namespace queries + Vision call
    - Normalization: "O que é o HCM?" passes raw to embedding without expansion
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Identity Formal Queries Pipeline Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - **Test file**: `tests/test_dap_preservation.py`
  - **Setup**: Mock external APIs (OpenAI, Pinecone, Gemini) with deterministic responses
  - **Observe behavior on UNFIXED code**:
    - Observe: "Como acessar o módulo de folha de pagamento?" → full pipeline executes (embedding + namespace search + Vision if needed)
    - Observe: "O que é folha de pagamento?" → NOT intercepted as identity, proceeds through RAG
    - Observe: Cached query → served from cache before any processing
    - Observe: High-confidence RAG result (score > 0.80) → AI Gate bypass activates
  - **Write property-based tests capturing observed behavior**:
    - For all non-identity, non-abbreviated queries (NOT isBugCondition): pipeline calls remain identical
    - For all formal queries without abbreviations: `_normalizar_query()` returns input unchanged
    - For all queries: cache check remains the FIRST operation in the pipeline
    - For all high-confidence results: AI Gate bypass still activates (score > 0.80 with selector)
    - For all non-identity queries mentioning "Aura" or "nome" in other contexts: NOT short-circuited
  - **Hypothesis strategies**: Generate random Portuguese formal queries (no abbreviations, no informal markers, no identity patterns) and verify pipeline behavior is unchanged
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: Tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3. Fix for identity question short-circuit and query normalization

  - [ ] 3.1 Add identity detection constants and helper function
    - Add `_IDENTITY_PATTERNS` list at module level in `dap_engine.py` with regex patterns for identity/meta questions in Portuguese: "quem é vc", "quem é você", "quem e voce", "qual seu nome", "qual é seu nome", "qual o seu nome", "o que vc faz", "o que você faz", "o que voce faz", "quem te criou", "como vc se chama", "como você se chama", "vc é quem", "me fala sobre vc", "se apresenta", "se apresente"
    - Add `_IDENTITY_RESPONSE` dict with canned response structure (mensagem, sugestoes, confidence_score, source_reference)
    - Add `_is_identity_question(prompt: str) -> bool` helper that normalizes input (lower + strip) and checks against patterns
    - _Bug_Condition: isBugCondition_Identity(input) where input.prompt matches identity patterns_
    - _Expected_Behavior: Return canned response immediately, zero external API calls_
    - _Preservation: Non-identity queries must NOT match these patterns_
    - _Requirements: 2.1, 2.4_

  - [ ] 3.2 Add module alias map and query normalization helper
    - Add `_MODULE_ALIASES` dict mapping abbreviations to expanded forms: "hcm" → "HCM Gestão de Pessoas Human Capital Management", "bpm" → "BPM Business Process Management gestão processos", "ged" → "GED Gestão Eletrônica de Documentos", "konviva" → "Konviva plataforma educação corporativa LMS", etc.
    - Add `_INFORMAL_MARKERS` set: {"vc", "q ", "pq", "tb", "oq"}
    - Add `_normalizar_query(prompt: str) -> str` helper that:
      - Checks for known abbreviations in `_MODULE_ALIASES` and appends expanded terms
      - Detects informal markers and expands them contextually
      - ALWAYS preserves original query text (additive only, never removes words)
      - Returns original text unchanged if no abbreviations or informal markers found
    - _Bug_Condition: isBugCondition_Normalization(input) where input contains known abbreviations or informal markers_
    - _Expected_Behavior: Normalized text is longer, contains expanded terms, preserves original words_
    - _Preservation: Formal queries without abbreviations pass through unchanged_
    - _Requirements: 2.2, 2.3_

  - [ ] 3.3 Insert identity short-circuit in `_analisar_sync()`
    - Insert AFTER the cache check (step 1) and BEFORE the RAG search (step 2)
    - Call `_is_identity_question(prompt_usuario)`
    - If true: log interception with `logger.info()`, build response with user_name personalization from session, cache the response, return immediately
    - Ensure response structure matches expected format: mensagem, elemento_id (None), seletor_css (None), sugestoes (non-empty list), confidence_score (1.0), source_reference ("identity_detector")
    - _Bug_Condition: isBugCondition_Identity(input)_
    - _Expected_Behavior: Short-circuit pipeline, zero API calls, instant canned response_
    - _Preservation: Cache check still runs FIRST before identity detection_
    - _Requirements: 2.1, 2.4, 3.4_

  - [ ] 3.4 Insert query normalization in `_analisar_sync()`
    - Insert AFTER identity check and BEFORE `buscar_contexto_multi_namespace()` call
    - Call `_normalizar_query(texto_busca_rag)` to expand abbreviations and add context keywords
    - Pass the normalized text to `buscar_contexto_multi_namespace()` instead of raw `texto_busca_rag`
    - Log when normalization modifies the query: `logger.info(f"Query normalizada: {original} → {normalized}")`
    - Ensure pipeline ordering is preserved: cache → identity → normalize → RAG → guardrail → AI Gate → Vision
    - _Bug_Condition: isBugCondition_Normalization(input)_
    - _Expected_Behavior: Normalized text reaches embedding, improving Pinecone retrieval scores_
    - _Preservation: All downstream steps (guardrail, AI Gate, Vision) operate on RAG results as before_
    - _Requirements: 2.2, 2.3, 3.1, 3.2, 3.3, 3.5_

  - [ ] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Identity Short-Circuit & Normalization Active
    - **IMPORTANT**: Re-run the SAME test from task 1 - do NOT write a new test
    - The test from task 1 encodes the expected behavior for both bug conditions
    - When this test passes, it confirms:
      - Identity questions return canned responses without API calls
      - Informal queries are normalized before embedding
    - Run bug condition exploration test from step 1
    - **EXPECTED OUTCOME**: Test PASSES (confirms bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Identity Formal Queries Pipeline Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 - do NOT write new tests
    - Run preservation property tests from step 2
    - **EXPECTED OUTCOME**: Tests PASS (confirms no regressions)
    - Confirm all preservation tests still pass after fix:
      - Formal queries proceed through full pipeline unchanged
      - Cache check remains first operation
      - AI Gate bypass still activates for high-confidence results
      - Non-identity queries mentioning "Aura" or "nome" are NOT short-circuited
      - Normalization returns formal queries unchanged (additive only)

- [ ] 4. Checkpoint - Ensure all tests pass
  - Run full test suite: `pytest tests/test_dap_bug_condition.py tests/test_dap_preservation.py -v`
  - Verify Property 1 (Bug Condition) test PASSES after fix
  - Verify Property 2 (Preservation) tests PASS after fix
  - Verify no other existing tests are broken by the changes
  - Ask the user if questions arise or if manual validation against live Aura DAP is needed

## Task Dependency Graph

```json
{
  "waves": [
    ["1", "2"],
    ["3.1", "3.2"],
    ["3.3", "3.4"],
    ["3.5", "3.6"],
    ["4"]
  ]
}
```

## Notes

- Tasks 1 and 2 are independent and can be written in parallel
- Tasks 3.1 and 3.2 are independent module-level additions
- Task 3.3 depends on 3.1 (identity constants must exist before inserting the short-circuit)
- Task 3.4 depends on 3.2 (normalizer must exist before inserting the normalization step)
- Tasks 3.5 and 3.6 re-run existing tests — do NOT write new tests
- Property-based tests use Hypothesis library (already in project dependencies)
- All mocks should target the actual import paths in `dap_engine.py`
- The identity detector must be placed AFTER cache check to preserve cache-first behavior
- Normalization is additive only — never removes or replaces original query words

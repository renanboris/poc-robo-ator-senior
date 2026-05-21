# Bugfix Requirements Document

## Introduction

The Aura DAP engine (`dap_engine.py`) has two related bugs causing RAG retrieval failures and wasted API calls. Identity/meta questions (e.g., "Quem é vc?", "Qual seu nome?") trigger the full expensive pipeline (OpenAI embedding + 26 Pinecone namespace queries + Gemini Vision) when they should be answered instantly with canned responses. Additionally, informal or short queries (e.g., "O que é o HCM?") fail to retrieve relevant context from Pinecone because the raw query text produces embeddings that don't match well against formally-indexed content, despite the relevant namespace (`gestao_de_pessoas`) being loaded.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the user asks an identity/meta question (e.g., "Quem é vc?", "Qual seu nome?", "O que você faz?") THEN the system triggers the full pipeline: OpenAI embedding generation, Pinecone multi-namespace search across all 26 namespaces, and Gemini Vision API call with screenshot, wasting ~$0.01-0.03 per query in API costs

1.2 WHEN the user asks a short informal query about a known module using abbreviations or colloquial phrasing (e.g., "O que é o HCM?") THEN the system sends the raw query text directly to embedding generation without normalization, producing embeddings that fail to match against formally-indexed content in the relevant namespace (e.g., `gestao_de_pessoas`)

1.3 WHEN the user asks a query with informal/abbreviated phrasing (e.g., "Só quero q vc me fale o que é o Konviva") THEN the system fails to retrieve context that would be found with more formal phrasing, returning no results despite relevant content existing in Pinecone

1.4 WHEN identity/meta questions receive no RAG context (as expected, since no relevant indexed content exists for them) THEN the system falls through to the expensive Gemini Vision API call unnecessarily

### Expected Behavior (Correct)

2.1 WHEN the user asks an identity/meta question (e.g., "Quem é vc?", "Qual seu nome?", "O que você faz?") THEN the system SHALL detect the identity pattern and return an instant canned response WITHOUT calling any external API (no OpenAI embedding, no Pinecone search, no Gemini Vision)

2.2 WHEN the user asks a short informal query about a known module using abbreviations (e.g., "O que é o HCM?") THEN the system SHALL normalize the query by expanding abbreviations and adding context keywords (e.g., "HCM" → "HCM Gestão de Pessoas Human Capital Management") before generating the embedding

2.3 WHEN the user asks a query with informal/abbreviated phrasing (e.g., "Só quero q vc me fale o que é o Konviva") THEN the system SHALL normalize the query to improve embedding similarity, increasing the likelihood of retrieving relevant context from Pinecone

2.4 WHEN a query is identified as an identity/meta question THEN the system SHALL short-circuit the pipeline immediately after detection, returning a response with appropriate personality and suggestions without any downstream API calls

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user asks a navigation question (e.g., "Como acessar o módulo de folha?") THEN the system SHALL CONTINUE TO process through the full RAG + Vision pipeline as before

3.2 WHEN the user asks a detailed technical question with formal phrasing that already matches indexed content well THEN the system SHALL CONTINUE TO retrieve relevant context from Pinecone with the same quality as before

3.3 WHEN the RAG search returns a high-confidence result (score > 0.80 with a direct selector) THEN the system SHALL CONTINUE TO activate the AI Gate bypass and return the result without calling Gemini Vision

3.4 WHEN the cache contains a valid response for the query THEN the system SHALL CONTINUE TO serve the cached response before any other processing

3.5 WHEN the user asks a conceptual question that is NOT an identity/meta question (e.g., "O que é folha de pagamento?") THEN the system SHALL CONTINUE TO process through the RAG pipeline normally (not short-circuited as identity)

---

## Bug Condition (Formal Specification)

### Bug Condition 1: Identity/Meta Questions Waste API Calls

```pascal
FUNCTION isBugCondition_Identity(X)
  INPUT: X of type UserQuery
  OUTPUT: boolean
  
  // Returns true when the query is an identity/meta question about Aura itself
  RETURN X.prompt matches identity patterns ("quem é vc", "qual seu nome", "o que vc faz", etc.)
END FUNCTION
```

```pascal
// Property: Fix Checking - Identity Short-Circuit
FOR ALL X WHERE isBugCondition_Identity(X) DO
  result ← _analisar_sync'(X)
  ASSERT no_external_api_calls(result) AND result.mensagem contains identity_response AND result.sugestoes is not empty
END FOR
```

```pascal
// Property: Preservation Checking - Non-Identity Queries
FOR ALL X WHERE NOT isBugCondition_Identity(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

### Bug Condition 2: Informal/Short Queries Fail Retrieval

```pascal
FUNCTION isBugCondition_Normalization(X)
  INPUT: X of type UserQuery
  OUTPUT: boolean
  
  // Returns true when the query contains abbreviations or informal phrasing
  // that would benefit from normalization before embedding
  RETURN X.prompt contains known_abbreviations OR X.prompt.length < threshold OR X.prompt contains informal_markers
END FUNCTION
```

```pascal
// Property: Fix Checking - Query Normalization Improves Retrieval
FOR ALL X WHERE isBugCondition_Normalization(X) DO
  normalized ← normalize_query(X.prompt)
  ASSERT normalized contains expanded_terms AND len(normalized) >= len(X.prompt)
END FOR
```

```pascal
// Property: Preservation Checking - Formal Queries Unchanged
FOR ALL X WHERE NOT isBugCondition_Normalization(X) DO
  ASSERT normalize_query(X.prompt) = X.prompt
END FOR
```

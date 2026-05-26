# Aura GPS & Feedback Bugs — Bugfix Design

## Overview

Este documento cobre o design de correção para três bugs identificados na extensão Aura DAP após a reestruturação modular (`aura-dap-restructure`):

- **Bug 1** — Race condition em `_avancarPasso` (`aura_gps_engine.js`): o evento que validou o passo N ainda está propagando quando o listener do passo N+1 é registrado, fazendo o GPS travar no passo 1.
- **Bug 2** — AI Gate em `_analisar_sync` (`dap_engine.py`): o bloco de GPS enrichment só existe no caminho do Gemini Vision; o caminho de alta confiança (`resultado_rapido`) retorna sem `gps_passos`.
- **Bug 3** — Feedback negativo em `aura_feedback.js` / `bridge.js` / `app.py`: o dislike é salvo apenas no `localStorage`; nenhuma chamada chega ao backend para marcar ou remover o vetor no Pinecone.

A estratégia de correção é **mínima e local**: nenhum redesign de arquitetura, sem flags globais, sem timestamps adicionais. Cada fix é contido no menor escopo possível.

---

## Glossary

- **Bug_Condition (C)**: Condição que ativa o bug — entrada ou estado que produz comportamento incorreto.
- **Property (P)**: Comportamento correto esperado quando C(X) é verdadeiro.
- **Preservation**: Comportamento existente que não deve ser alterado pela correção.
- **`_avancarPasso`**: Função em `aura_gps_engine.js` chamada quando um passo é validado; responsável por limpar o validador atual e iniciar o próximo passo.
- **`_iniciarPasso`**: Função em `aura_gps_engine.js` que registra o validador do passo N via `_registrarValidador`.
- **`_validadorClick`**: Função em `aura_gps_engine.js` que, quando `target_selector` está vazio ou não encontra elemento, registra um listener de delegação no `document`.
- **`_analisar_sync`**: Função síncrona em `dap_engine.py` que executa o pipeline RAG + AI Gate + Gemini Vision.
- **AI Gate**: Bloco em `_analisar_sync` que retorna `resultado_rapido` quando `score > 0.80` e `seletor_direto` está presente, bypassando o Gemini Vision.
- **GPS enrichment**: Bloco try/except em `_analisar_sync` que busca roteiro no índice e adiciona `gps_passos` à resposta.
- **`_enriquecer_com_gps`**: Função auxiliar a ser extraída do bloco de GPS enrichment — idempotente, sem exceção propagada.
- **`_registrar`**: Closure interna em `aura_feedback.js` que persiste o feedback no `localStorage` e remove a barra visualmente.
- **`AURA_FEEDBACK_EVENT`**: Novo tipo de `postMessage` a ser emitido pelo `aura_feedback.js` no caminho do dislike.
- **`feedback_event`**: Nova `action` a ser tratada pelo `background.js` para encaminhar o dislike ao backend.
- **`/api/feedback`**: Novo endpoint FastAPI em `app.py` que recebe o dislike, marca/remove o vetor no Pinecone e invalida o cache SQLite.

---

## Bug Details

### Bug 1 — GPS para no primeiro passo

#### Bug Condition

O bug ocorre quando `_avancarPasso` é chamado a partir de um handler de evento (click) que ainda está propagando na árvore DOM. O `_cleanupValidator` remove o listener do passo N, mas `_iniciarPasso(N+1)` é chamado **no mesmo tick de execução**. Se o passo N+1 usa delegação no `document` (porque `target_selector` está vazio ou o elemento não foi encontrado), o novo listener captura o evento original ainda em propagação e valida o passo N+1 imediatamente — sem ação real do usuário.

**Formal Specification:**
```
FUNCTION isBugCondition_GPS(step, calledFrom)
  INPUT: step de tipo StepModel, calledFrom de tipo string ("init" | "avancarPasso")
  OUTPUT: boolean

  // Bug ocorre quando:
  // (a) _iniciarPasso é chamado a partir de _avancarPasso (não de init)
  // (b) o passo usa delegação no document (target_selector vazio ou elemento ausente)
  RETURN calledFrom = "avancarPasso"
         AND (step.target_selector = ""
              OR AuraSpotlight.encontrarElemento(step.target_selector) = null)
END FUNCTION
```

#### Examples

- **Caso típico**: Passo 1 tem `target_selector: ""` (delegação). Usuário clica em qualquer elemento. O clique valida o passo 1 via `_onValidado()` → `_avancarPasso()`. No mesmo tick, `_iniciarPasso(1)` registra listener no `document`. O evento de clique ainda está em bubbling e é capturado pelo novo listener → passo 2 validado sem ação real. GPS trava visualmente no passo 1 (painel não atualiza para passo 2).
- **Caso com seletor válido**: Passo 1 tem `target_selector: "#btn-salvar"` e o elemento existe. O listener é registrado diretamente no elemento, não no `document`. O evento não propaga para o `document` após o `removeEventListener`. Sem bug.
- **Caso init**: `_iniciarPasso(0)` chamado de `init()`. Não há evento em propagação. Sem bug.
- **Caso branch_id**: `_avancarPasso` com `branch_id` já usa `setTimeout(fn, 0)` para diferir. Sem bug nesse caminho.

---

### Bug 2 — AI Gate suprime sugestão de GPS

#### Bug Condition

O bloco de GPS enrichment existe apenas no caminho do Gemini Vision (seção 5 de `_analisar_sync`). O caminho do AI Gate (seção 4) retorna `resultado_rapido` diretamente, sem executar o enrichment.

**Formal Specification:**
```
FUNCTION isBugCondition_AIGate(busca_rag)
  INPUT: busca_rag de tipo dict | None
  OUTPUT: boolean

  RETURN busca_rag != None
         AND busca_rag["score"] > 0.80
         AND busca_rag["seletor_direto"] != None
END FUNCTION
```

#### Examples

- **Caso bug**: Score = 0.92, `seletor_direto = "#btn-sign"`. AI Gate ativa, retorna `resultado_rapido` sem `gps_passos`. Frontend não exibe botão "Me guie até lá".
- **Caso sem bug (score baixo)**: Score = 0.65. AI Gate não ativa. Gemini Vision executa, GPS enrichment é executado, `gps_passos` pode ser adicionado.
- **Caso sem roteiro GPS**: Score = 0.92, AI Gate ativa, GPS enrichment executado mas `gps_results` vazio. `gps_passos` não adicionado — comportamento correto.

---

### Bug 3 — Feedback negativo não remove entrada da base de conhecimento

#### Bug Condition

A função `_registrar` em `aura_feedback.js` salva no `localStorage` e remove a barra visualmente, mas não emite `postMessage` para o bridge. Sem mensagem no bridge, nenhuma chamada chega ao `background.js` e nenhuma requisição é feita ao backend.

**Formal Specification:**
```
FUNCTION isBugCondition_Feedback(tipo)
  INPUT: tipo de tipo string ("like" | "dislike")
  OUTPUT: boolean

  RETURN tipo = "dislike"
END FUNCTION
```

#### Examples

- **Caso bug**: Usuário clica 👎. `_registrar("dislike", btn)` salva no `localStorage`. Nenhum `postMessage` emitido. Vetor no Pinecone permanece intacto. Próxima consulta idêntica retorna a mesma resposta ruim.
- **Caso like (preservado)**: Usuário clica 👍. `_registrar("like", btn)` salva no `localStorage`. Comportamento atual mantido — likes não enviam chamada ao backend.
- **Caso backend indisponível**: Dislike emitido via `postMessage`, background tenta POST `/api/feedback`, falha. `localStorage` já foi salvo. UI não é bloqueada.

---

## Expected Behavior

### Preservation Requirements

**Bug 1 — Comportamentos inalterados:**
- Quando `target_selector` é válido e o elemento está presente no DOM, o listener é registrado diretamente no elemento (sem delegação) — sem alteração.
- Quando `_iniciarPasso(0)` é chamado de `init()`, nenhum `setTimeout` é introduzido — o passo 0 inicia imediatamente.
- Quando o passo tem `branch_id`, o `setTimeout(fn, 0)` já existente em `_avancarPasso` é preservado sem modificação.
- Todos os `validation_type` diferentes de `click` (`type`, `enter`, `url_change`, `element_present`, `element_absent`) continuam funcionando sem regressão.
- O abandono explícito do GPS continua emitindo `gps:abandoned` e retornando para modo `assist`.

**Bug 2 — Comportamentos inalterados:**
- Quando `score <= 0.80` ou `seletor_direto` é `None`, o caminho do Gemini Vision executa sem alteração.
- Quando o AI Gate ativa mas não há roteiro GPS disponível, `resultado_rapido` é retornado sem o campo `gps_passos` — sem degradação.
- A latência do caminho de alta confiança não deve ser degradada além do tempo de lookup do roteiro (operação já existente no caminho Vision).
- O frontend continua apresentando CTA explícito ao usuário — GPS não inicia automaticamente (conforme Requirement 2.2 do spec de referência).

**Bug 3 — Comportamentos inalterados:**
- Quando o usuário clica 👍, apenas o `localStorage` é atualizado e a barra é removida — nenhuma chamada ao backend (comportamento atual preservado).
- A barra de feedback é removida visualmente independentemente do resultado da chamada ao backend.
- O `localStorage` continua sendo salvo como fallback mesmo quando o backend não está disponível.
- Quando o cache SQLite não contém entrada correspondente ao prompt do dislike, o endpoint continua marcando/removendo o vetor no Pinecone normalmente.

**Scope — Bug 1:**
Apenas o caminho `_avancarPasso → _iniciarPasso` quando o próximo passo usa delegação no `document` é afetado. Nenhuma outra chamada a `_iniciarPasso` é modificada.

**Scope — Bug 2:**
Apenas o bloco de retorno do AI Gate em `_analisar_sync` é afetado. A função `_enriquecer_com_gps` é uma extração do bloco existente — sem nova lógica.

**Scope — Bug 3:**
Apenas o caminho `tipo === "dislike"` em `_registrar` é afetado. O caminho `tipo === "like"` não é modificado.

---

## Hypothesized Root Cause

### Bug 1 — Race condition no validador de delegação

1. **Event bubbling não termina antes do próximo listener ser registrado**: O evento `click` que disparou `_onValidado()` ainda está percorrendo a árvore DOM quando `_avancarPasso()` chama `_iniciarPasso(proximo)` no mesmo tick síncrono. O `document.addEventListener` registrado em `_validadorClick` captura esse mesmo evento.

2. **`_cleanupValidator` remove o listener do passo N, mas não isola o evento**: O `removeEventListener` do passo N é chamado corretamente, mas o evento já passou pelo ponto de captura do passo N. O novo listener do passo N+1 é adicionado antes que o bubbling termine.

3. **O caminho `branch_id` já tem a solução**: Em `_avancarPasso`, quando `step.branch_id` existe, o código usa `setTimeout(fn, 0)` para diferir `_iniciarPasso`. Esse padrão correto não foi aplicado ao caminho sem `branch_id` quando o próximo passo usa delegação.

4. **`init()` não tem o problema**: Quando `_iniciarPasso(0)` é chamado de `init()`, não há evento em propagação. O `setTimeout` não é necessário nesse caminho.

### Bug 2 — Bloco de GPS enrichment não extraído como função reutilizável

1. **Código duplicado por omissão**: O GPS enrichment foi adicionado ao caminho do Gemini Vision (seção 5) mas não ao caminho do AI Gate (seção 4). A ausência de uma função auxiliar compartilhada tornou fácil esquecer o segundo caminho.

2. **AI Gate retorna antes do enrichment**: O `return resultado_rapido` na seção 4 ocorre antes de qualquer tentativa de buscar roteiro GPS. O bloco try/except de enrichment está fisicamente após o `return`.

3. **Respostas de alta confiança são as mais beneficiadas**: Exatamente quando o score é alto (> 0.80) e há seletor direto, o usuário provavelmente está em uma tela onde o GPS seria mais útil — pois o sistema já sabe qual roteiro é relevante.

### Bug 3 — Feedback negativo sem propagação ao backend

1. **`_registrar` foi projetado apenas para persistência local**: A implementação original salva no `localStorage` e remove a barra. Não havia contrato de comunicação com o backend para feedback.

2. **Ausência de handler `feedback_event` no `background.js`**: O `background.js` não tem case para `action: 'feedback_event'`, então mesmo que o bridge enviasse a mensagem, ela seria descartada com `{ error: 'unknown_action' }`.

3. **Ausência de endpoint `/api/feedback` no backend**: O `app.py` não tem rota para receber feedback de qualidade. Sem endpoint, não há como marcar vetores no Pinecone nem invalidar o cache SQLite.

4. **Pinecone e cache SQLite permanecem intactos**: Sem a cadeia completa (frontend → bridge → background → backend → Pinecone/SQLite), respostas ruins continuam sendo servidas indefinidamente.

---

## Correctness Properties

Property 1: Bug Condition — GPS não valida passo N+1 com evento do passo N

_For any_ passo onde `isBugCondition_GPS(step, "avancarPasso")` é verdadeiro (target_selector vazio ou elemento ausente, chamado de `_avancarPasso`), o `_iniciarPasso` corrigido SHALL registrar o listener de delegação somente após o término da propagação do evento corrente, garantindo que `passo_validado_sem_acao_real = false`.

**Validates: Requirements 2.1, 2.2, 2.3**

---

Property 2: Preservation — GPS com seletor válido não é afetado

_For any_ passo onde `isBugCondition_GPS(step, calledFrom)` é falso (target_selector válido e elemento presente, ou chamado de `init`), o `_iniciarPasso` corrigido SHALL produzir exatamente o mesmo comportamento que o original — sem `setTimeout` introduzido, sem regressão nos validadores.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

---

Property 3: Bug Condition — AI Gate inclui GPS enrichment

_For any_ `busca_rag` onde `isBugCondition_AIGate(busca_rag)` é verdadeiro (score > 0.80 e seletor_direto presente), o `_analisar_sync` corrigido SHALL executar `_enriquecer_com_gps` antes de retornar, adicionando `gps_passos` à resposta quando um roteiro relevante for encontrado.

**Validates: Requirements 2.4, 2.5**

---

Property 4: Preservation — Caminho Gemini Vision não é alterado

_For any_ `busca_rag` onde `isBugCondition_AIGate(busca_rag)` é falso (score <= 0.80 ou seletor_direto ausente), o `_analisar_sync` corrigido SHALL produzir exatamente o mesmo resultado que o original — sem alteração no caminho do Gemini Vision.

**Validates: Requirements 3.5, 3.6, 3.7**

---

Property 5: Bug Condition — Dislike propaga ao backend

_For any_ feedback onde `isBugCondition_Feedback(feedback.tipo)` é verdadeiro (tipo = "dislike"), o `_registrar` corrigido SHALL emitir `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` e payload `{ tipo, prompt, url, ts }`, resultando em chamada POST ao endpoint `/api/feedback` no backend.

**Validates: Requirements 2.6, 2.7, 2.8**

---

Property 6: Preservation — Like não envia chamada ao backend

_For any_ feedback onde `isBugCondition_Feedback(feedback.tipo)` é falso (tipo = "like"), o `_registrar` corrigido SHALL produzir exatamente o mesmo comportamento que o original — apenas `localStorage` atualizado, sem `postMessage` emitido.

**Validates: Requirements 3.8, 3.9, 3.10**

---

## Fix Implementation

### Bug 1 — `aura_gps_engine.js`: diferir `_iniciarPasso` em `_avancarPasso`

**Arquivo**: `extension/modules/aura_gps_engine.js`

**Função**: `_avancarPasso`

**Mudança específica**: No caminho sem `branch_id`, substituir a chamada direta a `_iniciarPasso(proximo)` por `setTimeout(function() { _iniciarPasso(proximo); }, 0)` — mas **somente** quando o próximo passo usa delegação no `document`.

**Raciocínio**: `setTimeout(fn, 0)` adia a execução para após o término do event loop corrente, garantindo que o bubbling do evento que validou o passo N termine antes de o listener do passo N+1 ser registrado. A verificação antecipada de delegação (antes do `setTimeout`) evita o overhead do timer quando não é necessário.

**Specific Changes**:

1. **Adicionar função auxiliar `_usaDelegacao(step)`**: Verifica se o próximo passo usará delegação no `document` — retorna `true` se `target_selector` está vazio ou se `AuraSpotlight.encontrarElemento` retorna `null`.

2. **Modificar o caminho sem `branch_id` em `_avancarPasso`**: Envolver `_iniciarPasso(proximo)` em `setTimeout(fn, 0)` quando `_usaDelegacao(_passos[proximo])` for verdadeiro.

3. **Não modificar o caminho `init → _iniciarPasso(0)`**: `init()` chama `_iniciarPasso(0)` diretamente — sem evento em propagação, sem necessidade de `setTimeout`.

4. **Não modificar o caminho `branch_id`**: Já usa `setTimeout(fn, 0)` — preservado sem alteração.

```javascript
// Função auxiliar a adicionar (antes de _avancarPasso)
function _usaDelegacao(step) {
  if (!step || !step.target_selector) return true;
  var match = global.AuraSpotlight
    ? global.AuraSpotlight.encontrarElemento(step.target_selector)
    : null;
  return !match || !match.elemento;
}

// Trecho modificado em _avancarPasso (caminho sem branch_id):
// ANTES:
if (proximo >= _passos.length) {
  _concluir();
} else {
  _iniciarPasso(proximo);
}

// DEPOIS:
if (proximo >= _passos.length) {
  _concluir();
} else if (_usaDelegacao(_passos[proximo])) {
  setTimeout(function () { _iniciarPasso(proximo); }, 0);
} else {
  _iniciarPasso(proximo);
}
```

---

### Bug 2 — `dap_engine.py`: extrair `_enriquecer_com_gps` e chamar em ambos os caminhos

**Arquivo**: `dap_engine.py`

**Função**: `_analisar_sync`

**Mudança específica**: Extrair o bloco try/except de GPS enrichment para uma função auxiliar `_enriquecer_com_gps(resultado, prompt_usuario, tenant_id)` e chamá-la tanto antes do `return resultado_rapido` (AI Gate) quanto antes do `return resultado_final` (Gemini Vision).

**Specific Changes**:

1. **Extrair função `_enriquecer_com_gps`**: Move o bloco try/except existente para uma função de módulo. A função é idempotente (não modifica `resultado` se `gps_passos` já existe), não propaga exceção (try/except interno), e retorna o dict modificado in-place.

2. **Chamar antes do `return resultado_rapido`** no bloco AI Gate (seção 4).

3. **Substituir o bloco inline** no caminho Gemini Vision (seção 5) pela chamada à função extraída.

```python
# Nova função auxiliar (adicionar antes de _analisar_sync)
def _enriquecer_com_gps(resultado: dict, prompt_usuario: str, tenant_id: str) -> dict:
    """Busca roteiro GPS relevante e adiciona gps_passos ao resultado.
    
    Idempotente: não modifica resultado se gps_passos já existe.
    Não propaga exceção: falhas são logadas em DEBUG e ignoradas.
    """
    if "gps_passos" in resultado:
        return resultado
    try:
        fallback_engine = get_navigation_fallback_engine()
        if fallback_engine:
            gps_results = fallback_engine.indexer.search(prompt_usuario, tenant_id, top_k=1)
            if gps_results:
                from pathlib import Path as _Path
                roteiro_name = gps_results[0]["roteiro_name"]
                roteiro_path = _Path("roteiros_salvos") / f"{roteiro_name}.json"
                if roteiro_path.exists():
                    with open(roteiro_path, 'r', encoding='utf-8') as f:
                        roteiro_data = json.load(f)
                    nav_path = fallback_engine.path_extractor.extract_navigation_path(
                        roteiro_data, target_query=prompt_usuario
                    )
                    if nav_path and nav_path.get("steps") and len(nav_path["steps"]) >= 2:
                        resultado["gps_passos"] = nav_path["steps"]
                        resultado["gps_nome_aula"] = roteiro_name
                        logger.info(
                            f"🧭 GPS enrichment: {len(nav_path['steps'])} passos do roteiro "
                            f"'{roteiro_name}' anexados à resposta"
                        )
    except Exception as e:
        logger.debug(f"GPS enrichment skipped: {e}")
    return resultado

# No bloco AI Gate (seção 4), antes do return:
# ANTES:
_cache_set(cache_key, resultado_rapido)
return resultado_rapido

# DEPOIS:
_enriquecer_com_gps(resultado_rapido, prompt_usuario, tenant_id)
_cache_set(cache_key, resultado_rapido)
return resultado_rapido

# No caminho Gemini Vision (seção 5), substituir o bloco try/except inline:
# ANTES: bloco try/except de GPS enrichment inline
# DEPOIS:
_enriquecer_com_gps(resultado_final, prompt_usuario, tenant_id)
```

---

### Bug 3 — Três camadas: `aura_feedback.js`, `bridge.js`, `background.js`, `app.py`

#### Camada 1: `extension/modules/aura_feedback.js`

**Mudança**: No caminho `tipo === "dislike"` da closure `_registrar`, adicionar `window.postMessage` após o `localStorage.setItem`.

```javascript
// DEPOIS (apenas no caminho dislike):
const _registrar = (tipo, btn) => {
    like.disabled = dislike.disabled = true;
    btn.classList.add(tipo === 'like' ? 'voted-yes' : 'voted-no');
    const payload = {
        tipo,
        prompt: (prompt || '').substring(0, 100),
        url: window.location.href,
        ts: Date.now()
    };
    try {
        const key = `aura_fb_${Date.now()}`;
        localStorage.setItem(key, JSON.stringify(payload));
    } catch (e) {}
    // NOVO: propaga dislike ao backend via bridge
    if (tipo === 'dislike') {
        try {
            window.postMessage(
                { type: 'AURA_FEEDBACK_EVENT', payload },
                window.location.origin
            );
        } catch (e) {}
    }
    setTimeout(() => { bar.style.opacity = '0'; }, 350);
    setTimeout(() => { bar.remove(); }, 850);
};
```

#### Camada 2: `extension/bridge.js`

**Mudança**: Adicionar handler para `AURA_FEEDBACK_EVENT` seguindo o padrão existente de `AURA_ANALYTICS_EVENT`.

```javascript
// Adicionar após o handler AURA_ANALYTICS_EVENT:
// 🟢 PONTE PARA FEEDBACK EVENTS
if (event.data.type === "AURA_FEEDBACK_EVENT") {
    chrome.runtime.sendMessage(
        { action: "feedback_event", payload: event.data.payload },
        () => {
            const err = chrome.runtime.lastError;
            if (err) console.warn("Aura Bridge: Falha ao enviar feedback_event:", err.message);
        }
    );
    return;
}
```

#### Camada 3: `extension/background.js`

**Mudança 1**: Adicionar `feedback` a `AURA_ENDPOINTS`.

```javascript
const AURA_ENDPOINTS = Object.freeze({
  analyze:   _cfgEndpoints.analyze   || 'http://localhost:8000/analyze',
  missions:  _cfgEndpoints.missions  || 'http://localhost:8000/api/missoes',
  gps:       _cfgEndpoints.gps       || 'http://localhost:8000/api/gps-roteiro',
  analytics: _cfgEndpoints.analytics || 'http://localhost:8000/api/analytics/extensao',
  feedback:  _cfgEndpoints.feedback  || 'http://localhost:8000/api/feedback'  // NOVO
});
```

**Mudança 2**: Adicionar handler `feedback_event` no `chrome.runtime.onMessage.addListener`.

```javascript
if (request.action === 'feedback_event') {
    fetch(AURA_ENDPOINTS.feedback, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + AURA_AUTH_TOKEN
        },
        body: JSON.stringify(request.payload || {})
    })
    .then(r => r.json())
    .then(data => sendResponse({ ok: true, data }))
    .catch(err => sendResponse({ ok: false, reason: err.message }));
    return true;
}
```

#### Camada 4: `app.py`

**Mudança**: Adicionar modelo Pydantic `FeedbackEventReq` e endpoint `POST /api/feedback`.

```python
class FeedbackEventReq(BaseModel):
    tipo: str          # "like" | "dislike"
    prompt: str
    url: str
    ts: int            # timestamp ms

@app.post("/api/feedback")
async def registrar_feedback(payload: FeedbackEventReq, request: Request):
    """Recebe feedback de qualidade da extensão Aura.
    
    Para dislikes:
    - Busca o vetor no Pinecone pelo embedding do prompt
    - Marca com metadata feedback='negative' ou deleta
    - Invalida a entrada correspondente no cache SQLite
    """
    if payload.tipo != "dislike":
        return {"ok": True, "action": "noop"}  # likes não afetam o backend
    
    try:
        resultado = await asyncio.to_thread(
            dap_engine.processar_feedback_negativo,
            payload.prompt,
            payload.url,
            payload.ts
        )
        return {"ok": True, "action": resultado.get("action", "unknown")}
    except Exception as e:
        logging.error(f"[feedback] Erro ao processar dislike: {e}")
        return {"ok": False, "reason": str(e)}
```

**Mudança adicional em `dap_engine.py`**: Adicionar função `processar_feedback_negativo`.

```python
def processar_feedback_negativo(prompt: str, url: str, ts: int) -> dict:
    """Marca ou remove o vetor Pinecone correspondente ao prompt e invalida o cache SQLite.
    
    Estratégia: marca com metadata feedback='negative' (não deleta imediatamente,
    preserva auditoria). O score threshold do RAG pode ser ajustado para ignorar
    vetores marcados em iteração futura.
    """
    if not pinecone_index or not client_openai:
        return {"action": "skipped", "reason": "engines_unavailable"}
    
    try:
        # 1. Gera embedding do prompt para busca
        embedding = gerar_embedding(prompt)
        
        # 2. Busca o vetor mais próximo no Pinecone (namespace senior_default)
        resultados = pinecone_index.query(
            vector=embedding, top_k=1,
            namespace="senior_default",
            include_metadata=True
        )
        
        if not resultados.matches or resultados.matches[0].score < SCORE_THRESHOLD:
            return {"action": "not_found"}
        
        melhor = resultados.matches[0]
        
        # 3. Marca com metadata feedback='negative'
        pinecone_index.update(
            id=melhor.id,
            namespace="senior_default",
            set_metadata={"feedback": "negative", "feedback_ts": ts}
        )
        
        # 4. Invalida entrada no cache SQLite
        import hashlib
        # Invalida todas as entradas de cache que contenham este prompt
        with _cache_lock:
            with sqlite3.connect(_DB_CACHE_FILE) as conn:
                conn.execute(
                    "DELETE FROM dap_cache WHERE cache_key LIKE ?",
                    (f"%{prompt[:50]}%",)
                )
                conn.commit()
        
        logger.info(f"[feedback] Vetor '{melhor.id}' marcado como negative (score={melhor.score:.3f})")
        return {"action": "marked_negative", "vector_id": melhor.id}
    
    except Exception as e:
        logger.error(f"[feedback] Erro ao processar feedback negativo: {e}")
        return {"action": "error", "reason": str(e)}
```

---

## Testing Strategy

### Validation Approach

A estratégia segue duas fases para cada bug: primeiro, executar testes no código **não corrigido** para confirmar o bug e o root cause (exploratory); depois, verificar que a correção funciona (fix checking) e que comportamentos existentes não regridem (preservation checking).

---

### Bug 1 — Exploratory Bug Condition Checking

**Goal**: Confirmar que o listener do passo N+1 captura o evento do passo N quando ambos usam delegação no `document`.

**Test Plan**: Criar um roteiro com dois passos de `target_selector: ""`. Simular um clique via `dispatchEvent`. Observar se o passo 2 é validado imediatamente sem segundo clique.

**Test Cases**:
1. **Dois passos com delegação**: Roteiro `[{target_selector: ""}, {target_selector: ""}]`. Disparar um `click` no `document`. Verificar se `_stepIndex` avança para 2 sem segundo clique. (Falha no código não corrigido.)
2. **Passo 1 com seletor, passo 2 com delegação**: Roteiro `[{target_selector: "#btn"}, {target_selector: ""}]`. Clicar em `#btn`. Verificar se passo 2 é validado imediatamente. (Pode falhar dependendo do bubbling.)
3. **Dois passos com seletor válido**: Roteiro `[{target_selector: "#btn1"}, {target_selector: "#btn2"}]`. Clicar em `#btn1`. Verificar que passo 2 aguarda clique em `#btn2`. (Não falha — confirma que o bug é específico à delegação.)

**Expected Counterexamples**:
- `_stepIndex === 2` após um único clique quando ambos os passos usam delegação.
- Causa confirmada: listener do passo N+1 registrado antes do fim do bubbling do evento do passo N.

### Bug 1 — Fix Checking

**Goal**: Verificar que após a correção, o passo N+1 aguarda ação real do usuário.

**Pseudocode:**
```
FOR ALL step WHERE isBugCondition_GPS(step, "avancarPasso") DO
  result ← _iniciarPasso_fixed(nextIndex)
  ASSERT _stepIndex = nextIndex  // painel atualizado
  ASSERT passo_validado_sem_acao_real = false  // listener não disparou sozinho
END FOR
```

### Bug 1 — Preservation Checking

**Goal**: Verificar que passos com seletor válido continuam funcionando sem `setTimeout`.

**Pseudocode:**
```
FOR ALL step WHERE NOT isBugCondition_GPS(step, calledFrom) DO
  ASSERT _iniciarPasso_original(step) = _iniciarPasso_fixed(step)
  // Sem setTimeout introduzido, sem regressão
END FOR
```

**Test Cases**:
1. **Seletor válido**: Verificar que `_iniciarPasso` não usa `setTimeout` quando elemento existe no DOM.
2. **Chamada de `init`**: Verificar que `_iniciarPasso(0)` de `init()` não usa `setTimeout`.
3. **`validation_type: type`**: Verificar que validador de input continua funcionando.
4. **`validation_type: url_change`**: Verificar que MutationObserver continua funcionando.

---

### Bug 2 — Exploratory Bug Condition Checking

**Goal**: Confirmar que `resultado_rapido` não contém `gps_passos` quando AI Gate ativa.

**Test Plan**: Mockar `buscar_contexto_multi_namespace` para retornar `score=0.92` e `seletor_direto="#btn"`. Chamar `_analisar_sync`. Verificar ausência de `gps_passos` no resultado.

**Test Cases**:
1. **AI Gate ativo, roteiro disponível**: Score=0.92, seletor presente, roteiro GPS indexado. Verificar que `gps_passos` está ausente no resultado. (Falha no código não corrigido.)
2. **AI Gate inativo**: Score=0.65. Verificar que `gps_passos` pode estar presente (caminho Vision). (Não falha.)

**Expected Counterexamples**:
- `"gps_passos" not in resultado` quando AI Gate ativa e roteiro GPS existe.

### Bug 2 — Fix Checking

**Pseudocode:**
```
FOR ALL busca_rag WHERE isBugCondition_AIGate(busca_rag) DO
  result ← _analisar_sync_fixed(busca_rag)
  ASSERT "gps_passos" IN result OR gps_enrichment_executado = true
END FOR
```

### Bug 2 — Preservation Checking

**Pseudocode:**
```
FOR ALL busca_rag WHERE NOT isBugCondition_AIGate(busca_rag) DO
  ASSERT _analisar_sync_original(busca_rag) = _analisar_sync_fixed(busca_rag)
END FOR
```

**Test Cases**:
1. **Score baixo**: Verificar que caminho Vision não é alterado.
2. **Sem seletor_direto**: Verificar que caminho Vision não é alterado.
3. **AI Gate ativo, sem roteiro GPS**: Verificar que `resultado_rapido` retorna sem `gps_passos` (comportamento correto).
4. **`_enriquecer_com_gps` idempotente**: Chamar duas vezes com mesmo resultado — verificar que `gps_passos` não é duplicado.

---

### Bug 3 — Exploratory Bug Condition Checking

**Goal**: Confirmar que nenhum `postMessage` é emitido ao clicar 👎 no código não corrigido.

**Test Plan**: Usar Playwright para carregar `aura_feedback.js`, clicar no botão dislike, e interceptar `window.postMessage`. Verificar ausência de `AURA_FEEDBACK_EVENT`.

**Test Cases**:
1. **Clique em dislike**: Verificar que nenhum `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` é emitido. (Falha no código não corrigido — confirma o bug.)
2. **Clique em like**: Verificar que nenhum `postMessage` é emitido. (Não falha — comportamento correto preservado.)
3. **`localStorage` salvo**: Verificar que `localStorage` contém a entrada após dislike. (Não falha — comportamento existente.)

**Expected Counterexamples**:
- Nenhum `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` após clique em dislike.

### Bug 3 — Fix Checking

**Pseudocode:**
```
FOR ALL feedback WHERE isBugCondition_Feedback(feedback.tipo) DO
  result ← _registrar_fixed(feedback.tipo, feedback.btn)
  ASSERT postMessageEmitido = true
         AND type = "AURA_FEEDBACK_EVENT"
         AND backendChamado = true
         AND localStorageSalvo = true
END FOR
```

### Bug 3 — Preservation Checking

**Pseudocode:**
```
FOR ALL feedback WHERE NOT isBugCondition_Feedback(feedback.tipo) DO
  ASSERT _registrar_original(feedback.tipo, feedback.btn)
       = _registrar_fixed(feedback.tipo, feedback.btn)
  // Apenas localStorage, sem postMessage
END FOR
```

**Test Cases**:
1. **Like não emite postMessage**: Verificar que clique em 👍 não emite `AURA_FEEDBACK_EVENT`.
2. **Backend indisponível**: Verificar que UI não bloqueia quando `/api/feedback` retorna erro.
3. **Cache SQLite sem entrada**: Verificar que `processar_feedback_negativo` não falha quando não há cache para o prompt.
4. **Pinecone sem match**: Verificar que `processar_feedback_negativo` retorna `{"action": "not_found"}` sem exceção.

---

### Unit Tests

- **Bug 1**: Testar `_usaDelegacao(step)` com seletor vazio, seletor válido, e elemento ausente no DOM.
- **Bug 1**: Testar que `_avancarPasso` usa `setTimeout` apenas quando próximo passo usa delegação.
- **Bug 2**: Testar `_enriquecer_com_gps` com roteiro disponível, sem roteiro, e com `gps_passos` já presente (idempotência).
- **Bug 2**: Testar que AI Gate chama `_enriquecer_com_gps` antes do `return`.
- **Bug 3**: Testar `processar_feedback_negativo` com Pinecone mockado — marcação de metadata e invalidação de cache.
- **Bug 3**: Testar endpoint `POST /api/feedback` com payload `tipo: "like"` (noop) e `tipo: "dislike"`.

### Property-Based Tests

- **Bug 1 (Property 1)**: Gerar roteiros aleatórios com passos de `target_selector` vazio. Para cada par de passos consecutivos, verificar que o segundo passo não é validado sem segundo evento de clique.
- **Bug 1 (Property 2)**: Gerar roteiros com `target_selector` válido. Verificar que o comportamento de validação é idêntico ao original.
- **Bug 2 (Property 3)**: Gerar scores aleatórios > 0.80 com seletor presente. Verificar que `_enriquecer_com_gps` é sempre chamado.
- **Bug 2 (Property 4)**: Gerar scores aleatórios <= 0.80. Verificar que o resultado é idêntico ao original.
- **Bug 3 (Property 5)**: Gerar payloads de dislike aleatórios. Verificar que `postMessage` é sempre emitido com os campos corretos.
- **Bug 3 (Property 6)**: Gerar payloads de like aleatórios. Verificar que nenhum `postMessage` é emitido.

### Integration Tests

- **Bug 1**: Teste end-to-end com roteiro de 3 passos (todos com `target_selector: ""`). Verificar que cada passo requer clique independente.
- **Bug 2**: Teste com backend real (ou mock de alto nível). Verificar que resposta do AI Gate contém `gps_passos` quando roteiro existe.
- **Bug 3**: Teste com Playwright. Clicar 👎, verificar `postMessage` emitido, verificar que background recebe `feedback_event`, verificar que `/api/feedback` é chamado.
- **Bug 3**: Verificar que vetor no Pinecone recebe metadata `feedback: 'negative'` após dislike (teste com Pinecone real ou mock).

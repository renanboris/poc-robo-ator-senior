# Aura Extension Chrome Load Failure — Bugfix Design

## Overview

A extensão Aura DAP falha ao carregar no Chrome porque `content.js` é declarado com `"world": "MAIN"` no manifest, contexto em que `chrome.runtime` é `undefined`. A função `_injectScript` chama `chrome.runtime.getURL(src)` na linha 21, causando um `TypeError` imediato que interrompe todo o carregamento de módulos e torna o assistente inoperante.

A correção é cirúrgica e em dois arquivos:

1. **`extension/content.js`**: modificar `_injectScript` para receber `extensionId` como parâmetro e construir a URL como `chrome-extension://{extensionId}/{src}`, eliminando a dependência de `chrome.runtime`. Refatorar `_carregarModulos` para obter o `extensionId` via `_obterExtensionId()` antes do loop e passá-lo a cada chamada.
2. **`extension/manifest.json`**: adicionar os 8 arquivos de `modules/*.js` em `web_accessible_resources`, pois sem essa declaração o Chrome bloquearia o carregamento mesmo com a URL correta.

O mecanismo de passagem do `extensionId` já existe na arquitetura: `bridge.js` (mundo `ISOLATED`) injeta `chrome.runtime.id` no atributo `data-aura-id` do `document.documentElement`, e `_obterExtensionId()` já lê esse atributo com retry. Nenhuma nova infraestrutura é necessária.

---

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug — `content.js` executa no mundo `MAIN` e chama `chrome.runtime.getURL()` diretamente, onde `chrome.runtime` é `undefined`.
- **Property (P)**: O comportamento correto esperado — `_injectScript` resolve a URL do módulo usando `extensionId` obtido do DOM, sem acessar `chrome.runtime`.
- **Preservation**: Todos os comportamentos existentes que não devem ser alterados pela correção — guardião de login, retry de `_obterExtensionId`, inicialização de `_inicializarAura`, comportamento de `bridge.js` e `shield.js`.
- **`_injectScript(src)`**: Função em `extension/content.js` que cria um elemento `<script>` e o injeta no DOM para carregar módulos da extensão.
- **`_carregarModulos()`**: Função em `extension/content.js` que itera sobre a lista de módulos e chama `_injectScript` sequencialmente.
- **`_obterExtensionId(tentativas)`**: Função em `extension/content.js` que lê `document.documentElement.getAttribute('data-aura-id')` com até 20 tentativas de 100ms cada.
- **`bridge.js`**: Content script declarado com `"world": "ISOLATED"` que tem acesso a `chrome.runtime` e injeta `chrome.runtime.id` no atributo `data-aura-id` do DOM.
- **`web_accessible_resources`**: Seção do `manifest.json` que declara quais arquivos da extensão podem ser referenciados por páginas web externas via URL `chrome-extension://`.
- **Mundo MAIN**: Contexto de execução de content scripts que compartilha o JavaScript da página — sem acesso a `chrome.runtime`.
- **Mundo ISOLATED**: Contexto de execução de content scripts isolado da página — com acesso a `chrome.runtime`.

---

## Bug Details

### Bug Condition

O bug se manifesta quando `content.js` é carregado no mundo `MAIN` e a função `_injectScript` tenta resolver a URL de um módulo chamando `chrome.runtime.getURL(src)`. No mundo `MAIN`, `chrome.runtime` é `undefined`, causando `TypeError: Cannot read properties of undefined (reading 'getURL')` na linha 21 de `content.js`.

**Formal Specification:**

```
FUNCTION isBugCondition(X)
  INPUT: X de tipo ScriptExecutionContext
  OUTPUT: boolean

  RETURN X.world = 'MAIN'
         AND X.calls_chrome_runtime_getURL_directly = true
         AND typeof(chrome.runtime) = 'undefined'
END FUNCTION
```

### Examples

- **Exemplo 1 — Crash imediato no carregamento**: Extensão instalada, usuário acessa `https://*.senior.com.br/*`. `content.js` executa, `_tentarIniciarAura()` detecta login, chama `_carregarModulos()`, que chama `_injectScript('modules/aura_state.js')`. Na linha 21, `chrome.runtime.getURL(...)` lança `TypeError`. **Esperado**: URL resolvida como `chrome-extension://{id}/modules/aura_state.js`. **Atual**: crash.
- **Exemplo 2 — Todos os módulos bloqueados**: Mesmo que o crash fosse contornado, `modules/aura_state.js` não está em `web_accessible_resources`. O Chrome retornaria erro 404 ao tentar carregar o script. **Esperado**: módulo carregado com sucesso. **Atual**: bloqueado pelo manifest.
- **Exemplo 3 — Aura completamente inoperante**: Como nenhum módulo é carregado, `window.AuraUI`, `window.AuraState`, `window.AuraAssistEngine` etc. são `undefined`. Qualquer tentativa de uso resulta em erros secundários. **Esperado**: assistente inicializado e funcional. **Atual**: inoperante.
- **Edge case — `extensionId` ainda não disponível**: `bridge.js` e `content.js` executam em `document_start`. Se `content.js` chamar `_obterExtensionId()` antes de `bridge.js` ter escrito o atributo, o retry de 20×100ms já trata esse caso. Nenhuma mudança necessária aqui.

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- `bridge.js` (mundo `ISOLATED`) SHALL CONTINUE TO injetar `chrome.runtime.id` no atributo `data-aura-id` do `document.documentElement` antes que `content.js` precise dele.
- O guardião de login (`_aguardarLogin`, `_tentarIniciarAura`, `_estaLogado`) SHALL CONTINUE TO aguardar o login antes de inicializar a Aura.
- O flag `_auraInicializada` SHALL CONTINUE TO impedir inicializações duplicadas.
- `_obterExtensionId()` SHALL CONTINUE TO realizar até 20 tentativas com intervalo de 100ms antes de retornar `null`.
- `_inicializarAura(extensionId)` SHALL CONTINUE TO construir a URL do `dotlottie-player` no formato `chrome-extension://{extensionId}/aura.json` — esse trecho já usa `extensionId` corretamente e não deve ser alterado.
- `shield.js` SHALL CONTINUE TO desativar e restaurar o `window.define` do RequireJS conforme seu comportamento atual.
- Todos os handlers de mensagens `window` (`AURA_FETCH_MISSION_RESPONSE`, `AURA_GPS_EXPLICIT_RESPONSE`) SHALL CONTINUE TO funcionar sem alteração.

**Scope:**
Todos os caminhos de execução que **não** envolvem a chamada a `chrome.runtime.getURL()` em `_injectScript` devem ser completamente inalterados por esta correção. Isso inclui:
- Toda a lógica de `bridge.js`
- Toda a lógica de `shield.js`
- O guardião de login e seus observers/timers
- A função `_inicializarAura` e seus handlers de UI
- Os handlers de Magic Link e MutationObserver de SPA

---

## Hypothesized Root Cause

Com base na análise do código real:

1. **Acesso direto a `chrome.runtime` no mundo MAIN** *(causa primária)*: `_injectScript` em `content.js` chama `chrome.runtime.getURL(src)` na linha 21. O manifest declara `content.js` com `"world": "MAIN"`, onde `chrome.runtime` é `undefined`. Não há guard (`if (chrome?.runtime)`) antes da chamada.

2. **Ausência de `modules/*.js` em `web_accessible_resources`** *(causa secundária)*: O manifest atual lista apenas `["aura.json", "aura_config.js", "guided_execution.js", "checklist_widget.js", "hesitation_detector.js", "nps_modal.js"]`. Os 8 arquivos em `modules/` não estão declarados. Mesmo com a URL correta, o Chrome bloquearia o carregamento desses scripts.

3. **`extensionId` já disponível via mecanismo existente** *(não é causa, é a solução)*: `bridge.js` já injeta `chrome.runtime.id` no DOM via `data-aura-id`, e `_obterExtensionId()` já existe em `content.js` para lê-lo. A correção apenas precisa conectar esses dois pontos: passar o `extensionId` para `_injectScript`.

4. **Ordem de execução não é problema**: Ambos `bridge.js` e `content.js` executam em `document_start`. O retry de `_obterExtensionId()` (20×100ms) já absorve qualquer race condition entre os dois scripts.

---

## Correctness Properties

Property 1: Bug Condition — Resolução de URL de Módulo sem `chrome.runtime`

_For any_ chamada a `_injectScript(src, extensionId)` onde `extensionId` é uma string não-vazia obtida via `_obterExtensionId()`, a função corrigida SHALL construir `s.src` como `'chrome-extension://' + extensionId + '/' + src` sem acessar `chrome.runtime`, e o elemento `<script>` SHALL ser injetado no DOM com sucesso.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Comportamentos Não Relacionados ao Bug

_For any_ caminho de execução onde `isBugCondition` NÃO se aplica (bridge.js, shield.js, guardião de login, handlers de UI, Magic Link, MutationObserver), a função corrigida SHALL produzir exatamente o mesmo resultado que o código original, preservando todos os comportamentos existentes.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

---

## Fix Implementation

### Changes Required

#### File 1: `extension/content.js`

**Function**: `_injectScript`

**Change**: Adicionar parâmetro `extensionId` e substituir `chrome.runtime.getURL(src)` por construção manual da URL.

```javascript
// ANTES
function _injectScript(src) {
    return new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = chrome.runtime.getURL(src);  // ← CRASH: chrome.runtime é undefined no mundo MAIN
        s.onload = resolve;
        s.onerror = reject;
        (document.head || document.documentElement).appendChild(s);
    });
}

// DEPOIS
function _injectScript(src, extensionId) {
    return new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = 'chrome-extension://' + extensionId + '/' + src;
        s.onload = resolve;
        s.onerror = reject;
        (document.head || document.documentElement).appendChild(s);
    });
}
```

**Function**: `_carregarModulos`

**Change**: Obter `extensionId` via `_obterExtensionId()` antes do loop e passá-lo a cada chamada de `_injectScript`.

```javascript
// ANTES
async function _carregarModulos() {
    var modulos = [ /* ... */ ];
    for (var i = 0; i < modulos.length; i++) {
        await _injectScript(modulos[i]);
    }
}

// DEPOIS
async function _carregarModulos(extensionId) {
    var modulos = [ /* ... */ ];
    for (var i = 0; i < modulos.length; i++) {
        await _injectScript(modulos[i], extensionId);
    }
}
```

**Call sites de `_carregarModulos`**: As duas chamadas existentes em `_tentarIniciarAura` e no timeout de `_aguardarLogin` já obtêm `extensionId` via `_obterExtensionId()` antes de chamar `_carregarModulos`. Basta passar o `extensionId` já disponível:

```javascript
// ANTES (em ambos os call sites)
_carregarModulos().then(function () { ... })

// DEPOIS
_carregarModulos(extensionId).then(function () { ... })
```

#### File 2: `extension/manifest.json`

**Section**: `web_accessible_resources`

**Change**: Adicionar os 8 arquivos de `modules/` ao array `resources` existente.

```json
// ANTES
"web_accessible_resources": [
    {
        "resources": [
            "aura.json", "aura_config.js", "guided_execution.js",
            "checklist_widget.js", "hesitation_detector.js", "nps_modal.js"
        ],
        "matches": ["https://*.senior.com.br/*"]
    }
]

// DEPOIS
"web_accessible_resources": [
    {
        "resources": [
            "aura.json",
            "aura_config.js",
            "modules/aura_state.js",
            "modules/aura_feedback.js",
            "modules/aura_ui.js",
            "modules/aura_dom_mapper.js",
            "modules/aura_spotlight.js",
            "modules/aura_gps_engine.js",
            "modules/aura_mission_engine.js",
            "modules/aura_assist_engine.js",
            "guided_execution.js",
            "checklist_widget.js",
            "hesitation_detector.js",
            "nps_modal.js"
        ],
        "matches": ["https://*.senior.com.br/*"]
    }
]
```

**Nota**: A ordem dos recursos no array reflete a ordem de carregamento em `_carregarModulos`, facilitando auditoria futura.

---

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não corrigido (exploratory); depois, verificar que a correção funciona e que nenhum comportamento existente foi quebrado (fix + preservation checking).

Como `content.js` é um script de extensão Chrome sem framework de testes nativo, os testes serão escritos com Jest + jsdom para simular o ambiente DOM, mockando `document.createElement` e verificando o atributo `src` do elemento `<script>` criado.

### Exploratory Bug Condition Checking

**Goal**: Confirmar o crash de `chrome.runtime.getURL()` no código original e validar que a causa raiz é exatamente a identificada.

**Test Plan**: Executar `_injectScript('modules/aura_state.js')` no código **não corrigido** em um ambiente onde `chrome.runtime` é `undefined` (simulando o mundo MAIN). Observar o `TypeError`.

**Test Cases**:
1. **Crash com `chrome.runtime` undefined**: Chamar `_injectScript('modules/aura_state.js')` sem definir `chrome.runtime` no ambiente de teste — deve lançar `TypeError: Cannot read properties of undefined (reading 'getURL')` (falha no código original).
2. **Crash para qualquer módulo**: Repetir para `modules/aura_ui.js`, `guided_execution.js` — todos devem falhar da mesma forma (falha no código original).
3. **Verificação do manifest**: Confirmar que `modules/aura_state.js` não está em `web_accessible_resources` no manifest original (falha de configuração confirmada).

**Expected Counterexamples**:
- `TypeError: Cannot read properties of undefined (reading 'getURL')` ao chamar `_injectScript` com `chrome.runtime = undefined`.
- Causa confirmada: acesso direto a `chrome.runtime` sem guard no mundo MAIN.

### Fix Checking

**Goal**: Verificar que para todas as entradas onde a bug condition se aplica, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL src IN modulos DO
  FOR ALL extensionId IN ['abc123', 'xyz789', 'test-id-001'] DO
    result := _injectScript_fixed(src, extensionId)
    ASSERT result.scriptElement.src = 'chrome-extension://' + extensionId + '/' + src
    ASSERT no_crash(result)
  END FOR
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as entradas onde a bug condition NÃO se aplica, o comportamento é idêntico ao original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT behavior_original(X) = behavior_fixed(X)
END FOR
```

**Testing Approach**: Testes de unidade para os caminhos não afetados. Property-based testing é recomendado para `_obterExtensionId` (verificar que o retry funciona para qualquer número de tentativas entre 0 e 20) e para a construção da URL (verificar que qualquer `extensionId` válido produz uma URL bem formada).

**Test Cases**:
1. **Preservação do retry de `_obterExtensionId`**: Simular `data-aura-id` ausente por N iterações (N < 20) e verificar que a função retorna o ID quando ele aparece — comportamento deve ser idêntico antes e depois da correção.
2. **Preservação da URL do dotlottie-player**: Verificar que `_inicializarAura` ainda constrói `chrome-extension://{extensionId}/aura.json` corretamente — esse trecho não é tocado pela correção.
3. **Preservação do guardião de login**: Verificar que `_estaLogado()` retorna `false` em URLs de login e `true` com tokens no storage — sem alteração.
4. **Preservação do flag `_auraInicializada`**: Verificar que chamadas duplicadas a `_tentarIniciarAura` são ignoradas após a primeira inicialização.

### Unit Tests

- Testar `_injectScript(src, extensionId)` com diferentes valores de `src` e `extensionId` — verificar que `s.src` é sempre `chrome-extension://{extensionId}/{src}`.
- Testar `_carregarModulos(extensionId)` — verificar que todos os 12 módulos são injetados em ordem sequencial.
- Testar `_injectScript` com `onerror` — verificar que a Promise é rejeitada quando o script falha ao carregar.
- Testar o manifest — verificar que todos os 14 recursos estão declarados em `web_accessible_resources`.

### Property-Based Tests

- Gerar `extensionId` aleatórios (strings alfanuméricas) e verificar que a URL construída sempre tem o formato `chrome-extension://{id}/{src}` — nenhum `extensionId` válido deve causar crash.
- Gerar caminhos de módulo aleatórios e verificar que a URL é sempre construída corretamente sem acessar `chrome.runtime`.
- Gerar números de tentativas aleatórios (0–19) para `_obterExtensionId` e verificar que o retry sempre converge quando o atributo é eventualmente definido.

### Integration Tests

- Carregar a extensão no Chrome em modo desenvolvedor e acessar `https://*.senior.com.br/*` — verificar que o console mostra `[Aura] Orquestrador inicializado.` sem erros.
- Verificar no DevTools (aba Network) que todos os módulos em `modules/` são carregados com status 200.
- Verificar que o container `#aura-floating-container` é criado no DOM após o carregamento.
- Verificar que o `dotlottie-player` carrega `aura.json` corretamente via URL `chrome-extension://`.
- Recarregar a extensão e verificar que o comportamento se repete sem erros.

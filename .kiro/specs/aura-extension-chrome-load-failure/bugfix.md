# Bugfix Requirements Document

## Introduction

A extensão Aura DAP falha ao carregar no Google Chrome com o erro `TypeError: Cannot read properties of undefined (reading 'getURL')` em `content.js:21`. O problema impede que todos os módulos da extensão sejam injetados, tornando o assistente Aura completamente inoperante para os usuários do Senior X.

A causa raiz é que `content.js` é declarado no manifest com `"world": "MAIN"`, o que significa que ele executa no contexto da página web — onde a API `chrome.runtime` não está disponível. A função `_injectScript` chama `chrome.runtime.getURL(src)` diretamente, resultando em `chrome.runtime` sendo `undefined` no momento da execução.

Adicionalmente, os arquivos do diretório `modules/` não estão declarados em `web_accessible_resources` no manifest, o que bloquearia o carregamento dos scripts mesmo que o `getURL` funcionasse.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a extensão Aura é carregada em uma página do Senior X no Chrome THEN o sistema lança `TypeError: Cannot read properties of undefined (reading 'getURL')` em `content.js:21` porque `chrome.runtime` é `undefined` no contexto `world: MAIN`

1.2 WHEN `_injectScript` é chamada com qualquer caminho de módulo THEN o sistema falha imediatamente ao tentar resolver a URL do recurso da extensão, interrompendo o loop de carregamento de módulos

1.3 WHEN o carregamento de módulos falha THEN o sistema registra `[Aura] Falha ao carregar módulos.` no console e nenhum módulo Aura (`AuraUI`, `AuraState`, `AuraAssistEngine`, etc.) é inicializado

1.4 WHEN os arquivos em `modules/` não estão listados em `web_accessible_resources` no `manifest.json` THEN o sistema bloqueia o carregamento desses scripts mesmo que a URL seja resolvida corretamente

### Expected Behavior (Correct)

2.1 WHEN a extensão Aura é carregada em uma página do Senior X no Chrome THEN o sistema SHALL resolver as URLs dos módulos usando o `extensionId` já disponível no atributo `data-aura-id` do DOM (injetado por `bridge.js` no mundo `ISOLATED`), sem depender de `chrome.runtime` no contexto `MAIN`

2.2 WHEN `_injectScript` é chamada com qualquer caminho de módulo THEN o sistema SHALL construir a URL do recurso no formato `chrome-extension://{extensionId}/{src}` usando o `extensionId` obtido via `_obterExtensionId()`, que já é o mecanismo de passagem de ID entre mundos existente na arquitetura

2.3 WHEN o carregamento de módulos é concluído com sucesso THEN o sistema SHALL inicializar todos os módulos Aura e registrar `[Aura] Orquestrador inicializado.` no console

2.4 WHEN os arquivos em `modules/` e demais recursos injetáveis são declarados em `web_accessible_resources` no `manifest.json` THEN o sistema SHALL permitir que esses scripts sejam carregados como recursos acessíveis pela página

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `bridge.js` é executado no mundo `ISOLATED` THEN o sistema SHALL CONTINUE TO injetar o `extensionId` no atributo `data-aura-id` do `document.documentElement` antes que `content.js` precise dele

3.2 WHEN o usuário não está logado no Senior X THEN o sistema SHALL CONTINUE TO aguardar o login antes de inicializar a Aura, respeitando o guardião `_aguardarLogin`

3.3 WHEN a Aura já foi inicializada (`_auraInicializada = true`) THEN o sistema SHALL CONTINUE TO ignorar chamadas subsequentes de inicialização para evitar duplicação

3.4 WHEN `_obterExtensionId` é chamada e o atributo `data-aura-id` ainda não está disponível THEN o sistema SHALL CONTINUE TO realizar até 20 tentativas com intervalo de 100ms antes de retornar `null`

3.5 WHEN `_inicializarAura` recebe um `extensionId` válido THEN o sistema SHALL CONTINUE TO construir a URL do `dotlottie-player` no formato `chrome-extension://{extensionId}/aura.json` para o container HTML

3.6 WHEN `shield.js` desativa temporariamente o RequireJS THEN o sistema SHALL CONTINUE TO restaurar o `window.define` original após o `DOMContentLoaded`, preservando o comportamento do Senior X

---

## Bug Condition (Pseudocódigo)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X de tipo ScriptExecutionContext
  OUTPUT: boolean

  // Retorna verdadeiro quando content.js executa em world MAIN
  // e tenta acessar chrome.runtime diretamente
  RETURN X.world = 'MAIN' AND X.calls_chrome_runtime_getURL_directly = true
END FUNCTION
```

```pascal
// Propriedade: Fix Checking — Resolução de URL sem chrome.runtime
FOR ALL X WHERE isBugCondition(X) DO
  result ← _injectScript'(X.modulePath)
  ASSERT result.url = 'chrome-extension://' + extensionId + '/' + X.modulePath
  ASSERT no_crash(result)
END FOR
```

```pascal
// Propriedade: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT F(X) = F'(X)
  // Comportamento de bridge.js, shield.js, guardião de login e demais módulos
  // permanece idêntico ao original
END FOR
```

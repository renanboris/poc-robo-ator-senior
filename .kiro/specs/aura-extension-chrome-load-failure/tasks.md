# Implementation Plan

- [x] 1. Escrever teste de exploração da bug condition (ANTES do fix)
  - **Property 1: Bug Condition** - Crash de `chrome.runtime.getURL` no mundo MAIN
  - **CRITICAL**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: Este teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **GOAL**: Surfaçar contraexemplos que demonstrem que o bug existe
  - **Scoped PBT Approach**: Para este bug determinístico, escopar a propriedade ao caso concreto: qualquer `src` de módulo com `chrome.runtime = undefined`
  - Configurar ambiente Jest + jsdom com `chrome.runtime = undefined` (simulando o mundo MAIN)
  - Extrair `_injectScript` do código original de `extension/content.js` (sem modificação)
  - Testar que `_injectScript('modules/aura_state.js')` lança `TypeError: Cannot read properties of undefined (reading 'getURL')` para qualquer caminho de módulo
  - Usar `fc.property(fc.string(), src => expect(() => _injectScript(src)).toThrow('getURL'))` para cobrir múltiplos caminhos
  - Executar no código NÃO CORRIGIDO — resultado esperado: FALHA (confirma o bug)
  - Documentar contraexemplos encontrados (ex: `_injectScript('modules/aura_state.js')` → `TypeError`)
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2_

- [x] 2. Escrever testes de preservação (ANTES do fix)
  - **Property 2: Preservation** - Comportamentos não relacionados ao bug permanecem idênticos
  - **IMPORTANT**: Seguir metodologia observation-first
  - Observar comportamento no código NÃO CORRIGIDO para entradas onde `isBugCondition` é falso
  - **Observação 1**: `_obterExtensionId()` com `data-aura-id` ausente por N iterações (N < 20) retorna o ID quando o atributo é eventualmente definido — verificar que o retry funciona
  - **Observação 2**: `_inicializarAura(extensionId)` constrói `chrome-extension://{extensionId}/aura.json` corretamente no container HTML — esse trecho não é tocado pelo fix
  - **Observação 3**: `_estaLogado()` retorna `false` em URLs de login e `true` quando tokens estão no storage
  - **Observação 4**: `_auraInicializada = true` impede chamadas duplicadas a `_tentarIniciarAura`
  - Escrever property-based test: para qualquer `extensionId` alfanumérico válido, `_inicializarAura` constrói a URL do dotlottie-player como `chrome-extension://{extensionId}/aura.json`
  - Escrever property-based test: para qualquer número de tentativas N entre 0 e 19, `_obterExtensionId` retorna o ID quando o atributo é definido na tentativa N
  - Verificar que os testes PASSAM no código não corrigido (confirma baseline a preservar)
  - Marcar tarefa como completa quando os testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix — Corrigir carregamento de módulos no mundo MAIN

  - [x] 3.1 Modificar `_injectScript` em `extension/content.js`
    - Adicionar parâmetro `extensionId` à assinatura: `function _injectScript(src, extensionId)`
    - Substituir `s.src = chrome.runtime.getURL(src)` por `s.src = 'chrome-extension://' + extensionId + '/' + src`
    - Remover qualquer dependência de `chrome.runtime` nesta função
    - Verificar que `s.onload`, `s.onerror` e o `appendChild` permanecem inalterados
    - _Bug_Condition: `isBugCondition(X)` onde `X.world = 'MAIN'` AND `X.calls_chrome_runtime_getURL_directly = true`_
    - _Expected_Behavior: `s.src = 'chrome-extension://' + extensionId + '/' + src` sem acesso a `chrome.runtime`_
    - _Preservation: `s.onload`, `s.onerror`, `appendChild` e estrutura da Promise permanecem idênticos_
    - _Requirements: 2.1, 2.2_

  - [x] 3.2 Modificar `_carregarModulos` em `extension/content.js`
    - Adicionar parâmetro `extensionId` à assinatura: `async function _carregarModulos(extensionId)`
    - Passar `extensionId` a cada chamada: `await _injectScript(modulos[i], extensionId)`
    - Preservar a lista de módulos e a ordem de carregamento sequencial exatamente como está
    - _Bug_Condition: `_carregarModulos` chamada sem `extensionId`, causando crash em `_injectScript`_
    - _Expected_Behavior: todos os 12 módulos injetados em ordem com URL correta_
    - _Preservation: lista de módulos, ordem de carregamento e estrutura do loop permanecem idênticos_
    - _Requirements: 2.2, 2.3_

  - [x] 3.3 Atualizar call sites de `_carregarModulos` em `extension/content.js`
    - Em `_tentarIniciarAura`: alterar `_carregarModulos()` para `_carregarModulos(extensionId)` (o `extensionId` já está disponível no escopo do `.then`)
    - No timeout de `_aguardarLogin`: alterar `_carregarModulos()` para `_carregarModulos(extensionId)` (o `extensionId` já está disponível no escopo do `.then`)
    - Verificar que nenhum outro call site existe no arquivo
    - _Requirements: 2.2_

  - [x] 3.4 Adicionar `modules/*.js` em `web_accessible_resources` no `extension/manifest.json`
    - Adicionar os 8 arquivos de módulos ao array `resources` existente, na ordem de carregamento:
      `"modules/aura_state.js"`, `"modules/aura_feedback.js"`, `"modules/aura_ui.js"`,
      `"modules/aura_dom_mapper.js"`, `"modules/aura_spotlight.js"`, `"modules/aura_gps_engine.js"`,
      `"modules/aura_mission_engine.js"`, `"modules/aura_assist_engine.js"`
    - Preservar todos os recursos já declarados: `aura.json`, `aura_config.js`, `guided_execution.js`, `checklist_widget.js`, `hesitation_detector.js`, `nps_modal.js`
    - Preservar o `matches` existente: `["https://*.senior.com.br/*"]`
    - _Bug_Condition: `modules/*.js` ausentes em `web_accessible_resources` → Chrome bloqueia carregamento_
    - _Expected_Behavior: Chrome permite carregamento de todos os módulos via URL `chrome-extension://`_
    - _Requirements: 2.4_

  - [x] 3.5 Verificar que o teste de exploração da bug condition agora passa
    - **Property 1: Expected Behavior** - Resolução de URL de Módulo sem `chrome.runtime`
    - **IMPORTANT**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever um novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado está satisfeito
    - Executar o teste de bug condition do passo 1 no código CORRIGIDO
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2 — Expected Behavior Properties do design_

  - [x] 3.6 Verificar que os testes de preservação ainda passam
    - **Property 2: Preservation** - Comportamentos não relacionados ao bug permanecem idênticos
    - **IMPORTANT**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar os testes de preservação do passo 2 no código CORRIGIDO
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma ausência de regressões)
    - Confirmar que `_obterExtensionId`, `_inicializarAura`, `_estaLogado` e `_auraInicializada` se comportam identicamente ao original

- [x] 4. Checkpoint — Garantir que todos os testes passam
  - Executar a suite completa de testes (property 1 + property 2 + unit tests)
  - Confirmar que o console mostra `[Aura] Orquestrador inicializado.` sem erros ao carregar a extensão no Chrome
  - Verificar no DevTools (aba Network) que todos os módulos em `modules/` são carregados com status 200
  - Verificar que o container `#aura-floating-container` é criado no DOM após o carregamento
  - Perguntar ao usuário se surgirem dúvidas durante a validação

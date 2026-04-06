# Video Render Progress Bar — Bugfix Design

## Overview

Durante a renderização do vídeo MP4, o frontend (`index.html`) ignora completamente o campo `data.progresso` emitido via WebSocket pelo backend. O resultado é um spinner estático durante toda a etapa mais longa da produção, sem qualquer feedback de avanço ao operador.

A infraestrutura de ponta a ponta já existe: `main.py` emite `PROGRESSO:{pct}` via stdout, `app.py` captura e faz broadcast do campo `progresso` via WebSocket, e o frontend já tem WebSocket conectado. O bug está exclusivamente na camada de apresentação: o handler `_ws.onmessage` em `index.html` só verifica `data.ocupado` para resolver a Promise de conclusão, ignorando `data.progresso` por completo.

O fix é cirúrgico: adicionar lógica no `onmessage` para detectar mensagens com `data.progresso` enquanto o step ativo é o de renderização, e atualizar um elemento visual no DOM do step correspondente.

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug — mensagem WebSocket com `data.progresso` numérico chega ao frontend enquanto o step de renderização está ativo, mas nenhum elemento visual é atualizado
- **Property (P)**: O comportamento correto esperado — o step de renderização SHALL exibir o valor de progresso recebido (porcentagem ou barra) e atualizá-lo a cada mensagem
- **Preservation**: O comportamento existente que não deve ser alterado pelo fix — spinner padrão nos outros steps, tratamento de erro, fallback de polling, avanço para steps subsequentes
- **`_ws.onmessage`**: Handler de mensagens WebSocket em `templates/index.html` que atualmente só reage a `data.ocupado === false`
- **`runStepper`**: Função em `templates/index.html` que itera sobre os `STEPS`, dispara cada endpoint e aguarda conclusão via `pollStatus()`
- **`_wsResolve`**: Callback armazenado que resolve a Promise de `aguardarStatus()` quando `data.ocupado` passa a `false`
- **`STEPS[0]`**: O step de renderização de vídeo (`🎬 Renderização do vídeo (MP4)`), único que recebe `data.progresso` do backend
- **`CustomRenderLogger`**: Classe em `main.py` que intercepta o progresso do moviepy e emite `PROGRESSO:{pct}` via stdout
- **`_set_estado(progresso=pct)`**: Chamada em `app.py` que atualiza o estado do servidor e faz broadcast via WebSocket

## Bug Details

### Bug Condition

O bug se manifesta quando o backend emite uma mensagem WebSocket com `data.progresso` numérico (0–100) enquanto o step de renderização está em execução. O `onmessage` do frontend recebe a mensagem mas não executa nenhuma ação para atualizar o DOM, pois a única lógica presente verifica exclusivamente `!data.ocupado`.

**Formal Specification:**
```
FUNCTION isBugCondition(wsMessage)
  INPUT: wsMessage — objeto JSON recebido via WebSocket
  OUTPUT: boolean

  RETURN wsMessage.progresso IS NOT NULL
         AND typeof wsMessage.progresso === 'number'
         AND wsMessage.ocupado === true
         AND stepAtivo === STEPS[0]  // step de renderização
         AND elementoProgressoNoDOM NÃO FOI ATUALIZADO
END FUNCTION
```

### Examples

- Backend emite `{"ocupado": true, "progresso": 23}` → frontend recebe, `onmessage` executa, `!data.ocupado` é `false`, nenhuma branch é executada, DOM permanece com spinner estático. **Esperado**: exibir "23%".
- Backend emite `{"ocupado": true, "progresso": 75}` → mesmo comportamento. **Esperado**: exibir "75%".
- Backend emite `{"ocupado": false, "progresso": null, "sucesso": "..."}` → `_wsResolve` é chamado, step passa para `ok`. **Esperado (com fix)**: ter exibido 100% antes de transicionar.
- Backend emite `{"ocupado": true, "progresso": 47}` durante step de SCORM → **Esperado**: nenhum indicador de progresso (SCORM não emite `PROGRESSO:`, mas mesmo que chegasse, não deve afetar o spinner do step de SCORM).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Steps de SCORM, PDF e SimLink continuam exibindo apenas o spinner padrão, sem indicador de progresso numérico
- Quando a renderização falha e o backend emite `data.erro`, o step continua sendo marcado com estado de erro (`err`) normalmente
- Quando o WebSocket está desconectado, o fallback `_pollFallback` continua aguardando conclusão via polling sem quebrar o fluxo do stepper
- Após a renderização concluir com sucesso, o `runStepper` continua avançando para os steps seguintes (SCORM, PDF, SimLink) normalmente
- Nova sessão (`newSession()`) não carrega estado residual de progresso de sessões anteriores

**Scope:**
Todos os inputs que NÃO envolvem mensagens WebSocket com `data.progresso` durante o step de renderização devem ser completamente inalterados pelo fix. Isso inclui:
- Cliques e interações do usuário com outros elementos da UI
- Mensagens WebSocket sem o campo `progresso` ou com `progresso: null`
- Comportamento dos steps 1–4 (SCORM, PDF, SimLink, Indexação)
- Lógica de resolução da Promise via `_wsResolve`

## Hypothesized Root Cause

Com base na análise do código, a causa raiz é única e bem localizada:

1. **Handler `onmessage` incompleto**: O handler em `conectarWS()` só contém lógica para o caso `!data.ocupado`. Não existe nenhuma branch para `data.progresso`. O campo chega ao frontend mas é descartado silenciosamente pelo bloco `try/catch {}` vazio.

2. **Ausência de referência ao step ativo no handler**: O `onmessage` não tem acesso ao elemento DOM do step corrente. O `runStepper` cria elementos DOM localmente dentro do loop `for`, mas não expõe uma referência que o handler possa usar para atualizar o progresso em tempo real.

3. **Ausência de elemento visual de progresso no step de renderização**: O HTML do step é gerado com apenas `<div class="step-icon spinning"></div>` e `<span>label</span>`. Não existe nenhum elemento de porcentagem ou barra de progresso no template do step.

4. **Sem mecanismo de comunicação entre `runStepper` e `onmessage`**: O `runStepper` e o `onmessage` são funções independentes sem canal de comunicação. Para que o `onmessage` atualize o DOM do step correto, é necessário um mecanismo de referência compartilhada (ex: variável de módulo apontando para o elemento DOM ativo).

## Correctness Properties

Property 1: Bug Condition — Progresso de Renderização Exibido no Frontend

_For any_ mensagem WebSocket onde `data.progresso` é um número entre 0 e 100 e `data.ocupado` é `true`, recebida enquanto o step de renderização (`STEPS[0]`) está ativo no stepper, a função `onmessage` corrigida SHALL atualizar o elemento visual de progresso do step de renderização com o valor recebido, de forma que o operador veja a porcentagem atual de avanço.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Comportamento Inalterado para Inputs Fora da Bug Condition

_For any_ mensagem WebSocket onde `data.progresso` é `null` ou `undefined`, ou onde o step ativo não é o de renderização, ou onde `data.ocupado` passa a `false`, a função `onmessage` corrigida SHALL produzir exatamente o mesmo comportamento que a função original, preservando a resolução da Promise de conclusão, o tratamento de erro, e o spinner padrão dos demais steps.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assumindo que a análise de causa raiz está correta:

**File**: `templates/index.html`

**Scope**: Apenas JavaScript — nenhuma alteração em `app.py` ou `main.py` é necessária.

**Specific Changes**:

1. **Adicionar variável de referência ao step ativo**: Declarar uma variável de módulo (ex: `_activeRenderStepEl`) que armazena a referência ao elemento DOM do step de renderização enquanto ele está em execução.

2. **Atualizar `runStepper` para expor a referência**: No início do step de renderização (`i === 0`), atribuir o elemento DOM criado à variável `_activeRenderStepEl`. Ao concluir ou falhar o step, limpar a referência (`_activeRenderStepEl = null`).

3. **Adicionar elemento de progresso no template do step de renderização**: Incluir um `<span>` ou elemento inline no HTML gerado para o step de renderização que exiba a porcentagem (ex: `<span id="${stepId}-pct" class="step-pct"></span>`).

4. **Estender `onmessage` para reagir a `data.progresso`**: Adicionar uma branch no handler que, quando `data.progresso` é numérico e `_activeRenderStepEl` não é null, atualiza o texto do elemento de porcentagem com o valor recebido.

5. **Garantir que a lógica de resolução da Promise não seja afetada**: A branch de `data.progresso` deve ser independente da branch de `!data.ocupado`. Ambas podem coexistir na mesma mensagem (ex: `{ocupado: false, progresso: null}`) sem interferência.

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não corrigido com testes exploratórios; depois, verificar o fix e a preservação com testes unitários e baseados em propriedades.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES do fix. Confirmar ou refutar a análise de causa raiz. Se refutada, re-hipotetisar.

**Test Plan**: Simular mensagens WebSocket com `data.progresso` no handler `onmessage` do código não corrigido e verificar que nenhum elemento DOM é atualizado.

**Test Cases**:
1. **Progresso 0%**: Simular `{ocupado: true, progresso: 0}` → verificar que nenhum elemento com porcentagem aparece no DOM do step (vai falhar no código corrigido, confirma o bug no original)
2. **Progresso 47%**: Simular `{ocupado: true, progresso: 47}` → mesmo resultado esperado
3. **Progresso 100%**: Simular `{ocupado: true, progresso: 100}` → mesmo resultado esperado
4. **Sequência crescente**: Simular 0%, 25%, 50%, 75%, 100% em sequência → verificar que o DOM nunca reflete nenhum valor

**Expected Counterexamples**:
- O elemento de porcentagem não existe no DOM (não foi criado no template do step)
- Mesmo que existisse, `onmessage` não o atualizaria pois não há branch para `data.progresso`

### Fix Checking

**Goal**: Verificar que para todos os inputs onde a bug condition é verdadeira, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL wsMessage WHERE isBugCondition(wsMessage) DO
  result := onmessage_fixed(wsMessage)
  ASSERT elementoProgressoNoDOM.textContent === wsMessage.progresso + '%'
  ASSERT _wsResolve NÃO FOI CHAMADO  // Promise não resolvida prematuramente
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos os inputs onde a bug condition NÃO é verdadeira, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL wsMessage WHERE NOT isBugCondition(wsMessage) DO
  ASSERT onmessage_original(wsMessage) === onmessage_fixed(wsMessage)
END FOR
```

**Testing Approach**: Testes baseados em propriedades são recomendados para preservation checking porque:
- Geram automaticamente muitas combinações de mensagens WebSocket
- Cobrem edge cases como `progresso: null`, `progresso: 0`, `ocupado: false` com e sem `progresso`
- Garantem que a lógica de resolução da Promise não foi quebrada para nenhum input

**Test Plan**: Observar o comportamento no código não corrigido para mensagens sem `progresso`, depois escrever testes de propriedade capturando esse comportamento.

**Test Cases**:
1. **Resolução de Promise preservada**: Verificar que `{ocupado: false, progresso: null}` ainda resolve `_wsResolve` corretamente após o fix
2. **Erro preservado**: Verificar que `{ocupado: false, erro: "Falha: ..."}` ainda resolve com `sucesso: false`
3. **Spinner dos outros steps preservado**: Verificar que durante steps 1–4, mensagens com `progresso` não afetam o DOM desses steps
4. **Estado residual limpo**: Verificar que `_activeRenderStepEl` é `null` após conclusão ou erro do step de renderização

### Unit Tests

- Testar `onmessage` com `{ocupado: true, progresso: 47}` e verificar atualização do DOM
- Testar `onmessage` com `{ocupado: false, progresso: null}` e verificar resolução da Promise
- Testar `onmessage` com `{ocupado: true, progresso: 47}` quando `_activeRenderStepEl` é `null` (step não ativo) e verificar que nada é atualizado
- Testar sequência de mensagens de progresso e verificar que o valor mais recente é exibido

### Property-Based Tests

- Gerar valores aleatórios de `progresso` em [0, 100] e verificar que todos são exibidos corretamente quando o step de renderização está ativo
- Gerar mensagens aleatórias sem `progresso` (ou com `progresso: null`) e verificar que o comportamento de resolução da Promise é idêntico ao original
- Gerar combinações de `{ocupado, progresso, erro, sucesso}` e verificar que a lógica de resolução da Promise nunca é acionada por mensagens de progresso

### Integration Tests

- Iniciar uma renderização real e verificar que o indicador de progresso aparece e aumenta no stepper
- Verificar que após a renderização, o step avança para SCORM normalmente
- Verificar que uma renderização com erro marca o step como `err` independente do progresso anterior
- Verificar que uma nova sessão não exibe progresso residual de sessões anteriores

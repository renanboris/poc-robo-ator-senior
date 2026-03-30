# Robot Execution Timeout and Aura Indexing — Bugfix Design

## Overview

Dois bugs afetam o fluxo de execução do robô e a linha de produção em `templates/index.html`.

**Bug 1 — Timeout prematuro**: A função `aguardarStatus()` usa um timeout hardcoded de 180.000ms (3 minutos). Roteiros longos (muitos passos, narrações extensas) ultrapassam esse limite e recebem uma mensagem de falha falsa, interrompendo o fluxo mesmo quando o robô está executando corretamente.

**Bug 2 — Step de Indexação Aura (falso positivo confirmado)**: Após leitura completa do arquivo, o array `STEPS` já contém o quarto item com `endpoint: n => \`/api/ingest/${n}\`` completo e funcional. O bug reportado era artefato de truncação na leitura anterior. O endpoint `/api/ingest/{arquivo}` existe e está implementado em `app.py`. **Não há código a corrigir para o Bug 2.**

A correção real é pontual: aumentar o valor do timeout e corrigir a mensagem de erro associada em dois locais dentro de `aguardarStatus` e `_pollFallback`.

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug — quando `timeoutMs` expira antes da conclusão real do processo
- **Property (P)**: O comportamento correto — o sistema deve aguardar a conclusão real do processo sem reportar falha prematura
- **Preservation**: Comportamentos existentes que não devem ser alterados pela correção
- **aguardarStatus(timeoutMs)**: Função em `templates/index.html` que aguarda o sinal de conclusão via WebSocket ou polling
- **_pollFallback(resolve, timeoutMs)**: Fallback de polling HTTP usado quando o WebSocket não está disponível
- **pollStatus()**: Alias de `aguardarStatus()` sem argumentos — usa o valor default
- **ocupado**: Flag de estado retornada pelo backend indicando se o processo ainda está em execução

## Bug Details

### Bug Condition

O bug se manifesta quando a execução do robô (`/api/executar-robo/`) demora mais de 180.000ms (3 minutos). A função `aguardarStatus` dispara o `setTimeout` interno antes que o backend sinalize conclusão, resolvendo a Promise com `sucesso: false` e uma mensagem de erro falsa.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input de tipo { duracaoExecucaoMs: number }
  OUTPUT: boolean

  RETURN input.duracaoExecucaoMs > 180000
         AND processoAindaEmExecucao(input)
         AND NOT sinalDeConclusaoRecebido(input)
END FUNCTION
```

### Examples

- Roteiro com 15 passos e narrações longas demora ~4 minutos → sistema reporta "Tempo esgotado" aos 3 min, robô ainda executando
- Roteiro com 25 passos demora ~8 minutos → mesmo comportamento, falha falsa
- Roteiro com 5 passos demora ~90 segundos → não afetado (abaixo de 3 min)
- Roteiro com 30 passos demora ~25 minutos → afetado; com fix de 30 min, passa a funcionar

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Quando o robô falha com erro real (`sucesso: false` vindo do backend), o sistema deve continuar reportando a falha corretamente
- Quando o usuário cancela via `/api/cancelar`, o sistema deve continuar reportando a interrupção
- Quando a execução conclui em menos de 30 minutos, o sistema deve reportar sucesso imediatamente ao receber o sinal, sem aguardar o timeout
- O fallback de polling (`_pollFallback`) deve continuar funcionando quando o WebSocket não está disponível
- As etapas de renderização de vídeo, SCORM e PDF no stepper devem continuar funcionando com o mesmo comportamento

**Scope:**
Todos os inputs onde `duracaoExecucaoMs <= 1800000` (30 minutos) e o processo conclui normalmente não devem ser afetados. O fix não altera a lógica de resolução — apenas o limite de espera.

## Hypothesized Root Cause

1. **Valor hardcoded insuficiente**: `aguardarStatus(timeoutMs = 180000)` define 3 minutos como default. Roteiros longos excedem esse limite rotineiramente.

2. **Mensagem de erro hardcoded**: A string `'Tempo esgotado. O processo excedeu 3 minutos.'` aparece em dois locais — no `setTimeout` dentro de `aguardarStatus` e no loop de `_pollFallback`. Ambos precisam ser atualizados para refletir o novo limite.

3. **Ausência de configuração externalizada**: O valor não está em constante nomeada nem em variável de configuração, dificultando manutenção futura.

4. **Bug 2 é falso positivo**: A leitura anterior do arquivo foi truncada na linha 771 de 1219. O step de indexação está completo no código real. Nenhuma correção necessária.

## Correctness Properties

Property 1: Bug Condition — Timeout Não Interrompe Execução Longa

_For any_ execução do robô onde `isBugCondition` retorna true (duração > 3 min e processo ainda em execução), a função `aguardarStatus` corrigida SHALL aguardar até o novo limite (1.800.000ms / 30 minutos) antes de resolver com timeout, permitindo que execuções longas concluam normalmente.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation — Comportamento Inalterado Para Execuções Normais

_For any_ execução onde `isBugCondition` retorna false (duração ≤ 3 min, ou processo que falha com erro real, ou cancelamento explícito), a função `aguardarStatus` corrigida SHALL produzir exatamente o mesmo resultado que a versão original, preservando todos os fluxos de sucesso rápido, falha real e cancelamento.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

**File**: `templates/index.html`

**Specific Changes**:

1. **Aumentar o valor default do timeout**:
   - De: `function aguardarStatus(timeoutMs = 180000)`
   - Para: `function aguardarStatus(timeoutMs = 1800000)`

2. **Corrigir a mensagem de timeout no WebSocket path**:
   - De: `resolve({ sucesso: false, mensagem: 'Tempo esgotado. O processo excedeu 3 minutos.' })`
   - Para: `resolve({ sucesso: false, mensagem: 'Tempo esgotado. O processo excedeu 30 minutos.' })`

3. **Corrigir a mensagem de timeout no fallback de polling**:
   - De: `resolve({ sucesso: false, mensagem: 'Tempo esgotado. O processo excedeu 3 minutos.' })`
   - Para: `resolve({ sucesso: false, mensagem: 'Tempo esgotado. O processo excedeu 30 minutos.' })`

**Scope**: 3 linhas alteradas, todas dentro de `aguardarStatus` e `_pollFallback`. Nenhuma outra função é afetada.

**Bug 2**: Nenhuma alteração necessária. O array `STEPS` já contém o quarto item completo:
```javascript
{ label: '🧠 Indexação na base de conhecimento', endpoint: n => `/api/ingest/${n}` }
```

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro confirmar o bug no código original (execução longa falha prematuramente), depois verificar que o fix permite a conclusão e preserva os demais comportamentos.

### Exploratory Bug Condition Checking

**Goal**: Confirmar que `aguardarStatus` resolve com falsa negativa antes da conclusão real do processo quando a duração excede 180.000ms.

**Test Plan**: Simular uma Promise que resolve após 200.000ms e verificar que `aguardarStatus` (sem fix) retorna `sucesso: false` antes da resolução.

**Test Cases**:
1. **Timeout prematuro via WebSocket path**: Mock de `_ws.readyState === WebSocket.OPEN`, `_wsResolve` nunca chamado em 180s → deve retornar `sucesso: false` (confirma bug)
2. **Timeout prematuro via polling path**: Mock de `/api/status` sempre retornando `ocupado: true` por 180s → deve retornar `sucesso: false` (confirma bug)
3. **Execução longa bem-sucedida (unfixed)**: Processo que conclui em 200s → sistema reporta falha aos 180s mesmo com sucesso real

**Expected Counterexamples**:
- `aguardarStatus` resolve com `{ sucesso: false, mensagem: 'Tempo esgotado...' }` antes do processo concluir
- Causa confirmada: valor hardcoded `180000` insuficiente

### Fix Checking

**Goal**: Verificar que para todas as execuções onde `isBugCondition` é verdadeiro, a versão corrigida aguarda até 1.800.000ms.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := aguardarStatus_fixed()
  ASSERT result.sucesso = true  // quando processo conclui antes de 30 min
  ASSERT timer_disparado_apos >= 1800000  // timeout só ocorre após 30 min
END FOR
```

### Preservation Checking

**Goal**: Verificar que execuções rápidas, falhas reais e cancelamentos continuam funcionando identicamente.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT aguardarStatus_original(input) = aguardarStatus_fixed(input)
END FOR
```

**Testing Approach**: Testes unitários com mocks de WebSocket e fetch são suficientes aqui. A lógica de resolução não muda — apenas o limite de espera.

**Test Cases**:
1. **Sucesso rápido (< 3 min)**: Processo conclui em 60s → ambas as versões retornam `sucesso: true` imediatamente
2. **Falha real do backend**: Backend retorna `{ ocupado: false, erro: 'returncode 1' }` → ambas retornam `sucesso: false` com a mensagem correta
3. **Cancelamento**: Backend retorna `{ ocupado: false, erro: 'Cancelado pelo usuário' }` → comportamento preservado
4. **Fallback de polling**: WebSocket indisponível, polling conclui em 90s → comportamento preservado

### Unit Tests

- Testar `aguardarStatus` com mock de WebSocket que resolve em 200s → deve retornar sucesso (fixed) vs falha (unfixed)
- Testar `_pollFallback` com mock de fetch que retorna `ocupado: false` após 200s → deve retornar sucesso (fixed)
- Testar que execuções rápidas (< 180s) continuam resolvendo imediatamente em ambas as versões

### Property-Based Tests

- Gerar durações aleatórias entre 0 e 1.800.000ms e verificar que `aguardarStatus` só retorna timeout quando `duracaoMs >= 1800000`
- Gerar respostas aleatórias do backend (`ocupado: true/false`, `erro: string | null`) e verificar que a lógica de resolução é preservada independente do timeout

### Integration Tests

- Executar um roteiro real com mais de 3 minutos de duração e verificar que o sistema aguarda a conclusão sem reportar falha
- Verificar que após o fix, a linha de produção (stepper) é acionada normalmente após execução longa do robô
- Verificar que a etapa de indexação Aura (`/api/ingest/`) é chamada e concluída no stepper (comportamento já funcional, teste de regressão)

# PrimeNG Modal Selector Fallback Fix - Design Técnico

## Overview

Este bugfix adiciona detecção de contexto de modal PrimeNG e geração de seletores com escopo adequado para elementos dentro de diálogos. O problema atual é que `resolvePrimeNGComponent()` em `capture_dual_output.py` gera seletores genéricos como `'ui-btn'` para botões de busca dentro de modais, e `_gerar_candidatos()` em `vision_engine.py` não tenta variantes com escopo de modal, resultando em ambiguidade e fallback para coordenadas (~26% de sucesso).

A solução implementa detecção de ancestral modal durante a captura e prefixação de seletores com o escopo do diálogo (ex: `p-dialog[role="dialog"] [name='tipoTitulo'] button.button-addon`), além de estratégias de fallback resilientes no executor que tentam múltiplas variantes de escopo antes de recorrer a coordenadas.

## Glossary

- **Bug_Condition (C)**: Condição que identifica quando um elemento está dentro de um modal PrimeNG e o seletor capturado não inclui o escopo do modal
- **Property (P)**: Comportamento esperado — seletores devem incluir prefixo de escopo de modal e resolver >90% das vezes sem fallback de coordenadas
- **Preservation**: Comportamento de componentes PrimeNG fora de modais, checkboxes, diálogos de confirmação e cascade do executor devem permanecer inalterados
- **resolvePrimeNGComponent()**: Função JavaScript em `capture_dual_output.py` (linha ~276) que identifica 10 tipos de componentes PrimeNG compostos e gera seletores semânticos
- **_gerar_candidatos()**: Função Python em `vision_engine.py` (linha ~553) que gera lista de tentativas de localização com fallbacks progressivos
- **Modal PrimeNG**: Componentes `p-dialog`, `ui-dialog`, `s-dialog`, `p-confirmdialog` que criam overlays dinâmicos sobre a aplicação principal
- **Escopo de Modal**: Prefixo CSS que ancora um seletor ao contexto de um diálogo específico (ex: `p-dialog[role="dialog"]`)

## Bug Details

### Bug Condition

O bug se manifesta quando um elemento interativo (botão de busca, linha de tabela, campo de entrada) está dentro de um modal PrimeNG e o sistema de captura não detecta esse contexto. A função `resolvePrimeNGComponent()` gera um seletor baseado apenas no componente local sem considerar o ancestral modal, resultando em seletores ambíguos que correspondem a múltiplos elementos no DOM.

**Formal Specification:**
```
FUNCTION isBugCondition(element, capturedSelector)
  INPUT: element of type HTMLElement, capturedSelector of type string
  OUTPUT: boolean
  
  modalAncestor := element.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]')
  
  RETURN modalAncestor IS NOT NULL
         AND capturedSelector DOES NOT contain modal scope prefix
         AND (capturedSelector matches multiple elements in document
              OR capturedSelector is generic like 'ui-btn', 'button', '.button-addon')
END FUNCTION
```

### Examples

- **Exemplo 1**: Usuário clica no botão de busca `button.button-addon` dentro de um autocomplete em modal de seleção de tipo de título. O capture gera `'ui-btn'` que corresponde a 4+ botões na página. Executor falha e usa coordenadas com 26% de sucesso.

- **Exemplo 2**: Usuário seleciona linha "Adiantamento Crédito a Identificar" em tabela dentro de `p-dialog`. O capture não gera seletor estável. Executor não encontra elemento e falha completamente.

- **Exemplo 3**: Usuário clica em linha de transação "90330" em modal. O capture gera seletor sem escopo de modal. Executor busca no DOM inteiro, encontra múltiplas correspondências ambíguas e usa coordenadas (falha).

- **Exemplo 4 (Edge Case)**: Modal é aberto dinamicamente após operação assíncrona. O elemento ainda não existe no DOM quando o capture tenta gerar o seletor. Sistema deve aguardar estabilização do modal antes de capturar.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Componentes PrimeNG fora de modais (autocomplete, calendar, dropdown em formulários principais) devem continuar usando a lógica existente de `resolvePrimeNGComponent()` sem prefixo de modal
- Checkboxes em tabelas devem continuar usando estratégia `:has-text()` para ancorar em conteúdo de linha
- Botões de confirmação em diálogos (`p-confirmdialog`) devem continuar usando a lógica especial existente em `_gerar_candidatos()` (linhas 584-607)
- Cascade de fallback do executor (Brain → Menu Contexto → Foco → Heurísticas → Coordenadas → Sniper → Hint → Frames → Vision) deve permanecer intacto

**Scope:**
Todas as interações que NÃO envolvem elementos dentro de modais PrimeNG devem ser completamente inalteradas. Isso inclui:
- Formulários principais da aplicação
- Navegação por menus e sidebar
- Campos de entrada em telas não-modais
- Botões de ação em barras de ferramentas

## Hypothesized Root Cause

Baseado na análise do código, as causas mais prováveis são:

1. **Falta de Detecção de Contexto Modal no Capture**: A função `resolvePrimeNGComponent()` (linha 276 de `capture_dual_output.py`) não verifica se o elemento clicado está dentro de um ancestral modal antes de gerar o seletor. Ela apenas sobe na árvore DOM procurando identificadores (`name`, `data-testid`, `id`) mas não adiciona prefixo de escopo.

2. **Seletores Genéricos para Botões de Addon**: Quando `resolvePrimeNGComponent()` identifica um `button.button-addon` (linha 304), ela retorna apenas `'button'` como sufixo. Se não encontrar identificador estável no loop de 8 níveis (linhas 327-365), retorna o fallback genérico `${hostId} ${suffix}` que resulta em `'p-autocomplete button'` — ambíguo quando há múltiplos autocompletes na página.

3. **Ausência de Variantes com Escopo Modal no Executor**: A função `_gerar_candidatos()` em `vision_engine.py` (linha 553) tem lógica especial para diálogos de confirmação (linhas 584-607) mas não gera variantes com escopo de modal para outros tipos de elementos. Quando recebe um seletor ambíguo como hint, não tenta prefixá-lo com `p-dialog`, `ui-dialog`, etc.

4. **Timing de Renderização Assíncrona**: Modais PrimeNG são renderizados dinamicamente após eventos de usuário. O capture pode tentar gerar seletor antes do modal estar completamente estável no DOM, resultando em seletores baseados em estrutura transitória.

## Correctness Properties

Property 1: Bug Condition - Modal Scope Detection

_For any_ elemento interativo dentro de um modal PrimeNG (p-dialog, ui-dialog, s-dialog, p-confirmdialog), o sistema de captura SHALL detectar o ancestral modal e gerar um seletor que inclui o prefixo de escopo do diálogo, garantindo que o seletor seja único dentro do contexto do modal e não ambíguo no DOM global.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation - Non-Modal PrimeNG Components

_For any_ componente PrimeNG que NÃO está dentro de um modal (autocomplete, calendar, dropdown em formulários principais), o sistema SHALL continuar gerando seletores usando a lógica existente de `resolvePrimeNGComponent()` sem adicionar prefixo de modal, preservando o comportamento atual que já funciona corretamente para esses casos.

**Validates: Requirements 3.1, 3.5**

Property 3: Preservation - Checkbox and Dialog Confirmation Behavior

_For any_ checkbox em tabela ou botão de confirmação em diálogo, o sistema SHALL continuar usando as estratégias especiais existentes (`:has-text()` para checkboxes, escopo de dialog para confirmações), sem interferência da nova lógica de detecção de modal.

**Validates: Requirements 3.2, 3.3**

Property 4: Executor Fallback Resilience

_For any_ ação capturada com seletor que inclui escopo de modal, o executor SHALL tentar múltiplas variantes de escopo (p-dialog[role="dialog"], .ui-dialog, s-dialog) antes de recorrer ao fallback de coordenadas, aumentando a taxa de sucesso para >90% sem necessidade de coordenadas.

**Validates: Requirements 2.4, 2.5**

## Fix Implementation

### Changes Required

Assumindo que nossa análise de causa raiz está correta:

**File**: `capture_variants/capture_dual_output.py`

**Function**: `resolvePrimeNGComponent` (linha ~276)

**Specific Changes**:

1. **Adicionar Detecção de Ancestral Modal**: Antes de retornar o seletor final, verificar se o elemento está dentro de um modal PrimeNG usando `el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]')`. Se encontrado, extrair um identificador estável do modal (atributo `role`, `aria-labelledby`, ou classe específica).

2. **Prefixar Seletor com Escopo de Modal**: Se modal detectado, prefixar o seletor gerado com o escopo do diálogo. Exemplo: se o seletor original é `[name='tipoTitulo'] button`, o seletor final deve ser `p-dialog[role="dialog"] [name='tipoTitulo'] button`.

3. **Adicionar Metadado de Contexto Modal**: Incluir campo `modal_context` no JSON retornado por `window.capturarElemento()` (linha ~477) para que o executor saiba que o elemento estava em modal durante a captura.

4. **Aguardar Estabilização de Modal**: Adicionar verificação de que o modal está completamente renderizado antes de capturar o seletor. Usar `modalAncestor.getAttribute('aria-hidden') !== 'true'` e verificar que o modal tem dimensões visíveis (`getBoundingClientRect().width > 0`).

5. **Fallback para Seletor de Linha em Tabelas Modais**: Para elementos `<tr>` ou `<td>` dentro de modais, gerar seletor baseado em `:has-text()` com o conteúdo único da linha, prefixado com escopo de modal. Exemplo: `p-dialog tr:has-text("Adiantamento Crédito")`.

**File**: `vision_engine.py`

**Function**: `_gerar_candidatos` (linha ~553)

**Specific Changes**:

1. **Detectar Hint com Escopo de Modal**: Verificar se `seletor_hint` começa com prefixos de modal (`p-dialog`, `ui-dialog`, `s-dialog`, `[role="dialog"]`). Se sim, extrair o escopo e o seletor interno.

2. **Gerar Variantes de Escopo de Modal**: Se o hint contém escopo de modal, gerar candidatos adicionais com variantes de prefixo:
   - `p-dialog[role="dialog"] {seletor_interno}`
   - `.ui-dialog {seletor_interno}`
   - `s-dialog {seletor_interno}`
   - `[role="dialog"] {seletor_interno}`
   - `.p-dialog-content {seletor_interno}` (para casos onde o escopo é mais específico)

3. **Adicionar Candidatos de Tabela Modal**: Se `tipo_elemento` indica elemento de tabela (`tr`, `td`) e há escopo de modal, gerar candidatos usando `:has-text()` com o `label_curto`:
   ```python
   for modal_scope in ["p-dialog", ".ui-dialog", "s-dialog", "[role='dialog']"]:
       candidatos.append(TentativaLocalizacao(
           seletor=f"{modal_scope} tr:has-text('{label_curto}')",
           iframe_hint=iframe_hint,
           descricao=f"modal table row '{label_curto}' em {modal_scope}",
       ))
   ```

4. **Priorizar Candidatos com Escopo de Modal**: Inserir candidatos com escopo de modal no início da lista (antes dos candidatos genéricos) para que sejam tentados primeiro, reduzindo latência de localização.

5. **Preservar Lógica Existente de Dialog de Confirmação**: Garantir que a lógica especial para botões de confirmação (linhas 584-607) não seja afetada pela nova lógica de modal. Esses candidatos devem continuar sendo gerados e priorizados.

**File**: `capture_variants/capture_dual_output.py`

**Function**: `getBestSelector` (linha ~412)

**Specific Changes**:

1. **Adicionar Verificação de Modal no Fallback Genérico**: No final da função, antes de retornar o fallback de `nth-child`, verificar se o elemento está em modal e adicionar prefixo de escopo se necessário.

2. **Melhorar Seletor de Botões em Modais**: Para elementos `button` ou `a` dentro de modais sem identificadores estáveis, usar combinação de escopo de modal + texto visível: `p-dialog button:has-text('{texto}')`.

## Testing Strategy

### Validation Approach

A estratégia de teste segue abordagem de duas fases: primeiro, executar testes exploratórios no código UNFIXED para confirmar a hipótese de causa raiz e coletar contraexemplos reais; depois, implementar o fix e validar que os seletores com escopo de modal resolvem corretamente e que o comportamento de componentes não-modais permanece inalterado.

### Exploratory Bug Condition Checking

**Goal**: Confirmar que o código UNFIXED não detecta contexto de modal e gera seletores ambíguos. Coletar contraexemplos reais de seletores capturados e taxas de falha do executor.

**Test Plan**: Executar capturas de workflows que envolvem interações em modais PrimeNG no Senior X. Inspecionar os seletores gerados no JSON do roteiro e verificar se incluem escopo de modal. Executar o robot com esses roteiros e medir taxa de sucesso vs fallback de coordenadas.

**Test Cases**:
1. **Modal Autocomplete Search Button**: Capturar clique no botão de busca `button.button-addon` dentro de autocomplete em modal de seleção (falhará no unfixed — seletor será genérico `'ui-btn'`)
2. **Modal Table Row Selection**: Capturar seleção de linha em tabela dentro de `p-dialog` (falhará no unfixed — seletor não será gerado ou será instável)
3. **Modal Transaction Row Click**: Capturar clique em linha de transação com código específico em modal (falhará no unfixed — seletor sem escopo encontrará múltiplas correspondências)
4. **Async Modal Rendering**: Capturar interação em modal que aparece após operação assíncrona (pode falhar no unfixed se captura ocorrer antes de modal estabilizar)

**Expected Counterexamples**:
- Seletores capturados não contêm prefixo `p-dialog`, `ui-dialog`, ou `[role="dialog"]`
- Executor encontra 4+ candidatos para seletores genéricos como `'ui-btn'`
- Taxa de fallback para coordenadas >70% em ações dentro de modais
- Possíveis causas confirmadas: falta de detecção de ancestral modal, seletores genéricos sem identificador estável, ausência de variantes com escopo no executor

### Fix Checking

**Goal**: Verificar que para todas as interações onde a condição de bug se aplica (elemento em modal), o sistema fixado gera seletores com escopo de modal e o executor resolve corretamente sem fallback de coordenadas.

**Pseudocode:**
```
FOR ALL interaction WHERE isBugCondition(interaction.element, interaction.capturedSelector) DO
  capturedSelector := capture_with_modal_detection(interaction.element)
  ASSERT capturedSelector contains modal scope prefix
  
  executionResult := executor.locate_and_click(capturedSelector)
  ASSERT executionResult.success = TRUE
  ASSERT executionResult.fallback_layer != "coordinates"
  ASSERT executionResult.fallback_layer IN ["brain", "sniper", "hint"]
END FOR
```

**Test Cases**:
1. **Modal Autocomplete Search Button (Fixed)**: Capturar e executar clique em botão de busca em modal — seletor deve ser `p-dialog[role="dialog"] [name='tipoTitulo'] button.button-addon` e resolver >90% das vezes
2. **Modal Table Row Selection (Fixed)**: Capturar e executar seleção de linha em tabela modal — seletor deve ser `p-dialog tr:has-text("Adiantamento Crédito")` e resolver corretamente
3. **Multiple Modals Scenario**: Capturar interações em cenário com múltiplos modais abertos sequencialmente — seletores devem ser únicos e não conflitar
4. **Modal Close and Reopen**: Capturar interação, fechar modal, reabrir e executar — seletor deve continuar válido após re-renderização

### Preservation Checking

**Goal**: Verificar que para todas as interações onde a condição de bug NÃO se aplica (elementos fora de modais), o sistema fixado produz exatamente o mesmo resultado que o sistema original.

**Pseudocode:**
```
FOR ALL interaction WHERE NOT isBugCondition(interaction.element, interaction.capturedSelector) DO
  selectorOriginal := capture_original(interaction.element)
  selectorFixed    := capture_fixed(interaction.element)
  
  ASSERT selectorOriginal = selectorFixed
  
  executionOriginal := executor_original.locate_and_click(selectorOriginal)
  executionFixed    := executor_fixed.locate_and_click(selectorFixed)
  
  ASSERT executionOriginal.success = executionFixed.success
  ASSERT executionOriginal.fallback_layer = executionFixed.fallback_layer
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente cobrindo diferentes tipos de componentes PrimeNG fora de modais
- Detecta edge cases que testes manuais podem perder (ex: autocomplete aninhado em tab panel, calendar em accordion)
- Fornece garantias fortes de que o comportamento não mudou para toda a superfície de entrada não-modal

**Test Plan**: Observar comportamento no código UNFIXED para componentes PrimeNG em formulários principais, depois escrever testes property-based que capturam esse comportamento e verificam que o código FIXED preserva exatamente os mesmos seletores e taxas de sucesso.

**Test Cases**:
1. **Main Form Autocomplete Preservation**: Observar que autocomplete em formulário principal gera `[name='campo'] button` no unfixed, verificar que fixed gera o mesmo (sem prefixo de modal)
2. **Calendar Trigger Preservation**: Observar que calendar trigger em formulário principal gera `[name='data'] button` no unfixed, verificar que fixed preserva
3. **Dropdown Trigger Preservation**: Observar que dropdown em formulário principal gera `.ui-dropdown-trigger` ancorado em identificador, verificar que fixed preserva
4. **Checkbox in Non-Modal Table Preservation**: Observar que checkbox em tabela não-modal usa `:has-text()` no unfixed, verificar que fixed preserva essa estratégia

### Unit Tests

- Testar função `detectModalAncestor(element)` isoladamente com elementos dentro e fora de modais
- Testar geração de prefixo de escopo de modal com diferentes tipos de diálogos (p-dialog, ui-dialog, s-dialog)
- Testar extração de identificador estável de modal (role, aria-labelledby)
- Testar função `_gerar_candidatos()` com hints que contêm escopo de modal vs hints sem escopo
- Testar priorização de candidatos (candidatos com escopo de modal devem vir primeiro)

### Property-Based Tests

- Gerar elementos aleatórios dentro de modais PrimeNG e verificar que seletores sempre incluem escopo
- Gerar elementos aleatórios fora de modais e verificar que seletores nunca incluem escopo de modal
- Gerar configurações aleatórias de múltiplos modais aninhados e verificar que escopo mais específico é usado
- Gerar workflows aleatórios com mix de interações modais e não-modais e verificar taxa de sucesso >90% sem coordenadas

### Integration Tests

- Testar fluxo completo: captura → geração de roteiro → execução do robot em workflow real do Senior X com modais
- Testar cenário de múltiplos modais abertos sequencialmente (modal de busca → modal de detalhes → modal de confirmação)
- Testar cenário de modal dentro de iframe (se aplicável no Senior X)
- Testar que feedback visual do cursor_engine funciona corretamente para elementos em modais
- Testar que telemetria do Brain registra corretamente acertos/falhas para seletores com escopo de modal

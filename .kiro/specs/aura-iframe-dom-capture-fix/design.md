# Aura Iframe DOM Capture Fix - Bugfix Design

## Overview

O `AuraDomMapper.capturar()` atualmente ignora elementos dentro de iframes, capturando apenas elementos do documento principal. Isso resulta em contexto incompleto para a IA, especialmente no Senior X onde o conteúdo principal (como o GED iframe `ecm_sign`) está dentro de iframes.

A estratégia de correção é adaptar a lógica de iteração sobre iframes já implementada e testada no `AuraSpotlight.encontrarElemento()` para o `AuraDomMapper.capturar()`, preservando completamente o formato de saída atual e garantindo backward compatibility total.

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug - quando há iframes acessíveis na página mas o DOM context não inclui elementos deles
- **Property (P)**: O comportamento desejado quando iframes acessíveis estão presentes - elementos dentro deles devem ser capturados e incluídos no DOM context
- **Preservation**: Comportamento existente de captura de elementos do documento principal e formato de saída que devem permanecer inalterados
- **AuraDomMapper.capturar()**: A função em `extension/modules/aura_dom_mapper.js` que captura elementos interativos visíveis e retorna string formatada para consumo pela IA
- **data-aura-map**: Atributo usado para mapear elementos capturados com índices únicos, permitindo referência posterior para highlight e interação
- **Same-origin iframe**: Iframe que compartilha a mesma origem (protocolo, domínio, porta) do documento principal, permitindo acesso ao contentDocument
- **Cross-origin iframe**: Iframe de origem diferente que lança SecurityError ao tentar acessar contentDocument sem permissões adequadas

## Bug Details

### Bug Condition

O bug se manifesta quando há iframes acessíveis (same-origin ou com permissões) na página, mas o `AuraDomMapper.capturar()` não itera sobre eles para capturar seus elementos interativos. O resultado é um DOM context incompleto que não representa o estado real da tela.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type PageContext
  OUTPUT: boolean
  
  RETURN input.page_has_iframes = true
         AND input.at_least_one_iframe_is_accessible = true
         AND input.dom_context_includes_iframe_elements = false
END FUNCTION
```

### Examples

- **Exemplo 1 - GED no Senior X**: Usuário está na tela do GED (iframe `ecm_sign`). Esperado: capturar botões "Novo Documento", "Buscar documentos", etc. Atual: captura apenas header/sidebar do documento principal.

- **Exemplo 2 - Formulário em iframe**: Página com formulário dentro de iframe. Esperado: capturar inputs, selects, buttons do formulário. Atual: captura apenas elementos fora do iframe.

- **Exemplo 3 - Múltiplos iframes**: Página com 3 iframes acessíveis. Esperado: capturar elementos de todos os 3 iframes + documento principal. Atual: captura apenas documento principal.

- **Edge case - Iframe cross-origin**: Página com iframe inacessível (cross-origin sem permissões). Esperado: capturar elementos do documento principal sem falhar. Atual: já funciona corretamente (não tenta acessar iframes).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Captura de elementos do documento principal deve continuar funcionando exatamente como antes
- Formato da string de saída deve permanecer idêntico: `[ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}"`
- Lógica de filtragem de duplicatas baseada em texto deve continuar funcionando
- Atribuição de `data-aura-map` com índices únicos deve continuar funcionando
- Ignorar elementos dentro do container da própria extensão AURA deve continuar funcionando
- Lógica de visibilidade (bounding box) deve continuar funcionando

**Scope:**
Todas as páginas que NÃO possuem iframes acessíveis devem ter saída completamente idêntica à versão atual. Isso inclui:
- Páginas sem iframes
- Páginas com iframes cross-origin inacessíveis
- Páginas onde todos os iframes estão vazios ou sem elementos interativos

## Hypothesized Root Cause

Baseado na análise do código e no histórico ("nas versões passadas ele já analisava o iframe normalmente"), as causas mais prováveis são:

1. **Remoção acidental da lógica de iframe**: Em alguma refatoração anterior, a lógica de iteração sobre iframes foi removida do `AuraDomMapper.capturar()`, enquanto foi preservada no `AuraSpotlight.encontrarElemento()`

2. **Implementação incompleta**: A funcionalidade de captura de iframes nunca foi implementada no `AuraDomMapper`, apenas no `AuraSpotlight`, criando inconsistência entre os dois módulos

3. **Separação de responsabilidades mal executada**: Durante a reestruturação da AURA (feature `aura-dap-restructure`), a lógica de iframe pode ter sido centralizada apenas no Spotlight, assumindo incorretamente que o DomMapper não precisaria dela

4. **Falta de testes de regressão**: Ausência de testes automatizados permitiu que a funcionalidade de iframe fosse perdida sem detecção imediata

## Correctness Properties

Property 1: Bug Condition - Iframe Element Capture

_For any_ page context where iframes acessíveis estão presentes (isBugCondition returns true), a função corrigida `AuraDomMapper.capturar()` SHALL iterar sobre todos os iframes acessíveis, capturar elementos interativos visíveis dentro deles, e incluí-los no DOM context retornado com indicador de iframe.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Non-Iframe Page Behavior

_For any_ page context onde iframes acessíveis NÃO estão presentes (isBugCondition returns false), a função corrigida `AuraDomMapper.capturar()` SHALL produzir exatamente a mesma saída que a função original, preservando formato, índices, e comportamento de captura do documento principal.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Changes Required

Assumindo que nossa análise de causa raiz está correta:

**File**: `extension/modules/aura_dom_mapper.js`

**Function**: `capturar()`

**Specific Changes**:

1. **Adicionar função auxiliar para captura em documento**:
   - Extrair a lógica atual de captura em uma função `capturarEmDocumento(doc, frameInfo, startIndex)`
   - `frameInfo` será `null` para documento principal ou objeto `{ name: string }` para iframes
   - `startIndex` permite continuar índices globais únicos

2. **Implementar iteração sobre iframes**:
   - Após capturar elementos do documento principal, iterar sobre `document.querySelectorAll('iframe')`
   - Para cada iframe, usar try-catch para acessar `frame.contentDocument || frame.contentWindow.document`
   - Se acessível, chamar `capturarEmDocumento()` passando o frameDoc e frameInfo

3. **Adicionar indicador de iframe na saída**:
   - Modificar formato de saída para incluir `(iframe: ${frameName})` quando elemento vem de iframe
   - Exemplo: `[ID: 300] TIPO: button | TEXTO: "Novo Documento" (iframe: ecm_sign)`
   - Manter formato original para elementos do documento principal

4. **Preservar índices únicos globais**:
   - Usar contador global que incrementa através de documento principal e todos os iframes
   - Não reiniciar índices para cada iframe
   - Garantir que `data-aura-map` continue sendo único em toda a página

5. **Tratar exceções cross-origin silenciosamente**:
   - Envolver acesso a `contentDocument` em try-catch
   - Continuar iteração normalmente se acesso falhar
   - Não logar erros ou expor informações sensíveis

6. **Garantir ordem de captura**:
   - Capturar elementos do documento principal primeiro
   - Depois capturar elementos de iframes na ordem em que aparecem no DOM
   - Isso garante que elementos principais tenham IDs menores (mais estáveis)

## Testing Strategy

### Validation Approach

A estratégia de teste segue abordagem de duas fases: primeiro, demonstrar o bug no código não corrigido através de testes exploratórios, depois verificar que a correção funciona e preserva comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotetisar.

**Test Plan**: Criar páginas HTML de teste com iframes acessíveis (same-origin), carregar a extensão AURA não corrigida, executar `AuraDomMapper.capturar()` no console, e observar que elementos dentro de iframes não aparecem na saída.

**Test Cases**:
1. **Single Iframe Test**: Página com 1 iframe contendo 3 botões (falhará no código não corrigido - botões não aparecem)
2. **Multiple Iframes Test**: Página com 3 iframes, cada um com elementos diferentes (falhará no código não corrigido - nenhum elemento de iframe aparece)
3. **Mixed Content Test**: Página com elementos no documento principal E dentro de iframe (falhará parcialmente - apenas elementos principais aparecem)
4. **Cross-Origin Iframe Test**: Página com iframe cross-origin inacessível (pode passar ou falhar dependendo de como erro é tratado)

**Expected Counterexamples**:
- Elementos dentro de iframes não aparecem na string retornada por `capturar()`
- Possíveis causas: ausência de iteração sobre iframes, exceção não tratada ao acessar contentDocument, lógica de seletor não aplicada a frameDoc

### Fix Checking

**Goal**: Verificar que para todas as páginas onde a condição de bug existe, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL pageContext WHERE isBugCondition(pageContext) DO
  dom_context := AuraDomMapper.capturar'(pageContext)
  ASSERT dom_context.includes_iframe_elements = true
  ASSERT dom_context.iframe_element_count > 0
  ASSERT dom_context.format_is_correct = true
  ASSERT dom_context.iframe_indicator_present = true
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as páginas onde a condição de bug NÃO existe, a função corrigida produz exatamente o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL pageContext WHERE NOT isBugCondition(pageContext) DO
  ASSERT AuraDomMapper.capturar(pageContext) = AuraDomMapper.capturar'(pageContext)
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente através do domínio de entrada
- Captura edge cases que testes unitários manuais podem perder
- Fornece garantias fortes de que comportamento permanece inalterado para todas as páginas sem iframes

**Test Plan**: Observar comportamento no código NÃO CORRIGIDO primeiro para páginas sem iframes, depois escrever testes baseados em propriedades capturando esse comportamento.

**Test Cases**:
1. **No Iframe Preservation**: Observar que páginas sem iframes produzem saída específica no código não corrigido, depois verificar que código corrigido produz saída idêntica
2. **Cross-Origin Iframe Preservation**: Observar que páginas com iframes inacessíveis não falham no código não corrigido, depois verificar que código corrigido mantém esse comportamento
3. **Empty Iframe Preservation**: Observar que iframes vazios não adicionam elementos no código não corrigido, depois verificar que código corrigido mantém esse comportamento
4. **Extension Container Exclusion Preservation**: Observar que elementos dentro do container AURA são ignorados no código não corrigido, depois verificar que código corrigido mantém essa exclusão

### Unit Tests

- Testar captura de elementos em documento principal (sem iframes)
- Testar captura de elementos em single iframe acessível
- Testar captura de elementos em múltiplos iframes acessíveis
- Testar que iframes cross-origin não causam falha
- Testar que índices globais são únicos através de documento principal e iframes
- Testar que formato de saída inclui indicador de iframe corretamente
- Testar que elementos do container AURA continuam sendo ignorados
- Testar que duplicatas baseadas em texto continuam sendo filtradas

### Property-Based Tests

- Gerar páginas aleatórias com número variável de iframes (0-5) e elementos (0-20 por documento/iframe), verificar que todos os elementos acessíveis são capturados
- Gerar configurações aleatórias de visibilidade (bounding box), verificar que apenas elementos visíveis são capturados
- Gerar páginas aleatórias sem iframes, verificar que saída é idêntica entre versão original e corrigida
- Testar através de muitos cenários que índices `data-aura-map` permanecem únicos globalmente

### Integration Tests

- Testar fluxo completo: capturar DOM context em página com iframe do Senior X GED, enviar ao backend, verificar que IA identifica corretamente a localização
- Testar que `AuraSpotlight.aplicar()` consegue aplicar highlight em elementos capturados de iframes
- Testar switching entre contextos (documento principal → iframe → documento principal) e verificar que captura funciona em todos os contextos
- Testar que feedback visual (sonar highlight) ocorre corretamente quando elementos de iframe são referenciados

# Executor Seletor Hint Priority Fix - Bugfix Design

## Overview

O executor Python (`vision_engine.py`) está ignorando o campo `seletor_hint` do roteiro JSON e priorizando candidatos baseados em `label_curto` (texto visual cosmético) na função `_gerar_candidatos()`. Isso causa falhas de execução mesmo quando o sistema de captura JavaScript está gerando seletores corretos e específicos.

A estratégia de fix é adicionar `seletor_hint` como candidato de alta prioridade (primeiras 3 posições) na lista de candidatos quando ele está presente, não é vazio, não é frágil, e `label_curto` é genérico. Isso garante que seletores semânticos capturados sejam tentados antes de candidatos baseados em texto visual, aumentando a taxa de sucesso de >28% para >90%.

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug - quando `seletor_hint` válido e não-frágil é ignorado em favor de candidatos baseados em `label_curto` genérico
- **Property (P)**: O comportamento desejado - `seletor_hint` deve ser adicionado como candidato de alta prioridade e tentado antes de candidatos baseados em `label_curto`
- **Preservation**: Comportamento existente que deve permanecer inalterado - quando `seletor_hint` está ausente, vazio ou frágil, usar `label_curto` como atualmente
- **_gerar_candidatos()**: A função em `vision_engine.py` (linhas ~553-720) que gera a lista ordenada de estratégias de localização de elementos
- **seletor_hint**: Campo do roteiro JSON que contém o seletor CSS capturado pelo JavaScript (ex: `[name='e070emp'] button`)
- **label_curto**: Campo do roteiro JSON que contém o texto visual do elemento (ex: `ui-btn`, `Selecionar`)
- **TentativaLocalizacao**: Estrutura de dados que representa um candidato de localização com seletor, iframe_hint, e descrição
- **_e_seletor_fragil()**: Função que detecta se um seletor é frágil (tag genérica sem atributos identificadores)
- **_TAGS_FRAGEIS**: Conjunto de tags HTML consideradas frágeis: `button`, `input`, `span`, `div`, etc.
- **Sniper Semântico**: Camada de localização que usa seletores CSS específicos antes de escalar para coordenadas

## Bug Details

### Bug Condition

O bug manifesta quando o executor recebe um roteiro JSON com `seletor_hint` válido e não-frágil, mas gera candidatos baseados em `label_curto` genérico que são tentados primeiro na cascata de localização. Isso causa falha de identidade quando múltiplos elementos correspondem ao texto genérico, escalando para fallback de coordenadas com baixa taxa de sucesso.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type AcaoTecnica (ação técnica do roteiro)
  OUTPUT: boolean
  
  // Extrai campos relevantes
  alvo := input.elemento_alvo
  seletor_hint := alvo.seletor_hint
  label_curto := alvo.label_curto
  
  // Bug ocorre quando:
  // 1. seletor_hint está presente e não é vazio
  // 2. seletor_hint não é frágil (não é tag genérica sem atributos)
  // 3. label_curto é genérico ou ambíguo (tag frágil ou texto cosmético)
  // 4. Executor gera candidatos usando label_curto antes de seletor_hint
  
  RETURN (
    seletor_hint IS NOT NULL AND
    seletor_hint ≠ "" AND
    NOT _e_seletor_fragil(seletor_hint) AND
    (label_curto IN _TAGS_FRAGEIS OR 
     label_curto é genérico como "ui-btn", "button", "span", "Selecionar")
  )
END FUNCTION
```

### Examples

**Exemplo 1: Botão de busca PrimeNG (Lupa) - FORA de modal**

```json
{
  "label_curto": "ui-btn",
  "seletor_hint": "[name='e070emp'] button",
  "primeng_component": "p-autocomplete:search_button"
}
```

**Comportamento Atual (Buggy)**:
- Executor gera candidatos: `text="ui-btn"`, `[aria-label='ui-btn']`, `button:has-text('ui-btn')`
- Encontra 5+ elementos com texto "ui-btn" na página (múltiplas lupas)
- Falha na verificação de identidade: "esperado 'ui-btn', encontrado 'Centro de custos'"
- Escala para coordenadas capturadas (28% de sucesso)
- Log: `[Sniper] 5 candidatos para 'ui-btn'...`

**Comportamento Esperado (Fixed)**:
- Executor adiciona `[name='e070emp'] button` como primeiro candidato (posição 0)
- Tenta o seletor composto PrimeNG primeiro
- Sucesso na primeira tentativa (>90% de sucesso)
- Log: `[Sniper] Tentando '[name='e070emp'] button' (PrimeNG hint priority)...`

**Exemplo 2: Botão "Selecionar" em modal PrimeNG**

```json
{
  "label_curto": "Selecionar",
  "seletor_hint": "p-dialog[role=\"dialog\"] button#e070emp-select-button",
  "primeng_component": "p-dialog:modal_button"
}
```

**Comportamento Atual (Buggy)**:
- Executor gera candidatos: `text="Selecionar"`, `button:has-text('Selecionar')`, `[role='button'][name='Selecionar']`
- Pode encontrar múltiplos botões "Selecionar" (dentro e fora de modais, em diferentes modais)
- Clica no botão errado ou falha na verificação de identidade
- Escala para coordenadas que podem clicar no botão errado

**Comportamento Esperado (Fixed)**:
- Executor adiciona `p-dialog[role="dialog"] button#e070emp-select-button` como primeiro candidato
- Escopa a busca dentro do modal correto usando o prefixo `p-dialog[role="dialog"]`
- Clica no botão correto dentro do modal específico
- Sucesso na primeira tentativa

**Exemplo 3: Input de texto com label genérico**

```json
{
  "label_curto": "input",
  "seletor_hint": "input[name='e070emp']",
  "tipo_elemento": "input"
}
```

**Comportamento Atual (Buggy)**:
- Executor gera candidatos: `getByLabel('input')`, `[aria-label='input']`, `text="input"`
- Não encontra elemento ou encontra elemento errado
- Escala para coordenadas

**Comportamento Esperado (Fixed)**:
- Executor adiciona `input[name='e070emp']` como primeiro candidato
- Localiza o input correto pelo atributo `name`
- Sucesso na primeira tentativa

**Exemplo 4: Edge case - seletor_hint frágil (deve preservar comportamento atual)**

```json
{
  "label_curto": "Confirmar",
  "seletor_hint": "button",
  "tipo_elemento": "button"
}
```

**Comportamento Atual e Esperado (Preservation)**:
- `_e_seletor_fragil("button")` retorna `True` (tag genérica sem atributos)
- Executor NÃO adiciona `button` como candidato de alta prioridade
- Usa candidatos baseados em `label_curto`: `text="Confirmar"`, `button:has-text('Confirmar')`
- Comportamento permanece inalterado (preservation)

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Mouse clicks e interações manuais devem continuar funcionando exatamente como antes
- Casos especiais já implementados (checkboxes PrimeNG, dialogs de confirmação, widgets compostos) devem continuar funcionando
- Verificação de identidade antes de executar ação deve continuar sendo aplicada
- Escalação para Gemini Vision quando todas as camadas falham deve continuar funcionando
- Telemetria e aprendizado de longo prazo no Brain devem continuar usando a mesma lógica

**Scope:**
Todas as ações técnicas que NÃO envolvem `seletor_hint` válido e não-frágil devem ser completamente não afetadas por este fix. Isso inclui:
- Ações onde `seletor_hint` está ausente ou vazio
- Ações onde `seletor_hint` é frágil (tag genérica sem atributos)
- Ações onde `label_curto` não é genérico (texto específico e único)
- Casos especiais já tratados (checkboxes, dialogs, widgets PrimeNG compostos)

## Hypothesized Root Cause

Baseado na análise do código e dos logs de execução, as causas mais prováveis são:

1. **Ordem de Priorização Incorreta**: A função `_gerar_candidatos()` atualmente:
   - Verifica casos especiais (checkboxes, dialogs, widgets PrimeNG) usando `seletor_hint` ✅
   - Depois gera candidatos genéricos usando `label_curto` (text=, getByRole, aria-label) ❌
   - Adiciona `seletor_hint` genérico apenas implicitamente em camadas posteriores ❌
   
   O problema é que candidatos baseados em `label_curto` são tentados ANTES do `seletor_hint` na cascata, mesmo quando `seletor_hint` é mais específico e confiável.

2. **Falta de Candidato Explícito para seletor_hint Genérico**: A função trata casos especiais (checkboxes, dialogs, widgets compostos) mas não adiciona `seletor_hint` como candidato de alta prioridade quando ele é válido mas não se encaixa em nenhum caso especial.

3. **Dependência Excessiva de label_curto**: O código assume que `label_curto` é uma boa fonte de candidatos, mas em aplicações PrimeNG/Angular, `label_curto` frequentemente contém apenas texto cosmético interno (`ui-btn`, `ui-button-text`) que não é único na página.

4. **Ausência de Validação de Genericidade de label_curto**: O código verifica se `label_curto` está em `_TAGS_FRAGEIS` mas não detecta textos genéricos como `ui-btn`, `button`, `span` que são igualmente problemáticos.

## Correctness Properties

Property 1: Bug Condition - Priorização de seletor_hint

_For any_ ação técnica onde o bug condition holds (seletor_hint está presente, não é vazio, não é frágil, e label_curto é genérico), a função _gerar_candidatos corrigida SHALL adicionar seletor_hint como candidato de alta prioridade nas primeiras 3 posições da lista de candidatos, garantindo que seja tentado antes de candidatos baseados em label_curto.

**Validates: Requirements 2.1, 2.2, 2.4**

Property 2: Preservation - Comportamento Inalterado para Casos Não-Buggy

_For any_ ação técnica onde o bug condition does NOT hold (seletor_hint está ausente, vazio, frágil, ou label_curto não é genérico), a função _gerar_candidatos corrigida SHALL produzir exatamente a mesma lista de candidatos que a função original, preservando todo o comportamento existente de localização e fallback.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assumindo que nossa análise de causa raiz está correta:

**File**: `vision_engine.py`

**Function**: `_gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)`

**Specific Changes**:

1. **Adicionar Detecção de label_curto Genérico**: Criar função helper para detectar se `label_curto` é genérico/cosmético
   - Verificar se está em `_TAGS_FRAGEIS`
   - Verificar se corresponde a padrões PrimeNG comuns: `ui-btn`, `ui-button-text`, `ui-clickable`, etc.
   - Verificar se é texto muito curto (< 3 caracteres) ou muito genérico (`button`, `span`, `div`)

2. **Adicionar Candidato de Alta Prioridade para seletor_hint**: Após os casos especiais existentes (checkboxes, dialogs, widgets compostos), adicionar lógica:
   ```python
   # Se seletor_hint é válido, não-frágil, e label_curto é genérico,
   # adiciona seletor_hint como candidato de alta prioridade
   if seletor_hint and not _e_seletor_fragil(seletor_hint) and _e_label_generico(label_curto):
       candidatos.append(TentativaLocalizacao(
           seletor=seletor_hint,
           iframe_hint=iframe_hint,
           descricao=f"seletor_hint priority '{seletor_hint[:60]}'",
       ))
   ```

3. **Posicionamento Estratégico**: Inserir este candidato APÓS os casos especiais (checkboxes, dialogs, widgets compostos) mas ANTES dos candidatos baseados em `label_curto` (text=, getByRole, aria-label)
   - Posição ideal: após linha ~630 (após casos especiais) e antes da linha ~632 (antes de candidatos de label_curto)

4. **Preservar Casos Especiais Existentes**: Não modificar a lógica de casos especiais que já funciona:
   - Checkboxes PrimeNG (`.ui-chkbox`, `p-checkbox`)
   - Dialogs de confirmação (`p-confirmdialog`, `p-dialog`)
   - Widgets compostos PrimeNG (`p-autocomplete`, `p-calendar`, etc.)

5. **Adicionar Logging para Debugging**: Adicionar log quando candidato de alta prioridade é adicionado:
   ```python
   logger.debug(f"[Sniper] Adicionando seletor_hint como alta prioridade: {seletor_hint[:60]}")
   ```

### Implementation Pseudocode

```python
def _e_label_generico(label: str) -> bool:
    """Detecta se label_curto é genérico/cosmético e não deve ser priorizado."""
    if not label:
        return True
    
    label_lower = label.strip().lower()
    
    # Tags HTML genéricas
    if label_lower in _TAGS_FRAGEIS:
        return True
    
    # Textos PrimeNG cosmético internos
    TEXTOS_PRIMENG_COSMETICOS = {
        "ui-btn", "ui-button", "ui-button-text", "ui-clickable",
        "ui-widget", "ui-state-default", "p-button", "p-element"
    }
    if label_lower in TEXTOS_PRIMENG_COSMETICOS:
        return True
    
    # Textos muito curtos ou genéricos
    if len(label) < 3:
        return True
    
    return False


def _gerar_candidatos(...) -> list[TentativaLocalizacao]:
    candidatos: list[TentativaLocalizacao] = []
    
    # ... (casos especiais existentes: checkboxes, dialogs, widgets compostos) ...
    
    # ── NOVO: Candidato de alta prioridade para seletor_hint ──────────────────
    # Quando seletor_hint é válido, não-frágil, e label_curto é genérico,
    # adiciona seletor_hint como candidato de alta prioridade
    if (seletor_hint and 
        not _e_seletor_fragil(seletor_hint) and 
        _e_label_generico(label_curto)):
        
        logger.debug(f"[Sniper] Adicionando seletor_hint como alta prioridade: {seletor_hint[:60]}")
        candidatos.append(TentativaLocalizacao(
            seletor=seletor_hint,
            iframe_hint=iframe_hint,
            descricao=f"seletor_hint priority '{seletor_hint[:60]}'",
        ))
    
    # ... (continua com candidatos baseados em label_curto) ...
    
    return candidatos
```

## Testing Strategy

### Validation Approach

A estratégia de teste segue uma abordagem de duas fases: primeiro, demonstrar o bug no código não corrigido através de testes exploratórios que falham, depois verificar que o fix funciona corretamente e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES de implementar o fix. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotizar.

**Test Plan**: Escrever testes que simulam ações técnicas com `seletor_hint` válido e `label_curto` genérico, e verificar que a função `_gerar_candidatos()` NÃO adiciona `seletor_hint` como candidato de alta prioridade. Executar estes testes no código NÃO CORRIGIDO para observar falhas e confirmar o problema.

**Test Cases**:
1. **Botão PrimeNG com label genérico** (falhará no código não corrigido)
   - Input: `seletor_hint="[name='e070emp'] button"`, `label_curto="ui-btn"`
   - Verificar: candidatos NÃO contém `[name='e070emp'] button` nas primeiras 3 posições
   - Verificar: primeiro candidato é baseado em `label_curto` (ex: `text="ui-btn"`)

2. **Botão em modal com label genérico** (falhará no código não corrigido)
   - Input: `seletor_hint="p-dialog[role='dialog'] button#e070emp-select-button"`, `label_curto="Selecionar"`
   - Verificar: candidatos NÃO contém o seletor completo do modal nas primeiras 3 posições
   - Verificar: primeiro candidato é baseado em `label_curto` (ex: `text="Selecionar"`)

3. **Input com label genérico** (falhará no código não corrigido)
   - Input: `seletor_hint="input[name='e070emp']"`, `label_curto="input"`
   - Verificar: candidatos NÃO contém `input[name='e070emp']` nas primeiras 3 posições
   - Verificar: primeiro candidato é baseado em `label_curto` (ex: `getByLabel('input')`)

4. **Edge case: seletor_hint frágil** (deve passar mesmo no código não corrigido - preservation)
   - Input: `seletor_hint="button"`, `label_curto="Confirmar"`
   - Verificar: candidatos NÃO contém `button` como candidato de alta prioridade
   - Verificar: comportamento é baseado em `label_curto` (preservation)

**Expected Counterexamples**:
- Candidatos baseados em `label_curto` genérico aparecem antes de `seletor_hint` específico
- `seletor_hint` válido não é adicionado como candidato explícito de alta prioridade
- Possíveis causas confirmadas: ordem de priorização incorreta, falta de candidato explícito para `seletor_hint` genérico

### Fix Checking

**Goal**: Verificar que para todas as ações técnicas onde o bug condition holds, a função corrigida adiciona `seletor_hint` como candidato de alta prioridade e o tenta antes de candidatos baseados em `label_curto`.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  candidatos := _gerar_candidatos'(input.seletor_hint, input.label_curto, ...)
  
  // Verifica que seletor_hint foi adicionado como candidato de alta prioridade
  ASSERT EXISTS candidato IN candidatos WHERE (
    candidato.seletor = input.seletor_hint AND
    index_of(candidatos, candidato) < 3
  )
  
  // Verifica que candidatos baseados em label_curto vêm DEPOIS
  idx_hint := index_of(candidatos, candidato com seletor_hint)
  idx_label := index_of(candidatos, primeiro candidato com label_curto)
  
  ASSERT idx_hint < idx_label OR idx_label = -1
  
  // Verifica que a descrição indica prioridade
  ASSERT candidato.descricao CONTAINS "priority" OR "hint priority"
END FOR
```

**Test Cases**:
1. **Botão PrimeNG com label genérico** (deve passar no código corrigido)
   - Input: `seletor_hint="[name='e070emp'] button"`, `label_curto="ui-btn"`
   - Verificar: `[name='e070emp'] button` está nas primeiras 3 posições
   - Verificar: vem antes de candidatos baseados em `ui-btn`

2. **Botão em modal com label genérico** (deve passar no código corrigido)
   - Input: `seletor_hint="p-dialog[role='dialog'] button#e070emp-select-button"`, `label_curto="Selecionar"`
   - Verificar: seletor completo do modal está nas primeiras 3 posições
   - Verificar: vem antes de candidatos baseados em `Selecionar`

3. **Input com label genérico** (deve passar no código corrigido)
   - Input: `seletor_hint="input[name='e070emp']"`, `label_curto="input"`
   - Verificar: `input[name='e070emp']` está nas primeiras 3 posições
   - Verificar: vem antes de candidatos baseados em `input`

### Preservation Checking

**Goal**: Verificar que para todas as ações técnicas onde o bug condition NÃO holds, a função corrigida produz exatamente a mesma lista de candidatos que a função original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  // F = função original (antes do fix)
  // F' = função corrigida (depois do fix)
  
  candidatos_original := _gerar_candidatos(input.seletor_hint, input.label_curto, ...)
  candidatos_corrigido := _gerar_candidatos'(input.seletor_hint, input.label_curto, ...)
  
  // Comportamento deve ser idêntico quando:
  // - seletor_hint está ausente/vazio
  // - seletor_hint é frágil
  // - label_curto não é genérico
  
  ASSERT candidatos_original = candidatos_corrigido
  ASSERT len(candidatos_original) = len(candidatos_corrigido)
  ASSERT FOR ALL i, candidatos_original[i].seletor = candidatos_corrigido[i].seletor
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente através do domínio de entrada
- Captura edge cases que testes unitários manuais podem perder
- Fornece garantias fortes de que o comportamento é inalterado para todas as entradas não-buggy

**Test Plan**: Observar comportamento no código NÃO CORRIGIDO primeiro para casos de preservation, depois escrever testes property-based capturando esse comportamento.

**Test Cases**:
1. **seletor_hint ausente** (deve preservar comportamento)
   - Input: `seletor_hint=""`, `label_curto="Confirmar"`
   - Verificar: candidatos são idênticos antes e depois do fix

2. **seletor_hint frágil** (deve preservar comportamento)
   - Input: `seletor_hint="button"`, `label_curto="Confirmar"`
   - Verificar: candidatos são idênticos antes e depois do fix

3. **label_curto específico** (deve preservar comportamento)
   - Input: `seletor_hint="button#generic"`, `label_curto="Confirmar Pedido de Venda"`
   - Verificar: candidatos são idênticos antes e depois do fix

4. **Casos especiais existentes** (deve preservar comportamento)
   - Checkboxes PrimeNG: `seletor_hint="item:has-text('Pasta') .ui-chkbox"`
   - Dialogs de confirmação: `label_curto="Sim"` em `p-confirmdialog`
   - Widgets compostos: `seletor_hint="[name='e070emp'] button"` com `p-autocomplete`
   - Verificar: casos especiais continuam sendo tratados como antes

### Unit Tests

- Testar `_e_label_generico()` com diversos inputs (tags HTML, textos PrimeNG, textos curtos, textos específicos)
- Testar `_gerar_candidatos()` com combinações de `seletor_hint` válido/inválido e `label_curto` genérico/específico
- Testar edge cases (seletor_hint vazio, None, frágil; label_curto vazio, None, específico)
- Testar que casos especiais existentes (checkboxes, dialogs, widgets) não são afetados

### Property-Based Tests

- Gerar ações técnicas aleatórias e verificar que `seletor_hint` válido é sempre priorizado quando `label_curto` é genérico
- Gerar configurações aleatórias de roteiro e verificar que preservation é mantida para casos não-buggy
- Testar que a ordem de candidatos é consistente através de muitos cenários

### Integration Tests

- Testar fluxo completo de execução com roteiro real contendo botões PrimeNG com `label_curto` genérico
- Testar que taxa de sucesso aumenta de ~28% para >90% após o fix
- Testar que logs mostram tentativa de `seletor_hint` antes de `label_curto`
- Testar que redução de escalações para fallback de coordenadas ocorre

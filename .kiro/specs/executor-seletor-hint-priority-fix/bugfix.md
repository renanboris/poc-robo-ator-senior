# Bugfix Requirements Document

## Introduction

O executor Python (`vision_engine.py`) está ignorando o campo `seletor_hint` do JSON do roteiro e usando o campo `label_curto` (que é apenas um texto visual cosmético) para buscar elementos na interface. Isso causa falhas na execução mesmo quando o sistema de captura JavaScript está gerando seletores corretos.

**Impacto**: Taxa de sucesso da execução caiu para ~28% (deveria ser >90%), causando workflows automatizados não funcionarem corretamente e forçando o sistema a cair em fallback de coordenadas que falha frequentemente.

**Evidência**: Logs mostram `[Sniper] 5 candidatos para 'ui-btn'...` quando deveria estar usando `[name='e070emp'] button` do campo `seletor_hint`.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o roteiro JSON contém um `seletor_hint` válido (ex: `[name='e070emp'] button`) e um `label_curto` genérico (ex: `ui-btn`) THEN o executor usa o `label_curto` para gerar candidatos de busca ao invés de priorizar o `seletor_hint`

1.2 WHEN o executor gera candidatos usando `label_curto` genérico como `ui-btn` THEN múltiplos elementos na página correspondem ao texto, causando falha de identidade e escalando para fallback de coordenadas

1.3 WHEN o `seletor_hint` contém seletores compostos PrimeNG (ex: `[name='e070emp'] button`) THEN o executor não os prioriza adequadamente na cascata de estratégias, tentando primeiro candidatos baseados em `label_curto`

1.4 WHEN o fallback de coordenadas é acionado devido à falha dos candidatos baseados em `label_curto` THEN a taxa de sucesso cai para ~28% pois as coordenadas são menos resilientes que seletores semânticos

### Expected Behavior (Correct)

2.1 WHEN o roteiro JSON contém um `seletor_hint` válido e não-frágil THEN o executor SHALL priorizar o `seletor_hint` na geração de candidatos antes de usar `label_curto`

2.2 WHEN o `seletor_hint` contém seletores compostos PrimeNG (ex: `[name='e070emp'] button`) THEN o executor SHALL adicioná-los como candidatos de alta prioridade na camada Sniper Semântico

2.3 WHEN o `seletor_hint` é válido mas frágil (tag genérica sem atributos identificadores) THEN o executor SHALL usar `label_curto` como estratégia complementar, não como substituto

2.4 WHEN o executor gera candidatos de busca THEN o executor SHALL usar `seletor_hint` como fonte primária de seletores e `label_curto` apenas para validação de identidade ou como fallback

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o `seletor_hint` está ausente ou vazio no roteiro JSON THEN o executor SHALL CONTINUE TO usar `label_curto` para gerar candidatos como faz atualmente

3.2 WHEN o `seletor_hint` é detectado como frágil pela função `_e_seletor_fragil()` THEN o executor SHALL CONTINUE TO escalar para outras estratégias (Sniper, Coordenadas, etc.)

3.3 WHEN candidatos baseados em `label_curto` são gerados (getByRole, getByLabel, text=) THEN o executor SHALL CONTINUE TO aplicar verificação de identidade antes de executar a ação

3.4 WHEN o `seletor_hint` contém checkboxes PrimeNG (`.ui-chkbox`) ou botões em modais (`p-dialog`) THEN o executor SHALL CONTINUE TO tratá-los como candidatos especiais de alta prioridade

3.5 WHEN todas as camadas de localização falham THEN o executor SHALL CONTINUE TO escalar para Gemini Vision como última camada de self-healing

3.6 WHEN o executor registra sucesso ou falha no Brain THEN o executor SHALL CONTINUE TO usar a mesma lógica de telemetria e aprendizado de longo prazo


---

## Bug Condition Analysis

### Bug Condition Function

A condição de bug ocorre quando o executor recebe um roteiro com `seletor_hint` válido mas prioriza `label_curto` na geração de candidatos:

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AcaoTecnica
  OUTPUT: boolean
  
  // Extrai campos relevantes
  alvo ← X.elemento_alvo
  seletor_hint ← alvo.seletor_hint
  label_curto ← alvo.label_curto
  
  // Bug ocorre quando:
  // 1. seletor_hint está presente e não é vazio
  // 2. seletor_hint não é frágil (não é tag genérica)
  // 3. label_curto é genérico ou ambíguo
  // 4. Executor usa label_curto ao invés de seletor_hint
  
  RETURN (
    seletor_hint IS NOT NULL AND
    seletor_hint ≠ "" AND
    NOT _e_seletor_fragil(seletor_hint) AND
    (label_curto IN _TAGS_FRAGEIS OR 
     label_curto é genérico como "ui-btn", "button", "span")
  )
END FUNCTION
```

### Property Specification - Fix Checking

Para todas as ações técnicas onde a condição de bug é verdadeira, o executor corrigido deve priorizar `seletor_hint`:

```pascal
// Property: Fix Checking - Priorização de seletor_hint
FOR ALL X WHERE isBugCondition(X) DO
  candidatos ← _gerar_candidatos'(X)
  
  // Verifica que seletor_hint foi adicionado como candidato de alta prioridade
  ASSERT EXISTS candidato IN candidatos WHERE (
    candidato.seletor = X.elemento_alvo.seletor_hint AND
    candidato está nas primeiras 3 posições da lista
  )
  
  // Verifica que candidatos baseados em label_curto vêm DEPOIS
  idx_hint ← index_of(candidatos, candidato com seletor_hint)
  idx_label ← index_of(candidatos, primeiro candidato com label_curto)
  
  ASSERT idx_hint < idx_label OR idx_label = -1
  
  // Verifica que a execução tenta seletor_hint antes de label_curto
  resultado ← encontrar_e_clicar'(X)
  ASSERT log contém tentativa de seletor_hint antes de tentativa de label_curto
END FOR
```

### Property Specification - Preservation Checking

Para todas as ações técnicas onde a condição de bug NÃO é verdadeira, o comportamento deve permanecer inalterado:

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  // F = função original (antes do fix)
  // F' = função corrigida (depois do fix)
  
  candidatos_original ← _gerar_candidatos(X)
  candidatos_corrigido ← _gerar_candidatos'(X)
  
  // Comportamento deve ser idêntico quando:
  // - seletor_hint está ausente/vazio
  // - seletor_hint é frágil
  // - label_curto não é genérico
  
  ASSERT candidatos_original = candidatos_corrigido
  ASSERT encontrar_e_clicar(X) = encontrar_e_clicar'(X)
END FOR
```

### Counterexamples

**Exemplo 1: Botão de busca PrimeNG (Lupa)**

```json
{
  "label_curto": "ui-btn",
  "seletor_hint": "[name='e070emp'] button",
  "primeng_component": "p-autocomplete:search_button"
}
```

**Comportamento Atual (Buggy)**:
- Executor gera candidatos: `text="ui-btn"`, `[aria-label='ui-btn']`, etc.
- Encontra 5+ elementos com texto "ui-btn" na página
- Falha na verificação de identidade
- Escala para coordenadas (28% de sucesso)

**Comportamento Esperado (Fixed)**:
- Executor adiciona `[name='e070emp'] button` como primeiro candidato
- Tenta o seletor composto PrimeNG primeiro
- Sucesso na primeira tentativa (>90% de sucesso)

**Exemplo 2: Botão "Selecionar" em modal**

```json
{
  "label_curto": "Selecionar",
  "seletor_hint": "p-dialog[role=\"dialog\"] button#e070emp-select-button",
  "primeng_component": "p-dialog:modal_button"
}
```

**Comportamento Atual (Buggy)**:
- Executor gera candidatos: `text="Selecionar"`, `button:has-text('Selecionar')`, etc.
- Pode encontrar múltiplos botões "Selecionar" (dentro e fora de modais)
- Clica no botão errado ou falha

**Comportamento Esperado (Fixed)**:
- Executor adiciona `p-dialog[role="dialog"] button#e070emp-select-button` como primeiro candidato
- Escopa a busca dentro do modal correto
- Clica no botão correto dentro do modal

---

## Technical Context

### Affected Module
- **File**: `vision_engine.py`
- **Function**: `_gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)`
- **Lines**: ~553-720

### Root Cause
A função `_gerar_candidatos()` atualmente:
1. Verifica casos especiais (checkboxes, dialogs, PrimeNG widgets) usando `seletor_hint`
2. Depois gera candidatos genéricos usando `label_curto` (text=, getByRole, aria-label)
3. Adiciona `seletor_hint` apenas no final, na Camada 3 (após Sniper e Coordenadas)

O problema é que candidatos baseados em `label_curto` são tentados ANTES do `seletor_hint` na cascata, mesmo quando `seletor_hint` é mais específico e confiável.

### Proposed Fix Strategy
1. **Adicionar `seletor_hint` como candidato de alta prioridade** na função `_gerar_candidatos()`
2. **Inserir candidato de `seletor_hint` no início da lista** quando não é frágil
3. **Manter casos especiais** (checkboxes, dialogs, PrimeNG) que já usam `seletor_hint` corretamente
4. **Preservar fallback para `label_curto`** quando `seletor_hint` está ausente ou é frágil

### Success Criteria
- Taxa de sucesso da execução: >90% (atualmente ~28%)
- Logs mostram tentativa de `seletor_hint` antes de `label_curto`
- Redução de escalações para fallback de coordenadas
- Nenhuma regressão em casos onde `seletor_hint` está ausente

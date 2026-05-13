# Fase 3: Adicionar modal_context ao JSON - COMPLETA ✅

## Data
2026-05-08

## Status
✅ **FASE 3 COMPLETA**

## O Que Foi Feito

### 1. Adicionado Campo modal_context ao JSON
- **Arquivo modificado**: `capture_variants/radar_script.js`
- **Função modificada**: `processarEvento(target, acao, valor)`
- **Localização**: Antes da chamada `window.capturarElemento()`

### 2. Código Adicionado

```javascript
// Detect modal context for telemetry
const modalAncestor = target.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
const modalContext = modalAncestor ? {
    type: modalAncestor.tagName.toLowerCase(),
    role: modalAncestor.getAttribute('role') || '',
    visible: modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0
} : null;

window.capturarElemento(JSON.stringify({
    // ... campos existentes ...
    modal_context: modalContext,  // ← NOVO CAMPO
    // ... outros campos ...
}));
```

### 3. Estrutura do Campo modal_context

**Quando elemento está FORA de modal**:
```json
{
    "modal_context": null
}
```

**Quando elemento está DENTRO de modal**:
```json
{
    "modal_context": {
        "type": "p-dialog",
        "role": "dialog",
        "visible": true
    }
}
```

### 4. Campos do modal_context

- **type**: Tag HTML do modal em lowercase (ex: `p-dialog`, `ui-dialog`, `div`)
- **role**: Atributo `role` do modal (ex: `dialog`, vazio se não tiver)
- **visible**: `true` se modal está visível (`aria-hidden !== 'true'` e `width > 0`), `false` caso contrário

## Como Testar

### 1. Capturar Workflow com Modal

```bash
# Via dashboard (recomendado)
python capture_variants/capture_dual_output.py "Teste Modal Context" "Workflow com modal" --auto
```

### 2. Verificar Roteiro JSON Gerado

1. Após captura, abrir o arquivo JSON gerado em `roteiros_salvos/`
2. Procurar por ações capturadas
3. Verificar campo `modal_context` em cada ação

### 3. Exemplos de JSON Esperado

**Ação em elemento FORA de modal**:
```json
{
    "id_acao": 1,
    "acao": "clique",
    "elemento_alvo": {
        "seletor_hint": "button.ui-btn",
        "modal_context": null
    }
}
```

**Ação em botão DENTRO de modal**:
```json
{
    "id_acao": 2,
    "acao": "clique",
    "elemento_alvo": {
        "seletor_hint": "button.button-addon",
        "modal_context": {
            "type": "p-dialog",
            "role": "dialog",
            "visible": true
        }
    }
}
```

**Ação em linha de tabela em modal**:
```json
{
    "id_acao": 3,
    "acao": "clique",
    "elemento_alvo": {
        "seletor_hint": "tr:has-text('Código 123')",
        "modal_context": {
            "type": "p-dialog",
            "role": "dialog",
            "visible": true
        }
    }
}
```

## Critério de Sucesso

- ✅ Campo `modal_context` aparece no JSON capturado
- ✅ `modal_context: null` quando elemento está fora de modal
- ✅ `modal_context: { type, role, visible }` quando elemento está em modal
- ✅ `type` contém tag do modal em lowercase
- ✅ `role` contém atributo role do modal
- ✅ `visible: true` para modais visíveis, `false` para ocultos
- ✅ Captura continua funcionando normalmente

## Validação

### Cenários de Teste

1. **Botão em modal de busca**:
   - Abrir modal de busca
   - Clicar no botão de pesquisa
   - Verificar JSON: `modal_context: { type: "p-dialog", role: "dialog", visible: true }`

2. **Linha de tabela em modal**:
   - Abrir modal com tabela
   - Clicar em uma linha
   - Verificar JSON: `modal_context` presente com informações corretas

3. **Botão fora de modal**:
   - Clicar em botão na tela principal
   - Verificar JSON: `modal_context: null`

4. **Input em modal**:
   - Digitar em campo dentro de modal
   - Verificar JSON: `modal_context` presente

## Rollback (se necessário)

```bash
# Reverter apenas radar_script.js
git checkout HEAD -- capture_variants/radar_script.js
```

## Próximos Passos

### Fase 4: Modificar Seletores com Escopo (30 min) 🎯 SOLUÇÃO REAL
- Modificar `capture_variants/radar_script.js`
- Adicionar prefixo de modal aos seletores em `resolvePrimeNGComponent()`
- Modificar todos os returns da função para incluir escopo de modal
- Tratar casos especiais:
  - Tabelas em modais (`tr`, `td`)
  - Botões em modais
  - Inputs em modais
- Executar testes:
  - `python -m pytest test_primeng_preservation.py -v` (deve passar: 5/5)
  - `python -m pytest test_primeng_modal_bug_exploration.py -v` (deve passar: 5/5)
- Capturar workflow real e verificar seletores
- Medir taxa de sucesso (esperado: >90% vs. 26% atual)

---

**Status**: ✅ FASE 3 COMPLETA  
**Risco**: BAIXO (apenas adiciona campo ao JSON, não muda comportamento)  
**Impacto**: ZERO (campo é informativo, não afeta execução ainda)  
**Próxima Ação**: Fase 4 - Modificar seletores com escopo de modal (SOLUÇÃO REAL)


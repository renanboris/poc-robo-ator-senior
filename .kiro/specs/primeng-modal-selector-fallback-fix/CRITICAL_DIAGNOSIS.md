# DIAGNÓSTICO CRÍTICO - Detecção de Modal Não Funciona

## Data: 2026-05-08
## Status: PROBLEMA CRÍTICO IDENTIFICADO

## Resumo Executivo

A detecção de modal está implementada no JavaScript (`radar_script.js`), mas **NÃO está funcionando**. Análise do roteiro capturado mostra:

- **0 seletores com prefixo `p-dialog`** (esperado: ~6 seletores)
- **6 seletores genéricos `ui-btn`** (sem escopo de modal)
- **Campo `modal_context` NUNCA aparece no JSON final**

## Evidências do Log

```
[ROBÔ BASTIDORES]: ERROR: [DEBUG] ERRO ao injetar script radar: Frame.evaluate: Frame was detached
[ROBÔ BASTIDORES]: ERROR: [DEBUG] ERRO ao injetar script radar: Frame.evaluate: Frame was detached
[ROBÔ BASTIDORES]: ERROR: [DEBUG] ERRO ao injetar script radar: Frame.evaluate: Frame was detached
```

**3 erros de injeção em frames** - o script não está sendo injetado nos iframes onde os modais aparecem.

## Análise do Roteiro Capturado

### Arquivo: `roteiros_salvos/ERP_X_-_Incluindo_um_titulo_no_Financeir.json`

**Seletores capturados:**
```json
"label_curto": "ui-btn"  // Linha 159 - SEM prefixo p-dialog
"label_curto": "ui-btn"  // Linha 251 - SEM prefixo p-dialog
"label_curto": "ui-btn"  // Linha 343 - SEM prefixo p-dialog
"label_curto": "ui-btn"  // Linha 409 - SEM prefixo p-dialog
"label_curto": "ui-btn"  // Linha 501 - SEM prefixo p-dialog
"label_curto": "ui-btn"  // Linha 593 - SEM prefixo p-dialog
```

**Busca por `p-dialog`:** 0 resultados
**Busca por `modal_context`:** 0 resultados

## Análise do Código JavaScript

### Função `resolvePrimeNGComponent()` - Linhas 95-200

**Detecção de modal implementada:**
```javascript
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
console.log('[MODAL DEBUG]', {
    hasModal: !!modalAncestor,
    modalType: modalAncestor?.tagName,
    modalRole: modalAncestor?.getAttribute('role'),
    element: el.tagName,
    elementClass: el.className
});
```

**Função `addModalScope()` implementada:**
```javascript
const addModalScope = (seletor) => {
    if (!modalAncestor) return seletor;
    
    const isVisible = modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0;
    
    if (!isVisible) return seletor;
    
    const modalScope = modalAncestor.getAttribute('role') === 'dialog' 
        ? 'p-dialog[role="dialog"]' 
        : modalAncestor.tagName.toLowerCase();
    
    return `${modalScope} ${seletor}`;
};
```

**Aplicação em todos os 4 returns:**
- Linha 122: `return { seletor: addModalScope(...), ... }`
- Linha 175: `return { seletor: addModalScope(...), ... }`
- Linha 181: `return { seletor: addModalScope(...), ... }`
- Linha 185: `return { seletor: addModalScope(...), ... }`

### Função `processarEvento()` - Linhas 295-320

**Campo `modal_context` adicionado:**
```javascript
const modalAncestor = target.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
const modalContext = modalAncestor ? {
    type: modalAncestor.tagName.toLowerCase(),
    role: modalAncestor.getAttribute('role') || '',
    visible: modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0
} : null;

window.capturarElemento(JSON.stringify({
    // ... outros campos ...
    modal_context: modalContext,
    // ... outros campos ...
}));
```

## Causa Raiz Identificada

### PROBLEMA 1: Script não está sendo injetado nos iframes

**Evidência:**
- 3 erros `Frame.evaluate: Frame was detached` por captura
- Modais PrimeNG são renderizados em **overlays dinâmicos**, não necessariamente em iframes
- Mas o erro indica que há frames sendo criados/destruídos rapidamente

**Hipótese:**
- Os modais podem estar em um **CDK overlay** ou **portal** que é criado dinamicamente
- O script está tentando injetar em frames que são destruídos antes da injeção completar
- O retry logic (100ms → 300ms → 600ms) não é suficiente

### PROBLEMA 2: Modais podem não ser iframes

**Análise:**
- PrimeNG usa `<p-dialog>` que é renderizado como um **overlay direto no DOM**
- Não é um iframe, mas um elemento posicionado com `position: fixed` ou `absolute`
- O script deveria funcionar no **main frame** sem precisar de injeção em iframes

### PROBLEMA 3: Console logs não aparecem

**Evidência:**
- Nenhum log `[MODAL DEBUG]` aparece no output
- Isso indica que a função `resolvePrimeNGComponent()` **não está sendo chamada**
- Ou o console.log está sendo suprimido

## Hipóteses Prioritárias

### Hipótese #1: Script não está sendo carregado (MAIS PROVÁVEL)
- O arquivo `radar_script.js` não está sendo lido corretamente
- Erro de sintaxe JavaScript que quebra silenciosamente
- Cache do navegador usando versão antiga

### Hipótese #2: Função não está sendo chamada
- O fluxo de execução não passa por `resolvePrimeNGComponent()`
- O fallback genérico está sendo usado antes
- A ordem de verificação está errada

### Hipótese #3: Seletor de modal está errado
- `el.closest('p-dialog, ...')` não encontra o modal
- O modal tem uma estrutura DOM diferente
- O modal está em um shadow DOM

## Próximos Passos de Investigação

### PASSO 1: Verificar se o script está sendo carregado
```javascript
// Adicionar no INÍCIO do radar_script.js (linha 6)
console.log('[RADAR] Script loaded successfully');
window.__radarVersion = '2.0.0';
```

### PASSO 2: Verificar se a função está sendo chamada
```javascript
// Adicionar no início de resolvePrimeNGComponent() (linha 96)
console.log('[RADAR] resolvePrimeNGComponent called', el.tagName, el.className);
```

### PASSO 3: Verificar estrutura DOM do modal
```javascript
// Adicionar em processarEvento() antes de capturar
console.log('[RADAR] Element ancestors:', 
    Array.from(target.parentElement?.children || []).map(c => c.tagName)
);
```

### PASSO 4: Verificar se modal_context está no JSON
```python
# Adicionar em capture_dual_output.py após receber evento
print(f"[DEBUG] Evento recebido: {evento_json[:200]}")
```

## Ações Recomendadas

### AÇÃO IMEDIATA: Adicionar logging de diagnóstico
1. Adicionar `console.log` no início do script
2. Adicionar `console.log` em `resolvePrimeNGComponent()`
3. Adicionar `console.log` em `processarEvento()`
4. Rodar nova captura com console aberto (F12)

### AÇÃO SECUNDÁRIA: Verificar cache do navegador
1. Limpar cache do Playwright
2. Adicionar `--disable-cache` nas opções do navegador
3. Verificar se `radar_script.js` está sendo lido do disco

### AÇÃO TERCIÁRIA: Simplificar teste
1. Criar página HTML simples com modal PrimeNG
2. Testar detecção de modal isoladamente
3. Verificar se `el.closest('p-dialog')` funciona

## Conclusão

O código de detecção de modal está **implementado corretamente** no JavaScript, mas **não está sendo executado**. O problema mais provável é:

1. **Script não está sendo carregado** (cache, erro de sintaxe, path errado)
2. **Função não está sendo chamada** (ordem de execução errada)
3. **Console logs estão sendo suprimidos** (configuração do Playwright)

A próxima iteração deve focar em **adicionar logging de diagnóstico** para identificar onde o fluxo está quebrando.

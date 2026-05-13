# INSTRUÇÕES DE TESTE - Diagnóstico de Detecção de Modal

## Objetivo

Identificar por que a detecção de modal não está funcionando, mesmo com o código implementado corretamente.

## Mudanças Aplicadas

Adicionei **logging extensivo** no `radar_script.js` para rastrear a execução:

### 1. Logging de Carregamento do Script (Linhas 5-15)
```javascript
console.log('[RADAR] ========================================');
console.log('[RADAR] Script loading - Version 2.1.0');
console.log('[RADAR] Timestamp:', new Date().toISOString());
console.log('[RADAR] ========================================');
```

**O que verificar:** Se este log aparecer, o script está sendo carregado.

### 2. Logging em `resolvePrimeNGComponent()` (Linhas 98-104)
```javascript
console.log('[RADAR] resolvePrimeNGComponent called', {
    tag: el.tagName,
    className: el.className,
    id: el.id
});
```

**O que verificar:** Se este log aparecer, a função está sendo chamada.

### 3. Logging em `processarEvento()` (Linhas 302-318)
```javascript
console.log('[RADAR] processarEvento called', { ... });
console.log('[RADAR] PrimeNG result:', _pResult);
console.log('[RADAR] Final selector:', _seletor);
console.log('[RADAR] Modal context:', modalContext);
```

**O que verificar:** Se estes logs aparecerem, o evento está sendo processado.

## Como Testar

### PASSO 1: Abrir Console do Navegador

1. Iniciar captura normalmente
2. **ANTES de clicar em qualquer coisa**, pressionar **F12** para abrir DevTools
3. Ir para a aba **Console**
4. Verificar se aparece:
   ```
   [RADAR] ========================================
   [RADAR] Script loading - Version 2.1.0
   [RADAR] Timestamp: 2026-05-08T...
   [RADAR] ========================================
   [RADAR] Script injected successfully
   ```

**Se NÃO aparecer:** O script não está sendo carregado (problema de cache ou path).

**Se aparecer:** O script está carregado, prosseguir para PASSO 2.

### PASSO 2: Clicar em Elemento Fora do Modal

1. Clicar em qualquer elemento da página principal (ex: menu lateral)
2. Verificar no console se aparece:
   ```
   [RADAR] processarEvento called { action: 'clique', tag: 'SPAN', ... }
   [RADAR] resolvePrimeNGComponent called { tag: 'SPAN', ... }
   [MODAL DEBUG] { hasModal: false, ... }
   [RADAR] PrimeNG result: null
   [RADAR] Final selector: ...
   [RADAR] Modal context: null
   ```

**Se NÃO aparecer:** A função `processarEvento()` não está sendo chamada (problema de event listener).

**Se aparecer:** O fluxo está funcionando, prosseguir para PASSO 3.

### PASSO 3: Abrir Modal e Clicar Dentro

1. Clicar em um botão que abre modal (ex: "Incluir títulos")
2. **Aguardar modal abrir completamente**
3. Clicar em um botão dentro do modal (ex: botão de busca)
4. Verificar no console se aparece:
   ```
   [RADAR] processarEvento called { action: 'clique', tag: 'BUTTON', ... }
   [RADAR] resolvePrimeNGComponent called { tag: 'BUTTON', ... }
   [MODAL DEBUG] { hasModal: true, modalType: 'P-DIALOG', ... }
   [RADAR] PrimeNG result: { seletor: 'p-dialog ...', ... }
   [RADAR] Final selector: p-dialog ...
   [RADAR] Modal context: { type: 'p-dialog', role: 'dialog', visible: true }
   ```

**Se `hasModal: false`:** O seletor `el.closest('p-dialog, ...')` não está encontrando o modal.

**Se `hasModal: true` mas `seletor` não tem prefixo:** A função `addModalScope()` não está sendo aplicada.

**Se tudo aparecer correto:** O problema está no Python, não no JavaScript.

## Cenários Possíveis

### Cenário A: Nenhum log aparece
**Causa:** Script não está sendo carregado.
**Solução:** 
- Limpar cache do navegador
- Verificar se `radar_script.js` está no path correto
- Verificar se há erro de sintaxe JavaScript

### Cenário B: Logs aparecem, mas `hasModal: false`
**Causa:** Estrutura DOM do modal é diferente do esperado.
**Solução:**
- Inspecionar elemento do modal no DevTools
- Verificar se é `<p-dialog>` ou outro componente
- Ajustar seletor em `el.closest(...)`

### Cenário C: Logs aparecem, `hasModal: true`, mas seletor sem prefixo
**Causa:** Função `addModalScope()` não está sendo aplicada.
**Solução:**
- Verificar se `modalAncestor` está visível (`aria-hidden !== 'true'`)
- Verificar se `getBoundingClientRect().width > 0`
- Adicionar mais logging em `addModalScope()`

### Cenário D: Logs aparecem corretos, mas roteiro sem prefixo
**Causa:** Problema no Python ao processar o JSON.
**Solução:**
- Verificar se `modal_context` está no JSON recebido
- Verificar se Python está usando o campo correto
- Adicionar logging em `capture_dual_output.py`

## Próximos Passos Após Teste

1. **Copiar TODOS os logs do console** (Ctrl+A, Ctrl+C)
2. **Colar em um arquivo de texto** para análise
3. **Identificar qual cenário ocorreu** (A, B, C ou D)
4. **Reportar resultado** com os logs completos

## Comandos Úteis no Console

### Verificar se script está carregado:
```javascript
window.__radarVersion
// Deve retornar: "2.1.0"
```

### Verificar se função existe:
```javascript
typeof resolvePrimeNGComponent
// Deve retornar: "function"
```

### Testar detecção de modal manualmente:
```javascript
// Clicar em elemento dentro do modal e executar:
$0.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]')
// Deve retornar: <p-dialog> ou null
```

## Observações Importantes

- **Manter console aberto durante TODA a captura**
- **NÃO fechar DevTools** até terminar
- **Copiar logs ANTES de fechar o navegador**
- **Testar com pelo menos 3 cliques dentro do modal**

## Resultado Esperado

Se tudo estiver funcionando, você deve ver:
- ✅ Script carregado com sucesso
- ✅ Função `processarEvento()` chamada em cada clique
- ✅ Função `resolvePrimeNGComponent()` chamada
- ✅ `hasModal: true` para cliques dentro do modal
- ✅ Seletor com prefixo `p-dialog` no log
- ✅ `modal_context` não-nulo no log

Se algum desses itens falhar, temos o ponto exato onde o problema está ocorrendo.

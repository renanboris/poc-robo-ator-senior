# Plano para Solução CORRETA - Detecção de Modal na Captura

## Date
2026-05-08

## Decisão
Após feedback do usuário, ficou claro que a solução no `vision_engine.py` era apenas um **band-aid** que não resolve a causa raiz. O problema REAL está na **captura**, não na execução.

## Problema Raiz

**Captura Atual**:
```javascript
// Usuário clica em botão dentro de modal
el.closest('button')  // Encontra: <button class="ui-btn">
// Gera: "button.ui-btn"  ❌ AMBÍGUO (existe 4x no DOM)
```

**Captura Correta**:
```javascript
// Usuário clica em botão dentro de modal
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog');
if (modalAncestor) {
    // Gera: "p-dialog button.ui-btn"  ✅ ÚNICO
}
```

## Por Que as Tentativas Anteriores Falharam

### Problema: JavaScript Inline em Python String
```python
script_radar = """() => {
    // JavaScript com escape complexo
    text.replace(/\\s+/g, ' ')  // Precisa escape duplo
    const modalAncestor = ...    // Conflitos de escopo
}"""
```

**Problemas**:
- ❌ Escape de strings Python → JavaScript é propenso a erros
- ❌ Regex quebram facilmente (`/\s+/` vira `/s+/`)
- ❌ Difícil de debugar (erro só aparece no navegador)
- ❌ Sem validação de sintaxe (ESLint, etc.)
- ❌ Conflitos de escopo difíceis de detectar

## Solução CORRETA: JavaScript em Arquivo Separado

### Estrutura
```
capture_variants/
├── capture_dual_output.py
└── radar_script.js  ← NOVO: JavaScript puro, sem escape
```

### Vantagens
✅ **Sem problemas de escape** - JavaScript puro, sem strings Python  
✅ **Validação de sintaxe** - Pode usar ESLint, JSHint, etc.  
✅ **Fácil de testar** - Copiar/colar no console do navegador  
✅ **Fácil de debugar** - Erros claros, sem confusão Python/JS  
✅ **Manutenível** - Código limpo, sem triple-quotes  
✅ **Versionável** - Git diff mostra mudanças JavaScript claramente  

## Plano de Implementação

### Fase 1: Extração (15 min)
1. Extrair JavaScript atual de `capture_dual_output.py`
2. Salvar em `capture_variants/radar_script.js`
3. Modificar Python para carregar do arquivo:
   ```python
   script_path = Path(__file__).parent / "radar_script.js"
   with open(script_path, 'r', encoding='utf-8') as f:
       script_radar = f"() => {{ {f.read()} }}"
   ```
4. **Testar**: Verificar que captura ainda funciona (sem mudanças)

### Fase 2: Validação (10 min)
1. Validar sintaxe JavaScript:
   ```bash
   # Opção 1: Node.js
   node -c radar_script.js
   
   # Opção 2: Online
   # Copiar código para https://jshint.com/
   ```
2. Testar no console do navegador
3. Confirmar que não há erros de sintaxe

### Fase 3: Implementação Incremental (1-2h)

#### Commit 1: Adicionar Logging de Modal
```javascript
// No início de resolvePrimeNGComponent()
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
console.log('[MODAL DEBUG]', {
    hasModal: !!modalAncestor,
    modalType: modalAncestor?.tagName,
    element: el.tagName
});
```

**Teste**: Capturar workflow, verificar logs no console (F12)

#### Commit 2: Adicionar modal_context ao JSON
```javascript
// No final de processarEvento()
const modalAncestor = target.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
const modalContext = modalAncestor ? {
    type: modalAncestor.tagName.toLowerCase(),
    role: modalAncestor.getAttribute('role') || '',
    visible: modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0
} : null;

window.capturarElemento(JSON.stringify({
    // ... campos existentes ...
    modal_context: modalContext  // NOVO
}));
```

**Teste**: Capturar workflow, verificar que `modal_context` aparece no JSON

#### Commit 3: Modificar Seletores com Escopo de Modal
```javascript
// Em resolvePrimeNGComponent(), após gerar seletor
if (modalAncestor) {
    const isVisible = modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0;
    
    if (isVisible) {
        const modalScope = modalAncestor.getAttribute('role') === 'dialog' 
            ? 'p-dialog[role="dialog"]' 
            : modalAncestor.tagName.toLowerCase();
        
        seletor = `${modalScope} ${seletor}`;
    }
}
```

**Teste**: Capturar workflow, verificar seletores no roteiro

#### Commit 4: Tratamento Especial para Tabelas em Modais
```javascript
// Em resolvePrimeNGComponent(), para elementos tr/td
if (modalAncestor && (el.tagName.toLowerCase() === 'tr' || el.tagName.toLowerCase() === 'td')) {
    const isVisible = modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0;
    
    if (isVisible) {
        const modalScope = modalAncestor.getAttribute('role') === 'dialog' 
            ? 'p-dialog[role="dialog"]' 
            : modalAncestor.tagName.toLowerCase();
        
        const rowText = el.textContent.trim().substring(0, 40).replace(/['"\\]/g, '');
        if (rowText) {
            return {
                seletor: `${modalScope} tr:has-text("${rowText}")`,
                componentType: `${hostId}:table_row`,
                partName: 'table_row',
                identifier: ''
            };
        }
    }
}
```

**Teste**: Capturar seleção de linha em modal, verificar seletor

### Fase 4: Validação Final (30 min)
1. Executar testes de preservação:
   ```bash
   python -m pytest test_primeng_preservation.py -v
   ```
2. Executar testes de bug exploration:
   ```bash
   python -m pytest test_primeng_modal_bug_exploration.py -v
   ```
3. Capturar workflow real com modal
4. Executar roteiro e medir taxa de sucesso

## Rollback Plan

Se algo der errado em qualquer fase:
```bash
# Reverter para estado funcional
git checkout HEAD -- capture_variants/

# Ou reverter commit específico
git revert <commit-hash>
```

## Critérios de Sucesso

### Fase 1 (Extração)
- ✅ Captura funciona exatamente como antes
- ✅ Nenhuma mudança de comportamento
- ✅ JavaScript validado sem erros de sintaxe

### Fase 2 (Logging)
- ✅ Logs aparecem no console do navegador
- ✅ Detecta corretamente quando elemento está em modal
- ✅ Captura continua funcionando normalmente

### Fase 3 (modal_context)
- ✅ Campo `modal_context` aparece no JSON capturado
- ✅ Contém informações corretas (type, role, visible)
- ✅ Captura continua funcionando normalmente

### Fase 4 (Seletores com Escopo)
- ✅ Seletores em modais incluem prefixo de modal
- ✅ Seletores fora de modais NÃO incluem prefixo
- ✅ Taxa de sucesso melhora de ~26% para >90%
- ✅ Todos os testes passam (preservação + bug exploration)

## Próximos Passos

1. **AGORA**: Extrair JavaScript para arquivo separado (Fase 1)
2. **DEPOIS**: Implementar detecção de modal incrementalmente (Fases 2-4)
3. **VALIDAR**: Testar cada mudança antes de prosseguir
4. **MEDIR**: Comparar taxa de sucesso antes/depois

---

**Status**: PRONTO PARA IMPLEMENTAÇÃO
**Abordagem**: Incremental e segura
**Risco**: BAIXO (rollback fácil em cada fase)
**Impacto Esperado**: 3-4x melhoria na taxa de sucesso em modais

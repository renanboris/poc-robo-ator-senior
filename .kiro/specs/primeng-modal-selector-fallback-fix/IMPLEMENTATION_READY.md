# Implementação Pronta para Execução - Solução Correta na Captura

## Status
✅ **PRONTO PARA IMPLEMENTAR**  
📋 **Plano completo documentado**  
🎯 **Abordagem incremental e segura**

## Contexto

Após múltiplas tentativas e feedback do usuário, ficou claro que:
- ❌ Solução no `vision_engine.py` é apenas band-aid
- ✅ Problema REAL está na captura (JavaScript)
- ✅ Solução: Extrair JavaScript para arquivo separado

## Arquivos Relevantes

### Documentação Criada
- `.kiro/specs/primeng-modal-selector-fallback-fix/PROPER_SOLUTION_PLAN.md` - Plano completo
- `.kiro/specs/primeng-modal-selector-fallback-fix/ROLLBACK_COMPLETE.md` - Histórico de tentativas
- `.kiro/specs/primeng-modal-selector-fallback-fix/bugfix.md` - Especificação do bug
- `.kiro/specs/primeng-modal-selector-fallback-fix/design.md` - Design da solução
- `.kiro/specs/primeng-modal-selector-fallback-fix/tasks.md` - Tasks

### Código a Modificar
- `capture_variants/capture_dual_output.py` - Arquivo principal
- `capture_variants/radar_script.js` - NOVO arquivo a criar

### Testes
- `test_primeng_preservation.py` - Testes de preservação (5/5 passando)
- `test_primeng_modal_bug_exploration.py` - Testes de bug (5/5 passando com código simulado)

## Implementação em 4 Fases

### FASE 1: Extrair JavaScript (15 min) ⏳ PRÓXIMO PASSO

**Objetivo**: Mover JavaScript de string Python para arquivo separado

**Passos**:
1. Ler `capture_variants/capture_dual_output.py` linhas 193-670
2. Extrair todo o conteúdo de `script_radar = """() => { ... }"""`
3. Salvar em `capture_variants/radar_script.js` (sem o wrapper `() => {}`)
4. Modificar Python para carregar do arquivo:
   ```python
   from pathlib import Path
   
   async def _injetar_em_contexto(contexto):
       script_path = Path(__file__).parent / "radar_script.js"
       with open(script_path, 'r', encoding='utf-8') as f:
           script_content = f.read()
       script_radar = f"() => {{ {script_content} }}"
       
       try:
           await contexto.evaluate(script_radar)
       except PlaywrightError as e:
           if "Target closed" not in str(e):
               raise
   ```

**Teste**:
```bash
# Capturar um workflow simples
python capture_variants/capture_dual_output.py "Teste" "Descrição" --auto

# Verificar que funciona exatamente como antes
# Deve capturar ações normalmente
```

**Critério de Sucesso**: Captura funciona exatamente como antes, sem mudanças de comportamento

---

### FASE 2: Adicionar Logging de Modal (10 min)

**Objetivo**: Detectar quando elemento está em modal (apenas logs)

**Modificar**: `capture_variants/radar_script.js`

**Adicionar no início de `resolvePrimeNGComponent()`**:
```javascript
// MODAL DETECTION: Log para debug
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
console.log('[MODAL DEBUG]', {
    hasModal: !!modalAncestor,
    modalType: modalAncestor?.tagName,
    modalRole: modalAncestor?.getAttribute('role'),
    element: el.tagName,
    elementClass: el.className
});
```

**Teste**:
```bash
# Capturar workflow com modal
# Abrir DevTools (F12) → Console
# Verificar logs [MODAL DEBUG] aparecem
# Verificar que detecta corretamente quando está em modal
```

**Critério de Sucesso**: Logs aparecem no console, detecta modal corretamente

---

### FASE 3: Adicionar modal_context ao JSON (15 min)

**Objetivo**: Capturar informações do modal no JSON

**Modificar**: `capture_variants/radar_script.js`

**No final de `processarEvento()`, antes de `window.capturarElemento()`**:
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
    tag: target.tagName.toLowerCase(),
    texto_encontrado: valor || getElementName(target),
    seletor: _seletor,
    primeng_component: _pResult ? _pResult.componentType : '',
    modal_context: modalContext,  // ← NOVO
    iframe: getFrameId(), 
    acao,
    posicao_visual: `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`,
    html_snapshot: target.outerHTML.substring(0, 300)
}));
```

**Teste**:
```bash
# Capturar workflow com modal
# Abrir roteiro JSON gerado
# Verificar que campo modal_context aparece
# Verificar valores corretos (type, role, visible)
```

**Critério de Sucesso**: Campo `modal_context` aparece no JSON com informações corretas

---

### FASE 4: Modificar Seletores com Escopo (30 min) 🎯 SOLUÇÃO REAL

**Objetivo**: Adicionar prefixo de modal aos seletores

**Modificar**: `capture_variants/radar_script.js`

**Em `resolvePrimeNGComponent()`, após gerar cada `seletor`**:

```javascript
// Exemplo: Após gerar seletor em borrowedFromInput
if (borrowedFromInput) {
    const wrapperTag = cur.tagName.toLowerCase();
    let wrapperClass = '';
    if (cur.classList.length > 0) {
        const c = Array.from(cur.classList).find(cls => cls.startsWith('ui-') || cls.startsWith('p-'));
        if (c) wrapperClass = `.${c}`;
    }
    const wrapperSel = `${wrapperTag}${wrapperClass}`;
    let seletor = `${wrapperSel}:has(${identifier}) ${suffix}`;
    
    // MODAL SCOPE: Add modal prefix if element is in modal
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
    
    return { seletor, componentType: `${hostId}:${partName}`, partName, identifier };
}
```

**Repetir para todos os returns em `resolvePrimeNGComponent()`**:
- `if (borrowedFromInput)` - linha ~360
- `if (isSameElement)` - linha ~380
- `else` (identifier found) - linha ~395
- Fallback (no identifier) - linha ~410

**Tratamento especial para tabelas**:
```javascript
// Special handling for table rows in modals
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

**Teste**:
```bash
# 1. Executar testes de preservação
python -m pytest test_primeng_preservation.py -v
# Deve passar: 5/5

# 2. Executar testes de bug exploration
python -m pytest test_primeng_modal_bug_exploration.py -v
# Deve passar: 5/5

# 3. Capturar workflow real com modal
# Verificar seletores no roteiro:
# - Elementos em modal: "p-dialog button.ui-btn"
# - Elementos fora: "button.ui-btn" (sem prefixo)

# 4. Executar roteiro
# Medir taxa de sucesso (esperado: >90%)
```

**Critério de Sucesso**: 
- ✅ Todos os testes passam
- ✅ Seletores em modais têm prefixo
- ✅ Seletores fora de modais NÃO têm prefixo
- ✅ Taxa de sucesso melhora de ~26% para >90%

---

## Rollback em Cada Fase

```bash
# Se Fase 1 falhar
git checkout HEAD -- capture_variants/

# Se Fase 2 falhar
git checkout HEAD -- capture_variants/radar_script.js

# Se Fase 3 falhar
git checkout HEAD -- capture_variants/radar_script.js

# Se Fase 4 falhar
git checkout HEAD -- capture_variants/radar_script.js
```

## Comandos Úteis

### Validar Sintaxe JavaScript
```bash
# Opção 1: Node.js (se instalado)
node -c capture_variants/radar_script.js

# Opção 2: Copiar para https://jshint.com/

# Opção 3: Testar no console do navegador (F12)
# Copiar/colar código e verificar erros
```

### Executar Testes
```bash
# Testes de preservação (não deve quebrar nada)
python -m pytest test_primeng_preservation.py -v

# Testes de bug exploration (deve resolver o problema)
python -m pytest test_primeng_modal_bug_exploration.py -v

# Todos os testes
python -m pytest test_primeng*.py -v
```

### Capturar Workflow de Teste
```bash
# Via dashboard (recomendado)
# Ou via CLI:
python capture_variants/capture_dual_output.py "Teste Modal" "Workflow com modal" --auto
```

---

## Próxima Ação

**INICIAR FASE 1**: Extrair JavaScript para arquivo separado

1. Ler `capture_variants/capture_dual_output.py` linhas 193-670
2. Extrair conteúdo de `script_radar`
3. Criar `capture_variants/radar_script.js`
4. Modificar Python para carregar do arquivo
5. Testar que captura funciona

**Tempo estimado**: 15 minutos  
**Risco**: BAIXO (apenas reorganização, sem mudanças de lógica)  
**Rollback**: Fácil (git checkout)

---

**Status**: ✅ PRONTO PARA IMPLEMENTAÇÃO  
**Documentação**: ✅ COMPLETA  
**Testes**: ✅ PRONTOS  
**Plano**: ✅ DETALHADO  
**Aprovação do Usuário**: ✅ CONFIRMADA

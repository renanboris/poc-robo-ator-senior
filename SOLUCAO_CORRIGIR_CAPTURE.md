# Solução para a Última Questão Não Finalizada - corrigir_capture.md

## 📋 Avaliação do Arquivo

### Contexto
O arquivo `corrigir_capture.md` (2.285 linhas) documenta uma extensa sessão de debugging para problemas de mapeamento de componentes PrimeNG no sistema de captura do Senior Training OS.

### Última Questão Não Finalizada

**Localização:** Linha 4.525 (final do arquivo)
**Status:** Usuário disse "continue" mas não houve resposta/conclusão

**Problema Identificado:**
O sistema de captura (`capture_dual_output.py`) falha ao mapear elementos PrimeNG dentro de modais, gerando seletores genéricos ambíguos que causam falhas no executor (`vision_engine.py`).

---

## 🔍 Análise do Problema

### Evidências dos Logs de Teste

```
[ROBÔ BASTIDORES]: INFO: [FOTO 5] | CLIQUE | ui-btn
[ROBÔ BASTIDORES]: INFO: [FOTO 9] | CLIQUE | ui-btn
```

**Sintomas:**
- Seletores genéricos capturados: `'ui-btn'` (ambíguo)
- Taxa de sucesso do fallback de coordenadas: **26.3%** (55 acertos / 209 tentativas)
- Falhas completas em ações específicas:
  - "Selecionar o tipo de título 'Adiantamento Crédito a Identificar' (ACI)" → **FALHA TOTAL**
  - "O usuário selecionou a transação com o código '90330'" → **FALHA TOTAL**

### Causa Raiz

1. **No Capture (JavaScript):**
   - `resolvePrimeNGComponent()` não detecta quando elemento está dentro de modal
   - Gera seletores sem escopo de modal
   - Resultado: seletores ambíguos que correspondem a múltiplos elementos

2. **No Executor (Python):**
   - `_gerar_candidatos()` não tenta variantes com escopo de modal
   - Recebe seletor ambíguo como hint
   - Encontra 4+ candidatos, cai em fallback de coordenadas (~26% sucesso)

---

## ✅ Solução Criada

### Spec Completo de Bugfix

**Nome:** `primeng-modal-selector-fallback-fix`  
**Tipo:** Bugfix (correção de bug existente)  
**Localização:** `.kiro/specs/primeng-modal-selector-fallback-fix/`

### Documentos Criados

#### 1. bugfix.md - Requisitos do Bug (15 cláusulas)

**Comportamento Atual (Defeituoso) - 5 cláusulas:**
1. Botões de busca em modais capturam seletor genérico `'ui-btn'`
2. Linhas de tabela em modais não geram seletor estável
3. Seletores sem escopo de modal encontram múltiplas correspondências
4. Executor cai em fallback de coordenadas com ~26% de sucesso
5. Fallback de coordenadas falha em modais dinâmicos

**Comportamento Esperado (Correto) - 5 cláusulas:**
1. Botões em modais devem gerar: `p-dialog [name='campo'] button.button-addon`
2. Linhas de tabela devem gerar: `p-dialog tr:has-text("texto único")`
3. Seletores devem ser únicos dentro do contexto do modal
4. Executor deve resolver sem fallback de coordenadas
5. Taxa de sucesso deve ser >90%

**Comportamento Inalterado (Preservação) - 5 cláusulas:**
1. Componentes PrimeNG fora de modais continuam funcionando
2. Checkboxes mantêm estratégia `:has-text()`
3. Diálogos de confirmação mantêm lógica especial
4. Cascade de fallback do executor preservado
5. Elementos HTML padrão mantêm lógica existente

#### 2. design.md - Design Técnico

**Análise de Causa Raiz (4 causas identificadas):**
1. Falta de detecção de contexto modal no `resolvePrimeNGComponent()`
2. Seletores genéricos para botões sem identificador estável
3. Ausência de variantes com escopo modal no `_gerar_candidatos()`
4. Timing de renderização assíncrona de modais

**4 Propriedades de Correção (Property-Based Testing):**
1. **Modal Scope Detection** - elementos em modais devem ter prefixo de escopo
2. **Non-Modal Preservation** - componentes fora de modais não devem ter prefixo
3. **Checkbox/Dialog Preservation** - estratégias especiais preservadas
4. **Executor Fallback Resilience** - taxa de sucesso >90% sem coordenadas

**Mudanças Técnicas Específicas:**

**Arquivo:** `capture_variants/capture_dual_output.py`  
**Função:** `resolvePrimeNGComponent()` (linha ~276)

```javascript
// 1. Detectar ancestral modal
const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');

if (modalAncestor) {
    // 2. Extrair escopo do modal
    const modalScope = modalAncestor.getAttribute('role') === 'dialog' 
        ? 'p-dialog[role="dialog"]' 
        : modalAncestor.tagName.toLowerCase();
    
    // 3. Verificar que modal está visível
    const isVisible = modalAncestor.getAttribute('aria-hidden') !== 'true' 
        && modalAncestor.getBoundingClientRect().width > 0;
    
    if (isVisible) {
        // 4. Prefixar seletor com escopo de modal
        seletor = `${modalScope} ${seletor}`;
    }
}

// 5. Tratamento especial para linhas de tabela em modais
if (modalAncestor && (el.tagName.toLowerCase() === 'tr' || el.tagName.toLowerCase() === 'td')) {
    const rowText = el.textContent.trim().substring(0, 40).replace(/['"\\]/g, '');
    return `${modalScope} tr:has-text("${rowText}")`;
}
```

**Arquivo:** `vision_engine.py`  
**Função:** `_gerar_candidatos()` (linha ~553)

```python
# 1. Detectar se hint contém escopo de modal
MODAL_PREFIXES = ["p-dialog", "ui-dialog", "s-dialog", "[role='dialog']", "p-confirmdialog"]
has_modal_scope = any(prefix in seletor_hint for prefix in MODAL_PREFIXES)

if has_modal_scope:
    # 2. Extrair escopo e seletor interno
    for prefix in MODAL_PREFIXES:
        if prefix in seletor_hint:
            parts = seletor_hint.split(prefix, 1)
            if len(parts) == 2:
                internal_selector = parts[1].strip()
                
                # 3. Gerar variantes com diferentes escopos de modal
                for modal_scope in ["p-dialog[role='dialog']", ".ui-dialog", "s-dialog", "[role='dialog']", ".p-dialog-content"]:
                    candidatos.insert(0, TentativaLocalizacao(
                        seletor=f"{modal_scope} {internal_selector}",
                        iframe_hint=iframe_hint,
                        descricao=f"modal-scoped variant '{modal_scope}'",
                    ))
            break

# 4. Candidatos para linhas de tabela em modais
if tipo_elemento in ("tr", "td") and has_modal_scope and label_curto:
    for modal_scope in ["p-dialog", ".ui-dialog", "s-dialog", "[role='dialog']"]:
        candidatos.insert(0, TentativaLocalizacao(
            seletor=f"{modal_scope} tr:has-text('{label_curto}')",
            iframe_hint=iframe_hint,
            descricao=f"modal table row '{label_curto}' em {modal_scope}",
        ))
```

#### 3. tasks.md - Plano de Implementação (15 tasks em 5 fases)

**Fase 1: Testes Exploratórios (ANTES do fix)**
- **Task 1:** Bug Condition Exploration Test
  - Escrever teste que deve **FALHAR** no código unfixed
  - Confirmar que seletores em modais são ambíguos
  - Documentar contraexemplos encontrados
  
- **Task 2:** Preservation Property Tests
  - Observar comportamento unfixed para componentes fora de modais
  - Escrever testes property-based capturando comportamento atual
  - Testes devem **PASSAR** no código unfixed (baseline a preservar)

**Fase 2: Implementação do Fix**
- **Task 3.1:** Adicionar detecção de modal no capture JavaScript
- **Task 3.2:** Adicionar geração de candidatos com escopo no executor Python
- **Task 3.3:** Melhorar fallback para botões em modais

**Fase 3: Validação**
- **Task 3.4:** Re-executar teste de bug condition (deve **PASSAR** agora)
- **Task 3.5:** Re-executar testes de preservação (devem continuar **PASSANDO**)

**Fase 4: Testes de Integração**
- **Task 4.1:** Fluxo completo capture → execution
- **Task 4.2:** Múltiplos modais sequenciais
- **Task 4.3:** Modal close/reopen
- **Task 4.4:** Async modal rendering
- **Task 4.5:** Telemetria do Brain

**Fase 5: Checkpoint Final**
- **Task 5:** Validação completa, >90% taxa de sucesso

---

## 📊 Resultados Esperados

### Antes do Fix (Situação Atual)

| Métrica | Valor |
|---------|-------|
| Seletores capturados | `'ui-btn'` (genérico) |
| Taxa de sucesso | ~26% (fallback coordenadas) |
| Seleções em modal | Falha completa |
| Candidatos por seletor | 4+ (ambíguo) |

### Depois do Fix (Esperado)

| Métrica | Valor |
|---------|-------|
| Seletores capturados | `p-dialog [name='campo'] button.button-addon` |
| Taxa de sucesso | >90% (sem fallback coordenadas) |
| Seleções em modal | Funcionando corretamente |
| Candidatos por seletor | 1 (único no contexto) |

### Exemplos de Transformação

**Botão de busca em modal:**
- ❌ Antes: `'ui-btn'` → 4+ correspondências → fallback coordenadas (26% sucesso)
- ✅ Depois: `p-dialog[role="dialog"] [name='tipoTitulo'] button.button-addon` → 1 correspondência → sucesso direto (>90%)

**Linha de tabela em modal:**
- ❌ Antes: Sem seletor estável → falha total
- ✅ Depois: `p-dialog tr:has-text("Adiantamento Crédito a Identificar")` → sucesso (>90%)

**Transação em modal:**
- ❌ Antes: Seletor sem escopo → múltiplas correspondências → falha
- ✅ Depois: `p-dialog tr:has-text("90330")` → correspondência única → sucesso (>90%)

---

## 🎯 Garantias de Preservação

### Zero Regressão em Componentes Não-Modais

**Componentes PrimeNG em formulários principais:**
- Autocomplete: continua gerando `[name='campo'] button`
- Calendar: continua gerando `[name='data'] button`
- Dropdown: continua gerando `.ui-dropdown-trigger` com âncora

**Estratégias especiais preservadas:**
- Checkboxes em tabelas: continua usando `:has-text()`
- Diálogos de confirmação: continua usando lógica especial `_SELETORES_DIALOG`
- Cascade de fallback: Brain → Sniper → Coordinates → Vision (inalterado)

---

## 📂 Estrutura dos Arquivos Criados

```
.kiro/specs/primeng-modal-selector-fallback-fix/
├── bugfix.md           # Requisitos do bug (15 cláusulas)
├── design.md           # Design técnico (4 propriedades PBT)
├── tasks.md            # Plano de implementação (15 tasks)
└── .config.kiro        # Configuração do spec
```

---

## 🚀 Como Implementar

### Passo 1: Revisar os Documentos
Todos os arquivos estão em `.kiro/specs/primeng-modal-selector-fallback-fix/`

### Passo 2: Executar as Tasks Sequencialmente

1. **Começar pela Task 1** (Bug Condition Exploration)
   - Escrever teste que deve falhar no código atual
   - Confirmar que o bug existe
   - Documentar contraexemplos

2. **Task 2** (Preservation Tests)
   - Observar comportamento atual de componentes não-modais
   - Escrever testes que devem passar no código atual

3. **Tasks 3.1-3.3** (Implementação)
   - Modificar `capture_dual_output.py`
   - Modificar `vision_engine.py`
   - Implementar detecção de modal e geração de seletores com escopo

4. **Tasks 3.4-3.5** (Validação)
   - Re-executar teste de bug condition (deve passar agora)
   - Re-executar testes de preservação (devem continuar passando)

5. **Tasks 4.1-4.5** (Integração)
   - Testar fluxos completos
   - Validar múltiplos cenários
   - Verificar telemetria

6. **Task 5** (Checkpoint)
   - Validação final
   - Confirmar >90% taxa de sucesso

### Passo 3: Validar Resultados

**Critérios de Sucesso:**
- ✅ Taxa de sucesso >90% para ações em modais
- ✅ Zero regressão em componentes não-modais
- ✅ Seletores únicos e estáveis
- ✅ Todos os testes passando

---

## 📝 Notas Importantes

### Metodologia de Bugfix com Property-Based Testing

Este spec segue rigorosamente a metodologia de bugfix:

1. **Observation First:** Observar comportamento unfixed antes de escrever testes
2. **Test Before Fix:** Escrever testes que falham no código unfixed
3. **Implement Fix:** Implementar correção
4. **Validate Fix:** Re-executar testes (devem passar agora)
5. **Preserve Behavior:** Garantir que testes de preservação continuam passando

### Property-Based Testing

Tasks 1 e 2 usam property-based testing para:
- Gerar muitos casos de teste automaticamente
- Cobrir edge cases que testes manuais podem perder
- Fornecer garantias fortes de correção e preservação

### Ordem de Execução

**CRÍTICO:** As tasks devem ser executadas na ordem sequencial:
1. Testes exploratórios ANTES do fix
2. Implementação do fix
3. Validação DEPOIS do fix
4. Testes de integração
5. Checkpoint final

---

## ✅ Conclusão

A análise do arquivo `corrigir_capture.md` está completa e a solução para a última questão não finalizada foi criada com sucesso.

**Status:** ✅ Spec completo e pronto para implementação

**Próximo Passo:** Executar as tasks sequencialmente começando pela Task 1

**Resultado Esperado:** Taxa de sucesso >90% para elementos PrimeNG em modais, com zero regressão em componentes não-modais.

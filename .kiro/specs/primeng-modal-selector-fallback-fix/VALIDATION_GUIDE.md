# Guia de Validação Manual - Fix de Injeção em Iframes

## Objetivo
Validar que o JavaScript `radar_script.js` está sendo injetado corretamente nos iframes e que a detecção de modal PrimeNG está funcionando.

## Pré-requisitos
- ✅ Testes automatizados passando (10/10)
- ✅ Código do fix aplicado
- ✅ Senior X acessível

## Passo 1: Preparar Ambiente

### 1.1 Abrir Console do Navegador
- Pressione **F12** para abrir DevTools
- Vá para a aba **Console**
- Deixe o console aberto durante toda a captura

### 1.2 Limpar Console
- Clique no ícone 🚫 (Clear console) ou pressione **Ctrl+L**

## Passo 2: Iniciar Captura

### 2.1 Iniciar via Dashboard
```bash
# Abrir dashboard
python app.py

# Ou via CLI
python capture_variants/capture_dual_output.py "Teste Modal" "Workflow com modal" --auto
```

### 2.2 Aguardar Login
- Aguarde o navegador abrir
- Faça login no Senior X se necessário
- Aguarde o toast "MAPEAMENTO ATIVO" aparecer

## Passo 3: Validar Injeção Principal

### 3.1 Verificar Logs de Injeção
No console, procure por:

```
[DEBUG] Main page binding verification: { hasWindowBinding: true, hasGlobalBinding: true, radarInjected: true }
```

✅ **ESPERADO**: `radarInjected: true`  
❌ **PROBLEMA**: Se `radarInjected: false`, o script não foi injetado

### 3.2 Verificar Frames Existentes
No console, procure por:

```
[DEBUG] Radar injected in existing frame: https://...
```

✅ **ESPERADO**: Mensagem para cada frame existente  
⚠️ **NORMAL**: Pode não haver frames no início

## Passo 4: Interagir com Modal

### 4.1 Abrir um Modal PrimeNG
- Clique em um botão que abre modal (ex: "Novo", "Editar", "Pesquisar")
- Aguarde o modal aparecer completamente

### 4.2 Verificar Injeção no Frame do Modal
No console, procure por:

```
[DEBUG] ✅ Radar injected successfully in frame: https://...
```

✅ **ESPERADO**: Mensagem aparece quando modal abre  
❌ **PROBLEMA**: Se não aparecer, o frame não foi injetado

### 4.3 Clicar em Elemento Dentro do Modal
- Clique em um botão dentro do modal (ex: "Confirmar", "Pesquisar", "Salvar")

### 4.4 Verificar Logs de Detecção de Modal
No console, procure por:

```
[MODAL DEBUG] {
  hasModal: true,
  modalType: "P-DIALOG",
  modalRole: "dialog",
  element: "BUTTON",
  elementClass: "ui-btn"
}
```

✅ **ESPERADO**: `hasModal: true` e `modalType` preenchido  
❌ **PROBLEMA**: Se `hasModal: false`, a detecção falhou

## Passo 5: Validar JSON Capturado

### 5.1 Fechar Navegador
- Feche o navegador para finalizar a captura
- Aguarde o processamento do roteiro

### 5.2 Localizar Roteiro Gerado
```bash
# Procurar roteiro mais recente
ls -lt roteiros_salvos/ | head -5

# Ou procurar por nome
ls roteiros_salvos/*Teste_Modal*.json
```

### 5.3 Verificar Campo modal_context
```bash
# Procurar campo modal_context no roteiro
grep -A 5 "modal_context" roteiros_salvos/Teste_Modal*.json
```

✅ **ESPERADO**:
```json
"modal_context": {
  "type": "p-dialog",
  "role": "dialog",
  "visible": true
}
```

❌ **PROBLEMA**: Se não encontrar, o campo não foi capturado

### 5.4 Verificar Seletores com Escopo
```bash
# Procurar seletores com prefixo de modal
grep "p-dialog\[role=\"dialog\"\]" roteiros_salvos/Teste_Modal*.json
```

✅ **ESPERADO**:
```json
"seletor_hint": "p-dialog[role=\"dialog\"] button.button-addon"
```

❌ **PROBLEMA**: Se seletores não tiverem prefixo, o escopo não foi aplicado

## Passo 6: Executar Roteiro

### 6.1 Executar via Dashboard
- Abra o dashboard
- Clique em "Executar" no roteiro capturado

### 6.2 Observar Execução
- Observe se o robô consegue encontrar os elementos no modal
- Conte quantas ações foram bem-sucedidas

### 6.3 Calcular Taxa de Sucesso
```
Taxa de Sucesso = (Ações Bem-Sucedidas / Total de Ações) × 100%
```

✅ **ESPERADO**: Taxa de sucesso **>90%**  
⚠️ **ATENÇÃO**: Se taxa <90%, pode haver outros problemas

## Checklist de Validação

### Injeção de JavaScript
- [ ] Log `radarInjected: true` na página principal
- [ ] Log `✅ Radar injected successfully` em frames
- [ ] Sem erros `Frame was detached` no console

### Detecção de Modal
- [ ] Log `[MODAL DEBUG]` aparece ao clicar em modal
- [ ] Campo `hasModal: true` no log
- [ ] Campo `modalType` preenchido (ex: "P-DIALOG")

### JSON Capturado
- [ ] Campo `modal_context` presente no roteiro
- [ ] Campo `modal_context.type` preenchido
- [ ] Campo `modal_context.visible: true`

### Seletores
- [ ] Seletores em modais têm prefixo `p-dialog[role="dialog"]`
- [ ] Seletores fora de modais NÃO têm prefixo
- [ ] Seletores são únicos (não ambíguos)

### Execução
- [ ] Robô encontra elementos no modal
- [ ] Taxa de sucesso >90%
- [ ] Sem fallback para coordenadas em modais

## Troubleshooting

### Problema: radarInjected: false
**Causa**: Script não foi injetado na página principal  
**Solução**: Verificar se `radar_script.js` existe e está correto

### Problema: Sem logs de injeção em frames
**Causa**: Frames não estão sendo detectados  
**Solução**: Verificar se modal realmente usa iframe

### Problema: hasModal: false
**Causa**: Elemento não está dentro de modal  
**Solução**: Verificar se modal é PrimeNG (p-dialog, ui-dialog)

### Problema: modal_context ausente no JSON
**Causa**: JavaScript não foi injetado no frame do modal  
**Solução**: Verificar logs de injeção em frames

### Problema: Seletores sem prefixo
**Causa**: Função `addModalScope()` não está sendo chamada  
**Solução**: Verificar código JavaScript em `radar_script.js`

### Problema: Taxa de sucesso <90%
**Causa**: Pode haver outros problemas além de modais  
**Solução**: Analisar logs de execução e identificar padrões de falha

## Resultados Esperados

### Antes do Fix ❌
```
Console:
  Frame.evaluate: Frame was detached
  Frame.evaluate: Frame was detached

JSON:
  "seletor_hint": "ui-btn"  ← Genérico
  (sem modal_context)

Taxa de Sucesso: ~27%
```

### Depois do Fix ✅
```
Console:
  [DEBUG] ✅ Radar injected successfully in frame
  [MODAL DEBUG] { hasModal: true, modalType: "P-DIALOG" }

JSON:
  "seletor_hint": "p-dialog[role=\"dialog\"] ui-btn"  ← Específico
  "modal_context": { "type": "p-dialog", "visible": true }

Taxa de Sucesso: >90%
```

## Próximos Passos

### Se Validação Passar ✅
1. Marcar task como completa
2. Testar em workflows de produção
3. Monitorar telemetria no `brain.db`
4. Coletar feedback dos usuários

### Se Validação Falhar ❌
1. Documentar sintomas específicos
2. Coletar logs completos do console
3. Compartilhar roteiro JSON capturado
4. Investigar causa raiz adicional

---

**Tempo Estimado**: 10-15 minutos  
**Dificuldade**: Média  
**Pré-requisitos**: Acesso ao Senior X, conhecimento básico de DevTools

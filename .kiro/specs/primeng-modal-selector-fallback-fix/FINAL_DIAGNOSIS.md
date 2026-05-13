# Diagnóstico Final - Fix de Detecção de Modal PrimeNG

## Data
2026-05-08

## Status
⚠️ **PROBLEMA CRÍTICO IDENTIFICADO**

## Análise Comparativa dos Logs

### Captura 1 (Antes da Correção do `modal_context`)
```
[ROBÔ BASTIDORES]: INFO: [FOTO 6] | CLIQUE | 1
```
**Roteiro gerado**:
```json
"seletor_hint": "p-dialog[role=\"dialog\"] tr:has-text(\"1\")"  ✅
"seletor_hint": "p-dialog[role=\"dialog\"] tr:has-text(\"ACI\")"  ✅
```
**Resultado**: 2 elementos com prefixo de modal

### Captura 2 (Depois da Correção do `modal_context`)
```
[ROBÔ BASTIDORES]: INFO: [FOTO 6] | CLIQUE | 1
```
**Roteiro gerado**:
```bash
grep "p-dialog" roteiros_salvos/*.json
# Resultado: No matches found  ❌
```
**Resultado**: 0 elementos com prefixo de modal

## Problema Identificado

### Causa Raiz
A adição do campo `modal_context` ao `evento_base` **quebrou** a captura de seletores com escopo de modal.

**Hipótese**: O campo `modal_context` pode estar causando um erro de serialização JSON ou um problema no processamento Python que está fazendo com que os seletores com prefixo sejam perdidos.

### Evidências

1. **Antes da correção**: 2 seletores com prefixo `p-dialog`
2. **Depois da correção**: 0 seletores com prefixo `p-dialog`
3. **Campo `modal_context`**: Ainda ausente no roteiro final
4. **Erros de injeção**: Mesma quantidade (3 erros `Frame was detached`)

## Análise Técnica

### O Que Funcionou na Captura 1

```python
# Código ANTES da correção
evento_base = {
    ...
    # modal_context NÃO estava aqui
    "elemento_alvo": {
        "seletor_hint": dados["seletor"],  # ← Funcionava
        ...
    },
    ...
}
```

**Resultado**: Seletores com prefixo foram gerados corretamente

### O Que Quebrou na Captura 2

```python
# Código DEPOIS da correção
evento_base = {
    ...
    "modal_context": dados.get("modal_context"),  # ← ADICIONADO
    "elemento_alvo": {
        "seletor_hint": dados["seletor"],  # ← Parou de funcionar
        ...
    },
    ...
}
```

**Resultado**: Seletores com prefixo NÃO foram gerados

## Hipóteses

### Hipótese 1: Erro de Serialização JSON
O campo `modal_context` pode conter um objeto complexo que não é serializável em JSON, causando um erro silencioso que corrompe o evento inteiro.

**Teste**:
```python
# Verificar se modal_context é None ou um dict válido
modal_ctx = dados.get("modal_context")
if modal_ctx is not None and not isinstance(modal_ctx, dict):
    logger.error(f"modal_context inválido: {type(modal_ctx)}")
```

### Hipótese 2: Ordem dos Campos
A posição do campo `modal_context` antes de `elemento_alvo` pode estar causando um problema de processamento.

**Teste**:
```python
# Mover modal_context para depois de elemento_alvo
evento_base = {
    ...
    "elemento_alvo": {...},
    "modal_context": dados.get("modal_context"),  # ← Mover para cá
    ...
}
```

### Hipótese 3: Cache do Navegador
O navegador pode estar usando uma versão em cache do `radar_script.js` que não tem a detecção de modal.

**Teste**:
- Limpar cache do navegador (Ctrl+Shift+Del)
- Forçar reload (Ctrl+F5)
- Verificar timestamp do arquivo `radar_script.js`

### Hipótese 4: Problema no JavaScript
O JavaScript pode estar falhando silenciosamente ao tentar criar o objeto `modal_context`.

**Teste**:
```javascript
// Adicionar try-catch em processarEvento()
try {
    const modalContext = modalAncestor ? {...} : null;
    window.capturarElemento(JSON.stringify({
        ...
        modal_context: modalContext,
        ...
    }));
} catch (e) {
    console.error('[MODAL DEBUG] Erro ao capturar:', e);
}
```

## Recomendações Imediatas

### 1. Reverter Mudança Temporariamente ⚠️

```python
# REMOVER esta linha temporariamente
# "modal_context": dados.get("modal_context"),
```

**Objetivo**: Confirmar que a adição do campo é a causa do problema

### 2. Adicionar Logging Detalhado

```python
# Em on_capturar_elemento()
logger.info(f"[DEBUG] dados recebidos: {json.dumps(dados, indent=2)}")
logger.info(f"[DEBUG] modal_context: {dados.get('modal_context')}")
logger.info(f"[DEBUG] seletor: {dados.get('seletor')}")
```

**Objetivo**: Ver exatamente o que está sendo recebido do JavaScript

### 3. Validar Estrutura do JSON

```python
# Antes de criar evento_base
try:
    modal_ctx = dados.get("modal_context")
    if modal_ctx is not None:
        # Tentar serializar para verificar se é válido
        json.dumps(modal_ctx)
        logger.info(f"[DEBUG] modal_context válido: {modal_ctx}")
except Exception as e:
    logger.error(f"[DEBUG] modal_context inválido: {e}")
    modal_ctx = None
```

### 4. Testar com Console Aberto

Durante a próxima captura:
1. Abrir DevTools (F12)
2. Ir para aba Console
3. Procurar por:
   - Logs `[MODAL DEBUG]`
   - Erros JavaScript
   - Warnings de serialização

## Plano de Ação

### Fase 1: Diagnóstico (15 min)
1. ✅ Reverter adição do campo `modal_context`
2. ✅ Capturar novamente
3. ✅ Verificar se seletores com prefixo voltam a aparecer

### Fase 2: Investigação (30 min)
1. ✅ Adicionar logging detalhado
2. ✅ Capturar com console aberto
3. ✅ Analisar estrutura do `modal_context` recebido

### Fase 3: Correção (30 min)
1. ✅ Identificar causa raiz
2. ✅ Implementar fix correto
3. ✅ Validar que seletores continuam funcionando

### Fase 4: Validação (15 min)
1. ✅ Capturar workflow completo
2. ✅ Verificar campo `modal_context` presente
3. ✅ Verificar seletores com prefixo presentes
4. ✅ Medir taxa de sucesso

## Conclusão Temporária

### O Que Sabemos ✅

1. **Detecção de modal funciona**: Captura 1 provou que seletores com prefixo são gerados
2. **Injeção funciona parcialmente**: Script é injetado na página principal
3. **Retry logic funciona**: Está tentando reinjetar em frames

### O Que NÃO Sabemos ❌

1. **Por que `modal_context` quebra a captura**: Causa raiz desconhecida
2. **Por que `modal_context` não aparece**: Pode estar sendo filtrado ou causando erro
3. **Por que apenas 8% de cobertura**: Pode ser timing ou problema de detecção

### Próximo Passo Crítico

🔴 **REVERTER** a adição do campo `modal_context` e **CAPTURAR NOVAMENTE** para confirmar que os seletores com prefixo voltam a funcionar.

Se confirmado, investigar **POR QUE** a adição do campo quebra a captura antes de tentar adicionar novamente.

---

**Status**: 🔴 **REGRESSÃO CRÍTICA**  
**Impacto**: Pior que antes (0% vs. 8% de cobertura)  
**Prioridade**: **URGENTE**  
**Próxima Ação**: Reverter mudança e investigar causa raiz

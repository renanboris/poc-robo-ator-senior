# Fix do Radar no Step-by-Step Validation

## Problema Identificado

Quando o analista clicava em **"Corrigir"** no overlay step-by-step, o Radar não estava funcionando:
- O cronômetro não aparecia
- O clique não era capturado
- A tela ficava travada esperando indefinidamente
- Eventualmente o processo falhava com `returncode=1`

## Causa Raiz

Três problemas principais foram identificados:

### 1. **Binding não funcionava em iframes**
O `expose_binding("__hitl_captura__")` é feito no contexto principal, mas Senior X usa iframes extensivamente. Iframes não têm acesso ao binding do frame principal.

**Solução**: Implementar comunicação via `postMessage` entre iframes e frame principal.

### 2. **Cronômetro não era injetado corretamente**
O CSS de animação (`@keyframes hitl-radar-pulse`) não estava sendo injetado antes de usar a classe `.hitl-radar-pulse-dot`.

**Solução**: Injetar CSS de animação primeiro, depois o HTML do indicador visual.

### 3. **Falta de tratamento de erro**
Se o clique não fosse capturado, o processo ficava travado esperando indefinidamente.

**Solução**: Adicionar logs detalhados e validação de seletor capturado.

## Implementação do Fix

### 1. Injeção de CSS de Animação
```javascript
// Injeta CSS primeiro
if (!document.getElementById('hitl-radar-pulse-style')) {
    const st = document.createElement('style');
    st.id = 'hitl-radar-pulse-style';
    st.innerHTML = `
        @keyframes hitl-radar-pulse {
            0%,100% { opacity:1; } 50% { opacity:0.5; }
        }
        .hitl-radar-pulse-dot {
            display:inline-block; width:8px; height:8px;
            background:#ef4444; border-radius:50%;
            animation: hitl-radar-pulse 1.2s ease infinite;
        }
    `;
    document.head.appendChild(st);
}
```

### 2. Comunicação via postMessage para iframes
```javascript
// No iframe
if (window.self !== window.top) {
    window.top.postMessage({
        type: '__hitl_radar_captura__',
        seletor: seletor,
        label: label
    }, '*');
} else {
    // Frame principal
    if (window.__hitl_captura__) {
        window.__hitl_captura__(JSON.stringify({ seletor, label }));
    }
}

// No frame principal — listener para postMessage
window.addEventListener('message', (e) => {
    if (e.data && e.data.type === '__hitl_radar_captura__') {
        if (window.__hitl_captura__) {
            window.__hitl_captura__(JSON.stringify({
                seletor: e.data.seletor,
                label: e.data.label
            }));
        }
    }
}, false);
```

### 3. Validação e Logging
```python
# Extrai seletor capturado
seletor_capturado = self._decisao_humana.get("seletor", "")
if not seletor_capturado:
    logger.warning("[STEP] Radar: nenhum seletor foi capturado")
    return ""

logger.info(f"[STEP] Seletor capturado via radar: {seletor_capturado}")
```

## Fluxo Corrigido

1. **Analista clica em "Corrigir"** no overlay step-by-step
2. **Radar é ativado**:
   - CSS de animação é injetado
   - Indicador visual "Radar ativo — clique no elemento correto" aparece
   - Cronômetro começa (120s)
   - Botão "❌ Cancelar" fica disponível
3. **Listener de clique é injetado em TODOS os frames**:
   - Frame principal: chama `__hitl_captura__` binding diretamente
   - Iframes: usam `postMessage` para comunicar com frame principal
4. **Analista clica no elemento correto**:
   - Clique é capturado (em qualquer frame)
   - Feedback visual imediato (outline cyan)
   - Seletor é enviado para Python via binding
5. **Python recebe o seletor**:
   - Valida se não está vazio
   - Salva no Brain com `hitl_corrigido=1`
   - Retorna para continuar a execução

## Melhorias Implementadas

### ✅ Cronômetro Visual
- Countdown de 120s aparece no overlay
- Atualiza a cada segundo
- Ao atingir 0, cancela automaticamente

### ✅ Botão Cancelar
- Permite que o analista cancele o radar sem clicar em nada
- Limpa o countdown e o indicador visual
- Retorna seletor vazio (pula a correção)

### ✅ Suporte a iframes
- Listener de clique funciona em qualquer frame
- postMessage garante comunicação entre frames
- Sem dependência de binding no contexto do iframe

### ✅ Logging Detalhado
- `[STEP] Radar step ativado — aguardando clique do analista`
- `[STEP] Seletor capturado via radar: [id='s-button-9']`
- `[STEP] Radar cancelado pelo analista`
- `[STEP] Timeout de 120s no radar step — cancelando captura`

## Testes Implementados

Arquivo: `test_radar_fix.py`

- ✅ `test_radar_cronometro_injetado` — Valida injeção de CSS
- ✅ `test_radar_captura_clique` — Valida captura de clique
- ✅ `test_radar_cancelar` — Valida botão Cancelar
- ✅ `test_radar_postmessage_iframe` — Valida comunicação via postMessage
- ✅ `test_radar_timeout` — Valida timeout de 120s

**Resultado**: 5/5 testes passando ✅

## Como Testar Manualmente

1. Inicie o validador HITL:
   ```bash
   python validator_hitl.py roteiros_salvos/seu_roteiro.json
   ```

2. Quando uma ação for executada, o overlay step-by-step aparecerá

3. Clique em **"✏️ Corrigir"**

4. Você verá:
   - Overlay com "Radar ativo — clique no elemento correto"
   - Cronômetro contando de 120s para 0
   - Botão "❌ Cancelar"

5. Clique no elemento correto na tela

6. O seletor será capturado e salvo no Brain

## Compatibilidade

- ✅ Frame principal (Senior X)
- ✅ Iframes (Senior X usa extensivamente)
- ✅ Múltiplos iframes aninhados
- ✅ Frames com origem diferente (postMessage funciona com `*`)
- ✅ Modo step-by-step (padrão)
- ✅ Modo auto (fallback para step-by-step em caso de falha)

## Próximos Passos

1. Testar em produção com roteiros reais
2. Monitorar logs para validar captura de cliques
3. Coletar feedback do analista sobre UX do cronômetro
4. Considerar aumentar timeout se necessário (atualmente 120s)

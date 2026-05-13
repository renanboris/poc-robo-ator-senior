# Guia de Troubleshooting: Radar Step-by-Step

## Problema: Cronômetro não aparece

### Sintomas
- Overlay "Radar ativo" aparece, mas sem cronômetro
- Botão "❌ Cancelar" não aparece

### Diagnóstico
1. Verifique se o CSS de animação foi injetado:
   ```javascript
   // No console do Chrome DevTools
   document.getElementById('hitl-radar-pulse-style')
   // Deve retornar o elemento <style>
   ```

2. Verifique se o overlay step-by-step existe:
   ```javascript
   document.getElementById('hitl-step-overlay')
   // Deve retornar o elemento <div>
   ```

### Solução
- Verifique se há erros no console do Chrome (F12 → Console)
- Procure por logs em `validator_hitl.py`:
  ```
  [STEP] Radar step ativado — aguardando clique do analista
  ```
- Se não houver logs, o Radar não foi ativado

---

## Problema: Clique não é capturado

### Sintomas
- Cronômetro aparece e funciona
- Você clica no elemento, mas nada acontece
- Tela fica travada esperando

### Diagnóstico
1. Verifique se o listener de clique foi injetado:
   ```javascript
   // No console do Chrome DevTools
   window.__hitlRadarStepAtivo
   // Deve ser true quando o radar está ativo
   ```

2. Verifique se o binding está disponível:
   ```javascript
   window.__hitl_captura__
   // Deve ser uma função
   ```

3. Se estiver em um iframe, verifique se o postMessage está funcionando:
   ```javascript
   // No console do iframe
   window.self !== window.top
   // Deve ser true se estiver em um iframe
   ```

### Solução
- **Frame principal**: Verifique se `__hitl_captura__` é uma função
  - Se não, o binding não foi exposto corretamente
  - Verifique `_setup_captura_humana()` em `validator_hitl.py`

- **Iframe**: Verifique se postMessage está funcionando
  - Abra o console do frame principal (não do iframe)
  - Clique em um elemento no iframe
  - Procure por mensagens postMessage:
    ```javascript
    window.addEventListener('message', (e) => {
        console.log('postMessage recebido:', e.data);
    });
    ```

- **Logs em Python**:
  ```
  [STEP] Seletor capturado via radar: [id='btn-acoes']
  ```
  Se não aparecer, o clique não foi capturado

---

## Problema: Timeout de 120s é atingido

### Sintomas
- Cronômetro chega a 0
- Radar é cancelado automaticamente
- Seletor vazio é retornado

### Diagnóstico
1. Verifique se o listener de clique está ativo:
   ```javascript
   window.__hitlRadarStepAtivo
   // Deve ser true
   ```

2. Verifique se há erros ao clicar:
   - Abra o console do Chrome (F12 → Console)
   - Clique no elemento
   - Procure por erros vermelhos

3. Verifique se o elemento é clicável:
   - Tente clicar em um elemento diferente
   - Verifique se há `pointer-events: none` no CSS

### Solução
- **Aumentar timeout**: Edite `_ativar_radar_step()` em `validator_hitl.py`
  ```python
  await asyncio.wait_for(self._evento_humano.wait(), timeout=180)  # 3 minutos
  ```

- **Verificar elemento**: Tente clicar em um elemento diferente
  - Botões geralmente funcionam bem
  - Evite clicar em elementos com `pointer-events: none`

- **Verificar iframe**: Se estiver em um iframe
  - Verifique se o iframe tem `sandbox` restritivo
  - Verifique se há CORS issues

---

## Problema: Seletor capturado está incorreto

### Sintomas
- Clique é capturado
- Seletor é salvo no Brain
- Mas o seletor não funciona na próxima execução

### Diagnóstico
1. Verifique o seletor capturado:
   ```
   [STEP] Seletor capturado via radar: [id='btn-acoes']
   ```

2. Teste o seletor no console:
   ```javascript
   document.querySelector("[id='btn-acoes']")
   // Deve retornar o elemento
   ```

3. Verifique se o elemento tem `data-testid`:
   ```javascript
   document.querySelector("[id='btn-acoes']").getAttribute('data-testid')
   ```

### Solução
- **Seletor muito específico**: O elemento pode ter mudado
  - Verifique se o `id` é estável
  - Prefira `data-testid` ou `aria-label`

- **Seletor muito genérico**: Pode estar capturando o elemento errado
  - Verifique se há múltiplos elementos com o mesmo seletor
  - Use `document.querySelectorAll()` para verificar

- **Elemento dinâmico**: O elemento pode ser renderizado dinamicamente
  - Verifique se o elemento existe quando o seletor é testado
  - Considere usar um seletor mais robusto

---

## Problema: Radar não funciona em iframe específico

### Sintomas
- Radar funciona no frame principal
- Radar não funciona em um iframe específico
- Clique no iframe não é capturado

### Diagnóstico
1. Verifique se o iframe tem `sandbox`:
   ```html
   <iframe sandbox="allow-same-origin allow-scripts"></iframe>
   ```

2. Verifique se há CORS issues:
   - Abra o console do Chrome (F12 → Console)
   - Procure por erros de CORS

3. Verifique se o listener foi injetado no iframe:
   ```javascript
   // No console do iframe
   window.__hitlRadarStepAtivo
   // Deve ser true quando o radar está ativo
   ```

### Solução
- **Sandbox restritivo**: Adicione permissões necessárias
  ```html
  <iframe sandbox="allow-same-origin allow-scripts allow-popups"></iframe>
  ```

- **CORS issues**: Verifique se o iframe é da mesma origem
  - Se não, postMessage pode não funcionar
  - Considere usar `window.top` para acessar o frame principal

- **Listener não injetado**: Verifique se há erros ao injetar
  - Procure por logs em `validator_hitl.py`:
    ```
    [STEP] Radar inject iframe 'https://...': ...
    ```

---

## Problema: Botão "❌ Cancelar" não funciona

### Sintomas
- Botão aparece
- Clique no botão não funciona
- Radar continua ativo

### Diagnóstico
1. Verifique se o botão tem event listener:
   ```javascript
   // No console do Chrome DevTools
   const btn = document.getElementById('hitl-radar-cancel-btn');
   btn.onclick
   // Deve ser uma função
   ```

2. Verifique se há erros ao clicar:
   - Abra o console do Chrome (F12 → Console)
   - Clique no botão
   - Procure por erros vermelhos

### Solução
- **Event listener não foi adicionado**: Verifique se o botão foi criado corretamente
  - Procure por logs em `validator_hitl.py`:
    ```
    [STEP] Radar step ativado — aguardando clique do analista
    ```

- **Erro ao chamar binding**: Verifique se `__hitl_captura__` está disponível
  ```javascript
  window.__hitl_captura__
  // Deve ser uma função
  ```

---

## Logs Úteis para Diagnosticar

### Em Python (validator_hitl.py)
```
[STEP] Radar step ativado — aguardando clique do analista
[STEP] Seletor capturado via radar: [id='btn-acoes']
[STEP] Radar cancelado pelo analista
[STEP] Timeout de 120s no radar step — cancelando captura
[STEP] Radar: nenhum seletor foi capturado
```

### No Console do Chrome (F12 → Console)
```javascript
// Verificar se o radar está ativo
window.__hitlRadarStepAtivo

// Verificar se o binding está disponível
window.__hitl_captura__

// Verificar se o cronômetro está rodando
window.__hitlRadarCountdownId

// Verificar se estamos em um iframe
window.self !== window.top
```

---

## Checklist de Troubleshooting

- [ ] Cronômetro aparece?
- [ ] Listener de clique está ativo (`window.__hitlRadarStepAtivo === true`)?
- [ ] Binding está disponível (`window.__hitl_captura__` é função)?
- [ ] Elemento é clicável (sem `pointer-events: none`)?
- [ ] Seletor capturado é válido (`document.querySelector(seletor)` retorna elemento)?
- [ ] Se em iframe: postMessage está funcionando?
- [ ] Se em iframe: iframe tem permissões necessárias no `sandbox`?
- [ ] Logs em Python mostram captura de clique?

---

## Contato e Suporte

Se o problema persistir:
1. Colete os logs de `validator_hitl.py`
2. Abra o console do Chrome (F12 → Console) e copie os erros
3. Teste os comandos JavaScript acima
4. Crie uma issue com os detalhes

**Arquivo de referência**: `.kiro/specs/hitl-step-by-step-validation/RADAR_FIX.md`

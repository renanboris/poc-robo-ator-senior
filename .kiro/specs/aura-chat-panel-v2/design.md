# Design Document — aura-chat-panel-v2

## Overview

Este documento descreve o design técnico do redesign do Chat_Panel da Aura DAP. O escopo cobre cinco melhorias contidas exclusivamente nos arquivos da extensão Chrome (`extension/`):

1. **Fundo sólido anti-transparência** — substituir `rgba(255,255,255,0.28)` por `rgba(255,255,255,0.92)` com fallback sólido via `@supports`.
2. **Botões de feedback com SVG** — substituir emoji `👍👎` por SVG inline estilizado via CSS.
3. **Typing Indicator animado** — substituir texto estático por componente `.aura-typing-dots` como Message_Bubble na Thread_Area.
4. **Histórico de sessão** — introduzir Thread_Area scrollável com array `_historico[]` em memória.
5. **Auto-hide inteligente** — pausar o timer de 12s durante scroll na Thread_Area e durante Typing_Indicator.

A API pública `window.AuraUI` (10 métodos) e todos os modos existentes (assist, gps, train, prove) são preservados sem alteração de assinatura.

---

## Architecture

### Visão geral dos módulos afetados

```
content.js
  └─ cria HTML do #aura-floating-container
       └─ #aura-speech-bubble  ← estrutura HTML alterada (Thread_Area adicionada)

aura_ui.js
  ├─ _historico[]              ← novo estado privado
  ├─ _typingBubbleEl           ← referência ao Typing_Indicator ativo
  ├─ _typingTimeout            ← timeout de 30s para fallback de erro
  ├─ exibirBalao()             ← adaptado para renderizar na Thread_Area
  ├─ _appendBubble()           ← novo helper privado
  ├─ _scrollThreadToBottom()   ← novo helper privado
  ├─ _initScrollEngajamento()  ← novo helper privado (listener de scroll)
  └─ init()                    ← registra listener de scroll na Thread_Area

aura_assist_engine.js
  └─ dispararAnalise()         ← delega exibição do Typing_Indicator para AuraUI

aura_feedback.js
  └─ criar()                   ← SVG inline em vez de emoji textContent

extension/style.css
  ├─ #aura-speech-bubble       ← background e backdrop-filter atualizados
  ├─ .aura-chat-bubble         ← mesmo padrão de opacidade alta
  ├─ .aura-thread-area         ← nova regra (max-height, overflow-y, scroll)
  ├─ .aura-msg-bubble          ← novas regras (aura vs user, alinhamento, cores)
  ├─ .aura-typing-bubble       ← wrapper do Typing_Indicator como Message_Bubble
  └─ .aura-fb-btn              ← estilos SVG (cor padrão, hover like, hover dislike)
```

### Fluxo de dados — pergunta do usuário

```
Usuário digita → dispararAnalise()
  → AuraUI.adicionarMensagemUsuario(texto)   [novo]
  → AuraUI.exibirTypingIndicator()           [novo]
  → postMessage(AURA_CAPTURE)

AURA_RESPONSE recebido → AuraAssistEngine._handleMessage()
  → AuraUI.removerTypingIndicator()          [novo]
  → AuraUI.exibirBalao(texto, opcoes, true)  [assinatura preservada]
    → _appendBubble('aura', texto)
    → _scrollThreadToBottom()
```

### Diagrama de componentes do Chat_Panel

```
#aura-speech-bubble
├── .aura-panel-header
│   ├── .aura-panel-title  "Aura"
│   └── #aura-btn-close    ✕
├── #aura-thread-area  (role="log", aria-live="polite")
│   ├── .aura-msg-bubble.aura-msg-aura   ← mensagem da Aura
│   ├── .aura-msg-bubble.aura-msg-user   ← mensagem do usuário
│   └── .aura-typing-bubble              ← Typing_Indicator (temporário)
│       └── .aura-typing-dots
│           ├── <span>
│           ├── <span>
│           └── <span>
├── .aura-options                        ← chips de sugestão (preservado)
└── .aura-input-wrapper                  ← input + botão enviar (preservado)
```

---

## Components and Interfaces

### 1. `content.js` — HTML do container

**Mudança:** adicionar `.aura-panel-header` e `#aura-thread-area` dentro de `#aura-speech-bubble`. Remover o elemento `.aura-text` (substituído pela Thread_Area). Preservar `.aura-options` e `.aura-input-wrapper`.

```html
<!-- Novo HTML de #aura-speech-bubble em content.js -->
<div id="aura-speech-bubble">
  <div class="aura-panel-header">
    <span class="aura-panel-title">Aura</span>
    <button class="aura-btn-close" id="aura-btn-close" aria-label="Fechar">✕</button>
  </div>
  <div class="aura-thread-area" id="aura-thread-area"
       role="log" aria-live="polite" aria-label="Conversa com a Aura">
  </div>
  <div class="aura-options"></div>
  <div class="aura-input-wrapper">
    <input type="text" id="aura-prompt-input"
           placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">
    <button class="aura-btn-send" id="aura-btn-ask">➜</button>
  </div>
</div>
```

**Nota:** o elemento `.aura-text` é removido do HTML estático. `exibirBalao()` passa a escrever na Thread_Area via `_appendBubble()`.

---

### 2. `aura_ui.js` — novos helpers e estado

#### Estado privado adicionado

```js
let _historico = [];          // { role: 'aura'|'user', texto: string, timestamp: number }
let _typingBubbleEl = null;   // referência ao elemento DOM do Typing_Indicator ativo
let _typingTimeout  = null;   // timeout de 30s para fallback de erro
```

#### `_getThreadArea()` — helper de referência DOM

```js
function _getThreadArea() { return document.getElementById('aura-thread-area'); }
```

#### `_appendBubble(role, texto)` — renderiza Message_Bubble

```js
/**
 * Cria e insere uma Message_Bubble na Thread_Area.
 * @param {'aura'|'user'} role
 * @param {string} texto
 * @returns {HTMLElement} o elemento criado
 */
function _appendBubble(role, texto) { ... }
```

- Cria `<div class="aura-msg-bubble aura-msg-{role}">` com o texto.
- Adiciona ao `#aura-thread-area`.
- Chama `_scrollThreadToBottom()`.
- Retorna o elemento (usado para remover o Typing_Indicator).

#### `_scrollThreadToBottom()` — scroll automático

```js
function _scrollThreadToBottom() {
    const area = _getThreadArea();
    if (area) area.scrollTop = area.scrollHeight;
}
```

#### `_initScrollEngajamento()` — listener de scroll na Thread_Area

```js
/**
 * Registra listener de scroll na Thread_Area para ativar Engagement_Lock.
 * Chamado uma única vez em init(). Não duplica registros.
 */
function _initScrollEngajamento() { ... }
```

- Adiciona `scroll` listener na Thread_Area.
- No handler: `_bubbleEngajada = true; clearTimeout(_bubbleTimeout);`
- Reinicia o timer de 12s após 12s sem interação (via `setTimeout` interno).

#### `exibirTypingIndicator()` — exibe Typing_Indicator

```js
/**
 * Exibe o Typing_Indicator como Message_Bubble da Aura na Thread_Area.
 * Ativa Engagement_Lock. Inicia timeout de 30s para fallback de erro.
 */
function exibirTypingIndicator() { ... }
```

- Cria `<div class="aura-typing-bubble" aria-label="Aura está digitando">` com `.aura-typing-dots` (3 `<span>`).
- Armazena referência em `_typingBubbleEl`.
- Ativa `_bubbleEngajada = true`.
- Inicia `_typingTimeout` de 30s → ao expirar, chama `removerTypingIndicator()` e `_appendBubble('aura', 'Não consegui processar a resposta. Tente novamente.')`.

#### `removerTypingIndicator()` — remove Typing_Indicator

```js
/**
 * Remove o Typing_Indicator do DOM e cancela o timeout de 30s.
 */
function removerTypingIndicator() { ... }
```

- Remove `_typingBubbleEl` do DOM se existir.
- Cancela `_typingTimeout`.
- Zera `_typingBubbleEl = null`.

#### `adicionarMensagemUsuario(texto)` — registra mensagem do usuário

```js
/**
 * Adiciona a mensagem do usuário ao _historico e renderiza na Thread_Area.
 * Chamado por dispararAnalise() antes de exibirTypingIndicator().
 * @param {string} texto
 */
function adicionarMensagemUsuario(texto) { ... }
```

- Push em `_historico`: `{ role: 'user', texto, timestamp: Date.now() }`.
- Chama `_appendBubble('user', texto)`.

#### `exibirBalao(texto, opcoes, mostrarFeedback)` — adaptado

A assinatura é **preservada**. Mudanças internas:

- Em vez de `bubble.querySelector('.aura-text').innerText = texto`, chama `_appendBubble('aura', texto)`.
- Push em `_historico`: `{ role: 'aura', texto, timestamp: Date.now() }`.
- Garante que `bubble.classList.add('active')` ainda ocorre (para exibir o painel).
- Chips de sugestão e feedback continuam sendo inseridos em `.aura-options`.
- Auto-hide de 12s: respeita `_bubbleEngajada` e verifica se `_typingBubbleEl !== null` (não fecha durante Typing_Indicator).

#### `esconderBalao()` — preservado

Apenas remove `active` do painel. **Não limpa `_historico`** (preservado para reabrir na mesma sessão).

#### `init()` — registra scroll listener

Adiciona chamada a `_initScrollEngajamento()` após `_initEngajamento()`.

---

### 3. `aura_assist_engine.js` — `dispararAnalise()` adaptado

**Mudança mínima:** substituir a chamada direta a `AuraUI.exibirBalao(...)` pelo par:

```js
// Antes:
global.AuraUI.exibirBalao('Já estou analisando... Só um momento! 🔍', []);

// Depois:
if (global.AuraUI.adicionarMensagemUsuario) {
    global.AuraUI.adicionarMensagemUsuario(prompt);
}
if (global.AuraUI.exibirTypingIndicator) {
    global.AuraUI.exibirTypingIndicator();
} else {
    global.AuraUI.exibirBalao('Já estou analisando... Só um momento! 🔍', []);
}
```

O guard `else` garante compatibilidade retroativa caso `exibirTypingIndicator` não esteja disponível.

**No handler `_handleMessage` (AURA_RESPONSE):** adicionar chamada a `removerTypingIndicator()` antes de `exibirBalao()`:

```js
if (global.AuraUI.removerTypingIndicator) {
    global.AuraUI.removerTypingIndicator();
}
global.AuraUI.exibirBalao(textoResposta, opcoes, true);
```

**Nota:** `adicionarMensagemUsuario`, `exibirTypingIndicator` e `removerTypingIndicator` são métodos **internos** expostos no namespace `window.AuraUI` para uso pelos módulos dependentes, mas não fazem parte da API pública documentada no Req 6. Os 10 métodos públicos originais são preservados sem alteração.

---

### 4. `aura_feedback.js` — SVG inline

**Mudança:** substituir `like.textContent = '👍'` e `dislike.textContent = '👎'` por SVG inline. Remover estilos inline; usar classes CSS.

```js
// SVG like (thumbs-up)
like.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
  fill="none" stroke="currentColor" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
  <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
</svg>`;

// SVG dislike (thumbs-down)
dislike.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"
  fill="none" stroke="currentColor" stroke-width="2"
  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
  <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
  <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
</svg>`;
```

Classes CSS aplicadas via `style.css` (ver seção CSS abaixo).

---

### 5. `extension/style.css` — regras novas e alteradas

#### Req 1 — Fundo do Chat_Panel

```css
/* Substituir background atual de #aura-speech-bubble */
#aura-speech-bubble {
    background: rgba(255, 255, 255, 0.92) !important;
    backdrop-filter: blur(16px) !important;
    -webkit-backdrop-filter: blur(16px) !important;
}

@supports not (backdrop-filter: blur(1px)) {
    #aura-speech-bubble {
        background: #ffffff !important;
    }
}

/* Chat Stack bubbles — mesmo padrão */
.aura-chat-bubble {
    background: rgba(255, 255, 255, 0.92) !important;
}

@supports not (backdrop-filter: blur(1px)) {
    .aura-chat-bubble {
        background: #ffffff !important;
    }
}
```

#### Req 2 — Botões de feedback SVG

```css
.aura-fb-btn {
    background: transparent !important;
    border: none !important;
    cursor: pointer !important;
    padding: 4px !important;
    color: #94a3b8 !important;
    display: inline-flex !important;
    align-items: center !important;
    transition: color 0.2s ease !important;
}

.aura-fb-btn svg {
    width: 16px !important;
    height: 16px !important;
    pointer-events: none !important;
}

.aura-fb-btn.aura-fb-like:hover  { color: #00ddb3 !important; }
.aura-fb-btn.aura-fb-dislike:hover { color: #ef4444 !important; }
```

#### Req 3 — Typing Indicator como Message_Bubble

```css
.aura-typing-bubble {
    align-self: flex-start !important;
    background: rgba(0, 221, 179, 0.10) !important;
    border: 1px solid rgba(0, 221, 179, 0.2) !important;
    border-radius: 12px 12px 12px 4px !important;
    padding: 10px 14px !important;
    margin-bottom: 4px !important;
}
```

#### Req 4 — Thread_Area e Message_Bubbles

```css
.aura-thread-area {
    display: flex !important;
    flex-direction: column !important;
    gap: 6px !important;
    max-height: 260px !important;
    overflow-y: auto !important;
    padding: 4px 2px !important;
    scroll-behavior: smooth !important;
}

.aura-thread-area::-webkit-scrollbar { width: 3px !important; }
.aura-thread-area::-webkit-scrollbar-track { background: transparent !important; }
.aura-thread-area::-webkit-scrollbar-thumb { background: #cbd5e1 !important; border-radius: 4px !important; }

.aura-msg-bubble {
    max-width: 85% !important;
    font-size: 13.5px !important;
    line-height: 1.5 !important;
    padding: 8px 12px !important;
    border-radius: 12px !important;
    word-break: break-word !important;
}

/* Mensagens da Aura — esquerda */
.aura-msg-aura {
    align-self: flex-start !important;
    background: rgba(0, 221, 179, 0.10) !important;
    border: 1px solid rgba(0, 221, 179, 0.2) !important;
    color: #1e293b !important;
    border-radius: 12px 12px 12px 4px !important;
}

/* Mensagens do usuário — direita */
.aura-msg-user {
    align-self: flex-end !important;
    background: #00ddb3 !important;
    color: #ffffff !important;
    border-radius: 12px 12px 4px 12px !important;
}
```

#### Panel header

```css
.aura-panel-header {
    display: flex !important;
    align-items: center !important;
    justify-content: space-between !important;
    padding-bottom: 8px !important;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06) !important;
}

.aura-panel-title {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #64748b !important;
    letter-spacing: 0.02em !important;
}
```

---

## Data Models

### `_historico` — array em memória

```ts
interface HistoricoEntry {
    role:      'aura' | 'user';
    texto:     string;
    timestamp: number;   // Date.now()
}

// Escopo: variável privada do módulo aura_ui.js
let _historico: HistoricoEntry[] = [];
```

**Ciclo de vida:**
- Criado vazio na carga do módulo.
- Populado por `adicionarMensagemUsuario()` e `exibirBalao()`.
- Preservado em memória ao chamar `esconderBalao()`.
- Descartado automaticamente ao fechar a aba (sem `localStorage`/`sessionStorage`).

### Estado privado de UI

```ts
let _bubbleTimeout:   ReturnType<typeof setTimeout> | null;  // auto-hide 12s
let _bubbleEngajada:  boolean;   // Engagement_Lock
let _typingBubbleEl:  HTMLElement | null;  // referência ao Typing_Indicator no DOM
let _typingTimeout:   ReturnType<typeof setTimeout> | null;  // fallback 30s
```

### Feedback entry (localStorage — inalterado)

```ts
interface FeedbackEntry {
    tipo:   'like' | 'dislike';
    prompt: string;   // max 100 chars
    url:    string;
    ts:     number;
}
// key: `aura_fb_${Date.now()}`
```

---

## Correctness Properties


*Uma propriedade é uma característica ou comportamento que deve ser verdadeiro em todas as execuções válidas do sistema — essencialmente, uma declaração formal sobre o que o software deve fazer. Propriedades servem como ponte entre especificações legíveis por humanos e garantias de correção verificáveis por máquina.*

**Reflexão de redundância:** Após analisar todos os critérios, as propriedades candidatas são:

- **1.4** — contraste WCAG para qualquer cor de fundo (PROPERTY)
- **2.5** — round-trip de feedback no localStorage para qualquer prompt (PROPERTY)
- **3.3** — remoção do Typing_Indicator e exibição da resposta para qualquer texto (PROPERTY)
- **4.1 + 4.2 + 4.3** — estrutura e conteúdo do `_historico` para qualquer mensagem (podem ser combinadas: 4.1 é subsumed por 4.2 e 4.3 que já verificam campos e valores)
- **4.4** — renderização correta de bubbles para qualquer sequência de mensagens (PROPERTY)
- **4.5** — scroll automático para o fundo após qualquer append (PROPERTY)
- **4.7** — `esconderBalao()` preserva `_historico` para qualquer sequência (PROPERTY)
- **5.2** — Engagement_Lock impede auto-hide (PROPERTY)
- **5.4** — listener de scroll registrado exatamente uma vez para qualquer N de chamadas (PROPERTY)
- **6.1** — todos os 10 métodos públicos existem (PROPERTY sobre conjunto de nomes)
- **6.3** — `exibirBalao` funciona em qualquer modo (PROPERTY)

**Consolidações:**
- 4.1 (estrutura do entry) é subsumed por 4.2 e 4.3 que já verificam campos específicos → remover 4.1 como propriedade separada.
- 4.2 e 4.3 podem ser combinadas em uma única propriedade de round-trip do histórico: "para qualquer par (pergunta, resposta), ambas as entradas aparecem no `_historico` com os campos corretos".
- 6.1 e 6.3 são complementares mas não redundantes: 6.1 verifica existência, 6.3 verifica comportamento por modo. Manter ambas.

---

### Property 1: Contraste WCAG sobre qualquer fundo

*Para qualquer* cor de fundo RGB da página do Senior X, ao compor `rgba(255, 255, 255, 0.92)` sobre essa cor, a razão de contraste WCAG 2.1 entre o texto `#1e293b` e o fundo resultante do painel SHALL ser maior ou igual a 4.5:1.

**Validates: Requirements 1.4**

---

### Property 2: Round-trip de feedback no localStorage

*Para qualquer* string de prompt (incluindo strings vazias, com caracteres especiais e com mais de 100 caracteres), após o usuário clicar em like ou dislike, o `localStorage` SHALL conter uma entrada com os campos `tipo`, `prompt` (truncado a 100 caracteres), `url` e `ts` com os tipos corretos.

**Validates: Requirements 2.5**

---

### Property 3: Typing_Indicator removido e resposta exibida para qualquer texto

*Para qualquer* texto de resposta da IA recebido via `AURA_RESPONSE`, após o processamento do evento, a Thread_Area SHALL não conter o elemento `.aura-typing-bubble` e SHALL conter um elemento `.aura-msg-aura` cujo conteúdo de texto inclui o texto da resposta.

**Validates: Requirements 3.3**

---

### Property 4: Round-trip do histórico de conversa

*Para qualquer* sequência de pares (pergunta do usuário, resposta da Aura), após cada ciclo completo de `dispararAnalise()` + `AURA_RESPONSE`, o array `_historico` SHALL conter entradas com `role='user'` e `role='aura'` correspondentes, cada uma com os campos `texto` (igual ao texto enviado/recebido) e `timestamp` (número inteiro positivo).

**Validates: Requirements 4.1, 4.2, 4.3**

---

### Property 5: Renderização fiel de Message_Bubbles para qualquer sequência

*Para qualquer* sequência de mensagens com roles alternados ou consecutivos, cada mensagem com `role='aura'` renderizada na Thread_Area SHALL ter a classe `aura-msg-aura` e cada mensagem com `role='user'` SHALL ter a classe `aura-msg-user`, preservando a ordem de inserção.

**Validates: Requirements 4.4**

---

### Property 6: Scroll automático para o fundo após qualquer append

*Para qualquer* número de mensagens adicionadas à Thread_Area, após cada chamada a `_appendBubble()`, o valor de `scrollTop` da Thread_Area SHALL ser igual ao seu `scrollHeight` (painel scrollado até o fim).

**Validates: Requirements 4.5**

---

### Property 7: `esconderBalao()` preserva o histórico

*Para qualquer* sequência de mensagens armazenadas em `_historico`, após chamar `esconderBalao()`, o array `_historico` SHALL ter o mesmo comprimento e os mesmos conteúdos que antes da chamada.

**Validates: Requirements 4.7**

---

### Property 8: Engagement_Lock impede o auto-hide

*Para qualquer* estado do Chat_Panel onde `_bubbleEngajada = true` (Engagement_Lock ativo), após o disparo do timer de 12 segundos, o Chat_Panel SHALL permanecer com a classe `active` (não ser fechado pelo auto-hide).

**Validates: Requirements 5.2**

---

### Property 9: Listener de scroll registrado exatamente uma vez

*Para qualquer* número N de chamadas a `exibirBalao()`, um único evento de scroll na Thread_Area SHALL disparar o handler de Engagement_Lock exatamente uma vez (não N vezes), garantindo que não há duplicação de listeners.

**Validates: Requirements 5.4**

---

### Property 10: Todos os métodos públicos da API preservados

*Para cada* um dos 10 nomes de métodos públicos (`init`, `exibirBalao`, `exibirBaloesSequenciais`, `esconderBalao`, `ativarBadge`, `desativarBadge`, `tocarAnimacao`, `setLastPrompt`, `wasPlayerDragged`, `resetDragFlag`), `window.AuraUI[methodName]` SHALL ser uma função.

**Validates: Requirements 6.1**

---

### Property 11: `exibirBalao` funciona em qualquer modo

*Para qualquer* modo em `['assist', 'gps', 'train', 'prove']`, após `AuraState.setMode(modo)`, chamar `exibirBalao(texto, [], false)` com qualquer texto SHALL renderizar um elemento `.aura-msg-aura` na Thread_Area sem lançar exceções.

**Validates: Requirements 6.3**

---

## Error Handling

### Typing_Indicator timeout (30s)

Se `AURA_RESPONSE` não chegar em 30 segundos após `dispararAnalise()`:
- `_typingTimeout` dispara.
- `removerTypingIndicator()` é chamado.
- `_appendBubble('aura', 'Não consegui processar a resposta. Tente novamente.')` exibe mensagem de erro.
- Inputs são reativados via `_reativarInputs()` (chamado em `aura_assist_engine.js`).

### `exibirBalao()` sem Thread_Area no DOM

Se `#aura-thread-area` não existir (DOM não inicializado):
- `_appendBubble()` retorna sem lançar exceção (guard `if (!area) return`).
- O painel ainda recebe `active` para não quebrar o fluxo de exibição.

### Duplo registro de listeners

`_initScrollEngajamento()` usa uma flag `_scrollListenerRegistrado` para garantir que o listener de scroll seja adicionado apenas uma vez, mesmo que `init()` seja chamado múltiplas vezes.

### Compatibilidade retroativa em `dispararAnalise()`

O guard `if (global.AuraUI.exibirTypingIndicator)` garante que, se `aura_ui.js` for carregado em uma versão anterior sem o novo método, o comportamento cai de volta para `exibirBalao('Já estou analisando...')`.

### Feedback sem `_historico` (módulo isolado)

`aura_feedback.js` não depende de `_historico`. O módulo continua funcionando de forma independente.

---

## Testing Strategy

### Abordagem dual

Este feature combina lógica de UI pura (funções com input/output claros) e comportamento de DOM. A estratégia usa:

- **Testes de exemplo** (unit tests): verificam comportamentos específicos e determinísticos (CSS properties, DOM structure, API surface).
- **Testes de propriedade** (property-based tests): verificam invariantes universais sobre inputs variados (histórico, renderização, contraste, scroll).

### Biblioteca de property-based testing

**[fast-check](https://github.com/dubzzz/fast-check)** (JavaScript/TypeScript) — escolhida por:
- Compatibilidade nativa com ambientes de browser e Node.js.
- Sem dependências externas além do próprio fast-check.
- Suporte a geradores arbitrários para strings, arrays, e objetos.

Configuração mínima: **100 iterações por propriedade** (`numRuns: 100`).

### Testes de propriedade (property-based)

Cada teste referencia a propriedade do design via comentário:
```
// Feature: aura-chat-panel-v2, Property N: <texto da propriedade>
```

| Propriedade | Gerador | Verificação |
|---|---|---|
| P1 — Contraste WCAG | `fc.tuple(fc.integer(0,255), fc.integer(0,255), fc.integer(0,255))` | `contrasteWCAG(compor(rgba(255,255,255,0.92), bgRGB), '#1e293b') >= 4.5` |
| P2 — Feedback localStorage | `fc.string()` (prompt) | localStorage entry tem campos corretos após click |
| P3 — Typing_Indicator removido | `fc.string({ minLength: 1 })` (resposta) | `.aura-typing-bubble` ausente, `.aura-msg-aura` presente |
| P4 — Round-trip histórico | `fc.array(fc.record({ pergunta: fc.string(), resposta: fc.string() }))` | `_historico` contém entradas corretas |
| P5 — Renderização de bubbles | `fc.array(fc.oneof(fc.constant('aura'), fc.constant('user')))` | classes corretas por role |
| P6 — Scroll automático | `fc.integer({ min: 1, max: 50 })` (N mensagens) | `scrollTop === scrollHeight` após cada append |
| P7 — `esconderBalao` preserva histórico | `fc.array(fc.record({ role: ..., texto: fc.string() }))` | `_historico` inalterado após esconderBalao() |
| P8 — Engagement_Lock | `fc.boolean()` (estado inicial do lock) | painel permanece `active` quando lock=true |
| P9 — Listener único | `fc.integer({ min: 1, max: 20 })` (N chamadas) | handler disparado exatamente 1x por scroll |
| P10 — API pública | `fc.constantFrom(...10 method names)` | `typeof window.AuraUI[name] === 'function'` |
| P11 — Modos | `fc.constantFrom('assist', 'gps', 'train', 'prove')` | exibirBalao não lança exceção, bubble renderizada |

### Testes de exemplo (unit tests)

- CSS: `background: rgba(255,255,255,0.92)` em `#aura-speech-bubble`.
- CSS: `@supports not (backdrop-filter)` → `background: #ffffff`.
- DOM: `.aura-typing-dots` contém exatamente 3 `<span>`.
- DOM: `aria-label="Aura está digitando"` no container do Typing_Indicator.
- DOM: botões like/dislike contêm `<svg>`, não emoji.
- DOM: botões like/dislike sem atributo `style` inline.
- Timeout: após 30s mockado, Typing_Indicator removido e mensagem de erro exibida.
- Persistência: `localStorage` e `sessionStorage` não contêm chave de histórico.
- API: `esconderBalao()` remove classe `active` do painel.

### Testes de fumaça (smoke tests)

- `window.AuraUI` existe após carregamento do módulo.
- Todos os 10 métodos públicos são funções.
- Nenhum novo arquivo JS externo introduzido.
- Apenas arquivos em `extension/` modificados.

### Plano de teste manual mínimo

1. Carregar a extensão no Chrome com o Senior X aberto em uma tela com fundo roxo/saturado.
2. Clicar no avatar → verificar que o painel é legível (fundo branco opaco).
3. Digitar uma pergunta e pressionar Enter → verificar que o Typing_Indicator aparece com 3 dots animados.
4. Aguardar resposta → verificar que o Typing_Indicator desaparece e a resposta aparece como bubble verde-claro à esquerda.
5. Verificar que a pergunta do usuário aparece como bubble verde à direita.
6. Rolar a Thread_Area → verificar que o painel não fecha automaticamente.
7. Parar de interagir por 12s → verificar que o painel fecha.
8. Reabrir o painel → verificar que o histórico da sessão está preservado.
9. Passar o cursor sobre like → verificar cor `#00ddb3`; sobre dislike → `#ef4444`.
10. Clicar em like → verificar que a barra de feedback desaparece com fade-out.

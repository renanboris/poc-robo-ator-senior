# Implementation Plan: aura-chat-panel-v2

## Overview

Este plano implementa o redesign visual e de UX do Chat_Panel da Aura DAP (extensão Chrome). As mudanças são contidas exclusivamente nos arquivos `extension/` e preservam a API pública `window.AuraUI` e todos os modos existentes (assist, gps, train, prove).

A implementação segue uma abordagem incremental: primeiro a estrutura HTML e CSS base, depois o histórico de conversa, em seguida o Typing Indicator, depois os botões de feedback, e finalmente o auto-hide inteligente. Cada etapa valida a funcionalidade antes de avançar.

---

## Tasks

- [x] 1. Atualizar estrutura HTML do Chat_Panel e estilos base
  - Modificar `extension/content.js` para adicionar `.aura-panel-header` e `#aura-thread-area` dentro de `#aura-speech-bubble`
  - Remover o elemento `.aura-text` do HTML estático (substituído pela Thread_Area)
  - Preservar `.aura-options` e `.aura-input-wrapper` sem alterações
  - Atualizar `extension/style.css` com fundo sólido `rgba(255,255,255,0.92)` e `backdrop-filter: blur(16px)` para `#aura-speech-bubble`
  - Adicionar regra `@supports not (backdrop-filter: blur(1px))` com fallback `background: #ffffff` sólido
  - Aplicar o mesmo padrão de opacidade alta para `.aura-chat-bubble` (Chat_Stack)
  - Adicionar estilos para `.aura-panel-header`, `.aura-panel-title` e `.aura-btn-close`
  - Adicionar estilos para `.aura-thread-area` (max-height: 260px, overflow-y: auto, scroll-behavior: smooth)
  - Adicionar estilos para scrollbar customizada da Thread_Area
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [ ]* 1.1 Escrever testes de exemplo para estilos CSS do fundo
  - Verificar que `#aura-speech-bubble` tem `background: rgba(255,255,255,0.92)`
  - Verificar que `#aura-speech-bubble` tem `backdrop-filter: blur(16px)`
  - Verificar que a regra `@supports not (backdrop-filter)` define `background: #ffffff`
  - Verificar que `.aura-chat-bubble` tem `background: rgba(255,255,255,0.92)`
  - _Requirements: 1.1, 1.2, 1.3, 1.5_

- [x] 2. Implementar sistema de histórico de conversa e Message_Bubbles
  - [x] 2.1 Adicionar estado privado em `extension/modules/aura_ui.js`
    - Adicionar variáveis `_historico = []`, `_typingBubbleEl = null`, `_typingTimeout = null`
    - Adicionar flag `_scrollListenerRegistrado = false` para evitar duplicação de listeners
    - _Requirements: 4.1, 4.2, 4.6_

  - [x] 2.2 Implementar helpers de renderização de Message_Bubbles
    - Criar função `_getThreadArea()` que retorna `document.getElementById('aura-thread-area')`
    - Criar função `_appendBubble(role, texto)` que cria `<div class="aura-msg-bubble aura-msg-{role}">`, adiciona ao DOM, chama `_scrollThreadToBottom()` e retorna o elemento
    - Criar função `_scrollThreadToBottom()` que define `scrollTop = scrollHeight` na Thread_Area
    - _Requirements: 4.4, 4.5_

  - [x] 2.3 Implementar função `adicionarMensagemUsuario(texto)`
    - Adicionar entry ao `_historico` com `{ role: 'user', texto, timestamp: Date.now() }`
    - Chamar `_appendBubble('user', texto)` para renderizar
    - Expor no namespace `window.AuraUI`
    - _Requirements: 4.2, 4.4_

  - [x] 2.4 Adaptar função `exibirBalao(texto, opcoes, mostrarFeedback)`
    - Preservar assinatura pública sem alterações
    - Substituir escrita em `.aura-text` por chamada a `_appendBubble('aura', texto)`
    - Adicionar entry ao `_historico` com `{ role: 'aura', texto, timestamp: Date.now() }`
    - Garantir que `bubble.classList.add('active')` ainda ocorre
    - Preservar lógica de chips de sugestão e feedback em `.aura-options`
    - _Requirements: 4.3, 4.4, 4.8_

  - [x] 2.5 Adicionar estilos CSS para Message_Bubbles
    - Adicionar regras para `.aura-msg-bubble` (max-width: 85%, padding, border-radius, word-break)
    - Adicionar regras para `.aura-msg-aura` (align-self: flex-start, background verde-claro, border-radius assimétrico)
    - Adicionar regras para `.aura-msg-user` (align-self: flex-end, background verde, texto branco, border-radius assimétrico)
    - _Requirements: 4.4_

  - [ ]* 2.6 Escrever teste de propriedade para round-trip do histórico
    - **Property 4: Round-trip do histórico de conversa**
    - **Validates: Requirements 4.1, 4.2, 4.3**
    - Usar `fc.array(fc.record({ pergunta: fc.string(), resposta: fc.string() }))` para gerar sequências de pares
    - Verificar que após cada ciclo `dispararAnalise()` + `AURA_RESPONSE`, o `_historico` contém entradas com roles corretos e campos válidos
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ]* 2.7 Escrever teste de propriedade para renderização de Message_Bubbles
    - **Property 5: Renderização fiel de Message_Bubbles para qualquer sequência**
    - **Validates: Requirements 4.4**
    - Usar `fc.array(fc.oneof(fc.constant('aura'), fc.constant('user')))` para gerar sequências de roles
    - Verificar que cada mensagem renderizada tem a classe CSS correta (`aura-msg-aura` ou `aura-msg-user`)
    - _Requirements: 4.4_

  - [ ]* 2.8 Escrever teste de propriedade para scroll automático
    - **Property 6: Scroll automático para o fundo após qualquer append**
    - **Validates: Requirements 4.5**
    - Usar `fc.integer({ min: 1, max: 50 })` para gerar N mensagens
    - Verificar que após cada `_appendBubble()`, `scrollTop === scrollHeight` na Thread_Area
    - _Requirements: 4.5_

  - [ ]* 2.9 Escrever teste de propriedade para preservação do histórico ao esconder
    - **Property 7: `esconderBalao()` preserva o histórico**
    - **Validates: Requirements 4.7**
    - Usar `fc.array(fc.record({ role: fc.constantFrom('aura', 'user'), texto: fc.string() }))` para gerar histórico
    - Verificar que após `esconderBalao()`, o `_historico` tem o mesmo comprimento e conteúdo
    - _Requirements: 4.7_

- [ ] 3. Checkpoint - Validar histórico de conversa
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implementar Typing Indicator animado
  - [x] 4.1 Implementar função `exibirTypingIndicator()`
    - Criar `<div class="aura-typing-bubble" aria-label="Aura está digitando">` com `.aura-typing-dots` contendo 3 `<span>`
    - Armazenar referência em `_typingBubbleEl`
    - Ativar `_bubbleEngajada = true` (Engagement_Lock)
    - Iniciar `_typingTimeout` de 30s que chama `removerTypingIndicator()` e exibe mensagem de erro
    - Expor no namespace `window.AuraUI`
    - _Requirements: 3.1, 3.2, 3.4, 3.5_

  - [x] 4.2 Implementar função `removerTypingIndicator()`
    - Remover `_typingBubbleEl` do DOM se existir
    - Cancelar `_typingTimeout`
    - Zerar `_typingBubbleEl = null`
    - Expor no namespace `window.AuraUI`
    - _Requirements: 3.3_

  - [x] 4.3 Adicionar estilos CSS para Typing Indicator
    - Adicionar regras para `.aura-typing-bubble` (align-self: flex-start, background verde-claro, border-radius)
    - Verificar que `.aura-typing-dots` já existe em `extension/style.css` com animação de 3 spans
    - _Requirements: 3.2_

  - [x] 4.4 Adaptar `dispararAnalise()` em `extension/modules/aura_assist_engine.js`
    - Substituir chamada direta a `exibirBalao('Já estou analisando...')` por `adicionarMensagemUsuario(prompt)` + `exibirTypingIndicator()`
    - Adicionar guard `if (global.AuraUI.exibirTypingIndicator)` com fallback para `exibirBalao` (compatibilidade retroativa)
    - _Requirements: 3.1_

  - [x] 4.5 Adaptar `_handleMessage()` em `extension/modules/aura_assist_engine.js`
    - Adicionar chamada a `removerTypingIndicator()` antes de `exibirBalao()` no handler de `AURA_RESPONSE`
    - Adicionar guard `if (global.AuraUI.removerTypingIndicator)` para compatibilidade
    - _Requirements: 3.3_

  - [ ]* 4.6 Escrever teste de exemplo para estrutura DOM do Typing Indicator
    - Verificar que `.aura-typing-dots` contém exatamente 3 elementos `<span>`
    - Verificar que o container tem `aria-label="Aura está digitando"`
    - _Requirements: 3.2, 3.5_

  - [ ]* 4.7 Escrever teste de exemplo para timeout de 30s
    - Mockar `setTimeout` e avançar 30s
    - Verificar que `removerTypingIndicator()` foi chamado
    - Verificar que mensagem de erro foi exibida
    - _Requirements: 3.4_

  - [ ]* 4.8 Escrever teste de propriedade para remoção do Typing Indicator
    - **Property 3: Typing_Indicator removido e resposta exibida para qualquer texto**
    - **Validates: Requirements 3.3**
    - Usar `fc.string({ minLength: 1 })` para gerar textos de resposta
    - Verificar que após `AURA_RESPONSE`, `.aura-typing-bubble` está ausente e `.aura-msg-aura` está presente
    - _Requirements: 3.3_

- [ ] 5. Checkpoint - Validar Typing Indicator
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implementar botões de feedback com SVG estilizado
  - [x] 6.1 Substituir emoji por SVG inline em `extension/modules/aura_feedback.js`
    - Substituir `like.textContent = '👍'` por SVG thumbs-up inline
    - Substituir `dislike.textContent = '👎'` por SVG thumbs-down inline
    - Adicionar `aria-hidden="true"` nos elementos SVG
    - Adicionar classes `aura-fb-like` e `aura-fb-dislike` nos botões
    - Remover estilos inline dos botões (delegar para CSS)
    - Preservar lógica de registro em `localStorage` e fade-out sem alterações
    - _Requirements: 2.1, 2.5, 2.6_

  - [x] 6.2 Adicionar estilos CSS para botões de feedback
    - Adicionar regras para `.aura-fb-btn` (background: transparent, border: none, color: #94a3b8, display: inline-flex)
    - Adicionar regras para `.aura-fb-btn svg` (width: 16px, height: 16px)
    - Adicionar regras para `.aura-fb-btn.aura-fb-like:hover` (color: #00ddb3)
    - Adicionar regras para `.aura-fb-btn.aura-fb-dislike:hover` (color: #ef4444)
    - _Requirements: 2.2, 2.3, 2.4, 2.6_

  - [ ]* 6.3 Escrever testes de exemplo para botões de feedback
    - Verificar que botões like/dislike contêm elemento `<svg>`, não emoji
    - Verificar que botões não têm atributo `style` inline
    - _Requirements: 2.1, 2.6_

  - [ ]* 6.4 Escrever teste de propriedade para round-trip de feedback no localStorage
    - **Property 2: Round-trip de feedback no localStorage**
    - **Validates: Requirements 2.5**
    - Usar `fc.string()` para gerar prompts (incluindo vazios, especiais, longos)
    - Verificar que após click em like/dislike, `localStorage` contém entry com campos corretos (tipo, prompt truncado a 100 chars, url, ts)
    - _Requirements: 2.5_

- [x] 7. Implementar auto-hide inteligente com Engagement_Lock
  - [x] 7.1 Implementar função `_initScrollEngajamento()`
    - Verificar flag `_scrollListenerRegistrado` para evitar duplicação
    - Adicionar listener de `scroll` na Thread_Area
    - No handler: ativar `_bubbleEngajada = true`, cancelar `_bubbleTimeout`
    - Reiniciar timer de 12s após 12s sem interação (via `setTimeout` interno)
    - Marcar `_scrollListenerRegistrado = true`
    - _Requirements: 5.1, 5.4_

  - [x] 7.2 Adaptar lógica de auto-hide em `exibirBalao()`
    - Verificar `_bubbleEngajada` antes de fechar o painel pelo timer de 12s
    - Verificar se `_typingBubbleEl !== null` (não fechar durante Typing Indicator)
    - Preservar comportamento de `mouseenter` e `focus` no input para ativar Engagement_Lock
    - _Requirements: 5.2, 5.3_

  - [x] 7.3 Chamar `_initScrollEngajamento()` em `init()`
    - Adicionar chamada após `_initEngajamento()` existente
    - _Requirements: 5.4_

  - [ ]* 7.4 Escrever teste de propriedade para Engagement_Lock
    - **Property 8: Engagement_Lock impede o auto-hide**
    - **Validates: Requirements 5.2**
    - Usar `fc.boolean()` para gerar estado inicial do lock
    - Verificar que quando `_bubbleEngajada = true`, o painel permanece `active` após 12s
    - _Requirements: 5.2_

  - [ ]* 7.5 Escrever teste de propriedade para listener único de scroll
    - **Property 9: Listener de scroll registrado exatamente uma vez**
    - **Validates: Requirements 5.4**
    - Usar `fc.integer({ min: 1, max: 20 })` para gerar N chamadas a `exibirBalao()`
    - Verificar que um evento de scroll dispara o handler exatamente 1x (não N vezes)
    - _Requirements: 5.4_

- [ ] 8. Checkpoint - Validar auto-hide inteligente
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Validar preservação da API pública e compatibilidade
  - [ ]* 9.1 Escrever testes de fumaça para API pública
    - Verificar que `window.AuraUI` existe após carregamento
    - Verificar que todos os 10 métodos públicos são funções: `init`, `exibirBalao`, `exibirBaloesSequenciais`, `esconderBalao`, `ativarBadge`, `desativarBadge`, `tocarAnimacao`, `setLastPrompt`, `wasPlayerDragged`, `resetDragFlag`
    - Verificar que nenhum novo arquivo JS externo foi introduzido
    - Verificar que apenas arquivos em `extension/` foram modificados
    - _Requirements: 6.1, 6.2, 6.4, 6.5_

  - [ ]* 9.2 Escrever teste de propriedade para métodos públicos preservados
    - **Property 10: Todos os métodos públicos da API preservados**
    - **Validates: Requirements 6.1**
    - Usar `fc.constantFrom(...10 method names)` para gerar nomes de métodos
    - Verificar que `typeof window.AuraUI[methodName] === 'function'`
    - _Requirements: 6.1_

  - [ ]* 9.3 Escrever teste de propriedade para compatibilidade com modos
    - **Property 11: `exibirBalao` funciona em qualquer modo**
    - **Validates: Requirements 6.3**
    - Usar `fc.constantFrom('assist', 'gps', 'train', 'prove')` para gerar modos
    - Verificar que após `AuraState.setMode(modo)`, `exibirBalao(texto, [], false)` renderiza bubble sem exceções
    - _Requirements: 6.3_

  - [ ]* 9.4 Escrever teste de exemplo para `esconderBalao()`
    - Verificar que `esconderBalao()` remove classe `active` do painel
    - Verificar que `_historico` não é limpo (preservado para reabrir)
    - _Requirements: 4.7, 6.2_

- [ ]* 10. Escrever teste de propriedade para contraste WCAG
  - **Property 1: Contraste WCAG sobre qualquer fundo**
  - **Validates: Requirements 1.4**
  - Usar `fc.tuple(fc.integer(0,255), fc.integer(0,255), fc.integer(0,255))` para gerar cores RGB de fundo
  - Implementar função de composição de `rgba(255,255,255,0.92)` sobre cor de fundo
  - Implementar função de cálculo de contraste WCAG 2.1
  - Verificar que contraste entre texto `#1e293b` e fundo composto é >= 4.5:1
  - _Requirements: 1.4_

- [ ] 11. Checkpoint final - Validar integração completa
  - Ensure all tests pass, ask the user if questions arise.

---

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- Cada task referencia requirements específicos para rastreabilidade
- Checkpoints garantem validação incremental
- Testes de propriedade validam invariantes universais usando fast-check (100 iterações)
- Testes de exemplo validam comportamentos específicos e estrutura DOM/CSS
- A implementação preserva a API pública `window.AuraUI` (10 métodos) sem alterações de assinatura
- Todos os modos existentes (assist, gps, train, prove) são preservados
- Nenhuma nova dependência externa é introduzida
- Apenas arquivos em `extension/` são modificados

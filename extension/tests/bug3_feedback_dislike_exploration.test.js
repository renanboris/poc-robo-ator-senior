// Bug 3 — Feedback Dislike postMessage Exploration Test
//
// **Validates: Requirements 3.1, 3.2**
//
// OBJETIVO: Confirmar que o bug existe no código NÃO corrigido.
// Este teste DEVE FALHAR no código não corrigido — a falha confirma que
// nenhum `postMessage` com `type: 'AURA_FEEDBACK_EVENT'` é emitido ao
// clicar no botão 👎.
//
// CAUSA RAIZ: A closure `_registrar` em `aura_feedback.js` salva o feedback
// no `localStorage` e remove a barra visualmente, mas NÃO emite `postMessage`
// para o bridge. Sem a mensagem no bridge, nenhuma chamada chega ao
// `background.js` e nenhuma requisição é feita ao backend.
//
// ESTRATÉGIA DO TESTE:
//   - Carregar `aura_feedback.js` via eval (padrão do projeto)
//   - Interceptar `window.postMessage` com jest.spyOn antes de clicar
//   - Clicar no botão dislike (`aura-fb-dislike`)
//   - Verificar que nenhuma chamada a `postMessage` com
//     `type: 'AURA_FEEDBACK_EVENT'` foi emitida (confirma o bug)
//   - Verificar que `localStorage` contém a entrada (comportamento existente)
//   - Verificar que clique em like também não emite `postMessage`
//     (comportamento correto — não falha)
//
// COUNTEREXAMPLE DOCUMENTADO:
//   postMessageEmitido = false após clique em dislike
//   Causa raiz: `_registrar` não contém `window.postMessage` para o caminho
//   dislike no código não corrigido.
//
// DO NOT attempt to fix the test or the code when it fails.

'use strict';

const fs   = require('fs');
const path = require('path');

// ─────────────────────────────────────────────────────────────────────────────
// Carregamento do módulo real via eval (padrão do projeto)
// ─────────────────────────────────────────────────────────────────────────────

function loadAuraFeedback() {
  const code = fs.readFileSync(
    path.join(__dirname, '..', 'modules', 'aura_feedback.js'),
    'utf8'
  );
  // eslint-disable-next-line no-eval
  (0, eval)(code);
}

// ─────────────────────────────────────────────────────────────────────────────
// Suite principal
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 3 — Feedback Dislike postMessage Exploration (código NÃO corrigido)', () => {

  let postMessageSpy;
  let postMessageCalls;

  beforeEach(() => {
    // Limpa o DOM e o localStorage antes de cada teste
    document.body.innerHTML = '';
    localStorage.clear();

    // Silencia logs do módulo
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});

    // Intercepta window.postMessage e registra todas as chamadas
    postMessageCalls = [];
    postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(function (message) {
      postMessageCalls.push(message);
    });

    // Carrega o módulo real
    loadAuraFeedback();
  });

  afterEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();
    jest.clearAllMocks();
    jest.restoreAllMocks();
    delete global.AuraFeedback;
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 1 — BUG CONDITION PRINCIPAL (deve FALHAR no código não corrigido)
  //
  // Verifica que nenhum `postMessage` com `type: 'AURA_FEEDBACK_EVENT'`
  // é emitido ao clicar no botão dislike.
  //
  // No código NÃO corrigido: `_registrar('dislike', ...)` não chama
  //   `window.postMessage` → postMessageEmitido = false → assertion FALHA ✓
  //
  // No código CORRIGIDO: `_registrar('dislike', ...)` chama
  //   `window.postMessage({ type: 'AURA_FEEDBACK_EVENT', payload })` →
  //   postMessageEmitido = true → assertion PASSA ✓
  //
  // COUNTEREXAMPLE: postMessageEmitido = false após clique em dislike
  // ───────────────────────────────────────────────────────────────────────────
  test('BUG CONDITION: clique em dislike deve emitir postMessage com type AURA_FEEDBACK_EVENT (DEVE FALHAR agora)', () => {
    // Cria a barra de feedback com o módulo real
    const bar = global.AuraFeedback.criar('prompt de teste', 'resposta de teste');
    document.body.appendChild(bar);

    const dislikeBtn = bar.querySelector('.aura-fb-dislike');
    expect(dislikeBtn).not.toBeNull();

    // Clica no botão dislike
    dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    // Filtra chamadas a postMessage com type: 'AURA_FEEDBACK_EVENT'
    const feedbackMessages = postMessageCalls.filter(
      msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
    );

    // ASSERTION QUE DEVE FALHAR NO CÓDIGO NÃO CORRIGIDO:
    //
    // Após o clique em dislike, deve ter sido emitido pelo menos um
    // postMessage com type: 'AURA_FEEDBACK_EVENT'.
    //
    // No código NÃO corrigido: feedbackMessages.length === 0 → FALHA ✓
    //
    // COUNTEREXAMPLE: postMessageEmitido = false após clique em dislike
    // Causa raiz: `_registrar` não contém `window.postMessage` para o
    // caminho dislike no código não corrigido.
    expect(feedbackMessages.length).toBeGreaterThan(0);
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 2 — BUG CONDITION: payload deve conter campos corretos
  //
  // Verifica que o postMessage emitido contém o payload esperado:
  //   { tipo: 'dislike', prompt, url, ts }
  //
  // No código NÃO corrigido: nenhum postMessage é emitido → assertion FALHA ✓
  // No código CORRIGIDO: postMessage emitido com payload correto → PASSA ✓
  // ───────────────────────────────────────────────────────────────────────────
  test('BUG CONDITION: postMessage de dislike deve conter payload { tipo, prompt, url, ts } (DEVE FALHAR agora)', () => {
    const promptTexto = 'como criar um pedido de compra';
    const bar = global.AuraFeedback.criar(promptTexto, 'resposta qualquer');
    document.body.appendChild(bar);

    const dislikeBtn = bar.querySelector('.aura-fb-dislike');
    dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    // Filtra mensagens AURA_FEEDBACK_EVENT
    const feedbackMessages = postMessageCalls.filter(
      msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
    );

    // ASSERTION QUE DEVE FALHAR NO CÓDIGO NÃO CORRIGIDO:
    // Deve existir pelo menos uma mensagem com o payload correto
    expect(feedbackMessages.length).toBeGreaterThan(0);

    const msg = feedbackMessages[0];
    expect(msg.payload).toBeDefined();
    expect(msg.payload.tipo).toBe('dislike');
    expect(typeof msg.payload.prompt).toBe('string');
    expect(typeof msg.payload.url).toBe('string');
    expect(typeof msg.payload.ts).toBe('number');
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 3 — COMPORTAMENTO EXISTENTE: localStorage deve ser salvo após dislike
  //
  // Este caso NÃO deve falhar — confirma que o comportamento existente de
  // persistência no localStorage é preservado.
  //
  // EXPECTED: localStorage contém a entrada após clique em dislike
  // ───────────────────────────────────────────────────────────────────────────
  test('COMPORTAMENTO EXISTENTE: localStorage deve conter entrada após clique em dislike (não falha)', () => {
    const bar = global.AuraFeedback.criar('prompt de teste', 'resposta de teste');
    document.body.appendChild(bar);

    const dislikeBtn = bar.querySelector('.aura-fb-dislike');

    // Verifica que localStorage está vazio antes do clique
    expect(localStorage.length).toBe(0);

    // Clica no botão dislike
    dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    // EXPECTED: localStorage deve conter pelo menos uma entrada
    expect(localStorage.length).toBeGreaterThan(0);

    // Verifica que a entrada contém tipo: 'dislike'
    let encontrouDislike = false;
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      const value = JSON.parse(localStorage.getItem(key));
      if (value && value.tipo === 'dislike') {
        encontrouDislike = true;
        break;
      }
    }
    expect(encontrouDislike).toBe(true);
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 4 — COMPORTAMENTO CORRETO: like NÃO deve emitir postMessage
  //
  // Este caso NÃO deve falhar — confirma que o like não emite postMessage
  // (comportamento correto que deve ser preservado pelo fix).
  //
  // EXPECTED: nenhum postMessage com type: 'AURA_FEEDBACK_EVENT' após like
  // ───────────────────────────────────────────────────────────────────────────
  test('COMPORTAMENTO CORRETO: clique em like NÃO deve emitir postMessage AURA_FEEDBACK_EVENT (não falha)', () => {
    const bar = global.AuraFeedback.criar('prompt de teste', 'resposta de teste');
    document.body.appendChild(bar);

    const likeBtn = bar.querySelector('.aura-fb-like');
    expect(likeBtn).not.toBeNull();

    // Clica no botão like
    likeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    // Filtra chamadas a postMessage com type: 'AURA_FEEDBACK_EVENT'
    const feedbackMessages = postMessageCalls.filter(
      msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
    );

    // EXPECTED: nenhum postMessage de feedback emitido para like
    // Este comportamento deve ser preservado pelo fix
    expect(feedbackMessages.length).toBe(0);
  });


  // ───────────────────────────────────────────────────────────────────────────
  // Caso 5 — DOCUMENTAÇÃO DO COUNTEREXAMPLE
  //
  // Documenta explicitamente o counterexample do Bug 3:
  //   Input:  clique no botão dislike com prompt e url válidos
  //   Bug:    nenhum postMessage com type: 'AURA_FEEDBACK_EVENT' emitido
  //   Fix:    postMessage emitido com { type: 'AURA_FEEDBACK_EVENT', payload }
  //
  // ASSERTION: postMessageEmitido deve ser true após clique em dislike
  // FALHA no código não corrigido (postMessageEmitido = false) ✓
  // ───────────────────────────────────────────────────────────────────────────
  test('COUNTEREXAMPLE: documenta postMessageEmitido = false após clique em dislike (DEVE FALHAR agora)', () => {
    const bar = global.AuraFeedback.criar('consulta sobre relatório financeiro', 'resposta da IA');
    document.body.appendChild(bar);

    const dislikeBtn = bar.querySelector('.aura-fb-dislike');

    // Registra estado antes do clique
    const postMessageCountBefore = postMessageCalls.length;

    // Único clique no dislike
    dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

    // Captura o estado após o clique
    const feedbackMessagesAfterClick = postMessageCalls.filter(
      msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
    );
    const postMessageEmitido = feedbackMessagesAfterClick.length > 0;

    // DOCUMENTAÇÃO DO COUNTEREXAMPLE:
    // No código NÃO corrigido: postMessageEmitido === false
    //   (porque `_registrar` não chama `window.postMessage` para dislike)
    // No código CORRIGIDO: postMessageEmitido === true
    //   (porque `_registrar` emite `window.postMessage({ type: 'AURA_FEEDBACK_EVENT', payload })`)
    //
    // A assertion abaixo FALHA no código não corrigido (confirma o bug):
    // postMessageEmitido deve ser true após clique em dislike
    expect(postMessageEmitido).toBe(true);

    // Adicionalmente: localStorage deve ter sido salvo (comportamento existente)
    expect(localStorage.length).toBeGreaterThan(0);
  });

});

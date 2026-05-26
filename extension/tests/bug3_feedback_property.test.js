// Feature: aura-gps-feedback-bugs, Property 5: Dislike propaga ao backend
//
// Property tests (Task 9) — Validates: Requirements 2.6, 2.7, 2.8 (Property 5)
//                                       Requirements 3.8, 3.9, 3.10 (Property 6)
//
// Property 5 — Fix Checking:
//   Para todo payload de dislike, verificar que `postMessage` é sempre emitido
//   com os campos corretos: type = 'AURA_FEEDBACK_EVENT', payload.tipo = 'dislike'.
//   O fix adiciona `window.postMessage({ type: 'AURA_FEEDBACK_EVENT', payload }, origin)`
//   no caminho `tipo === 'dislike'` da closure `_registrar` em `aura_feedback.js`.
//
// Property 6 — Preservation:
//   Para todo payload de like, verificar que nenhum `postMessage` com
//   `type: 'AURA_FEEDBACK_EVENT'` é emitido — comportamento original preservado.
//   Verificar também que `localStorage` é salvo para likes (comportamento existente).
//
// Framework: Jest (jsdom) + fast-check (≥ 100 iterações).

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

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
// Geradores fast-check
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Gera strings de prompt com 1–100 caracteres (ASCII imprimível).
 */
const arbPrompt = fc.string({ minLength: 1, maxLength: 100 });

/**
 * Gera URLs válidas no formato http(s)://host/path.
 * Usa fc.webUrl() que produz URLs bem formadas.
 */
const arbUrl = fc.webUrl();

/**
 * Gera timestamps inteiros positivos (ms desde epoch).
 */
const arbTs = fc.integer({ min: 1_000_000, max: 9_999_999_999_999 });

// ─────────────────────────────────────────────────────────────────────────────
// Suite — Property 5: Fix Checking (dislike propaga ao backend)
//
// Cenário: Para todo payload de dislike gerado aleatoriamente, o módulo
// corrigido DEVE emitir `window.postMessage` com:
//   - type === 'AURA_FEEDBACK_EVENT'
//   - payload.tipo === 'dislike'
//   - payload.prompt === string truncada a 100 chars
//   - payload.url === string
//   - payload.ts === number
// E DEVE salvar no localStorage (comportamento existente preservado).
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 3 — Property 5: Fix Checking — dislike sempre emite postMessage com campos corretos', () => {

  let postMessageSpy;
  let postMessageCalls;

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();

    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});

    postMessageCalls = [];
    postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(function (message) {
      postMessageCalls.push(message);
    });

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
  // Property 5a — Para todo prompt (1–100 chars), postMessage é emitido após
  // clique em dislike com type === 'AURA_FEEDBACK_EVENT'.
  //
  // Validates: Requirements 2.6, 2.7, 2.8
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: dislike sempre emite postMessage com type AURA_FEEDBACK_EVENT', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          // Reset entre iterações
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta qualquer');
          document.body.appendChild(bar);

          const dislikeBtn = bar.querySelector('.aura-fb-dislike');
          if (!dislikeBtn) return false;

          dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const feedbackMessages = postMessageCalls.filter(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );

          // postMessageEmitido deve ser true para todo prompt de dislike
          return feedbackMessages.length > 0;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 5b — Para todo prompt (1–100 chars), o payload do postMessage
  // contém os campos corretos: tipo='dislike', prompt (string), url (string),
  // ts (number).
  //
  // Validates: Requirements 2.6, 2.7, 2.8
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: payload do postMessage de dislike contém { tipo, prompt, url, ts } corretos', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(bar);

          const dislikeBtn = bar.querySelector('.aura-fb-dislike');
          if (!dislikeBtn) return false;

          dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const feedbackMessages = postMessageCalls.filter(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );

          if (feedbackMessages.length === 0) return false;

          const msg = feedbackMessages[0];

          // Verifica estrutura do payload
          if (!msg.payload) return false;
          if (msg.payload.tipo !== 'dislike') return false;
          if (typeof msg.payload.prompt !== 'string') return false;
          if (typeof msg.payload.url !== 'string') return false;
          if (typeof msg.payload.ts !== 'number') return false;

          // Verifica que prompt foi truncado a 100 chars
          if (msg.payload.prompt.length > 100) return false;

          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 5c — Para todo prompt (1–100 chars), localStorage é salvo após
  // clique em dislike (comportamento existente preservado pelo fix).
  //
  // Validates: Requirements 2.6, 2.8
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: localStorage é salvo após dislike (comportamento existente preservado)', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(bar);

          const dislikeBtn = bar.querySelector('.aura-fb-dislike');
          if (!dislikeBtn) return false;

          // Verifica que localStorage está vazio antes do clique
          if (localStorage.length !== 0) return false;

          dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // localStorage deve conter pelo menos uma entrada após dislike
          if (localStorage.length === 0) return false;

          // Verifica que a entrada contém tipo: 'dislike'
          let encontrouDislike = false;
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            try {
              const value = JSON.parse(localStorage.getItem(key));
              if (value && value.tipo === 'dislike') {
                encontrouDislike = true;
                break;
              }
            } catch (_) {}
          }

          return encontrouDislike;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 5d — Para todo prompt (1–100 chars), postMessage e localStorage
  // são emitidos/salvos simultaneamente (ambos ocorrem no mesmo clique).
  //
  // Validates: Requirements 2.6, 2.7, 2.8
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: dislike emite postMessage E salva localStorage no mesmo clique', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(bar);

          const dislikeBtn = bar.querySelector('.aura-fb-dislike');
          if (!dislikeBtn) return false;

          dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const postMessageEmitido = postMessageCalls.some(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );
          const localStorageSalvo = localStorage.length > 0;

          // Ambos devem ser true após um único clique em dislike
          return postMessageEmitido && localStorageSalvo;
        }
      ),
      { numRuns: 100 }
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Suite — Property 6: Preservation (like não envia chamada ao backend)
//
// Cenário: Para todo payload de like gerado aleatoriamente, o módulo
// corrigido NÃO DEVE emitir `window.postMessage` com type 'AURA_FEEDBACK_EVENT'.
// Deve apenas salvar no localStorage (comportamento original preservado).
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 3 — Property 6: Preservation — like nunca emite postMessage AURA_FEEDBACK_EVENT', () => {

  let postMessageSpy;
  let postMessageCalls;

  beforeEach(() => {
    document.body.innerHTML = '';
    localStorage.clear();

    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});

    postMessageCalls = [];
    postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(function (message) {
      postMessageCalls.push(message);
    });

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
  // Property 6a — Para todo prompt (1–100 chars), nenhum postMessage com
  // type 'AURA_FEEDBACK_EVENT' é emitido após clique em like.
  //
  // Validates: Requirements 3.8, 3.9, 3.10
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: like nunca emite postMessage com type AURA_FEEDBACK_EVENT', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta qualquer');
          document.body.appendChild(bar);

          const likeBtn = bar.querySelector('.aura-fb-like');
          if (!likeBtn) return false;

          likeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const feedbackMessages = postMessageCalls.filter(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );

          // Nenhum postMessage de feedback deve ser emitido para like
          return feedbackMessages.length === 0;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 6b — Para todo prompt (1–100 chars), localStorage é salvo após
  // clique em like (comportamento existente preservado).
  //
  // Validates: Requirements 3.8, 3.9
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: localStorage é salvo após like (comportamento existente preservado)', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(bar);

          const likeBtn = bar.querySelector('.aura-fb-like');
          if (!likeBtn) return false;

          if (localStorage.length !== 0) return false;

          likeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // localStorage deve conter pelo menos uma entrada após like
          if (localStorage.length === 0) return false;

          // Verifica que a entrada contém tipo: 'like'
          let encontrouLike = false;
          for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            try {
              const value = JSON.parse(localStorage.getItem(key));
              if (value && value.tipo === 'like') {
                encontrouLike = true;
                break;
              }
            } catch (_) {}
          }

          return encontrouLike;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 6c — Para todo prompt (1–100 chars), like salva localStorage
  // mas NÃO emite postMessage (ambas as condições verificadas juntas).
  //
  // Validates: Requirements 3.8, 3.9, 3.10
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: like salva localStorage mas não emite postMessage (ambas condições)', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const bar = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(bar);

          const likeBtn = bar.querySelector('.aura-fb-like');
          if (!likeBtn) return false;

          likeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const postMessageNaoEmitido = postMessageCalls.filter(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          ).length === 0;

          const localStorageSalvo = localStorage.length > 0;

          // Like: sem postMessage E com localStorage salvo
          return postMessageNaoEmitido && localStorageSalvo;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 6d — Assimetria dislike/like: para o mesmo prompt, dislike emite
  // postMessage e like não emite. Verifica que o fix é cirúrgico (apenas dislike).
  //
  // Validates: Requirements 3.8, 3.9, 3.10
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: assimetria dislike/like — mesmo prompt, comportamentos distintos', () => {
    fc.assert(
      fc.property(
        arbPrompt,
        (prompt) => {
          // ── Teste com DISLIKE ──
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const barDislike = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(barDislike);
          const dislikeBtn = barDislike.querySelector('.aura-fb-dislike');
          if (!dislikeBtn) return false;
          dislikeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const dislikeEmitiu = postMessageCalls.some(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );

          // ── Teste com LIKE ──
          document.body.innerHTML = '';
          localStorage.clear();
          postMessageCalls.length = 0;
          delete global.AuraFeedback;
          loadAuraFeedback();

          const barLike = global.AuraFeedback.criar(prompt, 'resposta');
          document.body.appendChild(barLike);
          const likeBtn = barLike.querySelector('.aura-fb-like');
          if (!likeBtn) return false;
          likeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          const likeEmitiu = postMessageCalls.some(
            msg => msg && msg.type === 'AURA_FEEDBACK_EVENT'
          );

          // Dislike DEVE emitir, like NÃO DEVE emitir
          return dislikeEmitiu === true && likeEmitiu === false;
        }
      ),
      { numRuns: 100 }
    );
  });
});

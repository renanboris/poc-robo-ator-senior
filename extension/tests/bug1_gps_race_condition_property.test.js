// Feature: aura-gps-feedback-bugs, Property 1: GPS não valida passo N+1 com evento do passo N
//
// Property tests (Task 3) — Validates: Requirements 2.1, 2.2, 2.3 (Property 1)
//                                       Requirements 3.1, 3.2, 3.3, 3.4 (Property 2)
//
// Property 1 — Fix Checking:
//   Para todo roteiro com passos de target_selector que usam delegação no document
//   (AuraSpotlight retorna null), um único clique avança exatamente um passo (não dois).
//   O fix usa setTimeout(fn, 0) para diferir _iniciarPasso quando o próximo passo
//   usa delegação — garantindo que passo_validado_sem_acao_real = false.
//
// Property 2 — Preservation:
//   Para todo roteiro com target_selector válido e elemento presente no DOM
//   (AuraSpotlight retorna o elemento), _iniciarPasso não introduz setTimeout —
//   a transição é síncrona, comportamento idêntico ao original.
//
// Framework: Jest (jsdom) + fast-check (≥ 100 iterações).

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Carregamento do módulo real via eval (padrão do projeto)
// ─────────────────────────────────────────────────────────────────────────────

function loadGpsEngine() {
  const code = fs.readFileSync(
    path.join(__dirname, '..', 'modules', 'aura_gps_engine.js'),
    'utf8'
  );
  // eslint-disable-next-line no-eval
  (0, eval)(code);
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers de setup
// ─────────────────────────────────────────────────────────────────────────────

function makeAuraStateStub() {
  return {
    getMode:        jest.fn().mockReturnValue('gps'),
    setMode:        jest.fn(),
    registerModule: jest.fn(),
    session:        { steps_total: 0, tenant_id: 'senior_default', roteiro_id: null }
  };
}

function makeAuraUIStub() {
  return {
    exibirBalao:             jest.fn(),
    exibirBaloesSequenciais: jest.fn(),
    esconderBalao:           jest.fn()
  };
}

/**
 * Configura globals com AuraSpotlight que sempre retorna null (delegação).
 * Usado para Property 1 (fix checking).
 */
function setupGlobalsDelegacao() {
  global.AuraState     = makeAuraStateStub();
  global.AuraSpotlight = {
    aplicar:           jest.fn(),
    remover:           jest.fn(),
    encontrarElemento: jest.fn().mockReturnValue(null)
  };
  global.AuraUI = makeAuraUIStub();
}

/**
 * Configura globals com AuraSpotlight que retorna o elemento do DOM.
 * Usado para Property 2 (preservation).
 */
function setupGlobalsComElemento() {
  global.AuraState     = makeAuraStateStub();
  global.AuraSpotlight = {
    aplicar:           jest.fn(),
    remover:           jest.fn(),
    encontrarElemento: jest.fn().mockImplementation((seletor) => {
      const el = document.querySelector(seletor);
      return el ? { elemento: el } : null;
    })
  };
  global.AuraUI = makeAuraUIStub();
}

function teardownGlobals() {
  if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
    global.AuraGpsEngine.teardown();
  }
  delete global.AuraGpsEngine;
  delete global.AuraState;
  delete global.AuraSpotlight;
  delete global.AuraUI;
}

function limparDom(n) {
  for (let i = 1; i <= (n || 10); i++) {
    const el = document.getElementById(`btn-${i}`);
    if (el) el.remove();
  }
  const panel = document.getElementById('aura-gps-panel');
  if (panel) panel.remove();
}

/**
 * Cria N botões com IDs btn-1..btn-N no document.body.
 */
function criarBotoes(n) {
  const btns = [];
  for (let i = 1; i <= n; i++) {
    const btn = document.createElement('button');
    btn.id = `btn-${i}`;
    btn.textContent = `Botão ${i}`;
    document.body.appendChild(btn);
    btns.push(btn);
  }
  return btns;
}

/**
 * Constrói um roteiro com `numPassos` passos, todos com o mesmo seletor `#btn-1`.
 * AuraSpotlight retorna null → _usaDelegacao retorna true → fix aplica setTimeout.
 * Cada passo tem validation_type: 'click' e timeout_sec: 30.
 */
function buildRoteiroDelegacao(numPassos) {
  const passos = [];
  for (let i = 0; i < numPassos; i++) {
    passos.push({
      id:              `passo-${i}`,
      intent:          `Passo ${i} — delegação`,
      target_selector: '#btn-1',
      validation_type: 'click',
      timeout_sec:     30
    });
  }
  return { id: 'roteiro-delegacao', passos };
}

/**
 * Constrói um roteiro com `numPassos` passos, cada um com seletor único #btn-N.
 * AuraSpotlight retorna o elemento → _usaDelegacao retorna false → sem setTimeout.
 */
function buildRoteiroSeletores(numPassos) {
  const passos = [];
  for (let i = 0; i < numPassos; i++) {
    passos.push({
      id:              `passo-${i}`,
      intent:          `Passo ${i} — seletor válido`,
      target_selector: `#btn-${i + 1}`,
      validation_type: 'click',
      timeout_sec:     30
    });
  }
  return { id: 'roteiro-seletores', passos };
}

// ─────────────────────────────────────────────────────────────────────────────
// Suite — Property 1: Fix Checking (delegação)
//
// Cenário: AuraSpotlight retorna null → _usaDelegacao = true → fix aplica
// setTimeout(fn, 0) em _avancarPasso antes de chamar _iniciarPasso(N+1).
//
// Verificação da condição de fix:
//   - Imediatamente após o clique (antes do setTimeout): _stepIndex === N
//     (passo N+1 ainda não iniciado — diferido via setTimeout)
//   - Após advanceTimersByTime(0): _stepIndex === N+1
//     (passo N+1 iniciado, mas aguardando segundo clique real)
//   - passo_validado_sem_acao_real = false: _stepIndex !== N+2 após advanceTimersByTime(0)
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 1 — Property 1: Fix Checking — delegação avança exatamente um passo por clique', () => {

  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(window, 'postMessage').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    jest.clearAllMocks();
    teardownGlobals();
    limparDom(10);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 1a — Para todo roteiro com 2–5 passos de delegação (AuraSpotlight
  // retorna null), imediatamente após o clique (antes do setTimeout disparar),
  // _stepIndex ainda é 0 — passo_validado_sem_acao_real = false.
  //
  // Esta é a verificação direta do fix: _iniciarPasso(1) é diferido via
  // setTimeout(fn, 0), então _stepIndex === 0 imediatamente após o clique.
  //
  // Validates: Requirements 2.1, 2.2, 2.3
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: imediatamente após clique (antes do setTimeout), _stepIndex ainda é 0', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 5 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(1); // btn-1 para todos os passos
          setupGlobalsDelegacao();
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = buildRoteiroDelegacao(numPassos);
          global.AuraGpsEngine.init(roteiro);

          if (global.AuraGpsEngine.getCurrentStepIndex() !== 0) return false;

          // Clica em #btn-1 — valida passo 0 via delegação no document
          btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // ANTES do setTimeout disparar: _stepIndex deve ser 0
          // (passo 1 diferido via setTimeout — fix aplicado)
          // passo_validado_sem_acao_real = false
          const stepImediato = global.AuraGpsEngine.getCurrentStepIndex();
          return stepImediato === 0;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 1b — Após advanceTimersByTime(0), _stepIndex === 1:
  // o passo 1 foi iniciado (setTimeout disparou), mas NÃO validado
  // (aguarda segundo clique real).
  //
  // Validates: Requirements 2.1, 2.2, 2.3
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: após setTimeout(0) disparar, _stepIndex === 1 (passo iniciado, não validado)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 5 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(1);
          setupGlobalsDelegacao();
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = buildRoteiroDelegacao(numPassos);
          global.AuraGpsEngine.init(roteiro);

          // Clica em #btn-1 — valida passo 0
          btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // Dispara o setTimeout(fn, 0) do fix
          jest.advanceTimersByTime(0);

          // Após o setTimeout: passo 1 iniciado → _stepIndex === 1
          // Mas passo 1 NÃO foi validado (aguarda segundo clique)
          // → _stepIndex !== 2 (passo_validado_sem_acao_real = false)
          const stepApos = global.AuraGpsEngine.getCurrentStepIndex();
          return stepApos === 1;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 1c — Para cada par de passos consecutivos em roteiro de delegação,
  // disparar um clique avança stepIndex de N para N+1 (não para N+2).
  //
  // Testa múltiplas transições: clique → advanceTimersByTime(0) → clique → ...
  // Validates: Requirements 2.1, 2.2, 2.3
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: cada clique avança exatamente um passo em roteiro de delegação', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 4 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(1);
          setupGlobalsDelegacao();
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = buildRoteiroDelegacao(numPassos);
          global.AuraGpsEngine.init(roteiro);

          // Verifica cada transição N → N+1 (exceto o último passo que conclui)
          for (let n = 0; n < numPassos - 1; n++) {
            const stepAntes = global.AuraGpsEngine.getCurrentStepIndex();
            if (stepAntes !== n) return false;

            // Clica em #btn-1 — valida passo N
            btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

            // Imediatamente: _stepIndex ainda é N (passo N+1 diferido)
            if (global.AuraGpsEngine.getCurrentStepIndex() !== n) return false;

            // Após setTimeout(fn, 0): _stepIndex === N+1
            jest.advanceTimersByTime(0);
            const stepDepois = global.AuraGpsEngine.getCurrentStepIndex();

            // Deve avançar exatamente um passo (não dois)
            if (stepDepois !== n + 1) return false;
          }

          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// Suite — Property 2: Preservation (seletor válido)
//
// Cenário: AuraSpotlight retorna o elemento → _usaDelegacao = false →
// _iniciarPasso(N+1) chamado SINCRONAMENTE (sem setTimeout do fix).
//
// Verificação de preservation:
//   - Imediatamente após o clique no botão correto: _stepIndex === N+1
//     (transição síncrona — sem setTimeout introduzido pelo fix)
//   - init() inicia passo 0 imediatamente (sem setTimeout)
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug 1 — Property 2: Preservation — seletor válido não é afetado pelo fix', () => {

  beforeEach(() => {
    jest.spyOn(console, 'warn').mockImplementation(() => {});
    jest.spyOn(console, 'log').mockImplementation(() => {});
    jest.spyOn(console, 'error').mockImplementation(() => {});
    jest.spyOn(window, 'postMessage').mockImplementation(() => {});
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
    jest.clearAllMocks();
    teardownGlobals();
    limparDom(10);
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 2a — Para roteiros com seletores válidos e elementos presentes,
  // _iniciarPasso não introduz setTimeout: a transição é síncrona.
  //
  // Após clicar no botão correto, _stepIndex === N+1 IMEDIATAMENTE
  // (sem necessidade de advanceTimersByTime).
  //
  // Validates: Requirements 3.1, 3.2, 3.3, 3.4
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: seletor válido — transição síncrona após clique (sem setTimeout do fix)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 5 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(numPassos);
          setupGlobalsComElemento();
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = buildRoteiroSeletores(numPassos);
          global.AuraGpsEngine.init(roteiro);

          if (global.AuraGpsEngine.getCurrentStepIndex() !== 0) return false;

          // Clica no botão correto (#btn-1 para passo 0)
          btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // Com seletor válido: _usaDelegacao = false → _iniciarPasso(1) síncrono
          // → _stepIndex === 1 IMEDIATAMENTE (sem advanceTimersByTime)
          const stepApos = global.AuraGpsEngine.getCurrentStepIndex();
          return stepApos === 1;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 2b — init() inicia passo 0 imediatamente, independentemente do
  // target_selector (vazio ou válido). O fix não afeta o caminho init → _iniciarPasso(0).
  //
  // Validates: Requirements 3.1, 3.2
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: init() inicia passo 0 imediatamente (sem setTimeout do fix)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 5 }),
        fc.boolean(),  // true = seletor válido, false = delegação
        (numPassos, usarSeletorValido) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          if (usarSeletorValido) {
            criarBotoes(numPassos);
            setupGlobalsComElemento();
          } else {
            criarBotoes(1);
            setupGlobalsDelegacao();
          }
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = usarSeletorValido
            ? buildRoteiroSeletores(numPassos)
            : buildRoteiroDelegacao(numPassos);

          // init() chama _iniciarPasso(0) diretamente — sem setTimeout do fix
          global.AuraGpsEngine.init(roteiro);

          // Passo 0 deve estar ativo IMEDIATAMENTE após init()
          const stepAposInit = global.AuraGpsEngine.getCurrentStepIndex();
          return stepAposInit === 0;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 2c — Roteiro misto: passo 0 com seletor válido (AuraSpotlight
  // encontra elemento), passo 1 com delegação (AuraSpotlight retorna null).
  //
  // Após clicar no botão do passo 0:
  //   - Imediatamente: _stepIndex === 0 (passo 1 usa delegação → diferido via setTimeout)
  //   - Após advanceTimersByTime(0): _stepIndex === 1
  //
  // Validates: Requirements 3.1, 3.2, 3.3, 3.4
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: roteiro misto (seletor + delegação) — transição correta', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 4 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(numPassos);

          // Passo 0: AuraSpotlight encontra #btn-1 (seletor válido → síncrono)
          // Passos 1+: AuraSpotlight retorna null (delegação → setTimeout)
          let chamadas = 0;
          global.AuraState     = makeAuraStateStub();
          global.AuraSpotlight = {
            aplicar:           jest.fn(),
            remover:           jest.fn(),
            encontrarElemento: jest.fn().mockImplementation((seletor) => {
              chamadas++;
              // Primeira chamada (_iniciarPasso(0)): retorna elemento
              // Demais (_usaDelegacao para passo 1, _iniciarPasso(1), etc.): null
              if (chamadas === 1) {
                const el = document.querySelector(seletor);
                return el ? { elemento: el } : null;
              }
              return null;
            })
          };
          global.AuraUI = makeAuraUIStub();
          loadGpsEngine();

          jest.useFakeTimers();

          // Roteiro: passo 0 com #btn-1 (seletor válido), passos 1+ com #btn-1 (delegação)
          const passos = [
            { id: 'p0', intent: 'Passo 0 — seletor', target_selector: '#btn-1', validation_type: 'click', timeout_sec: 30 }
          ];
          for (let i = 1; i < numPassos; i++) {
            passos.push({ id: `p${i}`, intent: `Passo ${i} — delegação`, target_selector: '#btn-1', validation_type: 'click', timeout_sec: 30 });
          }
          const roteiro = { id: 'roteiro-misto', passos };

          global.AuraGpsEngine.init(roteiro);
          if (global.AuraGpsEngine.getCurrentStepIndex() !== 0) return false;

          // Clica em #btn-1 — valida passo 0 via listener direto
          btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // Imediatamente: passo 1 usa delegação → diferido via setTimeout
          const stepImediato = global.AuraGpsEngine.getCurrentStepIndex();
          if (stepImediato !== 0) return false;

          // Após setTimeout(fn, 0): passo 1 iniciado
          jest.advanceTimersByTime(0);
          const stepApos = global.AuraGpsEngine.getCurrentStepIndex();
          return stepApos === 1;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 2d — Seletor válido: clicar no botão ERRADO não avança o passo.
  // Clicar no botão CORRETO avança sincronamente.
  //
  // Validates: Requirements 3.3, 3.4
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: seletor válido — clique no botão correto avança, clique errado não avança', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 4 }),
        (numPassos) => {
          teardownGlobals();
          limparDom(10);
          jest.useRealTimers();
          jest.clearAllMocks();

          const btns = criarBotoes(numPassos);
          setupGlobalsComElemento();
          loadGpsEngine();

          jest.useFakeTimers();

          const roteiro = buildRoteiroSeletores(numPassos);
          global.AuraGpsEngine.init(roteiro);

          // Clica no botão ERRADO (#btn-2 quando passo 0 espera #btn-1)
          btns[1].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
          if (global.AuraGpsEngine.getCurrentStepIndex() !== 0) return false;

          // Clica no botão CORRETO (#btn-1 para passo 0)
          btns[0].dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));

          // Com seletor válido: transição síncrona → _stepIndex === 1 imediatamente
          const stepApos = global.AuraGpsEngine.getCurrentStepIndex();
          return stepApos === 1;
        }
      ),
      { numRuns: 100 }
    );
  });
});

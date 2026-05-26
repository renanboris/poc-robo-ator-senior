// Feature: aura-dap-restructure, Property 4: Validação orientada a tipo — round trip de ação
//
// Property test (Task 5.4) — Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7
//
// Para cada `validation_type` suportado pelo Aura_GPS, simular a ação correspondente
// (click, right_click, double_click, type, enter, url_change, element_present,
// element_absent) deve resultar na emissão do evento `gps:step_validated` no
// `document`. NÃO simular a ação NÃO deve emitir o evento.
//
// Framework: Jest (jsdom) + fast-check (≥ 100 iterações).

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Carregamento do módulo real `aura_gps_engine.js` no contexto jsdom.
// ─────────────────────────────────────────────────────────────────────────────

function loadModule(filename) {
  const code = fs.readFileSync(
    path.join(__dirname, '..', 'modules', filename),
    'utf8'
  );
  // eslint-disable-next-line no-eval
  eval(code);
}

// ─────────────────────────────────────────────────────────────────────────────
// Tipos suportados pelo motor GPS — espelham os ramos de `_registrarValidador`
// em aura_gps_engine.js.
// ─────────────────────────────────────────────────────────────────────────────

const SUPPORTED_TYPES = [
  'click',
  'right_click',
  'double_click',
  'type',
  'enter',
  'url_change',
  'element_present',
  'element_absent',
];

const INTERACTIVE_TYPES = new Set([
  'click', 'right_click', 'double_click', 'type', 'enter'
]);

const TARGET_ID        = 'aura-property4-target';
const TARGET_SELECTOR  = '#aura-property4-target';
const PRESENT_ID       = 'aura-property4-present';
const PRESENT_SELECTOR = '#aura-property4-present';
const TYPED_VALUE      = 'aura-test-value';
const URL_PATTERN      = 'aura-property4-match';
const URL_BASE         = 'https://example.test/';

// ─────────────────────────────────────────────────────────────────────────────
// Helpers de location — necessários para `url_change`.
// O motor lê `global.location.href` em `_validadorUrlChange` e `global.location.origin`
// em `_emitAnalytics`. Override com `configurable: true` permite re-override entre
// iterações.
// ─────────────────────────────────────────────────────────────────────────────

const ORIGINAL_HREF   = window.location.href;
const ORIGINAL_ORIGIN = window.location.origin || 'http://localhost';

function setLocation(href) {
  Object.defineProperty(window, 'location', {
    value: {
      href,
      origin:   'https://example.test',
      toString: () => href,
    },
    writable:     true,
    configurable: true,
  });
}

function resetLocation() {
  Object.defineProperty(window, 'location', {
    value: {
      href:     ORIGINAL_HREF,
      origin:   ORIGINAL_ORIGIN,
      toString: () => ORIGINAL_HREF,
    },
    writable:     true,
    configurable: true,
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Construtores de step e setup por tipo.
// ─────────────────────────────────────────────────────────────────────────────

function buildStep(validation_type) {
  const base = {
    id:              'p1',
    intent:          'Property 4 step',
    target_selector: '',
    validation_type,
    expected_state:  {},
    timeout_sec:     30,
  };

  if (validation_type === 'click' || validation_type === 'right_click' ||
      validation_type === 'double_click' || validation_type === 'enter') {
    return Object.assign(base, { target_selector: TARGET_SELECTOR });
  }

  if (validation_type === 'type') {
    return Object.assign(base, {
      target_selector: TARGET_SELECTOR,
      expected_state:  { value: TYPED_VALUE },
    });
  }

  if (validation_type === 'url_change') {
    return Object.assign(base, { expected_state: { url_pattern: URL_PATTERN } });
  }

  if (validation_type === 'element_present' || validation_type === 'element_absent') {
    return Object.assign(base, { expected_state: { selector: PRESENT_SELECTOR } });
  }

  throw new Error(`Tipo não suportado em buildStep: ${validation_type}`);
}

/**
 * Prepara o DOM/URL ANTES do `init()` conforme o tipo e a decisão de simular.
 *
 * Para tipos interativos (click/type/enter/...), retorna o elemento alvo.
 * Para `url_change` e `element_present`, a "ação" já é refletida no preInit:
 *   - `url_change` shouldSimulate=true  → URL casa com o padrão antes do init.
 *   - `url_change` shouldSimulate=false → URL não casa.
 *   - `element_present` shouldSimulate=true  → elemento já está presente.
 *   - `element_present` shouldSimulate=false → elemento ausente.
 *
 * Para `element_absent`:
 *   - shouldSimulate=true  → elemento ausente, validador agenda 500ms.
 *   - shouldSimulate=false → elemento presente, validador nunca dispara.
 */
function preInit(validation_type, shouldSimulate) {
  switch (validation_type) {
    case 'click':
    case 'right_click':
    case 'double_click': {
      const el = document.createElement('button');
      el.id = TARGET_ID;
      el.textContent = 'alvo';
      document.body.appendChild(el);
      return el;
    }
    case 'type':
    case 'enter': {
      const el = document.createElement('input');
      el.type = 'text';
      el.id   = TARGET_ID;
      document.body.appendChild(el);
      return el;
    }
    case 'url_change': {
      setLocation(shouldSimulate ? (URL_BASE + URL_PATTERN + '/page') : (URL_BASE + 'no-match/page'));
      return null;
    }
    case 'element_present': {
      if (shouldSimulate) {
        const el = document.createElement('div');
        el.id = PRESENT_ID;
        document.body.appendChild(el);
        return el;
      }
      return null;
    }
    case 'element_absent': {
      if (!shouldSimulate) {
        // Mantém o elemento presente — não pode ser validado como "absent".
        const el = document.createElement('div');
        el.id = PRESENT_ID;
        document.body.appendChild(el);
        return el;
      }
      return null;
    }
    default:
      throw new Error(`Tipo não suportado em preInit: ${validation_type}`);
  }
}

/**
 * Simula a ação correspondente ao `validation_type` para tipos interativos.
 * Para `url_change`, `element_present` e `element_absent`, a ação já foi
 * refletida em `preInit` (URL/DOM pré-configurados); aqui é no-op.
 */
function simulateAction(validation_type, el) {
  switch (validation_type) {
    case 'click':
      el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
      return;
    case 'right_click':
      el.dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true }));
      return;
    case 'double_click':
      el.dispatchEvent(new MouseEvent('dblclick', { bubbles: true, cancelable: true }));
      return;
    case 'type':
      el.value = TYPED_VALUE;
      el.dispatchEvent(new Event('input', { bubbles: true }));
      return;
    case 'enter':
      el.focus(); // jsdom: input.focus() atualiza document.activeElement
      document.dispatchEvent(new KeyboardEvent('keydown', {
        key:        'Enter',
        bubbles:    true,
        cancelable: true,
      }));
      return;
    case 'url_change':
    case 'element_present':
    case 'element_absent':
      // Ação já refletida em preInit.
      return;
    default:
      throw new Error(`Tipo não suportado em simulateAction: ${validation_type}`);
  }
}

function cleanupDom() {
  for (const id of [TARGET_ID, PRESENT_ID, 'aura-gps-panel']) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Suite
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraGpsEngine — Property 4: validação orientada a tipo (round trip de ação)', () => {

  let warnSpy;
  let errorSpy;
  let postMessageSpy;

  beforeEach(() => {
    // Mocks de dependências chamadas durante init/_iniciarPasso/_concluir.
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('gps'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session:        { steps_total: 0, tenant_id: 'senior_default', roteiro_id: null },
    };
    global.AuraSpotlight = {
      aplicar:           jest.fn(),
      remover:           jest.fn(),
      // Retorna null para forçar o fallback de delegação no document
      // (em _validadorClick / _validadorEnter), que é o caminho coberto por
      // este teste sem precisar simular contexto de iframe.
      encontrarElemento: jest.fn().mockReturnValue(null),
    };
    global.AuraUI = {
      exibirBalao:             jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:           jest.fn(),
    };

    // Silencia logs esperados (warns de defaults, eventuais errors do engine).
    warnSpy  = jest.spyOn(console, 'warn').mockImplementation(() => {});
    errorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    // postMessage é chamado em _emitAnalytics. jsdom às vezes loga erro de
    // `targetOrigin` mismatch; bypass total mantendo a API estável.
    postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(() => {});

    // Carrega o motor real
    loadModule('aura_gps_engine.js');
  });

  afterEach(() => {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    cleanupDom();
    resetLocation();

    warnSpy.mockRestore();
    errorSpy.mockRestore();
    postMessageSpy.mockRestore();
    jest.clearAllMocks();

    delete global.AuraGpsEngine;
    delete global.AuraState;
    delete global.AuraSpotlight;
    delete global.AuraUI;
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 4 — combinada (positivo + negativo via shouldSimulate booleano).
  //
  // Para cada validation_type ∈ SUPPORTED_TYPES e cada shouldSimulate ∈ {true, false}:
  //   - shouldSimulate=true  ⇒ a ação correspondente é simulada (ou pré-configurada
  //                             no caso de url_change/element_present/element_absent).
  //                             Esperado: gps:step_validated foi emitido pelo menos uma vez.
  //   - shouldSimulate=false ⇒ a ação NÃO é simulada (ou pré-configurada para falhar).
  //                             Esperado: gps:step_validated NÃO foi emitido.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: round trip por validation_type — simular emite, não simular não emite', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...SUPPORTED_TYPES),
        fc.boolean(),
        (validation_type, shouldSimulate) => {
          // Reset duro entre iterações
          if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
            global.AuraGpsEngine.teardown();
          }
          cleanupDom();
          resetLocation();

          // Fake timers — necessário para element_absent (delay de 500ms) e
          // para evitar que o step timeout (30s) dispare durante o teste.
          jest.useFakeTimers();

          const handler = jest.fn();
          document.addEventListener('gps:step_validated', handler);

          let outcome;
          try {
            // Pré-condição (DOM/URL) conforme tipo + decisão de simular.
            const el = preInit(validation_type, shouldSimulate);

            // Inicializa o motor com roteiro de UM passo.
            // Para url_change/element_present, a validação síncrona em init()
            // pode emitir gps:step_validated imediatamente quando shouldSimulate=true.
            global.AuraGpsEngine.init({
              id:     'roteiro_property4',
              passos: [buildStep(validation_type)],
            });

            // Simula a ação para tipos interativos quando shouldSimulate=true.
            if (INTERACTIVE_TYPES.has(validation_type) && shouldSimulate && el) {
              simulateAction(validation_type, el);
            }

            // Avança 600ms — > 500ms do delay do element_absent e
            // << 30000ms do step timeout.
            jest.advanceTimersByTime(600);

            const fired = handler.mock.calls.length > 0;
            outcome = fired === shouldSimulate;
          } finally {
            document.removeEventListener('gps:step_validated', handler);
            jest.useRealTimers();
          }

          return outcome;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Variante explícita — apenas o caso POSITIVO, garantindo que TODOS os tipos
  // suportados emitem o evento ao menos uma vez. Cobre o universo de tipos
  // mesmo quando a propriedade combinada amostra desigualmente.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: para cada validation_type, simular a ação SEMPRE emite gps:step_validated', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...SUPPORTED_TYPES),
        (validation_type) => {
          if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
            global.AuraGpsEngine.teardown();
          }
          cleanupDom();
          resetLocation();

          jest.useFakeTimers();

          const handler = jest.fn();
          document.addEventListener('gps:step_validated', handler);

          let outcome;
          try {
            const el = preInit(validation_type, /* shouldSimulate */ true);
            global.AuraGpsEngine.init({
              id:     'roteiro_property4_pos',
              passos: [buildStep(validation_type)],
            });
            if (INTERACTIVE_TYPES.has(validation_type) && el) {
              simulateAction(validation_type, el);
            }
            jest.advanceTimersByTime(600);
            outcome = handler.mock.calls.length > 0;
          } finally {
            document.removeEventListener('gps:step_validated', handler);
            jest.useRealTimers();
          }

          return outcome;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Variante explícita — apenas o caso NEGATIVO. Sem simular a ação, o evento
  // gps:step_validated NUNCA pode ser emitido para nenhum tipo suportado.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: para cada validation_type, NÃO simular NUNCA emite gps:step_validated', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...SUPPORTED_TYPES),
        (validation_type) => {
          if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
            global.AuraGpsEngine.teardown();
          }
          cleanupDom();
          resetLocation();

          jest.useFakeTimers();

          const handler = jest.fn();
          document.addEventListener('gps:step_validated', handler);

          let outcome;
          try {
            preInit(validation_type, /* shouldSimulate */ false);
            global.AuraGpsEngine.init({
              id:     'roteiro_property4_neg',
              passos: [buildStep(validation_type)],
            });
            // Sem simular ação. Avança o tempo o suficiente para garantir que
            // qualquer delay interno (element_absent: 500ms) tenha oportunidade
            // de disparar caso o validador esteja errado.
            jest.advanceTimersByTime(600);
            outcome = handler.mock.calls.length === 0;
          } finally {
            document.removeEventListener('gps:step_validated', handler);
            jest.useRealTimers();
          }

          return outcome;
        }
      ),
      { numRuns: 100 }
    );
  });
});

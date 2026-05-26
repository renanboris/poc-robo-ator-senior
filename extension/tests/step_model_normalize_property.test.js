// Feature: aura-dap-restructure, Property 3: Step_Model com campos ausentes não falha silenciosamente
//
// Property test (Task 5.2) — Validates: Requirements 3.4
//
// Para qualquer objeto de passo recebido do backend com um ou mais campos
// obrigatórios ausentes, o `aura_gps_engine` deve aplicar o valor padrão
// definido para aquele campo e continuar a execução — nunca lançar exceção
// não tratada nem ignorar o passo.
//
// Framework: Jest (jsdom) + fast-check (mínimo de 100 iterações).

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

// Campos com default segundo Step_Model — espelham STEP_DEFAULTS no módulo.
const REQUIRED_DEFAULT_FIELDS = [
  'validation_type',
  'timeout_sec',
  'xp_value',
  'xp_penalty_per_hint',
  'difficulty',
  'hint'
];

// ─────────────────────────────────────────────────────────────────────────────
// Setup global — mocks mínimos das dependências usadas indiretamente.
// `normalizeStep` é puro, mas o IIFE faz referência a window/console.
// ─────────────────────────────────────────────────────────────────────────────

describe('AuraGpsEngine.normalizeStep — Property 3', () => {

  let warnSpy;

  beforeEach(() => {
    // Dependências do módulo (não usadas por normalizeStep, mas presentes no escopo)
    global.AuraState = {
      getMode:        jest.fn().mockReturnValue('gps'),
      setMode:        jest.fn(),
      registerModule: jest.fn(),
      session:        { steps_total: 0, tenant_id: 'senior_default', roteiro_id: null }
    };
    global.AuraSpotlight = {
      aplicar:           jest.fn(),
      remover:           jest.fn(),
      encontrarElemento: jest.fn().mockReturnValue(null)
    };
    global.AuraUI = {
      exibirBalao:             jest.fn(),
      exibirBaloesSequenciais: jest.fn(),
      esconderBalao:           jest.fn()
    };

    // Silencia console.warn (esperado para cada campo ausente).
    warnSpy = jest.spyOn(console, 'warn').mockImplementation(() => {});

    // Carrega o módulo real.
    loadModule('aura_gps_engine.js');
  });

  afterEach(() => {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
      global.AuraGpsEngine.teardown();
    }
    warnSpy.mockRestore();
    jest.clearAllMocks();
    delete global.AuraGpsEngine;
    delete global.AuraState;
    delete global.AuraSpotlight;
    delete global.AuraUI;
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 3 (versão mínima): passo apenas com `intent` —
  // após normalizeStep, todos os campos com default devem estar definidos.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: passo mínimo (apenas intent) — todos os defaults aplicados', () => {
    fc.assert(
      fc.property(
        // Passo mínimo com apenas o campo `intent` — caso canônico do design.
        fc.record({ intent: fc.string() }),
        (partialStep) => {
          let normalized;
          // 1. Não deve lançar exceção.
          expect(() => {
            normalized = global.AuraGpsEngine.normalizeStep(partialStep);
          }).not.toThrow();

          // 2. Deve retornar um objeto.
          if (normalized === null || typeof normalized !== 'object') return false;

          // 3. Todos os campos com default devem estar definidos (não-undefined, não-null).
          for (const campo of REQUIRED_DEFAULT_FIELDS) {
            if (normalized[campo] === undefined || normalized[campo] === null) {
              return false;
            }
          }

          // 4. O `intent` original deve ser preservado.
          if (normalized.intent !== partialStep.intent) return false;

          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 3 (versão forte): passo com subconjunto arbitrário dos campos
  // opcionais omitidos. O invariante é o mesmo — todos os campos com default
  // devem estar preenchidos após normalizeStep, qualquer combinação de omissão.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: omissão arbitrária de qualquer subconjunto de campos opcionais', () => {
    // Arbitrários para cada campo opcional.
    const validationTypes = [
      'click', 'right_click', 'double_click', 'type', 'enter',
      'url_change', 'element_present', 'element_absent', 'visual_state'
    ];
    const difficulties = ['easy', 'medium', 'hard'];

    fc.assert(
      fc.property(
        // Para cada campo opcional, geramos `option` (presente) ou `undefined` (ausente).
        fc.string(),                                      // intent (sempre presente, requisito mínimo)
        fc.option(fc.constantFrom(...validationTypes),    { nil: undefined }),
        fc.option(fc.integer({ min: 1, max: 600 }),       { nil: undefined }),
        fc.option(fc.integer({ min: 0, max: 1000 }),      { nil: undefined }),
        fc.option(fc.integer({ min: 0, max: 1000 }),      { nil: undefined }),
        fc.option(fc.constantFrom(...difficulties),       { nil: undefined }),
        fc.option(fc.string(),                            { nil: undefined }),
        (intent, validation_type, timeout_sec, xp_value, xp_penalty_per_hint, difficulty, hint) => {
          // Monta o passo, OMITINDO chaves com valor undefined (não apenas atribuindo undefined).
          const partialStep = { intent };
          if (validation_type     !== undefined) partialStep.validation_type     = validation_type;
          if (timeout_sec         !== undefined) partialStep.timeout_sec         = timeout_sec;
          if (xp_value            !== undefined) partialStep.xp_value            = xp_value;
          if (xp_penalty_per_hint !== undefined) partialStep.xp_penalty_per_hint = xp_penalty_per_hint;
          if (difficulty          !== undefined) partialStep.difficulty          = difficulty;
          if (hint                !== undefined) partialStep.hint                = hint;

          let normalized;
          // 1. Nunca lança.
          expect(() => {
            normalized = global.AuraGpsEngine.normalizeStep(partialStep);
          }).not.toThrow();

          if (normalized === null || typeof normalized !== 'object') return false;

          // 2. Todos os campos com default ficam preenchidos.
          for (const campo of REQUIRED_DEFAULT_FIELDS) {
            if (normalized[campo] === undefined || normalized[campo] === null) {
              return false;
            }
          }

          // 3. Quando o campo foi fornecido, o valor original é preservado.
          if (validation_type     !== undefined && normalized.validation_type     !== validation_type)     return false;
          if (timeout_sec         !== undefined && normalized.timeout_sec         !== timeout_sec)         return false;
          if (xp_value            !== undefined && normalized.xp_value            !== xp_value)            return false;
          if (xp_penalty_per_hint !== undefined && normalized.xp_penalty_per_hint !== xp_penalty_per_hint) return false;
          if (difficulty          !== undefined && normalized.difficulty          !== difficulty)          return false;
          if (hint                !== undefined && normalized.hint                !== hint)                return false;

          // 4. `intent` sempre preservado.
          if (normalized.intent !== intent) return false;

          return true;
        }
      ),
      { numRuns: 100 }
    );
  });

  // ───────────────────────────────────────────────────────────────────────────
  // Property 3 (caso extremo): objeto vazio e null-safe — não deve lançar.
  // ───────────────────────────────────────────────────────────────────────────
  test('fc.property: objeto vazio também recebe todos os defaults', () => {
    fc.assert(
      fc.property(
        // Gera um único valor (objeto vazio) — apenas para reaproveitar fc.assert.
        fc.constant({}),
        (emptyStep) => {
          let normalized;
          expect(() => {
            normalized = global.AuraGpsEngine.normalizeStep(emptyStep);
          }).not.toThrow();

          for (const campo of REQUIRED_DEFAULT_FIELDS) {
            if (normalized[campo] === undefined || normalized[campo] === null) {
              return false;
            }
          }
          return true;
        }
      ),
      { numRuns: 100 }
    );
  });
});

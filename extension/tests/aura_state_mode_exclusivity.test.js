// Feature: aura-dap-restructure, Property 1: Exclusividade de modo
//
// Property 1 (design.md):
//   Para qualquer sequência de chamadas a setMode(mode), em nenhum momento
//   dois modos distintos devem estar ativos simultaneamente — aura_mode deve
//   sempre conter exatamente um dos valores válidos: 'assist', 'gps',
//   'train', 'prove'.
//
// Validates: Requirements 1.1, 1.5, 1.6
//
// Estratégia:
//   - Carrega o módulo real extension/modules/aura_state.js no escopo global
//     do jsdom (o IIFE registra window.AuraState).
//   - Stuba os módulos consumidos por setMode (AuraAssistEngine, AuraGpsEngine,
//     AuraMissionEngine) com init/teardown no-op para evitar dependências
//     reais de DOM/rede.
//   - Gera sequências aleatórias de modos com fc.constantFrom e verifica
//     a invariante após CADA chamada a setMode (não só ao final), garantindo
//     que getMode() sempre retorne exatamente um dos quatro valores válidos.

const fs = require('fs');
const path = require('path');
const fc = require('fast-check');

const VALID_MODES = ['assist', 'gps', 'train', 'prove'];

function makeEngineStub() {
    return {
        init: jest.fn(),
        teardown: jest.fn()
    };
}

function loadAuraState() {
    const source = fs.readFileSync(
        path.resolve(__dirname, '..', 'modules', 'aura_state.js'),
        'utf8'
    );
    // Indirect eval para executar no escopo global (jsdom: window === globalThis).
    // O IIFE do módulo registra window.AuraState.
    (0, eval)(source);
}

describe('AuraState — Property 1: Exclusividade de modo', () => {
    beforeAll(() => {
        // Stuba engines ANTES de carregar aura_state.js, embora o registro
        // dependa de chamadas explícitas a registerModule. Os modos 'train'
        // e 'prove' chamam diretamente window.AuraGpsEngine / AuraMissionEngine.
        window.AuraAssistEngine = makeEngineStub();
        window.AuraGpsEngine = makeEngineStub();
        window.AuraMissionEngine = makeEngineStub();

        loadAuraState();

        // Registra stubs para os modos baseados em registry ('assist', 'gps').
        window.AuraState.registerModule('assist', window.AuraAssistEngine);
        window.AuraState.registerModule('gps', window.AuraGpsEngine);

        // Modos compostos exigem roteiro ativo; um stub mínimo basta.
        window.AuraState.setActiveRoteiro(
            { id: 'roteiro_test', passos: [] },
            { error_penalty: 1 }
        );
    });

    afterAll(() => {
        delete window.AuraState;
        delete window.AuraAssistEngine;
        delete window.AuraGpsEngine;
        delete window.AuraMissionEngine;
    });

    test('property: para qualquer sequência de setMode, getMode() retorna exatamente um modo válido', () => {
        fc.assert(
            fc.property(
                fc.array(
                    fc.constantFrom('assist', 'gps', 'train', 'prove'),
                    { minLength: 1, maxLength: 20 }
                ),
                (sequence) => {
                    for (let i = 0; i < sequence.length; i++) {
                        window.AuraState.setMode(sequence[i]);
                        const current = window.AuraState.getMode();

                        // Invariante 1: getMode() retorna um dos quatro valores válidos
                        if (VALID_MODES.indexOf(current) === -1) {
                            return false;
                        }

                        // Invariante 2: exatamente um valor válido (não pode haver
                        // estado intermediário ou múltiplo). Comparamos o modo
                        // contra a lista canônica e exigimos exatamente uma
                        // correspondência.
                        const matches = VALID_MODES.filter(function (m) {
                            return m === current;
                        }).length;
                        if (matches !== 1) {
                            return false;
                        }

                        // Invariante adicional: o modo solicitado deve ter sido
                        // efetivamente aplicado (já que sequence[i] é sempre válido).
                        if (current !== sequence[i]) {
                            return false;
                        }
                    }
                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });

    test('property: getMode() é estável após sequência (idempotência da última transição)', () => {
        fc.assert(
            fc.property(
                fc.array(
                    fc.constantFrom('assist', 'gps', 'train', 'prove'),
                    { minLength: 1, maxLength: 10 }
                ),
                (sequence) => {
                    sequence.forEach(function (m) {
                        window.AuraState.setMode(m);
                    });
                    const last = sequence[sequence.length - 1];
                    return window.AuraState.getMode() === last
                        && VALID_MODES.indexOf(window.AuraState.getMode()) !== -1;
                }
            ),
            { numRuns: 100 }
        );
    });
});

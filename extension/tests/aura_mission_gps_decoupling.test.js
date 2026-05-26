// Feature: aura-dap-restructure, Property 5: Instrumentação GPS pela Mission sem acoplamento
//
// Property 5 (design.md):
//   Para qualquer sessão em aura_mode 'train' ou 'prove', todos os eventos
//   gps:step_validated, gps:step_failed e gps:completed emitidos pelo GPS
//   devem ser recebidos pelo aura_mission_engine — e em aura_mode 'gps'
//   (sem missão), esses mesmos eventos não devem acionar lógica de XP ou HUD.
//
// Validates: Requirements 6.1, 6.2, 4.5
//
// Estratégia:
//   - Carrega o módulo real extension/modules/aura_mission_engine.js no escopo
//     global do jsdom. O IIFE registra window.AuraMissionEngine.
//   - Mocka AuraState (com getMode mutável), AuraUI e AuraSpotlight.
//   - Para cada modo em fc.constantFrom('gps','train','prove'), reinicia o
//     engine via teardown()+init(scoringConfig), dispara sequências de eventos
//     gps:step_validated/step_failed/completed e verifica:
//       * em 'train'/'prove': HUD presente; XP/errorsCount refletem os eventos
//       * em 'gps': HUD ausente; XP=0; errorsCount=0; resumo não exibido
//
// Framework: Jest com jsdom (configurado no package.json)

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

function loadModule(filename) {
    const code = fs.readFileSync(
        path.resolve(__dirname, '..', 'modules', filename),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(code);
}

describe('AuraMissionEngine — Property 5: Instrumentação GPS sem acoplamento', () => {

    // currentMode é mutável para que getMode() reflita a iteração da property.
    let currentMode = 'assist';

    beforeAll(() => {
        // Mocks que o AuraMissionEngine consome ao tocar o HUD/balões.
        global.AuraUI = {
            exibirBalao:             jest.fn(),
            exibirBaloesSequenciais: jest.fn(),
            esconderBalao:           jest.fn(),
        };
        global.AuraSpotlight = {
            aplicar:           jest.fn(),
            remover:           jest.fn(),
            encontrarElemento: jest.fn().mockReturnValue(null),
        };

        // AuraState mock: getMode lê o currentMode mutável definido por iteração.
        global.AuraState = {
            getMode:        jest.fn(() => currentMode),
            setMode:        jest.fn((m) => { currentMode = m; }),
            registerModule: jest.fn(),
            session: {
                steps_total: 3,
                tenant_id:   'senior_default',
                roteiro_id:  'roteiro_p5',
            },
            get mode() { return currentMode; },
        };

        // Carrega o motor real uma única vez. A mesma closure é reutilizada
        // entre iterações via teardown()+init(), evitando listeners orfãos.
        loadModule('aura_mission_engine.js');
    });

    afterAll(() => {
        if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
            global.AuraMissionEngine.teardown();
        }
        // Remove resíduos de DOM, se houver.
        const hud = document.getElementById('aura-mission-hud');
        if (hud) hud.remove();

        delete global.AuraMissionEngine;
        delete global.AuraState;
        delete global.AuraUI;
        delete global.AuraSpotlight;
    });

    // Arbitrário de evento GPS único: kind ∈ {validated, failed} com step_id e xp_value.
    const gpsEventArb = fc.record({
        kind:     fc.constantFrom('validated', 'failed'),
        step_id:  fc.string({ minLength: 1, maxLength: 16 }).filter(s => /^[a-zA-Z0-9_-]+$/.test(s)),
        xp_value: fc.integer({ min: 1, max: 100 }),
    });

    // ── Property principal ───────────────────────────────────────────────────
    // Para qualquer modo e qualquer sequência de eventos GPS, os eventos só
    // afetam XP/HUD/errorsCount em modo 'train'/'prove'. Em 'gps', são ignorados.

    test('fc.property: eventos GPS atualizam XP/HUD em train|prove e são ignorados em gps', () => {
        const SCORING = { base_xp: 0, error_penalty: 5, no_help_bonus: 50 };

        fc.assert(
            fc.property(
                fc.constantFrom('gps', 'train', 'prove'),
                fc.array(gpsEventArb, { minLength: 1, maxLength: 8 }),
                (mode, events) => {
                    // Define o modo da iteração (consultado por getMode() do mock).
                    currentMode = mode;

                    // Reset duro do motor entre iterações: garante _xp/_errorsCount/_hud limpos.
                    global.AuraMissionEngine.teardown();
                    global.AuraUI.exibirBalao.mockClear();

                    // Inicializa: em gps, init() retorna cedo e não cria HUD nem registra listeners.
                    global.AuraMissionEngine.init(SCORING);

                    // Dispara os eventos GPS. Calcula valores esperados quando aplicável.
                    let expectedXp     = SCORING.base_xp;
                    let expectedErrors = 0;
                    const isMission    = (mode === 'train' || mode === 'prove');

                    for (const ev of events) {
                        if (ev.kind === 'validated') {
                            document.dispatchEvent(new CustomEvent('gps:step_validated', {
                                detail: {
                                    step:      { id: ev.step_id, xp_value: ev.xp_value },
                                    stepIndex: 0
                                }
                            }));
                            if (isMission) expectedXp += ev.xp_value;
                        } else {
                            document.dispatchEvent(new CustomEvent('gps:step_failed', {
                                detail: { step: { id: ev.step_id }, stepIndex: 0 }
                            }));
                            if (isMission) {
                                expectedXp     = Math.max(0, expectedXp - SCORING.error_penalty);
                                expectedErrors = expectedErrors + 1;
                            }
                        }
                    }

                    const score = global.AuraMissionEngine.getScore();
                    const hud   = document.getElementById('aura-mission-hud');

                    if (isMission) {
                        // Em train/prove: HUD foi renderizado e os eventos GPS foram processados.
                        if (!hud)                                return false;
                        if (score.xp !== expectedXp)             return false;
                        if (score.errorsCount !== expectedErrors) return false;
                    } else {
                        // Em gps: HUD ausente, sem XP nem contagem de erros (nenhum acoplamento).
                        if (hud)                       return false;
                        if (score.xp !== 0)            return false;
                        if (score.errorsCount !== 0)   return false;
                    }

                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });

    // ── Property auxiliar ───────────────────────────────────────────────────
    // gps:completed deve ser ignorado pela Mission em modo 'gps' (sem resumo,
    // sem remoção de HUD inexistente). Em train/prove, o resumo é exibido.

    test('fc.property: gps:completed dispara resumo apenas em train|prove', () => {
        const SCORING = { base_xp: 0, error_penalty: 5, no_help_bonus: 50 };

        fc.assert(
            fc.property(
                fc.constantFrom('gps', 'train', 'prove'),
                (mode) => {
                    currentMode = mode;

                    global.AuraMissionEngine.teardown();
                    global.AuraUI.exibirBalao.mockClear();
                    global.AuraMissionEngine.init(SCORING);

                    document.dispatchEvent(new CustomEvent('gps:completed', {
                        detail: { roteiro_id: 'roteiro_p5', steps_total: 3 }
                    }));

                    const exibirBalaoCalled = global.AuraUI.exibirBalao.mock.calls.length > 0;
                    const hudExiste         = !!document.getElementById('aura-mission-hud');
                    const isMission         = (mode === 'train' || mode === 'prove');

                    if (isMission) {
                        // Resumo exibido pela Mission e HUD removido em gps:completed.
                        if (!exibirBalaoCalled) return false;
                        if (hudExiste)          return false;
                    } else {
                        // gps: nenhum resumo e nenhum HUD (Mission desligada).
                        if (exibirBalaoCalled) return false;
                        if (hudExiste)         return false;
                    }
                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });
});

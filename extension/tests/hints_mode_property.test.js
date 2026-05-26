// Feature: aura-dap-restructure, Property 6: Hints desabilitados ou limitados em modo prove
//
// Property-based test para Task 7.4 do spec aura-dap-restructure.
//
// Validates: Requirements 6.3, 6.4
//
// Property 6 (texto canônico do design.md):
//   "Para qualquer sessão em aura_mode 'prove', o número de hints concedidos
//    deve ser ≤ 1 por sessão — e em aura_mode 'train', hints devem ser
//    permitidos com custo de XP."
//
// Estratégia:
//   - Gerar fc.integer({min: 0, max: 20}) representando quantidade de pedidos
//     de hint em uma sessão.
//   - Para modo 'prove': iniciar a missão, simular N cliques no botão de hint,
//     verificar que `hints_used ≤ 1`.
//   - Para modo 'train': simular N cliques, verificar que `hints_used == N`
//     e que o XP foi decrementado em N * xp_penalty_per_hint.
//   - Resetar o estado entre iterações (teardown + cleanup do DOM).
//
// Framework: Jest com jsdom (configurado no package.json) + fast-check.

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Helper: carrega um módulo IIFE no contexto do jsdom (window disponível)
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
// Helper: prepara o ambiente para uma única iteração da property
// ─────────────────────────────────────────────────────────────────────────────
function setupAmbiente(mode) {
    // Mocks dos módulos dependidos pelo AuraMissionEngine
    global.AuraUI = {
        exibirBalao:             jest.fn(),
        exibirBaloesSequenciais: jest.fn(),
        esconderBalao:           jest.fn(),
    };

    global.AuraSpotlight = {
        aplicar:          jest.fn(),
        remover:          jest.fn(),
        encontrarElemento: jest.fn().mockReturnValue(null),
    };

    // AuraState com getMode retornando o modo desejado
    global.AuraState = {
        getMode:        jest.fn().mockReturnValue(mode),
        setMode:        jest.fn(),
        registerModule: jest.fn(),
        session: {
            steps_total: 3,
            tenant_id:   'senior_default',
            roteiro_id:  'roteiro_property_test',
        },
    };

    // Carrega o AuraMissionEngine real (IIFE que registra em window.AuraMissionEngine)
    loadModule('aura_mission_engine.js');
}

function tearDownAmbiente() {
    if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
        global.AuraMissionEngine.teardown();
    }
    delete global.AuraMissionEngine;
    delete global.AuraState;
    delete global.AuraUI;
    delete global.AuraSpotlight;

    // Limpa qualquer resíduo do DOM (HUD pode ter ficado em casos de exceção)
    const hud = document.getElementById('aura-mission-hud');
    if (hud) hud.remove();
}

// ─────────────────────────────────────────────────────────────────────────────
// Property 6 — Hints em modo prove e train
// ─────────────────────────────────────────────────────────────────────────────

describe('Property 6 — Hints desabilitados ou limitados em modo prove', () => {

    afterEach(() => {
        tearDownAmbiente();
        jest.clearAllMocks();
    });

    // ── Property 6.a: modo prove → hints_used ≤ 1 ─────────────────────────────
    // Validates: Requirement 6.4
    test('fc.property: para qualquer N pedidos de hint em modo prove, hints_used ≤ 1', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 0, max: 20 }),
                (numPedidos) => {
                    // Reset entre iterações
                    tearDownAmbiente();
                    setupAmbiente('prove');

                    const scoringProve = {
                        base_xp:       100,
                        error_penalty: 15,
                        no_help_bonus: 50,
                    };

                    global.AuraMissionEngine.init(scoringProve);

                    // Simula passo atual via evento gps:step_started
                    // (sem isso, _solicitarHint retorna antes de incrementar contador)
                    const passo = {
                        id:                  'p1',
                        intent:              'Clique no menu',
                        target_selector:     '#btn',
                        xp_value:            10,
                        xp_penalty_per_hint: 5,
                    };
                    document.dispatchEvent(new CustomEvent('gps:step_started', {
                        detail: { step: passo, stepIndex: 0 }
                    }));

                    // Simula N cliques no botão "Preciso de Ajuda"
                    const btnAjuda = document.getElementById('aura-hud-btn-ajuda');
                    if (!btnAjuda) return false; // HUD deveria existir em modo prove

                    for (let i = 0; i < numPedidos; i++) {
                        btnAjuda.click();
                    }

                    const score = global.AuraMissionEngine.getScore();
                    return score.hintsUsed <= 1;
                }
            ),
            { numRuns: 100 }
        );
    });

    // ── Property 6.b: modo train → hints_used == numPedidos com custo de XP ──
    // Validates: Requirement 6.3
    test('fc.property: em modo train, N pedidos de hint resultam em hints_used == N e XP decrementado', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 0, max: 20 }),
                (numPedidos) => {
                    // Reset entre iterações
                    tearDownAmbiente();
                    setupAmbiente('train');

                    const baseXp           = 1000;
                    const xpPenaltyPerHint = 5;
                    const scoringTrain = {
                        base_xp:       baseXp,
                        error_penalty: 15,
                        no_help_bonus: 50,
                    };

                    global.AuraMissionEngine.init(scoringTrain);

                    const passo = {
                        id:                  'p1',
                        intent:              'Clique no menu',
                        target_selector:     '#btn',
                        xp_value:            10,
                        xp_penalty_per_hint: xpPenaltyPerHint,
                    };
                    document.dispatchEvent(new CustomEvent('gps:step_started', {
                        detail: { step: passo, stepIndex: 0 }
                    }));

                    const btnAjuda = document.getElementById('aura-hud-btn-ajuda');
                    if (!btnAjuda) return false;

                    for (let i = 0; i < numPedidos; i++) {
                        btnAjuda.click();
                    }

                    const score = global.AuraMissionEngine.getScore();

                    // hints_used deve ser exatamente N (sem limite em train)
                    if (score.hintsUsed !== numPedidos) return false;

                    // XP deve ter sido decrementado em N * xp_penalty_per_hint,
                    // com piso em 0 (Math.max(0, _xp - custo))
                    const xpEsperado = Math.max(0, baseXp - numPedidos * xpPenaltyPerHint);
                    return score.xp === xpEsperado;
                }
            ),
            { numRuns: 100 }
        );
    });

});

// Feature: aura-dap-restructure, Property 7: Analytics events contêm campos obrigatórios
//
// Property 7 (design.md):
//   Para qualquer evento de analytics emitido pelo sistema, o payload deve
//   conter todos os campos obrigatórios definidos para aquele `event_type` —
//   nenhum campo obrigatório deve estar ausente ou nulo.
//
// Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
//
// Estratégia:
//   - Carrega os módulos reais `aura_gps_engine.js` e `aura_mission_engine.js`
//     no escopo global do jsdom (cada IIFE registra seu objeto em window).
//   - Stuba `AuraState`, `AuraSpotlight` e `AuraUI` para isolar o teste das
//     dependências externas dos engines.
//   - Para cada `event_type` (selecionado via fc.constantFrom), dirige os
//     engines pelo cenário mínimo que dispara aquele evento e captura todas
//     as chamadas a `window.postMessage` com `type: 'AURA_ANALYTICS_EVENT'`.
//   - Verifica que ao menos um envelope é emitido para o `event_type`
//     escolhido e que TODOS os envelopes desse tipo possuem TODOS os campos
//     obrigatórios definidos pela Requirements 9.1–9.6, com valores não-nulos
//     e não-undefined (zero é considerado um valor válido, ex: step_index=0,
//     duration_sec=0).
//
// Notas:
//   - Cada iteração da property reinicia os engines, limpa o DOM e reseta o
//     spy, garantindo isolamento entre runs.
//   - `numRuns: 100` (mínimo exigido pelo design).

'use strict';

const fs = require('fs');
const path = require('path');
const fc = require('fast-check');

// ─── MAPA event_type → campos obrigatórios ──────────────────────────────────
const REQUIRED_FIELDS_BY_EVENT = {
    gps_start:         ['roteiro_id', 'timestamp', 'mode'],
    step_complete:     ['step_id', 'step_index', 'validation_type', 'duration_sec'],
    step_error:        ['step_id', 'step_index', 'validation_type'],
    session_abandoned: ['step_index_at_abandon', 'steps_total'],
    hint_requested:    ['step_id', 'step_index', 'hints_total_session'],
    mission_complete:  ['roteiro_id', 'mode', 'score_final', 'xp_final', 'hints_used', 'errors_count', 'duration_sec']
};

const EVENT_TYPES = Object.keys(REQUIRED_FIELDS_BY_EVENT);

// ─── HELPERS ────────────────────────────────────────────────────────────────

function loadModule(filename) {
    const code = fs.readFileSync(
        path.join(__dirname, '..', 'modules', filename),
        'utf8'
    );
    // IIFE registra window.<Module>; eval indireto coloca o código no escopo global
    // do jsdom (window === globalThis).
    // eslint-disable-next-line no-eval
    (0, eval)(code);
}

function setupStubs(mode, roteiroId, stepsTotal) {
    global.AuraState = {
        getMode: () => mode,
        setMode: jest.fn(),
        registerModule: jest.fn(),
        session: {
            mode: mode,
            roteiro_id: roteiroId || null,
            steps_total: stepsTotal || 0,
            tenant_id: 'test_tenant',
            xp: 0,
            hints_used: 0,
            errors_count: 0,
            session_start: null,
            mode_start: null,
            step_index: 0
        }
    };
    global.AuraSpotlight = {
        aplicar: jest.fn(),
        remover: jest.fn(),
        encontrarElemento: jest.fn().mockReturnValue(null)
    };
    global.AuraUI = {
        exibirBalao: jest.fn(),
        exibirBaloesSequenciais: jest.fn(),
        esconderBalao: jest.fn()
    };
}

function teardownAll() {
    if (global.AuraGpsEngine && typeof global.AuraGpsEngine.teardown === 'function') {
        try { global.AuraGpsEngine.teardown(); } catch (_) { /* noop */ }
    }
    if (global.AuraMissionEngine && typeof global.AuraMissionEngine.teardown === 'function') {
        try { global.AuraMissionEngine.teardown(); } catch (_) { /* noop */ }
    }
    delete global.AuraGpsEngine;
    delete global.AuraMissionEngine;
    delete global.AuraState;
    delete global.AuraSpotlight;
    delete global.AuraUI;
}

function makeRoteiro(timeoutSec) {
    return {
        id: 'roteiro_property7',
        passos: [{
            id: 'step_1',
            intent: 'Clique no botão alvo',
            target_selector: '#aura-property7-target',
            validation_type: 'click',
            timeout_sec: timeoutSec || 60,
            xp_value: 10,
            xp_penalty_per_hint: 5
        }]
    };
}

function captureEnvelopesFor(spy, eventType) {
    return spy.mock.calls
        .map(call => call[0])
        .filter(msg =>
            msg
            && msg.type === 'AURA_ANALYTICS_EVENT'
            && msg.payload
            && msg.payload.event_type === eventType
        )
        .map(msg => msg.payload);
}

// Dirige os engines para emitir o `eventType` escolhido. Retorna `true` quando
// pelo menos uma chamada a postMessage para esse event_type foi capturada e
// todos os campos obrigatórios estão presentes (não-undefined e não-null).
function exerciseAndCheck(eventType, spy) {
    const roteiro = makeRoteiro(1);

    if (eventType === 'gps_start') {
        setupStubs('gps', roteiro.id, roteiro.passos.length);
        loadModule('aura_gps_engine.js');
        window.AuraGpsEngine.init(roteiro);
    }

    else if (eventType === 'step_complete') {
        setupStubs('gps', roteiro.id, roteiro.passos.length);
        document.body.innerHTML = '<button id="aura-property7-target">alvo</button>';
        loadModule('aura_gps_engine.js');
        window.AuraGpsEngine.init(roteiro);
        // Validador click usa fallback no document quando AuraSpotlight retorna null.
        const target = document.getElementById('aura-property7-target');
        target.click();
    }

    else if (eventType === 'step_error') {
        setupStubs('gps', roteiro.id, roteiro.passos.length);
        loadModule('aura_gps_engine.js');
        window.AuraGpsEngine.init(roteiro);
        // Avança além do timeout_sec=1 para disparar _timeoutPasso.
        jest.advanceTimersByTime(1500);
    }

    else if (eventType === 'session_abandoned') {
        setupStubs('gps', roteiro.id, roteiro.passos.length);
        loadModule('aura_gps_engine.js');
        window.AuraGpsEngine.init(roteiro);
        const btn = document.getElementById('aura-gps-btn-abandonar');
        if (btn) btn.click();
    }

    else if (eventType === 'hint_requested') {
        setupStubs('train', roteiro.id, roteiro.passos.length);
        loadModule('aura_gps_engine.js');
        loadModule('aura_mission_engine.js');
        window.AuraMissionEngine.init({ base_xp: 100, error_penalty: 15 });
        // Dispara gps:step_started para registrar _currentStep no Mission engine.
        document.dispatchEvent(new CustomEvent('gps:step_started', {
            detail: { step: roteiro.passos[0], stepIndex: 0 }
        }));
        const btn = document.getElementById('aura-hud-btn-ajuda');
        if (btn) btn.click();
    }

    else if (eventType === 'mission_complete') {
        setupStubs('train', roteiro.id, roteiro.passos.length);
        loadModule('aura_mission_engine.js');
        window.AuraMissionEngine.init({ base_xp: 100, error_penalty: 15, no_help_bonus: 50 });
        // Dispara gps:completed para acionar _onCompleted.
        document.dispatchEvent(new CustomEvent('gps:completed', {
            detail: { roteiro_id: roteiro.id, steps_total: roteiro.passos.length }
        }));
    }

    // ── Verificação ─────────────────────────────────────────────────────────
    const envelopes = captureEnvelopesFor(spy, eventType);
    if (envelopes.length === 0) {
        // Nenhum evento capturado — falha da propriedade
        return false;
    }

    const required = REQUIRED_FIELDS_BY_EVENT[eventType];
    // TODOS os envelopes do tipo escolhido devem possuir TODOS os campos
    // obrigatórios com valor não-undefined e não-null.
    return envelopes.every(envelope => {
        const payload = envelope.payload || {};
        return required.every(field => {
            const value = payload[field];
            return value !== undefined && value !== null;
        });
    });
}

// ─── PROPERTY TEST ───────────────────────────────────────────────────────────

describe('AuraAnalytics — Property 7: campos obrigatórios em analytics events', () => {
    let postMessageSpy;

    beforeEach(() => {
        jest.useFakeTimers();
        // Não deixar postMessage real disparar MessageEvents que poderiam
        // acionar handlers reais de bridge/content scripts (ainda que
        // ausentes neste teste).
        postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(() => {});
        document.body.innerHTML = '';
    });

    afterEach(() => {
        teardownAll();
        document.body.innerHTML = '';
        postMessageSpy.mockRestore();
        jest.useRealTimers();
        jest.clearAllMocks();
    });

    test('property: para qualquer event_type, o payload contém todos os campos obrigatórios', () => {
        fc.assert(
            fc.property(
                fc.constantFrom(...EVENT_TYPES),
                (eventType) => {
                    // Reset entre iterações: encerra engines, limpa DOM e
                    // o histórico do spy. Isso garante que cada execução é
                    // independente e que envelopes capturados pertencem
                    // exclusivamente à iteração corrente.
                    teardownAll();
                    document.body.innerHTML = '';
                    postMessageSpy.mockClear();

                    return exerciseAndCheck(eventType, postMessageSpy);
                }
            ),
            { numRuns: 100 }
        );
    });
});

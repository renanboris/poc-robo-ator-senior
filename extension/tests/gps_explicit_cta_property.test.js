// Feature: aura-dap-restructure, Property 2: GPS não inicia automaticamente a partir de resposta IA
// Validates: Requirements 2.2, 2.4
//
// Property 2 verifica que, para qualquer payload `AURA_RESPONSE` contendo `gps_passos`,
// o `AuraAssistEngine` NÃO transiciona automaticamente para o modo `gps` e NÃO invoca
// `AuraGpsEngine.init` — apenas oferece um CTA explícito ao usuário, mantendo
// `AuraState.getMode() === 'assist'` até confirmação explícita do usuário.
//
// Framework: Jest (jsdom environment) + fast-check (numRuns: 100).

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

/**
 * Carrega e executa um módulo IIFE no contexto do jsdom (window disponível).
 * Os módulos usam (function(global){ ... })(window) — eval no contexto global
 * do jsdom faz window ser o global correto.
 */
function loadModule(filename) {
    const code = fs.readFileSync(
        path.join(__dirname, '..', 'modules', filename),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(code);
}

describe('Aura DAP Restructure — Property 2: GPS não inicia automaticamente a partir de resposta IA', () => {

    let gpsInitMock;
    let setModeSpy;

    beforeEach(() => {
        // ── Mocks de dependências externas ao AuraAssistEngine ────────────────

        // AuraUI: balões, badge, animação. Métodos chamados pelo handler ficam
        // como jest.fn() — não validamos UI aqui, apenas o estado de modo.
        global.AuraUI = {
            exibirBalao:           jest.fn(),
            exibirBaloesSequenciais: jest.fn(),
            esconderBalao:         jest.fn(),
            ativarBadge:           jest.fn(),
            desativarBadge:        jest.fn(),
            tocarAnimacao:         jest.fn(),
            setLastPrompt:         jest.fn(),
            removerTypingIndicator: jest.fn(),
            exibirTypingIndicator:  jest.fn(),
            adicionarMensagemUsuario: jest.fn(),
            getHistorico:          jest.fn().mockReturnValue([]),
        };

        global.AuraDomMapper = {
            capturar: jest.fn().mockReturnValue(''),
        };

        global.AuraSpotlight = {
            aplicar:           jest.fn(),
            remover:           jest.fn(),
            encontrarElemento: jest.fn().mockReturnValue(null),
        };

        // Stub explícito de AuraGpsEngine: o teste verifica que init() NÃO é
        // chamado pelo response handler do AuraAssistEngine sem ação explícita
        // do usuário.
        gpsInitMock = jest.fn();
        global.AuraGpsEngine = {
            init:     gpsInitMock,
            teardown: jest.fn(),
        };

        // Mission engine não é exercido pelo handler de AURA_RESPONSE no modo
        // assist, mas é declarado por segurança.
        global.AuraMissionEngine = {
            init:     jest.fn(),
            teardown: jest.fn(),
        };

        // ── Carrega os módulos canônicos reais ───────────────────────────────
        // AuraState primeiro (registra interface em window.AuraState),
        // depois AuraAssistEngine (registra-se no registry do AuraState).
        loadModule('aura_state.js');
        loadModule('aura_assist_engine.js');

        // Spy na função real AuraState.setMode para confirmar que o handler
        // não dispara transição de modo de forma automática.
        setModeSpy = jest.spyOn(global.AuraState, 'setMode');

        // Inicializa o AuraAssistEngine: registra o listener de 'message' e
        // o idle timer. Necessário para que o handler de AURA_RESPONSE seja
        // exercido pelo dispatchEvent.
        global.AuraAssistEngine.init();
    });

    afterEach(() => {
        if (global.AuraAssistEngine && typeof global.AuraAssistEngine.teardown === 'function') {
            global.AuraAssistEngine.teardown();
        }
        if (setModeSpy && typeof setModeSpy.mockRestore === 'function') {
            setModeSpy.mockRestore();
        }
        delete global.AuraState;
        delete global.AuraAssistEngine;
        delete global.AuraGpsEngine;
        delete global.AuraMissionEngine;
        delete global.AuraUI;
        delete global.AuraDomMapper;
        delete global.AuraSpotlight;
        jest.clearAllMocks();
    });

    // ── Property test ────────────────────────────────────────────────────────
    //
    // Para qualquer payload AURA_RESPONSE com `gps_passos` arbitrário:
    //   1. AuraState.getMode() permanece 'assist'.
    //   2. AuraState.setMode NÃO é chamado com 'gps' (nem com qualquer outro modo).
    //   3. AuraGpsEngine.init NÃO é invocado pelo handler.
    //
    // Isso reflete o requisito de que o GPS só inicia após confirmação explícita
    // do usuário (clique no CTA exibido pelo AuraUI.exibirBalao).
    //
    // Validates: Requirements 2.2, 2.4

    test('fc.property: payloads com gps_passos não disparam transição automática para gps', () => {
        // Sanity check: o modo inicial é 'assist'.
        expect(global.AuraState.getMode()).toBe('assist');

        fc.assert(
            fc.property(
                fc.record({
                    mensagem: fc.string(),
                    gps_passos: fc.array(
                        fc.record({
                            id:     fc.string(),
                            intent: fc.string(),
                        }),
                        { minLength: 1, maxLength: 5 }
                    ),
                }),
                (payload) => {
                    // Reset do estado de mocks para esta iteração — o estado de
                    // AuraState e do listener registrado é preservado entre
                    // iterações, pois não há transição de modo legítima.
                    gpsInitMock.mockClear();
                    setModeSpy.mockClear();

                    // Constrói um MessageEvent sintético com a origin correta
                    // para que a checagem `event.origin !== window.location.origin`
                    // do _handleMessage seja satisfeita e o handler execute.
                    const evt = new MessageEvent('message', {
                        data:   { type: 'AURA_RESPONSE', payload: payload },
                        origin: window.location.origin,
                    });

                    window.dispatchEvent(evt);

                    // Invariante 1: o modo permanece 'assist' após processar a resposta.
                    if (global.AuraState.getMode() !== 'assist') {
                        return false;
                    }

                    // Invariante 2: setMode não foi chamado com 'gps' (ou qualquer
                    // outro modo) como efeito do recebimento da resposta.
                    const transicionouModo = setModeSpy.mock.calls.some(
                        (call) => call[0] !== undefined && call[0] !== 'assist'
                    );
                    if (transicionouModo) {
                        return false;
                    }

                    // Invariante 3: AuraGpsEngine.init não foi invocado
                    // automaticamente pelo handler — só o CTA explícito pode
                    // invocá-lo.
                    if (gpsInitMock.mock.calls.length !== 0) {
                        return false;
                    }

                    return true;
                }
            ),
            { numRuns: 100 }
        );

        // Após 100 iterações, o modo final ainda deve ser 'assist'.
        expect(global.AuraState.getMode()).toBe('assist');
    });
});

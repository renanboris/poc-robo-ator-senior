// Feature: aura-dap-restructure, Property 8: Validação de origem de mensagens
// Validates: Requirements 10.3, 10.4, 10.5
//
// Property 8 (design.md):
//   Para qualquer mensagem recebida via window.addEventListener("message"),
//   mensagens cuja event.origin difere de window.location.origin devem ser
//   ignoradas — e mensagens sem o campo `type` esperado devem ser descartadas
//   silenciosamente.
//
// Estratégia:
//   - Carrega os módulos canônicos reais que registram listeners de
//     `message` no `window`: aura_state.js e aura_assist_engine.js.
//     O AuraAssistEngine é o consumidor primário de AURA_RESPONSE e contém
//     a lógica defensiva exigida pelos requisitos 10.3/10.4/10.5
//     (`event.origin !== window.location.origin` → return; sem `type` → return).
//   - Stuba todas as dependências (AuraUI, AuraSpotlight, AuraGpsEngine,
//     AuraDomMapper, AuraMissionEngine) com jest.fn para detectar qualquer
//     efeito colateral que indicaria que a mensagem foi processada.
//   - Spia window.postMessage para detectar emissão de analytics
//     (assist_response_received), que é o efeito colateral mais sensível
//     ao processamento bem-sucedido de AURA_RESPONSE.
//
//   Estratégia 1 — origem inválida:
//     Gera origin arbitrária via fc.string() (filtrada para garantir que é
//     diferente de window.location.origin) e despacha um MessageEvent
//     contendo um payload AURA_RESPONSE bem-formado. A invariante exige
//     que NENHUM stub de dependência seja chamado e NENHUM postMessage
//     seja emitido — i.e., a mensagem é silenciosamente ignorada.
//
//   Estratégia 2 — mensagens sem campo `type` com origin válida:
//     Despacha MessageEvents cuja `data` não contém `type` (ou é null/string/
//     número/objeto sem a chave). A invariante exige descarte silencioso —
//     nenhum efeito colateral, nenhuma exceção lançada.
//
// Framework: Jest (jsdom environment) + fast-check (numRuns: 100).

'use strict';

const fs   = require('fs');
const path = require('path');
const fc   = require('fast-check');

/**
 * Carrega e executa um módulo IIFE no contexto do jsdom.
 * Os módulos canônicos usam (function(global){ ... })(window) — o eval no
 * escopo global do jsdom faz com que `window` seja o globalThis correto.
 */
function loadModule(filename) {
    const code = fs.readFileSync(
        path.join(__dirname, '..', 'modules', filename),
        'utf8'
    );
    // eslint-disable-next-line no-eval
    eval(code);
}

describe('Aura DAP Restructure — Property 8: Validação de origem de mensagens', () => {

    let auraUiStub;
    let auraSpotlightStub;
    let auraGpsStub;
    let postMessageSpy;
    let consoleErrorSpy;

    beforeEach(() => {
        // ── Stubs de dependências do AuraAssistEngine ─────────────────────────
        // Qualquer chamada a estes stubs durante o dispatch indica que a
        // mensagem foi processada — i.e., a validação falhou.

        auraUiStub = {
            exibirBalao:              jest.fn(),
            exibirBaloesSequenciais:  jest.fn(),
            esconderBalao:            jest.fn(),
            ativarBadge:              jest.fn(),
            desativarBadge:           jest.fn(),
            tocarAnimacao:            jest.fn(),
            setLastPrompt:            jest.fn(),
            removerTypingIndicator:   jest.fn(),
            exibirTypingIndicator:    jest.fn(),
            adicionarMensagemUsuario: jest.fn(),
            getHistorico:             jest.fn().mockReturnValue([]),
        };
        global.AuraUI = auraUiStub;

        global.AuraDomMapper = {
            capturar: jest.fn().mockReturnValue(''),
        };

        auraSpotlightStub = {
            aplicar:           jest.fn(),
            remover:           jest.fn(),
            encontrarElemento: jest.fn().mockReturnValue(null),
        };
        global.AuraSpotlight = auraSpotlightStub;

        auraGpsStub = {
            init:     jest.fn(),
            teardown: jest.fn(),
        };
        global.AuraGpsEngine = auraGpsStub;

        global.AuraMissionEngine = {
            init:     jest.fn(),
            teardown: jest.fn(),
        };

        // ── Carrega os módulos canônicos reais ────────────────────────────────
        loadModule('aura_state.js');
        loadModule('aura_assist_engine.js');

        // ── Spia postMessage para detectar emissão de analytics ───────────────
        // Em jsdom, window.postMessage despacha um MessageEvent assíncrono que
        // poderia re-acionar o handler. O spy serve para confirmar que NENHUM
        // postMessage foi emitido como efeito do recebimento de uma mensagem
        // inválida — o handler deve retornar imediatamente.
        postMessageSpy = jest.spyOn(window, 'postMessage').mockImplementation(() => {});

        // Spia console.error para garantir que mensagens descartadas não
        // produzem stack traces (descarte deve ser silencioso).
        consoleErrorSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

        // Inicializa o AuraAssistEngine: registra _handleMessage como listener
        // de 'message' no window. Sem isso a propriedade não pode ser exercida.
        global.AuraAssistEngine.init();
    });

    afterEach(() => {
        if (global.AuraAssistEngine && typeof global.AuraAssistEngine.teardown === 'function') {
            global.AuraAssistEngine.teardown();
        }
        postMessageSpy.mockRestore();
        consoleErrorSpy.mockRestore();
        delete global.AuraState;
        delete global.AuraAssistEngine;
        delete global.AuraGpsEngine;
        delete global.AuraMissionEngine;
        delete global.AuraUI;
        delete global.AuraDomMapper;
        delete global.AuraSpotlight;
        jest.clearAllMocks();
    });

    /**
     * Helper: verifica que NENHUM efeito colateral observável ocorreu.
     * Retorna true se a mensagem foi efetivamente ignorada.
     */
    function nenhumEfeitoColateral() {
        // UI: nada renderizado nem balão exibido
        if (auraUiStub.exibirBalao.mock.calls.length             !== 0) return false;
        if (auraUiStub.exibirBaloesSequenciais.mock.calls.length !== 0) return false;
        if (auraUiStub.removerTypingIndicator.mock.calls.length  !== 0) return false;

        // Spotlight: não aplicado nem removido por causa da mensagem
        if (auraSpotlightStub.aplicar.mock.calls.length !== 0) return false;
        if (auraSpotlightStub.remover.mock.calls.length !== 0) return false;

        // GPS: não inicializado
        if (auraGpsStub.init.mock.calls.length !== 0) return false;

        // Analytics: nenhum postMessage emitido em resposta à mensagem inválida
        if (postMessageSpy.mock.calls.length !== 0) return false;

        return true;
    }

    function limparMocks() {
        auraUiStub.exibirBalao.mockClear();
        auraUiStub.exibirBaloesSequenciais.mockClear();
        auraUiStub.removerTypingIndicator.mockClear();
        auraSpotlightStub.aplicar.mockClear();
        auraSpotlightStub.remover.mockClear();
        auraGpsStub.init.mockClear();
        postMessageSpy.mockClear();
    }

    // ── Estratégia 1 — Origem diferente de window.location.origin ────────────
    //
    // Para qualquer origin arbitrária ≠ window.location.origin, com payload
    // AURA_RESPONSE bem-formado, o handler DEVE ignorar a mensagem.
    //
    // Validates: Requirements 10.3, 10.4

    test('property: mensagens com origin ≠ window.location.origin são ignoradas', () => {
        // Sanity check: o handler está registrado e processa AURA_RESPONSE
        // quando a origin é correta. Se este sanity falhar, o teste de
        // propriedade abaixo seria trivialmente verdadeiro (false positive).
        const validEvt = new MessageEvent('message', {
            data:   { type: 'AURA_RESPONSE', payload: { mensagem: 'oi' } },
            origin: window.location.origin,
        });
        window.dispatchEvent(validEvt);
        expect(auraUiStub.exibirBalao).toHaveBeenCalled();
        limparMocks();

        const myOrigin = window.location.origin;

        fc.assert(
            fc.property(
                // Origin arbitrária — string qualquer, filtrada para excluir
                // a origem real do jsdom (jsdom default: http://localhost).
                fc.string().filter((s) => s !== myOrigin),
                // Payload AURA_RESPONSE bem-formado (com type e gps_passos
                // opcionais). Se a validação de origem falhar, o handler
                // tentaria processar isto e dispararia efeitos colaterais.
                fc.record({
                    type:    fc.constant('AURA_RESPONSE'),
                    payload: fc.record({
                        mensagem:     fc.string(),
                        seletor_css:  fc.option(fc.string(), { nil: undefined }),
                        elemento_id:  fc.option(fc.integer(), { nil: undefined }),
                        gps_passos:   fc.option(
                            fc.array(fc.record({ id: fc.string(), intent: fc.string() })),
                            { nil: undefined }
                        ),
                    }),
                }),
                (origemAtacante, data) => {
                    limparMocks();

                    let lancouExcecao = false;
                    try {
                        const evt = new MessageEvent('message', {
                            data:   data,
                            origin: origemAtacante,
                        });
                        window.dispatchEvent(evt);
                    } catch (_) {
                        lancouExcecao = true;
                    }

                    // Invariante 1: nenhum efeito colateral observável.
                    if (!nenhumEfeitoColateral()) return false;
                    // Invariante 2: descarte silencioso — sem exceção propagada.
                    if (lancouExcecao) return false;
                    // Invariante 3: o modo permanece 'assist' (não houve
                    // transição que pudesse ser causada por processamento).
                    if (global.AuraState.getMode() !== 'assist') return false;

                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });

    // ── Estratégia 2 — Mensagens sem campo `type` com origin válida ──────────
    //
    // Para mensagens com origem correta mas sem o campo `type` esperado, o
    // handler DEVE descartar a mensagem silenciosamente — sem exceção e sem
    // efeitos colaterais.
    //
    // Validates: Requirement 10.5

    test('property: mensagens sem campo `type` (origem válida) são descartadas silenciosamente', () => {
        const myOrigin = window.location.origin;

        // Geradores de payload SEM o campo `type`:
        //   - null
        //   - string arbitrária
        //   - número arbitrário
        //   - boolean
        //   - record arbitrário cujas chaves não incluem 'type'
        //   - array
        const payloadSemType = fc.oneof(
            fc.constant(null),
            fc.constant(undefined),
            fc.string(),
            fc.integer(),
            fc.boolean(),
            fc.array(fc.anything()),
            // Object cujos campos NÃO incluem 'type'. Construímos a partir de
            // chaves arbitrárias e removemos qualquer 'type' que aparecer.
            fc.dictionary(fc.string(), fc.anything()).map((obj) => {
                const clone = Object.assign({}, obj);
                delete clone.type;
                return clone;
            })
        );

        fc.assert(
            fc.property(
                payloadSemType,
                (data) => {
                    limparMocks();

                    let lancouExcecao = false;
                    try {
                        const evt = new MessageEvent('message', {
                            data:   data,
                            origin: myOrigin,
                        });
                        window.dispatchEvent(evt);
                    } catch (_) {
                        lancouExcecao = true;
                    }

                    // Invariante 1: nenhum efeito colateral observável —
                    // nem balão exibido, nem GPS iniciado, nem analytics.
                    if (!nenhumEfeitoColateral()) return false;
                    // Invariante 2: descarte silencioso (sem exceção).
                    if (lancouExcecao) return false;
                    // Invariante 3: console.error não foi acionado pelo
                    // listener (descarte verdadeiramente silencioso).
                    if (consoleErrorSpy.mock.calls.length !== 0) return false;

                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });
});

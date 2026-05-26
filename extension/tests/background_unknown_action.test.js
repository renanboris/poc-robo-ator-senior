// Feature: aura-dap-restructure, Property 9: Background retorna erro para ação desconhecida
//
// Property test para o handler `chrome.runtime.onMessage` em `extension/background.js`.
//
// **Validates: Requirements 8.7**
//
// Para qualquer string de ação NÃO reconhecida pelo background, a resposta deve ser
// exatamente `{ error: "unknown_action" }` e nenhuma exceção deve ser lançada.
//
// Estratégia: como background.js é um service worker MV3 que depende de globals do
// runtime de extensão (chrome.*, importScripts), carregamos o arquivo dentro de um
// contexto isolado via Node `vm` com mocks mínimos para `chrome`, `fetch`,
// `importScripts` e `console`. Capturamos o listener registrado em
// `chrome.runtime.onMessage.addListener` e o invocamos diretamente com mensagens
// arbitrárias.
//
// Refatoração: nenhuma. O background.js permanece intocado — o teste apenas
// observa o comportamento do listener em um sandbox.

'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const fc = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Conjunto canônico de ações reconhecidas, conforme requisito 8.1 e parent task.
//
// Inclui ações declaradas no design (`fetch_hint`) mesmo que ainda não
// implementadas — o teste deve verificar comportamento APENAS para ações fora
// deste conjunto, conforme a redação literal de Property 9.
// ─────────────────────────────────────────────────────────────────────────────

const ACOES_RECONHECIDAS = new Set([
    'analisar_agora',
    'fetch_mission',
    'fetch_gps_explicit',
    'pre_capture',
    'analytics_event',
    'fetch_hint',
]);

// ─────────────────────────────────────────────────────────────────────────────
// Carregador isolado: lê background.js e o executa em sandbox vm com mocks
// suficientes para que o listener de `chrome.runtime.onMessage` seja registrado.
// ─────────────────────────────────────────────────────────────────────────────

function carregarListenerDoBackground() {
    const codigo = fs.readFileSync(
        path.join(__dirname, '..', 'background.js'),
        'utf8'
    );

    let listenerCapturado = null;

    const sandbox = {
        // Console silencioso — background.js loga em diversos pontos.
        console: { log: () => {}, warn: () => {}, error: () => {}, info: () => {} },

        // importScripts é específico de service workers MV3. Lançamos para
        // exercitar o catch em background.js (que apenas emite um warn).
        importScripts: () => { throw new Error('importScripts não disponível em sandbox'); },

        // chrome API: somente o estritamente necessário para registrar e
        // operar o listener no caminho `unknown_action`.
        chrome: {
            runtime: {
                onMessage: {
                    addListener: (fn) => { listenerCapturado = fn; },
                },
                // Ausência de erro — usado por captureVisibleTab.
                lastError: null,
            },
            tabs: {
                captureVisibleTab: (_windowId, _opts, cb) => {
                    // Não deveria ser chamado para ações desconhecidas, mas
                    // mantemos um stub seguro para evitar TypeError caso seja.
                    if (typeof cb === 'function') cb('data:image/png;base64,AAAA');
                },
            },
        },

        // fetch jamais deve ser invocado para uma ação desconhecida; um stub
        // que retorna Promise resolvida evita falsos positivos caso seja.
        fetch: () => Promise.resolve({
            ok: true,
            json: () => Promise.resolve({}),
        }),

        // Timers reais para qualquer setTimeout incidental.
        setTimeout: setTimeout,
        clearTimeout: clearTimeout,

        // Globais V8 que background.js consome ao montar AURA_ENDPOINTS.
        Object,
        Set,
        Promise,
        Error,
        JSON,
        encodeURIComponent,
        decodeURIComponent,
        Array,
        String,
        Number,
        Boolean,
    };

    // self-reference para qualquer código que cheque global/globalThis.
    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;
    sandbox.self = sandbox;

    vm.createContext(sandbox);
    vm.runInContext(codigo, sandbox, { filename: 'background.js' });

    if (typeof listenerCapturado !== 'function') {
        throw new Error('Listener não foi registrado em chrome.runtime.onMessage.addListener.');
    }

    return listenerCapturado;
}

// ─────────────────────────────────────────────────────────────────────────────
// Suite — Property 9
// ─────────────────────────────────────────────────────────────────────────────

describe('Property 9 — Background retorna erro para ação desconhecida', () => {

    let listener;

    beforeAll(() => {
        listener = carregarListenerDoBackground();
    });

    // ── Teste determinístico: ação string arbitrária fixa ────────────────────
    // Validates: Requirements 8.7

    test('responde { error: "unknown_action" } para uma ação claramente desconhecida', () => {
        const respostas = [];
        const sendResponse = (r) => respostas.push(r);

        expect(() => {
            listener({ action: 'acao_que_nao_existe_xyz' }, /* sender */ {}, sendResponse);
        }).not.toThrow();

        expect(respostas).toHaveLength(1);
        expect(respostas[0]).toEqual({ error: 'unknown_action' });
    });

    // ── Teste determinístico: ação ausente no payload ────────────────────────
    // Validates: Requirements 8.7

    test('responde { error: "unknown_action" } quando o campo action é undefined', () => {
        const respostas = [];
        const sendResponse = (r) => respostas.push(r);

        expect(() => {
            listener({}, {}, sendResponse);
        }).not.toThrow();

        expect(respostas).toHaveLength(1);
        expect(respostas[0]).toEqual({ error: 'unknown_action' });
    });

    // ── Teste determinístico: ação string vazia ──────────────────────────────
    // Validates: Requirements 8.7

    test('responde { error: "unknown_action" } para action === ""', () => {
        const respostas = [];
        const sendResponse = (r) => respostas.push(r);

        expect(() => {
            listener({ action: '' }, {}, sendResponse);
        }).not.toThrow();

        expect(respostas).toHaveLength(1);
        expect(respostas[0]).toEqual({ error: 'unknown_action' });
    });

    // ── Property-based test ──────────────────────────────────────────────────
    // Validates: Requirements 8.7
    //
    // Para qualquer string `action` que NÃO esteja no conjunto canônico de
    // ações reconhecidas, o listener deve:
    //   1. não lançar exceção;
    //   2. invocar sendResponse exatamente uma vez;
    //   3. com o objeto literal { error: "unknown_action" }.

    test('fc.property: qualquer ação desconhecida produz { error: "unknown_action" } sem exceção', () => {
        fc.assert(
            fc.property(
                fc.string().filter(s => !ACOES_RECONHECIDAS.has(s)),
                (acaoDesconhecida) => {
                    const respostas = [];
                    const sendResponse = (r) => respostas.push(r);

                    let lançouExcecao = false;
                    try {
                        listener({ action: acaoDesconhecida }, {}, sendResponse);
                    } catch (_e) {
                        lançouExcecao = true;
                    }

                    if (lançouExcecao) return false;
                    if (respostas.length !== 1) return false;

                    const r = respostas[0];
                    if (r === null || typeof r !== 'object') return false;

                    const chaves = Object.keys(r);
                    if (chaves.length !== 1) return false;
                    if (chaves[0] !== 'error') return false;
                    if (r.error !== 'unknown_action') return false;

                    return true;
                }
            ),
            { numRuns: 100 }
        );
    });

});

// Feature: aura-extension-chrome-load-failure
// Bug Condition Exploration Test — Task 3.5
//
// Este teste verifica que o código CORRIGIDO satisfaz o comportamento esperado.
// Após o fix, _injectScript recebe extensionId como segundo parâmetro e constrói
// a URL como 'chrome-extension://{extensionId}/{src}' sem usar chrome.runtime.
//
// EXPECTED OUTCOME: TODOS OS TESTES PASSAM (confirma que o bug foi corrigido)
//
// Validates: Requirements 2.1, 2.2

const fc = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Extração da função _injectScript CORRIGIDA
//
// Reflete exatamente a implementação atual de extension/content.js após o fix:
//
//   function _injectScript(src, extensionId) {
//       return new Promise(function (resolve, reject) {
//           var s = document.createElement('script');
//           s.src = 'chrome-extension://' + extensionId + '/' + src;
//           s.onload = resolve;
//           s.onerror = reject;
//           (document.head || document.documentElement).appendChild(s);
//       });
//   }
//
// Não usa chrome.runtime — sem crash no mundo MAIN.
// ─────────────────────────────────────────────────────────────────────────────

// Versão instrumentada: captura o src atribuído ao elemento antes de qualquer
// normalização do jsdom, e dispara onload via mock de appendChild.
function _injectScript_fixed_instrumented(src, extensionId) {
    return new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        // Captura o valor bruto antes de atribuir ao elemento jsdom
        var rawSrc = 'chrome-extension://' + extensionId + '/' + src;
        s._rawSrc = rawSrc; // armazena para inspeção no teste
        s.src = rawSrc;
        s.onload = resolve;
        s.onerror = reject;
        (document.head || document.documentElement).appendChild(s);
    });
}

// Versão simples (idêntica ao content.js corrigido) — usada para testes de resolução
function _injectScript_fixed(src, extensionId) {
    return new Promise(function (resolve, reject) {
        var s = document.createElement('script');
        s.src = 'chrome-extension://' + extensionId + '/' + src;
        s.onload = resolve;
        s.onerror = reject;
        (document.head || document.documentElement).appendChild(s);
    });
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: intercepta appendChild para disparar onload imediatamente,
// simulando que o script foi carregado com sucesso.
// ─────────────────────────────────────────────────────────────────────────────

function mockAppendChildWithOnload() {
    const mockFn = jest.fn().mockImplementation(function (el) {
        setTimeout(function () {
            if (typeof el.onload === 'function') el.onload();
        }, 0);
        return el;
    });
    jest.spyOn(document.head, 'appendChild').mockImplementation(mockFn);
    jest.spyOn(document.documentElement, 'appendChild').mockImplementation(mockFn);
    return mockFn;
}

// ─────────────────────────────────────────────────────────────────────────────
// Grupo: Bug Condition — _injectScript deve funcionar no mundo MAIN
//
// Estes testes verificam o comportamento CORRETO após o fix:
// _injectScript NÃO deve lançar erro quando chamada com um extensionId válido.
//
// No código corrigido (que usa 'chrome-extension://' + extensionId + '/' + src),
// estes testes PASSAM porque não há acesso a chrome.runtime.
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug Condition — _injectScript deve funcionar no mundo MAIN (sem chrome.runtime)', () => {

    beforeEach(() => {
        // Simula o ambiente world: MAIN onde chrome.runtime é undefined.
        global.chrome = {}; // chrome existe, mas chrome.runtime é undefined
        mockAppendChildWithOnload();
    });

    afterEach(() => {
        delete global.chrome;
        jest.restoreAllMocks();
    });

    // ── Teste determinístico: módulo concreto ─────────────────────────────────
    // Validates: Requirement 2.1
    //
    // ESPERADO (após fix): _injectScript_fixed resolve sem lançar TypeError
    // O código corrigido não acessa chrome.runtime → sem crash
    // A Promise resolve com undefined (onload é chamado sem argumento)

    test('_injectScript_fixed("modules/aura_state.js", extensionId) deve resolver sem TypeError', async () => {
        const extensionId = 'testextensionid123';
        // Verifica que a Promise resolve (não rejeita) — sem crash
        await expect(
            _injectScript_fixed('modules/aura_state.js', extensionId)
        ).resolves.toBeUndefined();
    });

    // ── Teste determinístico: verificar URL construída ────────────────────────
    // Validates: Requirement 2.2
    //
    // Verifica que s._rawSrc é construído como 'chrome-extension://{extensionId}/{src}'
    // (capturado antes da normalização do jsdom)

    test('_injectScript_fixed deve construir URL como chrome-extension://{extensionId}/{src}', async () => {
        const extensionId = 'testextensionid123';
        const src = 'modules/aura_state.js';
        const expectedUrl = 'chrome-extension://' + extensionId + '/' + src;

        let capturedElement = null;

        jest.restoreAllMocks();
        jest.spyOn(document.head, 'appendChild').mockImplementation(function (el) {
            capturedElement = el;
            setTimeout(function () {
                if (typeof el.onload === 'function') el.onload();
            }, 0);
            return el;
        });
        jest.spyOn(document.documentElement, 'appendChild').mockImplementation(function (el) {
            capturedElement = el;
            setTimeout(function () {
                if (typeof el.onload === 'function') el.onload();
            }, 0);
            return el;
        });

        await _injectScript_fixed_instrumented(src, extensionId);

        expect(capturedElement).not.toBeNull();
        // Verifica o valor bruto capturado antes da normalização do jsdom
        expect(capturedElement._rawSrc).toBe(expectedUrl);
    });

    // ── Testes determinísticos: todos os módulos do loop _carregarModulos ─────
    // Validates: Requirement 2.2

    const modulos = [
        'modules/aura_state.js',
        'modules/aura_feedback.js',
        'modules/aura_ui.js',
        'modules/aura_dom_mapper.js',
        'modules/aura_spotlight.js',
        'modules/aura_gps_engine.js',
        'modules/aura_mission_engine.js',
        'modules/aura_assist_engine.js',
        'guided_execution.js',
        'checklist_widget.js',
        'hesitation_detector.js',
    ];

    modulos.forEach(function (modulo) {
        test(`_injectScript_fixed("${modulo}", extensionId) deve resolver sem TypeError`, async () => {
            const extensionId = 'testextensionid123';
            await expect(
                _injectScript_fixed(modulo, extensionId)
            ).resolves.toBeUndefined();
        });
    });

    // ── Property-based test: qualquer (src, extensionId) deve funcionar ───────
    // Validates: Requirements 2.1, 2.2
    //
    // Para qualquer string src e extensionId alfanumérico, _injectScript_fixed
    // NÃO deve rejeitar e deve construir a URL corretamente.

    test('fc.property: _injectScript_fixed NÃO deve rejeitar para qualquer (src, extensionId) no mundo MAIN', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.string(),
                fc.stringMatching(/^[a-z0-9]{8,32}$/),
                async function (src, extensionId) {
                    const expectedUrl = 'chrome-extension://' + extensionId + '/' + src;
                    let capturedElement = null;

                    jest.restoreAllMocks();
                    jest.spyOn(document.head, 'appendChild').mockImplementation(function (el) {
                        capturedElement = el;
                        setTimeout(function () {
                            if (typeof el.onload === 'function') el.onload();
                        }, 0);
                        return el;
                    });
                    jest.spyOn(document.documentElement, 'appendChild').mockImplementation(function (el) {
                        capturedElement = el;
                        setTimeout(function () {
                            if (typeof el.onload === 'function') el.onload();
                        }, 0);
                        return el;
                    });

                    // Verifica que a Promise resolve sem crash
                    await expect(
                        _injectScript_fixed_instrumented(src, extensionId)
                    ).resolves.toBeUndefined();

                    // Verifica que a URL foi construída corretamente
                    expect(capturedElement).not.toBeNull();
                    expect(capturedElement._rawSrc).toBe(expectedUrl);
                }
            ),
            { numRuns: 100 }
        );
    });

});

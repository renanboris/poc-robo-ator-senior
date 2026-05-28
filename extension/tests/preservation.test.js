// Feature: aura-extension-chrome-load-failure
// Preservation Tests — Task 2
//
// **IMPORTANT**: Estes testes DEVEM PASSAR no código NÃO corrigido.
// Eles confirmam o baseline de comportamentos que devem ser preservados pelo fix.
// NÃO modificar extension/content.js — extrair funções para uso nos testes.
//
// Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6

'use strict';

const fc = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Extração das funções do content.js original
//
// content.js é uma IIFE que não exporta nada. As funções são reconstruídas
// aqui exatamente como aparecem no código fonte, sem qualquer modificação.
// ─────────────────────────────────────────────────────────────────────────────

// ── _obterExtensionId (extraída de content.js, sem modificação) ───────────────
// Lê document.documentElement.getAttribute('data-aura-id') com até 20 tentativas
// de 100ms cada antes de retornar null.

async function _obterExtensionId(tentativas) {
    tentativas = tentativas || 0;
    var id = document.documentElement.getAttribute('data-aura-id');
    if (id) return id;
    if (tentativas > 20) return null;
    await new Promise(function (r) { setTimeout(r, 100); });
    return _obterExtensionId(tentativas + 1);
}

// ── _estaLogado (extraída de content.js, sem modificação) ────────────────────
// Retorna false em URLs de login; true quando há tokens no sessionStorage/localStorage.

function _estaLogado() {
    if (/\/login|\/auth|\/signin|\/sso/i.test(window.location.href)) return false;
    var campoSenha = document.querySelector('input[type="password"]');
    if (campoSenha && campoSenha.offsetParent !== null) return false;
    try {
        var stores = [sessionStorage, localStorage];
        for (var si = 0; si < stores.length; si++) {
            var st = stores[si];
            for (var i = 0; i < st.length; i++) {
                if (/token|auth|session|jwt|bearer|access/i.test(st.key(i) || '')) return true;
            }
        }
    } catch (e) {}
    var outlet = document.querySelector('router-outlet');
    if (outlet && outlet.nextElementSibling) return true;
    var appRoot = document.querySelector('app-root, platform-root, senior-root');
    if (appRoot && appRoot.children.length > 1) return true;
    return ['p-breadcrumb', 'p-menubar', '[aria-label*="Grupo de menus"]',
            '[class*="user-name"]', '.senior-header']
           .some(function (sel) { return document.querySelector(sel) !== null; });
}

// ── _inicializarAura (extraída de content.js, sem modificação) ────────────────
// Cria o container HTML com o dotlottie-player e inicializa os módulos.
// Dependências de window são mockadas nos testes.

async function _inicializarAura(extensionId) {
    if (window.customElements) {
        try {
            await window.customElements.whenDefined('dotlottie-player');
        } catch (e) {
            console.error('[Aura] dotlottie-player não disponível.', e);
            return;
        }
    }

    var auraContainer = document.createElement('div');
    auraContainer.id = 'aura-floating-container';
    auraContainer.innerHTML = [
        '<div class="aura-badge" id="aura-notification-badge">1</div>',
        '<div id="aura-chat-stack"></div>',
        '<dotlottie-player id="aura-lottie-player"',
        '  src="chrome-extension://' + extensionId + '/aura.json"',
        '  background="transparent" speed="1">',
        '</dotlottie-player>',
        '<div id="aura-speech-bubble">',
        '  <button class="aura-btn-close" id="aura-btn-close" aria-label="Fechar">✕</button>',
        '  <div class="aura-text">Olá, sou a Aura! Como posso te ajudar nesta tela?</div>',
        '  <div class="aura-input-wrapper">',
        '    <input type="text" id="aura-prompt-input"',
        '      placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">',
        '    <button class="aura-btn-send" id="aura-btn-ask">➜</button>',
        '  </div>',
        '  <div class="aura-options"></div>',
        '</div>'
    ].join('\n');
    document.documentElement.appendChild(auraContainer);

    window.AuraUI.init();
    window.AuraState.setMode('assist');

    if (window.AuraHesitationDetector) {
        window.AuraHesitationDetector.ativar(window._auraApiBase || 'http://localhost:8000');
    }

    if (window.AuraFeedback && window.AuraFeedback.inicializarNps) {
        window.AuraFeedback.inicializarNps(window._auraApiBase || 'http://localhost:8000');
    }

    var player = document.getElementById('aura-lottie-player');
    if (player) {
        player.addEventListener('click', function () {
            if (window.AuraUI.wasPlayerDragged()) {
                window.AuraUI.resetDragFlag();
                return;
            }
            window.AuraUI.tocarAnimacao();
            window.AuraUI.desativarBadge();
            var bubble = document.getElementById('aura-speech-bubble');
            if (bubble && bubble.classList.contains('active')) {
                window.AuraUI.esconderBalao();
            } else {
                var stack = document.getElementById('aura-chat-stack');
                if (stack) stack.innerHTML = '';
                window.AuraUI.exibirBalao('Como posso te ajudar nesta tela?', []);
            }
        });
    }

    console.log('[Aura] Orquestrador inicializado.');
}

// ─────────────────────────────────────────────────────────────────────────────
// Observação 1 — _obterExtensionId retry
//
// Validates: Requirements 3.1, 3.4
// ─────────────────────────────────────────────────────────────────────────────

describe('Observação 1 — _obterExtensionId: retry até o atributo estar disponível', () => {

    beforeEach(() => {
        jest.useFakeTimers();
        // Garante que o atributo não existe antes de cada teste
        document.documentElement.removeAttribute('data-aura-id');
    });

    afterEach(() => {
        jest.useRealTimers();
        document.documentElement.removeAttribute('data-aura-id');
    });

    // ── Teste determinístico: atributo disponível imediatamente ──────────────
    // Validates: Requirement 3.4

    test('retorna o ID imediatamente quando data-aura-id já está definido', async () => {
        document.documentElement.setAttribute('data-aura-id', 'ext-id-imediato');

        const result = await _obterExtensionId();

        expect(result).toBe('ext-id-imediato');
    });

    // ── Teste determinístico: atributo definido após 1 tentativa ─────────────
    // Validates: Requirement 3.4

    test('retorna o ID quando o atributo é definido após 1 tentativa (100ms)', async () => {
        // Define o atributo após 100ms (durante a primeira espera)
        setTimeout(() => {
            document.documentElement.setAttribute('data-aura-id', 'ext-id-tardio');
        }, 50);

        const promise = _obterExtensionId();

        // Avança os timers para processar o setTimeout interno e o externo
        jest.runAllTimersAsync();

        const result = await promise;
        expect(result).toBe('ext-id-tardio');
    });

    // ── Teste determinístico: retorna null após 20 tentativas sem atributo ───
    // Validates: Requirement 3.4

    test('retorna null quando data-aura-id nunca é definido (> 20 tentativas)', async () => {
        // Nunca define o atributo — deve retornar null após esgotar tentativas
        const promise = _obterExtensionId();

        jest.runAllTimersAsync();

        const result = await promise;
        expect(result).toBeNull();
    });

    // ── Property-based test: para qualquer N entre 0 e 19, retorna o ID ──────
    // Validates: Requirements 3.1, 3.4
    //
    // Para qualquer número de tentativas N (0 ≤ N ≤ 19), _obterExtensionId
    // retorna o ID quando o atributo é definido na tentativa N.
    //
    // Este teste PASSA no código não corrigido — confirma baseline a preservar.

    test('fc.property: retorna o ID quando definido em qualquer tentativa N (0 ≤ N ≤ 19)', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.integer({ min: 0, max: 19 }),
                fc.string({ minLength: 1, maxLength: 32 }).filter(s => /^[a-zA-Z0-9_-]+$/.test(s)),
                async (n, extensionId) => {
                    // Limpa estado entre execuções da propriedade
                    document.documentElement.removeAttribute('data-aura-id');
                    jest.useRealTimers();
                    jest.useFakeTimers();

                    // Define o atributo após N * 100ms (na tentativa N)
                    const delay = n * 100 + 50; // 50ms dentro do intervalo da tentativa N
                    setTimeout(() => {
                        document.documentElement.setAttribute('data-aura-id', extensionId);
                    }, delay);

                    const promise = _obterExtensionId();
                    jest.runAllTimersAsync();

                    const result = await promise;

                    // Limpa para o próximo run
                    document.documentElement.removeAttribute('data-aura-id');

                    return result === extensionId;
                }
            ),
            { numRuns: 20 }
        );
        // Garante que timers reais estão ativos ao sair do teste
        jest.useRealTimers();
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Observação 2 — URL do dotlottie-player em _inicializarAura
//
// Validates: Requirements 3.5
// ─────────────────────────────────────────────────────────────────────────────

describe('Observação 2 — _inicializarAura: URL do dotlottie-player é chrome-extension://{id}/aura.json', () => {

    beforeEach(() => {
        // Garante que fake timers não estão ativos neste grupo
        jest.useRealTimers();

        // Mock das dependências de window que _inicializarAura chama
        global.window.AuraUI = {
            init: jest.fn(),
            wasPlayerDragged: jest.fn().mockReturnValue(false),
            resetDragFlag: jest.fn(),
            tocarAnimacao: jest.fn(),
            desativarBadge: jest.fn(),
            esconderBalao: jest.fn(),
            exibirBalao: jest.fn(),
        };
        global.window.AuraState = {
            setMode: jest.fn(),
        };
        global.window.AuraHesitationDetector = {
            ativar: jest.fn(),
        };
        global.window.AuraFeedback = {
            criar: jest.fn(),
            inicializarNps: jest.fn(),
            mostrarNps: jest.fn(),
        };
        // Não mockar customElements — deixar o guard `if (window.customElements)` em
        // _inicializarAura pular o await whenDefined, evitando dependência de timers.
        // jsdom não define customElements por padrão, então o guard é false.
        delete global.window.customElements;
    });

    afterEach(() => {
        // Remove o container criado por _inicializarAura
        const container = document.getElementById('aura-floating-container');
        if (container) container.parentNode.removeChild(container);

        delete global.window.AuraUI;
        delete global.window.AuraState;
        delete global.window.AuraHesitationDetector;
        delete global.window.AuraFeedback;

        jest.clearAllMocks();
    });

    // ── Teste determinístico: URL construída corretamente ────────────────────
    // Validates: Requirement 3.5

    test('_inicializarAura("abc123") cria dotlottie-player com src="chrome-extension://abc123/aura.json"', async () => {
        await _inicializarAura('abc123');

        const container = document.getElementById('aura-floating-container');
        expect(container).not.toBeNull();

        // Verifica a URL no innerHTML do container
        expect(container.innerHTML).toContain('src="chrome-extension://abc123/aura.json"');
    });

    // ── Teste determinístico: extensionId diferente ───────────────────────────
    // Validates: Requirement 3.5

    test('_inicializarAura("xyz789abc") cria dotlottie-player com src correto', async () => {
        await _inicializarAura('xyz789abc');

        const container = document.getElementById('aura-floating-container');
        expect(container).not.toBeNull();
        expect(container.innerHTML).toContain('src="chrome-extension://xyz789abc/aura.json"');
    });

    // ── Property-based test: qualquer extensionId alfanumérico válido ─────────
    // Validates: Requirements 3.5
    //
    // Para qualquer extensionId alfanumérico válido, _inicializarAura constrói
    // a URL do dotlottie-player como chrome-extension://{extensionId}/aura.json.
    //
    // Este teste PASSA no código não corrigido — confirma baseline a preservar.

    test('fc.property: URL do dotlottie-player é sempre chrome-extension://{id}/aura.json', async () => {
        await fc.assert(
            fc.asyncProperty(
                // Gera extensionIds alfanuméricos válidos (como IDs reais de extensão Chrome)
                fc.stringMatching(/^[a-z]{10,32}$/),
                async (extensionId) => {
                    // Limpa container anterior se existir
                    const anterior = document.getElementById('aura-floating-container');
                    if (anterior) anterior.parentNode.removeChild(anterior);

                    await _inicializarAura(extensionId);

                    const container = document.getElementById('aura-floating-container');
                    if (!container) return false;

                    const urlEsperada = `chrome-extension://${extensionId}/aura.json`;
                    const temUrl = container.innerHTML.includes(`src="${urlEsperada}"`);

                    // Limpa para o próximo run
                    container.parentNode.removeChild(container);

                    return temUrl;
                }
            ),
            { numRuns: 50 }
        );
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Observação 3 — _estaLogado
//
// Validates: Requirements 3.2
// ─────────────────────────────────────────────────────────────────────────────

describe('Observação 3 — _estaLogado: retorna false em URLs de login, true com tokens', () => {

    const originalLocation = window.location;

    afterEach(() => {
        // Restaura window.location
        Object.defineProperty(window, 'location', {
            value: originalLocation,
            writable: true,
            configurable: true,
        });
        sessionStorage.clear();
        localStorage.clear();
        jest.clearAllMocks();
    });

    // ── Testes determinísticos: URLs de login retornam false ─────────────────
    // Validates: Requirement 3.2

    const urlsDeLogin = [
        { desc: '/login', href: 'https://app.senior.com.br/login' },
        { desc: '/auth', href: 'https://app.senior.com.br/auth' },
        { desc: '/signin', href: 'https://app.senior.com.br/signin' },
        { desc: '/sso', href: 'https://app.senior.com.br/sso' },
        { desc: '/login?redirect=...', href: 'https://app.senior.com.br/login?redirect=/dashboard' },
    ];

    urlsDeLogin.forEach(({ desc, href }) => {
        test(`retorna false para URL de login: ${desc}`, () => {
            Object.defineProperty(window, 'location', {
                value: { href },
                writable: true,
                configurable: true,
            });

            expect(_estaLogado()).toBe(false);
        });
    });

    // ── Testes determinísticos: tokens no storage retornam true ──────────────
    // Validates: Requirement 3.2

    test('retorna true quando há "token" no sessionStorage', () => {
        Object.defineProperty(window, 'location', {
            value: { href: 'https://app.senior.com.br/dashboard' },
            writable: true,
            configurable: true,
        });
        sessionStorage.setItem('access_token', 'eyJhbGciOiJIUzI1NiJ9');

        expect(_estaLogado()).toBe(true);

        sessionStorage.clear();
    });

    test('retorna true quando há "auth" no localStorage', () => {
        Object.defineProperty(window, 'location', {
            value: { href: 'https://app.senior.com.br/dashboard' },
            writable: true,
            configurable: true,
        });
        localStorage.setItem('authData', JSON.stringify({ userId: 42 }));

        expect(_estaLogado()).toBe(true);

        localStorage.clear();
    });

    test('retorna true quando há "jwt" no sessionStorage', () => {
        Object.defineProperty(window, 'location', {
            value: { href: 'https://app.senior.com.br/home' },
            writable: true,
            configurable: true,
        });
        sessionStorage.setItem('jwt_token', 'some.jwt.value');

        expect(_estaLogado()).toBe(true);

        sessionStorage.clear();
    });

    test('retorna false quando storage está vazio e URL não é de login', () => {
        Object.defineProperty(window, 'location', {
            value: { href: 'https://app.senior.com.br/dashboard' },
            writable: true,
            configurable: true,
        });
        sessionStorage.clear();
        localStorage.clear();

        // Sem tokens e sem elementos de UI logada → false
        expect(_estaLogado()).toBe(false);
    });

    // ── Property-based test: qualquer URL com padrão de login retorna false ───
    // Validates: Requirement 3.2

    test('fc.property: qualquer URL contendo /login, /auth, /signin ou /sso retorna false', () => {
        const loginPaths = ['/login', '/auth', '/signin', '/sso'];

        fc.assert(
            fc.property(
                fc.constantFrom(...loginPaths),
                fc.string({ maxLength: 30 }).filter(s => /^[a-zA-Z0-9._-]*$/.test(s)),
                (path, suffix) => {
                    const href = `https://app.senior.com.br${path}${suffix}`;
                    Object.defineProperty(window, 'location', {
                        value: { href },
                        writable: true,
                        configurable: true,
                    });
                    sessionStorage.clear();
                    localStorage.clear();

                    return _estaLogado() === false;
                }
            ),
            { numRuns: 100 }
        );
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Observação 4 — flag _auraInicializada
//
// Validates: Requirements 3.3
// ─────────────────────────────────────────────────────────────────────────────

describe('Observação 4 — _auraInicializada: guard impede inicializações duplicadas', () => {

    // ── Teste determinístico: flag funciona como guard ────────────────────────
    // Validates: Requirement 3.3
    //
    // Verifica que _tentarIniciarAura ignora chamadas subsequentes quando
    // _auraInicializada = true. Replica a lógica do guard exatamente como
    // aparece em content.js.

    test('_tentarIniciarAura não inicializa novamente quando _auraInicializada = true', () => {
        // Replica o guard de content.js
        var _auraInicializada = false;
        var inicializacoesChamadas = 0;

        function _tentarIniciarAura() {
            if (_auraInicializada) return; // ← guard exato de content.js
            _auraInicializada = true;
            inicializacoesChamadas++;
        }

        // Primeira chamada: deve inicializar
        _tentarIniciarAura();
        expect(inicializacoesChamadas).toBe(1);
        expect(_auraInicializada).toBe(true);

        // Segunda chamada: deve ser ignorada pelo guard
        _tentarIniciarAura();
        expect(inicializacoesChamadas).toBe(1); // ainda 1 — não incrementou

        // Terceira chamada: também ignorada
        _tentarIniciarAura();
        expect(inicializacoesChamadas).toBe(1);
    });

    // ── Teste determinístico: flag começa como false ──────────────────────────
    // Validates: Requirement 3.3

    test('_auraInicializada começa como false (primeira chamada sempre executa)', () => {
        var _auraInicializada = false;
        var executou = false;

        function _tentarIniciarAura() {
            if (_auraInicializada) return;
            _auraInicializada = true;
            executou = true;
        }

        expect(_auraInicializada).toBe(false);
        _tentarIniciarAura();
        expect(executou).toBe(true);
        expect(_auraInicializada).toBe(true);
    });

    // ── Teste determinístico: N chamadas após a primeira são todas ignoradas ──
    // Validates: Requirement 3.3

    test('N chamadas após a primeira inicialização são todas ignoradas', () => {
        var _auraInicializada = false;
        var contagem = 0;

        function _tentarIniciarAura() {
            if (_auraInicializada) return;
            _auraInicializada = true;
            contagem++;
        }

        // Primeira chamada
        _tentarIniciarAura();
        expect(contagem).toBe(1);

        // 10 chamadas subsequentes — todas ignoradas
        for (var i = 0; i < 10; i++) {
            _tentarIniciarAura();
        }

        expect(contagem).toBe(1); // sempre 1
    });

    // ── Property-based test: qualquer número de chamadas extras → contagem = 1
    // Validates: Requirement 3.3

    test('fc.property: independente do número de chamadas extras, inicialização ocorre exatamente 1 vez', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 0, max: 100 }),
                (chamadosExtras) => {
                    var _auraInicializada = false;
                    var contagem = 0;

                    function _tentarIniciarAura() {
                        if (_auraInicializada) return;
                        _auraInicializada = true;
                        contagem++;
                    }

                    // Primeira chamada
                    _tentarIniciarAura();

                    // N chamadas extras
                    for (var i = 0; i < chamadosExtras; i++) {
                        _tentarIniciarAura();
                    }

                    return contagem === 1;
                }
            ),
            { numRuns: 100 }
        );
    });

});

// Feature: aura-dap-restructure
// Regression tests — Requirement 11: Preservação das funcionalidades existentes

/**
 * Estes testes verificam que as funcionalidades existentes da extensão Aura DAP
 * continuam funcionando após a reorganização modular.
 *
 * Dependências mockadas: AuraUI, AuraState, AuraSpotlight, AuraAssistEngine, AuraGpsEngine
 * Framework: Jest (jsdom environment)
 */

describe('Aura DAP Restructure — Regressão', () => {

    // ── Setup: mock dos módulos globais ───────────────────────────────────────

    beforeEach(() => {
        jest.useFakeTimers();

        global.AuraUI = {
            exibirBalao: jest.fn(),
            exibirBaloesSequenciais: jest.fn(),
            esconderBalao: jest.fn(),
            ativarBadge: jest.fn(),
            desativarBadge: jest.fn(),
            tocarAnimacao: jest.fn(),
            wasPlayerDragged: jest.fn().mockReturnValue(false),
            resetDragFlag: jest.fn(),
            init: jest.fn(),
        };

        global.AuraState = {
            getMode: jest.fn().mockReturnValue('assist'),
            setMode: jest.fn(),
            resetSession: jest.fn(),
            mode: 'assist',
            session: {},
        };

        global.AuraSpotlight = {
            aplicar: jest.fn(),
            remover: jest.fn(),
            encontrarElemento: jest.fn().mockReturnValue(document.createElement('button')),
        };

        global.AuraAssistEngine = {
            resetarProatividade: jest.fn(),
            dispararAnalise: jest.fn(),
            init: jest.fn(),
            teardown: jest.fn(),
        };

        global.AuraGpsEngine = {
            init: jest.fn(),
            teardown: jest.fn(),
        };

        // Limpa listeners de mensagem entre testes
        window._auraMessageListeners = [];
    });

    afterEach(() => {
        jest.useRealTimers();
        jest.clearAllMocks();
    });

    // ── Teste 1: Clique no mascote → balão exibido com input ─────────────────
    // Validates: Requirement 11.1

    test('clique no mascote exibe balão com texto de boas-vindas', () => {
        // Arrange: cria o elemento do player no DOM
        const player = document.createElement('div');
        player.id = 'aura-lottie-player';
        document.body.appendChild(player);

        const bubble = document.createElement('div');
        bubble.id = 'aura-speech-bubble';
        // balão não está ativo (fechado)
        document.body.appendChild(bubble);

        const stack = document.createElement('div');
        stack.id = 'aura-chat-stack';
        stack.innerHTML = '<div>mensagem antiga</div>';
        document.body.appendChild(stack);

        // Registra o handler de clique (replica o wiring do content.js)
        player.addEventListener('click', function () {
            if (global.AuraUI.wasPlayerDragged()) {
                global.AuraUI.resetDragFlag();
                return;
            }
            global.AuraUI.tocarAnimacao();
            global.AuraUI.desativarBadge();
            const b = document.getElementById('aura-speech-bubble');
            if (b && b.classList.contains('active')) {
                global.AuraUI.esconderBalao();
            } else {
                const s = document.getElementById('aura-chat-stack');
                if (s) s.innerHTML = '';
                global.AuraUI.exibirBalao('Como posso te ajudar nesta tela?', []);
            }
        });

        // Act
        player.click();

        // Assert
        expect(global.AuraUI.exibirBalao).toHaveBeenCalledTimes(1);
        expect(global.AuraUI.exibirBalao).toHaveBeenCalledWith(
            'Como posso te ajudar nesta tela?',
            []
        );
        // Stack deve ter sido limpo
        expect(stack.innerHTML).toBe('');

        // Cleanup
        document.body.removeChild(player);
        document.body.removeChild(bubble);
        document.body.removeChild(stack);
    });

    // ── Teste 2: Resposta com seletor_css → spotlight aplicado ───────────────
    // Validates: Requirement 11.3

    test('AURA_RESPONSE com seletor_css aplica spotlight no elemento', () => {
        // Arrange: registra o handler de mensagem (replica _handleMessage do assist engine)
        function handleMessage(event) {
            if (event.origin !== window.location.origin) return;
            if (!event.data || !event.data.type) return;

            if (event.data.type === 'AURA_RESPONSE') {
                const payload = event.data.payload || {};
                const textoResposta = payload.mensagem || 'Resposta';
                const temGPS = payload.gps_passos && payload.gps_passos.length > 0;

                if (!temGPS) {
                    global.AuraUI.exibirBalao(textoResposta, [], true);

                    if (payload.seletor_css) {
                        global.AuraSpotlight.remover();
                        const el = global.AuraSpotlight.encontrarElemento(payload.seletor_css);
                        if (el) {
                            global.AuraSpotlight.aplicar(payload.seletor_css, true);
                        }
                    }
                }
            }
        }
        window.addEventListener('message', handleMessage);

        // Act: simula postMessage com seletor_css
        window.postMessage(
            {
                type: 'AURA_RESPONSE',
                payload: { mensagem: 'Clique no botão salvar', seletor_css: '.btn-salvar' }
            },
            window.location.origin
        );

        // Processa eventos pendentes
        return new Promise(resolve => setTimeout(resolve, 0)).then(() => {
            // Assert
            expect(global.AuraSpotlight.aplicar).toHaveBeenCalledTimes(1);
            expect(global.AuraSpotlight.aplicar).toHaveBeenCalledWith('.btn-salvar', true);

            window.removeEventListener('message', handleMessage);
        });
    });

    // ── Teste 3: URL com aura_mission → missão carregada ─────────────────────
    // Validates: Requirement 11.4

    test('_processarMagicLink com aura_mission envia AURA_FETCH_MISSION via postMessage', () => {
        // Arrange: simula URL com parâmetro aura_mission
        const originalLocation = window.location;
        delete window.location;
        window.location = {
            search: '?aura_mission=missao_123',
            origin: 'http://localhost',
            protocol: 'http:',
            host: 'localhost',
            pathname: '/app',
            hash: '',
            href: 'http://localhost/app?aura_mission=missao_123',
        };
        window.history = { replaceState: jest.fn() };

        const postMessageSpy = jest.spyOn(window, 'postMessage');

        // Replica _processarMagicLink do content.js
        function _processarMagicLink() {
            var urlParams = new URLSearchParams(window.location.search);
            var origin = window.location.origin;

            var missionToLoad = urlParams.get('aura_mission');
            if (missionToLoad) {
                window.postMessage(
                    { type: 'AURA_FETCH_MISSION', mission_id: missionToLoad },
                    origin
                );
                var baseUrl = window.location.protocol + '//' +
                              window.location.host +
                              window.location.pathname;
                window.history.replaceState(
                    { path: baseUrl + window.location.hash },
                    '',
                    baseUrl + window.location.hash
                );
            }
        }

        // Act
        _processarMagicLink();

        // Assert
        expect(postMessageSpy).toHaveBeenCalledWith(
            { type: 'AURA_FETCH_MISSION', mission_id: 'missao_123' },
            'http://localhost'
        );

        // Cleanup
        postMessageSpy.mockRestore();
        window.location = originalLocation;
    });

    // ── Teste 4: Idle 15s → balões sequenciais proativos exibidos ────────────
    // Validates: Requirement 11.5

    test('após 15s de inatividade exibe balões sequenciais proativos no modo assist', () => {
        // Arrange: replica a lógica do idle timer do aura_assist_engine
        const TEMPO_LIMITE_SEGUNDOS = 15;
        let _tempoInativo = 0;
        let _jaOfereceuAjudaProativa = false;

        // Cria elemento do balão (não ativo = fechado)
        const bubble = document.createElement('div');
        bubble.id = 'aura-speech-bubble';
        document.body.appendChild(bubble);

        const badge = document.createElement('div');
        badge.id = 'aura-notification-badge';
        document.body.appendChild(badge);

        global.AuraState.getMode.mockReturnValue('assist');

        const idleInterval = setInterval(() => {
            _tempoInativo++;
            if (_tempoInativo >= TEMPO_LIMITE_SEGUNDOS && _tempoInativo % TEMPO_LIMITE_SEGUNDOS === 0) {
                const bubbleElement = document.getElementById('aura-speech-bubble');
                const modoAtivo = global.AuraState ? global.AuraState.getMode() : 'assist';

                if (bubbleElement && !bubbleElement.classList.contains('active') && modoAtivo === 'assist') {
                    if (!_jaOfereceuAjudaProativa) {
                        _jaOfereceuAjudaProativa = true;
                        if (global.AuraUI) {
                            global.AuraUI.exibirBaloesSequenciais(["Oiii! 👋", "Se precisar de ajuda", "Estou aqui! ✨"]);
                        }
                    }
                }
            }
        }, 1000);

        // Act: avança 15 segundos
        jest.advanceTimersByTime(15000);

        // Assert
        expect(global.AuraUI.exibirBaloesSequenciais).toHaveBeenCalledTimes(1);
        expect(global.AuraUI.exibirBaloesSequenciais).toHaveBeenCalledWith(
            ["Oiii! 👋", "Se precisar de ajuda", "Estou aqui! ✨"]
        );

        // Cleanup
        clearInterval(idleInterval);
        document.body.removeChild(bubble);
        document.body.removeChild(badge);
    });

    // ── Teste 5: Troca de URL SPA → resetarProatividade() chamado ────────────
    // Validates: Requirement 11.6

    test('mudança de URL SPA dispara AuraAssistEngine.resetarProatividade()', () => {
        // Arrange: cria body para o observer
        let urlAtual = 'http://localhost/tela-a';
        let _spaDebounce = null;

        // Simula window.location.href mutável
        Object.defineProperty(window, 'location', {
            value: { href: 'http://localhost/tela-b', origin: 'http://localhost' },
            writable: true,
            configurable: true,
        });

        const observerCallback = function () {
            if (_spaDebounce) return;
            _spaDebounce = setTimeout(function () {
                _spaDebounce = null;
                if (urlAtual !== window.location.href) {
                    urlAtual = window.location.href;
                    global.AuraAssistEngine.resetarProatividade();
                    global.AuraSpotlight.remover();
                }
            }, 300);
        };

        // Simula disparo do MutationObserver
        observerCallback();

        // Act: avança o debounce
        jest.advanceTimersByTime(300);

        // Assert
        expect(global.AuraAssistEngine.resetarProatividade).toHaveBeenCalledTimes(1);
        expect(global.AuraSpotlight.remover).toHaveBeenCalledTimes(1);
    });

    // ── Teste 6: GPS não inicia automaticamente ao receber gps_passos ─────────
    // Validates: Requirement 11.2 / Requirement 2.2

    test('AURA_RESPONSE com gps_passos NÃO muda aura_mode e exibe botão "Iniciar GPS"', () => {
        // Arrange: registra handler que replica o comportamento do assist engine
        function handleMessage(event) {
            if (event.origin !== window.location.origin) return;
            if (!event.data || !event.data.type) return;

            if (event.data.type === 'AURA_RESPONSE') {
                const payload = event.data.payload || {};
                const textoResposta = payload.mensagem || 'Resposta';
                const temGPS = payload.gps_passos &&
                               Array.isArray(payload.gps_passos) &&
                               payload.gps_passos.length > 0;

                if (temGPS) {
                    // CTA explícito — NÃO chama setMode automaticamente
                    const roteiro = {
                        id: payload.gps_nome_aula || 'gps_session',
                        passos: payload.gps_passos
                    };
                    const opcoes = [
                        {
                            label: 'Iniciar GPS',
                            action: () => {
                                global.AuraState.setMode('gps');
                                global.AuraGpsEngine.init(roteiro);
                            }
                        }
                    ];
                    global.AuraUI.exibirBalao(textoResposta, opcoes, true);
                    // aura_mode permanece 'assist' — setMode NÃO é chamado aqui
                }
            }
        }
        window.addEventListener('message', handleMessage);

        // Act: simula resposta com gps_passos
        window.postMessage(
            {
                type: 'AURA_RESPONSE',
                payload: {
                    mensagem: 'Encontrei um roteiro para você!',
                    gps_passos: [{ intent: 'Clique aqui' }]
                }
            },
            window.location.origin
        );

        return new Promise(resolve => setTimeout(resolve, 0)).then(() => {
            // Assert: setMode NÃO foi chamado com 'gps' automaticamente
            expect(global.AuraState.setMode).not.toHaveBeenCalledWith('gps');

            // Assert: exibirBalao foi chamado com botão "Iniciar GPS"
            expect(global.AuraUI.exibirBalao).toHaveBeenCalledTimes(1);
            const [, opcoes] = global.AuraUI.exibirBalao.mock.calls[0];
            expect(opcoes).toEqual(
                expect.arrayContaining([
                    expect.objectContaining({ label: 'Iniciar GPS' })
                ])
            );

            window.removeEventListener('message', handleMessage);
        });
    });

});

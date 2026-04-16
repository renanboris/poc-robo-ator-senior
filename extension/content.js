/**
 * content.js — Orquestrador Aura DAP (world: MAIN)
 *
 * Responsabilidades:
 *  1. Injetar módulos via <script> sequencial
 *  2. Inicializar UI e engines após carregamento
 *  3. Registrar handlers de Magic Link (?aura_mission, ?aura_gps)
 *  4. Registrar MutationObserver de SPA
 *  5. Guardião de login (_estaLogado / _tentarIniciarAura / _aguardarLogin)
 *
 * Sem lógica de negócio inline — apenas orquestração e wiring.
 */
(function () {
    'use strict';

    // ── Injeção de módulos ────────────────────────────────────────────────────

    function _injectScript(src, extensionId) {
        return new Promise(function (resolve, reject) {
            var s = document.createElement('script');
            s.src = 'chrome-extension://' + extensionId + '/' + src;
            s.onload = resolve;
            s.onerror = reject;
            (document.head || document.documentElement).appendChild(s);
        });
    }

    async function _carregarModulos(extensionId) {
        var modulos = [
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
            'nps_modal.js'
        ];
        for (var i = 0; i < modulos.length; i++) {
            await _injectScript(modulos[i], extensionId);
        }
    }

    // ── Obter extensionId injetado pelo background ────────────────────────────

    async function _obterExtensionId(tentativas) {
        tentativas = tentativas || 0;
        var id = document.documentElement.getAttribute('data-aura-id');
        if (id) return id;
        if (tentativas > 20) return null;
        await new Promise(function (r) { setTimeout(r, 100); });
        return _obterExtensionId(tentativas + 1);
    }

    // ── Inicialização principal ───────────────────────────────────────────────

    async function _inicializarAura(extensionId) {
        // Aguarda dotlottie-player estar definido
        if (window.customElements) {
            try {
                await window.customElements.whenDefined('dotlottie-player');
            } catch (e) {
                console.error('[Aura] dotlottie-player não disponível.', e);
                return;
            }
        }

        // ── Criar container HTML ──────────────────────────────────────────────
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
            '  <div class="aura-panel-header">',
            '    <span class="aura-panel-title">Aura</span>',
            '    <button class="aura-btn-close" id="aura-btn-close" aria-label="Fechar">✕</button>',
            '  </div>',
            '  <div class="aura-thread-area" id="aura-thread-area"',
            '       role="log" aria-live="polite" aria-label="Conversa com a Aura">',
            '  </div>',
            '  <div class="aura-options"></div>',
            '  <div class="aura-input-wrapper">',
            '    <input type="text" id="aura-prompt-input"',
            '      placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">',
            '    <button class="aura-btn-send" id="aura-btn-ask">➜</button>',
            '  </div>',
            '</div>'
        ].join('\n');
        document.documentElement.appendChild(auraContainer);

        // ── Inicializar módulos ───────────────────────────────────────────────
        window.AuraUI.init();
        window.AuraState.setMode('assist'); // dispara AuraAssistEngine.init() via registry

        // ── Ativar detector de hesitação (Smart Tips) ─────────────────────────
        if (window.AuraHesitationDetector) {
            window.AuraHesitationDetector.ativar(window._auraApiBase || 'http://localhost:8000');
        }

        // ── Inicializar modal de NPS pós-treinamento ──────────────────────────
        if (window.AuraNpsModal) {
            window.AuraNpsModal.inicializar(window._auraApiBase || 'http://localhost:8000');
        }

        // ── Handler de clique no player (toggle balão) ────────────────────────
        var player = document.getElementById('aura-lottie-player');
        if (player) {
            player.addEventListener('click', function () {
                // AuraUI rastreia drag internamente; consulta o flag antes de consumir
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
                    // Limpa sequência proativa
                    var stack = document.getElementById('aura-chat-stack');
                    if (stack) stack.innerHTML = '';
                    window.AuraUI.exibirBalao('Como posso te ajudar nesta tela?', []);
                }
            });
        }

        // ── Handlers de botões do balão ───────────────────────────────────────
        var btnAsk = document.getElementById('aura-btn-ask');
        if (btnAsk) {
            btnAsk.addEventListener('pointerdown', function (e) {
                e.preventDefault();
                e.stopPropagation();
                window.AuraAssistEngine.dispararAnalise();
            });
        }

        var promptInput = document.getElementById('aura-prompt-input');
        if (promptInput) {
            promptInput.addEventListener('keydown', function (e) {
                if (e.key === 'Enter') {
                    e.stopPropagation();
                    window.AuraAssistEngine.dispararAnalise();
                }
            });
        }

        var btnClose = document.getElementById('aura-btn-close');
        if (btnClose) {
            btnClose.addEventListener('click', function (e) {
                e.stopPropagation();
                window.AuraUI.esconderBalao();
            });
        }

        // Fechar balão ao clicar fora do container
        document.addEventListener('click', function (e) {
            var bubbleEl = document.getElementById('aura-speech-bubble');
            var container = document.getElementById('aura-floating-container');
            if (!bubbleEl || !container) return;
            if (!container.contains(e.target) && bubbleEl.classList.contains('active')) {
                window.AuraUI.esconderBalao();
            }
        });

        // ── Magic Link ────────────────────────────────────────────────────────
        _processarMagicLink();

        // ── MutationObserver de SPA ───────────────────────────────────────────
        _registrarObserverSPA();

        // ── Handlers de mensagens window ──────────────────────────────────────
        window.addEventListener('message', _handleWindowMessage);

        console.log('[Aura] Orquestrador inicializado.');
    }

    // ── Magic Link ────────────────────────────────────────────────────────────

    function _processarMagicLink() {
        var urlParams = new URLSearchParams(window.location.search);
        var origin = window.location.origin;

        // ?aura_mission=<id>
        var missionToLoad = urlParams.get('aura_mission');
        if (missionToLoad) {
            console.log('[Aura] Magic Link detectado — missão:', missionToLoad);
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

        // ?aura_gps=<objetivo>
        var gpsObjetivo = urlParams.get('aura_gps');
        if (gpsObjetivo) {
            console.log('[Aura] Magic Link GPS detectado — objetivo:', gpsObjetivo);
            window.postMessage(
                { type: 'AURA_FETCH_GPS', objetivo: gpsObjetivo },
                origin
            );
            var baseUrlGps = window.location.protocol + '//' +
                             window.location.host +
                             window.location.pathname;
            window.history.replaceState(
                { path: baseUrlGps + window.location.hash },
                '',
                baseUrlGps + window.location.hash
            );
        }
    }

    // ── MutationObserver de SPA ───────────────────────────────────────────────

    function _registrarObserverSPA() {
        var urlAtual = window.location.href;
        var _spaDebounce = null;

        var observerSPA = new MutationObserver(function () {
            if (_spaDebounce) return;
            _spaDebounce = setTimeout(function () {
                _spaDebounce = null;
                if (urlAtual !== window.location.href) {
                    urlAtual = window.location.href;
                    window.AuraAssistEngine.resetarProatividade();
                    window.AuraSpotlight.remover();
                    var bubbleEl = document.getElementById('aura-speech-bubble');
                    if (bubbleEl && bubbleEl.classList.contains('active') &&
                        window.AuraState.getMode() === 'assist') {
                        window.AuraUI.exibirBaloesSequenciais(
                            ['Oiii! 👋', 'Tela nova!', 'Precisa de ajuda? ✨']
                        );
                    }
                }
            }, 300);
        });
        observerSPA.observe(document.body, { childList: true, subtree: true });
    }

    // ── Handler de mensagens window ───────────────────────────────────────────

    function _handleWindowMessage(event) {
        if (event.origin !== window.location.origin) return;
        if (!event.data || !event.data.type) return;

        // Resposta de missão carregada via Magic Link
        if (event.data.type === 'AURA_FETCH_MISSION_RESPONSE') {
            var data = event.data.payload;
            if (!data || data.erro) {
                window.AuraUI.exibirBalao(
                    'Não consegui carregar os dados desta certificação. Verifique se o servidor está online.',
                    []
                );
                return;
            }
            var roteiro = {
                id: data.title || 'mission',
                passos: data.steps || []
            };
            var scoringConfig = data.scoring || { base_xp: 0, no_help_bonus: 50, error_penalty: 15 };
            window.AuraState.setMode('train');
            window.AuraGpsEngine.init(roteiro);
            window.AuraMissionEngine.init(scoringConfig);
            return;
        }

        // Resposta de GPS explícito (fetch_gps_explicit)
        if (event.data.type === 'AURA_GPS_EXPLICIT_RESPONSE') {
            var d = event.data.payload || {};
            if (d.status === 'sucesso' && d.passos && d.passos.length) {
                var roteiroGps = {
                    id: d.nome_aula || 'gps_session',
                    passos: d.passos
                };
                window.AuraState.setMode('gps');
                window.AuraGpsEngine.init(roteiroGps);
            } else {
                window.AuraUI.exibirBalao(
                    'Não encontrei um roteiro para isso. Tente descrever o objetivo com mais detalhes.',
                    []
                );
            }
            return;
        }
    }

    // ── Guardião de login ─────────────────────────────────────────────────────

    var _auraInicializada = false;

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

    function _tentarIniciarAura() {
        if (_auraInicializada) return;
        if (_estaLogado()) {
            _auraInicializada = true;
            console.log('[Aura] Login detectado. Inicializando assistente...');
            _obterExtensionId().then(function (extensionId) {
                if (!extensionId) {
                    console.error('[Aura] extensionId não encontrado.');
                    return;
                }
                _carregarModulos(extensionId).then(function () {
                    _inicializarAura(extensionId);
                }).catch(function (err) {
                    console.error('[Aura] Falha ao carregar módulos.', err);
                });
            });
        }
    }

    function _aguardarLogin() {
        _tentarIniciarAura();
        if (_auraInicializada) return;

        var _pollTimer = setInterval(function () {
            if (_auraInicializada) { clearInterval(_pollTimer); return; }
            _tentarIniciarAura();
        }, 500);

        var _throttle = null;
        var observer = new MutationObserver(function () {
            if (_auraInicializada) { observer.disconnect(); return; }
            if (_throttle) return;
            _throttle = setTimeout(function () {
                _throttle = null;
                _tentarIniciarAura();
                if (_auraInicializada) {
                    observer.disconnect();
                    clearInterval(_pollTimer);
                }
            }, 100);
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });

        setTimeout(function () {
            if (_auraInicializada) return;
            console.log('[Aura] Timeout atingido — inicializando por precaução.');
            observer.disconnect();
            clearInterval(_pollTimer);
            _auraInicializada = true;
            _obterExtensionId().then(function (extensionId) {
                if (!extensionId) return;
                _carregarModulos(extensionId).then(function () {
                    _inicializarAura(extensionId);
                }).catch(function (err) {
                    console.error('[Aura] Falha ao carregar módulos (timeout).', err);
                });
            });
        }, 30000);
    }

    // ── Bootstrap ─────────────────────────────────────────────────────────────

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _aguardarLogin);
    } else {
        _aguardarLogin();
    }

})();

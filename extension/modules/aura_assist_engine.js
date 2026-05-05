/**
 * aura_assist_engine.js
 * Módulo: AuraAssistEngine
 *
 * Responsável por:
 *  - Idle timer e proatividade (balões sequenciais após inatividade)
 *  - Disparo de análise IA (postMessage AURA_CAPTURE)
 *  - Handler de AURA_RESPONSE com CTA explícito para GPS quando gps_passos presente
 *  - Reativação de inputs após resposta
 *
 * Dependências (carregadas antes via <script> sequencial):
 *  - window.AuraUI       — exibirBalao, exibirBaloesSequenciais, ativarBadge, setLastPrompt
 *  - window.AuraState    — getMode, setMode, registerModule
 *  - window.AuraDomMapper — capturar()
 *  - window.AuraSpotlight — aplicar, remover
 *  - window.AuraGpsEngine — init(roteiro)  (chamado após confirmação do usuário)
 *
 * Carregado via <script> sequencial — sem bundler (world: MAIN).
 * Expõe interface pública em window.AuraAssistEngine.
 */
(function (global) {
    'use strict';

    // ── Estado privado ────────────────────────────────────────────────────────
    let _jaOfereceuAjudaProativa = false;
    let _tempoInativo = 0;
    const TEMPO_LIMITE_SEGUNDOS = 15;
    let _throttleTimer = null;
    let _idleInterval = null;
    let _messageListener = null;

    // ── Funções privadas ──────────────────────────────────────────────────────

    /**
     * Tenta descobrir o nome do usuário logado via DOM ou localStorage.
     * Retorna "Utilizador" como fallback.
     */
    function _descobrirNomeUsuario() {
        try {
            const seletoresNome = document.querySelectorAll(
                '.user-name, .profile-name, [data-testid="user-name"], .header-user span, [aria-label*="perfil de"]'
            );
            for (let el of seletoresNome) {
                const texto = el.innerText || el.textContent;
                if (texto && texto.trim().length > 2) {
                    return texto.trim().split(' ')[0];
                }
            }
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (key.toLowerCase().includes('user') || key.toLowerCase().includes('profile')) {
                    try {
                        const obj = JSON.parse(localStorage.getItem(key));
                        if (obj && (obj.name || obj.nome || obj.firstName)) {
                            const nomeCompleto = obj.name || obj.nome || obj.firstName;
                            return nomeCompleto.split(' ')[0];
                        }
                    } catch (_) { /* ignora entradas não-JSON */ }
                }
            }
        } catch (e) {
            console.warn('[AuraAssistEngine] Não foi possível descobrir o nome do usuário.', e);
        }
        return 'Utilizador';
    }

    /**
     * Reativa os inputs do balão após receber resposta da IA.
     */
    function _reativarInputs() {
        const inputEl   = document.getElementById('aura-prompt-input');
        const btnEnviar = document.getElementById('aura-btn-ask');
        if (inputEl)   { inputEl.disabled   = false; inputEl.focus(); }
        if (btnEnviar)   btnEnviar.disabled = false;
    }

    /**
     * Reseta o cronômetro de inatividade com throttle de 500ms.
     */
    function _resetarCronometro() {
        if (_throttleTimer) return;
        _tempoInativo = 0;
        _throttleTimer = setTimeout(() => { _throttleTimer = null; }, 500);
    }

    /**
     * Inicia o idle timer e registra os event listeners de atividade do usuário.
     */
    function _iniciarIdleTimer() {
        document.addEventListener('mousemove', _resetarCronometro);
        document.addEventListener('keypress',  _resetarCronometro);
        document.addEventListener('click',     _resetarCronometro);
        document.addEventListener('scroll',    _resetarCronometro);

        _idleInterval = setInterval(() => {
            _tempoInativo++;
            if (_tempoInativo >= TEMPO_LIMITE_SEGUNDOS && _tempoInativo % TEMPO_LIMITE_SEGUNDOS === 0) {
                const bubbleElement = document.getElementById('aura-speech-bubble');
                const badgeElement  = document.getElementById('aura-notification-badge');
                const modoAtivo     = global.AuraState ? global.AuraState.getMode() : 'assist';

                // Só exibe proatividade no modo assist e quando o balão não está aberto
                if (bubbleElement && !bubbleElement.classList.contains('active') && modoAtivo === 'assist') {
                    if (!_jaOfereceuAjudaProativa) {
                        _jaOfereceuAjudaProativa = true;
                        if (global.AuraUI) {
                            global.AuraUI.exibirBaloesSequenciais(["Oiii! 👋", "Se precisar de ajuda", "Estou aqui! ✨"]);
                        }
                        // Após as bubbles sumirem, acende o badge
                        setTimeout(() => {
                            if (badgeElement && global.AuraState && global.AuraState.getMode() === 'assist') {
                                badgeElement.classList.add('active');
                            }
                        }, 8000);
                    } else {
                        if (badgeElement) badgeElement.classList.add('active');
                    }
                }
            }
        }, 1000);
    }

    /**
     * Para o idle timer e remove os event listeners de atividade.
     */
    function _pararIdleTimer() {
        if (_idleInterval) {
            clearInterval(_idleInterval);
            _idleInterval = null;
        }
        document.removeEventListener('mousemove', _resetarCronometro);
        document.removeEventListener('keypress',  _resetarCronometro);
        document.removeEventListener('click',     _resetarCronometro);
        document.removeEventListener('scroll',    _resetarCronometro);
        if (_throttleTimer) {
            clearTimeout(_throttleTimer);
            _throttleTimer = null;
        }
    }

    /**
     * Handler de mensagens window para AURA_RESPONSE.
     * Implementa CTA explícito para GPS quando gps_passos está presente —
     * NÃO altera aura_mode automaticamente.
     */
    function _handleMessage(event) {
        if (event.origin !== window.location.origin) return;
        if (!event.data || !event.data.type) return;

        if (event.data.type === 'AURA_RESPONSE') {
            const payload = event.data.payload || {};
            
            // Remove Typing Indicator antes de exibir resposta
            if (global.AuraUI && typeof global.AuraUI.removerTypingIndicator === 'function') {
                global.AuraUI.removerTypingIndicator();
            }
            
            _reativarInputs();

            const textoResposta = payload.mensagem || payload.advice || 'Desculpe, não consegui processar a resposta.';

            // Monta sugestões como botões de follow-up
            let sugestoes = [];
            if (payload.sugestoes && Array.isArray(payload.sugestoes)) {
                sugestoes = payload.sugestoes.map(s => ({
                    label: s,
                    action: () => {
                        if (global.AuraSpotlight) {
                            global.AuraSpotlight.remover();
                        }
                        dispararAnalise(s);
                    }
                }));
            }

            const temGPS = payload.gps_passos && Array.isArray(payload.gps_passos) && payload.gps_passos.length > 0;
            const temSpotlight = !!(payload.seletor_css || payload.elemento_id);
            const temNavigationGuided = payload.navigation_mode === 'guided' && 
                                       payload.navigation_path && 
                                       Array.isArray(payload.navigation_path) && 
                                       payload.navigation_path.length > 0;
            const tenantIdResp = (global.AuraState && global.AuraState.session && global.AuraState.session.tenant_id)
                ? global.AuraState.session.tenant_id
                : 'senior_default';

            // Analytics: assist_response_received
            window.postMessage({
                type: 'AURA_ANALYTICS_EVENT',
                payload: {
                    event_type: 'assist_response_received',
                    timestamp:  new Date().toISOString(),
                    payload: {
                        has_gps:      temGPS,
                        has_spotlight: temSpotlight,
                        has_navigation: temNavigationGuided,
                        tenant_id:    tenantIdResp,
                        timestamp:    new Date().toISOString()
                    }
                }
            }, window.location.origin);

            if (temNavigationGuided) {
                // ── Navegação guiada passo-a-passo ────────────────────────────
                console.log('[AuraAssistEngine] Iniciando navegação guiada:', payload.breadcrumb);
                console.log('[AuraAssistEngine] window.GuidedNavigationController disponível?', typeof window.GuidedNavigationController);
                
                // Exibe mensagem do AURA
                if (global.AuraUI) {
                    global.AuraUI.exibirBalao(textoResposta, sugestoes, true);
                }
                
                // Inicializa o GuidedNavigationController se disponível
                if (window.GuidedNavigationController) {
                    console.log('[AuraAssistEngine] GuidedNavigationController encontrado, criando instância...');
                    
                    // Cria instância se não existir
                    if (!window._auraNavController) {
                        window._auraNavController = new window.GuidedNavigationController();
                        console.log('[AuraAssistEngine] Nova instância criada');
                    } else {
                        console.log('[AuraAssistEngine] Usando instância existente');
                    }
                    
                    // Inicia navegação guiada
                    window._auraNavController.startNavigation(
                        payload.navigation_path,
                        payload.breadcrumb || ''
                    ).then(function(success) {
                        if (success) {
                            console.log('[AuraAssistEngine] Navegação guiada iniciada com sucesso');
                        } else {
                            console.warn('[AuraAssistEngine] Falha ao iniciar navegação guiada');
                        }
                    }).catch(function(err) {
                        console.error('[AuraAssistEngine] Erro ao iniciar navegação guiada:', err);
                    });
                } else {
                    console.warn('[AuraAssistEngine] GuidedNavigationController não disponível');
                    console.warn('[AuraAssistEngine] window object keys:', Object.keys(window).filter(function(k) { return k.includes('Navigation') || k.includes('Guided'); }));
                }
                
            } else if (temGPS) {
                // ── CTA explícito para GPS — NÃO inicia automaticamente ──────
                // Preserva o Step_Model canônico sem achatamento (sem missionDataAdapter)
                const roteiro = {
                    id:     payload.gps_nome_aula || 'gps_session',
                    passos: payload.gps_passos   // Step_Model canônico preservado
                };

                const opcoes = [
                    {
                        label: 'Iniciar GPS',
                        action: () => {
                            if (global.AuraSpotlight) global.AuraSpotlight.remover();
                            if (global.AuraState)     global.AuraState.setMode('gps');
                            if (global.AuraGpsEngine) global.AuraGpsEngine.init(roteiro);
                        }
                    },
                    ...sugestoes.slice(0, 1)
                ];

                if (global.AuraUI) {
                    global.AuraUI.exibirBalao(textoResposta, opcoes, true);
                }
                // aura_mode permanece 'assist' até o usuário clicar em "Iniciar GPS"

            } else {
                // ── Comportamento padrão: resposta de assistente ─────────────
                if (global.AuraUI) {
                    global.AuraUI.exibirBalao(textoResposta, sugestoes, true);
                }

                // Aplica spotlight se houver seletor ou elemento_id na resposta
                if (payload.seletor_css) {
                    if (global.AuraSpotlight) {
                        global.AuraSpotlight.remover();
                        let matchAlvo = null;
                        try { matchAlvo = global.AuraSpotlight.encontrarElemento(payload.seletor_css); } catch (_) {}
                        if (matchAlvo) {
                            global.AuraSpotlight.aplicar(payload.seletor_css, true);
                        } else if (payload.elemento_id != null) {
                            global.AuraSpotlight.aplicar(payload.elemento_id, false);
                        }
                    }
                } else if (payload.elemento_id != null) {
                    if (global.AuraSpotlight) {
                        global.AuraSpotlight.aplicar(payload.elemento_id, false);
                    }
                }
            }
        }
    }

    // ── Interface pública ─────────────────────────────────────────────────────

    /**
     * Inicializa o módulo: registra listener de mensagens e inicia idle timer.
     * Chamado por AuraState.setMode('assist') ou diretamente pelo orquestrador.
     */
    function init() {
        // Evita duplo registro
        if (_messageListener) return;

        _messageListener = _handleMessage;
        window.addEventListener('message', _messageListener);
        _iniciarIdleTimer();
        console.log('[AuraAssistEngine] init()');
    }

    /**
     * Encerra o módulo: remove listener de mensagens e para idle timer.
     * Chamado por AuraState.setMode() ao sair do modo assist.
     */
    function teardown() {
        if (_messageListener) {
            window.removeEventListener('message', _messageListener);
            _messageListener = null;
        }
        _pararIdleTimer();
        console.log('[AuraAssistEngine] teardown()');
    }

    /**
     * Dispara análise IA com o texto fornecido ou com o conteúdo do input.
     * Desabilita inputs durante o processamento.
     *
     * @param {string} [textoOpcional] — texto a enviar; se omitido, usa o input ou fallback padrão
     */
    function dispararAnalise(textoOpcional) {
        const inputEl   = document.getElementById('aura-prompt-input');
        const btnEnviar = document.getElementById('aura-btn-ask');
        const prompt    = textoOpcional || (inputEl?.value || '').trim() || 'O que devo fazer nesta tela?';

        if (inputEl)   { inputEl.value = ''; inputEl.disabled = true; }
        if (btnEnviar)   btnEnviar.disabled = true;

        // Adiciona mensagem do usuário ao histórico e exibe Typing Indicator
        if (global.AuraUI) {
            if (typeof global.AuraUI.adicionarMensagemUsuario === 'function') {
                global.AuraUI.adicionarMensagemUsuario(prompt);
            }
            
            if (typeof global.AuraUI.exibirTypingIndicator === 'function') {
                global.AuraUI.exibirTypingIndicator();
            } else {
                // Fallback para compatibilidade retroativa
                global.AuraUI.exibirBalao('Já estou analisando... Só um momento! 🔍', []);
            }
            
            global.AuraUI.setLastPrompt(prompt);
        }

        const extratoDOM = global.AuraDomMapper ? global.AuraDomMapper.capturar() : '';
        const nomeReal   = _descobrirNomeUsuario();
        const tenantId   = (global.AuraState && global.AuraState.session && global.AuraState.session.tenant_id)
            ? global.AuraState.session.tenant_id
            : 'senior_default';

        // Analytics: assist_prompt_sent
        window.postMessage({
            type: 'AURA_ANALYTICS_EVENT',
            payload: {
                event_type: 'assist_prompt_sent',
                timestamp:  new Date().toISOString(),
                payload: {
                    prompt_length: prompt.length,
                    tenant_id:     tenantId,
                    timestamp:     new Date().toISOString()
                }
            }
        }, window.location.origin);

        window.postMessage({
            type:        'AURA_CAPTURE',
            url:         window.location.href,
            prompt:      prompt,
            dom_context: extratoDOM,
            user_name:   nomeReal,
            tenant_id:   'senior_default'
        }, window.location.origin);
    }

    /**
     * Reseta o estado de proatividade e o cronômetro de inatividade.
     * Chamado pelo orquestrador ao detectar troca de URL (SPA).
     */
    function resetarProatividade() {
        _jaOfereceuAjudaProativa = false;
        _tempoInativo = 0;
    }

    // ── Registro no AuraState ─────────────────────────────────────────────────
    if (global.AuraState && typeof global.AuraState.registerModule === 'function') {
        global.AuraState.registerModule('assist', { init, teardown });
    }

    global.AuraAssistEngine = {
        init,
        teardown,
        dispararAnalise,
        resetarProatividade
    };

    console.log('[AuraAssistEngine] módulo carregado.');

})(window);

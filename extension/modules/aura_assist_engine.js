/**
 * aura_assist_engine.js
 * Módulo: AuraAssistEngine
 *
 * Responsável por:
 *  - Idle timer e proatividade (balões sequenciais após inatividade)
 *  - Disparo de análise IA (postMessage AURA_CAPTURE)
 *  - Handler de AURA_RESPONSE com CTA explícito para GPS quando gps_passos presente
 *  - Reativação de inputs após resposta
 *  - Detecção de hesitação em campos de input e exibição de dica contextual (Req. 11.8, 12.4, 13.3)
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

    // ── Estado privado — Detecção de Hesitação ────────────────────────────────
    const HESITATION_THRESHOLD_MS = 5000;
    const CAMPOS_MONITORADOS = ['INPUT', 'TEXTAREA', 'SELECT'];
    const _HESITATION_TOOLTIP_ID = 'aura-hint-tooltip';
    let _hesitationTimer = null;
    let _campoHesitacao = null;
    let _hesitationFocusinHandler = null;
    let _hesitationFocusoutHandler = null;
    let _hesitationAtivo = false;
    let _hesitationApiBase = 'http://localhost:8000';

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

    // ── Funções privadas — Detecção de Hesitação ─────────────────────────────

    /**
     * Retorna o threshold de hesitação em ms.
     * Usa window.AURA_HESITATION_MS se definido e positivo, senão HESITATION_THRESHOLD_MS.
     */
    function _getHesitationThreshold() {
        const custom = global.AURA_HESITATION_MS;
        if (typeof custom === 'number' && custom > 0) return custom;
        return HESITATION_THRESHOLD_MS;
    }

    /**
     * Obtém o seletor CSS do campo para uso na consulta de hint.
     * Prioridade: #id > [name="..."] > tagName
     *
     * @param {Element} campo
     * @returns {string}
     */
    function _obterSeletorCampo(campo) {
        if (campo.id) return '#' + campo.id;
        if (campo.name) return '[name="' + campo.name + '"]';
        return campo.tagName.toLowerCase();
    }

    /**
     * Verifica se o campo é do tipo password.
     * Campos de senha nunca recebem hint (Req. 11.8).
     *
     * @param {Element} campo
     * @returns {boolean}
     */
    function _isCampoSenha(campo) {
        return !!(campo.type && campo.type.toLowerCase() === 'password');
    }

    /**
     * Remove o tooltip de hint do DOM, se existir.
     */
    function _removerTooltipHesitacao() {
        const existente = document.getElementById(_HESITATION_TOOLTIP_ID);
        if (existente && existente.parentNode) {
            existente.parentNode.removeChild(existente);
        }
    }

    /**
     * Posiciona o tooltip próximo ao campo de input.
     * Prefere abaixo; se não couber, posiciona acima.
     *
     * @param {HTMLElement} tooltip
     * @param {Element}     campo
     */
    function _posicionarTooltipHesitacao(tooltip, campo) {
        if (!campo) {
            tooltip.style.bottom = '24px';
            tooltip.style.right  = '24px';
            return;
        }

        const rect = campo.getBoundingClientRect();
        const tw   = tooltip.offsetWidth  || 260;
        const th   = tooltip.offsetHeight || 110;
        const vw   = global.innerWidth;
        const vh   = global.innerHeight;
        const GAP  = 8;

        let top  = rect.bottom + GAP;
        let left = rect.left;

        // Não sair pela direita
        if (left + tw > vw - GAP) left = vw - tw - GAP;
        if (left < GAP) left = GAP;

        // Se não couber abaixo, posicionar acima
        if (top + th > vh - GAP) top = rect.top - th - GAP;
        if (top < GAP) top = GAP;

        tooltip.style.top  = top  + 'px';
        tooltip.style.left = left + 'px';
    }

    /**
     * Cria e exibe o tooltip de hint próximo ao campo.
     * Usa textContent para todos os textos (sem innerHTML com dados da API).
     *
     * @param {Element} campo — campo de input que gerou a hesitação
     * @param {Object}  hint  — objeto retornado pela API { micro_narracao, roteiro_id, passo_id }
     */
    function _exibirTooltipHesitacao(campo, hint) {
        _removerTooltipHesitacao();

        const tooltip = document.createElement('div');
        tooltip.id = _HESITATION_TOOLTIP_ID;

        tooltip.style.cssText = [
            'position: fixed',
            'background: #1e293b',
            'color: #ffffff',
            'border-radius: 10px',
            'padding: 14px 16px',
            'max-width: 300px',
            'min-width: 200px',
            'z-index: 2147483644',
            'box-shadow: 0 8px 32px rgba(0,0,0,0.45)',
            'font-family: system-ui, -apple-system, sans-serif',
            'font-size: 13px',
            'line-height: 1.5',
            'pointer-events: auto',
            'user-select: none'
        ].join(';');

        // Cabeçalho com label e botão fechar
        const cabecalho = document.createElement('div');
        cabecalho.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:8px';

        const label = document.createElement('span');
        label.style.cssText = 'font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:0.05em;text-transform:uppercase';
        label.textContent = 'Dica Aura';
        cabecalho.appendChild(label);

        const btnFechar = document.createElement('button');
        btnFechar.style.cssText = [
            'background: transparent',
            'border: none',
            'color: #94a3b8',
            'cursor: pointer',
            'font-size: 14px',
            'line-height: 1',
            'padding: 0 0 0 8px'
        ].join(';');
        btnFechar.textContent = '✕';
        btnFechar.setAttribute('aria-label', 'Fechar dica');
        btnFechar.addEventListener('click', function (e) {
            e.stopPropagation();
            _removerTooltipHesitacao();
        });
        cabecalho.appendChild(btnFechar);
        tooltip.appendChild(cabecalho);

        // Texto da micro_narracao
        const texto = document.createElement('div');
        texto.style.cssText = 'margin-bottom:12px;color:#e2e8f0';
        texto.textContent = hint.micro_narracao || '';
        tooltip.appendChild(texto);

        // Botão "Ver passo completo"
        const btnVerPasso = document.createElement('button');
        btnVerPasso.style.cssText = [
            'background: #3b82f6',
            'border: none',
            'color: #ffffff',
            'border-radius: 6px',
            'padding: 6px 12px',
            'cursor: pointer',
            'font-size: 12px',
            'font-weight: 600',
            'width: 100%'
        ].join(';');
        btnVerPasso.textContent = 'Ver passo completo';
        btnVerPasso.addEventListener('click', function (e) {
            e.stopPropagation();
            _removerTooltipHesitacao();
            // Usa AuraGpsEngine se disponível; caso contrário apenas fecha o tooltip
            if (global.AuraGpsEngine && typeof global.AuraGpsEngine.init === 'function' && hint.roteiro_id) {
                global.AuraGpsEngine.init({ id: hint.roteiro_id });
            }
        });
        tooltip.appendChild(btnVerPasso);

        document.documentElement.appendChild(tooltip);
        _posicionarTooltipHesitacao(tooltip, campo);
    }

    /**
     * Consulta a API de hint para o campo atual.
     * Silencioso em caso de erro (fetch não quebra a extensão).
     *
     * @param {Element} campo
     */
    function _consultarHintHesitacao(campo) {
        const seletor = _obterSeletorCampo(campo);
        const apiBase = global.AURA_CONFIG && global.AURA_CONFIG.apiBase
            ? global.AURA_CONFIG.apiBase
            : _hesitationApiBase;
        const url = apiBase + '/api/dap/hint' +
                    '?url='     + encodeURIComponent(global.location.href) +
                    '&seletor=' + encodeURIComponent(seletor);

        fetch(url)
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (hint) {
                if (!hint) return;
                if (_campoHesitacao !== campo) return; // usuário já mudou de campo
                _exibirTooltipHesitacao(campo, hint);
            })
            .catch(function () {
                // Silencioso — não quebrar a extensão
            });
    }

    /**
     * Cancela o timer de hesitação em andamento.
     */
    function _cancelarTimerHesitacao() {
        if (_hesitationTimer !== null) {
            clearTimeout(_hesitationTimer);
            _hesitationTimer = null;
        }
    }

    /**
     * Inicia o monitoramento de hesitação para o campo recém-focado.
     *
     * @param {Element} campo
     */
    function _iniciarMonitoramentoHesitacao(campo) {
        _cancelarTimerHesitacao();
        _removerTooltipHesitacao();
        _campoHesitacao = campo;

        // Listener de keydown com { once: true } — cancela timer ao digitar
        campo.addEventListener('keydown', function _onKeydown() {
            _cancelarTimerHesitacao();
            _removerTooltipHesitacao();
        }, { once: true });

        _hesitationTimer = setTimeout(function () {
            _hesitationTimer = null;
            if (_campoHesitacao !== campo) return;
            if (_isCampoSenha(campo)) return; // nunca exibir hint em campos de senha
            _consultarHintHesitacao(campo);
        }, _getHesitationThreshold());
    }

    /**
     * Handler de focusin: detecta foco em campos monitorados.
     *
     * @param {FocusEvent} event
     */
    function _handleHesitationFocusin(event) {
        const alvo = event.target;
        if (!alvo || CAMPOS_MONITORADOS.indexOf(alvo.tagName) === -1) return;
        _iniciarMonitoramentoHesitacao(alvo);
    }

    /**
     * Handler de focusout: cancela timer e remove tooltip ao sair do campo.
     *
     * @param {FocusEvent} event
     */
    function _handleHesitationFocusout(event) {
        const alvo = event.target;
        if (!alvo || CAMPOS_MONITORADOS.indexOf(alvo.tagName) === -1) return;
        if (_campoHesitacao === alvo) {
            _cancelarTimerHesitacao();
            _removerTooltipHesitacao();
            _campoHesitacao = null;
        }
    }

    // ── Funções públicas — Detecção de Hesitação ──────────────────────────────

    /**
     * Ativa o detector de hesitação em campos de input.
     * Idempotente: chamar duas vezes não duplica listeners.
     *
     * @param {string} [apiBase] — base URL da API; usa window.AURA_CONFIG.apiBase ou fallback
     */
    function ativarDetectorHesitacao(apiBase) {
        if (_hesitationAtivo) return; // idempotência

        _hesitationApiBase = apiBase
            || (global.AURA_CONFIG && global.AURA_CONFIG.apiBase)
            || 'http://localhost:8000';
        _hesitationAtivo = true;

        _hesitationFocusinHandler  = _handleHesitationFocusin;
        _hesitationFocusoutHandler = _handleHesitationFocusout;

        document.addEventListener('focusin',  _hesitationFocusinHandler,  true);
        document.addEventListener('focusout', _hesitationFocusoutHandler, true);

        console.log('[AuraAssistEngine] Detector de hesitação ativado. Threshold:', _getHesitationThreshold(), 'ms');
    }

    /**
     * Desativa o detector de hesitação: remove listeners, cancela timer e remove tooltip.
     */
    function desativarDetectorHesitacao() {
        if (!_hesitationAtivo) return;

        _cancelarTimerHesitacao();
        _removerTooltipHesitacao();

        if (_hesitationFocusinHandler) {
            document.removeEventListener('focusin',  _hesitationFocusinHandler,  true);
            _hesitationFocusinHandler = null;
        }
        if (_hesitationFocusoutHandler) {
            document.removeEventListener('focusout', _hesitationFocusoutHandler, true);
            _hesitationFocusoutHandler = null;
        }

        _hesitationAtivo   = false;
        _campoHesitacao    = null;

        console.log('[AuraAssistEngine] Detector de hesitação desativado.');
    }

    // ── Handler de mensagens ──────────────────────────────────────────────────

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
                        tenant_id:    tenantIdResp,
                        timestamp:    new Date().toISOString()
                    }
                }
            }, window.location.origin);

            if (temGPS) {
                // ── CTA explícito para GPS — NÃO inicia automaticamente ──────
                // Preserva o Step_Model canônico sem achatamento (sem missionDataAdapter)
                const roteiro = {
                    id:     payload.gps_nome_aula || 'gps_session',
                    passos: payload.gps_passos   // Step_Model canônico preservado
                };

                const opcoes = [
                    {
                        label: '🧭 Me guie até lá',
                        className: 'aura-btn-gps',
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
     * Inicializa o módulo: registra listener de mensagens, inicia idle timer
     * e ativa o detector de hesitação em campos de input.
     * Chamado por AuraState.setMode('assist') ou diretamente pelo orquestrador.
     */
    function init() {
        // Evita duplo registro
        if (_messageListener) return;

        _messageListener = _handleMessage;
        window.addEventListener('message', _messageListener);
        _iniciarIdleTimer();
        ativarDetectorHesitacao();
        console.log('[AuraAssistEngine] init()');
    }

    /**
     * Encerra o módulo: remove listener de mensagens, para idle timer
     * e desativa o detector de hesitação.
     * Chamado por AuraState.setMode() ao sair do modo assist.
     */
    function teardown() {
        if (_messageListener) {
            window.removeEventListener('message', _messageListener);
            _messageListener = null;
        }
        _pararIdleTimer();
        desativarDetectorHesitacao();
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
            tenant_id:   'senior_default',
            historico:   (global.AuraUI && typeof global.AuraUI.getHistorico === 'function')
                ? global.AuraUI.getHistorico()
                : []
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
        resetarProatividade,
        ativarDetectorHesitacao,
        desativarDetectorHesitacao
    };

    console.log('[AuraAssistEngine] módulo carregado.');

})(window);

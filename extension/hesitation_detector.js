/**
 * hesitation_detector.js — Detecção Proativa de Hesitação (Smart Tips)
 *
 * Monitora eventos de foco em campos de input e detecta inatividade superior
 * a HESITATION_THRESHOLD_MS. Quando detectada, consulta a API de hint contextual
 * e exibe tooltip com micro_narracao e botão "Ver passo completo".
 *
 * Expõe: window.AuraHesitationDetector
 *   - ativar(apiBase)  — começa a monitorar campos de input
 *   - desativar()      — para o monitoramento e remove tooltips
 *
 * Requisitos: 8.1, 8.5, 8.6, 8.7
 */
(function (global) {
    'use strict';

    // ─── CONSTANTES ──────────────────────────────────────────────────────────────

    var TOOLTIP_ID             = 'aura-hint-tooltip';
    var DEFAULT_THRESHOLD_MS   = 5000;
    var CAMPOS_MONITORADOS     = ['INPUT', 'TEXTAREA', 'SELECT'];

    // ─── ESTADO PRIVADO ──────────────────────────────────────────────────────────

    var _ativo          = false;
    var _apiBase        = 'http://localhost:8000';
    var _timer          = null;
    var _campoAtual     = null;
    var _onFocusin      = null;   // listener de focusin no document
    var _onFocusout     = null;   // listener de focusout no document

    // ─── UTILITÁRIOS ─────────────────────────────────────────────────────────────

    /**
     * Retorna o threshold em ms: usa window.AURA_HESITATION_MS se definido,
     * senão DEFAULT_THRESHOLD_MS.
     */
    function _getThreshold() {
        var custom = global.AURA_HESITATION_MS;
        if (typeof custom === 'number' && custom > 0) return custom;
        return DEFAULT_THRESHOLD_MS;
    }

    /**
     * Obtém o seletor CSS do campo para uso na consulta de hint.
     * Prioridade: #id > [name="..."] > tagName
     */
    function _obterSeletor(campo) {
        if (campo.id) {
            return '#' + campo.id;
        }
        if (campo.name) {
            return '[name="' + campo.name + '"]';
        }
        return campo.tagName.toLowerCase();
    }

    /**
     * Verifica se o campo é do tipo password (nunca exibir hints — Req 8.7).
     */
    function _isCampoSenha(campo) {
        return campo.type && campo.type.toLowerCase() === 'password';
    }

    // ─── TOOLTIP ─────────────────────────────────────────────────────────────────

    /**
     * Remove o tooltip de hint do DOM, se existir.
     */
    function _removerTooltip() {
        var existente = document.getElementById(TOOLTIP_ID);
        if (existente && existente.parentNode) {
            existente.parentNode.removeChild(existente);
        }
    }

    /**
     * Cria e exibe o tooltip de hint próximo ao campo.
     * Usa textContent para todos os textos (sem innerHTML com dados da API).
     *
     * @param {Element} campo         — campo de input que gerou a hesitação
     * @param {Object}  hint          — objeto retornado pela API { micro_narracao, roteiro_id, passo_id }
     */
    function _exibirTooltip(campo, hint) {
        _removerTooltip();

        var tooltip = document.createElement('div');
        tooltip.id = TOOLTIP_ID;

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
        var cabecalho = document.createElement('div');
        cabecalho.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-bottom:8px';

        var label = document.createElement('span');
        label.style.cssText = 'font-size:11px;color:#94a3b8;font-weight:600;letter-spacing:0.05em;text-transform:uppercase';
        label.textContent = 'Dica Aura';
        cabecalho.appendChild(label);

        var btnFechar = document.createElement('button');
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
            _removerTooltip();
        });
        cabecalho.appendChild(btnFechar);

        tooltip.appendChild(cabecalho);

        // Texto da micro_narracao
        var texto = document.createElement('div');
        texto.style.cssText = 'margin-bottom:12px;color:#e2e8f0';
        texto.textContent = hint.micro_narracao || '';
        tooltip.appendChild(texto);

        // Botão "Ver passo completo" (Req 8.5)
        var btnVerPasso = document.createElement('button');
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
            _removerTooltip();
            // Inicia guided execution se disponível (Req 8.5)
            if (typeof global.AuraGuidedExecution !== 'undefined' &&
                typeof global.AuraGuidedExecution.iniciar === 'function' &&
                hint.roteiro_id) {
                global.AuraGuidedExecution.iniciar(hint.roteiro_id, _apiBase);
            }
        });
        tooltip.appendChild(btnVerPasso);

        document.documentElement.appendChild(tooltip);

        // Posicionar próximo ao campo
        _posicionarTooltip(tooltip, campo);
    }

    /**
     * Posiciona o tooltip próximo ao campo de input.
     * Prefere abaixo; se não couber, posiciona acima.
     */
    function _posicionarTooltip(tooltip, campo) {
        if (!campo) {
            tooltip.style.bottom = '24px';
            tooltip.style.right  = '24px';
            return;
        }

        var rect = campo.getBoundingClientRect();
        var tw   = tooltip.offsetWidth  || 260;
        var th   = tooltip.offsetHeight || 110;
        var vw   = global.innerWidth;
        var vh   = global.innerHeight;
        var GAP  = 8;

        var top  = rect.bottom + GAP;
        var left = rect.left;

        // Não sair pela direita
        if (left + tw > vw - GAP) left = vw - tw - GAP;
        if (left < GAP) left = GAP;

        // Se não couber abaixo, posicionar acima
        if (top + th > vh - GAP) top = rect.top - th - GAP;
        if (top < GAP) top = GAP;

        tooltip.style.top  = top  + 'px';
        tooltip.style.left = left + 'px';
    }

    // ─── CONSULTA DE HINT ────────────────────────────────────────────────────────

    /**
     * Consulta a API de hint para o campo atual.
     * Silencioso em caso de erro (Req: tratar erros de fetch silenciosamente).
     */
    function _consultarHint(campo) {
        var seletor = _obterSeletor(campo);
        var url     = _apiBase + '/api/dap/hint' +
                      '?url='     + encodeURIComponent(global.location.href) +
                      '&seletor=' + encodeURIComponent(seletor);

        fetch(url)
            .then(function (res) {
                if (!res.ok) return null;
                return res.json();
            })
            .then(function (hint) {
                // Verificar se o campo ainda está ativo e o tooltip não foi descartado
                if (!hint || hint === null) return;
                if (_campoAtual !== campo) return;  // usuário já mudou de campo
                _exibirTooltip(campo, hint);
            })
            .catch(function () {
                // Silencioso — não quebrar a extensão
            });
    }

    // ─── LÓGICA DE HESITAÇÃO ─────────────────────────────────────────────────────

    /**
     * Cancela o timer de hesitação em andamento.
     */
    function _cancelarTimer() {
        if (_timer !== null) {
            clearTimeout(_timer);
            _timer = null;
        }
    }

    /**
     * Inicia o monitoramento de hesitação para o campo recém-focado.
     */
    function _iniciarMonitoramento(campo) {
        _cancelarTimer();
        _removerTooltip();
        _campoAtual = campo;

        // Listener de keydown com { once: true } — cancela timer e remove tooltip (Req 8.6)
        campo.addEventListener('keydown', function _onKeydown() {
            _cancelarTimer();
            _removerTooltip();
        }, { once: true });

        // Timer de hesitação
        _timer = setTimeout(function () {
            _timer = null;
            // Verificar novamente se o campo ainda está ativo
            if (_campoAtual !== campo) return;
            // Nunca consultar para campos de senha (Req 8.7)
            if (_isCampoSenha(campo)) return;
            _consultarHint(campo);
        }, _getThreshold());
    }

    // ─── HANDLERS DE EVENTOS ─────────────────────────────────────────────────────

    /**
     * Handler de focusin: detecta foco em campos monitorados.
     */
    function _handleFocusin(event) {
        var alvo = event.target;
        if (!alvo || CAMPOS_MONITORADOS.indexOf(alvo.tagName) === -1) return;
        _iniciarMonitoramento(alvo);
    }

    /**
     * Handler de focusout: cancela timer e remove tooltip ao sair do campo.
     */
    function _handleFocusout(event) {
        var alvo = event.target;
        if (!alvo || CAMPOS_MONITORADOS.indexOf(alvo.tagName) === -1) return;
        if (_campoAtual === alvo) {
            _cancelarTimer();
            _removerTooltip();
            _campoAtual = null;
        }
    }

    // ─── INTERFACE PÚBLICA ───────────────────────────────────────────────────────

    /**
     * Ativa o detector de hesitação.
     * Idempotente: chamar duas vezes não duplica listeners.
     *
     * @param {string} [apiBase] — base URL da API (padrão: http://localhost:8000)
     */
    function ativar(apiBase) {
        if (_ativo) return;  // Idempotência — não duplicar listeners

        _apiBase = apiBase || 'http://localhost:8000';
        _ativo   = true;

        _onFocusin  = _handleFocusin;
        _onFocusout = _handleFocusout;

        document.addEventListener('focusin',  _onFocusin,  true);
        document.addEventListener('focusout', _onFocusout, true);

        console.log('[AuraHesitationDetector] Ativado. Threshold:', _getThreshold(), 'ms');
    }

    /**
     * Desativa o detector: remove listeners, cancela timer e remove tooltip.
     */
    function desativar() {
        if (!_ativo) return;

        _cancelarTimer();
        _removerTooltip();

        if (_onFocusin) {
            document.removeEventListener('focusin',  _onFocusin,  true);
            _onFocusin = null;
        }
        if (_onFocusout) {
            document.removeEventListener('focusout', _onFocusout, true);
            _onFocusout = null;
        }

        _ativo      = false;
        _campoAtual = null;

        console.log('[AuraHesitationDetector] Desativado.');
    }

    // ─── REGISTRO NO WINDOW ──────────────────────────────────────────────────────

    global.AuraHesitationDetector = {
        ativar:    ativar,
        desativar: desativar
    };

    console.log('[AuraHesitationDetector] Módulo carregado.');

})(window);

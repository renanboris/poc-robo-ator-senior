// Feature: aura-dap-restructure
// Module: aura_feedback
// Responsabilidade: barra de feedback de qualidade de resposta da IA (👍/👎)
//                   e modal de NPS pós-treinamento (Req. 12.6, 11.9, 13.4)
// Carregado via <script> sequencial — sem bundler, world: MAIN

(function (global) {
    'use strict';

    // ── Estado privado — NPS ──────────────────────────────────────────────────

    var _npsApiBase = (global.AURA_CONFIG && global.AURA_CONFIG.apiBase) || 'http://localhost:8000';
    var _NPS_MODAL_ID = 'aura-nps-modal';

    // ── Funções privadas — NPS ────────────────────────────────────────────────

    /**
     * Handler de mensagens para eventos de analytics do canal oficial.
     * Escuta AURA_ANALYTICS_EVENT com event_type === 'mission_complete'.
     * Valida origem antes de processar (Req. 10.3, 10.4).
     * @param {MessageEvent} event
     */
    function _handleNpsMessage(event) {
        // Validação de origem — ignorar mensagens de origens externas
        if (event.origin !== global.location.origin) return;

        if (!event.data || event.data.type !== 'AURA_ANALYTICS_EVENT') return;

        var payload = event.data.payload;
        if (!payload || payload.event_type !== 'mission_complete') return;

        var roteiroId = payload.roteiro_id;
        if (!roteiroId) return;

        var chave = 'nps_exibido_' + roteiroId;

        // Verificar se já foi exibido para este roteiro (idempotência por roteiro)
        try {
            chrome.storage.local.get([chave], function (resultado) {
                if (resultado[chave]) return; // já exibido, não mostrar novamente
                // Delay de 3s antes de exibir (Req. 11.9)
                setTimeout(function () {
                    _mostrarNpsModal(roteiroId);
                }, 3000);
            });
        } catch (e) {
            // chrome.storage não disponível — exibir diretamente após delay
            setTimeout(function () {
                _mostrarNpsModal(roteiroId);
            }, 3000);
        }
    }

    /**
     * Remove o modal NPS do DOM.
     */
    function _fecharNpsModal() {
        var el = document.getElementById(_NPS_MODAL_ID);
        if (el) el.parentNode.removeChild(el);
    }

    /**
     * Persiste que o NPS já foi exibido para este roteiro.
     * @param {string} roteiroId
     */
    function _marcarNpsExibido(roteiroId) {
        try {
            var chave = 'nps_exibido_' + roteiroId;
            var obj = {};
            obj[chave] = true;
            chrome.storage.local.set(obj);
        } catch (e) {
            // chrome.storage não disponível — silencioso
        }
    }

    /**
     * Constrói e exibe o modal de NPS pós-treinamento.
     * Idempotente: não duplica o modal se já estiver aberto.
     * @param {string} roteiroId
     */
    function _mostrarNpsModal(roteiroId) {
        // Idempotente: não duplicar o modal se já estiver aberto
        if (document.getElementById(_NPS_MODAL_ID)) return;

        var scoreSelecionado = null;

        // ── Overlay ───────────────────────────────────────────────────────────
        var overlay = document.createElement('div');
        overlay.id = _NPS_MODAL_ID;
        overlay.style.cssText = [
            'position: fixed',
            'top: 0',
            'left: 0',
            'width: 100%',
            'height: 100%',
            'background: rgba(0,0,0,0.5)',
            'z-index: 2147483647',
            'display: flex',
            'align-items: center',
            'justify-content: center',
            'font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
        ].join('; ');

        // ── Card central ──────────────────────────────────────────────────────
        var card = document.createElement('div');
        card.style.cssText = [
            'background: #1e293b',
            'border-radius: 16px',
            'max-width: 400px',
            'width: 90%',
            'padding: 28px 24px 24px',
            'box-shadow: 0 20px 60px rgba(0,0,0,0.5)',
            'color: #f1f5f9',
        ].join('; ');

        // ── Título ────────────────────────────────────────────────────────────
        var titulo = document.createElement('h3');
        titulo.textContent = 'Como foi este treinamento?';
        titulo.style.cssText = [
            'margin: 0 0 8px',
            'font-size: 18px',
            'font-weight: 600',
            'color: #f1f5f9',
        ].join('; ');

        // ── Subtítulo ─────────────────────────────────────────────────────────
        var subtitulo = document.createElement('p');
        subtitulo.textContent = 'Em uma escala de 0 a 10, o quanto este treinamento te ajudou?';
        subtitulo.style.cssText = [
            'margin: 0 0 20px',
            'font-size: 13px',
            'color: #94a3b8',
            'line-height: 1.4',
        ].join('; ');

        // ── Labels da escala ──────────────────────────────────────────────────
        var labelsRow = document.createElement('div');
        labelsRow.style.cssText = [
            'display: flex',
            'justify-content: space-between',
            'margin-bottom: 6px',
        ].join('; ');

        var labelEsq = document.createElement('span');
        labelEsq.textContent = 'Nada';
        labelEsq.style.cssText = 'font-size: 11px; color: #64748b;';

        var labelDir = document.createElement('span');
        labelDir.textContent = 'Muito';
        labelDir.style.cssText = 'font-size: 11px; color: #64748b;';

        labelsRow.appendChild(labelEsq);
        labelsRow.appendChild(labelDir);

        // ── Escala 0-10 ───────────────────────────────────────────────────────
        var escalaRow = document.createElement('div');
        escalaRow.style.cssText = [
            'display: flex',
            'gap: 4px',
            'margin-bottom: 20px',
        ].join('; ');

        var botoesPontuacao = [];

        for (var i = 0; i <= 10; i++) {
            (function (valor) {
                var btn = document.createElement('button');
                btn.textContent = String(valor);
                btn.style.cssText = [
                    'flex: 1',
                    'padding: 8px 0',
                    'border: 1px solid #334155',
                    'border-radius: 6px',
                    'background: #0f172a',
                    'color: #94a3b8',
                    'font-size: 13px',
                    'cursor: pointer',
                    'transition: background 0.15s, color 0.15s, border-color 0.15s',
                ].join('; ');

                btn.addEventListener('mouseenter', function () {
                    if (scoreSelecionado !== valor) {
                        btn.style.background = '#00e5e520';
                        btn.style.borderColor = '#00e5e5';
                        btn.style.color = '#00e5e5';
                    }
                });

                btn.addEventListener('mouseleave', function () {
                    if (scoreSelecionado !== valor) {
                        btn.style.background = '#0f172a';
                        btn.style.borderColor = '#334155';
                        btn.style.color = '#94a3b8';
                    }
                });

                btn.addEventListener('click', function () {
                    scoreSelecionado = valor;
                    // Resetar todos os botões
                    botoesPontuacao.forEach(function (b) {
                        b.style.background = '#0f172a';
                        b.style.borderColor = '#334155';
                        b.style.color = '#94a3b8';
                    });
                    // Destacar o selecionado
                    btn.style.background = '#00e5e5';
                    btn.style.borderColor = '#00e5e5';
                    btn.style.color = '#0f172a';
                });

                botoesPontuacao.push(btn);
                escalaRow.appendChild(btn);
            })(i);
        }

        // ── Textarea de comentário ────────────────────────────────────────────
        var labelComentario = document.createElement('label');
        labelComentario.textContent = 'Comentário (opcional)';
        labelComentario.style.cssText = [
            'display: block',
            'font-size: 12px',
            'color: #94a3b8',
            'margin-bottom: 6px',
        ].join('; ');

        var textarea = document.createElement('textarea');
        textarea.placeholder = 'O que poderia ser melhorado?';
        textarea.rows = 3;
        textarea.style.cssText = [
            'width: 100%',
            'box-sizing: border-box',
            'background: #0f172a',
            'border: 1px solid #334155',
            'border-radius: 8px',
            'color: #f1f5f9',
            'font-size: 13px',
            'padding: 8px 10px',
            'resize: vertical',
            'margin-bottom: 20px',
            'font-family: inherit',
            'outline: none',
        ].join('; ');

        textarea.addEventListener('focus', function () {
            textarea.style.borderColor = '#00e5e5';
        });
        textarea.addEventListener('blur', function () {
            textarea.style.borderColor = '#334155';
        });

        // ── Botões de ação ────────────────────────────────────────────────────
        var botoesRow = document.createElement('div');
        botoesRow.style.cssText = [
            'display: flex',
            'gap: 10px',
            'justify-content: flex-end',
        ].join('; ');

        var btnPular = document.createElement('button');
        btnPular.textContent = 'Pular';
        btnPular.style.cssText = [
            'padding: 9px 20px',
            'border: 1px solid #334155',
            'border-radius: 8px',
            'background: transparent',
            'color: #94a3b8',
            'font-size: 14px',
            'cursor: pointer',
        ].join('; ');

        var btnEnviar = document.createElement('button');
        btnEnviar.textContent = 'Enviar';
        btnEnviar.style.cssText = [
            'padding: 9px 20px',
            'border: none',
            'border-radius: 8px',
            'background: #00e5e5',
            'color: #0f172a',
            'font-size: 14px',
            'font-weight: 600',
            'cursor: pointer',
        ].join('; ');

        // ── Handlers de ação ──────────────────────────────────────────────────

        btnEnviar.addEventListener('click', function () {
            if (scoreSelecionado === null) return; // score obrigatório

            var comentario = textarea.value.trim() || null;

            // Enviar para a API (silencioso em caso de erro) — usa _npsApiBase
            try {
                fetch(_npsApiBase + '/api/analytics/nps', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        roteiro_id: roteiroId,
                        score: scoreSelecionado,
                        comentario: comentario,
                    }),
                }).catch(function () {});
            } catch (e) {
                // silencioso
            }

            _marcarNpsExibido(roteiroId);
            _fecharNpsModal();
        });

        btnPular.addEventListener('click', function () {
            _marcarNpsExibido(roteiroId);
            _fecharNpsModal();
        });

        botoesRow.appendChild(btnPular);
        botoesRow.appendChild(btnEnviar);

        // ── Montar card ───────────────────────────────────────────────────────
        card.appendChild(titulo);
        card.appendChild(subtitulo);
        card.appendChild(labelsRow);
        card.appendChild(escalaRow);
        card.appendChild(labelComentario);
        card.appendChild(textarea);
        card.appendChild(botoesRow);

        overlay.appendChild(card);
        document.documentElement.appendChild(overlay);
    }

    // ── Funções públicas — NPS ────────────────────────────────────────────────

    /**
     * Inicializa o módulo NPS: configura a base da API e registra o listener
     * para eventos de analytics do canal oficial (AURA_ANALYTICS_EVENT).
     * Deve ser chamado uma única vez pelo orquestrador (content.js).
     * @param {string} [apiBase] - URL base da API (opcional; usa AURA_CONFIG.apiBase como fallback)
     */
    function inicializarNps(apiBase) {
        if (apiBase) {
            _npsApiBase = apiBase;
        } else {
            _npsApiBase = (global.AURA_CONFIG && global.AURA_CONFIG.apiBase) || 'http://localhost:8000';
        }
        global.addEventListener('message', _handleNpsMessage);
    }

    /**
     * Exibe o modal de NPS para o roteiro informado.
     * Idempotente: não duplica o modal se já estiver aberto.
     * @param {string} roteiroId
     */
    function mostrarNps(roteiroId) {
        _mostrarNpsModal(roteiroId);
    }

    // ── Função existente — barra inline 👍/👎 ────────────────────────────────

    /**
     * Cria e retorna a barra de feedback (HTMLElement) para uma resposta da IA.
     * @param {string} prompt  - Texto do prompt enviado pelo usuário
     * @param {string} resposta - Texto da resposta recebida da IA (reservado para uso futuro)
     * @returns {HTMLElement}
     */
    function criar(prompt, resposta) {
        const bar = document.createElement('div');
        bar.className = 'aura-feedback-bar';

        const like = document.createElement('button');
        like.className = 'aura-fb-btn aura-fb-like';
        like.title = 'Isso ajudou';
        like.setAttribute('aria-label', 'Isso ajudou');
        like.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M7 10v12"/>
            <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/>
        </svg>`;

        const dislike = document.createElement('button');
        dislike.className = 'aura-fb-btn aura-fb-dislike';
        dislike.title = 'Não ajudou';
        dislike.setAttribute('aria-label', 'Não ajudou');
        dislike.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M17 14V2"/>
            <path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22h0a3.13 3.13 0 0 1-3-3.88Z"/>
        </svg>`;

        bar.appendChild(like);
        bar.appendChild(dislike);

        const _registrar = (tipo, btn) => {
            like.disabled = dislike.disabled = true;
            btn.classList.add(tipo === 'like' ? 'voted-yes' : 'voted-no');
            const payload = {
                tipo,
                prompt: (prompt || '').substring(0, 100),
                url: window.location.href,
                ts: Date.now()
            };
            try {
                const key = `aura_fb_${Date.now()}`;
                localStorage.setItem(key, JSON.stringify(payload));
            } catch (e) {}
            // NOVO: propaga dislike ao backend via bridge
            if (tipo === 'dislike') {
                try {
                    window.postMessage(
                        { type: 'AURA_FEEDBACK_EVENT', payload },
                        window.location.origin
                    );
                } catch (e) {}
            }
            setTimeout(() => { bar.style.opacity = '0'; }, 350);
            setTimeout(() => { bar.remove(); }, 850);
        };

        like.addEventListener('click',    (e) => { e.stopPropagation(); _registrar('like', like); });
        dislike.addEventListener('click', (e) => { e.stopPropagation(); _registrar('dislike', dislike); });

        return bar;
    }

    // Expõe namespace global
    global.AuraFeedback = {
        // Barra inline 👍/👎
        criar,
        // Modal NPS pós-treinamento (Req. 12.6, 11.9, 13.4)
        inicializarNps,
        mostrarNps,
    };

}(window));

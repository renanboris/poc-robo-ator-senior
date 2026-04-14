/**
 * nps_modal.js — Modal de NPS Pós-Treinamento (Requisito 10)
 *
 * Expõe window.AuraNpsModal com:
 *   - inicializar(apiBase) — registra listener para eventos de analytics
 *   - mostrar(roteiroId)   — exibe modal de NPS
 *
 * Regras:
 *   - textContent para todos os textos (sem innerHTML com dados externos)
 *   - Erros de fetch silenciosos
 *   - Idempotente: mostrar() duas vezes não duplica o modal
 *   - Exibido no máximo 1x por usuário por roteiro (chrome.storage.local)
 */
(function () {
    'use strict';

    var _apiBase = 'http://localhost:8000';
    var _MODAL_ID = 'aura-nps-modal';

    // ── Inicializar ───────────────────────────────────────────────────────────

    function inicializar(apiBase) {
        if (apiBase) {
            _apiBase = apiBase;
        }
        window.addEventListener('message', _handleMessage);
    }

    // ── Handler de mensagens ──────────────────────────────────────────────────

    function _handleMessage(event) {
        if (!event.data || event.data.type !== 'aura_analytics') return;
        if (event.data.evento !== 'completou') return;

        var roteiroId = event.data.roteiro_id;
        if (!roteiroId) return;

        var chave = 'nps_exibido_' + roteiroId;

        // Verificar se já foi exibido para este roteiro (Requisito 10.4)
        try {
            chrome.storage.local.get([chave], function (resultado) {
                if (resultado[chave]) return; // já exibido, não mostrar novamente
                // Aguardar 3 segundos antes de exibir (Requisito 10.1)
                setTimeout(function () {
                    mostrar(roteiroId);
                }, 3000);
            });
        } catch (e) {
            // chrome.storage não disponível — exibir diretamente após delay
            setTimeout(function () {
                mostrar(roteiroId);
            }, 3000);
        }
    }

    // ── Mostrar modal ─────────────────────────────────────────────────────────

    function mostrar(roteiroId) {
        // Idempotente: não duplicar o modal se já estiver aberto
        if (document.getElementById(_MODAL_ID)) return;

        var scoreSelecionado = null;

        // ── Overlay ───────────────────────────────────────────────────────────
        var overlay = document.createElement('div');
        overlay.id = _MODAL_ID;
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
                    botoesPontuacao.forEach(function (b, idx) {
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

        function _fecharModal() {
            var el = document.getElementById(_MODAL_ID);
            if (el) el.parentNode.removeChild(el);
        }

        function _marcarExibido() {
            try {
                var chave = 'nps_exibido_' + roteiroId;
                var obj = {};
                obj[chave] = true;
                chrome.storage.local.set(obj);
            } catch (e) {
                // chrome.storage não disponível — silencioso
            }
        }

        btnEnviar.addEventListener('click', function () {
            if (scoreSelecionado === null) return; // score obrigatório

            var comentario = textarea.value.trim() || null;

            // Enviar para a API (silencioso em caso de erro)
            try {
                fetch(_apiBase + '/api/analytics/nps', {
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

            _marcarExibido();
            _fecharModal();
        });

        btnPular.addEventListener('click', function () {
            _marcarExibido();
            _fecharModal();
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

    // ── Expor API pública ─────────────────────────────────────────────────────

    window.AuraNpsModal = {
        inicializar: inicializar,
        mostrar: mostrar,
    };

})();

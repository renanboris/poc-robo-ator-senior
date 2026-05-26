// aura_ui.js — Módulo de UI da Aura (balões, badge, drag, animação lottie)
// Carregado via <script> sequencial no world: MAIN (sem bundler)
// Depende de: window.AuraFeedback (lazy — só usa se disponível)

(function () {
    'use strict';

    // ── Estado privado do módulo ──────────────────────────────────────────────
    let _bubbleTimeout = null;
    let _bubbleEngajada = false;   // trava: true enquanto o usuário interage com o balão
    let _chatStackTimers = [];
    let _animacaoRodando = false;
    let _ultimoPromptParaFeedback = '';
    
    // Estado para histórico de conversa e typing indicator
    let _historico = [];           // { role: 'aura'|'user', texto: string, timestamp: number }
    let _typingBubbleEl = null;    // referência ao elemento DOM do Typing_Indicator ativo
    let _typingTimeout = null;     // timeout de 30s para fallback de erro
    let _scrollListenerRegistrado = false;  // flag para evitar duplicação de listeners

    // ── Referências ao DOM (resolvidas lazily) ────────────────────────────────
    function _getBubble()    { return document.getElementById('aura-speech-bubble'); }
    function _getBadge()     { return document.getElementById('aura-notification-badge'); }
    function _getStack()     { return document.getElementById('aura-chat-stack'); }
    function _getPlayer()    { return document.getElementById('aura-lottie-player'); }
    function _getContainer() { return document.getElementById('aura-floating-container'); }
    function _getThreadArea() { return document.getElementById('aura-thread-area'); }

    // ── Helpers de renderização de Message_Bubbles ────────────────────────────
    
    /**
     * Converte markdown básico para HTML seguro (negrito, itálico, code).
     * Escapa HTML primeiro para evitar XSS, depois aplica formatação.
     */
    function _renderMarkdown(texto) {
        // 1. Escapa HTML para segurança
        let safe = texto
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
        
        // 2. Aplica markdown básico
        safe = safe.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');  // **negrito**
        safe = safe.replace(/\*(.+?)\*/g, '<em>$1</em>');              // *itálico*
        safe = safe.replace(/`(.+?)`/g, '<code>$1</code>');            // `code`
        safe = safe.replace(/\n/g, '<br>');                             // quebras de linha
        
        return safe;
    }

    /**
     * Cria e insere uma Message_Bubble na Thread_Area.
     * @param {'aura'|'user'} role
     * @param {string} texto
     * @returns {HTMLElement} o elemento criado
     */
    function _appendBubble(role, texto) {
        const area = _getThreadArea();
        if (!area) return null;
        
        const bubble = document.createElement('div');
        bubble.className = `aura-msg-bubble aura-msg-${role}`;
        bubble.innerHTML = _renderMarkdown(texto);
        
        area.appendChild(bubble);
        _scrollThreadToBottom();
        
        return bubble;
    }
    
    /**
     * Scroll automático para o fundo da Thread_Area.
     */
    function _scrollThreadToBottom() {
        const area = _getThreadArea();
        if (area) {
            area.scrollTop = area.scrollHeight;
        }
    }

    // ── Drag do container ─────────────────────────────────────────────────────
    let _isDragging = false;
    let _wasDragged = false;
    let _startX, _startY, _initialX, _initialY;

    function _initDrag() {
        const player = _getPlayer();
        if (!player) return;

        player.addEventListener('mousedown', (e) => {
            _isDragging = true;
            _wasDragged = false;
            _startX = e.clientX;
            _startY = e.clientY;
            const rect = _getContainer().getBoundingClientRect();
            _initialX = rect.left;
            _initialY = rect.top;
            const container = _getContainer();
            container.style.left   = _initialX + 'px';
            container.style.top    = _initialY + 'px';
            container.style.right  = 'auto';
            container.style.bottom = 'auto';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!_isDragging) return;
            const dx = e.clientX - _startX;
            const dy = e.clientY - _startY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) _wasDragged = true;

            const container = _getContainer();
            const maxX = window.innerWidth  - container.offsetWidth;
            const maxY = window.innerHeight - container.offsetHeight;

            container.style.left = Math.max(8, Math.min(_initialX + dx, maxX - 8)) + 'px';
            container.style.top  = Math.max(8, Math.min(_initialY + dy, maxY - 8)) + 'px';
        });

        document.addEventListener('mouseup', () => {
            _isDragging = false;
        });

        // Impede que o mousedown no balão inicie o drag do container
        const bubble = _getBubble();
        if (bubble) {
            bubble.addEventListener('mousedown', (e) => {
                e.stopPropagation();
            });
        }
    }

    // ── Trava de engajamento ──────────────────────────────────────────────────
    function _initEngajamento() {
        const bubble = _getBubble();
        const input  = document.getElementById('aura-prompt-input');

        if (bubble) {
            bubble.addEventListener('mouseenter', () => {
                _bubbleEngajada = true;
                clearTimeout(_bubbleTimeout);
            });
        }

        if (input) {
            input.addEventListener('focus', () => {
                _bubbleEngajada = true;
                clearTimeout(_bubbleTimeout);
                window.postMessage({ type: 'AURA_PRE_CAPTURE' }, window.location.origin);
            });
        }
    }

    // ── Trava de engajamento por scroll ───────────────────────────────────────
    function _initScrollEngajamento() {
        // Evita duplicação de listeners
        if (_scrollListenerRegistrado) return;
        
        const area = _getThreadArea();
        if (!area) return;
        
        let scrollResetTimer = null;
        
        area.addEventListener('scroll', () => {
            // Ativa Engagement_Lock durante o scroll
            _bubbleEngajada = true;
            clearTimeout(_bubbleTimeout);
            
            // Reinicia timer de 12s após parar de scrollar
            clearTimeout(scrollResetTimer);
            scrollResetTimer = setTimeout(() => {
                // Após 12s sem scroll, permite auto-hide novamente
                _bubbleEngajada = false;
                
                // Reinicia o timer de auto-hide de 12s
                const bubble = _getBubble();
                if (bubble && bubble.classList.contains('active') && !_typingBubbleEl) {
                    _bubbleTimeout = setTimeout(() => {
                        if (bubble.classList.contains('active') && !_bubbleEngajada && !_typingBubbleEl) {
                            bubble.classList.remove('active');
                            const badge = _getBadge();
                            if (badge && !window.AuraState?.session?.mode?.startsWith('train') && !window.AuraState?.session?.mode?.startsWith('prove')) {
                                badge.classList.add('active');
                            }
                        }
                    }, 12000);
                }
            }, 12000);
        });
        
        _scrollListenerRegistrado = true;
    }

    // ── Funções de histórico de conversa ──────────────────────────────────────
    
    /**
     * Adiciona a mensagem do usuário ao _historico e renderiza na Thread_Area.
     * Chamado por dispararAnalise() antes de exibirTypingIndicator().
     * @param {string} texto
     */
    function adicionarMensagemUsuario(texto) {
        _historico.push({
            role: 'user',
            texto: texto,
            timestamp: Date.now()
        });
        _appendBubble('user', texto);
    }

    /**
     * Exibe o Typing_Indicator animado na Thread_Area.
     * Ativa Engagement_Lock e inicia timeout de 30s para fallback de erro.
     */
    function exibirTypingIndicator() {
        // Remove typing indicator anterior se existir
        removerTypingIndicator();
        
        const area = _getThreadArea();
        if (!area) return;
        
        // Cria o elemento do Typing_Indicator
        const typingBubble = document.createElement('div');
        typingBubble.className = 'aura-typing-bubble';
        typingBubble.setAttribute('aria-label', 'Aura está digitando');
        
        const dots = document.createElement('div');
        dots.className = 'aura-typing-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        
        typingBubble.appendChild(dots);
        area.appendChild(typingBubble);
        
        _typingBubbleEl = typingBubble;
        _scrollThreadToBottom();
        
        // Ativa Engagement_Lock
        _bubbleEngajada = true;
        clearTimeout(_bubbleTimeout);
        
        // Timeout de 30s para fallback de erro
        _typingTimeout = setTimeout(() => {
            removerTypingIndicator();
            exibirBalao('Desculpe, houve um problema ao processar sua solicitação. Tente novamente.', [], false);
        }, 30000);
    }

    /**
     * Remove o Typing_Indicator do DOM e cancela o timeout.
     */
    function removerTypingIndicator() {
        if (_typingBubbleEl) {
            _typingBubbleEl.remove();
            _typingBubbleEl = null;
        }
        
        if (_typingTimeout) {
            clearTimeout(_typingTimeout);
            _typingTimeout = null;
        }
    }

    // ── Interface pública ─────────────────────────────────────────────────────

    /**
     * Exibe o balão principal com texto, botões de opção e barra de feedback opcional.
     * Auto-hide em 12s se o usuário não interagir.
     */
    function exibirBalao(texto, opcoes = [], mostrarFeedback = false) {
        const bubble = _getBubble();
        const badge  = _getBadge();
        if (!bubble) return;

        // Limpa balões sequenciais se estiverem visíveis
        const stack = _getStack();
        if (stack) stack.innerHTML = '';

        clearTimeout(_bubbleTimeout);
        _bubbleEngajada = false;
        if (badge) badge.classList.remove('active');

        // Adiciona mensagem da Aura ao histórico e renderiza na Thread_Area
        _historico.push({
            role: 'aura',
            texto: texto,
            timestamp: Date.now()
        });
        _appendBubble('aura', texto);

        const optDiv = bubble.querySelector('.aura-options');
        optDiv.innerHTML = '';

        // Remove barra de feedback anterior, se houver
        bubble.querySelector('.aura-feedback-bar')?.remove();

        if (mostrarFeedback) {
            // Chamada lazy: só usa AuraFeedback se disponível
            if (window.AuraFeedback && typeof window.AuraFeedback.criar === 'function') {
                const fb = window.AuraFeedback.criar(_ultimoPromptParaFeedback, texto);
                optDiv.parentNode.insertBefore(fb, optDiv);
            }
        }

        opcoes.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = opt.className || 'aura-btn';
            btn.innerText = opt.label;
            btn.addEventListener('click', (e) => { e.stopPropagation(); opt.action(); });
            optDiv.appendChild(btn);
        });

        bubble.classList.add('active');

        // AUTO-HIDE: só fecha se o usuário não interagiu com o balão e não há Typing Indicator ativo
        _bubbleTimeout = setTimeout(() => {
            if (bubble.classList.contains('active') && !_bubbleEngajada && !_typingBubbleEl) {
                bubble.classList.remove('active');
                const badge = _getBadge();
                if (badge && !window.AuraState?.session?.mode?.startsWith('train') && !window.AuraState?.session?.mode?.startsWith('prove')) {
                    badge.classList.add('active');
                }
            }
        }, 12000);
    }

    /**
     * Exibe balões sequenciais estilo WhatsApp no chat stack.
     * Cada bolha aparece com delay humanizado e desaparece após 7s.
     */
    function exibirBaloesSequenciais(mensagens) {
        _chatStackTimers.forEach(t => clearTimeout(t));
        _chatStackTimers = [];

        const stack = _getStack();
        if (!stack) return;
        stack.innerHTML = '';

        const bubble = _getBubble();
        if (bubble) bubble.classList.remove('active');

        const DELAYS     = [0, 1100, 2000];   // ms para aparecer cada bolha
        const VIDA_BOLHA = 7000;               // ms de vida após aparecer
        const DUR_FADE   = 600;
        const OPACIDADES_ANTERIORES = [0.25, 0.55];

        mensagens.forEach((texto, i) => {
            const delay = DELAYS[i] ?? (i * 900);

            const t1 = setTimeout(() => {
                // Aplica fade progressivo a partir da 3ª bolha
                if (i >= 2) {
                    const existentes = stack.querySelectorAll('.aura-chat-bubble:not(.aura-bubble-out)');
                    existentes.forEach((el, j) => {
                        const idx = existentes.length - 1 - j;
                        const op = OPACIDADES_ANTERIORES[idx] ?? 0.15;
                        el.style.transition = 'opacity 0.5s ease';
                        el.style.opacity = op;
                    });
                }

                const el = document.createElement('div');
                el.className = 'aura-chat-bubble';
                el.textContent = texto;
                stack.appendChild(el);

                const t2 = setTimeout(() => {
                    el.classList.add('aura-bubble-out');
                    setTimeout(() => el.remove(), DUR_FADE);
                }, VIDA_BOLHA);
                _chatStackTimers.push(t2);
            }, delay);
            _chatStackTimers.push(t1);
        });
    }

    /**
     * Remove a classe `active` do balão principal (esconde o balão).
     */
    function esconderBalao() {
        const bubble = _getBubble();
        if (bubble) bubble.classList.remove('active');
    }

    /**
     * Adiciona classe `active` ao badge de notificação.
     */
    function ativarBadge() {
        const badge = _getBadge();
        if (badge) badge.classList.add('active');
    }

    /**
     * Remove classe `active` do badge de notificação.
     */
    function desativarBadge() {
        const badge = _getBadge();
        if (badge) badge.classList.remove('active');
    }

    /**
     * Toca a animação lottie uma vez (chama tocarAnimacaoUmaVez internamente).
     */
    function tocarAnimacao() {
        _tocarAnimacaoUmaVez();
    }

    function _tocarAnimacaoUmaVez() {
        const player = _getPlayer();
        if (!player) return;
        if (_animacaoRodando) return;
        _animacaoRodando = true;
        player.stop();
        player.play();
    }

    /**
     * Atualiza o último prompt usado para feedback (chamado por AuraAssistEngine).
     */
    function setLastPrompt(prompt) {
        _ultimoPromptParaFeedback = prompt || '';
    }

    /**
     * Retorna se o drag foi detectado no último mousedown (usado pelo orquestrador
     * para distinguir clique de arraste no player).
     */
    function wasPlayerDragged() {
        return _wasDragged;
    }

    /**
     * Reseta o flag de drag (chamado após consumir o evento de clique).
     */
    function resetDragFlag() {
        _wasDragged = false;
    }

    // ── Inicialização dos listeners de animação ───────────────────────────────
    // Chamada pelo orquestrador após o DOM do container estar pronto.
    function init() {
        const player = _getPlayer();
        if (player) {
            player.addEventListener('complete', () => {
                _animacaoRodando = false;
                player.pause();
            });

            player.addEventListener('ready', () => {
                _tocarAnimacaoUmaVez();
            });

            setTimeout(() => {
                if (!_animacaoRodando) _tocarAnimacaoUmaVez();
            }, 400);
        }

        _initDrag();
        _initEngajamento();
        _initScrollEngajamento();
    }

    // ── Exposição do namespace público ────────────────────────────────────────
    window.AuraUI = {
        init,
        exibirBalao,
        exibirBaloesSequenciais,
        esconderBalao,
        ativarBadge,
        desativarBadge,
        tocarAnimacao,
        setLastPrompt,
        wasPlayerDragged,
        resetDragFlag,
        adicionarMensagemUsuario,
        exibirTypingIndicator,
        removerTypingIndicator,
        getHistorico: function() {
            // Retorna as últimas 5 mensagens para contexto conversacional
            return _historico.slice(-5).map(function(m) {
                return { autor: m.role, texto: m.texto };
            });
        }
    };

    console.log('AuraUI: módulo carregado.');
})();

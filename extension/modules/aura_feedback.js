// Feature: aura-dap-restructure
// Module: aura_feedback
// Responsabilidade: barra de feedback de qualidade de resposta da IA (👍/👎)
// Carregado via <script> sequencial — sem bundler, world: MAIN

(function (global) {
    'use strict';

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
        like.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 22V11M2 13v6c0 1.1.9 2 2 2h1M16.5 3c-.8 0-1.5.7-1.5 1.5V11h4.4c.8 0 1.5.5 1.8 1.2l1.7 4.4c.2.5.1 1-.1 1.4-.3.5-.8.8-1.4.8H14c-1.1 0-2-.9-2-2v-2.5c0-.8-.7-1.5-1.5-1.5h-5C4.7 13 4 12.3 4 11.5v-7C4 3.7 4.7 3 5.5 3h9.4c.8 0 1.5.5 1.8 1.2l.8 2.1"/>
        </svg>`;

        const dislike = document.createElement('button');
        dislike.className = 'aura-fb-btn aura-fb-dislike';
        dislike.title = 'Não ajudou';
        dislike.setAttribute('aria-label', 'Não ajudou');
        dislike.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17 2v11M22 11V5c0-1.1-.9-2-2-2h-1M7.5 21c.8 0 1.5-.7 1.5-1.5V13H4.6c-.8 0-1.5-.5-1.8-1.2L1.1 7.4C.9 6.9 1 6.4 1.2 6c.3-.5.8-.8 1.4-.8H10c1.1 0 2 .9 2 2v2.5c0 .8.7 1.5 1.5 1.5h5c.8 0 1.5.7 1.5 1.5v7c0 .8-.7 1.5-1.5 1.5H8.6c-.8 0-1.5-.5-1.8-1.2l-.8-2.1"/>
        </svg>`;

        bar.appendChild(like);
        bar.appendChild(dislike);

        const _registrar = (tipo, btn) => {
            like.disabled = dislike.disabled = true;
            btn.classList.add(tipo === 'like' ? 'voted-yes' : 'voted-no');
            try {
                const key = `aura_fb_${Date.now()}`;
                localStorage.setItem(key, JSON.stringify({
                    tipo,
                    prompt: (prompt || '').substring(0, 100),
                    url: window.location.href,
                    ts: Date.now()
                }));
            } catch (e) {}
            setTimeout(() => { bar.style.opacity = '0'; }, 350);
            setTimeout(() => { bar.remove(); }, 850);
        };

        like.addEventListener('click',    (e) => { e.stopPropagation(); _registrar('like', like); });
        dislike.addEventListener('click', (e) => { e.stopPropagation(); _registrar('dislike', dislike); });

        return bar;
    }

    // Expõe namespace global
    global.AuraFeedback = {
        criar
    };

}(window));

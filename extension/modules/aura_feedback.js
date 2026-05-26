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
        like.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M7 10v12"/>
            <path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"/>
        </svg>`;

        const dislike = document.createElement('button');
        dislike.className = 'aura-fb-btn aura-fb-dislike';
        dislike.title = 'Não ajudou';
        dislike.setAttribute('aria-label', 'Não ajudou');
        dislike.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
        criar
    };

}(window));

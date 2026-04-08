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
        like.className = 'aura-fb-btn';
        like.title = 'Isso ajudou';
        like.textContent = '👍';

        const dislike = document.createElement('button');
        dislike.className = 'aura-fb-btn';
        dislike.title = 'Não ajudou';
        dislike.textContent = '👎';

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

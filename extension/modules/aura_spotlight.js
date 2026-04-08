// Feature: aura-dap-restructure
// Module: aura_spotlight — backdrop, sonar highlight, scroll para elemento
// Suporta iframes do Senior X
// world: MAIN — sem bundler, namespace global window.AuraSpotlight

(function () {
    'use strict';

    // ─── PRIVADO ─────────────────────────────────────────────────────────────────

    function encontrarElementoNaTela(seletorCSS) {
        let el = document.querySelector(seletorCSS);
        if (el) return { elemento: el, frame: null };
        const iframes = document.querySelectorAll('iframe');
        for (let frame of iframes) {
            try {
                const frameDoc = frame.contentDocument || frame.contentWindow.document;
                el = frameDoc.querySelector(seletorCSS);
                if (el) return { elemento: el, frame: frame };
            } catch (e) {}
        }
        return null;
    }

    function criarBackdrop(rect, frameTop, frameLeft) {
        document.getElementById('aura-backdrop')?.remove();
        const backdrop = document.createElement('div');
        backdrop.id = 'aura-backdrop';
        backdrop.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
            background: rgba(0,0,0,0.6); z-index: 999998; pointer-events: none;
            clip-path: polygon(
                0% 0%, 0% 100%, 
                ${frameLeft + rect.left}px 100%, 
                ${frameLeft + rect.left}px ${frameTop + rect.top}px, 
                ${frameLeft + rect.right}px ${frameTop + rect.top}px, 
                ${frameLeft + rect.right}px ${frameTop + rect.bottom}px, 
                ${frameLeft + rect.left}px ${frameTop + rect.bottom}px, 
                ${frameLeft + rect.left}px 100%, 
                100% 100%, 100% 0%
            );
            transition: opacity 0.5s ease;
            opacity: 1;
        `;
        document.body.appendChild(backdrop);
        setTimeout(() => {
            if (backdrop) {
                backdrop.style.opacity = '0';
                setTimeout(() => backdrop.remove(), 500);
            }
        }, 5000);
    }

    // ─── INTERFACE PÚBLICA ────────────────────────────────────────────────────────

    window.AuraSpotlight = {

        /**
         * Busca um elemento no document principal e em iframes do Senior X.
         * @param {string} seletor — seletor CSS
         * @returns {{ elemento: Element, frame: HTMLIFrameElement|null }|null}
         */
        encontrarElemento(seletor) {
            return encontrarElementoNaTela(seletor);
        },

        /**
         * Aplica backdrop + sonar highlight no elemento identificado por seletorOuId.
         * @param {string} seletorOuId — seletor CSS (quando isSeletor=true) ou aura-map id
         * @param {boolean} isSeletor — true: trata como seletor CSS; false: busca por data-aura-map
         */
        aplicar(seletorOuId, isSeletor = false) {
            document.getElementById('aura-sonar-highlight')?.remove();
            document.getElementById('aura-backdrop')?.remove();

            if (!seletorOuId) return;

            const match = isSeletor
                ? encontrarElementoNaTela(seletorOuId)
                : encontrarElementoNaTela(`[data-aura-map="${seletorOuId}"]`);

            if (!match || !match.elemento) return;

            const el = match.elemento;
            const frame = match.frame;

            el.scrollIntoView({ behavior: 'smooth', block: 'center' });

            setTimeout(() => {
                const rect = el.getBoundingClientRect();
                let fTop = 0, fLeft = 0;
                if (frame) {
                    const fRect = frame.getBoundingClientRect();
                    fTop = fRect.top;
                    fLeft = fRect.left;
                }

                criarBackdrop(rect, fTop, fLeft);

                const highlight = document.createElement('div');
                highlight.id = 'aura-sonar-highlight';
                const top = rect.top + fTop + window.scrollY;
                const left = rect.left + fLeft + window.scrollX;

                highlight.style.cssText = `
                    position: absolute;
                    top: ${top - 6}px; left: ${left - 6}px;
                    width: ${rect.width + 12}px; height: ${rect.height + 12}px;
                    border: 4px solid #00E676; border-radius: 8px;
                    box-shadow: 0 0 20px #00E676, inset 0 0 10px #00E676;
                    z-index: 999999; pointer-events: none;
                    animation: aura-pulse 1.5s infinite;
                    transition: opacity 0.5s ease;
                `;
                document.body.appendChild(highlight);

                setTimeout(() => {
                    if (highlight) {
                        highlight.style.opacity = '0';
                        setTimeout(() => highlight.remove(), 500);
                    }
                }, 5500);

                el.addEventListener('click', () => {
                    document.getElementById('aura-sonar-highlight')?.remove();
                    document.getElementById('aura-backdrop')?.remove();
                }, { once: true });
            }, 500);
        },

        /**
         * Remove imediatamente o sonar highlight e o backdrop, se presentes.
         */
        remover() {
            document.getElementById('aura-sonar-highlight')?.remove();
            document.getElementById('aura-backdrop')?.remove();
        }
    };

})();

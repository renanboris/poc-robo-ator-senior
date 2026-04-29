// Feature: aura-dap-restructure
// Module: AuraDomMapper
// Responsibility: Captura elementos interativos visíveis na tela para envio ao backend IA
// world: MAIN — sem bundler, namespace global window.AuraDomMapper

(function () {
    'use strict';

    /**
     * Captura os elementos interativos visíveis na tela e retorna uma string
     * formatada com a lista de elementos mapeados para consumo pela IA.
     *
     * @returns {string} Lista de elementos interativos visíveis na tela
     */
    function capturar() {
        // Limpa mapeamentos anteriores
        document.querySelectorAll('[data-aura-map]').forEach(e => e.removeAttribute('data-aura-map'));

        const auraContainer = document.getElementById('aura-floating-container');

        const seletores = [
            "button", "a", "input", "select",
            "[role='button']", "[role='menuitem']", "[role='tab']", "[role='link']",
            "[class*='btn']", "[class*='button']", "[class*='action']", "[class*='icon']",
            "[tabindex]:not([tabindex='-1'])",
            "[ng-click]", "[onclick]",
            "*:not(div):not(span):not(p):not(body):not(html)"
        ].join(", ");

        const elementos = document.querySelectorAll(seletores);
        const domList = [];
        const elementosMapeados = new Set();

        elementos.forEach((el, index) => {
            // Ignora elementos dentro do container da própria extensão
            if (auraContainer && auraContainer.contains(el)) return;

            const rect = el.getBoundingClientRect();
            const visivel = rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top <= window.innerHeight;

            if (visivel) {
                let texto = el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || "";
                texto = texto.trim().substring(0, 40).replace(/\n/g, " ");

                if (texto && texto.length > 1 && !elementosMapeados.has(texto)) {
                    elementosMapeados.add(texto);
                    el.setAttribute('data-aura-map', index);
                    domList.push(`[ID: ${index}] TIPO: ${el.tagName.toLowerCase()} | TEXTO: "${texto}"`);
                }
            }
        });

        return "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n" + domList.join("\n");
    }

    // Expõe interface pública no namespace global
    window.AuraDomMapper = {
        capturar
    };

})();

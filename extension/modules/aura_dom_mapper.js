// Feature: aura-dap-restructure
// Module: AuraDomMapper
// Responsibility: Captura elementos interativos visíveis na tela para envio ao backend IA
// world: MAIN — sem bundler, namespace global window.AuraDomMapper

(function () {
    'use strict';

    /**
     * Função auxiliar para capturar elementos em um documento específico (principal ou iframe).
     * 
     * @param {Document} doc - Document ou contentDocument para capturar
     * @param {Object|null} frameInfo - null para documento principal, ou { name: string, element: HTMLIFrameElement } para iframes
     * @param {number} startIndex - índice inicial para IDs de elementos (manter unicidade global)
     * @param {Set} elementosMapeados - Set compartilhado para filtragem de duplicatas de texto
     * @returns {{ elementos: Array, proximoIndice: number }} - elementos capturados e próximo índice disponível
     */
    function _capturarEmDocumento(doc, frameInfo, startIndex, elementosMapeados) {
        const auraContainer = document.getElementById('aura-floating-container');

        const seletores = [
            "button", "a", "input", "select",
            "[role='button']", "[role='menuitem']", "[role='tab']", "[role='link']",
            "[class*='btn']", "[class*='button']", "[class*='action']", "[class*='icon']",
            "[tabindex]:not([tabindex='-1'])",
            "[ng-click]", "[onclick]",
            "*:not(div):not(span):not(p):not(body):not(html)"
        ].join(", ");

        const elementos = doc.querySelectorAll(seletores);
        const domList = [];
        let currentIndex = startIndex;

        elementos.forEach((el) => {
            // Ignora elementos dentro do container da própria extensão
            if (auraContainer && auraContainer.contains(el)) return;

            const rect = el.getBoundingClientRect();
            
            // Para elementos em iframe, ajustar cálculo de visibilidade considerando posição do iframe
            let visivel;
            if (frameInfo && frameInfo.element) {
                // Elemento em iframe: no browser real, getBoundingClientRect() retorna valores
                // relativos ao viewport do iframe. No JSDOM, todos os rects são zero.
                // Estratégia: usar getBoundingClientRect() quando disponível (browser real),
                // e fazer fallback para style inline quando rect é zero (JSDOM).
                if (rect.width > 0 && rect.height > 0) {
                    // Browser real: tem dimensões reais
                    visivel = true;
                } else {
                    // JSDOM ou elemento sem layout: verificar style inline
                    // Considera invisível apenas se explicitamente width:0 ou height:0 no style
                    const inlineWidth  = parseFloat(el.style.width)  || 0;
                    const inlineHeight = parseFloat(el.style.height) || 0;
                    const hasExplicitZero = (el.style.width  !== '' && inlineWidth  === 0) ||
                                           (el.style.height !== '' && inlineHeight === 0);
                    visivel = !hasExplicitZero;
                }
            } else {
                // Documento principal: verificar se está dentro da viewport
                // Usa getBoundingClientRect() quando disponível; fallback para style inline no JSDOM
                if (rect.width > 0 && rect.height > 0) {
                    visivel = rect.top >= 0 && rect.top <= window.innerHeight;
                } else {
                    // JSDOM: verificar style inline — considera invisível apenas se explicitamente zero
                    const inlineWidth  = parseFloat(el.style.width)  || 0;
                    const inlineHeight = parseFloat(el.style.height) || 0;
                    const hasExplicitZero = (el.style.width  !== '' && inlineWidth  === 0) ||
                                           (el.style.height !== '' && inlineHeight === 0);
                    visivel = !hasExplicitZero;
                }
            }

            if (visivel) {
                let texto = el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("placeholder") || "";
                texto = texto.trim().substring(0, 40).replace(/\n/g, " ");

                if (texto && texto.length > 1 && !elementosMapeados.has(texto)) {
                    elementosMapeados.add(texto);
                    el.setAttribute('data-aura-map', currentIndex);
                    
                    // Formato de saída com indicador de iframe quando aplicável
                    const frameSuffix = frameInfo ? ` (iframe: ${frameInfo.name})` : '';
                    domList.push(`[ID: ${currentIndex}] TIPO: ${el.tagName.toLowerCase()} | TEXTO: "${texto}"${frameSuffix}`);
                    
                    currentIndex++;
                }
            }
        });

        return { elementos: domList, proximoIndice: currentIndex };
    }

    /**
     * Captura os elementos interativos visíveis na tela e retorna uma string
     * formatada com a lista de elementos mapeados para consumo pela IA.
     * 
     * Itera sobre documento principal e todos os iframes acessíveis (same-origin).
     *
     * @returns {string} Lista de elementos interativos visíveis na tela
     */
    function capturar() {
        // Limpa mapeamentos anteriores
        document.querySelectorAll('[data-aura-map]').forEach(e => e.removeAttribute('data-aura-map'));

        const elementosMapeados = new Set();
        const todosElementos = [];
        let proximoIndice = 0;

        // 1. Capturar elementos do documento principal
        const resultadoPrincipal = _capturarEmDocumento(document, null, proximoIndice, elementosMapeados);
        todosElementos.push(...resultadoPrincipal.elementos);
        proximoIndice = resultadoPrincipal.proximoIndice;

        // 2. Iterar sobre iframes e capturar elementos de iframes acessíveis
        const iframes = document.querySelectorAll('iframe');
        iframes.forEach(frame => {
            try {
                // Tentar acessar contentDocument (funciona apenas para same-origin)
                const frameDoc = frame.contentDocument || frame.contentWindow.document;
                
                if (frameDoc) {
                    // Extrair nome do iframe para indicador
                    const frameName = frame.name || frame.id || 'iframe';
                    const frameInfo = { name: frameName, element: frame };
                    
                    // Capturar elementos do iframe
                    const resultadoIframe = _capturarEmDocumento(frameDoc, frameInfo, proximoIndice, elementosMapeados);
                    todosElementos.push(...resultadoIframe.elementos);
                    proximoIndice = resultadoIframe.proximoIndice;
                }
            } catch (e) {
                // SecurityError para iframes cross-origin - continuar silenciosamente
                // Não logar para evitar poluir console com erros esperados
            }
        });

        return "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n" + todosElementos.join("\n");
    }

    // Expõe interface pública no namespace global
    window.AuraDomMapper = {
        capturar
    };

})();

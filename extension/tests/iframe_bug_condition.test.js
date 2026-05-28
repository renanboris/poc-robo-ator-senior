// Feature: aura-iframe-dom-capture-fix
// Bug Condition Exploration Test — Task 1
//
// **CRITICAL**: Este teste DEVE FALHAR no código NÃO CORRIGIDO
// A falha confirma que o bug existe: elementos dentro de iframes acessíveis
// NÃO são capturados pelo AuraDomMapper.capturar()
//
// **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: TESTES FALHAM
// **EXPECTED OUTCOME APÓS O FIX**: TESTES PASSAM
//
// Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3, 2.4

const fc = require('fast-check');
const fs = require('fs');
const path = require('path');
const auraDomMapperCode = fs.readFileSync(
    path.join(__dirname, '../modules/aura_dom_mapper.js'),
    'utf-8'
);

// ─────────────────────────────────────────────────────────────────────────────
// Extração da função AuraDomMapper.capturar() ORIGINAL (não corrigida)
//
// Esta é a implementação atual de extension/modules/aura_dom_mapper.js
// que NÃO itera sobre iframes, causando o bug.
// ─────────────────────────────────────────────────────────────────────────────

function capturar_original() {
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

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Cria uma página HTML de teste com iframe acessível (same-origin)
// ─────────────────────────────────────────────────────────────────────────────

function criarPaginaComIframe(iframeContent) {
    // Limpa o documento
    document.body.innerHTML = '';
    document.head.innerHTML = '';

    // Adiciona elementos no documento principal
    const mainButton = document.createElement('button');
    mainButton.textContent = 'Botão Principal';
    mainButton.style.width = '100px';
    mainButton.style.height = '30px';
    document.body.appendChild(mainButton);

    // Cria iframe acessível (same-origin)
    const iframe = document.createElement('iframe');
    iframe.id = 'test-iframe';
    iframe.name = 'ecm_sign'; // Simula o iframe do GED no Senior X
    iframe.style.width = '800px';
    iframe.style.height = '600px';
    document.body.appendChild(iframe);

    // Popula o iframe com conteúdo
    const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
    iframeDoc.body.innerHTML = iframeContent;

    return { iframe, iframeDoc };
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Verifica se a condição de bug está presente
// ─────────────────────────────────────────────────────────────────────────────

function isBugCondition() {
    // Verifica se há iframes acessíveis na página
    const iframes = document.querySelectorAll('iframe');
    let hasAccessibleIframe = false;

    iframes.forEach(frame => {
        try {
            const doc = frame.contentDocument || frame.contentWindow.document;
            if (doc) {
                hasAccessibleIframe = true;
            }
        } catch (e) {
            // Cross-origin iframe - não acessível
        }
    });

    return hasAccessibleIframe;
}

// ─────────────────────────────────────────────────────────────────────────────
// Grupo: Bug Condition — Elementos dentro de iframes NÃO são capturados
//
// **CRITICAL**: Estes testes DEVEM FALHAR no código não corrigido
// A falha confirma que o bug existe
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug Condition — Iframe Elements Not Captured (DEVE FALHAR no código não corrigido)', () => {

    beforeEach(() => {
        // Simula window.innerHeight para cálculos de visibilidade
        Object.defineProperty(window, 'innerHeight', {
            writable: true,
            configurable: true,
            value: 768
        });
        eval(auraDomMapperCode);
    });

    afterEach(() => {
        document.body.innerHTML = '';
        document.head.innerHTML = '';
        delete window.AuraDomMapper;
    });

    // ── Teste 1: Single Iframe com botão ──────────────────────────────────────
    // Validates: Requirements 1.1, 2.1, 2.2
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA
    // O botão "Novo Documento" dentro do iframe NÃO aparece na saída
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // O botão "Novo Documento" aparece na saída com indicador (iframe: ecm_sign)

    test('COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado', () => {
        // Arrange: Cria página com iframe contendo botão
        const iframeContent = `
            <button id="novo-doc" style="width: 150px; height: 40px;">Novo Documento</button>
        `;
        criarPaginaComIframe(iframeContent);

        // Verifica que a condição de bug está presente
        expect(isBugCondition()).toBe(true);

        // Act: Executa captura no código não corrigido
        const resultado = window.AuraDomMapper.capturar();

        // Assert: NO CÓDIGO NÃO CORRIGIDO, este teste FALHA
        // porque o botão do iframe NÃO está presente na saída
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('(iframe: ecm_sign)');
    });

    // ── Teste 2: Múltiplos elementos dentro de iframe ─────────────────────────
    // Validates: Requirements 1.2, 2.2, 2.3
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA
    // Nenhum dos 3 elementos do iframe aparece na saída
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Todos os 3 elementos aparecem com indicador de iframe

    test('COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados', () => {
        // Arrange: Cria iframe com 3 elementos interativos
        const iframeContent = `
            <button style="width: 150px; height: 40px;">Novo Documento</button>
            <input type="text" value="Buscar documentos" style="width: 200px; height: 30px;" />
            <a href="#" style="display: inline-block; width: 100px; height: 20px;">Ajuda</a>
        `;
        criarPaginaComIframe(iframeContent);

        expect(isBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: NO CÓDIGO NÃO CORRIGIDO, estes testes FALHAM
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('Buscar documentos');
        expect(resultado).toContain('Ajuda');
    });

    // ── Teste 3: Elementos do documento principal E iframe ────────────────────
    // Validates: Requirements 1.3, 2.1, 2.4
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA PARCIAL
    // Apenas "Botão Principal" aparece, "Botão Iframe" NÃO aparece
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Ambos os botões aparecem, com indicador de iframe para o segundo

    test('COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado', () => {
        // Arrange: Página com elementos em ambos os contextos
        const iframeContent = `
            <button style="width: 120px; height: 35px;">Botão Iframe</button>
        `;
        criarPaginaComIframe(iframeContent);

        expect(isBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: NO CÓDIGO NÃO CORRIGIDO, este teste FALHA
        // "Botão Principal" está presente, mas "Botão Iframe" NÃO está
        expect(resultado).toContain('Botão Principal');
        expect(resultado).toContain('Botão Iframe');
        expect(resultado).toContain('(iframe: ecm_sign)');
    });

    // ── Teste 4: Verificar que data-aura-map NÃO é atribuído a elementos de iframe ─
    // Validates: Requirements 2.3, 2.4
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA
    // Elementos dentro do iframe NÃO recebem data-aura-map
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Elementos do iframe recebem data-aura-map com índices únicos

    test('COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map', () => {
        // Arrange
        const iframeContent = `
            <button id="iframe-btn" style="width: 120px; height: 35px;">Botão Iframe</button>
        `;
        const { iframe, iframeDoc } = criarPaginaComIframe(iframeContent);

        expect(isBugCondition()).toBe(true);

        // Act
        window.AuraDomMapper.capturar();

        // Assert: NO CÓDIGO NÃO CORRIGIDO, este teste FALHA
        // O botão do iframe NÃO tem data-aura-map
        const iframeButton = iframeDoc.getElementById('iframe-btn');
        expect(iframeButton.hasAttribute('data-aura-map')).toBe(true);
    });

    // ── Property-Based Test: Qualquer iframe com elementos deve ser capturado ─
    // Validates: Requirements 2.1, 2.2, 2.3, 2.4
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA
    // Para qualquer número de elementos em iframe, nenhum é capturado
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Todos os elementos acessíveis em iframes são capturados

    test('fc.property: Elementos em iframes acessíveis DEVEM ser capturados', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 5 }), // Número de botões no iframe
                fc.array(
                    fc.string({ minLength: 3, maxLength: 20 }).filter(s => s.trim().length > 1),
                    { minLength: 1, maxLength: 5 }
                ), // Textos dos botões com conteúdo visível
                (numButtons, buttonTexts) => {
                    // Arrange: Cria iframe com N botões
                    const buttons = buttonTexts.slice(0, numButtons).map(text => 
                        `<button style="width: 100px; height: 30px;">${text}</button>`
                    ).join('\n');
                    
                    criarPaginaComIframe(buttons);
                    expect(isBugCondition()).toBe(true);

                    // Act
                    const resultado = window.AuraDomMapper.capturar();

                    // Assert: NO CÓDIGO NÃO CORRIGIDO, este teste FALHA
                    // Pelo menos um dos textos dos botões deve aparecer na saída
                    const algumTextoEncontrado = buttonTexts.slice(0, numButtons).some(text => 
                        resultado.includes(text.trim().substring(0, 40))
                    );
                    expect(algumTextoEncontrado).toBe(true);
                }
            ),
            { numRuns: 50 }
        );
    });

    // ── Teste 5: Cenário real do Senior X GED ─────────────────────────────────
    // Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.4
    //
    // **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: FALHA
    // Elementos do GED (dentro do iframe ecm_sign) NÃO são capturados
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Elementos do GED aparecem com indicador (iframe: ecm_sign)

    test('COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados', () => {
        // Arrange: Simula estrutura do Senior X com GED
        document.body.innerHTML = `
            <div id="header" style="width: 100%; height: 60px;">
                <button style="width: 80px; height: 30px;">Menu</button>
            </div>
            <div id="sidebar" style="width: 200px; height: 600px;">
                <button style="width: 150px; height: 35px;">Novidades e atualizações</button>
            </div>
            <iframe id="ecm_sign" name="ecm_sign" style="width: 1000px; height: 700px;"></iframe>
        `;

        const iframe = document.getElementById('ecm_sign');
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.body.innerHTML = `
            <div id="ged-toolbar">
                <button style="width: 150px; height: 40px;">Novo Documento</button>
                <input type="text" placeholder="Buscar documentos" style="width: 300px; height: 35px;" />
                <button style="width: 100px; height: 40px;">Filtros</button>
            </div>
        `;

        expect(isBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: NO CÓDIGO NÃO CORRIGIDO, estes testes FALHAM
        // Elementos do header/sidebar aparecem, mas elementos do GED NÃO
        expect(resultado).toContain('Menu'); // Documento principal - OK
        expect(resultado).toContain('Novidades e atualizações'); // Documento principal - OK
        expect(resultado).toContain('Novo Documento'); // Iframe - FALHA no código não corrigido
        expect(resultado).toContain('Buscar documentos'); // Iframe - FALHA no código não corrigido
        expect(resultado).toContain('Filtros'); // Iframe - FALHA no código não corrigido
        expect(resultado).toContain('(iframe: ecm_sign)'); // Indicador - FALHA no código não corrigido
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Documentação de Counterexamples Esperados
// ─────────────────────────────────────────────────────────────────────────────
//
// Quando este teste é executado no código NÃO CORRIGIDO, esperamos ver falhas como:
//
// FAIL extension/tests/iframe_bug_condition.test.js
//   Bug Condition — Iframe Elements Not Captured
//     ✕ COUNTEREXAMPLE: Botão "Novo Documento" dentro de iframe ecm_sign NÃO é capturado
//       Expected substring: "Novo Documento"
//       Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
//
//     ✕ COUNTEREXAMPLE: Múltiplos elementos dentro de iframe NÃO são capturados
//       Expected substring: "Novo Documento"
//       Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
//
//     ✕ COUNTEREXAMPLE: Apenas elementos do documento principal são capturados, iframe é ignorado
//       Expected substring: "Botão Iframe"
//       Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n[ID: 0] TIPO: button | TEXTO: \"Botão Principal\""
//
//     ✕ COUNTEREXAMPLE: Elementos de iframe NÃO recebem data-aura-map
//       Expected: true
//       Received: false
//
//     ✕ fc.property: Elementos em iframes acessíveis DEVEM ser capturados
//       Property failed after 1 tests
//       Counterexample: [2, ["button1", "button2"]]
//
//     ✕ COUNTEREXAMPLE: Cenário real Senior X GED - elementos do iframe ecm_sign NÃO são capturados
//       Expected substring: "Novo Documento"
//       Received string: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n[ID: 0] TIPO: button | TEXTO: \"Menu\"\n[ID: 1] TIPO: button | TEXTO: \"Novidades e atualizações\""
//
// Estas falhas CONFIRMAM que o bug existe: elementos dentro de iframes acessíveis
// NÃO são capturados pelo AuraDomMapper.capturar()
//
// Após implementar o fix (Task 3), estes mesmos testes devem PASSAR, confirmando
// que o bug foi corrigido.

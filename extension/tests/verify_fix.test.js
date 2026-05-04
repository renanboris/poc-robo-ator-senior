// Feature: aura-iframe-dom-capture-fix
// Task 3.2: Verificação do Fix — Teste deve PASSAR após implementação
//
// Este teste carrega o código CORRIGIDO de aura_dom_mapper.js
// e verifica que elementos de iframe agora são capturados corretamente.
//
// **EXPECTED OUTCOME**: TODOS OS TESTES PASSAM

const fs = require('fs');
const path = require('path');

// Carrega o código corrigido de aura_dom_mapper.js
const auraDomMapperCode = fs.readFileSync(
    path.join(__dirname, '../modules/aura_dom_mapper.js'),
    'utf-8'
);

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
// Grupo: Verificação do Fix — Elementos de iframe DEVEM ser capturados
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 3.2 — Verificação do Fix (DEVE PASSAR após implementação)', () => {

    beforeEach(() => {
        // Simula window.innerHeight para cálculos de visibilidade
        Object.defineProperty(window, 'innerHeight', {
            writable: true,
            configurable: true,
            value: 768
        });

        // Carrega o código corrigido no ambiente de teste
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
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // O botão "Novo Documento" aparece na saída com indicador (iframe: ecm_sign)

    test('✅ Botão "Novo Documento" dentro de iframe ecm_sign É capturado', () => {
        // Arrange: Cria página com iframe contendo botão
        const iframeContent = `
            <button id="novo-doc" style="width: 150px; height: 40px;">Novo Documento</button>
        `;
        criarPaginaComIframe(iframeContent);

        // Act: Executa captura com código CORRIGIDO
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Após o FIX, este teste PASSA
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('(iframe: ecm_sign)');
    });

    // ── Teste 2: Múltiplos elementos dentro de iframe ─────────────────────────
    // Validates: Requirements 1.2, 2.2, 2.3
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Todos os 3 elementos aparecem com indicador de iframe

    test('✅ Múltiplos elementos dentro de iframe SÃO capturados', () => {
        // Arrange: Cria iframe com 3 elementos interativos
        const iframeContent = `
            <button style="width: 150px; height: 40px;">Novo Documento</button>
            <input type="text" value="Buscar documentos" style="width: 200px; height: 30px;" />
            <a href="#" style="display: inline-block; width: 100px; height: 20px;">Ajuda</a>
        `;
        criarPaginaComIframe(iframeContent);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Após o FIX, estes testes PASSAM
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('Buscar documentos');
        expect(resultado).toContain('Ajuda');
        expect(resultado).toContain('(iframe: ecm_sign)');
    });

    // ── Teste 3: Elementos do documento principal E iframe ────────────────────
    // Validates: Requirements 1.3, 2.1, 2.4
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Ambos os botões aparecem, com indicador de iframe para o segundo

    test('✅ Elementos do documento principal E iframe são capturados', () => {
        // Arrange: Página com elementos em ambos os contextos
        const iframeContent = `
            <button style="width: 120px; height: 35px;">Botão Iframe</button>
        `;
        criarPaginaComIframe(iframeContent);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Após o FIX, este teste PASSA
        expect(resultado).toContain('Botão Principal');
        expect(resultado).toContain('Botão Iframe');
        expect(resultado).toContain('(iframe: ecm_sign)');
        
        // Verifica que "Botão Principal" NÃO tem indicador de iframe
        const lines = resultado.split('\n');
        const mainButtonLine = lines.find(line => line.includes('Botão Principal'));
        expect(mainButtonLine).not.toContain('(iframe:');
        
        // Verifica que "Botão Iframe" TEM indicador de iframe
        const iframeButtonLine = lines.find(line => line.includes('Botão Iframe'));
        expect(iframeButtonLine).toContain('(iframe: ecm_sign)');
    });

    // ── Teste 4: Verificar que data-aura-map É atribuído a elementos de iframe ─
    // Validates: Requirements 2.3, 2.4
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Elementos do iframe recebem data-aura-map com índices únicos

    test('✅ Elementos de iframe RECEBEM data-aura-map', () => {
        // Arrange
        const iframeContent = `
            <button id="iframe-btn" style="width: 120px; height: 35px;">Botão Iframe</button>
        `;
        const { iframe, iframeDoc } = criarPaginaComIframe(iframeContent);

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Após o FIX, este teste PASSA
        const iframeButton = iframeDoc.getElementById('iframe-btn');
        expect(iframeButton.hasAttribute('data-aura-map')).toBe(true);
        
        // Verifica que o índice é maior que 0 (pois o botão principal vem primeiro)
        const iframeButtonIndex = parseInt(iframeButton.getAttribute('data-aura-map'));
        expect(iframeButtonIndex).toBeGreaterThan(0);
    });

    // ── Teste 5: Verificar índices globalmente únicos ─────────────────────────
    // Validates: Requirements 2.3, 2.4
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Índices não reiniciam para cada iframe, são globalmente únicos

    test('✅ Índices são globalmente únicos entre documento principal e iframes', () => {
        // Arrange: Cria página com múltiplos elementos em ambos os contextos
        document.body.innerHTML = '';
        
        const btn1 = document.createElement('button');
        btn1.textContent = 'Botão 1';
        btn1.style.width = '100px';
        btn1.style.height = '30px';
        document.body.appendChild(btn1);
        
        const btn2 = document.createElement('button');
        btn2.textContent = 'Botão 2';
        btn2.style.width = '100px';
        btn2.style.height = '30px';
        document.body.appendChild(btn2);
        
        const iframe = document.createElement('iframe');
        iframe.name = 'test-frame';
        iframe.style.width = '800px';
        iframe.style.height = '600px';
        document.body.appendChild(iframe);
        
        const iframeDoc = iframe.contentDocument;
        const btn3 = iframeDoc.createElement('button');
        btn3.id = 'btn3';
        btn3.textContent = 'Botão 3';
        btn3.style.width = '100px';
        btn3.style.height = '30px';
        iframeDoc.body.appendChild(btn3);
        
        const btn4 = iframeDoc.createElement('button');
        btn4.id = 'btn4';
        btn4.textContent = 'Botão 4';
        btn4.style.width = '100px';
        btn4.style.height = '30px';
        iframeDoc.body.appendChild(btn4);

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Índices devem ser sequenciais e únicos
        const idx1 = parseInt(btn1.getAttribute('data-aura-map'));
        const idx2 = parseInt(btn2.getAttribute('data-aura-map'));
        const idx3 = parseInt(btn3.getAttribute('data-aura-map'));
        const idx4 = parseInt(btn4.getAttribute('data-aura-map'));
        
        expect(idx1).toBe(0);
        expect(idx2).toBe(1);
        expect(idx3).toBe(2); // Não reinicia, continua de onde parou
        expect(idx4).toBe(3);
        
        // Verifica que todos os índices são únicos
        const indices = [idx1, idx2, idx3, idx4];
        const uniqueIndices = new Set(indices);
        expect(uniqueIndices.size).toBe(4);
    });

    // ── Teste 6: Cenário real do Senior X GED ─────────────────────────────────
    // Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.4
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Elementos do GED aparecem com indicador (iframe: ecm_sign)

    test('✅ Cenário real Senior X GED - elementos do iframe ecm_sign SÃO capturados', () => {
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

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Após o FIX, estes testes PASSAM
        expect(resultado).toContain('Menu'); // Documento principal
        expect(resultado).toContain('Novidades e atualizações'); // Documento principal
        expect(resultado).toContain('Novo Documento'); // Iframe - AGORA CAPTURADO
        expect(resultado).toContain('Buscar documentos'); // Iframe - AGORA CAPTURADO
        expect(resultado).toContain('Filtros'); // Iframe - AGORA CAPTURADO
        expect(resultado).toContain('(iframe: ecm_sign)'); // Indicador presente
    });

    // ── Teste 7: Cross-origin iframes não causam erro ─────────────────────────
    // Validates: Requirements 3.1 (Preservation)
    //
    // **EXPECTED OUTCOME APÓS O FIX**: PASSA
    // Iframes cross-origin são ignorados silenciosamente sem causar erro

    test('✅ Cross-origin iframes não causam erro (tratamento de SecurityError)', () => {
        // Arrange: Cria página com botão principal
        document.body.innerHTML = '';
        
        const mainButton = document.createElement('button');
        mainButton.textContent = 'Botão Principal';
        mainButton.style.width = '100px';
        mainButton.style.height = '30px';
        document.body.appendChild(mainButton);
        
        // Simula iframe cross-origin (não podemos criar um real em jsdom)
        // Mas podemos verificar que o código não quebra
        const iframe = document.createElement('iframe');
        iframe.name = 'cross-origin-frame';
        iframe.style.width = '800px';
        iframe.style.height = '600px';
        document.body.appendChild(iframe);
        
        // Sobrescreve contentDocument para simular SecurityError
        Object.defineProperty(iframe, 'contentDocument', {
            get() {
                throw new DOMException('Blocked a frame with origin', 'SecurityError');
            }
        });
        Object.defineProperty(iframe, 'contentWindow', {
            get() {
                return {
                    get document() {
                        throw new DOMException('Blocked a frame with origin', 'SecurityError');
                    }
                };
            }
        });

        // Act: Não deve lançar erro
        expect(() => {
            const resultado = window.AuraDomMapper.capturar();
            // Deve capturar apenas o botão principal
            expect(resultado).toContain('Botão Principal');
        }).not.toThrow();
    });

});

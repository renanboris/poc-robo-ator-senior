// Feature: aura-iframe-dom-capture-fix
// Unit Tests for Iframe Capture Logic — Task 4
//
// Testes unitários para validar a lógica de captura de elementos em iframes
// implementada em aura_dom_mapper.js

const fs = require('fs');
const path = require('path');

// Carrega o código corrigido de aura_dom_mapper.js
const auraDomMapperCode = fs.readFileSync(
    path.join(__dirname, '../modules/aura_dom_mapper.js'),
    'utf-8'
);

// ─────────────────────────────────────────────────────────────────────────────
// Task 4.1: Test `_capturarEmDocumento` helper function
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 4.1 — Unit Tests: _capturarEmDocumento helper function', () => {

    beforeEach(() => {
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

    // ── Teste 1: Captura do documento principal (frameInfo = null) ────────────
    test('_capturarEmDocumento captura elementos do documento principal', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão 1</button>
            <button style="width: 100px; height: 30px;">Botão 2</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão 1');
        expect(resultado).toContain('Botão 2');
        expect(resultado).not.toContain('(iframe:');
    });

    // ── Teste 2: Captura de iframe (frameInfo com name) ───────────────────────
    test('_capturarEmDocumento captura elementos de iframe com indicador', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Principal');
        expect(resultado).toContain('Botão Iframe');
        expect(resultado).toContain('(iframe: test-frame)');
    });

    // ── Teste 3: startIndex é respeitado ──────────────────────────────────────
    test('_capturarEmDocumento respeita startIndex para índices únicos', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Botão 1</button>
            <button id="btn2" style="width: 100px; height: 30px;">Botão 2</button>
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="btn3" style="width: 100px; height: 30px;">Botão 3</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Índices devem ser sequenciais
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        const btn3 = iframeDoc.getElementById('btn3');

        const idx1 = parseInt(btn1.getAttribute('data-aura-map'));
        const idx2 = parseInt(btn2.getAttribute('data-aura-map'));
        const idx3 = parseInt(btn3.getAttribute('data-aura-map'));

        expect(idx1).toBe(0);
        expect(idx2).toBe(1);
        expect(idx3).toBe(2); // Continua do documento principal
    });

    // ── Teste 4: Filtragem de visibilidade funciona em ambos os contextos ─────
    test('_capturarEmDocumento filtra elementos invisíveis em documento principal', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Visível</button>
            <button style="width: 0; height: 0;">Invisível</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Visível');
        expect(resultado).not.toContain('Invisível');
    });

    test('_capturarEmDocumento filtra elementos invisíveis em iframe', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Visível Iframe</button>
            <button style="width: 0; height: 0;">Invisível Iframe</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Visível Iframe');
        expect(resultado).not.toContain('Invisível Iframe');
    });

    // ── Teste 5: Filtragem de duplicatas funciona em ambos os contextos ───────
    test('_capturarEmDocumento filtra duplicatas no documento principal', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Salvar</button>
            <button id="btn2" style="width: 100px; height: 30px;">Salvar</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        const ocorrencias = (resultado.match(/Salvar/g) || []).length;
        expect(ocorrencias).toBe(1);

        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        expect(btn1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn2.hasAttribute('data-aura-map')).toBe(false);
    });

    test('_capturarEmDocumento filtra duplicatas entre documento principal e iframe', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Salvar</button>
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="btn2" style="width: 100px; height: 30px;">Salvar</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Apenas uma ocorrência (do documento principal)
        const ocorrencias = (resultado.match(/Salvar/g) || []).length;
        expect(ocorrencias).toBe(1);

        const btn1 = document.getElementById('btn1');
        const btn2 = iframeDoc.getElementById('btn2');
        expect(btn1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn2.hasAttribute('data-aura-map')).toBe(false);
    });

    // ── Teste 6: Exclusão do container AURA funciona em ambos os contextos ────
    test('_capturarEmDocumento exclui container AURA no documento principal', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Normal</button>
            <div id="aura-floating-container">
                <button style="width: 100px; height: 30px;">Botão AURA</button>
            </div>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Normal');
        expect(resultado).not.toContain('Botão AURA');
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Task 4.2: Test iframe iteration and error handling
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 4.2 — Unit Tests: Iframe iteration and error handling', () => {

    beforeEach(() => {
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

    // ── Teste 1: Iframes same-origin acessíveis são processados ───────────────
    test('Iframes same-origin acessíveis são processados', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="frame1" name="frame1" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('frame1');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Frame 1</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Frame 1');
        expect(resultado).toContain('(iframe: frame1)');
    });

    // ── Teste 2: SecurityError cross-origin é tratado silenciosamente ─────────
    test('SecurityError cross-origin é tratado silenciosamente', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="cross-origin" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('cross-origin');
        
        // Simula SecurityError
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
            expect(resultado).toContain('Botão Principal');
        }).not.toThrow();
    });

    // ── Teste 3: Iframes vazios não adicionam elementos ────────────────────────
    test('Iframes vazios não adicionam elementos mas não causam erro', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="empty-frame" name="empty-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('empty-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = ''; // Vazio

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Principal');
        const linhas = resultado.split('\n').filter(l => l.trim());
        expect(linhas.length).toBe(2); // Header + 1 elemento
    });

    // ── Teste 4: Múltiplos iframes são processados em ordem DOM ───────────────
    test('Múltiplos iframes são processados em ordem DOM', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="frame1" name="frame1" style="width: 800px; height: 600px;"></iframe>
            <iframe id="frame2" name="frame2" style="width: 800px; height: 600px;"></iframe>
        `;

        const frame1 = document.getElementById('frame1');
        const frame1Doc = frame1.contentDocument;
        frame1Doc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Frame 1</button>
        `;

        const frame2 = document.getElementById('frame2');
        const frame2Doc = frame2.contentDocument;
        frame2Doc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Frame 2</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Principal');
        expect(resultado).toContain('Botão Frame 1');
        expect(resultado).toContain('Botão Frame 2');
        expect(resultado).toContain('(iframe: frame1)');
        expect(resultado).toContain('(iframe: frame2)');

        // Verifica ordem: Principal → Frame1 → Frame2
        const idxPrincipal = resultado.indexOf('Botão Principal');
        const idxFrame1 = resultado.indexOf('Botão Frame 1');
        const idxFrame2 = resultado.indexOf('Botão Frame 2');

        expect(idxPrincipal).toBeLessThan(idxFrame1);
        expect(idxFrame1).toBeLessThan(idxFrame2);
    });

    // ── Teste 5: Nome do iframe é extraído corretamente ───────────────────────
    test('Nome do iframe é extraído: name → id → "iframe"', () => {
        // Arrange: Iframe com name
        document.body.innerHTML = `
            <iframe id="my-id" name="my-name" style="width: 800px; height: 600px;"></iframe>
        `;

        let iframe = document.querySelector('iframe');
        let iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão 1</button>
        `;

        // Act
        let resultado = window.AuraDomMapper.capturar();

        // Assert: Usa name
        expect(resultado).toContain('(iframe: my-name)');

        // Arrange: Iframe sem name, com id
        document.body.innerHTML = `
            <iframe id="my-id" style="width: 800px; height: 600px;"></iframe>
        `;

        iframe = document.querySelector('iframe');
        iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão 2</button>
        `;

        // Act
        resultado = window.AuraDomMapper.capturar();

        // Assert: Usa id
        expect(resultado).toContain('(iframe: my-id)');

        // Arrange: Iframe sem name nem id
        document.body.innerHTML = `
            <iframe style="width: 800px; height: 600px;"></iframe>
        `;

        iframe = document.querySelector('iframe');
        iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão 3</button>
        `;

        // Act
        resultado = window.AuraDomMapper.capturar();

        // Assert: Usa fallback "iframe"
        expect(resultado).toContain('(iframe: iframe)');
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Task 4.3: Test global index uniqueness
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 4.3 — Unit Tests: Global index uniqueness', () => {

    beforeEach(() => {
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

    // ── Teste 1: Índices não reiniciam para cada iframe ───────────────────────
    test('Índices não reiniciam para cada iframe', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Botão 1</button>
            <iframe id="frame1" name="frame1" style="width: 800px; height: 600px;"></iframe>
            <iframe id="frame2" name="frame2" style="width: 800px; height: 600px;"></iframe>
        `;

        const frame1 = document.getElementById('frame1');
        const frame1Doc = frame1.contentDocument;
        frame1Doc.body.innerHTML = `
            <button id="btn2" style="width: 100px; height: 30px;">Botão 2</button>
        `;

        const frame2 = document.getElementById('frame2');
        const frame2Doc = frame2.contentDocument;
        frame2Doc.body.innerHTML = `
            <button id="btn3" style="width: 100px; height: 30px;">Botão 3</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Índices são sequenciais
        const btn1 = document.getElementById('btn1');
        const btn2 = frame1Doc.getElementById('btn2');
        const btn3 = frame2Doc.getElementById('btn3');

        const idx1 = parseInt(btn1.getAttribute('data-aura-map'));
        const idx2 = parseInt(btn2.getAttribute('data-aura-map'));
        const idx3 = parseInt(btn3.getAttribute('data-aura-map'));

        expect(idx1).toBe(0);
        expect(idx2).toBe(1); // NÃO reinicia
        expect(idx3).toBe(2); // NÃO reinicia
    });

    // ── Teste 2: data-aura-map são únicos em toda a página ────────────────────
    test('data-aura-map são únicos em toda a página', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Botão 1</button>
            <button id="btn2" style="width: 100px; height: 30px;">Botão 2</button>
            <iframe id="frame1" name="frame1" style="width: 800px; height: 600px;"></iframe>
        `;

        const frame1 = document.getElementById('frame1');
        const frame1Doc = frame1.contentDocument;
        frame1Doc.body.innerHTML = `
            <button id="btn3" style="width: 100px; height: 30px;">Botão 3</button>
            <button id="btn4" style="width: 100px; height: 30px;">Botão 4</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Todos os índices são únicos
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        const btn3 = frame1Doc.getElementById('btn3');
        const btn4 = frame1Doc.getElementById('btn4');

        const indices = [
            parseInt(btn1.getAttribute('data-aura-map')),
            parseInt(btn2.getAttribute('data-aura-map')),
            parseInt(btn3.getAttribute('data-aura-map')),
            parseInt(btn4.getAttribute('data-aura-map'))
        ];

        const uniqueIndices = new Set(indices);
        expect(uniqueIndices.size).toBe(4); // Todos únicos
    });

    // ── Teste 3: Índices incrementam sequencialmente ──────────────────────────
    test('Índices incrementam sequencialmente: main doc → iframe1 → iframe2', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Botão 1</button>
            <button id="btn2" style="width: 100px; height: 30px;">Botão 2</button>
            <iframe id="frame1" name="frame1" style="width: 800px; height: 600px;"></iframe>
            <iframe id="frame2" name="frame2" style="width: 800px; height: 600px;"></iframe>
        `;

        const frame1 = document.getElementById('frame1');
        const frame1Doc = frame1.contentDocument;
        frame1Doc.body.innerHTML = `
            <button id="btn3" style="width: 100px; height: 30px;">Botão 3</button>
        `;

        const frame2 = document.getElementById('frame2');
        const frame2Doc = frame2.contentDocument;
        frame2Doc.body.innerHTML = `
            <button id="btn4" style="width: 100px; height: 30px;">Botão 4</button>
            <button id="btn5" style="width: 100px; height: 30px;">Botão 5</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Sequência 0, 1, 2, 3, 4
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        const btn3 = frame1Doc.getElementById('btn3');
        const btn4 = frame2Doc.getElementById('btn4');
        const btn5 = frame2Doc.getElementById('btn5');

        expect(parseInt(btn1.getAttribute('data-aura-map'))).toBe(0);
        expect(parseInt(btn2.getAttribute('data-aura-map'))).toBe(1);
        expect(parseInt(btn3.getAttribute('data-aura-map'))).toBe(2);
        expect(parseInt(btn4.getAttribute('data-aura-map'))).toBe(3);
        expect(parseInt(btn5.getAttribute('data-aura-map'))).toBe(4);
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Task 4.4: Test output format with iframe indicator
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 4.4 — Unit Tests: Output format with iframe indicator', () => {

    beforeEach(() => {
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

    // ── Teste 1: Elementos do documento principal NÃO têm indicador ───────────
    test('Elementos do documento principal NÃO têm indicador de iframe', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Principal');
        expect(resultado).toMatch(/\[ID: \d+\] TIPO: button \| TEXTO: "Botão Principal"$/m);
        expect(resultado).not.toContain('(iframe:');
    });

    // ── Teste 2: Elementos de iframe TÊM indicador ────────────────────────────
    test('Elementos de iframe TÊM indicador (iframe: ${name})', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert
        expect(resultado).toContain('Botão Iframe');
        expect(resultado).toMatch(/\[ID: \d+\] TIPO: button \| TEXTO: "Botão Iframe" \(iframe: test-frame\)/);
    });

    // ── Teste 3: Fallback de nome do iframe funciona ──────────────────────────
    test('Fallback de nome do iframe: name → id → "iframe"', () => {
        // Test 1: Com name
        document.body.innerHTML = `
            <iframe id="my-id" name="my-name" style="width: 800px; height: 600px;"></iframe>
        `;

        let iframe = document.querySelector('iframe');
        let iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `<button style="width: 100px; height: 30px;">Btn</button>`;

        let resultado = window.AuraDomMapper.capturar();
        expect(resultado).toContain('(iframe: my-name)');

        // Test 2: Sem name, com id
        document.body.innerHTML = `
            <iframe id="my-id" style="width: 800px; height: 600px;"></iframe>
        `;

        iframe = document.querySelector('iframe');
        iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `<button style="width: 100px; height: 30px;">Btn</button>`;

        resultado = window.AuraDomMapper.capturar();
        expect(resultado).toContain('(iframe: my-id)');

        // Test 3: Sem name nem id
        document.body.innerHTML = `
            <iframe style="width: 800px; height: 600px;"></iframe>
        `;

        iframe = document.querySelector('iframe');
        iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `<button style="width: 100px; height: 30px;">Btn</button>`;

        resultado = window.AuraDomMapper.capturar();
        expect(resultado).toContain('(iframe: iframe)');
    });

    // ── Teste 4: Formato completo da linha de saída ───────────────────────────
    test('Formato completo da linha de saída está correto', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Formato exato
        const linhas = resultado.split('\n');
        
        // Header
        expect(linhas[0]).toBe('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
        
        // Elemento principal (sem indicador)
        expect(linhas[1]).toMatch(/^\[ID: 0\] TIPO: button \| TEXTO: "Botão Principal"$/);
        
        // Elemento iframe (com indicador)
        expect(linhas[2]).toMatch(/^\[ID: 1\] TIPO: button \| TEXTO: "Botão Iframe" \(iframe: test-frame\)$/);
    });

});

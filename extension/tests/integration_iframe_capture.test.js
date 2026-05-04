// Feature: aura-iframe-dom-capture-fix
// Integration Tests — Task 5
//
// Testes de integração para validar o fluxo completo de captura de elementos
// em iframes e integração com outros módulos da AURA

const fs = require('fs');
const path = require('path');

// Carrega os módulos necessários
const auraDomMapperCode = fs.readFileSync(
    path.join(__dirname, '../modules/aura_dom_mapper.js'),
    'utf-8'
);

// ─────────────────────────────────────────────────────────────────────────────
// Task 5.1: Test complete capture flow with iframes
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 5.1 — Integration Tests: Complete capture flow with iframes', () => {

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

    // ── Teste 1: Fluxo completo com documento principal + iframe ──────────────
    test('Fluxo completo: captura documento principal + iframe', () => {
        // Arrange: Página complexa com múltiplos elementos
        document.body.innerHTML = `
            <header>
                <button style="width: 80px; height: 30px;">Menu</button>
                <input type="text" value="Buscar" style="width: 200px; height: 30px;" />
            </header>
            <main>
                <button style="width: 100px; height: 35px;">Novo</button>
                <iframe id="content-frame" name="content-frame" style="width: 1000px; height: 700px;"></iframe>
            </main>
        `;

        const iframe = document.getElementById('content-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <div class="toolbar">
                <button style="width: 120px; height: 40px;">Salvar</button>
                <button style="width: 120px; height: 40px;">Cancelar</button>
            </div>
            <form>
                <input type="text" placeholder="Nome" style="width: 300px; height: 35px;" />
                <input type="email" placeholder="Email" style="width: 300px; height: 35px;" />
            </form>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Todos os elementos capturados
        expect(resultado).toContain('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
        
        // Documento principal
        expect(resultado).toContain('Menu');
        expect(resultado).toContain('Buscar');
        expect(resultado).toContain('Novo');
        
        // Iframe
        expect(resultado).toContain('Salvar');
        expect(resultado).toContain('Cancelar');
        expect(resultado).toContain('Nome');
        expect(resultado).toContain('Email');
        
        // Indicadores de iframe
        expect(resultado).toContain('(iframe: content-frame)');
        
        // Verifica que elementos principais NÃO têm indicador
        const linhas = resultado.split('\n');
        const linhaMenu = linhas.find(l => l.includes('Menu'));
        expect(linhaMenu).not.toContain('(iframe:');
    });

    // ── Teste 2: Formato correto para todos os elementos ──────────────────────
    test('Formato correto para todos os elementos', () => {
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
        
        expect(linhas[0]).toBe('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
        expect(linhas[1]).toMatch(/^\[ID: \d+\] TIPO: button \| TEXTO: "Botão Principal"$/);
        expect(linhas[2]).toMatch(/^\[ID: \d+\] TIPO: button \| TEXTO: "Botão Iframe" \(iframe: test-frame\)$/);
    });

    // ── Teste 3: Índices globalmente únicos ───────────────────────────────────
    test('Índices são globalmente únicos em toda a página', () => {
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

        // Assert: Todos os índices únicos
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        const btn3 = frame1Doc.getElementById('btn3');
        const btn4 = frame2Doc.getElementById('btn4');
        const btn5 = frame2Doc.getElementById('btn5');

        const indices = [
            parseInt(btn1.getAttribute('data-aura-map')),
            parseInt(btn2.getAttribute('data-aura-map')),
            parseInt(btn3.getAttribute('data-aura-map')),
            parseInt(btn4.getAttribute('data-aura-map')),
            parseInt(btn5.getAttribute('data-aura-map'))
        ];

        const uniqueIndices = new Set(indices);
        expect(uniqueIndices.size).toBe(5);
        expect(indices).toEqual([0, 1, 2, 3, 4]); // Sequencial
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Task 5.2: Test AuraSpotlight integration (Conceptual)
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 5.2 — Integration Tests: AuraSpotlight integration (Conceptual)', () => {

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

    // ── Teste 1: Elementos de iframe recebem data-aura-map ────────────────────
    test('Elementos de iframe recebem data-aura-map para uso com AuraSpotlight', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="iframe-btn" style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Elemento de iframe tem data-aura-map
        const iframeBtn = iframeDoc.getElementById('iframe-btn');
        expect(iframeBtn.hasAttribute('data-aura-map')).toBe(true);
        
        const auraMapId = iframeBtn.getAttribute('data-aura-map');
        expect(auraMapId).toBeTruthy();
        expect(parseInt(auraMapId)).toBeGreaterThanOrEqual(0);
    });

    // ── Teste 2: IDs de elementos de iframe podem ser usados para referência ──
    test('IDs de elementos de iframe podem ser usados para referência', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="main-btn" style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="iframe-btn" style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();
        
        // Extract ID from output
        const match = resultado.match(/\[ID: (\d+)\] TIPO: button \| TEXTO: "Botão Iframe"/);
        expect(match).toBeTruthy();
        
        const capturedId = parseInt(match[1]);
        
        // Assert: ID capturado corresponde ao data-aura-map
        const iframeBtn = iframeDoc.getElementById('iframe-btn');
        const auraMapId = parseInt(iframeBtn.getAttribute('data-aura-map'));
        
        expect(capturedId).toBe(auraMapId);
    });

    // ── Teste 3: Elementos de iframe podem ser localizados via data-aura-map ──
    test('Elementos de iframe podem ser localizados via data-aura-map', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="test-frame" name="test-frame" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('test-frame');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="iframe-btn" style="width: 100px; height: 30px;">Botão Iframe</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Elemento pode ser localizado via seletor
        const iframeBtn = iframeDoc.getElementById('iframe-btn');
        const auraMapId = iframeBtn.getAttribute('data-aura-map');
        
        // Simula busca do AuraSpotlight
        const foundElement = iframeDoc.querySelector(`[data-aura-map="${auraMapId}"]`);
        expect(foundElement).toBe(iframeBtn);
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Task 5.3: Test Senior X GED scenario (Conceptual/Manual)
// ─────────────────────────────────────────────────────────────────────────────

describe('Task 5.3 — Integration Tests: Senior X GED scenario (Conceptual)', () => {

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

    // ── Teste 1: Simula estrutura do Senior X com GED ─────────────────────────
    test('Simula estrutura do Senior X com iframe GED (ecm_sign)', () => {
        // Arrange: Estrutura típica do Senior X
        document.body.innerHTML = `
            <div id="header" style="width: 100%; height: 60px;">
                <button style="width: 80px; height: 30px;">Menu</button>
                <button style="width: 100px; height: 30px;">Notificações</button>
            </div>
            <div id="sidebar" style="width: 200px; height: 700px;">
                <button style="width: 180px; height: 35px;">Novidades e atualizações</button>
                <button style="width: 180px; height: 35px;">Gestão</button>
            </div>
            <div id="main-content">
                <iframe id="ecm_sign" name="ecm_sign" style="width: 1200px; height: 800px;"></iframe>
            </div>
        `;

        const iframe = document.getElementById('ecm_sign');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <div id="ged-toolbar">
                <button style="width: 150px; height: 40px;">Novo Documento</button>
                <button style="width: 100px; height: 40px;">Filtros</button>
                <input type="text" placeholder="Buscar documentos" style="width: 300px; height: 35px;" />
            </div>
            <div id="ged-content">
                <button style="width: 80px; height: 30px;">Abrir</button>
                <button style="width: 80px; height: 30px;">Editar</button>
            </div>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Elementos do GED são capturados
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('Filtros');
        expect(resultado).toContain('Buscar documentos');
        expect(resultado).toContain('Abrir');
        expect(resultado).toContain('Editar');
        
        // Indicador de iframe ecm_sign
        expect(resultado).toContain('(iframe: ecm_sign)');
        
        // Elementos do documento principal também capturados
        expect(resultado).toContain('Menu');
        expect(resultado).toContain('Novidades e atualizações');
    });

    // ── Teste 2: Verifica que AURA pode identificar localização no GED ────────
    test('AURA pode identificar localização dentro do GED', () => {
        // Arrange: Simula cenário onde usuário está no GED
        document.body.innerHTML = `
            <div id="header">
                <button style="width: 80px; height: 30px;">Menu</button>
            </div>
            <iframe id="ecm_sign" name="ecm_sign" style="width: 1200px; height: 800px;"></iframe>
        `;

        const iframe = document.getElementById('ecm_sign');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <h1>Gestão Eletrônica de Documentos</h1>
            <button style="width: 150px; height: 40px;">Novo Documento</button>
        `;

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: DOM context inclui elementos do GED
        // Isso permite que a IA identifique corretamente a localização
        expect(resultado).toContain('Gestão Eletrônica de Documentos');
        expect(resultado).toContain('Novo Documento');
        expect(resultado).toContain('(iframe: ecm_sign)');
        
        // Simula análise da IA: se "Gestão Eletrônica de Documentos" está presente
        // com indicador (iframe: ecm_sign), a IA pode concluir que o usuário
        // está dentro do módulo GED
        const contemGED = resultado.includes('Gestão Eletrônica de Documentos') &&
                         resultado.includes('(iframe: ecm_sign)');
        expect(contemGED).toBe(true);
    });

    // ── Teste 3: Múltiplos elementos do GED são capturados ────────────────────
    test('Múltiplos elementos do GED são capturados com índices únicos', () => {
        // Arrange
        document.body.innerHTML = `
            <iframe id="ecm_sign" name="ecm_sign" style="width: 1200px; height: 800px;"></iframe>
        `;

        const iframe = document.getElementById('ecm_sign');
        const iframeDoc = iframe.contentDocument;
        iframeDoc.body.innerHTML = `
            <button id="btn1" style="width: 150px; height: 40px;">Novo Documento</button>
            <button id="btn2" style="width: 100px; height: 40px;">Filtros</button>
            <input id="input1" type="text" placeholder="Buscar" style="width: 300px; height: 35px;" />
            <button id="btn3" style="width: 80px; height: 30px;">Ajuda</button>
        `;

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Todos os elementos têm data-aura-map único
        const btn1 = iframeDoc.getElementById('btn1');
        const btn2 = iframeDoc.getElementById('btn2');
        const input1 = iframeDoc.getElementById('input1');
        const btn3 = iframeDoc.getElementById('btn3');

        expect(btn1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn2.hasAttribute('data-aura-map')).toBe(true);
        expect(input1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn3.hasAttribute('data-aura-map')).toBe(true);

        const indices = [
            parseInt(btn1.getAttribute('data-aura-map')),
            parseInt(btn2.getAttribute('data-aura-map')),
            parseInt(input1.getAttribute('data-aura-map')),
            parseInt(btn3.getAttribute('data-aura-map'))
        ];

        const uniqueIndices = new Set(indices);
        expect(uniqueIndices.size).toBe(4); // Todos únicos
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Manual Testing Instructions
// ─────────────────────────────────────────────────────────────────────────────

/*
MANUAL TESTING INSTRUCTIONS FOR SENIOR X GED:

1. Navigate to Senior X application
2. Open the GED module (Gestão Eletrônica de Documentos)
3. Open browser console
4. Execute: window.AuraDomMapper.capturar()
5. Verify output includes:
   - Elements from main document (header, sidebar)
   - Elements from GED iframe (buttons, inputs)
   - Indicator "(iframe: ecm_sign)" for GED elements
   - Globally unique IDs across all elements

6. Test AURA question: "onde estou?"
   - Expected: AURA should identify location as GED module
   - Previous behavior: AURA identified location as "Novidades e atualizações" (incorrect)

7. Test AURA interaction: "clique no botão Novo Documento"
   - Expected: AURA should highlight the button inside the GED iframe
   - Verify that AuraSpotlight.aplicar() works with iframe elements

8. Test with multiple iframes:
   - Open page with multiple iframes (if available)
   - Verify all accessible iframes are processed
   - Verify cross-origin iframes don't cause errors

9. Performance test:
   - Measure execution time of capturar() on complex pages
   - Verify no significant performance degradation

10. Edge cases:
    - Empty iframes
    - Nested iframes (if supported)
    - Dynamically added iframes
    - Iframes with many elements (100+)
*/

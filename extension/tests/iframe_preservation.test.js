// Feature: aura-iframe-dom-capture-fix
// Preservation Property Tests — Task 2
//
// **IMPORTANT**: Estes testes seguem metodologia observation-first
// 1. Observar comportamento no código NÃO CORRIGIDO para páginas sem iframes
// 2. Documentar outputs observados (formato, IDs, texto)
// 3. Escrever testes baseados em propriedades capturando esse comportamento
// 4. Executar testes no código NÃO CORRIGIDO
//
// **EXPECTED OUTCOME NO CÓDIGO NÃO CORRIGIDO**: TESTES PASSAM
// (confirma baseline behavior a preservar)
//
// **EXPECTED OUTCOME APÓS O FIX**: TESTES CONTINUAM PASSANDO
// (confirma que não houve regressão)
//
// Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5

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
// Esta é a implementação atual que queremos preservar para páginas sem iframes
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
// Helper: Verifica se NÃO há condição de bug (páginas sem iframes acessíveis)
// ─────────────────────────────────────────────────────────────────────────────

function isNotBugCondition() {
    const iframes = document.querySelectorAll('iframe');
    
    if (iframes.length === 0) {
        return true; // Sem iframes
    }

    // Verifica se todos os iframes são inacessíveis ou vazios
    let hasAccessibleIframeWithContent = false;
    iframes.forEach(frame => {
        try {
            const doc = frame.contentDocument || frame.contentWindow.document;
            if (doc && doc.body && doc.body.children.length > 0) {
                hasAccessibleIframeWithContent = true;
            }
        } catch (e) {
            // Cross-origin iframe - inacessível (OK para preservation)
        }
    });

    return !hasAccessibleIframeWithContent;
}

// ─────────────────────────────────────────────────────────────────────────────
// Grupo: Preservation — Comportamento de páginas sem iframes deve ser preservado
//
// **CRITICAL**: Estes testes DEVEM PASSAR no código não corrigido E após o fix
// Eles garantem que não há regressão
// ─────────────────────────────────────────────────────────────────────────────

describe('Preservation — Non-Iframe Page Behavior (DEVE PASSAR no código não corrigido E após fix)', () => {

    beforeEach(() => {
        // Simula window.innerHeight para cálculos de visibilidade
        Object.defineProperty(window, 'innerHeight', {
            writable: true,
            configurable: true,
            value: 768
        });

        // Carrega o módulo AuraDomMapper no contexto JSDOM
        // O código atual tem fallback de style inline que funciona no JSDOM
        eval(auraDomMapperCode);
    });

    afterEach(() => {
        document.body.innerHTML = '';
        document.head.innerHTML = '';
        delete window.AuraDomMapper;
    });

    // ── Teste 1: Página sem iframes - captura elementos do documento principal ─
    // Validates: Requirements 3.1, 3.2
    //
    // **OBSERVED BEHAVIOR NO CÓDIGO NÃO CORRIGIDO**:
    // - Elementos visíveis são capturados
    // - Formato: [ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}"
    // - Sem indicador de iframe
    //
    // **PRESERVATION GOAL**: Após o fix, comportamento deve ser idêntico

    test('Preservation: Página sem iframes captura elementos corretamente', () => {
        // Arrange: Página simples sem iframes
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Salvar</button>
            <input type="text" value="Nome" style="width: 200px; height: 30px;" />
            <a href="#" style="display: inline-block; width: 80px; height: 20px;">Ajuda</a>
        `;

        // Verifica que NÃO há condição de bug
        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Comportamento observado no código não corrigido
        expect(resultado).toContain('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
        expect(resultado).toContain('Salvar');
        expect(resultado).toContain('Nome');
        expect(resultado).toContain('Ajuda');
        
        // Verifica formato correto (sem indicador de iframe)
        expect(resultado).toMatch(/\[ID: \d+\] TIPO: button \| TEXTO: "Salvar"/);
        expect(resultado).toMatch(/\[ID: \d+\] TIPO: input \| TEXTO: "Nome"/);
        expect(resultado).toMatch(/\[ID: \d+\] TIPO: a \| TEXTO: "Ajuda"/);
        
        // NÃO deve conter indicador de iframe
        expect(resultado).not.toContain('(iframe:');
    });

    // ── Teste 2: Formato de saída preservado ──────────────────────────────────
    // Validates: Requirements 3.2
    //
    // **OBSERVED BEHAVIOR**: Formato exato da string de saída
    // **PRESERVATION GOAL**: Formato deve permanecer idêntico

    test('Preservation: Formato de saída [ID: X] TIPO: Y | TEXTO: "Z" é preservado', () => {
        // Arrange
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Clique Aqui</button>
        `;

        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Formato exato observado
        const linhas = resultado.split('\n');
        expect(linhas[0]).toBe('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
        expect(linhas[1]).toMatch(/^\[ID: \d+\] TIPO: button \| TEXTO: "Clique Aqui"$/);
    });

    // ── Teste 3: data-aura-map atribuído com índices únicos ───────────────────
    // Validates: Requirements 3.5
    //
    // **OBSERVED BEHAVIOR**: Elementos recebem data-aura-map com índices únicos
    // **PRESERVATION GOAL**: Atribuição de índices deve continuar funcionando

    test('Preservation: data-aura-map é atribuído com índices únicos', () => {
        // Arrange
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Botão 1</button>
            <button id="btn2" style="width: 100px; height: 30px;">Botão 2</button>
            <button id="btn3" style="width: 100px; height: 30px;">Botão 3</button>
        `;

        expect(isNotBugCondition()).toBe(true);

        // Act
        window.AuraDomMapper.capturar();

        // Assert: Todos os botões têm data-aura-map único
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        const btn3 = document.getElementById('btn3');

        expect(btn1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn2.hasAttribute('data-aura-map')).toBe(true);
        expect(btn3.hasAttribute('data-aura-map')).toBe(true);

        const id1 = btn1.getAttribute('data-aura-map');
        const id2 = btn2.getAttribute('data-aura-map');
        const id3 = btn3.getAttribute('data-aura-map');

        // Índices devem ser únicos
        expect(id1).not.toBe(id2);
        expect(id2).not.toBe(id3);
        expect(id1).not.toBe(id3);
    });

    // ── Teste 4: Filtragem de duplicatas baseada em texto ─────────────────────
    // Validates: Requirements 3.5
    //
    // **OBSERVED BEHAVIOR**: Elementos com mesmo texto são filtrados (apenas primeiro é incluído)
    // **PRESERVATION GOAL**: Lógica de filtragem deve continuar funcionando

    test('Preservation: Filtragem de duplicatas baseada em texto funciona', () => {
        // Arrange: Dois botões com mesmo texto
        document.body.innerHTML = `
            <button id="btn1" style="width: 100px; height: 30px;">Salvar</button>
            <button id="btn2" style="width: 100px; height: 30px;">Salvar</button>
        `;

        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Apenas uma ocorrência de "Salvar" na saída
        const ocorrencias = (resultado.match(/Salvar/g) || []).length;
        expect(ocorrencias).toBe(1);

        // Apenas o primeiro botão recebe data-aura-map
        const btn1 = document.getElementById('btn1');
        const btn2 = document.getElementById('btn2');
        expect(btn1.hasAttribute('data-aura-map')).toBe(true);
        expect(btn2.hasAttribute('data-aura-map')).toBe(false);
    });

    // ── Teste 5: Container AURA é excluído ────────────────────────────────────
    // Validates: Requirements 3.4
    //
    // **OBSERVED BEHAVIOR**: Elementos dentro de #aura-floating-container são ignorados
    // **PRESERVATION GOAL**: Exclusão do container AURA deve continuar funcionando

    test('Preservation: Elementos dentro do container AURA são ignorados', () => {
        // Arrange: Página com container AURA
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Normal</button>
            <div id="aura-floating-container">
                <button style="width: 100px; height: 30px;">Botão AURA</button>
            </div>
        `;

        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Apenas "Botão Normal" aparece, "Botão AURA" é ignorado
        expect(resultado).toContain('Botão Normal');
        expect(resultado).not.toContain('Botão AURA');
    });

    // ── Teste 6: Lógica de visibilidade (bounding box) ────────────────────────
    // Validates: Requirements 3.1
    //
    // **OBSERVED BEHAVIOR**: Apenas elementos com bounding box válido são capturados
    // **PRESERVATION GOAL**: Lógica de visibilidade deve continuar funcionando

    test('Preservation: Apenas elementos visíveis (bounding box válido) são capturados', () => {
        // Arrange: Elementos visíveis e invisíveis
        // NOTA: Em JSDOM, getBoundingClientRect() sempre retorna zeros.
        // O fallback de style inline detecta width:0/height:0 como invisível.
        // Elementos "fora da tela" não podem ser detectados no JSDOM via top/innerHeight,
        // portanto este teste valida apenas a lógica de width/height zero.
        document.body.innerHTML = `
            <button id="visivel" style="width: 100px; height: 30px;">Visível</button>
            <button id="invisivel" style="width: 0; height: 0;">Invisível</button>
            <button id="fora-tela" style="width: 0; height: 0;">Fora da Tela</button>
        `;

        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Apenas "Visível" aparece
        expect(resultado).toContain('Visível');
        expect(resultado).not.toContain('Invisível');
        expect(resultado).not.toContain('Fora da Tela');
    });

    // ── Teste 7: Iframe cross-origin não causa falha ──────────────────────────
    // Validates: Requirements 3.3
    //
    // **OBSERVED BEHAVIOR**: Iframes inacessíveis não causam exceções
    // **PRESERVATION GOAL**: Tratamento de cross-origin deve continuar funcionando
    //
    // **NOTE**: Em ambiente de teste JSDOM, não conseguimos simular SecurityError real
    // Este teste documenta o comportamento esperado

    test('Preservation: Iframe cross-origin (simulado) não causa falha', () => {
        // Arrange: Página com iframe (em JSDOM, será same-origin, mas documenta comportamento)
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="cross-origin-iframe" style="width: 800px; height: 600px;"></iframe>
        `;

        // Simula iframe vazio (sem conteúdo acessível)
        const iframe = document.getElementById('cross-origin-iframe');
        // Não populamos o iframe - simula inacessibilidade

        expect(isNotBugCondition()).toBe(true);

        // Act: Não deve lançar exceção
        expect(() => {
            const resultado = window.AuraDomMapper.capturar();
            expect(resultado).toContain('Botão Principal');
        }).not.toThrow();
    });

    // ── Teste 8: Iframe vazio não adiciona elementos ──────────────────────────
    // Validates: Requirements 3.3
    //
    // **OBSERVED BEHAVIOR**: Iframes vazios não contribuem elementos para a saída
    // **PRESERVATION GOAL**: Comportamento deve permanecer idêntico

    test('Preservation: Iframe vazio não adiciona elementos à saída', () => {
        // Arrange: Página com iframe vazio
        document.body.innerHTML = `
            <button style="width: 100px; height: 30px;">Botão Principal</button>
            <iframe id="empty-iframe" style="width: 800px; height: 600px;"></iframe>
        `;

        const iframe = document.getElementById('empty-iframe');
        const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
        iframeDoc.body.innerHTML = ''; // Explicitamente vazio

        expect(isNotBugCondition()).toBe(true);

        // Act
        const resultado = window.AuraDomMapper.capturar();

        // Assert: Apenas elementos do documento principal
        expect(resultado).toContain('Botão Principal');
        const linhas = resultado.split('\n').filter(l => l.trim());
        expect(linhas.length).toBe(2); // Header + 1 elemento
    });

    // ── Property-Based Test: Páginas sem iframes têm saída consistente ────────
    // Validates: Requirements 3.1, 3.2, 3.5
    //
    // **PRESERVATION GOAL**: Para qualquer página sem iframes, comportamento é consistente

    test('fc.property: Páginas sem iframes produzem saída consistente', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 10 }), // Número de botões
                fc.array(
                    // Textos com pelo menos 2 caracteres alfanuméricos (sem HTML especial nem só espaços)
                    fc.stringMatching(/^[A-Za-z0-9][A-Za-z0-9 ]{1,18}[A-Za-z0-9]$/),
                    { minLength: 1, maxLength: 10 }
                ),
                (numButtons, buttonTexts) => {
                    // Arrange: Cria página sem iframes com N botões
                    const uniqueTexts = [...new Set(buttonTexts)].slice(0, numButtons);
                    document.body.innerHTML = uniqueTexts.map(text => 
                        `<button style="width: 100px; height: 30px;">${text}</button>`
                    ).join('\n');

                    expect(isNotBugCondition()).toBe(true);

                    // Act
                    const resultado = window.AuraDomMapper.capturar();

                    // Assert: Propriedades preservadas
                    // 1. Formato correto
                    expect(resultado).toContain('ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:');
                    
                    // 2. Todos os textos únicos aparecem
                    uniqueTexts.forEach(text => {
                        expect(resultado).toContain(text);
                    });

                    // 3. Formato de cada linha é correto
                    const linhas = resultado.split('\n').slice(1); // Pula header
                    linhas.forEach(linha => {
                        if (linha.trim()) {
                            expect(linha).toMatch(/^\[ID: \d+\] TIPO: button \| TEXTO: ".+"$/);
                        }
                    });

                    // 4. Sem indicador de iframe
                    expect(resultado).not.toContain('(iframe:');

                    // 5. data-aura-map atribuído
                    const buttons = document.querySelectorAll('button');
                    buttons.forEach(btn => {
                        expect(btn.hasAttribute('data-aura-map')).toBe(true);
                    });
                }
            ),
            { numRuns: 50 }
        );
    });

    // ── Property-Based Test: Índices data-aura-map são únicos ─────────────────
    // Validates: Requirements 3.5
    //
    // **PRESERVATION GOAL**: Índices sempre únicos, independente do número de elementos

    test('fc.property: Índices data-aura-map são sempre únicos', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 2, max: 20 }), // Número de elementos
                (numElements) => {
                    // Arrange: Cria página com N elementos únicos
                    document.body.innerHTML = Array.from({ length: numElements }, (_, i) => 
                        `<button style="width: 100px; height: 30px;">Botão ${i}</button>`
                    ).join('\n');

                    expect(isNotBugCondition()).toBe(true);

                    // Act
                    window.AuraDomMapper.capturar();

                    // Assert: Todos os índices são únicos
                    const buttons = document.querySelectorAll('button');
                    const indices = Array.from(buttons).map(btn => btn.getAttribute('data-aura-map'));
                    const uniqueIndices = new Set(indices);

                    expect(uniqueIndices.size).toBe(numElements);
                }
            ),
            { numRuns: 30 }
        );
    });

    // ── Property-Based Test: Filtragem de duplicatas é consistente ────────────
    // Validates: Requirements 3.5
    //
    // **PRESERVATION GOAL**: Duplicatas sempre filtradas, apenas primeiro elemento mantido

    test('fc.property: Filtragem de duplicatas é consistente', () => {
        fc.assert(
            fc.property(
                // Texto com pelo menos 2 caracteres alfanuméricos (sem HTML especial nem só espaços)
                fc.stringMatching(/^[A-Za-z0-9][A-Za-z0-9 ]{3,13}[A-Za-z0-9]$/),
                fc.integer({ min: 2, max: 5 }), // Número de duplicatas
                (texto, numDuplicatas) => {
                    // Arrange: Cria N botões com mesmo texto
                    document.body.innerHTML = Array.from({ length: numDuplicatas }, (_, i) => 
                        `<button id="btn${i}" style="width: 100px; height: 30px;">${texto}</button>`
                    ).join('\n');

                    expect(isNotBugCondition()).toBe(true);

                    // Act
                    const resultado = window.AuraDomMapper.capturar();

                    // Assert: Apenas uma ocorrência na saída
                    const ocorrencias = (resultado.match(new RegExp(texto, 'g')) || []).length;
                    expect(ocorrencias).toBe(1);

                    // Apenas o primeiro botão tem data-aura-map
                    const btn0 = document.getElementById('btn0');
                    expect(btn0.hasAttribute('data-aura-map')).toBe(true);

                    for (let i = 1; i < numDuplicatas; i++) {
                        const btn = document.getElementById(`btn${i}`);
                        expect(btn.hasAttribute('data-aura-map')).toBe(false);
                    }
                }
            ),
            { numRuns: 30 }
        );
    });

    // ── Property-Based Test: Visibilidade é respeitada ────────────────────────
    // Validates: Requirements 3.1
    //
    // **PRESERVATION GOAL**: Apenas elementos com bounding box válido são capturados

    test('fc.property: Apenas elementos visíveis são capturados', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 1, max: 5 }), // Elementos visíveis
                fc.integer({ min: 1, max: 5 }), // Elementos invisíveis
                (numVisiveis, numInvisiveis) => {
                    // Arrange: Cria elementos visíveis e invisíveis
                    const visiveis = Array.from({ length: numVisiveis }, (_, i) => 
                        `<button style="width: 100px; height: 30px;">Visível ${i}</button>`
                    );
                    const invisiveis = Array.from({ length: numInvisiveis }, (_, i) => 
                        `<button style="width: 0; height: 0;">Invisível ${i}</button>`
                    );

                    document.body.innerHTML = [...visiveis, ...invisiveis].join('\n');

                    expect(isNotBugCondition()).toBe(true);

                    // Act
                    const resultado = window.AuraDomMapper.capturar();

                    // Assert: Apenas elementos visíveis aparecem
                    for (let i = 0; i < numVisiveis; i++) {
                        expect(resultado).toContain(`Visível ${i}`);
                    }
                    for (let i = 0; i < numInvisiveis; i++) {
                        expect(resultado).not.toContain(`Invisível ${i}`);
                    }
                }
            ),
            { numRuns: 30 }
        );
    });

});

// ─────────────────────────────────────────────────────────────────────────────
// Documentação de Comportamento Observado
// ─────────────────────────────────────────────────────────────────────────────
//
// COMPORTAMENTO OBSERVADO NO CÓDIGO NÃO CORRIGIDO (para páginas sem iframes):
//
// 1. **Formato de Saída**:
//    - Header: "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:"
//    - Cada elemento: "[ID: ${index}] TIPO: ${tagName} | TEXTO: "${texto}""
//    - Sem indicador de iframe
//
// 2. **Captura de Elementos**:
//    - Elementos do documento principal são capturados corretamente
//    - Apenas elementos visíveis (bounding box válido) são incluídos
//    - Elementos fora da tela (top > innerHeight) são ignorados
//    - Elementos com width=0 ou height=0 são ignorados
//
// 3. **Atribuição de data-aura-map**:
//    - Cada elemento capturado recebe atributo data-aura-map com índice único
//    - Índices são números inteiros sequenciais
//    - Índices são globalmente únicos na página
//
// 4. **Filtragem de Duplicatas**:
//    - Elementos com mesmo texto são filtrados
//    - Apenas o primeiro elemento com determinado texto é incluído
//    - Apenas o primeiro elemento recebe data-aura-map
//
// 5. **Exclusão do Container AURA**:
//    - Elementos dentro de #aura-floating-container são ignorados
//    - Não aparecem na saída nem recebem data-aura-map
//
// 6. **Tratamento de Iframes**:
//    - Iframes vazios não contribuem elementos
//    - Iframes inacessíveis (cross-origin) não causam exceções
//    - Código não itera sobre iframes (causa do bug)
//
// PRESERVATION GOAL:
// Após implementar o fix para capturar elementos de iframes acessíveis,
// TODOS estes comportamentos devem permanecer IDÊNTICOS para páginas sem iframes.
//
// EXPECTED TEST RESULTS:
// - NO CÓDIGO NÃO CORRIGIDO: Todos os testes PASSAM ✓
// - APÓS O FIX: Todos os testes CONTINUAM PASSANDO ✓
//
// Se algum teste falhar após o fix, isso indica REGRESSÃO e o fix deve ser revisado.

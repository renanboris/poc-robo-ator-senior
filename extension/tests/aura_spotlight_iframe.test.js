// Feature: aura-dap-restructure
// Example test — Task 15.2: Spotlight dentro de iframe
//
// Verifica que AuraSpotlight.encontrarElemento busca tanto no document
// principal quanto em iframes same-origin (cenário típico do Senior X).
//
// Validates: Requirement 11.7
// Framework: Jest (jsdom environment)
//
// Estratégia:
//   - Carrega o módulo real extension/modules/aura_spotlight.js no escopo
//     global do jsdom (o IIFE registra window.AuraSpotlight).
//   - Monta um DOM com:
//       * um elemento exclusivo no document principal,
//       * um iframe same-origin cujo contentDocument contém outro
//         elemento com seletor distinto.
//   - Chama AuraSpotlight.encontrarElemento(...) para cada caso e valida
//     o retorno (`{ elemento, frame }` ou null).

const fs = require('fs');
const path = require('path');

function loadAuraSpotlight() {
    const source = fs.readFileSync(
        path.resolve(__dirname, '..', 'modules', 'aura_spotlight.js'),
        'utf8'
    );
    // Indirect eval para executar no escopo global (jsdom: window === globalThis).
    // O IIFE do módulo registra window.AuraSpotlight.
    (0, eval)(source);
}

describe('AuraSpotlight.encontrarElemento — busca em document e em iframes', () => {
    beforeAll(() => {
        loadAuraSpotlight();
    });

    afterAll(() => {
        delete window.AuraSpotlight;
    });

    afterEach(() => {
        document.body.innerHTML = '';
    });

    test('encontra elemento no document principal', () => {
        // Arrange: elemento único no document principal
        document.body.innerHTML = `
            <button id="btn-principal" class="alvo-main">Salvar</button>
        `;

        // Act
        const resultado = window.AuraSpotlight.encontrarElemento('.alvo-main');

        // Assert: retorna { elemento, frame: null } e o elemento é o esperado
        expect(resultado).not.toBeNull();
        expect(resultado.frame).toBeNull();
        expect(resultado.elemento).toBe(document.getElementById('btn-principal'));
    });

    test('encontra elemento dentro de iframe same-origin', () => {
        // Arrange: cria um iframe e injeta um elemento no seu contentDocument
        const iframe = document.createElement('iframe');
        iframe.id = 'frame-senior-x';
        document.body.appendChild(iframe);

        const frameDoc = iframe.contentDocument || iframe.contentWindow.document;
        // Garante que o body do iframe esteja inicializado (jsdom cria
        // automaticamente, mas reforçamos por segurança).
        if (!frameDoc.body) {
            frameDoc.documentElement.appendChild(frameDoc.createElement('body'));
        }
        frameDoc.body.innerHTML = `
            <button id="btn-iframe" class="alvo-iframe">Confirmar</button>
        `;
        const alvoIframe = frameDoc.getElementById('btn-iframe');

        // Sanity: o elemento NÃO existe no document principal
        expect(document.querySelector('.alvo-iframe')).toBeNull();

        // Act
        const resultado = window.AuraSpotlight.encontrarElemento('.alvo-iframe');

        // Assert: retorna { elemento, frame } com o iframe correto
        expect(resultado).not.toBeNull();
        expect(resultado.frame).toBe(iframe);
        expect(resultado.elemento).toBe(alvoIframe);
    });

    test('distingue entre document principal e iframe quando ambos coexistem', () => {
        // Arrange: elemento no document principal + outro distinto dentro do iframe
        document.body.innerHTML = `
            <button id="btn-main" class="alvo-main">Editar</button>
        `;
        const iframe = document.createElement('iframe');
        document.body.appendChild(iframe);

        const frameDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (!frameDoc.body) {
            frameDoc.documentElement.appendChild(frameDoc.createElement('body'));
        }
        frameDoc.body.innerHTML = `
            <a id="link-iframe" class="alvo-iframe" href="#">Detalhes</a>
        `;

        // Act
        const noMain = window.AuraSpotlight.encontrarElemento('.alvo-main');
        const noIframe = window.AuraSpotlight.encontrarElemento('.alvo-iframe');

        // Assert: cada chamada retorna o elemento na sua origem correta
        expect(noMain).not.toBeNull();
        expect(noMain.frame).toBeNull();
        expect(noMain.elemento).toBe(document.getElementById('btn-main'));

        expect(noIframe).not.toBeNull();
        expect(noIframe.frame).toBe(iframe);
        expect(noIframe.elemento).toBe(frameDoc.getElementById('link-iframe'));
    });

    test('retorna null quando o seletor não existe em lugar nenhum', () => {
        // Arrange: nem o document nem o iframe contêm o seletor procurado
        document.body.innerHTML = `
            <button class="presente">Existo</button>
        `;
        const iframe = document.createElement('iframe');
        document.body.appendChild(iframe);

        const frameDoc = iframe.contentDocument || iframe.contentWindow.document;
        if (!frameDoc.body) {
            frameDoc.documentElement.appendChild(frameDoc.createElement('body'));
        }
        frameDoc.body.innerHTML = `
            <span class="tambem-presente">Aqui também</span>
        `;

        // Act
        const resultado = window.AuraSpotlight.encontrarElemento('.nao-existe');

        // Assert: retorna null (não undefined, conforme contrato do módulo)
        expect(resultado).toBeNull();
    });
});

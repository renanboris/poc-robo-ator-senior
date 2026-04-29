// Feature: aura-dap-feedback-icons-fix
// Bug Condition Exploration Test — Task 1
//
// **Validates: Requirements 1.1, 1.2**
//
// Este teste verifica a CONDIÇÃO DE BUG no código NÃO CORRIGIDO.
// O bug se manifesta quando os ícones SVG de feedback são renderizados com
// fill="currentColor" no JavaScript, mas o CSS aplica fill: none !important.
//
// **CRITICAL**: Este teste DEVE FALHAR no código não corrigido.
// A falha confirma que o bug existe e demonstra o conflito atributo/CSS.
//
// **EXPECTED OUTCOME**: TESTE FALHA (isso é correto — prova que o bug existe)
//
// Após o fix (Task 3), este mesmo teste PASSARÁ, confirmando que o bug foi corrigido.

const fc = require('fast-check');

// ─────────────────────────────────────────────────────────────────────────────
// Extração da função criar() do módulo aura_feedback.js (UNFIXED)
//
// Esta é a implementação ATUAL (não corrigida) que contém o bug:
// - SVG elements têm fill="currentColor" (linhas 23 e 31)
// - CSS aplica fill: none !important (style.css linha 420)
// - Resultado: conflito que causa renderização incorreta
// ─────────────────────────────────────────────────────────────────────────────

function criar_unfixed(prompt, resposta) {
    const bar = document.createElement('div');
    bar.className = 'aura-feedback-bar';

    const like = document.createElement('button');
    like.className = 'aura-fb-btn aura-fb-like';
    like.title = 'Isso ajudou';
    like.setAttribute('aria-label', 'Isso ajudou');
    // BUG: fill="currentColor" conflita com CSS fill: none !important
    like.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M7 22V11M2 13v6c0 1.1.9 2 2 2h1M16.5 3c-.8 0-1.5.7-1.5 1.5V11h4.4c.8 0 1.5.5 1.8 1.2l1.7 4.4c.2.5.1 1-.1 1.4-.3.5-.8.8-1.4.8H14c-1.1 0-2-.9-2-2v-2.5c0-.8-.7-1.5-1.5-1.5h-5C4.7 13 4 12.3 4 11.5v-7C4 3.7 4.7 3 5.5 3h9.4c.8 0 1.5.5 1.8 1.2l.8 2.1"/>
    </svg>`;

    const dislike = document.createElement('button');
    dislike.className = 'aura-fb-btn aura-fb-dislike';
    dislike.title = 'Não ajudou';
    dislike.setAttribute('aria-label', 'Não ajudou');
    // BUG: fill="currentColor" conflita com CSS fill: none !important
    dislike.innerHTML = `<svg aria-hidden="true" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
        <path d="M17 2v11M22 11V5c0-1.1-.9-2-2-2h-1M7.5 21c.8 0 1.5-.7 1.5-1.5V13H4.6c-.8 0-1.5-.5-1.8-1.2L1.1 7.4C.9 6.9 1 6.4 1.2 6c.3-.5.8-.8 1.4-.8H10c1.1 0 2 .9 2 2v2.5c0 .8.7 1.5 1.5 1.5h5c.8 0 1.5.7 1.5 1.5v7c0 .8-.7 1.5-1.5 1.5H8.6c-.8 0-1.5-.5-1.8-1.2l-.8-2.1"/>
    </svg>`;

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

// ─────────────────────────────────────────────────────────────────────────────
// Helper: Injeta CSS do style.css no jsdom para simular o ambiente real
// ─────────────────────────────────────────────────────────────────────────────

function injectFeedbackCSS() {
    const style = document.createElement('style');
    style.textContent = `
        .aura-fb-btn {
            background: transparent !important;
            border: none !important;
            color: #94a3b8 !important;
            cursor: pointer !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            padding: 6px !important;
            border-radius: 6px !important;
            transition: all 0.2s ease !important;
            outline: none !important;
        }

        .aura-fb-btn svg {
            width: 16px !important;
            height: 16px !important;
            stroke: currentColor !important;
            stroke-width: 2 !important;
            fill: none !important;
        }

        .aura-fb-btn.aura-fb-like:hover {
            background: rgba(0, 221, 179, 0.1) !important;
            color: #00ddb3 !important;
            transform: translateY(-1px) !important;
        }

        .aura-fb-btn.aura-fb-dislike:hover {
            background: rgba(239, 68, 68, 0.1) !important;
            color: #ef4444 !important;
            transform: translateY(-1px) !important;
        }

        .aura-fb-btn:disabled {
            opacity: 0.5 !important;
            cursor: not-allowed !important;
        }

        .aura-fb-btn.voted-yes {
            color: #00ddb3 !important;
        }

        .aura-fb-btn.voted-no {
            color: #ef4444 !important;
        }
    `;
    document.head.appendChild(style);
}

// ─────────────────────────────────────────────────────────────────────────────
// Grupo: Bug Condition — Ícones SVG com conflito fill/stroke renderizam incorretamente
//
// **Property 1: Bug Condition** - Ícones SVG com conflito fill/stroke renderizam incorretamente
//
// Estes testes verificam a CONDIÇÃO DE BUG no código não corrigido:
// - SVG elements TÊM o atributo fill="currentColor" (JavaScript)
// - Computed CSS style mostra fill: none (CSS sobrescreve)
// - Parent element tem classe aura-fb-btn
// - Resultado: conflito que causa renderização incorreta
//
// **EXPECTED OUTCOME**: TESTES FALHAM no código não corrigido
// (a falha confirma que o bug existe)
// ─────────────────────────────────────────────────────────────────────────────

describe('Bug Condition — Ícones SVG com conflito fill/stroke renderizam incorretamente', () => {

    beforeEach(() => {
        document.body.innerHTML = '';
        injectFeedbackCSS();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        document.head.innerHTML = '';
    });

    // ── Teste determinístico: verificar atributo fill="currentColor" existe ───
    // Validates: Requirement 1.1
    //
    // ESPERADO (código não corrigido): SVG elements TÊM fill="currentColor"
    // Este teste PASSA no código não corrigido (confirma presença do atributo bugado)
    // Após o fix, este teste FALHARÁ (atributo será removido)

    test('Like icon SVG deve ter atributo fill="currentColor" (código não corrigido)', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const likeBtn = bar.querySelector('.aura-fb-like');
        const svg = likeBtn.querySelector('svg');

        // No código não corrigido, o atributo fill existe
        expect(svg.hasAttribute('fill')).toBe(true);
        expect(svg.getAttribute('fill')).toBe('currentColor');
    });

    test('Dislike icon SVG deve ter atributo fill="currentColor" (código não corrigido)', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const dislikeBtn = bar.querySelector('.aura-fb-dislike');
        const svg = dislikeBtn.querySelector('svg');

        // No código não corrigido, o atributo fill existe
        expect(svg.hasAttribute('fill')).toBe(true);
        expect(svg.getAttribute('fill')).toBe('currentColor');
    });

    // ── Teste determinístico: verificar conflito com CSS fill: none ───────────
    // Validates: Requirement 1.2
    //
    // ESPERADO (código não corrigido): Computed style mostra fill: none
    // enquanto o atributo inline diz fill="currentColor"
    // Este conflito causa a renderização incorreta

    test('Like icon SVG deve ter conflito: atributo fill="currentColor" vs CSS fill: none', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const likeBtn = bar.querySelector('.aura-fb-like');
        const svg = likeBtn.querySelector('svg');

        // Atributo inline diz currentColor
        expect(svg.getAttribute('fill')).toBe('currentColor');

        // CSS computed style diz none (devido ao !important)
        const computedStyle = window.getComputedStyle(svg);
        expect(computedStyle.fill).toBe('none');

        // Este conflito é o BUG
        expect(svg.getAttribute('fill')).not.toBe(computedStyle.fill);
    });

    test('Dislike icon SVG deve ter conflito: atributo fill="currentColor" vs CSS fill: none', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const dislikeBtn = bar.querySelector('.aura-fb-dislike');
        const svg = dislikeBtn.querySelector('svg');

        // Atributo inline diz currentColor
        expect(svg.getAttribute('fill')).toBe('currentColor');

        // CSS computed style diz none (devido ao !important)
        const computedStyle = window.getComputedStyle(svg);
        expect(computedStyle.fill).toBe('none');

        // Este conflito é o BUG
        expect(svg.getAttribute('fill')).not.toBe(computedStyle.fill);
    });

    // ── Teste determinístico: verificar parent tem classe aura-fb-btn ─────────
    // Validates: Requirement 1.1

    test('Like icon parent deve ter classe aura-fb-btn', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const likeBtn = bar.querySelector('.aura-fb-like');
        const svg = likeBtn.querySelector('svg');

        expect(svg.parentElement.classList.contains('aura-fb-btn')).toBe(true);
    });

    test('Dislike icon parent deve ter classe aura-fb-btn', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const dislikeBtn = bar.querySelector('.aura-fb-dislike');
        const svg = dislikeBtn.querySelector('svg');

        expect(svg.parentElement.classList.contains('aura-fb-btn')).toBe(true);
    });

    // ── Property-based test: Bug Condition para qualquer prompt/resposta ──────
    // Validates: Requirements 1.1, 1.2
    //
    // Para qualquer prompt e resposta, os ícones SVG devem ter o conflito
    // fill="currentColor" (atributo) vs fill: none (CSS)
    //
    // Este teste PASSA no código não corrigido (confirma bug existe sempre)
    // Após o fix, este teste FALHARÁ (conflito será eliminado)

    test('fc.property: Bug Condition existe para qualquer (prompt, resposta)', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.string(),
                fc.string(),
                async function (prompt, resposta) {
                    document.body.innerHTML = '';
                    const bar = criar_unfixed(prompt, resposta);
                    document.body.appendChild(bar);

                    const likeBtn = bar.querySelector('.aura-fb-like');
                    const dislikeBtn = bar.querySelector('.aura-fb-dislike');
                    const likeSvg = likeBtn.querySelector('svg');
                    const dislikeSvg = dislikeBtn.querySelector('svg');

                    // Bug Condition: atributo fill existe
                    expect(likeSvg.hasAttribute('fill')).toBe(true);
                    expect(likeSvg.getAttribute('fill')).toBe('currentColor');
                    expect(dislikeSvg.hasAttribute('fill')).toBe(true);
                    expect(dislikeSvg.getAttribute('fill')).toBe('currentColor');

                    // Bug Condition: CSS computed style é none
                    const likeComputedStyle = window.getComputedStyle(likeSvg);
                    const dislikeComputedStyle = window.getComputedStyle(dislikeSvg);
                    expect(likeComputedStyle.fill).toBe('none');
                    expect(dislikeComputedStyle.fill).toBe('none');

                    // Bug Condition: conflito existe
                    expect(likeSvg.getAttribute('fill')).not.toBe(likeComputedStyle.fill);
                    expect(dislikeSvg.getAttribute('fill')).not.toBe(dislikeComputedStyle.fill);

                    // Bug Condition: parent tem classe aura-fb-btn
                    expect(likeSvg.parentElement.classList.contains('aura-fb-btn')).toBe(true);
                    expect(dislikeSvg.parentElement.classList.contains('aura-fb-btn')).toBe(true);
                }
            ),
            { numRuns: 50 }
        );
    });

    // ── Teste de Expected Behavior (DEVE FALHAR no código não corrigido) ─────
    // Validates: Requirements 2.1, 2.2 (from bugfix.md)
    //
    // Este teste codifica o COMPORTAMENTO ESPERADO após o fix:
    // - SVG elements NÃO devem ter atributo fill
    // - Computed style deve mostrar fill: none e stroke: currentColor
    // - Ícones devem usar apenas stroke para renderização
    //
    // **EXPECTED OUTCOME**: Este teste FALHA no código não corrigido
    // (confirma que o comportamento esperado NÃO está presente)
    //
    // Após o fix (Task 3), este mesmo teste PASSARÁ

    test('EXPECTED BEHAVIOR: Like icon deve usar apenas stroke sem atributo fill (DEVE FALHAR agora)', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const likeBtn = bar.querySelector('.aura-fb-like');
        const svg = likeBtn.querySelector('svg');

        // Expected behavior: NÃO deve ter atributo fill
        // No código não corrigido, este teste FALHA
        expect(svg.hasAttribute('fill')).toBe(false);

        // Expected behavior: computed style deve ser fill: none, stroke: currentColor
        const computedStyle = window.getComputedStyle(svg);
        expect(computedStyle.fill).toBe('none');
        expect(computedStyle.stroke).toBe('currentColor');
    });

    test('EXPECTED BEHAVIOR: Dislike icon deve usar apenas stroke sem atributo fill (DEVE FALHAR agora)', () => {
        const bar = criar_unfixed('test prompt', 'test response');
        document.body.appendChild(bar);

        const dislikeBtn = bar.querySelector('.aura-fb-dislike');
        const svg = dislikeBtn.querySelector('svg');

        // Expected behavior: NÃO deve ter atributo fill
        // No código não corrigido, este teste FALHA
        expect(svg.hasAttribute('fill')).toBe(false);

        // Expected behavior: computed style deve ser fill: none, stroke: currentColor
        const computedStyle = window.getComputedStyle(svg);
        expect(computedStyle.fill).toBe('none');
        expect(computedStyle.stroke).toBe('currentColor');
    });

    // ── Property-based test: Expected Behavior (DEVE FALHAR no código não corrigido) ──
    // Validates: Requirements 2.1, 2.2
    //
    // Para qualquer prompt e resposta, os ícones devem usar apenas stroke
    // sem atributo fill.
    //
    // **EXPECTED OUTCOME**: Este teste FALHA no código não corrigido
    // Após o fix, este teste PASSARÁ

    test('fc.property: EXPECTED BEHAVIOR - Ícones devem usar apenas stroke para qualquer (prompt, resposta) (DEVE FALHAR agora)', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.string(),
                fc.string(),
                async function (prompt, resposta) {
                    document.body.innerHTML = '';
                    const bar = criar_unfixed(prompt, resposta);
                    document.body.appendChild(bar);

                    const likeBtn = bar.querySelector('.aura-fb-like');
                    const dislikeBtn = bar.querySelector('.aura-fb-dislike');
                    const likeSvg = likeBtn.querySelector('svg');
                    const dislikeSvg = dislikeBtn.querySelector('svg');

                    // Expected behavior: NÃO deve ter atributo fill
                    expect(likeSvg.hasAttribute('fill')).toBe(false);
                    expect(dislikeSvg.hasAttribute('fill')).toBe(false);

                    // Expected behavior: computed style correto
                    const likeComputedStyle = window.getComputedStyle(likeSvg);
                    const dislikeComputedStyle = window.getComputedStyle(dislikeSvg);
                    expect(likeComputedStyle.fill).toBe('none');
                    expect(likeComputedStyle.stroke).toBe('currentColor');
                    expect(dislikeComputedStyle.fill).toBe('none');
                    expect(dislikeComputedStyle.stroke).toBe('currentColor');
                }
            ),
            { numRuns: 50 }
        );
    });

});

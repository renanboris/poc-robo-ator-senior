// content.js - Interface da Aura (Mundo MAIN) com Olho Biônico, Memória e Typewriter
// Atualizações: Spotlight centralizado, Fallback Híbrido, Histórico de Conversa e Efeito de Digitação.

(function() {
    console.log("Aura: Iniciando interface...");

    // 🟢 SPRINT 1 & 3: Memória de Curto Prazo e Controlo de Digitação
    let historicoAura = [];
    let auraTypingInterval = null;

    // 🟢 CAÇADORA DE NOMES DINÂMICA
    function descobrirNomeUsuario() {
        try {
            const seletoresNome = document.querySelectorAll('.user-name, .profile-name, [data-testid="user-name"], .header-user span, [aria-label*="perfil de"]');
            for (let el of seletoresNome) {
                let texto = el.innerText || el.textContent;
                if (texto && texto.trim().length > 2) {
                    return texto.trim().split(' ')[0];
                }
            }

            for (let i = 0; i < localStorage.length; i++) {
                try {
                    let key = localStorage.key(i);
                    if (!key.toLowerCase().includes('user') && !key.toLowerCase().includes('profile')) continue;
                    let obj = JSON.parse(localStorage.getItem(key));
                    let nome = obj?.name || obj?.nome || obj?.firstName;
                    if (nome) return nome.split(' ')[0];
                } catch (_) { /* segue para próxima chave */ }
            }
        } catch (e) {
            console.warn("Aura: Não foi possível caçar o nome dinâmico.");
        }
        return "Utilizador";
    }

    async function obterExtensionId(tentativas = 0) {
        const id = document.documentElement.getAttribute('data-aura-id');
        if (id) return id;
        if (tentativas > 20) return null;
        await new Promise(r => setTimeout(r, 100));
        return obterExtensionId(tentativas + 1);
    }

    async function iniciarAura() {
        const extensionId = await obterExtensionId();
        if (!extensionId || !window.customElements) return;

        try {
            await window.customElements.whenDefined('dotlottie-player');
        } catch (e) {
            console.error("Aura: dotlottie-player não disponível.", e);
            return;
        }

        const auraContainer = document.createElement('div');
        auraContainer.id = 'aura-floating-container';
        auraContainer.innerHTML = `
            <div id="aura-speech-bubble">
                <div class="aura-text">Olá, sou a Aura! Como posso ajudar nesta tela?</div>
                <div class="aura-input-wrapper">
                    <input type="text" id="aura-prompt-input" placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">
                    <button class="aura-btn-send" id="aura-btn-ask">➜</button>
                </div>
                <div class="aura-options"></div>
            </div>
            <dotlottie-player id="aura-lottie-player" src="chrome-extension://${extensionId}/aura.lottie" background="transparent" speed="1" loop autoplay></dotlottie-player>
        `;
        document.documentElement.appendChild(auraContainer);

        let isDragging = false, wasDragged = false;
        let startX, startY, initialX, initialY;

        const player = document.getElementById('aura-lottie-player');
        const bubble = document.getElementById('aura-speech-bubble');

        // Drag and Drop
        player.addEventListener('mousedown', (e) => {
            isDragging = true;
            wasDragged = false;
            startX = e.clientX;
            startY = e.clientY;
            initialX = auraContainer.offsetLeft;
            initialY = auraContainer.offsetTop;
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;

            let newX = initialX + dx;
            let newY = initialY + dy;

            newX = Math.max(0, Math.min(newX, window.innerWidth - auraContainer.offsetWidth));
            newY = Math.max(0, Math.min(newY, window.innerHeight - auraContainer.offsetHeight));

            auraContainer.style.left = newX + 'px';
            auraContainer.style.top = newY + 'px';
            auraContainer.style.right = 'auto';
            auraContainer.style.bottom = 'auto';
        });

        document.addEventListener('mouseup', () => { isDragging = false; });

        player.addEventListener('click', (e) => {
            if (wasDragged) return;
            if (bubble.classList.contains('active')) {
                bubble.classList.remove('active');
            } else {
                exibirBalaoAura("Precisa de ajuda com esta tela?", [], false);
            }
        });

        document.getElementById('aura-btn-ask').addEventListener('pointerdown', (e) => {
            e.preventDefault(); e.stopPropagation(); dispararAnaliseIA();
        });
        document.getElementById('aura-prompt-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.stopPropagation(); dispararAnaliseIA(); }
        });
        document.getElementById('aura-speech-bubble').addEventListener('mousedown', e => e.stopPropagation());

        // ─── MOTOR DE PROATIVIDADE (IDLE TIMER) ───
        let tempoInativo = 0;
        const TEMPO_LIMITE_SEGUNDOS = 30;

        function resetarCronometro() { tempoInativo = 0; }

        document.addEventListener('mousemove', resetarCronometro);
        document.addEventListener('keypress', resetarCronometro);
        document.addEventListener('click', resetarCronometro);
        document.addEventListener('scroll', resetarCronometro);

        setInterval(() => {
            const bubbleElement = document.getElementById('aura-speech-bubble');
            if (bubbleElement && bubbleElement.classList.contains('active')) return;

            tempoInativo++;
            if (tempoInativo === TEMPO_LIMITE_SEGUNDOS) {
                tempoInativo = 0; 
                exibirBalaoAura("Vejo que você parou nesta tela. Precisa de alguma ajuda para continuar? 🤔", [
                    { label: "Sim, me ajude", action: () => dispararAnaliseIA("O que devo fazer nesta tela?") },
                    {
                        label: "Não, obrigado",
                        action: () => {
                            bubbleElement.classList.remove('active');
                            resetarCronometro();
                        }
                    }
                ]);
            }
        }, 1000);

        // 🟢 DETETOR DE NAVEGAÇÃO ANGULAR
        let urlAtual = window.location.href;
        let spaDebounce = null;

        const observerSPA = new MutationObserver(() => {
            if (urlAtual === window.location.href) return;
            clearTimeout(spaDebounce);
            spaDebounce = setTimeout(() => {
                urlAtual = window.location.href;
                console.log("Aura: Troca de tela Angular detetada. Limpando contexto antigo...");
                document.getElementById('aura-sonar-highlight')?.remove();
                document.getElementById('aura-backdrop')?.remove();
                
                // Limpa a memória se mudar drasticamente de tela
                historicoAura = []; 
                
                if (bubble.classList.contains('active')) {
                    exibirBalaoAura(`Olá, ${descobrirNomeUsuario()}! Precisa de ajuda nesta nova tela?`, [], false);
                }
            }, 300);
        });
        observerSPA.observe(document.body, { childList: true, subtree: true });

        // PRE-CAPTURE
        document.getElementById('aura-prompt-input').addEventListener('focus', () => {
            window.postMessage({ type: "AURA_PRE_CAPTURE" }, window.location.origin);
        });
    }

    // 🟢 SPRINT 3: MOTOR TYPEWRITER (Efeito Máquina de Escrever)
    function exibirBalaoAura(texto, opcoes = [], efeitoDigitacao = true) {
        const bubble = document.getElementById('aura-speech-bubble');
        if (!bubble) return;

        const textEl = bubble.querySelector('.aura-text');
        const optDiv = bubble.querySelector('.aura-options');
        
        optDiv.innerHTML = '';
        optDiv.style.opacity = '0';
        optDiv.style.transition = 'opacity 0.4s ease';
        optDiv.style.pointerEvents = 'none';

        opcoes.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'aura-btn';
            btn.innerText = opt.label;
            btn.addEventListener('click', (e) => { 
                e.stopPropagation(); 
                opt.action(); 
            });
            optDiv.appendChild(btn);
        });

        bubble.classList.add('active');

        if (auraTypingInterval) clearInterval(auraTypingInterval);

        if (efeitoDigitacao) {
            textEl.innerHTML = ''; 
            let i = 0;
            // Velocidade da digitação: 25ms por letra
            auraTypingInterval = setInterval(() => {
                textEl.innerHTML += texto.charAt(i);
                i++;
                if (i >= texto.length) {
                    clearInterval(auraTypingInterval);
                    // Revela os chips ao terminar de digitar
                    optDiv.style.opacity = '1';
                    optDiv.style.pointerEvents = 'auto';
                }
            }, 25); 
        } else {
            textEl.innerHTML = texto;
            optDiv.style.opacity = '1';
            optDiv.style.pointerEvents = 'auto';
        }
    }

    // =========================================================
    // 👁️ O OLHO BIÔNICO DA AURA E CAÇADOR DE IFRAMES
    // =========================================================

    function capturarDOMParaIA() {
        document.querySelectorAll('[data-aura-map]').forEach(e => e.removeAttribute('data-aura-map'));

        const seletores = [
            "button", "a[href]", "input", "select", "textarea",
            "[role='button']", "[role='menuitem']", "[role='tab']", "[role='link']",
            "[class*='btn']", "[class*='button']", "[class*='action']",
            "[tabindex]:not([tabindex='-1'])",
            "[ng-click]", "[onclick]"
        ].join(", ");

        const elementos = document.querySelectorAll(seletores);
        let domList = [];
        let elementosMapeados = new Set();

        for (let index = 0; index < elementos.length; index++) {
            if (domList.length >= 80) break; 

            const el = elementos[index];
            const rect = el.getBoundingClientRect();

            if (rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top <= window.innerHeight) {
                let texto = el.innerText || el.textContent || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || "";
                texto = texto.trim().substring(0, 40).replace(/\n/g, " ");

                if (texto && texto.length > 1 && !elementosMapeados.has(texto)) {
                    elementosMapeados.add(texto);
                    el.setAttribute('data-aura-map', index);
                    domList.push(`[ID: ${index}] TIPO: ${el.tagName.toLowerCase()} | TEXTO: "${texto}"`);
                }
            }
        }

        return "ELEMENTOS INTERATIVOS VISÍVEIS NA TELA:\n" + domList.join("\n");
    }

    function encontrarElementoNaTela(seletorCSS) {
        let el = document.querySelector(seletorCSS);
        if (el) return { elemento: el, frame: null };

        const iframes = document.querySelectorAll('iframe');
        for (let frame of iframes) {
            try {
                const frameDoc = frame.contentDocument || frame.contentWindow.document;
                el = frameDoc.querySelector(seletorCSS);
                if (el) return { elemento: el, frame: frame };
            } catch (e) {
                // Erro de CORS
            }
        }
        return null;
    }

    // 🟢 BACKDROP TEMPORÁRIO
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

    // 🟢 HOLOFOTE CENTRALIZADO
    function aplicarHolofoteDom(auraIdOuSeletor, isSeletor = false) {
        document.getElementById('aura-sonar-highlight')?.remove();
        document.getElementById('aura-backdrop')?.remove();

        if (!auraIdOuSeletor) return;

        let match = isSeletor
            ? encontrarElementoNaTela(auraIdOuSeletor)
            : encontrarElementoNaTela(`[data-aura-map="${auraIdOuSeletor}"]`);

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

            highlight.style.cssText = `
                position: fixed;
                top: ${rect.top + fTop - 6}px;
                left: ${rect.left + fLeft - 6}px;
                width: ${rect.width + 12}px;
                height: ${rect.height + 12}px;
                border: 4px solid #00E676;
                border-radius: 8px;
                box-shadow: 0 0 20px #00E676, inset 0 0 10px #00E676;
                z-index: 999999;
                pointer-events: none;
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
    }

    // =========================================================
    // 🟢 RECEPTOR DE RESPOSTAS DA AURA
    // =========================================================
    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        if (event.data.type !== "AURA_RESPONSE") return;

        const payload = event.data.payload || {};
        const textoResposta = payload.mensagem || payload.advice || "Desculpe, não consegui processar a resposta.";

        // Salva a resposta da Aura na Memória
        historicoAura.push({ autor: "Aura", texto: textoResposta });
        if (historicoAura.length > 4) historicoAura.shift(); 

        let sugestoes = [];
        if (payload.sugestoes && Array.isArray(payload.sugestoes)) {
            sugestoes = payload.sugestoes.map(s => ({
                label: s,
                action: () => {
                    document.getElementById('aura-prompt-input').value = s;
                    dispararAnaliseIA(s);
                }
            }));
        }

        // Exibe o balão com EFEITO DE DIGITAÇÃO ativado (true é o padrão)
        exibirBalaoAura(textoResposta, sugestoes);

        if (payload.seletor_css) {
            console.log("Aura: Tentando usar memória muscular (Brain/JSON):", payload.seletor_css);
            let matchAlvo = null;
            try {
                matchAlvo = encontrarElementoNaTela(payload.seletor_css);
            } catch(e) {
                console.warn("Aura: Seletor CSS inválido:", payload.seletor_css);
            }

            if (matchAlvo?.elemento) {
                console.log("Aura: Elemento encontrado pelo CSS exato (mesmo dentro de Iframes)!");
                aplicarHolofoteDom(payload.seletor_css, true);
            } else if (payload.elemento_id != null) {
                console.warn("Aura: Seletor CSS não encontrado. Acionando Plano B (Visão da IA)...");
                aplicarHolofoteDom(payload.elemento_id, false);
            } else {
                console.warn("Aura: Plano B também falhou. Nenhum elemento encontrado.");
                document.getElementById('aura-sonar-highlight')?.remove();
                document.getElementById('aura-backdrop')?.remove();
            }
        } else if (payload.elemento_id != null) {
            console.log("Aura: Sem memória muscular. Usando leitura dinâmica de DOM: ID", payload.elemento_id);
            aplicarHolofoteDom(payload.elemento_id, false);
        } else {
            document.getElementById('aura-sonar-highlight')?.remove();
            document.getElementById('aura-backdrop')?.remove();
        }
    });

    // =========================================================
    // 🟢 DISPARO PARA A IA
    // =========================================================
    function dispararAnaliseIA(textoOpcional) {
        const inputEl = document.getElementById('aura-prompt-input');
        const prompt  = textoOpcional || (inputEl?.value || '').trim() || "O que devo fazer nesta tela?";

        document.getElementById('aura-sonar-highlight')?.remove();
        document.getElementById('aura-backdrop')?.remove();

        historicoAura.push({ autor: "Utilizador", texto: prompt });
        if (historicoAura.length > 4) historicoAura.shift(); 

        // 🟢 Passa `false` para a mensagem de sistema NÃO ter efeito de digitação lenta
        exibirBalaoAura("Estou a analisar a interface... Só um momento! 🔍", [], false);
        if (inputEl) inputEl.value = '';

        const extratoDOM = capturarDOMParaIA();
        const nomeReal = descobrirNomeUsuario();

        window.postMessage({
            type:        "AURA_CAPTURE",
            url:         window.location.href,
            prompt:      prompt,
            dom_context: extratoDOM,
            user_name:   nomeReal,
            tenant_id:   "senior_default",
            historico:   historicoAura 
        }, window.location.origin);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciarAura);
    } else {
        iniciarAura();
    }
})();
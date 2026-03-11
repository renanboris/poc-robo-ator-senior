// content.js - Interface da Aura (Mundo MAIN)

(function() {
    console.log("Aura: Iniciando interface...");

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
                <div class="aura-text">Olá, sou a Aura! Como posso te ajudar nesta tela?</div>
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
                exibirBalaoAura("Precisa de ajuda com esta tela?", []);
            }
        });

        document.getElementById('aura-btn-ask').addEventListener('click', (e) => {
            e.stopPropagation(); dispararAnaliseIA();
        });
        document.getElementById('aura-prompt-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.stopPropagation(); dispararAnaliseIA(); }
        });
        document.getElementById('aura-speech-bubble').addEventListener('mousedown', e => e.stopPropagation());
    }

    function exibirBalaoAura(texto, opcoes = []) {
        const bubble = document.getElementById('aura-speech-bubble');
        if (!bubble) return;

        bubble.querySelector('.aura-text').innerText = texto;
        const optDiv = bubble.querySelector('.aura-options');
        optDiv.innerHTML = '';
        
        opcoes.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'aura-btn';
            btn.innerText = opt.label;
            btn.addEventListener('click', (e) => { e.stopPropagation(); opt.action(); });
            optDiv.appendChild(btn);
        });

        bubble.classList.add('active');
    }

    function aplicarHolofote(seletor) {
        document.getElementById('aura-sonar-highlight')?.remove();

        if (!seletor || seletor === "") return;

        const elemento = document.querySelector(seletor);
        if (!elemento) {
            console.warn("Aura: O Python indicou o seletor, mas não achei na tela:", seletor);
            return;
        }

        elemento.scrollIntoView({ behavior: 'smooth', block: 'center' });

        setTimeout(() => {
            const rect = elemento.getBoundingClientRect();
            const sonar = document.createElement('div');
            sonar.id = 'aura-sonar-highlight';
            
            sonar.style.top = (rect.top + (rect.height / 2)) + 'px';
            sonar.style.left = (rect.left + (rect.width / 2)) + 'px';
            
            document.body.appendChild(sonar);

            elemento.addEventListener('click', () => {
                document.getElementById('aura-sonar-highlight')?.remove();
                exibirBalaoAura("Excelente! O que fazemos agora?", []);
            }, { once: true });
            
        }, 400);
    }

    function dispararAnaliseIA() {
        const inputEl = document.getElementById('aura-prompt-input');
        const prompt  = (inputEl?.value || '').trim() || "O que devo fazer nesta tela?";

        exibirBalaoAura("Analisando a tela... Só um momento! 🔍", []);
        
        if (inputEl) inputEl.value = '';

        window.postMessage({
            type:   "AURA_CAPTURE",
            url:    window.location.href,
            prompt: prompt
        }, window.location.origin);
    }

    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        
        if (event.data.type === "AURA_RESPONSE") {
            const payload = event.data.payload || {};
            
            exibirBalaoAura(payload.advice || "Pronto!", []);

            if (payload.action === 'highlight' && payload.selector) {
                aplicarHolofote(payload.selector);
            } else {
                document.getElementById('aura-sonar-highlight')?.remove();
            }
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', iniciarAura);
    } else {
        iniciarAura();
    }
})();
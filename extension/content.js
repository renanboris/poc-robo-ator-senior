// content.js - Interface da Aura (Mundo MAIN) com Olho Biônico, Motor GPS, Feedback Premium e Badge Notification

function injetarEstilosAura() {
    if (document.getElementById('aura-css-styles')) return;
    const style = document.createElement('style');
    style.id = 'aura-css-styles';
    style.innerHTML = `
        #aura-speech-bubble .aura-options:empty { display: none !important; padding-top: 0 !important; border-top: none !important; }
        @keyframes aura-pulse { 0% { transform: scale(1); opacity: 1; } 50% { transform: scale(1.04); opacity: 0.8; } 100% { transform: scale(1); opacity: 1; } }
    `;
    document.head.appendChild(style);
}

(function() {
    console.log("Aura: Iniciando interface...");

    let roteiroAtivo = null;
    let passoAtualIndex = 0;
    let modoPilotoAutomatico = false;
    let auraTypingInterval = null;

    function descobrirNomeUsuario() {
        try {
            const seletoresNome = document.querySelectorAll('.user-name, .profile-name, [data-testid="user-name"], .header-user span');
            for (let el of seletoresNome) {
                let texto = el.innerText || el.textContent;
                if (texto && texto.trim().length > 2) return texto.trim().split(' ')[0]; 
            }
        } catch (e) { }
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
        injetarEstilosAura(); 
        const extensionId = await obterExtensionId();
        if (!extensionId || !window.customElements) return;

        try { await window.customElements.whenDefined('dotlottie-player'); } 
        catch (e) { return; }

        const auraContainer = document.createElement('div');
        auraContainer.id = 'aura-floating-container';

        auraContainer.innerHTML = `
            <div id="aura-notification-badge" class="aura-badge">1</div>
            <dotlottie-player id="aura-lottie-player" src="chrome-extension://${extensionId}/aura.json" background="transparent" speed="1"></dotlottie-player>
            <div id="aura-speech-bubble">
                <button class="aura-btn-close" id="aura-btn-close" aria-label="Fechar">✕</button>
                
                <div class="aura-text-wrapper">
                    <div class="aura-text">Olá, sou a Aura! Como posso te ajudar nesta tela?</div>
                    
                    <div id="aura-feedback-container" class="aura-feedback-wrapper" style="display: none;">
                        <div id="aura-feedback-actions" style="display: flex; gap: 6px;">
                            <button class="aura-btn-feedback" id="aura-btn-like" title="Útil">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
                            </button>
                            <button class="aura-btn-feedback" id="aura-btn-dislike" title="Incorreto">
                                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"></path></svg>
                            </button>
                        </div>
                        <span id="aura-feedback-msg" class="aura-feedback-msg" style="display:none;"></span>
                    </div>
                </div>

                <div class="aura-input-wrapper" id="aura-input-container">
                    <input type="text" id="aura-prompt-input" placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">
                    <button class="aura-btn-send" id="aura-btn-ask">➜</button>
                </div>
                <div class="aura-options"></div>
            </div>
        `;
        document.documentElement.appendChild(auraContainer);

        function verificarVisibilidadeDAP() {
            const url = window.location.href.toLowerCase();
            const isLogin = url.includes('login') || url.includes('auth');
            auraContainer.style.display = isLogin ? 'none' : 'block';
        }
        setInterval(verificarVisibilidadeDAP, 1000);
        verificarVisibilidadeDAP();

        let isDragging = false, wasDragged = false;
        let startX, startY, initialX, initialY;

        const player = document.getElementById('aura-lottie-player');
        const bubble = document.getElementById('aura-speech-bubble');
        const badge = document.getElementById('aura-notification-badge');

        let _animacaoRodando = false;
        function tocarAnimacaoUmaVez() {
            if (_animacaoRodando) return;
            _animacaoRodando = true;
            player.stop();  
            player.play();
        }

        player.addEventListener('complete', () => { _animacaoRodando = false; player.pause(); });
        player.addEventListener('ready', () => tocarAnimacaoUmaVez());
        setTimeout(() => { if (!_animacaoRodando) tocarAnimacaoUmaVez(); }, 400);

        player.addEventListener('mousedown', (e) => {
            isDragging = true; wasDragged = false; startX = e.clientX; startY = e.clientY;
            const rect = auraContainer.getBoundingClientRect();
            initialX = rect.left; initialY = rect.top;
            auraContainer.style.left = initialX + 'px'; auraContainer.style.top = initialY + 'px';
            auraContainer.style.right = 'auto'; auraContainer.style.bottom = 'auto';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX; const dy = e.clientY - startY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;
            const maxX = window.innerWidth - 170; const maxY = window.innerHeight - 170;
            auraContainer.style.left = Math.max(8, Math.min(initialX + dx, maxX - 8)) + 'px';
            auraContainer.style.top  = Math.max(8, Math.min(initialY + dy, maxY - 8)) + 'px';
        });

        document.addEventListener('mouseup', () => isDragging = false);
        bubble.addEventListener('mousedown', (e) => e.stopPropagation());

        // FIX DUPLO CLIQUE NO MASCOTE
        player.addEventListener('click', (e) => {
            if (wasDragged) { wasDragged = false; return; }
            tocarAnimacaoUmaVez();
            proatividadeSilenciada = false;
            badge.classList.remove('active');

            if (_autoCloseTimeout) { 
                clearTimeout(_autoCloseTimeout); 
                _autoCloseTimeout = null; 
            }

            if (bubble.classList.contains('active')) {
                bubble.classList.remove('active');
            } else {
                exibirBalaoAura("Precisa de ajuda com esta tela?", [], true, false);
            }
        });

        document.getElementById('aura-btn-ask').addEventListener('pointerdown', (e) => { e.preventDefault(); e.stopPropagation(); dispararAnaliseIA(); });
        document.getElementById('aura-prompt-input').addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.stopPropagation(); dispararAnaliseIA(); } });

        document.getElementById('aura-btn-close').addEventListener('click', (e) => {
            e.stopPropagation(); bubble.classList.remove('active'); roteiroAtivo = null; proatividadeSilenciada = true;
            if (_autoCloseTimeout) { clearTimeout(_autoCloseTimeout); _autoCloseTimeout = null; }
            document.getElementById('aura-sonar-highlight')?.remove(); document.getElementById('aura-backdrop')?.remove();
        });

        const btnLike = document.getElementById('aura-btn-like');
        const btnDislike = document.getElementById('aura-btn-dislike');
        const actionsDiv = document.getElementById('aura-feedback-actions');
        const msgDiv = document.getElementById('aura-feedback-msg');

        btnLike.addEventListener('click', () => {
            actionsDiv.style.display = 'none'; msgDiv.style.display = 'block'; msgDiv.style.color = '#007a6b'; msgDiv.innerText = 'Obrigado pelo feedback!';
        });

        btnDislike.addEventListener('click', () => {
            actionsDiv.style.display = 'none'; msgDiv.style.display = 'block'; msgDiv.style.color = '#ef4444'; msgDiv.innerText = 'Reportado. Vou melhorar!';
            const ultimaPergunta = document.getElementById('aura-prompt-input')?.value || "última pergunta";
            window.postMessage({ type: "AURA_FEEDBACK_NEGATIVE", prompt: ultimaPergunta }, window.location.origin);
        });

        // ─── MOTOR DE PROATIVIDADE COM BADGE ──────────────────────────────
        let tempoInativo = 0;
        const TEMPO_LIMITE_SEGUNDOS = 15;
        let _throttleTimer = null;
        let _autoCloseTimeout = null; 
        let proatividadeSilenciada = false; 

        function resetarCronometro() {
            if (_throttleTimer) return;
            tempoInativo = 0;
            _throttleTimer = setTimeout(() => { _throttleTimer = null; }, 500);
        }

        document.addEventListener('mousemove', resetarCronometro);
        document.addEventListener('keypress', resetarCronometro);
        document.addEventListener('scroll', resetarCronometro);
        
        document.addEventListener('click', () => {
            resetarCronometro();
            const bubbleElement = document.getElementById('aura-speech-bubble');
            if (bubbleElement && bubbleElement.classList.contains('active') && _autoCloseTimeout) {
                clearTimeout(_autoCloseTimeout);
                _autoCloseTimeout = null;
                bubbleElement.classList.remove('active');
                badge.classList.add('active'); 
                proatividadeSilenciada = true; 
            }
        });

        setInterval(() => {
            tempoInativo++;
            if (tempoInativo === TEMPO_LIMITE_SEGUNDOS && !proatividadeSilenciada) {
                const bubbleElement = document.getElementById('aura-speech-bubble');
                
                if (bubbleElement && !bubbleElement.classList.contains('active')) {
                    tocarAnimacaoUmaVez();
                    
                    exibirBalaoAura("Vejo que você parou nesta tela. Precisa de alguma ajuda para continuar?", [
                        { label: "Sim, me ajude", action: () => { 
                            if (_autoCloseTimeout) { clearTimeout(_autoCloseTimeout); _autoCloseTimeout = null; }
                            exibirBalaoAura("Ótimo! O que você gostaria de fazer?", [], true, false);
                            document.getElementById('aura-prompt-input').focus();
                        }},
                        { label: "Não, obrigado", action: () => { 
                            if (_autoCloseTimeout) { clearTimeout(_autoCloseTimeout); _autoCloseTimeout = null; }
                            bubbleElement.classList.remove('active'); proatividadeSilenciada = true; resetarCronometro(); 
                        }}
                    ], false, true); 
                    
                    _autoCloseTimeout = setTimeout(() => {
                        if (bubbleElement.classList.contains('active')) {
                            bubbleElement.classList.remove('active');
                            badge.classList.add('active'); 
                            proatividadeSilenciada = true; 
                            resetarCronometro();
                        }
                    }, 12000);
                }
            }
        }, 1000);

        let urlAtual = window.location.href;
        let _spaDebounce = null;
        const observerSPA = new MutationObserver(() => {
            if (_spaDebounce) return;
            _spaDebounce = setTimeout(() => {
                _spaDebounce = null;
                if (urlAtual !== window.location.href) {
                    urlAtual = window.location.href;
                    document.getElementById('aura-sonar-highlight')?.remove(); document.getElementById('aura-backdrop')?.remove();
                    proatividadeSilenciada = false; badge.classList.remove('active');
                    if (_autoCloseTimeout) { clearTimeout(_autoCloseTimeout); _autoCloseTimeout = null; }
                    
                    if (!roteiroAtivo) {
                        const bubbleEl = document.getElementById('aura-speech-bubble');
                        if (bubbleEl?.classList.contains('active')) {
                            exibirBalaoAura(`Olá, ${descobrirNomeUsuario()}! Precisa de ajuda nesta nova tela?`, [], true, false);
                        }
                    }
                }
            }, 300);
        });
        observerSPA.observe(document.body, { childList: true, subtree: true });

        document.getElementById('aura-prompt-input').addEventListener('focus', () => { window.postMessage({ type: "AURA_PRE_CAPTURE" }, window.location.origin); });
    }

    // =========================================================
    // 🟢 RENDERIZADOR DO BALÃO
    // =========================================================
    function exibirBalaoAura(texto, opcoes = [], efeitoDigitacao = true, ocultarInput = false) {
        const bubble = document.getElementById('aura-speech-bubble');
        if (!bubble) return;

        texto = texto || ""; // Trava Anti-Crash

        const fbContainer = document.getElementById('aura-feedback-container');
        if (fbContainer) {
            fbContainer.classList.remove('show-feedback');
        }

        const textEl = bubble.querySelector('.aura-text');
        const optDiv = bubble.querySelector('.aura-options');
        
        if (ocultarInput) { bubble.classList.add('no-input'); } 
        else { bubble.classList.remove('no-input'); }

        optDiv.innerHTML = ''; optDiv.style.opacity = '0'; optDiv.style.pointerEvents = 'none';
        _reativarInputs();

        opcoes.forEach(opt => {
            const btn = document.createElement('button'); btn.className = 'aura-btn'; btn.innerText = opt.label;
            btn.addEventListener('click', (e) => { e.stopPropagation(); opt.action(); }); optDiv.appendChild(btn);
        });

        bubble.classList.add('active');

        let textoFormatado = texto.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>');            

        if (auraTypingInterval) clearInterval(auraTypingInterval);

        if (efeitoDigitacao && !textoFormatado.includes('<br>')) {
            textEl.innerHTML = ''; let i = 0;
            auraTypingInterval = setInterval(() => {
                textEl.innerHTML += textoFormatado.charAt(i); i++;
                if (i >= textoFormatado.length) { clearInterval(auraTypingInterval); optDiv.style.opacity = '1'; optDiv.style.pointerEvents = 'auto'; }
            }, 25); 
        } else {
            textEl.style.opacity = '0'; textEl.innerHTML = textoFormatado;
            setTimeout(() => { textEl.style.opacity = '1'; }, 50); optDiv.style.opacity = '1'; optDiv.style.pointerEvents = 'auto';
        }
    }

    // =========================================================
    // 🟢 BUSCA NATIVA E SEMÂNTICA (Padrão Enterprise via XPath)
    // =========================================================
    function encontrarElementoNaTela(alvo) {
        if (!alvo) return null;

        // 1. TENTATIVA A: Busca direta via seletor CSS clássico (O mais rápido)
        // O try/catch ignora erros se a IA inventar pseudo-seletores como :contains
        try {
            let el = document.querySelector(alvo);
            if (el && el.offsetParent !== null) return { elemento: el, frame: null };
        } catch(e) {} 

        // 2. TENTATIVA B: Busca Semântica por Texto Visível (XPath Nativo do Chrome)
        // Se a busca CSS falhou, vamos extrair o texto para procurar na tela.
        let textoLimpo = alvo;
        if (alvo.includes(':contains(')) {
            // Extrai a palavra de dentro do :contains('Palavra')
            const match = alvo.match(/:contains\(['"]?(.*?)['"]?\)/);
            if (match) textoLimpo = match[1];
        } else {
            // Remove pontos ou hashtags iniciais se a IA mandou uma classe/id errada
            textoLimpo = alvo.replace(/^[.#]/, "").trim(); 
        }

        if (textoLimpo && textoLimpo.length > 2) {
            try {
                const txtLower = textoLimpo.toLowerCase();
                // O XPath varre a tela à procura de links, botões ou itens de menu que contenham a palavra (case-insensitive)
                const xpath = `//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúàèìòùâêîôûãõç'), '${txtLower}')] | //button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúàèìòùâêîôûãõç'), '${txtLower}')] | //*[contains(@class, 'menu-item') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúàèìòùâêîôûãõç'), '${txtLower}')] | //*[contains(@role, 'button') and contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÃÕÇ', 'abcdefghijklmnopqrstuvwxyzáéíóúàèìòùâêîôûãõç'), '${txtLower}')]`;
                
                const result = document.evaluate(xpath, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                let elXPath = result.singleNodeValue;
                
                // Verifica se achou e se o elemento não está invisível no Angular (display: none)
                if (elXPath && elXPath.offsetParent !== null) {
                    return { elemento: elXPath, frame: null };
                }
            } catch(e) {}
        }

        // 3. TENTATIVA C: Busca Extrema dentro de Iframes (Fallbacks)
        const iframes = document.querySelectorAll('iframe');
        for (let frame of iframes) {
            try {
                const frameDoc = frame.contentDocument || frame.contentWindow.document;
                let el = frameDoc.querySelector(alvo);
                if (el && el.offsetParent !== null) return { elemento: el, frame: frame };
            } catch (e) {}
        }
        
        return null; // Retorna null para o GPS tentar novamente nos próximos milissegundos
    }

    function criarBackdrop(rect, frameTop, frameLeft) {
        document.getElementById('aura-backdrop')?.remove();
        const backdrop = document.createElement('div'); 
        backdrop.id = 'aura-backdrop';
        
        // pointer-events: none garante que NADA fique bloqueado.
        backdrop.style.cssText = `
            position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; 
            background: rgba(0,0,0,0.6); z-index: 999998; pointer-events: none; 
            clip-path: polygon(0% 0%, 0% 100%, ${frameLeft + rect.left}px 100%, ${frameLeft + rect.left}px ${frameTop + rect.top}px, ${frameLeft + rect.right}px ${frameTop + rect.top}px, ${frameLeft + rect.right}px ${frameTop + rect.bottom}px, ${frameLeft + rect.left}px ${frameTop + rect.bottom}px, ${frameLeft + rect.left}px 100%, 100% 100%, 100% 0%); 
            transition: opacity 1s ease; opacity: 1;
        `;
        document.body.appendChild(backdrop);
        
        // 🟢 FASE 1 (Atenção): O fundo escuro some após 3.5 segundos para libertar a visão do ERP
        setTimeout(() => { 
            if (backdrop) { 
                backdrop.style.opacity = '0'; 
                setTimeout(() => backdrop.remove(), 1000); 
            } 
        }, 3500);
    }

    function aplicarHolofoteDom(auraIdOuSeletor, isSeletor = false) {
        document.getElementById('aura-sonar-highlight')?.remove(); 
        document.getElementById('aura-backdrop')?.remove();
        
        if (!auraIdOuSeletor) return;
        
        let match = isSeletor ? encontrarElementoNaTela(auraIdOuSeletor) : encontrarElementoNaTela(`[data-aura-map="${auraIdOuSeletor}"]`);
        if (!match || !match.elemento) return;
        
        const el = match.elemento; 
        const frame = match.frame; 
        
        // Faz o scroll suave para o botão
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Esperamos 500ms para o scroll terminar antes de desenhar
        setTimeout(() => {
            const rect = el.getBoundingClientRect(); 
            let fTop = 0, fLeft = 0;
            if (frame) { const fRect = frame.getBoundingClientRect(); fTop = fRect.top; fLeft = fRect.left; }
            
            criarBackdrop(rect, fTop, fLeft);
            
            const highlight = document.createElement('div'); 
            highlight.id = 'aura-sonar-highlight';
            const top = rect.top + fTop + window.scrollY; 
            const left = rect.left + fLeft + window.scrollX;
            
            highlight.style.cssText = `
                position: absolute; top: ${top - 6}px; left: ${left - 6}px; 
                width: ${rect.width + 12}px; height: ${rect.height + 12}px; 
                border: 4px solid #00E676; border-radius: 8px; 
                box-shadow: 0 0 20px #00E676, inset 0 0 10px #00E676; 
                z-index: 999999; pointer-events: none; 
                animation: aura-pulse 1.5s infinite; transition: opacity 0.5s ease;
            `;
            document.body.appendChild(highlight);
            
            // 🟢 FASE 2 (Sinalização): A luz verde pisca por 15 longos segundos
            const hideTimeout = setTimeout(() => { 
                if (highlight) { 
                    highlight.style.opacity = '0'; 
                    setTimeout(() => highlight.remove(), 500); 
                } 
            }, 15000);
            
            // 🟢 FASE 3 (Ação do Utilizador): Se ele clicar no botão, limpamos a luz instantaneamente
            el.addEventListener('click', () => { 
                clearTimeout(hideTimeout);
                document.getElementById('aura-sonar-highlight')?.remove(); 
                document.getElementById('aura-backdrop')?.remove(); 
            }, { once: true });
            
        }, 500);
    }

// =========================================================
    // 🟢 2. INICIAR ROTEIRO (Trava Anti-Fantasma)
    // =========================================================
    function iniciarRoteiro(payloadRoteiro, autoPilot = false) {
        roteiroAtivo = payloadRoteiro; 
        passoAtualIndex = 0; 
        
        // 🟢 TRAVA FÍSICA: Ignora a IA e obriga o Piloto Automático a ficar Desligado
        modoPilotoAutomatico = false; 
        
        executarPassoAtual();
    }

    // ✅ FUNÇÃO RESTAURADA: Esta função tinha sumido do seu código!
    function executarPassoAtual() {
        if (!roteiroAtivo || passoAtualIndex >= roteiroAtivo.length) {
            roteiroAtivo = null; 
            exibirBalaoAura("Chegámos ao fim do processo! Agora é contigo. ✨", [], true, false);
            return;
        }
        const passo = roteiroAtivo[passoAtualIndex];
        const msgPasso = passo.mensagem || `Siga para o passo ${passoAtualIndex + 1}...`; // Trava anti-crash
        
        exibirBalaoAura(msgPasso, [], true, true); 
        farejarBotao(passo, 0);
    }

// =========================================================
    // 🟢 3. BUSCA COM PACIÊNCIA
    // =========================================================
    function farejarBotao(passo, tentativas) {
        // 🟢 AUMENTAMOS PARA 40 TENTATIVAS (12 Segundos). 
        // Dá tempo de sobra para a animação do menu Angular abrir!
        if (tentativas > 40) {
            exibirBalaoAura("Parece que a página demorou a carregar ou o botão mudou. Queres tentar de novo? 🤔", [], true, false);
            roteiroAtivo = null; 
            return;
        }

        let match = null;
        
        if (passo.elemento_id != null) {
            match = encontrarElementoNaTela(`[data-aura-map="${passo.elemento_id}"]`);
        } 
        
        if (!match && passo.seletor_css) {
            match = encontrarElementoNaTela(passo.seletor_css);
        }

        if (match && match.elemento) {
            let alvo = passo.elemento_id != null ? passo.elemento_id : passo.seletor_css;
            aplicarHolofoteDom(alvo, passo.elemento_id == null); 
            
            match.elemento.addEventListener('click', () => { 
                passoAtualIndex++; 
                // Espera 800ms para a tela nova carregar antes de procurar o próximo botão
                setTimeout(executarPassoAtual, 800); 
            }, { once: true });
            
            // O Piloto Automático está desativado na raiz, mas a lógica de segurança fica aqui
            if (modoPilotoAutomatico && passoAtualIndex < roteiroAtivo.length) { 
                setTimeout(() => { if (roteiroAtivo) match.elemento.click(); }, 2000); 
            }
        } else { 
            // Tenta de novo daqui a 300 milissegundos
            setTimeout(() => farejarBotao(passo, tentativas + 1), 300); 
        }
    }

    // =========================================================
    // ─── COMUNICAÇÃO (Listeners e Disparos)
    // =========================================================
    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        if (event.data.type === "AURA_RESPONSE") {
            const payload = event.data.payload || {};
            _reativarInputs();

            const textoResposta = payload.mensagem || payload.advice || "Desculpe, não consegui processar a resposta.";
            let sugestoes = [];
            if (payload.sugestoes && Array.isArray(payload.sugestoes)) {
                sugestoes = payload.sugestoes.map(s => ({ label: s, action: () => { document.getElementById('aura-sonar-highlight')?.remove(); document.getElementById('aura-backdrop')?.remove(); dispararAnaliseIA(s); } }));
            }

            if (payload.roteiro && Array.isArray(payload.roteiro)) {
                document.getElementById('aura-sonar-highlight')?.remove();
                iniciarRoteiro(payload.roteiro, payload.piloto_automatico === true);
            } else {
                roteiroAtivo = null; 
                exibirBalaoAura(textoResposta, sugestoes, true, false); 
                
                const fbContainer = document.getElementById('aura-feedback-container');
                if (fbContainer) { 
                    fbContainer.classList.add('show-feedback');
                    document.getElementById('aura-feedback-actions').style.display = 'flex'; 
                    document.getElementById('aura-feedback-msg').style.display = 'none'; 
                }

                if (payload.seletor_css) {
                    let matchAlvo = null; try { matchAlvo = encontrarElementoNaTela(payload.seletor_css); } catch(e) {}
                    if (matchAlvo?.elemento) aplicarHolofoteDom(payload.seletor_css, true);
                    else if (payload.elemento_id != null) aplicarHolofoteDom(payload.elemento_id, false);
                } else if (payload.elemento_id != null) { aplicarHolofoteDom(payload.elemento_id, false);
                } else { document.getElementById('aura-sonar-highlight')?.remove(); }
            }
        }
    });

    function dispararAnaliseIA(textoOpcional) {
        const inputEl = document.getElementById('aura-prompt-input'); 
        const btnEnviar = document.getElementById('aura-btn-ask');
        const prompt  = textoOpcional || (inputEl?.value || '').trim() || "O que devo fazer nesta tela?";
        
        if (inputEl)  { inputEl.value = ''; inputEl.disabled = true; } 
        if (btnEnviar) btnEnviar.disabled = true;

        const fbContainer = document.getElementById('aura-feedback-container');
        if (fbContainer) fbContainer.classList.remove('show-feedback');

        const loadingHTML = `<div class="aura-typing-dots"><span></span><span></span><span></span></div>`;
        exibirBalaoAura(loadingHTML, [], false, true); 

        const extratoDOM = capturarDOMParaIA(); const nomeReal = descobrirNomeUsuario();
        window.postMessage({ type: "AURA_CAPTURE", url: window.location.href, prompt: prompt, dom_context: extratoDOM, user_name: nomeReal, tenant_id: "senior_default" }, window.location.origin);
    }

    function _reativarInputs() {
        const inputEl = document.getElementById('aura-prompt-input'); const btnEnviar = document.getElementById('aura-btn-ask');
        if (inputEl) inputEl.disabled = false; if (btnEnviar) btnEnviar.disabled = false; if (inputEl) inputEl.focus();
    }

    if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciarAura); } 
    else { iniciarAura(); }
})();
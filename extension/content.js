// content.js - Interface da Aura (Mundo MAIN) com Olho Biônico e Academia Operacional

(function() {
    console.log("Aura: Iniciando interface...");

    let _bubbleTimeout = null;
    let _jaOfereceuAjudaProativa = false; // 🟢 Controle para o balão não irritar o utilizador

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
                let key = localStorage.key(i);
                if (key.toLowerCase().includes('user') || key.toLowerCase().includes('profile')) {
                    let obj = JSON.parse(localStorage.getItem(key));
                    if (obj && (obj.name || obj.nome || obj.firstName)) {
                        let nomeCompleto = obj.name || obj.nome || obj.firstName;
                        return nomeCompleto.split(' ')[0];
                    }
                }
            }
        } catch (e) { console.warn("Aura: Não foi possível caçar o nome dinâmico."); }

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

        // 🟢 Utilizando a sua classe original .aura-badge do style.css
        auraContainer.innerHTML = `
            <div class="aura-badge" id="aura-notification-badge">1</div>
            <dotlottie-player id="aura-lottie-player" src="chrome-extension://${extensionId}/aura.json" background="transparent" speed="1"></dotlottie-player>
            <div id="aura-speech-bubble">
                <button class="aura-btn-close" id="aura-btn-close" aria-label="Fechar">✕</button>
                <div class="aura-text">Olá, sou a Aura! Como posso te ajudar nesta tela?</div>
                <div class="aura-input-wrapper">
                    <input type="text" id="aura-prompt-input" placeholder="Ex: Como eu crio uma pasta?" autocomplete="off">
                    <button class="aura-btn-send" id="aura-btn-ask">➜</button>
                </div>
                <div class="aura-options"></div>
            </div>
        `;
        document.documentElement.appendChild(auraContainer);

        let isDragging = false, wasDragged = false;
        let startX, startY, initialX, initialY;

        const player = document.getElementById('aura-lottie-player');
        const bubble = document.getElementById('aura-speech-bubble');
        let _animacaoRodando = false;

        function tocarAnimacaoUmaVez() {
            if (_animacaoRodando) return;
            _animacaoRodando = true;
            player.stop();  
            player.play();
        }

        player.addEventListener('complete', () => {
            _animacaoRodando = false;
            player.pause(); 
        });

        player.addEventListener('ready', () => {
            tocarAnimacaoUmaVez();
        });
        
        setTimeout(() => {
            if (!_animacaoRodando) tocarAnimacaoUmaVez();
        }, 400);

        player.addEventListener('mousedown', (e) => {
            isDragging = true;
            wasDragged = false;
            startX = e.clientX;
            startY = e.clientY;
            const rect = auraContainer.getBoundingClientRect();
            initialX = rect.left;
            initialY = rect.top;
            auraContainer.style.left   = initialX + 'px';
            auraContainer.style.top    = initialY + 'px';
            auraContainer.style.right  = 'auto';
            auraContainer.style.bottom = 'auto';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            if (Math.abs(dx) > 3 || Math.abs(dy) > 3) wasDragged = true;

            const maxX = window.innerWidth  - auraContainer.offsetWidth;
            const maxY = window.innerHeight - auraContainer.offsetHeight;

            auraContainer.style.left = Math.max(8, Math.min(initialX + dx, maxX - 8)) + 'px';
            auraContainer.style.top  = Math.max(8, Math.min(initialY + dy, maxY - 8)) + 'px';
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });

        bubble.addEventListener('mousedown', (e) => {
            e.stopPropagation(); 
        });

        player.addEventListener('click', (e) => {
            if (wasDragged) { wasDragged = false; return; }

            tocarAnimacaoUmaVez();
            
            // 🟢 Apaga o badge assim que o utilizador clica
            const badge = document.getElementById('aura-notification-badge');
            if (badge) badge.classList.remove('active');

            if (bubble.classList.contains('active')) {
                bubble.classList.remove('active');
            } else {
                exibirBalaoAura("Precisa de ajuda com esta tela?", []);
            }
        });

        document.getElementById('aura-btn-ask').addEventListener('pointerdown', (e) => {
            e.preventDefault(); e.stopPropagation(); dispararAnaliseIA();
        });
        document.getElementById('aura-prompt-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.stopPropagation(); dispararAnaliseIA(); }
        });

        document.getElementById('aura-btn-close').addEventListener('click', (e) => {
            e.stopPropagation();
            bubble.classList.remove('active');
        });

        document.addEventListener('click', (e) => {
            const bubbleEl = document.getElementById('aura-speech-bubble');
            const container = document.getElementById('aura-floating-container');
            if (!bubbleEl || !container) return;
            if (!container.contains(e.target) && bubbleEl.classList.contains('active')) {
                bubbleEl.classList.remove('active');
            }
        });

        // ─── MOTOR DE PROATIVIDADE (IDLE TIMER) ──────────────────────────────────
        let tempoInativo = 0;
        const TEMPO_LIMITE_SEGUNDOS = 30;
        let _throttleTimer = null;

        function resetarCronometro() {
            if (_throttleTimer) return;
            tempoInativo = 0;
            _throttleTimer = setTimeout(() => { _throttleTimer = null; }, 500);
        }

        document.addEventListener('mousemove', resetarCronometro);
        document.addEventListener('keypress', resetarCronometro);
        document.addEventListener('click',     resetarCronometro);
        document.addEventListener('scroll',    resetarCronometro);

        setInterval(() => {
            tempoInativo++;
            if (tempoInativo === TEMPO_LIMITE_SEGUNDOS) {
                const bubbleElement = document.getElementById('aura-speech-bubble');
                const badgeElement = document.getElementById('aura-notification-badge');
                
                if (bubbleElement && !bubbleElement.classList.contains('active') && !_mission.ativa) {
                    // 🟢 Se ainda não ofereceu o balão nesta tela, abre o balão.
                    if (!_jaOfereceuAjudaProativa) {
                        _jaOfereceuAjudaProativa = true;
                        exibirBalaoAura("Vejo que você parou nesta tela. Precisa de alguma ajuda para continuar? 🤔", [
                            { label: "Sim, me ajude",  action: () => dispararAnaliseIA("O que devo fazer nesta tela?") },
                            { label: "Não, obrigado",  action: () => { bubbleElement.classList.remove('active'); resetarCronometro(); } }
                        ]);
                    } else {
                        // 🟢 Se já ofereceu, acende APENAS o badge vermelho silenciosamente.
                        if (badgeElement) badgeElement.classList.add('active');
                    }
                }
            }
        }, 1000);

        // ─── GATILHO PUSH (MAGIC LINK CORPORATIVO) ───────────────────────────────
        const urlParams = new URLSearchParams(window.location.search);
        const missionToLoad = urlParams.get('aura_mission');
        if (missionToLoad) {
            console.log("Aura: Magic Link detectado. Solicitando missão: ", missionToLoad);
            window.postMessage({ type: "AURA_FETCH_MISSION", mission_id: missionToLoad }, window.location.origin);
            
            const baseUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
            const hash = window.location.hash; 
            window.history.replaceState({path: baseUrl + hash}, '', baseUrl + hash);
        }

        let urlAtual = window.location.href;
        let _spaDebounce = null;
        const observerSPA = new MutationObserver(() => {
            if (_spaDebounce) return;
            _spaDebounce = setTimeout(() => {
                _spaDebounce = null;
                if (urlAtual !== window.location.href) {
                    urlAtual = window.location.href;
                    console.log("Aura: Troca de tela Angular detetada. Limpando contexto antigo...");
                    
                    // 🟢 Reseta a memória proativa ao mudar de ecrã (nova tela, nova oportunidade de ajudar)
                    _jaOfereceuAjudaProativa = false;
                    
                    document.getElementById('aura-sonar-highlight')?.remove();
                    document.getElementById('aura-backdrop')?.remove();
                    const bubbleEl = document.getElementById('aura-speech-bubble');
                    if (bubbleEl?.classList.contains('active') && !_mission.ativa) {
                        exibirBalaoAura(`Olá, ${descobrirNomeUsuario()}! Precisa de ajuda nesta nova tela?`, []);
                    }
                }
            }, 300);
        });
        observerSPA.observe(document.body, { childList: true, subtree: true });

        document.getElementById('aura-prompt-input').addEventListener('focus', () => {
            window.postMessage({ type: "AURA_PRE_CAPTURE" }, window.location.origin);
        });
    }

    let _ultimoPromptParaFeedback = '';

    function exibirBalaoAura(texto, opcoes = [], mostrarFeedback = false) {
        const bubble = document.getElementById('aura-speech-bubble');
        const badge = document.getElementById('aura-notification-badge');
        if (!bubble) return;

        clearTimeout(_bubbleTimeout);
        // Esconde a notificação se o balão abriu
        if (badge) badge.classList.remove('active');

        bubble.querySelector('.aura-text').innerText = texto;
        const optDiv = bubble.querySelector('.aura-options');
        optDiv.innerHTML = '';

        bubble.querySelector('.aura-feedback-bar')?.remove();
        if (mostrarFeedback) {
            const fb = _criarBarraFeedback(_ultimoPromptParaFeedback, texto);
            optDiv.parentNode.insertBefore(fb, optDiv);
        }

        opcoes.forEach(opt => {
            const btn = document.createElement('button');
            btn.className = 'aura-btn';
            btn.innerText = opt.label;
            btn.addEventListener('click', (e) => { e.stopPropagation(); opt.action(); });
            optDiv.appendChild(btn);
        });

        bubble.classList.add('active');

        // 🟢 AUTO-HIDE com Notificação: Recolhe o balão em 12s e acende o badge
        _bubbleTimeout = setTimeout(() => {
            if (bubble.classList.contains('active')) {
                bubble.classList.remove('active');
                if (badge && !_mission.ativa) {
                    badge.classList.add('active');
                }
            }
        }, 12000);
    }

    // =========================================================
    // 👁️ O OLHO BIÔNICO DA AURA
    // =========================================================

    function capturarDOMParaIA() {
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
        let domList = [];
        let elementosMapeados = new Set();

        elementos.forEach((el, index) => {
            if (auraContainer && auraContainer.contains(el)) return;
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
        });

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
            } catch (e) {}
        }
        return null;
    }

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

    function aplicarHolofoteDom(auraIdOuSeletor, isSeletor = false) {
        document.getElementById('aura-sonar-highlight')?.remove();
        document.getElementById('aura-backdrop')?.remove();
        
        if (!auraIdOuSeletor) return;

        let match = isSeletor ? encontrarElementoNaTela(auraIdOuSeletor) : encontrarElementoNaTela(`[data-aura-map="${auraIdOuSeletor}"]`);
        if (!match || !match.elemento) return;

        const el = match.elemento;
        const frame = match.frame;

        el.scrollIntoView({ behavior: 'smooth', block: 'center' });

        setTimeout(() => {
            const rect = el.getBoundingClientRect();
            let fTop = 0, fLeft = 0;
            if (frame) {
                const fRect = frame.getBoundingClientRect();
                fTop = fRect.top; fLeft = fRect.left;
            }

            criarBackdrop(rect, fTop, fLeft);

            const highlight = document.createElement('div');
            highlight.id = 'aura-sonar-highlight';
            const top = rect.top + fTop + window.scrollY;
            const left = rect.left + fLeft + window.scrollX;

            highlight.style.cssText = `
                position: absolute;
                top: ${top - 6}px; left: ${left - 6}px;
                width: ${rect.width + 12}px; height: ${rect.height + 12}px;
                border: 4px solid #00E676; border-radius: 8px;
                box-shadow: 0 0 20px #00E676, inset 0 0 10px #00E676;
                z-index: 999999; pointer-events: none;
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

    // ─── LISTENER DE MENSAGENS (AURA_RESPONSE e MISSIONS) ───────────────────────
    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;

        if (event.data.type === "AURA_FETCH_MISSION_RESPONSE") {
            const data = event.data.payload;
            if (!data || data.erro) {
                console.error("Aura: Falha ao carregar missão via link.", data?.erro);
                exibirBalaoAura("Não consegui carregar os dados desta certificação. Verifique se o servidor está online.", []);
                return;
            }
            iniciarMissao(data);
            return;
        }

        if (event.data.type === "AURA_RESPONSE") {
            const payload = event.data.payload || {};
            _reativarInputs();
            const textoResposta = payload.mensagem || payload.advice || "Desculpe, não consegui processar a resposta.";

            let sugestoes = [];
            if (payload.sugestoes && Array.isArray(payload.sugestoes)) {
                sugestoes = payload.sugestoes.map(s => ({
                    label: s,
                    action: () => {
                        document.getElementById('aura-sonar-highlight')?.remove();
                        document.getElementById('aura-backdrop')?.remove();
                        dispararAnaliseIA(s);
                    }
                }));
            }

            const temGPS = payload.gps_passos && Array.isArray(payload.gps_passos) && payload.gps_passos.length > 0;

            if (temGPS) {
                const missionDataAdapter = {
                    title: payload.gps_nome_aula || "Simulação Assistida",
                    scoring: { base_xp: 100, no_help_bonus: 50, error_penalty: 15 },
                    steps: payload.gps_passos.map((p, i) => ({
                        intent: p.tooltip || p.ancora || "Avance para o próximo passo",
                        validation: { target_selector: p.seletor },
                        timeout_for_hint_sec: 12,
                        xp_penalty_per_hint: 15
                    }))
                };

                const gpsOpcoes = [
                    {
                        label: 'Iniciar Simulação Prática',
                        action: () => {
                            document.getElementById('aura-sonar-highlight')?.remove();
                            document.getElementById('aura-backdrop')?.remove();
                            iniciarMissao(missionDataAdapter);
                        }
                    },
                    ...sugestoes.slice(0, 1)
                ];
                exibirBalaoAura(textoResposta, gpsOpcoes, true);
            } else {
                exibirBalaoAura(textoResposta, sugestoes, true);

                if (payload.seletor_css) {
                    document.getElementById('aura-sonar-highlight')?.remove();
                    let matchAlvo = null;
                    try { matchAlvo = encontrarElementoNaTela(payload.seletor_css); }
                    catch(e) {}

                    if (matchAlvo?.elemento) {
                        aplicarHolofoteDom(payload.seletor_css, true);
                    } else {
                        if (payload.elemento_id != null) aplicarHolofoteDom(payload.elemento_id, false);
                    }
                } else if (payload.elemento_id != null) {
                    aplicarHolofoteDom(payload.elemento_id, false);
                }
            }
        }

        if (event.data.type === "AURA_GPS_RESPONSE") {
            const d = event.data.payload || {};
            if (d.status === 'sucesso' && d.passos?.length) {
                const missionDataAdapter = {
                    title: d.nome_aula || "Simulação Assistida",
                    scoring: { base_xp: 100, no_help_bonus: 50, error_penalty: 15 },
                    steps: d.passos.map((p) => ({
                        intent: p.tooltip || p.ancora || "Avance para o próximo passo",
                        validation: { target_selector: p.seletor },
                        timeout_for_hint_sec: 12,
                        xp_penalty_per_hint: 15
                    }))
                };
                iniciarMissao(missionDataAdapter);
            } else {
                exibirBalaoAura('Não encontrei uma missão para isso. Tente descrever o objetivo com mais detalhes.', []);
            }
        }
    });

    function dispararAnaliseIA(textoOpcional) {
        const inputEl = document.getElementById('aura-prompt-input');
        const btnEnviar = document.getElementById('aura-btn-ask');
        const prompt  = textoOpcional || (inputEl?.value || '').trim() || "O que devo fazer nesta tela?";

        if (inputEl)  { inputEl.value = ''; inputEl.disabled = true; }
        if (btnEnviar) btnEnviar.disabled = true;

        exibirBalaoAura("Já estou analisando... Só um momento! 🔍", []);

        const extratoDOM = capturarDOMParaIA();
        const nomeReal   = descobrirNomeUsuario();

        _ultimoPromptParaFeedback = prompt;
        window.postMessage({
            type:        "AURA_CAPTURE",
            url:         window.location.href,
            prompt:      prompt,
            dom_context: extratoDOM,
            user_name:   nomeReal,
            tenant_id:   "senior_default"
        }, window.location.origin);
    }

    function _reativarInputs() {
        const inputEl   = document.getElementById('aura-prompt-input');
        const btnEnviar = document.getElementById('aura-btn-ask');
        if (inputEl)   inputEl.disabled   = false;
        if (btnEnviar) btnEnviar.disabled = false;
        if (inputEl)   inputEl.focus();
    }


// ════════════════════════════════════════════════════════════════════
// MÓDULO ACADEMIA OPERACIONAL — Simulador Prático e Certificação
// ════════════════════════════════════════════════════════════════════

const _mission = {
    ativa: false,
    dados: null,
    idx: 0,
    xpAtual: 0,
    timerOciosidade: null,
    dicaUsadaNoPasso: false,
    _listenerClick: null,
    _urlWatcher: null
};

function _criarHudMissao() {
    document.getElementById('aura-mission-hud')?.remove();
    const hud = document.createElement('div');
    hud.id = 'aura-mission-hud';
    hud.style.cssText = `
        position: fixed; top: 20px; left: 50%; transform: translateX(-50%);
        background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 12px;
        padding: 14px 24px; z-index: 2147483647; color: white; font-family: sans-serif;
        box-shadow: 0 10px 40px rgba(0,0,0,0.5); display: flex; flex-direction: column; gap: 8px;
        min-width: 350px; transition: all 0.3s;
    `;
    
    hud.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; font-size:12px; color:#94a3b8;">
            <span style="text-transform:uppercase; font-weight:bold; letter-spacing:1px; color:#0ea5e9;">Simulação Operacional</span>
            <span id="mission-xp-display" style="font-weight:bold; color:#22c55e;">XP: 0</span>
        </div>
        <div id="mission-intent" style="font-size:16px; font-weight:500;">Aguarde...</div>
        <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
            <div id="mission-progress-dots" style="display:flex; gap:4px;"></div>
            <button id="btn-pedir-ajuda" style="background:rgba(245,158,11,0.2); border:1px solid #f59e0b; color:#fbbf24; border-radius:6px; padding:4px 8px; font-size:11px; cursor:pointer; transition:all 0.2s;">
                Preciso de Ajuda
            </button>
            <button id="btn-sair-missao" style="background:none; border:none; color:#ef4444; font-size:11px; cursor:pointer;">Abandonar</button>
        </div>
    `;
    
    document.documentElement.appendChild(hud);

    document.getElementById('btn-sair-missao').addEventListener('click', pararMissao);
    document.getElementById('btn-pedir-ajuda').addEventListener('click', () => { _exibirDica(true); });
}

function _atualizarHudMissao() {
    const hud = document.getElementById('aura-mission-hud');
    if (!hud || !_mission.dados) return;

    const passo = _mission.dados.steps[_mission.idx];
    document.getElementById('mission-intent').textContent = passo.intent;
    
    const xpEl = document.getElementById('mission-xp-display');
    xpEl.textContent = `XP: ${_mission.xpAtual}`;
    xpEl.style.transform = 'scale(1.1)';
    setTimeout(() => xpEl.style.transform = 'scale(1)', 300);

    const dots = document.getElementById('mission-progress-dots');
    dots.innerHTML = _mission.dados.steps.map((_, i) => `
        <div style="width:8px; height:8px; border-radius:50%; background:${i < _mission.idx ? '#22c55e' : (i === _mission.idx ? '#0ea5e9' : 'rgba(255,255,255,0.2)')};
        box-shadow:${i === _mission.idx ? '0 0 8px #0ea5e9' : 'none'}; transition:all 0.3s;"></div>
    `).join('');
}

function _exibirDica(forcadoPeloUsuario = false) {
    if (!_mission.ativa || _mission.dicaUsadaNoPasso) return;
    
    _mission.dicaUsadaNoPasso = true;
    const passo = _mission.dados.steps[_mission.idx];
    
    _mission.xpAtual = Math.max(0, _mission.xpAtual - (passo.xp_penalty_per_hint || 15));
    _atualizarHudMissao();

    exibirBalaoAura(forcadoPeloUsuario ? "Sem problemas, eu mostro o caminho!" : "Parece que você travou. Veja a dica na tela!", []);
    aplicarHolofoteDom(passo.validation?.target_selector, true);
}

function _iniciarPassoAtual() {
    if (!_mission.ativa) return;
    
    _mission.dicaUsadaNoPasso = false;
    document.getElementById('aura-sonar-highlight')?.remove();
    document.getElementById('aura-backdrop')?.remove();
    clearTimeout(_mission.timerOciosidade);

    const passo = _mission.dados.steps[_mission.idx];
    _atualizarHudMissao();

    const tempoLimite = (passo.timeout_for_hint_sec || 12) * 1000;
    _mission.timerOciosidade = setTimeout(() => { _exibirDica(false); }, tempoLimite);

    if (_mission._listenerClick) document.removeEventListener('click', _mission._listenerClick, true);
    
    _mission._listenerClick = (e) => {
        const seletor = passo.validation?.target_selector;
        if (!seletor) { setTimeout(_avancarMissao, 600); return; }

        const match = encontrarElementoNaTela(seletor);
        const elAlvo = match ? match.elemento : null;

        if (elAlvo && (elAlvo.contains(e.target) || elAlvo === e.target)) {
            clearTimeout(_mission.timerOciosidade);
            setTimeout(_avancarMissao, 600);
        }
    };
    
    document.addEventListener('click', _mission._listenerClick, true);
}

function _avancarMissao() {
    if (!_mission.ativa) return;
    _mission.idx++;

    if (_mission.idx >= _mission.dados.steps.length) {
        _finalizarMissaoComSucesso();
    } else {
        _iniciarPassoAtual();
    }
}

function iniciarMissao(missionData) {
    if (!missionData || !missionData.steps || missionData.steps.length === 0) return;
    
    pararMissao();
    _mission.ativa = true;
    _mission.dados = missionData;
    _mission.idx = 0;
    _mission.xpAtual = missionData.scoring?.base_xp || 100;

    _criarHudMissao();
    
    exibirBalaoAura(`Iniciando certificação: ${missionData.title}. O seu objetivo aparece no topo da tela. Boa sorte!`, [
        { label: 'Começar', action: () => document.getElementById('aura-speech-bubble')?.classList.remove('active') }
    ]);

    _iniciarPassoAtual();

    let _lastUrl = window.location.href;
    _mission._urlWatcher = new MutationObserver(() => {
        if (!_mission.ativa) return;
        const current = window.location.href;
        if (current !== _lastUrl) {
            _lastUrl = current;
            setTimeout(() => {
                const passo = _mission.dados.steps[_mission.idx];
                const seletor = passo?.validation?.target_selector;
                if (seletor && !encontrarElementoNaTela(seletor)) {
                     _avancarMissao();
                }
            }, 1200); 
        }
    });
    _mission._urlWatcher.observe(document.body, { childList: true, subtree: true });
}

function _finalizarMissaoComSucesso() {
    const bonus = _mission.xpAtual === (_mission.dados.scoring?.base_xp || 100) ? (_mission.dados.scoring?.no_help_bonus || 50) : 0;
    const xpFinal = _mission.xpAtual + bonus;
    
    pararMissao(false);

    const msg = bonus > 0 
        ? `🏆 Incrível! Você completou a simulação com 100% de autonomia e ganhou um bônus perfeito! Total: ${xpFinal} XP.`
        : `✅ Simulação concluída! Você provou a sua capacidade de operar este fluxo e conquistou ${xpFinal} XP.`;

    exibirBalaoAura(msg, [
        { label: 'Fechar Aba', action: () => document.getElementById('aura-speech-bubble')?.classList.remove('active') }
    ]);
}

function pararMissao(fecharBalao = true) {
    _mission.ativa = false;
    clearTimeout(_mission.timerOciosidade);
    if (_mission._listenerClick) document.removeEventListener('click', _mission._listenerClick, true);
    if (_mission._urlWatcher) { _mission._urlWatcher.disconnect(); _mission._urlWatcher = null; }
    
    document.getElementById('aura-sonar-highlight')?.remove();
    document.getElementById('aura-backdrop')?.remove();
    document.getElementById('aura-mission-hud')?.remove();
    
    if (fecharBalao) {
        document.getElementById('aura-speech-bubble')?.classList.remove('active');
    }
}

    // ════════════════════════════════════════════════════════════════════
    // MÓDULO FEEDBACK
    // ════════════════════════════════════════════════════════════════════
    function _criarBarraFeedback(prompt, resposta) {
        const bar = document.createElement('div');
        bar.className = 'aura-feedback-bar';

        const like    = document.createElement('button');
        like.className = 'aura-fb-btn';
        like.title     = 'Isso ajudou';
        like.textContent = '👍';

        const dislike    = document.createElement('button');
        dislike.className = 'aura-fb-btn';
        dislike.title     = 'Não ajudou';
        dislike.textContent = '👎';

        bar.appendChild(like);
        bar.appendChild(dislike);

        const _registrar = (tipo, btn) => {
            like.disabled = dislike.disabled = true;
            btn.classList.add(tipo === 'like' ? 'voted-yes' : 'voted-no');
            try {
                const key = `aura_fb_${Date.now()}`;
                localStorage.setItem(key, JSON.stringify({
                    tipo, prompt: (prompt||'').substring(0,100),
                    url: window.location.href, ts: Date.now()
                }));
            } catch(e) {}
            setTimeout(() => { bar.style.opacity = '0'; }, 350);
            setTimeout(() => { bar.remove(); }, 850);
        };

        like.addEventListener('click',    (e) => { e.stopPropagation(); _registrar('like', like); });
        dislike.addEventListener('click', (e) => { e.stopPropagation(); _registrar('dislike', dislike); });

        return bar;
    }

    // ═══════════════════════════════════════════════════════════════════
    // GUARDIÃO DE LOGIN
    // ═══════════════════════════════════════════════════════════════════
    let _auraInicializada = false;

    function _estaLogado() {
        if (/\/login|\/auth|\/signin|\/sso/i.test(window.location.href)) return false;
        const campoSenha = document.querySelector('input[type="password"]');
        if (campoSenha && campoSenha.offsetParent !== null) return false;
        try {
            for (const st of [sessionStorage, localStorage]) {
                for (let i = 0; i < st.length; i++) {
                    if (/token|auth|session|jwt|bearer|access/i.test(st.key(i) || '')) return true;
                }
            }
        } catch(e) {}
        const outlet = document.querySelector('router-outlet');
        if (outlet && outlet.nextElementSibling) return true;
        const appRoot = document.querySelector('app-root, platform-root, senior-root');
        if (appRoot && appRoot.children.length > 1) return true;
        return ['p-breadcrumb', 'p-menubar', '[aria-label*="Grupo de menus"]',
                '[class*="user-name"]', '.senior-header']
               .some(sel => document.querySelector(sel) !== null);
    }

    function _tentarIniciarAura() {
        if (_auraInicializada) return;
        if (_estaLogado()) {
            _auraInicializada = true;
            console.log("Aura: Login detectado. Inicializando assistente...");
            iniciarAura();
        }
    }

    function _aguardarLogin() {
        _tentarIniciarAura();
        if (_auraInicializada) return;
        const _pollTimer = setInterval(() => {
            if (_auraInicializada) { clearInterval(_pollTimer); return; }
            _tentarIniciarAura();
        }, 500);

        let _throttle = null;
        const observer = new MutationObserver(() => {
            if (_auraInicializada) { observer.disconnect(); return; }
            if (_throttle) return;
            _throttle = setTimeout(() => {
                _throttle = null;
                _tentarIniciarAura();
                if (_auraInicializada) {
                    observer.disconnect();
                    clearInterval(_pollTimer);
                }
            }, 100);
        });
        observer.observe(document.documentElement, { childList: true, subtree: true });

        setTimeout(() => {
            if (_auraInicializada) return;
            console.log("Aura: Timeout atingido — inicializando por precaução.");
            observer.disconnect();
            clearInterval(_pollTimer);
            _auraInicializada = true;
            iniciarAura();
        }, 30_000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _aguardarLogin);
    } else {
        _aguardarLogin();
    }
})();
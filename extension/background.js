console.log("Aura: Service Worker iniciado.");

let cachedScreenshot = null; // 🟢 Guarda a foto antecipada

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    // 🟢 Escuta o gatilho de Pre-Capture (Quando o utilizador clica no input)
    if (request.action === "pre_capture") {
        chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
            if (!chrome.runtime.lastError) {
                cachedScreenshot = dataUrl;
                console.log("Aura: Pre-capture concluído. Imagem pronta na agulha.");
            }
        });
        return true;
    }

    if (request.action !== "analisar_agora") return false;

    console.log("Aura: Análise final solicitada para:", request.url);

    try {
        // Função de disparo para a API
        const dispararParaPython = (imagemB64) => {
            fetch("http://localhost:8000/analyze", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    // 🟢 Sprint 2: Crachá de Identidade (Proteção contra ataques)
                    "Authorization": "Bearer senior_training_secreto_2026" 
                },
                body: JSON.stringify({
                    image: imagemB64,
                    url: request.url,
                    prompt: request.prompt || "O que devo fazer nesta tela?",
                    dom_context: request.dom_context || "", 
                    user_name: request.user_name || "Utilizador",
                    tenant_id: request.tenant_id || "senior_default",
                    // 🟢 Sprint 1: Memória de Contexto (Passa a janela deslizante de mensagens)
                    historico: request.historico || [] 
                })
            })
            .then(res => res.json())
            .then(data => sendResponse(data))
            .catch(err => sendResponse({ mensagem: `Erro de conexão: ${err.message}` }));
        };

        // 🟢 ZERO-LATENCY: Se já temos a foto em cache (porque ele clicou no input antes), usa-a imediatamente!
        if (cachedScreenshot) {
            console.log("Aura: Usando Screenshot do Cache! Ganhámos 500ms.");
            dispararParaPython(cachedScreenshot);
            cachedScreenshot = null; // Limpa o cache para a próxima
        } else {
            // Se o utilizador foi muito rápido, tira a foto na hora (Plano B)
            setTimeout(() => {
                chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
                    if (chrome.runtime.lastError) {
                        sendResponse({ mensagem: "Não consegui capturar a tela." });
                        return;
                    }
                    dispararParaPython(dataUrl);
                });
            }, 300);
        }

    } catch (err) {
        sendResponse({ mensagem: "Falha na extensão: " + err.message });
    }

    return true; 
});
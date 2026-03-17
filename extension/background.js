console.log("Aura: Service Worker iniciado.");

let cachedScreenshot = null; 
let cacheTimestamp = 0; // 🟢 Controla a validade da foto

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    // 🟢 Escuta o gatilho de Pre-Capture
    if (request.action === "pre_capture") {
        chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
            if (!chrome.runtime.lastError) {
                cachedScreenshot = dataUrl;
                cacheTimestamp = Date.now(); // Marca a hora exata da foto
                console.log("Aura: Pre-capture concluído. Imagem pronta na agulha.");
            }
            // 🟢 FIX: OBRIGATÓRIO avisar ao Chrome que terminamos para não estourar a porta
            sendResponse({ status: "ok" }); 
        });
        return true; 
    }

    if (request.action !== "analisar_agora") return false;

    console.log("Aura: Análise final solicitada para:", request.url);

    try {
        const dispararParaPython = (imagemB64) => {
            fetch("http://localhost:8000/analyze", {
                method: "POST",
                headers: { 
                    "Content-Type": "application/json",
                    "Authorization": "Bearer senior_training_secreto_2026" 
                },
                body: JSON.stringify({
                    image: imagemB64,
                    url: request.url,
                    prompt: request.prompt || "O que devo fazer nesta tela?",
                    dom_context: request.dom_context || "", 
                    user_name: request.user_name || "Utilizador",
                    tenant_id: request.tenant_id || "senior_default",
                    historico: request.historico || [] 
                })
            })
            .then(res => res.json())
            .then(data => sendResponse(data))
            .catch(err => sendResponse({ mensagem: `Erro de conexão: ${err.message}` }));
        };

        // 🟢 FIX: Verifica se temos cache E se a foto foi tirada há menos de 5 segundos (5000ms)
        const isCacheValid = cachedScreenshot && (Date.now() - cacheTimestamp < 5000);

        if (isCacheValid) {
            console.log("Aura: Usando Screenshot do Cache! Ganhámos 500ms.");
            dispararParaPython(cachedScreenshot);
            cachedScreenshot = null; 
        } else {
            if (cachedScreenshot) console.log("Aura: Cache expirado (foto velha). Capturando nova tela...");
            
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
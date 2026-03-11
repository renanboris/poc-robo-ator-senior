// background.js - O Cérebro da Aura (100% PT-BR e Captura Blindada)
console.log("Aura: Service Worker iniciado.");

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    if (request.action !== "analisar_agora") return false;

    console.log("Aura: Análise solicitada para:", request.url);

    try {
        // Delay de 400ms para garantir que animações da tela pararam
        setTimeout(() => {
            // Passar "null" força o Chrome a usar a janela focada automaticamente
            chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
                
                if (chrome.runtime.lastError) {
                    console.error("Aura Captura Erro:", chrome.runtime.lastError.message);
                    sendResponse({ 
                        advice: "Não consegui capturar a tela. Lembre-se: não funciono em páginas protegidas do Google (como nova guia ou configurações). Vá para o sistema da Senior!" 
                    });
                    return;
                }

                // Dispara para o nosso Training OS
                fetch("http://localhost:8000/analyze", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        image: dataUrl,
                        url: request.url,
                        prompt: request.prompt || "O que devo fazer nesta tela?"
                    })
                })
                .then(res => {
                    if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
                    return res.json();
                })
                .then(data => {
                    console.log("Aura: Resposta recebida do Training OS", data);
                    sendResponse(data);
                })
                .catch(err => {
                    console.error("Aura Fetch Error:", err);
                    sendResponse({ 
                        advice: `Não consegui conectar ao Training OS. O seu terminal com 'python app.py' está rodando?\n\nErro: ${err.message}` 
                    });
                });
            });
        }, 400);
    } catch (err) {
        sendResponse({ advice: "Falha crítica na extensão: " + err.message });
    }

    return true; 
});
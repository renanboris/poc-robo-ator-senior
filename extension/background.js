console.log("Aura: Service Worker iniciado.");

let cachedScreenshot = null; 

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    if (request.action === "pre_capture") {
        chrome.tabs.captureVisibleTab(null, { format: 'png' }, (dataUrl) => {
            if (!chrome.runtime.lastError) {
                cachedScreenshot = dataUrl;
                console.log("Aura: Pre-capture concluído. Imagem pronta na agulha.");
            }
        });
        return true;
    }

    if (request.action === "buscar_gps") {
        fetch(
            `http://localhost:8000/api/gps-roteiro?objetivo=${encodeURIComponent(request.objetivo || '')}&tenant_id=${request.tenant_id || 'senior_default'}`,
            { headers: { "Authorization": "Bearer senior_training_secreto_2026" } }
        )
        .then(r => r.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ status: 'erro', mensagem: err.message }));
        return true;
    }

    // 🟢 NOVO: Busca Missão no Python (Chamado pelo Magic Link do bridge.js)
    if (request.action === "fetch_mission") {
        fetch(`http://localhost:8000/api/missoes/${encodeURIComponent(request.mission_id.replace('.json', ''))}`)
        .then(r => r.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ erro: err.message }));
        return true;
    }

    if (request.action !== "analisar_agora") return false;

    console.log("Aura: Análise final solicitada para:", request.url);

    try {
        const dispararParaPython = (imagemB64) => {
            // MANTIDO: Lógica de Regex para otimizar chamada de GPS!
            const promptLimpo = (request.prompt || '').trim();
            const temIntencaoGPS = /criar|acessar|navegar|abrir|configurar|cadastrar|adicionar|editar|excluir|onde|como\s+(faço|eu|posso)|me\s+(mostre|leve|guie)/i.test(promptLimpo);
            const objetivoGPS   = promptLimpo.substring(0, 120);

            const gpsPromise = temIntencaoGPS
                ? fetch(
                    `http://localhost:8000/api/gps-roteiro?objetivo=${encodeURIComponent(objetivoGPS)}&tenant_id=${request.tenant_id || 'senior_default'}`,
                    { headers: { "Authorization": "Bearer senior_training_secreto_2026" } }
                  ).then(r => r.json()).catch(() => null)
                : Promise.resolve(null);

            const analyzePromise = fetch("http://localhost:8000/analyze", {
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
            }).then(res => res.json());

            Promise.all([analyzePromise, gpsPromise])
                .then(([data, gpsData]) => {
                    if (gpsData?.status === 'sucesso' && gpsData.passos?.length >= 2) {
                        data.gps_passos    = gpsData.passos;
                        data.gps_nome_aula = gpsData.nome_aula;
                    }
                    sendResponse(data);
                })
                .catch(err => sendResponse({ mensagem: `Erro de conexão: ${err.message}` }));
        };

        if (cachedScreenshot) {
            console.log("Aura: Usando Screenshot do Cache! Ganhámos 500ms.");
            dispararParaPython(cachedScreenshot);
            cachedScreenshot = null; 
        } else {
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
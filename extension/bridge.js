// bridge.js - A Ponte Veloz (Mundo MAIN)
// ✅ MANTIDO: Handler de AURA_PRE_CAPTURE e repasse do "historico" para a IA
// ✅ ADICIONADO: Ponte para AURA_FETCH_MISSION (Contorna CORS)

(function() {
    document.documentElement.setAttribute('data-aura-id', chrome.runtime.id);
    console.log("Aura Bridge: ID da extensão ancorado no DOM.");

    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        if (!event.data) return;

        if (!chrome?.runtime?.id) {
            console.warn("Aura Bridge: A extensão foi recarregada. Por favor, dê um F5 na página.");
            return;
        }

        if (event.data.type === "AURA_PRE_CAPTURE") {
            try {
                chrome.runtime.sendMessage({ action: "pre_capture" }, () => {
                    const err = chrome.runtime.lastError; 
                });
                console.log("Aura Bridge: Pre-capture solicitado ao background.");
            } catch (err) {
                console.warn("Aura Bridge: Falha ao solicitar pre-capture:", err.message);
            }
            return;
        }

        // 🟢 PONTE PARA ANALYTICS EVENTS
        if (event.data.type === "AURA_ANALYTICS_EVENT") {
            chrome.runtime.sendMessage({ action: "analytics_event", payload: event.data.payload }, () => {
                const err = chrome.runtime.lastError;
                if (err) console.warn("Aura Bridge: Falha ao enviar analytics_event:", err.message);
            });
            return;
        }

        // 🟢 PONTE PARA FEEDBACK EVENTS
        if (event.data.type === "AURA_FEEDBACK_EVENT") {
            chrome.runtime.sendMessage(
                { action: "feedback_event", payload: event.data.payload },
                () => {
                    const err = chrome.runtime.lastError;
                    if (err) console.warn("Aura Bridge: Falha ao enviar feedback_event:", err.message);
                }
            );
            return;
        }

        // 🟢 PONTE PARA BUSCAR MISSÕES (Magic Link)
        if (event.data.type === "AURA_FETCH_MISSION") {
            chrome.runtime.sendMessage({ action: "fetch_mission", mission_id: event.data.mission_id }, (response) => {
                window.postMessage({
                    type: "AURA_FETCH_MISSION_RESPONSE",
                    payload: response
                }, window.location.origin);
            });
            return;
        }

        // 🟢 PONTE PARA GPS EXPLÍCITO (Magic Link ?aura_gps=)
        if (event.data.type === "AURA_FETCH_GPS") {
            chrome.runtime.sendMessage({
                action:    "fetch_gps_explicit",
                objetivo:  event.data.objetivo || "",
                tenant_id: event.data.tenant_id || "senior_default"
            }, (response) => {
                const err = chrome.runtime.lastError;
                if (err) {
                    console.warn("Aura Bridge: Falha ao buscar GPS:", err.message);
                    window.postMessage({
                        type: "AURA_GPS_EXPLICIT_RESPONSE",
                        payload: { status: "erro", mensagem: err.message }
                    }, window.location.origin);
                    return;
                }
                window.postMessage({
                    type: "AURA_GPS_EXPLICIT_RESPONSE",
                    payload: response
                }, window.location.origin);
            });
            return;
        }

        if (event.data.type !== "AURA_CAPTURE") return;

        try {
            chrome.runtime.sendMessage({
                action:      "analisar_agora",
                url:         event.data.url,
                prompt:      event.data.prompt      || "O que devo fazer nesta tela?",
                dom_context: event.data.dom_context || "",
                user_name:   event.data.user_name   || "Utilizador",
                tenant_id:   event.data.tenant_id   || "senior_default",
                historico:   event.data.historico   || [] 
            }, (response) => {

                if (chrome.runtime.lastError) {
                    console.warn("Aura Bridge Erro:", chrome.runtime.lastError.message);
                    window.postMessage({
                        type: "AURA_RESPONSE",
                        payload: { mensagem: "A Aura está acordando... Tente de novo em um segundo! 🔄" }
                    }, window.location.origin);
                    return;
                }

                if (!response) {
                    console.warn("Aura Bridge: Resposta undefined recebida.");
                    window.postMessage({
                        type: "AURA_RESPONSE",
                        payload: { mensagem: "Hum, não recebi resposta do cérebro. O servidor Python está ligado? 🤔" }
                    }, window.location.origin);
                    return;
                }

                window.postMessage({
                    type: "AURA_RESPONSE",
                    payload: response
                }, window.location.origin);
            });
        } catch (err) {
            console.error("Aura Bridge Crash:", err);
            window.postMessage({
                type: "AURA_RESPONSE",
                payload: { mensagem: "Erro interno de comunicação na extensão. Dê um F5 na página." }
            }, window.location.origin);
        }
    });
})();
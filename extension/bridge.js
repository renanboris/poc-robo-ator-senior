// bridge.js - A Ponte Veloz (Mundo ISOLATED)

(function() {
    document.documentElement.setAttribute('data-aura-id', chrome.runtime.id);
    console.log("Aura Bridge: ID da extensão ancorado no DOM.");

    window.addEventListener("message", (event) => {
        if (event.origin !== window.location.origin) return;
        if (!event.data || event.data.type !== "AURA_CAPTURE") return;

        try {
            chrome.runtime.sendMessage({
                action: "analisar_agora",
                url:    event.data.url,
                prompt: event.data.prompt || "O que devo fazer nesta tela?"
            }, (response) => {
                
                if (chrome.runtime.lastError) {
                    console.warn("Aura Bridge Erro:", chrome.runtime.lastError.message);
                    window.postMessage({
                        type: "AURA_RESPONSE",
                        payload: { advice: "A Aura está acordando... Tente de novo em um segundo! 🔄" }
                    }, window.location.origin);
                    return;
                }

                if (!response) {
                    console.warn("Aura Bridge: Resposta undefined recebida.");
                    window.postMessage({
                        type: "AURA_RESPONSE",
                        payload: { advice: "Hum, não recebi resposta do cérebro. O servidor Python está ligado? 🤔" }
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
                payload: { advice: "Erro interno de comunicação na extensão." }
            }, window.location.origin);
        }
    });
})();
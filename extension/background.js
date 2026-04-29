console.log("Aura: Service Worker iniciado.");

// Carrega aura_config.js que define AURA_CONFIG com token e endpoints.
// Em MV3 service workers, importScripts é a forma de carregar scripts adicionais.
try {
  importScripts('aura_config.js');
} catch (e) {
  console.warn('[Aura BG] aura_config.js não encontrado — usando configuração padrão de localhost.');
}

// ─── CONFIGURAÇÃO ─────────────────────────────────────────────────────────────
// Lê AURA_CONFIG definido em aura_config.js (carregado antes via manifest.json).
// Se não estiver definido, usa fallback para localhost sem token.
var _cfg = (typeof AURA_CONFIG !== 'undefined') ? AURA_CONFIG : {};
var _cfgEndpoints = (_cfg && _cfg.endpoints) ? _cfg.endpoints : {};

const AURA_AUTH_TOKEN = (_cfg && _cfg.authToken) ? _cfg.authToken : '';

const AURA_ENDPOINTS = Object.freeze({
  analyze:   _cfgEndpoints.analyze   || 'http://localhost:8000/analyze',
  missions:  _cfgEndpoints.missions  || 'http://localhost:8000/api/missoes',
  gps:       _cfgEndpoints.gps       || 'http://localhost:8000/api/gps-roteiro',
  analytics: _cfgEndpoints.analytics || 'http://localhost:8000/api/analytics/extensao'
});

// Aviso para endpoints com protocolo não seguro fora de localhost
Object.values(AURA_ENDPOINTS).forEach(function(url) {
  if (!url.startsWith('https://') && !url.startsWith('http://localhost')) {
    console.warn('[Aura BG] Endpoint com protocolo não seguro detectado:', url);
  }
});

/**
 * Retorna a configuração ativa sem expor o token.
 * Útil para diagnóstico e testes.
 */
function getConfig() {
  return { endpoints: Object.assign({}, AURA_ENDPOINTS) };
}

// Catálogo canônico de event_types aceitos pela extensão
const ANALYTICS_EVENT_TYPES = new Set([
  'assist_prompt_sent',
  'assist_response_received',
  'gps_start',
  'gps_step_started',
  'step_complete',
  'step_error',
  'session_abandoned',
  'mission_start',
  'hint_requested',
  'mission_complete'
]);

let cachedScreenshot = null;

// Fila de retry para analytics
let _analyticsQueue = [];

function _flushAnalyticsQueue() {
    if (_analyticsQueue.length === 0) return;
    const item = _analyticsQueue.shift();
    fetch(AURA_ENDPOINTS.analytics, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + AURA_AUTH_TOKEN },
        body: JSON.stringify(item.payload)
    })
    .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); })
    .catch(() => {
        item.attempts = (item.attempts || 0) + 1;
        if (item.attempts < 3) {
            _analyticsQueue.push(item); // recoloca no final da fila
        } else {
            console.warn('[Aura BG] analytics_event descartado após 3 tentativas:', item.payload?.event_type);
        }
    })
    .finally(() => {
        if (_analyticsQueue.length > 0) setTimeout(_flushAnalyticsQueue, 1000);
    });
}

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

    if (request.action === "fetch_mission") {
        fetch(AURA_ENDPOINTS.missions + '/' + encodeURIComponent(request.mission_id.replace('.json', '')))
        .then(r => r.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ erro: err.message }));
        return true;
    }

    if (request.action === 'fetch_gps_explicit') {
        fetch(
            AURA_ENDPOINTS.gps + '?objetivo=' + encodeURIComponent(request.objetivo || '') + '&tenant_id=' + (request.tenant_id || 'senior_default'),
            { headers: { 'Authorization': 'Bearer ' + AURA_AUTH_TOKEN } }
        )
        .then(r => r.json())
        .then(data => sendResponse(data))
        .catch(err => sendResponse({ status: 'erro', mensagem: err.message }));
        return true;
    }

    if (request.action === 'analytics_event') {
        var eventType = request.payload && request.payload.event_type;
        if (!ANALYTICS_EVENT_TYPES.has(eventType)) {
            sendResponse({ ok: false, reason: 'event_type_unknown' });
            return true;
        }
        _analyticsQueue.push({ payload: request.payload, attempts: 0 });
        _flushAnalyticsQueue();
        sendResponse({ ok: true });
        return true;
    }

    if (request.action !== "analisar_agora") {
        sendResponse({ error: 'unknown_action' });
        return true;
    }

    console.log("Aura: Análise final solicitada para:", request.url);

    try {
        const dispararParaPython = (imagemB64) => {
            fetch(AURA_ENDPOINTS.analyze, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + AURA_AUTH_TOKEN
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

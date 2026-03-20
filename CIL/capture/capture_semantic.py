"""
capture_semantic.py — Capturador Semântico Assíncrono (CIL)
===================================================================
Captura semântica baseada em:
- screenshot rápido + fila assíncrona (não trava a gravação)
- interpretação via Gemini (gera o pattern_detectado para o executor)
- Injeção Global (Context-level) Imortal para capturar IFRAMES e MAIN PAGE
- Trava de Gravação (Ignora cliques de Login)

CHANGELOG v2 — 3 bugs corrigidos:

  BUG A (crítico): JS de captura nunca extraía o seletor CSS do elemento clicado.
      Todo roteiro gerado chegava ao vision_engine com seletor_css="" hardcoded,
      deixando o Sniper Semântico completamente cego — ele nunca tinha uma âncora
      DOM para partir e dependia 100% do Gemini Vision em todos os passos.
      FIX: adicionada função getUniqueSelector() ao JS_INJECTION. Ela sobe a
      árvore DOM priorizando: id próprio → data-testid → name → aria-label →
      combinação de tag+classes únicas. O seletor resultante é enviado no payload
      e persistido em seletor_css no JSON do roteiro.

  BUG B (bomba-relógio): expose_binding usava lambda que fechava sobre a variável
      `page` antes dela existir (linha 368 vs linha 374). Closure captura
      referência, não valor — funciona por acidente de timing, mas quebra se
      algo disparar no intervalo entre as duas linhas ou em refatorações futuras.
      FIX: substituído por async def _binding_handler(source, payload) que recebe
      page via nonlocal depois de ela ser criada, garantindo escopo correto.

  BUG C (silencioso): asyncio.ensure_future() criava Tasks sem supervisão.
      Exceções dentro de handle_raw_click eram engolidas — cliques podiam sumir
      sem nenhum log de erro visível.
      FIX: substituído por asyncio.create_task() com add_done_callback que loga
      qualquer exceção não tratada, tornando falhas visíveis no terminal.
"""

import asyncio
import base64
import json
import logging
import os
import re
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import async_playwright

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[CAPTURE CIL] %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# CONFIG IA E AMBIENTE
# ──────────────────────────────────────────────────────────────
_g_key = os.getenv("GOOGLE_API_KEY")
if not _g_key:
    logger.error("GOOGLE_API_KEY ausente. O Capturador Semântico requer Visão IA.")
    sys.exit(1)

gemini_client = genai.Client(api_key=_g_key)

# ──────────────────────────────────────────────────────────────
# ESTADO GLOBAL E FILA
# ──────────────────────────────────────────────────────────────
cliques_capturados: list[dict] = []
raw_click_events: list[dict] = []

_id_acao_global = 0
_lock_id: Optional[asyncio.Lock] = None
_processing_queue: Optional[asyncio.Queue] = None
_workers: list[asyncio.Task] = []
_recording_active = False  # 🔴 Começa desligado para ignorar o Login!

# ── Debounce de cliques duplos ────────────────────────────────
# O Angular Material propaga mousedown em cascata: o clique num
# mat-list-item dispara um evento no wrapper E outro no filho
# (span/div interno) em ~10-80ms. Sem debounce, cada clique real
# vira 2 passos idênticos no roteiro.
#
# Critério de duplicata: mesmo alvo (seletor OU posição ±MARGEM)
# dentro de JANELA_MS milissegundos.
_DEBOUNCE_JANELA_MS   = 400   # janela temporal (ms) para detectar duplicata
_DEBOUNCE_MARGEM_PCT  = 0.03  # margem de posição (3% do viewport) para "mesmo lugar"
_ultimo_clique_ts: float = 0.0
_ultimo_clique_x: float  = -1.0
_ultimo_clique_y: float  = -1.0
_ultimo_clique_sel: str  = ""

PATTERNS_SUPORTADOS = [
    "button_click",
    "menu_navigation",
    "search_debounce",
    "table_selection",
    "form_fill",
    "unknown",
]

def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:60].strip("_")

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

# ──────────────────────────────────────────────────────────────
# JS DE CAPTURA (AUTO-EXECUTÁVEL E IMORTAL)
# FIX BUG A: adicionada getUniqueSelector() que sobe a árvore DOM
# e extrai o melhor seletor disponível para o elemento clicado.
# Prioridade: id → data-testid → name → aria-label → tag+classes
# ──────────────────────────────────────────────────────────────
JS_INJECTION = """
(() => {
    if (window.__radarListenerAdded) return;
    window.__radarListenerAdded = true;

    // ── 1. Bolha UI "Imortal" ──────────────────────────────────
    setInterval(() => {
        let isTop = false;
        try { isTop = window === window.top; } catch(e) { isTop = false; }

        if (isTop && !document.getElementById('senior-rec-widget')) {
            const recWidget = document.createElement('div');
            recWidget.id = 'senior-rec-widget';
            recWidget.style.cssText =
                'position:fixed;bottom:30px;right:30px;background:rgba(15,23,42,0.85);' +
                'backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);' +
                'border-radius:100px;padding:10px 20px;display:flex;align-items:center;' +
                'gap:10px;z-index:2147483647;font-family:Segoe UI,sans-serif;' +
                'box-shadow:0 10px 25px rgba(0,0,0,0.5);pointer-events:none;' +
                'transition:opacity 0.1s ease;';
            recWidget.innerHTML =
                '<div style="width:12px;height:12px;background:#00e5e5;border-radius:50%;' +
                'animation:pulse-cyan 1.5s infinite;"></div>' +
                '<div style="color:white;font-size:13px;font-weight:bold;letter-spacing:1px;">' +
                'MAPEAMENTO CIL ATIVO</div>';

            if (!document.getElementById('senior-rec-styles')) {
                const st = document.createElement('style');
                st.id = 'senior-rec-styles';
                st.innerHTML = '@keyframes pulse-cyan{' +
                    '0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(0,229,229,0.7)}' +
                    '70%{transform:scale(1);box-shadow:0 0 0 10px rgba(0,229,229,0)}' +
                    '100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(0,229,229,0)}}';
                document.head.appendChild(st);
            }
            document.documentElement.appendChild(recWidget);
        }
    }, 1000);

    // ── 2. FIX BUG A: getUniqueSelector() ─────────────────────
    // Sobe a árvore DOM a partir do elemento alvo e constrói o
    // seletor CSS mais específico e estável possível.
    // Prioridade: id → data-testid → name → aria-label → tag+classes
    function getUniqueSelector(el) {
        if (!el || el === document.body) return '';
        try {
            // Nível 1: id próprio (mais estável)
            if (el.id && !el.id.match(/^(ng-|mat-|cdk-|\\d)/)) {
                return '#' + CSS.escape(el.id);
            }

            // Nível 2: data-testid (intencionalmente estável)
            const testid = el.getAttribute('data-testid');
            if (testid) return '[data-testid="' + testid + '"]';

            // Nível 3: name em inputs/selects
            const name = el.getAttribute('name');
            if (name && ['INPUT','SELECT','TEXTAREA','BUTTON'].includes(el.tagName)) {
                return el.tagName.toLowerCase() + '[name="' + name + '"]';
            }

            // Nível 4: aria-label (semântico e estável)
            const aria = el.getAttribute('aria-label');
            if (aria && aria.length < 60) {
                return '[aria-label="' + aria.replace(/"/g, '\\"') + '"]';
            }

            // Nível 5: tag + classes relevantes (filtra classes dinâmicas Angular)
            const tag = el.tagName.toLowerCase();
            const classes = Array.from(el.classList)
                .filter(c =>
                    !c.match(/^(ng-|cdk-|mat-mdc-|_mdc-|ng-star|animate|active|open|focus|hover|selected)/) &&
                    c.length > 2 && c.length < 40
                )
                .slice(0, 3);

            if (classes.length > 0) {
                const classSelector = tag + '.' + classes.join('.');
                // Valida se é único na página
                try {
                    if (document.querySelectorAll(classSelector).length === 1) {
                        return classSelector;
                    }
                } catch(e) {}
            }

            // Nível 6: subir um nível e tentar com o pai
            const parent = el.parentElement;
            if (parent && parent !== document.body) {
                const parentSel = getUniqueSelector(parent);
                if (parentSel) {
                    const childSel = parentSel + ' > ' + tag;
                    try {
                        if (document.querySelectorAll(childSel).length === 1) {
                            return childSel;
                        }
                    } catch(e) {}
                    // nth-child como último recurso dentro do pai
                    const siblings = Array.from(parent.children);
                    const idx = siblings.indexOf(el) + 1;
                    return parentSel + ' > ' + tag + ':nth-child(' + idx + ')';
                }
            }

            return tag; // fallback mínimo
        } catch(e) {
            return '';
        }
    }

    // ── 3. O Espião de Cliques Global ─────────────────────────
    document.addEventListener('mousedown', (e) => {
        if (e.button !== 0 && e.button !== 2) return;

        const rect = e.target.getBoundingClientRect();
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

        const targetText  = (e.target.innerText || e.target.textContent || '').substring(0, 80).trim();
        const aria        = e.target.getAttribute ? (e.target.getAttribute('aria-label') || '') : '';
        const title       = e.target.getAttribute ? (e.target.getAttribute('title') || '') : '';
        const role        = e.target.getAttribute ? (e.target.getAttribute('role') || '') : '';
        const tag         = (e.target.tagName || '').toLowerCase();

        // FIX BUG A: captura o seletor CSS único do elemento
        const seletor_css = getUniqueSelector(e.target);

        // Tenta subir até o elemento interativo mais próximo para melhor seletor
        let interactiveEl = e.target;
        const interactiveTags = ['BUTTON','A','INPUT','SELECT','TEXTAREA','MAT-LIST-ITEM','LI'];
        let ancestor = e.target;
        for (let i = 0; i < 5; i++) {
            if (!ancestor.parentElement) break;
            ancestor = ancestor.parentElement;
            if (interactiveTags.includes(ancestor.tagName)) {
                interactiveEl = ancestor;
                break;
            }
        }
        const seletor_interativo = interactiveEl !== e.target
            ? getUniqueSelector(interactiveEl)
            : seletor_css;

        const payload = {
            acao:             e.button === 2 ? 'clique_direito' : 'clique',
            x_pct:            (rect.left + rect.width / 2) / vw,
            y_pct:            (rect.top + rect.height / 2) / vh,
            w_pct:            rect.width / vw,
            h_pct:            rect.height / vh,
            text_hint:        targetText,
            aria_hint:        aria,
            title_hint:       title,
            role_hint:        role,
            tag_hint:         tag,
            // FIX BUG A: campos novos
            seletor_css:      seletor_interativo || seletor_css,
            seletor_fallback: seletor_css,
            viewport_w:       vw,
            viewport_h:       vh,
            scroll_y:         window.scrollY || 0,
            page_title:       document.title || ''
        };

        // Feedback visual do clique
        setTimeout(() => {
            const h = document.createElement('div');
            h.style.position        = 'absolute';
            h.style.left            = (rect.left + window.scrollX) + 'px';
            h.style.top             = (rect.top + window.scrollY) + 'px';
            h.style.width           = rect.width + 'px';
            h.style.height          = rect.height + 'px';
            h.style.border          = '2px solid #00e5e5';
            h.style.backgroundColor = 'rgba(0, 229, 229, 0.2)';
            h.style.zIndex          = '999999';
            h.style.pointerEvents   = 'none';
            h.style.transition      = 'all 0.3s';
            document.body.appendChild(h);
            setTimeout(() => h.style.opacity = '0', 250);
            setTimeout(() => h.remove(), 500);
        }, 120);

        if (window.registrarCliqueSemantico) {
            window.registrarCliqueSemantico(payload).catch(err =>
                console.error("[CIL] Falha ao registrar clique:", err)
            );
        }
    }, true);

    // ── 4. Detector de Duplo Clique ───────────────────────────────
    // O mousedown já capturou o 1º clique. O dblclick dispara logo depois.
    // Estratégia: quando dblclick for detectado, enviamos um payload especial
    // com acao='duplo_clique' para o Python promover o último clique gravado.
    document.addEventListener('dblclick', (e) => {
        const rect = e.target.getBoundingClientRect();
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

        const payload = {
            acao: 'duplo_clique',
            x_pct: (rect.left + rect.width / 2) / vw,
            y_pct: (rect.top + rect.height / 2) / vh,
            w_pct: rect.width / vw,
            h_pct: rect.height / vh,
            text_hint: (e.target.innerText || e.target.textContent || '').substring(0, 80).trim(),
            aria_hint: e.target.getAttribute ? (e.target.getAttribute('aria-label') || '') : '',
            title_hint: e.target.getAttribute ? (e.target.getAttribute('title') || '') : '',
            role_hint:  e.target.getAttribute ? (e.target.getAttribute('role') || '') : '',
            tag_hint:   (e.target.tagName || '').toLowerCase(),
            seletor_css:      getUniqueSelector(e.target),
            seletor_fallback: getUniqueSelector(e.target),
            viewport_w: vw,
            viewport_h: vh,
            scroll_y:   window.scrollY || 0,
            page_title: document.title || ''
        };

        if (window.registrarCliqueSemantico) {
            window.registrarCliqueSemantico(payload).catch(err =>
                console.error("[CIL] Falha ao registrar duplo clique:", err)
            );
        }
    }, true);

    // ── 5. Detector de Teclado (Enter, Tab, Esc, Delete, atalhos) ─
    // ERPs usam teclado intensivamente: Enter confirma, Tab navega entre
    // campos, Esc fecha modais, F2 abre edição inline, Ctrl+S salva.
    const TECLAS_FUNCIONAIS = new Set([
        'Enter', 'Escape', 'Delete', 'F2', 'F4', 'F5',
    ]);
    const ATALHOS_CTRL = new Set(['s', 'z', 'y']);

    document.addEventListener('keydown', (e) => {
        const ehAtalhoCtrl = (e.ctrlKey || e.metaKey) && ATALHOS_CTRL.has(e.key.toLowerCase());
        const ehTeclaFuncional = TECLAS_FUNCIONAIS.has(e.key);
        if (!ehTeclaFuncional && !ehAtalhoCtrl) return;

        const tag = (e.target.tagName || '').toLowerCase();
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
        const rect = e.target.getBoundingClientRect();

        let tecla = e.key;
        if (e.ctrlKey) tecla = 'Ctrl+' + e.key.toUpperCase();
        if (e.metaKey)  tecla = 'Meta+' + e.key.toUpperCase();

        const payload = {
            acao: 'tecla',
            tecla: tecla,
            x_pct: rect.width > 0 ? (rect.left + rect.width / 2) / vw : 0.5,
            y_pct: rect.height > 0 ? (rect.top + rect.height / 2) / vh : 0.5,
            w_pct: rect.width / vw,
            h_pct: rect.height / vh,
            text_hint: (e.target.value || e.target.innerText || '').substring(0, 40).trim(),
            aria_hint:  e.target.getAttribute ? (e.target.getAttribute('aria-label') || '') : '',
            title_hint: e.target.getAttribute ? (e.target.getAttribute('title') || '') : '',
            role_hint:  e.target.getAttribute ? (e.target.getAttribute('role') || '') : '',
            tag_hint:   tag,
            seletor_css:      getUniqueSelector(e.target),
            seletor_fallback: '',
            viewport_w: vw,
            viewport_h: vh,
            scroll_y:   window.scrollY || 0,
            page_title: document.title || ''
        };

        if (window.registrarCliqueSemantico) {
            window.registrarCliqueSemantico(payload).catch(err =>
                console.error("[CIL] Falha ao registrar tecla:", err)
            );
        }
    }, true);

    // ── 6. Detector de Select / Dropdown ─────────────────────────
    // Captura mudança de valor em <select>, radio e checkbox.
    document.addEventListener('change', (e) => {
        const tag = (e.target.tagName || '').toLowerCase();
        if (!['select', 'input'].includes(tag)) return;
        if (tag === 'input') {
            const type = (e.target.type || '').toLowerCase();
            if (!['checkbox', 'radio'].includes(type)) return;
        }

        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
        const rect = e.target.getBoundingClientRect();
        const valorSelecionado = e.target.value || String(e.target.checked);
        const textoOpcao = (e.target.options && e.target.selectedIndex >= 0)
            ? (e.target.options[e.target.selectedIndex].text || '').substring(0, 80)
            : valorSelecionado.substring(0, 80);

        const payload = {
            acao: 'selecionar_opcao',
            tecla: '',
            valor_selecionado: valorSelecionado.substring(0, 80),
            x_pct: (rect.left + rect.width / 2) / vw,
            y_pct: (rect.top + rect.height / 2) / vh,
            w_pct: rect.width / vw,
            h_pct: rect.height / vh,
            text_hint: textoOpcao,
            aria_hint:  e.target.getAttribute ? (e.target.getAttribute('aria-label') || '') : '',
            title_hint: e.target.getAttribute ? (e.target.getAttribute('title') || '') : '',
            role_hint:  e.target.getAttribute ? (e.target.getAttribute('role') || '') : '',
            tag_hint:   tag,
            seletor_css:      getUniqueSelector(e.target),
            seletor_fallback: '',
            viewport_w: vw,
            viewport_h: vh,
            scroll_y:   window.scrollY || 0,
            page_title: document.title || ''
        };

        if (window.registrarCliqueSemantico) {
            window.registrarCliqueSemantico(payload).catch(err =>
                console.error("[CIL] Falha ao registrar seleção:", err)
            );
        }
    }, true);
})();
"""

# ──────────────────────────────────────────────────────────────
# PROMPT / IA
# ──────────────────────────────────────────────────────────────
def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default

def normalizar_pattern(nome: str) -> str:
    nome = (nome or "").strip().lower()
    if nome in PATTERNS_SUPORTADOS:
        return nome
    return "unknown"

async def analisar_semantica_gemini(
    b64_img: str, payload: dict, contexto_fluxo: Optional[dict] = None
) -> dict:
    contexto_fluxo  = contexto_fluxo or {}
    ultima_intencao = contexto_fluxo.get("ultima_intencao", "")
    passo_anterior  = contexto_fluxo.get("passo_anterior", "")

    # FIX BUG A: inclui o seletor capturado no prompt para o Gemini ter contexto DOM
    seletor_hint = payload.get("seletor_css", "")
    seletor_info = f'- seletor_css capturado: "{seletor_hint}"' if seletor_hint else ""

    prompt = f"""
Você é o 'Semantic Capture Agent' de um sistema de automação enterprise.
Sua missão é interpretar o SIGNIFICADO OPERACIONAL do clique do usuário usando a imagem e as coordenadas.

CONTEXTO DE FLUXO:
- Última intenção capturada: "{ultima_intencao}"
- Passo anterior resumido: "{passo_anterior}"

DADOS DO CLIQUE:
- X relativo: {payload['x_pct']*100:.1f}%
- Y relativo: {payload['y_pct']*100:.1f}%
- text_hint: "{payload.get('text_hint', '')}"
- aria_hint: "{payload.get('aria_hint', '')}"
- title_hint: "{payload.get('title_hint', '')}"
{seletor_info}

CLASSIFIQUE o clique em UM dos patterns abaixo:
- button_click (botões simples e ações primárias)
- menu_navigation (abrir menus, ícones de navegação lateral, abas)
- search_debounce (campos de busca, filtros)
- table_selection (linhas, colunas, pastas, checkboxes de grelhas)
- form_fill (campos de formulário normais)
- unknown (se ambíguo)

Responda ESTRITAMENTE em JSON válido, sem markdown:

{{
  "intencao_desejada": "frase direta do objetivo (ex: Navegar para Senior Flow)",
  "entidade": "nome do item alvo (ex: Senior Flow)",
  "tipo_alvo": "checkbox|botao|input|icone|linha|menu|aba|pasta",
  "pattern_detectado": "um dos patterns suportados",
  "confianca_pattern": 0.0,
  "variaveis_pattern": {{
    "query": "",
    "row_entity": "",
    "column_name": ""
  }},
  "validacao_esperada": {{
    "alvo": "Descreva exatamente o que deve mudar na tela após este clique para sabermos que funcionou"
  }}
}}
"""

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=base64.b64decode(b64_img), mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.1
            ),
        )
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Falha na IA Semântica: {e}")
        return {
            "intencao_desejada": f"Clicar em {payload.get('text_hint') or 'elemento'}",
            "entidade":          payload.get("text_hint", ""),
            "tipo_alvo":         payload.get("tag_hint") or "elemento_visual",
            "pattern_detectado": "unknown",
            "confianca_pattern": 0.25,
            "variaveis_pattern": {},
            "validacao_esperada": {"alvo": "A tela mudou conforme esperado"},
        }

# ──────────────────────────────────────────────────────────────
# PIPELINE ASSÍNCRONO
# ──────────────────────────────────────────────────────────────
def montar_contexto_fluxo() -> dict:
    if not cliques_capturados:
        return {}
    ultima = cliques_capturados[-1]
    return {
        "ultima_intencao": ultima.get("intencao_semantica", ""),
        "passo_anterior":  ultima.get("micro_narracao", ""),
    }

async def capturar_screenshot_limpo(page) -> str:
    await page.evaluate(
        "() => { const w = document.getElementById('senior-rec-widget'); "
        "if(w) w.style.opacity = '0'; }"
    )
    screenshot_bytes = await page.screenshot(type="jpeg", quality=60, full_page=False)
    await page.evaluate(
        "() => { const w = document.getElementById('senior-rec-widget'); "
        "if(w) w.style.opacity = '1'; }"
    )
    return base64.b64encode(screenshot_bytes).decode("utf-8")

# FIX BUG C: callback que loga exceções de tasks não supervisionadas
def _log_task_exception(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(
            f"[Task Error] Exceção não tratada em handle_raw_click: "
            f"{type(exc).__name__}: {exc}\n"
            f"{''.join(traceback.format_tb(exc.__traceback__))}"
        )

def _is_clique_duplicado(payload: dict) -> bool:
    """
    Retorna True se este clique for uma duplicata do anterior.

    Detecta dois padrões de duplicata do Angular Material:

    1. Bubbling temporal: dois eventos para o mesmo elemento físico
       chegam em < _DEBOUNCE_JANELA_MS ms (wrapper + filho).

    2. Bubbling posicional: coordenadas x_pct/y_pct dentro de
       _DEBOUNCE_MARGEM_PCT do clique anterior (o filho está
       solapado sobre o pai — coordenadas quase idênticas).

    Seletor idêntico + dentro da janela → duplicata garantida.
    Seletor diferente mas posição idêntica → também duplicata
    (filho vs pai com ids distintos mas fisicamente sobrepostos).
    """
    global _ultimo_clique_ts, _ultimo_clique_x, _ultimo_clique_y, _ultimo_clique_sel

    import time as _time
    agora_ms   = _time.monotonic() * 1000
    delta_ms   = agora_ms - _ultimo_clique_ts
    x_now      = payload.get("x_pct", -1.0)
    y_now      = payload.get("y_pct", -1.0)
    sel_now    = payload.get("seletor_css", "")

    dentro_janela   = delta_ms < _DEBOUNCE_JANELA_MS
    mesmo_seletor   = sel_now and sel_now == _ultimo_clique_sel
    mesma_posicao   = (
        abs(x_now - _ultimo_clique_x) < _DEBOUNCE_MARGEM_PCT and
        abs(y_now - _ultimo_clique_y) < _DEBOUNCE_MARGEM_PCT
    )

    if dentro_janela and (mesmo_seletor or mesma_posicao):
        logger.info(
            f"   [Debounce] ⏭️  Clique ignorado — duplicata detectada "
            f"(Δt={delta_ms:.0f}ms, Δx={abs(x_now-_ultimo_clique_x):.3f}, "
            f"Δy={abs(y_now-_ultimo_clique_y):.3f}, seletor={'igual' if mesmo_seletor else 'diferente'})"
        )
        return True

    # Não é duplicata — atualiza o baseline para o próximo clique
    _ultimo_clique_ts  = agora_ms
    _ultimo_clique_x   = x_now
    _ultimo_clique_y   = y_now
    _ultimo_clique_sel = sel_now
    return False


async def handle_raw_click(source, payload, page):
    global _id_acao_global, _lock_id, _processing_queue, _recording_active

    # A TRAVA DE LOGIN: Se a gravação não estiver ativa, ignora o clique
    if not _recording_active:
        return

    # ── Debounce: rejeita cliques duplicados do Angular Material ──
    # Verificado ANTES de adquirir o lock para não bloquear o loop de eventos
    if payload.get("acao") != "duplo_clique" and _is_clique_duplicado(payload):
        return

    # ── Tratamento especial de duplo clique ──────────────────────
    # O dblclick JS chega DEPOIS dos dois mousedown.
    # Se o último clique gravado foi na mesma posição (±3%) e está na fila
    # ou já processado, promovemos ele para duplo_clique ao invés de criar
    # um passo novo — evita ter "clique" + "duplo_clique" para a mesma ação.
    if payload.get("acao") == "duplo_clique":
        async with _lock_id:
            promovel = (
                raw_click_events
                and abs(raw_click_events[-1]["payload"].get("x_pct", -1) - payload.get("x_pct", -1)) < _DEBOUNCE_MARGEM_PCT
                and abs(raw_click_events[-1]["payload"].get("y_pct", -1) - payload.get("y_pct", -1)) < _DEBOUNCE_MARGEM_PCT
            )
            if promovel:
                # Promove o raw_event anterior para duplo_clique
                raw_click_events[-1]["payload"]["acao"] = "duplo_clique"
                logger.info(
                    f"   [DblClick] ⚡ Clique anterior promovido para duplo_clique "
                    f"em ({payload.get('x_pct', 0)*100:.1f}%, {payload.get('y_pct', 0)*100:.1f}%)"
                )
                return  # não grava um passo novo — o anterior já foi atualizado
            # Se não tem clique anterior correspondente, grava como passo novo
            # (caso raro: usuário deu dblclick sem mousedown detectado)

    async with _lock_id:
        _id_acao_global += 1
        meu_id_acao = _id_acao_global

    frame = source.get("frame")
    if frame and frame != page.main_frame:
        payload["iframe_hint"] = frame.name or frame.url
        logger.info(
            f"📸 [Captura {meu_id_acao}] Clique num Iframe ({str(payload['iframe_hint'])[:30]}...)"
        )
    else:
        payload["iframe_hint"] = None
        logger.info(f"📸 [Captura {meu_id_acao}] Clique na Página Principal!")

    try:
        screenshot_b64 = await capturar_screenshot_limpo(page)
    except Exception as e:
        screenshot_b64 = ""
        logger.warning(f"[Captura {meu_id_acao}] Screenshot falhou: {e}")

    raw_event = {
        "id_acao":     meu_id_acao,
        "payload":     payload,
        "screenshot_b64": screenshot_b64,
        "capturado_em":   utc_now(),
    }
    raw_click_events.append(raw_event)
    await _processing_queue.put(raw_event)

async def worker_processamento(worker_id: int):
    global _processing_queue
    while True:
        item = await _processing_queue.get()
        if item is None:
            _processing_queue.task_done()
            break
        try:
            await processar_click_semantico(item)
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Erro: {e}")
        finally:
            _processing_queue.task_done()

async def _descrever_tela(b64_img: str, contexto: str = "") -> dict:
    """
    Pede ao Gemini uma descrição estruturada da tela.
    Captura o ENTENDIMENTO, não só o clique.
    """
    prompt = f"""Analise esta tela de ERP e descreva em JSON:
{{
    "onde_estou": "onde o usuário está no sistema",
    "tela_id": "identificador curto (ex: ged_documentos, painel_principal)",
    "sidebar_estado": "colapsada|expandida|submenu_aberto",
    "sidebar_item_ativo": "qual item está ativo (se houver)",
    "iframe_presente": false,
    "iframe_descricao": "",
    "conteudo_central": "o que aparece na área central (resumo de 1 frase)"
}}
{f'Contexto adicional: {contexto}' if contexto else ''}"""
    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[prompt, types.Part.from_bytes(
                data=base64.b64decode(b64_img), mime_type="image/jpeg"
            )],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )
        return json.loads(response.text)
    except Exception:
        return {"onde_estou": "", "tela_id": "", "sidebar_estado": "", "conteudo_central": ""}


async def processar_click_semantico(item: dict):
    payload       = item["payload"]
    b64_img_antes = item["screenshot_b64"]
    id_acao       = item["id_acao"]
    page          = item.get("page")  # página Playwright, se disponível

    contexto_fluxo = montar_contexto_fluxo()

    # ── Captura o entendimento da tela ANTES do clique ──────────
    descricao_antes = await _descrever_tela(b64_img_antes, "imediatamente antes do clique")

    # ── Análise semântica do clique ──────────────────────────────
    analise = await analisar_semantica_gemini(b64_img_antes, payload, contexto_fluxo)

    # ── Screenshot DEPOIS do clique (se página disponível) ──────
    b64_img_depois = ""
    descricao_depois = {}
    if page:
        try:
            await asyncio.sleep(1.2)  # aguarda animação/navegação
            screenshot_depois = await page.screenshot(type="jpeg", quality=60, full_page=False)
            b64_img_depois = base64.b64encode(screenshot_depois).decode("utf-8")
            descricao_depois = await _descrever_tela(b64_img_depois, "após o clique")
        except Exception:
            pass

    pattern      = normalizar_pattern(analise.get("pattern_detectado"))
    acao_raw     = payload.get("acao", "clique")

    if acao_raw == "duplo_clique":
        acao_semantica = "duplo_clique"
    elif acao_raw == "clique_direito":
        acao_semantica = "clique_direito"
    elif acao_raw == "tecla":
        tecla = payload.get("tecla", "")
        acao_semantica = "digitar_e_enter" if tecla == "Enter" else "tecla"
    elif acao_raw == "selecionar_opcao":
        acao_semantica = "selecionar_opcao"
    elif pattern in ("search_debounce", "form_fill"):
        acao_semantica = "preencher_campo"
    else:
        acao_semantica = "clique"

    valor_input_base = analise.get("variaveis_pattern", {}).get("query", "")
    if acao_raw == "tecla":
        valor_input_base = payload.get("tecla", "")
    elif acao_raw == "selecionar_opcao":
        valor_input_base = payload.get("valor_selecionado", "") or payload.get("text_hint", "")

    entidade    = analise.get("entidade", "")
    label_curto = (
        entidade
        or payload.get("text_hint")
        or payload.get("aria_hint")
        or analise.get("tipo_alvo", "alvo")
    )
    seletor_capturado = payload.get("seletor_css", "")

    acao = {
        "id_acao":            id_acao,
        "acao":               acao_semantica,
        "intencao_semantica": analise.get("intencao_desejada", f"Ação {id_acao}"),
        "valor_input":        valor_input_base,
        "micro_narracao":     f"...{analise.get('intencao_desejada', '').lower()}...",
        "pattern_detectado":  pattern,
        "seletor_css":        seletor_capturado,

        # CONTEXTO SEMÂNTICO — o que diferencia v3 das versões anteriores
        "contexto_semantico": {
            "tela_antes": descricao_antes,
            "tela_depois": descricao_depois,
            "raciocinio": analise.get("raciocinio_captura", ""),
            "o_que_mudou": _inferir_mudanca(descricao_antes, descricao_depois),
        },

        "elemento_alvo": {
            "descricao_visual":    f"{analise.get('tipo_alvo', '')} {entidade}".strip(),
            "contexto_tela":       payload.get("page_title", ""),
            "tipo_elemento":       analise.get("tipo_alvo", ""),
            "label_curto":         label_curto,
            "coordenadas_relativas": {
                "x_pct": payload["x_pct"],
                "y_pct": payload["y_pct"],
                "w_pct": payload["w_pct"],
                "h_pct": payload["h_pct"],
            },
            "screenshot_referencia": b64_img_antes,
            "screenshot_depois":     b64_img_depois,
            "iframe_hint":           payload.get("iframe_hint"),
        },
        "validacao_esperada": analise.get("validacao_esperada", {}),
    }

    cliques_capturados.append(acao)
    logger.info(
        f"🧠 [IA {id_acao}] {acao['intencao_semantica']} | "
        f"Pattern: {pattern} | Seletor: {seletor_capturado[:40] or '(nenhum)'} | "
        f"Tela: {descricao_antes.get('tela_id','')} → {descricao_depois.get('tela_id','')}"
    )


def _inferir_mudanca(antes: dict, depois: dict) -> str:
    """Descreve em linguagem natural o que mudou entre as duas telas."""
    if not antes or not depois:
        return ""
    partes = []
    if antes.get("tela_id") != depois.get("tela_id"):
        partes.append(f"tela mudou de '{antes.get('tela_id','')}' para '{depois.get('tela_id','')}'")
    if antes.get("sidebar_item_ativo") != depois.get("sidebar_item_ativo"):
        partes.append(f"item ativo mudou para '{depois.get('sidebar_item_ativo','')}'")
    if antes.get("sidebar_estado") != depois.get("sidebar_estado"):
        partes.append(f"sidebar: {antes.get('sidebar_estado','')} → {depois.get('sidebar_estado','')}")
    if antes.get("conteudo_central") != depois.get("conteudo_central"):
        partes.append(f"conteúdo central atualizou")
    return "; ".join(partes) if partes else "sem mudança detectada"

# ──────────────────────────────────────────────────────────────
# ORQUESTRADOR DE NAVEGAÇÃO E LOGIN
# ──────────────────────────────────────────────────────────────
async def capturar_cliques_na_tela(nome_aula: str, objetivo: str):
    global _lock_id, _processing_queue, _workers, _recording_active

    _lock_id          = asyncio.Lock()
    _processing_queue = asyncio.Queue()
    _recording_active = False

    # Reseta o debounce no início de cada sessão de gravação
    global _ultimo_clique_ts, _ultimo_clique_x, _ultimo_clique_y, _ultimo_clique_sel
    _ultimo_clique_ts  = 0.0
    _ultimo_clique_x   = -1.0
    _ultimo_clique_y   = -1.0
    _ultimo_clique_sel = ""

    _workers = [
        asyncio.create_task(worker_processamento(1)),
        asyncio.create_task(worker_processamento(2)),
    ]

    SENIOR_URL = os.getenv(
        "SENIOR_URL",
        "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/",
    )
    usuario = os.getenv("SENIOR_USER")
    senha   = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("ERRO FATAL: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)

        await context.add_init_script(JS_INJECTION)
        page = await context.new_page()

        # FIX BUG B: expose_binding declarado APÓS page existir, usando closure correta.
        # A referência a `page` agora está garantidamente resolvida.
        async def _binding_handler(source, payload):
            # FIX BUG C: usa create_task + done_callback para capturar exceções
            task = asyncio.create_task(handle_raw_click(source, payload, page))
            task.add_done_callback(_log_task_exception)

        await context.expose_binding("registrarCliqueSemantico", _binding_handler)

        try:
            print("⏳ A iniciar o navegador e a tentar auto-login...")
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")

            campo_usr = page.locator(
                "input[type='text'], input[type='email'], [placeholder*='usuario']"
            ).first
            await campo_usr.wait_for(state="visible", timeout=10000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.4)

            try:
                await page.locator(
                    "button:has-text('Próximo'), button:has-text('Continuar')"
                ).first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")

            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.4)
            await page.keyboard.press("Enter")

            print("⏳ A aguardar carregamento completo do painel...")
            await page.wait_for_load_state("load", timeout=30000)
            await asyncio.sleep(2.0)

        except Exception as e:
            print(f"⚠️ AVISO: Conclua o login manualmente! ({e})")
            try:
                await page.wait_for_load_state("load", timeout=60000)
            except Exception:
                pass

        if page.is_closed():
            print("❌ ERRO: O navegador foi fechado antes do mapeamento. Abortando.")
            return

        # Re-injeta após login (garante que o JS esteja ativo na SPA carregada)
        try:
            await page.evaluate(JS_INJECTION)
        except Exception:
            pass

        # Re-injeta em cada navegação de main_frame (SPA do Angular troca o DOM)
        page.on(
            "framenavigated",
            lambda frame: asyncio.create_task(page.evaluate(JS_INJECTION))
            if frame == page.main_frame
            else None,
        )

        # 🟢 LIGA A GRAVAÇÃO agora que o login foi concluído
        _recording_active = True

        print("\n" + "=" * 60)
        print("🔴 MAPEAMENTO SEMÂNTICO CIL ATIVO")
        print("Pode navegar livremente, inclusive dentro do GED/Iframes.")
        print("A IA processará os cliques em segundo plano.")
        print("Feche o navegador quando terminar o fluxo.")
        print("=" * 60 + "\n")

        await page.wait_for_event("close", timeout=0)

        print(
            "⏳ O navegador foi fechado. "
            "A aguardar que a IA termine de classificar os últimos cliques..."
        )
        await _processing_queue.join()
        for _ in _workers:
            await _processing_queue.put(None)
        await asyncio.gather(*_workers, return_exceptions=True)

        if cliques_capturados:
            os.makedirs("roteiros_salvos", exist_ok=True)
            caminho_arquivo = f"roteiros_salvos/{limpar_nome(nome_aula)}.json"

            roteiro = {
                "metadata": {
                    "nome_aula":       nome_aula,
                    "id_treinamento":  limpar_nome(nome_aula),
                    "versao_schema":   "CIL-v2",
                    "objetivo":        objetivo,
                },
                "passos": [
                    {
                        "id_passo":   i + 1,
                        "tipo_passo": "action",
                        "pedagogia":  {"ancora": acao["intencao_semantica"]},
                        "acoes_tecnicas": [acao],
                    }
                    for i, acao in enumerate(cliques_capturados)
                ],
            }

            with open(caminho_arquivo, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, indent=2, ensure_ascii=False)

            print(f"\n✅ SUCESSO! Roteiro CIL-v2 guardado em: {caminho_arquivo}")
            print(f"   {len(cliques_capturados)} passos capturados.")
        else:
            print("\n⚠️ Nenhum clique foi registado.")

        try:
            await browser.close()
        except Exception:
            pass


if __name__ == "__main__":
    print(
        "\n" + "=" * 50 +
        "\nSENIOR SISTEMAS — TRAINING OS (CIL CAPTURE v2)\n" +
        "=" * 50
    )
    nome_aula = input("Qual é o nome desta aula?\n> ").strip()
    objetivo  = input("Qual é o objetivo deste fluxo?\n> ").strip()
    asyncio.run(capturar_cliques_na_tela(nome_aula, objetivo))
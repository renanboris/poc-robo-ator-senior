
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Adiciona o diretório pai ao path para importar módulos da raiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import limpar_nome
from shadow_builder import (
    utc_now,
    inferir_acao_semantica,
    inferir_entidade_negocio,
    inferir_padrao_interacao,
    classificar_ruido,
)

# Aliases de compatibilidade — mantidos para testes e código externo que
# importa pelo nome legado. Internamente delegam para as funções unificadas
# do shadow_builder, que agora suportam os casos específicos do hybrid
# (tecla, selecionar_opcao, aria_hint, title_hint, modal_action, etc.)
def infer_semantic_action_from_hints(payload: dict) -> str:
    return inferir_acao_semantica("", "", "", "", hints=payload)

def infer_pattern_from_hints(payload: dict) -> str:
    return inferir_padrao_interacao("", "", "", "", "", hints=payload)

def is_noise_event(payload: dict) -> bool:
    return classificar_ruido("", "", "", "", "", hints=payload)

def infer_business_entity_from_hints(payload: dict) -> str:
    return inferir_entidade_negocio("", "", "", hints=payload)

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

load_dotenv()

logging.basicConfig(level=logging.INFO, format="[HYBRID] %(message)s")
logger = logging.getLogger("capture_hybrid_shadow")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "").strip()
gemini_client = genai.Client(api_key=GOOGLE_API_KEY) if (GOOGLE_API_KEY and genai) else None
HYBRID_DISABLE_GEMINI = os.getenv("HYBRID_DISABLE_GEMINI", "0").strip().lower() in {"1", "true", "yes", "on"}

cliques_capturados = []
_processing_queue = None
_workers = []
_recording_active = False
_id_acao_global = 0
_lock_id = None

# Sprint 4: estado para promoção clique → duplo_clique
_ultimo_evento_queue: dict = {}   # guarda o último item enfileirado para promoção
_DBLCLICK_JANELA_MS = 600         # janela de consolidação em ms

JS_HYBRID = r"""
(() => {
    if (window.__hybridCaptureLoaded) return;
    window.__hybridCaptureLoaded = true;

    // ── Sprint 1: Detecta se estamos no shell ou num módulo iframe ──
    function getCaptureScope() {
        try {
            if (window !== window.top) return 'module_iframe';
        } catch(e) {}
        return 'shell';
    }

    // ── Sprint 2: Label inteligente — sobe a árvore em ícones "burros" ──
    // Ícones (i, svg, span.fa-*) não têm texto próprio.
    // Subimos até o pai interativo e tentamos aria-label, title, texto próximo.
    function getSmartLabel(el) {
        const ICON_TAGS = new Set(['I', 'SVG', 'PATH', 'USE']);
        const isIconEl = ICON_TAGS.has(el.tagName)
            || (el.tagName === 'SPAN' && Array.from(el.classList).some(c => /^(fa-|icon-|mdi-|material-)/.test(c)));

        // Para ícones, sobe imediatamente para o pai interativo
        if (isIconEl) {
            let cur = el.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!cur) break;
                const aria = cur.getAttribute && cur.getAttribute('aria-label');
                if (aria) return aria;
                const title = cur.getAttribute && cur.getAttribute('title');
                if (title) return title;
                const txt = (cur.innerText || cur.textContent || '').trim().replace(/\s+/g, ' ');
                if (txt && txt.length > 1 && txt.length < 80) return txt;
                cur = cur.parentElement;
            }
            // Tenta pegar o breadcrumb mais próximo como contexto
            const bc = document.querySelector('.ui-breadcrumb, [aria-label*="breadcrumb"], nav[aria-label]');
            if (bc) {
                const bcText = (bc.innerText || bc.textContent || '').trim().replace(/\s+/g, ' ');
                if (bcText && bcText.length < 80) return `Ícone (${bcText})`;
            }
            return 'ícone de ação';
        }

        // Elemento editável
        const isEditable = ['INPUT','TEXTAREA','SELECT'].includes(el.tagName);
        if (isEditable) {
            return el.getAttribute('aria-label')
                || el.getAttribute('placeholder')
                || el.getAttribute('name')
                || 'Campo de entrada';
        }

        // Texto direto
        const text = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
        if (text && text.length > 1 && text.length < 120) return text;

        // Sobe a árvore procurando aria-label ou title
        let cur = el;
        for (let i = 0; i < 4; i++) {
            if (!cur) break;
            const aria = cur.getAttribute && cur.getAttribute('aria-label');
            if (aria) return aria;
            const title = cur.getAttribute && cur.getAttribute('title');
            if (title) return title;
            cur = cur.parentElement;
        }
        return (el.tagName || 'elemento').toLowerCase();
    }

    // Mantém getElementName como alias para compatibilidade
    function getElementName(el) { return getSmartLabel(el); }

    function getUniqueSelector(el) {
        if (!el || el === document.body) return '';
        try {
            if (el.id && !String(el.id).match(/^(ng-|mat-|cdk-|\d)/)) {
                return '#' + CSS.escape(el.id);
            }
            const testid = el.getAttribute('data-testid') || el.getAttribute('data-test');
            if (testid) return '[data-testid="' + testid + '"]';
            const name = el.getAttribute('name');
            if (name && ['INPUT','SELECT','TEXTAREA','BUTTON'].includes(el.tagName)) {
                return el.tagName.toLowerCase() + '[name="' + name + '"]';
            }
            const aria = el.getAttribute('aria-label');
            if (aria && aria.length < 60) return '[aria-label="' + aria.replace(/"/g, '\\"') + '"]';
            const ph = el.getAttribute('placeholder');
            if (ph) return '[placeholder="' + ph.replace(/"/g, '\\"') + '"]';
            const tag = el.tagName.toLowerCase();
            const classes = Array.from(el.classList || [])
                .filter(c => !c.match(/^(ng-|cdk-|mat-mdc-|_mdc-|ng-star|animate|active|open|focus|hover|selected)/) && c.length > 2 && c.length < 40)
                .slice(0, 3);
            if (classes.length > 0) {
                const classSelector = tag + '.' + classes.join('.');
                try {
                    if (document.querySelectorAll(classSelector).length === 1) return classSelector;
                } catch (e) {}
            }
            const role = el.getAttribute('role');
            const txt = (el.innerText || el.textContent || '').trim().replace(/\s+/g, ' ');
            if (role && txt && txt.length < 50) return '[role="' + role + '"]';
            const parent = el.parentElement;
            if (parent && parent !== document.body) {
                const parentSel = getUniqueSelector(parent);
                if (parentSel) {
                    const siblings = Array.from(parent.children);
                    const idx = siblings.indexOf(el) + 1;
                    return parentSel + ' > ' + tag + ':nth-child(' + idx + ')';
                }
            }
            return tag;
        } catch(e) {
            return '';
        }
    }

    function getFrameId() {
        if (window.name) return window.name;
        try {
            const href = window.location.href;
            if (href && href !== window.top?.location?.href) return href;
        } catch(e) {}
        return 'Pagina Principal';
    }

    let lastClickTs = 0;
    let lastClickSel = '';
    let lastClickX = -1;
    let lastClickY = -1;

    function isDuplicate(payload) {
        const now = Date.now();
        const sameTime = (now - lastClickTs) < 350;
        const sameSel = payload.seletor_css && payload.seletor_css === lastClickSel;
        const samePos = Math.abs(payload.x_pct - lastClickX) < 0.03 && Math.abs(payload.y_pct - lastClickY) < 0.03;
        if ((sameSel || samePos) && sameTime) return true;
        lastClickTs = now;
        lastClickSel = payload.seletor_css || '';
        lastClickX = payload.x_pct;
        lastClickY = payload.y_pct;
        return false;
    }

    function buildBasePayload(target, action, extra) {
        const rect = target.getBoundingClientRect();
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

        let interactiveEl = target;
        let ancestor = target;
        const interactiveTags = ['BUTTON','A','INPUT','SELECT','TEXTAREA','MAT-LIST-ITEM','LI'];
        for (let i = 0; i < 5; i++) {
            if (!ancestor || !ancestor.parentElement) break;
            ancestor = ancestor.parentElement;
            if (interactiveTags.includes(ancestor.tagName)) {
                interactiveEl = ancestor;
                break;
            }
        }

        return {
            acao: action,
            tag: (target.tagName || '').toLowerCase(),
            text_hint: getSmartLabel(target).substring(0, 120),
            aria_hint: target.getAttribute ? (target.getAttribute('aria-label') || '') : '',
            title_hint: target.getAttribute ? (target.getAttribute('title') || '') : '',
            role_hint: target.getAttribute ? (target.getAttribute('role') || '') : '',
            iframe_hint: getFrameId(),
            capture_scope: getCaptureScope(),
            seletor_css: getUniqueSelector(interactiveEl) || getUniqueSelector(target),
            seletor_fallback: getUniqueSelector(target),
            html_snapshot: (target.outerHTML || '').substring(0, 400),
            x_pct: (rect.left + rect.width / 2) / vw,
            y_pct: (rect.top + rect.height / 2) / vh,
            w_pct: rect.width / vw,
            h_pct: rect.height / vh,
            viewport_w: vw,
            viewport_h: vh,
            page_title: document.title || '',
            url_hint: location.href || '',
            ...extra
        };
    }

    document.addEventListener('mousedown', (e) => {
        if (e.button !== 0 && e.button !== 2) return;
        const payload = buildBasePayload(e.target, e.button === 2 ? 'clique_direito' : 'clique', {});
        if (isDuplicate(payload)) return;
        if (window.registrarCliqueHybrid) window.registrarCliqueHybrid(payload).catch(console.error);
    }, true);

    document.addEventListener('dblclick', (e) => {
        const payload = buildBasePayload(e.target, 'duplo_clique', { is_dblclick_promotion: true });
        if (window.registrarCliqueHybrid) window.registrarCliqueHybrid(payload).catch(console.error);
    }, true);

    const TECLAS_FUNCIONAIS = new Set(['Enter', 'Escape', 'Delete', 'F2', 'F4', 'F5']);
    const ATALHOS_CTRL = new Set(['s', 'z', 'y']);

    document.addEventListener('keydown', (e) => {
        const ehAtalhoCtrl = (e.ctrlKey || e.metaKey) && ATALHOS_CTRL.has(e.key.toLowerCase());
        const ehTeclaFuncional = TECLAS_FUNCIONAIS.has(e.key);
        if (!ehTeclaFuncional && !ehAtalhoCtrl) return;

        let tecla = e.key;
        if (e.ctrlKey) tecla = 'Ctrl+' + e.key.toUpperCase();
        if (e.metaKey) tecla = 'Meta+' + e.key.toUpperCase();

        const payload = buildBasePayload(e.target, 'tecla', {
            tecla: tecla,
            valor_input: (e.target && 'value' in e.target) ? String(e.target.value || '').substring(0, 80) : ''
        });
        if (window.registrarCliqueHybrid) window.registrarCliqueHybrid(payload).catch(console.error);
    }, true);

    document.addEventListener('change', (e) => {
        const tag = (e.target.tagName || '').toLowerCase();
        if (!['select', 'input'].includes(tag)) return;
        if (tag === 'input') {
            const type = (e.target.type || '').toLowerCase();
            if (!['checkbox', 'radio'].includes(type)) return;
        }
        const valorSelecionado = e.target.value || String(e.target.checked);
        const textoOpcao = (e.target.options && e.target.selectedIndex >= 0)
            ? (e.target.options[e.target.selectedIndex].text || '').substring(0, 80)
            : String(valorSelecionado).substring(0, 80);

        const payload = buildBasePayload(e.target, 'selecionar_opcao', {
            valor_selecionado: String(valorSelecionado).substring(0, 80),
            text_hint: textoOpcao
        });
        if (window.registrarCliqueHybrid) window.registrarCliqueHybrid(payload).catch(console.error);
    }, true);

    if (window === window.top && !document.getElementById('senior-rec-widget')) {
        const recWidget = document.createElement('div');
        recWidget.id = 'senior-rec-widget';
        recWidget.style.cssText =
            'position:fixed;bottom:30px;right:30px;background:rgba(15,23,42,0.85);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);border-radius:100px;padding:10px 20px;display:flex;align-items:center;gap:10px;z-index:2147483647;font-family:Segoe UI,sans-serif;box-shadow:0 10px 25px rgba(0,0,0,0.5);pointer-events:none;';
        recWidget.innerHTML =
            '<div style="width:12px;height:12px;background:#00e5e5;border-radius:50%;"></div>' +
            '<div style="color:white;font-size:13px;font-weight:bold;letter-spacing:1px;">MAPEAMENTO HÍBRIDO ATIVO</div>';
        document.documentElement.appendChild(recWidget);
    }
})();
"""

async def descrever_tela_bytes(screenshot_bytes, contexto=""):
    if not gemini_client or HYBRID_DISABLE_GEMINI:
        return {"onde_estou": "", "tela_id": "", "sidebar_estado": "", "sidebar_item_ativo": "", "conteudo_central": ""}
    prompt = f"""Analise esta tela de ERP e descreva em JSON:
{{
  "onde_estou": "onde o usuário está no sistema",
  "tela_id": "identificador curto da tela",
  "sidebar_estado": "colapsada|expandida|submenu_aberto",
  "sidebar_item_ativo": "item ativo",
  "iframe_presente": false,
  "iframe_descricao": "",
  "conteudo_central": "resumo curto do centro da tela"
}}
{f'Contexto adicional: {contexto}' if contexto else ''}"""
    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Gemini tela falhou: {e}")
        return {"onde_estou": "", "tela_id": "", "sidebar_estado": "", "sidebar_item_ativo": "", "conteudo_central": ""}

async def analisar_semantica_hibrida(b64_img, payload, contexto_fluxo=None):
    contexto_fluxo = contexto_fluxo or {}
    fallback = {
        "semantic_action": inferir_acao_semantica("", "", "", "", hints=payload),
        "business_entity": inferir_entidade_negocio("", "", "", hints=payload),
        "business_target": payload.get("text_hint", ""),
        "pattern_detected": inferir_padrao_interacao("", "", "", "", "", hints=payload),
        "confidence": 0.25,
        "expected_effect": "A tela mudou conforme esperado",
        "intent_description": f"{payload.get('acao','clique')} em {payload.get('text_hint') or 'elemento'}",
        "validation_expected": {"alvo": "A tela mudou conforme esperado"},
    }
    if not gemini_client or HYBRID_DISABLE_GEMINI:
        return fallback

    prompt = f"""
Você é um analista semântico do Senior X.
Interprete o significado operacional do evento.

CONTEXTO:
- Última intenção: "{contexto_fluxo.get('ultima_intencao','')}"
- Passo anterior: "{contexto_fluxo.get('passo_anterior','')}"

DADOS DO EVENTO:
- ação bruta: "{payload.get('acao','')}"
- text_hint: "{payload.get('text_hint','')}"
- aria_hint: "{payload.get('aria_hint','')}"
- title_hint: "{payload.get('title_hint','')}"
- role_hint: "{payload.get('role_hint','')}"
- page_title: "{payload.get('page_title','')}"
- seletor_css: "{payload.get('seletor_css','')}"
- x relativo: {payload.get('x_pct',0)*100:.1f}%
- y relativo: {payload.get('y_pct',0)*100:.1f}%

Responda em JSON:
{{
  "semantic_action": "navigate|open|search|filter|fill|select|confirm|save|delete|upload|download|close",
  "business_entity": "tipo de entidade principal",
  "business_target": "nome do alvo de negócio ou label mais importante",
  "pattern_detected": "button_click|menu_navigation|search_debounce|table_selection|form_fill|unknown",
  "confidence": 0.0,
  "expected_effect": "o que deve acontecer na tela",
  "intent_description": "frase curta do objetivo operacional",
  "validation_expected": {{
    "alvo": "o que deve mudar para confirmar sucesso"
  }}
}}
"""
    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[prompt, types.Part.from_bytes(data=base64.b64decode(b64_img), mime_type="image/jpeg")],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )
        parsed = json.loads(response.text)
        return {
            "semantic_action": parsed.get("semantic_action") or fallback["semantic_action"],
            "business_entity": parsed.get("business_entity") or fallback["business_entity"],
            "business_target": parsed.get("business_target") or fallback["business_target"],
            "pattern_detected": parsed.get("pattern_detected") or fallback["pattern_detected"],
            "confidence": parsed.get("confidence", fallback["confidence"]),
            "expected_effect": parsed.get("expected_effect") or fallback["expected_effect"],
            "intent_description": parsed.get("intent_description") or fallback["intent_description"],
            "validation_expected": parsed.get("validation_expected") or fallback["validation_expected"],
        }
    except Exception:
        return fallback

def _inferir_contexto_leve(payload_antes: dict, payload_depois: dict | None = None) -> dict:
    """
    Contexto semântico leve, sem Gemini.
    Usa url, page_title e iframe do payload técnico para preencher
    tela_antes/tela_depois e o_que_mudou mesmo quando Gemini está desligado.
    """
    def _tela_from_payload(p: dict) -> dict:
        if not p:
            return {}
        return {
            "tela_id": p.get("page_title", ""),
            "url": p.get("url_hint", ""),
            "iframe": p.get("iframe_hint", ""),
            "scope": p.get("capture_scope", ""),
        }

    tela_antes = _tela_from_payload(payload_antes)
    tela_depois = _tela_from_payload(payload_depois) if payload_depois else {}

    mudancas = []
    if tela_antes.get("url") and tela_depois.get("url") and tela_antes["url"] != tela_depois["url"]:
        # Extrai a parte mais legível da URL (último segmento não-vazio)
        url_depois = tela_depois["url"]
        segmento = next((s for s in reversed(url_depois.split("/")) if s and not s.startswith("#")), url_depois)
        mudancas.append(f"url mudou → {segmento}")
    if tela_antes.get("tela_id") and tela_depois.get("tela_id") and tela_antes["tela_id"] != tela_depois["tela_id"]:
        mudancas.append(f"tela mudou para '{tela_depois['tela_id']}'")
    if tela_antes.get("iframe") != tela_depois.get("iframe") and tela_depois.get("iframe"):
        mudancas.append(f"entrou no iframe '{tela_depois['iframe']}'")

    return {
        "tela_antes": tela_antes,
        "tela_depois": tela_depois,
        "o_que_mudou": "; ".join(mudancas) if mudancas else "",
    }


def infer_change(antes: dict, depois: dict) -> str:
    """Usado quando Gemini retorna descrições ricas de tela."""
    partes = []
    if antes.get("tela_id") != depois.get("tela_id"):
        partes.append(f"tela mudou de '{antes.get('tela_id','')}' para '{depois.get('tela_id','')}'")
    if antes.get("sidebar_item_ativo") != depois.get("sidebar_item_ativo"):
        partes.append(f"item ativo mudou para '{depois.get('sidebar_item_ativo','')}'")
    if antes.get("conteudo_central") != depois.get("conteudo_central"):
        partes.append("conteúdo central atualizou")
    return "; ".join(partes)

def montar_contexto_fluxo():
    if not cliques_capturados:
        return {}
    ultima = cliques_capturados[-1]
    return {
        "ultima_intencao": ultima.get("intencao_semantica", ""),
        "passo_anterior": ultima.get("micro_narracao", ""),
    }

async def processar_evento_hibrido(item):
    payload = item["payload"]
    screenshot_bytes_antes = item["screenshot_bytes"]
    b64_img_antes = base64.b64encode(screenshot_bytes_antes).decode("utf-8") if screenshot_bytes_antes else ""
    page = item.get("page")
    id_acao = item["id_acao"]

    # =========================================================
    # 1. ETAPA MECÂNICA: Tirar a foto do "DEPOIS" rapidamente
    # =========================================================
    screenshot_bytes_depois = None
    screenshot_b64_depois = ""
    payload_depois = None

    if page and not page.is_closed():
        try:
            await asyncio.sleep(1.0)
            screenshot_bytes_depois = await page.screenshot(type="jpeg", quality=60, full_page=False)
            screenshot_b64_depois = base64.b64encode(screenshot_bytes_depois).decode("utf-8")
            # Captura o estado técnico da tela depois para contexto leve
            payload_depois = {
                "page_title": await page.title(),
                "url_hint": page.url,
                "iframe_hint": payload.get("iframe_hint", ""),
                "capture_scope": payload.get("capture_scope", ""),
            }
        except Exception:
            pass

    # =========================================================
    # 2. ETAPA COGNITIVA: Analisar com a IA (se disponível)
    # =========================================================
    descricao_antes = {}
    descricao_depois = {}

    if screenshot_bytes_antes:
        descricao_antes = await descrever_tela_bytes(screenshot_bytes_antes, "imediatamente antes do evento")

    if screenshot_bytes_depois:
        descricao_depois = await descrever_tela_bytes(screenshot_bytes_depois, "após o evento")

    sem = await analisar_semantica_hibrida(b64_img_antes, payload, montar_contexto_fluxo())

    # =========================================================
    # 3. Sprint 3: Contexto semântico — Gemini se disponível,
    #    senão contexto leve via url/title/iframe
    # =========================================================
    if descricao_antes or descricao_depois:
        # Gemini rodou — usa resultado rico
        contexto_sem = {
            "tela_antes": descricao_antes,
            "tela_depois": descricao_depois,
            "o_que_mudou": infer_change(descricao_antes, descricao_depois),
        }
    else:
        # Gemini desligado — usa contexto leve determinístico
        contexto_sem = _inferir_contexto_leve(payload, payload_depois)

    # =========================================================
    # 4. MONTAGEM DO EVENTO ENRIQUECIDO
    # =========================================================
    # Resolve label_curto — nunca deixa "i", "span", "elemento"
    raw_label = payload.get("text_hint", "") or sem["business_target"]
    TAGS_BURRAS = {"i", "span", "div", "a", "elemento", "ícone de ação", ""}
    label_curto = raw_label if raw_label.lower() not in TAGS_BURRAS else sem["business_target"] or "ação"

    # Se Gemini retornou unknown, aplica heurística local como fallback
    pattern_final = sem["pattern_detected"]
    if pattern_final == "unknown":
        pattern_final = inferir_padrao_interacao("", "", "", "", "", hints=payload)

    # Marca eventos de ruído — o gerador decide se descarta
    noise = classificar_ruido("", "", "", "", "", hints=payload)

    acao = {
        "id_acao": id_acao,
        "captured_at": utc_now(),
        "acao": payload.get("acao", "clique"),
        "capture_scope": payload.get("capture_scope", "shell"),
        "is_noise": noise,
        "intencao_semantica": sem["intent_description"],
        "semantic_action": sem["semantic_action"],
        "business_entity": sem["business_entity"],
        "business_target": sem["business_target"] or label_curto,
        "pattern_detectado": pattern_final,
        "valor_input": payload.get("valor_input", "") or payload.get("valor_selecionado", ""),
        "micro_narracao": f".{(sem['intent_description'] or '').lower()}.",
        "contexto_semantico": contexto_sem,
        "validacao_esperada": sem.get("validation_expected", {}),
        "elemento_alvo": {
            "descricao_visual": raw_label or sem["business_target"],
            "contexto_tela": descricao_antes.get("onde_estou", "") or payload.get("page_title", ""),
            "tipo_elemento": payload.get("tag") or sem["business_entity"],
            "label_curto": label_curto[:60],
            "coordenadas_relativas": {
                "x_pct": float(payload.get("x_pct", 0.5)),
                "y_pct": float(payload.get("y_pct", 0.5)),
                "w_pct": float(payload.get("w_pct", 0.05)),
                "h_pct": float(payload.get("h_pct", 0.05)),
            },
            "seletor_hint": payload.get("seletor_css", ""),
            "seletor_fallback": payload.get("seletor_fallback", ""),
            "iframe_hint": payload.get("iframe_hint"),
            "html_hint": payload.get("html_snapshot", "")[:300],
            "screenshot_referencia": b64_img_antes,
            "screenshot_depois": screenshot_b64_depois,
        },
        "technical": payload,
    }

    cliques_capturados.append(acao)
    noise_tag = " [NOISE]" if noise else ""
    scope_tag = f"[{acao['capture_scope']}]" if acao.get("capture_scope") else ""
    logger.info(f"#{id_acao:03d} {scope_tag}{noise_tag} | {acao['acao']} | {acao['semantic_action']} | {label_curto} | {pattern_final}")

async def worker(worker_id):
    while True:
        item = await _processing_queue.get()
        if item is None:
            _processing_queue.task_done()
            break
        try:
            await processar_evento_hibrido(item)
        except Exception as e:
            logger.error(f"[Worker {worker_id}] Erro: {e}")
        finally:
            _processing_queue.task_done()

def _log_task_exception(task):
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.error(f"Task falhou: {exc}")

async def registrar_clique_hibrido(source, payload):
    global _id_acao_global, _ultimo_evento_queue
    if not _recording_active:
        return

    frame = getattr(source, "frame", None)
    page = getattr(source, "page", None)
    if page is None and frame is not None:
        page = frame.page

    # ── Sprint 4: Promoção clique → duplo_clique ──────────────────
    # Quando chega um duplo_clique, verifica se o último evento enfileirado
    # é um clique simples no mesmo alvo (±3% posição, dentro de 600ms).
    # Se sim, promove o item já na fila em vez de criar um passo novo.
    if payload.get("is_dblclick_promotion"):
        import time as _time
        agora_ms = _time.monotonic() * 1000
        prev = _ultimo_evento_queue
        if prev:
            delta_ms = agora_ms - prev.get("ts_ms", 0)
            dx = abs(payload.get("x_pct", -1) - prev["payload"].get("x_pct", -1))
            dy = abs(payload.get("y_pct", -1) - prev["payload"].get("y_pct", -1))
            if delta_ms < _DBLCLICK_JANELA_MS and dx < 0.03 and dy < 0.03:
                # Promove o payload já na fila — não cria novo item
                prev["payload"]["acao"] = "duplo_clique"
                logger.info(
                    f"   [DblClick] ⚡ Clique #{prev['id_acao']} promovido para duplo_clique "
                    f"(Δt={delta_ms:.0f}ms)"
                )
                return
        # Sem clique anterior correspondente — registra como passo novo normalmente

    async with _lock_id:
        _id_acao_global += 1
        my_id = _id_acao_global

    screenshot_bytes = b""
    try:
        if page and not page.is_closed():
            screenshot_bytes = await page.screenshot(type="jpeg", quality=60, full_page=False)
    except Exception:
        pass

    import time as _time
    item = {
        "id_acao": my_id,
        "payload": payload,
        "screenshot_bytes": screenshot_bytes,
        "page": page,
        "ts_ms": _time.monotonic() * 1000,
    }
    _ultimo_evento_queue = item
    await _processing_queue.put(item)

async def _binding_handler(source, payload):
    task = asyncio.create_task(registrar_clique_hibrido(source, payload))
    task.add_done_callback(_log_task_exception)

async def _inject_in_frame(frame):
    """Tenta injetar o JS no frame com retry — frames de SPA/iframe podem não estar prontos."""
    for _ in range(20):
        try:
            await frame.evaluate(JS_HYBRID)
            return True
        except Exception:
            await asyncio.sleep(0.5)
    return False

async def _inject_everywhere(context, page):
    """Injeta via add_init_script (novos contextos) + avalia em todos os frames existentes."""
    try:
        await context.add_init_script(JS_HYBRID)
    except Exception:
        pass
    try:
        await page.evaluate(JS_HYBRID)
    except Exception:
        pass
    for frame in page.frames:
        await _inject_in_frame(frame)

async def _rebind_frames_loop(page, stop_flag):
    """Loop periódico que injeta o JS em frames novos que aparecem dinamicamente."""
    seen = set()
    while not stop_flag["stop"]:
        for frame in page.frames:
            key = id(frame)
            if key in seen:
                continue
            ok = await _inject_in_frame(frame)
            if ok:
                seen.add(key)
        await asyncio.sleep(1.0)

async def capturar_hibrido(nome_aula, objetivo):
    global _processing_queue, _workers, _recording_active, _lock_id
    _processing_queue = asyncio.Queue()
    _workers = [asyncio.create_task(worker(i + 1)) for i in range(2)]
    _lock_id = asyncio.Lock()

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("ERRO: configure SENIOR_USER e SENIOR_PASS no .env")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        await context.expose_binding("registrarCliqueHybrid", _binding_handler)

        print("Abrindo Senior X...")
        await page.goto(SENIOR_URL)
        await asyncio.sleep(2.0)
        try:
            await page.keyboard.press("Escape")
        except Exception:
            pass

        try:
            campo_usr = page.locator("input[type='text'], input[type='email'], [placeholder*='usuario'], [placeholder*='Usuário']").first
            await campo_usr.wait_for(state="visible", timeout=15000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.5)
        except Exception:
            print("Não consegui preencher o usuário automaticamente. Faça login manual se precisar.")

        try:
            prox = page.locator("button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')").first
            if await prox.count() > 0:
                await prox.click()
                await asyncio.sleep(1.0)
        except Exception:
            pass

        try:
            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.5)
            
            # A MÁGICA: Pressionar Enter diretamente no campo de senha
            await page.keyboard.press("Enter")
            await asyncio.sleep(1.0)
            
            # Fallback de segurança caso o Enter não submeta o formulário
            entrar = page.locator("button:has-text('Entrar'), button:has-text('Login'), button:has-text('Acessar'), button[type='submit']").first
            if await entrar.count() > 0:
                await entrar.click()
        except Exception:
            print("Não consegui finalizar o login automaticamente. Complete manualmente.")

        print("Aguardando estabilização da tela...")
        await asyncio.sleep(8.0)
        await _inject_everywhere(context, page)
        stop_flag = {"stop": False}
        rebind_task = asyncio.create_task(_rebind_frames_loop(page, stop_flag))

        _recording_active = True

        print("\n" + "=" * 60)
        print("CAPTURE HÍBRIDO ATIVO")
        print("O clique oficial segue técnico; a semântica roda em shadow.")
        print("Faça um fluxo curto de teste e feche o navegador ao final.")
        print("=" * 60 + "\n")

        await page.wait_for_event("close", timeout=0)

        _recording_active = False
        stop_flag["stop"] = True
        try:
            await rebind_task
        except Exception:
            pass

        print("Aguardando a fila terminar...")
        await _processing_queue.join()
        for _ in _workers:
            await _processing_queue.put(None)
        await asyncio.gather(*_workers, return_exceptions=True)

        out_json = Path("roteiros_salvos") / f"{limpar_nome(nome_aula)}_hybrid.json"
        out_jsonl = Path("shadow_exports") / f"{limpar_nome(nome_aula)}_shadow.jsonl"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)

        passos = []
        for i, acao in enumerate(cliques_capturados):
            acao_out = {
                "acao": acao.get("acao", "clique"),
                "capture_scope": acao.get("capture_scope", "shell"),
                "is_noise": acao.get("is_noise", False),
                "intencao_semantica": acao.get("intencao_semantica", ""),
                "elemento_alvo": {
                    **acao.get("elemento_alvo", {}),
                    "confianca_captura": "media",
                },
                "valor_input": acao.get("valor_input", ""),
                "micro_narracao": acao.get("micro_narracao", ""),
                "seletor_css": acao.get("technical", {}).get("seletor_css") or acao.get("elemento_alvo", {}).get("seletor_hint", ""),
                "validacao_esperada": {
                    "tipo": "estado_visual",
                    **(acao.get("validacao_esperada", {}) or {}),
                },
            }
            passos.append({
                "id_passo": i + 1,
                "tipo_passo": "action",
                "peso_narrativo": 2,
                "pause_sugerida": 2.5,
                "pedagogia": {"ancora": acao.get("intencao_semantica", ""), "tooltip_dap": ""},
                "alerta_instrutor": None,
                "is_conclusao": False,
                "acoes_tecnicas": [acao_out],
            })

        roteiro = {
            "metadata": {
                "nome_aula": nome_aula,
                "id_treinamento": limpar_nome(nome_aula),
                "versao_schema": "HYBRID-v1",
                "objetivo": objetivo,
                "captured_at": utc_now(),
            },
            "configuracao_gravacao": {"gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"},
            "passos": passos,
        }

        out_json.write_text(json.dumps(roteiro, ensure_ascii=False, indent=2), encoding="utf-8")
        with out_jsonl.open("w", encoding="utf-8") as f:
            for acao in cliques_capturados:
                f.write(json.dumps(acao, ensure_ascii=False) + "\n")

        print(f"\nJSON híbrido salvo em: {out_json}")
        print(f"Shadow JSONL salvo em: {out_jsonl}")
        print(f"Passos capturados: {len(cliques_capturados)}")
        await browser.close()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("SENIOR SISTEMAS — CAPTURE HÍBRIDO SHADOW")
    print("=" * 60)
    nome_aula = input("Nome da aula:\n> ").strip()
    objetivo = input("Objetivo do fluxo:\n> ").strip()
    asyncio.run(capturar_hibrido(nome_aula, objetivo))

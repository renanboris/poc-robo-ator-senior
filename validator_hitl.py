"""
validator_hitl.py — Senior Training OS · Validador com Assistência Humana
==========================================================================
Executa roteiros com o analista como co-piloto sob demanda.

Três níveis de pausa — cada um com cor e urgência diferentes:

  🟡 PREVENTIVA  — confiança baixa ANTES de clicar.
                   Pergunta ao analista antes de executar.
                   O analista confirma ou aponta o elemento certo.

  🟠 CHECKPOINT  — estado da tela NÃO BATE com o esperado APÓS um passo.
                   O Gemini Vision avalia o screenshot e sinaliza desvio.
                   O analista decide continuar, refazer ou pular.
                   Quando o analista continua mesmo com desvio, a flag
                   _desvio_anterior é propagada ao próximo passo para
                   contextualizar possíveis falhas em cascata.

  🔴 FALHA DURA  — todas as 7 camadas do vision_engine falharam.
                   Três opções para o analista:
                   • 🖱 Mostrar aqui — radar imediato (tela já está certa)
                   • 🧭 Navegar e mostrar — analista navega até o estado
                     correto e confirma antes de ativar o radar
                   • ↩ Refazer passo anterior — volta ao passo que causou
                     o desvio de estado e tenta corrigir a causa raiz
                   O seletor é capturado, salvo no Brain e o fluxo retoma.
                   Screenshot de referência exibido quando disponível.

Melhorias de confiança:
  - Brain tem prioridade sobre confianca_captura na avaliação de nível
  - Correções HITL atualizam score_engine além do brain.db
  - Prompt do Gemini na captura tem critério explícito para confiança

Cada correção humana é salva no Brain DB (brain.db) e em scores.db.
Na próxima execução, o sistema já sabe onde está o elemento.

Uso:
    python validator_hitl.py roteiros_salvos/minha_aula.json
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from enum import Enum

from dotenv import load_dotenv
from playwright.async_api import Page, async_playwright

import score_engine as _score_engine

# ── Importa módulos existentes do Training OS ─────────────────────────────────
from vision_engine import (
    _consultar_cache,
    _e_seletor_fragil,
    _registrar_sucesso_cache,
    encontrar_e_clicar,
    obter_ultima_camada_vencedora,
)

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("hitl")

# ── Configuração Gemini para checkpoint validation ────────────────────────────
_g_key = os.getenv("GOOGLE_API_KEY")
_gemini = None
try:
    from google import genai
    from google.genai import types as gtypes
    if _g_key:
        _gemini = genai.Client(api_key=_g_key)
    else:
        logger.warning("GOOGLE_API_KEY ausente. Checkpoint Gemini desativado.")
except ImportError:
    logger.warning("google-genai não instalado. Checkpoint Gemini desativado.")

# ── Thresholds ─────────────────────────────────────────────────────────────────
BRAIN_HITS_ALTA   = 2    # hits no Brain para considerar alta confiança (baixado de 3 → 2)
TIMEOUT_HUMANO    = 180  # segundos esperando analista (3 minutos)
CHECKPOINT_HABILITADO = _gemini is not None


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════

class NivelConfianca(Enum):
    ALTA  = "alta"   # Brain hit sólido ou seletor semântico validado
    MEDIA = "media"  # Sniper acertou mas sem histórico no Brain
    BAIXA = "baixa"  # Gemini Vision / coordenadas / seletor frágil


class TipoPausa(Enum):
    PREVENTIVA = "preventiva"  # 🟡
    CHECKPOINT = "checkpoint"  # 🟠
    FALHA_DURA = "falha_dura"  # 🔴


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS — CONFIANÇA
# ══════════════════════════════════════════════════════════════════════════════

def _nivel_confianca(acao_tec: dict) -> NivelConfianca:
    """
    Determina a confiança ANTES de tentar executar a ação.
    Combina: histórico no Brain + qualidade do seletor + confiança da captura.

    ORDEM DE PRIORIDADE:
    1. Brain com hits sólidos → ALTA (ignora confianca_captura)
    2. Brain com seletor mas sem hits suficientes → MEDIA
    3. confianca_captura == "baixa" → BAIXA (sem histórico no Brain)
    4. Seletor frágil → BAIXA
    5. Seletor semântico sem histórico → MEDIA
    """
    intencao  = acao_tec.get("intencao_semantica", "")
    alvo      = acao_tec.get("elemento_alvo", {})
    seletor   = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")
    conf_cap  = alvo.get("confianca_captura", "media")

    # Brain tem prioridade — se já aprendeu com hits sólidos, ignora confianca_captura
    if intencao:
        cache = _consultar_cache(intencao)
        if cache and cache.hits >= BRAIN_HITS_ALTA and cache.falhas_consecutivas == 0:
            return NivelConfianca.ALTA
        if cache and cache.seletor:
            return NivelConfianca.MEDIA

    # Sem histórico no Brain — avalia confiança da captura original
    if conf_cap == "baixa":
        return NivelConfianca.BAIXA

    # Avalia qualidade do seletor
    if not seletor or _e_seletor_fragil(seletor):
        return NivelConfianca.BAIXA

    # Seletor semântico sólido mas sem histórico no Brain
    for prefixo_bom in ("data-testid", "aria-label", "[id=", "[name=", "placeholder"):
        if prefixo_bom in seletor:
            return NivelConfianca.MEDIA

    return NivelConfianca.MEDIA


# ══════════════════════════════════════════════════════════════════════════════
# CHECKPOINT — VALIDAÇÃO DE ESTADO VIA GEMINI VISION
# ══════════════════════════════════════════════════════════════════════════════

async def _validar_checkpoint(
    page: Page,
    tooltip_dap: str,
    ancora: str,
    screenshot_ref_b64: str | None = None,
) -> tuple[bool, str]:
    """
    Tira screenshot e pede ao Gemini Vision para avaliar se a tela atual
    corresponde ao estado esperado descrito no roteiro.

    Fase 3.3: se screenshot_ref_b64 estiver disponível (gravação original),
    envia ambas as imagens para comparação visual direta.

    Retorna (estado_ok: bool, observacao: str).
    """
    if not CHECKPOINT_HABILITADO or not tooltip_dap:
        return True, "Checkpoint desabilitado."

    try:
        screenshot_atual = await page.screenshot(type="jpeg", quality=60, full_page=False)

        contents = []

        # Fase 3.3: inclui screenshot de referência se disponível
        if screenshot_ref_b64:
            try:
                import base64
                ref_bytes = base64.b64decode(screenshot_ref_b64)
                contents.append("IMAGEM 1 — REFERÊNCIA (como a tela estava na gravação original):")
                contents.append(gtypes.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))
                contents.append("IMAGEM 2 — TELA ATUAL (estado após executar o passo):")
            except Exception:
                pass  # referência inválida — continua sem ela

        contents.append(gtypes.Part.from_bytes(data=screenshot_atual, mime_type="image/jpeg"))

        modo_comparacao = "Compare as duas imagens e avalie se a tela atual corresponde ao estado esperado." if screenshot_ref_b64 else "Analise o screenshot."

        prompt = (
            f"Você está validando a execução de um roteiro de treinamento no ERP Senior X.\n\n"
            f"Após executar um passo, o estado esperado da tela é:\n"
            f"- Localização: {tooltip_dap}\n"
            f"- Descrição: {ancora[:200] if ancora else 'Não informado'}\n\n"
            f"{modo_comparacao}\n\n"
            f"Responda APENAS com JSON:\n"
            f'{{ "estado_ok": true/false, "confianca": "alta|media|baixa", '
            f'"observacao": "uma frase curta descrevendo o que vê e se bate com o esperado" }}'
        )
        contents.append(prompt)

        resposta = await asyncio.to_thread(
            _gemini.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.05,
            ),
        )

        dados = json.loads(resposta.text)
        return dados.get("estado_ok", True), dados.get("observacao", "")

    except Exception as e:
        logger.warning(f"Checkpoint Gemini falhou (não crítico): {e}")
        return True, "Checkpoint não disponível."


# ══════════════════════════════════════════════════════════════════════════════
# OVERLAY HITL — Interface visual na janela do Chrome
# ══════════════════════════════════════════════════════════════════════════════

# JS do getBestSelector — mesma lógica do radar_script.js (capture_dual_output)
# Suporta: PrimeNG composites, checkboxes Angular, menus de contexto, modais,
# calendários, seletores semânticos. Só cai em nth-child como último recurso.
_JS_GET_BEST_SELECTOR = """
    (el) => {
        // ── Escopo de modal ──────────────────────────────────────────────────
        const modalAncestor = el.closest('p-dialog, ui-dialog, s-dialog, p-confirmdialog, [role="dialog"]');
        const addModalScope = (seletor) => {
            if (!modalAncestor) return seletor;
            const modalScope = modalAncestor.getAttribute('role') === 'dialog'
                ? '[role="dialog"]'
                : modalAncestor.tagName.toLowerCase();
            return modalScope + ' ' + seletor;
        };

        // ── SELETOR CONTEXTUAL DE LINHA (universal) ──────────────────────────
        // Princípio: qualquer elemento dentro de uma linha de tabela/lista deve ser
        // identificado pelo CONTEÚDO da linha, não pela posição.
        // Funciona para: HTML tables, PrimeNG, Angular Material, AG Grid, listas genéricas.
        const resolveRowContext = (el) => {
            const ROW_SELECTORS = 'tr, [role="row"], li, [role="listitem"], .p-datatable-row, .mat-row, .ag-row, [class*="-row"]:not(input)';
            const rowEl = el.closest(ROW_SELECTORS);
            if (!rowEl || rowEl === el) return null;

            const getRowIdentifier = (row) => {
                const cells = Array.from(row.querySelectorAll('td, th, [role="cell"], [role="gridcell"]'));
                const candidates = cells.length > 0 ? cells : Array.from(row.children);
                for (const cell of candidates) {
                    const hasOnlyButtons = Array.from(cell.children).every(
                        c => c.tagName === 'BUTTON' || c.tagName === 'A' ||
                             c.getAttribute('role') === 'button' ||
                             c.classList.contains('ui-button') || c.classList.contains('p-button')
                    );
                    if (hasOnlyButtons && cell.children.length > 0) continue;
                    const text = (cell.innerText || cell.textContent || '').replace(/\\s+/g, ' ').trim();
                    if (text.length > 2 && !/^\\d+$/.test(text))
                        return text.substring(0, 50).replace(/["\\\\]/g, '');
                }
                const fullText = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                return fullText.length > 2 ? fullText.substring(0, 50).replace(/["\\\\]/g, '') : null;
            };

            const rowText = getRowIdentifier(rowEl);
            if (!rowText) return null;

            const getElementSelector = (el) => {
                let cur = el;
                for (let i = 0; i < 5; i++) {
                    if (!cur || cur === rowEl) break;
                    const aria = cur.getAttribute('aria-label');
                    if (aria) return '[aria-label="' + aria.replace(/"/g, '\\\\"') + '"]';
                    const testid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
                    if (testid) return '[data-testid="' + testid + '"]';
                    const role = cur.getAttribute('role');
                    if (role && role !== 'presentation' && role !== 'none') {
                        const txt = (cur.innerText || '').trim().replace(/\\s+/g, ' ');
                        if (txt && txt.length > 0 && txt.length < 40)
                            return '[role="' + role + '"]:has-text("' + txt.replace(/"/g, '\\\\"') + '")';
                        return '[role="' + role + '"]';
                    }
                    cur = cur.parentElement;
                }
                const txt = (el.innerText || '').trim().replace(/\\s+/g, ' ');
                if (txt && txt.length > 0 && txt.length < 40)
                    return 'text="' + txt.replace(/"/g, '\\\\"') + '"';
                return el.tagName.toLowerCase();
            };

            let rowTag = rowEl.tagName.toLowerCase();
            if (rowEl.getAttribute('role') === 'row') rowTag = '[role="row"]';
            else if (rowEl.getAttribute('role') === 'listitem') rowTag = '[role="listitem"]';

            return rowTag + ':has-text("' + rowText + '") ' + getElementSelector(el);
        };

        const _hasStableAttr = (el) => {
            let cur = el;
            for (let i = 0; i < 4; i++) {
                if (!cur) break;
                if (cur.getAttribute('data-testid') || cur.getAttribute('data-test')) return true;
                if (cur.getAttribute('aria-label')) return true;
                if (cur.getAttribute('name') && cur.getAttribute('name').length < 40) return true;
                cur = cur.parentElement;
            }
            return false;
        };

        // Aplica contexto de linha quando o elemento está em tabela
        // OU quando não tem atributo estável próprio (evita over-engineering)
        const isInTable = !!el.closest('table, [role="grid"], [role="treegrid"], p-table, .p-datatable, .ui-datatable');
        if (isInTable || !_hasStableAttr(el)) {
            const rowContextSelector = resolveRowContext(el);
            if (rowContextSelector) return addModalScope(rowContextSelector);
        }

        // ── Calendário PrimeNG: dia clicado ──────────────────────────────────
        const calendarCell = el.closest('.ui-datepicker-calendar td, .p-datepicker-calendar td');
        if (calendarCell || (el.tagName.toLowerCase() === 'a' && el.closest('.ui-datepicker, .p-datepicker'))) {
            const dayText = (el.innerText || el.textContent || '').trim();
            if (dayText && /^\\d{1,2}$/.test(dayText)) {
                const calHost = el.closest('p-calendar, .ui-calendar, span.ui-calendar');
                if (calHost) {
                    const inp = calHost.querySelector('input:not([type="hidden"])');
                    const iname = inp && (inp.getAttribute('name') || inp.getAttribute('formcontrolname'));
                    if (iname) return addModalScope("span.ui-calendar:has([name='" + iname + "']) a:text-is('" + dayText + "')");
                }
                return addModalScope(".ui-datepicker a:text-is('" + dayText + "')");
            }
        }

        // ── Checkbox Angular/PrimeNG ─────────────────────────────────────────
        const customCheckbox = el.closest('p-checkbox, mat-checkbox, [role="checkbox"], .ui-chkbox');
        if (customCheckbox) {
            let cliqueInterno = customCheckbox.tagName.toLowerCase();
            if (cliqueInterno === 'p-checkbox') cliqueInterno = 'p-checkbox .ui-chkbox-box';
            else if (customCheckbox.classList.contains('ui-chkbox')) cliqueInterno = '.ui-chkbox .ui-chkbox-box';
            const parentRow = customCheckbox.closest('tr, item, li, .ui-g, .list-item, .row');
            if (parentRow) {
                let text = (parentRow.textContent || '').replace(/\\s+/g, ' ').trim();
                if (text.length > 2) {
                    const cleanText = text.substring(0, 40).replace(/['"\\\\/]/g, '');
                    let pTag = parentRow.tagName.toLowerCase();
                    if (pTag === 'div' && parentRow.classList.contains('ui-g')) pTag = '.ui-g';
                    return addModalScope(pTag + ':has-text("' + cleanText + '") ' + cliqueInterno);
                }
            }
            const parentComId = customCheckbox.closest('[id]:not([id*="ng-"]):not([id*="mat-"])');
            if (parentComId && parentComId.id)
                return addModalScope(parentComId.tagName.toLowerCase() + '#' + parentComId.id + ' ' + cliqueInterno);
        }

        // ── PrimeNG composite components ─────────────────────────────────────
        const resolvePrimeNG = (el) => {
            let suffix = '', partName = '', hostId = '';
            if (el.closest('.ui-datepicker-trigger, button[icon*="calendar"], p-calendar button, .ui-calendar button'))
                { suffix = 'button'; partName = 'calendar_trigger'; hostId = 'p-calendar'; }
            else if (el.closest('.ui-dropdown-trigger, .p-dropdown-trigger'))
                { suffix = '.ui-dropdown-trigger'; partName = 'dropdown_trigger'; hostId = 'p-dropdown'; }
            else if (el.closest('.ui-dropdown-label, .p-dropdown-label'))
                { suffix = '.ui-dropdown-label'; partName = 'label'; hostId = 'p-dropdown'; }
            else if (el.closest('.ui-multiselect-trigger, .p-multiselect-trigger'))
                { suffix = '.ui-multiselect-trigger'; partName = 'trigger'; hostId = 'p-multiselect'; }
            else if (el.closest('.ui-spinner-up, .p-inputnumber-button-up'))
                { suffix = '.ui-spinner-up'; partName = 'increment'; hostId = 'p-spinner'; }
            else if (el.closest('.ui-spinner-down, .p-inputnumber-button-down'))
                { suffix = '.ui-spinner-down'; partName = 'decrement'; hostId = 'p-spinner'; }
            else if (el.closest('.ui-splitbutton-menubutton, .p-splitbutton-menubutton'))
                { suffix = '.ui-splitbutton-menubutton'; partName = 'menu_trigger'; hostId = 'p-splitbutton'; }
            else if (el.closest('.ui-inputswitch-slider, .p-inputswitch-slider'))
                { suffix = '.ui-inputswitch-slider'; partName = 'slider'; hostId = 'p-inputswitch'; }
            else if (el.closest('button.button-addon, button.ui-autocomplete-dropdown, s-autocomplete button, .ui-autocomplete-dropdown'))
                { suffix = 'button'; partName = 'search_button'; hostId = 'p-autocomplete'; }
            else if (modalAncestor && (el.tagName.toLowerCase() === 'button' || el.closest('button')))
                { suffix = 'button'; partName = 'modal_button'; hostId = 'p-dialog'; }
            else if (el.tagName.toLowerCase() === 'input' || el.closest('input')) {
                const primeHost = el.closest('p-autocomplete, .ui-autocomplete, p-calendar, .ui-calendar, p-spinner, .ui-spinner, p-chips, .ui-chips, .p-inputgroup, .ui-inputgroup, s-autocomplete');
                if (primeHost) {
                    suffix = 'input'; partName = 'input';
                    hostId = primeHost.tagName.toLowerCase().includes('calendar') ? 'p-calendar' :
                             primeHost.tagName.toLowerCase().includes('spinner') ? 'p-spinner' :
                             primeHost.tagName.toLowerCase().includes('chips') ? 'p-chips' : 'p-autocomplete';
                }
            }
            if (!suffix) return null;

            let cur = el, identifier = '', borrowedFromInput = false;
            for (let i = 0; i < 8; i++) {
                if (!cur) break;
                const name = cur.getAttribute('name') || cur.getAttribute('formcontrolname');
                const testid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
                const idAttr = cur.id && !cur.id.match(/(ng-|mat-|cdk-|^\\d)/) && !cur.id.includes('autocomplete') ? cur.id : null;
                if (name) { identifier = "[name='" + name + "']"; break; }
                if (testid) { identifier = "[data-testid='" + testid + "']"; break; }
                if (idAttr) { identifier = '#' + idAttr; break; }
                if (cur.tagName.toLowerCase().startsWith('p-') || cur.classList.contains('ui-calendar') || cur.classList.contains('ui-autocomplete') || cur.classList.contains('ui-dropdown') || cur.classList.contains('ui-multiselect') || cur.classList.contains('ui-inputgroup')) {
                    const innerInput = cur.querySelector('input:not([type="hidden"])');
                    if (innerInput && innerInput !== el) {
                        const iname = innerInput.getAttribute('name') || innerInput.getAttribute('formcontrolname');
                        if (iname) { identifier = "[name='" + iname + "']"; borrowedFromInput = true; break; }
                        const itest = innerInput.getAttribute('data-testid') || innerInput.getAttribute('data-test');
                        if (itest) { identifier = "[data-testid='" + itest + "']"; borrowedFromInput = true; break; }
                        const iid = innerInput.id && !innerInput.id.match(/(ng-|mat-|cdk-|^\\d)/) && !innerInput.id.includes('autocomplete') ? innerInput.id : null;
                        if (iid) { identifier = '#' + iid; borrowedFromInput = true; break; }
                    }
                }
                cur = cur.parentElement;
            }
            if (identifier) {
                if (borrowedFromInput) {
                    const wrapperTag = cur.tagName.toLowerCase();
                    let wrapperClass = '';
                    const c = Array.from(cur.classList).find(cls => cls.startsWith('ui-') || cls.startsWith('p-'));
                    if (c) wrapperClass = '.' + c;
                    return addModalScope(wrapperTag + wrapperClass + ':has(' + identifier + ') ' + suffix);
                }
                let isSameElement = false;
                try { isSameElement = (cur === el) || cur.matches(suffix); } catch(e) {}
                if (isSameElement) {
                    const tagPart = suffix.split('.')[0];
                    const tag = ['input', 'button'].includes(tagPart) ? tagPart : cur.tagName.toLowerCase();
                    return addModalScope(tag + identifier);
                }
                return addModalScope(identifier + ' ' + suffix);
            }
            return addModalScope(hostId + ' ' + suffix);
        };

        const primeResult = resolvePrimeNG(el);
        if (primeResult) return primeResult;

        // ── Fallback genérico: sobe 8 níveis buscando atributo estável ───────
        let cur = el;
        for (let i = 0; i < 8; i++) {
            if (!cur) break;
            const tid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
            if (tid) return addModalScope("[data-testid='" + tid + "']");
            const aria = cur.getAttribute('aria-label');
            if (aria) return addModalScope("[aria-label='" + aria + "']");
            const name = cur.getAttribute('name');
            if (name && name.length < 40) return addModalScope("[name='" + name + "']");
            if (cur.id && !cur.id.match(/^[\\d\\-_]/) && !cur.id.match(/ng-|mat-|cdk-/))
                return addModalScope("[id='" + cur.id + "']");
            cur = cur.parentElement;
        }
        const ph = el.getAttribute('placeholder');
        if (ph) return addModalScope("[placeholder='" + ph + "']");
        const role = el.getAttribute('role');
        if (role && role !== 'presentation') {
            const t = (el.innerText || '').trim().replace(/\\n/g, ' ');
            if (t && t.length < 50) return addModalScope("[role='" + role + "']:has-text('" + t + "')");
        }
        const txt = (el.innerText || '').trim().replace(/\\n/g, ' ');
        if (txt && txt.length > 1 && txt.length < 50) return addModalScope('text="' + txt + '"');
        const parentAria = el.closest('[aria-label]')?.getAttribute('aria-label');
        if (parentAria) return addModalScope("[aria-label='" + parentAria + "'] " + el.tagName.toLowerCase());
        // Último recurso: nth-child (frágil, mas melhor que nada)
        const siblings = Array.from(el.parentElement?.children || []);
        return addModalScope(el.tagName.toLowerCase() + ':nth-child(' + (siblings.indexOf(el) + 1) + ')');
    }
"""

_JS_OVERLAY = """
(params) => {
    const { tipo, titulo, mensagem, instrucao, nomeAcao } = params;

    // Remove overlay anterior
    document.getElementById('hitl-overlay')?.remove();
    document.getElementById('hitl-style')?.remove();

    // Paleta por tipo
    const paleta = {
        preventiva: {
            bg:     'rgba(15,23,42,0.97)',
            border: '#f59e0b',
            badge:  '#f59e0b',
            emoji:  '🟡',
        },
        checkpoint: {
            bg:     'rgba(15,23,42,0.97)',
            border: '#f97316',
            badge:  '#f97316',
            emoji:  '🟠',
        },
        falha_dura: {
            bg:     'rgba(15,23,42,0.97)',
            border: '#ef4444',
            badge:  '#ef4444',
            emoji:  '🔴',
        },
    };

    const cor = paleta[tipo] || paleta.falha_dura;

    // CSS
    const st = document.createElement('style');
    st.id = 'hitl-style';
    st.innerHTML = `
        #hitl-overlay {
            position: fixed; top: 24px; right: 24px;
            width: 360px; z-index: 2147483647;
            background: ${cor.bg};
            border: 2px solid ${cor.border};
            border-radius: 14px;
            box-shadow: 0 24px 60px rgba(0,0,0,0.7),
                        0 0 0 1px rgba(255,255,255,0.05),
                        0 0 32px ${cor.border}44;
            font-family: 'Segoe UI', system-ui, sans-serif;
            color: #f1f5f9; overflow: hidden;
            animation: hitl-slide-in 0.35s cubic-bezier(0.16,1,0.3,1) both;
        }
        @keyframes hitl-slide-in {
            from { opacity:0; transform:translateX(120px); }
            to   { opacity:1; transform:translateX(0); }
        }
        .hitl-header {
            background: ${cor.border}22;
            border-bottom: 1px solid ${cor.border}44;
            padding: 12px 16px;
            display: flex; align-items: center; gap: 10px;
        }
        .hitl-badge {
            background: ${cor.badge};
            color: #000; font-size: 10px; font-weight: 800;
            padding: 2px 8px; border-radius: 99px;
            text-transform: uppercase; letter-spacing: 1px;
            flex-shrink: 0;
        }
        .hitl-titulo {
            font-size: 13px; font-weight: 700; color: #fff;
        }
        .hitl-body { padding: 14px 16px; }
        .hitl-msg {
            font-size: 13px; color: #cbd5e1; line-height: 1.5;
            margin-bottom: 8px;
        }
        .hitl-instrucao {
            font-size: 11px; color: ${cor.badge};
            font-weight: 600; margin-bottom: 14px;
            display: flex; align-items: center; gap: 6px;
        }
        .hitl-acao-tag {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px; padding: 6px 10px;
            font-size: 11px; color: #94a3b8;
            margin-bottom: 14px; font-family: monospace;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .hitl-btns {
            display: flex; gap: 8px; flex-wrap: wrap;
        }
        .hitl-btn {
            padding: 8px 14px; border-radius: 8px;
            font-size: 12px; font-weight: 600; cursor: pointer;
            border: none; transition: all 0.15s;
            flex: 1; min-width: 80px;
        }
        .hitl-btn-ok {
            background: ${cor.border};
            color: #000;
        }
        .hitl-btn-ok:hover { opacity: 0.88; transform: translateY(-1px); }
        .hitl-btn-sec {
            background: rgba(255,255,255,0.08);
            color: #cbd5e1;
            border: 1px solid rgba(255,255,255,0.12) !important;
        }
        .hitl-btn-sec:hover { background: rgba(255,255,255,0.14); }
        .hitl-radar-msg {
            display: none; margin-top: 10px;
            padding: 10px 12px;
            background: rgba(239,68,68,0.1);
            border: 1px solid rgba(239,68,68,0.3);
            border-radius: 8px;
            font-size: 12px; color: #fca5a5;
            text-align: center; line-height: 1.5;
        }
        .hitl-radar-msg.ativo { display: block; }
        @keyframes hitl-radar-pulse {
            0%,100% { opacity:1; } 50% { opacity:0.5; }
        }
        .hitl-radar-dot {
            display: inline-block; width:8px; height:8px;
            background:#ef4444; border-radius:50%;
            margin-right:6px;
            animation: hitl-radar-pulse 1.2s ease infinite;
        }
    `;
    document.head.appendChild(st);

    // HTML
    const ov = document.createElement('div');
    ov.id = 'hitl-overlay';
    ov.innerHTML = `
        <div class="hitl-header">
            <span style="font-size:16px">${cor.emoji}</span>
            <span class="hitl-badge">${titulo}</span>
            <span class="hitl-titulo">Aura precisa de você</span>
        </div>
        <div class="hitl-body">
            <div class="hitl-msg">${mensagem}</div>
            ${nomeAcao ? `<div class="hitl-acao-tag">→ ${nomeAcao}</div>` : ''}
            <div class="hitl-instrucao">⟶ ${instrucao}</div>
            <div class="hitl-btns" id="hitl-btns-container"></div>
            <div class="hitl-radar-msg" id="hitl-radar-msg">
                <span class="hitl-radar-dot"></span>
                Radar ativo — clique no elemento correto na tela
            </div>
        </div>
    `;
    document.documentElement.appendChild(ov);
}
"""

async def _injetar_overlay(
    page: Page,
    tipo: TipoPausa,
    titulo: str,
    mensagem: str,
    instrucao: str,
    nome_acao: str = "",
) -> None:
    await page.evaluate(_JS_OVERLAY, {
        "tipo":      tipo.value,
        "titulo":    titulo,
        "mensagem":  mensagem,
        "instrucao": instrucao,
        "nomeAcao":  nome_acao,
    })


# JS do botão flutuante "Pronto, estou na tela certa" — usado no modo "Navegar e mostrar"
_JS_BOTAO_PRONTO = """
() => {
    document.getElementById('hitl-nav-pronto')?.remove();
    const btn = document.createElement('button');
    btn.id = 'hitl-nav-pronto';
    btn.innerHTML = '✅ Pronto — estou na tela certa';
    btn.style.cssText = `
        position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%);
        z-index: 2147483647;
        background: #22c55e; color: #000;
        border: none; border-radius: 100px;
        padding: 14px 32px; font-size: 15px; font-weight: 700;
        cursor: pointer; font-family: 'Segoe UI', sans-serif;
        box-shadow: 0 8px 24px rgba(34,197,94,0.5);
        animation: hitl-pulse-green 1.8s ease infinite;
    `;
    const st = document.createElement('style');
    st.id = 'hitl-nav-pronto-style';
    st.innerHTML = `
        @keyframes hitl-pulse-green {
            0%,100% { box-shadow: 0 8px 24px rgba(34,197,94,0.5); }
            50%      { box-shadow: 0 8px 32px rgba(34,197,94,0.85); transform: translateX(-50%) scale(1.03); }
        }
    `;
    document.head.appendChild(st);
    document.documentElement.appendChild(btn);
    btn.addEventListener('click', () => {
        btn.remove();
        document.getElementById('hitl-nav-pronto-style')?.remove();
        window.__hitl_captura__(JSON.stringify({ seletor: '', acao: 'nav_pronto' }));
    });
}
"""


async def _injetar_botao_pronto(page: Page) -> None:
    """Injeta o botão flutuante verde 'Pronto — estou na tela certa'."""
    await page.evaluate(_JS_BOTAO_PRONTO)


async def _remover_botao_pronto(page: Page) -> None:
    await page.evaluate("""() => {
        document.getElementById('hitl-nav-pronto')?.remove();
        document.getElementById('hitl-nav-pronto-style')?.remove();
    }""")


async def _remover_overlay(page: Page) -> None:
    await page.evaluate("""() => {
        document.getElementById('hitl-overlay')?.remove();
        document.getElementById('hitl-style')?.remove();
    }""")


async def _highlight_hitl(page: Page, seletor: str, cor: str = "#f59e0b") -> None:
    """Destaca o elemento que o sistema encontrou (para o analista avaliar)."""
    await page.evaluate(f"""(sel) => {{
        const el = document.querySelector(sel);
        if (!el) return;
        el.scrollIntoView({{ behavior:'smooth', block:'center' }});
        const prev = el.style.outline;
        el.setAttribute('data-hitl-prev-outline', prev);
        el.style.outline = '3px solid {cor}';
        el.style.boxShadow = '0 0 16px {cor}88';
    }}""", seletor)


async def _remover_highlight_hitl(page: Page, seletor: str) -> None:
    await page.evaluate("""(sel) => {
        const el = document.querySelector(sel);
        if (!el) return;
        el.style.outline = el.getAttribute('data-hitl-prev-outline') || '';
        el.style.boxShadow = '';
    }""", seletor)


# ══════════════════════════════════════════════════════════════════════════════
# HIGHLIGHT DO ELEMENTO CLICADO (step-by-step)
# Verde (#22c55e) = sucesso, Vermelho (#ef4444) = falha
# Usa outline (não border) para não alterar layout
# ══════════════════════════════════════════════════════════════════════════════

_JS_HIGHLIGHT_STEP_ELEMENT = """
(params) => {
    const { selector, success } = params;

    // Remove highlight anterior se existir
    document.getElementById('hitl-step-highlight-style')?.remove();
    document.querySelectorAll('[data-hitl-step-highlighted]').forEach(el => {
        el.style.outline = el.getAttribute('data-hitl-step-prev-outline') || '';
        el.style.outlineOffset = el.getAttribute('data-hitl-step-prev-offset') || '';
        el.style.boxShadow = el.getAttribute('data-hitl-step-prev-shadow') || '';
        el.removeAttribute('data-hitl-step-highlighted');
        el.removeAttribute('data-hitl-step-prev-outline');
        el.removeAttribute('data-hitl-step-prev-offset');
        el.removeAttribute('data-hitl-step-prev-shadow');
        el.classList.remove('hitl-step-highlight-pulse');
    });

    // Encontrar elemento pelo seletor
    const el = document.querySelector(selector);
    if (!el) return false;

    // Scroll suave para o elemento
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });

    // Cores baseadas em sucesso/falha
    const color = success ? '#22c55e' : '#ef4444';
    const colorAlpha = success ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)';

    // Salvar estilos anteriores
    el.setAttribute('data-hitl-step-prev-outline', el.style.outline || '');
    el.setAttribute('data-hitl-step-prev-offset', el.style.outlineOffset || '');
    el.setAttribute('data-hitl-step-prev-shadow', el.style.boxShadow || '');
    el.setAttribute('data-hitl-step-highlighted', '1');

    // Injetar CSS de animação
    const st = document.createElement('style');
    st.id = 'hitl-step-highlight-style';
    st.innerHTML = `
        @keyframes hitl-step-highlight-pulse {
            0%   { box-shadow: 0 0 0 0 ${colorAlpha}, 0 0 8px ${colorAlpha}; }
            50%  { box-shadow: 0 0 0 6px transparent, 0 0 16px ${colorAlpha}; }
            100% { box-shadow: 0 0 0 0 ${colorAlpha}, 0 0 8px ${colorAlpha}; }
        }
        .hitl-step-highlight-pulse {
            animation: hitl-step-highlight-pulse 1.5s ease-in-out infinite;
        }
    `;
    document.head.appendChild(st);

    // Aplicar highlight
    el.style.outline = `3px solid ${color}`;
    el.style.outlineOffset = '2px';
    el.classList.add('hitl-step-highlight-pulse');

    return true;
}
"""

_JS_REMOVE_STEP_HIGHLIGHT = """
() => {
    document.getElementById('hitl-step-highlight-style')?.remove();
    document.querySelectorAll('[data-hitl-step-highlighted]').forEach(el => {
        el.style.outline = el.getAttribute('data-hitl-step-prev-outline') || '';
        el.style.outlineOffset = el.getAttribute('data-hitl-step-prev-offset') || '';
        el.style.boxShadow = el.getAttribute('data-hitl-step-prev-shadow') || '';
        el.removeAttribute('data-hitl-step-highlighted');
        el.removeAttribute('data-hitl-step-prev-outline');
        el.removeAttribute('data-hitl-step-prev-offset');
        el.removeAttribute('data-hitl-step-prev-shadow');
        el.classList.remove('hitl-step-highlight-pulse');
    });
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# OVERLAY STEP-BY-STEP (minimalista, canto inferior esquerdo)
# ══════════════════════════════════════════════════════════════════════════════

_JS_STEP_OVERLAY = """
(params) => {
    const { passoAtual, passoTotal, acaoAtual, acaoTotal, descricao, sucesso, camada } = params;

    // Remove overlay anterior
    document.getElementById('hitl-step-overlay')?.remove();
    document.getElementById('hitl-step-overlay-style')?.remove();

    // CSS
    const st = document.createElement('style');
    st.id = 'hitl-step-overlay-style';
    st.innerHTML = `
        #hitl-step-overlay {
            position: fixed;
            bottom: 20px;
            left: 20px;
            max-width: 400px;
            min-width: 320px;
            z-index: 999999;
            background: rgba(15, 23, 42, 0.92);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-radius: 12px;
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5),
                        0 0 0 1px rgba(255, 255, 255, 0.05);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: #f1f5f9;
            overflow: hidden;
            animation: hitl-step-slide-in 0.3s cubic-bezier(0.16, 1, 0.3, 1) both;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }
        @keyframes hitl-step-slide-in {
            from { opacity: 0; transform: translateY(20px); }
            to   { opacity: 1; transform: translateY(0); }
        }
        .hitl-step-header {
            padding: 12px 16px 8px 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .hitl-step-progress {
            font-size: 12px;
            font-weight: 700;
            color: #94a3b8;
            letter-spacing: 0.3px;
        }
        .hitl-step-status {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 99px;
        }
        .hitl-step-status-ok {
            background: rgba(34, 197, 94, 0.15);
            color: #4ade80;
        }
        .hitl-step-status-fail {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
        }
        .hitl-step-body {
            padding: 4px 16px 12px 16px;
        }
        .hitl-step-desc {
            font-size: 13px;
            color: #e2e8f0;
            line-height: 1.4;
            margin-bottom: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .hitl-step-camada {
            font-size: 11px;
            font-weight: 600;
            color: #7dd3fc;
            opacity: 0.85;
        }
        .hitl-step-buttons {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }
        .hitl-step-btn {
            padding: 7px 12px;
            border-radius: 7px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            border: none;
            transition: all 0.15s ease;
            white-space: nowrap;
        }
        .hitl-step-btn:hover {
            transform: translateY(-1px);
            filter: brightness(1.1);
        }
        .hitl-step-btn:active {
            transform: translateY(0);
        }
        .hitl-step-btn-ok {
            background: #22c55e;
            color: #000;
        }
        .hitl-step-btn-corrigir {
            background: rgba(251, 191, 36, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.3) !important;
        }
        .hitl-step-btn-auto {
            background: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            border: 1px solid rgba(99, 102, 241, 0.3) !important;
        }
        .hitl-step-btn-pular {
            background: rgba(255, 255, 255, 0.06);
            color: #94a3b8;
            border: 1px solid rgba(255, 255, 255, 0.1) !important;
        }
    `;
    document.head.appendChild(st);

    // HTML
    const ov = document.createElement('div');
    ov.id = 'hitl-step-overlay';

    const statusClass = sucesso ? 'hitl-step-status-ok' : 'hitl-step-status-fail';
    const statusText = sucesso ? '✅ Sucesso' : '❌ Falhou';

    ov.innerHTML = `
        <div class="hitl-step-header">
            <span class="hitl-step-progress">Passo ${passoAtual}/${passoTotal} — Ação ${acaoAtual}/${acaoTotal}</span>
            <span class="hitl-step-status ${statusClass}">${statusText}</span>
        </div>
        <div class="hitl-step-body">
            <div class="hitl-step-desc" title="${descricao}">${descricao} <span class="hitl-step-camada">via ${camada || '—'}</span></div>
            <div class="hitl-step-buttons">
                <button class="hitl-step-btn hitl-step-btn-ok" data-step-action="ok">✅ Ok</button>
                <button class="hitl-step-btn hitl-step-btn-corrigir" data-step-action="corrigir">✏️ Corrigir</button>
                <button class="hitl-step-btn hitl-step-btn-auto" data-step-action="auto_5">⏩ Auto 5</button>
                <button class="hitl-step-btn hitl-step-btn-pular" data-step-action="pular">⏭ Pular</button>
            </div>
        </div>
    `;
    document.documentElement.appendChild(ov);

    // Event listeners — envia decisão via binding
    ov.querySelectorAll('[data-step-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const action = btn.getAttribute('data-step-action');
            window.__hitl_captura__(JSON.stringify({ acao: 'step_' + action }));
        });
    });
}
"""

_JS_REMOVE_STEP_OVERLAY = """
() => {
    document.getElementById('hitl-step-overlay')?.remove();
    document.getElementById('hitl-step-overlay-style')?.remove();
}
"""

# ══════════════════════════════════════════════════════════════════════════════
# OVERLAY RELATÓRIO FINAL — Exibido ao término de todas as ações
# ══════════════════════════════════════════════════════════════════════════════

_JS_RELATORIO_FINAL = """
(params) => {
    const { totalAcoes, correcoes, acoesPuladas, taxaAcerto } = params;

    // Remove overlays anteriores
    document.getElementById('hitl-step-overlay')?.remove();
    document.getElementById('hitl-step-overlay-style')?.remove();
    document.getElementById('hitl-relatorio-final')?.remove();
    document.getElementById('hitl-relatorio-final-style')?.remove();
    document.getElementById('hitl-pause-btn')?.remove();
    document.getElementById('hitl-pause-btn-style')?.remove();

    // CSS
    const st = document.createElement('style');
    st.id = 'hitl-relatorio-final-style';
    st.innerHTML = `
        #hitl-relatorio-final {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 420px;
            z-index: 2147483647;
            background: rgba(15, 23, 42, 0.97);
            border: 2px solid #22c55e;
            border-radius: 16px;
            box-shadow: 0 24px 60px rgba(0, 0, 0, 0.7),
                        0 0 0 1px rgba(255, 255, 255, 0.05),
                        0 0 40px rgba(34, 197, 94, 0.15);
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            color: #f1f5f9;
            overflow: hidden;
            animation: hitl-relatorio-in 0.4s cubic-bezier(0.16, 1, 0.3, 1) both;
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
        }
        @keyframes hitl-relatorio-in {
            from { opacity: 0; transform: translate(-50%, -50%) scale(0.9); }
            to   { opacity: 1; transform: translate(-50%, -50%) scale(1); }
        }
        .hitl-rel-header {
            background: rgba(34, 197, 94, 0.08);
            border-bottom: 1px solid rgba(34, 197, 94, 0.2);
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .hitl-rel-badge {
            background: #22c55e;
            color: #000;
            font-size: 10px;
            font-weight: 800;
            padding: 3px 10px;
            border-radius: 99px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .hitl-rel-title {
            font-size: 14px;
            font-weight: 700;
            color: #fff;
        }
        .hitl-rel-body {
            padding: 20px;
        }
        .hitl-rel-stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 20px;
        }
        .hitl-rel-stat {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 10px;
            padding: 12px 14px;
            text-align: center;
        }
        .hitl-rel-stat-value {
            font-size: 22px;
            font-weight: 800;
            color: #fff;
            line-height: 1.2;
        }
        .hitl-rel-stat-label {
            font-size: 11px;
            color: #94a3b8;
            margin-top: 4px;
            font-weight: 500;
        }
        .hitl-rel-stat-acerto .hitl-rel-stat-value {
            color: #4ade80;
        }
        .hitl-rel-stat-correcoes .hitl-rel-stat-value {
            color: #fbbf24;
        }
        .hitl-rel-stat-puladas .hitl-rel-stat-value {
            color: #94a3b8;
        }
        .hitl-rel-buttons {
            display: flex;
            gap: 10px;
        }
        .hitl-rel-btn {
            flex: 1;
            padding: 12px 16px;
            border-radius: 10px;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            border: none;
            transition: all 0.15s ease;
            text-align: center;
        }
        .hitl-rel-btn:hover {
            transform: translateY(-1px);
            filter: brightness(1.1);
        }
        .hitl-rel-btn:active {
            transform: translateY(0);
        }
        .hitl-rel-btn-gravar {
            background: #22c55e;
            color: #000;
            box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
        }
        .hitl-rel-btn-fechar {
            background: rgba(255, 255, 255, 0.08);
            color: #cbd5e1;
            border: 1px solid rgba(255, 255, 255, 0.12) !important;
        }
    `;
    document.head.appendChild(st);

    // HTML
    const ov = document.createElement('div');
    ov.id = 'hitl-relatorio-final';
    ov.innerHTML = `
        <div class="hitl-rel-header">
            <span style="font-size:18px">📊</span>
            <span class="hitl-rel-badge">Concluído</span>
            <span class="hitl-rel-title">Relatório HITL</span>
        </div>
        <div class="hitl-rel-body">
            <div class="hitl-rel-stats">
                <div class="hitl-rel-stat">
                    <div class="hitl-rel-stat-value">${totalAcoes}</div>
                    <div class="hitl-rel-stat-label">Ações executadas</div>
                </div>
                <div class="hitl-rel-stat hitl-rel-stat-acerto">
                    <div class="hitl-rel-stat-value">${taxaAcerto}%</div>
                    <div class="hitl-rel-stat-label">Taxa de acerto</div>
                </div>
                <div class="hitl-rel-stat hitl-rel-stat-correcoes">
                    <div class="hitl-rel-stat-value">${correcoes}</div>
                    <div class="hitl-rel-stat-label">Correções feitas</div>
                </div>
                <div class="hitl-rel-stat hitl-rel-stat-puladas">
                    <div class="hitl-rel-stat-value">${acoesPuladas}</div>
                    <div class="hitl-rel-stat-label">Ações puladas</div>
                </div>
            </div>
            <div class="hitl-rel-buttons">
                <button class="hitl-rel-btn hitl-rel-btn-gravar" data-rel-action="gravar">🎬 Gravar agora</button>
                <button class="hitl-rel-btn hitl-rel-btn-fechar" data-rel-action="fechar">Fechar</button>
            </div>
        </div>
    `;
    document.documentElement.appendChild(ov);

    // Event listeners — envia decisão via binding
    ov.querySelectorAll('[data-rel-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            const action = btn.getAttribute('data-rel-action');
            window.__hitl_captura__(JSON.stringify({ acao: 'relatorio_' + action }));
        });
    });
}
"""


# ══════════════════════════════════════════════════════════════════════════════
# NOVOS COMPONENTES — HITL MELHORADO
# ══════════════════════════════════════════════════════════════════════════════

class AutoPlayController:
    """Gerencia o modo de execução automática e controle de pausas."""

    def __init__(self):
        self._is_auto_play: bool = False  # Step-by-step é o padrão
        self._pause_requested: bool = False
        self._current_step_index: int = 0

    async def execute_continuous(self, steps: list[dict]) -> None:
        """Executa passos continuamente até pausa ou falha"""
        pass  # Implementado no loop principal

    def request_pause(self) -> None:
        """Solicita pausa após ação atual"""
        self._pause_requested = True

    def resume_auto_play(self) -> None:
        """Retoma execução automática"""
        self._is_auto_play = True
        self._pause_requested = False

    def is_paused(self) -> bool:
        """Verifica se execução está pausada"""
        return not self._is_auto_play or self._pause_requested


class StepNavigator:
    """Interface visual para navegação e controle de passos quando pausado."""

    def __init__(self, page: Page):
        self._page = page
        self._current_step: int = 0
        self._total_steps: int = 0
        self._step_status: dict[int, str] = {}  # executed, pending, error

    async def show_navigator(self, step_info: dict) -> None:
        """Exibe overlay do navegador centralizado"""
        await self._inject_navigator_overlay(step_info)

    async def hide_navigator(self) -> None:
        """Remove overlay do navegador"""
        await self._page.evaluate("""() => {
            document.getElementById('hitl-navigator')?.remove();
            document.getElementById('hitl-navigator-style')?.remove();
        }""")

    async def update_step_info(self, step_index: int, status: str) -> None:
        """Atualiza informações do passo atual"""
        self._current_step = step_index
        self._step_status[step_index] = status

    async def wait_for_user_action(self) -> dict:
        """Aguarda decisão do usuário no navegador"""
        pass  # Implementado via binding

    async def navigate_to_step(self, step_index: int) -> None:
        """Navega para passo específico"""
        self._current_step = step_index

    async def _inject_navigator_overlay(self, step_info: dict) -> None:
        """Injeta o overlay do navegador de passos"""
        await self._page.evaluate("""(stepInfo) => {
            // Remove navegador anterior
            document.getElementById('hitl-navigator')?.remove();
            document.getElementById('hitl-navigator-style')?.remove();

            // CSS do navegador
            const style = document.createElement('style');
            style.id = 'hitl-navigator-style';
            style.innerHTML = `
                #hitl-navigator {
                    position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                    width: 480px; z-index: 2147483647;
                    background: rgba(15,23,42,0.97);
                    border: 2px solid #f59e0b;
                    border-radius: 14px;
                    box-shadow: 0 24px 60px rgba(0,0,0,0.8);
                    font-family: 'Segoe UI', system-ui, sans-serif;
                    color: #f1f5f9; overflow: hidden;
                    animation: hitl-navigator-in 0.3s ease both;
                    backdrop-filter: blur(12px);
                }
                @keyframes hitl-navigator-in {
                    from { opacity:0; transform:translate(-50%,-50%) scale(0.9); }
                    to   { opacity:1; transform:translate(-50%,-50%) scale(1); }
                }
                .hitl-nav-header {
                    background: #f59e0b22;
                    border-bottom: 1px solid #f59e0b44;
                    padding: 16px 20px;
                    display: flex; align-items: center; gap: 12px;
                }
                .hitl-nav-badge {
                    background: #f59e0b;
                    color: #000; font-size: 11px; font-weight: 800;
                    padding: 4px 10px; border-radius: 99px;
                    text-transform: uppercase; letter-spacing: 1px;
                }
                .hitl-nav-title {
                    font-size: 14px; font-weight: 700; color: #fff;
                }
                .hitl-nav-body { padding: 20px; }
                .hitl-nav-step-info {
                    margin-bottom: 16px;
                }
                .hitl-nav-step-desc {
                    font-size: 13px; color: #cbd5e1; line-height: 1.5;
                    margin-bottom: 12px;
                }
                .hitl-nav-actions {
                    display: grid; grid-template-columns: 1fr 1fr; gap: 10px;
                    margin-bottom: 16px;
                }
                .hitl-nav-btn {
                    padding: 10px 16px; border-radius: 8px;
                    font-size: 12px; font-weight: 600; cursor: pointer;
                    border: none; transition: all 0.15s;
                    display: flex; align-items: center; gap: 8px;
                }
                .hitl-nav-btn-primary {
                    background: #f59e0b; color: #000;
                }
                .hitl-nav-btn-secondary {
                    background: rgba(255,255,255,0.08);
                    color: #cbd5e1;
                    border: 1px solid rgba(255,255,255,0.12) !important;
                }
                .hitl-nav-btn:hover { opacity: 0.88; transform: translateY(-1px); }
                .hitl-nav-navigation {
                    display: flex; justify-content: space-between; align-items: center;
                    padding-top: 16px;
                    border-top: 1px solid rgba(255,255,255,0.1);
                }
                .hitl-nav-nav-btn {
                    padding: 8px 12px; border-radius: 6px;
                    font-size: 11px; font-weight: 600; cursor: pointer;
                    border: 1px solid rgba(255,255,255,0.2);
                    background: rgba(255,255,255,0.05);
                    color: #cbd5e1;
                }
                .hitl-nav-jump {
                    display: flex; align-items: center; gap: 8px;
                }
                .hitl-nav-jump input {
                    width: 60px; padding: 6px 8px; border-radius: 4px;
                    border: 1px solid rgba(255,255,255,0.2);
                    background: rgba(255,255,255,0.05);
                    color: #fff; font-size: 11px;
                }
            `;
            document.head.appendChild(style);

            // HTML do navegador
            const navigator = document.createElement('div');
            navigator.id = 'hitl-navigator';
            navigator.innerHTML = `
                <div class="hitl-nav-header">
                    <span style="font-size:18px">🎯</span>
                    <span class="hitl-nav-badge">Passo ${stepInfo.current}/${stepInfo.total}</span>
                    <span class="hitl-nav-title">Navegador de Passos</span>
                </div>
                <div class="hitl-nav-body">
                    <div class="hitl-nav-step-info">
                        <div class="hitl-nav-step-desc">
                            <strong>Passo atual:</strong> ${stepInfo.description || 'Sem descrição'}
                        </div>
                        <div style="font-size:11px; color:#64748b;">
                            Status: <span style="color:${stepInfo.status === 'executed' ? '#22c55e' : stepInfo.status === 'error' ? '#ef4444' : '#f59e0b'}">${stepInfo.status}</span>
                        </div>
                    </div>
                    
                    <div class="hitl-nav-actions">
                        <button class="hitl-nav-btn hitl-nav-btn-primary" data-action="continue_auto">
                            ▶ Continuar auto
                        </button>
                        <button class="hitl-nav-btn hitl-nav-btn-secondary" data-action="redo_step">
                            🔄 Refazer este passo
                        </button>
                        <button class="hitl-nav-btn hitl-nav-btn-secondary" data-action="correct_selector">
                            ✏️ Corrigir seletor
                        </button>
                        <button class="hitl-nav-btn hitl-nav-btn-secondary" data-action="skip_step">
                            ⏭ Pular esta ação
                        </button>
                    </div>
                    
                    <div class="hitl-nav-navigation">
                        <button class="hitl-nav-nav-btn" data-action="prev_step">◄ Anterior</button>
                        <div class="hitl-nav-jump">
                            <span style="font-size:11px; color:#64748b;">Ir para:</span>
                            <input type="number" id="hitl-jump-input" min="1" max="${stepInfo.total}" value="${stepInfo.current}">
                            <button class="hitl-nav-nav-btn" data-action="jump_to">Ir</button>
                        </div>
                        <button class="hitl-nav-nav-btn" data-action="next_step">Próximo ►</button>
                    </div>
                </div>
            `;
            document.documentElement.appendChild(navigator);

            // Event listeners para os botões
            navigator.querySelectorAll('[data-action]').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const action = btn.getAttribute('data-action');
                    let payload = { acao: action };
                    
                    if (action === 'jump_to') {
                        const input = document.getElementById('hitl-jump-input');
                        payload.target_step = parseInt(input.value) || stepInfo.current;
                    }
                    
                    window.__hitl_captura__(JSON.stringify(payload));
                });
            });
        }""", step_info)


class FloatingPauseButton:
    """Botão flutuante sempre visível para controle manual de pausa."""

    def __init__(self, page: Page):
        self._page = page
        self._is_visible: bool = False

    async def show_pause_button(self) -> None:
        """Exibe botão de pausa flutuante"""
        await self._page.evaluate("""() => {
            // Remove botão anterior
            document.getElementById('hitl-pause-btn')?.remove();
            document.getElementById('hitl-pause-btn-style')?.remove();

            // CSS do botão
            const style = document.createElement('style');
            style.id = 'hitl-pause-btn-style';
            style.innerHTML = `
                #hitl-pause-btn {
                    position: fixed; bottom: 24px; right: 24px;
                    z-index: 2147483647;
                    background: #f97316; color: #000;
                    border: none; border-radius: 100px;
                    padding: 12px 24px; font-size: 13px; font-weight: 700;
                    cursor: pointer; font-family: 'Segoe UI', sans-serif;
                    box-shadow: 0 8px 24px rgba(249,115,22,0.5);
                    transition: all 0.15s;
                }
                #hitl-pause-btn:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 12px 32px rgba(249,115,22,0.6);
                }
            `;
            document.head.appendChild(style);

            // Botão
            const btn = document.createElement('button');
            btn.id = 'hitl-pause-btn';
            btn.innerHTML = '⏸ PAUSAR';
            document.documentElement.appendChild(btn);

            btn.addEventListener('click', () => {
                window.__hitl_captura__(JSON.stringify({ acao: 'pause_requested' }));
            });
        }""")
        self._is_visible = True

    async def hide_pause_button(self) -> None:
        """Remove botão de pausa"""
        await self._page.evaluate("""() => {
            document.getElementById('hitl-pause-btn')?.remove();
            document.getElementById('hitl-pause-btn-style')?.remove();
        }""")
        self._is_visible = False

    async def update_button_state(self, is_paused: bool) -> None:
        """Atualiza visual do botão (pausar/continuar)"""
        if is_paused:
            await self._page.evaluate("""() => {
                const btn = document.getElementById('hitl-pause-btn');
                if (btn) {
                    btn.innerHTML = '▶ CONTINUAR';
                    btn.style.background = '#22c55e';
                }
            }""")
        else:
            await self._page.evaluate("""() => {
                const btn = document.getElementById('hitl-pause-btn');
                if (btn) {
                    btn.innerHTML = '⏸ PAUSAR';
                    btn.style.background = '#f97316';
                }
            }""")


class EnhancedRadarSystem:
    """Sistema de captura de cliques para correção de seletores."""

    def __init__(self, page: Page):
        self._page = page
        self._is_active: bool = False
        self._captured_selector: str = ""

    async def activate_radar(self) -> None:
        """Ativa modo radar para captura de cliques"""
        self._is_active = True
        await self._page.evaluate(f"""() => {{
            if (window.__hitlRadarAtivo) return;
            window.__hitlRadarAtivo = true;

            const getSelector = {_JS_GET_BEST_SELECTOR};

            const handler = (e) => {{
                // Não captura cliques nos overlays do HITL
                if (e.target.closest('#hitl-overlay') || e.target.closest('#hitl-navigator')) return;

                e.preventDefault();
                e.stopPropagation();

                window.__hitlRadarAtivo = false;
                document.removeEventListener('click', handler, true);

                const seletor = getSelector(e.target);
                const label = e.target.innerText?.trim()?.substring(0, 60)
                            || e.target.getAttribute('aria-label')
                            || e.target.tagName.toLowerCase();

                // Feedback visual imediato (outline ciano pulsante)
                const prev = e.target.style.outline;
                e.target.style.outline = '3px solid #00e5e5';
                e.target.style.boxShadow = '0 0 16px #00e5e588';
                setTimeout(() => {{
                    e.target.style.outline = prev;
                    e.target.style.boxShadow = '';
                }}, 1200);

                window.__hitl_captura__(JSON.stringify({{ seletor, label, acao: 'capturou' }}));
            }};

            document.addEventListener('click', handler, true);
        }}""")

    async def deactivate_radar(self) -> None:
        """Desativa modo radar"""
        self._is_active = False
        await self._page.evaluate("""() => {
            window.__hitlRadarAtivo = false;
        }""")

    async def wait_for_click(self) -> str:
        """Aguarda clique do usuário e retorna seletor"""
        # Implementado via binding no HitlValidator
        return self._captured_selector


class ValidationEngine:
    """Gerencia validações preventivas e checkpoints."""

    def __init__(self, gemini_client):
        self._gemini = gemini_client
        self._checkpoint_enabled: bool = True
        self._preventive_enabled: bool = True

    async def validate_preventive(self, action: dict, selector: str) -> bool:
        """Validação preventiva antes de executar ação"""
        confidence = _nivel_confianca(action)
        return confidence != NivelConfianca.BAIXA

    async def validate_checkpoint(self, page: Page, expected_state: str) -> tuple[bool, str]:
        """Validação checkpoint após executar passo"""
        return await _validar_checkpoint(page, expected_state, "", None)

    def should_pause_preventive(self, confidence: NivelConfianca, is_auto_play: bool) -> bool:
        """Determina se deve pausar para validação preventiva"""
        return confidence == NivelConfianca.BAIXA and not is_auto_play

    def should_pause_checkpoint(self, is_auto_play: bool) -> bool:
        """Determina se deve pausar para checkpoint"""
        return not is_auto_play and self._checkpoint_enabled


class PersistenceManager:
    """Gerencia persistência de correções e atualização de roteiros."""

    def __init__(self):
        self._corrections: dict[str, str] = {}  # intencao -> seletor

    def save_correction(self, intention: str, selector: str) -> None:
        """Salva correção no mapa in-memory"""
        self._corrections[intention] = selector

    async def persist_to_brain_db(self, intention: str, selector: str) -> None:
        """Persiste seletor no Brain DB"""
        _registrar_sucesso_cache(intention, seletor=selector)

    async def update_score_engine(self, intention: str) -> None:
        """Atualiza score engine com sucesso"""
        try:
            _score_engine.registrar_execucao(intention, sucesso=True, confianca_captura=1.0)
        except Exception as e:
            logger.warning(f"Score engine não atualizado: {e}")

    def rewrite_roteiro_json(self, json_path: str) -> int:
        """Reescreve roteiro com seletores corrigidos"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                roteiro = json.load(f)

            alteracoes = 0
            for passo in roteiro.get("passos", []):
                for acao in passo.get("acoes_tecnicas", []):
                    intencao = acao.get("intencao_semantica", "")
                    if intencao in self._corrections:
                        seletor_novo = self._corrections[intencao]
                        if "elemento_alvo" not in acao:
                            acao["elemento_alvo"] = {}
                        acao["elemento_alvo"]["seletor_hint"] = seletor_novo
                        acao["elemento_alvo"]["confianca_captura"] = "alta"
                        alteracoes += 1

            if alteracoes > 0:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(roteiro, f, indent=2, ensure_ascii=False)

            return alteracoes
        except Exception as e:
            logger.warning(f"Erro ao reescrever roteiro: {e}")
            return 0


# ══════════════════════════════════════════════════════════════════════════════
# CLASSE PRINCIPAL — HitlValidator (REFATORADA)
# ══════════════════════════════════════════════════════════════════════════════

class HitlValidator:

    def __init__(self):
        # Componentes originais
        self._evento_humano: asyncio.Event = asyncio.Event()
        self._decisao_humana: dict = {}       # resultado da decisão do analista
        self._captura_seletor: str = ""       # seletor capturado do clique humano
        self._stats = {
            "passos_executados":    0,  # Renomeado de passos_ok
            "passos_com_erro":      0,  # Novo
            "correcoes_salvas":     0,  # Renomeado de passos_corrigidos
            "pausas_manuais":       0,  # Novo
            "pausas_automaticas":   0,  # Novo
            "passos_checkpoint":    0,  # Checkpoints com desvio detectado
            "intervencoes":         0,  # Mantido para compatibilidade
            "acoes_puladas":        0,  # Ações puladas pelo analista
        }
        # Mapa intencao_semantica → seletor_corrigido
        # Usado ao final para reescrever o roteiro JSON
        self._correcoes_seletores: dict = {}
        # Flag de desvio de estado — propagada do checkpoint para o próximo passo
        self._desvio_anterior: bool = False
        # Referência ao passo anterior — usada na Falha Dura para oferecer "Refazer"
        self._passo_anterior: dict | None = None
        # Step-by-step: contador de ações restantes em modo auto (0 = step-by-step)
        self._modo_auto_restante: int = 0

        # Novos componentes HITL melhorado
        self._auto_play_controller: AutoPlayController | None = None
        self._step_navigator: StepNavigator | None = None
        self._floating_pause_button: FloatingPauseButton | None = None
        self._enhanced_radar_system: EnhancedRadarSystem | None = None
        self._validation_engine: ValidationEngine | None = None
        self._persistence_manager: PersistenceManager = PersistenceManager()

        # Estado do sistema melhorado
        self._current_step_index: int = 0
        self._total_steps: int = 0
        self._is_navigator_open: bool = False
        # Decisão do analista no relatório final ('gravar' ou 'fechar')
        self._decisao_relatorio: str = "fechar"

    # ─── Setup da captura de clique humano ────────────────────────────────────

    async def _setup_captura_humana(self, page: Page) -> None:
        """
        Expõe binding Python no browser para capturar o clique do analista.
        Quando o radar está ativo, qualquer clique chama __hitl_captura__ com
        o seletor do elemento clicado.
        """
        async def _on_captura(source, args):
            try:
                payload = await args.json_value()
                dados   = json.loads(payload) if isinstance(payload, str) else payload

                # Captura de seletor (radar ativo)
                if "seletor" in dados:
                    self._captura_seletor = dados.get("seletor", "")
                    self._decisao_humana = {"acao": dados.get("acao", "capturou"), "seletor": self._captura_seletor}

                # Ações do navegador de passos
                elif "acao" in dados:
                    acao = dados["acao"]

                    # Controle de pausa
                    if acao == "pause_requested":
                        if self._auto_play_controller:
                            self._auto_play_controller.request_pause()
                        self._decisao_humana = {"acao": "pause_requested"}

                    # Ações do navegador
                    elif acao in ["continue_auto", "redo_step", "correct_selector", "skip_step",
                                  "prev_step", "next_step", "jump_to"]:
                        self._decisao_humana = dados

                    # Ações do overlay step-by-step
                    elif acao.startswith("step_"):
                        self._decisao_humana = dados

                    # Outras ações (compatibilidade com sistema antigo)
                    else:
                        self._decisao_humana = dados

                self._evento_humano.set()

            except Exception as e:
                logger.warning(f"Captura humana falhou: {e}")

        # Expõe o binding no contexto do browser
        await page.context.expose_binding(
            "__hitl_captura__",
            _on_captura,
            handle=True,
        )

        # Inicializa componentes novos
        self._auto_play_controller = AutoPlayController()
        self._step_navigator = StepNavigator(page)
        self._floating_pause_button = FloatingPauseButton(page)
        self._enhanced_radar_system = EnhancedRadarSystem(page)
        self._validation_engine = ValidationEngine(_gemini)

        # Exibe botão de pausa apenas em modo silent (auto-play)
        # Em step-by-step o controle é feito pelo overlay de cada ação
        if getattr(self, "_silent", False):
            await self._floating_pause_button.show_pause_button()

    async def _setup_persistent_pause_button(self, page: Page) -> None:
        """
        Configura listener para re-injetar o botão de pausa após cada navegação.
        Isso garante que o botão permaneça visível mesmo após page.goto() ou reloads.
        Só ativo em modo silent (auto-play) — em step-by-step o overlay controla o fluxo.
        """
        async def on_load():
            if not getattr(self, "_silent", False):
                return
            if self._floating_pause_button and not self._is_navigator_open:
                try:
                    await self._floating_pause_button.show_pause_button()
                except Exception as e:
                    logger.warning(f"Erro ao re-injetar botão de pausa: {e}")

        page.on("load", lambda: asyncio.create_task(on_load()))

    async def _ativar_radar(self, page: Page) -> None:
        """Ativa o radar de clique — captura o próximo clique do analista."""
        await page.evaluate(f"""() => {{
            // Mostra indicador visual de radar ativo
            const msg = document.getElementById('hitl-radar-msg');
            if (msg) msg.classList.add('ativo');

            if (window.__hitlRadarAtivo) return;
            window.__hitlRadarAtivo = true;

            const getSelector = {_JS_GET_BEST_SELECTOR};

            const handler = (e) => {{
                // Não captura cliques nos botões do próprio overlay
                if (e.target.closest('#hitl-overlay')) return;

                e.preventDefault();
                e.stopPropagation();

                window.__hitlRadarAtivo = false;
                document.removeEventListener('click', handler, true);

                const seletor = getSelector(e.target);
                const label   = e.target.innerText?.trim()?.substring(0, 60)
                              || e.target.getAttribute('aria-label')
                              || e.target.tagName.toLowerCase();

                // Feedback visual imediato
                const prev = e.target.style.outline;
                e.target.style.outline = '3px solid #00e5e5';
                e.target.style.boxShadow = '0 0 16px #00e5e588';
                setTimeout(() => {{
                    e.target.style.outline = prev;
                    e.target.style.boxShadow = '';
                }}, 1200);

                window.__hitl_captura__(JSON.stringify({{ seletor, label }}));
            }};

            document.addEventListener('click', handler, true);
        }}""")

    async def _adicionar_botoes(
        self, page: Page, botoes: list[dict]
    ) -> None:
        """
        Renderiza botões de decisão no overlay.
        Cada botão: { label, acao, estilo ('ok'|'sec') }
        """
        await page.evaluate("""(botoes) => {
            const container = document.getElementById('hitl-btns-container');
            if (!container) return;
            container.innerHTML = '';
            botoes.forEach(b => {
                const btn = document.createElement('button');
                btn.className = `hitl-btn hitl-btn-${b.estilo || 'sec'}`;
                btn.textContent = b.label;
                btn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    window.__hitl_captura__(JSON.stringify({ seletor: '', acao: b.acao }));
                });
                container.appendChild(btn);
            });
        }""", botoes)

    # ─── Aguarda decisão do analista ──────────────────────────────────────────

    async def _aguardar_decisao(self, timeout: int = TIMEOUT_HUMANO) -> dict:
        """Pausa a execução até o analista interagir ou timeout."""
        self._evento_humano.clear()
        self._decisao_humana = {}
        try:
            await asyncio.wait_for(self._evento_humano.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout de {timeout}s atingido. Pulando passo.")
            self._decisao_humana = {"acao": "timeout"}
        return self._decisao_humana

    # ─── Step-by-step: highlight do elemento clicado ─────────────────────────

    async def _highlight_element(self, page: Page, selector: str, success: bool) -> None:
        """
        Destaca o elemento que foi clicado/interagido com outline colorido:
          - Verde (#22c55e) = ação bem-sucedida
          - Vermelho (#ef4444) = ação falhou

        Usa CSS outline (não border) para não alterar layout.
        Inclui animação de pulse/glow para chamar atenção do analista.
        O highlight é removido quando o overlay é dispensado.
        """
        if not selector:
            return
        try:
            await page.evaluate(_JS_HIGHLIGHT_STEP_ELEMENT, {
                "selector": selector,
                "success": success,
            })
        except Exception as e:
            # Falha no highlight não deve interromper o fluxo
            logger.debug(f"[STEP] Highlight falhou para '{selector}': {e}")

    async def _remove_step_highlight(self, page: Page) -> None:
        """Remove o highlight do elemento step-by-step."""
        try:
            await page.evaluate(_JS_REMOVE_STEP_HIGHLIGHT)
        except Exception:
            pass  # Falha na remoção não é crítica

    # ─── Step-by-step: overlay e decisão após cada ação ───────────────────────

    async def _mostrar_overlay_step(
        self,
        page: Page,
        passo: dict | None,
        acao_tec: dict,
        resultado: bool,
        camada: str = "",
    ) -> None:
        """
        Exibe overlay minimalista step-by-step após executar uma ação.
        Mostra progresso (Passo X/Y — Ação Z/W), descrição da ação,
        camada que acertou e botões de decisão.
        Injeta HTML/CSS no browser via page.evaluate().
        """
        # Calcular progresso
        passo_atual = (self._current_step_index or 0) + 1
        passo_total = self._total_steps or 1

        # Calcular ação atual dentro do passo
        acoes = (passo or {}).get("acoes_tecnicas", [])
        acao_total = len(acoes) if acoes else 1
        # Determinar índice da ação atual dentro do passo
        acao_atual = 1
        intencao_atual = acao_tec.get("intencao_semantica", "")
        for i, a in enumerate(acoes):
            if a.get("intencao_semantica") == intencao_atual:
                acao_atual = i + 1
                break

        # Montar descrição
        alvo = acao_tec.get("elemento_alvo", {})
        label = alvo.get("label_curto", "")
        acao_tipo = acao_tec.get("acao", "clique")
        intencao = acao_tec.get("intencao_semantica", "")[:60]
        descricao = f'"{acao_tipo} → {label}"' if label else f'"{intencao}"'

        # Camada que acertou (ex: "via Brain", "via Sniper")
        camada_display = camada if camada else "—"

        # Destacar elemento clicado (verde=sucesso, vermelho=falha)
        seletor_highlight = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")
        if seletor_highlight:
            await self._highlight_element(page, seletor_highlight, resultado)

        # Remover overlay anterior e injetar novo
        await page.evaluate(_JS_REMOVE_STEP_OVERLAY)
        await page.evaluate(_JS_STEP_OVERLAY, {
            "passoAtual": passo_atual,
            "passoTotal": passo_total,
            "acaoAtual": acao_atual,
            "acaoTotal": acao_total,
            "descricao": descricao,
            "sucesso": resultado,
            "camada": camada_display,
        })

        logger.info(
            f"[STEP] {'✅' if resultado else '❌'} {acao_tipo} → {label} "
            f"| Passo {passo_atual}/{passo_total} Ação {acao_atual}/{acao_total} "
            f"| via {camada_display}"
        )

    async def _aguardar_decisao_step(self, timeout: int = 300) -> str:
        """
        Aguarda decisão do analista no overlay step-by-step.
        Retorna uma string indicando a ação escolhida:
          'ok'       — avançar (ação validada)
          'corrigir' — ativar radar para corrigir seletor
          'auto_N'   — ativar modo auto para N ações
          'pular'    — pular sem registrar

        Espera pelo evento __hitl_captura__ com payload step_*.
        """
        self._evento_humano.clear()
        self._decisao_humana = {}

        try:
            await asyncio.wait_for(self._evento_humano.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"[STEP] Timeout de {timeout}s — auto-aprovando ação")
            return "ok"

        acao = self._decisao_humana.get("acao", "")

        # Mapear ações do overlay step-by-step
        if acao == "step_ok":
            return "ok"
        elif acao == "step_corrigir":
            return "corrigir"
        elif acao.startswith("step_auto_"):
            # Extrai N de "step_auto_5"
            try:
                n = int(acao.replace("step_auto_", ""))
                return f"auto_{n}"
            except ValueError:
                return "auto_5"
        elif acao == "step_pular":
            return "pular"
        else:
            # Compatibilidade com outros payloads
            return "ok"

    async def _ativar_radar_step(self, page: Page) -> str:
        """
        Ativa o radar para o analista clicar no elemento correto.
        Retorna o seletor capturado ou string vazia se timeout/cancelado.

        Fluxo:
        1. Injeta JS do radar em TODOS os frames (main + iframes)
        2. Mostra indicador visual "Radar ativo — clique no elemento correto"
        3. Aguarda clique do analista (capturado via __hitl_captura__ binding)
        4. Retorna o seletor capturado

        IMPORTANTE: Senior X usa iframes extensivamente. O listener de clique
        precisa ser injetado em cada frame, não só no principal.
        """
        logger.info("[STEP] Radar step ativado — aguardando clique do analista")

        # Limpa estado anterior de captura
        self._captura_seletor = ""
        self._evento_humano.clear()
        self._decisao_humana = {}

        # 1. Mostra indicador visual no frame principal (overlay está lá)
        # Injeta CSS de animação primeiro
        await page.evaluate("""() => {
            if (!document.getElementById('hitl-radar-pulse-style')) {
                const st = document.createElement('style');
                st.id = 'hitl-radar-pulse-style';
                st.innerHTML = `
                    @keyframes hitl-radar-pulse {
                        0%,100% { opacity:1; } 50% { opacity:0.5; }
                    }
                    .hitl-radar-pulse-dot {
                        display:inline-block; width:8px; height:8px;
                        background:#ef4444; border-radius:50%;
                        animation: hitl-radar-pulse 1.2s ease infinite;
                    }
                `;
                document.head.appendChild(st);
            }
        }""")

        # Agora injeta o indicador visual
        await page.evaluate("""() => {
            const overlay = document.getElementById('hitl-step-overlay');
            if (!overlay) return;
            
            let radarMsg = document.getElementById('hitl-step-radar-msg');
            if (!radarMsg) {
                radarMsg = document.createElement('div');
                radarMsg.id = 'hitl-step-radar-msg';
                radarMsg.style.cssText = 'margin-top:8px;padding:8px 12px;background:rgba(239,68,68,0.15);border:1px solid rgba(239,68,68,0.4);border-radius:8px;text-align:center;color:#fca5a5;font-size:13px;display:flex;align-items:center;justify-content:center;gap:8px;flex-wrap:wrap;';
                overlay.appendChild(radarMsg);
            }
            
            radarMsg.innerHTML = '<span class="hitl-radar-pulse-dot"></span>'
                + '<span id="hitl-radar-text">Radar ativo — clique no elemento correto</span>'
                + '<span id="hitl-radar-countdown" style="font-weight:700;color:#f87171;">⏱ 120s</span>'
                + '<button id="hitl-radar-cancel-btn" style="margin-left:8px;padding:4px 10px;border:1px solid rgba(239,68,68,0.5);border-radius:6px;background:rgba(239,68,68,0.2);color:#fca5a5;font-size:11px;font-weight:600;cursor:pointer;">❌ Cancelar</button>';
            radarMsg.style.display = 'flex';
            
            // Cancel button handler
            const cancelBtn = document.getElementById('hitl-radar-cancel-btn');
            if (cancelBtn) {
                cancelBtn.onclick = (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (window.__hitlRadarCountdownId) {
                        clearInterval(window.__hitlRadarCountdownId);
                        window.__hitlRadarCountdownId = null;
                    }
                    radarMsg.style.display = 'none';
                    if (window.__hitl_captura__) {
                        window.__hitl_captura__(JSON.stringify({ seletor: '', acao: 'radar_cancelado' }));
                    }
                };
            }
        }""")

        # Countdown timer no frame principal (120s → 0)
        await page.evaluate("""() => {
            if (window.__hitlRadarCountdownId) clearInterval(window.__hitlRadarCountdownId);
            let remaining = 120;
            window.__hitlRadarCountdownId = setInterval(() => {
                remaining--;
                const countdownEl = document.getElementById('hitl-radar-countdown');
                if (countdownEl) countdownEl.textContent = '⏱ ' + remaining + 's';
                if (remaining <= 0) {
                    clearInterval(window.__hitlRadarCountdownId);
                    window.__hitlRadarCountdownId = null;
                    const radarMsg = document.getElementById('hitl-step-radar-msg');
                    if (radarMsg) radarMsg.style.display = 'none';
                    if (window.__hitl_captura__) {
                        window.__hitl_captura__(JSON.stringify({ seletor: '', acao: 'radar_cancelado' }));
                    }
                }
            }, 1000);
        }""")

        # 2. Injeta listener de clique em TODOS os frames (main + iframes)
        # IMPORTANTE: iframes não têm acesso ao binding expose_binding do contexto principal
        # Solução: usar postMessage para comunicar do iframe com o frame principal
        _radar_js = f"""() => {{
            if (window.__hitlRadarStepAtivo) return;
            window.__hitlRadarStepAtivo = true;

            const getSelector = {_JS_GET_BEST_SELECTOR};

            const handler = (e) => {{
                // Não captura cliques nos overlays (só existem no frame principal)
                if (e.target.closest('#hitl-step-overlay')) return;
                if (e.target.closest('#hitl-overlay')) return;

                e.preventDefault();
                e.stopPropagation();

                window.__hitlRadarStepAtivo = false;
                document.removeEventListener('click', handler, true);

                const seletor = getSelector(e.target);
                const label   = e.target.innerText?.trim()?.substring(0, 60)
                              || e.target.getAttribute('aria-label')
                              || e.target.tagName.toLowerCase();

                // Feedback visual imediato (cyan outline)
                const prev = e.target.style.outline;
                e.target.style.outline = '3px solid #00e5e5';
                e.target.style.boxShadow = '0 0 16px #00e5e588';
                setTimeout(() => {{
                    e.target.style.outline = prev;
                    e.target.style.boxShadow = '';
                }}, 1200);

                // Se estamos em um iframe, usa postMessage para comunicar com o frame principal
                if (window.self !== window.top) {{
                    window.top.postMessage({{
                        type: '__hitl_radar_captura__',
                        seletor: seletor,
                        label: label
                    }}, '*');
                }} else {{
                    // Frame principal — chama binding diretamente
                    if (window.__hitl_captura__) {{
                        window.__hitl_captura__(JSON.stringify({{ seletor, label }}));
                    }}
                }}
            }};

            document.addEventListener('click', handler, true);
        }}"""

        # Injeta no frame principal
        try:
            await page.evaluate(_radar_js)
        except Exception as e:
            logger.debug(f"[STEP] Radar inject main frame: {e}")

        # Injeta em todos os iframes da página
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                await frame.evaluate(_radar_js)
            except Exception as e:
                logger.debug(f"[STEP] Radar inject iframe '{frame.url[:60]}': {e}")

        # 3. Setup listener para postMessage (captura cliques de iframes)
        await page.evaluate("""() => {
            if (window.__hitlRadarPostMessageSetup) return;
            window.__hitlRadarPostMessageSetup = true;

            window.addEventListener('message', (e) => {
                if (e.data && e.data.type === '__hitl_radar_captura__') {
                    // Clique capturado em um iframe — repassa para o binding
                    if (window.__hitl_captura__) {
                        window.__hitl_captura__(JSON.stringify({
                            seletor: e.data.seletor,
                            label: e.data.label
                        }));
                    }
                }
            }, false);
        }""")

        # Aguarda captura do clique (timeout de 120s — analista pode precisar navegar)
        try:
            await asyncio.wait_for(self._evento_humano.wait(), timeout=120)
        except asyncio.TimeoutError:
            logger.warning("[STEP] Timeout de 120s no radar step — cancelando captura")
            # Desativa radar em todos os frames + limpa countdown
            _cleanup_js = """() => {
                window.__hitlRadarStepAtivo = false;
                if (window.__hitlRadarCountdownId) {
                    clearInterval(window.__hitlRadarCountdownId);
                    window.__hitlRadarCountdownId = null;
                }
                const radarMsg = document.getElementById('hitl-step-radar-msg');
                if (radarMsg) radarMsg.style.display = 'none';
            }"""
            try:
                await page.evaluate(_cleanup_js)
            except Exception:
                pass
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
                except Exception:
                    pass
            return ""

        # Check if radar was cancelled by the analyst
        if self._decisao_humana.get("acao") == "radar_cancelado":
            logger.info("[STEP] Radar cancelado pelo analista")
            # Limpa flag nos iframes
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
                except Exception:
                    pass
            return ""

        # Extrai seletor capturado
        seletor_capturado = self._decisao_humana.get("seletor", "")
        if not seletor_capturado:
            logger.warning("[STEP] Radar: nenhum seletor foi capturado")
            return ""

        logger.info(f"[STEP] Seletor capturado via radar: {seletor_capturado}")

        # Limpa countdown no frame principal após captura bem-sucedida
        try:
            await page.evaluate("""() => {
                if (window.__hitlRadarCountdownId) {
                    clearInterval(window.__hitlRadarCountdownId);
                    window.__hitlRadarCountdownId = null;
                }
                const radarMsg = document.getElementById('hitl-step-radar-msg');
                if (radarMsg) {
                    radarMsg.style.background = 'rgba(34,197,94,0.15)';
                    radarMsg.style.borderColor = 'rgba(34,197,94,0.4)';
                    const textEl = document.getElementById('hitl-radar-text');
                    if (textEl) textEl.textContent = '✅ Seletor capturado!';
                    const countdownEl = document.getElementById('hitl-radar-countdown');
                    if (countdownEl) countdownEl.style.display = 'none';
                    const cancelBtn = document.getElementById('hitl-radar-cancel-btn');
                    if (cancelBtn) cancelBtn.style.display = 'none';
                }
            }""")
        except Exception:
            pass

        # Desativa radar em todos os frames
        for frame in page.frames:
            try:
                await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
            except Exception:
                pass

        return seletor_capturado

    # ─── Pausa 🟡 PREVENTIVA (baixa confiança antes de clicar) ───────────────

    async def _pausa_preventiva(
        self, page: Page, acao_tec: dict, seletor_encontrado: str
    ) -> str:
        """
        Pergunta ao analista ANTES de executar uma ação de baixa confiança.
        Retorna: 'confirmar' | 'capturou' (seletor corrigido) | 'pular'
        """
        self._stats["intervencoes"] += 1
        alvo   = acao_tec.get("elemento_alvo", {})
        label  = alvo.get("label_curto", "?")
        intenc = acao_tec.get("intencao_semantica", "")[:80]

        await _injetar_overlay(
            page,
            TipoPausa.PREVENTIVA,
            titulo="Baixa Confiança",
            mensagem=(
                f'Encontrei um elemento para <b>"{label}"</b> mas com confiança baixa.<br><br>'
                f"O elemento destacado em âmbar é o correto?"
            ),
            instrucao="Confirme ou clique no elemento certo na tela",
            nome_acao=intenc,
        )


        if seletor_encontrado:
            await _highlight_hitl(page, seletor_encontrado, "#f59e0b")

        await self._adicionar_botoes(page, [
            {"label": "✓ Sim, pode clicar",    "acao": "confirmar", "estilo": "ok"},
            {"label": "✕ Não, vou mostrar",    "acao": "capturar",  "estilo": "sec"},
            {"label": "⏭ Pular esta ação",     "acao": "pular",     "estilo": "sec"},
        ])

        decisao = await self._aguardar_decisao()
        acao    = decisao.get("acao", "pular")

        if seletor_encontrado:
            await _remover_highlight_hitl(page, seletor_encontrado)

        if acao == "capturar":
            # Ativa radar para o analista apontar o elemento certo
            await self._ativar_radar(page)
            decisao = await self._aguardar_decisao()
            acao    = decisao.get("acao", "pular")

        await _remover_overlay(page)
        return acao  # 'confirmar' | 'capturou' | 'pular'

    # ─── Pausa 🟠 CHECKPOINT (desvio de estado após passo) ───────────────────

    async def _pausa_checkpoint(
        self, page: Page, passo: dict, observacao: str
    ) -> str:
        """
        Notifica o analista sobre desvio de estado após um passo.
        Retorna: 'continuar' | 'refazer' | 'pular'
        """
        self._stats["intervencoes"] += 1
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        id_p    = passo.get("id_passo", "?")

        await _injetar_overlay(
            page,
            TipoPausa.CHECKPOINT,
            titulo=f"Passo {id_p} — Verificação",
            mensagem=(
                f"O passo foi executado, mas a tela parece diferente do esperado.<br><br>"
                f"<b>Esperado:</b> {tooltip}<br>"
                f"<b>Observado:</b> {observacao}"
            ),
            instrucao="Verifique a tela e escolha como continuar",
        )

        await self._adicionar_botoes(page, [
            {"label": "✓ Está correto",    "acao": "continuar", "estilo": "ok"},
            {"label": "↩ Refazer passo",   "acao": "refazer",   "estilo": "sec"},
            {"label": "⏭ Próximo passo",   "acao": "pular",     "estilo": "sec"},
        ])

        decisao = await self._aguardar_decisao()
        await _remover_overlay(page)
        return decisao.get("acao", "continuar")

    # ─── Pausa 🔴 FALHA DURA (todas as camadas falharam) ─────────────────────

    async def _pausa_falha_dura(
        self,
        page: Page,
        acao_tec: dict,
        passo_anterior: dict | None = None,
        desvio_anterior: bool = False,
    ) -> str:
        """
        Oferece três caminhos ao analista quando todas as camadas falharam:

          'mostrar_aqui'   — radar imediato (tela já está no estado certo)
          'navegar'        — analista navega livremente e confirma com botão flutuante
          'refazer_passo'  — volta ao passo anterior para corrigir a causa raiz
          'pular'          — pula esta ação

        Exibe screenshot de referência quando disponível.
        Exibe aviso de desvio anterior quando desvio_anterior=True.
        """
        self._stats["intervencoes"] += 1
        alvo   = acao_tec.get("elemento_alvo", {})
        label  = alvo.get("label_curto", "?")
        intenc = acao_tec.get("intencao_semantica", "")[:80]

        # Monta mensagem com contexto de desvio anterior
        aviso_desvio = ""
        if desvio_anterior:
            aviso_desvio = (
                '<div style="margin-bottom:10px;padding:8px 10px;'
                'background:rgba(249,115,22,0.12);border:1px solid rgba(249,115,22,0.4);'
                'border-radius:8px;font-size:11px;color:#fdba74;line-height:1.4;">'
                '⚠️ <b>Atenção:</b> o passo anterior teve desvio de estado. '
                'Esta falha pode ser consequência disso — a tela pode estar diferente do esperado.'
                '</div>'
            )

        # Monta miniatura da screenshot de referência se disponível
        ref_img_html = ""
        ref_b64 = alvo.get("screenshot_referencia")
        if ref_b64:
            ref_img_html = (
                '<div style="margin-bottom:10px;">'
                '<div style="font-size:10px;color:#64748b;font-weight:600;'
                'text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">'
                '📸 Como a tela deveria estar:</div>'
                f'<img src="data:image/jpeg;base64,{ref_b64}" '
                'style="width:100%;border-radius:6px;border:1px solid rgba(255,255,255,0.1);'
                'opacity:0.85;" />'
                '</div>'
            )

        mensagem = (
            f'{aviso_desvio}'
            f'{ref_img_html}'
            f'Esgotei todas as tentativas para encontrar <b>"{label}"</b>.<br><br>'
            f'Como você quer resolver?'
        )

        await _injetar_overlay(
            page,
            TipoPausa.FALHA_DURA,
            titulo="Elemento Não Encontrado",
            mensagem=mensagem,
            instrucao="Escolha como continuar",
            nome_acao=intenc,
        )

        # Monta botões — "Refazer passo anterior" só aparece se há passo anterior
        botoes = [
            {"label": "🖱 Mostrar aqui",      "acao": "mostrar_aqui",  "estilo": "ok"},
            {"label": "🧭 Navegar e mostrar", "acao": "navegar",       "estilo": "sec"},
        ]
        if passo_anterior is not None:
            label_passo = passo_anterior.get("pedagogia", {}).get("tooltip_dap", "") or \
                          f"Passo {passo_anterior.get('id_passo', '?')}"
            botoes.append({
                "label":  f"↩ Refazer: {label_passo[:30]}",
                "acao":   "refazer_passo",
                "estilo": "sec",
            })
        botoes.append({"label": "⏭ Pular esta ação", "acao": "pular", "estilo": "sec"})

        await self._adicionar_botoes(page, botoes)

        decisao = await self._aguardar_decisao()
        acao    = decisao.get("acao", "pular")

        if acao == "mostrar_aqui":
            # Radar imediato — tela já está no estado certo
            await self._ativar_radar(page)
            decisao = await self._aguardar_decisao()
            acao    = decisao.get("acao", "pular")

        elif acao == "navegar":
            # Remove overlay, injeta botão flutuante, aguarda confirmação do analista
            await _remover_overlay(page)
            await _injetar_botao_pronto(page)
            print("   🧭 Modo navegação — aguardando analista confirmar tela certa...", flush=True)
            decisao = await self._aguardar_decisao(timeout=TIMEOUT_HUMANO)
            await _remover_botao_pronto(page)

            if decisao.get("acao") == "nav_pronto":
                # Analista confirmou — agora ativa o radar
                await _injetar_overlay(
                    page,
                    TipoPausa.FALHA_DURA,
                    titulo="Radar Ativo",
                    mensagem=f'Agora clique no elemento correto para <b>"{label}"</b>.',
                    instrucao="Clique no elemento certo — o Radar está ativo",
                    nome_acao=intenc,
                )
                await self._adicionar_botoes(page, [
                    {"label": "⏭ Pular esta ação", "acao": "pular", "estilo": "sec"},
                ])
                await self._ativar_radar(page)
                decisao = await self._aguardar_decisao()
                acao    = decisao.get("acao", "pular")
            else:
                acao = decisao.get("acao", "pular")

        await _remover_overlay(page)
        return acao  # 'capturou' | 'refazer_passo' | 'pular'

    # ─── Salva seletor capturado no Brain ─────────────────────────────────────

    def _salvar_correcao_no_brain(self, acao_tec: dict, seletor_capturado: str) -> None:
        """
        Persiste o seletor ensinado pelo analista no Brain DB e atualiza score_engine.
        Na próxima execução, o sistema vai direto nele (alta confiança).
        Marca com hitl_corrigido=1 para proteger contra invalidação automática.
        """
        if not seletor_capturado:
            return
        intencao = acao_tec.get("intencao_semantica", "")
        alvo     = acao_tec.get("elemento_alvo", {})
        iframe   = alvo.get("iframe_hint")
        if intencao:
            # Atualiza brain.db — seletor aprendido pelo analista com hitl_corrigido=1
            _registrar_sucesso_cache(
                intencao, seletor=seletor_capturado, iframe=iframe, hitl_corrigido=True
            )
            logger.info(f"Brain atualizado (hitl_corrigido=1): '{intencao[:60]}' → '{seletor_capturado}'")

            # Atualiza scores.db — correção HITL equivale a execução bem-sucedida
            # com confiança máxima (analista confirmou o elemento correto)
            try:
                _score_engine.registrar_execucao(
                    intencao,
                    sucesso=True,
                    confianca_captura=1.0,
                )
            except Exception as e:
                logger.warning(f"score_engine não atualizado (não crítico): {e}")

            self._stats["correcoes_salvas"] += 1
            # Guarda também no mapa in-memory para reescrita do JSON
            self._correcoes_seletores[intencao] = seletor_capturado

    # ─── Login ────────────────────────────────────────────────────────────────

    async def _fazer_login(self, page: Page) -> bool:
        SENIOR_URL = os.getenv("SENIOR_URL",
            "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        usuario = os.getenv("SENIOR_USER_EXECUTE")
        senha   = os.getenv("SENIOR_PASS_EXECUTE")

        if not usuario or not senha:
            print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)", flush=True)
            return False

        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")

            campo_usr = page.locator(
                "input[type='text'], input[type='email'], [placeholder*='usuario']"
            ).first
            await campo_usr.wait_for(state="visible", timeout=10000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.5)

            try:
                await page.locator(
                    "button:has-text('Próximo'), button:has-text('Proximo'), "
                    "button:has-text('Continuar')"
                ).first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")

            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("load", timeout=30_000)
            await asyncio.sleep(2.0)

            # Re-injeta o botão de pausa após login (página foi recarregada)
            if self._floating_pause_button and getattr(self, "_silent", False):
                await self._floating_pause_button.show_pause_button()

            print("✅ Login OK.", flush=True)
            return True

        except Exception as e:
            logger.warning(f"Auto-login falhou: {e}")
            print("⚠️  Login automático falhou. Conclua manualmente (60s).", flush=True)
            try:
                await page.wait_for_load_state("networkidle", timeout=60_000)
                await asyncio.sleep(3.0)

                # Re-injeta o botão de pausa após login manual
                if self._floating_pause_button and getattr(self, "_silent", False):
                    await self._floating_pause_button.show_pause_button()

                return True
            except Exception:
                print("❌ Timeout de login manual.", flush=True)
                return False

    # ─── Executar uma ação técnica com HITL ───────────────────────────────────

    async def _executar_acao_com_hitl(
        self,
        page: Page,
        acao_tec: dict,
        passo_anterior: dict | None = None,
        desvio_anterior: bool = False,
        passo: dict | None = None,
    ) -> str:
        """
        Tenta executar uma ação usando vision_engine.
        Modo step-by-step: pausa APÓS cada ação para o analista validar.
        Se confiança baixa → pausa preventiva (exceto em modo --silent).
        Se falha total → pausa falha dura com opções de navegação e refazer.

        O modo auto (_modo_auto_restante > 0) permite pular N pausas
        consecutivas quando o analista confia no fluxo. Se uma ação falha
        durante modo auto, volta automaticamente para step-by-step.

        Retorna:
          'ok'            — ação executada com sucesso
          'pulou'         — ação pulada pelo analista
          'refazer_passo' — analista pediu para refazer o passo anterior
        """
        if acao_tec.get("acao") == "concluir_video":
            return "ok"

        silent = getattr(self, "_silent", False)

        confianca = _nivel_confianca(acao_tec)
        alvo      = acao_tec.get("elemento_alvo", {})
        seletor   = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")

        # ── 🟡 Pausa preventiva (baixa confiança antes de tentar) ────────────
        # Em modo --silent, pula a pausa preventiva e tenta diretamente
        if confianca == NivelConfianca.BAIXA and not silent:
            resposta = await self._pausa_preventiva(page, acao_tec, seletor)

            if resposta == "pular":
                self._stats["acoes_puladas"] += 1
                return "pulou"

            if resposta == "capturou" and self._captura_seletor:
                # Analista apontou o elemento certo — usa diretamente
                self._salvar_correcao_no_brain(acao_tec, self._captura_seletor)
                acao_corrigida = dict(acao_tec)
                if "elemento_alvo" not in acao_corrigida:
                    acao_corrigida["elemento_alvo"] = {}
                acao_corrigida["elemento_alvo"]["seletor_hint"] = self._captura_seletor
                sucesso = await encontrar_e_clicar(page, acao_corrigida)
                return "ok" if sucesso else "pulou"

            # 'confirmar' → tenta normalmente

        # ── Execução via vision_engine (todas as 7 camadas) ──────────────────
        sucesso = await encontrar_e_clicar(page, acao_tec)

        # ── 🔴 Falha dura — todas as camadas esgotadas ───────────────────────
        if not sucesso:
            # Se estava em modo auto, falha força volta ao step-by-step
            if self._modo_auto_restante > 0:
                self._modo_auto_restante = 0
                logger.info("Falha em modo auto → voltando para step-by-step")

            resposta = await self._pausa_falha_dura(
                page,
                acao_tec,
                passo_anterior=passo_anterior,
                desvio_anterior=desvio_anterior,
            )

            if resposta == "pular":
                self._stats["acoes_puladas"] += 1
                return "pulou"

            if resposta == "refazer_passo":
                return "refazer_passo"

            if resposta == "capturou" and self._captura_seletor:
                self._salvar_correcao_no_brain(acao_tec, self._captura_seletor)
                acao_corrigida = dict(acao_tec)
                if "elemento_alvo" not in acao_corrigida:
                    acao_corrigida["elemento_alvo"] = {}
                acao_corrigida["elemento_alvo"]["seletor_hint"] = self._captura_seletor
                sucesso = await encontrar_e_clicar(page, acao_corrigida)

            return "ok" if sucesso else "pulou"

        # ── Step-by-step: pausa após cada ação bem-sucedida ──────────────────
        # Em modo --silent, não pausa (comportamento legado)
        if not silent:
            if self._modo_auto_restante > 0:
                # Modo auto: decrementa e avança sem pausa
                self._modo_auto_restante -= 1
            else:
                # Step-by-step (padrão): mostra overlay e aguarda decisão
                camada_vencedora = obter_ultima_camada_vencedora() if sucesso else "—"
                await self._mostrar_overlay_step(page, passo, acao_tec, sucesso, camada=camada_vencedora)
                decisao = await self._aguardar_decisao_step()

                # Remove overlay e highlight após decisão
                # (exceto "corrigir" — o radar precisa do overlay para mostrar o cronômetro)
                if decisao != "corrigir":
                    await page.evaluate(_JS_REMOVE_STEP_OVERLAY)
                await self._remove_step_highlight(page)

                if decisao == "ok":
                    # Reforçar memória no Brain — analista confirmou que ação está correta
                    intencao = acao_tec.get("intencao_semantica", "")
                    if intencao:
                        _registrar_sucesso_cache(intencao)
                elif decisao == "corrigir":
                    seletor_corrigido = await self._ativar_radar_step(page)
                    # Agora sim remove o overlay (radar já terminou)
                    await page.evaluate(_JS_REMOVE_STEP_OVERLAY)
                    if seletor_corrigido:
                        self._salvar_correcao_no_brain(acao_tec, seletor_corrigido)
                        # Executa o clique com o seletor corrigido — o analista
                        # apontou o elemento certo, então o sistema deve clicar nele
                        # imediatamente (sem precisar que o analista clique de novo)
                        acao_corrigida = dict(acao_tec)
                        if "elemento_alvo" not in acao_corrigida:
                            acao_corrigida["elemento_alvo"] = {}
                        acao_corrigida["elemento_alvo"]["seletor_hint"] = seletor_corrigido
                        await encontrar_e_clicar(page, acao_corrigida)
                elif decisao.startswith("auto_"):
                    try:
                        self._modo_auto_restante = int(decisao.split("_")[1])
                    except (IndexError, ValueError):
                        self._modo_auto_restante = 5  # fallback padrão
                elif decisao == "pular":
                    pass  # avança sem registrar sucesso

        return "ok"

    # ─── Executar um passo completo com checkpoint ────────────────────────────

    async def _executar_passo(
        self, page: Page, passo: dict, idx: int, total: int
    ) -> str:
        """
        Executa um passo completo com checkpoint pós-execução.

        Retorna:
          'ok'            — passo concluído normalmente
          'refazer_passo' — analista pediu para refazer este passo (sinaliza ao loop externo)
        """
        id_p    = passo.get("id_passo", idx + 1)
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        ancora  = passo.get("pedagogia", {}).get("ancora",  "")
        acoes   = passo.get("acoes_tecnicas", [])
        is_fim  = passo.get("is_conclusao", False)

        # Aviso contextual quando o passo anterior teve desvio de estado
        aviso_desvio = ""
        if self._desvio_anterior:
            aviso_desvio = " ⚠️ [desvio anterior]"

        print(f"\n── Passo {id_p}/{total} {tooltip or ''}{aviso_desvio}", flush=True)

        if is_fim:
            print(f"   [CONCLUSÃO] {ancora[:80]}", flush=True)
            self._stats["passos_executados"] += 1
            self._desvio_anterior = False
            return "ok"

        # Executa todas as ações do passo, propagando contexto de desvio e passo anterior
        pediu_refazer = False
        for acao_tec in acoes:
            resultado = await self._executar_acao_com_hitl(
                page,
                acao_tec,
                passo_anterior=self._passo_anterior,
                desvio_anterior=self._desvio_anterior,
                passo=passo,
            )
            label  = acao_tec.get("elemento_alvo", {}).get("label_curto", "?")
            status = "✅" if resultado == "ok" else ("↩" if resultado == "refazer_passo" else "⏭")
            print(f"   {status} {acao_tec.get('acao','?')} → {label}", flush=True)

            if resultado == "refazer_passo":
                pediu_refazer = True
                break  # interrompe as ações restantes deste passo

            await asyncio.sleep(0.6)

        # Se o analista pediu refazer o passo anterior, sinaliza ao loop externo
        if pediu_refazer:
            self._desvio_anterior = False
            return "refazer_passo"

        # ── 🟠 Checkpoint: valida estado após o passo ─────────────────────────
        # Checkpoint só roda em modo --silent (auto-play).
        # Em step-by-step o analista já valida cada ação individualmente.
        silent = getattr(self, "_silent", False)
        if CHECKPOINT_HABILITADO and tooltip and silent:
            # Extrai screenshot de referência da última ação do passo
            screenshot_ref = None
            for acao_tec in reversed(acoes):
                ref = (acao_tec.get("elemento_alvo") or {}).get("screenshot_referencia")
                if ref:
                    screenshot_ref = ref
                    break

            estado_ok, observacao = await _validar_checkpoint(
                page, tooltip, ancora, screenshot_ref_b64=screenshot_ref
            )

            if not estado_ok:
                print(f"   ⚠️  Checkpoint: {observacao}", flush=True)
                self._stats["passos_checkpoint"] += 1
                decisao = await self._pausa_checkpoint(page, passo, observacao)

                if decisao == "refazer":
                    print(f"   ↩ Refazendo passo {id_p}...", flush=True)
                    self._desvio_anterior = False  # refazendo — limpa flag
                    for acao_tec in acoes:
                        await self._executar_acao_com_hitl(page, acao_tec, passo=passo)
                        await asyncio.sleep(0.6)
                    # Após refazer, limpa desvio
                    self._desvio_anterior = False
                else:
                    # Analista continuou mesmo com desvio — propaga flag ao próximo passo
                    self._desvio_anterior = (decisao != "continuar" or not estado_ok)
            else:
                print(f"   ✓ Checkpoint OK: {observacao}", flush=True)
                self._desvio_anterior = False
        else:
            # Sem checkpoint — limpa flag de desvio
            self._desvio_anterior = False

        self._stats["passos_executados"] += 1
        return "ok"

    # ─── Ponto de entrada principal ───────────────────────────────────────────


    async def _exibir_relatorio_final(self, page: Page = None) -> str:
        """
        Exibe relatório final com estatísticas atualizadas.
        Se page está disponível, injeta overlay no browser e aguarda decisão.
        Retorna: 'gravar' ou 'fechar' (decisão do analista).
        """
        total = self._stats["passos_executados"]
        correcoes = self._stats["correcoes_salvas"]
        puladas = self._stats["acoes_puladas"]

        # Calcular taxa de acerto: (total - correções - puladas) / total * 100
        if total > 0:
            taxa_acerto = round(((total - correcoes - puladas) / total) * 100, 1)
        else:
            taxa_acerto = 0.0

        # Relatório no terminal
        print(f"\n{'═'*55}", flush=True)
        print("  RELATÓRIO HITL", flush=True)
        print(f"{'═'*55}", flush=True)
        print(f"  Ações executadas:      {total}", flush=True)
        print(f"  Correções feitas:      {correcoes}", flush=True)
        print(f"  Ações puladas:         {puladas}", flush=True)
        print(f"  Taxa de acerto:        {taxa_acerto}%", flush=True)
        print(f"  Passos com erro:       {self._stats['passos_com_erro']}", flush=True)
        print(f"{'═'*55}\n", flush=True)

        if correcoes > 0:
            print(f"✅ {correcoes} correção(ões) salvas no Brain.", flush=True)
            print("   Próxima execução vai acertar sem precisar de ajuda.", flush=True)

        # Overlay no browser (se page disponível)
        decisao = "fechar"
        if page:
            try:
                # Remove overlays anteriores (step, pause button)
                await page.evaluate(_JS_REMOVE_STEP_OVERLAY)
                await page.evaluate(_JS_REMOVE_STEP_HIGHLIGHT)

                # Injeta overlay de relatório final
                await page.evaluate(_JS_RELATORIO_FINAL, {
                    "totalAcoes": total,
                    "correcoes": correcoes,
                    "acoesPuladas": puladas,
                    "taxaAcerto": taxa_acerto,
                })

                # Aguarda decisão do analista (Gravar ou Fechar)
                logger.info("[HITL] Relatório final exibido. Aguardando decisão do analista...")
                resultado = await self._aguardar_decisao(timeout=300)  # 5 min timeout
                acao = resultado.get("acao", "")

                if acao == "relatorio_gravar":
                    decisao = "gravar"
                    print("🎬 Analista escolheu: Gravar agora", flush=True)
                else:
                    decisao = "fechar"
                    print("✖ Analista escolheu: Fechar sem gravar", flush=True)

            except Exception as e:
                logger.warning(f"Overlay de relatório falhou (não crítico): {e}")
                decisao = "fechar"

        return decisao

    async def _marcar_hitl_validado(self, caminho_json: str) -> None:
        """Marca o roteiro como HITL validado no dashboard."""
        try:
            import urllib.error
            import urllib.parse
            import urllib.request
            arquivo = os.path.basename(caminho_json)
            req = urllib.request.Request(
                f"http://localhost:8000/api/marcar-hitl-validado/{urllib.parse.quote(arquivo)}",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            print("✅ Roteiro marcado como HITL validado no Dashboard.", flush=True)
        except Exception as e:
            print(f"   (Servidor offline — marcar HITL manualmente: {e})", flush=True)

    def _salvar_correcao_no_brain(self, acao_tec: dict, seletor_capturado: str) -> None:
        """
        Persiste o seletor ensinado pelo analista no Brain DB e atualiza score_engine.
        Na próxima execução, o sistema vai direto nele (alta confiança).
        Marca com hitl_corrigido=1 para proteger contra invalidação automática.
        """
        if not seletor_capturado:
            return
        intencao = acao_tec.get("intencao_semantica", "")
        alvo     = acao_tec.get("elemento_alvo", {})
        iframe   = alvo.get("iframe_hint")
        if intencao:
            # Atualiza brain.db — seletor aprendido pelo analista com hitl_corrigido=1
            _registrar_sucesso_cache(
                intencao, seletor=seletor_capturado, iframe=iframe, hitl_corrigido=True
            )
            logger.info(f"Brain atualizado (hitl_corrigido=1): '{intencao[:60]}' → '{seletor_capturado}'")

            # Atualiza scores.db — correção HITL equivale a execução bem-sucedida
            # com confiança máxima (analista confirmou o elemento correto)
            try:
                _score_engine.registrar_execucao(
                    intencao,
                    sucesso=True,
                    confianca_captura=1.0,
                )
            except Exception as e:
                logger.warning(f"score_engine não atualizado (não crítico): {e}")

            self._stats["correcoes_salvas"] += 1
            # Guarda também no mapa in-memory para reescrita do JSON
            self._correcoes_seletores[intencao] = seletor_capturado
            self._persistence_manager.save_correction(intencao, seletor_capturado)

    def _reescrever_roteiro_json(self, caminho_json: str) -> None:
        """
        Atualiza o roteiro JSON com os seletores corrigidos pelo analista.
        Assim as correções sobrevivem mesmo sem o brain.db.
        """
        try:
            with open(caminho_json, "r", encoding="utf-8") as f:
                roteiro = json.load(f)

            alteracoes = 0
            for passo in roteiro.get("passos", []):
                for acao in passo.get("acoes_tecnicas", []):
                    intencao = acao.get("intencao_semantica", "")
                    if intencao in self._correcoes_seletores:
                        seletor_novo = self._correcoes_seletores[intencao]
                        if "elemento_alvo" not in acao:
                            acao["elemento_alvo"] = {}
                        acao["elemento_alvo"]["seletor_hint"] = seletor_novo
                        acao["elemento_alvo"]["confianca_captura"] = "alta"
                        alteracoes += 1

            if alteracoes > 0:
                with open(caminho_json, "w", encoding="utf-8") as f:
                    json.dump(roteiro, f, indent=2, ensure_ascii=False)
                print(f"✅ Roteiro atualizado com {alteracoes} seletor(es) corrigido(s).", flush=True)

        except Exception as e:
            logger.warning(f"Não foi possível reescrever o roteiro: {e}")

    async def executar(self, caminho_json: str, silent: bool = False) -> None:
        self._silent = silent
        print(f"\n{'═'*55}", flush=True)
        print(f"  VALIDADOR HITL — {os.path.basename(caminho_json)}", flush=True)
        if silent:
            print("  MODO SILENCIOSO — só pausa em falha dura", flush=True)
        print(f"{'═'*55}\n", flush=True)

        with open(caminho_json, "r", encoding="utf-8") as f:
            roteiro = json.load(f)

        passos = roteiro.get("passos", [])
        total  = len(passos)
        nome   = roteiro.get("metadata", {}).get("nome_aula", "Aula")

        self._total_steps = total

        print(f"📋 {nome} — {total} passos", flush=True)
        print(f"🔍 Checkpoint Gemini: {'ATIVO' if CHECKPOINT_HABILITADO else 'DESABILITADO'}\n",
              flush=True)

        async with async_playwright() as pw:
            # ── Detecta monitor auxiliar (mesmo padrão do main.py) ───────────
            _window_x, _window_y = 0, 0
            try:
                from screeninfo import get_monitors
                monitores = get_monitors()
                monitor_aux = next((m for m in monitores if not m.is_primary), None)
                if monitor_aux:
                    _window_x = monitor_aux.x
                    _window_y = monitor_aux.y
                    print(f"[Monitor] Usando monitor auxiliar: {monitor_aux.name} {monitor_aux.width}x{monitor_aux.height} pos=({_window_x},{_window_y})", flush=True)
                else:
                    print("[Monitor] Monitor auxiliar não encontrado — usando monitor primário.", flush=True)
            except Exception as e:
                print(f"[Monitor] screeninfo falhou ({e}) — usando posição padrão.", flush=True)

            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--start-maximized",
                    f"--window-position={_window_x},{_window_y}",
                    "--disable-infobars",
                    "--disable-features=Translate",
                    "--lang=pt-BR",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            context = await browser.new_context(
                no_viewport=True,
                locale="pt-BR",
                bypass_csp=True,           # necessário para injetar JS em páginas com CSP restritivo
                ignore_https_errors=True,  # evita falhas em ambientes com certificados self-signed
            )
            page    = await context.new_page()

            # ── Maximiza via CDP no monitor correto ──────────────────────────
            # --start-maximized + --window-position falha no Windows em monitores
            # não-primários. CDP Browser.setWindowBounds é a forma confiável.
            try:
                cdp = await context.new_cdp_session(page)
                wid_resp = await cdp.send("Browser.getWindowForTarget")
                window_id = wid_resp["windowId"]
                await cdp.send("Browser.setWindowBounds", {
                    "windowId": window_id,
                    "bounds": {
                        "left":        _window_x,
                        "top":         _window_y,
                        "windowState": "maximized",
                    },
                })
                await cdp.detach()
                print("[Monitor] Janela maximizada via CDP.", flush=True)
            except Exception as e:
                print(f"[Monitor] CDP maximize falhou ({e}) — continuando.", flush=True)

            # Instala cursor humanizado (visual de depuração)
            try:
                from cursor_engine import instalar_cursor
                await instalar_cursor(page)
            except Exception:
                pass

            # Configura captura de clique humano (binding Python ↔ JS) e inicializa componentes
            await self._setup_captura_humana(page)

            # Configura listener para re-injetar botão após navegações de página
            await self._setup_persistent_pause_button(page)

            # Re-injeta o binding __hitl_captura__ em novos frames dinamicamente
            # (modais PrimeNG, menus de contexto, iframes carregados após o login)
            # Mesmo padrão do capture_dual_output: frameattached + framenavigated
            async def _reinjetar_binding_em_frame(frame):
                """Garante que o binding está disponível em frames novos/navegados."""
                for _ in range(3):  # até 3 tentativas com delay crescente
                    try:
                        if frame.is_detached():
                            return
                        await asyncio.sleep(0.15)
                        if frame.is_detached():
                            return
                        # O expose_binding já foi registrado no context — só precisa
                        # garantir que o frame não está em estado inválido
                        await frame.evaluate("() => true")
                        return
                    except Exception:
                        await asyncio.sleep(0.3)

            page.on("frameattached",  lambda f: asyncio.create_task(_reinjetar_binding_em_frame(f)))
            page.on("framenavigated", lambda f: asyncio.create_task(_reinjetar_binding_em_frame(f)))

            # Login
            ok = await self._fazer_login(page)
            if not ok:
                await browser.close()
                return

            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)

            # Execução: step-by-step (padrão) ou auto-play (--silent)
            if silent:
                # Modo silencioso: auto-play, só pausa em falha dura
                await self._execute_with_auto_play(page, passos)
            else:
                # Modo padrão: step-by-step, pausa após cada ação
                await self._execute_step_by_step(page, passos, total)

            await asyncio.sleep(1.0)

            # Relatório final com overlay no browser (antes de fechar)
            self._decisao_relatorio = await self._exibir_relatorio_final(page)

            await asyncio.sleep(0.5)
            await browser.close()

        # Reescreve o roteiro JSON com os seletores corrigidos pelo analista
        if self._stats["correcoes_salvas"] > 0:
            alteracoes = self._persistence_manager.rewrite_roteiro_json(caminho_json)
            if alteracoes > 0:
                print(f"✅ Roteiro atualizado com {alteracoes} seletor(es) corrigido(s).", flush=True)

        # Marca o roteiro como hitl_validado no servidor
        await self._marcar_hitl_validado(caminho_json)

        # Dispara gravação se o analista escolheu "🎬 Gravar agora"
        if self._decisao_relatorio == "gravar":
            print("🎬 Iniciando gravação...", flush=True)
            subprocess.Popen([sys.executable, "main.py", caminho_json, "--record"])

    async def _execute_step_by_step(self, page: Page, passos: list[dict], total: int) -> None:
        """
        Loop principal step-by-step (PADRÃO).
        Executa uma ação por vez, pausa após cada uma para o analista validar.
        Usa _executar_passo → _executar_acao_com_hitl que respeita _modo_auto_restante.
        """
        idx = 0
        while idx < len(passos):
            passo = passos[idx]
            self._current_step_index = idx
            self._passo_anterior = passos[idx - 1] if idx > 0 else None

            resultado = await self._executar_passo(page, passo, idx, total)

            if resultado == "refazer_passo" and idx > 0:
                # Volta ao passo anterior para corrigir a causa raiz
                idx_refazer = idx - 1
                passo_ant = passos[idx_refazer]
                id_ant = passo_ant.get("id_passo", idx_refazer + 1)
                print(f"\n   ↩ Refazendo passo {id_ant} (causa raiz)...", flush=True)
                self._passo_anterior = passos[idx_refazer - 1] if idx_refazer > 0 else None
                self._desvio_anterior = False
                await self._executar_passo(page, passo_ant, idx_refazer, total)
                await asyncio.sleep(0.8)
                # Após refazer o anterior, tenta o passo atual novamente
                self._passo_anterior = passo_ant
            else:
                idx += 1

    async def _execute_with_auto_play(self, page: Page, passos: list[dict]) -> None:
        """
        Loop auto-play (usado apenas em modo --silent).
        Executa sem pausas, só para em falhas reais.
        """
        idx = 0
        while idx < len(passos):
            passo = passos[idx]
            self._current_step_index = idx
            self._passo_anterior = passos[idx - 1] if idx > 0 else None

            # Atualiza informações do passo no navegador (se estiver aberto)
            if self._is_navigator_open and self._step_navigator:
                await self._step_navigator.update_step_info(idx, "pending")

            # Verifica se há solicitação de pausa manual
            if self._auto_play_controller and self._auto_play_controller.is_paused():
                await self._handle_manual_pause(page, passo, idx)
                continue  # Reprocessa o mesmo passo após a pausa

            # Executa o passo em modo auto-play
            resultado = await self._executar_passo_auto_play(page, passo, idx, len(passos))

            if resultado == "refazer_passo" and idx > 0:
                # Volta ao passo anterior para corrigir a causa raiz
                idx_refazer = idx - 1
                passo_ant   = passos[idx_refazer]
                id_ant      = passo_ant.get("id_passo", idx_refazer + 1)
                print(f"\n   ↩ Refazendo passo {id_ant} (causa raiz)...", flush=True)
                self._passo_anterior = passos[idx_refazer - 1] if idx_refazer > 0 else None
                self._desvio_anterior = False
                await self._executar_passo_auto_play(page, passo_ant, idx_refazer, len(passos))
                await asyncio.sleep(0.8)
                # Após refazer o anterior, tenta o passo atual novamente
                self._passo_anterior = passo_ant
            else:
                idx += 1

    async def _handle_manual_pause(self, page: Page, passo: dict, step_index: int) -> None:
        """
        Trata pausa manual solicitada pelo usuário via botão de pausa.
        """
        self._stats["pausas_manuais"] += 1
        self._is_navigator_open = True

        # Atualiza botão para modo "continuar"
        if self._floating_pause_button:
            await self._floating_pause_button.update_button_state(is_paused=True)

        # Exibe navegador de passos
        step_info = {
            "current": step_index + 1,
            "total": self._total_steps,
            "description": passo.get("pedagogia", {}).get("tooltip_dap", "Sem descrição"),
            "status": "pending"
        }

        if self._step_navigator:
            await self._step_navigator.show_navigator(step_info)

        # Aguarda decisão do usuário
        decisao = await self._aguardar_decisao(timeout=300)  # 5 minutos
        acao = decisao.get("acao", "continue_auto")

        # Processa ação do usuário
        await self._process_navigator_action(page, decisao, step_index)

        # Remove navegador e atualiza botão
        if self._step_navigator:
            await self._step_navigator.hide_navigator()

        if self._floating_pause_button:
            await self._floating_pause_button.update_button_state(is_paused=False)

        self._is_navigator_open = False

        # Retoma auto-play
        if self._auto_play_controller:
            self._auto_play_controller.resume_auto_play()

    async def _process_navigator_action(self, page: Page, decisao: dict, current_step: int) -> None:
        """
        Processa ações do navegador de passos.
        """
        acao = decisao.get("acao", "continue_auto")

        if acao == "continue_auto":
            # Retoma execução automática
            pass

        elif acao == "redo_step":
            # Refaz o passo atual
            print(f"   🔄 Refazendo passo {current_step + 1}...", flush=True)

        elif acao == "correct_selector":
            # Ativa radar para correção
            if self._enhanced_radar_system:
                await self._enhanced_radar_system.activate_radar()
                print("   ✏️ Radar ativo — clique no elemento correto...", flush=True)

        elif acao == "skip_step":
            # Pula o passo atual
            print(f"   ⏭ Pulando passo {current_step + 1}...", flush=True)

        elif acao == "prev_step":
            # Navega para passo anterior
            if current_step > 0:
                self._current_step_index = current_step - 1
                print(f"   ◄ Navegando para passo {current_step}...", flush=True)

        elif acao == "next_step":
            # Navega para próximo passo
            if current_step < self._total_steps - 1:
                self._current_step_index = current_step + 1
                print(f"   ► Navegando para passo {current_step + 2}...", flush=True)

        elif acao == "jump_to":
            # Pula para passo específico
            target_step = decisao.get("target_step", current_step + 1) - 1  # Convert to 0-based
            if 0 <= target_step < self._total_steps:
                self._current_step_index = target_step
                print(f"   ⏭ Pulando para passo {target_step + 1}...", flush=True)

    async def _executar_passo_auto_play(
        self, page: Page, passo: dict, idx: int, total: int
    ) -> str:
        """
        Executa um passo em modo auto-play (sem pausas preventivas ou checkpoints).
        Pausa automaticamente apenas em falhas reais.
        """
        id_p    = passo.get("id_passo", idx + 1)
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        ancora  = passo.get("pedagogia", {}).get("ancora",  "")
        acoes   = passo.get("acoes_tecnicas", [])
        is_fim  = passo.get("is_conclusao", False)

        # Aviso contextual quando o passo anterior teve desvio de estado
        aviso_desvio = ""
        if self._desvio_anterior:
            aviso_desvio = " ⚠️ [desvio anterior]"

        print(f"\n── Passo {id_p}/{total} {tooltip or ''}{aviso_desvio}", flush=True)

        if is_fim:
            print(f"   [CONCLUSÃO] {ancora[:80]}", flush=True)
            self._stats["passos_executados"] += 1
            self._desvio_anterior = False
            return "ok"

        # Executa todas as ações do passo em modo auto-play
        pediu_refazer = False
        for acao_tec in acoes:
            # Verifica pausa manual durante execução
            if self._auto_play_controller and self._auto_play_controller.is_paused():
                break

            resultado = await self._executar_acao_auto_play(page, acao_tec)
            label  = acao_tec.get("elemento_alvo", {}).get("label_curto", "?")
            status = "✅" if resultado == "ok" else ("❌" if resultado == "error" else "⏭")
            print(f"   {status} {acao_tec.get('acao','?')} → {label}", flush=True)

            if resultado == "error":
                # Falha real - pausa automática
                self._stats["pausas_automaticas"] += 1
                await self._handle_automatic_pause(page, acao_tec, passo)
                break

            # Delay mínimo para execução rápida
            await asyncio.sleep(0.6)

        self._stats["passos_executados"] += 1
        self._desvio_anterior = False
        return "ok"

    async def _executar_acao_auto_play(self, page: Page, acao_tec: dict) -> str:
        """
        Executa uma ação em modo auto-play (sem pausas preventivas).
        Retorna: 'ok', 'error', 'skip'
        """
        if acao_tec.get("acao") == "concluir_video":
            return "ok"

        # Execução direta via vision_engine (todas as 7 camadas)
        sucesso = await encontrar_e_clicar(page, acao_tec)

        if not sucesso:
            # Falha real - será tratada como pausa automática
            return "error"

        return "ok"

    async def _handle_automatic_pause(self, page: Page, acao_tec: dict, passo: dict) -> None:
        """
        Trata pausa automática em caso de falha real.
        """
        print("   🔴 Falha detectada - pausando automaticamente...", flush=True)

        # Força pausa no auto-play controller
        if self._auto_play_controller:
            self._auto_play_controller.request_pause()

        # Exibe navegador com opções de correção
        step_info = {
            "current": self._current_step_index + 1,
            "total": self._total_steps,
            "description": passo.get("pedagogia", {}).get("tooltip_dap", "Falha na execução"),
            "status": "error"
        }

        if self._step_navigator:
            await self._step_navigator.show_navigator(step_info)

        self._is_navigator_open = True


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator_hitl.py <caminho_do_roteiro.json> [--silent]")
        print("Ex:  python validator_hitl.py roteiros_salvos/GED_M01_A01.json")
        print("     --silent  Desativa pausas preventivas e checkpoints (só pausa em falha dura)")
        sys.exit(1)

    caminho = sys.argv[1]
    if not os.path.exists(caminho):
        print(f"❌ Arquivo não encontrado: {caminho}")
        sys.exit(1)

    modo_silencioso = "--silent" in sys.argv
    asyncio.run(HitlValidator().executar(caminho, silent=modo_silencioso))

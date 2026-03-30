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

  🔴 FALHA DURA  — todas as 7 camadas do vision_engine falharam.
                   O analista clica no elemento certo na tela.
                   O seletor é capturado, salvo no Brain e o fluxo retoma.

Cada correção humana é salva no Brain DB (brain.db).
Na próxima execução, o sistema já sabe onde está o elemento.

Uso:
    python validator_hitl.py roteiros_salvos/minha_aula.json
"""

import asyncio
import sys
import os
import json
import logging
import sqlite3
import base64
import re
import hashlib
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page

# ── Importa módulos existentes do Training OS ─────────────────────────────────
from vision_engine import (
    encontrar_e_clicar,
    _consultar_cache,
    _registrar_sucesso_cache,
    _e_seletor_fragil,
    DB_PATH,
    MAX_FALHAS_CACHE,
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
BRAIN_HITS_ALTA   = 3    # hits no Brain para considerar alta confiança
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
    """
    intencao  = acao_tec.get("intencao_semantica", "")
    alvo      = acao_tec.get("elemento_alvo", {})
    seletor   = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")
    conf_cap  = alvo.get("confianca_captura", "media")

    # Captura original foi classificada como baixa pelo Gemini Vision
    if conf_cap == "baixa":
        return NivelConfianca.BAIXA

    # Consulta Brain — memória de longo prazo
    if intencao:
        cache = _consultar_cache(intencao)
        if cache and cache.hits >= BRAIN_HITS_ALTA and cache.falhas_consecutivas == 0:
            return NivelConfianca.ALTA
        if cache and cache.seletor:
            return NivelConfianca.MEDIA

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

async def _validar_checkpoint(page: Page, tooltip_dap: str, ancora: str) -> tuple[bool, str]:
    """
    Tira screenshot e pede ao Gemini Vision para avaliar se a tela atual
    corresponde ao estado esperado descrito no roteiro.

    Retorna (estado_ok: bool, observacao: str).
    """
    if not CHECKPOINT_HABILITADO or not tooltip_dap:
        return True, "Checkpoint desabilitado."

    try:
        screenshot = await page.screenshot(type="jpeg", quality=60, full_page=False)

        prompt = (
            f"Você está validando a execução de um roteiro de treinamento no ERP Senior X.\n\n"
            f"Após executar um passo, o estado esperado da tela é:\n"
            f"- Localização: {tooltip_dap}\n"
            f"- Descrição: {ancora[:200] if ancora else 'Não informado'}\n\n"
            f"Analise o screenshot e responda APENAS com JSON:\n"
            f'{{ "estado_ok": true/false, "confianca": "alta|media|baixa", '
            f'"observacao": "uma frase curta descrevendo o que vê e se bate com o esperado" }}'
        )

        resposta = await asyncio.to_thread(
            _gemini.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                gtypes.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
                prompt,
            ],
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

# JS do getBestSelector — extraído do capture.py para capturar cliques humanos
_JS_GET_BEST_SELECTOR = """
    (el) => {
        let cur = el;
        for (let i = 0; i < 5; i++) {
            if (!cur) break;
            const tid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
            if (tid) return `[data-testid='${tid}']`;
            const aria = cur.getAttribute('aria-label');
            if (aria) return `[aria-label='${aria}']`;
            const name = cur.getAttribute('name');
            if (name && name.length < 40) return `[name='${name}']`;
            if (cur.id && !cur.id.match(/^[\\d\\-_]/) && !cur.id.match(/ng-|mat-|cdk-/))
                return `[id='${cur.id}']`;
            cur = cur.parentElement;
        }
        const ph = el.getAttribute('placeholder');
        if (ph) return `[placeholder='${ph}']`;
        const txt = el.innerText?.trim() || '';
        if (txt && txt.length > 1 && txt.length < 50) return `text="${txt}"`;
        const siblings = Array.from(el.parentElement?.children || []);
        return `${el.tagName.toLowerCase()}:nth-child(${siblings.indexOf(el) + 1})`;
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
# CLASSE PRINCIPAL — HitlValidator
# ══════════════════════════════════════════════════════════════════════════════

class HitlValidator:

    def __init__(self):
        self._evento_humano: asyncio.Event = asyncio.Event()
        self._decisao_humana: dict = {}       # resultado da decisão do analista
        self._captura_seletor: str = ""       # seletor capturado do clique humano
        self._stats = {
            "passos_ok":         0,
            "passos_checkpoint": 0,
            "passos_corrigidos": 0,
            "acoes_puladas":     0,
            "intervencoes":      0,
        }
        # Mapa intencao_semantica → seletor_corrigido
        # Usado ao final para reescrever o roteiro JSON
        self._correcoes_seletores: dict = {}

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
                self._captura_seletor = dados.get("seletor", "")
                self._decisao_humana  = {"acao": "capturou", "seletor": self._captura_seletor}
                self._evento_humano.set()
            except Exception as e:
                logger.warning(f"Captura humana falhou: {e}")

        # Expõe o binding no contexto do browser
        await page.context.expose_binding(
            "__hitl_captura__",
            _on_captura,
            handle=True,
        )

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

    async def _pausa_falha_dura(self, page: Page, acao_tec: dict) -> str:
        """
        Ativa o radar para o analista apontar o elemento correto.
        Retorna: 'capturou' (com seletor salvo) | 'pular'
        """
        self._stats["intervencoes"] += 1
        alvo   = acao_tec.get("elemento_alvo", {})
        label  = alvo.get("label_curto", "?")
        intenc = acao_tec.get("intencao_semantica", "")[:80]

        await _injetar_overlay(
            page,
            TipoPausa.FALHA_DURA,
            titulo="Elemento Não Encontrado",
            mensagem=(
                f'Esgotei todas as tentativas para encontrar <b>"{label}"</b>.<br><br>'
                f"Clique no elemento correto na tela para eu aprender onde ele está."
            ),
            instrucao="Clique no elemento certo — o Radar está ativo",
            nome_acao=intenc,
        )

        await self._adicionar_botoes(page, [
            {"label": "⏭ Pular esta ação", "acao": "pular", "estilo": "sec"},
        ])

        await self._ativar_radar(page)
        decisao = await self._aguardar_decisao()
        await _remover_overlay(page)
        return decisao.get("acao", "pular")

    # ─── Salva seletor capturado no Brain ─────────────────────────────────────

    def _salvar_correcao_no_brain(self, acao_tec: dict, seletor_capturado: str) -> None:
        """
        Persiste o seletor ensinado pelo analista no Brain DB.
        Na próxima execução, o sistema vai direto nele (alta confiança).
        """
        if not seletor_capturado:
            return
        intencao = acao_tec.get("intencao_semantica", "")
        alvo     = acao_tec.get("elemento_alvo", {})
        iframe   = alvo.get("iframe_hint")
        if intencao:
            _registrar_sucesso_cache(intencao, seletor=seletor_capturado, iframe=iframe)
            logger.info(f"Brain atualizado: '{intencao[:60]}' → '{seletor_capturado}'")
            self._stats["passos_corrigidos"] += 1
            # Guarda também no mapa in-memory para reescrita do JSON
            self._correcoes_seletores[intencao] = seletor_capturado

    # ─── Login ────────────────────────────────────────────────────────────────

    async def _fazer_login(self, page: Page) -> bool:
        SENIOR_URL = os.getenv("SENIOR_URL",
            "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        usuario = os.getenv("SENIOR_USER")
        senha   = os.getenv("SENIOR_PASS")

        if not usuario or not senha:
            print("ERRO: Credenciais ausentes no .env", flush=True)
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
            print("✅ Login OK.", flush=True)
            return True

        except Exception as e:
            logger.warning(f"Auto-login falhou: {e}")
            print("⚠️  Login automático falhou. Conclua manualmente (60s).", flush=True)
            try:
                await page.wait_for_load_state("networkidle", timeout=60_000)
                await asyncio.sleep(3.0)
                return True
            except Exception:
                print("❌ Timeout de login manual.", flush=True)
                return False

    # ─── Executar uma ação técnica com HITL ───────────────────────────────────

    async def _executar_acao_com_hitl(self, page: Page, acao_tec: dict) -> bool:
        """
        Tenta executar uma ação usando vision_engine.
        Se confiança baixa → pausa preventiva.
        Se falha total → pausa falha dura.
        Retorna True se a ação foi executada (com ou sem correção humana).
        """
        if acao_tec.get("acao") == "concluir_video":
            return True

        confianca = _nivel_confianca(acao_tec)
        alvo      = acao_tec.get("elemento_alvo", {})
        seletor   = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")

        # ── 🟡 Pausa preventiva (baixa confiança antes de tentar) ────────────
        if confianca == NivelConfianca.BAIXA:
            resposta = await self._pausa_preventiva(page, acao_tec, seletor)

            if resposta == "pular":
                self._stats["acoes_puladas"] += 1
                return False

            if resposta == "capturou" and self._captura_seletor:
                # Analista apontou o elemento certo — usa diretamente
                self._salvar_correcao_no_brain(acao_tec, self._captura_seletor)
                acao_corrigida = dict(acao_tec)
                if "elemento_alvo" not in acao_corrigida:
                    acao_corrigida["elemento_alvo"] = {}
                acao_corrigida["elemento_alvo"]["seletor_hint"] = self._captura_seletor
                sucesso = await encontrar_e_clicar(page, acao_corrigida)
                return sucesso

            # 'confirmar' → tenta normalmente
        # ── Execução via vision_engine (todas as 7 camadas) ──────────────────
        sucesso = await encontrar_e_clicar(page, acao_tec)

        # ── 🔴 Falha dura — todas as camadas esgotadas ───────────────────────
        if not sucesso:
            resposta = await self._pausa_falha_dura(page, acao_tec)

            if resposta == "pular":
                self._stats["acoes_puladas"] += 1
                return False

            if resposta == "capturou" and self._captura_seletor:
                self._salvar_correcao_no_brain(acao_tec, self._captura_seletor)
                acao_corrigida = dict(acao_tec)
                if "elemento_alvo" not in acao_corrigida:
                    acao_corrigida["elemento_alvo"] = {}
                acao_corrigida["elemento_alvo"]["seletor_hint"] = self._captura_seletor
                sucesso = await encontrar_e_clicar(page, acao_corrigida)

        return sucesso

    # ─── Executar um passo completo com checkpoint ────────────────────────────

    async def _executar_passo(self, page: Page, passo: dict, idx: int, total: int) -> None:
        id_p    = passo.get("id_passo", idx + 1)
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        ancora  = passo.get("pedagogia", {}).get("ancora",  "")
        acoes   = passo.get("acoes_tecnicas", [])
        is_fim  = passo.get("is_conclusao", False)

        print(f"\n── Passo {id_p}/{total} {tooltip or ''}", flush=True)

        if is_fim:
            print(f"   [CONCLUSÃO] {ancora[:80]}", flush=True)
            self._stats["passos_ok"] += 1
            return

        # Executa todas as ações do passo
        for acao_tec in acoes:
            ok = await self._executar_acao_com_hitl(page, acao_tec)
            label = acao_tec.get("elemento_alvo", {}).get("label_curto", "?")
            status = "✅" if ok else "⏭"
            print(f"   {status} {acao_tec.get('acao','?')} → {label}", flush=True)
            await asyncio.sleep(0.6)

        # ── 🟠 Checkpoint: valida estado após o passo ─────────────────────────
        if CHECKPOINT_HABILITADO and tooltip:
            estado_ok, observacao = await _validar_checkpoint(page, tooltip, ancora)

            if not estado_ok:
                print(f"   ⚠️  Checkpoint: {observacao}", flush=True)
                self._stats["passos_checkpoint"] += 1
                decisao = await self._pausa_checkpoint(page, passo, observacao)

                if decisao == "refazer":
                    print(f"   ↩ Refazendo passo {id_p}...", flush=True)
                    for acao_tec in acoes:
                        await self._executar_acao_com_hitl(page, acao_tec)
                        await asyncio.sleep(0.6)
            else:
                print(f"   ✓ Checkpoint OK: {observacao}", flush=True)

        self._stats["passos_ok"] += 1

    # ─── Ponto de entrada principal ───────────────────────────────────────────


    def _reescrever_roteiro_com_correcoes(self, caminho_json: str) -> None:
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

    async def executar(self, caminho_json: str) -> None:
        print(f"\n{'═'*55}", flush=True)
        print(f"  VALIDADOR HITL — {os.path.basename(caminho_json)}", flush=True)
        print(f"{'═'*55}\n", flush=True)

        with open(caminho_json, "r", encoding="utf-8") as f:
            roteiro = json.load(f)

        passos = roteiro.get("passos", [])
        total  = len(passos)
        nome   = roteiro.get("metadata", {}).get("nome_aula", "Aula")

        print(f"📋 {nome} — {total} passos", flush=True)
        print(f"🔍 Checkpoint Gemini: {'ATIVO' if CHECKPOINT_HABILITADO else 'DESABILITADO'}\n",
              flush=True)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--start-fullscreen",
                    "--disable-infobars",
                    "--disable-features=Translate",
                    "--lang=pt-BR",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            context = await browser.new_context(no_viewport=True, locale="pt-BR")
            page    = await context.new_page()

            # Instala cursor humanizado (visual de depuração)
            try:
                from cursor_engine import instalar_cursor
                await instalar_cursor(page)
            except Exception:
                pass

            # Configura captura de clique humano (binding Python ↔ JS)
            await self._setup_captura_humana(page)

            # Login
            ok = await self._fazer_login(page)
            if not ok:
                await browser.close()
                return

            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)

            # Executa os passos
            for idx, passo in enumerate(passos):
                await self._executar_passo(page, passo, idx, total)
                await asyncio.sleep(0.8)

            await asyncio.sleep(2.0)
            await browser.close()

        # Relatório final
        print(f"\n{'═'*55}", flush=True)
        print(f"  RELATÓRIO HITL", flush=True)
        print(f"{'═'*55}", flush=True)
        print(f"  Passos OK:             {self._stats['passos_ok']}", flush=True)
        print(f"  Checkpoints com desvio:{self._stats['passos_checkpoint']}", flush=True)
        print(f"  Correções salvas:      {self._stats['passos_corrigidos']}", flush=True)
        print(f"  Ações puladas:         {self._stats['acoes_puladas']}", flush=True)
        print(f"  Intervenções humanas:  {self._stats['intervencoes']}", flush=True)
        print(f"{'═'*55}\n", flush=True)

        if self._stats["passos_corrigidos"] > 0:
            print(f"✅ {self._stats['passos_corrigidos']} correção(ões) salvas no Brain.", flush=True)
            print("   Próxima execução vai acertar sem precisar de ajuda.", flush=True)

        # Reescreve o roteiro JSON com os seletores corrigidos pelo analista
        # Garante que as correções sobrevivem mesmo se o brain.db for deletado
        if self._stats["passos_corrigidos"] > 0 and hasattr(self, "_correcoes_seletores"):
            self._reescrever_roteiro_com_correcoes(caminho_json)

        # Marca o roteiro como hitl_validado no servidor
        try:
            import urllib.request, urllib.error, urllib.parse
            arquivo = os.path.basename(caminho_json)
            req = urllib.request.Request(
                f"http://localhost:8000/api/marcar-hitl-validado/{urllib.parse.quote(arquivo)}",
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
            print("✅ Roteiro marcado como HITL validado no Dashboard.", flush=True)
        except Exception as e:
            print(f"   (Servidor offline — marcar HITL manualmente: {e})", flush=True)


# ══════════════════════════════════════════════════════════════════════════════
# PONTO DE ENTRADA CLI
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator_hitl.py <caminho_do_roteiro.json>")
        print("Ex:  python validator_hitl.py roteiros_salvos/GED_M01_A01.json")
        sys.exit(1)

    caminho = sys.argv[1]
    if not os.path.exists(caminho):
        print(f"❌ Arquivo não encontrado: {caminho}")
        sys.exit(1)

    asyncio.run(HitlValidator().executar(caminho))
"""
screen_reader.py — Leitor de Tela Semântico
============================================
Responde a pergunta que estava faltando no CIL: "O que estou vendo agora?"

CAMADAS DE IDENTIFICAÇÃO (do mais barato ao mais caro):
  1. Fingerprint DOM   → 0 tokens,  ~30ms  — "já conheço esta tela"
  2. Heurística DOM    → 0 tokens,  ~20ms  — "infiro pelo contexto"
  3. Gemini visual     → ~500 tokens, ~2s  — "nunca vi esta tela" → aprende

Uso:
    estado = await ler_tela(page, objetivo="Abrir pasta Financeiro")
    # estado.onde_estou == "GED > Documentos > raiz"
    # estado.tela_id    == "ged_documentos"        ← identificado sem Gemini na 2ª vez
    # estado.objetivo_atingido == False
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class EstadoDaTela:
    """Representa o entendimento do agente sobre o estado atual da interface."""

    # ONDE o agente está
    onde_estou: str = ""                # "Painel principal do Senior X"
    tela_id: str = ""                   # identificador estável: "ged_documentos_raiz"

    # O QUE o agente vê
    elementos_visiveis: list = field(default_factory=list)  # [{nome, tipo, estado}]
    sidebar_estado: str = ""            # "colapsada" | "expandida" | "submenu_aberto"
    sidebar_item_ativo: str = ""        # qual item está selecionado
    iframe_presente: bool = False
    iframe_conteudo: str = ""           # o que o iframe está mostrando

    # O QUE é possível fazer
    acoes_disponiveis: list = field(default_factory=list)

    # PROGRESSO em relação ao objetivo
    objetivo_atingido: bool = False
    progresso: str = ""                 # "Estou no GED, preciso navegar para Documentos"
    proximo_passo_sugerido: str = ""    # sugestão de ação em linguagem natural

    # METADADOS
    confianca: float = 0.0
    screenshot_b64: Optional[str] = None


async def ler_tela(
    page: Page,
    objetivo: str = "",
    gemini_client=None,
) -> EstadoDaTela:
    """
    Identifica e descreve a tela atual.

    Fluxo de custo crescente:
      1. Fingerprint DOM  → 0 tokens — reconhece telas já vistas
      2. Heurística DOM   → 0 tokens — infere por elementos presentes
      3. Gemini visual    → ~500 tokens — para telas novas (e aprende)

    Args:
        page: Página Playwright atual
        objetivo: O que o agente está tentando alcançar
        gemini_client: Cliente Gemini (None = só DOM)
    """
    from screen_fingerprint import (
        identificar_tela, extrair_sinais, registrar_tela, listar_telas_conhecidas
    )

    estado = EstadoDaTela()

    # ── Camada 1: Fingerprint DOM (0 tokens) ─────────────────────
    resultado_fp = await identificar_tela(page)

    if not resultado_fp.desconhecida and not resultado_fp.incerto:
        # Tela conhecida e confirmada — carrega do banco
        estado = await _carregar_estado_do_banco(page, resultado_fp.tela_id, objetivo)
        logger.info(f"[ScreenReader] ✅ Cache hit: '{resultado_fp.tela_id}' em {resultado_fp.tempo_ms:.0f}ms")
        return estado

    # ── Camada 2: Heurística DOM (0 tokens) ──────────────────────
    estado = await _ler_dom(page, estado)

    if resultado_fp.incerto:
        # Score entre 60-79% — usa o candidato mas sinaliza incerteza
        estado.tela_id    = resultado_fp.tela_id
        estado.onde_estou = f"Provável: {resultado_fp.tela_id} (confiança {resultado_fp.confianca:.0%})"
        estado.confianca  = resultado_fp.confianca
        logger.info(f"[ScreenReader] ⚠ Match incerto: '{resultado_fp.tela_id}' — usando heurística DOM")
        # Se não há objetivo específico, retorna sem gastar Gemini
        if not objetivo or not gemini_client:
            return estado

    # ── Camada 3: Gemini visual (tela nova ou objetivo específico) ──
    if not gemini_client:
        logger.info("[ScreenReader] Gemini indisponível — retornando estado DOM parcial")
        return estado

    logger.info("[ScreenReader] 🆕 Tela nova (ou objetivo requer análise) — chamando Gemini...")
    estado = await _ler_visualmente(page, estado, objetivo, gemini_client)

    # Aprende: registra o fingerprint desta tela para não precisar do Gemini na próxima vez
    if estado.tela_id and not resultado_fp.incerto:
        sinais = await extrair_sinais(page)
        registrar_tela(
            tela_id=estado.tela_id,
            sinais=sinais,
            nome_descritivo=estado.onde_estou,
            descricao_gemini=estado.onde_estou,
            acoes_disponiveis=estado.acoes_disponiveis,
        )
        logger.info(f"[ScreenReader] 📚 Aprendido: '{estado.tela_id}' — não precisará do Gemini na próxima vez")

    return estado


async def _carregar_estado_do_banco(
    page: Page, tela_id: str, objetivo: str
) -> EstadoDaTela:
    """
    Reconstrói o EstadoDaTela a partir do que está salvo no banco,
    combinando com leitura DOM rápida para pegar o estado atual
    (item ativo, submenu aberto, etc.).
    """
    import sqlite3

    estado = EstadoDaTela(tela_id=tela_id)

    # Carrega metadados estáticos do banco
    try:
        with sqlite3.connect("brain_v2.db") as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM telas_conhecidas WHERE tela_id=?", (tela_id,)
            ).fetchone()
            if row:
                estado.onde_estou          = row["nome_descritivo"] or tela_id
                estado.acoes_disponiveis   = json.loads(row["acoes_disponiveis"] or "[]")
    except Exception:
        estado.onde_estou = tela_id

    # Atualiza estado dinâmico via DOM (0 tokens — só lê o que mudou)
    estado = await _ler_dom(page, estado)

    # Avalia progresso em relação ao objetivo (sem Gemini — heurística simples)
    if objetivo:
        estado.progresso = f"Na tela '{estado.onde_estou}', objetivo: {objetivo[:50]}"

    return estado


async def _ler_dom(page: Page, estado: EstadoDaTela) -> EstadoDaTela:
    """
    Extrai informações básicas do DOM sem chamar Gemini.
    Rápido, gratuito, mas limitado — não entende imagens ou layouts complexos.
    """
    try:
        info = await page.evaluate("""() => {
            const resultado = {
                url: location.href,
                titulo: document.title,
                iframes: [],
                sidebar_ativo: "",
                sidebar_expandida: false,
            };

            // Detecta iframes visíveis
            document.querySelectorAll('iframe').forEach(f => {
                const r = f.getBoundingClientRect();
                if (r.width > 100 && r.height > 100) {
                    resultado.iframes.push({
                        name: f.name || '',
                        src: (f.src || '').slice(0, 60),
                        visivel: r.width > 0
                    });
                }
            });

            // Detecta item de menu ativo na sidebar
            const sidebar = document.querySelector(
                'aside, nav, [class*="sidebar"], [class*="sidenav"], mat-sidenav'
            );
            if (sidebar) {
                const ativo = sidebar.querySelector(
                    '[aria-current="page"], [aria-selected="true"], .active, .selected, [class*="activated"]'
                );
                if (ativo) {
                    resultado.sidebar_ativo = (
                        ativo.getAttribute('aria-label') ||
                        ativo.innerText ||
                        ativo.textContent || ''
                    ).trim().slice(0, 60);
                }

                // Detecta se submenu está expandido
                resultado.sidebar_expandida = !!(
                    sidebar.querySelector('[aria-expanded="true"]') ||
                    sidebar.querySelector('.submenu:not([hidden])') ||
                    sidebar.offsetWidth > 150
                );
            }

            // Detecta conteúdo principal
            const main = document.querySelector(
                'main, [role="main"], [class*="content"], [class*="main-panel"]'
            );
            resultado.conteudo_principal = main
                ? (main.innerText || '').slice(0, 120).replace(/[ \t\n]+/g, ' ').trim()
                : '';

            return resultado;
        }""")

        estado.iframe_presente = len(info.get("iframes", [])) > 0
        if info.get("iframes"):
            nomes = [f.get("name") or f.get("src", "")[:20] for f in info["iframes"]]
            estado.iframe_conteudo = f"iframes: {', '.join(filter(None, nomes))}"

        estado.sidebar_item_ativo = info.get("sidebar_ativo", "")
        estado.sidebar_estado = "expandida" if info.get("sidebar_expandida") else "colapsada"

    except Exception as e:
        logger.warning(f"[ScreenReader] Erro DOM: {e}")

    return estado


async def _ler_visualmente(
    page: Page,
    estado: EstadoDaTela,
    objetivo: str,
    gemini_client,
) -> EstadoDaTela:
    """
    Usa Gemini para entender a tela visualmente.
    Mais rico que o DOM — vê labels, ícones, estado visual real.
    """
    from google.genai import types

    try:
        screenshot = await page.screenshot(type="jpeg", quality=80, full_page=False)

        contexto_dom = ""
        if estado.sidebar_item_ativo:
            contexto_dom += f"DOM detectou item ativo na sidebar: '{estado.sidebar_item_ativo}'. "
        if estado.iframe_presente:
            contexto_dom += f"DOM detectou: {estado.iframe_conteudo}. "

        prompt_objetivo = ""
        if objetivo:
            prompt_objetivo = f"""
OBJETIVO ATUAL: "{objetivo}"
Avalie: o objetivo já foi atingido? Em que ponto do caminho estamos?
"""

        prompt = f"""Você é o sistema de percepção de um agente de automação de ERP.
Analise esta tela e descreva o que você vê de forma estruturada.

{contexto_dom}
{prompt_objetivo}

Responda em JSON:
{{
    "onde_estou": "descrição em linguagem natural de onde o agente está (ex: 'Tela principal do Senior X com sidebar colapsada')",
    "tela_id": "identificador curto e estável (ex: 'ged_documentos_raiz', 'senior_flow_submenu', 'painel_principal')",
    "sidebar_estado": "colapsada|expandida|submenu_aberto",
    "sidebar_item_ativo": "qual item está visualmente selecionado/ativo",
    "iframe_visivel": false,
    "iframe_descricao": "o que o iframe está mostrando (se houver)",
    "elementos_principais": [
        {{"nome": "...", "tipo": "sidebar|botao|lista|formulario|modal|iframe", "estado": "ativo|inativo|expandido|colapsado"}}
    ],
    "acoes_disponiveis": ["lista do que é possível fazer agora"],
    "objetivo_atingido": false,
    "progresso_objetivo": "onde estamos em relação ao objetivo",
    "proximo_passo": "sugestão específica do que fazer agora para avançar",
    "confianca": 0.9
}}"""

        resp = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            ],
            config=__import__("google.genai.types", fromlist=["GenerateContentConfig"]).GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )

        out = json.loads(resp.text)

        estado.onde_estou              = out.get("onde_estou", "")
        estado.tela_id                 = out.get("tela_id", "")
        estado.sidebar_estado          = out.get("sidebar_estado", estado.sidebar_estado)
        estado.sidebar_item_ativo      = out.get("sidebar_item_ativo", estado.sidebar_item_ativo)
        estado.iframe_presente         = out.get("iframe_visivel", estado.iframe_presente)
        estado.iframe_conteudo         = out.get("iframe_descricao", estado.iframe_conteudo)
        estado.elementos_visiveis      = out.get("elementos_principais", [])
        estado.acoes_disponiveis       = out.get("acoes_disponiveis", [])
        estado.objetivo_atingido       = out.get("objetivo_atingido", False)
        estado.progresso               = out.get("progresso_objetivo", "")
        estado.proximo_passo_sugerido  = out.get("proximo_passo", "")
        estado.confianca               = float(out.get("confianca", 0.8))

        logger.info(f"[ScreenReader] Onde: {estado.onde_estou[:60]}")
        logger.info(f"[ScreenReader] Sidebar: {estado.sidebar_estado} | Ativo: {estado.sidebar_item_ativo}")
        if objetivo:
            logger.info(f"[ScreenReader] Objetivo atingido: {estado.objetivo_atingido} | {estado.progresso[:60]}")

    except Exception as e:
        logger.warning(f"[ScreenReader] Erro Gemini: {e}")

    return estado


async def objetivo_atingido(
    page: Page,
    objetivo: str,
    gemini_client=None,
) -> tuple[bool, str]:
    """
    Verifica se um objetivo específico foi atingido.
    Retorna (atingido: bool, motivo: str).

    Mais simples e focado que ler_tela() — usa quando só precisa
    de uma confirmação binária após uma ação.
    """
    if not gemini_client:
        return True, "Gemini indisponível — assumindo sucesso"

    from google.genai import types

    try:
        screenshot = await page.screenshot(type="jpeg", quality=75, full_page=False)

        prompt = f"""Analise esta tela e responda objetivamente:

OBJETIVO: "{objetivo}"

O objetivo foi atingido? Olhe evidências concretas na tela:
- Títulos, cabeçalhos, breadcrumbs
- Conteúdo da área central
- Estado do menu lateral
- Mensagens de confirmação

NÃO assuma — olhe a evidência visual.

JSON: {{"atingido": true/false, "evidencia": "o que na tela confirma ou nega", "confianca": 0.0-1.0}}"""

        resp = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            ],
            config=__import__("google.genai.types", fromlist=["GenerateContentConfig"]).GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )

        out = json.loads(resp.text)
        atingido = out.get("atingido", False)
        evidencia = out.get("evidencia", "")[:100]

        if atingido:
            logger.info(f"[ScreenReader] ✅ Objetivo atingido: {evidencia}")
        else:
            logger.info(f"[ScreenReader] ⏳ Objetivo pendente: {evidencia}")

        return atingido, evidencia

    except Exception as e:
        logger.warning(f"[ScreenReader] Erro verificação: {e}")
        return False, f"Erro: {e}"
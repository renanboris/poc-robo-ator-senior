"""
vision_engine_cil_v5.py — Motor CIL (Cognitive Interface Layer) v5
===================================================================
Foco desta versão:
- exploração MACRO da sidebar (sem números mágicos rígidos)
- uso de coordenadas do capture como âncora
- scroll do container real do menu, com telemetria before/after
- varredura visual restrita à sidebar antes de desistir
- guardrails fortes para cliques em menu
- Sniper real reativado
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import Page

# Pattern Engine — consulta o registry de padrões
try:
    from pattern_engine import pattern_engine
    _PATTERN_ENGINE_DISPONIVEL = True
    logger_temp = logging.getLogger(__name__)
    logger_temp.info("[CIL] Pattern Engine carregado com sucesso.")
except ImportError:
    _PATTERN_ENGINE_DISPONIVEL = False
    pattern_engine = None

load_dotenv()
logger = logging.getLogger(__name__)

_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Gemini Vision desativado.")

DB_PATH          = "brain_v2.db"   # novo arquivo — sem conflito com brain.db de testes
MAX_FALHAS_CACHE = 3


def _init_db():
    """
    Brain DB v2 — schema enriquecido.
    Campos novos: pattern, strategy_usada, validacao_ok, contexto_sistema.
    Arquivo separado brain_v2.db nao conflita com dados anteriores.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memoria_semantica (
                    hash_intencao       TEXT PRIMARY KEY,
                    intencao            TEXT,
                    seletor             TEXT,
                    coords              TEXT,
                    iframe              TEXT,
                    pattern             TEXT DEFAULT '',
                    strategy_usada      TEXT DEFAULT '',
                    contexto_sistema    TEXT DEFAULT '',
                    validacao_ok        INTEGER DEFAULT 1,
                    hits                INTEGER DEFAULT 0,
                    falhas_consecutivas INTEGER DEFAULT 0,
                    ultima_atualizacao  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    versao_schema       INTEGER DEFAULT 2
                )
                """
            )
    except Exception as e:
        logger.error(f"Nao foi possivel inicializar Brain DB v2: {e}")


_init_db()


def _chave_cache(intencao: str) -> str:
    return hashlib.md5(intencao.strip().lower().encode()).hexdigest()[:16]


@dataclass
class EntradaCache:
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    pattern: str = ""
    strategy_usada: str = ""
    validacao_ok: bool = True
    hits: int = 0
    falhas_consecutivas: int = 0


@dataclass(slots=True)
class TentativaLocalizacao:
    seletor: str
    iframe_hint: Optional[str] = None
    exact: bool = False
    via_pierce: bool = False
    role: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    title: Optional[str] = None
    descricao: str = ""


def _consultar_cache(intencao: str) -> Optional[EntradaCache]:
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM memoria_semantica WHERE hash_intencao = ?", (chave,)).fetchone()
            if row:
                if row["falhas_consecutivas"] >= MAX_FALHAS_CACHE:
                    conn.execute("DELETE FROM memoria_semantica WHERE hash_intencao = ?", (chave,))
                    return None
                # Descarta entradas onde validacao_ok=0 — o clique não foi confirmado
                if row["validacao_ok"] == 0:
                    logger.info(f"   [Brain] Entrada invalidada (validacao_ok=0) para: '{intencao[:50]}'")
                    return None
                logger.info(f"   [Brain] Memoria ativada para: '{intencao[:50]}'")
                return EntradaCache(
                    seletor=row["seletor"],
                    coords=json.loads(row["coords"]) if row["coords"] else None,
                    iframe_src=row["iframe"],
                    pattern=row["pattern"] or "",
                    strategy_usada=row["strategy_usada"] or "",
                    validacao_ok=bool(row["validacao_ok"]),
                    hits=row["hits"],
                    falhas_consecutivas=row["falhas_consecutivas"],
                )
    except Exception:
        pass
    return None


def _registrar_sucesso_cache(
    intencao: str,
    seletor: Optional[str] = None,
    coords: Optional[dict] = None,
    iframe: Optional[str] = None,
    pattern: str = "",
    strategy_usada: str = "",
    validacao_ok: bool = True,
):
    """Registra um acerto no Brain DB v2, incluindo pattern e strategy."""
    chave = _chave_cache(intencao)
    coords_str = json.dumps(coords) if coords else None
    if seletor and not seletor.startswith(("text=", "[", "#", "nav", "aside", "li", "tr", "xpath=")):
        seletor = None
    try:
        with sqlite3.connect(DB_PATH) as conn:
            existente = conn.execute(
                "SELECT hits FROM memoria_semantica WHERE hash_intencao = ?", (chave,)
            ).fetchone()
            if existente:
                query = (
                    "UPDATE memoria_semantica SET hits = hits + 1, falhas_consecutivas = 0, "
                    "ultima_atualizacao = CURRENT_TIMESTAMP, validacao_ok = ?"
                )
                params: list = [int(validacao_ok)]
                if seletor:
                    query += ", seletor = ?"; params.append(seletor)
                if coords_str:
                    query += ", coords = ?"; params.append(coords_str)
                if iframe:
                    query += ", iframe = ?"; params.append(iframe)
                if pattern:
                    query += ", pattern = ?"; params.append(pattern)
                if strategy_usada:
                    query += ", strategy_usada = ?"; params.append(strategy_usada)
                query += " WHERE hash_intencao = ?"; params.append(chave)
                conn.execute(query, params)
            else:
                conn.execute(
                    """
                    INSERT INTO memoria_semantica
                        (hash_intencao, intencao, seletor, coords, iframe,
                         pattern, strategy_usada, validacao_ok, hits, falhas_consecutivas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 0)
                    """,
                    (chave, intencao, seletor, coords_str, iframe,
                     pattern or "", strategy_usada or "", int(validacao_ok)),
                )
    except Exception:
        pass


def _registrar_falha_cache(intencao: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE memoria_semantica SET falhas_consecutivas = falhas_consecutivas + 1 WHERE hash_intencao = ?",
                (_chave_cache(intencao),),
            )
    except Exception:
        pass


def _registrar_healing_necessario(intencao: str, acao_tec: dict):
    try:
        arquivo = "relatorio_auto_cura.json"
        registro = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intencao_original": intencao,
            "label_procurado": acao_tec.get("elemento_alvo", {}).get("label_curto", "N/A"),
            "status": "CURADO VIA IA VISUAL (SELF-HEALING)",
        }
        logs = []
        if os.path.exists(arquivo):
            with open(arquivo, "r", encoding="utf-8") as f:
                logs = json.load(f)
        logs.append(registro)
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        logger.warning(f"💊 OPERAÇÃO SALVA: A IA Visual encontrou e clicou no elemento '{intencao}'.")
    except Exception:
        pass


_TAGS_FRAGEIS = {"h1", "h2", "h3", "h4", "span", "div", "em", "p", "li", "ul", "a", "button", "input", "section", "article", "td", "tr", "svg", "i", "path"}


def _e_seletor_fragil(seletor: str) -> bool:
    if not seletor:
        return True
    for p in ("text=", "has-text", "[aria-label=", "[data-testid=", "[id=", "[name=", "[placeholder=", "[role="):
        if p in seletor:
            return False
    tag = seletor.strip().split(":")[0].split("[")[0].split(".")[0].split(">")[0].strip()
    return tag in _TAGS_FRAGEIS


def _extrair_atributo(seletor: str, atributo: str) -> Optional[str]:
    match = re.search(rf"{atributo}=['\"]([^'\"]+)['\"]", seletor)
    return match.group(1) if match else None


def _gerar_candidatos(seletor_hint: str, label_curto: str, iframe_hint: Optional[str], acao: str, tipo_elemento: str, html_hint: str) -> list[TentativaLocalizacao]:
    candidatos = []
    eh_digitacao = acao in ("digitar_e_enter", "preencher_campo")
    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS if label_curto else False

    if label_curto and not is_tag_generica:
        if not eh_digitacao:
            candidatos.append(TentativaLocalizacao(seletor=f'text="{label_curto}"', iframe_hint=iframe_hint, exact=True, descricao=f"texto exato '{label_curto}'"))
        role = {"button": "button", "link": "link", "menu_item": "menuitem", "checkbox": "checkbox", "tab": "tab", "input": "textbox"}.get(tipo_elemento)
        if role:
            candidatos.append(TentativaLocalizacao(seletor="", role=role, label=label_curto, iframe_hint=iframe_hint, descricao=f"role={role} name='{label_curto}'"))
        candidatos.append(TentativaLocalizacao(seletor=f"[aria-label='{label_curto}']", iframe_hint=iframe_hint, descricao=f"aria-label='{label_curto}'"))
        candidatos.append(TentativaLocalizacao(seletor=f"[title*='{label_curto}' i]", iframe_hint=iframe_hint, descricao=f"title*='{label_curto}'"))

    tid = _extrair_atributo(seletor_hint, "data-testid")
    if tid:
        candidatos.append(TentativaLocalizacao(seletor=f"[data-testid='{tid}']", iframe_hint=iframe_hint, descricao=f"data-testid='{tid}'"))

    if html_hint:
        ph = re.search(r"placeholder=['\"]([^'\"]+)['\"]", html_hint)
        if ph:
            candidatos.append(TentativaLocalizacao(seletor=f"[placeholder='{ph.group(1)}']", iframe_hint=iframe_hint, descricao=f"placeholder='{ph.group(1)}'"))
            candidatos.append(TentativaLocalizacao(seletor="", placeholder=ph.group(1), iframe_hint=iframe_hint, descricao=f"get_by_placeholder '{ph.group(1)}'"))

    if label_curto and not is_tag_generica and not eh_digitacao and len(label_curto) > 3:
        candidatos.append(TentativaLocalizacao(seletor=f"text={label_curto}", iframe_hint=iframe_hint, exact=False, descricao=f"texto parcial '{label_curto}'"))

    return candidatos


async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal", "iframe-cross-origin"):
        return page
    for seletor_iframe in [
        f"iframe[name='{iframe_hint}']",
        f"iframe[src*='{iframe_hint}']",
        f"iframe[id='{iframe_hint}']",
        f"iframe[title*='{iframe_hint}']",
    ]:
        try:
            fl = page.frame_locator(seletor_iframe)
            await fl.locator("body").wait_for(state="attached", timeout=800)
            return fl
        except Exception:
            continue
    return page


async def _scroll_para_area_esperada(page: Page, coords_relativas: Optional[dict]) -> int:
    try:
        if coords_relativas and coords_relativas.get("y_pct"):
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            altura_est = coords_relativas["y_pct"] * vp["height"] * 2
            if altura_est > vp["height"] * 0.8:
                await page.evaluate(f"window.scrollTo(0, {max(0, int(altura_est - 300))})")
                await asyncio.sleep(0.3)
        scroll_y = await page.evaluate("() => window.scrollY") or 0
        return int(scroll_y)
    except Exception:
        return 0


async def _tirar_foto_limpa(page: Page) -> bytes:
    try:
        await page.evaluate("() => { document.querySelectorAll('#robo-cursor, #robo-legenda, .robo-tooltip, #senior-rec-widget').forEach(el => { el.setAttribute('data-old-op', el.style.opacity||''); el.style.opacity = '0'; }); }")
        await asyncio.sleep(0.1)
        foto = await page.screenshot(type="jpeg", quality=60, full_page=False)
        await page.evaluate("() => { document.querySelectorAll('#robo-cursor, #robo-legenda, .robo-tooltip, #senior-rec-widget').forEach(el => { el.style.opacity = el.getAttribute('data-old-op')||'1'; }); }")
        return foto
    except Exception:
        return await page.screenshot(type="jpeg", quality=60, full_page=False)


async def _screenshot_sidebar_clip(page: Page) -> Optional[bytes]:
    faixa = await _obter_faixa_util_sidebar(page)
    try:
        clip = {
            "x": max(0, int(faixa["left"])),
            "y": max(0, int(faixa["top"])),
            "width": max(60, int(faixa["width"])),
            "height": max(120, int(faixa["height"])),
        }
        return await page.screenshot(type="jpeg", quality=70, clip=clip)
    except Exception:
        return None


async def _highlight_elemento(locator, page) -> None:
    try:
        await locator.evaluate("el => { const o=el.style.outline; el.style.outline='2px solid #00e5e5'; setTimeout(()=>el.style.outline=o, 1200); }")
        await asyncio.sleep(0.2)
    except Exception:
        pass


async def _highlight_coords(page: Page, x: int, y: int) -> None:
    try:
        await page.evaluate(f"() => {{ const d=document.createElement('div'); d.style.cssText='position:fixed;left:{x-18}px;top:{y-18}px;width:36px;height:36px;border-radius:50%;border:3px solid #00e5e5;z-index:999999;animation:ping 0.6s ease-out;'; document.body.appendChild(d); setTimeout(()=>d.remove(),900); }}")
    except Exception:
        pass


async def _aguardar_estabilidade(page: Page, timeout_ms: int = 2000) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        await asyncio.sleep(0.4)


async def _executar_acao(locator, page, acao: str, valor: str) -> None:
    try:
        await locator.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    try:
        box = await locator.bounding_box(timeout=1000)
        if box:
            try:
                from cursor_engine import mover_cursor_humanizado
                await page.evaluate("() => { const c = document.getElementById('robo-cursor'); if(c) c.style.opacity = '1'; }")
                await mover_cursor_humanizado(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            except Exception:
                pass
            if "checkbox" not in acao:
                await locator.hover(timeout=2000)
    except Exception:
        pass

    await _highlight_elemento(locator, page)

    if acao == "duplo_clique":
        await locator.dblclick(timeout=3000)
    elif acao == "clique_direito":
        await locator.click(button="right", timeout=3000)
    elif acao == "tecla":
        # Foca o elemento e pressiona a tecla funcional (Enter, Esc, F2, Ctrl+S…)
        try:
            await locator.focus(timeout=1000)
        except Exception:
            pass
        if valor:
            await page.keyboard.press(valor)
        await asyncio.sleep(0.3)
    elif acao == "selecionar_opcao":
        # Seleciona opção em <select> nativo ou componente Angular
        try:
            await locator.select_option(value=valor, timeout=2000)
        except Exception:
            try:
                await locator.select_option(label=valor, timeout=1000)
            except Exception:
                await locator.click(timeout=2000)  # fallback: abre o dropdown
    elif acao == "digitar_e_enter":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
        await asyncio.sleep(1)
        await page.keyboard.press("Enter")
    elif acao == "preencher_campo":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
    else:
        await locator.click(timeout=3000)

    await _aguardar_estabilidade(page)


async def _tentar_candidato(page: Page, candidato: TentativaLocalizacao, acao: str, valor: str, timeout_ms: int = 2500) -> bool:
    try:
        contexto = await _resolver_contexto(page, candidato.iframe_hint)

        if not candidato.seletor:
            if hasattr(contexto, "get_by_role") and candidato.role and candidato.label:
                loc = contexto.get_by_role(candidato.role, name=candidato.label).first
            elif hasattr(contexto, "get_by_label") and candidato.label:
                loc = contexto.get_by_label(candidato.label).first
            elif hasattr(contexto, "get_by_placeholder") and candidato.placeholder:
                loc = contexto.get_by_placeholder(candidato.placeholder).first
            elif hasattr(contexto, "get_by_title") and candidato.title:
                loc = contexto.get_by_title(candidato.title).first
            else:
                return False
        elif candidato.seletor.startswith("text="):
            loc = contexto.get_by_text(candidato.seletor[5:].strip('"').strip("'"), exact=candidato.exact).first
        elif candidato.via_pierce:
            loc = page.locator(candidato.seletor).first
        else:
            loc = contexto.locator(candidato.seletor).first

        await loc.wait_for(state="visible", timeout=timeout_ms)
        await _executar_acao(loc, page, acao, valor)
        return True
    except Exception:
        return False


async def _buscar_em_todos_os_frames(page: Page, candidatos: list[TentativaLocalizacao], acao: str, valor: str) -> Optional[str]:
    try:
        frames = page.frames
    except Exception:
        return None

    frames_filhos = [f for f in frames if f != page.main_frame]
    for frame in frames_filhos:
        for cand_frame in candidatos[:10]:
            try:
                if not cand_frame.seletor:
                    if hasattr(frame, "get_by_role") and cand_frame.role and cand_frame.label:
                        loc = frame.get_by_role(cand_frame.role, name=cand_frame.label).first
                    elif hasattr(frame, "get_by_label") and cand_frame.label:
                        loc = frame.get_by_label(cand_frame.label).first
                    elif hasattr(frame, "get_by_placeholder") and cand_frame.placeholder:
                        loc = frame.get_by_placeholder(cand_frame.placeholder).first
                    elif hasattr(frame, "get_by_title") and cand_frame.title:
                        loc = frame.get_by_title(cand_frame.title).first
                    else:
                        continue
                elif cand_frame.seletor.startswith("text="):
                    loc = frame.get_by_text(cand_frame.seletor[5:].strip('"').strip("'"), exact=cand_frame.exact).first
                else:
                    loc = frame.locator(cand_frame.seletor).first

                await loc.wait_for(state="visible", timeout=1200)
                await _executar_acao(loc, page, acao, valor)
                logger.info(f"   [Todos os Frames] Encontrado em frame: {frame.url[:60]}")
                return frame.url
            except Exception:
                continue
    return None


async def _obter_faixa_util_sidebar(page: Page) -> dict:
    """
    Descobre a sidebar real e separa topo fixo / miolo rolável / rodapé fixo.
    Nada de pegar o primeiro [class*=sidebar]; usamos geometria + contexto.
    """
    try:
        info = await page.evaluate(
            """() => {
                const selectors = [
                  'aside', 'nav', '[class*="sidebar"]', '[class*="sidenav"]',
                  '[class*="drawer"]', '.mat-drawer', '.mat-sidenav', '[role="navigation"]'
                ];
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const nodes = [];
                for (const s of selectors) {
                    document.querySelectorAll(s).forEach(el => nodes.push(el));
                }

                let root = null;
                let bestScore = -1e9;
                for (const el of nodes) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    if (r.width < 36 || r.height < vh * 0.40) continue;
                    if (r.left > vw * 0.35) continue;
                    const widthPenalty = Math.abs(Math.min(r.width, 260) - 90) * 0.6;
                    const score = ((vw - r.left) * 3.0) + (r.height * 0.4) + (Math.max(0, 80 - r.left) * 4.0) - widthPenalty;
                    if (score > bestScore) {
                        bestScore = score;
                        root = el;
                    }
                }

                if (!root) {
                    return {
                        left: 0, top: 0, width: 100, height: vh,
                        x_hover: 40, y_top: Math.round(vh * 0.22), y_bottom: Math.round(vh * 0.85),
                        right: 100
                    };
                }

                const r = root.getBoundingClientRect();
                let yTop = r.top + Math.max(140, r.height * 0.18);
                let yBottom = r.bottom - Math.max(100, r.height * 0.12);

                const all = [...root.querySelectorAll('*')];
                for (const el of all) {
                    const txt = ((el.innerText || el.textContent || el.getAttribute('title') || el.getAttribute('aria-label') || '') + '').trim();
                    const b = el.getBoundingClientRect();
                    if (b.height < 12 || b.width < 12) continue;
                    if (/dados do usu[aá]rio|usu[aá]rio|usuario|perfil|avatar/i.test(txt) && b.bottom < r.top + r.height * 0.45) {
                        yTop = Math.max(yTop, b.bottom + 12);
                    }
                    if (/sara/i.test(txt) && b.top > r.top + r.height * 0.55) {
                        yBottom = Math.min(yBottom, b.top - 12);
                    }
                }

                yTop = Math.max(r.top + 60, yTop);
                yBottom = Math.max(yTop + 120, Math.min(r.bottom - 40, yBottom));

                return {
                    left: Math.round(r.left),
                    top: Math.round(r.top),
                    width: Math.round(r.width),
                    height: Math.round(r.height),
                    right: Math.round(r.right),
                    x_hover: Math.round(r.left + Math.min(40, Math.max(18, r.width * 0.35))),
                    y_top: Math.round(yTop),
                    y_bottom: Math.round(yBottom)
                };
            }"""
        )
        return info or {"left": 0, "top": 0, "width": 100, "height": 900, "right":100, "x_hover": 40, "y_top": 240, "y_bottom": 820}
    except Exception:
        return {"left": 0, "top": 0, "width": 100, "height": 900, "right":100, "x_hover": 40, "y_top": 240, "y_bottom": 820}


async def _resetar_scroll_sidebar(page: Page) -> bool:
    try:
        result = await page.evaluate(
            """() => {
                const selectors = ['aside', 'nav', '[class*="sidebar"]', '[class*="sidenav"]', '[class*="drawer"]', '.mat-drawer', '.mat-sidenav', '[role="navigation"]'];
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                let root = null;
                let bestScore = -1e9;
                const roots = [];
                for (const s of selectors) document.querySelectorAll(s).forEach(el => roots.push(el));
                for (const el of roots) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    if (r.width < 36 || r.height < vh * 0.40) continue;
                    if (r.left > vw * 0.35) continue;
                    const score = ((vw - r.left) * 3.0) + (r.height * 0.4) + (Math.max(0, 80 - r.left) * 4.0) - (Math.abs(Math.min(r.width, 260) - 90) * 0.6);
                    if (score > bestScore) { bestScore = score; root = el; }
                }
                if (!root) return {ok:false, changed:false};
                const candidates = [root, ...root.querySelectorAll('*')];
                let best = null;
                let bestInnerScore = -1e9;
                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const scrollable = el.scrollHeight > el.clientHeight + 20;
                    const visible = r.width > 20 && r.height > 80 && r.left < vw * 0.35 && style.display !== 'none' && style.visibility !== 'hidden';
                    if (!scrollable || !visible) continue;
                    const score = (el.scrollHeight - el.clientHeight) + Math.min(r.height, 600) - (r.top < root.getBoundingClientRect().top + 80 ? 200 : 0);
                    if (score > bestInnerScore) { bestInnerScore = score; best = el; }
                }
                if (!best) return {ok:false, changed:false};
                const before = best.scrollTop;
                best.scrollTop = 0;
                return {ok:true, changed: best.scrollTop !== before, before, after: best.scrollTop};
            }"""
        )
        if result and result.get('ok'):
            logger.info(f"   [Strategy: Menu] Reset scroll sidebar -> before:{result.get('before')} after:{result.get('after')} changed:{result.get('changed')}")
        return bool(result and result.get('ok'))
    except Exception:
        return False


async def _expandir_sidebar_por_hover(page: Page, y_hint: Optional[int] = None) -> dict:
    faixa = await _obter_faixa_util_sidebar(page)
    x = int(faixa["x_hover"])
    if y_hint is None:
        y = int((faixa["y_top"] + faixa["y_bottom"]) / 2)
    else:
        y = max(faixa["y_top"] + 8, min(int(y_hint), faixa["y_bottom"] - 8))
    logger.info(f"   [Strategy: Menu] Movendo mouse para X:{x}, Y:{y} para forçar hover e expandir sidebar...")
    try:
        await page.mouse.move(x, y)
        await asyncio.sleep(0.7)
    except Exception:
        pass
    return faixa


async def _scroll_sidebar_container(page: Page, pixels: int = 260) -> bool:
    try:
        result = await page.evaluate(
            """(pixels) => {
                const selectors = ['aside', 'nav', '[class*="sidebar"]', '[class*="sidenav"]', '[class*="drawer"]', '.mat-drawer', '.mat-sidenav', '[role="navigation"]'];
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                let root = null;
                let bestScore = -1e9;
                const roots = [];
                for (const s of selectors) document.querySelectorAll(s).forEach(el => roots.push(el));
                for (const el of roots) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    if (r.width < 36 || r.height < vh * 0.40) continue;
                    if (r.left > vw * 0.35) continue;
                    const score = ((vw - r.left) * 3.0) + (r.height * 0.4) + (Math.max(0, 80 - r.left) * 4.0) - (Math.abs(Math.min(r.width, 260) - 90) * 0.6);
                    if (score > bestScore) { bestScore = score; root = el; }
                }
                if (!root) return {ok:false, changed:false};
                const rootRect = root.getBoundingClientRect();
                const candidates = [root, ...root.querySelectorAll('*')];
                let best = null;
                let bestInnerScore = -1e9;
                for (const el of candidates) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    const scrollable = el.scrollHeight > el.clientHeight + 20;
                    const visible = r.width > 20 && r.height > 80 && r.left < vw * 0.35 && style.display !== 'none' && style.visibility !== 'hidden';
                    if (!scrollable || !visible) continue;
                    const topPenalty = r.top < rootRect.top + 90 ? 250 : 0;
                    const bottomPenalty = r.bottom > rootRect.bottom - 70 ? 50 : 0;
                    const score = (el.scrollHeight - el.clientHeight) + Math.min(r.height, 600) - topPenalty - bottomPenalty;
                    if (score > bestInnerScore) { bestInnerScore = score; best = el; }
                }
                if (!best) return {ok:false, changed:false};
                const before = best.scrollTop;
                best.scrollTop = Math.min(best.scrollTop + pixels, best.scrollHeight);
                return {ok:true, changed: best.scrollTop !== before, before, after: best.scrollTop};
            }""",
            pixels,
        )
        if result and result.get("ok"):
            logger.info(f"   [Strategy: Menu] Scroll sidebar -> before:{result.get('before')} after:{result.get('after')} changed:{result.get('changed')}")
        return bool(result and result.get("changed"))
    except Exception:
        return False


async def _menu_item_ficou_ativo(page: Page, label: str) -> bool:
    try:
        info = await page.evaluate(
            """(label) => {
                const scope = document.querySelector('aside, nav, [class*="sidebar"], [class*="sidenav"], [class*="drawer"], .mat-drawer, .mat-sidenav') || document;
                const all = [...scope.querySelectorAll('*')];
                const low = label.toLowerCase();
                for (const el of all) {
                    const txt = ((el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '') + '').trim().toLowerCase();
                    if (!txt || !txt.includes(low)) continue;
                    let node = el;
                    for (let i=0; i<5 && node; i++, node=node.parentElement) {
                        const html = (node.outerHTML || '').toLowerCase();
                        const cls = (node.className || '').toString().toLowerCase();
                        if (cls.includes('active') || cls.includes('selected') || html.includes('aria-current="page"') || html.includes("aria-selected=\"true\"") || html.includes("aria-expanded=\"true\"")) {
                            return true;
                        }
                    }
                }
                return false;
            }""",
            label,
        )
        return bool(info)
    except Exception:
        return False


async def _resolver_locator_clicavel_de_menu(page: Page, label: str):
    sidebar = await _encontrar_sidebar_container(page)
    contexto = sidebar if sidebar else page
    tentativas = [
        contexto.get_by_text(label, exact=True).first,
        contexto.get_by_text(label, exact=False).first,
        contexto.locator(f"[aria-label*='{label}' i]").first,
        contexto.locator(f"[title*='{label}' i]").first,
        contexto.locator(f"[data-tooltip*='{label}' i]").first,
    ]
    for base in tentativas:
        try:
            if await base.count() == 0 or not await base.is_visible():
                continue
            candidatos_ancestrais = [
                "xpath=ancestor::*[@role='menuitem'][1]",
                "xpath=ancestor::button[1]",
                "xpath=ancestor::a[1]",
                "xpath=ancestor::li[1]",
                "xpath=ancestor::*[contains(@class,'menu')][1]",
                "xpath=ancestor::*[contains(@class,'nav')][1]",
                "xpath=ancestor::*[contains(@class,'item')][1]",
            ]
            for anc in candidatos_ancestrais:
                try:
                    loc = base.locator(anc).first
                    if await loc.count() > 0 and await loc.is_visible():
                        return loc
                except Exception:
                    pass
            return base
        except Exception:
            pass
    return None


async def _encontrar_sidebar_container(page: Page):
    """
    Descobre a sidebar REAL por geometria, não pelo primeiro selector genérico.
    Priorizamos o container alto, estreito/moderado e mais à esquerda.
    """
    try:
        info = await page.evaluate(
            """() => {
                const selectors = [
                  'aside', 'nav', '[class*="sidebar"]', '[class*="sidenav"]',
                  '[class*="drawer"]', '.mat-drawer', '.mat-sidenav',
                  '[role="navigation"]'
                ];
                const vw = window.innerWidth;
                const vh = window.innerHeight;
                const nodes = [];
                for (const s of selectors) {
                    document.querySelectorAll(s).forEach(el => nodes.push(el));
                }
                let best = null;
                let bestScore = -1e9;
                for (const el of nodes) {
                    const r = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;
                    if (r.width < 36 || r.height < vh * 0.40) continue;
                    if (r.left > vw * 0.35) continue; // sidebar real precisa estar no terço esquerdo
                    const widthPenalty = Math.abs(Math.min(r.width, 260) - 90) * 0.6;
                    const leftBonus = (vw - r.left) * 3.0;
                    const heightBonus = r.height * 0.4;
                    const edgeBonus = Math.max(0, 80 - r.left) * 4.0;
                    const score = leftBonus + heightBonus + edgeBonus - widthPenalty;
                    if (score > bestScore) {
                        bestScore = score;
                        best = { left:r.left, top:r.top, width:r.width, height:r.height, right:r.right, selector:s };
                    }
                }
                return best;
            }"""
        )
        if not info:
            return None
        # monta um locator robusto pela posição geométrica descoberta
        candidates = [
            "aside", "nav", "[class*='sidebar']", "[class*='sidenav']",
            "[class*='drawer']", ".mat-drawer", ".mat-sidenav", "[role='navigation']",
        ]
        best_loc = None
        best_dx = 10**9
        for sel in candidates:
            try:
                locs = page.locator(sel)
                count = await locs.count()
                for i in range(min(count, 12)):
                    loc = locs.nth(i)
                    if not await loc.is_visible():
                        continue
                    box = await loc.bounding_box()
                    if not box:
                        continue
                    dx = abs(box['x'] - info['left']) + abs(box['width'] - info['width'])
                    if dx < best_dx:
                        best_dx = dx
                        best_loc = loc
            except Exception:
                pass
        return best_loc
    except Exception:
        return None


async def _clicar_elemento_sem_hover(locator, page: Page, acao: str, valor: str) -> bool:
    try:
        await locator.scroll_into_view_if_needed(timeout=1500)
    except Exception:
        pass
    try:
        box = await locator.bounding_box()
        if not box:
            return False
        x = int(box["x"] + box["width"] / 2)
        y = int(box["y"] + box["height"] / 2)
        logger.info(f"   [Mouse] Disparando clique físico no alvo de menu -> X:{x}, Y:{y}")
        await _highlight_coords(page, x, y)
        if acao == "clique_direito":
            await page.mouse.click(x, y, button="right")
        elif acao == "duplo_clique":
            await page.mouse.dblclick(x, y)
        else:
            await page.mouse.click(x, y)
        await _aguardar_estabilidade(page, timeout_ms=1800)
        return True
    except Exception:
        return False


async def _gemini_localizar_elemento(screenshot_atual: bytes, screenshot_ref_b64: Optional[str], descricao_visual: str, intencao: str, contexto_tela: str, viewport: dict, scroll_y: int) -> Optional[dict]:
    if not gemini_client:
        return None
    logger.info("   [Vision] O DOM falhou. Acordando o Agente Operacional Visual...")
    contents: list = []
    if screenshot_ref_b64:
        try:
            ref_bytes = base64.b64decode(screenshot_ref_b64)
            contents.append("IMAGEM 1 - REFERENCIA (estado da tela na gravacao original):")
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))
        except Exception:
            pass
    contents.append("IMAGEM 2 - TELA ATUAL (onde o elemento deve ser clicado agora):")
    contents.append(types.Part.from_bytes(data=screenshot_atual, mime_type="image/jpeg"))
    contents.append(
        f"Você é o 'Senior AI Operator', um agente autônomo de navegação visual.\n"
        f"Localize as coordenadas exatas (centro do alvo) na IMAGEM 2.\n"
        f"- Intenção: {intencao}\n"
        f"- Descrição Visual (Alvo): {descricao_visual}\n"
        f"- Contexto: {contexto_tela}\n"
        f"🚨 Se a intenção for menu lateral (ex: Senior Flow, GED), priorize a comparação com a IMAGEM 1 e NUNCA chute fora da sidebar. Se tiver dúvidas, responda {{\"metodo\":\"nao_encontrado\"}}.\n"
        f"Responda ESTRITAMENTE em JSON: {{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":123,\"y\":456}},\"confianca\":\"alta|media|baixa\"}}"
    )
    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.05),
        )
        resultado = json.loads(resposta.text)
        if resultado.get("metodo") == "nao_encontrado":
            return None
        return resultado
    except Exception as e:
        logger.warning(f"   [Vision] Falha na analise visual: {e}")
        return None


async def _gemini_localizar_em_sidebar(page: Page, label: str, screenshot_ref_b64: Optional[str]) -> Optional[dict]:
    if not gemini_client:
        return None
    clip = await _screenshot_sidebar_clip(page)
    if not clip:
        return None
    contents: list = []
    if screenshot_ref_b64:
        try:
            ref_bytes = base64.b64decode(screenshot_ref_b64)
            contents.append("IMAGEM 1 - REFERENCIA ORIGINAL DO CLIQUE/ALVO:")
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))
        except Exception:
            pass
    contents.append("IMAGEM 2 - CROP DA SIDEBAR ATUAL:")
    contents.append(types.Part.from_bytes(data=clip, mime_type="image/jpeg"))
    contents.append(
        f"Você é um agente de exploração da SIDEBAR.\n"
        f"Alvo desejado: {label}.\n"
        f"A sidebar tem áreas fixas no topo/rodapé e uma faixa rolável no meio.\n"
        f"Procure o item/ícone correspondente a {label} apenas no menu da sidebar.\n"
        f"Ignore avatar/usuário no topo, Home fixo e SARA no rodapé.\n"
        f"Se encontrar, devolva coordenadas relativas AO CROP no JSON: {{\"metodo\":\"coordenadas\",\"coordenadas\":{{\"x\":50,\"y\":200}},\"confianca\":\"alta|media|baixa\"}}.\n"
        f"Se não encontrar com segurança, devolva {{\"metodo\":\"nao_encontrado\"}}."
    )
    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.05),
        )
        out = json.loads(resposta.text)
        if out.get("metodo") == "nao_encontrado":
            return None
        faixa = await _obter_faixa_util_sidebar(page)
        cx = int(out["coordenadas"]["x"] + faixa["left"])
        cy = int(out["coordenadas"]["y"] + faixa["top"])
        return {"coordenadas": {"x": cx, "y": cy}, "confianca": out.get("confianca", "media")}
    except Exception:
        return None


def _parse_coords(coords):
    try:
        if isinstance(coords, dict):
            return int(coords.get("x", 0)), int(coords.get("y", 0))
        elif isinstance(coords, list):
            if len(coords) > 0 and isinstance(coords[0], dict):
                return int(coords[0].get("x", 0)), int(coords[0].get("y", 0))
            elif len(coords) >= 2:
                return int(coords[0]), int(coords[1])
        elif isinstance(coords, str):
            nums = re.findall(r"\d+", coords)
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])
    except Exception:
        pass
    return 0, 0


async def _clicar_por_coordenadas(page: Page, coords, acao: str, valor: str) -> bool:
    try:
        x, y = _parse_coords(coords)
        if x <= 0 or y <= 0:
            raise ValueError(f"Coordenadas invalidas: x={x}, y={y}")
        logger.info(f"   [Mouse] Disparando clique na coordenada da tela -> X:{x}, Y:{y}")
        await _highlight_coords(page, x, y)
        await asyncio.sleep(0.25)
        if acao == "duplo_clique":
            await page.mouse.dblclick(x, y)
        elif acao == "clique_direito":
            await page.mouse.click(x, y, button="right")
        elif acao == "tecla":
            # Clica para focar, depois pressiona a tecla
            await page.mouse.click(x, y)
            await asyncio.sleep(0.2)
            if valor:
                await page.keyboard.press(valor)
        else:
            await page.mouse.click(x, y)
        if acao in ("digitar_e_enter", "preencher_campo") and valor:
            await asyncio.sleep(0.2)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=40)
            if acao == "digitar_e_enter":
                await asyncio.sleep(0.8)
                await page.keyboard.press("Enter")
        await _aguardar_estabilidade(page)
        return True
    except Exception as exc:
        logger.warning(f"Clique por coordenadas falhou: {exc}")
        return False


async def _gemini_vision_first(
    page: Page,
    intencao: str,
    label_curto: str,
    descricao_visual: str,
    contexto_tela: str,
    screenshot: bytes,
    pattern: str = "",
    coords_relativas: Optional[dict] = None,
) -> Optional[dict]:
    """
    Coração da arquitetura Vision-First.
    Envia um screenshot de alta qualidade ao Gemini com um prompt claro e direto.
    Retorna as coordenadas do elemento ou None.

    Diferença crítica vs abordagem anterior:
    - Screenshot JPEG quality=85 (vs 60 antes) — itens de menu pequenos precisam de nitidez
    - Prompt específico por pattern — menu tem regras diferentes de formulário
    - Sem crop pré-definido — o Gemini enxerga a tela toda e decide sozinho
    - GPS das coords originais do capture passado como dica, não como verdade absoluta
    """
    if not gemini_client:
        return None

    vp = page.viewport_size or {"width": 1920, "height": 1080}
    dica_gps = ""
    if coords_relativas and coords_relativas.get("x_pct"):
        x_est = int(coords_relativas["x_pct"] * vp["width"])
        y_est = int(coords_relativas["y_pct"] * vp["height"])
        dica_gps = f"\n📍 GPS: durante a gravação, o clique ocorreu em aprox X:{x_est}, Y:{y_est}. Use como dica de região, não como verdade absoluta."

    if pattern == "menu_navigation":
        instrucao = (
            f"Você é um agente de automação visual. Preciso que você encontre e me dê as coordenadas "
            f"do item de menu chamado '{label_curto}' na barra lateral esquerda desta tela.\n"
            f"Contexto: {contexto_tela}\n"
            f"{dica_gps}\n\n"
            f"REGRAS:\n"
            f"- O alvo está NA BARRA LATERAL ESQUERDA (sidebar/menu lateral)\n"
            f"- Procure o texto '{label_curto}' ou um ícone claramente associado a ele\n"
            f"- Retorne as coordenadas do CENTRO do elemento clicável\n"
            f"- Se não encontrar com certeza, retorne metodo: nao_encontrado\n"
            f"- NÃO chute. É melhor dizer não encontrado do que dar coordenadas erradas\n\n"
            f"Responda SOMENTE em JSON: "
            f'{{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":123,\"y\":456}},\"confianca\":\"alta|media|baixa\"}}'
        )
    else:
        instrucao = (
            f"Você é um agente de automação visual. Preciso das coordenadas do elemento: '{label_curto}'.\n"
            f"Descrição: {descricao_visual}\n"
            f"Contexto da tela: {contexto_tela}\n"
            f"{dica_gps}\n\n"
            f"Retorne o CENTRO do elemento clicável.\n"
            f"Se não encontrar com clareza, retorne metodo: nao_encontrado.\n\n"
            f"Responda SOMENTE em JSON: "
            f'{{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":123,\"y\":456}},\"confianca\":\"alta|media|baixa\"}}'
        )

    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                instrucao,
                types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )
        resultado = json.loads(resposta.text)
        if resultado.get("metodo") == "nao_encontrado":
            return None
        logger.info(f"   [Vision] Gemini: confiança={resultado.get('confianca','?')} | {resultado.get('raciocinio','')[:80]}")
        return resultado
    except Exception as e:
        logger.warning(f"   [Vision] Falha na chamada Gemini: {e}")
        return None


async def _tirar_foto_hd(page: Page) -> bytes:
    """Screenshot de alta qualidade para o Vision-First. JPEG 85 garante
    legibilidade de labels pequenos em menus — qualidade 60 distorce texto."""
    try:
        await page.evaluate(
            "() => { document.querySelectorAll('#robo-cursor,#robo-legenda,.robo-tooltip,#senior-rec-widget')"
            ".forEach(el => { el.setAttribute('data-op',el.style.opacity||''); el.style.opacity='0'; }); }"
        )
        await asyncio.sleep(0.1)
        foto = await page.screenshot(type="jpeg", quality=85, full_page=False)
        await page.evaluate(
            "() => { document.querySelectorAll('#robo-cursor,#robo-legenda,.robo-tooltip,#senior-rec-widget')"
            ".forEach(el => { el.style.opacity=el.getAttribute('data-op')||'1'; }); }"
        )
        return foto
    except Exception:
        return await page.screenshot(type="jpeg", quality=85, full_page=False)


async def _encontrar_e_clicar_core(page: Page, acao_tec: dict) -> bool:
    """
    ARQUITETURA VISION-FIRST (v7)
    ==============================
    Inspirada em como Manus/OpenClaw funcionam: Vision é o cérebro principal,
    não o fallback de último recurso.

    Fluxo de decisão:
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. Brain DB  → seletor salvo de execução anterior (rápido) │
    │ 2. seletor_css do roteiro → tentativa DOM direta (rápido)  │
    │ 3. VISION FIRST → Screenshot HD + Gemini → coordenadas     │  ← estratégia principal
    │    (para menu_navigation: hover antes para expandir sidebar) │
    │    (scroll sidebar e retry até 3× se item não visível)      │
    │ 4. Sniper DOM → candidatos por texto/aria (fallback)        │
    │ 5. Coords do capture → clique GPS original (último recurso) │
    └─────────────────────────────────────────────────────────────┘

    Removido da v6:
    - Loop de 8 iterações com múltiplas chamadas Gemini por scroll
    - _resolver_locator_clicavel_de_menu (xpath de ancestral, frágil)
    - _menu_item_ficou_ativo (checa classes CSS que Angular não usa)
    - _obter_faixa_util_sidebar (scoring JS com números mágicos)
    - _encontrar_sidebar_container (duplicata do anterior)
    - _gemini_localizar_em_sidebar (crop pré-definido, limitante)
    """
    alvo             = acao_tec.get("elemento_alvo", {})
    acao             = acao_tec.get("acao", "clique")
    intencao         = acao_tec.get("intencao_semantica", "Acao na interface")
    valor            = acao_tec.get("valor_input", "") or ""
    label_curto      = alvo.get("label_curto", "")
    pattern          = acao_tec.get("pattern_detectado", "")
    coords_relativas = alvo.get("coordenadas_relativas")
    descricao_visual = alvo.get("descricao_visual", label_curto)
    contexto_tela    = alvo.get("contexto_tela", "")
    iframe_hint      = alvo.get("iframe_hint", "")
    seletor_css      = acao_tec.get("seletor_css", "")

    logger.info(f"\n   Executando: {intencao[:80]}")
    if _PATTERN_ENGINE_DISPONIVEL and pattern_engine and pattern:
        taxa = pattern_engine.taxa_sucesso_pattern(pattern)
        best_strat = pattern_engine.melhor_strategy_historica(pattern, contexto_tela[:30])
        logger.info(
            f"   [PatternEngine] \'{pattern}\' | taxa histórica: {taxa:.0%}"
            + (f" | melhor strategy: {best_strat}" if best_strat else "")
        )
    scroll_y = await _scroll_para_area_esperada(page, coords_relativas)

    # ── 1. BRAIN DB ─────────────────────────────────────────────
    cache = await asyncio.to_thread(_consultar_cache, intencao)
    if cache:
        if cache.seletor:
            cand = TentativaLocalizacao(seletor=cache.seletor, iframe_hint=cache.iframe_src or iframe_hint, descricao="brain cache")
            if await _tentar_candidato(page, cand, acao, valor, timeout_ms=1500):
                logger.info("   [Brain] ✅ Acerto direto via memória.")
                await asyncio.to_thread(_registrar_sucesso_cache, intencao)
                return True
        if cache.coords:
            if await _clicar_por_coordenadas(page, cache.coords, acao, valor):
                logger.info("   [Brain] ✅ Acerto via coordenadas memorizadas.")
                await asyncio.to_thread(_registrar_sucesso_cache, intencao)
                return True

    # ── 2. SELETOR CSS DO ROTEIRO ────────────────────────────────
    # Tenta rápido o seletor capturado pelo getUniqueSelector().
    # Timeout curto: se não achou em 800ms, não vale a pena insistir.
    if seletor_css:
        try:
            contexto = await _resolver_contexto(page, iframe_hint)
            loc = contexto.locator(seletor_css).first
            await loc.wait_for(state="visible", timeout=800)
            await _executar_acao(loc, page, acao, valor)
            logger.info(f"   [CSS] ✅ Seletor direto funcionou: {seletor_css[:60]}")
            await asyncio.to_thread(_registrar_sucesso_cache, intencao, seletor=seletor_css)
            return True
        except Exception:
            logger.info(f"   [CSS] Seletor não localizou o elemento. Partindo para Vision...")

    # ── 3. VISION FIRST ──────────────────────────────────────────
    # Para menu_navigation: hover na sidebar para expandir ANTES do screenshot.
    # Para outros patterns: screenshot direto.
    if gemini_client:
        vp = page.viewport_size or {"width": 1920, "height": 1080}

        # Prepara o estado da tela para o screenshot
        if pattern == "menu_navigation":
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            faixa = await _obter_faixa_util_sidebar(page)

            # Detecta submenu: x_pct > 0.08 significa que o capture gravou
            # o clique dentro do painel expandido, não no ícone da coluna lateral.
            eh_submenu = (
                coords_relativas
                and coords_relativas.get("x_pct", 0) > 0.08
            )

            # Sempre reseta scroll para garantir que o topo da sidebar está visível.
            await _resetar_scroll_sidebar(page)
            await asyncio.sleep(0.3)

            x_hover = int(faixa.get("x_hover", 40))

            if eh_submenu:
                # SUBMENU: hover na Y do próprio item (não no centro genérico).
                # O item fica próximo do ícone pai — hoverar ali mantém o submenu aberto.
                # Ex: GED y_pct=0.603 (Y:651) está perto do Senior Flow y_pct=0.665 (Y:718).
                # Hoverar em Y:651 na borda da sidebar (X:23) mantém o pai ativo.
                y_raw   = int(coords_relativas["y_pct"] * vp["height"])
                y_hover = max(faixa.get("y_top", 100), min(y_raw, faixa.get("y_bottom", vp["height"] - 100)))
                logger.info(f"   [Vision-First] Submenu — hover X:{x_hover} Y:{y_hover} (na Y do item para manter pai expandido)...")
            else:
                # ITEM PRINCIPAL: hover no centro da faixa útil.
                if coords_relativas and coords_relativas.get("y_pct"):
                    y_raw   = int(coords_relativas["y_pct"] * vp["height"])
                    y_hover = max(faixa.get("y_top", 100), min(y_raw, faixa.get("y_bottom", vp["height"] - 100)))
                else:
                    y_hover = int((faixa.get("y_top", 200) + faixa.get("y_bottom", vp["height"] - 100)) / 2)
                logger.info(f"   [Vision-First] Item principal — hover X:{x_hover} Y:{y_hover}...")

            try:
                await page.mouse.move(x_hover, y_hover)
                await asyncio.sleep(1.5)  # tempo extra para submenu abrir completamente
            except Exception:
                pass

        # Tenta até 3× com scroll entre tentativas (para itens fora do viewport)
        MAX_TENTATIVAS_VISION = 3
        for tentativa_v in range(MAX_TENTATIVAS_VISION):
            logger.info(f"   [Vision-First] Capturando screenshot HD (tentativa {tentativa_v+1}/{MAX_TENTATIVAS_VISION})...")
            foto = await _tirar_foto_hd(page)

            resultado = await _gemini_vision_first(
                page=page,
                intencao=intencao,
                label_curto=label_curto,
                descricao_visual=descricao_visual,
                contexto_tela=contexto_tela,
                screenshot=foto,
                pattern=pattern,
                coords_relativas=coords_relativas,
            )

            if resultado and resultado.get("coordenadas"):
                c = resultado["coordenadas"]
                confianca = resultado.get("confianca", "media")

                # Guardrail para menu: coordenada deve estar no lado esquerdo da tela
                # Guardrail: x_pct_max vem do registry, fallback 0.45
                _guardrail_x = (
                    pattern_engine.guardrail(pattern, "x_pct_max", 0.45)
                    if _PATTERN_ENGINE_DISPONIVEL and pattern_engine and pattern
                    else 0.45
                )
                if pattern == "menu_navigation" and c.get("x", 9999) > vp["width"] * _guardrail_x:
                    logger.warning(f"   [Vision Guardrail] X:{c['x']} além de {_guardrail_x:.0%} da tela — descartado.")
                    # Não desiste: scrolla e tenta novamente
                else:
                    logger.info(f"   [Vision-First] ✅ Gemini localizou '{label_curto}' em X:{c.get('x')} Y:{c.get('y')} (confiança: {confianca})")
                    if await _clicar_por_coordenadas(page, c, acao, valor):
                        await asyncio.to_thread(_registrar_sucesso_cache, intencao, coords=c)
                        await asyncio.to_thread(_registrar_healing_necessario, intencao, acao_tec)
                        return True

            if tentativa_v < MAX_TENTATIVAS_VISION - 1:
                # Scrolla a sidebar/página e tenta novamente
                logger.info(f"   [Vision-First] Elemento não localizado. Scroll e nova tentativa...")
                if pattern == "menu_navigation":
                    await _scroll_sidebar_container(page, 280)
                    try:
                        # Mantém hover na borda da sidebar (não nas coords do capture)
                        await page.mouse.move(x_hover, y_hover)
                        await asyncio.sleep(0.8)
                    except Exception:
                        pass
                else:
                    await page.evaluate("window.scrollBy(0, 300)")
                    await asyncio.sleep(0.5)

    # ── 4. SNIPER DOM ────────────────────────────────────────────
    # Fallback quando Gemini não está disponível ou retornou nao_encontrado.
    logger.info(f"   [Sniper] Vision não resolveu. Tentando candidatos DOM para '{label_curto}'...")
    candidatos = _gerar_candidatos(
        seletor_css, label_curto, iframe_hint,
        acao, alvo.get("tipo_elemento", "button"), ""
    )
    for cand in candidatos:
        if await _tentar_candidato(page, cand, acao, valor, timeout_ms=1000):
            logger.info(f"   [Sniper] ✅ Acerto: {cand.descricao}")
            await asyncio.to_thread(_registrar_sucesso_cache, intencao, seletor=cand.seletor)
            return True

    frame_url = await _buscar_em_todos_os_frames(page, candidatos, acao, valor)
    if frame_url:
        logger.info(f"   [Sniper] ✅ Encontrado em iframe: {frame_url[:60]}")
        return True

    # ── 5. GPS ORIGINAL DO CAPTURE ───────────────────────────────
    # Último recurso: usa as coordenadas exatas gravadas pelo capture_semantic.
    # Pode não funcionar se o layout mudou, mas vale tentar antes de desistir.
    if coords_relativas and coords_relativas.get("x_pct") and coords_relativas.get("y_pct"):
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        x = int(coords_relativas["x_pct"] * vp["width"])
        y = int(coords_relativas["y_pct"] * vp["height"])
        logger.info(f"   [GPS Fallback] Tentando coordenadas originais do capture: X:{x} Y:{y}")
        if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
            return True

    logger.error(f"   [FALHA TOTAL] Impossivel executar: '{intencao[:70]}'")
    return False


async def _validar_menu_item_ativo_dom(page: Page, label: str) -> Optional[bool]:
    """
    Validação DETERMINÍSTICA de menu lateral via DOM.
    Retorna True se o item ficou ativo, False se claramente inativo, None se inconclusivo.

    Por que isso existe:
    O Gemini comete falsos negativos em menus do Senior X porque vê o conteúdo
    do painel central (ex: "Indicadores de Incorporação") e conclui que o clique
    errou — mesmo quando o item de menu está visivelmente ativo.
    DOM não alucina: aria-current, aria-selected e classes 'active'/'selected'
    são sinais confiáveis de que o item está ativo.
    """
    try:
        resultado = await page.evaluate(
            """(label) => {
                const low = label.toLowerCase().trim();

                // Seletores que Angular Material usa para estado ativo
                const atributosAtivos = [
                    '[aria-current="page"]',
                    '[aria-current="true"]',
                    '[aria-selected="true"]',
                    '[aria-expanded="true"]',
                ];
                const classesAtivas = ['active', 'selected', 'is-active', 'mat-mdc-list-item-activated', 'activated'];

                // Escopo na sidebar
                const sidebar = document.querySelector(
                    'aside, nav, [class*="sidebar"], [class*="sidenav"], mat-sidenav, [role="navigation"]'
                ) || document;

                const todos = [...sidebar.querySelectorAll('*')];

                for (const el of todos) {
                    // Verifica se este elemento contém o texto do label
                    const txt = ((el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '') + '').trim().toLowerCase();
                    if (!txt.includes(low)) continue;

                    // Sobe até 6 níveis procurando indicador de ativo
                    let node = el;
                    for (let i = 0; i < 6 && node && node !== document.body; i++, node = node.parentElement) {
                        // Checa atributos ARIA
                        for (const attr of atributosAtivos) {
                            if (node.matches && node.matches(attr)) return { ativo: true, motivo: attr };
                        }
                        // Checa classes
                        const cls = (node.className || '').toString().toLowerCase();
                        for (const c of classesAtivas) {
                            if (cls.includes(c)) return { ativo: true, motivo: 'class:' + c };
                        }
                        // Checa se um submenu filho está expandido/visível (indica que o pai foi clicado)
                        const filhos = node.querySelectorAll ? [...node.querySelectorAll('[aria-expanded="true"], [aria-current="page"]')] : [];
                        if (filhos.length > 0) return { ativo: true, motivo: 'filho_expandido' };
                    }
                }

                // Nenhum sinal encontrado — inconclusivo (não é falha, é "não sei")
                return { ativo: null, motivo: 'sem_sinal_dom' };
            }""",
            label,
        )
        if resultado is None:
            return None
        if resultado.get("ativo") is True:
            logger.info(f"   [Validador DOM] ✅ '{label}' ativo via {resultado.get('motivo')}")
            return True
        if resultado.get("ativo") is False:
            logger.warning(f"   [Validador DOM] ❌ '{label}' explicitamente inativo")
            return False
        # ativo == null → inconclusivo
        logger.info(f"   [Validador DOM] ⚪ Sem sinal DOM para '{label}' — delegando ao Gemini")
        return None
    except Exception as e:
        logger.warning(f"   [Validador DOM] Erro: {e}")
        return None


async def _validar_estado_visual(
    page: Page,
    validacao: dict,
    pattern: str = "",
    label_curto: str = "",
    iframe_hint: str = "",
) -> bool:
    """
    Validação em três camadas:

    1. DETERMINÍSTICA (DOM) — para menu_navigation.
    2. IFRAME FOCADO — quando iframe_hint presente: crop do iframe + prompt correto.
    3. GEMINI GERAL — para outros patterns sem iframe.
    """
    if not validacao or not validacao.get("alvo"):
        return True

    logger.info(f"   [Validador] Conferindo: '{validacao['alvo'][:80]}'")
    await _aguardar_estabilidade(page, timeout_ms=2500)

    # ── Camada 1: DOM determinístico (menu lateral) ──────────────
    if pattern == "menu_navigation" and label_curto and not iframe_hint:
        dom_resultado = await _validar_menu_item_ativo_dom(page, label_curto)
        if dom_resultado is True:
            logger.info("   [Validador] ✅ SUCESSO determinístico via DOM")
            return True
        if dom_resultado is False:
            logger.warning("   [Validador] ❌ FALHA determinística via DOM")
            return False

    # ── Camada 1b: DOM determinístico para navegação em iframe ───
    # Para ações de retorno ao root (breadcrumb home, página inicial),
    # verifica se o breadcrumb agora tem apenas 1 item (ícone raiz).
    # Isso é mais confiável do que pedir ao Gemini para encontrar o texto "Home"
    # que nunca aparece como título — o GED mostra listagem de pastas diretamente.
    if iframe_hint and label_curto:
        label_lower = label_curto.lower()
        is_home_nav = any(w in label_lower for w in ("home", "inicial", "raiz", "root", "início"))
        if is_home_nav:
            try:
                breadcrumb_depth = await page.evaluate("""
                    () => {
                        const sels = ['iframe[name="ci"]', 'iframe[src*="ci"]', 'iframe'];
                        for (const sel of sels) {
                            const fr = document.querySelector(sel);
                            if (!fr) continue;
                            try {
                                const doc = fr.contentDocument || fr.contentWindow.document;
                                if (!doc) continue;
                                const bc = doc.querySelector('.ui-breadcrumb, [class*="breadcrumb"], nav[aria-label*="bread"]');
                                if (bc) {
                                    const items = bc.querySelectorAll('li, a, span');
                                    return items.length;
                                }
                            } catch(e) {}
                        }
                        return -1;
                    }
                """)
                if breadcrumb_depth is not None and 0 < breadcrumb_depth <= 2:
                    logger.info(f"   [Validador DOM] ✅ Breadcrumb no root (profundidade:{breadcrumb_depth}) — Home confirmado")
                    return True
            except Exception:
                pass

        # Para qualquer ação em iframe: verifica se o URL do iframe mudou
        # ou se o título do conteúdo corresponde ao label (checagem rápida no DOM)
        try:
            dom_match = await page.evaluate(
                """(label) => {
                    const sels = ['iframe[name="ci"]', 'iframe[src*="ci"]', 'iframe'];
                    for (const sel of sels) {
                        const fr = document.querySelector(sel);
                        if (!fr) continue;
                        try {
                            const doc = fr.contentDocument || fr.contentWindow.document;
                            if (!doc) continue;
                            const txt = (doc.title || doc.body?.innerText || '').toLowerCase();
                            if (txt.includes(label.toLowerCase())) return true;
                            // Verifica h1/h2/breadcrumb
                            const heads = doc.querySelectorAll('h1, h2, .breadcrumb-item, .ui-breadcrumb li:last-child');
                            for (const h of heads) {
                                if ((h.innerText || h.textContent || '').toLowerCase().includes(label.toLowerCase()))
                                    return true;
                            }
                        } catch(e) {}
                    }
                    return false;
                }""",
                label_curto,
            )
            if dom_match:
                logger.info(f"   [Validador DOM] ✅ '{label_curto}' encontrado no DOM do iframe")
                return True
        except Exception:
            pass

    if not gemini_client:
        logger.info("   [Validador] Gemini indisponível — assumindo sucesso.")
        return True

    try:
        # ── Camada 2: Validação focada no iframe ─────────────────
        if iframe_hint:
            foto = await _tirar_foto_iframe(page, iframe_hint)
            label_lower = (label_curto or "").lower()
            is_home_nav = any(w in label_lower for w in ("home", "inicial", "raiz", "root", "início"))

            if is_home_nav:
                # Para navegação ao root: o GED não mostra título "Home" —
                # mostra a listagem de pastas raiz sem nenhum breadcrumb de subpasta.
                prompt_iframe = (
                    f"Esta imagem mostra o conteúdo de um sistema GED/ERP.\n"
                    f"O robô clicou no ícone de 'página inicial' (casa/home) no breadcrumb.\n"
                    f"Aceite como SUCESSO se QUALQUER uma dessas evidências aparecer:\n"
                    f"  - o breadcrumb mostra apenas o ícone raiz (sem nomes de subpastas)\n"
                    f"  - o conteúdo mostra uma listagem de pastas de nível raiz\n"
                    f"  - o título da área é genérico (ex: 'Documentos', 'Home', 'Início', ou similar)\n"
                    f"  - a tela claramente 'resetou' para o nível mais alto de navegação\n"
                    f"NÃO exija que a palavra 'Home' apareça em algum lugar — é um ícone, não texto.\n"
                )
            else:
                prompt_iframe = (
                    f"Esta imagem mostra o conteúdo de uma área do sistema ERP.\n"
                    f"O robô acabou de clicar em '{label_curto or validacao['alvo']}'.\n"
                    f"Verifique se a ação funcionou. Aceite como SUCESSO se qualquer evidência aparecer:\n"
                    f"  - título/cabeçalho da área mostra '{label_curto}'\n"
                    f"  - breadcrumb atualizado para incluir '{label_curto}'\n"
                    f"  - conteúdo da pasta/item '{label_curto}' está visível (arquivos, subpastas, registros)\n"
                    f"  - item '{label_curto}' está selecionado/destacado na lista\n"
                    f"NÃO procure na barra lateral esquerda — o alvo está no CONTEÚDO CENTRAL.\n"
                )

            contents = [
                "Você é um validador de automação. Responda só com JSON.",
                prompt_iframe,
                'Responda SOMENTE em JSON: {"sucesso": true/false, "motivo": "..."}',
                types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
            ]

        # ── Camada 3: Menu lateral ────────────────────────────────
        elif pattern == "menu_navigation":
            foto = await _tirar_foto_limpa(page)
            contents = [
                "Você é um validador de automação. Responda só com JSON.",
                (
                    f"O robô acabou de clicar no item de menu '{label_curto or validacao['alvo']}'.\n"
                    f"Olhe o screenshot: o item ficou ativo/selecionado no menu lateral?\n"
                    f"Aceite como sucesso: item destacado, sublinhado, colorido diferente, submenu aberto.\n"
                    f"NÃO avalie o conteúdo do painel central.\n"
                ),
                'Responda SOMENTE em JSON: {"sucesso": true/false, "motivo": "..."}',
                types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
            ]

        # ── Camada 3: Geral ───────────────────────────────────────
        else:
            foto = await _tirar_foto_limpa(page)
            contents = [
                "Você é um validador de automação. Responda só com JSON.",
                f"Evidência visual esperada na tela: {validacao['alvo']}",
                'Responda SOMENTE em JSON: {"sucesso": true/false, "motivo": "..."}',
                types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
            ]

        res = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )
        out = json.loads(res.text)
        is_success = out.get("sucesso", True)
        if is_success:
            logger.info(f"   [Validador] ✅ SUCESSO visual: {out.get('motivo', '')[:80]}")
        else:
            logger.warning(f"   [Validador] ❌ FALHA visual: {out.get('motivo', '')[:80]}")
        return is_success

    except Exception as e:
        logger.warning(f"   [Validador] Erro Gemini: {e} — assumindo sucesso")
        return True


async def _tirar_foto_iframe(page: Page, iframe_hint: str) -> Optional[bytes]:
    """
    Tira screenshot focado no iframe alvo.
    Tenta obter as dimensões reais do iframe para um crop preciso.
    Se não conseguir, retorna screenshot da página inteira.
    """
    try:
        # Tenta obter bounding box do iframe pela geometria
        info = await page.evaluate(
            """(hint) => {
                const sels = [
                    `iframe[name='${hint}']`,
                    `iframe[src*='${hint}']`,
                    `iframe[id='${hint}']`,
                    `iframe[title*='${hint}']`,
                ];
                for (const sel of sels) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100 && r.height > 100)
                            return { x: r.left, y: r.top, width: r.width, height: r.height };
                    }
                }
                // Fallback: maior iframe visível
                let best = null, bestArea = 0;
                for (const el of document.querySelectorAll('iframe')) {
                    const r = el.getBoundingClientRect();
                    const area = r.width * r.height;
                    if (area > bestArea && r.width > 200) { bestArea = area; best = r; }
                }
                return best ? { x: best.left, y: best.top, width: best.width, height: best.height } : null;
            }""",
            iframe_hint,
        )
        if info:
            clip = {
                "x": max(0, int(info["x"])),
                "y": max(0, int(info["y"])),
                "width": max(200, int(info["width"])),
                "height": max(200, int(info["height"])),
            }
            return await page.screenshot(type="jpeg", quality=85, clip=clip)
    except Exception:
        pass
    # Fallback: tela inteira
    return await _tirar_foto_hd(page)


async def _sidebar_explorer(
    page: Page,
    label_curto: str,
    acao: str,
    valor: str,
    coords_relativas: Optional[dict],
) -> bool:
    """
    Percorre a sidebar/submenu procurando o item.

    Para itens PRINCIPAIS (x_pct <= 0.08): usa crop estreito da sidebar + scroll.
    Para SUBMENUS (x_pct > 0.08): usa screenshot de tela inteira + hover na Y do item
    para manter o submenu do pai expandido. Não faz scroll (submenu não tem scroll).
    """
    if not gemini_client:
        return False

    vp = page.viewport_size or {"width": 1920, "height": 1080}
    faixa      = await _obter_faixa_util_sidebar(page)
    x_hover    = int(faixa["x_hover"])
    eh_submenu = (
        coords_relativas
        and coords_relativas.get("x_pct", 0) > 0.08
    )

    if eh_submenu:
        # Submenu: hover na Y do item para manter o pai expandido.
        # Usa screenshot de tela inteira — o submenu fica fora do crop estreito da sidebar.
        y_raw    = int(coords_relativas["y_pct"] * vp["height"])
        y_hover  = max(faixa.get("y_top", 100), min(y_raw, faixa.get("y_bottom", vp["height"] - 100)))

        logger.info(f"   [Sidebar Explorer] Submenu — hover X:{x_hover} Y:{y_hover} + screenshot tela inteira para '{label_curto}'...")
        await _resetar_scroll_sidebar(page)
        try:
            await page.mouse.move(x_hover, y_hover)
            await asyncio.sleep(1.5)
        except Exception:
            pass

        # Uma única tentativa com tela inteira (submenus não têm scroll)
        foto = await _tirar_foto_hd(page)
        try:
            resp = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    (
                        f"Esta é a tela inteira de um ERP. O menu lateral tem um submenu expandido.\n"
                        f"Procure o item de submenu '{label_curto}' — é um texto ou ícone dentro do painel expandido que aparece ao lado dos ícones da sidebar.\n"
                        f"Retorne as coordenadas do CENTRO do elemento na TELA INTEIRA (não relativo a nenhum crop).\n"
                        f"Se não encontrar com certeza: {{\"metodo\":\"nao_encontrado\"}}\n"
                        f"JSON: {{\"metodo\":\"coordenadas\",\"coordenadas\":{{\"x\":200,\"y\":400}},\"confianca\":\"alta|media|baixa\"}}"
                    ),
                    types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
            )
            out = json.loads(resp.text)
            if out.get("metodo") != "nao_encontrado" and out.get("coordenadas"):
                cx = int(out["coordenadas"]["x"])
                cy = int(out["coordenadas"]["y"])
                logger.info(f"   [Sidebar Explorer] ✅ Submenu '{label_curto}' em X:{cx} Y:{cy} (confiança:{out.get('confianca','?')})")
                if await _clicar_por_coordenadas(page, {"x": cx, "y": cy}, acao, valor):
                    return True
        except Exception as e:
            logger.warning(f"   [Sidebar Explorer] Erro submenu: {e}")
        return False

    # ITEM PRINCIPAL: comportamento original com crop e scroll
    logger.info(f"   [Sidebar Explorer] Iniciando varredura completa para '{label_curto}'...")
    y_centro      = int((faixa["y_top"] + faixa["y_bottom"]) / 2)
    altura_pagina = max(200, int(faixa["y_bottom"] - faixa["y_top"]) - 40)

    await _resetar_scroll_sidebar(page)
    try:
        await page.mouse.move(x_hover, y_centro)
        await asyncio.sleep(1.0)
    except Exception:
        pass

    for pagina in range(8):
        logger.info(f"   [Sidebar Explorer] Página {pagina + 1}/8 da sidebar...")
        clip_bytes = await _screenshot_sidebar_clip(page)
        if not clip_bytes:
            break
        try:
            resp = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model="gemini-2.5-flash",
                contents=[
                    (
                        f"Esta imagem é um CROP da barra lateral de um ERP.\n"
                        f"Procure o item '{label_curto}' neste crop.\n"
                        f"Se encontrar, retorne coordenadas relativas ao CROP (não à tela).\n"
                        f"Se não encontrar: {{\"metodo\":\"nao_encontrado\"}}\n"
                        f"JSON: {{\"metodo\":\"coordenadas\",\"coordenadas\":{{\"x\":50,\"y\":120}},\"confianca\":\"alta|media|baixa\"}}"
                    ),
                    types.Part.from_bytes(data=clip_bytes, mime_type="image/jpeg"),
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
            )
            out = json.loads(resp.text)
            if out.get("metodo") != "nao_encontrado" and out.get("coordenadas"):
                cx = int(out["coordenadas"]["x"] + faixa["left"])
                cy = int(out["coordenadas"]["y"] + faixa["top"])
                if faixa["left"] <= cx <= faixa["left"] + faixa["width"] and faixa["y_top"] <= cy <= faixa["y_bottom"]:
                    logger.info(f"   [Sidebar Explorer] ✅ '{label_curto}' em X:{cx} Y:{cy} (p{pagina+1}, confiança:{out.get('confianca','?')})")
                    if await _clicar_por_coordenadas(page, {"x": cx, "y": cy}, acao, valor):
                        return True
        except Exception as e:
            logger.warning(f"   [Sidebar Explorer] Erro: {e}")

        changed = await _scroll_sidebar_container(page, altura_pagina)
        if not changed:
            logger.info("   [Sidebar Explorer] Fim do scroll da sidebar.")
            break
        try:
            await page.mouse.move(x_hover, y_centro)
            await asyncio.sleep(0.6)
        except Exception:
            break

    return False


async def _iframe_explorer(
    page: Page,
    label_curto: str,
    acao: str,
    valor: str,
    iframe_hint: str,
    coords_relativas: Optional[dict],
) -> bool:
    """
    Procura e clica em um elemento DENTRO de um iframe específico.

    Por que existe separado do Sidebar Explorer:
    O GED do Senior X roda dentro de um iframe (hint: "ci").
    Pastas, tabelas e botões estão no DOM do iframe — invisíveis para
    qualquer locator que opere no page principal.

    Estratégia:
    1. Tira screenshot focado no iframe (crop preciso)
    2. Gemini localiza o elemento dentro desse crop
    3. Converte coords do crop para coords da tela
    4. Clica via page.mouse (que opera em coordenadas de tela, atravessando iframes)

    Alternativa DOM: tenta locators diretos no frame antes de chamar Gemini.
    """
    if not gemini_client:
        return False

    logger.info(f"   [iFrame Explorer] Procurando '{label_curto}' no iframe '{iframe_hint}'...")

    # ── Tentativa 1: DOM dentro do frame ────────────────────────
    # Rápido e gratuito — tenta antes de gastar chamada Gemini
    try:
        frames = page.frames
        for frame in frames:
            if iframe_hint.lower() in (frame.name or "").lower() or iframe_hint.lower() in (frame.url or "").lower():
                for seletor in [
                    f"text=\"{label_curto}\"",
                    f"[title*='{label_curto}' i]",
                    f"[aria-label*='{label_curto}' i]",
                    f"*:has-text(\"{label_curto}\")",
                ]:
                    try:
                        loc = frame.locator(seletor).first
                        await loc.wait_for(state="visible", timeout=800)
                        box = await loc.bounding_box()
                        if box:
                            cx = int(box["x"] + box["width"] / 2)
                            cy = int(box["y"] + box["height"] / 2)
                            logger.info(f"   [iFrame Explorer] ✅ DOM direto: '{label_curto}' em X:{cx} Y:{cy}")
                            await page.mouse.click(cx, cy)
                            await _aguardar_estabilidade(page)
                            return True
                    except Exception:
                        continue
    except Exception:
        pass

    # ── Tentativa 2: Vision dentro do iframe ─────────────────────
    # Obtém bounding box do iframe para referenciar coordenadas
    try:
        iframe_box = await page.evaluate(
            """(hint) => {
                const sels = [`iframe[name='${hint}']`, `iframe[src*='${hint}']`, `iframe[id='${hint}']`];
                for (const sel of sels) {
                    const el = document.querySelector(sel);
                    if (el) {
                        const r = el.getBoundingClientRect();
                        if (r.width > 100) return { x: r.left, y: r.top, w: r.width, h: r.height };
                    }
                }
                // Fallback: maior iframe
                let best = null, ba = 0;
                for (const el of document.querySelectorAll('iframe')) {
                    const r = el.getBoundingClientRect();
                    if (r.width * r.height > ba && r.width > 200) { ba = r.width * r.height; best = r; }
                }
                return best ? { x: best.left, y: best.top, w: best.width, h: best.height } : null;
            }""",
            iframe_hint,
        )
    except Exception:
        iframe_box = None

    foto = await _tirar_foto_iframe(page, iframe_hint)
    if not foto:
        return False

    dica = ""
    if coords_relativas and iframe_box:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        x_abs = int(coords_relativas["x_pct"] * vp["width"])
        y_abs = int(coords_relativas["y_pct"] * vp["height"])
        # Converte para coords relativas ao crop do iframe
        x_rel = x_abs - int(iframe_box.get("x", 0))
        y_rel = y_abs - int(iframe_box.get("y", 0))
        dica = f"\n📍 GPS: na gravação, o clique estava em aprox X:{x_rel} Y:{y_rel} dentro deste iframe."

    try:
        resp = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                (
                    f"Esta imagem é o conteúdo de um iframe de um sistema ERP.\n"
                    f"Procure o elemento '{label_curto}' nesta tela.\n"
                    f"Pode ser uma pasta, linha de tabela, botão ou link com esse nome.\n"
                    f"{dica}\n"
                    f"Se encontrar, dê as coordenadas do centro RELATIVAS A ESTA IMAGEM.\n"
                    f"Se não encontrar: {{\"metodo\":\"nao_encontrado\"}}\n"
                    f"JSON: {{\"metodo\":\"coordenadas\",\"coordenadas\":{{\"x\":200,\"y\":150}},\"confianca\":\"alta|media|baixa\"}}"
                ),
                types.Part.from_bytes(data=foto, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
        )
        out = json.loads(resp.text)
        if out.get("metodo") == "nao_encontrado":
            logger.info(f"   [iFrame Explorer] Gemini não localizou '{label_curto}' no iframe.")
            return False

        if out.get("coordenadas"):
            # Converte coords do crop para coords da tela
            ox = int(iframe_box.get("x", 0)) if iframe_box else 0
            oy = int(iframe_box.get("y", 0)) if iframe_box else 0
            cx = int(out["coordenadas"]["x"]) + ox
            cy = int(out["coordenadas"]["y"]) + oy
            logger.info(f"   [iFrame Explorer] ✅ '{label_curto}' em X:{cx} Y:{cy} (confiança:{out.get('confianca','?')})")
            await _highlight_coords(page, cx, cy)
            await asyncio.sleep(0.2)
            await page.mouse.click(cx, cy)
            await _aguardar_estabilidade(page)
            return True

    except Exception as e:
        logger.warning(f"   [iFrame Explorer] Erro Gemini: {e}")

    return False


async def encontrar_e_clicar(page: Page, acao_tec: dict) -> bool:
    """
    Ponto de entrada. Orquestra core → validação → resgate por contexto.

    Roteamento do resgate:
    - tem iframe_hint → _iframe_explorer  (contexto: conteúdo de iframe)
    - pattern == menu_navigation → _sidebar_explorer  (contexto: sidebar)
    - outros → vision genérico  (contexto: página principal)
    """
    label_curto = acao_tec.get("elemento_alvo", {}).get("label_curto", "")
    pattern     = acao_tec.get("pattern_detectado", "")
    intencao    = acao_tec.get("intencao_semantica", "Ação")
    alvo        = acao_tec.get("elemento_alvo", {})
    acao        = acao_tec.get("acao", "clique")
    valor       = acao_tec.get("valor_input", "") or ""
    iframe_hint = alvo.get("iframe_hint", "") or ""

    sucesso_core = await _encontrar_e_clicar_core(page, acao_tec)
    if not sucesso_core:
        return False

    validacao = acao_tec.get("validacao_esperada")
    if not validacao or not validacao.get("alvo"):
        return True

    # Validação com contexto correto desde o início
    is_valido = await _validar_estado_visual(
        page, validacao, pattern, label_curto=label_curto, iframe_hint=iframe_hint
    )
    if is_valido:
        return True

    # ── FALHA DE VALIDAÇÃO — Invalida o Brain DB ─────────────────
    # O core retornou True (clicou em algo) mas o validador confirmou
    # que o resultado não foi o esperado. Isso significa que o Brain DB
    # tinha dados ruins (seletor/coords de sessão anterior com layout diferente).
    # Marcamos validacao_ok=0 para que a próxima consulta ignore esta entrada.
    logger.warning(
        f"   [Brain] Invalidando cache para '{intencao[:50]}' — clique não confirmado pelo validador."
    )
    await asyncio.to_thread(_registrar_sucesso_cache, intencao, validacao_ok=False)

    # ── Resgate roteado por CONTEXTO ─────────────────────────────
    logger.warning(f"   [Resgate] Iniciando resgate para '{intencao[:50]}'. Contexto: {'iframe:'+iframe_hint if iframe_hint else pattern}")

    # CONTEXTO 1: iframe — elemento está dentro de um frame filho
    if iframe_hint:
        sucesso = await _iframe_explorer(
            page, label_curto, acao, valor, iframe_hint, alvo.get("coordenadas_relativas")
        )
        if sucesso:
            await asyncio.sleep(0.8)
            if await _validar_estado_visual(page, validacao, pattern, label_curto=label_curto, iframe_hint=iframe_hint):
                await asyncio.to_thread(_registrar_healing_necessario, intencao + " (IFRAME)", acao_tec)
                return True

    # CONTEXTO 2: menu lateral — elemento está na sidebar
    elif pattern == "menu_navigation":
        sucesso = await _sidebar_explorer(
            page, label_curto, acao, valor, alvo.get("coordenadas_relativas")
        )
        if sucesso:
            await asyncio.sleep(1.0)
            if await _validar_estado_visual(page, validacao, pattern, label_curto=label_curto):
                await asyncio.to_thread(_registrar_healing_necessario, intencao + " (EXPLORER)", acao_tec)
                return True

    # CONTEXTO 3: página principal — elemento genérico
    else:
        try:
            foto = await _tirar_foto_hd(page)
            resultado = await _gemini_vision_first(
                page=page, intencao=intencao, label_curto=label_curto,
                descricao_visual=alvo.get("descricao_visual", label_curto),
                contexto_tela=alvo.get("contexto_tela", ""),
                screenshot=foto, pattern=pattern,
                coords_relativas=alvo.get("coordenadas_relativas"),
            )
            if resultado and resultado.get("coordenadas"):
                if await _clicar_por_coordenadas(page, resultado["coordenadas"], acao, valor):
                    if await _validar_estado_visual(page, validacao, pattern, label_curto=label_curto):
                        await asyncio.to_thread(_registrar_healing_necessario, intencao + " (RESGATE)", acao_tec)
                        return True
        except Exception:
            pass

    logger.error(f"   [Resgate] Esgotado para: '{intencao[:60]}'")
    return False
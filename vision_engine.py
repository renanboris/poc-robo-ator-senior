"""
vision_engine.py — Motor de localização e execução de ações no browser.

Filosofia: cascata de estratégias do mais barato ao mais caro.
Cada camada só é acionada se a anterior falhar completamente.

Camadas de Resiliência:
  0  Brain (Memória SQLite Permanente - Auto-Cura e Zero-Touch)
  1  Foco nativo / active element (campos de digitação inline e novas pastas)
  1.5 Heurísticas Senior X (Ícones mudos como Home, Lixeira, etc)
  2  Sniper semântico — 15+ seletores Playwright nativos (getByRole, getByLabel…)
  3  Seletor hint original (se não for frágil)
  4  Busca em todos os frames da página (sem depender do hint de iframe)
  5  Gemini Vision — Agente Operacional Autônomo (Self-Healing Supremo)
  6  Coordenadas relativas da gravação (corrigidas por scroll)

Correcoes aplicadas:

  [BUG-1] ALTO — gemini_client sem guard de chave ausente
  [BUG-2] ALTO — Brain salva cand.descricao como seletor quando cand.seletor=""
  [BUG-3] ALTO — Double _registrar_falha_cache quando Brain seletor falha
  [BUG-4] MÉDIO — _init_db() chamado no nivel do modulo sem try/except
  [PERFORMANCE-1] — Adicionado slots=True em TentativaLocalizacao para economia de RAM.
  [PERFORMANCE-2] — Ativado modo WAL no SQLite para alta concorrência sem bloqueio.
  [PERFORMANCE-3] — DB queries migradas para threads assíncronas (asyncio.to_thread).
  [FEATURE-1] — Delay de 1s injetado antes do Enter em todas as ações digitar_e_enter.
  [FEATURE-2] — Self-Healing Visual com registo de cura (relatorio_auto_cura.json).
  [FIX] "Efeito Espelho" — _tirar_foto_limpa() oculta legendas do robô antes do screenshot da IA.
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

load_dotenv()

logger = logging.getLogger(__name__)

# [BUG-1] FIX: guard de chave ausente
_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Gemini Vision desativado (fallback: coordenadas).")

# ──────────────────────────────────────────────────────────────
# BRAIN - MEMORIA DE LONGO PRAZO (SQLITE)
# ──────────────────────────────────────────────────────────────
DB_PATH          = "brain.db"
MAX_FALHAS_CACHE = 3


def _init_db():
    """Inicializa o banco de dados SQLite com otimizações de alta concorrência."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA cache_size = -64000;") 

            conn.execute("""
                CREATE TABLE IF NOT EXISTS memoria_semantica (
                    hash_intencao TEXT PRIMARY KEY,
                    intencao TEXT,
                    seletor TEXT,
                    coords TEXT,
                    iframe TEXT,
                    hits INTEGER DEFAULT 0,
                    falhas_consecutivas INTEGER DEFAULT 0,
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    except Exception as e:
        logger.error(f"Nao foi possivel inicializar Brain DB em '{DB_PATH}': {e}")


_init_db()


def _chave_cache(intencao: str) -> str:
    return hashlib.md5(intencao.strip().lower().encode()).hexdigest()[:16]


@dataclass
class EntradaCache:
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    hits: int = 0
    falhas_consecutivas: int = 0


def _consultar_cache(intencao: str) -> Optional[EntradaCache]:
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM memoria_semantica WHERE hash_intencao = ?", (chave,)
            ).fetchone()

            if row:
                if row["falhas_consecutivas"] >= MAX_FALHAS_CACHE:
                    logger.debug(f"   [Brain] Memoria obsoleta apagada: '{intencao[:40]}'")
                    conn.execute("DELETE FROM memoria_semantica WHERE hash_intencao = ?", (chave,))
                    return None

                logger.info(f"   [Brain] Memoria ativada para: '{intencao[:50]}'")
                return EntradaCache(
                    seletor=row["seletor"],
                    coords=json.loads(row["coords"]) if row["coords"] else None,
                    iframe_src=row["iframe"],
                    hits=row["hits"],
                    falhas_consecutivas=row["falhas_consecutivas"],
                )
    except Exception as e:
        logger.error(f"Erro ao ler Brain DB: {e}")
    return None


def _registrar_sucesso_cache(
    intencao: str,
    seletor: Optional[str] = None,
    coords: Optional[dict] = None,
    iframe: Optional[str] = None,
):
    chave      = _chave_cache(intencao)
    coords_str = json.dumps(coords) if coords else None

    # Descarta seletores muito vagos
    if seletor and not seletor.startswith(("text=", "[", "#")):
        seletor = None

    try:
        with sqlite3.connect(DB_PATH) as conn:
            existente = conn.execute(
                "SELECT hits FROM memoria_semantica WHERE hash_intencao = ?", (chave,)
            ).fetchone()

            if existente:
                query  = "UPDATE memoria_semantica SET hits = hits + 1, falhas_consecutivas = 0, ultima_atualizacao = CURRENT_TIMESTAMP"
                params: list = []
                if seletor:
                    query += ", seletor = ?"; params.append(seletor)
                if coords_str:
                    query += ", coords = ?"; params.append(coords_str)
                if iframe:
                    query += ", iframe = ?"; params.append(iframe)
                query += " WHERE hash_intencao = ?"; params.append(chave)
                conn.execute(query, params)
            else:
                conn.execute("""
                    INSERT INTO memoria_semantica
                        (hash_intencao, intencao, seletor, coords, iframe, hits, falhas_consecutivas)
                    VALUES (?, ?, ?, ?, ?, 1, 0)
                """, (chave, intencao, seletor, coords_str, iframe))
    except Exception as e:
        logger.error(f"Erro ao salvar no Brain DB: {e}")


def _registrar_falha_cache(intencao: str):
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE memoria_semantica SET falhas_consecutivas = falhas_consecutivas + 1 WHERE hash_intencao = ?",
                (chave,),
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
            "status": "CURADO VIA IA VISUAL (SELF-HEALING)"
        }
        logs = []
        if os.path.exists(arquivo):
            with open(arquivo, "r", encoding="utf-8") as f:
                logs = json.load(f)
        logs.append(registro)
        with open(arquivo, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        logger.warning(f"💊 OPERAÇÃO SALVA: A IA Visual encontrou e clicou no elemento '{intencao}'.")
    except Exception as e:
        pass


# ──────────────────────────────────────────────────────────────
# ESTRUTURAS DE CANDIDATOS (SNIPER)
# ──────────────────────────────────────────────────────────────
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


# ──────────────────────────────────────────────────────────────
# ANALISE DE SELETORES E ATRIBUTOS
# ──────────────────────────────────────────────────────────────
_TAGS_FRAGEIS = {
    "h1", "h2", "h3", "h4", "span", "div", "em", "p", "li",
    "ul", "a", "button", "input", "section", "article", "td", "tr", "svg", "i", "path",
}


def _e_seletor_fragil(seletor: str) -> bool:
    if not seletor:
        return True
    for prefixo in ("text=", "has-text", "[aria-label=", "[data-testid=", "[id=", "[name=", "[placeholder=", "[role="):
        if prefixo in seletor:
            return False
    tag = seletor.strip().split(":")[0].split("[")[0].split(".")[0].split(">")[0].strip()
    return tag in _TAGS_FRAGEIS


def _extrair_atributo(seletor: str, atributo: str) -> Optional[str]:
    match = re.search(rf"{atributo}=['\"]([^'\"]+)['\"]", seletor)
    return match.group(1) if match else None


# ──────────────────────────────────────────────────────────────
# GERACAO DE CANDIDATOS (SNIPER)
# ──────────────────────────────────────────────────────────────
def _gerar_candidatos(
    seletor_hint: str, label_curto: str, iframe_hint: Optional[str],
    acao: str, tipo_elemento: str, html_hint: str,
) -> list[TentativaLocalizacao]:
    candidatos: list[TentativaLocalizacao] = []
    eh_digitacao    = acao in ("digitar_e_enter", "preencher_campo")
    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS

    if label_curto and not is_tag_generica:
        if not eh_digitacao:
            candidatos.append(TentativaLocalizacao(
                seletor=f'text="{label_curto}"', iframe_hint=iframe_hint,
                exact=True, descricao=f"texto exato '{label_curto}'",
            ))

        role_map = {"button": "button", "link": "link", "menu_item": "menuitem",
                    "checkbox": "checkbox", "tab": "tab", "input": "textbox"}
        role = role_map.get(tipo_elemento)
        if role:
            candidatos.append(TentativaLocalizacao(
                seletor="", role=role, label=label_curto,
                iframe_hint=iframe_hint, descricao=f"role={role} name='{label_curto}'",
            ))

        if eh_digitacao or tipo_elemento in ("input",):
            candidatos.append(TentativaLocalizacao(
                seletor="", label=label_curto, iframe_hint=iframe_hint,
                descricao=f"label '{label_curto}'",
            ))

        candidatos.append(TentativaLocalizacao(
            seletor=f"[aria-label='{label_curto}']", iframe_hint=iframe_hint,
            descricao=f"aria-label='{label_curto}'",
        ))
        if label_curto != label_curto.lower():
            candidatos.append(TentativaLocalizacao(
                seletor=f"[aria-label='{label_curto.lower()}']",
                iframe_hint=iframe_hint, descricao="aria-label lowercase",
            ))

    aria_hint = _extrair_atributo(seletor_hint, "aria-label")
    if aria_hint and aria_hint != label_curto:
        candidatos.append(TentativaLocalizacao(
            seletor=f"[aria-label='{aria_hint}']", iframe_hint=iframe_hint,
            descricao=f"aria-label do hint '{aria_hint}'",
        ))

    testid = _extrair_atributo(seletor_hint, "data-testid")
    if testid:
        candidatos.append(TentativaLocalizacao(
            seletor=f"[data-testid='{testid}']", iframe_hint=iframe_hint,
            descricao=f"data-testid='{testid}'",
        ))
        variante = testid.replace("-", "_") if "-" in testid else testid.replace("_", "-")
        candidatos.append(TentativaLocalizacao(
            seletor=f"[data-testid='{variante}']", iframe_hint=iframe_hint,
            descricao=f"data-testid variante '{variante}'",
        ))

    if html_hint:
        ph_match = re.search(r"placeholder=['\"]([^'\"]+)['\"]", html_hint)
        if ph_match:
            ph = ph_match.group(1)
            candidatos.append(TentativaLocalizacao(
                seletor=f"[placeholder='{ph}']", iframe_hint=iframe_hint, descricao=f"placeholder='{ph}'",
            ))
            candidatos.append(TentativaLocalizacao(
                seletor="", placeholder=ph, iframe_hint=iframe_hint, descricao=f"getByPlaceholder '{ph}'",
            ))

        title_match = re.search(r"title=['\"]([^'\"]+)['\"]", html_hint)
        if title_match:
            t = title_match.group(1)
            candidatos.append(TentativaLocalizacao(
                seletor=f"[title='{t}']", iframe_hint=iframe_hint, descricao=f"title='{t}'",
            ))
            candidatos.append(TentativaLocalizacao(
                seletor="", title=t, iframe_hint=iframe_hint, descricao=f"getByTitle '{t}'",
            ))

        id_match = re.search(r"\bid=['\"]([^'\"]+)['\"]", html_hint)
        if id_match:
            elem_id = id_match.group(1)
            if not re.search(r"(ng-|mat-|cdk-|\d{5,})", elem_id):
                candidatos.append(TentativaLocalizacao(
                    seletor=f"#{elem_id}", iframe_hint=iframe_hint, descricao=f"id='{elem_id}'",
                ))

    if label_curto and not is_tag_generica and not eh_digitacao and len(label_curto) > 3:
        candidatos.append(TentativaLocalizacao(
            seletor=f">> text={label_curto}", via_pierce=True, iframe_hint=iframe_hint,
            descricao=f"shadow DOM pierce texto '{label_curto}'",
        ))
        candidatos.append(TentativaLocalizacao(
            seletor=f"text={label_curto}", iframe_hint=iframe_hint,
            exact=False, descricao=f"texto parcial '{label_curto}'",
        ))

    return candidatos


# ──────────────────────────────────────────────────────────────
# RESOLUCAO DE IFRAME E SCROLL
# ──────────────────────────────────────────────────────────────
async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal", "iframe-cross-origin"):
        return page

    for seletor_iframe in [
        f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']",
        f"iframe[id='{iframe_hint}']",   f"iframe[title*='{iframe_hint}']",
    ]:
        try:
            fl = page.frame_locator(seletor_iframe)
            await fl.locator("body").wait_for(state="attached", timeout=800)
            return fl
        except Exception:
            continue

    try:
        for frame in page.frames:
            try:
                if iframe_hint in frame.url or iframe_hint in frame.name:
                    return frame
            except Exception:
                continue
    except Exception:
        pass

    return page


async def _scroll_para_area_esperada(page: Page, coords_relativas: Optional[dict]) -> int:
    try:
        if coords_relativas and coords_relativas.get("y_pct"):
            vp            = page.viewport_size or {"width": 1920, "height": 1080}
            altura_est    = coords_relativas["y_pct"] * vp["height"] * 2
            if altura_est > vp["height"] * 0.8:
                await page.evaluate(f"window.scrollTo(0, {max(0, int(altura_est - 300))})")
                await asyncio.sleep(0.3)
        scroll_y = await page.evaluate("() => window.scrollY") or 0
        return int(scroll_y)
    except Exception:
        return 0


# ──────────────────────────────────────────────────────────────
# HIGHLIGHT VISUAL E FOTO LIMPA
# ──────────────────────────────────────────────────────────────
async def _tirar_foto_limpa(page: Page) -> bytes:
    """
    Tira um screenshot garantindo que cursores, legendas e marcações do robô
    fiquem ocultos milissegundos antes da foto, evitando o 'Efeito Espelho' na IA.
    """
    esconder_fantasmas = """() => {
        const elementos = document.querySelectorAll('#robo-cursor, #robo-legenda, .robo-tooltip, #senior-rec-widget, div[style*="z-index: 999999"]');
        elementos.forEach(el => {
            el.setAttribute('data-old-opacity', el.style.opacity || '');
            el.style.opacity = '0';
        });
    }"""
    
    mostrar_fantasmas = """() => {
        const elementos = document.querySelectorAll('#robo-cursor, #robo-legenda, .robo-tooltip, #senior-rec-widget, div[style*="z-index: 999999"]');
        elementos.forEach(el => {
            el.style.opacity = el.getAttribute('data-old-opacity') || '1';
        });
    }"""
    
    try:
        await page.evaluate(esconder_fantasmas)
        await asyncio.sleep(0.1) # Aguarda o DOM redesenhar
        foto = await page.screenshot(type="jpeg", quality=60, full_page=False)
        await page.evaluate(mostrar_fantasmas)
        return foto
    except Exception as e:
        logger.warning(f"Falha ao camuflar UI do robô antes da foto: {e}")
        return await page.screenshot(type="jpeg", quality=60, full_page=False)

async def _highlight_elemento(locator, page) -> None:
    try:
        await locator.evaluate("""el => {
            const alvoVisual = el;
            const oldOutline = alvoVisual.style.outline;
            const oldBoxShadow = alvoVisual.style.boxShadow;
            const oldBorderRadius = alvoVisual.style.borderRadius;

            alvoVisual.style.outline = '2px solid #00e5e5';
            alvoVisual.style.boxShadow = '0 0 8px rgba(0,229,229,0.5)';
            alvoVisual.style.borderRadius = '4px';
            
            setTimeout(() => {
                alvoVisual.style.outline = oldOutline; 
                alvoVisual.style.boxShadow = oldBoxShadow;
                alvoVisual.style.borderRadius = oldBorderRadius;
            }, 1200);
        }""")
        await asyncio.sleep(0.2)
    except Exception:
        pass


async def _highlight_coords(page: Page, x: int, y: int) -> None:
    try:
        await page.evaluate(f"""() => {{
            const dot = document.createElement('div');
            dot.style.cssText = 'position:fixed;left:{x-18}px;top:{y-18}px;width:36px;height:36px;border-radius:50%;background:rgba(0,229,229,0.5);border:3px solid #00e5e5;z-index:999999;pointer-events:none;animation:ping 0.6s ease-out;';
            document.body.appendChild(dot);
            setTimeout(() => dot.remove(), 900);
        }}""")
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
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            from cursor_engine import mover_cursor_humanizado
            await page.evaluate("() => { const c = document.getElementById('robo-cursor'); if(c) c.style.opacity = '1'; }")
            await mover_cursor_humanizado(page, cx, cy)
            
            if "checkbox" not in acao and "p-checkbox" not in str(locator):
                await locator.hover(timeout=2000)
    except Exception:
        pass

    await _highlight_elemento(locator, page)

    is_file = False
    try:
        html_do_botao = await locator.evaluate("el => el.outerHTML", timeout=1000)
        if 'type="file"' in html_do_botao.lower() or 'upload' in html_do_botao.lower():
            is_file = True
    except Exception:
        pass

    if acao == "upload" or is_file:
        import tempfile
        import os
        nome_arquivo = valor if valor else "documento_treinamento.pdf"
        nome_arquivo = nome_arquivo.split("\\")[-1].split("/")[-1] 
        
        tmp_path = os.path.join(tempfile.gettempdir(), nome_arquivo)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"{nome_arquivo.upper()}\n\nLorem ipsum dolor sit amet. Este documento é uma simulação.")
        
        await page.evaluate(f"""(nome) => {{
            const overlay = document.createElement('div');
            overlay.id = 'senior-upload-overlay';
            overlay.style.cssText = `
                position:fixed; top:0; left:0; width:100vw; height:100vh;
                background:rgba(15,23,42,0.92); backdrop-filter:blur(8px);
                display:flex; flex-direction:column; align-items:center; justify-content:center;
                z-index:2147483647; color:#fff; font-family:'Segoe UI', sans-serif;
                opacity:0; transition:opacity 0.6s ease;
            `;
            overlay.innerHTML = `
                <div style="font-size:64px; margin-bottom:15px; animation: bounce-vertical 1s infinite alternate;">📁</div>
                <h2 style="font-weight:400; font-size:28px; margin:0;">Buscando arquivo local no computador...</h2>
                <p style="color:#00e5e5; font-size:22px; font-weight:bold; margin-top:20px; letter-spacing:1px;">Selecionando: ${{nome}}</p>
            `;
            document.body.appendChild(overlay);
            setTimeout(() => overlay.style.opacity = '1', 50);
        }}""", nome_arquivo)
        
        await asyncio.sleep(2.5)
        
        try:
            await locator.set_input_files(tmp_path, timeout=2000)
        except Exception:
            try:
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await locator.click(timeout=2000)
                file_chooser = await fc_info.value
                await file_chooser.set_files(tmp_path)
            except Exception:
                pass
        
        await page.evaluate("""() => {
            const overlay = document.getElementById('senior-upload-overlay');
            if(overlay) {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 600);
            }
        }""")
        await asyncio.sleep(0.5)
        return

    if acao == "duplo_clique":
        await locator.dblclick(timeout=3000)
    elif acao == "clique_direito":
        await locator.click(button="right", timeout=3000)
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


# ──────────────────────────────────────────────────────────────
# TENTATIVA DE SELETOR E FOCO NATIVO
# ──────────────────────────────────────────────────────────────
async def _tentar_candidato(
    page: Page, candidato: TentativaLocalizacao, acao: str, valor: str, timeout_ms: int = 3500
) -> bool:
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
            texto = candidato.seletor[5:].strip('"').strip("'")
            loc   = contexto.get_by_text(texto, exact=candidato.exact).first
        elif candidato.via_pierce:
            loc = page.locator(candidato.seletor).first
        else:
            loc = contexto.locator(candidato.seletor).first

        await loc.wait_for(state="visible", timeout=timeout_ms)
        await _executar_acao(loc, page, acao, valor)
        return True
    except Exception:
        return False


async def _digitar_no_active_element(page: Page, acao: str, valor: str) -> bool:
    try:
        is_editable = False
        for _ in range(5):
            is_editable = await page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el.tagName === 'BODY') return false;
                return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable || el.getAttribute('contenteditable') === 'true';
            }""")
            if is_editable:
                break
            await asyncio.sleep(0.3)

        if not is_editable:
            return False

        await page.evaluate("""() => {
            const el = document.activeElement;
            el.style.transition = 'all 0.3s';
            el.style.outline = '4px solid #00e5e5';
            el.style.boxShadow = '0 0 25px rgba(0,229,229,0.5)';
        }""")
        await asyncio.sleep(0.8)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
        if acao == "digitar_e_enter":
            await asyncio.sleep(1) 
            await page.keyboard.press("Enter")
        await asyncio.sleep(0.3)
        try:
            await page.evaluate("() => { const el = document.activeElement; if (el) { el.style.outline = ''; el.style.boxShadow = ''; } }")
        except Exception:
            pass
        await _aguardar_estabilidade(page)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# BUSCA EM TODOS OS FRAMES
# ──────────────────────────────────────────────────────────────
async def _buscar_em_todos_os_frames(
    page: Page, candidatos: list[TentativaLocalizacao], acao: str, valor: str
) -> Optional[str]:
    try:
        frames = page.frames
    except Exception:
        return None

    frames_filhos = [f for f in frames if f != page.main_frame]

    for frame in frames_filhos:
        for candidato in candidatos[:8]:
            cand_frame = TentativaLocalizacao(
                seletor=candidato.seletor, iframe_hint=None, exact=candidato.exact,
                via_pierce=candidato.via_pierce, role=candidato.role, label=candidato.label,
                placeholder=candidato.placeholder, title=candidato.title, descricao=candidato.descricao,
            )
            try:
                contexto = frame
                if not cand_frame.seletor:
                    if hasattr(contexto, "get_by_role") and cand_frame.role and cand_frame.label:
                        loc = contexto.get_by_role(cand_frame.role, name=cand_frame.label).first
                    elif hasattr(contexto, "get_by_label") and cand_frame.label:
                        loc = contexto.get_by_label(cand_frame.label).first
                    elif hasattr(contexto, "get_by_placeholder") and cand_frame.placeholder:
                        loc = contexto.get_by_placeholder(cand_frame.placeholder).first
                    elif hasattr(contexto, "get_by_title") and cand_frame.title:
                        loc = contexto.get_by_title(cand_frame.title).first
                    else:
                        continue
                elif cand_frame.seletor.startswith("text="):
                    texto = cand_frame.seletor[5:].strip('"').strip("'")
                    loc   = contexto.get_by_text(texto, exact=cand_frame.exact).first
                else:
                    loc = contexto.locator(cand_frame.seletor).first

                await loc.wait_for(state="visible", timeout=1500)
                await _executar_acao(loc, page, acao, valor)
                logger.info(f"   [Todos os Frames] Encontrado em frame: {frame.url[:60]}")
                return frame.url
            except Exception:
                continue
    return None


# ──────────────────────────────────────────────────────────────
# GEMINI VISION (AGENTE OPERACIONAL) & COORDENADAS
# ──────────────────────────────────────────────────────────────
async def _gemini_localizar_elemento(
    screenshot_atual: bytes, screenshot_ref_b64: Optional[str],
    descricao_visual: str, intencao: str, contexto_tela: str,
    viewport: dict, scroll_y: int,
) -> Optional[dict]:
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
        f"A tela possui uma resolução de {viewport['width']}px de largura por {viewport['height']}px de altura.\n"
        f"O scroll vertical atual é {scroll_y}px.\n\n"
        f"SUA MISSÃO:\n"
        f"Localize as coordenadas exatas (centro do alvo) na IMAGEM 2 baseando-se nestes dados humanos:\n"
        f"- O QUE o usuário quer fazer (Intenção): {intencao}\n"
        f"- COMO era o botão (Descrição Visual): {descricao_visual}\n"
        f"- ONDE ele deveria estar (Contexto): {contexto_tela}\n\n"
        f"CUIDADO COM TABELAS E GRIDS: Se a intenção for 'habilitar algo para alguém' (ex: permissão), você DEVE cruzar a linha da pessoa com a coluna da permissão e retornar a coordenada EXATAMENTE em cima do Checkbox, e NÃO em cima do texto do nome.\n\n"
        f"Responda ESTRITAMENTE em JSON com a seguinte estrutura. O campo 'raciocinio' é OBRIGATÓRIO para você explicar como encontrou o alvo antes de dar a coordenada.\n"
        f"Exemplo Sucesso: {{\n"
        f"  \"metodo\": \"coordenadas\",\n"
        f"  \"raciocinio\": \"Encontrei a linha 'Adriana' e a coluna 'Download'. O checkbox na interseção está vazio. Coordenadas: X:845, Y:312\",\n"
        f"  \"coordenadas\": {{\"x\": 845, \"y\": 312}},\n"
        f"  \"confianca\": \"alta\"\n"
        f"}}\n"
        f"Exemplo Falha: {{\"metodo\": \"nao_encontrado\", \"raciocinio\": \"A Adriana não está visível\"}}"
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

        await _highlight_coords(page, x, y)
        await asyncio.sleep(0.3)

        if acao == "duplo_clique":
            await page.mouse.dblclick(x, y)
        elif acao == "clique_direito":
            await page.mouse.click(x, y, button="right")
        else:
            await page.mouse.click(x, y)

        if acao in ("digitar_e_enter", "preencher_campo") and valor:
            await asyncio.sleep(0.3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=40)
            if acao == "digitar_e_enter":
                await asyncio.sleep(1) 
                await page.keyboard.press("Enter")

        await _aguardar_estabilidade(page)
        return True
    except Exception as exc:
        logger.warning(f"Clique por coordenadas falhou: {exc}")
        return False


# ──────────────────────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL (A MAQUINA DE DECISAO)
# ──────────────────────────────────────────────────────────────
async def _encontrar_e_clicar_core(page: Page, acao_tec: dict) -> bool:
    alvo:     dict         = acao_tec.get("elemento_alvo", {})
    acao:     str          = acao_tec.get("acao", "clique")
    intencao: str          = acao_tec.get("intencao_semantica", "Acao na interface")
    valor:    str          = acao_tec.get("valor_input", "") or ""

    label_curto:     str           = alvo.get("label_curto", "")
    iframe_hint:     Optional[str] = alvo.get("iframe_hint")
    seletor_hint:    str           = alvo.get("seletor_hint", "")
    descricao_visual: str          = alvo.get("descricao_visual", label_curto)
    contexto_tela:   str           = alvo.get("contexto_tela", "")
    tipo_elemento:   str           = alvo.get("tipo_elemento", "button")
    html_hint:       str           = alvo.get("html_hint", "")
    coords_relativas: Optional[dict] = alvo.get("coordenadas_relativas")

    logger.info(f"\n   Executando: {intencao[:80]}")
    scroll_y = await _scroll_para_area_esperada(page, coords_relativas)

    # ── 0. BRAIN (Memoria SQLite de longo prazo) ──────────────────────────────
    brain_registrou_falha = False
    cache = await asyncio.to_thread(_consultar_cache, intencao)
    
    if cache:
        if cache.seletor:
            cand_cache = TentativaLocalizacao(
                seletor=cache.seletor,
                iframe_hint=cache.iframe_src or iframe_hint,
                descricao="brain knowledge",
            )
            if await _tentar_candidato(page, cand_cache, acao, valor):
                await asyncio.to_thread(_registrar_sucesso_cache, intencao)
                return True
            else:
                await asyncio.to_thread(_registrar_falha_cache, intencao)
                brain_registrou_falha = True
        elif cache.coords:
            if await _clicar_por_coordenadas(page, cache.coords, acao, valor):
                await asyncio.to_thread(_registrar_sucesso_cache, intencao)
                return True
            else:
                await asyncio.to_thread(_registrar_falha_cache, intencao)
                brain_registrou_falha = True

    # ── 1. Foco Nativo (exclusivo para inputs) ────────────────────────────────
    if acao in ("digitar_e_enter", "preencher_campo"):
        logger.info("   [Foco Nativo] Verificando se cursor ja esta posicionado...")
        if await _digitar_no_active_element(page, acao, valor):
            logger.info("   [Foco Nativo] Texto inserido no campo ja focado!")
            return True

        logger.info("   [Foco Nativo] Buscando div contenteditable generica...")
        contexto = await _resolver_contexto(page, iframe_hint)
        try:
            loc_edit = contexto.locator("[contenteditable='true']")
            if await loc_edit.count() > 0 and await loc_edit.first.is_visible():
                await _executar_acao(loc_edit.first, page, acao, valor)
                return True
        except Exception:
            pass

    # ── 1.5. HEURISTICAS SENIOR X (icones mudos) ─────────────────────────────
    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS
    if is_tag_generica or not label_curto:
        intencao_low          = intencao.lower()
        contexto_heuristica   = await _resolver_contexto(page, iframe_hint)

        if any(p in intencao_low for p in ["pagina inicial", "página inicial", "home", "inicio", "início", "raiz", "dashboard"]):
            logger.info("   [Senior X] Heuristica ativada para icone Home/Breadcrumb...")
            seletores_home = [
                "li.ng-star-inserted:first-child", "p-breadcrumb li:first-child",
                ".pi-home", ".fa-home", ".ph-house", "i[class*='home']", "span[class*='home']",
            ]
            for sel in seletores_home:
                try:
                    loc = contexto_heuristica.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await _executar_acao(loc, page, acao, valor)
                        logger.info("   [Heuristica] Icone Home atingido com sucesso.")
                        await asyncio.to_thread(_registrar_sucesso_cache, intencao, seletor=sel, iframe=iframe_hint)
                        return True
                except Exception:
                    pass

    # ── Gera candidatos ───────────────────────────────────────────────────────
    candidatos = _gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)

    # ── 2. Sniper Semantico ───────────────────────────────────────────────────
    if candidatos:
        logger.info(f"   [Sniper] {len(candidatos)} candidatos para '{label_curto}'...")
        for cand in candidatos:
            if await _tentar_candidato(page, cand, acao, valor):
                logger.info(f"   [Sniper] Acerto: {cand.descricao}")
                await asyncio.to_thread(
                    _registrar_sucesso_cache,
                    intencao,
                    seletor=cand.seletor if cand.seletor else None,
                    iframe=iframe_hint,
                )
                return True

    # ── 3. Seletor Hint Original ──────────────────────────────────────────────
    if seletor_hint and not _e_seletor_fragil(seletor_hint):
        cand_hint = TentativaLocalizacao(
            seletor=seletor_hint, iframe_hint=iframe_hint,
            descricao=f"hint original '{seletor_hint[:40]}'",
        )
        if await _tentar_candidato(page, cand_hint, acao, valor):
            logger.info(f"   [Hint] Seletor original funcionou: {seletor_hint[:60]}")
            await asyncio.to_thread(_registrar_sucesso_cache, intencao, seletor=seletor_hint, iframe=iframe_hint)
            return True

    # ── 4. Busca Profunda em Todos os Frames ──────────────────────────────────
    if candidatos:
        logger.info("   [Todos os Frames] Procurando o elemento em frames filhos...")
        frame_url = await _buscar_em_todos_os_frames(page, candidatos, acao, valor)
        if frame_url:
            await asyncio.to_thread(_registrar_sucesso_cache, intencao, iframe=frame_url)
            return True

    # ── 5. Gemini Vision (Self-Healing Supremo / Autonomous UI) ───────────────
    logger.info("   [Vision] DOM esgotado. Iniciando varredura visual...")
    try:
        # 🟢 FOTO LIMPA
        screenshot_atual = await _tirar_foto_limpa(page)
    except Exception as exc:
        logger.warning(f"Screenshot falhou antes do Gemini: {exc}")
        screenshot_atual = None

    if screenshot_atual:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        resultado = await _gemini_localizar_elemento(
            screenshot_atual=screenshot_atual,
            screenshot_ref_b64=alvo.get("screenshot_referencia"),
            descricao_visual=descricao_visual,
            intencao=intencao,
            contexto_tela=contexto_tela,
            viewport=vp,
            scroll_y=scroll_y,
        )
        if resultado:
            coords_ia = resultado.get("coordenadas")
            if coords_ia:
                if await _clicar_por_coordenadas(page, coords_ia, acao, valor):
                    logger.info("   [Vision] ✅ Clique por Inteligência Visual bem-sucedido!")
                    await asyncio.to_thread(_registrar_sucesso_cache, intencao, coords=coords_ia)
                    await asyncio.to_thread(_registrar_healing_necessario, intencao, acao_tec)
                    return True

    # ── 6. Fallback Cego (Coordenadas Relativas Originais) ───────────────────
    if coords_relativas and coords_relativas.get("x_pct"):
        logger.info("   [Fallback Final] Coordenadas da gravacao original...")
        try:
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            x  = int(coords_relativas["x_pct"] * vp["width"])
            y  = int(coords_relativas["y_pct"] * vp["height"])
            if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
                logger.info(f"   [Fallback Final] Clique em ({x}, {y}) executado.")
                return True
        except Exception as exc:
            logger.warning(f"Fallback de coordenadas falhou: {exc}")

    # ── Falha Total ───────────────────────────────────────────────────────────
    if not brain_registrou_falha:
        await asyncio.to_thread(_registrar_falha_cache, intencao)
    logger.error(f"   [FALHA TOTAL] Impossivel executar: '{intencao[:70]}'")
    return False

# ──────────────────────────────────────────────────────────────
# AGENTIC UI - O VALIDADOR E RESGATE DE ESTADO
# ──────────────────────────────────────────────────────────────
async def _validar_estado_visual(page: Page, validacao: dict) -> bool:
    if not gemini_client or not validacao or not validacao.get("alvo"):
        return True
        
    logger.info(f"   [Validador] Conferindo o trabalho: '{validacao['alvo']}'")
    await _aguardar_estabilidade(page, timeout_ms=3000)
    
    try:
        # 🟢 FOTO LIMPA
        screenshot_bytes = await _tirar_foto_limpa(page)
        contents = [
            "Você é o 'Senior AI Validator', um agente de garantia de qualidade (QA).",
            "Sua missão é olhar para o ecrã atual e confirmar se a ação anterior foi bem-sucedida.",
            f"A evidência visual esperada no ecrã é: {validacao['alvo']}",
            "Responda ESTRITAMENTE em JSON com a seguinte estrutura:",
            "{\"sucesso\": true ou false, \"motivo\": \"Explicação curta do que você viu\"}",
            types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg")
        ]
        
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )
        resultado = json.loads(resposta.text)
        
        is_success = resultado.get("sucesso", True)
        if is_success:
            logger.info(f"   [Validador] ✅ SUCESSO CONFIRMADO: {resultado.get('motivo')}")
        else:
            logger.warning(f"   [Validador] ❌ FALHA DETECTADA: {resultado.get('motivo')}")
            
        return is_success
        
    except Exception as e:
        logger.warning(f"   [Validador] Erro ao consultar a IA: {e}")
        return True

async def encontrar_e_clicar(page: Page, acao_tec: dict) -> bool:
    validacao = acao_tec.get("validacao_esperada")
    intencao = acao_tec.get("intencao_semantica", "Ação")
    
    sucesso_core = await _encontrar_e_clicar_core(page, acao_tec)
    
    if not sucesso_core:
        return False
        
    if not validacao or not validacao.get("alvo"):
        return True
        
    is_valido = await _validar_estado_visual(page, validacao)
    
    if is_valido:
        return True
        
    await asyncio.to_thread(_registrar_falha_cache, intencao)
        
    logger.error(f"   [Agentic UI] O CSS mentiu! A validação de '{intencao[:30]}...' falhou!")
    logger.info("   [Agentic UI] Ativando protocolo de resgate visual autônomo...")
    
    vp = page.viewport_size or {"width": 1920, "height": 1080}
    scroll_y = int(await page.evaluate("() => window.scrollY") or 0)
    
    try:
        # 🟢 FOTO LIMPA
        screenshot_resgate = await _tirar_foto_limpa(page)
        resultado_resgate = await _gemini_localizar_elemento(
            screenshot_atual=screenshot_resgate,
            screenshot_ref_b64=None,
            descricao_visual=validacao["alvo"],
            intencao=f"CORRIGIR FALHA: Tentar atingir o objetivo '{validacao['alvo']}'",
            contexto_tela="Tentativa de resgate após o clique errado do DOM falhar a validação",
            viewport=vp,
            scroll_y=scroll_y
        )
        
        if resultado_resgate and resultado_resgate.get("coordenadas"):
            coords_ia = resultado_resgate["coordenadas"]
            acao = acao_tec.get("acao", "clique")
            valor = acao_tec.get("valor_input", "")
            
            if await _clicar_por_coordenadas(page, coords_ia, acao, valor):
                logger.info("   [Agentic UI] 💊 Resgate Visual executado com sucesso!")
                
                if await _validar_estado_visual(page, validacao):
                    await asyncio.to_thread(_registrar_healing_necessario, intencao + " (RESGATE)", acao_tec)
                    return True
    except Exception as e:
        logger.warning(f"   [Agentic UI] Falha no resgate visual: {e}")
        
    return False
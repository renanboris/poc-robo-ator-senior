"""
vision_engine_cil.py — Motor CIL v8 (Clean)
============================================
Arquitetura simplificada: um fluxo único, sem camadas redundantes.

FLUXO DE EXECUÇÃO (encontrar_e_clicar):
  1. Brain DB      → seletor/coords validados de execução anterior
  2. CSS direto    → seletor_css capturado pelo getUniqueSelector()
  3. Gemini Click  → screenshot HD + Gemini → coords → clique
                     (para menu: hover correto antes do screenshot)
  4. DOM Sniper    → candidatos por texto/aria-label (fallback leve)
  5. GPS Fallback  → coords originais do capture (último recurso)
  → Valida resultado → se falha: invalida Brain DB + tenta Gemini rescue

DECISÕES DE DESIGN:
  - Gemini é o cérebro principal, não o último recurso
  - DOM é usado apenas onde é confiável (seletor_css capturado e iframe)
  - Submenus Angular: hover na Y do item, não no centro genérico
  - iframe: screenshot focado + prompt contextual
  - Sem XPath de ancestral, sem scoring de sidebar, sem loops de 8 iterações
"""

import asyncio
import hashlib
import json
import logging
import os
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

# ── Gemini ─────────────────────────────────────────────────────
_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Vision desativado.")

# ── Pattern Engine (opcional) ───────────────────────────────────
try:
    from knowledge.pattern_engine import pattern_engine as _pe
    logger.info("[CIL] Pattern Engine carregado.")
except ImportError:
    _pe = None

# ══════════════════════════════════════════════════════════════════
# BRAIN DB v2
# ══════════════════════════════════════════════════════════════════
DB_PATH          = "data/brain_v2.db"
MAX_FALHAS_CACHE = 3


@dataclass
class _Cache:
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    hits: int = 0


def _init_db():
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("PRAGMA journal_mode=WAL;")
            c.execute("PRAGMA synchronous=NORMAL;")
            c.execute("""
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
                )""")
    except Exception as e:
        logger.error(f"Brain DB init error: {e}")


_init_db()


def _hash(s: str) -> str:
    return hashlib.md5(s.strip().lower().encode()).hexdigest()[:16]


def _brain_get(intencao: str) -> Optional[_Cache]:
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.row_factory = sqlite3.Row
            row = c.execute(
                "SELECT * FROM memoria_semantica WHERE hash_intencao=?",
                (_hash(intencao),)
            ).fetchone()
            if not row:
                return None
            if row["falhas_consecutivas"] >= MAX_FALHAS_CACHE:
                c.execute("DELETE FROM memoria_semantica WHERE hash_intencao=?", (_hash(intencao),))
                return None
            if row["validacao_ok"] == 0:
                logger.info(f"   [Brain] Entrada inválida (validacao_ok=0): '{intencao[:50]}'")
                return None
            logger.info(f"   [Brain] Memória ativada: '{intencao[:50]}'")
            return _Cache(
                seletor=row["seletor"],
                coords=json.loads(row["coords"]) if row["coords"] else None,
                iframe_src=row["iframe"],
                hits=row["hits"],
            )
    except Exception:
        return None


def _brain_save(
    intencao: str,
    seletor: Optional[str] = None,
    coords: Optional[dict] = None,
    iframe: Optional[str] = None,
    pattern: str = "",
    strategy: str = "",
    validacao_ok: bool = True,
):
    h = _hash(intencao)
    # Filtra seletores instáveis (texto literal, tags genéricas)
    if seletor and not any(seletor.startswith(p) for p in ("[", "#", "xpath=")):
        seletor = None
    # FIX D: filtra coords claramente inválidas (fora da tela ou zero)
    if coords:
        x, y = coords.get("x", 0), coords.get("y", 0)
        if x <= 0 or y <= 0 or x > 3840 or y > 2160:
            coords = None
    try:
        with sqlite3.connect(DB_PATH) as c:
            exists = c.execute(
                "SELECT hits FROM memoria_semantica WHERE hash_intencao=?", (h,)
            ).fetchone()
            if exists:
                c.execute("""
                    UPDATE memoria_semantica
                    SET hits=hits+1, falhas_consecutivas=0,
                        ultima_atualizacao=CURRENT_TIMESTAMP,
                        validacao_ok=?,
                        seletor=COALESCE(NULLIF(?,NULL),seletor),
                        coords=COALESCE(NULLIF(?,NULL),coords),
                        iframe=COALESCE(NULLIF(?,NULL),iframe),
                        pattern=COALESCE(NULLIF(?,NULL),pattern),
                        strategy_usada=COALESCE(NULLIF(?,NULL),strategy_usada)
                    WHERE hash_intencao=?""",
                    (int(validacao_ok), seletor,
                     json.dumps(coords) if coords else None,
                     iframe, pattern or None, strategy or None, h)
                )
            else:
                c.execute("""
                    INSERT INTO memoria_semantica
                        (hash_intencao,intencao,seletor,coords,iframe,
                         pattern,strategy_usada,validacao_ok,hits,falhas_consecutivas)
                    VALUES (?,?,?,?,?,?,?,?,1,0)""",
                    (h, intencao, seletor,
                     json.dumps(coords) if coords else None,
                     iframe, pattern or "", strategy or "", int(validacao_ok))
                )
    except Exception:
        pass


def _brain_invalidate(intencao: str):
    """Marca a entrada como inválida sem deletar — preserva o histórico."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute(
                "UPDATE memoria_semantica SET validacao_ok=0, falhas_consecutivas=falhas_consecutivas+1 WHERE hash_intencao=?",
                (_hash(intencao),)
            )
    except Exception:
        pass


def _brain_log_healing(intencao: str, label: str, strategy: str):
    try:
        arquivo = "data/relatorio_auto_cura.json"
        log = json.load(open(arquivo)) if os.path.exists(arquivo) else []
        log.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "intencao": intencao, "label": label, "strategy": strategy
        })
        json.dump(log, open(arquivo, "w"), indent=2, ensure_ascii=False)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════
# UTILITÁRIOS DE PÁGINA
# ══════════════════════════════════════════════════════════════════

async def _wait(page: Page, ms: int = 2000) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=ms)
    except Exception:
        await asyncio.sleep(ms / 4000)


async def _screenshot(page: Page, quality: int = 85) -> bytes:
    """Screenshot limpo — oculta widgets de gravação."""
    try:
        await page.evaluate(
            "() => document.querySelectorAll('#robo-cursor,#senior-rec-widget')"
            ".forEach(e=>{e.setAttribute('_op',e.style.opacity||'');e.style.opacity='0'})"
        )
        await asyncio.sleep(0.08)
        foto = await page.screenshot(type="jpeg", quality=quality, full_page=False)
        await page.evaluate(
            "() => document.querySelectorAll('#robo-cursor,#senior-rec-widget')"
            ".forEach(e=>{e.style.opacity=e.getAttribute('_op')||'1'})"
        )
        return foto
    except Exception:
        return await page.screenshot(type="jpeg", quality=quality, full_page=False)


async def _screenshot_iframe(page: Page, iframe_hint: str) -> bytes:
    """Screenshot focado no bounding box do iframe."""
    try:
        info = await page.evaluate("""(hint) => {
            const sels = [`iframe[name='${hint}']`,`iframe[src*='${hint}']`,`iframe[id='${hint}']`];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) { const r=el.getBoundingClientRect(); if(r.width>100) return {x:r.left,y:r.top,w:r.width,h:r.height}; }
            }
            let best=null,ba=0;
            document.querySelectorAll('iframe').forEach(el=>{
                const r=el.getBoundingClientRect(); if(r.width*r.height>ba&&r.width>200){ba=r.width*r.height;best=r;}
            });
            return best?{x:best.left,y:best.top,w:best.width,h:best.height}:null;
        }""", iframe_hint)
        if info:
            return await page.screenshot(type="jpeg", quality=85, clip={
                "x": max(0, int(info["x"])), "y": max(0, int(info["y"])),
                "width": max(200, int(info["w"])), "height": max(200, int(info["h"]))
            })
    except Exception:
        pass
    return await _screenshot(page)


async def _click(page: Page, x: int, y: int, acao: str = "clique", valor: str = "") -> bool:
    """Clique físico por coordenadas absolutas."""
    try:
        if x <= 0 or y <= 0:
            return False
        logger.info(f"   [Mouse] X:{x} Y:{y}")
        try:
            await page.evaluate(
                f"()=>{{const d=document.createElement('div');d.style.cssText='position:fixed;left:{x-14}px;top:{y-14}px;width:28px;height:28px;border-radius:50%;border:2px solid #00e5e5;z-index:999999;pointer-events:none;';document.body.appendChild(d);setTimeout(()=>d.remove(),700);}}"
            )
        except Exception:
            pass
        await asyncio.sleep(0.15)
        if acao == "duplo_clique":
            await page.mouse.dblclick(x, y)
        elif acao == "clique_direito":
            await page.mouse.click(x, y, button="right")
        elif acao == "tecla" and valor:
            await page.mouse.click(x, y)
            await asyncio.sleep(0.15)
            await page.keyboard.press(valor)
        else:
            await page.mouse.click(x, y)
        if acao in ("digitar_e_enter", "preencher_campo") and valor:
            await asyncio.sleep(0.15)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=40)
            if acao == "digitar_e_enter":
                await asyncio.sleep(0.8)
                await page.keyboard.press("Enter")
        await _wait(page, 2000)
        return True
    except Exception as e:
        logger.warning(f"   [Mouse] Clique falhou: {e}")
        return False


async def _executar_locator(locator, page: Page, acao: str, valor: str) -> bool:
    """Executa ação num locator Playwright."""
    try:
        await locator.scroll_into_view_if_needed(timeout=1500)
        box = await locator.bounding_box(timeout=800)
        if box:
            cx = int(box["x"] + box["width"] / 2)
            cy = int(box["y"] + box["height"] / 2)
            return await _click(page, cx, cy, acao, valor)
        return False
    except Exception:
        return False


async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal"):
        return page
    for sel in [f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']", f"iframe[id='{iframe_hint}']"]:
        try:
            fl = page.frame_locator(sel)
            await fl.locator("body").wait_for(state="attached", timeout=600)
            return fl
        except Exception:
            continue
    return page


# ══════════════════════════════════════════════════════════════════
# SIDEBAR — UTILITÁRIOS
# ══════════════════════════════════════════════════════════════════

async def _sidebar_info(page: Page) -> dict:
    """Descobre a sidebar por geometria. Retorna faixa útil e ponto de hover."""
    _DEFAULT = {"left": 0, "top": 0, "width": 80, "height": 900,
                "x_hover": 40, "y_top": 150, "y_bottom": 820}
    try:
        info = await page.evaluate("""() => {
            const sels=['aside','nav','[class*="sidebar"],[class*="sidenav"]','.mat-drawer','.mat-sidenav','[role="navigation"]'];
            const vw=window.innerWidth, vh=window.innerHeight;
            let best=null, bestScore=-1e9;
            sels.flatMap(s=>[...document.querySelectorAll(s)]).forEach(el=>{
                const r=el.getBoundingClientRect(), st=getComputedStyle(el);
                if(st.display==='none'||st.visibility==='hidden') return;
                if(r.width<30||r.height<vh*0.35||r.left>vw*0.35) return;
                const score=(vw-r.left)*3+r.height*0.4+Math.max(0,80-r.left)*4;
                if(score>bestScore){bestScore=score;best=r;}
            });
            if(!best) return null;
            return {
                left:Math.round(best.left), top:Math.round(best.top),
                width:Math.round(best.width), height:Math.round(best.height),
                x_hover:Math.round(best.left+Math.min(35,best.width*0.3)),
                y_top:Math.round(best.top+Math.max(120,best.height*0.15)),
                y_bottom:Math.round(best.bottom-Math.max(80,best.height*0.1))
            };
        }""")
        return info or _DEFAULT
    except Exception:
        return _DEFAULT


async def _sidebar_reset(page: Page) -> None:
    """Reseta o scroll interno da sidebar para o topo."""
    try:
        await page.evaluate("""() => {
            const sels=['mat-sidenav','mat-nav-list','[class*="sidenav-content"],[class*="sidebar"],[class*="menu-list"]','aside','[role="navigation"]'];
            for(const s of sels){
                const el=document.querySelector(s);
                if(el&&el.scrollHeight>el.clientHeight){el.scrollTop=0;return;}
            }
        }""")
        await asyncio.sleep(0.2)
    except Exception:
        pass


async def _sidebar_scroll(page: Page, delta: int = 280) -> bool:
    """Scrolla o container interno da sidebar. Retorna True se mudou."""
    try:
        result = await page.evaluate("""(delta) => {
            const sels=['mat-sidenav','mat-nav-list','[class*="sidenav-content"],[class*="sidebar"]','aside','[role="navigation"]'];
            for(const s of sels){
                const el=document.querySelector(s);
                if(el&&el.scrollHeight>el.clientHeight+10){
                    const before=el.scrollTop;
                    el.scrollTop=Math.min(el.scrollTop+delta,el.scrollHeight);
                    return el.scrollTop!==before;
                }
            }
            return false;
        }""", delta)
        return bool(result)
    except Exception:
        return False


# ══════════════════════════════════════════════════════════════════
# GEMINI — FUNÇÃO ÚNICA DE LOCALIZAÇÃO
# ══════════════════════════════════════════════════════════════════

async def _gemini_localizar(
    screenshot: bytes,
    label: str,
    instrucao: str,
) -> Optional[dict]:
    """
    Envia um screenshot ao Gemini e pede as coordenadas do elemento.
    Retorna dict com 'coordenadas': {'x': int, 'y': int} ou None.
    """
    if not gemini_client:
        return None
    try:
        resp = await asyncio.to_thread(
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
        out = json.loads(resp.text)
        if out.get("metodo") == "nao_encontrado" or not out.get("coordenadas"):
            motivo = out.get("raciocinio", out.get("motivo", "sem motivo"))[:70]
            logger.info(f"   [Gemini] nao_encontrado: {motivo}")
            return None
        logger.info(f"   [Gemini] confiança={out.get('confianca','?')} | {out.get('raciocinio','')[:70]}")
        return out
    except Exception as e:
        logger.warning(f"   [Gemini] Erro: {e}")
        return None


def _instrucao_menu(label: str, gps: str = "") -> str:
    return (
        f"Encontre o item '{label}' na BARRA LATERAL ESQUERDA desta tela de ERP.\n"
        f"Pode ser texto, ícone, ou item de submenu expandido.\n"
        f"{gps}\n"
        f"Retorne o CENTRO do elemento clicável.\n"
        f"Se não encontrar com certeza: {{\"metodo\":\"nao_encontrado\"}}\n"
        f"JSON: {{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":50,\"y\":400}},\"confianca\":\"alta|media|baixa\"}}"
    )


def _instrucao_iframe(label: str, gps: str = "") -> str:
    return (
        f"Esta é a área de conteúdo de um sistema ERP.\n"
        f"Procure o elemento '{label}' — pode ser pasta, linha, botão ou link.\n"
        f"{gps}\n"
        f"Retorne o CENTRO do elemento clicável na imagem.\n"
        f"Se não encontrar: {{\"metodo\":\"nao_encontrado\"}}\n"
        f"JSON: {{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":200,\"y\":300}},\"confianca\":\"alta|media|baixa\"}}"
    )


def _instrucao_geral(label: str, descricao: str, gps: str = "") -> str:
    return (
        f"Encontre o elemento '{label}' nesta tela.\n"
        f"Descrição: {descricao}\n"
        f"{gps}\n"
        f"Retorne o CENTRO do elemento clicável.\n"
        f"Se não encontrar: {{\"metodo\":\"nao_encontrado\"}}\n"
        f"JSON: {{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":200,\"y\":300}},\"confianca\":\"alta|media|baixa\"}}"
    )


# ══════════════════════════════════════════════════════════════════
# VALIDAÇÃO
# ══════════════════════════════════════════════════════════════════

async def _validar_menu_dom(page: Page, label: str) -> Optional[bool]:
    """Checa se item de menu ficou ativo via DOM. Retorna True/False/None."""
    try:
        result = await page.evaluate("""(label) => {
            const scope=document.querySelector('aside,nav,[class*="sidebar"],[class*="sidenav"],mat-sidenav')||document;
            const low=label.toLowerCase();
            for(const el of scope.querySelectorAll('*')){
                const txt=((el.innerText||el.textContent||el.getAttribute('aria-label')||'')+'').trim().toLowerCase();
                if(!txt.includes(low)) continue;
                let node=el;
                for(let i=0;i<5&&node;i++,node=node.parentElement){
                    const cls=(node.className||'').toString().toLowerCase();
                    const html=(node.outerHTML||'').toLowerCase();
                    if(cls.includes('active')||cls.includes('selected')||
                       html.includes('aria-current="page"')||html.includes('aria-selected="true"')||
                       html.includes('aria-expanded="true"'))
                        return {ativo:true};
                }
            }
            return {ativo:null};
        }""", label)
        if result and result.get("ativo") is True:
            logger.info(f"   [Validador DOM] ✅ '{label}' ativo")
            return True
        return None
    except Exception:
        return None


async def _validar(
    page: Page,
    validacao: dict,
    pattern: str = "",
    label: str = "",
    iframe_hint: str = "",
) -> bool:
    """Valida o resultado de uma ação. Três camadas: DOM, Gemini iframe, Gemini geral."""
    if not validacao or not validacao.get("alvo"):
        return True

    logger.info(f"   [Validador] Conferindo: '{validacao['alvo'][:70]}'")
    await _wait(page, 2500)

    # 1. DOM determinístico para menu lateral
    if pattern == "menu_navigation" and label and not iframe_hint:
        dom = await _validar_menu_dom(page, label)
        if dom is True:
            logger.info("   [Validador] ✅ DOM confirmou")
            return True

    # 2. DOM rápido para iframe (título/breadcrumb)
    if iframe_hint and label:
        try:
            match = await page.evaluate("""(hint, label) => {
                const sels=[
                    `iframe[name='${hint}']`,
                    `iframe[src*='${hint}']`,
                    `iframe[id='${hint}']`,
                    'iframe'
                ];
                for(const s of sels){
                    const fr=document.querySelector(s);
                    if(!fr) continue;
                    try{
                        const doc=fr.contentDocument||fr.contentWindow.document;
                        if(!doc) continue;
                        const txt=(doc.title||doc.body?.innerText||'').toLowerCase();
                        if(txt.includes(label.toLowerCase())) return true;
                        for(const h of doc.querySelectorAll('h1,h2,.breadcrumb-item,[class*="breadcrumb"] li:last-child')){
                            if((h.innerText||h.textContent||'').toLowerCase().includes(label.toLowerCase())) return true;
                        }
                    }catch(e){}
                }
                return false;
            }""", iframe_hint, label)
            if match:
                logger.info(f"   [Validador DOM] ✅ '{label}' no iframe")
                return True
        except Exception:
            pass

    if not gemini_client:
        return True

    # 3. Gemini visual
    try:
        foto = await _screenshot_iframe(page, iframe_hint) if iframe_hint else await _screenshot(page)

        if iframe_hint:
            label_lower = label.lower()
            is_home = any(w in label_lower for w in ("home", "inicial", "raiz", "root"))
            if is_home:
                prompt = (
                    f"Esta é a área de conteúdo de um ERP. O usuário voltou para a página raiz.\n"
                    f"Aceite como SUCESSO se: breadcrumb mostra só 1 nível, listagem de pastas raiz visível, ou área resetou para o início.\n"
                    f"NÃO exija texto 'Home' — é um ícone.\n"
                    f'JSON: {{"sucesso":true/false,"motivo":"..."}}'
                )
            else:
                prompt = (
                    f"Esta é a área de conteúdo de um ERP. O usuário clicou em '{label}'.\n"
                    f"Aceite como SUCESSO se: título/cabeçalho mostra '{label}', breadcrumb inclui '{label}', "
                    f"ou conteúdo do item está visível.\n"
                    f"NÃO procure na barra lateral — o alvo está no CONTEÚDO CENTRAL.\n"
                    f'JSON: {{"sucesso":true/false,"motivo":"..."}}'
                )
        elif pattern == "menu_navigation":
            prompt = (
                f"O usuário clicou no item de menu '{label}'.\n"
                f"Aceite como SUCESSO se o item estiver destacado/ativo/colorido diferente no menu lateral.\n"
                f"NÃO avalie o painel central.\n"
                f'JSON: {{"sucesso":true/false,"motivo":"..."}}'
            )
        else:
            prompt = (
                f"Verifique se esta ação funcionou: {validacao['alvo']}\n"
                f'JSON: {{"sucesso":true/false,"motivo":"..."}}'
            )

        res = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[prompt, types.Part.from_bytes(data=foto, mime_type="image/jpeg")],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
        )
        out = json.loads(res.text)
        ok = out.get("sucesso", True)
        motivo = out.get("motivo", "")[:80]
        if ok:
            logger.info(f"   [Validador] ✅ {motivo}")
        else:
            logger.warning(f"   [Validador] ❌ {motivo}")
        return ok
    except Exception as e:
        logger.warning(f"   [Validador] Erro Gemini: {e} — assumindo sucesso")
        return True


# ══════════════════════════════════════════════════════════════════
# CORE — ENCONTRAR E CLICAR
# ══════════════════════════════════════════════════════════════════

async def _executar_passo(page: Page, acao_tec: dict) -> tuple[bool, str]:
    """
    Tenta executar um passo. Retorna (sucesso, strategy_usada).

    Fluxo linear:
      brain → css → gemini → sniper_dom → gps_fallback
    """
    alvo     = acao_tec.get("elemento_alvo", {})
    acao     = acao_tec.get("acao", "clique")
    intencao = acao_tec.get("intencao_semantica", "")
    valor    = acao_tec.get("valor_input", "") or ""
    label    = alvo.get("label_curto", "")
    pattern  = acao_tec.get("pattern_detectado", "")
    coords_r = alvo.get("coordenadas_relativas")
    iframe   = alvo.get("iframe_hint", "") or ""
    seletor  = acao_tec.get("seletor_css", "")
    descricao= alvo.get("descricao_visual", label)

    vp = page.viewport_size or {"width": 1920, "height": 1080}

    # GPS string para dica ao Gemini
    gps = ""
    if coords_r:
        gx = int(coords_r.get("x_pct", 0) * vp["width"])
        gy = int(coords_r.get("y_pct", 0) * vp["height"])
        gps = f"📍 GPS: gravado em X:{gx} Y:{gy} — use como dica, não como verdade."

    # ── 1. BRAIN DB ──────────────────────────────────────────────
    cache = _brain_get(intencao)
    if cache:
        if cache.seletor:
            try:
                ctx = await _resolver_contexto(page, cache.iframe_src or iframe)
                loc = ctx.locator(cache.seletor).first
                await loc.wait_for(state="visible", timeout=1200)
                if await _executar_locator(loc, page, acao, valor):
                    logger.info("   [Brain] ✅ Seletor memória")
                    return True, "brain_seletor"
            except Exception:
                pass
        if cache.coords:
            x, y = int(cache.coords.get("x", 0)), int(cache.coords.get("y", 0))
            if await _click(page, x, y, acao, valor):
                logger.info("   [Brain] ✅ Coords memória")
                return True, "brain_coords"

    # ── 2. CSS DIRETO ────────────────────────────────────────────
    if seletor:
        try:
            ctx = await _resolver_contexto(page, iframe)
            loc = ctx.locator(seletor).first
            await loc.wait_for(state="visible", timeout=700)
            if await _executar_locator(loc, page, acao, valor):
                logger.info(f"   [CSS] ✅ {seletor[:55]}")
                _brain_save(intencao, seletor=seletor, iframe=iframe, pattern=pattern, strategy="css")
                return True, "css"
        except Exception:
            logger.info("   [CSS] Não localizou. Partindo para Vision...")

    # ── 3. GEMINI CLICK ──────────────────────────────────────────
    if gemini_client:
        # Prepara o estado da tela conforme o pattern
        if pattern == "menu_navigation":
            await _sidebar_reset(page)
            await asyncio.sleep(0.3)
            faixa = await _sidebar_info(page)
            x_h = int(faixa["x_hover"])
            # Y: usa a Y do item (não genérica) — mantém submenu pai aberto
            if coords_r:
                y_raw = int(coords_r["y_pct"] * vp["height"])
                y_h   = max(faixa["y_top"], min(y_raw, faixa["y_bottom"]))
            else:
                y_h = int((faixa["y_top"] + faixa["y_bottom"]) / 2)
            try:
                await page.mouse.move(x_h, y_h)
                await asyncio.sleep(1.5)
            except Exception:
                pass

        # Tenta até 3× com scroll entre tentativas
        for tentativa in range(3):
            logger.info(f"   [Vision] Tentativa {tentativa+1}/3...")

            if iframe:
                foto       = await _screenshot_iframe(page, iframe)
                instrucao  = _instrucao_iframe(label, gps)
            elif pattern == "menu_navigation":
                foto      = await _screenshot(page)
                instrucao = _instrucao_menu(label, gps)
            else:
                foto      = await _screenshot(page)
                instrucao = _instrucao_geral(label, descricao, gps)

            resultado = await _gemini_localizar(foto, label, instrucao)

            if resultado and resultado.get("coordenadas"):
                c = resultado["coordenadas"]
                cx, cy = int(c.get("x", 0)), int(c.get("y", 0))

                # Guardrail: menu deve estar no lado esquerdo
                if pattern == "menu_navigation" and cx > vp["width"] * 0.45:
                    logger.warning(f"   [Vision] X:{cx} fora da sidebar — descartado")
                else:
                    if await _click(page, cx, cy, acao, valor):
                        logger.info(f"   [Vision] ✅ X:{cx} Y:{cy}")
                        _brain_save(intencao, coords={"x": cx, "y": cy}, iframe=iframe, pattern=pattern, strategy="vision")
                        _brain_log_healing(intencao, label, "vision")
                        return True, "vision"

            if tentativa < 2:
                if pattern == "menu_navigation":
                    await _sidebar_scroll(page, 280)
                    try:
                        await page.mouse.move(x_h, y_h)
                        await asyncio.sleep(0.8)
                    except Exception:
                        pass
                elif not iframe:
                    try:
                        await page.evaluate("window.scrollBy(0,250)")
                    except Exception:
                        pass
                    await asyncio.sleep(0.4)

    # ── 4. SNIPER DOM (candidatos por texto/aria) ────────────────
    logger.info(f"   [Sniper] Tentando DOM para '{label}'...")
    for sel in [
        f'[aria-label="{label}"]', f'[title="{label}"]',
        f'text="{label}"',
    ]:
        try:
            ctx = await _resolver_contexto(page, iframe)
            loc = ctx.locator(sel).first
            await loc.wait_for(state="visible", timeout=600)
            if await _executar_locator(loc, page, acao, valor):
                logger.info(f"   [Sniper] ✅ {sel}")
                _brain_save(intencao, seletor=sel, iframe=iframe, pattern=pattern, strategy="sniper")
                return True, "sniper"
        except Exception:
            continue

    # Busca também em frames filhos
    try:
        for frame in [f for f in page.frames if f != page.main_frame]:
            for sel in [f'text="{label}"', f'[aria-label="{label}"]']:
                try:
                    loc = frame.locator(sel).first
                    await loc.wait_for(state="visible", timeout=500)
                    box = await loc.bounding_box(timeout=500)
                    if box:
                        cx = int(box["x"] + box["width"] / 2)
                        cy = int(box["y"] + box["height"] / 2)
                        if await _click(page, cx, cy, acao, valor):
                            logger.info(f"   [Sniper] ✅ Frame: {frame.url[:40]}")
                            return True, "sniper_frame"
                except Exception:
                    continue
    except Exception:
        pass

    # ── 5. GPS FALLBACK ──────────────────────────────────────────
    if coords_r and coords_r.get("x_pct") and coords_r.get("y_pct"):
        gx = int(coords_r["x_pct"] * vp["width"])
        gy = int(coords_r["y_pct"] * vp["height"])
        logger.info(f"   [GPS] Tentando coords originais X:{gx} Y:{gy}")
        if await _click(page, gx, gy, acao, valor):
            # FIX A: GPS NÃO salva no Brain DB — são coords não confiáveis do capture
            # que podem estar erradas se o layout mudou. O Brain só aprende de
            # Vision (que viu a tela atual) ou CSS (que localizou o DOM).
            return True, "gps"

    # ── IFRAME AUTO-DETECT (quando iframe_hint=null mas Vision falhou 3×) ───
    # Para button_click e table_selection: se Vision falhou mas há iframes na
    # página, o elemento pode estar dentro de um iframe não mapeado no roteiro.
    # Tenta cada iframe com screenshot focado + Gemini.
    if gemini_client and not iframe and pattern in ("button_click", "table_selection", "form_fill", "search_debounce"):
        try:
            frames_info = await page.evaluate("""() => {
                return [...document.querySelectorAll('iframe')].map(f => {
                    const r = f.getBoundingClientRect();
                    return {name: f.name || '', src: f.src || '', id: f.id || '',
                            w: r.width, h: r.height, x: r.left, y: r.top};
                }).filter(f => f.w > 200 && f.h > 100);
            }""")
            if frames_info:
                logger.info(f"   [iFrame Auto-Detect] {len(frames_info)} iframe(s) encontrado(s) — tentando Vision dentro deles...")
                for fi in frames_info[:3]:  # máximo 3 iframes
                    hint = fi.get("name") or fi.get("id") or (fi.get("src", "")[:30])
                    if not hint:
                        continue
                    clip = {"x": max(0, int(fi["x"])), "y": max(0, int(fi["y"])),
                            "width": max(200, int(fi["w"])), "height": max(200, int(fi["h"]))}
                    try:
                        foto_frame = await page.screenshot(type="jpeg", quality=85, clip=clip)
                        instrucao_f = (
                            f"Esta imagem é o conteúdo de uma área do sistema ERP (iframe '{hint}').\n"
                            f"Procure o elemento '{label}' — botão, link ou campo com este texto/ícone.\n"
                            f"Retorne coordenadas RELATIVAS A ESTA IMAGEM (crop).\n"
                            f"Se não encontrar: {{\"metodo\":\"nao_encontrado\"}}\n"
                            f"JSON: {{\"metodo\":\"coordenadas\",\"raciocinio\":\"...\",\"coordenadas\":{{\"x\":100,\"y\":50}},\"confianca\":\"alta|media|baixa\"}}"
                        )
                        resultado_f = await _gemini_localizar(foto_frame, label, instrucao_f)
                        if resultado_f and resultado_f.get("coordenadas"):
                            # Converte coords do crop para coords absolutas da tela
                            rx = int(resultado_f["coordenadas"]["x"]) + int(fi["x"])
                            ry = int(resultado_f["coordenadas"]["y"]) + int(fi["y"])
                            logger.info(f"   [iFrame Auto-Detect] ✅ '{label}' em iframe '{hint}' → tela X:{rx} Y:{ry}")
                            if await _click(page, rx, ry, acao, valor):
                                _brain_save(intencao, coords={"x": rx, "y": ry}, iframe=hint,
                                           pattern=pattern, strategy="iframe_autodetect")
                                _brain_log_healing(intencao, label, "iframe_autodetect")
                                return True, "iframe_autodetect"
                    except Exception as e_f:
                        logger.warning(f"   [iFrame Auto-Detect] Erro no iframe '{hint}': {e_f}")
        except Exception:
            pass

    return False, ""


# ══════════════════════════════════════════════════════════════════
# API PÚBLICA
# ══════════════════════════════════════════════════════════════════

async def encontrar_e_clicar(page: Page, acao_tec: dict) -> bool:
    """
    Ponto de entrada principal.
    Executa o passo, valida, e tenta um resgate se necessário.
    """
    alvo     = acao_tec.get("elemento_alvo", {})
    label    = alvo.get("label_curto", "")
    pattern  = acao_tec.get("pattern_detectado", "")
    intencao = acao_tec.get("intencao_semantica", "")
    iframe   = alvo.get("iframe_hint", "") or ""
    validacao= acao_tec.get("validacao_esperada")

    logger.info(f"\n   Executando: {intencao[:80]}")
    if _pe and pattern:
        taxa = _pe.taxa_sucesso_pattern(pattern)
        logger.info(f"   [Pattern] '{pattern}' | taxa: {taxa:.0%}")

    # Executa
    sucesso, strategy = await _executar_passo(page, acao_tec)
    if not sucesso:
        return False

    # Sem validação configurada → assume sucesso
    if not validacao or not validacao.get("alvo"):
        return True

    # Valida
    ok = await _validar(page, validacao, pattern, label, iframe)
    if ok:
        _brain_save(intencao, pattern=pattern, strategy=strategy, validacao_ok=True)
        return True

    # Validação falhou — invalida o Brain DB e tenta resgate
    logger.warning(f"   [Resgate] Validação falhou para '{intencao[:50]}'")
    _brain_invalidate(intencao)

    # Um resgate: Gemini com tela limpa
    if gemini_client:
        await asyncio.sleep(1.0)
        foto = await _screenshot_iframe(page, iframe) if iframe else await _screenshot(page)
        if iframe:
            instrucao = _instrucao_iframe(label)
        elif pattern == "menu_navigation":
            instrucao = _instrucao_menu(label)
        else:
            instrucao = _instrucao_geral(label, alvo.get("descricao_visual", label))

        resultado = await _gemini_localizar(foto, label, instrucao)
        if resultado and resultado.get("coordenadas"):
            c = resultado["coordenadas"]
            cx, cy = int(c.get("x", 0)), int(c.get("y", 0))
            if pattern == "menu_navigation" and cx > (page.viewport_size or {}).get("width", 1920) * 0.45:
                logger.warning(f"   [Resgate] X:{cx} fora da sidebar — abortando")
                return False
            acao_str = acao_tec.get("acao", "clique")
            valor_str = acao_tec.get("valor_input", "") or ""
            if await _click(page, cx, cy, acao_str, valor_str):
                await asyncio.sleep(1.0)
                ok2 = await _validar(page, validacao, pattern, label, iframe)
                if ok2:
                    _brain_save(intencao, coords={"x": cx, "y": cy}, pattern=pattern, strategy="rescue_vision", validacao_ok=True)
                    _brain_log_healing(intencao, label, "rescue_vision")
                    logger.info("   [Resgate] ✅ Resgate bem-sucedido")
                    return True

    logger.error(f"   [FALHA] '{intencao[:60]}'")
    return False
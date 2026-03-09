"""
vision_engine.py — Motor de localização e execução de ações no browser.

Filosofia: cascata de estratégias do mais barato ao mais caro.
Cada camada só é acionada se a anterior falhar completamente.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import Page, FrameLocator

load_dotenv()

logger = logging.getLogger(__name__)
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ──────────────────────────────────────────────────────────────
# 📦 ESTRUTURAS DE DADOS
# ──────────────────────────────────────────────────────────────

@dataclass
class EntradaCache:
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    hits: int = 0
    falhas_consecutivas: int = 0  # Penaliza entradas que param de funcionar

@dataclass
class TentativaLocalizacao:
    seletor: str
    iframe_hint: Optional[str] = None
    exact: bool = False
    via_pierce: bool = False          # Shadow DOM
    role: Optional[str] = None        # Para getByRole
    label: Optional[str] = None       # Para getByLabel
    placeholder: Optional[str] = None
    title: Optional[str] = None
    descricao: str = ""               # Log humanizado

# ──────────────────────────────────────────────────────────────
# 🗃️ CACHE SEMÂNTICO
# ──────────────────────────────────────────────────────────────

_cache_sessao: dict[str, EntradaCache] = {}

MAX_FALHAS_CACHE = 3  # Após 3 falhas consecutivas, a entrada é descartada

def _chave_cache(intencao: str) -> str:
    """Hash MD5 de 16 chars — sem colisão por truncagem de string."""
    return hashlib.md5(intencao.strip().lower().encode()).hexdigest()[:16]

def _consultar_cache(intencao: str) -> Optional[EntradaCache]:
    entrada = _cache_sessao.get(_chave_cache(intencao))
    if not entrada:
        return None
    if entrada.falhas_consecutivas >= MAX_FALHAS_CACHE:
        logger.debug(f"Cache descartado por {MAX_FALHAS_CACHE} falhas: '{intencao[:40]}'")
        return None
    if entrada.hits >= 1:
        logger.info(f"   ⚡ [Cache] Hit para: '{intencao[:50]}'")
        return entrada
    return None

def _registrar_sucesso_cache(intencao: str, seletor: Optional[str] = None,
                              coords: Optional[dict] = None, iframe: Optional[str] = None) -> None:
    chave = _chave_cache(intencao)
    entrada = _cache_sessao.get(chave, EntradaCache())
    entrada.hits += 1
    entrada.falhas_consecutivas = 0
    if seletor:
        entrada.seletor = seletor
    if coords:
        entrada.coords = coords
    if iframe:
        entrada.iframe_src = iframe
    _cache_sessao[chave] = entrada

def _registrar_falha_cache(intencao: str) -> None:
    chave = _chave_cache(intencao)
    entrada = _cache_sessao.get(chave, EntradaCache())
    entrada.falhas_consecutivas += 1
    _cache_sessao[chave] = entrada

# ──────────────────────────────────────────────────────────────
# 🔬 ANÁLISE DE SELETORES
# ──────────────────────────────────────────────────────────────

_TAGS_FRAGEIS = {
    'h1','h2','h3','h4','span','div','em','p','li',
    'ul','a','button','input','section','article','td','tr','svg','i'
}

def _e_seletor_fragil(seletor: str) -> bool:
    if not seletor:
        return True
    # Seletores semânticos são robustos
    for prefixo in ("text=", "has-text", "[aria-label=", "[data-testid=",
                    "[id=", "[name=", "[placeholder=", "[role="):
        if prefixo in seletor:
            return False
    tag = seletor.strip().split(':')[0].split('[')[0].split('.')[0].split('>')[0].strip()
    return tag in _TAGS_FRAGEIS

def _extrair_atributo(seletor: str, atributo: str) -> Optional[str]:
    match = re.search(rf'{atributo}=[\'"]([^\'"]+)[\'"]', seletor)
    return match.group(1) if match else None

# ──────────────────────────────────────────────────────────────
# 🎯 GERAÇÃO DE CANDIDATOS (SNIPER)
# ──────────────────────────────────────────────────────────────

def _gerar_candidatos(
    seletor_hint: str,
    label_curto: str,
    iframe_hint: Optional[str],
    acao: str,
    tipo_elemento: str,
    html_hint: str,
) -> list[TentativaLocalizacao]:
    candidatos: list[TentativaLocalizacao] = []
    eh_digitacao = acao in ("digitar_e_enter", "preencher_campo")

    # ── 1. Playwright nativos de alto nível ──────────────────
    if label_curto:
        if not eh_digitacao:
            # getByText exato
            candidatos.append(TentativaLocalizacao(
                seletor=f'text="{label_curto}"',
                iframe_hint=iframe_hint,
                exact=True,
                descricao=f"texto exato '{label_curto}'"
            ))

        role_map = {
            "button": "button", "link": "link", "menu_item": "menuitem",
            "checkbox": "checkbox", "tab": "tab", "input": "textbox",
        }
        role = role_map.get(tipo_elemento)
        if role:
            candidatos.append(TentativaLocalizacao(
                seletor="", role=role, label=label_curto, iframe_hint=iframe_hint,
                descricao=f"role={role} name='{label_curto}'"
            ))

        if eh_digitacao or tipo_elemento in ("input",):
            candidatos.append(TentativaLocalizacao(
                seletor="", label=label_curto, iframe_hint=iframe_hint,
                descricao=f"label '{label_curto}'"
            ))

        candidatos.append(TentativaLocalizacao(
            seletor=f"[aria-label='{label_curto}']", iframe_hint=iframe_hint,
            descricao=f"aria-label='{label_curto}'"
        ))

        if label_curto != label_curto.lower():
            candidatos.append(TentativaLocalizacao(
                seletor=f"[aria-label='{label_curto.lower()}']", iframe_hint=iframe_hint,
                descricao=f"aria-label lowercase"
            ))

    # ── 2. Extração do seletor hint ──────────────────────────
    aria_hint = _extrair_atributo(seletor_hint, "aria-label")
    if aria_hint and aria_hint != label_curto:
        candidatos.append(TentativaLocalizacao(seletor=f"[aria-label='{aria_hint}']", iframe_hint=iframe_hint, descricao=f"aria-label do hint '{aria_hint}'"))

    testid = _extrair_atributo(seletor_hint, "data-testid")
    if testid:
        candidatos.append(TentativaLocalizacao(seletor=f"[data-testid='{testid}']", iframe_hint=iframe_hint, descricao=f"data-testid='{testid}'"))

    # ── 3. Extração do HTML hint ─────────────────────────────
    if html_hint:
        ph_match = re.search(r'placeholder=[\'"]([^\'"]+)[\'"]', html_hint)
        if ph_match:
            ph = ph_match.group(1)
            candidatos.append(TentativaLocalizacao(seletor=f"[placeholder='{ph}']", iframe_hint=iframe_hint, descricao=f"placeholder='{ph}'"))

        title_match = re.search(r'title=[\'"]([^\'"]+)[\'"]', html_hint)
        if title_match:
            t = title_match.group(1)
            candidatos.append(TentativaLocalizacao(seletor=f"[title='{t}']", iframe_hint=iframe_hint, descricao=f"title='{t}'"))

        id_match = re.search(r'\bid=[\'"]([^\'"]+)[\'"]', html_hint)
        if id_match:
            elem_id = id_match.group(1)
            if not re.search(r'(ng-|mat-|cdk-|\d{5,})', elem_id):
                candidatos.append(TentativaLocalizacao(seletor=f"#{elem_id}", iframe_hint=iframe_hint, descricao=f"id='{elem_id}'"))

    # ── 4. Shadow DOM (pierce) ───────────────────────────────
    if label_curto and not eh_digitacao:
        candidatos.append(TentativaLocalizacao(seletor=f">> text={label_curto}", via_pierce=True, iframe_hint=iframe_hint, descricao=f"shadow DOM pierce texto '{label_curto}'"))

    # ── 5. Texto parcial (último recurso textual) ────────────
    if label_curto and not eh_digitacao and len(label_curto) > 3:
        candidatos.append(TentativaLocalizacao(seletor=f"text={label_curto}", iframe_hint=iframe_hint, exact=False, descricao=f"texto parcial '{label_curto}'"))

    return candidatos

# ──────────────────────────────────────────────────────────────
# 🖼️ RESOLUÇÃO DE IFRAME
# ──────────────────────────────────────────────────────────────

async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    """Retorna o contexto de localização correto."""
    if not iframe_hint or iframe_hint in ("Página Principal", "iframe-cross-origin"):
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

    try:
        frames = page.frames
        for frame in frames:
            try:
                if iframe_hint in frame.url or iframe_hint in frame.name:
                    return frame
            except Exception:
                continue
    except Exception:
        pass

    logger.debug(f"Iframe '{iframe_hint}' não encontrado. Usando página principal.")
    return page

# ──────────────────────────────────────────────────────────────
# ✨ HIGHLIGHT VISUAL E EXECUÇÃO FÍSICA
# ──────────────────────────────────────────────────────────────

async def _highlight_elemento(locator, page: Page) -> None:
    try:
        await locator.evaluate("""el => {
            el.style.transition = 'all 0.25s';
            el.style.outline = '4px solid #009999';
            el.style.boxShadow = '0 0 20px rgba(0,153,153,0.8)';
        }""")
        await asyncio.sleep(1.0)
        await locator.evaluate("el => { el.style.outline = ''; el.style.boxShadow = ''; }")
    except Exception:
        pass

async def _highlight_coords(page: Page, x: int, y: int) -> None:
    try:
        await page.evaluate(f"""() => {{
            const dot = document.createElement('div');
            dot.style.cssText = `
                position: fixed; left: {x - 18}px; top: {y - 18}px;
                width: 36px; height: 36px; border-radius: 50%;
                background: rgba(0,153,153,0.5); border: 3px solid #009999;
                z-index: 999999; pointer-events: none; animation: ping 0.6s ease-out;
            `;
            document.body.appendChild(dot);
            setTimeout(() => dot.remove(), 900);
        }}""")
    except Exception:
        pass

async def _aguardar_estabilidade(page: Page, timeout_ms: int = 1500) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        await asyncio.sleep(0.4)

async def _executar_acao(locator, page: Page, acao: str, valor: str) -> None:
    try:
        await locator.scroll_into_view_if_needed(timeout=2000)
        await locator.hover(timeout=1500)
    except Exception:
        pass

    await _highlight_elemento(locator, page)

    if acao == "duplo_clique":
        await locator.dblclick(timeout=3000)
    elif acao == "digitar_e_enter":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
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
# 🔑 TENTATIVA DE SELETOR ÚNICO E FOCO NATIVO
# ──────────────────────────────────────────────────────────────

async def _tentar_candidato(page: Page, candidato: TentativaLocalizacao, acao: str, valor: str, timeout_ms: int = 3500) -> bool:
    try:
        contexto = await _resolver_contexto(page, candidato.iframe_hint)

        if not candidato.seletor:
            if hasattr(contexto, 'get_by_role') and candidato.role and candidato.label:
                loc = contexto.get_by_role(candidato.role, name=candidato.label).first
            elif hasattr(contexto, 'get_by_label') and candidato.label:
                loc = contexto.get_by_label(candidato.label).first
            elif hasattr(contexto, 'get_by_placeholder') and candidato.placeholder:
                loc = contexto.get_by_placeholder(candidato.placeholder).first
            elif hasattr(contexto, 'get_by_title') and candidato.title:
                loc = contexto.get_by_title(candidato.title).first
            else:
                return False
        elif candidato.seletor.startswith("text="):
            texto = candidato.seletor[5:].strip('"').strip("'")
            loc = contexto.get_by_text(texto, exact=candidato.exact).first
        elif candidato.via_pierce:
            loc = page.locator(candidato.seletor).first
        else:
            loc = contexto.locator(candidato.seletor).first

        await loc.wait_for(state="visible", timeout=timeout_ms)
        await _executar_acao(loc, page, acao, valor)
        return True
    except Exception as exc:
        return False

async def _digitar_no_active_element(page: Page, acao: str, valor: str) -> bool:
    """O Truque do Cursor: resolve pastas pré-focadas imediatamente."""
    try:
        # Loop de espera ativa para o caso de modais lentos
        is_editable = False
        for _ in range(5):
            is_editable = await page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el.tagName === 'BODY') return false;
                return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' ||
                       el.isContentEditable || el.getAttribute('contenteditable') === 'true';
            }""")
            if is_editable: break
            await asyncio.sleep(0.3)

        if not is_editable:
            return False

        await page.evaluate("""() => {
            const el = document.activeElement;
            el.style.transition = 'all 0.3s';
            el.style.outline = '4px solid #009999';
            el.style.boxShadow = '0 0 25px #009999';
        }""")
        await asyncio.sleep(0.8)

        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
        if acao == "digitar_e_enter":
            await page.keyboard.press("Enter")

        await asyncio.sleep(0.3)
        try:
            await page.evaluate("() => { if(document.activeElement) { document.activeElement.style.outline = ''; } }")
        except Exception: pass

        await _aguardar_estabilidade(page)
        return True
    except Exception as exc:
        logger.debug(f"Active element fallback falhou: {exc}")
        return False

# ──────────────────────────────────────────────────────────────
# 🌐 BUSCA EM TODOS OS FRAMES E GEMINI VISION
# ──────────────────────────────────────────────────────────────

async def _buscar_em_todos_os_frames(page: Page, candidatos: list[TentativaLocalizacao], acao: str, valor: str) -> Optional[str]:
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
                    if hasattr(contexto, 'get_by_role') and cand_frame.role and cand_frame.label:
                        loc = contexto.get_by_role(cand_frame.role, name=cand_frame.label).first
                    elif hasattr(contexto, 'get_by_label') and cand_frame.label:
                        loc = contexto.get_by_label(cand_frame.label).first
                    else: continue
                elif cand_frame.seletor.startswith("text="):
                    texto = cand_frame.seletor[5:].strip('"').strip("'")
                    loc = contexto.get_by_text(texto, exact=cand_frame.exact).first
                else:
                    loc = contexto.locator(cand_frame.seletor).first

                await loc.wait_for(state="visible", timeout=1500)
                await _executar_acao(loc, page, acao, valor)
                logger.info(f"   ✅ [Todos os Frames] Encontrado em frame: {frame.url[:60]}")
                return frame.url
            except Exception:
                continue
    return None

async def _gemini_localizar_elemento(screenshot_atual: bytes, screenshot_ref_b64: Optional[str], descricao_visual: str, intencao: str, contexto_tela: str, viewport: dict, scroll_y: int) -> Optional[dict]:
    logger.info(f"   👁️  [Gemini Vision] Analisando tela para: '{descricao_visual[:60]}'...")
    contents = []

    if screenshot_ref_b64:
        try:
            ref_bytes = base64.b64decode(screenshot_ref_b64)
            contents.append("IMAGEM 1 — REFERÊNCIA (estado da tela na gravação original):")
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/png"))
        except Exception: pass

    contents.append("IMAGEM 2 — TELA ATUAL (onde o elemento deve ser clicado agora):")
    contents.append(types.Part.from_bytes(data=screenshot_atual, mime_type="image/png"))
    contents.append(f"""Você está controlando um navegador com resolução {viewport['width']}x{viewport['height']}px.
O scroll vertical atual da página é {scroll_y}px.

Localize este elemento na IMAGEM 2 (tela atual):
- Intenção do usuário: {intencao}
- Descrição visual: {descricao_visual}
- Contexto da tela: {contexto_tela}

Responda ESTRITAMENTE com JSON:
{{"metodo": "coordenadas", "coordenadas": {{"x": 500, "y": 300}}, "confianca": "alta|media|baixa"}}
ou
{{"metodo": "nao_encontrado"}}
""")
    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.05),
        )
        resultado = json.loads(resposta.text)

        if resultado.get("metodo") == "nao_encontrado":
            logger.warning("   ⚠️  [Gemini] Elemento não encontrado na tela atual.")
            return None

        logger.info(f"   ✅ [Gemini] Coordenadas recebidas | confiança: {resultado.get('confianca', '?')}")
        return resultado
    except Exception as exc:
        logger.error(f"Erro na API de Visão Gemini: {exc}")
        return None

def _parse_coords(coords):
    """Extração cega de segurança para coordenadas vindas da IA."""
    try:
        if isinstance(coords, dict):
            return int(coords.get('x', 0)), int(coords.get('y', 0))
        elif isinstance(coords, list):
            if len(coords) > 0 and isinstance(coords[0], dict):
                return int(coords[0].get('x', 0)), int(coords[0].get('y', 0))
            elif len(coords) >= 2:
                return int(coords[0]), int(coords[1])
        elif isinstance(coords, str):
            nums = re.findall(r'\d+', coords)
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])
    except Exception: pass
    return 0, 0

async def _clicar_por_coordenadas(page: Page, coords, acao: str, valor: str) -> bool:
    try:
        x, y = _parse_coords(coords)
        if x <= 0 or y <= 0: raise ValueError(f"Coordenadas inválidas: x={x}, y={y}")

        await _highlight_coords(page, x, y)
        await asyncio.sleep(0.3)

        if acao == "duplo_clique": await page.mouse.dblclick(x, y)
        else: await page.mouse.click(x, y)

        if acao in ("digitar_e_enter", "preencher_campo") and valor:
            await asyncio.sleep(0.3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=40)
            if acao == "digitar_e_enter": await page.keyboard.press("Enter")

        await _aguardar_estabilidade(page)
        return True
    except Exception as exc:
        logger.warning(f"Clique por coordenadas falhou: {exc}")
        return False

async def _scroll_para_area_esperada(page: Page, coords_relativas: Optional[dict]) -> int:
    try:
        if coords_relativas and coords_relativas.get("y_pct"):
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            altura_estimada = coords_relativas["y_pct"] * vp["height"] * 2
            if altura_estimada > vp["height"] * 0.8:
                await page.evaluate(f"window.scrollTo(0, {max(0, int(altura_estimada - 300))})")
                await asyncio.sleep(0.3)
        scroll_y = await page.evaluate("() => window.scrollY") or 0
        return int(scroll_y)
    except Exception: return 0

# ──────────────────────────────────────────────────────────────
# 🤖 ORQUESTRADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────

async def encontrar_e_clicar(page: Page, acao_tec: dict) -> bool:
    alvo: dict = acao_tec.get("elemento_alvo", {})
    acao: str = acao_tec.get("acao", "clique")
    intencao: str = acao_tec.get("intencao_semantica", "Ação na interface")
    valor: str = acao_tec.get("valor_input", "") or ""
    label_curto: str = alvo.get("label_curto", "")
    iframe_hint: Optional[str] = alvo.get("iframe_hint")
    seletor_hint: str = alvo.get("seletor_hint", "")
    descricao_visual: str = alvo.get("descricao_visual", label_curto)
    contexto_tela: str = alvo.get("contexto_tela", "")
    tipo_elemento: str = alvo.get("tipo_elemento", "button")
    html_hint: str = alvo.get("html_hint", "")
    coords_relativas: Optional[dict] = alvo.get("coordenadas_relativas")

    logger.info(f"\n   🎯 Executando: {intencao[:80]}")
    scroll_y = await _scroll_para_area_esperada(page, coords_relativas)

    # ── 0. Cache semântico ──────────────────────────────────
    cache = _consultar_cache(intencao)
    if cache:
        if cache.seletor:
            cand_cache = TentativaLocalizacao(seletor=cache.seletor, iframe_hint=cache.iframe_src or iframe_hint, descricao="cache semântico")
            if await _tentar_candidato(page, cand_cache, acao, valor):
                _registrar_sucesso_cache(intencao)
                return True
            else:
                _registrar_falha_cache(intencao)
        elif cache.coords:
            if await _clicar_por_coordenadas(page, cache.coords, acao, valor):
                _registrar_sucesso_cache(intencao)
                return True

    # ── 1. Foco Nativo e Fallback de "Nova pasta" (VEM PRIMEIRO) ──
    if acao in ("digitar_e_enter", "preencher_campo"):
        logger.info("   ⌨️  [Foco Nativo] Verificando se o cursor já está posicionado...")
        if await _digitar_no_active_element(page, acao, valor):
            logger.info("   ✅ [Foco Nativo] Texto inserido direto no cursor!")
            return True
            
        logger.info("   ⌨️  [Foco Nativo] Buscando div contenteditable genérica (Nova pasta)...")
        contexto = await _resolver_contexto(page, iframe_hint)
        # O truque que você usava no seu primeiro script para pegar a Nova pasta
        try:
            loc_edit = contexto.locator("[contenteditable='true']")
            if await loc_edit.count() > 0 and await loc_edit.first.is_visible():
                await _executar_acao(loc_edit.first, page, acao, valor)
                return True
        except Exception: pass

    # ── Gera todos os candidatos do Sniper ────────────────────────────
    candidatos = _gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)

    # ── 2. Sniper semântico ─────────────────────────────────
    logger.info(f"   🔍 [Sniper] {len(candidatos)} candidatos para '{label_curto}'...")
    for cand in candidatos:
        if await _tentar_candidato(page, cand, acao, valor):
            logger.info(f"   ✅ [Sniper] Acerto: {cand.descricao}")
            _registrar_sucesso_cache(intencao, seletor=cand.seletor or cand.descricao, iframe=iframe_hint)
            return True

    # ── 3. Seletor hint original ────────────────────────────
    if seletor_hint and not _e_seletor_fragil(seletor_hint):
        cand_hint = TentativaLocalizacao(seletor=seletor_hint, iframe_hint=iframe_hint, descricao=f"hint original '{seletor_hint[:40]}'")
        if await _tentar_candidato(page, cand_hint, acao, valor):
            logger.info(f"   ✅ [Hint] Seletor original funcionou: {seletor_hint[:60]}")
            _registrar_sucesso_cache(intencao, seletor=seletor_hint, iframe=iframe_hint)
            return True

    # ── 4. Busca em todos os frames ─────────────────────────
    logger.info("   🌐 [Todos os Frames] Procurando o elemento em frames filhos...")
    frame_url = await _buscar_em_todos_os_frames(page, candidatos, acao, valor)
    if frame_url:
        _registrar_sucesso_cache(intencao, iframe=frame_url)
        return True

    # ── 5. Gemini Vision ────────────────────────────────────
    logger.info("   🤖 [Vision] DOM esgotado. Acionando Gemini Visual...")
    try:
        screenshot_atual = await page.screenshot(type="png", full_page=False)
    except Exception as exc:
        logger.warning(f"Screenshot falhou antes do Gemini: {exc}")
        screenshot_atual = None

    if screenshot_atual:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        resultado = await _gemini_localizar_elemento(screenshot_atual, alvo.get("screenshot_referencia"), descricao_visual, intencao, contexto_tela, vp, scroll_y)

        if resultado:
            coords_ia = resultado.get("coordenadas")
            if coords_ia:
                if await _clicar_por_coordenadas(page, coords_ia, acao, valor):
                    logger.info("   ✅ [Vision] Clique por coordenadas da IA bem-sucedido.")
                    _registrar_sucesso_cache(intencao, coords=coords_ia)
                    return True

    # ── 6. Coordenadas relativas da gravação ────────────────
    if coords_relativas and coords_relativas.get("x_pct"):
        logger.info("   📍 [Fallback Final] Coordenadas da gravação original...")
        try:
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            x = int(coords_relativas["x_pct"] * vp["width"])
            y = int(coords_relativas["y_pct"] * vp["height"])
            if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
                logger.info(f"   ✅ [Fallback Final] Clique em ({x}, {y}) executado.")
                return True
        except Exception as exc:
            logger.warning(f"Fallback de coordenadas falhou: {exc}")

    # ── 💀 Falha total ───────────────────────────────────────
    _registrar_falha_cache(intencao)
    logger.error(f"   💀 [FALHA TOTAL] Impossível executar: '{intencao[:70]}'")
    return False
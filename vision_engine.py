import asyncio
import json
import base64
import re
import os
import logging
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)
gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Cache semântico da sessão atual
_cache_sessao = {}

# ==============================================================
# 🔍 UTILITÁRIOS DE SELETOR E CACHE
# ==============================================================
def _e_seletor_fragil(seletor: str) -> bool:
    if not seletor:
        return True
    if seletor.startswith("text=") or "has-text" in seletor:
        return False
    if "[aria-label=" in seletor or "[data-testid=" in seletor:
        return False
    if "[id=" in seletor or "[name=" in seletor or "[placeholder=" in seletor:
        return False
        
    frageis = {
        'h1', 'h2', 'h3', 'h4', 'span', 'div', 'em', 'p', 'li', 
        'ul', 'a', 'button', 'input', 'section', 'article', 'td', 'tr'
    }
    seletor_limpo = seletor.strip().split(':')[0].split('[')[0].split('.')[0]
    return seletor_limpo in frageis

def extrair_valor_atributo(seletor: str, atributo: str) -> str | None:
    match = re.search(rf"{atributo}=['\"]([^'\"]+)['\"]", seletor)
    return match.group(1) if match else None

def gerar_seletores_alternativos(seletor_original: str, label_curto: str, iframe: str | None) -> list[dict]:
    alternativas = []
    
    if label_curto:
        # A MAGIA DO SNIPER: "exact=True" força o Playwright a achar apenas o texto, 
        # ignorando a linha inteira da tabela (evitando clicar no checkbox)
        alternativas.append({
            "seletor": f'text="{label_curto}"', 
            "dentro_do_iframe": iframe, 
            "exact": True
        })
        alternativas.append({
            "seletor": f"[aria-label='{label_curto}']", 
            "dentro_do_iframe": iframe
        })
        
    aria_label = extrair_valor_atributo(seletor_original, "aria-label")
    if aria_label and aria_label != label_curto:
        alternativas.append({
            "seletor": f"[aria-label='{aria_label.lower()}']", 
            "dentro_do_iframe": iframe
        })
    
    testid = extrair_valor_atributo(seletor_original, "data-testid")
    if testid:
        alternativas.append({
            "seletor": f"[data-testid='{testid.replace('-', '_')}']", 
            "dentro_do_iframe": iframe
        })
        
    return alternativas

def _consultar_cache(intencao: str) -> dict | None:
    chave = intencao.strip().lower()[:60]
    entrada = _cache_sessao.get(chave)
    if entrada and entrada.get("hits", 0) >= 1:
        print(f"   ⚡ [Cache] Hit para: '{intencao[:40]}'")
        return entrada
    return None

def _atualizar_cache(intencao: str, seletor: str = None, coords: dict = None, iframe: str = None):
    chave = intencao.strip().lower()[:60]
    existente = _cache_sessao.get(chave, {"hits": 0})
    existente["hits"] = existente.get("hits", 0) + 1
    
    if seletor: 
        existente["seletor"] = seletor
    if coords: 
        existente["coords"] = coords
    if iframe: 
        existente["iframe"] = iframe
        
    _cache_sessao[chave] = existente

# ==============================================================
# 🎬 EXECUÇÃO FÍSICA NO BROWSER
# ==============================================================
async def _executar_acao_no_locator(locator, page, acao: str, valor: str):
    try: 
        await locator.scroll_into_view_if_needed(timeout=3000)
        await locator.hover(timeout=2000)
    except Exception: 
        pass
        
    try:
        await locator.evaluate("el => { el.style.transition='all 0.3s'; el.style.outline='4px solid #009999'; el.style.boxShadow='0 0 25px #009999'; }")
        await asyncio.sleep(1.2)
        await locator.evaluate("el => { el.style.outline=''; el.style.boxShadow=''; }")
    except Exception: 
        pass
    
    if acao == "duplo_clique": 
        await locator.dblclick(timeout=3000)
    elif acao == "digitar_e_enter":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        await page.keyboard.type(valor, delay=50)
        await page.keyboard.press("Enter")
    else: 
        await locator.click(timeout=3000)
        
    await asyncio.sleep(0.5)

async def _tentar_seletor(page, seletor: str, iframe: str | None, acao: str, valor: str, exact: bool = False) -> bool:
    try:
        contexto = page
        if iframe and iframe not in ['Página Principal', 'iframe_cross_origin']:
            contexto = page.frame_locator(f"iframe[name='{iframe}']")
        
        if seletor.startswith("text="):
            texto = seletor.replace("text=", "").replace('"', "").replace("'", "").strip()
            loc = contexto.get_by_text(texto, exact=exact).first
        else:
            loc = contexto.locator(seletor).first
            
        await loc.wait_for(state="visible", timeout=4000)
        await _executar_acao_no_locator(loc, page, acao, valor)
        return True
    except Exception: 
        return False

async def _clicar_por_coordenadas(page, coords: dict, acao: str, valor: str) -> bool:
    try:
        x = int(coords["x"])
        y = int(coords["y"])
        
        script_neon = f"""() => {{ 
            const dot = document.createElement('div'); 
            dot.style.cssText = `position: fixed; left: {x-15}px; top: {y-15}px; width: 30px; height: 30px; border-radius: 50%; background: rgba(0,153,153,0.6); border: 3px solid #009999; z-index: 999999; pointer-events: none;`; 
            document.body.appendChild(dot); 
            setTimeout(() => dot.remove(), 800); 
        }}"""
        await page.evaluate(script_neon)
        await asyncio.sleep(0.4)
        
        if acao == "duplo_clique": 
            await page.mouse.dblclick(x, y)
        else: 
            await page.mouse.click(x, y)
            
        if acao == "digitar_e_enter" and valor:
            await asyncio.sleep(0.3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=50)
            await page.keyboard.press("Enter")
            
        await asyncio.sleep(0.5)
        return True
    except Exception as e:
        logger.warning(f"Erro ao clicar por coordenadas: {e}")
        return False

# ==============================================================
# 👁️ GEMINI VISION — LOCALIZAÇÃO VISUAL
# ==============================================================
async def _gemini_localizar_elemento(screenshot_atual: bytes, screenshot_referencia_b64: str | None, descricao_visual: str, intencao: str, contexto_tela: str) -> dict | None:
    print(f"   👁️  [Gemini Vision] Analisando tela para: '{descricao_visual[:60]}'...")
    contents = []
    
    if screenshot_referencia_b64:
        try:
            ref_bytes = base64.b64decode(screenshot_referencia_b64)
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))
            contents.append("IMAGEM 1 — REFERÊNCIA (Como o botão era na gravação):")
        except Exception: 
            pass
            
    contents.append(types.Part.from_bytes(data=screenshot_atual, mime_type="image/jpeg"))
    contents.append(f"""IMAGEM 2 — TELA ATUAL:
Localize este elemento na tela atual:
- Intenção: {intencao}
- Descrição visual: {descricao_visual}
- Contexto: {contexto_tela}

Retorne um JSON com 'metodo': 'seletor', 'coordenadas' ou 'nao_encontrado'.""")

    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        resultado = json.loads(resposta.text)
        
        if resultado.get("metodo") == "nao_encontrado": 
            print(f"   ⚠️  [Gemini] A IA não encontrou o elemento na tela atual.")
            return None
            
        print(f"   ✅ [Gemini] Recomendação da IA: {resultado.get('metodo')} | Confiança: {resultado.get('confianca', '?')}")
        return resultado
    except Exception as e: 
        logger.error(f"Erro na comunicação com a API de Visão: {e}")
        return None

# ==============================================================
# 🤖 ORQUESTRADOR DE RESOLUÇÃO (O SNIPER)
# ==============================================================
async def encontrar_e_clicar(page, acao_tec: dict) -> bool:
    alvo = acao_tec.get("elemento_alvo", {})
    acao = acao_tec.get("acao", "clique")
    intencao = acao_tec.get("intencao_semantica", "Ação na interface")
    valor = acao_tec.get("valor_input", "")
    label_curto = alvo.get("label_curto", "")
    iframe_hint = alvo.get("iframe_hint")
    seletor_hint = alvo.get("seletor_hint", "")
    descricao_visual = alvo.get("descricao_visual", label_curto)
    contexto_tela = alvo.get("contexto_tela", "")

    print(f"\n   🎯 Executando: {intencao[:70]}")

    # 1. Tentativa no Cache Semântico
    cache = _consultar_cache(intencao)
    if cache and cache.get("seletor"):
        iframe_cache = cache.get("iframe", iframe_hint)
        if await _tentar_seletor(page, cache["seletor"], iframe_cache, acao, valor): 
            return True
        else: 
            _cache_sessao.pop(intencao.strip().lower()[:60], None)

    # 2. O SNIPER SEMÂNTICO (Executa ANTES do seletor genérico para evitar Checkboxes)
    print(f"   🔍 [Sniper] Buscando o texto exato para '{label_curto}'...")
    for alt in gerar_seletores_alternativos(seletor_hint, label_curto, iframe_hint):
        iframe_do_alt = alt.get("dentro_do_iframe", iframe_hint)
        exact_match = alt.get("exact", False)
        
        if await _tentar_seletor(page, alt["seletor"], iframe_do_alt, acao, valor, exact=exact_match):
            _atualizar_cache(intencao, seletor=alt["seletor"], iframe=iframe_do_alt)
            print(f"   ✅ [Sniper] Alvo atingido com precisão: {alt['seletor']}")
            return True

    # 3. Seletor Original (Fallback rápido, ex: botões com IDs seguros)
    if not _e_seletor_fragil(seletor_hint):
        if await _tentar_seletor(page, seletor_hint, iframe_hint, acao, valor):
            _atualizar_cache(intencao, seletor=seletor_hint, iframe=iframe_hint)
            print(f"   ✅ [Hint] Seletor técnico original funcionou: {seletor_hint}")
            return True

    # 4. Visão Multimodal (O Último Recurso)
    print(f"   🤖 [Vision] DOM falhou. Acionando IA Visual para olhar a tela...")
    try: 
        screenshot_atual = await page.screenshot(type="jpeg", quality=60)
    except Exception as e: 
        logger.warning(f"Página fechada ou congelada antes do screenshot: {e}")
        return False

    resultado = await _gemini_localizar_elemento(
        screenshot_atual, 
        alvo.get("screenshot_referencia"), 
        descricao_visual, 
        intencao, 
        contexto_tela
    )
    
    if resultado:
        if resultado.get("metodo") == "seletor" and resultado.get("seletor"):
            if await _tentar_seletor(page, resultado["seletor"], iframe_hint, acao, valor):
                _atualizar_cache(intencao, seletor=resultado["seletor"], iframe=iframe_hint)
                return True
                
        if resultado.get("metodo") == "coordenadas" and resultado.get("coordenadas"):
            if await _clicar_por_coordenadas(page, resultado["coordenadas"], acao, valor):
                _atualizar_cache(intencao, coords=resultado["coordenadas"])
                return True

    print(f"   💀 [FALHA TOTAL] Impossível executar a ação: '{intencao}'")
    return False
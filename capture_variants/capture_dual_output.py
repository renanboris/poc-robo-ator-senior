"""
capture_dual_output.py — Senior Training OS · Motor de Captura (Dual Output)
====================================================
Correcoes aplicadas:
  - Removida a importação cruzada de app.py (Isolamento total do script operário).
  - Try/Except global com flush=True para garantir que o painel leia erros reais.
  - Blindagem contra TargetClosedError (Falso Positivo ao fechar o navegador).
  - [NOVO] Hack Supremo para Checkboxes Angular/PrimeNG (textContent + :has-text).
  - [FIX] limpar_nome centralizado em utils.py (DRY).
"""

import asyncio
import base64
import json
import logging
import os
import sys
import time
import traceback

from dotenv import load_dotenv

# Adiciona o diretório pai ao path para importar módulos da raiz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from google.genai import types
from openai import OpenAI
from pinecone import Pinecone
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from shadow_builder import (
    _montar_evento_shadow,
    _salvar_shadow_jsonl,
    inferir_acao_semantica,
)
from utils import limpar_nome

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Analise semantica Gemini desativada.")

_oa_key = os.getenv("OPENAI_API_KEY")
_openai_client = OpenAI(api_key=_oa_key) if _oa_key else None
if not _openai_client:
    logger.warning("OPENAI_API_KEY ausente. RAG Pinecone desativado.")

OPENAI_EMBED_MODEL = "text-embedding-3-large"
TARGET_DIM         = 3072

cliques_capturados: list = []
shadow_capturado: list = []
_id_acao_global: int    = 0
_lock_id: asyncio.Lock  = None


def _retry_com_backoff(func, max_tentativas=5, delay_inicial=2):
    """
    Executa uma função com retry e backoff exponencial.
    Útil para APIs com rate limit (429) ou indisponibilidade temporária (503).
    """
    for tentativa in range(max_tentativas):
        try:
            return func()
        except Exception as e:
            erro_str = str(e)
            # Erros recuperáveis: 429 (rate limit), 503 (service unavailable)
            if "429" in erro_str or "503" in erro_str or "UNAVAILABLE" in erro_str or "Too Many Requests" in erro_str:
                if tentativa < max_tentativas - 1:
                    delay = delay_inicial * (2 ** tentativa)  # Backoff exponencial
                    logger.warning(f"Gemini API indisponível (tentativa {tentativa + 1}/{max_tentativas}). Aguardando {delay}s...")
                    print(f"⚠️  GEMINI INDISPONÍVEL — Tentativa {tentativa + 1}/{max_tentativas}. Aguardando {delay}s...", flush=True)
                    time.sleep(delay)
                    continue
            # Outros erros ou última tentativa: propaga a exceção
            raise
    raise Exception(f"Falha após {max_tentativas} tentativas com backoff exponencial")


def _chamar_openai_fallback(prompt_sistema: str, prompt_usuario: str, model="gpt-4o") -> dict:
    """
    Fallback para OpenAI quando Gemini falha completamente.
    Usa o mesmo formato de prompt e retorna JSON estruturado.
    """
    if not _openai_client:
        raise Exception("OpenAI não configurado. Impossível usar fallback.")

    logger.info(f"🔄 Usando OpenAI ({model}) como fallback...")
    print(f"🔄 FALLBACK ATIVADO: Usando OpenAI {model} para gerar o roteiro...", flush=True)

    try:
        resposta = _openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        return json.loads(resposta.choices[0].message.content)
    except Exception as e:
        logger.error(f"OpenAI fallback também falhou: {e}")
        raise


def _gerar_embedding_openai(texto: str) -> list[float]:
    resp = _openai_client.embeddings.create(input=texto, model=OPENAI_EMBED_MODEL, dimensions=TARGET_DIM)
    return resp.data[0].embedding

def _buscar_pinecone_sync(objetivo_aula: str) -> str:
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index     = os.getenv("PINECONE_INDEX_NAME")
    if not chave_pinecone or not nome_index or not _openai_client:
        return "Nenhum contexto adicional."
    try:
        pc        = Pinecone(api_key=chave_pinecone)
        index     = pc.Index(nome_index)
        embedding = _gerar_embedding_openai(objetivo_aula)
        resultado = index.query(
            vector=embedding, top_k=3, include_metadata=True,
            namespace=os.getenv("DEFAULT_TENANT_ID", "senior_default"),
        )
        textos = [m["metadata"].get("texto", "") or m["metadata"].get("text", "") for m in resultado.get("matches", []) if "metadata" in m]
        return "\n...\n".join(t for t in textos if t) or "Nenhum contexto."
    except Exception as e:
        logger.warning(f"Aviso Pinecone: {e}")
        return "Nenhum contexto adicional."

async def buscar_contexto_pinecone(objetivo_aula: str) -> str:
    return await asyncio.to_thread(_buscar_pinecone_sync, objetivo_aula)

def _extrair_coordenadas_relativas(posicao_str: str, viewport_w: int, viewport_h: int) -> dict:
    try:
        partes = dict(p.split(":") for p in posicao_str.split(","))
        w  = int(partes["w"]); h  = int(partes["h"])
        cx = int(partes["x"]) + w / 2
        cy = int(partes["y"]) + h / 2
        return {
            "x_pct": round(cx / viewport_w, 4), "y_pct": round(cy / viewport_h, 4),
            "w_pct": round(w / viewport_w, 4),  "h_pct": round(h / viewport_h, 4),
        }
    except Exception:
        return {"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05}

async def _analisar_elemento_com_gemini(screenshot_bytes: bytes, html_snapshot: str, label_capturado: str, coords: dict, acao: str) -> dict:
    fallback = {
        "intencao": f"{acao.capitalize()} em '{label_capturado}'",
        "descricao_visual": f"Elemento '{label_capturado}'",
        "contexto_tela": "Desconhecido", "tipo_elemento": "button", "confianca": "baixa",
    }
    if not gemini_client: return fallback
    prompt = f"""Voce e um analista de UX documentando uma sessao de uso do sistema Senior X.
O usuario realizou a acao '{acao}' no elemento com label: '{label_capturado}'.
HTML do elemento clicado: {html_snapshot[:250]}
Posicao relativa na tela: x={coords.get('x_pct','?')}, y={coords.get('y_pct','?')}

Analise o screenshot e responda com um JSON:
{{
  "intencao": "O QUE o usuario quis fazer, orientado a resultado",
  "descricao_visual": "COMO o elemento aparece na tela",
  "contexto_tela": "Em qual parte do sistema o usuario esta",
  "tipo_elemento": "button | input | menu_item | link | icon | checkbox | tab | folder",
  "confianca": "alta | media | baixa"
}}"""
    try:
        def _chamar_gemini():
            return gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), prompt],
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
            )

        resposta = await asyncio.to_thread(_retry_com_backoff, _chamar_gemini, max_tentativas=3, delay_inicial=1)
        resultado = json.loads(resposta.text)
        resultado.setdefault("intencao", fallback["intencao"])
        resultado.setdefault("descricao_visual", fallback["descricao_visual"])
        resultado.setdefault("contexto_tela", "Desconhecido")
        return resultado
    except Exception as e:
        # Gemini falhou na análise de screenshot — usar fallback básico
        # Não tentamos OpenAI aqui porque análise de imagem requer vision API (mais cara)
        logger.warning(f"⚠️  Gemini vision falhou para elemento '{label_capturado}': {str(e)[:80]}")
        return fallback


async def _injetar_em_contexto(contexto):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;

        if (window === window.top && !document.getElementById('senior-rec-widget')) {
            const recWidget = document.createElement('div');
            recWidget.id = 'senior-rec-widget';
            recWidget.style.cssText = 'position:fixed;bottom:30px;right:30px;background:rgba(15,23,42,0.85);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);border-radius:100px;padding:10px 20px;display:flex;align-items:center;gap:10px;z-index:2147483647;font-family:Segoe UI,sans-serif;box-shadow:0 10px 25px rgba(0,0,0,0.5);pointer-events:none;';
            recWidget.innerHTML = '<div style="width:12px;height:12px;background:#ef4444;border-radius:50%;animation:pulse-red 1.5s infinite;"></div><div style="color:white;font-size:13px;font-weight:bold;letter-spacing:1px;">MAPEAMENTO ATIVO</div>';
            if (!document.getElementById('senior-rec-styles')) {
                const st = document.createElement('style'); st.id = 'senior-rec-styles';
                st.innerHTML = '@keyframes pulse-red{0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(239,68,68,0.7)}70%{transform:scale(1);box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(239,68,68,0)}}';
                document.head.appendChild(st);
            }
            document.documentElement.appendChild(recWidget);
        }

        const getElementName = (el) => {
            // HACK: textContent no lugar de innerText para varrer o DOM invisivel do Angular
            const isCheckbox = el.closest('p-checkbox, mat-checkbox, [type="checkbox"], .ui-chkbox');
            if (isCheckbox) {
                const parentRow = el.closest('tr, item, li, .ui-g, .list-item, .row');
                if (parentRow) {
                    let text = parentRow.textContent || '';
                    text = text.replace(/\\s+/g, ' ').trim();
                    if (text.length > 2) {
                        return `Checkbox de: ${text.substring(0, 40)}`;
                    }
                }
                return 'Caixa de selecao Angular';
            }

            // Itens de menu de contexto (ngx-contextmenu, CDK overlay)
            // O clique pode cair no <em> (ícone) dentro do <a> ou <li> do menu.
            // Sobe para o item do menu e pega o texto visível.
            const menuItem = el.closest('.ngx-contextmenu li, [class*="contextmenu"] li, .cdk-overlay-pane li, .dropdown-menu li');
            if (menuItem) {
                // Pega apenas o texto, ignorando ícones (<em>, <i>, <svg>)
                const textoMenu = Array.from(menuItem.childNodes)
                    .filter(n => n.nodeType === Node.TEXT_NODE || (n.nodeType === Node.ELEMENT_NODE && !['EM','I','SVG','SPAN'].includes(n.tagName)))
                    .map(n => (n.textContent || '').trim())
                    .join(' ').replace(/\\s+/g, ' ').trim();
                if (textoMenu && textoMenu.length > 1) return textoMenu;
                // Fallback: innerText do item inteiro sem ícones
                const textoFull = (menuItem.innerText || menuItem.textContent || '').replace(/\\s+/g, ' ').trim();
                if (textoFull && textoFull.length > 1 && textoFull.length < 60) return textoFull;
            }
            const tag = el.tagName.toLowerCase();
            const isEditable = tag === 'input' || tag === 'textarea' || el.getAttribute('contenteditable') === 'true';
            if (isEditable) {
                // Filtra atributos Angular não resolvidos (name="undefined", placeholder="undefined")
                const clean = (v) => (v && v !== 'undefined' && v !== 'null') ? v : '';
                return clean(el.placeholder) || clean(el.name) || clean(el.title) || 'Campo de entrada';
            }
            const text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 0 && text.length < 100 && text !== 'undefined') return text;
            let cur = el;
            for (let i = 0; i < 6; i++) {
                if (!cur) break;
                if (cur.getAttribute('aria-label')) return cur.getAttribute('aria-label');
                if (cur.getAttribute('title')) return cur.getAttribute('title');
                // Tenta o id como label legível quando contém texto descritivo (ex: menu-item-Senior Flow)
                const elId = cur.getAttribute('id') || '';
                if (elId && !elId.match(/^(ng-|mat-|cdk-|\\d)/) && elId.includes('-') && elId.length < 60) {
                    // Extrai a parte descritiva do id (ex: "menu-item-Senior Flow" → "Senior Flow")
                    const partes = elId.split('-');
                    const descritivo = partes.slice(2).join(' ').trim();
                    if (descritivo && descritivo.length > 2) return descritivo;
                }
                // Tenta texto de filhos diretos (irmãos do ícone dentro do mesmo pai)
                if (i === 0) {
                    const irmaoTexto = Array.from(cur.parentElement?.children || [])
                        .filter(c => c !== cur && c.tagName !== 'I' && c.tagName !== 'SVG')
                        .map(c => (c.innerText || c.textContent || '').trim())
                        .find(t => t && t.length > 1 && t.length < 80);
                    if (irmaoTexto) return irmaoTexto;
                }
                cur = cur.parentElement;
            }
            return tag;
        };

        const getBestSelector = (el) => {
            const customCheckbox = el.closest('p-checkbox, mat-checkbox, [role="checkbox"], .ui-chkbox');
            if (customCheckbox) {
                let tagCheck = customCheckbox.tagName.toLowerCase();
                
                // HACK: Direciona o clique para a caixa visual interna do PrimeNG
                let cliqueInterno = tagCheck;
                if (tagCheck === 'p-checkbox') {
                    cliqueInterno = 'p-checkbox .ui-chkbox-box';
                } else if (tagCheck === 'div' && customCheckbox.classList.contains('ui-chkbox')) {
                    cliqueInterno = '.ui-chkbox .ui-chkbox-box';
                }

                // SELETOR SUPREMO: "Linha que tem este texto" > Checkbox
                const parentRow = customCheckbox.closest('tr, item, li, .ui-g, .list-item, .row');
                if (parentRow) {
                    let text = parentRow.textContent || '';
                    text = text.replace(/\\s+/g, ' ').trim();
                    if (text.length > 2) {
                        const cleanText = text.substring(0, 40).replace(/['"\\\\/]/g, '');
                        let pTag = parentRow.tagName.toLowerCase();
                        if (pTag === 'div' && parentRow.classList.contains('ui-g')) pTag = '.ui-g';
                        return `${pTag}:has-text("${cleanText}") ${cliqueInterno}`;
                    }
                }

                const parentComId = customCheckbox.closest('[id]:not([id*="ng-"]):not([id*="mat-"])');
                if (parentComId && parentComId.id) {
                    return `${parentComId.tagName.toLowerCase()}#${parentComId.id} ${cliqueInterno}`;
                }
            }

            let cur = el;
            for (let i = 0; i < 5; i++) {
                if (!cur) break;
                const tid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
                if (tid) return `[data-testid='${tid}']`;
                const aria = cur.getAttribute('aria-label');
                if (aria) return `[aria-label='${aria}']`;
                const name = cur.getAttribute('name');
                if (name && name.length < 40) return `[name='${name}']`;
                if (cur.id && !cur.id.match(/^[\\d\\-_]/) && !cur.id.match(/ng-|mat-|cdk-/)) return `[id='${cur.id}']`;
                cur = cur.parentElement;
            }
            const ph = el.getAttribute('placeholder');
            if (ph) return `[placeholder='${ph}']`;
            const role = el.getAttribute('role');
            if (role && role !== 'presentation') {
                const t = el.innerText?.trim().replace(/\\n/g, ' ') || '';
                if (t && t.length < 50) return `[role='${role}']:has-text('${t}')`;
            }
            const txt = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (txt && txt.length > 1 && txt.length < 50) return `text="${txt}"`;
            const parentAria = el.closest('[aria-label]')?.getAttribute('aria-label');
            if (parentAria) return `[aria-label='${parentAria}'] ${el.tagName.toLowerCase()}`;
            const siblings = Array.from(el.parentElement?.children || []);
            return `${el.tagName.toLowerCase()}:nth-child(${siblings.indexOf(el) + 1})`;
        };

        const getFrameId = () => {
            if (window.name) return window.name;
            try {
                const href = window.location.href;
                if (href && href !== window.top?.location?.href) return href.split('/').pop().split('?')[0] || 'iframe';
            } catch(e) {}
            return 'Pagina Principal';
        };

        const getRectComFallback = (el) => {
            // Elementos Angular da sidebar (position:fixed, ng-star-inserted) podem retornar
            // rect zerado se ainda estao em transicao de layout. Sobe na arvore ate achar
            // um ancestral com dimensoes validas, ou usa o centro da viewport como ultimo recurso.
            let cur = el;
            for (let i = 0; i < 6; i++) {
                if (!cur) break;
                const r = cur.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return r;
                cur = cur.parentElement;
            }
            // Fallback: centro da viewport (melhor que zero para o cursor_engine)
            return { x: window.innerWidth / 2, y: window.innerHeight / 2, width: 40, height: 20 };
        };

        const processarEvento = (target, acao, valor = '') => {
            const rect = getRectComFallback(target);
            window.capturarElemento(JSON.stringify({
                tag: target.tagName.toLowerCase(),
                texto_encontrado: valor || getElementName(target),
                seletor: getBestSelector(target),
                iframe: getFrameId(), acao,
                posicao_visual: `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`,
                html_snapshot: target.outerHTML.substring(0, 300)
            }));
            const orig = target.style.outline;
            target.style.outline = '2px solid red';
            setTimeout(() => target.style.outline = orig, 200);
        };

        let clickTimeout = null;
        document.addEventListener('mousedown', (e) => {
            if (e.button === 2) { processarEvento(e.target, 'clique_direito'); return; }
            if (e.button === 0) {
                if (clickTimeout !== null) { clearTimeout(clickTimeout); clickTimeout = null; return; }
                clickTimeout = setTimeout(() => { processarEvento(e.target, 'clique'); clickTimeout = null; }, 250);
            }
        }, true);
        document.addEventListener('dblclick', (e) => {
            clearTimeout(clickTimeout); clickTimeout = null;
            processarEvento(e.target, 'duplo_clique');
        }, true);
        let ultimoEnterTarget = null, ultimoEnterTime = 0;
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                ultimoEnterTarget = e.target; ultimoEnterTime = Date.now();
                processarEvento(e.target, 'digitar_e_enter', e.target.value || e.target.innerText || '');
            }
        }, true);
        document.addEventListener('blur', (e) => {
            const tag = e.target.tagName.toLowerCase();
            const tipo = (e.target.getAttribute('type') || '').toLowerCase();
            // Ignora checkboxes e radios — nunca geram preencher_campo
            // Ignora valores "undefined"/"null" que vazam de inputs ocultos do PrimeNG/Angular
            if (tipo === 'checkbox' || tipo === 'radio') return;
            const val = e.target.value || '';
            if (!val.trim() || val === 'undefined' || val === 'null') return;
            if (e.target === ultimoEnterTarget && Date.now() - ultimoEnterTime < 500) return;
            if ((tag === 'input' || tag === 'textarea' || e.target.isContentEditable) && e.target.value) {
                processarEvento(e.target, 'preencher_campo', e.target.value);
            }
        }, true);
    }"""
    try:
        await contexto.evaluate(script_radar)
    except PlaywrightError as e:
        if "Target closed" not in str(e) and "browser has been closed" not in str(e):
            pass
    except Exception:
        pass

async def injetar_radar_event_driven(page):
    await _injetar_em_contexto(page)
    async def injetar_com_delay(frame):
        try:
            await asyncio.sleep(0.5)
            await _injetar_em_contexto(frame)
        except Exception:
            pass
    page.on("frameattached",  lambda frame: asyncio.create_task(injetar_com_delay(frame)))
    page.on("framenavigated", lambda frame: asyncio.create_task(injetar_com_delay(frame)))

async def on_capturar_elemento(source, args):
    global _id_acao_global, _lock_id
    async with _lock_id:
        _id_acao_global += 1
        meu_id_acao = _id_acao_global

    try:
        dados_json = await args.json_value()
        dados      = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        acao       = dados.get("acao", "clique")
        label      = (dados["texto_encontrado"] or dados["tag"])[:40]
        logger.info(f"[FOTO {meu_id_acao}] | {acao.upper()} | {label}")

        screenshot_bytes = screenshot_b64 = None
        vp_w, vp_h = 1920, 1080
        page_ref = None
        page_title = ""
        page_url = ""

        try:
            frame = source.get("frame")
            if frame:
                page_ref         = frame.page
                screenshot_bytes = await page_ref.screenshot(type="jpeg", quality=80, full_page=False)
                screenshot_b64   = base64.b64encode(screenshot_bytes).decode("utf-8")
                vp               = await page_ref.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                vp_w, vp_h       = vp["w"], vp["h"]
                try:
                    page_title = await page_ref.title()
                except Exception:
                    page_title = ""
                try:
                    page_url = page_ref.url
                except Exception:
                    page_url = ""
        except PlaywrightError as e:
            if "Target closed" in str(e) or "browser has been closed" in str(e):
                return
            logger.warning(f"Falha ao tirar print: {e}")
        except Exception as e:
            logger.warning(f"Falha ao tirar print: {e}")

        coords  = _extrair_coordenadas_relativas(dados.get("posicao_visual", ""), vp_w, vp_h)
        # Aviso quando coordenadas ainda são padrão após fallback no JS
        if coords.get("x_pct") == 0.5 and coords.get("y_pct") == 0.5:
            logger.warning(f"[FOTO {meu_id_acao}] Coordenadas padrão (0.5/0.5) — fallback de viewport usado para '{label}'.")

        # ── Evento_Bruto: apenas dados mecânicos, sem chamada Gemini ─────────
        # O enriquecimento semântico (Gemini Vision) ocorre APÓS o encerramento
        # da sessão, via enriquecer_eventos_com_gemini(). Isso garante que a
        # captura não seja bloqueada por latência ou falha da API.
        iframe_id = dados.get("iframe", "Pagina Principal")
        valor_input = dados["texto_encontrado"] if acao in ["digitar_e_enter", "preencher_campo"] else ""

        # ── Flag de item de menu de contexto ─────────────────────────────────
        # Se a ação anterior foi clique_direito, este clique é um item do menu
        # de contexto que foi aberto. Marca para que o executor saiba buscar
        # dentro do overlay do menu em vez de varrer o DOM geral.
        _ultima_acao = cliques_capturados[-1].get("acao", "") if cliques_capturados else ""
        _is_context_menu_item = (acao == "clique" and _ultima_acao == "clique_direito")

        evento_base = {
            "id_acao":            meu_id_acao,
            "acao":               acao,
            "intencao_semantica": "",          # preenchido em enriquecer_eventos_com_gemini()
            "semantic_action":    "",          # preenchido em enriquecer_eventos_com_gemini()
            "is_context_menu_item": _is_context_menu_item,  # flag para o executor
            "elemento_alvo": {
                "descricao_visual":      "",   # preenchido em enriquecer_eventos_com_gemini()
                "contexto_tela":         "",   # preenchido em enriquecer_eventos_com_gemini()
                "tipo_elemento":         dados.get("tag", "button"),
                "confianca_captura":     "media",  # padrão antes do enriquecimento
                "label_curto":           label,
                "coordenadas_relativas": coords,
                "seletor_hint":          dados["seletor"],
                "iframe_hint":           iframe_id if iframe_id != "Pagina Principal" else None,
                "html_hint":             dados.get("html_snapshot", "")[:300],
                "screenshot_referencia": screenshot_b64,
            },
            "valor_input": valor_input,
            # Metadados de contexto para enriquecimento posterior
            "_page_title":  page_title,
            "_page_url":    page_url,
            "_vp_w":        vp_w,
            "_vp_h":        vp_h,
            "_dados_brutos": dados,
        }
        cliques_capturados.append(evento_base)
    except Exception as e:
        logger.error(f"Erro ao processar captura: {e}")

async def enriquecer_eventos_com_gemini(eventos_brutos: list[dict]) -> list[dict]:
    """
    Recebe lista de Evento_Bruto e retorna lista de Evento_Enriquecido.

    Opção C: enriquecimento seletivo + paralelização em lotes.

    - Eventos com label descritivo suficiente usam fallback heurístico direto
      (sem chamar Gemini) — economiza chamadas para eventos óbvios.
    - Eventos com label genérico ou ambíguo são enviados ao Gemini em lotes
      paralelos de até LOTE_GEMINI eventos simultâneos.
    - Nunca lança exceção.
    """
    if not eventos_brutos:
        return []

    # Labels que dispensam Gemini — o fallback heurístico já produz boa qualidade
    _LABELS_DESCRITIVOS_SUFICIENTES = {
        "nova pasta", "novo envelope", "excluir", "confirmar", "cancelar",
        "salvar", "enviar", "fechar", "abrir", "selecionar", "incluir",
        "upload", "download", "pesquisar", "buscar", "filtrar", "exportar",
        "importar", "editar", "renomear", "mover", "copiar", "compartilhar",
        "favoritar", "permissões", "assinar", "tirar foto", "reconhecimento facial",
        "novo", "criar", "adicionar", "remover", "atualizar", "voltar",
        "próximo", "anterior", "sim", "não", "ok", "aplicar",
    }

    # Tags que sempre precisam de Gemini — sem label semântico próprio
    _TAGS_PRECISAM_GEMINI = {"span", "i", "a", "div", "em", "svg", "path", "button"}

    LOTE_GEMINI = 8  # máximo de chamadas paralelas (dentro do rate limit da API)

    def _precisa_gemini(evento: dict) -> bool:
        """Decide se o evento precisa de análise Gemini ou se o fallback é suficiente."""
        if not gemini_client:
            return False
        alvo  = evento.get("elemento_alvo", {})
        label = (alvo.get("label_curto", "") or "").strip().lower()
        tag   = (alvo.get("tipo_elemento", "") or "").strip().lower()
        acao  = evento.get("acao", "")

        # Sem screenshot — Gemini não consegue analisar de qualquer forma
        if not alvo.get("screenshot_referencia"):
            return False
        # Label genérico (tag HTML) — Gemini é necessário para entender o contexto
        if label in _TAGS_PRECISAM_GEMINI or not label or len(label) <= 1:
            return True
        # Label começa com "checkbox de:" — já tem contexto suficiente
        if label.startswith("checkbox de:"):
            return False
        # Label descritivo conhecido — fallback heurístico é suficiente
        if any(label.startswith(d) or label == d for d in _LABELS_DESCRITIVOS_SUFICIENTES):
            return False
        # Ações de digitação com valor — fallback é suficiente
        if acao in ("preencher_campo", "digitar_e_enter") and evento.get("valor_input"):
            return False
        # Default: usa Gemini para labels desconhecidos
        return True

    def _fallback_heuristico(evento: dict) -> dict:
        """Gera análise heurística sem chamar Gemini."""
        alvo        = evento.get("elemento_alvo", {})
        label       = alvo.get("label_curto", "")
        acao        = evento.get("acao", "clique")
        valor_input = evento.get("valor_input", "")
        acao_sem = inferir_acao_semantica(
            acao, label,
            alvo.get("seletor_hint", ""),
            alvo.get("tipo_elemento", ""),
            valor_input,
        )
        return {
            "intencao":         f"{acao_sem.capitalize()} em '{label}'",
            "descricao_visual": f"Elemento '{label}'",
            "contexto_tela":    evento.get("_page_title", "Desconhecido") or "Desconhecido",
            "tipo_elemento":    alvo.get("tipo_elemento", "button"),
            "confianca":        "media",
        }

    async def _enriquecer_um(evento: dict) -> dict:
        """Enriquece um único evento — Gemini ou fallback conforme critério."""
        alvo    = evento.get("elemento_alvo", {})
        label   = alvo.get("label_curto", "")
        acao    = evento.get("acao", "clique")
        id_acao = evento.get("id_acao", "?")

        analise = None
        if _precisa_gemini(evento):
            screenshot_b64   = alvo.get("screenshot_referencia")
            screenshot_bytes = base64.b64decode(screenshot_b64) if screenshot_b64 else None
            try:
                analise = await _analisar_elemento_com_gemini(
                    screenshot_bytes,
                    alvo.get("html_hint", ""),
                    label,
                    alvo.get("coordenadas_relativas", {}),
                    acao,
                )
            except Exception as e:
                logger.warning(f"[Enriquecimento] Gemini falhou para id_acao={id_acao}: {str(e)[:80]}")

        if analise is None:
            analise = _fallback_heuristico(evento)

        evento_enriquecido = dict(evento)
        evento_enriquecido["intencao_semantica"] = analise["intencao"]
        evento_enriquecido["elemento_alvo"] = dict(alvo)
        evento_enriquecido["elemento_alvo"]["descricao_visual"]  = analise["descricao_visual"]
        evento_enriquecido["elemento_alvo"]["contexto_tela"]     = analise["contexto_tela"]
        evento_enriquecido["elemento_alvo"]["tipo_elemento"]     = analise.get("tipo_elemento", "button")
        evento_enriquecido["elemento_alvo"]["confianca_captura"] = analise.get("confianca", "media")
        return evento_enriquecido

    # Processa em lotes paralelos preservando a ordem original
    eventos_enriquecidos = [None] * len(eventos_brutos)
    gemini_count = sum(1 for e in eventos_brutos if _precisa_gemini(e))
    fallback_count = len(eventos_brutos) - gemini_count
    print(f"[Enriquecimento] {len(eventos_brutos)} eventos: {gemini_count} via Gemini, {fallback_count} via fallback heurístico", flush=True)

    for inicio in range(0, len(eventos_brutos), LOTE_GEMINI):
        lote = eventos_brutos[inicio:inicio + LOTE_GEMINI]
        resultados = await asyncio.gather(*[_enriquecer_um(e) for e in lote])
        for j, resultado in enumerate(resultados):
            eventos_enriquecidos[inicio + j] = resultado

    if not gemini_client or gemini_count == 0:
        print(f"CAPTURA_SEM_GEMINI:{len(eventos_brutos)}", flush=True)

    return eventos_enriquecidos



async def capturar_cliques_na_tela():
    global _lock_id, _id_acao_global
    _lock_id = asyncio.Lock()
    _id_acao_global = 0
    cliques_capturados.clear()
    shadow_capturado.clear()

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER_CAPTURE")
    senha      = os.getenv("SENIOR_PASS_CAPTURE")

    if not usuario or not senha:
        print("ERRO FATAL: Credenciais de captura ausentes no .env (SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE).", flush=True)
        return

    async with async_playwright() as p:
        # ── Detecta monitor auxiliar para abrir captura em fullHD ────────────
        _window_x, _window_y = 0, 0
        try:
            from screeninfo import get_monitors
            monitor_aux = next((m for m in get_monitors() if not m.is_primary), None)
            if monitor_aux:
                _window_x = monitor_aux.x
                _window_y = monitor_aux.y
        except Exception:
            pass

        browser = await p.chromium.launch(headless=False, args=[
            "--start-maximized",
            f"--window-position={_window_x},{_window_y}",
        ])
        context = await browser.new_context(no_viewport=True)
        page    = await context.new_page()

        await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)
        logger.info("Abrindo Senior X para Mapeamento...")
        print("A iniciar o navegador e a tentar login...", flush=True)

        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")

            campo_usr = page.locator("input[type='text'], input[type='email'], [placeholder*='usuario']").first
            await campo_usr.wait_for(state="visible", timeout=10000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.5)

            try:
                await page.locator("button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')").first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")

            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            print("Login efetuado. A aguardar carregamento do painel...", flush=True)
            await page.wait_for_load_state("load", timeout=30_000)
            await asyncio.sleep(2.0)

        except Exception as e:
            logger.warning(f"O auto-login falhou/travou: {e}")
            print("AVISO: O robô não conseguiu fazer o login automático. Por favor, conclua o login manualmente na janela do Chrome!", flush=True)
            try:
                await page.wait_for_load_state("networkidle", timeout=60000)
                await asyncio.sleep(3.0)
            except Exception:
                print("ERRO FATAL: Tempo esgotado para login manual.", flush=True)
                await browser.close()
                return

        await injetar_radar_event_driven(page)

        try:
            await page.evaluate("""() => {
                if (document.getElementById('aura-rec-toast')) return;
                const style = document.createElement('style');
                style.innerHTML = `
                    @keyframes _aura_slide_in  { from { opacity:0; transform:translateX(-50%) translateY(-24px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }
                    @keyframes _aura_slide_out { from { opacity:1; transform:translateX(-50%) translateY(0); } to { opacity:0; transform:translateX(-50%) translateY(-16px); } }
                    @keyframes _aura_rec_pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.55;transform:scale(.88)} }
                `;
                document.head.appendChild(style);

                const d = document.createElement('div');
                d.id = 'aura-rec-toast';
                d.innerHTML = `
                    <div style="display:flex;align-items:center;gap:10px;">
                        <span style="width:9px;height:9px;border-radius:50%;background:#ef4444;flex-shrink:0;animation:_aura_rec_pulse 1.4s ease infinite;box-shadow:0 0 0 3px rgba(239,68,68,.25);"></span>
                        <div>
                            <div style="font-size:12px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:#f1f5f9;">Mapeamento ativo</div>
                            <div style="font-size:11px;color:#94a3b8;margin-top:1px;">Clique de forma calma e firme</div>
                        </div>
                    </div>`;
                d.style.cssText = `
                    position:fixed;top:20px;left:50%;transform:translateX(-50%);
                    background:rgba(15,23,42,.92);
                    backdrop-filter:blur(16px) saturate(180%);
                    -webkit-backdrop-filter:blur(16px) saturate(180%);
                    border:1px solid rgba(255,255,255,.1);
                    border-radius:100px;
                    padding:10px 20px;
                    z-index:2147483647;
                    pointer-events:none;
                    box-shadow:0 8px 32px rgba(0,0,0,.45),0 0 0 1px rgba(255,255,255,.04);
                    animation:_aura_slide_in .4s cubic-bezier(.16,1,.3,1) both;
                    font-family:'Segoe UI',system-ui,sans-serif;
                `;
                document.documentElement.appendChild(d);
                setTimeout(() => { d.style.animation='_aura_slide_out .4s ease forwards'; setTimeout(()=>d.remove(),400); }, 5000);
            }""")
        except Exception:
            pass

        print("CAPTURA DUAL INICIADA! O roteiro oficial segue igual; o shadow semântico será salvo em paralelo. Feche o navegador ao terminar.", flush=True)

        loop_iterations = 0
        max_iterations = 1800  # 1 hora máximo (1800 * 2 segundos)

        try:
            while not page.is_closed() and loop_iterations < max_iterations:
                await asyncio.sleep(2)
                loop_iterations += 1

                # Log de progresso a cada 5 minutos
                if loop_iterations % 150 == 0:
                    print(f"[DEBUG] Captura ativa há {loop_iterations * 2 // 60} minutos. {len(cliques_capturados)} ações capturadas.", flush=True)

                try:
                    if page.is_closed():
                        print("[DEBUG] Navegador fechado detectado.", flush=True)
                        break
                    if not await page.evaluate("() => !!window.__radarInjetado"):
                        await _injetar_em_contexto(page)
                except PlaywrightError as e:
                    if "Target closed" in str(e) or "browser has been closed" in str(e):
                        print("[DEBUG] Playwright detectou fechamento do navegador.", flush=True)
                        break
                except Exception as ex:
                    print(f"[DEBUG] Exceção no loop de captura: {ex}", flush=True)
                    break

            if loop_iterations >= max_iterations:
                print("[AVISO] Timeout de 1 hora atingido. Finalizando captura.", flush=True)

        except Exception as e:
            print(f"[DEBUG] Exceção externa no loop: {e}", flush=True)
        finally:
            print(f"[DEBUG] Finalizando captura. Total de ações: {len(cliques_capturados)}", flush=True)
            try:
                await browser.close()
            except Exception:
                pass

def _validar_roteiro(roteiro: dict) -> tuple[bool, str]:
    """
    Portao de qualidade: verifica se o roteiro gerado tem estrutura minima valida
    antes de permitir que o auto-rebuild aconteca.
    
    Retorna (aprovado: bool, motivo: str).
    Criterios minimos:
      - Tem campo 'passos' com pelo menos 2 passos (1 real + 1 conclusao)
      - Pelo menos 50% dos passos tem acoes_tecnicas com seletor_hint preenchido
      - Menos de 70% das acoes com confianca='baixa' (indicativo de captura ruim)
    """
    passos = roteiro.get("passos", [])
    if len(passos) < 2:
        return False, f"Apenas {len(passos)} passo(s) gerado(s) — mapeamento insuficiente."

    total_acoes = 0
    acoes_com_seletor = 0
    acoes_baixa_confianca = 0

    for passo in passos:
        for acao in passo.get("acoes_tecnicas", []):
            if acao.get("acao") == "concluir_video":
                continue
            total_acoes += 1
            alvo = acao.get("elemento_alvo", {})
            if alvo.get("seletor_hint", "").strip():
                acoes_com_seletor += 1
            if alvo.get("confianca_captura") == "baixa":
                acoes_baixa_confianca += 1

    if total_acoes == 0:
        return False, "Nenhuma acao tecnica valida encontrada no roteiro."

    pct_seletor       = acoes_com_seletor / total_acoes
    pct_baixa_conf    = acoes_baixa_confianca / total_acoes

    if pct_seletor < 0.50:
        return False, (
            f"Apenas {pct_seletor:.0%} das acoes tem seletor — "
            "roteiro pode nao reproduzir corretamente."
        )
    if pct_baixa_conf > 0.70:
        return False, (
            f"{pct_baixa_conf:.0%} das acoes tem confianca baixa — "
            "qualidade do mapeamento insuficiente para indexar."
        )

    return True, (
        f"OK — {len(passos)} passos, {total_acoes} acoes, "
        f"{pct_seletor:.0%} com seletor, {pct_baixa_conf:.0%} baixa confianca."
    )


def _invocar_aura_sync(nome_aula: str, objetivo_aula: str, log_mapeador: list, contexto_rag: str):
    if not gemini_client:
        logger.error("Gemini nao configurado. Impossivel gerar roteiro.")
        return None

    logger.info("Acordando a Aura (Processamento Semantico)...")
    PROMPT_FALLBACK = (
        "Voce e a Aura, especialista em treinamento. Transforme o log em passos JSON. "
        "O JSON precisa ter: metadata, passos(id_passo, tipo_passo, pedagogia(ancora, tooltip_dap), "
        "is_conclusao, acoes_tecnicas, micro_narracoes). "
        "DENTRO DE acoes_tecnicas repasse EXATAMENTE os blocos de acao, intencao_semantica, "
        "elemento_alvo e valor_input do log original."
    )
    try:
        with open("aura_prompt.txt", "r", encoding="utf-8") as f:
            prompt_sistema = f.read()
    except FileNotFoundError:
        prompt_sistema = PROMPT_FALLBACK

    lista_para_ia = []
    for a in log_mapeador:
        alvo_sem_foto = {k: v for k, v in a["elemento_alvo"].items() if k != "screenshot_referencia"}
        lista_para_ia.append({
            "id_acao": a["id_acao"], "acao": a["acao"],
            "intencao_semantica": a["intencao_semantica"],
            "elemento_alvo_resumido": alvo_sem_foto, "valor_input": a["valor_input"],
        })

    prompt_usuario = (
        f"AULA: {nome_aula}\nOBJETIVO: {objetivo_aula}\n"
        f"CONTEXTO MANUAL: {contexto_rag}\n"
        f"ACOES CAPTURADAS:\n{json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}"
    )

    try:
        def _chamar_aura():
            return gemini_client.models.generate_content(
                model="gemini-2.5-flash", contents=prompt_usuario,
                config=types.GenerateContentConfig(
                    system_instruction=prompt_sistema,
                    response_mime_type="application/json", temperature=0.2,
                ),
            )

        logger.info("Chamando Gemini para gerar roteiro (com retry automático se necessário)...")
        resposta = _retry_com_backoff(_chamar_aura, max_tentativas=5, delay_inicial=3)
        dados_da_ia = json.loads(resposta.text)
        print("✅ Roteiro gerado com sucesso usando Gemini.", flush=True)
        print("IA_USADA:gemini", flush=True)  # Marcador para o dashboard

    except Exception as e_gemini:
        # Gemini falhou completamente após retries — tentar fallback OpenAI
        logger.error(f"❌ Gemini falhou após todas as tentativas: {e_gemini}")
        print(f"\n❌ GEMINI FALHOU: {str(e_gemini)[:100]}", flush=True)
        print("ALERTA_GEMINI_FALHOU:true", flush=True)  # Marcador para alerta visual

        if not _openai_client:
            print("❌ OpenAI não configurado. Impossível gerar roteiro.", flush=True)
            logger.error("OpenAI não configurado. Impossível usar fallback.")
            return None

        try:
            dados_da_ia = _chamar_openai_fallback(prompt_sistema, prompt_usuario, model="gpt-4o")
            print("✅ Roteiro gerado com sucesso usando OpenAI (fallback).", flush=True)
            print("IA_USADA:openai-fallback", flush=True)  # Marcador para o dashboard
        except Exception as e_openai:
            logger.error(f"❌ OpenAI fallback também falhou: {e_openai}")
            print(f"❌ OPENAI FALLBACK FALHOU: {str(e_openai)[:100]}", flush=True)
            print("\n🚨 FALHA CRÍTICA: Nenhuma IA disponível para gerar o roteiro.", flush=True)
            return None

    try:
        metadata = dados_da_ia.get("metadata", {}); metadata["nome_aula"] = nome_aula
        roteiro_final = {
            "metadata": metadata,
            "configuracao_gravacao": {"gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"},
            "passos": [],
        }
        for passo_ia in dados_da_ia.get("passos", []):
            passo_mesclado = {
                "id_passo":           passo_ia["id_passo"],
                "tipo_passo":         passo_ia.get("tipo_passo", "operacao"),
                "peso_narrativo":     passo_ia.get("peso_narrativo", 2),   # sistema de peso narrativo
                "pause_sugerida":     passo_ia.get("pause_sugerida", 2.5), # pausa em segundos por peso
                "pedagogia":          passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}),
                "alerta_instrutor":   passo_ia.get("alerta_instrutor"),
                "is_conclusao":       passo_ia.get("is_conclusao", False),
                "acoes_tecnicas":     [],
            }
            micro_narracoes = passo_ia.get("micro_narracoes", [])
            for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
                acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
                if acao_bruta:
                    # capture_scope e pattern_detectado vêm do shadow (se disponível),
                    # ficam em _capture_meta para não interferir no executor
                    shadow_ref = next((s for s in shadow_capturado if s.get("id_acao") == id_tec), None)
                    capture_meta = {}
                    if shadow_ref:
                        capture_meta = {
                            "capture_scope":    shadow_ref.get("capture_scope"),
                            "pattern_detectado": shadow_ref.get("pattern_detectado"),
                        }
                    passo_mesclado["acoes_tecnicas"].append({
                        "acao": acao_bruta["acao"], "intencao_semantica": acao_bruta["intencao_semantica"],
                        "elemento_alvo": acao_bruta["elemento_alvo"], "valor_input": acao_bruta["valor_input"],
                        "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else "",
                        "is_context_menu_item": acao_bruta.get("is_context_menu_item", False),
                        "_capture_meta": capture_meta,
                    })
            if passo_mesclado["is_conclusao"]:
                passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})
            roteiro_final["passos"].append(passo_mesclado)

        os.makedirs("roteiros_salvos", exist_ok=True)
        caminho_roteiro = os.path.join("roteiros_salvos", f"{limpar_nome(nome_aula)}.json")
        with open(caminho_roteiro, "w", encoding="utf-8") as f:
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)
        logger.info(f"Roteiro salvo em: {caminho_roteiro}")
        print(f"ROTEIRO_GERADO:{caminho_roteiro}", flush=True)

        # ── PORTÃO DE QUALIDADE + AUTO-REBUILD ───────────────────────────────
        # O roteiro é SEMPRE salvo — o analista pode revisá-lo manualmente.
        # O auto-rebuild só acontece se o roteiro passar no portão de qualidade,
        # evitando que peças ruins contaminem o dicionário da IA.
        aprovado, motivo_validacao = _validar_roteiro(roteiro_final)

        if aprovado:
            logger.info(f"Portão de qualidade: APROVADO — {motivo_validacao}")
            try:
                import threading

                import lego_builder as _lb

                def _rebuild_bg():
                    try:
                        resultado = _lb.construir_biblioteca()
                        if resultado.get("status") == "sucesso":
                            novas = resultado.get("total_acoes_novas", 0)
                            total = resultado.get("total_acoes_lidas", 0)
                            print(
                                f"AUTO-REBUILD: biblioteca atualizada — "
                                f"{total} peças lidas, {novas} novas adicionadas.",
                                flush=True,
                            )
                        else:
                            print(f"AUTO-REBUILD: aviso — {resultado.get('mensagem')}", flush=True)
                    except Exception as e_rb:
                        print(f"AUTO-REBUILD: erro (não crítico) — {e_rb}", flush=True)

                threading.Thread(target=_rebuild_bg, daemon=True, name="lego-rebuild").start()
                logger.info("Auto-rebuild da biblioteca iniciado em background.")
            except Exception as e:
                logger.warning(f"Não foi possível iniciar auto-rebuild: {e}")
        else:
            # Roteiro salvo mas não indexado automaticamente
            print(
                f"\n⚠️  AUTO-REBUILD BLOQUEADO — roteiro salvo mas não indexado.\n"
                f"   Motivo: {motivo_validacao}\n"
                f"   → Revise o roteiro em: {caminho_roteiro}\n"
                f"   → Se ok, clique em 'Atualizar Biblioteca' no Dashboard.",
                flush=True,
            )
            logger.warning(f"Portão de qualidade: REPROVADO — {motivo_validacao}")
        # ─────────────────────────────────────────────────────────────────────

        return caminho_roteiro

    except Exception as e:
        logger.error(f"Erro na mesclagem final do Roteiro: {e}")
        return None

async def orquestrador_pos_captura(nome_aula: str, objetivo: str):
    contexto_rag = await buscar_contexto_pinecone(objetivo)
    return await asyncio.to_thread(_invocar_aura_sync, nome_aula, objetivo, cliques_capturados, contexto_rag)

def iniciar_esteira_de_producao():
    try:
        print("\n" + "=" * 50 + "\nSENIOR SISTEMAS — TRAINING OS · DUAL OUTPUT\n" + "=" * 50, flush=True)

        is_auto = "--auto" in sys.argv

        if is_auto:
            args_posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]
            if len(args_posicionais) < 2:
                print("ERRO FATAL: Modo --auto requer: capture_dual_output.py <nome_aula> <objetivo> --auto", flush=True)
                sys.exit(1)
            nome_aula = args_posicionais[0]
            objetivo  = args_posicionais[1]
            logger.info(f"Iniciado via Dashboard | Aula: {nome_aula}")
        else:
            nome_aula = input("Qual e o nome desta aula? (Ex: Criando Pastas e Subpastas)\n> ")
            objetivo  = input("Qual e o objetivo do treinamento?\n> ")

        print("[DEBUG] Iniciando captura de cliques...", flush=True)
        asyncio.run(capturar_cliques_na_tela())
        print(f"[DEBUG] Captura finalizada. Total de ações: {len(cliques_capturados)}", flush=True)

        if not cliques_capturados:
            print("AVISO: Nenhuma acao capturada. O navegador foi fechado sem interacoes.", flush=True)
            sys.exit(1)

        print("[DEBUG] Salvando shadow JSONL...", flush=True)

        # ── Enriquecimento pós-captura: Gemini Vision roda aqui, não durante a captura ──
        # Isso garante que a sessão de captura não foi bloqueada por latência da API.
        print(f"[DEBUG] Enriquecendo {len(cliques_capturados)} eventos com Gemini Vision...", flush=True)
        eventos_enriquecidos = asyncio.run(enriquecer_eventos_com_gemini(cliques_capturados))

        # Monta shadow a partir dos eventos enriquecidos
        shadow_final = []
        for e in eventos_enriquecidos:
            alvo    = e.get("elemento_alvo", {})
            dados_b = e.get("_dados_brutos", {})
            analise = {
                "intencao":         e.get("intencao_semantica", ""),
                "descricao_visual": alvo.get("descricao_visual", ""),
                "contexto_tela":    alvo.get("contexto_tela", ""),
                "tipo_elemento":    alvo.get("tipo_elemento", "button"),
                "confianca":        alvo.get("confianca_captura", "media"),
            }
            shadow_final.append(
                _montar_evento_shadow(
                    id_acao=e["id_acao"],
                    acao=e["acao"],
                    label=alvo.get("label_curto", ""),
                    dados=dados_b if dados_b else {
                        "seletor": alvo.get("seletor_hint", ""),
                        "tag":     alvo.get("tipo_elemento", "button"),
                        "html_snapshot": alvo.get("html_hint", ""),
                    },
                    analise=analise,
                    iframe_id=alvo.get("iframe_hint"),
                    coords=alvo.get("coordenadas_relativas", {}),
                    screenshot_b64=alvo.get("screenshot_referencia"),
                    page_title=e.get("_page_title", ""),
                    page_url=e.get("_page_url", ""),
                    vp_w=e.get("_vp_w", 1920),
                    vp_h=e.get("_vp_h", 1080),
                    valor_input=e.get("valor_input", ""),
                )
            )

        _salvar_shadow_jsonl(nome_aula, objetivo, shadow_final)

        # ── Atualiza cliques_capturados com os eventos enriquecidos ──────────
        # CRÍTICO: orquestrador_pos_captura usa cliques_capturados para montar
        # o prompt da Aura. Sem esta atualização, intencao_semantica, descricao_visual
        # e contexto_tela chegam vazios ao roteiro, quebrando o Brain na execução.
        cliques_capturados.clear()
        cliques_capturados.extend(eventos_enriquecidos)

        print(f"[DEBUG] {len(cliques_capturados)} acoes capturadas. Processando Roteiro com Aura...", flush=True)
        caminho_roteiro_gerado = asyncio.run(orquestrador_pos_captura(nome_aula, objetivo))
        print(f"[DEBUG] Roteiro gerado: {caminho_roteiro_gerado}", flush=True)

        if caminho_roteiro_gerado:
            if is_auto:
                logger.info("Roteiro gerado! O Dashboard sera atualizado automaticamente.")
            else:
                if input("\nTudo pronto! Iniciar o Motor de Gravacao? (S/N)\n> ").strip().upper() == "S":
                    import subprocess
                    subprocess.run([sys.executable, "main.py", caminho_roteiro_gerado])
    except KeyboardInterrupt:
        print("\n[AVISO] Captura interrompida pelo usuário.", flush=True)
        sys.exit(0)
    except Exception as e:
        print(f"ERRO FATAL DE EXECUCAO: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    iniciar_esteira_de_producao()

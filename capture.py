"""
capture.py — Senior Training OS · Motor de Captura
====================================================
Correcoes aplicadas:
  - Removida a importação cruzada de app.py (Isolamento total do script operário).
  - Try/Except global com flush=True para garantir que o painel leia erros reais.
  - Blindagem contra TargetClosedError (Falso Positivo ao fechar o navegador).
  - [NOVO] Hack Supremo para Checkboxes Angular/PrimeNG (textContent + :has-text).
  - [FIX] limpar_nome e validar_roteiro centralizados em utils.py (DRY).
  - [FIX] Validação de IDs alucinados pelo Gemini em _invocar_aura_sync.
  - [FIX] getRectComFallback no JS injetado para coordenadas Angular.
"""

import asyncio
import base64
import json
import logging
import os
import sys
import traceback

from dotenv import load_dotenv
from google import genai
from google.genai import types
from openai import OpenAI
from pinecone import Pinecone
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from utils import aplicar_blur_screenshot, limpar_nome, safe_write_json, validar_roteiro

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
_id_acao_global: int    = 0
_lock_id: asyncio.Lock  = None
_pending_tasks: set     = set()
_nome_aula_sessao: str  = ""   # definido em iniciar_esteira_de_producao antes de capturar

def _gerar_embedding_openai(texto: str) -> list[float]:
    resp = _openai_client.embeddings.create(input=texto, model=OPENAI_EMBED_MODEL, dimensions=TARGET_DIM)
    return resp.data[0].embedding

def _buscar_pinecone_sync(objetivo_aula: str) -> str:
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index     = os.getenv("PINECONE_INDEX_NAME")
    if not chave_pinecone or not nome_index or not _openai_client:
        return "Nenhum contexto adicional."
    try:
        # NEW: Detecta namespace do objetivo_aula
        from namespace_detector import detectar_namespace

        contexto_deteccao = {"objetivo": objetivo_aula}
        namespace_detectado = detectar_namespace(contexto_deteccao)

        if namespace_detectado:
            namespace_query = namespace_detectado
            logger.info(f"[Namespace] Detectado: {namespace_detectado} (fonte: objetivo_aula)")
        else:
            namespace_query = os.getenv("DEFAULT_TENANT_ID", "senior_default")
            logger.info(f"[Namespace] Não detectado, usando tenant_id: {namespace_query}")

        pc        = Pinecone(api_key=chave_pinecone)
        index     = pc.Index(nome_index)
        embedding = _gerar_embedding_openai(objetivo_aula)
        resultado = index.query(
            vector=embedding, top_k=3, include_metadata=True,
            namespace=namespace_query,  # CHANGED: usa namespace detectado
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

def _extrair_coordenadas_absolutas(posicao_str: str) -> dict | None:
    """Extrai o centro absoluto (x, y) em pixels a partir de posicao_visual.
    Retorna None se a string estiver ausente ou malformada."""
    try:
        partes = dict(p.split(":") for p in posicao_str.split(","))
        cx = int(partes["x"]) + int(partes["w"]) / 2
        cy = int(partes["y"]) + int(partes["h"]) / 2
        return {"x": int(cx), "y": int(cy)}
    except Exception:
        return None

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
  "confianca": "alta (elemento tem data-testid, aria-label ou id semantico unico e estavel) | media (elemento identificavel por texto visivel, name ou placeholder) | baixa (elemento identificado apenas por posicao, indice numerico ou tag generica sem atributo identificador)"
}}"""
    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )
        resultado = json.loads(resposta.text)
        resultado.setdefault("intencao", fallback["intencao"])
        resultado.setdefault("descricao_visual", fallback["descricao_visual"])
        resultado.setdefault("contexto_tela", "Desconhecido")
        return resultado
    except Exception:
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

            const tag = el.tagName.toLowerCase();
            const isEditable = tag === 'input' || tag === 'textarea' || el.getAttribute('contenteditable') === 'true';
            if (isEditable) return el.placeholder || el.name || el.title || 'Campo de entrada';
            const text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 0 && text.length < 100) return text;
            let cur = el;
            for (let i = 0; i < 4; i++) {
                if (!cur) break;
                if (cur.getAttribute('aria-label')) return cur.getAttribute('aria-label');
                if (cur.getAttribute('title')) return cur.getAttribute('title');
                cur = cur.parentElement;
            }
            return tag;
        };

        const getBestSelector = (el) => {
            const customCheckbox = el.closest('p-checkbox, mat-checkbox, [role="checkbox"], .ui-chkbox');
            if (customCheckbox) {
                let tagCheck = customCheckbox.tagName.toLowerCase();
                let cliqueInterno = tagCheck;
                if (tagCheck === 'p-checkbox') {
                    cliqueInterno = 'p-checkbox .ui-chkbox-box';
                } else if (tagCheck === 'div' && customCheckbox.classList.contains('ui-chkbox')) {
                    cliqueInterno = '.ui-chkbox .ui-chkbox-box';
                }

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
            // Elementos Angular (position:fixed, ng-star-inserted) podem retornar
            // rect zerado se ainda estao em transicao de layout. Sobe na arvore
            // ate achar um ancestral com dimensoes validas.
            let cur = el;
            for (let i = 0; i < 5; i++) {
                if (!cur) break;
                const r = cur.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) return r;
                cur = cur.parentElement;
            }
            return el.getBoundingClientRect();
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

        // 🟢 MUDANÇA CRUCIAL: Bloquear o menu nativo do Chrome para ele não estragar a captura
        document.addEventListener('contextmenu', (e) => {
            e.preventDefault();
        }, true);

        let clickTimeout = null;
        let _lastMousedownTarget = null;

        const flushPending = () => {
            if (clickTimeout !== null && _lastMousedownTarget !== null) {
                clearTimeout(clickTimeout);
                clickTimeout = null;
                processarEvento(_lastMousedownTarget, 'clique');
                _lastMousedownTarget = null;
            }
        };

        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'hidden') flushPending();
        });
        window.addEventListener('pagehide', flushPending);

        document.addEventListener('mousedown', (e) => {
            // Se for botão direito (2), processa na hora, sem delays!
            if (e.button === 2) { 
                processarEvento(e.target, 'clique_direito'); 
                return; 
            }
            if (e.button === 0) {
                if (clickTimeout !== null) { clearTimeout(clickTimeout); clickTimeout = null; _lastMousedownTarget = null; return; }
                _lastMousedownTarget = e.target;
                clickTimeout = setTimeout(() => { processarEvento(e.target, 'clique'); clickTimeout = null; _lastMousedownTarget = null; }, 250);
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

async def _detectar_campo_sensivel(page_ref, seletor: str, id_acao: int) -> dict | None:
    """Detecta se o elemento alvo é um campo sensível (password ou BLUR_SELECTORS).

    Retorna dict com dados_blur se sensível, ou None caso contrário.
    Nunca lança exceção — falhas são silenciosas (Req 1.1, 1.4).
    """
    if not page_ref or not seletor:
        return None

    try:
        element_handle = await page_ref.locator(seletor).first.element_handle(timeout=1000)
    except Exception:
        return None

    if element_handle is None:
        return None

    tipo_campo = None

    # Verificar type="password" (Req 1.1)
    try:
        attr_type = await element_handle.get_attribute("type")
        if attr_type and attr_type.lower() == "password":
            tipo_campo = "password"
    except Exception:
        pass

    # Verificar seletores adicionais de BLUR_SELECTORS (Req 1.3)
    if tipo_campo is None:
        blur_selectors_raw = os.getenv("BLUR_SELECTORS", "")
        if blur_selectors_raw:
            for sel_extra in (s.strip() for s in blur_selectors_raw.split(",") if s.strip()):
                try:
                    count = await page_ref.locator(sel_extra).count()
                    if count > 0:
                        # Verificar se o elemento alvo corresponde a este seletor
                        matched = await page_ref.evaluate(
                            """([seletor, seletorExtra]) => {
                                const el = document.querySelector(seletor);
                                if (!el) return false;
                                return el.matches(seletorExtra);
                            }""",
                            [seletor, sel_extra],
                        )
                        if matched:
                            tipo_campo = sel_extra
                            break
                except Exception:
                    continue

    if tipo_campo is None:
        return None

    # Obter bounding box do elemento no viewport (Req 1.1)
    try:
        bbox = await element_handle.bounding_box()
    except Exception:
        bbox = None

    if bbox is None:
        logger.info(f"[BLUR {id_acao}] Campo sensível detectado (tipo={tipo_campo}) mas bounding_box indisponível — blur ignorado.")
        return None

    regiao = {
        "x": int(bbox["x"]),
        "y": int(bbox["y"]),
        "w": int(bbox["width"]),
        "h": int(bbox["height"]),
    }

    logger.info(f"[BLUR {id_acao}] Campo sensível detectado — tipo={tipo_campo} | regiao={regiao}")

    return {"blur": True, "regiao": regiao}


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

        screenshot_bytes = None
        screenshot_ref   = None   # path relativo em disco ou base64 fallback
        page_ref         = None   # referência à página, usada também para screenshot_elemento
        vp_w, vp_h = 1920, 1080

        try:
            frame = source.get("frame")
            if frame:
                page_ref         = frame.page
                screenshot_bytes = await page_ref.screenshot(type="jpeg", quality=80, full_page=False)
                vp               = await page_ref.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                vp_w, vp_h       = vp["w"], vp["h"]
                # Externaliza screenshot para disco; fallback para base64 se falhar
                if screenshot_bytes and _nome_aula_sessao:
                    pasta_screenshots = os.path.join(
                        "audios_gerados", limpar_nome(_nome_aula_sessao), "screenshots"
                    )
                    os.makedirs(pasta_screenshots, exist_ok=True)
                    screenshot_path = os.path.join(pasta_screenshots, f"acao_{meu_id_acao}.jpg")
                    try:
                        with open(screenshot_path, "wb") as f_img:
                            f_img.write(screenshot_bytes)
                        screenshot_ref = screenshot_path
                    except Exception:
                        screenshot_ref = base64.b64encode(screenshot_bytes).decode("utf-8")
                elif screenshot_bytes:
                    screenshot_ref = base64.b64encode(screenshot_bytes).decode("utf-8")
        except PlaywrightError as e:
            if "Target closed" in str(e) or "browser has been closed" in str(e):
                return
            logger.warning(f"Falha ao tirar print: {e}")
        except Exception as e:
            logger.warning(f"Falha ao tirar print: {e}")

        # Captura screenshot do elemento alvo via locator.screenshot() (Req 4.1–4.5)
        screenshot_elemento_ref = None
        if page_ref and _nome_aula_sessao and dados.get("seletor"):
            try:
                locator_elemento = page_ref.locator(dados["seletor"]).first
                elem_bytes = await locator_elemento.screenshot(type="jpeg", quality=85)
                pasta_elem = os.path.join(
                    "audios_gerados", limpar_nome(_nome_aula_sessao), "screenshots"
                )
                os.makedirs(pasta_elem, exist_ok=True)
                elem_path = os.path.join(pasta_elem, f"elemento_acao_{meu_id_acao}.jpg")
                with open(elem_path, "wb") as f_elem:
                    f_elem.write(elem_bytes)
                screenshot_elemento_ref = elem_path
            except Exception as e:
                logger.warning(f"[FOTO {meu_id_acao}] screenshot_elemento falhou: {e}")
                screenshot_elemento_ref = None

        # Detecção de campos sensíveis — Requisito 1.1 e 1.4
        dados_blur = await _detectar_campo_sensivel(
            page_ref, dados.get("seletor", ""), meu_id_acao
        )

        # Aplicar blur no screenshot_referencia se campo sensível detectado (Req 1.1, 1.5)
        if dados_blur and dados_blur.get("blur") and screenshot_ref:
            regiao_blur = dados_blur["regiao"]
            try:
                # Obter base64 do screenshot (seja de arquivo ou já em base64)
                if os.path.isfile(screenshot_ref):
                    with open(screenshot_ref, "rb") as _f:
                        _b64_original = base64.b64encode(_f.read()).decode("utf-8")
                else:
                    _b64_original = screenshot_ref

                _b64_borrado = aplicar_blur_screenshot(_b64_original, [regiao_blur])

                # Persistir de volta no mesmo formato (arquivo ou base64)
                if os.path.isfile(screenshot_ref):
                    _img_bytes = base64.b64decode(_b64_borrado)
                    with open(screenshot_ref, "wb") as _f:
                        _f.write(_img_bytes)
                    # screenshot_ref permanece o mesmo caminho de arquivo
                else:
                    screenshot_ref = _b64_borrado

                logger.info(f"[BLUR {meu_id_acao}] Blur aplicado no screenshot_referencia — regiao={regiao_blur}")
            except Exception as _e:
                logger.warning(f"[BLUR {meu_id_acao}] Falha ao aplicar blur no screenshot_referencia: {_e}")

        coords  = _extrair_coordenadas_relativas(dados.get("posicao_visual", ""), vp_w, vp_h)
        # Aviso quando coordenadas são zero — indica que getBoundingClientRect retornou vazio
        if coords.get("x_pct", 0) == 0.5 and coords.get("y_pct", 0) == 0.5:
            logger.warning(f"[FOTO {meu_id_acao}] Coordenadas padrão (0.5/0.5) — elemento pode ter sido capturado fora da viewport.")

        # Coordenadas absolutas (centro do elemento em pixels)
        coords_absolutas = _extrair_coordenadas_absolutas(dados.get("posicao_visual", ""))

        # Coordenadas relativas simplificadas (apenas x_pct / y_pct) para uso no playback
        if vp_w > 0 and vp_h > 0 and coords_absolutas is not None:
            coords_relativas_playback = {
                "x_pct": round(coords_absolutas["x"] / vp_w, 4),
                "y_pct": round(coords_absolutas["y"] / vp_h, 4),
            }
        else:
            coords_relativas_playback = None
            logger.warning(f"[FOTO {meu_id_acao}] coordenadas_relativas nao calculadas — viewport indisponivel (vp_w={vp_w}, vp_h={vp_h}).")
        analise = (
            await _analisar_elemento_com_gemini(
                screenshot_bytes, dados.get("html_snapshot", ""), label, coords, acao
            ) if screenshot_bytes else {
                "intencao": f"{acao.capitalize()} em '{label}'",
                "descricao_visual": f"Elemento '{label}'",
                "contexto_tela": "Desconhecido", "tipo_elemento": "button", "confianca": "baixa",
            }
        )

        iframe_id = dados.get("iframe", "Pagina Principal")
        cliques_capturados.append({
            "id_acao":            meu_id_acao,
            "acao":               acao,
            "intencao_semantica": analise["intencao"],
            "elemento_alvo": {
                "descricao_visual":      analise["descricao_visual"],
                "contexto_tela":         analise["contexto_tela"],
                "tipo_elemento":         analise.get("tipo_elemento", "button"),
                "confianca_captura":     analise.get("confianca", "media"),
                "label_curto":           label,
                "coordenadas_absolutas": coords_absolutas,
                "coordenadas_relativas": coords_relativas_playback if coords_relativas_playback is not None else coords,
                "seletor_hint":          dados["seletor"],
                "iframe_hint":           iframe_id if iframe_id != "Pagina Principal" else None,
                "html_hint":             dados.get("html_snapshot", "")[:300],
                "screenshot_referencia": screenshot_ref,
                "screenshot_elemento":   screenshot_elemento_ref,
                "dados_blur":            dados_blur,
            },
            "valor_input": dados["texto_encontrado"] if acao in ["digitar_e_enter", "preencher_campo"] else "",
        })
    except Exception as e:
        logger.error(f"Erro ao processar captura: {e}")

def _track(coro):
    """Wrap a coroutine in a tracked asyncio Task so it can be drained on session close."""
    task = asyncio.ensure_future(coro)
    _pending_tasks.add(task)
    task.add_done_callback(_pending_tasks.discard)
    return task


async def capturar_cliques_na_tela():
    global _lock_id, _pending_tasks
    _lock_id = asyncio.Lock()
    _pending_tasks = set()  # reset stale state from any previous run

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER_CAPTURE")
    senha      = os.getenv("SENIOR_PASS_CAPTURE")

    if not usuario or not senha:
        print("ERRO FATAL: Credenciais de captura ausentes no .env (SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE).", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=[
            "--start-maximized",
            "--disable-features=Translate",
            "--lang=pt-BR",
            "--no-first-run",
            "--no-default-browser-check",
        ])
        context = await browser.new_context(no_viewport=True, locale="pt-BR")
        page    = await context.new_page()

        await context.expose_binding("capturarElemento", lambda source, args: _track(on_capturar_elemento(source, args)), handle=True)
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

        print("GRAVACAO INICIADA! Use o sistema de forma cadenciada. Feche o navegador ao terminar.", flush=True)

        try:
            while not page.is_closed():
                await asyncio.sleep(2)
                try:
                    if page.is_closed():
                        break
                    if not await page.evaluate("() => !!window.__radarInjetado"):
                        await _injetar_em_contexto(page)
                except PlaywrightError as e:
                    if "Target closed" in str(e) or "browser has been closed" in str(e):
                        break
                except Exception:
                    break
        except Exception:
            pass

        # Drain all in-flight on_capturar_elemento tasks before returning,
        # so clicks processed during the last moments of the session are not lost.
        if _pending_tasks:
            logger.info(f"Aguardando {len(_pending_tasks)} tarefa(s) pendente(s) antes de encerrar...")
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
        _pending_tasks.clear()

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
        resposta = gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt_usuario,
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                response_mime_type="application/json", temperature=0.2,
            ),
        )
        dados_da_ia = json.loads(resposta.text)
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
                if acao_bruta is None:
                    logger.warning(
                        f"[Aura] ID alucinado ignorado: id_tec={id_tec!r} não existe no log. "
                        f"Aula: {nome_aula!r}"
                    )
                    continue
                passo_mesclado["acoes_tecnicas"].append({
                    "acao": acao_bruta["acao"], "intencao_semantica": acao_bruta["intencao_semantica"],
                    "elemento_alvo": acao_bruta["elemento_alvo"], "valor_input": acao_bruta["valor_input"],
                    "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else "",
                })
            if passo_mesclado["is_conclusao"]:
                passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})
            roteiro_final["passos"].append(passo_mesclado)

        os.makedirs("roteiros_salvos", exist_ok=True)
        caminho_roteiro = os.path.join("roteiros_salvos", f"{limpar_nome(nome_aula)}.json")
        safe_write_json(caminho_roteiro, roteiro_final)
        logger.info(f"Roteiro salvo em: {caminho_roteiro}")
        # Linha de protocolo lida pelo app.py para identificar o roteiro exato gerado.
        # NÃO altere o prefixo — o app.py depende dele para evitar o glob+mtime.
        print(f"ROTEIRO_GERADO:{caminho_roteiro}", flush=True)

        # ── PORTÃO DE QUALIDADE + AUTO-REBUILD ───────────────────────────────
        # O roteiro é SEMPRE salvo — o analista pode revisá-lo manualmente.
        # O auto-rebuild só acontece se o roteiro passar no portão de qualidade,
        # evitando que peças ruins contaminem o dicionário da IA.
        aprovado, motivo_validacao = validar_roteiro(roteiro_final)

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
        print("\n" + "=" * 50 + "\nSENIOR SISTEMAS — TRAINING OS\n" + "=" * 50, flush=True)

        is_auto = "--auto" in sys.argv

        if is_auto:
            args_posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]
            if len(args_posicionais) < 2:
                print("ERRO FATAL: Modo --auto requer: capture.py <nome_aula> <objetivo> --auto", flush=True)
                sys.exit(1)
            nome_aula = args_posicionais[0]
            objetivo  = args_posicionais[1]
            logger.info(f"Iniciado via Dashboard | Aula: {nome_aula}")
        else:
            nome_aula = input("Qual e o nome desta aula? (Ex: Criando Pastas e Subpastas)\n> ")
            objetivo  = input("Qual e o objetivo do treinamento?\n> ")

        async def _pipeline(nome_aula_inner, objetivo_inner):
            global _nome_aula_sessao
            _nome_aula_sessao = nome_aula_inner  # disponibiliza para on_capturar_elemento
            await capturar_cliques_na_tela()
            if cliques_capturados:
                logger.info(f"{len(cliques_capturados)} acoes capturadas. Processando Roteiro...")
                return await orquestrador_pos_captura(nome_aula_inner, objetivo_inner)
            return None

        caminho_roteiro_gerado = asyncio.run(_pipeline(nome_aula, objetivo))

        if not cliques_capturados:
            print("AVISO: Nenhuma acao capturada. O navegador foi fechado sem interacoes.", flush=True)
            sys.exit(1)

        if caminho_roteiro_gerado:
            if is_auto:
                logger.info("Roteiro gerado! O Dashboard sera atualizado automaticamente.")
            else:
                if input("\nTudo pronto! Iniciar o Motor de Gravacao? (S/N)\n> ").strip().upper() == "S":
                    import subprocess
                    subprocess.run([sys.executable, "main.py", caminho_roteiro_gerado])
    except Exception as e:
        print(f"ERRO FATAL DE EXECUCAO: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    iniciar_esteira_de_producao()

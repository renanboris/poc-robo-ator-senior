"""
capture.py — Senior Training OS · Motor de Captura
====================================================
Correcoes aplicadas:

  [BUG-1] CRITICO — Embedding incompatível com o índice Pinecone
    ANTES: gemini_client.models.embed_content(model="gemini-embedding-001")
    Gemini embedding-001 gera vetores de ~768 dimensões. O índice Pinecone é
    populado por dap_engine.py com OpenAI text-embedding-3-large (3072d).
    Dimensões incompatíveis → erro de dimensão ou, pior, 0 de similaridade.
    AGORA: OpenAI text-embedding-3-large 3072d — mesmo modelo do dap_engine.

  [BUG-2] ALTO — gemini_client sem guard de chave ausente
    ANTES: genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) no nível do módulo
    → crash com AttributeError confuso se GOOGLE_API_KEY não estiver no .env
    AGORA: guard + warning se chave ausente; funções dependentes retornam fallback.

  [BUG-3] MÉDIO — wait_for_load_state sem timeout
    ANTES: await page.wait_for_load_state("load") → hang indefinido se login falhar.
    AGORA: timeout=30_000 ms.

  [BUG-4] MÉDIO — CLI --auto: índices posicionais assumem sys.argv[1/2]
    ANTES: nome_aula = sys.argv[1]; objetivo = sys.argv[2]
    Se o usuário passa "capture.py --auto Nome Objetivo", sys.argv[1] == "--auto"
    e nome_aula == "--auto", objetivo == "Nome".
    AGORA: filtra flags antes de indexar os argumentos posicionais.

  [BUG-5] BAIXO — Browser não fechado em erro crítico de login
    ANTES: return logger.error(...) retorna silenciosamente sem browser.close()
    AGORA: await browser.close() garantido antes de retornar.

  [BUG-6] BAIXO — limpar_nome duplicada (DRY violation)
    Mantida localmente como fallback; tenta importar de app.py primeiro.
"""

import asyncio
import os
import json
import base64
import subprocess
import sys
import logging
import re
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from google import genai
from google.genai import types
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# [BUG-2] FIX: guards de chave — sem crash no import
_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Analise semantica Gemini desativada.")

_oa_key = os.getenv("OPENAI_API_KEY")
_openai_client = OpenAI(api_key=_oa_key) if _oa_key else None
if not _openai_client:
    logger.warning("OPENAI_API_KEY ausente. RAG Pinecone desativado.")

cliques_capturados: list = []
_id_acao_global: int    = 0
_lock_id: asyncio.Lock  = None  # criado dentro do event loop em capturar_cliques_na_tela


# ==============================================================
# [BUG-6] FIX: limpar_nome importada de app.py (DRY)
# ==============================================================
try:
    from app import limpar_nome
except ImportError:
    def limpar_nome(nome: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")


# ==============================================================
# RAG E PINECONE
# [BUG-1] FIX: OpenAI text-embedding-3-large — mesmo modelo de dap_engine
# ==============================================================
OPENAI_EMBED_MODEL = "text-embedding-3-large"
TARGET_DIM         = 3072


def _gerar_embedding_openai(texto: str) -> list[float]:
    """Mesmo modelo e dimensão usados por dap_engine.ingestar_para_pinecone."""
    resp = _openai_client.embeddings.create(
        input=texto, model=OPENAI_EMBED_MODEL, dimensions=TARGET_DIM
    )
    return resp.data[0].embedding


def _buscar_pinecone_sync(objetivo_aula: str) -> str:
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index     = os.getenv("PINECONE_INDEX_NAME")

    if not chave_pinecone or not nome_index:
        return "Nenhum contexto adicional."
    if not _openai_client:
        return "Nenhum contexto adicional (OpenAI nao configurado)."

    logger.info("Consultando o manual da Senior no Pinecone...")
    try:
        pc        = Pinecone(api_key=chave_pinecone)
        index     = pc.Index(nome_index)
        embedding = _gerar_embedding_openai(objetivo_aula)
        resultado = index.query(
            vector=embedding, top_k=3, include_metadata=True,
            namespace=os.getenv("DEFAULT_TENANT_ID", "senior_default"),
        )
        textos = [
            m["metadata"].get("texto", "") or m["metadata"].get("text", "")
            for m in resultado.get("matches", [])
            if "metadata" in m
        ]
        return "\n...\n".join(t for t in textos if t) or "Nenhum contexto."
    except Exception as e:
        logger.warning(f"Aviso Pinecone: {e}")
        return "Nenhum contexto adicional."


async def buscar_contexto_pinecone(objetivo_aula: str) -> str:
    return await asyncio.to_thread(_buscar_pinecone_sync, objetivo_aula)


# ==============================================================
# EXTRACAO E ANALISE SEMANTICA
# ==============================================================
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


async def _analisar_elemento_com_gemini(
    screenshot_bytes: bytes, html_snapshot: str, label_capturado: str, coords: dict, acao: str
) -> dict:
    fallback = {
        "intencao": f"{acao.capitalize()} em '{label_capturado}'",
        "descricao_visual": f"Elemento '{label_capturado}'",
        "contexto_tela": "Desconhecido", "tipo_elemento": "button", "confianca": "baixa",
    }
    if not gemini_client:
        return fallback

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
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1),
        )
        resultado = json.loads(resposta.text)
        resultado.setdefault("intencao",        fallback["intencao"])
        resultado.setdefault("descricao_visual", fallback["descricao_visual"])
        resultado.setdefault("contexto_tela",    "Desconhecido")
        return resultado
    except Exception:
        return fallback


# ==============================================================
# RADAR DE CAPTURA JAVASCRIPT
# ==============================================================
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
            const tag = el.tagName.toLowerCase();
            const isEditable = tag === 'input' || tag === 'textarea' || el.getAttribute('contenteditable') === 'true';
            if (isEditable) return el.placeholder || el.name || el.title || 'Campo de entrada';
            const text = el.innerText?.trim().replace(/\n/g, ' ') || '';
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
            let cur = el;
            for (let i = 0; i < 5; i++) {
                if (!cur) break;
                const tid = cur.getAttribute('data-testid') || cur.getAttribute('data-test');
                if (tid) return `[data-testid='${tid}']`;
                const aria = cur.getAttribute('aria-label');
                if (aria) return `[aria-label='${aria}']`;
                const name = cur.getAttribute('name');
                if (name && name.length < 40) return `[name='${name}']`;
                if (cur.id && !cur.id.match(/^[\d\-_]/) && !cur.id.match(/ng-|mat-|cdk-/)) return `[id='${cur.id}']`;
                cur = cur.parentElement;
            }
            const ph = el.getAttribute('placeholder');
            if (ph) return `[placeholder='${ph}']`;
            const role = el.getAttribute('role');
            if (role && role !== 'presentation') {
                const t = el.innerText?.trim().replace(/\n/g, ' ') || '';
                if (t && t.length < 50) return `[role='${role}']:has-text('${t}')`;
            }
            const txt = el.innerText?.trim().replace(/\n/g, ' ') || '';
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

        const processarEvento = (target, acao, valor = '') => {
            const rect = target.getBoundingClientRect();
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
            if (e.target === ultimoEnterTarget && Date.now() - ultimoEnterTime < 500) return;
            if ((tag === 'input' || tag === 'textarea' || e.target.isContentEditable) && e.target.value) {
                processarEvento(e.target, 'preencher_campo', e.target.value);
            }
        }, true);
    }"""
    try:
        await contexto.evaluate(script_radar)
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


# ==============================================================
# HANDLER DE CAPTURA
# ==============================================================
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

        try:
            frame = source.get("frame")
            if frame:
                page_ref         = frame.page
                screenshot_bytes = await page_ref.screenshot(type="jpeg", quality=80, full_page=False)
                screenshot_b64   = base64.b64encode(screenshot_bytes).decode("utf-8")
                vp               = await page_ref.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                vp_w, vp_h       = vp["w"], vp["h"]
        except Exception as e:
            logger.warning(f"Falha ao tirar print: {e}")

        coords  = _extrair_coordenadas_relativas(dados.get("posicao_visual", ""), vp_w, vp_h)
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
                "coordenadas_relativas": coords,
                "seletor_hint":          dados["seletor"],
                "iframe_hint":           iframe_id if iframe_id != "Pagina Principal" else None,
                "html_hint":             dados.get("html_snapshot", "")[:300],
                "screenshot_referencia": screenshot_b64,
            },
            "valor_input": dados["texto_encontrado"] if acao in ["digitar_e_enter", "preencher_campo"] else "",
        })
    except Exception as e:
        logger.error(f"Erro ao processar captura: {e}")


# ==============================================================
# SESSAO DE GRAVACAO NO BROWSER
# ==============================================================
async def capturar_cliques_na_tela():
    global _lock_id
    _lock_id = asyncio.Lock()  # criado dentro do event loop correto

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER")
    senha      = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        logger.error("Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page    = await context.new_page()

        await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)
        logger.info("Abrindo Senior X para Mapeamento...")

        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0); await page.keyboard.press("Escape")
            await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
            await page.get_by_role("button", name="Proximo").click()
            await asyncio.sleep(0.5); await page.keyboard.press("Escape")
            await page.locator("input[type='password']").fill(senha)
            await asyncio.sleep(0.5); await page.keyboard.press("Enter")
            # [BUG-3] FIX: timeout explicito
            await page.wait_for_load_state("load", timeout=30_000)
            await asyncio.sleep(1.0)
            await injetar_radar_event_driven(page)

            try:
                await page.evaluate("""() => {
                    if (!document.body) return;
                    const d = document.createElement('div');
                    d.innerHTML = 'GRAVACAO INICIADA!<br><span style="font-size:14px;font-weight:normal;">Clique de forma calma e firme.</span>';
                    d.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#e50914;color:white;padding:15px 30px;font-size:22px;font-weight:bold;font-family:sans-serif;z-index:999999;border-radius:8px;pointer-events:none;transition:opacity 1s ease;text-align:center;';
                    document.body.appendChild(d);
                    setTimeout(() => d.style.opacity='0', 4000);
                    setTimeout(() => d.remove(), 5000);
                }""")
            except Exception:
                pass

        except Exception as e:
            # [BUG-5] FIX: fecha o browser antes de retornar
            logger.error(f"Erro critico no login: {e}")
            await browser.close()
            return

        logger.info("GRAVACAO INICIADA! Use o sistema de forma cadenciada. Feche o navegador ao terminar.")
        try:
            while not page.is_closed():
                await asyncio.sleep(2)
                try:
                    if not await page.evaluate("() => !!window.__radarInjetado"):
                        await _injetar_em_contexto(page)
                except Exception:
                    break
        except Exception:
            pass


# ==============================================================
# AURA — PROCESSAMENTO SEMANTICO
# ==============================================================
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
                "id_passo": passo_ia["id_passo"], "tipo_passo": passo_ia.get("tipo_passo", "operacao"),
                "pedagogia": passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}),
                "alerta_instrutor": passo_ia.get("alerta_instrutor"),
                "is_conclusao": passo_ia.get("is_conclusao", False), "acoes_tecnicas": [],
            }
            micro_narracoes = passo_ia.get("micro_narracoes", [])
            for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
                acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
                if acao_bruta:
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
        with open(caminho_roteiro, "w", encoding="utf-8") as f:
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)
        logger.info(f"Roteiro salvo em: {caminho_roteiro}")
        return caminho_roteiro

    except Exception as e:
        logger.error(f"Erro na mesclagem final do Roteiro: {e}")
        return None


async def orquestrador_pos_captura(nome_aula: str, objetivo: str):
    contexto_rag = await buscar_contexto_pinecone(objetivo)
    return await asyncio.to_thread(_invocar_aura_sync, nome_aula, objetivo, cliques_capturados, contexto_rag)


# ==============================================================
# PONTO DE ENTRADA
# ==============================================================
def iniciar_esteira_de_producao():
    print("\n" + "=" * 50 + "\nSENIOR SISTEMAS — TRAINING OS\n" + "=" * 50)

    is_auto = "--auto" in sys.argv

    if is_auto:
        # [BUG-4] FIX: filtra flags antes de indexar posicionais
        args_posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]
        if len(args_posicionais) < 2:
            logger.error("Modo --auto requer: capture.py <nome_aula> <objetivo> --auto")
            sys.exit(1)
        nome_aula = args_posicionais[0]
        objetivo  = args_posicionais[1]
        logger.info(f"Iniciado via Dashboard | Aula: {nome_aula}")
    else:
        nome_aula = input("Qual e o nome desta aula? (Ex: Criando Pastas e Subpastas)\n> ")
        objetivo  = input("Qual e o objetivo do treinamento?\n> ")

    asyncio.run(capturar_cliques_na_tela())

    if not cliques_capturados:
        logger.warning("Nenhuma acao capturada. Encerrando.")
        sys.exit(1)

    logger.info(f"{len(cliques_capturados)} acoes capturadas. Processando Roteiro...")
    caminho_roteiro_gerado = asyncio.run(orquestrador_pos_captura(nome_aula, objetivo))

    if caminho_roteiro_gerado:
        if is_auto:
            logger.info("Roteiro gerado! O Dashboard sera atualizado automaticamente.")
        else:
            if input("\nTudo pronto! Iniciar o Motor de Gravacao? (S/N)\n> ").strip().upper() == "S":
                subprocess.run([sys.executable, "main.py", caminho_roteiro_gerado])


if __name__ == "__main__":
    iniciar_esteira_de_producao()

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
from pinecone import Pinecone

load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
cliques_capturados = []
_id_acao_global = 0
_lock_id = None 

# ==============================================================
# 🛠️ FUNÇÃO DE HIGIENIZAÇÃO GLOBAL (Alinhada com app.py)
# ==============================================================
def limpar_nome(nome: str) -> str:
    """Garante que o nome do JSON gerado seja idêntico ao esperado pelo sistema."""
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

# ==============================================================
# 📚 RAG E PINECONE
# ==============================================================
def _buscar_pinecone_sync(objetivo_aula: str) -> str:
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index = os.getenv("PINECONE_INDEX_NAME")
    if not chave_pinecone or not nome_index: return "Nenhum contexto adicional."
    
    logger.info("📚 Consultando o manual da Senior no Pinecone...")
    try:
        pc = Pinecone(api_key=chave_pinecone)
        index = pc.Index(nome_index)
        embedding_response = gemini_client.models.embed_content(model="gemini-embedding-001", contents=[objetivo_aula])
        resultado = index.query(vector=embedding_response.embeddings[0].values, top_k=3, include_metadata=True)
        textos = [match['metadata'].get('text', '') for match in resultado['matches'] if 'metadata' in match]
        return "\n...\n".join(textos) if textos else "Nenhum contexto."
    except Exception as e:
        logger.warning(f"Aviso Pinecone: {e}")
        return "Nenhum contexto adicional."

async def buscar_contexto_pinecone(objetivo_aula: str) -> str:
    return await asyncio.to_thread(_buscar_pinecone_sync, objetivo_aula)

# ==============================================================
# 📐 EXTRAÇÃO E ANÁLISE SEMÂNTICA DA IA (COM DIMENSÕES REAIS)
# ==============================================================
def _extrair_coordenadas_relativas(posicao_str: str, viewport_w: int, viewport_h: int) -> dict:
    try:
        partes = dict(p.split(':') for p in posicao_str.split(','))
        w = int(partes['w'])
        h = int(partes['h'])
        cx = int(partes['x']) + w / 2
        cy = int(partes['y']) + h / 2
        return {
            "x_pct": round(cx / viewport_w, 4), 
            "y_pct": round(cy / viewport_h, 4),
            "w_pct": round(w / viewport_w, 4),
            "h_pct": round(h / viewport_h, 4)
        }
    except Exception: 
        return {"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05}

async def _analisar_elemento_com_gemini(screenshot_bytes: bytes, html_snapshot: str, label_capturado: str, coords: dict, acao: str) -> dict:
    prompt = f"""Você é um analista de UX documentando uma sessão de uso do sistema Senior X.
O usuário realizou a ação '{acao}' no elemento com label: '{label_capturado}'.
HTML do elemento clicado: {html_snapshot[:250]}
Posição relativa na tela: x={coords.get('x_pct', '?')}, y={coords.get('y_pct', '?')}

Analise o screenshot e responda com um JSON:
{{
  "intencao": "O QUE o usuário quis fazer, orientado a resultado",
  "descricao_visual": "COMO o elemento aparece na tela",
  "contexto_tela": "Em qual parte do sistema o usuário está",
  "tipo_elemento": "button | input | menu_item | link | icon | checkbox | tab | folder",
  "confianca": "alta | media | baixa"
}}"""
    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        resultado = json.loads(resposta.text)
        if not resultado.get("intencao"): resultado["intencao"] = f"{acao.capitalize()} em '{label_capturado}'"
        if not resultado.get("descricao_visual"): resultado["descricao_visual"] = f"Elemento '{label_capturado}'"
        if not resultado.get("contexto_tela"): resultado["contexto_tela"] = "Desconhecido"
        return resultado
    except Exception as e:
        return {"intencao": f"{acao.capitalize()} em '{label_capturado}'", "descricao_visual": f"Elemento '{label_capturado}'", "contexto_tela": "Desconhecido", "tipo_elemento": "button", "confianca": "baixa"}

# ==============================================================
# 🕵️ RADAR DE CAPTURA JAVASCRIPT & UI (REC WIDGET)
# ==============================================================
async def _injetar_em_contexto(contexto):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;
        
        // 🔴 INJEÇÃO DO WIDGET 'REC' (Apenas no frame principal)
        if (window === window.top && !document.getElementById('senior-rec-widget')) {
            const recWidget = document.createElement('div');
            recWidget.id = 'senior-rec-widget';
            recWidget.style = `
                position: fixed; bottom: 30px; right: 30px; 
                background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); 
                border: 1px solid rgba(255,255,255,0.1); border-radius: 100px; 
                padding: 10px 20px; display: flex; align-items: center; gap: 10px; 
                z-index: 2147483647; font-family: 'Segoe UI', sans-serif; 
                box-shadow: 0 10px 25px rgba(0,0,0,0.5); pointer-events: none;
            `;
            recWidget.innerHTML = `
                <div style="width: 12px; height: 12px; background-color: #ef4444; border-radius: 50%; animation: pulse-red 1.5s infinite;"></div>
                <div style="color: white; font-size: 13px; font-weight: bold; letter-spacing: 1px;">MAPEAMENTO ATIVO</div>
            `;
            
            if (!document.getElementById('senior-rec-styles')) {
                const style = document.createElement('style');
                style.id = 'senior-rec-styles';
                style.innerHTML = `@keyframes pulse-red { 
                    0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); } 
                    70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); } 
                    100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); } 
                }`;
                document.head.appendChild(style);
            }
            document.documentElement.appendChild(recWidget);
        }

        const escapeStr = (s) => s ? s.replace(/'/g, "\\'") : '';

        const getElementName = (el) => {
            let isEditable = el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea' || el.getAttribute('contenteditable') === 'true';
            if (isEditable) return el.placeholder || el.name || el.title || 'Campo de entrada';
            let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 0 && text.length < 100) return text;
            let current = el;
            for (let i = 0; i < 4; i++) {
                if (!current) break;
                if(current.getAttribute('aria-label')) return current.getAttribute('aria-label');
                if(current.getAttribute('title')) return current.getAttribute('title');
                current = current.parentElement;
            }
            return el.tagName.toLowerCase();
        };

        const getBestSelector = (el) => {
            let current = el;
            for (let i = 0; i < 5; i++) {
                if (!current) break;
                let testid = current.getAttribute('data-testid') || current.getAttribute('data-test');
                if (testid) return `[data-testid='${testid}']`;
                let aria = current.getAttribute('aria-label');
                if (aria) return `[aria-label='${aria}']`;
                let name = current.getAttribute('name');
                if (name && name.length < 40) return `[name='${name}']`;
                if (current.id && !current.id.match(/^[\d\-_]/) && !current.id.match(/ng-|mat-|cdk-/)) return `[id='${current.id}']`;
                current = current.parentElement;
            }
            let isEditable = el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea' || el.isContentEditable || el.getAttribute('contenteditable') === 'true';
            if (isEditable) {
                let placeholder = el.getAttribute('placeholder');
                if (placeholder) return `[placeholder='${placeholder}']`;
                if (el.getAttribute('contenteditable') === 'true') {
                    let labelFor = document.querySelector(`label[for='${el.id}']`);
                    if (labelFor) return `[aria-label='${labelFor.innerText.trim()}']`;
                    return `[contenteditable='true']`;
                }
            }
            let role = el.getAttribute('role');
            if (role && role !== 'presentation') {
                let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
                if (text && text.length < 50) return `[role='${role}']:has-text('${text}')`;
            }
            let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 1 && text.length < 50) return `text="${text}"`;
            let tag = el.tagName.toLowerCase();
            let parentAria = el.closest('[aria-label]')?.getAttribute('aria-label');
            if (parentAria) return `[aria-label='${parentAria}'] ${tag}`;
            let siblings = Array.from(el.parentElement?.children || []);
            return `${tag}:nth-child(${siblings.indexOf(el) + 1})`;
        };

        const getFrameIdentifier = () => {
            if (window.name) return window.name;
            try {
                let selfSrc = window.location.href;
                if (selfSrc && selfSrc !== window.top?.location?.href) return selfSrc.split('/').pop().split('?')[0] || 'iframe';
            } catch (e) {}
            return 'Página Principal';
        };

        const processarEvento = (target, acao, valor = '') => {
            let label_semantico = getElementName(target);
            let tag = target.tagName.toLowerCase();
            let rect = target.getBoundingClientRect();
            let posicao = `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`;

            window.capturarElemento(JSON.stringify({
                tag: tag, texto_encontrado: valor || label_semantico, seletor: getBestSelector(target),
                iframe: getFrameIdentifier(), acao: acao, posicao_visual: posicao, html_snapshot: target.outerHTML.substring(0, 300)
            }));

            // Feedback visual rápido para o Especialista saber que capturou
            const originalOutline = target.style.outline;
            target.style.outline = '2px solid red';
            setTimeout(() => target.style.outline = originalOutline, 200);
        };

        // ── LÓGICA DE DEBOUNCE PARA PREVENIR DUPLO CLIQUE SENDO LIDO COMO 2 CLIQUES ──
        let clickTimeout = null;

        document.addEventListener('mousedown', (e) => { 
            // O botão direito (2) é acionado instantaneamente
            if (e.button === 2) {
                processarEvento(e.target, 'clique_direito');
                return;
            }
            
            // O botão esquerdo (0) usa debounce para aguardar um possível duplo clique
            if (e.button === 0) {
                if (clickTimeout !== null) {
                    clearTimeout(clickTimeout);
                    clickTimeout = null;
                    return; // Aborta o clique simples, o dblclick vai assumir
                }
                
                clickTimeout = setTimeout(() => {
                    processarEvento(e.target, 'clique');
                    clickTimeout = null;
                }, 250); // Aguarda 250ms
            }
        }, true);
        
        document.addEventListener('dblclick', (e) => {
            // Mata o timer do clique simples para não registrar duplicado
            clearTimeout(clickTimeout); 
            clickTimeout = null;
            processarEvento(e.target, 'duplo_clique');
        }, true);

        // Mantém o enter e blur originais para digitação
        let ultimoEnterTarget = null, ultimoEnterTime = 0;
        document.addEventListener('keydown', (e) => { 
            if (e.key === 'Enter') { 
                ultimoEnterTarget = e.target; 
                ultimoEnterTime = Date.now(); 
                processarEvento(e.target, 'digitar_e_enter', e.target.value || e.target.innerText || ''); 
            } 
        }, true);
        
        document.addEventListener('blur', (e) => {
            let tag = e.target.tagName.toLowerCase();
            if (e.target === ultimoEnterTarget && Date.now() - ultimoEnterTime < 500) return;
            if ((tag === 'input' || tag === 'textarea' || e.target.isContentEditable) && e.target.value) {
                processarEvento(e.target, 'preencher_campo', e.target.value);
            }
        }, true);
    }"""
    try: await contexto.evaluate(script_radar)
    except Exception: pass

async def injetar_radar_event_driven(page):
    await _injetar_em_contexto(page)
    async def injetar_com_delay(frame):
        try: await asyncio.sleep(0.5); await _injetar_em_contexto(frame)
        except Exception: pass
    page.on("frameattached", lambda frame: asyncio.create_task(injetar_com_delay(frame)))
    page.on("framenavigated", lambda frame: asyncio.create_task(injetar_com_delay(frame)))

# ==============================================================
# 📸 HANDLER DE CAPTURA DE AÇÕES
# ==============================================================
async def on_capturar_elemento(source, args):
    global _id_acao_global, _lock_id
    async with _lock_id:
        _id_acao_global += 1
        meu_id_acao = _id_acao_global

    try:
        dados_json = await args.json_value()
        dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json

        acao = dados.get('acao', 'clique')
        label = (dados['texto_encontrado'] or dados['tag'])[:40]
        logger.info(f"📸 [FOTO RÁPIDA {meu_id_acao}] | {acao.upper()} | {label}")

        screenshot_b64 = None
        vp_w, vp_h = 1920, 1080 
        screenshot_bytes = None
        
        try:
            frame = source.get("frame")
            if frame:
                page_ref = frame.page
                screenshot_bytes = await page_ref.screenshot(type="jpeg", quality=80, full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                vp = await page_ref.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                vp_w, vp_h = vp['w'], vp['h']
        except Exception as e: 
            logger.warning(f"Falha ao tirar print: {e}")

        coords = _extrair_coordenadas_relativas(dados.get('posicao_visual', ''), vp_w, vp_h)

        if screenshot_bytes:
            analise = await _analisar_elemento_com_gemini(screenshot_bytes, dados.get('html_snapshot', ''), label, coords, acao)
        else:
            analise = {"intencao": f"{acao.capitalize()} em '{label}'", "descricao_visual": f"Elemento '{label}'", "contexto_tela": "Desconhecido", "tipo_elemento": "button", "confianca": "baixa"}

        iframe_id = dados.get('iframe', 'Página Principal')

        cliques_capturados.append({
            "id_acao": meu_id_acao,
            "acao": acao,
            "intencao_semantica": analise["intencao"],
            "elemento_alvo": {
                "descricao_visual": analise["descricao_visual"],
                "contexto_tela": analise["contexto_tela"],
                "tipo_elemento": analise.get("tipo_elemento", "button"),
                "confianca_captura": analise.get("confianca", "media"),
                "label_curto": label,
                "coordenadas_relativas": coords,
                "seletor_hint": dados['seletor'],
                "iframe_hint": iframe_id if iframe_id != 'Página Principal' else None,
                "html_hint": dados.get("html_snapshot", "")[:300],
                "screenshot_referencia": screenshot_b64,
            },
            "valor_input": dados['texto_encontrado'] if acao in ['digitar_e_enter', 'preencher_campo'] else ""
        })
    except Exception as e:
        logger.error(f"Erro ao processar captura: {e}")

# ==============================================================
# 🔴 SESSÃO DE GRAVAÇÃO NO BROWSER
# ==============================================================
async def capturar_cliques_na_tela():
    global _lock_id
    _lock_id = asyncio.Lock()
    
    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)
        logger.info("\n🔄 Abrindo Senior X para Mapeamento...")
        
        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0); await page.keyboard.press("Escape")
            await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
            await page.get_by_role("button", name="Próximo").click()
            await asyncio.sleep(0.5); await page.keyboard.press("Escape")
            await page.locator("input[type='password']").fill(senha)
            await asyncio.sleep(0.5); await page.keyboard.press("Enter")
            await page.wait_for_load_state("load")
            await asyncio.sleep(1.0)

            await injetar_radar_event_driven(page)
            script_alerta_seguro = """() => {
                if(document.body) {
                    const div = document.createElement('div');
                    div.innerHTML = '🎬 GRAVAÇÃO INICIADA!<br><span style="font-size:14px; font-weight:normal;">Clique de forma calma e firme.</span>';
                    div.style.cssText = `position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #e50914; color: white; padding: 15px 30px; font-size: 22px; font-weight: bold; font-family: sans-serif; z-index: 999999; border-radius: 8px; pointer-events: none; transition: opacity 1s ease; text-align:center;`;
                    document.body.appendChild(div);
                    setTimeout(() => div.style.opacity = '0', 4000);
                    setTimeout(() => div.remove(), 5000);
                }
            }"""
            try: await page.evaluate(script_alerta_seguro)
            except Exception: pass
            
        except Exception as e:
            return logger.error(f"❌ Erro crítico no login: {e}")

        logger.info("\n🔴 GRAVAÇÃO INICIADA! Use o sistema de forma cadenciada. Feche o navegador ao terminar.\n")
        try:
            while not page.is_closed():
                await asyncio.sleep(2)
                try:
                    if not await page.evaluate("() => !!window.__radarInjetado"): 
                        await _injetar_em_contexto(page)
                except Exception: break 
        except Exception: pass

# ==============================================================
# 🧠 AURA E REPOSITÓRIO NOMINAL DE TESTES
# ==============================================================
def _invocar_aura_sync(nome_aula: str, objetivo_aula: str, log_mapeador: list, contexto_rag: str):
    logger.info("🧠 Acordando a Aura (Processamento Semântico)...")
    PROMPT_FALLBACK = "Você é a Aura, especialista em treinamento. Transforme o log em passos JSON. O JSON precisa ter: metadata, passos(id_passo, tipo_passo, pedagogia(ancora, tooltip_dap), is_conclusao, acoes_tecnicas, micro_narracoes). DENTRO DE acoes_tecnicas repasse EXATAMENTE os blocos de acao, intencao_semantica, elemento_alvo e valor_input do log original."
    
    try:
        with open("aura_prompt.txt", "r", encoding="utf-8") as f: prompt_sistema = f.read()
    except FileNotFoundError:
        prompt_sistema = PROMPT_FALLBACK

    lista_para_ia = []
    for a in log_mapeador:
        alvo_sem_foto = {k: v for k, v in a["elemento_alvo"].items() if k != "screenshot_referencia"}
        lista_para_ia.append({"id_acao": a["id_acao"], "acao": a["acao"], "intencao_semantica": a["intencao_semantica"], "elemento_alvo_resumido": alvo_sem_foto, "valor_input": a["valor_input"]})

    prompt_usuario = f"AULA: {nome_aula}\nOBJETIVO: {objetivo_aula}\nCONTEXTO MANUAL: {contexto_rag}\nAÇÕES CAPTURADAS:\n{json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}"

    try:
        resposta = gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt_usuario,
            config=types.GenerateContentConfig(system_instruction=prompt_sistema, response_mime_type="application/json", temperature=0.2)
        )
        dados_da_ia = json.loads(resposta.text)
        
        metadata = dados_da_ia.get("metadata", {})
        metadata["nome_aula"] = nome_aula
        
        roteiro_final = {"metadata": metadata, "configuracao_gravacao": {"gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"}, "passos": []}

        for passo_ia in dados_da_ia.get("passos", []):
            passo_mesclado = {"id_passo": passo_ia["id_passo"], "tipo_passo": passo_ia.get("tipo_passo", "operacao"), "pedagogia": passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}), "alerta_instrutor": passo_ia.get("alerta_instrutor", None), "is_conclusao": passo_ia.get("is_conclusao", False), "acoes_tecnicas": []}
            micro_narracoes = passo_ia.get("micro_narracoes", [])
            
            for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
                acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
                if acao_bruta:
                    passo_mesclado["acoes_tecnicas"].append({
                        "acao": acao_bruta["acao"], "intencao_semantica": acao_bruta["intencao_semantica"], 
                        "elemento_alvo": acao_bruta["elemento_alvo"], "valor_input": acao_bruta["valor_input"],
                        "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else ""
                    })
                    
            if passo_mesclado["is_conclusao"]: 
                passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})
            roteiro_final["passos"].append(passo_mesclado)

        os.makedirs("roteiros_salvos", exist_ok=True)
        # Usa a função de higienização oficial para garantir compatibilidade
        nome_arquivo_base = limpar_nome(nome_aula)
        caminho_roteiro = os.path.join("roteiros_salvos", f"{nome_arquivo_base}.json")

        with open(caminho_roteiro, 'w', encoding='utf-8') as f: 
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)
            
        logger.info(f"✅ Roteiro salvo permanentemente em: {caminho_roteiro}")
        return caminho_roteiro
        
    except Exception as e:
        logger.error(f"Erro na mesclagem final do Roteiro: {e}")
        return None

async def orquestrador_pos_captura(nome_aula: str, objetivo: str):
    contexto_rag = await buscar_contexto_pinecone(objetivo)
    return await asyncio.to_thread(_invocar_aura_sync, nome_aula, objetivo, cliques_capturados, contexto_rag)

def iniciar_esteira_de_producao():
    print("\n" + "=" * 50 + "\n🎓 SENIOR SISTEMAS — TRAINING OS (CRIADOR DE AULAS)\n" + "=" * 50)
    
    is_auto = "--auto" in sys.argv
    if is_auto:
        nome_aula = sys.argv[1]
        objetivo = sys.argv[2]
        logger.info(f"🌐 Iniciado via Dashboard Web | Aula: {nome_aula}")
    else:
        nome_aula = input("🏷️ Qual é o nome desta aula/vídeo? (Ex: Criando Pastas e Subpastas)\n> ")
        objetivo = input("🎙️ Qual é o objetivo do treinamento de hoje?\n> ")
    
    asyncio.run(capturar_cliques_na_tela())
    
    if not cliques_capturados: 
        logger.warning("Nenhuma ação capturada. Encerrando.")
        sys.exit(1) # Avisa a UI que deu erro/cancelou
        
    logger.info(f"\n📊 {len(cliques_capturados)} ações capturadas. Processando Roteiro...")
    
    caminho_roteiro_gerado = asyncio.run(orquestrador_pos_captura(nome_aula, objetivo))
    
    if caminho_roteiro_gerado:
        if is_auto:
            logger.info("✅ Roteiro gerado! O Dashboard será atualizado automaticamente.")
        else:
            if input("\n🎬 Tudo pronto! Iniciar o Motor de Gravação (main.py)? (S/N)\n> ").strip().upper() == "S":
                subprocess.run([sys.executable, "main.py", caminho_roteiro_gerado])

if __name__ == "__main__": 
    iniciar_esteira_de_producao()
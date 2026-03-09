import asyncio
import os
import json
import base64
import subprocess
import sys
import logging
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from google import genai
from google.genai import types
from pinecone import Pinecone

load_dotenv()

# Configuração de Log limpo
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
cliques_capturados = []
_contador_screenshots = 0

# LOCK DE SEGURANÇA CONTRA RACE CONDITIONS (Evita IDs duplicados)
_id_acao_global = 0
_lock_id = asyncio.Lock()

# ==============================================================
# 📚 RAG E PINECONE
# ==============================================================
def buscar_contexto_pinecone(objetivo_aula: str) -> str:
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index = os.getenv("PINECONE_INDEX_NAME")
    
    if not chave_pinecone or not nome_index:
        return "Nenhum contexto adicional."
    
    print("📚 Consultando o manual da Senior no Pinecone...")
    try:
        pc = Pinecone(api_key=chave_pinecone)
        index = pc.Index(nome_index)
        embedding_response = gemini_client.models.embed_content(
            model="gemini-embedding-001", 
            contents=[objetivo_aula]
        )
        resultado = index.query(
            vector=embedding_response.embeddings[0].values, 
            top_k=3, 
            include_metadata=True
        )
        textos = [
            match['metadata'].get('text', '') 
            for match in resultado['matches'] 
            if 'metadata' in match
        ]
        return "\n...\n".join(textos) if textos else "Nenhum contexto."
    except Exception as e:
        logger.warning(f"Aviso no Pinecone: {e}")
        return "Nenhum contexto adicional."

# ==============================================================
# 📐 ANÁLISE SEMÂNTICA (Usando Thread separada)
# ==============================================================
def _extrair_coordenadas_relativas(posicao_str: str, viewport_w: int, viewport_h: int) -> dict:
    try:
        partes = dict(p.split(':') for p in posicao_str.split(','))
        x = int(partes['x'])
        y = int(partes['y'])
        w_el = int(partes['w'])
        h_el = int(partes['h'])
        
        cx = x + w_el / 2
        cy = y + h_el / 2
        
        return {
            "x_pct": round(cx / viewport_w, 4), 
            "y_pct": round(cy / viewport_h, 4)
        }
    except Exception:
        return {"x_pct": 0.5, "y_pct": 0.5}

async def _analisar_elemento_com_gemini(screenshot_bytes: bytes, html_snapshot: str, label_capturado: str, coords: dict, acao: str) -> dict:
    prompt = f"""Você é um analista de UX documentando uma sessão de uso do sistema Senior X.
O usuário realizou a ação '{acao}' no elemento com label: '{label_capturado}'.
HTML do elemento clicado: {html_snapshot[:250]}
Posição relativa na tela: x={coords.get('x_pct', '?')}, y={coords.get('y_pct', '?')}

Analise o screenshot e responda com um JSON descrevendo o momento:
{{
  "intencao": "O QUE o usuário quis fazer, orientado a resultado",
  "descricao_visual": "COMO o elemento aparece na tela: tipo visual, cor, posição, texto exibido",
  "contexto_tela": "Em qual parte do sistema o usuário está",
  "tipo_elemento": "button | input | menu_item | link | icon | checkbox | tab | folder",
  "confianca": "alta | media | baixa"
}}"""
    try:
        # A MÁGICA DE PERFORMANCE: Libera o event loop do Playwright enquanto a IA pensa!
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=screenshot_bytes, mime_type="image/jpeg"), 
                prompt
            ],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        resultado = json.loads(resposta.text)
        
        if not resultado.get("intencao"): 
            resultado["intencao"] = f"{acao.capitalize()} em '{label_capturado}'"
        if not resultado.get("descricao_visual"): 
            resultado["descricao_visual"] = f"Elemento '{label_capturado}'"
            
        return resultado
    except Exception as e:
        logger.warning(f"Erro na IA de Visão (Fallback ativado): {e}")
        return {
            "intencao": f"{acao.capitalize()} em '{label_capturado}'", 
            "descricao_visual": f"Elemento '{label_capturado}'", 
            "contexto_tela": "Desconhecido", 
            "tipo_elemento": "button", 
            "confianca": "baixa"
        }

# ==============================================================
# 🕵️ RADAR DE CAPTURA (Com Escape JS e Cross-Origin fix)
# ==============================================================
async def _injetar_em_contexto(contexto):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;

        const escapeStr = (s) => s ? s.replace(/'/g, "\\'") : '';

        const getElementName = (el) => {
            let isEditable = el.tagName.toLowerCase() === 'input' || 
                             el.tagName.toLowerCase() === 'textarea' || 
                             el.getAttribute('contenteditable') === 'true';
            
            if (isEditable) {
                return el.placeholder || el.name || el.title || 'Campo de entrada';
            }
            
            let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 0 && text.length < 100) return text;

            let current = el;
            for (let i = 0; i < 4; i++) {
                if (!current) break;
                if (current.getAttribute('aria-label')) return current.getAttribute('aria-label');
                if (current.getAttribute('title')) return current.getAttribute('title');
                current = current.parentElement;
            }
            return el.tagName.toLowerCase();
        };

        const getBestSelector = (el) => {
            let current = el;
            for (let i = 0; i < 5; i++) {
                if (!current) break;
                if (current.getAttribute('data-testid')) {
                    return `[data-testid='${escapeStr(current.getAttribute('data-testid'))}']`;
                }
                if (current.getAttribute('aria-label')) {
                    return `[aria-label='${escapeStr(current.getAttribute('aria-label'))}']`;
                }
                if (current.id && !current.id.match(/^[\\d\\-_]/) && !current.id.match(/ng-|mat-|cdk-/)) {
                    return `[id='${escapeStr(current.id)}']`;
                }
                current = current.parentElement;
            }
            
            let isEditable = el.tagName.toLowerCase() === 'input' || 
                             el.tagName.toLowerCase() === 'textarea' || 
                             el.isContentEditable || 
                             el.getAttribute('contenteditable') === 'true';
                             
            if (isEditable && el.getAttribute('contenteditable') === 'true') {
                return `[contenteditable='true']`;
            }
            
            let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 1 && text.length < 50) {
                return `text="${escapeStr(text)}"`;
            }
            
            let tag = el.tagName.toLowerCase();
            let siblings = Array.from(el.parentElement?.children || []);
            return `${tag}:nth-child(${siblings.indexOf(el) + 1})`;
        };

        const getFrameIdentifier = () => {
            if (window.name) return window.name;
            try {
                if (window.top && window.location.href !== window.top.location.href) {
                    return window.location.href.split('/').pop().split('?')[0] || 'iframe';
                }
            } catch (e) { 
                return 'iframe_cross_origin'; 
            }
            return 'Página Principal';
        };

        const processarEvento = (target, acao, valor = '') => {
            let rect = target.getBoundingClientRect();
            let posicao = `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`;

            window.capturarElemento(JSON.stringify({
                tag: target.tagName.toLowerCase(),
                texto_encontrado: valor || getElementName(target),
                seletor: getBestSelector(target),
                iframe: getFrameIdentifier(),
                acao: acao,
                posicao_visual: posicao,
                html_snapshot: target.outerHTML.substring(0, 300)
            }));

            const originalBg = target.style.backgroundColor;
            target.style.backgroundColor = acao.includes('clique') ? 'rgba(0,153,153,0.4)' : 'rgba(0,100,255,0.4)';
            setTimeout(() => { target.style.backgroundColor = originalBg; }, 300);
        };

        let clickTimer = null;
        let ultimoEnterTarget = null;
        let ultimoEnterTime = 0;

        document.addEventListener('click', (e) => { 
            if (e.detail === 1) {
                clickTimer = setTimeout(() => processarEvento(e.target, 'clique'), 250); 
            }
        }, true);
        
        document.addEventListener('dblclick', (e) => { 
            clearTimeout(clickTimer); 
            processarEvento(e.target, 'duplo_clique'); 
        }, true);
        
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
    try: 
        await contexto.evaluate(script_radar)
    except Exception: 
        pass 

def handle_frame_error(task):
    try: 
        task.result()
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
            
    page.on("frameattached", lambda frame: asyncio.create_task(injetar_com_delay(frame)).add_done_callback(handle_frame_error))
    page.on("framenavigated", lambda frame: asyncio.create_task(injetar_com_delay(frame)).add_done_callback(handle_frame_error))

async def injetar_alerta_visual(page):
    script_alerta = """() => {
        const div = document.createElement('div');
        div.innerHTML = '🎬 GRAVAÇÃO INICIADA! PODE CLICAR!';
        div.style.cssText = `position: fixed; top: 20px; left: 50%; transform: translateX(-50%); background: #e50914; color: white; padding: 15px 30px; font-size: 22px; font-weight: bold; font-family: sans-serif; z-index: 999999; border-radius: 8px; pointer-events: none; transition: opacity 1s ease;`;
        document.body.appendChild(div);
        setTimeout(() => div.style.opacity = '0', 3500);
        setTimeout(() => div.remove(), 4500);
    }"""
    try: 
        await page.evaluate(script_alerta)
    except Exception: 
        pass

# ==============================================================
# 📸 HANDLER DE CAPTURA BLINDADO CONTRA RACE CONDITIONS
# ==============================================================
async def on_capturar_elemento(source, args):
    global _contador_screenshots, _id_acao_global
    
    # O LOCK GARANTE QUE NÃO EXISTAM AÇÕES COM O MESMO ID
    async with _lock_id:
        _id_acao_global += 1
        meu_id_acao = _id_acao_global

    try:
        dados_json = await args.json_value()
        if isinstance(dados_json, str):
            dados = json.loads(dados_json)
        else:
            dados = dados_json

        acao = dados.get('acao', 'clique')
        label = (dados['texto_encontrado'] or dados['tag'])[:40]

        print(f"🎬 [AÇÃO {meu_id_acao}] | {acao.upper()} | Label: {label} | Seletor: {dados['seletor']}")

        screenshot_b64 = None
        page_ref = None
        screenshot_bytes = None
        vp_w, vp_h = 1920, 1080 
        
        try:
            frame = source.get("frame")
            if frame:
                page_ref = frame.page
                # SALVA COMO JPEG: Mais rápido e economiza gigabytes de RAM
                screenshot_bytes = await page_ref.screenshot(type="jpeg", quality=60, full_page=False)
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
                
                vp = await page_ref.evaluate("() => ({w: window.innerWidth, h: window.innerHeight})")
                vp_w = vp['w']
                vp_h = vp['h']
        except Exception as e:
            logger.debug(f"Falha ao tirar screenshot da ação {meu_id_acao}: {e}")

        coords = _extrair_coordenadas_relativas(dados.get('posicao_visual', ''), vp_w, vp_h)

        if screenshot_bytes:
            analise = await _analisar_elemento_com_gemini(
                screenshot_bytes, 
                dados.get('html_snapshot', ''), 
                label, 
                coords, 
                acao
            )
            print(f"   ✅ Capturado: {analise['intencao'][:60]} | Confiança: {analise.get('confianca', '?')}")
        else:
            analise = {
                "intencao": f"{acao.capitalize()} em '{label}'", 
                "descricao_visual": f"Elemento '{label}'", 
                "contexto_tela": "Desconhecido", 
                "tipo_elemento": "button", 
                "confianca": "baixa"
            }

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
        logger.warning(f"Erro fatal no processamento da ação: {e}")

# ==============================================================
# 🔴 SESSÃO DE GRAVAÇÃO
# ==============================================================
async def capturar_cliques_na_tela():
    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)
        
        print("\n🔄 Abrindo Senior X para Mapeamento...")
        
        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")
            await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
            await page.get_by_role("button", name="Próximo").click()
            await asyncio.sleep(0.5)
            await page.keyboard.press("Escape")
            
            senha_input = page.locator("input[type='password']")
            await senha_input.wait_for(state="visible")
            await senha_input.fill(senha)
            await asyncio.sleep(0.5)
            await senha_input.press("Enter")

            await page.wait_for_load_state("load")
            await asyncio.sleep(1.0)

            await injetar_radar_event_driven(page)
            await injetar_alerta_visual(page)
            
        except Exception as e:
            print(f"❌ Erro crítico durante o Login: {e}")
            return

        print("\n🔴 GRAVAÇÃO INICIADA! Use o sistema. Feche o navegador ao terminar.\n")
        try:
            while True:
                if page.is_closed():
                    break
                await asyncio.sleep(2)
                try:
                    already = await page.evaluate("() => !!window.__radarInjetado")
                    if not already: 
                        await _injetar_em_contexto(page)
                except Exception:
                    # Se não conseguir avaliar, a página foi fechada pelo usuário.
                    break 
        except Exception:
            pass

# ==============================================================
# 🧠 AURA — GERAÇÃO DO ROTEIRO
# ==============================================================
def invocar_aura(objetivo_aula: str, log_mapeador: list, contexto_rag: str):
    print("\n🧠 Acordando a Aura (Vision-First + Professora Experiente)...")
    PROMPT_AURA_FALLBACK = """Você é a Aura, especialista em treinamento. Transforme o log em passos JSON. O JSON precisa ter: metadata, passos(id_passo, tipo_passo, pedagogia(ancora, tooltip_dap), is_conclusao, acoes_tecnicas, micro_narracoes). DENTRO DE acoes_tecnicas repasse EXATAMENTE os blocos de acao, intencao_semantica, elemento_alvo e valor_input do log original. Não altere a estrutura interna da ação."""

    try:
        with open("aura_prompt.txt", "r", encoding="utf-8") as f:
            prompt_sistema = f.read()
    except FileNotFoundError:
        print("⚠️ Arquivo 'aura_prompt.txt' não encontrado. Usando fallback mínimo.")
        prompt_sistema = PROMPT_AURA_FALLBACK

    lista_para_ia = []
    for a in log_mapeador:
        # Tira o screenshot gigante do log apenas para enviar para a IA montar o texto
        alvo_sem_screenshot = {k: v for k, v in a["elemento_alvo"].items() if k != "screenshot_referencia"}
        lista_para_ia.append({
            "id_acao": a["id_acao"], 
            "acao": a["acao"], 
            "intencao_semantica": a["intencao_semantica"], 
            "elemento_alvo_resumido": alvo_sem_screenshot, 
            "valor_input": a["valor_input"]
        })

    prompt_usuario = f"OBJETIVO: {objetivo_aula}\nCONTEXTO MANUAL: {contexto_rag}\nAÇÕES DO LOG:\n{json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}"

    print("⚙️ Gerando roteiro estruturado...")
    try:
        resposta = gemini_client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt_usuario,
            config=types.GenerateContentConfig(system_instruction=prompt_sistema, response_mime_type="application/json", temperature=0.2)
        )
        dados_da_ia = json.loads(resposta.text)
        
        roteiro_final = {
            "metadata": dados_da_ia.get("metadata", {}), 
            "configuracao_gravacao": {"gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"}, 
            "passos": []
        }

        for passo_ia in dados_da_ia.get("passos", []):
            passo_mesclado = {
                "id_passo": passo_ia["id_passo"], 
                "tipo_passo": passo_ia.get("tipo_passo", "operacao"), 
                "pedagogia": passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}), 
                "alerta_instrutor": passo_ia.get("alerta_instrutor", None), 
                "is_conclusao": passo_ia.get("is_conclusao", False), 
                "acoes_tecnicas": []
            }
            
            micro_narracoes = passo_ia.get("micro_narracoes", [])
            for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
                acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
                if acao_bruta:
                    passo_mesclado["acoes_tecnicas"].append({
                        "acao": acao_bruta["acao"], 
                        "intencao_semantica": acao_bruta["intencao_semantica"], 
                        "elemento_alvo": acao_bruta["elemento_alvo"], # Recoloca a foto no JSON final
                        "valor_input": acao_bruta["valor_input"],
                        "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else ""
                    })
                    
            if passo_mesclado["is_conclusao"]: 
                passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})
                
            roteiro_final["passos"].append(passo_mesclado)

        with open("roteiro.json", 'w', encoding='utf-8') as f: 
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)
            
        print("✅ roteiro.json gerado com sucesso!")
        
    except Exception as e: 
        print(f"❌ Erro ao montar o roteiro final: {e}")

def iniciar_esteira_de_producao():
    print("\n" + "=" * 50 + "\n🎓 SENIOR SISTEMAS — TRAINING OS\n" + "=" * 50)
    objetivo = input("🎙️ Olá! Qual é o objetivo do treinamento de hoje?\n> ")
    
    asyncio.run(capturar_cliques_na_tela())
    
    if not cliques_capturados: 
        print("\n❌ Nenhuma ação capturada. Encerrando.")
        return
        
    print(f"\n📊 Processando e analisando as {len(cliques_capturados)} ações capturadas...")
    invocar_aura(objetivo, cliques_capturados, buscar_contexto_pinecone(objetivo))
    
    if input("\n🎬 Tudo pronto! Iniciar o Motor de Gravação (main.py)? (S/N)\n> ").strip().upper() == "S":
        subprocess.run([sys.executable, "main.py"])

if __name__ == "__main__": 
    iniciar_esteira_de_producao()
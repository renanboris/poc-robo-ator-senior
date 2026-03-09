import asyncio
import os
import json
import base64
import subprocess
import sys
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from google import genai
from google.genai import types
from pinecone import Pinecone

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
cliques_capturados = []
_contador_screenshots = 0

def _extrair_coordenadas_relativas(posicao_str: str) -> dict:
    try:
        partes = dict(p.split(':') for p in posicao_str.split(','))
        x, y = int(partes['x']), int(partes['y'])
        w_el, h_el = int(partes['w']), int(partes['h'])
        cx, cy = x + w_el / 2, y + h_el / 2
        vw, vh = 1920, 1080 
        return {"x_pct": round(cx / vw, 4), "y_pct": round(cy / vh, 4)}
    except: return {"x_pct": 0.5, "y_pct": 0.5}

def buscar_contexto_pinecone(objetivo_aula):
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index = os.getenv("PINECONE_INDEX_NAME") 
    if not chave_pinecone or not nome_index: return "Nenhum contexto adicional."
    print("📚 Consultando o manual da Senior no Pinecone...")
    try:
        pc = Pinecone(api_key=chave_pinecone)
        index = pc.Index(nome_index) 
        embedding_response = gemini_client.models.embed_content(model="gemini-embedding-001", contents=[objetivo_aula])
        resultado = index.query(vector=embedding_response.embeddings[0].values, top_k=3, include_metadata=True)
        textos = [match['metadata'].get('text', '') for match in resultado['matches'] if 'metadata' in match]
        return "\n...\n".join(textos) if textos else "Nenhum contexto."
    except: return "Nenhum contexto adicional."

async def _injetar_em_contexto(contexto):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;
        
        // NOVO: Resolve o problema do botão Home (Ícones sem texto)
        const getElementName = (el) => {
            let isEditable = el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea' || el.getAttribute('contenteditable') === 'true';
            if (isEditable) return el.placeholder || el.name || el.title || 'Campo de entrada';
            
            let text = el.innerText?.trim().replace(/\\n/g, ' ') || '';
            if (text && text.length > 0 && text.length < 100) return text;

            let current = el;
            for(let i=0; i<4; i++) {
                if(!current) break;
                let aria = current.getAttribute('aria-label');
                if (aria) return aria;
                let title = current.getAttribute('title');
                if (title) return title;
                current = current.parentElement;
            }
            return el.tagName.toLowerCase();
        };

        const getBestSelector = (el) => {
            let current = el;
            for(let i = 0; i < 5; i++) { 
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
            let parentAriaLabel = el.closest('[aria-label]')?.getAttribute('aria-label');
            if (parentAriaLabel) return `[aria-label='${parentAriaLabel}'] ${tag}`;
            
            let siblings = Array.from(el.parentElement?.children || []);
            return `${tag}:nth-child(${siblings.indexOf(el) + 1})`;
        };

        const getFrameIdentifier = () => {
            if (window.name) return window.name;
            try {
                let selfSrc = window.location.href;
                if (selfSrc && selfSrc !== window.top?.location?.href) return selfSrc.split('/').pop().split('?')[0] || window.name || 'iframe';
            } catch(e) {}
            return 'Página Principal';
        };

        const processarEvento = (target, acao, valor = '') => {
            let label_corrigido = getElementName(target);
            let tag = target.tagName.toLowerCase();
            
            let rect = target.getBoundingClientRect();
            let posicao = `x:${Math.round(rect.x)},y:${Math.round(rect.y)},w:${Math.round(rect.width)},h:${Math.round(rect.height)}`;
            
            window.capturarElemento(JSON.stringify({ 
                tag: tag, 
                texto_encontrado: valor || label_corrigido, 
                seletor: getBestSelector(target), 
                iframe: getFrameIdentifier(), 
                acao: acao, 
                posicao_visual: posicao, 
                html_snapshot: target.outerHTML.substring(0, 300)
            }));
            
            const originalBg = target.style.backgroundColor;
            target.style.backgroundColor = acao.includes('clique') ? 'rgba(0,153,153,0.4)' : 'rgba(0,100,255,0.4)';
            setTimeout(() => target.style.backgroundColor = originalBg, 300);
        };

        let clickTimer = null;
        let ultimoEnterTarget = null;
        let ultimoEnterTime = 0;

        document.addEventListener('click', (e) => { if (e.detail === 1) { clickTimer = setTimeout(() => processarEvento(e.target, 'clique'), 250); }}, true);
        document.addEventListener('dblclick', (e) => { clearTimeout(clickTimer); processarEvento(e.target, 'duplo_clique'); }, true);
        document.addEventListener('keydown', (e) => { if (e.key === 'Enter') { ultimoEnterTarget = e.target; ultimoEnterTime = Date.now(); processarEvento(e.target, 'digitar_e_enter', e.target.value || e.target.innerText || ''); }}, true);
        document.addEventListener('blur', (e) => {
            let tag = e.target.tagName.toLowerCase();
            if (e.target === ultimoEnterTarget && Date.now() - ultimoEnterTime < 500) return;
            if ((tag === 'input' || tag === 'textarea' || e.target.isContentEditable) && e.target.value) processarEvento(e.target, 'preencher_campo', e.target.value);
        }, true);
    }"""
    try: await contexto.evaluate(script_radar)
    except: pass

async def injetar_radar_event_driven(page):
    await _injetar_em_contexto(page)
    async def injetar_com_delay(frame):
        await asyncio.sleep(0.5) 
        await _injetar_em_contexto(frame)
    page.on("frameattached", lambda frame: asyncio.create_task(injetar_com_delay(frame)))
    page.on("framenavigated", lambda frame: asyncio.create_task(injetar_com_delay(frame)))

async def injetar_alerta_visual(page):
    script_alerta = """() => {
        const div = document.createElement('div');
        div.innerHTML = '🎬 GRAVAÇÃO INICIADA! PODE CLICAR!';
        div.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); background:#e50914; color:white; padding:15px 30px; font-size:22px; font-weight:bold; font-family:sans-serif; z-index:999999; border-radius:8px; pointer-events: none;';
        document.body.appendChild(div);
        setTimeout(() => div.style.opacity = '0', 3500);
        setTimeout(() => div.remove(), 4500);
    }"""
    try: await page.evaluate(script_alerta)
    except: pass

async def on_capturar_elemento(source, args):
    global _contador_screenshots
    dados_json = await args.json_value()
    dados = json.loads(dados_json) if isinstance(dados_json, str) else dados_json
        
    acao = dados.get('acao', 'clique')
    label = dados['texto_encontrado'][:40] if dados['texto_encontrado'] else dados['tag']
    print(f"🎬 [AÇÃO {len(cliques_capturados)+1}] | {acao.upper()} | Label: {label} | Seletor: {dados['seletor']}")
    
    screenshot_b64 = None
    _contador_screenshots += 1
    
    if acao in ['clique', 'duplo_clique', 'digitar_e_enter']:
        try:
            frame = source["frame"]
            page_ref = frame.page
            screenshot_bytes = await page_ref.screenshot(type="png", full_page=False)
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        except: pass
        
    coords = _extrair_coordenadas_relativas(dados.get('posicao_visual', ''))
    
    cliques_capturados.append({
        "id_acao": len(cliques_capturados) + 1,
        "acao": acao,
        "intencao_semantica": f"{acao.capitalize()} em {label}",
        "elemento_alvo": {
            "descricao_visual": f"Elemento '{label}'",
            "label_curto": label, # A CHAVE DA PRECISÃO
            "contexto_tela": "Desconhecido",
            "coordenadas_relativas": coords,
            "seletor_hint": dados['seletor'],
            "iframe_hint": dados['iframe'] if dados['iframe'] != 'Página Principal' else None,
            "screenshot_referencia": screenshot_b64,
            "html_hint": dados.get("html_snapshot", "")[:300]
        },
        "valor_input": dados['texto_encontrado'] if acao in ['digitar_e_enter', 'preencher_campo'] else ""
    })

async def capturar_cliques_na_tela():
    usuario, senha = os.getenv("SENIOR_USER"), os.getenv("SENIOR_PASS")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        await context.expose_binding("capturarElemento", on_capturar_elemento, handle=True)
        
        print("\n🔄 Abrindo Senior X para Mapeamento...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        await asyncio.sleep(2)
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
        await asyncio.sleep(1)
        
        await injetar_radar_event_driven(page)
        await injetar_alerta_visual(page)
        
        print("\n🔴 GRAVAÇÃO INICIADA! Use o sistema. Feche o navegador ao terminar.\n")
        try:
            while not page.is_closed():
                await asyncio.sleep(5)
                try:
                    already = await page.evaluate("() => !!window.__radarInjetado")
                    if not already: await _injetar_em_contexto(page)
                except: pass
        except: pass 

def invocar_aura(objetivo_aula, log_mapeador, contexto_rag):
    print("\n🧠 Acordando a Aura (Visão Semântica + Prompt de Professora)...")
    
    PROMPT_AURA_FALLBACK = """Você é a Aura, especialista em treinamento. Transforme o log em passos JSON. O JSON precisa ter: metadata, passos(id_passo, tipo_passo, pedagogia(ancora, tooltip_dap), is_conclusao, acoes_tecnicas, micro_narracoes). DENTRO DE acoes_tecnicas repasse EXATAMENTE os blocos de acao, intencao_semantica, elemento_alvo e valor_input do log original."""

    try:
        with open("aura_prompt.txt", "r", encoding="utf-8") as f: prompt_sistema = f.read()
    except FileNotFoundError:
        print("⚠️ AVISO: Arquivo 'aura_prompt.txt' não encontrado! Usando Fallback.")
        prompt_sistema = PROMPT_AURA_FALLBACK

    prompt_usuario = f"OBJETIVO: {objetivo_aula}\nCONTEXTO MANUAL: {contexto_rag}\nAÇÕES DO LOG (Repasse os blocos 'elemento_alvo' inteiros sem modificar):\n{json.dumps(log_mapeador, indent=2)}"

    print("⚙️ Analisando intenções para gerar o Roteiro Vision-First...")
    resposta = gemini_client.models.generate_content(
        model="gemini-2.5-flash", contents=prompt_usuario,
        config=types.GenerateContentConfig(system_instruction=prompt_sistema, response_mime_type="application/json", temperature=0.2)
    )
    
    try:
        dados_da_ia = json.loads(resposta.text)
        roteiro_final = {"metadata": dados_da_ia.get("metadata", {}), "configuracao_gravacao": { "gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural" }, "passos": []}
        
        for passo_ia in dados_da_ia.get("passos", []):
            passo_mesclado = {
                "id_passo": passo_ia["id_passo"], "tipo_passo": passo_ia.get("tipo_passo", "operacao"), "pedagogia": passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}), "alerta_instrutor": passo_ia.get("alerta_instrutor", None), "is_conclusao": passo_ia.get("is_conclusao", False), "acoes_tecnicas": []
            }
            
            for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
                acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
                if acao_bruta:
                    passo_mesclado["acoes_tecnicas"].append({
                        "acao": acao_bruta["acao"],
                        "intencao_semantica": acao_bruta["intencao_semantica"],
                        "elemento_alvo": acao_bruta["elemento_alvo"],
                        "valor_input": acao_bruta["valor_input"],
                        "micro_narracao": passo_ia.get("micro_narracoes", [])[i] if "micro_narracoes" in passo_ia and i < len(passo_ia["micro_narracoes"]) else ""
                    })
                    
            if passo_mesclado["is_conclusao"]: passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})
            roteiro_final["passos"].append(passo_mesclado)
        
        with open("roteiro.json", 'w', encoding='utf-8') as f: json.dump(roteiro_final, f, indent=2, ensure_ascii=False)
        print("✅ Universal Lesson JSON gerado com sucesso!")
    except Exception as e: print(f"❌ Erro ao mesclar o JSON: {e}")

def iniciar_esteira_de_producao():
    print("\n" + "="*50 + "\n🎓 SENIOR SISTEMAS - TRAINING OS (CRIADOR DE AULAS)\n" + "="*50)
    objetivo = input("🎙️ Olá, Instrutor! Qual é o objetivo do treinamento de hoje?\n> ")
    asyncio.run(capturar_cliques_na_tela())
    if not cliques_capturados: return print("\n❌ Nenhuma ação capturada.")
    invocar_aura(objetivo, cliques_capturados, buscar_contexto_pinecone(objetivo))
    
    if input("\n🎬 Tudo pronto! Iniciar Motor Cinematográfico (main.py)? (S/N)\n> ").strip().upper() == "S":
        subprocess.run([sys.executable, "main.py"])

if __name__ == "__main__":
    iniciar_esteira_de_producao()
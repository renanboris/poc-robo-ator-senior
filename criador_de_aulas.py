import asyncio
import os
import json
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

# ==============================================================
# 🧠 MÓDULO 1: O RAG (Busca no Pinecone)
# ==============================================================
def buscar_contexto_pinecone(objetivo_aula):
    chave_pinecone = os.getenv("PINECONE_API_KEY")
    nome_index = os.getenv("PINECONE_INDEX_NAME") 

    if not chave_pinecone or not nome_index:
        print("⚠️ Chaves do Pinecone não encontradas no .env.")
        return "Nenhum contexto adicional."

    print("📚 Consultando o manual da Senior no Pinecone...")
    try:
        pc = Pinecone(api_key=chave_pinecone)
        index = pc.Index(nome_index) 
        
        embedding_response = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=[objetivo_aula]
        )
        vetor_objetivo = embedding_response.embeddings[0].values

        resultado = index.query(
            vector=vetor_objetivo, top_k=3, include_metadata=True
        )
        
        textos_encontrados = [match['metadata'].get('text', '') for match in resultado['matches'] if 'metadata' in match]
        contexto_final = "\n...\n".join(textos_encontrados)
        return contexto_final if contexto_final else "Nenhum contexto adicional."
            
    except Exception as e:
        print(f"⚠️ Aviso no RAG: Não foi possível conectar ao Pinecone. Usando IA nativa.")
        return "Nenhum contexto adicional."

# ==============================================================
# 👁️ MÓDULO 2: O GRAVADOR CONTÍNUO (Com Raio-X Nível 8)
# ==============================================================
async def injetar_radar(page):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;

        const processarEvento = (e, acao, valor = '') => {
            let el = e.target;
            let tag = el.tagName.toLowerCase();
            let texto = el.innerText ? el.innerText.trim().replace(/\\n/g, ' ') : '';
            
            // Tratamento especial para inputs que não têm innerText
            if (!texto && (tag === 'input' || tag === 'textarea')) {
                texto = el.placeholder || el.value || '';
            }

            let id = el.id || '';
            let id_herdado = false;
            let tipo_elemento = el.type || el.getAttribute('role') || '';
            
            // RAIO-X PROFUNDO: Sobe até 8 níveis na árvore HTML
            if (!id) {
                let current = el.parentElement;
                for(let i=0; i<8; i++) {
                    if(current && current.id) {
                        id = current.id;
                        id_herdado = true;
                        break;
                    }
                    if(current) current = current.parentElement;
                }
            }

            let iframeNome = window.name || 'Página Principal';
            const relatorio = { 
                tag: tag, 
                texto_encontrado: valor || texto, 
                id_html: id, 
                id_herdado: id_herdado, 
                tipo_elemento: tipo_elemento,
                iframe: iframeNome, 
                acao: acao 
            };
            window.capturarElemento(JSON.stringify(relatorio));
            
            const color = acao === 'clique' ? 'rgba(0, 153, 153, 0.4)' : 'rgba(0, 100, 255, 0.4)'; // Verde Senior
            const originalBg = e.target.style.backgroundColor;
            e.target.style.backgroundColor = color;
            setTimeout(() => e.target.style.backgroundColor = originalBg, 300);
        };

        document.addEventListener('click', (e) => {
            processarEvento(e, 'clique');
        }, true);

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                let valorDigitado = e.target.value || e.target.innerText || ''; 
                processarEvento(e, 'digitar_e_enter', valorDigitado);
            }
        }, true);
    }"""
    try:
        await page.evaluate(script_radar)
        for frame in page.frames:
            try: await frame.evaluate(script_radar)
            except: pass
    except Exception:
        pass

async def injetar_alerta_visual(page):
    script_alerta = """() => {
        const div = document.createElement('div');
        div.innerHTML = '🎬 GRAVAÇÃO INICIADA! PODE CLICAR!';
        div.style.cssText = 'position:fixed; top:20px; left:50%; transform:translateX(-50%); background:#e50914; color:white; padding:15px 30px; font-size:22px; font-weight:bold; font-family:sans-serif; z-index:999999; border-radius:8px; box-shadow:0 4px 15px rgba(0,0,0,0.5); transition: opacity 1s ease-in-out; pointer-events:none;';
        document.body.appendChild(div);
        setTimeout(() => div.style.opacity = '0', 3500);
        setTimeout(() => div.remove(), 4500);
    }"""
    try:
        await page.evaluate(script_alerta)
    except:
        pass

async def capturar_cliques_na_tela():
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        async def on_capturar_elemento(dados_json):
            dados = json.loads(dados_json)
            acao_capturada = dados.get('acao', 'clique')
            id_info = f"{dados['id_html']} (Herdado)" if dados.get('id_herdado') else dados['id_html']
            
            print(f"🎬 [AÇÃO: {acao_capturada.upper()}] | ID: {id_info or 'N/A'} | Tag: {dados['tag']} | Tipo: {dados.get('tipo_elemento','N/A')} | Valor: {dados['texto_encontrado'][:15]}")
            
            alvo = {"primeiro": True}
            if dados['iframe'] != 'Página Principal': alvo["dentro_do_iframe"] = dados["iframe"]
            
            # --- CONSTRUÇÃO DO SELETOR ULTRA-INTELIGENTE ---
            tag_str = dados['tag']
            if dados.get('tipo_elemento') == 'checkbox':
                tag_str += "[type='checkbox']"
            elif dados.get('tipo_elemento') == 'radio':
                tag_str += "[type='radio']"

            if dados['id_html']: 
                if dados.get('id_herdado'):
                    alvo["seletor"] = f"[id='{dados['id_html']}'] {tag_str}"
                else:
                    alvo["seletor"] = f"[id='{dados['id_html']}']"
            elif dados['texto_encontrado'] and acao_capturada == 'clique': 
                alvo["seletor"] = tag_str
                alvo["com_texto"] = dados["texto_encontrado"]
                alvo["pegar_pai"] = True
            else: 
                alvo["seletor"] = tag_str
                
            cliques_capturados.append({
                "acao_sugerida": acao_capturada,
                "valor_digitado": dados['texto_encontrado'] if acao_capturada == 'digitar_e_enter' else None,
                "alvo_semantico": alvo
            })

        await context.expose_binding("capturarElemento", lambda source, args: asyncio.create_task(on_capturar_elemento(args)))

        print("\n🔄 Abrindo o sistema da Senior para Mapeamento...")
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
        await page.wait_for_load_state("networkidle") 
        await asyncio.sleep(1)
        
        await injetar_alerta_visual(page)
        
        print("\n" + "🔴"*10)
        print("GRAVAÇÃO INICIADA! O sistema está capturando suas ações reais.")
        print("👉 Use o sistema normalmente.")
        print("👉 Se for digitar, escreva e aperte 'ENTER' para capturar o texto.")
        print("👉 FECHE O NAVEGADOR no 'X' quando terminar a aula.")
        print("🔴"*10 + "\n")

        try:
            while True:
                if page.is_closed(): break
                await injetar_radar(page)
                await asyncio.sleep(2)
        except Exception:
            pass 

# ==============================================================
# 🪄 MÓDULO 3: AURA (Design Instrucional)
# ==============================================================
def invocar_aura(objetivo_aula, log_mapeador, contexto_rag):
    print("\n🧠 Acordando a Aura (Designer Instrucional da Senior)...")
    
    prompt_sistema = """
    Você é a Aura, a IA Especialista em Design Instrucional da Senior Sistemas.
    Sua missão é gerar a narração didática e identificar a ação de cada passo, aplicando o framework de Microlearning.

    DIRETRIZES DA NARRAÇÃO:
    1. TOM CORPORATIVO: Use sempre a 1ª pessoa do plural ("Nós acessamos", "Em seguida, informamos o título").
    2. O GANCHO: O primeiro passo DEVE ser a abertura da aula, justificando com o CONTEXTO DO MANUAL o porquê de estarmos fazendo isso.
    3. O ENCERRAMENTO: O último passo SEMPRE DEVE ser "concluir_video", onde você faz um micro-resumo do aprendizado.

    ESTRUTURA OBRIGATÓRIA (JSON ESTRITO):
    Retorne a lista de passos contendo a 'acao' ("clique" ou "digitar_e_enter") e a 'narracao_ia'.
    Se a ação for "digitar_e_enter", adicione a chave 'valor_input' com o texto que o usuário digitou.
    NÃO INCLUA a chave 'alvo_semantico', o sistema mesclará automaticamente.

    {
      "metadata": { "id_treinamento": "GERADO_AUTO", "titulo": "TÍTULO", "modulo": "Senior Flow" },
      "passos": [ { "id_passo": 1, "acao": "digitar_e_enter", "valor_input": "Texto", "narracao_ia": "..." } ]
    }
    """

    lista_para_ia = [{"id_passo": i+1, "o_que_o_usuario_fez": passo} for i, passo in enumerate(log_mapeador)]

    prompt_usuario = f"""
    OBJETIVO DA AULA: {objetivo_aula}
    
    BASE DE CONHECIMENTO (RAG): {contexto_rag}

    AÇÕES CAPTURADAS:
    {json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}
    """

    print("⚙️ Estruturando a pedagogia, criando narrações e mesclando com o código...")
    
    resposta = gemini_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_usuario,
        config=types.GenerateContentConfig(
            system_instruction=prompt_sistema,
            response_mime_type="application/json",
            temperature=0.2, 
        ),
    )
    
    try:
        dados_da_ia = json.loads(resposta.text)
        
        roteiro_final = {
            "metadata": dados_da_ia.get("metadata", {"id_treinamento": "GERADO", "titulo": "Treinamento"}),
            "configuracao_gravacao": { "gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural" },
            "passos": []
        }
        
        for passo_ia in dados_da_ia.get("passos", []):
            if passo_ia.get("acao") == "concluir_video":
                roteiro_final["passos"].append(passo_ia)
                continue
                
            idx_mapeador = passo_ia.get("id_passo", 0) - 1
            if 0 <= idx_mapeador < len(log_mapeador):
                passo_mesclado = {
                    "id_passo": passo_ia["id_passo"],
                    "acao": passo_ia["acao"],
                    "alvo_semantico": log_mapeador[idx_mapeador]["alvo_semantico"],
                    "narracao_ia": passo_ia.get("narracao_ia", "")
                }
                if passo_ia.get("acao") == "digitar_e_enter":
                    passo_mesclado["valor_input"] = log_mapeador[idx_mapeador]["valor_digitado"] or "Texto Automático"
                
                roteiro_final["passos"].append(passo_mesclado)
        
        with open("roteiro.json", 'w', encoding='utf-8') as f:
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)

        print("✅ Roteiro JSON Pedagógico gerado e mesclado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao mesclar o JSON: {e}")

# ==============================================================
# 🏁 O MAESTRO (Fluxo Principal)
# ==============================================================
def iniciar_esteira_de_producao():
    print("\n" + "="*50)
    print("🎓 SENIOR SISTEMAS - TRAINING OS (CRIADOR DE AULAS)")
    print("="*50 + "\n")
    
    objetivo = input("🎙️ Olá, Instrutor! Qual é o objetivo do treinamento de hoje?\n> ")
    asyncio.run(capturar_cliques_na_tela())
    
    if not cliques_capturados:
        print("\n❌ Nenhuma ação foi capturada. Operação cancelada.")
        return

    contexto = buscar_contexto_pinecone(objetivo)
    invocar_aura(objetivo, cliques_capturados, contexto)
    
    print("\n" + "="*50)
    decisao = input("🎬 Tudo pronto! Deseja enviar este roteiro para a Ilha de Gravação e Edição agora? (S/N)\n> ")
    
    if decisao.strip().upper() == "S":
        print("🚀 Iniciando o Motor Cinematográfico (main.py)...")
        subprocess.run([sys.executable, "main.py"])
    else:
        print("👍 Tudo bem! O arquivo 'roteiro.json' está salvo.")

if __name__ == "__main__":
    iniciar_esteira_de_producao()
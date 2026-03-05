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
        return "Nenhum contexto adicional de manual disponível."

    print("📚 Consultando o manual da Senior no Pinecone...")
    try:
        pc = Pinecone(api_key=chave_pinecone)
        index = pc.Index(nome_index) 
        
        # O SEU BLOCO RESTAURADO E BLINDADO AQUI
        embedding_response = gemini_client.models.embed_content(
            model="gemini-embedding-001",
            contents=[objetivo_aula]
        )
        vetor_objetivo = embedding_response.embeddings[0].values

        resultado = index.query(
            vector=vetor_objetivo,
            top_k=3,
            include_metadata=True
        )
        
        textos_encontrados = [match['metadata'].get('text', '') for match in resultado['matches'] if 'metadata' in match]
        contexto_final = "\n...\n".join(textos_encontrados)
        
        if contexto_final:
            print("✅ Contexto didático encontrado no manual!")
            return contexto_final
        else:
            return "Nenhum contexto adicional encontrado no banco vetorial."
            
    except Exception as e:
        print(f"⚠️ Aviso no RAG: Não foi possível conectar ao Pinecone ({e}). Usando IA nativa.")
        return "Nenhum contexto adicional."

# ==============================================================
# 👁️ MÓDULO 2: O VASCULHADOR (Captura Silenciosa com Raio-X)
# ==============================================================
async def injetar_radar(page):
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;

        document.addEventListener('mouseover', (e) => {
            if (e.altKey) {
                e.target.setAttribute('data-original-outline', e.target.style.outline || '');
                e.target.style.outline = '3px solid #ff0055';
            }
        }, true);

        document.addEventListener('mouseout', (e) => {
            if (e.target.hasAttribute('data-original-outline')) {
                e.target.style.outline = e.target.getAttribute('data-original-outline');
            }
        }, true);

        document.addEventListener('click', (e) => {
            if (e.altKey) {
                e.preventDefault(); e.stopPropagation();
                
                let el = e.target;
                let tag = el.tagName.toLowerCase();
                let texto = el.innerText ? el.innerText.trim().replace(/\\n/g, ' ') : '';
                let id = el.id || '';
                
                // MÁGICA: O radar agora "sobe" no DOM caçando o ID forte do botão, 
                // caso o usuário clique apenas no texto (span) de dentro.
                let current = el.parentElement;
                for(let i=0; i<4; i++) {
                    if(!id && current && current.id) {
                        id = current.id;
                        break;
                    }
                    if(current) current = current.parentElement;
                }

                let iframeNome = window.name || 'Página Principal';

                const relatorio = { tag: tag, texto_encontrado: texto, id_html: id, iframe: iframeNome };
                window.capturarElemento(JSON.stringify(relatorio));
                
                const originalBg = e.target.style.backgroundColor;
                e.target.style.backgroundColor = '#00ff00';
                setTimeout(() => e.target.style.backgroundColor = originalBg, 300);
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

async def capturar_cliques_na_tela():
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        async def on_capturar_elemento(dados_json):
            dados = json.loads(dados_json)
            # Agora mostramos o ID capturado no terminal para você acompanhar a precisão!
            print(f"🎯 Captura! [ID: {dados['id_html'] or 'Sem ID'}] | [Tag: {dados['tag']}] | [Texto: {dados['texto_encontrado'][:15]}]")
            
            alvo = {"primeiro": True}
            if dados['iframe'] != 'Página Principal': alvo["dentro_do_iframe"] = dados["iframe"]
            
            if dados['id_html']: 
                alvo["seletor"] = f"#{dados['id_html']}"
            elif dados['texto_encontrado']: 
                # Usa combinação de TAG + Texto para evitar os "24 elementos invisíveis"
                alvo["seletor"] = dados["tag"]
                alvo["com_texto"] = dados["texto_encontrado"]
                alvo["pegar_pai"] = True
            else: 
                alvo["seletor"] = dados["tag"]
                
            cliques_capturados.append(alvo)

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
        await page.wait_for_load_state("domcontentloaded")
        
        print("\n" + "🚀"*10)
        print("TELA PRONTA! O Mapeador está ativo.")
        print("👉 Navegue livremente. SEGURE A TECLA 'ALT' e clique.")
        print("👉 FECHE O NAVEGADOR no 'X' para continuar.")
        print("🚀"*10 + "\n")

        try:
            while True:
                if page.is_closed(): break
                await injetar_radar(page)
                await asyncio.sleep(2)
        except Exception:
            pass 

# ==============================================================
# 🪄 MÓDULO 3: AURA (Decoupled - Gera apenas Narração)
# ==============================================================
def invocar_aura(objetivo_aula, log_mapeador, contexto_rag):
    print("\n🧠 Acordando a Aura (Diretora de Cena da Blaze Code)...")
    
    prompt_sistema = """
    Você é a Aura, a IA de Design Instrucional da Blaze Code.
    Sua única tarefa é gerar a narração didática e identificar a ação de cada passo.
    
    REGRAS DA NARRAÇÃO (narracao_ia):
    1. Proibido usar imperativo. Use a 1ª pessoa do plural (Nós acessamos, Nós clicamos).
    2. Use o CONTEXTO DO RAG para explicar o PORQUÊ das ações (ex: tempos de fila, regras de negócio).

    REGRAS DA AÇÃO (acao):
    Use apenas: "clique", "duplo_clique", "clique_direito", "digitar_e_enter" ou "aguardar_carregamento".

    ESTRUTURA OBRIGATÓRIA DO RETORNO (JSON ESTRITO):
    Você DEVE retornar um array de passos EXATAMENTE com o mesmo número de itens do log enviado.
    NÃO inclua a chave 'alvo_semantico' no seu retorno. O sistema fará a mesclagem depois.
    Adicione um ÚLTIMO passo extra com a "acao": "concluir_video".

    {
      "metadata": { "id_treinamento": "GERADO_AUTO", "titulo": "TÍTULO AQUI", "modulo": "Senior Flow" },
      "passos": [
        { "id_passo": 1, "acao": "clique", "narracao_ia": "..." }
      ]
    }
    """

    lista_para_ia = [{"id_passo": i+1, "o_que_o_usuario_fez": alvo} for i, alvo in enumerate(log_mapeador)]

    prompt_usuario = f"""
    OBJETIVO DA AULA: {objetivo_aula}
    
    CONTEXTO DO MANUAL (RAG):
    {contexto_rag}

    CLIQUES DO USUÁRIO (Crie um passo narrado para cada um destes {len(log_mapeador)} itens):
    {json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}
    """

    print("⚙️ Criando as narrações e mesclando com o código fonte...")
    
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
                    "alvo_semantico": log_mapeador[idx_mapeador],
                    "narracao_ia": passo_ia.get("narracao_ia", "")
                }
                roteiro_final["passos"].append(passo_mesclado)
        
        with open("roteiro.json", 'w', encoding='utf-8') as f:
            json.dump(roteiro_final, f, indent=2, ensure_ascii=False)

        print("✅ Roteiro JSON gerado e mesclado com sucesso!")
        
    except Exception as e:
        print(f"❌ Erro ao mesclar o JSON: {e}")

# ==============================================================
# 🏁 O MAESTRO (Fluxo Principal)
# ==============================================================
def iniciar_esteira_de_producao():
    print("\n" + "="*50)
    print("🎓 BLAZE CODE - TRAINING OS (CRIADOR DE AULAS)")
    print("="*50 + "\n")
    
    objetivo = input("🎙️ Olá, Instrutor! Qual é o objetivo do treinamento de hoje?\n> ")
    
    asyncio.run(capturar_cliques_na_tela())
    
    if not cliques_capturados:
        print("\n❌ Nenhum clique foi capturado com o ALT. Operação cancelada.")
        return

    contexto = buscar_contexto_pinecone(objetivo)
    invocar_aura(objetivo, cliques_capturados, contexto)
    
    print("\n" + "="*50)
    decisao = input("🎬 Tudo pronto! Deseja enviar este roteiro para a Ilha de Gravação e Edição agora? (S/N)\n> ")
    
    if decisao.strip().upper() == "S":
        print("🚀 Iniciando o Motor Cinematográfico (main.py) no mesmo ambiente virtual...")
        subprocess.run([sys.executable, "main.py"])
    else:
        print("👍 Tudo bem! O arquivo 'roteiro.json' está salvo.")

if __name__ == "__main__":
    iniciar_esteira_de_producao()
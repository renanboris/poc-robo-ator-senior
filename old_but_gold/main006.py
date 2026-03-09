import asyncio
import os
import json
import edge_tts
import pygame
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

pygame.mixer.init()
pygame.mixer.set_num_channels(2)

# ==============================================================
# 🛡️ FUNÇÃO ANTI-CONGELAMENTO
# ==============================================================
async def safe_evaluate(target, script, *args, timeout=2.0):
    try:
        await asyncio.wait_for(target.evaluate(script, *args), timeout=timeout)
        return True
    except Exception:
        return False

# ==============================================================
# 🎙️ MOTOR DE ÁUDIO IA (TEXT-TO-SPEECH)
# ==============================================================
async def gerar_e_tocar_audio(texto, id_passo, id_treinamento, voz="pt-BR-FranciscaNeural"):
    pasta_audio = os.path.join("audios_gerados", id_treinamento)
    os.makedirs(pasta_audio, exist_ok=True)
    
    arquivo_mp3 = os.path.join(pasta_audio, f"passo_{id_passo}.mp3")
    
    comunicador = edge_tts.Communicate(texto, voz)
    await comunicador.save(arquivo_mp3)
    
    som_voz = pygame.mixer.Sound(arquivo_mp3)
    canal_voz = pygame.mixer.Channel(1)
    canal_voz.play(som_voz)

def aguardar_audio_terminar():
    canal_voz = pygame.mixer.Channel(1)
    while canal_voz.get_busy():
        pygame.time.Clock().tick(10)

# ==============================================================
# 🧠 RESOLVEDOR SEMÂNTICO
# ==============================================================
async def resolver_alvo_semantico(page, alvo):
    def construir_locator(contexto):
        if "role" in alvo:
            loc = contexto.get_by_role(alvo["role"], name=alvo.get("nome"))
        elif "placeholder" in alvo:
            loc = contexto.get_by_placeholder(alvo["placeholder"], exact=False)
        elif "seletor" in alvo:
            kwargs = {}
            if "com_texto" in alvo:
                kwargs["has_text"] = alvo["com_texto"]
            loc = contexto.locator(alvo["seletor"], **kwargs)
        elif "texto_contem" in alvo:
            loc = contexto.get_by_text(alvo["texto_contem"], exact=False) 
        elif "texto_esperado" in alvo:
            loc = contexto.get_by_text(alvo["texto_esperado"], exact=True)
        else:
            raise ValueError(f"Alvo inválido: {alvo}")

        if alvo.get("pegar_pai"):
            loc = loc.locator("..")
        return loc

    if "dentro_do_iframe" in alvo:
        nome_frame = alvo["dentro_do_iframe"]
        loc_iframe = construir_locator(page.frame_locator(f'iframe[name="{nome_frame}"]'))
        loc_main = construir_locator(page)
        loc_final = loc_iframe.or_(loc_main)
    else:
        loc_final = construir_locator(page)

    if alvo.get("primeiro"):
        for _ in range(20): 
            try:
                count = await loc_final.count()
                for i in range(count):
                    nth_loc = loc_final.nth(i)
                    if await nth_loc.is_visible():
                        return nth_loc
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return loc_final.first
        
    return loc_final

# ==============================================================
# 🎬 MOTOR DE GRAVAÇÃO, EFEITOS E LEGENDAS
# ==============================================================
async def exibir_legenda_cinema(page, texto):
    script = f"""(texto) => {{
        let existing = document.getElementById('blaze-video-subtitle');
        if (existing) existing.remove();

        const sub = document.createElement('div');
        sub.id = 'blaze-video-subtitle';
        sub.style = `
            position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px);
            color: #ffffff; padding: 15px 35px; border-radius: 50px;
            font-family: 'Segoe UI', sans-serif; font-size: 20px; font-weight: 500;
            text-align: center; max-width: 75%; z-index: 999999;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-bottom: 3px solid #2596be;
            opacity: 0; transition: opacity 0.5s ease;
        `;
        sub.innerHTML = texto;
        document.body.appendChild(sub);
        
        setTimeout(() => sub.style.opacity = '1', 50);
    }}"""
    await safe_evaluate(page, script, texto, timeout=3.0)

async def remover_legenda(page):
    script = "() => { let e = document.getElementById('blaze-video-subtitle'); if(e) e.remove(); }"
    await safe_evaluate(page, script, timeout=1.5)

# 🚀 AGORA SUPORTA 3 TIPOS DE CLIQUE: Esquerdo, Direito e Duplo!
async def holofote_e_clique(locator, cor_neon="#2596be", tipo_clique="esquerdo"):
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    await asyncio.sleep(0.5)
    
    await safe_evaluate(locator, f"el => el.style.outline = '4px solid {cor_neon}'")
    await safe_evaluate(locator, f"el => el.style.boxShadow = '0 0 25px {cor_neon}'")
    
    aguardar_audio_terminar()
    await asyncio.sleep(0.3)
    
    await safe_evaluate(locator, "el => el.style.outline = ''")
    await safe_evaluate(locator, "el => el.style.boxShadow = ''")
        
    if tipo_clique == "duplo":
        await locator.dblclick()
    elif tipo_clique == "direito":
        await locator.click(button="right")
    else:
        await locator.click()

async def exibir_encerramento_cinema(page):
    script = """() => {
        return new Promise((resolve) => {
            const renderUI = () => {
                const overlay = document.createElement('div');
                overlay.style = `
                    position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                    background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(12px);
                    display: flex; flex-direction: column; align-items: center; justify-content: center;
                    z-index: 9999999; opacity: 0; transition: opacity 1s ease;
                `;

                overlay.innerHTML = `
                    <lottie-player 
                        src="https://lottie.host/76846e87-566d-49b8-b3d0-90a6290d22ec/5sys94coTA.json" 
                        background="transparent" 
                        speed="1" 
                        style="width: 250px; height: 250px;" 
                        autoplay>
                    </lottie-player>
                    <h1 style="margin-top: -10px; color: #ffffff; font-size: 38px; font-family: sans-serif; font-weight: bold; text-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                        Treinamento Concluído
                    </h1>
                `;
                document.body.appendChild(overlay);
                setTimeout(() => overlay.style.opacity = '1', 50);
                resolve(true); 
            };

            if (!document.querySelector('script[src*="lottie-player"]')) {
                const script = document.createElement('script');
                script.src = 'https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js';
                script.onload = renderUI; 
                script.onerror = renderUI; 
                document.head.appendChild(script);
            } else {
                renderUI();
            }
        });
    }"""
    for tentativa in range(3):
        sucesso = await safe_evaluate(page, script, timeout=5.0)
        if sucesso:
            return
        await asyncio.sleep(1.0)

# ==============================================================
# 🤖 INTERPRETADOR PRINCIPAL
# ==============================================================
async def executar_roteiro(caminho_json):
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("❌ ERRO: Verifique as credenciais no .env")
        return

    with open(caminho_json, 'r', encoding='utf-8') as f:
        roteiro = json.load(f)

    meta = roteiro["metadata"]
    id_treino = meta["id_treinamento"]
    cfg = roteiro["configuracao_gravacao"]
    voz_escolhida = cfg.get("voz_ia", "pt-BR-FranciscaNeural")

    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.play(loops=-1)

    pasta_video = cfg.get("pasta_destino", "videos_gerados")
    os.makedirs(pasta_video, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(
            no_viewport=True,
            record_video_dir=pasta_video if cfg["gravar_video"] else None,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        print("🔄 Realizando Login...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
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
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(7.0) 
        await page.keyboard.press("Escape")
        await asyncio.sleep(0.3)
        await page.keyboard.press("Escape")

        print("\n🎬 --- GRAVANDO VÍDEO COM NARRAÇÃO --- 🎬\n")
        
        for passo in roteiro["passos"]:
            acao = passo["acao"]
            texto_ia = passo.get('narracao_ia', '')
            
            print(f"▶️ Passo {passo['id_passo']} | 🎙️ Voz: '{texto_ia}'")
            
            if acao == "concluir_video":
                await exibir_encerramento_cinema(page)
                await gerar_e_tocar_audio(texto_ia, passo['id_passo'], id_treino, voz=voz_escolhida)
                aguardar_audio_terminar()
                await asyncio.sleep(3.0)
                break 

            await exibir_legenda_cinema(page, texto_ia)
            await gerar_e_tocar_audio(texto_ia, passo['id_passo'], id_treino, voz=voz_escolhida)
            
            alvo = passo.get("alvo_semantico")
            if alvo:
                locator = await resolver_alvo_semantico(page, alvo)

            if acao == "clique":
                await locator.wait_for(state="visible", timeout=10000)
                await holofote_e_clique(locator, tipo_clique="esquerdo")
                
            elif acao == "duplo_clique":
                await locator.wait_for(state="visible", timeout=10000)
                await holofote_e_clique(locator, tipo_clique="duplo")
                
            # 🚀 NOVA AÇÃO: CLIQUE DIREITO DO MOUSE!
            elif acao == "clique_direito":
                await locator.wait_for(state="visible", timeout=10000)
                await holofote_e_clique(locator, tipo_clique="direito")
            
            elif acao == "aguardar_carregamento":
                aguardar_audio_terminar()
                tempo = passo.get("tempo_espera", 3000)
                await asyncio.sleep(tempo / 1000.0)
                
            elif acao == "digitar_e_enter":
                await locator.wait_for(state="visible", timeout=10000)
                await locator.scroll_into_view_if_needed()
                await locator.hover()
                
                await safe_evaluate(locator, """el => {
                    let parent = el.parentElement;
                    for(let i=0; i<3; i++) {
                        if(parent && window.getComputedStyle(parent).overflow === 'hidden') {
                            parent.style.overflow = 'visible';
                            parent.setAttribute('data-neon-fixed', 'true');
                        }
                        if(parent) parent = parent.parentElement;
                    }
                    el.style.outline = '4px solid #2596be';
                    el.style.boxShadow = '0 0 25px #2596be';
                }""")
                
                aguardar_audio_terminar()
                
                await locator.click()
                await asyncio.sleep(0.5)
                
                await locator.fill("")
                await locator.type(passo["valor_input"], delay=60)
                
                await asyncio.sleep(0.5)
                await locator.press("Enter")
                
                await asyncio.sleep(2.0)
                
                await safe_evaluate(locator, """el => {
                    el.style.outline = '';
                    el.style.boxShadow = '';
                    let parent = el.parentElement;
                    for(let i=0; i<3; i++) {
                        if(parent && parent.hasAttribute('data-neon-fixed')) {
                            parent.style.overflow = '';
                            parent.removeAttribute('data-neon-fixed');
                        }
                        if(parent) parent = parent.parentElement;
                    }
                }""")

            await remover_legenda(page)
            await asyncio.sleep(0.5)

        pygame.mixer.music.stop()

        print("\n✅ Treinamento gravado com sucesso!")
        await asyncio.sleep(1.0)
        await page.close()
        await context.close()
        await browser.close()

if __name__ == "__main__":
    asyncio.run(executar_roteiro("roteiro.json"))
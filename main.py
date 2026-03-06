import asyncio
import os
import json
import time
import edge_tts
import pygame
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# ==========================================
# 🔧 CORREÇÃO PARA PYTHON 3.13 + MOVIEPY
# ==========================================
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip, concatenate_videoclips
import moviepy.audio.fx.all as afx

load_dotenv()

pygame.mixer.init()
pygame.mixer.set_num_channels(2)

# ==============================================================
# 🛡️ FUNÇÃO ANTI-CONGELAMENTO
# ==============================================================
async def safe_evaluate(target, script, arg=None, timeout=3.0):
    try:
        if arg is not None:
            await asyncio.wait_for(target.evaluate(script, arg), timeout=timeout)
        else:
            await asyncio.wait_for(target.evaluate(script), timeout=timeout)
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
    
    return arquivo_mp3 

def aguardar_audio_terminar():
    canal_voz = pygame.mixer.Channel(1)
    while canal_voz.get_busy():
        pygame.time.Clock().tick(10)

# ==============================================================
# 🧠 RESOLVEDOR SEMÂNTICO
# ==============================================================
def resolver_alvo_semantico(contexto_pagina, alvo):
    contexto = contexto_pagina
    if "dentro_do_iframe" in alvo:
        contexto = contexto_pagina.frame_locator(f"iframe[name='{alvo['dentro_do_iframe']}']")
        
    if "seletor" in alvo:
        kwargs = {}
        if "com_texto" in alvo: kwargs["has_text"] = alvo["com_texto"]
        elif "texto_esperado" in alvo: kwargs["has_text"] = alvo["texto_esperado"]
        loc = contexto.locator(alvo["seletor"], **kwargs)
    elif "texto_esperado" in alvo:
        loc = contexto.get_by_text(alvo["texto_esperado"], exact=False)
    else:
        raise ValueError(f"Alvo semântico inválido: {alvo}")
        
    if alvo.get("pegar_pai"): loc = loc.locator("..")
    if alvo.get("primeiro"): loc = loc.first
    return loc

# ==============================================================
# 🎬 MOTOR DE GRAVAÇÃO, EFEITOS E LEGENDAS
# ==============================================================
async def exibir_legenda_cinema(page, texto):
    script = """(texto) => {
        let existing = document.getElementById('senior-video-subtitle');
        if (existing) existing.remove();

        const sub = document.createElement('div');
        sub.id = 'senior-video-subtitle';
        sub.style = `
            position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px);
            color: #ffffff; padding: 15px 35px; border-radius: 50px;
            font-family: 'Segoe UI', sans-serif; font-size: 22px; font-weight: 500;
            text-align: center; max-width: 75%; z-index: 2147483647; line-height: 1.4;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5); border-bottom: 3px solid #009999;
            opacity: 0; transition: opacity 0.5s ease;
        `;
        sub.innerHTML = texto;
        document.documentElement.appendChild(sub);
        
        setTimeout(() => sub.style.opacity = '1', 50);
    }"""
    await safe_evaluate(page, script, arg=texto, timeout=3.0)

async def remover_legenda(page):
    script = "() => { let e = document.getElementById('senior-video-subtitle'); if(e) e.remove(); }"
    await safe_evaluate(page, script, timeout=1.5)

async def holofote_e_clique(locator, cor_neon="#009999", tipo_clique="esquerdo"):
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    await asyncio.sleep(0.5)
    
    await safe_evaluate(locator, f"el => el.style.transition = 'all 0.3s ease'")
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
                    z-index: 2147483647; opacity: 0; transition: opacity 1s ease;
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
                document.documentElement.appendChild(overlay);
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
        if sucesso: return
        await asyncio.sleep(1.0)


# ==============================================================
# 🎛️ MOTOR DE PÓS-PRODUÇÃO (A ILHA DE EDIÇÃO AUTOMÁTICA)
# ==============================================================
def renderizar_video_final(caminho_webm, timeline, id_treino, tempo_corte):
    print("\n" + "="*50)
    print("🎬 INICIANDO PÓS-PRODUÇÃO CINEMATOGRÁFICA...")
    print("="*50)
    
    try:
        # 1. A TESOURA: Corta os minutos/segundos de login do vídeo bruto
        print(f"✂️ Cortando os primeiros {tempo_corte:.1f} segundos (Login)...")
        video = VideoFileClip(caminho_webm).subclip(tempo_corte)
        clipes_de_audio = []

        # 2. A MOLDURA: Aplica o Overlay Corporativo com Redimensionamento
        if os.path.exists("overlay.png"):
            print("🖼️ Aplicando Overlay corporativo e ajustando margens...")
            overlay = ImageClip("overlay.png").set_duration(video.duration)
            
            # -----------------------------------------------------------------
            # 📐 AJUSTE DE MARGEM AQUI!
            # O valor 0.85 significa que o vídeo ocupará 85% do tamanho da tela.
            # Se a sua janela transparente for menor, diminua (ex: 0.75).
            # Se for maior, aumente (ex: 0.90).
            # -----------------------------------------------------------------
            fator_de_escala = 0.85 
            
            # Encolhe o vídeo e coloca exatamente no centro
            video_redimensionado = video.resize(fator_de_escala).set_position('center')
            
            # Cria um canvas de 1920x1080. 
            # Coloca o vídeo redimensionado no fundo e o overlay (com buraco transparente) por cima.
            video = CompositeVideoClip([video_redimensionado, overlay], size=(1920, 1080))

        # 3. MÚSICA DE FUNDO
        if os.path.exists("trilha.mp3"):
            print("🎵 Injetando trilha sonora e balanceando volume...")
            bgm = AudioFileClip("trilha.mp3").fx(afx.volumex, 0.08).fx(afx.audio_loop, duration=video.duration)
            clipes_de_audio.append(bgm)

        # 4. VOZES
        print("🎙️ Sincronizando falas da professora na linha do tempo...")
        for item in timeline:
            if os.path.exists(item["arquivo"]):
                voz = AudioFileClip(item["arquivo"]).set_start(item["inicio"])
                clipes_de_audio.append(voz)

        # 5. RENDERIZAÇÃO
        print("⚙️ Renderizando arquivo MP4 Final. Isso pode levar alguns minutos...")
        audio_final = CompositeAudioClip(clipes_de_audio)
        video = video.set_audio(audio_final)

        video_final = video
        if os.path.exists("outro.mp4"):
            print("✨ Inserindo Lottie de encerramento...")
            outro = VideoFileClip("outro.mp4").resize(video.size).set_fps(video.fps) 
            video_final = concatenate_videoclips([video, outro], method="compose")

        pasta_saida = "videos_prontos"
        os.makedirs(pasta_saida, exist_ok=True)
        caminho_final = os.path.join(pasta_saida, f"{id_treino}_FINALIZADO.mp4")

        video_final.write_videofile(
            caminho_final, 
            codec="libx264", 
            audio_codec="aac", 
            fps=24, 
            preset="ultrafast", 
            logger="bar"
        )
        
        video.close()
        video_final.close()
        
        print("\n" + "🚀"*15)
        print(f"✅ VÍDEO PRONTO PARA O LMS GERADO EM:\n👉 {caminho_final}")
        print("🚀"*15 + "\n")
        
    except Exception as e:
        print(f"❌ Erro na Pós-Produção: {e}")


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
    id_treino = meta.get("id_treinamento", "TREINAMENTO")
    cfg = roteiro["configuracao_gravacao"]
    voz_escolhida = cfg.get("voz_ia", "pt-BR-FranciscaNeural")

    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.play(loops=-1)

    pasta_video = cfg.get("pasta_destino", "videos_gerados")
    os.makedirs(pasta_video, exist_ok=True)

    timeline_audios = []
    caminho_video_webm = None
    tempo_corte_segundos = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        tempo_inicio_contexto = time.time()
        
        context = await browser.new_context(
            no_viewport=True,
            record_video_dir=pasta_video if cfg["gravar_video"] else None,
            record_video_size={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        print("🔄 Realizando Login na Senior X...")
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

        tempo_inicio_gravacao = time.time()
        tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto

        print("\n🎬 --- GRAVANDO VÍDEO E SINCRONIZANDO FALAS --- 🎬\n")
        
        for passo in roteiro["passos"]:
            acao = passo["acao"]
            texto_ia = passo.get('narracao_ia', '')
            
            print(f"▶️ Passo {passo['id_passo']} | 🎙️ Voz: '{texto_ia[:50]}...'")
            
            if acao == "concluir_video":
                await exibir_encerramento_cinema(page)
                instante_atual = time.time() - tempo_inicio_gravacao
                caminho_mp3 = await gerar_e_tocar_audio(texto_ia, passo['id_passo'], id_treino, voz=voz_escolhida)
                timeline_audios.append({"arquivo": caminho_mp3, "inicio": instante_atual})
                
                aguardar_audio_terminar()
                await asyncio.sleep(3.0)
                break 

            await exibir_legenda_cinema(page, texto_ia)
            
            instante_atual = time.time() - tempo_inicio_gravacao
            caminho_mp3 = await gerar_e_tocar_audio(texto_ia, passo['id_passo'], id_treino, voz=voz_escolhida)
            timeline_audios.append({"arquivo": caminho_mp3, "inicio": instante_atual})
            
            alvo = passo.get("alvo_semantico")
            if not alvo: continue
            
            locator = resolver_alvo_semantico(page, alvo)

            try:
                await locator.wait_for(state="visible", timeout=10000)
            except Exception:
                print(f"   ⚠️ Timeout no seletor primário. Tentando auto-repair...")
                if acao == "digitar_e_enter":
                    try:
                        contexto_frame = page.frame_locator(f"iframe[name='{alvo['dentro_do_iframe']}']") if "dentro_do_iframe" in alvo else page
                        locator = contexto_frame.get_by_text("Nova pasta", exact=False).first
                        await locator.wait_for(state="visible", timeout=4000)
                    except: pass

            if acao == "clique":
                await holofote_e_clique(locator, tipo_clique="esquerdo")
                
            elif acao == "duplo_clique":
                await holofote_e_clique(locator, tipo_clique="duplo")
                
            elif acao == "clique_direito":
                await holofote_e_clique(locator, tipo_clique="direito")
            
            elif acao == "aguardar_carregamento":
                aguardar_audio_terminar()
                tempo = passo.get("tempo_espera", 3000)
                await asyncio.sleep(tempo / 1000.0)
                
            elif acao == "digitar_e_enter":
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
                    el.style.transition = 'all 0.3s ease';
                    el.style.outline = '4px solid #009999';
                    el.style.boxShadow = '0 0 25px #009999';
                }""")
                
                aguardar_audio_terminar()
                
                await locator.click()
                await asyncio.sleep(0.5)
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                await page.keyboard.type(passo.get("valor_input", ""), delay=50)
                await asyncio.sleep(0.5)
                await page.keyboard.press("Enter")
                
                await asyncio.sleep(1.0)
                
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
        print("\n✅ Gravação Finalizada! Fechando navegador...")
        
        if cfg["gravar_video"]:
            caminho_video_webm = await page.video.path()
            
        await asyncio.sleep(1.0)
        await page.close()
        await context.close()
        await browser.close()
        await asyncio.sleep(1.0)

    print("\n" + "="*50)
    decisao = input("🤔 A gravação visual ficou boa? Deseja enviar para a renderização final no MoviePy? (S/N)\n> ")
    if decisao.strip().upper() == 'S':
        if cfg["gravar_video"] and caminho_video_webm:
            renderizar_video_final(caminho_video_webm, timeline_audios, id_treino, tempo_corte_segundos)
    else:
        print("🛑 Renderização cancelada.")

if __name__ == "__main__":
    asyncio.run(executar_roteiro("roteiro.json"))
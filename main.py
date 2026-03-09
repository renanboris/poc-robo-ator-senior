import asyncio
import os
import json
import time
import edge_tts
import pygame
import logging
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from vision_engine import encontrar_e_clicar

import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
logging.getLogger('playwright').setLevel(logging.CRITICAL)

from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, ImageClip
import moviepy.audio.fx as afx

load_dotenv()
pygame.mixer.init()
pygame.mixer.set_num_channels(2)

async def safe_evaluate(target, script, arg=None, timeout=3.0):
    try:
        if arg is not None:
            coro = target.evaluate(script, arg)
        else:
            coro = target.evaluate(script)
        await asyncio.wait_for(coro, timeout=timeout)
        return True
    except Exception:
        return False

async def gerar_audio(texto, id_unico, id_treinamento, voz="pt-BR-FranciscaNeural"):
    if not texto or not texto.strip(): 
        return None
        
    pasta_audio = os.path.join("audios_gerados", id_treinamento)
    os.makedirs(pasta_audio, exist_ok=True)
    arquivo_mp3 = os.path.join(pasta_audio, f"audio_{id_unico}.mp3")
    
    if not os.path.exists(arquivo_mp3):
        await edge_tts.Communicate(texto, voz, rate="-12%").save(arquivo_mp3)
        
    return arquivo_mp3 

def iniciar_reproducao_audio(arquivo_mp3):
    if arquivo_mp3 and os.path.exists(arquivo_mp3):
        som_voz = pygame.mixer.Sound(arquivo_mp3)
        pygame.mixer.Channel(1).play(som_voz)

async def aguardar_audio_terminar():
    while pygame.mixer.Channel(1).get_busy(): 
        await asyncio.sleep(0.1) 

async def exibir_legenda_cinema(page, texto):
    if not texto or not texto.strip(): 
        return
        
    script = f"""(texto) => {{
        let existing = document.getElementById('senior-video-subtitle');
        if (existing) existing.remove();
        
        const sub = document.createElement('div');
        sub.id = 'senior-video-subtitle';
        sub.style = `
            position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); 
            background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(8px); color: #ffffff; 
            padding: 15px 35px; border-radius: 50px; font-family: 'Segoe UI', sans-serif; 
            font-size: 22px; font-weight: 500; text-align: center; max-width: 75%; 
            z-index: 2147483647; line-height: 1.4; box-shadow: 0 10px 30px rgba(0,0,0,0.5); 
            border-bottom: 3px solid #009999; opacity: 0; transition: opacity 0.5s ease;
        `;
        sub.innerHTML = texto; 
        document.documentElement.appendChild(sub);
        
        setTimeout(() => sub.style.opacity = '1', 50);
    }}"""
    await safe_evaluate(page, script, arg=texto)

async def remover_legenda(page):
    await safe_evaluate(page, "() => { let e = document.getElementById('senior-video-subtitle'); if(e) e.remove(); }")

def renderizar_video_final(caminho_webm, timeline, id_treino, tempo_corte):
    print("\n" + "="*50 + "\n🎬 INICIANDO PÓS-PRODUÇÃO CINEMATOGRÁFICA...\n" + "="*50)
    try:
        # A correção vital para impedir falhas de diretório no final do processo
        os.makedirs("videos_prontos", exist_ok=True) 
        
        video = VideoFileClip(caminho_webm).subclipped(tempo_corte)
        clipes_de_audio = []
        
        if os.path.exists("overlay.png"):
            video_redimensionado = video.resized(0.85).with_position('center')
            overlay = ImageClip("overlay.png").with_duration(video.duration)
            video = CompositeVideoClip([video_redimensionado, overlay], size=(1920, 1080))
            
        if os.path.exists("trilha.mp3"):
            bgm = AudioFileClip("trilha.mp3").with_effects([afx.MultiplyVolume(0.08), afx.AudioLoop(duration=video.duration)])
            clipes_de_audio.append(bgm)
            
        for item in timeline:
            if os.path.exists(item["arquivo"]): 
                clipes_de_audio.append(AudioFileClip(item["arquivo"]).with_start(item["inicio"]))
        
        if clipes_de_audio:
            video = video.with_audio(CompositeAudioClip(clipes_de_audio))
            
        caminho_final = os.path.join("videos_prontos", f"{id_treino}_FINALIZADO.mp4")
        video.write_videofile(caminho_final, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast", logger=None)
        video.close()
        
        print(f"\n🚀 VÍDEO PRONTO EM:\n👉 {caminho_final}")
    except Exception as e: 
        print(f"❌ Erro na Pós-Produção: {e}")

async def executar_roteiro(caminho_json):
    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")
    
    if not usuario or not senha: 
        print("❌ ERRO: Verifique as credenciais no .env")
        return

    with open(caminho_json, 'r', encoding='utf-8') as f: 
        roteiro = json.load(f)
        
    id_treino = roteiro.get("metadata", {}).get("id_treinamento", "TREINAMENTO")
    cfg = roteiro.get("configuracao_gravacao", {"gravar_video": True, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"})
    voz_escolhida = cfg.get("voz_ia", "pt-BR-FranciscaNeural")

    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.play(loops=-1)

    os.makedirs(cfg.get("pasta_destino", "videos_gerados"), exist_ok=True)
    timeline_audios = []
    caminho_video_webm = None
    tempo_corte_segundos = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        tempo_inicio_contexto = time.time()
        
        context = await browser.new_context(
            no_viewport=True, 
            record_video_dir=cfg.get("pasta_destino", "videos_gerados") if cfg.get("gravar_video", True) else None, 
            record_video_size={"width": 1920, "height": 1080}
        )
        page = await context.new_page()

        try:
            print("🔄 Realizando Login na Senior X...")
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")
            
            await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
            await page.get_by_role("button", name="Próximo").click()
            await asyncio.sleep(0.5)
            await page.keyboard.press("Escape")
            
            await page.locator("input[type='password']").fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            
            await page.wait_for_load_state("load")
            await asyncio.sleep(7.0)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")

            # Apenas define o tempo de corte se o login for bem sucedido e não explodir
            tempo_inicio_gravacao = time.time()
            tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto

            print("\n🎬 --- GRAVANDO VÍDEO (MOTOR VISION-FIRST) --- 🎬\n")
            
            for passo in roteiro.get("passos", []):
                id_p = passo.get('id_passo', 'Fim')
                
                ancora = passo.get("pedagogia", {}).get("ancora", "")
                if ancora:
                    await exibir_legenda_cinema(page, ancora)
                    mp3 = await gerar_audio(ancora, f"{id_p}_ancora", id_treino, voz_escolhida)
                    if mp3: 
                        t_atual = time.time() - tempo_inicio_gravacao
                        iniciar_reproducao_audio(mp3)
                        timeline_audios.append({"arquivo": mp3, "inicio": t_atual})
                        
                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.5)

                if passo.get('is_conclusao', False) or (not passo.get("acoes_tecnicas") and passo.get('id_passo') == roteiro.get("passos")[-1].get('id_passo')):
                    await asyncio.sleep(3.0)
                    break 

                for i, acao_tec in enumerate(passo.get("acoes_tecnicas", [])):
                    micro_voz = acao_tec.get("micro_narracao", "")
                    if micro_voz:
                        await exibir_legenda_cinema(page, micro_voz)
                        mp3 = await gerar_audio(micro_voz, f"{id_p}_micro_{i}", id_treino, voz_escolhida)
                        if mp3: 
                            t_atual = time.time() - tempo_inicio_gravacao
                            iniciar_reproducao_audio(mp3)
                            timeline_audios.append({"arquivo": mp3, "inicio": t_atual})

                    if acao_tec.get("acao") != "concluir_video":
                        await encontrar_e_clicar(page, acao_tec)

                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.5)
                    
        except Exception as e:
            print(f"\n⚠️ Execução interrompida de forma inesperada: {e}")
            
        finally:
            pygame.mixer.music.stop()
            print("\n✅ Finalizando recursos do navegador...")
            try:
                if cfg.get("gravar_video", True) and not page.is_closed():
                    caminho_video_webm = await page.video.path()
                await asyncio.sleep(1.0)
                if not page.is_closed(): 
                    await page.close()
                await context.close()
                await browser.close()
            except Exception as fechar_erro:
                logging.debug(f"Erro silencioso ao fechar o navegador: {fechar_erro}")

    if caminho_video_webm and tempo_corte_segundos > 0:
        decisao = input("\n🤔 A gravação visual ficou boa? Enviar para MoviePy? (S/N)\n> ")
        if decisao.strip().upper() == 'S':
            renderizar_video_final(caminho_video_webm, timeline_audios, id_treino, tempo_corte_segundos)

if __name__ == "__main__": 
    asyncio.run(executar_roteiro("roteiro.json"))
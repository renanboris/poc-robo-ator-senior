import sys
import asyncio
import os
import json
import time
import edge_tts
import pygame
import logging
import hashlib
import re
from dotenv import load_dotenv

# Carrega as variáveis de ambiente (Login e Senha da Senior)
load_dotenv() 

from playwright.async_api import async_playwright
from vision_engine import encontrar_e_clicar

# Ajuste de compatibilidade para o MoviePy com versões mais recentes do Pillow
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

# Configurações de logs e áudio
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
logging.getLogger('playwright').setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import moviepy.audio.fx.all as afx

# Inicialização do mixer de áudio
pygame.mixer.init()
pygame.mixer.set_num_channels(2)

# ==============================================================
# 🛠️ FUNÇÕES AUXILIARES DE NAVEGAÇÃO E ÁUDIO
# ==============================================================

async def safe_evaluate(target, script, arg=None, timeout=3.0):
    """Executa um script no contexto da página com timeout de segurança."""
    try:
        if arg is not None:
            coro = target.evaluate(script, arg)
        else:
            coro = target.evaluate(script)
        await asyncio.wait_for(coro, timeout=timeout)
        return True
    except Exception as e:
        return False

async def gerar_audio(texto, id_unico, id_treinamento, voz="pt-BR-FranciscaNeural"):
    """Gera o arquivo de áudio MP3 utilizando a voz da IA da Microsoft (Edge TTS)."""
    if not texto or not texto.strip():
        return None
        
    nome_seguro_pasta = re.sub(r'[\\/*?:"<>|]', "", id_treinamento).replace(" ", "_")
    pasta_audio = os.path.join("audios_gerados", nome_seguro_pasta)
    os.makedirs(pasta_audio, exist_ok=True)
    
    assinatura = hashlib.md5(texto.encode('utf-8')).hexdigest()[:8]
    arquivo_mp3 = os.path.join(pasta_audio, f"audio_{id_unico}_{assinatura}.mp3")
    
    if not os.path.exists(arquivo_mp3):
        await edge_tts.Communicate(texto, voz, rate="-12%").save(arquivo_mp3)
        
    return arquivo_mp3 

def iniciar_reproducao_audio(arquivo_mp3):
    """Inicia a reprodução do áudio no canal 1 do Pygame."""
    if arquivo_mp3 and os.path.exists(arquivo_mp3):
        som = pygame.mixer.Sound(arquivo_mp3)
        pygame.mixer.Channel(1).play(som)

async def aguardar_audio_terminar():
    """Trava a execução do Playwright até que o áudio termine de ser reproduzido."""
    while pygame.mixer.Channel(1).get_busy():
        await asyncio.sleep(0.1) 

# ==============================================================
# 🎨 ELEMENTOS VISUAIS E CINEMATOGRÁFICOS (UI INJECT)
# ==============================================================

async def atualizar_progress_bar(page, passo_atual, total_passos, nome_aula):
    """Injeta a nova 'Progress Pill' flutuante no canto inferior direito."""
    porcentagem = int((passo_atual / total_passos) * 100)
    
    # Cálculo do anel SVG (Circunferência = 2 * pi * r, com r=10 -> ~62.8)
    dashoffset = 62.8 - (62.8 * porcentagem) / 100
    
    script = f"""() => {{
        let pill = document.getElementById('senior-progress-pill');
        if (!pill) {{
            pill = document.createElement('div');
            pill.id = 'senior-progress-pill';
            pill.style = `
                position: fixed; bottom: 30px; right: 30px; 
                background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); 
                border: 1px solid rgba(255,255,255,0.1); border-radius: 100px; 
                padding: 10px 20px; display: flex; align-items: center; gap: 15px; 
                z-index: 2147483647; font-family: 'Segoe UI', sans-serif; 
                box-shadow: 0 10px 25px rgba(0,0,0,0.5); transition: all 0.3s ease;
            `;
            
            const ringContainer = document.createElement('div');
            ringContainer.style = `position: relative; width: 24px; height: 24px;`;
            ringContainer.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" style="transform: rotate(-90deg);">
                    <circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="3"></circle>
                    <circle id="senior-progress-circle" cx="12" cy="12" r="10" fill="none" stroke="#00e5e5" stroke-width="3" stroke-dasharray="62.8" stroke-dashoffset="62.8" style="transition: stroke-dashoffset 0.8s ease-in-out; stroke-linecap: round;"></circle>
                </svg>
            `;

            const textContainer = document.createElement('div');
            textContainer.style = `display: flex; flex-direction: column; justify-content: center;`;
            textContainer.innerHTML = `
                <div style="color: #94a3b8; font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">{nome_aula}</div>
                <div id="senior-progress-step" style="color: #ffffff; font-size: 13px; font-weight: 500;">Passo {passo_atual} de {total_passos}</div>
            `;

            pill.appendChild(ringContainer);
            pill.appendChild(textContainer);
            document.documentElement.appendChild(pill);
        }}
        
        document.getElementById('senior-progress-circle').style.strokeDashoffset = '{dashoffset}';
        document.getElementById('senior-progress-step').innerText = 'Passo {passo_atual} de {total_passos}';
    }}"""
    await safe_evaluate(page, script)

async def exibir_legenda_cinema(page, texto):
    """Exibe as legendas com design moderno de Glassmorphism na parte inferior."""
    if not texto or not texto.strip():
        return
        
    script = f"""(texto) => {{
        let existing = document.getElementById('senior-video-subtitle');
        if (existing) existing.remove();
        
        const sub = document.createElement('div');
        sub.id = 'senior-video-subtitle';
        sub.style = `
            position: fixed; bottom: 40px; left: 50%; transform: translateX(-50%); 
            background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(8px); color: #ffffff; 
            padding: 12px 30px; border-radius: 50px; font-family: 'Segoe UI', sans-serif; 
            font-size: 20px; font-weight: 500; text-align: center; max-width: 75%; 
            z-index: 2147483647; line-height: 1.4; box-shadow: 0 10px 30px rgba(0,0,0,0.5); 
            border: 1px solid rgba(255,255,255,0.1); opacity: 0; transition: opacity 0.5s ease;
        `;
        sub.innerHTML = texto; 
        document.documentElement.appendChild(sub);
        
        setTimeout(() => sub.style.opacity = '1', 50);
    }}"""
    await safe_evaluate(page, script, arg=texto)

async def remover_legenda(page):
    """Remove a legenda da tela."""
    script = "() => { let e = document.getElementById('senior-video-subtitle'); if(e) e.remove(); }"
    await safe_evaluate(page, script)

async def exibir_encerramento_cinema(page):
    """Mostra a tela de conclusão do treinamento com animação Lottie."""
    script = """() => { return new Promise((resolve) => {
        const renderUI = () => {
            const overlay = document.createElement('div');
            overlay.style = `
                position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; 
                background: rgba(0, 0, 0, 0.85); backdrop-filter: blur(12px); 
                display: flex; flex-direction: column; align-items: center; 
                justify-content: center; z-index: 2147483647; opacity: 0; 
                transition: opacity 1s ease;
            `;
            overlay.innerHTML = `
                <lottie-player src="https://lottie.host/76846e87-566d-49b8-b3d0-90a6290d22ec/5sys94coTA.json" 
                               background="transparent" speed="1" style="width: 250px; height: 250px;" autoplay>
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
            document.head.appendChild(script);
        } else { 
            renderUI(); 
        }
    }); }"""
    await safe_evaluate(page, script, timeout=5.0)

# ==============================================================
# 📝 GERAÇÃO DE LEGENDAS (SRT) E VÍDEO FINAL
# ==============================================================

def formatar_tempo_srt(segundos_float):
    horas = int(segundos_float // 3600)
    minutos = int((segundos_float % 3600) // 60)
    segundos = int(segundos_float % 60)
    milisegundos = int(round((segundos_float - int(segundos_float)) * 1000))
    return f"{horas:02d}:{minutos:02d}:{segundos:02d},{milisegundos:03d}"

def gerar_arquivo_srt(timeline, caminho_srt):
    with open(caminho_srt, 'w', encoding='utf-8') as f:
        for idx, item in enumerate(timeline):
            inicio = formatar_tempo_srt(item["inicio"])
            fim = formatar_tempo_srt(item["fim"])
            texto = item["texto"]
            f.write(f"{idx + 1}\n")
            f.write(f"{inicio} --> {fim}\n")
            f.write(f"{texto}\n\n")

def renderizar_video_final(caminho_webm, timeline, nome_arquivo_base, tempo_corte):
    print("\n🎬 INICIANDO PÓS-PRODUÇÃO...")
    try:
        os.makedirs("videos_prontos", exist_ok=True) 
        video = VideoFileClip(caminho_webm).subclip(tempo_corte)
        clipes_de_audio = []
        
        if os.path.exists("trilha.mp3"):
            bgm = AudioFileClip("trilha.mp3").volumex(0.08)
            bgm = afx.audio_loop(bgm, duration=video.duration)
            clipes_de_audio.append(bgm)
            
        for item in timeline:
            if os.path.exists(item["arquivo"]): 
                voz = AudioFileClip(item["arquivo"]).set_start(item["inicio"])
                clipes_de_audio.append(voz)
        
        if clipes_de_audio: 
            video = video.set_audio(CompositeAudioClip(clipes_de_audio))
            
        caminho_final_mp4 = os.path.join("videos_prontos", f"{nome_arquivo_base}.mp4")
        caminho_final_srt = os.path.join("videos_prontos", f"{nome_arquivo_base}.srt")
        
        video.write_videofile(
            caminho_final_mp4, 
            codec="libx264", 
            audio_codec="aac", 
            fps=24, 
            preset="ultrafast", 
            logger='bar'
        )
        video.close()
        
        gerar_arquivo_srt(timeline, caminho_final_srt)
        print(f"🎉 SUCESSO! Vídeo gerado em: {caminho_final_mp4}")
        
    except Exception as e: 
        print(f"❌ Erro na Pós-Produção: {e}")

# ==============================================================
# 🤖 MOTOR DE EXECUÇÃO (ROBÔ)
# ==============================================================

async def executar_roteiro(caminho_json):
    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")
    
    if not usuario or not senha: 
        print("❌ ERRO: Verifique as credenciais no arquivo .env")
        sys.exit(1)

    with open(caminho_json, 'r', encoding='utf-8') as f: 
        roteiro = json.load(f)
    
    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", "Aula Senior")
    nome_arquivo_base = re.sub(r'[\\/*?:"<>|]', "", nome_aula_raw).replace(" ", "_")
    voz_escolhida = roteiro.get("configuracao_gravacao", {}).get("voz_ia", "pt-BR-FranciscaNeural")

    # Inicia a trilha sonora temporária durante a atuação ao vivo
    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.play(loops=-1)

    timeline_audios = []
    caminho_video_webm = None
    tempo_corte_segundos = -1
    
    passos_lista = roteiro.get("passos", [])
    total_passos = len(passos_lista)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-fullscreen', '--disable-infobars'])
        tempo_inicio_contexto = time.time()
        
        context = await browser.new_context(
            no_viewport=True, 
            record_video_dir="videos_gerados", 
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
            await asyncio.sleep(6.0)
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")

            tempo_inicio_gravacao = time.time()
            tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto

            print("\n🎬 --- GRAVANDO VÍDEO (TELA CHEIA) --- 🎬\n")

            for idx, passo in enumerate(passos_lista):
                id_p = passo.get('id_passo', idx + 1)
                
                # Injeta a pílula animada na tela
                await atualizar_progress_bar(page, idx + 1, total_passos, nome_aula_raw)
                
                ancora = passo.get("pedagogia", {}).get("ancora", "")
                if ancora:
                    await exibir_legenda_cinema(page, ancora)
                    mp3 = await gerar_audio(ancora, f"{id_p}_ancora", nome_arquivo_base, voz_escolhida)
                    
                    if mp3: 
                        t_atual = time.time() - tempo_inicio_gravacao
                        duracao = pygame.mixer.Sound(mp3).get_length()
                        iniciar_reproducao_audio(mp3)
                        timeline_audios.append({
                            "arquivo": mp3, 
                            "inicio": t_atual, 
                            "fim": t_atual + duracao, 
                            "texto": ancora
                        })
                        
                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.5)

                # Verifica se chegou na conclusão
                if passo.get('is_conclusao', False):
                    await exibir_encerramento_cinema(page)
                    await asyncio.sleep(4.0)
                    break 

                # Processa as ações de clique/digitação
                for i, acao_tec in enumerate(passo.get("acoes_tecnicas", [])):
                    if acao_tec.get("acao") == "concluir_video": 
                        continue
                    
                    micro_voz = acao_tec.get("micro_narracao", "")
                    if micro_voz:
                        await exibir_legenda_cinema(page, micro_voz)
                        mp3 = await gerar_audio(micro_voz, f"{id_p}_micro_{i}", nome_arquivo_base, voz_escolhida)
                        
                        if mp3: 
                            t_atual = time.time() - tempo_inicio_gravacao
                            duracao = pygame.mixer.Sound(mp3).get_length()
                            iniciar_reproducao_audio(mp3)
                            timeline_audios.append({
                                "arquivo": mp3, 
                                "inicio": t_atual, 
                                "fim": t_atual + duracao, 
                                "texto": micro_voz
                            })

                    # O Motor de Visão assume o controle do mouse aqui
                    await encontrar_e_clicar(page, acao_tec)
                    
                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.5)
                    
        except Exception as e: 
            # 🔴 MATA O ÁUDIO IMEDIATAMENTE SE O USUÁRIO FECHAR A JANELA
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            logging.error(f"⚠️ Gravação interrompida (Janela fechada ou erro fatal): {e}")
            tempo_corte_segundos = -1 # Flag para não salvar o vídeo corrompido
            
        finally:
            # Segurança dupla para calar o áudio no encerramento
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            
            try:
                if not page.is_closed(): 
                    caminho_video_webm = await page.video.path()
                await asyncio.sleep(1.0)
                
                if not page.is_closed(): 
                    await page.close()
                await context.close()
                await browser.close()
            except Exception: 
                pass
            
            # Limpa o arquivo de vídeo temporário se a gravação foi abortada
            if tempo_corte_segundos == -1 and caminho_video_webm and os.path.exists(caminho_video_webm):
                try: 
                    os.remove(caminho_video_webm)
                except Exception: 
                    pass
                caminho_video_webm = None

    # Salva o arquivo de estado para permitir a renderização posterior pelo Painel Web
    if caminho_video_webm and tempo_corte_segundos > 0:
        caminho_estado = os.path.join("videos_gerados", f"{nome_arquivo_base}_estado.json")
        estado_gravacao = {
            "caminho_webm": caminho_video_webm, 
            "timeline": timeline_audios, 
            "tempo_corte": tempo_corte_segundos
        }
        
        with open(caminho_estado, 'w', encoding='utf-8') as f:
            json.dump(estado_gravacao, f, indent=2)
            
        print("✅ Gravação bruta concluída e estado salvo.")
    else:
        print("❌ Operação abortada.")
        sys.exit(1) # Avisa a interface web que deu erro e deve fechar o loading

# ==============================================================
# 🚀 PONTO DE ENTRADA DO SCRIPT (CLI)
# ==============================================================

if __name__ == "__main__": 
    caminho_json = sys.argv[1] if len(sys.argv) > 1 else "roteiro.json"
    
    if not os.path.exists(caminho_json): 
        print(f"❌ Erro: O roteiro '{caminho_json}' não foi encontrado.")
        sys.exit(1)
        
    with open(caminho_json, 'r', encoding='utf-8') as f:
        nome_base = re.sub(r'[\\/*?:"<>|]', "", json.load(f).get("metadata", {}).get("nome_aula", "TREINAMENTO")).replace(" ", "_")
        
    caminho_estado = os.path.join("videos_gerados", f"{nome_base}_estado.json")

    # ETAPA 2: Apenas Renderizar
    if "--render" in sys.argv:
        if not os.path.exists(caminho_estado): 
            print("❌ Erro: Estado não encontrado. Execute a gravação do robô primeiro!")
            sys.exit(1)
            
        with open(caminho_estado, 'r', encoding='utf-8') as f: 
            st = json.load(f)
            
        renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])
        
    # ETAPA 1: Apenas Gravar (Playwright)
    elif "--record" in sys.argv:
        asyncio.run(executar_roteiro(caminho_json))
        
    # MODO TRADICIONAL COMPLETO (Se rodar sem flags no terminal)
    else:
        asyncio.run(executar_roteiro(caminho_json))
        
        if os.path.exists(caminho_estado):
            with open(caminho_estado, 'r', encoding='utf-8') as f: 
                st = json.load(f)
                
            renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])
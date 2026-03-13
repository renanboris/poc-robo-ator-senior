"""
main.py — Training OS · Motor de Gravacao e Renderizacao
=========================================================
Correcoes aplicadas:
  - limpar_nome removida (DRY): importada de app.py
  - import shutil movido para o topo
  - tempo_corte_segundos usa None como sentinel (nao -1)
  - page.video.path() verificado antes de usar
  - Threads de audio protegidas com try/except individual
  - wait_for_load_state com timeout explicito
  - LOGIN HÍBRIDO (Resiliente e com Fallback Humano)
"""

import sys
import asyncio
import os
import json
import time
import re
import shutil  # FIX: import no topo, nao dentro da funcao
import logging

import edge_tts
import pygame
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from vision_engine import encontrar_e_clicar
from cursor_engine import (
    instalar_cursor,
    garantir_cursor_visivel,
    mover_cursor_humanizado,
    obter_coords_acao,
)

from proglog import ProgressBarLogger

import PIL.Image
if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
import moviepy.audio.fx.all as afx

# FIX: importa limpar_nome de app.py — fonte de verdade unica (DRY)
# Se app.py nao estiver no path, define localmente como fallback
try:
    from app import limpar_nome
except ImportError:
    def limpar_nome(nome: str) -> str:
        return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

load_dotenv()

os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "hide"
logging.getLogger("playwright").setLevel(logging.CRITICAL)
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

pygame.mixer.init()
pygame.mixer.set_num_channels(2)


# ==============================================================
# CUSTOM LOGGER PARA ENVIAR PORCENTAGEM AO PAINEL
# ==============================================================
class CustomRenderLogger(ProgressBarLogger):
    def __init__(self):
        super().__init__()
        self.last_pct = -1

    def callback(self, **kw):
        pass

    def bars_callback(self, bar, attr, value, old_value=None):
        total = self.bars[bar].get("total", 0)
        if bar == "t" and total > 0:
            pct = int((value / total) * 100)
            if pct != self.last_pct:
                print(f"PROGRESSO:{pct}", flush=True)
                self.last_pct = pct


# ==============================================================
# UTILITARIOS GERAIS
# ==============================================================

# Manifesto global de audios
_audio_manifest: dict[str, str] = {}


def salvar_manifesto_audio(id_treinamento: str) -> None:
    nome_pasta    = limpar_nome(id_treinamento)
    caminho_pasta = os.path.join("audios_gerados", nome_pasta)
    os.makedirs(caminho_pasta, exist_ok=True)
    caminho = os.path.join(caminho_pasta, "_manifest.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(_audio_manifest, f, indent=2, ensure_ascii=False)
    logging.info(f"Manifesto de audio salvo: {caminho} ({len(_audio_manifest)} entradas)")


# ==============================================================
# AUDIO (TTS)
# ==============================================================
async def gerar_audio(
    texto: str, id_unico: str, id_treinamento: str, voz: str = "pt-BR-FranciscaNeural"
) -> str | None:
    if not texto or not texto.strip():
        return None

    texto_falado = re.sub(r"(?i)\becm_ged\b", "E C M gédi", texto)
    texto_falado = re.sub(r"\bGED\b", "gédi", texto_falado)
    texto_falado = re.sub(r"\bged\b", "gédi", texto_falado)
    texto_falado = texto_falado.replace("Senior X", "Senior X")

    nome_pasta  = limpar_nome(id_treinamento)
    pasta_audio = os.path.join("audios_gerados", nome_pasta)
    os.makedirs(pasta_audio, exist_ok=True)

    arquivo_mp3 = os.path.join(pasta_audio, f"audio_{id_unico}.mp3")

    if not os.path.exists(arquivo_mp3):
        await edge_tts.Communicate(texto_falado, voz, rate="-12%").save(arquivo_mp3)

    _audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"
    return arquivo_mp3


def iniciar_reproducao_audio(arquivo_mp3: str) -> None:
    if arquivo_mp3 and os.path.exists(arquivo_mp3):
        try:
            pygame.mixer.Channel(1).play(pygame.mixer.Sound(arquivo_mp3))
        except Exception as e:
            logging.warning(f"Falha ao reproduzir audio: {e}")


async def aguardar_audio_terminar() -> None:
    while pygame.mixer.Channel(1).get_busy():
        await asyncio.sleep(0.1)


# ==============================================================
# ELEMENTOS VISUAIS E CINEMATOGRAFICOS
# ==============================================================
async def safe_evaluate(target, script: str, arg=None, timeout: float = 3.0) -> bool:
    try:
        coro = target.evaluate(script, arg) if arg is not None else target.evaluate(script)
        await asyncio.wait_for(coro, timeout=timeout)
        return True
    except Exception:
        return False


async def atualizar_progress_bar(page, passo_atual: int, total_passos: int, nome_aula: str) -> None:
    porcentagem = int((passo_atual / total_passos) * 100)
    dashoffset  = 62.8 - (62.8 * porcentagem) / 100

    script = f"""() => {{
        let pill = document.getElementById('senior-progress-pill');
        if (!pill) {{
            pill = document.createElement('div');
            pill.id = 'senior-progress-pill';
            pill.style.cssText = `
                position:fixed; bottom:30px; right:30px;
                background:rgba(15,23,42,0.85); backdrop-filter:blur(12px);
                border:1px solid rgba(255,255,255,0.1); border-radius:100px;
                padding:10px 20px; display:flex; align-items:center; gap:15px;
                z-index:2147483646; font-family:'Segoe UI',sans-serif;
                box-shadow:0 10px 25px rgba(0,0,0,0.5); transition:all 0.3s ease;
            `;
            const ring = document.createElement('div');
            ring.style.cssText = 'position:relative;width:24px;height:24px;';
            ring.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" style="transform:rotate(-90deg)">
                  <circle cx="12" cy="12" r="10" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="3"/>
                  <circle id="senior-progress-circle" cx="12" cy="12" r="10" fill="none"
                    stroke="#00e5e5" stroke-width="3" stroke-dasharray="62.8" stroke-dashoffset="62.8"
                    style="transition:stroke-dashoffset 0.8s ease-in-out;stroke-linecap:round"/>
                </svg>`;
            const txt = document.createElement('div');
            txt.style.cssText = 'display:flex;flex-direction:column;justify-content:center;';
            txt.innerHTML = `
                <div style="color:#94a3b8;font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">{nome_aula}</div>
                <div id="senior-progress-step" style="color:#fff;font-size:13px;font-weight:500">Passo {passo_atual} de {total_passos}</div>`;
            pill.appendChild(ring);
            pill.appendChild(txt);
            document.documentElement.appendChild(pill);
        }}
        const circle = document.getElementById('senior-progress-circle');
        const step   = document.getElementById('senior-progress-step');
        if (circle) circle.style.strokeDashoffset = '{dashoffset}';
        if (step)   step.innerText = 'Passo {passo_atual} de {total_passos}';
    }}"""
    await safe_evaluate(page, script)


async def exibir_legenda_cinema(page, texto: str) -> None:
    if not texto or not texto.strip():
        return
    script = """(texto) => {
        let el = document.getElementById('senior-video-subtitle');
        if (el) el.remove();
        const sub = document.createElement('div');
        sub.id = 'senior-video-subtitle';
        sub.style.cssText = `
            position:fixed; bottom:40px; left:50%; transform:translateX(-50%);
            background:rgba(15,23,42,0.85); backdrop-filter:blur(8px); color:#fff;
            padding:12px 30px; border-radius:50px; font-family:'Segoe UI',sans-serif;
            font-size:20px; font-weight:500; text-align:center; max-width:75%;
            z-index:2147483645; line-height:1.4; box-shadow:0 10px 30px rgba(0,0,0,.5);
            border:1px solid rgba(255,255,255,.1); opacity:0; transition:opacity .5s ease;
        `;
        sub.innerHTML = texto;
        document.documentElement.appendChild(sub);
        setTimeout(() => sub.style.opacity = '1', 50);
    }"""
    await safe_evaluate(page, script, arg=texto)


async def remover_legenda(page) -> None:
    await safe_evaluate(page, "() => { const e = document.getElementById('senior-video-subtitle'); if(e) e.remove(); }")


async def exibir_encerramento_cinema(page) -> None:
    script = """() => new Promise((resolve) => {
        const renderUI = () => {
            const overlay = document.createElement('div');
            overlay.style.cssText = `
                position:fixed; top:0; left:0; width:100vw; height:100vh;
                background:rgba(0,0,0,0.85); backdrop-filter:blur(12px);
                display:flex; flex-direction:column; align-items:center;
                justify-content:center; z-index:2147483644; opacity:0;
                transition:opacity 1s ease;
            `;
            overlay.innerHTML = `
                <lottie-player src="https://lottie.host/76846e87-566d-49b8-b3d0-90a6290d22ec/5sys94coTA.json"
                    background="transparent" speed="1"
                    style="width:250px;height:250px;" autoplay></lottie-player>
                <h1 style="margin-top:-10px;color:#fff;font-size:38px;font-family:sans-serif;
                    font-weight:bold;text-shadow:0 4px 15px rgba(0,0,0,.5)">
                    Treinamento Concluido
                </h1>`;
            document.documentElement.appendChild(overlay);
            setTimeout(() => overlay.style.opacity = '1', 50);
            resolve(true);
        };
        if (!document.querySelector('script[src*="lottie-player"]')) {
            const s = document.createElement('script');
            s.src = 'https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js';
            s.onload = renderUI;
            document.head.appendChild(s);
        } else { renderUI(); }
    })"""
    await safe_evaluate(page, script, timeout=5.0)


# ==============================================================
# GERACAO DE LEGENDAS (SRT) E VIDEO FINAL
# ==============================================================
def formatar_tempo_srt(segundos: float) -> str:
    h  = int(segundos // 3600)
    m  = int((segundos % 3600) // 60)
    s  = int(segundos % 60)
    ms = int(round((segundos - int(segundos)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gerar_arquivo_srt(timeline: list, caminho_srt: str) -> None:
    with open(caminho_srt, "w", encoding="utf-8") as f:
        for idx, item in enumerate(timeline):
            f.write(f"{idx + 1}\n")
            f.write(f"{formatar_tempo_srt(item['inicio'])} --> {formatar_tempo_srt(item['fim'])}\n")
            f.write(f"{item['texto']}\n\n")


def renderizar_video_final(
    caminho_webm: str, timeline: list, nome_arquivo_base: str, tempo_corte: float
) -> None:
    print("\nINICIANDO POS-PRODUCAO...")
    try:
        os.makedirs("videos_prontos", exist_ok=True)
        video       = VideoFileClip(caminho_webm).subclip(tempo_corte)
        clipes_audio = []

        if os.path.exists("trilha.mp3"):
            bgm = AudioFileClip("trilha.mp3").volumex(0.08)
            bgm = afx.audio_loop(bgm, duration=video.duration)
            clipes_audio.append(bgm)

        for item in timeline:
            if os.path.exists(item["arquivo"]):
                clipes_audio.append(AudioFileClip(item["arquivo"]).set_start(item["inicio"]))

        if clipes_audio:
            video = video.set_audio(CompositeAudioClip(clipes_audio))

        mp4_path = os.path.join("videos_prontos", f"{nome_arquivo_base}.mp4")
        srt_path = os.path.join("videos_prontos", f"{nome_arquivo_base}.srt")

        video.write_videofile(
            mp4_path,
            codec="libx264",
            audio_codec="aac",
            fps=24,
            preset="ultrafast",
            logger=CustomRenderLogger(),
        )
        video.close()

        gerar_arquivo_srt(timeline, srt_path)
        print(f"SUCESSO! Video: {mp4_path}")

    except Exception as e:
        print(f"Erro na Pos-Producao: {e}")


# ==============================================================
# WRAPPER DE CLIQUE E VALIDACAO
# ==============================================================
def _validar_roteiro_gravacao(roteiro: dict) -> list[str]:
    erros = []
    if not roteiro.get("passos"):
        erros.append("Roteiro sem passos definidos.")
        return erros
    for p in roteiro["passos"]:
        pid = p.get("id_passo", "?")
        if not isinstance(p.get("acoes_tecnicas"), list):
            erros.append(f"Passo {pid}: campo 'acoes_tecnicas' ausente ou invalido.")
        if not p.get("pedagogia", {}).get("ancora"):
            erros.append(f"Passo {pid}: ancora (narracao principal) vazia.")
    return erros


async def clicar_com_animacao(page, acao_tec: dict) -> None:
    await garantir_cursor_visivel(page)

    # 🟢 O Mouse não "some" mais!
    # E a viagem (Curva Bézier) foi movida para dentro do vision_engine.py,
    # para garantir sincronia milimétrica com o elemento real e evitar pulos.
    await encontrar_e_clicar(page, acao_tec)

# ==============================================================
# MOTOR DE EXECUCAO PRINCIPAL
# ==============================================================
async def executar_roteiro(caminho_json: str) -> None:
    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER")
    senha      = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("ERRO: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS)")
        sys.exit(1)

    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    erros = _validar_roteiro_gravacao(roteiro)
    if erros:
        print("Roteiro invalido — corrija antes de gravar:")
        for e in erros:
            print(f"   {e}")
        sys.exit(1)

    metadata          = roteiro.get("metadata", {})
    nome_aula_raw     = metadata.get("nome_aula", "Aula Senior")
    id_treinamento    = metadata.get("id_treinamento", nome_aula_raw)
    nome_arquivo_base = limpar_nome(id_treinamento)
    voz_escolhida     = roteiro.get("configuracao_gravacao", {}).get("voz_ia", "pt-BR-FranciscaNeural")

    global _audio_manifest
    _audio_manifest.clear()

    # Limpa cache de audios antigos
    pasta_audio_cache = os.path.join("audios_gerados", nome_arquivo_base)
    if os.path.exists(pasta_audio_cache):
        try:
            shutil.rmtree(pasta_audio_cache)
        except Exception as e:
            logging.warning(f"Nao foi possivel limpar o cache de audio: {e}")
    os.makedirs(pasta_audio_cache, exist_ok=True)

    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.15)
        pygame.mixer.music.play(loops=-1)

    timeline_audios: list = []
    caminho_video_webm    = None

    # FIX: usa None como sentinel (nao -1) — mais legivel e semanticamente correto
    tempo_corte_segundos: float | None = None

    passos_lista = roteiro.get("passos", [])
    total_passos = len(passos_lista)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, args=["--start-fullscreen", "--disable-infobars"])
        tempo_inicio_contexto = time.time()

        context = await browser.new_context(
            no_viewport=True,
            record_video_dir="videos_gerados",
            record_video_size={"width": 1920, "height": 1080},
        )
        page = await context.new_page()
        await instalar_cursor(page)

        # ---------------------------------------------------------
        # 🟢 NOVO MOTOR DE LOGIN HÍBRIDO (Resiliente)
        # ---------------------------------------------------------
        print("A iniciar o robô e a tentar login no Senior X...", flush=True)
        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")

            # 1. Tenta preencher o usuário
            campo_usr = page.locator("input[type='text'], input[type='email'], [placeholder*='usuario']").first
            await campo_usr.wait_for(state="visible", timeout=10000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.5)

            # 2. Tenta clicar em Próximo ou aperta Enter
            try:
                await page.locator("button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')").first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")

            # 3. Aguarda a senha
            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            print("Login efetuado. A aguardar carregamento do painel para gravar...", flush=True)
            await page.wait_for_load_state("load", timeout=30_000)
            await asyncio.sleep(2.0)

        except Exception as e:
            logging.warning(f"O auto-login do Robô falhou: {e}")
            print("AVISO: O robô não conseguiu logar. Por favor, conclua o login manualmente na janela do Chrome em até 60 segundos!", flush=True)
            try:
                await page.wait_for_load_state("networkidle", timeout=60000)
                await asyncio.sleep(3.0)
            except Exception:
                print("ERRO FATAL: Tempo esgotado para login manual.", flush=True)
                await browser.close()
                return
        # ---------------------------------------------------------
        # FIM DO BLOCO DE LOGIN
        # ---------------------------------------------------------

        try:
            # Pula os modais caso ainda existam após o carregamento
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")

            tempo_inicio_gravacao = time.time()
            tempo_corte_segundos  = tempo_inicio_gravacao - tempo_inicio_contexto

            w = await page.evaluate("() => window.innerWidth")
            h = await page.evaluate("() => window.innerHeight")
            await page.mouse.move(w / 2, h / 2)

            print("\nGRAVANDO VIDEO E AUDIOS\n", flush=True)

            for idx, passo in enumerate(passos_lista):
                id_p              = passo.get("id_passo", idx + 1)
                pausa_inteligente = float(passo.get("pause_sugerida", 1.5))

                await atualizar_progress_bar(page, idx + 1, total_passos, nome_aula_raw)

                ancora = passo.get("pedagogia", {}).get("ancora", "")
                if ancora:
                    await exibir_legenda_cinema(page, ancora)
                    id_ancora = f"passo_{id_p}_ancora"
                    mp3       = await gerar_audio(ancora, id_ancora, nome_arquivo_base, voz_escolhida)

                    if mp3:
                        t_atual = time.time() - tempo_inicio_gravacao
                        try:
                            duracao = pygame.mixer.Sound(mp3).get_length()
                        except Exception:
                            duracao = 3.0  # fallback se o arquivo estiver corrompido
                        iniciar_reproducao_audio(mp3)
                        timeline_audios.append({
                            "arquivo": mp3,
                            "inicio":  t_atual,
                            "fim":     t_atual + duracao,
                            "texto":   ancora,
                        })

                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.5)

                if passo.get("is_conclusao", False):
                    await exibir_encerramento_cinema(page)
                    await asyncio.sleep(4.0)
                    break

                for i, acao_tec in enumerate(passo.get("acoes_tecnicas", [])):
                    if acao_tec.get("acao") == "concluir_video":
                        continue

                    micro_voz = acao_tec.get("micro_narracao", "")
                    if micro_voz:
                        await exibir_legenda_cinema(page, micro_voz)
                        id_acao = f"passo_{id_p}_acao_{i}"
                        mp3     = await gerar_audio(micro_voz, id_acao, nome_arquivo_base, voz_escolhida)

                        if mp3:
                            t_atual = time.time() - tempo_inicio_gravacao
                            try:
                                duracao = pygame.mixer.Sound(mp3).get_length()
                            except Exception:
                                duracao = 2.0
                            iniciar_reproducao_audio(mp3)
                            timeline_audios.append({
                                "arquivo": mp3,
                                "inicio":  t_atual,
                                "fim":     t_atual + duracao,
                                "texto":   micro_voz,
                            })

                    await clicar_com_animacao(page, acao_tec)
                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    
                    # 🟢 REDUTOR DE TEMPO MORTO (Deixa o robô ágil e natural)
                    pausa_real = min(pausa_inteligente * 0.3, 0.8)
                    await asyncio.sleep(pausa_real)

        except Exception as e:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            logging.error(f"Gravacao interrompida: {e}")
            tempo_corte_segundos = None  # FIX: None indica falha

        finally:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            salvar_manifesto_audio(id_treinamento)

            try:
                # FIX: verifica se o video existe antes de chamar .path()
                if not page.is_closed() and page.video:
                    caminho_video_webm = await page.video.path()
                await asyncio.sleep(1.0)
                if not page.is_closed():
                    await page.close()
                await context.close()
                await browser.close()
            except Exception:
                pass

            # FIX: usa None como sentinel — sem ambiguidade com valores negativos
            if tempo_corte_segundos is None and caminho_video_webm and os.path.exists(caminho_video_webm):
                try:
                    os.remove(caminho_video_webm)
                except Exception:
                    pass
                caminho_video_webm = None

    if caminho_video_webm and tempo_corte_segundos is not None and tempo_corte_segundos > 0:
        caminho_estado = os.path.join("videos_gerados", f"{nome_arquivo_base}_estado.json")
        with open(caminho_estado, "w", encoding="utf-8") as f:
            json.dump({
                "caminho_webm": caminho_video_webm,
                "timeline":     timeline_audios,
                "tempo_corte":  tempo_corte_segundos,
            }, f, indent=2)
        print("Gravacao bruta concluida. Estado salvo.", flush=True)
    else:
        print("Operacao abortada.", flush=True)
        sys.exit(1)


# ==============================================================
# PONTO DE ENTRADA (CLI)
# ==============================================================
if __name__ == "__main__":
    caminho_json = sys.argv[1] if len(sys.argv) > 1 else "roteiro.json"

    if not os.path.exists(caminho_json):
        print(f"Roteiro nao encontrado: '{caminho_json}'")
        sys.exit(1)

    with open(caminho_json, "r", encoding="utf-8") as f:
        dados = json.load(f)

    meta           = dados.get("metadata", {})
    id_treinamento = meta.get("id_treinamento", meta.get("nome_aula", "TREINAMENTO"))
    nome_base      = limpar_nome(id_treinamento)
    caminho_estado = os.path.join("videos_gerados", f"{nome_base}_estado.json")

    if "--render" in sys.argv:
        if not os.path.exists(caminho_estado):
            print("Estado nao encontrado. Execute a gravacao primeiro.")
            sys.exit(1)
        with open(caminho_estado, "r", encoding="utf-8") as f:
            st = json.load(f)
        renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])

    elif "--record" in sys.argv:
        asyncio.run(executar_roteiro(caminho_json))

    else:
        asyncio.run(executar_roteiro(caminho_json))
        if os.path.exists(caminho_estado):
            with open(caminho_estado, "r", encoding="utf-8") as f:
                st = json.load(f)
            renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])
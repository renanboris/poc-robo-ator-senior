"""
main.py — Training OS · Motor de Gravacao e Renderizacao
=========================================================
Correcoes aplicadas:
  - Tela Maximizada (--start-maximized e no_viewport=True)
  - Digitação humanizada no Login (press_sequentially)
  - limpar_nome removida (DRY): importada de app.py
  - import shutil movido para o topo
  - tempo_corte_segundos usa None como sentinel (nao -1)
  - page.video.path() verificado antes de usar
  - Threads de audio protegidas com try/except individual
  - wait_for_load_state com timeout explicito
  - LOGIN HÍBRIDO (Resiliente e com Fallback Humano)
  - Chaveador de Vozes (Edge TTS vs ElevenLabs)
"""

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time

import edge_tts
import PIL.Image
import pygame
import requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from proglog import ProgressBarLogger

import score_engine as _score_engine
from cursor_engine import (
    garantir_cursor_visivel,
    instalar_cursor,
)
from vision_engine import encontrar_e_clicar

if not hasattr(PIL.Image, "ANTIALIAS"):
    PIL.Image.ANTIALIAS = PIL.Image.LANCZOS

import moviepy.audio.fx.all as afx
from moviepy.editor import AudioFileClip, CompositeAudioClip, VideoFileClip

from utils import limpar_nome

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
_audio_manifest: dict[str, str] = {}
_audio_manifest_lock = asyncio.Lock()

def salvar_manifesto_audio(id_treinamento: str) -> None:
    nome_pasta    = limpar_nome(id_treinamento)
    caminho_pasta = os.path.join("audios_gerados", nome_pasta)
    os.makedirs(caminho_pasta, exist_ok=True)
    caminho = os.path.join(caminho_pasta, "_manifest.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(_audio_manifest, f, indent=2, ensure_ascii=False)
    logging.info(f"Manifesto de audio salvo: {caminho} ({len(_audio_manifest)} entradas)")

# ==============================================================
# AUDIO (TTS e ELEVENLABS)
# ==============================================================
async def gerar_audio(
    texto: str, id_unico: str, id_treinamento: str, voz: str = "pt-BR-FranciscaNeural"
) -> str | None:
    if not texto or not texto.strip():
        return None

    # Correções de pronúncia
    texto_falado = re.sub(r"(?i)\becm_ged\b", "E C M gédi", texto)
    texto_falado = re.sub(r"\bGED\b", "gédi", texto_falado)
    texto_falado = re.sub(r"\bged\b", "gédi", texto_falado)
    texto_falado = re.sub(r"(?i)\bsenior\b", "Sênior", texto_falado)
    # "X" avulso (palavra inteira, maiúsculo) → "Éks" — cobre Senior X, ERP X, etc.
    # Grafia fonética sem acento ambíguo: evita "êx" (prefixo) e problemas com ElevenLabs
    texto_falado = re.sub(r"\bX\b", "Éks", texto_falado)
    # "template/templates" → pronúncia inglesa correta (evita "templáte" do Azure pt-BR)
    texto_falado = re.sub(r"(?i)\btemplates?\b", lambda m: "têmpleits" if m.group().lower().endswith("s") else "têmpleit", texto_falado)

    # ── Pré-processamento anti-travada para edge-tts ─────────────────────────
    # Remove ou substitui caracteres que causam engasgos no Azure Neural TTS:
    # 1. Underscores viram espaço (IDs e nomes de campo tipo "nome_campo")
    texto_falado = texto_falado.replace("_", " ")
    # 2. Barras e pipes viram pausa natural
    texto_falado = re.sub(r"\s*[|/]\s*", ", ", texto_falado)
    # 3. Múltiplos espaços → um só
    texto_falado = re.sub(r" {2,}", " ", texto_falado).strip()

    nome_pasta  = limpar_nome(id_treinamento)
    pasta_audio = os.path.join("audios_gerados", nome_pasta)
    os.makedirs(pasta_audio, exist_ok=True)

    arquivo_mp3 = os.path.join(pasta_audio, f"audio_{id_unico}.mp3")

    if not os.path.exists(arquivo_mp3):
        if voz == "elevenlabs":
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                print("⚠️  Chave ELEVENLABS_API_KEY não encontrada no .env! Fazendo fallback para a voz gratuita...", flush=True)
                await edge_tts.Communicate(texto_falado, "pt-BR-FranciscaNeural", rate="-8%", pitch="-5Hz", volume="+8%").save(arquivo_mp3)
            else:
                try:
                    voice_id = "ErXwobaYiN019PkySvjV"
                    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

                    headers = {
                        "Accept": "audio/mpeg",
                        "Content-Type": "application/json",
                        "xi-api-key": api_key
                    }

                    data = {
                        "text": texto_falado,
                        "model_id": "eleven_multilingual_v2",
                        "voice_settings": {
                            "stability": 0.45,
                            "similarity_boost": 0.85,
                            "style": 0.35,
                            "use_speaker_boost": True
                        }
                    }

                    response = requests.post(url, json=data, headers=headers)
                    if response.status_code == 200:
                        with open(arquivo_mp3, 'wb') as f:
                            for chunk in response.iter_content(chunk_size=1024):
                                if chunk:
                                    f.write(chunk)
                    else:
                        print(f"⚠️  Erro no ElevenLabs ({response.status_code}): {response.text}. Fallback gratuito ativado.", flush=True)
                        await edge_tts.Communicate(texto_falado, "pt-BR-FranciscaNeural", rate="-8%", pitch="-5Hz", volume="+8%").save(arquivo_mp3)
                except Exception as e:
                    print(f"⚠️  Falha ao conectar no ElevenLabs: {e}. Fallback gratuito ativado.", flush=True)
                    await edge_tts.Communicate(texto_falado, "pt-BR-FranciscaNeural", rate="-8%", pitch="-5Hz", volume="+8%").save(arquivo_mp3)

        else:
            await edge_tts.Communicate(texto_falado, voz, rate="-8%", pitch="-5Hz", volume="+8%").save(arquivo_mp3)

    async with _audio_manifest_lock:
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

async def aplicar_blur_video(page, regiao: dict) -> None:
    """Injeta overlay sólido (#1a1a1a) sobre a região sensível na página gravada.

    O overlay é visível no vídeo gerado pelo Playwright, garantindo que dados
    sensíveis não apareçam na gravação (Requisito 1.2).
    """
    script = """(r) => {
        let el = document.getElementById('senior-blur-overlay');
        if (el) el.remove();
        const div = document.createElement('div');
        div.id = 'senior-blur-overlay';
        div.style.cssText = [
            'position:fixed',
            'z-index:2147483647',
            'background:#1a1a1a',
            'pointer-events:none',
            'left:' + r.x + 'px',
            'top:' + r.y + 'px',
            'width:' + r.w + 'px',
            'height:' + r.h + 'px',
        ].join(';');
        document.documentElement.appendChild(div);
    }"""
    await safe_evaluate(page, script, arg=regiao)

async def remover_blur_video(page) -> None:
    """Remove o overlay de blur injetado por aplicar_blur_video."""
    await safe_evaluate(page, "() => { const e = document.getElementById('senior-blur-overlay'); if(e) e.remove(); }")

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
    video = None
    clipes_audio = []

    try:
        os.makedirs("videos_prontos", exist_ok=True)
        video = VideoFileClip(caminho_webm).subclip(tempo_corte)

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
        temp_audio_path = os.path.join("videos_prontos", f"{nome_arquivo_base}_TEMP_audio.mp4")

        video.write_videofile(
            mp4_path,
            codec="libx264",
            audio_codec="aac",
            fps=30,
            preset="medium",
            ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
            temp_audiofile=temp_audio_path,
            logger=CustomRenderLogger(),
        )
        gerar_arquivo_srt(timeline, srt_path)
        print(f"SUCESSO! Video: {mp4_path}")

    except Exception as e:
        print(f"Erro na Pos-Producao: {e}")
    finally:
        if video:
            try: video.close()
            except: pass
        # Remove arquivo de áudio temporário do moviepy, se sobrar
        if 'temp_audio_path' in locals() and os.path.exists(temp_audio_path):
            try: os.remove(temp_audio_path)
            except: pass

        for clipe in clipes_audio:
            try: clipe.close()
            except: pass

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

async def clicar_com_animacao(page, acao_tec: dict) -> bool:
    await garantir_cursor_visivel(page)
    return await encontrar_e_clicar(page, acao_tec)

# ==============================================================
# MOTOR DE EXECUCAO PRINCIPAL
# ==============================================================
async def executar_roteiro(caminho_json: str) -> None:
    from contracts.capture_adapter import get_capture_adapter, GenericAdapter, SeniorXAdapter

    adapter    = get_capture_adapter()
    logging.info(f"[Pipeline] Adapter ativo: {type(adapter).__name__} | Sistema: {adapter.nome_sistema}")

    SENIOR_URL = adapter.url_base
    seletores  = adapter.obter_seletores_login()

    # Credenciais: SeniorXAdapter usa variáveis de execução; GenericAdapter usa adapter
    if isinstance(adapter, SeniorXAdapter):
        usuario = os.getenv("SENIOR_USER_EXECUTE", "")
        senha   = os.getenv("SENIOR_PASS_EXECUTE", "")
    else:
        creds   = adapter.obter_credenciais()
        usuario = creds["usuario"]
        senha   = creds["senha"]

    # Validação de credenciais adaptada ao adapter ativo
    if isinstance(adapter, SeniorXAdapter):
        if not usuario or not senha:
            print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)")
            sys.exit(1)
    elif isinstance(adapter, GenericAdapter) and adapter.login_requerido():
        if not usuario or not senha:
            print("ERRO: LOGIN_REQUIRED=true mas LOGIN_USER/LOGIN_PASS ausentes no .env.")
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
    async with _audio_manifest_lock:
        _audio_manifest.clear()

    pasta_audio_cache = os.path.join("audios_gerados", nome_arquivo_base)
    if os.path.exists(pasta_audio_cache):
        try:
            shutil.rmtree(pasta_audio_cache)
        except Exception as e:
            logging.warning(f"Nao foi possivel limpar o cache de audio: {e}")
    os.makedirs(pasta_audio_cache, exist_ok=True)

    if os.path.exists("trilha.mp3"):
        pygame.mixer.music.load("trilha.mp3")
        pygame.mixer.music.set_volume(0.10)
        pygame.mixer.music.play(loops=-1)

    timeline_audios: list = []
    caminho_video_webm    = None
    tempo_corte_segundos: float | None = None

    passos_lista = roteiro.get("passos", [])
    total_passos = len(passos_lista)

    print("Pré-gerando áudios do roteiro...", flush=True)
    tarefas_audio: list = []
    for passo in passos_lista:
        id_p   = passo.get("id_passo", passos_lista.index(passo) + 1)
        ancora = passo.get("pedagogia", {}).get("ancora", "")
        if ancora:
            tarefas_audio.append(
                gerar_audio(ancora, f"passo_{id_p}_ancora", nome_arquivo_base, voz_escolhida)
            )
        for i, acao_tec in enumerate(passo.get("acoes_tecnicas", [])):
            micro = acao_tec.get("micro_narracao", "")
            if micro:
                tarefas_audio.append(
                    gerar_audio(micro, f"passo_{id_p}_acao_{i}", nome_arquivo_base, voz_escolhida)
                )
    if tarefas_audio:
        resultados = await asyncio.gather(*tarefas_audio, return_exceptions=True)
        for i, res in enumerate(resultados):
            if isinstance(res, Exception):
                logging.error(f"[Audio] Falha na geração de áudio da tarefa {i}: {res}")
    print(f"✅ {len(tarefas_audio)} áudio(s) prontos. Iniciando gravação...", flush=True)

    async with async_playwright() as pw:
        # ── Detecta monitor auxiliar para gravar em fullHD ───────────────────
        # Usa screeninfo para encontrar o monitor não-primário (monitor externo).
        # Se não encontrar, usa o monitor primário como fallback.
        _window_x, _window_y = 0, 0
        try:
            from screeninfo import get_monitors
            monitores = get_monitors()
            monitor_aux = next((m for m in monitores if not m.is_primary), None)
            if monitor_aux:
                _window_x = monitor_aux.x
                _window_y = monitor_aux.y
                print(f"[Monitor] Usando monitor auxiliar: {monitor_aux.name} {monitor_aux.width}x{monitor_aux.height} pos=({_window_x},{_window_y})", flush=True)
            else:
                print("[Monitor] Monitor auxiliar não encontrado — usando monitor primário.", flush=True)
        except Exception as e:
            print(f"[Monitor] screeninfo falhou ({e}) — usando posição padrão.", flush=True)

        # 🟢 TELA MAXIMIZADA NO MONITOR AUXILIAR
        # --window-position posiciona a janela no monitor correto antes de maximizar.
        browser = await pw.chromium.launch(headless=False, args=[
            "--start-maximized",
            f"--window-position={_window_x},{_window_y}",
            "--disable-infobars",
            "--disable-features=Translate",
            "--lang=pt-BR",
            "--no-first-run",
            "--no-default-browser-check",
        ])
        tempo_inicio_contexto = time.time()

        # 🟢 Garantia do viewport flexível com no_viewport=True
        context = await browser.new_context(
            no_viewport=True,
            record_video_dir="videos_gerados",
            record_video_size={"width": 1920, "height": 1080},
            locale="pt-BR",
        )
        page = await context.new_page()
        await instalar_cursor(page)

        # ── Maximiza via CDP após criar a página ─────────────────────────────
        # --start-maximized falha com --window-position em monitores não-primários
        # no Windows. CDP Browser.setWindowBounds é a forma confiável.
        try:
            cdp = await context.new_cdp_session(page)
            wid_resp = await cdp.send("Browser.getWindowForTarget")
            window_id = wid_resp["windowId"]
            await cdp.send("Browser.setWindowBounds", {
                "windowId": window_id,
                "bounds": {
                    "left":        _window_x,
                    "top":         _window_y,
                    "windowState": "maximized",
                },
            })
            await cdp.detach()
            print("[Monitor] Janela maximizada via CDP.", flush=True)
        except Exception as e:
            print(f"[Monitor] CDP maximize falhou ({e}) — continuando.", flush=True)

        print(f"A iniciar o robô — adapter: {type(adapter).__name__}...", flush=True)
        try:
            if isinstance(adapter, GenericAdapter) and not adapter.login_requerido():
                # ── Modo sem login: navega direto para a URL alvo ─────────────
                logging.info(f"[Adapter] Modo sem login ativo. Navegando para: {adapter.url_base}")
                await page.goto(SENIOR_URL)
                await page.wait_for_load_state("load", timeout=30_000)
                await asyncio.sleep(2.0)
            else:
                # ── Fluxo de login (SeniorXAdapter ou GenericAdapter com login) ──
                await page.goto(SENIOR_URL)
                await asyncio.sleep(2.0)
                await page.keyboard.press("Escape")

                campo_usr = page.locator(seletores["campo_usuario"]).first
                await campo_usr.wait_for(state="visible", timeout=10000)

                # 🟢 Digitação Humanizada no Login
                await campo_usr.press_sequentially(usuario, delay=85)
                await asyncio.sleep(0.5)

                try:
                    await page.locator(seletores["botao_proximo"]).first.click(timeout=3000)
                except Exception:
                    await page.keyboard.press("Enter")

                campo_senha = page.locator(seletores["campo_senha"]).first
                await campo_senha.wait_for(state="visible", timeout=10000)

                # 🟢 Digitação Humanizada na Senha
                await campo_senha.press_sequentially(senha, delay=85)
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

        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            await page.keyboard.press("Escape")

            # ── Botão PLAY: aguarda o usuário confirmar que está pronto ───────
            await page.evaluate("""() => {
                if (document.getElementById('_aura_play_overlay')) return;
                const style = document.createElement('style');
                style.innerHTML = `
                    @keyframes _aura_pulse { 0%,100%{transform:scale(1);box-shadow:0 0 0 0 rgba(34,197,94,.5)} 50%{transform:scale(1.04);box-shadow:0 0 0 12px rgba(34,197,94,0)} }
                `;
                document.head.appendChild(style);
                const overlay = document.createElement('div');
                overlay.id = '_aura_play_overlay';
                overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,.55);backdrop-filter:blur(6px);z-index:2147483647;display:flex;align-items:center;justify-content:center;';
                overlay.innerHTML = `
                    <div style="background:rgba(15,23,42,.95);border:1px solid rgba(255,255,255,.12);border-radius:20px;padding:40px 56px;text-align:center;font-family:'Segoe UI',sans-serif;max-width:420px;">
                        <div style="font-size:13px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:#64748b;margin-bottom:8px;">Senior Training OS</div>
                        <div style="font-size:22px;font-weight:700;color:#f1f5f9;margin-bottom:6px;">Pronto para gravar?</div>
                        <div style="font-size:13px;color:#94a3b8;margin-bottom:32px;">Verifique se está na tela correta antes de iniciar.</div>
                        <button id="_aura_play_btn" style="background:#22c55e;color:#fff;border:none;border-radius:100px;padding:14px 40px;font-size:16px;font-weight:700;cursor:pointer;letter-spacing:.5px;animation:_aura_pulse 2s ease infinite;">▶ Iniciar Gravação</button>
                    </div>`;
                document.documentElement.appendChild(overlay);
                document.getElementById('_aura_play_btn').onclick = () => {
                    overlay.style.transition = 'opacity .3s';
                    overlay.style.opacity = '0';
                    setTimeout(() => overlay.remove(), 300);
                    window._aura_play_confirmado = true;
                };
            }""")

            # Aguarda o usuário clicar em "Iniciar Gravação" (polling a cada 500ms, timeout 5min)
            print("⏸  Aguardando confirmação do usuário para iniciar gravação...", flush=True)
            for _ in range(600):  # 600 * 0.5s = 5 minutos máximo
                confirmado = await page.evaluate("() => !!window._aura_play_confirmado")
                if confirmado:
                    break
                await asyncio.sleep(0.5)

            # ── Gap de 2s após confirmação: dá tempo para o sistema carregar ─
            await asyncio.sleep(2.0)

            tempo_inicio_gravacao = time.time()
            # INVARIANTE: Este delta captura intencionalmente todo o tempo desde a criação
            # do contexto Playwright (tempo_inicio_contexto), incluindo o login automático
            # ou o login manual de até 60 s (fallback humano). O valor é passado para
            # .subclip(tempo_corte) em renderizar_video_final() para remover o prefixo
            # do vídeo bruto antes do início real da gravação do roteiro.
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
                            duracao = 3.0
                        iniciar_reproducao_audio(mp3)
                        timeline_audios.append({
                            "arquivo": mp3,
                            "inicio":  t_atual,
                            "fim":     t_atual + duracao,
                            "texto":   ancora,
                        })

                    await aguardar_audio_terminar()
                    await remover_legenda(page)
                    await asyncio.sleep(0.15)

                if passo.get("is_conclusao", False):
                    await exibir_encerramento_cinema(page)
                    await asyncio.sleep(4.0)
                    break

                for i, acao_tec in enumerate(passo.get("acoes_tecnicas", [])):
                    if acao_tec.get("acao") == "concluir_video":
                        continue

                    # ── Injeta is_context_menu_item em tempo de execução ─────────────
                    # Compatibilidade com roteiros gerados antes da flag existir.
                    # Se a ação anterior foi clique_direito, esta é item de menu de contexto.
                    acoes_tecnicas = passo.get("acoes_tecnicas", [])
                    _acao_anterior = acoes_tecnicas[i - 1].get("acao", "") if i > 0 else ""
                    if (acao_tec.get("acao") == "clique" and
                            _acao_anterior == "clique_direito" and
                            not acao_tec.get("is_context_menu_item")):
                        acao_tec = dict(acao_tec)  # cópia para não mutar o roteiro
                        acao_tec["is_context_menu_item"] = True

                    micro_voz = acao_tec.get("micro_narracao", "")
                    # ── Clique direito: pula narração para não fechar o menu de contexto ──
                    # O menu de contexto fecha sozinho após alguns segundos. Se houver
                    # narração entre o clique_direito e o item do menu, o menu fecha antes
                    # de a próxima ação ser executada. A narração é adiada para depois.
                    _is_clique_direito = acao_tec.get("acao") == "clique_direito"
                    if micro_voz and not _is_clique_direito:
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

                    # Aplicar blur no vídeo se ação tem região sensível (Requisito 1.2)
                    _dados_blur = acao_tec.get("elemento_alvo", {}).get("dados_blur") or {}
                    _blur_ativo = bool(_dados_blur.get("blur")) and bool(_dados_blur.get("regiao"))
                    if _blur_ativo:
                        try:
                            await aplicar_blur_video(page, _dados_blur["regiao"])
                        except Exception as _blur_err:
                            logging.warning(f"[blur_video] Falha ao aplicar overlay de blur: {_blur_err}")
                            _blur_ativo = False

                    resultado_clique = await clicar_com_animacao(page, acao_tec)

                    # Após clique_direito: não aguarda áudio nem pausa — o menu de contexto
                    # precisa ser clicado imediatamente antes de fechar sozinho.
                    if not _is_clique_direito:
                        await aguardar_audio_terminar()
                        await remover_legenda(page)

                    if _blur_ativo:
                        try:
                            await remover_blur_video(page)
                        except Exception as _blur_err:
                            logging.warning(f"[blur_video] Falha ao remover overlay de blur: {_blur_err}")

                    try:
                        intencao = acao_tec.get("intencao_semantica", "").strip()
                        if intencao:
                            _mapa_confianca = {"alta": 1.0, "media": 0.7, "baixa": 0.3}
                            confianca_str = acao_tec.get("elemento_alvo", {}).get("confianca_captura", "alta")
                            confianca_val = _mapa_confianca.get(confianca_str, 1.0)
                            _score_engine.registrar_execucao(
                                intencao,
                                sucesso=bool(resultado_clique),
                                confianca_captura=confianca_val,
                            )
                    except Exception as _score_err:
                        logging.debug(f"[score_engine] Falha ao registrar execução (ignorada): {_score_err}")

                    pausa_real = min(pausa_inteligente * 0.3, 0.8)
                    if not _is_clique_direito:
                        await asyncio.sleep(pausa_real)

        except Exception as e:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            logging.error(f"Gravacao interrompida: {e}")
            tempo_corte_segundos = None

        finally:
            pygame.mixer.stop()
            pygame.mixer.music.stop()
            salvar_manifesto_audio(id_treinamento)

            try:
                if not page.is_closed() and page.video:
                    caminho_video_webm = await page.video.path()
                await asyncio.sleep(1.0)
                if not page.is_closed():
                    await page.close()
                await context.close()
                await browser.close()
            except Exception:
                pass

            if tempo_corte_segundos is None and caminho_video_webm and os.path.exists(caminho_video_webm):
                try:
                    os.remove(caminho_video_webm)
                except Exception:
                    pass
                caminho_video_webm = None

    if caminho_video_webm and tempo_corte_segundos is not None and tempo_corte_segundos > 0:
        caminho_estado = os.path.join("videos_gerados", f"{nome_arquivo_base}_estado.json")
        caminho_webm_rel = os.path.relpath(caminho_video_webm)
        timeline_rel = [
            {**item, "arquivo": os.path.relpath(item["arquivo"])}
            for item in timeline_audios
        ]
        with open(caminho_estado, "w", encoding="utf-8") as f:
            json.dump({
                "caminho_webm": caminho_webm_rel,
                "timeline":     timeline_rel,
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
        st["caminho_webm"] = os.path.abspath(st["caminho_webm"])
        st["timeline"] = [
            {**item, "arquivo": os.path.abspath(item["arquivo"])}
            for item in st["timeline"]
        ]
        renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])

    elif "--record" in sys.argv:
        asyncio.run(executar_roteiro(caminho_json))

    else:
        asyncio.run(executar_roteiro(caminho_json))
        if os.path.exists(caminho_estado):
            with open(caminho_estado, "r", encoding="utf-8") as f:
                st = json.load(f)
            st["caminho_webm"] = os.path.abspath(st["caminho_webm"])
            st["timeline"] = [
                {**item, "arquivo": os.path.abspath(item["arquivo"])}
                for item in st["timeline"]
            ]
            renderizar_video_final(st["caminho_webm"], st["timeline"], nome_base, st["tempo_corte"])

import json
import os
import zipfile
import shutil
import re
from pathlib import Path

# ─── FUNÇÃO ALINHADA COM O BACKEND ───
def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

def criar_pacote_scorm(caminho_json, pasta_destino="scorm_exports"):
    """
    Lê o JSON do treinamento e empacota num arquivo .zip SCORM 1.2
    com um simulador interativo em HTML/JS moderno.
    """
    os.makedirs(pasta_destino, exist_ok=True)

    with open(caminho_json, 'r', encoding='utf-8') as f:
        roteiro = json.load(f)

    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", "Simulador Senior")
    id_treino = metadata.get("id_treinamento", nome_aula_raw)

    nome_arquivo_base = limpar_nome(id_treino)

    temp_dir = Path(f"temp_scorm_{nome_arquivo_base}")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    # 1. Copia os áudios
    pasta_audio_origem = Path("audios_gerados") / nome_arquivo_base
    audio_dir_dest = temp_dir / "audios"
    audio_dir_dest.mkdir()
    if pasta_audio_origem.exists():
        for item in pasta_audio_origem.iterdir():
            if item.suffix == '.mp3':
                shutil.copy2(item, audio_dir_dest / item.name)

    # 2. imsmanifest.xml
    manifest_content = f"""<?xml version="1.0" standalone="no" ?>
<manifest identifier="SeniorTrainingOS" version="1"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
  <organizations default="B0">
    <organization identifier="B0">
      <title>{nome_aula_raw}</title>
      <item identifier="I_1" identifierref="R_1"><title>{nome_aula_raw}</title></item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="R_1" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/>
    </resource>
  </resources>
</manifest>"""
    with open(temp_dir / "imsmanifest.xml", "w", encoding="utf-8") as f:
        f.write(manifest_content)

    # 3. Processa os passos para o JS do Simulador
    slides = []
    for idx, passo in enumerate(roteiro.get("passos", [])):
        id_p = passo.get('id_passo', idx + 1)
        ancora = passo.get("pedagogia", {}).get("ancora", "")

        img_step = None
        for acao in passo.get("acoes_tecnicas", []):
            ref = acao.get("elemento_alvo", {}).get("screenshot_referencia")
            if ref:
                img_step = ref
                break

        if ancora:
            slides.append({
                "tipo": "ancora",
                "texto": ancora,
                "audio_id": f"{id_p}_ancora",
                "imagem_b64": img_step
            })

        for i, acao in enumerate(passo.get("acoes_tecnicas", [])):
            if acao.get("acao") == "concluir_video":
                continue
            alvo = acao.get("elemento_alvo", {})
            coords = alvo.get("coordenadas_relativas", {})
            slides.append({
                "tipo": "interacao",
                "acao": acao.get("acao", "clique"),
                "valor_input": acao.get("valor_input", ""),
                "texto": acao.get("micro_narracao", f"Interaja com {alvo.get('label_curto', 'o elemento')}"),
                "label": alvo.get("label_curto", ""),
                "audio_id": f"{id_p}_micro_{i}",
                "imagem_b64": alvo.get("screenshot_referencia", ""),
                "x_pct": coords.get("x_pct", 0.5),
                "y_pct": coords.get("y_pct", 0.5),
                "w_pct": coords.get("w_pct", 0.05),
                "h_pct": coords.get("h_pct", 0.05)
            })

    # 4. Gera o index.html
    slides_json = json.dumps(slides)
    html_content = _gerar_player_html(nome_aula_raw, slides_json)
    with open(temp_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

    # 5. Zipa o pacote SCORM
    zip_path = Path(pasta_destino) / f"{nome_arquivo_base}_SCORM.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, temp_dir)
                zipf.write(file_path, arcname)

    shutil.rmtree(temp_dir)
    print(f"📦 Pacote SCORM gerado com sucesso: {zip_path}")
    return str(zip_path)


def _gerar_player_html(titulo: str, slides_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<script>
var scorm = {{
  API: null,
  score: 0,
  init: function() {{
    var w = window;
    while (w.API == null && w.parent != null && w.parent != w) w = w.parent;
    this.API = w.API;
    if (this.API) this.API.LMSInitialize("");
  }},
  finish: function(pct) {{
    if (this.API) {{
      this.API.LMSSetValue("cmi.core.lesson_status", "completed");
      this.API.LMSSetValue("cmi.core.score.raw", String(Math.round(pct)));
      this.API.LMSSetValue("cmi.core.score.min", "0");
      this.API.LMSSetValue("cmi.core.score.max", "100");
      this.API.LMSCommit("");
      this.API.LMSFinish("");
    }}
  }}
}};
window.onload  = function() {{ scorm.init(); mostrarIntro(); }};
window.onunload = function() {{ scorm.finish(scorm.score); }};
document.addEventListener('contextmenu', e => e.preventDefault());
</script>
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body, html {{
  width: 100%; height: 100%;
  background: #0f172a;
  font-family: 'Segoe UI', system-ui, sans-serif;
  overflow: hidden; user-select: none;
}}
/* ── Layout ── */
#container {{
  position: relative; width: 100%; height: 100%;
  display: flex; justify-content: center; align-items: center;
}}
#bg-image {{
  width: 100%; height: 100%; object-fit: contain;
  opacity: 0; transition: opacity 0.25s ease;
}}
#bg-image.visible {{ opacity: 1; }}
/* ── Progresso ── */
#progress-track {{
  position: absolute; top: 0; left: 0; width: 100%; height: 3px; z-index: 40;
  background: rgba(255,255,255,0.08);
}}
#progress-fill {{
  height: 100%; background: linear-gradient(90deg, #00e5e5, #7c3aed);
  transition: width 0.4s cubic-bezier(0.4,0,0.2,1); width: 0%;
}}
/* ── Spotlight overlay ── */
#spotlight {{
  position: absolute; inset: 0; pointer-events: none; z-index: 8;
  opacity: 0; transition: opacity 0.3s;
}}
#spotlight.active {{ opacity: 1; }}
/* ── Zonas interativas ── */
.izone {{
  position: absolute; transform: translate(-50%, -50%);
  border-radius: 6px; z-index: 15;
  background: transparent; border: 2px solid transparent;
  transition: box-shadow 0.2s, border 0.2s;
}}
#zone-btn {{ cursor: pointer; }}
#zone-input {{
  background: rgba(255,255,255,0.98);
  border: 2px solid #00e5e5; outline: none;
  padding: 0 10px; font-size: 14px; color: #1f2937;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}}
#zone-input:focus {{ box-shadow: 0 0 0 3px rgba(0,229,229,0.35); }}
/* ── Tooltip callout (padrão Arcade) ── */
#callout {{
  position: absolute; z-index: 25; pointer-events: none;
  background: #1e293b; color: #f8fafc;
  padding: 10px 16px; border-radius: 10px;
  font-size: 13px; font-weight: 600; line-height: 1.4;
  max-width: 260px; text-align: center;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5);
  border: 1px solid rgba(255,255,255,0.12);
  opacity: 0; transform: translateY(6px);
  transition: opacity 0.25s, transform 0.25s;
  white-space: normal;
}}
#callout.show {{ opacity: 1; transform: translateY(0); }}
#callout::after {{
  content: ''; position: absolute; left: 50%; transform: translateX(-50%);
  border: 7px solid transparent;
}}
#callout.arrow-down::after {{
  bottom: -14px; border-top-color: #1e293b;
}}
#callout.arrow-up::after {{
  top: -14px; border-bottom-color: #1e293b;
}}
/* ── Hint pulse ── */
.hint-active {{
  animation: pulse 1.4s infinite alternate !important;
  border: 2px dashed rgba(0,229,229,0.85) !important;
  background: rgba(0,229,229,0.08) !important;
}}
@keyframes pulse {{
  from {{ box-shadow: 0 0 0 0 rgba(0,229,229,0.4); }}
  to   {{ box-shadow: 0 0 0 8px rgba(0,229,229,0); }}
}}
/* ── Success ── */
.success-glow {{
  border: 2px solid #10b981 !important;
  background: rgba(16,185,129,0.15) !important;
  box-shadow: 0 0 0 4px rgba(16,185,129,0.3), 0 0 20px rgba(16,185,129,0.5) !important;
}}
/* ── Error mask ── */
#error-mask {{
  position: absolute; inset: 0;
  box-shadow: inset 0 0 0 0 rgba(220,38,38,0);
  pointer-events: none; transition: box-shadow 0.25s; z-index: 20;
}}
.error-flash {{ box-shadow: inset 0 0 80px 20px rgba(220,38,38,0.45) !important; }}
/* ── Error pill ── */
#error-pill {{
  position: absolute; top: 20px; left: 50%;
  transform: translateX(-50%) translateY(-16px);
  background: rgba(220,38,38,0.95); color: #fff;
  padding: 9px 22px; border-radius: 50px;
  font-size: 13px; font-weight: 600;
  box-shadow: 0 8px 20px rgba(220,38,38,0.35);
  opacity: 0; pointer-events: none; z-index: 100;
  transition: all 0.35s cubic-bezier(0.34,1.56,0.64,1);
  display: flex; align-items: center; gap: 7px;
}}
#error-pill.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
/* ── Barra inferior ── */
#bar {{
  position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%);
  background: rgba(15,23,42,0.96); backdrop-filter: blur(16px);
  color: #f8fafc; padding: 10px 20px; border-radius: 100px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 12px 32px rgba(0,0,0,0.55);
  display: flex; align-items: center; gap: 10px;
  width: min(720px, 92vw); z-index: 30;
}}
.nbtn {{
  background: transparent; border: 1px solid rgba(255,255,255,0.18);
  color: #94a3b8; padding: 7px 14px; border-radius: 50px;
  cursor: pointer; font-size: 12px; font-weight: 700;
  transition: all 0.18s; display: flex; align-items: center; gap: 5px;
  white-space: nowrap; flex-shrink: 0;
}}
.nbtn:hover:not(:disabled) {{ background: rgba(255,255,255,0.1); color: #fff; border-color: rgba(255,255,255,0.4); }}
.nbtn:disabled {{ opacity: 0.28; cursor: not-allowed; }}
#btn-hint {{ border-color: rgba(0,229,229,0.5); color: #00e5e5; }}
#btn-hint:hover {{ background: #00e5e5 !important; color: #000 !important; border-color: #00e5e5 !important; }}
.bar-center {{ flex: 1; text-align: center; min-width: 0; }}
#bar-prefix {{ font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 2px; }}
#bar-text {{ font-size: 15px; font-weight: 500; line-height: 1.3; }}
#step-counter {{
  font-size: 11px; color: #475569; font-weight: 600;
  white-space: nowrap; flex-shrink: 0;
}}
/* ── Tela de intro ── */
#intro-screen {{
  position: absolute; inset: 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  display: flex; flex-direction: column;
  justify-content: center; align-items: center;
  color: #fff; z-index: 60; gap: 20px;
  padding: 40px;
}}
#intro-screen h1 {{ font-size: clamp(20px,3vw,32px); font-weight: 700; text-align: center; color: #f8fafc; }}
#intro-screen p  {{ font-size: 15px; color: #94a3b8; text-align: center; max-width: 480px; line-height: 1.6; }}
.intro-badge {{
  background: rgba(0,229,229,0.12); border: 1px solid rgba(0,229,229,0.3);
  color: #00e5e5; padding: 6px 16px; border-radius: 50px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.5px;
}}
#btn-start {{
  padding: 14px 40px; background: #00e5e5; color: #000;
  border: none; border-radius: 50px; font-size: 16px;
  cursor: pointer; font-weight: 800;
  box-shadow: 0 4px 20px rgba(0,229,229,0.35);
  transition: transform 0.15s, box-shadow 0.15s;
  margin-top: 8px;
}}
#btn-start:hover {{ transform: scale(1.04); box-shadow: 0 6px 28px rgba(0,229,229,0.5); }}
/* ── Tela final ── */
#end-screen {{
  position: absolute; inset: 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  display: none; flex-direction: column;
  justify-content: center; align-items: center;
  color: #fff; z-index: 50; gap: 14px; padding: 40px;
}}
#end-screen h1 {{ font-size: clamp(22px,3vw,34px); font-weight: 700; color: #f8fafc; text-align: center; }}
#end-screen p  {{ font-size: 15px; color: #94a3b8; text-align: center; }}
#score-ring {{
  width: 100px; height: 100px; border-radius: 50%;
  background: conic-gradient(#00e5e5 0%, #7c3aed 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 30px rgba(0,229,229,0.3);
}}
#score-ring-inner {{
  width: 78px; height: 78px; border-radius: 50%;
  background: #0f172a;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800; color: #00e5e5;
}}
#btn-finish {{
  padding: 12px 36px; background: #00e5e5; color: #000;
  border: none; border-radius: 50px; font-size: 15px;
  cursor: pointer; font-weight: 800;
  box-shadow: 0 4px 16px rgba(0,229,229,0.3);
  transition: transform 0.15s; margin-top: 8px;
}}
#btn-finish:hover {{ transform: scale(1.04); }}
/* ── Wrong click area ── */
#wrong-area {{ position: absolute; inset: 0; z-index: 5; cursor: default; }}
</style>
</head>
<body>
<div id="intro-screen">
  <span class="intro-badge">🎓 SIMULADOR INTERATIVO</span>
  <h1>{titulo}</h1>
  <p>Pratique o fluxo clicando nos elementos indicados. Siga as instruções na barra inferior e avance passo a passo.</p>
  <button id="btn-start" onclick="iniciar()">Começar Simulação &#8594;</button>
</div>

<div id="container" style="display:none;">
  <div id="progress-track"><div id="progress-fill"></div></div>
  <img id="bg-image" src="" alt="">
  <canvas id="spotlight"></canvas>
  <div id="wrong-area"></div>
  <div id="zone-btn"   class="izone" style="display:none;"></div>
  <input id="zone-input" class="izone" style="display:none;" autocomplete="off">
  <div id="callout"></div>
  <div id="error-mask"></div>
  <div id="error-pill">❌ Local incorreto. Tente novamente.</div>
  <div id="bar" style="display:none;">
    <button class="nbtn" id="btn-prev" onclick="ir(-1)">&#8592; Voltar</button>
    <div class="bar-center">
      <div id="bar-prefix"></div>
      <div id="bar-text"></div>
    </div>
    <span id="step-counter"></span>
    <button class="nbtn" id="btn-hint" onclick="dica()">💡 Ajuda</button>
    <button class="nbtn" id="btn-next" onclick="ir(1)" style="display:none;">Avançar &#8594;</button>
  </div>
</div>

<div id="end-screen">
  <div id="score-ring"><div id="score-ring-inner" id="score-pct">—</div></div>
  <h1>Simulação Concluída!</h1>
  <p id="score-detail">A sua participação foi registrada na plataforma.</p>
  <button id="btn-finish" onclick="finalizar()">Finalizar &#10003;</button>
</div>

<script>
(function() {{
  const slides = {slides_json};
  let cur = 0, acertos = 0, erros = 0, hintTimer = null;
  let audioAtual = null;

  // ── Áudio via arquivos copiados no pacote ────────────────────────────────
  function tocarAudio(audioId) {{
    if (!audioId) return;
    if (audioAtual) {{ audioAtual.pause(); audioAtual = null; }}

    // Tenta padrão novo (com hash) e legado
    const candidatos = [
      `audios/audio_${{audioId.replace('_ancora','_ancora').replace('_micro_','_micro_')}}.mp3`,
      `audios/audio_passo_${{audioId}}.mp3`
    ];

    // Busca pelo prefixo (padrão com hash no nome)
    const parts = audioId.split('_');
    const idPasso = parts[0];
    const sufixo  = parts.slice(1).join('_');
    // Usa fetch para listar não é possível em SCORM; tenta diretamente
    const src = `audios/audio_${{idPasso}}_${{sufixo}}`;
    audioAtual = new Audio(src + '.mp3');
    audioAtual.play().catch(() => {{
      // fallback legado
      audioAtual = new Audio(`audios/audio_passo_${{audioId}}.mp3`);
      audioAtual.play().catch(() => {{}});
    }});
  }}

  // ── Progresso ────────────────────────────────────────────────────────────
  function atualizarProgresso() {{
    const pct = slides.length ? (cur / slides.length) * 100 : 0;
    document.getElementById('progress-fill').style.width = pct + '%';
    const total = slides.filter(s => s.tipo === 'interacao').length;
    const feitos = slides.slice(0, cur).filter(s => s.tipo === 'interacao').length;
    document.getElementById('step-counter').textContent =
      total ? `${{feitos}} / ${{total}} ações` : '';
  }}

  // ── Spotlight canvas ─────────────────────────────────────────────────────
  function desenharSpotlight(xPix, yPix, wPix, hPix) {{
    const canvas = document.getElementById('spotlight');
    const container = document.getElementById('container');
    canvas.width  = container.clientWidth;
    canvas.height = container.clientHeight;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    const pad = 12;
    const rx = xPix - wPix/2 - pad, ry = yPix - hPix/2 - pad;
    const rw = wPix + pad*2,        rh = hPix + pad*2;
    ctx.save();
    ctx.globalCompositeOperation = 'destination-out';
    ctx.beginPath();
    ctx.roundRect(rx, ry, rw, rh, 8);
    ctx.fill();
    ctx.restore();
    canvas.classList.add('active');
  }}

  function limparSpotlight() {{
    const canvas = document.getElementById('spotlight');
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.classList.remove('active');
  }}

  // ── Callout tooltip ──────────────────────────────────────────────────────
  function mostrarCallout(xPix, yPix, hPix, texto) {{
    const el = document.getElementById('callout');
    el.textContent = texto;
    el.className = 'callout';
    el.style.display = 'block';

    // Posiciona acima ou abaixo dependendo do espaço
    const container = document.getElementById('container');
    const acima = yPix - hPix/2 > 80;
    el.style.left = xPix + 'px';
    el.style.transform = 'translateX(-50%)';

    if (acima) {{
      el.style.top  = (yPix - hPix/2 - 16) + 'px';
      el.style.bottom = 'auto';
      el.classList.add('arrow-down');
      el.style.transform = 'translateX(-50%) translateY(-100%)';
    }} else {{
      el.style.top  = (yPix + hPix/2 + 16) + 'px';
      el.style.bottom = 'auto';
      el.classList.add('arrow-up');
    }}

    requestAnimationFrame(() => el.classList.add('show'));
  }}

  function esconderCallout() {{
    const el = document.getElementById('callout');
    el.classList.remove('show');
  }}

  // ── Renderiza slide ──────────────────────────────────────────────────────
  function mostrar(index) {{
    clearTimeout(hintTimer);
    esconderCallout();
    limparSpotlight();

    const btn = document.getElementById('zone-btn');
    const inp = document.getElementById('zone-input');
    btn.style.display = 'none'; btn.className = 'izone';
    inp.style.display = 'none'; inp.className = 'izone'; inp.value = '';

    if (index >= slides.length) {{
      document.getElementById('bar').style.display = 'none';
      document.getElementById('container').style.display = 'none';
      const total = slides.filter(s => s.tipo === 'interacao').length;
      const pct   = total ? Math.round((acertos / total) * 100) : 100;
      scorm.score = pct;
      document.getElementById('score-ring-inner').textContent = pct + '%';
      document.getElementById('score-detail').textContent =
        `${{acertos}} acerto${{acertos !== 1 ? 's' : ''}} de ${{total}} interaç${{total !== 1 ? 'ões' : 'ão'}} (${{pct}}%)`;
      // Anima o anel de score
      document.getElementById('score-ring').style.background =
        `conic-gradient(#00e5e5 ${{pct}}%, rgba(255,255,255,0.08) ${{pct}}%)`;
      document.getElementById('end-screen').style.display = 'flex';
      return;
    }}

    const s = slides[index];
    const bg = document.getElementById('bg-image');

    atualizarProgresso();
    tocarAudio(s.audio_id);

    // Troca de imagem com fade
    if (s.imagem_b64 && bg.src !== 'data:image/jpeg;base64,' + s.imagem_b64) {{
      bg.classList.remove('visible');
      setTimeout(() => {{
        bg.src = 'data:image/jpeg;base64,' + s.imagem_b64;
        bg.onload = () => bg.classList.add('visible');
      }}, 120);
    }} else if (s.imagem_b64 && !bg.classList.contains('visible')) {{
      bg.classList.add('visible');
    }}

    const bar    = document.getElementById('bar');
    const prefix = document.getElementById('bar-prefix');
    const text   = document.getElementById('bar-text');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const btnHint = document.getElementById('btn-hint');

    btnPrev.disabled = (index === 0);
    bar.style.display = 'flex';
    text.innerHTML = s.texto || '';

    if (s.tipo === 'ancora') {{
      prefix.innerHTML = '💡 EXPLICAÇÃO';
      prefix.style.color = '#64748b';
      btnHint.style.display = 'none';
      btnNext.style.display = 'flex';
    }} else {{
      btnNext.style.display = 'none';
      btnHint.style.display = 'flex';
      const mapa = {{
        clique_direito:  ['🖱️ CLIQUE DIREITO', '#fbbf24'],
        digitar_e_enter: ['⌨️ DIGITE E ENTER',  '#a78bfa'],
        preencher_campo: ['⌨️ PREENCHA O CAMPO','#a78bfa'],
        duplo_clique:    ['🖱️ DUPLO CLIQUE',    '#60a5fa'],
      }};
      const [lbl, cor] = mapa[s.acao] || ['🎯 CLIQUE AQUI', '#00e5e5'];
      prefix.innerHTML = lbl; prefix.style.color = cor;

      const posicionar = () => {{
        const container = document.getElementById('container');
        const ir = bg.naturalWidth / bg.naturalHeight;
        const cr = container.clientWidth / container.clientHeight;
        let rw, rh, ox = 0, oy = 0;
        if (cr > ir) {{ rh = container.clientHeight; rw = rh * ir; ox = (container.clientWidth - rw) / 2; }}
        else         {{ rw = container.clientWidth;  rh = rw / ir; oy = (container.clientHeight - rh) / 2; }}

        const xp = ox + s.x_pct * rw;
        const yp = oy + s.y_pct * rh;
        const wp = Math.max((s.w_pct || 0) * rw, 28) + 8;
        const hp = Math.max((s.h_pct || 0) * rh, 28) + 8;

        desenharSpotlight(xp, yp, wp, hp);
        mostrarCallout(xp, yp, hp, s.label || s.texto.substring(0, 55));

        let zona;
        if (s.acao === 'digitar_e_enter' || s.acao === 'preencher_campo') {{
          zona = inp;
          inp.placeholder = s.valor_input ? 'Digite: ' + s.valor_input : 'Digite aqui...';
          inp.onkeydown = (e) => {{
            if (e.key !== 'Enter') return;
            const esp = (s.valor_input || '').trim().toLowerCase();
            const dig = inp.value.trim().toLowerCase();
            (dig === esp || esp === '') ? acertou(inp) : errouClique();
          }};
        }} else {{
          zona = btn;
          btn.onmousedown = (e) => {{
            e.stopPropagation();
            if (s.acao === 'clique_direito') {{
              e.button === 2 ? acertou(btn) : errouClique();
            }} else if (e.button === 0) {{
              acertou(btn);
            }}
          }};
          btn.ondblclick = (e) => {{
            e.stopPropagation();
            if (s.acao === 'duplo_clique') acertou(btn);
          }};
        }}

        zona.style.left = xp + 'px'; zona.style.top = yp + 'px';
        zona.style.width = wp + 'px'; zona.style.height = hp + 'px';
        zona.style.display = 'block';
        if (zona === inp) inp.focus();

        hintTimer = setTimeout(() => btn.classList.add('hint-active'), 8000);
      }};

      bg.complete && bg.naturalWidth ? posicionar() : (bg.onload = posicionar);
    }}
  }}

  function acertou(el) {{
    acertos++;
    esconderCallout();
    el.classList.remove('hint-active');
    el.classList.add('success-glow');
    setTimeout(() => {{ cur++; mostrar(cur); }}, 480);
  }}

  function errouClique() {{
    if (slides[cur]?.tipo !== 'interacao') return;
    erros++;
    const mask = document.getElementById('error-mask');
    const pill = document.getElementById('error-pill');
    mask.classList.add('error-flash');
    pill.classList.add('show');
    setTimeout(() => mask.classList.remove('error-flash'), 280);
    setTimeout(() => pill.classList.remove('show'), 2200);
  }}

  // ── Controles públicos ───────────────────────────────────────────────────
  window.iniciar = function() {{
    document.getElementById('intro-screen').style.display = 'none';
    document.getElementById('container').style.display = 'flex';
    document.getElementById('wrong-area').addEventListener('mousedown', (e) => {{
      if (e.button === 0 || e.button === 2) errouClique();
    }});
    mostrar(0);
  }};

  window.ir = function(delta) {{
    const novo = cur + delta;
    if (novo >= 0 && novo <= slides.length) {{ cur = novo; mostrar(cur); }}
  }};

  window.dica = function() {{
    clearTimeout(hintTimer);
    document.getElementById('zone-btn').classList.add('hint-active');
  }};

  window.finalizar = function() {{
    const total = slides.filter(s => s.tipo === 'interacao').length;
    const pct   = total ? Math.round((acertos / total) * 100) : 100;
    scorm.finish(pct);
    window.close();
  }};

  window.mostrarIntro = function() {{
    // chamado pelo onload — intro já está visível por padrão
  }};
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        criar_pacote_scorm(sys.argv[1])
    else:
        print("Uso: python scorm_builder.py <caminho_do_roteiro.json>")


import json
import os
import zipfile
import shutil
from pathlib import Path

from utils import limpar_nome


def criar_pacote_scorm(caminho_json, pasta_destino="scorm_exports"):
    """
    Lê o JSON do treinamento e empacota um arquivo .zip SCORM 1.2
    com player interativo em HTML/JS, agora com painel narrativo,
    Aura contextual e cenas pedagógicas mais ricas.
    """
    os.makedirs(pasta_destino, exist_ok=True)

    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", "Simulador Senior")
    id_treino = metadata.get("id_treinamento", nome_aula_raw)
    nome_arquivo_base = limpar_nome(id_treino)

    temp_dir = Path(f"temp_scorm_{nome_arquivo_base}")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    zip_path = Path(pasta_destino) / f"{nome_arquivo_base}_SCORM.zip"

    try:
        # 1. Copia áudios
        pasta_audio_origem = Path("audios_gerados") / nome_arquivo_base
        audio_dir_dest = temp_dir / "audios"
        audio_dir_dest.mkdir()
        if pasta_audio_origem.exists():
            for item in pasta_audio_origem.iterdir():
                if item.suffix.lower() == ".mp3":
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

        # 3. Slides enriquecidos
        passos = roteiro.get("passos", [])
        slides = []
        for idx, passo in enumerate(passos):
            id_p = passo.get("id_passo", idx + 1)
            pedagogia = passo.get("pedagogia", {}) or {}
            ancora = pedagogia.get("ancora", "")
            tooltip = pedagogia.get("tooltip_dap", "")
            alerta = passo.get("alerta_instrutor", "") or ""
            peso = passo.get("peso_narrativo", 2)
            tipo_passo = passo.get("tipo_passo", "navigation")

            # Âncora usa screenshot do passo ANTERIOR (estado da tela antes de começar)
            img_ancora = None
            if idx > 0:
                passo_anterior = passos[idx - 1]
                for acao in passo_anterior.get("acoes_tecnicas", []):
                    ref = acao.get("elemento_alvo", {}).get("screenshot_referencia")
                    if ref:
                        img_ancora = ref
                        break

            if ancora:
                slides.append({
                    "tipo": "ancora",
                    "scene_id": id_p,
                    "scene_kind": tipo_passo,
                    "scene_weight": peso,
                    "texto": ancora,
                    "tooltip": tooltip,
                    "alerta": alerta,
                    "audio_id": f"{id_p}_ancora",
                    "imagem_b64": img_ancora,
                })

            for i, acao in enumerate(passo.get("acoes_tecnicas", [])):
                if acao.get("acao") == "concluir_video":
                    continue

                alvo = acao.get("elemento_alvo", {}) or {}
                coords = alvo.get("coordenadas_relativas", {}) or {}

                slides.append({
                    "tipo": "interacao",
                    "scene_id": id_p,
                    "scene_kind": tipo_passo,
                    "scene_weight": peso,
                    "acao": acao.get("acao", "clique"),
                    "valor_input": acao.get("valor_input", ""),
                    "texto": acao.get(
                        "micro_narracao",
                        f"Interaja com {alvo.get('label_curto', 'o elemento')}"
                    ),
                    "tooltip": tooltip,
                    "alerta": alerta,
                    "label": alvo.get("label_curto", ""),
                    "audio_id": f"{id_p}_micro_{i}",
                    "imagem_b64": alvo.get("screenshot_referencia", "") or "",
                    "x_pct": coords.get("x_pct", 0.5),
                    "y_pct": coords.get("y_pct", 0.5),
                    "w_pct": coords.get("w_pct", 0.05),
                    "h_pct": coords.get("h_pct", 0.05),
                })

        slides_json = json.dumps(slides, ensure_ascii=False)
        html_content = _gerar_player_html(nome_aula_raw, slides_json)
        with open(temp_dir / "index.html", "w", encoding="utf-8") as f:
            f.write(html_content)

        # 4. Zipa o pacote
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, _dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    print(f"📦 Pacote SCORM gerado com sucesso: {zip_path}")
    return str(zip_path)



def _gerar_player_html(titulo: str, slides_json: str) -> str:
    html = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<script>
var scorm = {
  API: null,
  score: 0,
  init: function() {
    var w = window;
    while (w.API == null && w.parent != null && w.parent != w) w = w.parent;
    this.API = w.API;
    if (this.API) this.API.LMSInitialize("");
  },
  finish: function(pct) {
    if (this.API) {
      this.API.LMSSetValue("cmi.core.lesson_status", "completed");
      this.API.LMSSetValue("cmi.core.score.raw", String(Math.round(pct)));
      this.API.LMSSetValue("cmi.core.score.min", "0");
      this.API.LMSSetValue("cmi.core.score.max", "100");
      this.API.LMSCommit("");
      this.API.LMSFinish("");
    }
  }
};
window.onload = function() { scorm.init(); mostrarIntro(); };
window.onunload = function() { scorm.finish(scorm.score); };
document.addEventListener("contextmenu", e => e.preventDefault());
</script>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body, html {
  width: 100%; height: 100%;
  background: #0f172a;
  font-family: "Segoe UI", system-ui, sans-serif;
  overflow: hidden; user-select: none;
}

#container {
  position: relative; width: 100%; height: 100%;
  display: flex; justify-content: center; align-items: center;
}

#bg-image {
  width: 100%; height: 100%; object-fit: contain;
  opacity: 0; transition: opacity 0.25s ease;
}
#bg-image.visible { opacity: 1; }

/* progresso */
#progress-track {
  position: absolute; top: 0; left: 0; width: 100%; height: 3px; z-index: 40;
  background: rgba(255,255,255,0.08);
}
#progress-fill {
  height: 100%; width: 0%;
  background: linear-gradient(90deg, #00e5e5, #7c3aed);
  transition: width 0.4s cubic-bezier(0.4,0,0.2,1);
}

/* spotlight */
#spotlight {
  position: absolute; inset: 0; pointer-events: none; z-index: 8;
  opacity: 0; transition: opacity 0.3s;
}
#spotlight.active { opacity: 1; }

/* zonas interativas */
.izone {
  position: absolute; transform: translate(-50%, -50%);
  border-radius: 6px; z-index: 15;
  background: transparent; border: 2px solid transparent;
  transition: box-shadow 0.2s, border 0.2s;
}
#zone-btn { cursor: pointer; }
#zone-input {
  background: rgba(255,255,255,0.98);
  border: 2px solid #00e5e5; outline: none;
  padding: 0 10px; font-size: 14px; color: #1f2937;
  box-shadow: 0 4px 20px rgba(0,0,0,0.25);
}
#zone-input:focus { box-shadow: 0 0 0 3px rgba(0,229,229,0.35); }

/* callout */
#callout {
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
}
#callout.show { opacity: 1; transform: translateY(0); }
#callout::after {
  content: ""; position: absolute; left: 50%; transform: translateX(-50%);
  border: 7px solid transparent;
}
#callout.arrow-down::after { bottom: -14px; border-top-color: #1e293b; }
#callout.arrow-up::after { top: -14px; border-bottom-color: #1e293b; }

/* hint */
.hint-active {
  animation: pulse 1.4s infinite alternate !important;
  border: 2px dashed rgba(0,229,229,0.85) !important;
  background: rgba(0,229,229,0.08) !important;
}
@keyframes pulse {
  from { box-shadow: 0 0 0 0 rgba(0,229,229,0.4); }
  to   { box-shadow: 0 0 0 8px rgba(0,229,229,0); }
}

/* success */
.success-glow {
  border: 2px solid #10b981 !important;
  background: rgba(16,185,129,0.15) !important;
  box-shadow: 0 0 0 4px rgba(16,185,129,0.3), 0 0 20px rgba(16,185,129,0.5) !important;
}

/* erro */
#error-mask {
  position: absolute; inset: 0; pointer-events: none; z-index: 20;
  box-shadow: inset 0 0 0 0 rgba(245,158,11,0);
  transition: box-shadow 0.25s;
}
.error-flash {
  box-shadow: inset 0 0 48px 12px rgba(245,158,11,0.18) !important;
}

#error-pill {
  position: absolute; top: 20px; left: 50%;
  transform: translateX(-50%) translateY(-16px);
  background: rgba(245,158,11,0.96); color: #111827;
  padding: 10px 18px; border-radius: 999px;
  font-size: 13px; font-weight: 800;
  box-shadow: 0 8px 20px rgba(245,158,11,0.26);
  opacity: 0; pointer-events: none; z-index: 100;
  transition: all 0.35s cubic-bezier(0.34,1.56,0.64,1);
}
#error-pill.show {
  opacity: 1; transform: translateX(-50%) translateY(0);
}

/* painel narrativo */
#story-panel {
  position: absolute;
  top: 24px; right: 24px;
  width: min(420px, 34vw); min-width: 320px;
  max-height: calc(100vh - 48px);
  background: rgba(15,23,42,0.84);
  backdrop-filter: blur(18px);
  color: #f8fafc;
  border: 1px solid rgba(255,255,255,0.10);
  border-radius: 24px;
  box-shadow: 0 20px 48px rgba(0,0,0,0.45);
  z-index: 30;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width .22s ease;
}
#story-panel.collapsed { width: 290px; }

.story-head {
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 12px; padding: 16px 16px 8px 16px;
}
.story-kicker-wrap {
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
#scene-badge {
  background: rgba(0,229,229,0.12);
  border: 1px solid rgba(0,229,229,0.28);
  color: #00e5e5;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
}
#bar-prefix {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: #94a3b8;
}
.story-body { padding: 0 16px 12px 16px; }
.story-text {
  font-size: 18px; line-height: 1.5; font-weight: 600; color: #f8fafc;
}
#story-panel.collapsed .story-text {
  font-size: 15px; line-height: 1.4;
  max-height: 4.2em; overflow: hidden;
}
.story-tooltip {
  margin-top: 12px;
  background: rgba(15,118,110,0.18);
  border: 1px solid rgba(94,234,212,0.25);
  color: #ccfbf1;
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 12px; line-height: 1.45;
}
.story-alert {
  margin-top: 10px;
  background: rgba(245,158,11,0.14);
  border: 1px solid rgba(251,191,36,0.26);
  color: #fde68a;
  border-radius: 14px;
  padding: 10px 12px;
  font-size: 12px; line-height: 1.45;
}
.story-footer {
  display: flex; flex-direction: column; gap: 10px;
  padding: 0 16px 16px 16px;
}
.story-actions { display: flex; gap: 10px; flex-wrap: wrap; }

.icon-btn {
  width: 36px; height: 36px;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.12);
  background: rgba(255,255,255,0.06);
  color: #e2e8f0; cursor: pointer; flex-shrink: 0;
}
.icon-btn:hover {
  background: rgba(255,255,255,0.10);
  border-color: rgba(0,229,229,0.35);
}

.nbtn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.18);
  color: #e2e8f0;
  padding: 9px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  transition: all .18s;
}
.nbtn:hover:not(:disabled) {
  background: rgba(255,255,255,0.08);
  color: #fff;
  border-color: rgba(255,255,255,0.35);
}
.nbtn:disabled { opacity: .28; cursor: not-allowed; }
#btn-hint { border-color: rgba(0,229,229,0.35); color: #67e8f9; }
#step-counter {
  font-size: 11px; color: #94a3b8; font-weight: 700;
}

/* intro */
#intro-screen {
  position: absolute; inset: 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  display: flex; flex-direction: column; justify-content: center; align-items: center;
  color: #fff; z-index: 60; gap: 20px; padding: 40px;
}
#intro-screen h1 {
  font-size: clamp(20px,3vw,32px); font-weight: 700;
  text-align: center; color: #f8fafc;
}
#intro-screen p {
  font-size: 15px; color: #94a3b8;
  text-align: center; max-width: 520px; line-height: 1.6;
}
.intro-badge {
  background: rgba(0,229,229,0.12);
  border: 1px solid rgba(0,229,229,0.3);
  color: #00e5e5; padding: 6px 16px;
  border-radius: 50px; font-size: 12px; font-weight: 700; letter-spacing: 0.5px;
}
#btn-start {
  padding: 14px 40px; background: #00e5e5; color: #000;
  border: none; border-radius: 50px; font-size: 16px;
  cursor: pointer; font-weight: 800;
  box-shadow: 0 4px 20px rgba(0,229,229,0.35);
  transition: transform 0.15s, box-shadow 0.15s;
  margin-top: 8px;
}
#btn-start:hover {
  transform: scale(1.04);
  box-shadow: 0 6px 28px rgba(0,229,229,0.5);
}

/* final */
#end-screen {
  position: absolute; inset: 0;
  background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
  display: none; flex-direction: column;
  justify-content: center; align-items: center;
  color: #fff; z-index: 50; gap: 14px; padding: 40px;
}
#end-screen h1 {
  font-size: clamp(22px,3vw,34px); font-weight: 700; color: #f8fafc; text-align: center;
}
#end-screen p {
  font-size: 15px; color: #94a3b8; text-align: center; max-width: 520px;
}
#score-ring {
  width: 100px; height: 100px; border-radius: 50%;
  background: conic-gradient(#00e5e5 0%, #7c3aed 100%);
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 0 30px rgba(0,229,229,0.3);
}
#score-ring-inner {
  width: 78px; height: 78px; border-radius: 50%;
  background: #0f172a;
  display: flex; align-items: center; justify-content: center;
  font-size: 22px; font-weight: 800; color: #00e5e5;
}
#btn-finish {
  padding: 12px 36px; background: #00e5e5; color: #000;
  border: none; border-radius: 50px; font-size: 15px;
  cursor: pointer; font-weight: 800;
  box-shadow: 0 4px 16px rgba(0,229,229,0.3);
  transition: transform 0.15s; margin-top: 8px;
}
#btn-finish:hover { transform: scale(1.04); }

#wrong-area { position: absolute; inset: 0; z-index: 5; cursor: default; }
</style>
</head>
<body>
<div id="intro-screen">
  <span class="intro-badge">SENIOR PLAYBOOK ENGINE</span>
  <h1>__TITLE__</h1>
  <p>Aprenda o fluxo em contexto, pratique cada ação com foco guiado e avance com confiança operacional.</p>
  <button id="btn-start" onclick="iniciar()">Entrar na prática →</button>
</div>

<div id="container" style="display:none;">
  <div id="progress-track"><div id="progress-fill"></div></div>
  <img id="bg-image" src="" alt="">
  <canvas id="spotlight"></canvas>
  <div id="wrong-area"></div>
  <div id="zone-btn" class="izone" style="display:none;"></div>
  <input id="zone-input" class="izone" style="display:none;" autocomplete="off">
  <div id="callout"></div>
  <div id="error-mask"></div>
  <div id="error-pill">Quase. Tente olhar mais para a área destacada.</div>

  <div id="story-panel" class="collapsed" style="display:none;">
    <div class="story-head">
      <div class="story-kicker-wrap">
        <span id="scene-badge">CENA</span>
        <div id="bar-prefix"></div>
      </div>
      <button id="story-toggle" class="icon-btn" onclick="toggleStoryPanel()">✦</button>
    </div>

    <div class="story-body">
      <div id="bar-text" class="story-text"></div>
      <div id="story-tooltip" class="story-tooltip" style="display:none;"></div>
      <div id="story-alert" class="story-alert" style="display:none;"></div>
    </div>

    <div class="story-footer">
      <span id="step-counter"></span>
      <div class="story-actions">
        <button class="nbtn" id="btn-prev" onclick="ir(-1)">← Voltar</button>
        <button class="nbtn" id="btn-hint" onclick="dica()">Ajuda</button>
        <button class="nbtn" id="btn-next" onclick="ir(1)" style="display:none;">Avançar →</button>
      </div>
    </div>
  </div>
</div>

<div id="end-screen">
  <div id="score-ring"><div id="score-ring-inner">—</div></div>
  <h1>Habilidade desbloqueada</h1>
  <p id="score-detail">Você concluiu a prática principal deste fluxo.</p>
  <button id="btn-finish" onclick="finalizar()">Finalizar ✓</button>
</div>

<script>
(function() {
  const slides = __SLIDES__;
  let cur = 0, acertos = 0, erros = 0, hintTimer = null;
  let audioAtual = null;

  function tocarAudio(audioId) {
    if (!audioId) return;
    if (audioAtual) { audioAtual.pause(); audioAtual = null; }

    const src1 = `audios/audio_${audioId}.mp3`;
    const src2 = `audios/audio_passo_${audioId}.mp3`;

    audioAtual = new Audio(src1);
    audioAtual.play().catch(() => {
      audioAtual = new Audio(src2);
      audioAtual.play().catch(() => {});
    });
  }

  function atualizarProgresso() {
    const pct = slides.length ? (cur / slides.length) * 100 : 0;
    document.getElementById("progress-fill").style.width = pct + "%";
    const total = slides.filter(s => s.tipo === "interacao").length;
    const feitos = slides.slice(0, cur).filter(s => s.tipo === "interacao").length;
    document.getElementById("step-counter").textContent = total ? `${feitos} / ${total} ações` : "";
  }

  function desenharSpotlight(xPix, yPix, wPix, hPix) {
    const canvas = document.getElementById("spotlight");
    const container = document.getElementById("container");
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    ctx.fillStyle = "rgba(0,0,0,0.45)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const pad = 12;
    const rx = xPix - wPix/2 - pad, ry = yPix - hPix/2 - pad;
    const rw = wPix + pad*2, rh = hPix + pad*2;

    ctx.save();
    ctx.globalCompositeOperation = "destination-out";
    ctx.beginPath();
    if (ctx.roundRect) {
      ctx.roundRect(rx, ry, rw, rh, 8);
    } else {
      ctx.rect(rx, ry, rw, rh);
    }
    ctx.fill();
    ctx.restore();

    canvas.classList.add("active");
  }

  function limparSpotlight() {
    const canvas = document.getElementById("spotlight");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    canvas.classList.remove("active");
  }

  function mostrarCallout(xPix, yPix, hPix, texto) {
    const el = document.getElementById("callout");
    el.textContent = texto || "";
    el.className = "";
    el.style.display = "block";
    const acima = yPix - hPix/2 > 80;
    el.style.left = xPix + "px";
    el.style.transform = "translateX(-50%)";

    if (acima) {
      el.style.top = (yPix - hPix/2 - 16) + "px";
      el.classList.add("arrow-down");
      el.style.transform = "translateX(-50%) translateY(-100%)";
    } else {
      el.style.top = (yPix + hPix/2 + 16) + "px";
      el.classList.add("arrow-up");
    }

    requestAnimationFrame(() => el.classList.add("show"));
  }

  function esconderCallout() {
    const el = document.getElementById("callout");
    el.classList.remove("show");
  }

  function toggleStoryPanel() {
    const panel = document.getElementById("story-panel");
    panel.classList.toggle("collapsed");
  }
  window.toggleStoryPanel = toggleStoryPanel;

  function mostrar(index) {
    clearTimeout(hintTimer);
    esconderCallout();
    limparSpotlight();

    const btn = document.getElementById("zone-btn");
    const inp = document.getElementById("zone-input");
    btn.style.display = "none"; btn.className = "izone";
    inp.style.display = "none"; inp.className = "izone"; inp.value = "";

    if (index >= slides.length) {
      document.getElementById("story-panel").style.display = "none";
      document.getElementById("container").style.display = "none";

      const total = slides.filter(s => s.tipo === "interacao").length;
      const pct = total ? Math.round((acertos / total) * 100) : 100;
      scorm.score = pct;

      document.getElementById("score-ring-inner").textContent = pct + "%";
      document.getElementById("score-detail").textContent =
        `Você concluiu ${acertos} de ${total} ações com ${pct}% de aproveitamento. Continue para consolidar a habilidade no fluxo real.`;
      document.getElementById("score-ring").style.background =
        `conic-gradient(#00e5e5 ${pct}%, rgba(255,255,255,0.08) ${pct}%)`;
      document.getElementById("end-screen").style.display = "flex";
      return;
    }

    const s = slides[index];
    const bg = document.getElementById("bg-image");
    atualizarProgresso();
    tocarAudio(s.audio_id);

    if (s.imagem_b64 && bg.src !== "data:image/jpeg;base64," + s.imagem_b64) {
      // Imagem nova: seta src e aguarda onload para posicionar
      bg.classList.remove("visible");
      bg.onload = null;
      bg.src = "data:image/jpeg;base64," + s.imagem_b64;
      bg.onload = () => {
        bg.classList.add("visible");
        requestAnimationFrame(() => posicionar());
      };
    } else if (s.imagem_b64) {
      // Mesma imagem já carregada: aguarda reflow do container antes de posicionar
      if (!bg.classList.contains("visible")) bg.classList.add("visible");
      requestAnimationFrame(() => posicionar());
    } else {
      // Sem imagem: posiciona usando dimensões do container
      requestAnimationFrame(() => posicionar());
    }

    const bar = document.getElementById("story-panel");
    const prefix = document.getElementById("bar-prefix");
    const text = document.getElementById("bar-text");
    const tooltip = document.getElementById("story-tooltip");
    const alertBox = document.getElementById("story-alert");
    const badge = document.getElementById("scene-badge");
    const btnPrev = document.getElementById("btn-prev");
    const btnNext = document.getElementById("btn-next");
    const btnHint = document.getElementById("btn-hint");

    btnPrev.disabled = (index === 0);
    bar.style.display = "flex";
    text.innerHTML = s.texto || "";
    badge.textContent = `Cena ${s.scene_id || (index + 1)}`;

    if (s.tooltip) {
      tooltip.style.display = "block";
      tooltip.textContent = `Aura • ${s.tooltip}`;
    } else {
      tooltip.style.display = "none";
      tooltip.textContent = "";
    }

    if (s.alerta) {
      alertBox.style.display = "block";
      alertBox.textContent = `Atenção • ${s.alerta}`;
    } else {
      alertBox.style.display = "none";
      alertBox.textContent = "";
    }

    if (s.tipo === "ancora") {
      prefix.innerHTML = "Contexto da cena";
      prefix.style.color = "#94a3b8";
      btnHint.style.display = "none";
      btnNext.style.display = "inline-flex";
      return;
    }

    btnNext.style.display = "none";
    btnHint.style.display = "inline-flex";

    const mapa = {
      clique_direito: ["Clique direito", "#fbbf24"],
      digitar_e_enter: ["Digite e pressione Enter", "#a78bfa"],
      preencher_campo: ["Preencha o campo", "#a78bfa"],
      duplo_clique: ["Dê um duplo clique", "#60a5fa"],
    };
    const entry = mapa[s.acao] || ["Clique na área indicada", "#00e5e5"];
    prefix.innerHTML = entry[0];
    prefix.style.color = entry[1];

    const posicionar = () => {
      const container = document.getElementById("container");
      const ir = bg.naturalWidth / bg.naturalHeight;
      const cr = container.clientWidth / container.clientHeight;
      let rw, rh, ox = 0, oy = 0;

      if (cr > ir) {
        rh = container.clientHeight;
        rw = rh * ir;
        ox = (container.clientWidth - rw) / 2;
      } else {
        rw = container.clientWidth;
        rh = rw / ir;
        oy = (container.clientHeight - rh) / 2;
      }

      const xp = ox + s.x_pct * rw;
      const yp = oy + s.y_pct * rh;
      const wp = Math.max((s.w_pct || 0) * rw, 28) + 8;
      const hp = Math.max((s.h_pct || 0) * rh, 28) + 8;

      desenharSpotlight(xp, yp, wp, hp);
      mostrarCallout(xp, yp, hp, s.label || (s.texto || "").substring(0, 64));

      let zona;
      if (s.acao === "digitar_e_enter" || s.acao === "preencher_campo") {
        zona = inp;
        inp.placeholder = s.valor_input ? "Digite: " + s.valor_input : "Digite aqui...";
        inp.onkeydown = (e) => {
          if (e.key !== "Enter") return;
          const esp = (s.valor_input || "").trim().toLowerCase();
          const dig = inp.value.trim().toLowerCase();
          (dig === esp || esp === "") ? acertou(inp) : errouClique();
        };
      } else {
        zona = btn;
        btn.onmousedown = (e) => {
          e.stopPropagation();
          if (s.acao === "clique_direito") {
            e.button === 2 ? acertou(btn) : errouClique();
          } else if (e.button === 0) {
            acertou(btn);
          }
        };
        btn.ondblclick = (e) => {
          e.stopPropagation();
          if (s.acao === "duplo_clique") acertou(btn);
        };
      }

      zona.style.left = xp + "px";
      zona.style.top = yp + "px";
      zona.style.width = wp + "px";
      zona.style.height = hp + "px";
      zona.style.display = "block";

      if (zona === inp) inp.focus();
      hintTimer = setTimeout(() => zona.classList.add("hint-active"), 6500);
    };
  }

  function acertou(el) {
    acertos++;
    esconderCallout();
    clearTimeout(hintTimer);
    document.getElementById("story-alert").style.display = "none";
    el.classList.remove("hint-active");
    el.classList.add("success-glow");

    setTimeout(() => {
      cur++;
      mostrar(cur);
    }, 420);
  }

  function errouClique() {
    if (slides[cur] && slides[cur].tipo !== "interacao") return;
    erros++;
    const mask = document.getElementById("error-mask");
    const pill = document.getElementById("error-pill");
    mask.classList.add("error-flash");
    pill.classList.add("show");
    setTimeout(() => mask.classList.remove("error-flash"), 280);
    setTimeout(() => pill.classList.remove("show"), 2200);
  }

  window.iniciar = function() {
    document.getElementById("intro-screen").style.display = "none";
    document.getElementById("container").style.display = "flex";
    document.getElementById("wrong-area").addEventListener("mousedown", (e) => {
      if (e.button === 0 || e.button === 2) errouClique();
    });
    mostrar(0);
  };

  window.ir = function(delta) {
    const novo = cur + delta;
    if (novo >= 0 && novo <= slides.length) {
      cur = novo;
      mostrar(cur);
    }
  };

  window.dica = function() {
    clearTimeout(hintTimer);
    const btnZone = document.getElementById("zone-btn");
    const inputZone = document.getElementById("zone-input");
    const target = inputZone.style.display === "block" ? inputZone : btnZone;
    target.classList.add("hint-active");
  };

  window.finalizar = function() {
    const total = slides.filter(s => s.tipo === "interacao").length;
    const pct = total ? Math.round((acertos / total) * 100) : 100;
    scorm.finish(pct);
    window.close();
  };

  window.mostrarIntro = function() {};
})();
</script>
</body>
</html>"""
    return html.replace("__TITLE__", titulo).replace("__SLIDES__", slides_json)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python scorm_builder.py <caminho_do_roteiro.json>")
        sys.exit(1)
    try:
        criar_pacote_scorm(sys.argv[1])
    except FileNotFoundError:
        print(f"ERRO: arquivo de roteiro não encontrado: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)

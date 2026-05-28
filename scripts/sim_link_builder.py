"""
sim_link_builder.py
-------------------
Gera um SimLink — simulador interativo standalone a partir de um roteiro JSON.

Diferente do SCORM (que requer LMS), o SimLink é um único arquivo HTML
autocontido que pode ser:
  - aberto diretamente no navegador
  - hospedado em qualquer servidor estático
  - compartilhado via link direto (sem login, sem setup)

É a resposta ao GetDemo: mesma experiência de simulação clique-a-clique,
mas gerada automaticamente a partir do roteiro, com rastreamento opcional.
"""

import json
import os
import sys
from pathlib import Path

# Adiciona o diretório raiz ao path para importar utils.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from utils import limpar_nome


# ── Funções auxiliares (código idêntico ao scorm_builder.py) ─────────────────

def _selecionar_imagem_ancora(passos: list, idx: int) -> str | None:
    """
    Retorna a imagem de âncora para o passo de índice `idx`.

    Prioridade:
      1. screenshot_depois da última ação do passo anterior com valor não-vazio
      2. screenshot_referencia da última ação do passo anterior com valor não-vazio
      3. None (sem exceção)

    Para idx == 0, retorna None diretamente.
    """
    if idx == 0:
        return None
    acoes = passos[idx - 1].get("acoes_tecnicas", [])
    for acao in reversed(acoes):
        val = acao.get("elemento_alvo", {}).get("screenshot_depois")
        if val and isinstance(val, str):
            return val
    for acao in reversed(acoes):
        val = acao.get("elemento_alvo", {}).get("screenshot_referencia")
        if val and isinstance(val, str):
            return val
    return None


def _ler_viewport(acao: dict) -> tuple[int, int]:
    """
    Lê _vp_w/_vp_h com fallback em dois níveis:
      1. Nível da ação técnica (irmão de elemento_alvo) — fonte primária
      2. Dentro de elemento_alvo — fallback para roteiros legados
      3. 1920 × 1080 — padrão final
    """
    vp_w = acao.get("_vp_w") or 0
    vp_h = acao.get("_vp_h") or 0
    if not (vp_w > 0 and vp_h > 0):
        alvo = acao.get("elemento_alvo", {}) or {}
        vp_w = alvo.get("_vp_w") or 0
        vp_h = alvo.get("_vp_h") or 0
    if not (vp_w > 0 and vp_h > 0):
        vp_w, vp_h = 1920, 1080
    return int(vp_w), int(vp_h)


def _som_box_valido(som_box) -> bool:
    if not isinstance(som_box, dict):
        return False
    try:
        return (
            float(som_box["x"]) >= 0
            and float(som_box["y"]) >= 0
            and float(som_box["w"]) > 0
            and float(som_box["h"]) > 0
        )
    except (KeyError, TypeError, ValueError):
        return False


def _calcular_coords_som(
    som_box: dict, vp_w: int, vp_h: int
) -> tuple[float, float, float, float]:
    """
    Converte som_box_clicada (coordenadas absolutas) em percentuais [0.0, 1.0].
    Aplica clamping se os valores excederem os limites do viewport.
    """
    x_pct = min(max((som_box["x"] + som_box["w"] / 2) / vp_w, 0.0), 1.0)
    y_pct = min(max((som_box["y"] + som_box["h"] / 2) / vp_h, 0.0), 1.0)
    w_pct = min(max(som_box["w"] / vp_w, 0.0), 1.0)
    h_pct = min(max(som_box["h"] / vp_h, 0.0), 1.0)
    return x_pct, y_pct, w_pct, h_pct


def _resolver_coords(acao: dict) -> tuple[float, float, float, float]:
    """
    Resolve x_pct, y_pct, w_pct, h_pct para uma ação técnica.
    Prioridade: SoM → coordenadas_relativas → padrão 0.5/0.05
    """
    alvo = acao.get("elemento_alvo", {}) or {}
    som_box = alvo.get("som_box_clicada")
    vp_w, vp_h = _ler_viewport(acao)

    if _som_box_valido(som_box) and vp_w > 0 and vp_h > 0:
        return _calcular_coords_som(som_box, vp_w, vp_h)

    coords = alvo.get("coordenadas_relativas") or {}
    return (
        coords.get("x_pct", 0.5),
        coords.get("y_pct", 0.5),
        coords.get("w_pct", 0.05),
        coords.get("h_pct", 0.05),
    )


def criar_sim_link(caminho_json: str, pasta_destino: str = "sim_links") -> str:
    """
    Lê o roteiro JSON e gera um arquivo HTML standalone (SimLink).
    Retorna o caminho do arquivo gerado.
    """
    os.makedirs(pasta_destino, exist_ok=True)

    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", metadata.get("titulo", "Simulador Senior"))
    id_treino = metadata.get("id_treinamento", nome_aula_raw)
    nome_base = limpar_nome(id_treino)

    # ── Monta os slides (mesma lógica do scorm_builder) ──────────────────────
    slides = []
    pasta_audio = Path("audios_gerados") / nome_base
    passos = roteiro.get("passos", [])

    for idx, passo in enumerate(passos):
        id_p = passo.get("id_passo", idx + 1)
        ancora = passo.get("pedagogia", {}).get("ancora", "")

        img_ancora = _selecionar_imagem_ancora(passos, idx)

        if ancora:
            audio_ancora = _audio_b64(pasta_audio, id_p, "ancora")
            slides.append({
                "tipo": "ancora",
                "texto": ancora,
                "audio_b64": audio_ancora,
                "imagem_b64": img_ancora,
            })

        for i, acao in enumerate(passo.get("acoes_tecnicas", [])):
            if acao.get("acao") == "concluir_video":
                continue

            alvo = acao.get("elemento_alvo", {}) or {}
            x_pct, y_pct, w_pct, h_pct = _resolver_coords(acao)
            audio_micro = _audio_b64(pasta_audio, id_p, f"micro_{i}")

            slides.append({
                "tipo": "interacao",
                "acao": acao.get("acao", "clique"),
                "valor_input": acao.get("valor_input", ""),
                "texto": acao.get("micro_narracao", f"Interaja com {alvo.get('label_curto', 'o elemento')}"),
                "audio_b64": audio_micro,
                "imagem_b64": alvo.get("screenshot_referencia", "") or "",
                "x_pct": x_pct,
                "y_pct": y_pct,
                "w_pct": w_pct,
                "h_pct": h_pct,
            })

    slides_json = json.dumps(slides, ensure_ascii=False)
    html = _gerar_html(nome_aula_raw, slides_json)

    caminho_saida = Path(pasta_destino) / f"{nome_base}_SimLink.html"
    with open(caminho_saida, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"🔗 SimLink gerado: {caminho_saida}")
    return str(caminho_saida)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _audio_b64(pasta_audio: Path, id_passo, sufixo: str) -> str | None:
    """Tenta localizar o arquivo de áudio e retorna como base64, ou None."""
    import base64

    # Padrão novo: audio_{id}_{sufixo}_{hash}.mp3
    if pasta_audio.exists():
        padrao = f"audio_{id_passo}_{sufixo}"
        for arq in pasta_audio.iterdir():
            if arq.name.startswith(padrao) and arq.suffix == ".mp3":
                return base64.b64encode(arq.read_bytes()).decode()

        # Padrão legado: audio_passo_{id}_{sufixo}.mp3
        padrao_legado = f"audio_passo_{id_passo}_{sufixo}.mp3"
        caminho_legado = pasta_audio / padrao_legado
        if caminho_legado.exists():
            return base64.b64encode(caminho_legado.read_bytes()).decode()

    return None


def _gerar_html(titulo: str, slides_json: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{titulo}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body, html {{
    width: 100%; height: 100%;
    background: #0f172a;
    font-family: 'Segoe UI', system-ui, sans-serif;
    overflow: hidden; user-select: none;
  }}
  #container {{
    position: relative; width: 100%; height: 100%;
    display: flex; justify-content: center; align-items: center;
  }}
  #bg-image {{
    width: 100%; height: 100%;
    object-fit: contain; transition: opacity 0.25s;
  }}
  /* ── Zonas interativas ── */
  .zone {{
    position: absolute; transform: translate(-50%, -50%);
    border-radius: 4px; z-index: 10;
    background: transparent; border: 2px solid transparent;
    transition: box-shadow 0.2s, border 0.2s;
  }}
  #zone-btn {{ cursor: pointer; }}
  #zone-input {{
    background: rgba(255,255,255,0.98);
    border: 2px solid #00e5e5; outline: none;
    padding: 0 8px; font-size: 14px; color: #1f2937;
    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
  }}
  #zone-input:focus {{ box-shadow: 0 0 0 3px rgba(0,229,229,0.4); }}
  .hint-active {{
    animation: pulse 1.5s infinite alternate !important;
    border: 2px dashed rgba(0,229,229,0.8) !important;
    background: rgba(0,229,229,0.1) !important;
  }}
  @keyframes pulse {{
    from {{ box-shadow: 0 0 5px rgba(0,229,229,0.2); }}
    to   {{ box-shadow: 0 0 15px rgba(0,229,229,0.6); }}
  }}
  .success-glow {{
    border: 2px solid #10b981 !important;
    background: rgba(16,185,129,0.2) !important;
    box-shadow: 0 0 20px rgba(16,185,129,0.8), inset 0 0 10px rgba(16,185,129,0.5) !important;
  }}
  /* ── Máscara de erro ── */
  #error-mask {{
    position: absolute; inset: 0;
    box-shadow: inset 0 0 0 0 rgba(255,0,0,0);
    pointer-events: none; transition: box-shadow 0.3s; z-index: 20;
  }}
  .error-flash {{ box-shadow: inset 0 0 100px 20px rgba(220,38,38,0.5) !important; }}
  /* ── Pílula de feedback ── */
  #wrong-pill {{
    position: absolute; top: 20px; left: 50%;
    transform: translateX(-50%) translateY(-20px);
    background: rgba(220,38,38,0.95); color: #fff;
    padding: 10px 24px; border-radius: 50px;
    font-size: 13px; font-weight: 600;
    box-shadow: 0 10px 25px rgba(220,38,38,0.4);
    opacity: 0; pointer-events: none; z-index: 100;
    transition: all 0.4s cubic-bezier(0.34,1.56,0.64,1);
    display: flex; align-items: center; gap: 8px;
  }}
  #wrong-pill.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
  /* ── Barra inferior ── */
  #bar {{
    position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
    background: rgba(15,23,42,0.95); backdrop-filter: blur(12px);
    color: #f8fafc; padding: 12px 25px; border-radius: 100px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 10px 30px rgba(0,0,0,0.6);
    display: flex; align-items: center; gap: 12px;
    min-width: 600px; max-width: 90%; z-index: 30;
  }}
  .nav-btn {{
    background: transparent; border: 1px solid rgba(255,255,255,0.2);
    color: #cbd5e1; padding: 8px 16px; border-radius: 50px;
    cursor: pointer; font-size: 13px; font-weight: 600;
    transition: all 0.2s; display: flex; align-items: center; gap: 6px;
    white-space: nowrap;
  }}
  .nav-btn:hover:not(:disabled) {{ background: rgba(255,255,255,0.1); color: #fff; border-color: #fff; }}
  .nav-btn:disabled {{ opacity: 0.3; cursor: not-allowed; }}
  #btn-hint {{ border-color: #00e5e5; color: #00e5e5; }}
  #btn-hint:hover {{ background: #00e5e5; color: #000; }}
  .center-text {{ flex: 1; text-align: center; }}
  #prefix {{ font-weight: 700; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 3px; }}
  #instruction {{ font-size: 16px; font-weight: 500; line-height: 1.3; }}
  /* ── Progresso ── */
  #progress-wrap {{
    position: absolute; top: 0; left: 0; width: 100%; height: 3px; z-index: 40;
  }}
  #progress-bar {{
    height: 100%; background: #00e5e5;
    transition: width 0.3s ease; width: 0%;
  }}
  /* ── Tela final ── */
  #end-screen {{
    position: absolute; inset: 0;
    background: rgba(15,23,42,0.97);
    display: none; flex-direction: column;
    justify-content: center; align-items: center;
    color: #fff; z-index: 50; gap: 16px;
  }}
  #end-screen h1 {{ font-size: 32px; font-weight: 700; color: #f8fafc; }}
  #end-screen p  {{ font-size: 15px; color: #94a3b8; }}
  #btn-restart {{
    margin-top: 12px; padding: 12px 35px;
    background: #00e5e5; color: #000; border: none;
    border-radius: 50px; font-size: 15px; cursor: pointer;
    font-weight: 700; box-shadow: 0 4px 15px rgba(0,229,229,0.3);
    transition: transform 0.15s;
  }}
  #btn-restart:hover {{ transform: scale(1.04); }}
  /* ── Área de clique errado ── */
  #wrong-area {{ position: absolute; inset: 0; z-index: 5; cursor: default; }}
</style>
</head>
<body>
<div id="container">
  <div id="progress-wrap"><div id="progress-bar"></div></div>
  <img id="bg-image" src="" style="display:none;" alt="">
  <div id="wrong-area"></div>
  <div id="zone-btn"   class="zone" style="display:none;"></div>
  <input id="zone-input" class="zone" style="display:none;" autocomplete="off">
  <div id="error-mask"></div>
  <div id="wrong-pill">❌ Clique no local incorreto. Tente novamente.</div>
  <div id="bar" style="display:none;">
    <button class="nav-btn" id="btn-prev" onclick="ir(-1)">&#8592; Voltar</button>
    <div class="center-text">
      <div id="prefix"></div>
      <div id="instruction"></div>
    </div>
    <button class="nav-btn" id="btn-hint" onclick="dica()">Ajuda</button>
    <button class="nav-btn" id="btn-next" onclick="ir(1)">Avançar &#8594;</button>
  </div>
</div>
<div id="end-screen">
  <svg width="72" height="72" viewBox="0 0 24 24" fill="none" stroke="#00e5e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>
  </svg>
  <h1>Simulação Concluída!</h1>
  <p id="score-text"></p>
  <button id="btn-restart" onclick="reiniciar()">Refazer Simulação</button>
</div>
<script>
(function() {{
  const slides = {slides_json};
  let cur = 0, acertos = 0, erros = 0, hintTimer = null;
  let audioAtual = null;

  // ── Áudio inline (base64) ─────────────────────────────────────────────────
  function tocarAudio(b64) {{
    if (!b64) return;
    if (audioAtual) {{ audioAtual.pause(); audioAtual = null; }}
    audioAtual = new Audio("data:audio/mp3;base64," + b64);
    audioAtual.play().catch(() => {{}});
  }}

  // ── Progresso ─────────────────────────────────────────────────────────────
  function atualizarProgresso() {{
    const pct = slides.length ? (cur / slides.length) * 100 : 0;
    document.getElementById("progress-bar").style.width = pct + "%";
  }}

  // ── Renderiza slide ───────────────────────────────────────────────────────
  function mostrar(index) {{
    clearTimeout(hintTimer);
    const btn = document.getElementById("zone-btn");
    const inp = document.getElementById("zone-input");
    btn.style.display = "none"; btn.className = "zone";
    inp.style.display = "none"; inp.className = "zone"; inp.value = "";

    if (index >= slides.length) {{
      document.getElementById("bar").style.display = "none";
      document.getElementById("bg-image").style.display = "none";
      const total = acertos + erros;
      const pct = total ? Math.round((acertos / total) * 100) : 100;
      document.getElementById("score-text").textContent =
        "Acertos: " + acertos + " de " + total + " interações (" + pct + "%)";
      document.getElementById("end-screen").style.display = "flex";
      return;
    }}

    const s = slides[index];
    const bg = document.getElementById("bg-image");
    const bar = document.getElementById("bar");
    const prefix = document.getElementById("prefix");
    const instr = document.getElementById("instruction");

    document.getElementById("btn-prev").disabled = (index === 0);
    bar.style.display = "flex";
    instr.innerHTML = s.texto || "";
    atualizarProgresso();

    if (s.imagem_b64) {{
      bg.src = "data:image/jpeg;base64," + s.imagem_b64;
      bg.style.display = "block";
    }}

    tocarAudio(s.audio_b64);

    if (s.tipo === "ancora") {{
      prefix.innerHTML = "💡 EXPLICAÇÃO:";
      prefix.style.color = "#94a3b8";
      document.getElementById("btn-hint").style.display = "none";
      document.getElementById("btn-next").style.display = "flex";
    }} else {{
      document.getElementById("btn-hint").style.display = "flex";
      document.getElementById("btn-next").style.display = "none";

      const labels = {{
        clique_direito: ["🖱️ CLIQUE DIREITO:", "#fbbf24"],
        digitar_e_enter: ["⌨️ DIGITE O TEXTO:", "#a78bfa"],
        preencher_campo: ["⌨️ DIGITE O TEXTO:", "#a78bfa"],
        duplo_clique: ["🖱️ DUPLO CLIQUE:", "#60a5fa"],
      }};
      const [lbl, cor] = labels[s.acao] || ["🎯 CLIQUE AQUI:", "#00e5e5"];
      prefix.innerHTML = lbl; prefix.style.color = cor;

      bg.complete ? posicionar(s) : (bg.onload = () => posicionar(s));
    }}
  }}

  function posicionar(s) {{
    const container = document.getElementById("container");
    const bg = document.getElementById("bg-image");
    const btn = document.getElementById("zone-btn");
    const inp = document.getElementById("zone-input");

    const ir = bg.naturalWidth / bg.naturalHeight;
    const cr = container.clientWidth / container.clientHeight;
    let rw, rh, ox = 0, oy = 0;
    if (cr > ir) {{
      rh = container.clientHeight; rw = rh * ir;
      ox = (container.clientWidth - rw) / 2;
    }} else {{
      rw = container.clientWidth; rh = rw / ir;
      oy = (container.clientHeight - rh) / 2;
    }}

    const xp = ox + s.x_pct * rw;
    const yp = oy + s.y_pct * rh;
    const wp = Math.max((s.w_pct || 0) * rw, 24) + 8;
    const hp = Math.max((s.h_pct || 0) * rh, 24) + 8;

    let zona;
    if (s.acao === "digitar_e_enter" || s.acao === "preencher_campo") {{
      zona = inp;
      inp.placeholder = s.valor_input ? "Digite: " + s.valor_input : "Digite aqui...";
      inp.onkeydown = (e) => {{
        if (e.key !== "Enter") return;
        const esp = (s.valor_input || "").trim().toLowerCase();
        const dig = inp.value.trim().toLowerCase();
        (dig === esp || esp === "") ? acertou(inp) : errouClique();
      }};
    }} else {{
      zona = btn;
      btn.onmousedown = (e) => {{
        e.stopPropagation();
        if (s.acao === "clique_direito") {{
          e.button === 2 ? acertou(btn) : errouClique();
        }} else if (s.acao === "duplo_clique") {{
          // tratado no ondblclick
        }} else if (e.button === 0) {{
          acertou(btn);
        }}
      }};
      btn.ondblclick = (e) => {{
        e.stopPropagation();
        if (s.acao === "duplo_clique") acertou(btn);
      }};
    }}

    zona.style.left = xp + "px"; zona.style.top = yp + "px";
    zona.style.width = wp + "px"; zona.style.height = hp + "px";
    zona.style.display = "block";
    if (zona === inp) inp.focus();

    hintTimer = setTimeout(() => btn.classList.add("hint-active"), 7000);
  }}

  function acertou(el) {{
    acertos++;
    el.classList.remove("hint-active");
    el.classList.add("success-glow");
    setTimeout(() => {{ cur++; mostrar(cur); }}, 500);
  }}

  function errouClique() {{
    if (slides[cur]?.tipo !== "interacao") return;
    erros++;
    const mask = document.getElementById("error-mask");
    const pill = document.getElementById("wrong-pill");
    mask.classList.add("error-flash");
    pill.classList.add("show");
    setTimeout(() => mask.classList.remove("error-flash"), 300);
    setTimeout(() => pill.classList.remove("show"), 2000);
  }}

  // ── Controles públicos ────────────────────────────────────────────────────
  window.ir = function(delta) {{
    const novo = cur + delta;
    if (novo >= 0 && novo <= slides.length) {{ cur = novo; mostrar(cur); }}
  }};

  window.dica = function() {{
    clearTimeout(hintTimer);
    document.getElementById("zone-btn").classList.add("hint-active");
  }};

  window.reiniciar = function() {{
    cur = 0; acertos = 0; erros = 0;
    document.getElementById("end-screen").style.display = "none";
    mostrar(0);
  }};

  // ── Init ──────────────────────────────────────────────────────────────────
  document.getElementById("wrong-area").addEventListener("mousedown", (e) => {{
    if (e.button === 0 || e.button === 2) errouClique();
  }});
  document.addEventListener("contextmenu", e => e.preventDefault());
  mostrar(0);
}})();
</script>
</body>
</html>"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        criar_sim_link(sys.argv[1])
    else:
        print("Uso: python sim_link_builder.py <caminho_do_roteiro.json>")

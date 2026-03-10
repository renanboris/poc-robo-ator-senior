import json
import os
import zipfile
import shutil
import re
from pathlib import Path

def criar_pacote_scorm(caminho_json, pasta_destino="scorm_exports"):
    """
    Lê o JSON do treinamento e empacota num arquivo .zip SCORM 1.2
    com um simulador interativo em HTML/JS moderno (Navegação Livre e Posicionamento Perfeito).
    """
    os.makedirs(pasta_destino, exist_ok=True)
    
    with open(caminho_json, 'r', encoding='utf-8') as f:
        roteiro = json.load(f)

    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", "Simulador Senior")
    id_treino = metadata.get("id_treinamento", "TREINAMENTO")
    nome_arquivo_base = re.sub(r'[\\/*?:"<>|]', "", nome_aula_raw).replace(" ", "_")
    
    # Prepara pasta temporária para montar o SCORM
    temp_dir = Path(f"temp_scorm_{nome_arquivo_base}")
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir()

    # 1. Copia os áudios usados neste treinamento
    pasta_audio_origem = Path("audios_gerados") / re.sub(r'[\\/*?:"<>|]', "", id_treino).replace(" ", "_")
    audio_dir_dest = temp_dir / "audios"
    audio_dir_dest.mkdir()
    
    if pasta_audio_origem.exists():
        for item in pasta_audio_origem.iterdir():
            if item.suffix == '.mp3':
                shutil.copy2(item, audio_dir_dest / item.name)

    # 2. Cria o arquivo imsmanifest.xml (Padrão SCORM 1.2)
    manifest_content = f"""<?xml version="1.0" standalone="no" ?>
<manifest identifier="SeniorTrainingOS" version="1"
          xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
          xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
          xsi:schemaLocation="http://www.imsproject.org/xsd/imscp_rootv1p1p2 imscp_rootv1p1p2.xsd
                              http://www.imsglobal.org/xsd/imsmd_rootv1p2p1 imsmd_rootv1p2p1.xsd
                              http://www.adlnet.org/xsd/adlcp_rootv1p2 adlcp_rootv1p2.xsd">
  <metadata>
    <schema>ADL SCORM</schema>
    <schemaversion>1.2</schemaversion>
  </metadata>
  <organizations default="B0">
    <organization identifier="B0">
      <title>{nome_aula_raw}</title>
      <item identifier="I_1" identifierref="R_1">
        <title>{nome_aula_raw}</title>
      </item>
    </organization>
  </organizations>
  <resources>
    <resource identifier="R_1" type="webcontent" adlcp:scormtype="sco" href="index.html">
      <file href="index.html"/>
    </resource>
  </resources>
</manifest>
"""
    with open(temp_dir / "imsmanifest.xml", "w", encoding="utf-8") as f:
        f.write(manifest_content)

    # 3. Processa os passos para o JS do Simulador
    slides = []
    
    for idx, passo in enumerate(roteiro.get("passos", [])):
        id_p = passo.get('id_passo', idx + 1)
        ancora = passo.get("pedagogia", {}).get("ancora", "")
        
        if ancora:
            slides.append({
                "tipo": "ancora",
                "texto": ancora,
                "audio_id": f"{id_p}_ancora",
                "imagem_b64": None
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
                "audio_id": f"{id_p}_micro_{i}",
                "imagem_b64": alvo.get("screenshot_referencia", ""),
                "x_pct": coords.get("x_pct", 0.5),
                "y_pct": coords.get("y_pct", 0.5),
                "w_pct": coords.get("w_pct", 0.05), 
                "h_pct": coords.get("h_pct", 0.05)  
            })

    # 4. Gera o index.html (O Player SCORM Interativo Avançado)
    slides_json = json.dumps(slides)
    
    html_content = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{nome_aula_raw}</title>
    <script>
        var scorm = {{
            API: null,
            init: function() {{
                var win = window;
                while (win.API == null && win.parent != null && win.parent != win) {{ win = win.parent; }}
                this.API = win.API;
                if (this.API) this.API.LMSInitialize("");
            }},
            finish: function() {{
                if (this.API) {{
                    this.API.LMSSetValue("cmi.core.lesson_status", "completed");
                    this.API.LMSCommit("");
                    this.API.LMSFinish("");
                }}
            }}
        }};
        window.onload = function() {{ scorm.init(); iniciarSimulador(); }};
        window.onunload = function() {{ scorm.finish(); }};
        
        // Impede o botão direito de abrir o menu nativo
        document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #111827; overflow: hidden; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; user-select: none; }}
        #container {{ position: relative; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; }}
        
        /* Imagem de Fundo (A Matemática vai cuidar do object-fit) */
        #bg-image {{ width: 100%; height: 100%; object-fit: contain; transition: opacity 0.3s; }}
        
        /* Zonas Interativas (Totalmente invisíveis por padrão) */
        .interactive-zone {{
            position: absolute; transform: translate(-50%, -50%);
            border-radius: 6px; z-index: 10;
            background: transparent; border: 2px solid transparent;
            transition: box-shadow 0.2s ease, border 0.2s ease;
        }}
        
        #hotspot-btn {{ cursor: pointer; }}
        
        #hotspot-input {{
            background: rgba(255, 255, 255, 0.95); border: 2px solid #00e5e5; outline: none;
            padding: 0 10px; font-size: 14px; font-family: inherit; color: #1f2937;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3); border-radius: 4px;
        }}
        #hotspot-input:focus {{ box-shadow: 0 0 0 3px rgba(0, 229, 229, 0.3); }}

        /* Estética Elegante do Hint (Borda suave, sem preenchimento verde duro) */
        .hint-active {{
            animation: pulse-border 1.5s infinite alternate !important;
            border: 2px dashed rgba(0, 229, 229, 0.8) !important;
            background: rgba(0, 229, 229, 0.1) !important;
        }}
        
        @keyframes pulse-border {{
            from {{ box-shadow: 0 0 5px rgba(0,229,229,0.2); }}
            to {{ box-shadow: 0 0 15px rgba(0,229,229,0.6); }}
        }}

        /* Estética de Sucesso (Glow Esmeralda) */
        .success-glow {{
            border: 2px solid #10b981 !important;
            background: rgba(16, 185, 129, 0.2) !important;
            box-shadow: 0 0 20px rgba(16, 185, 129, 0.8), inset 0 0 10px rgba(16, 185, 129, 0.5) !important;
        }}

        /* Máscara de Erro (Pisca Vermelho) */
        #error-mask {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            box-shadow: inset 0 0 0 0 rgba(255, 0, 0, 0); pointer-events: none;
            transition: box-shadow 0.3s ease-out; z-index: 20;
        }}
        .error-flash {{ box-shadow: inset 0 0 100px 20px rgba(220, 38, 38, 0.5) !important; }}

        /* Barra de Instruções Moderna com Navegação */
        #instruction-bar {{
            position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
            background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(12px);
            color: #f8fafc; padding: 12px 25px; border-radius: 100px;
            border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 30px rgba(0,0,0,0.6);
            display: flex; align-items: center; justify-content: space-between;
            min-width: 600px; max-width: 90%; z-index: 30;
        }}
        
        .nav-btn {{
            background: transparent; border: 1px solid rgba(255,255,255,0.2); color: #cbd5e1;
            padding: 8px 16px; border-radius: 50px; cursor: pointer; font-size: 13px; font-weight: 600;
            transition: all 0.2s; display: flex; align-items: center; gap: 6px;
        }}
        .nav-btn:hover:not(:disabled) {{ background: rgba(255,255,255,0.1); color: #fff; border-color: #fff; }}
        .nav-btn:disabled {{ opacity: 0.3; cursor: not-allowed; }}
        
        #btn-hint {{ border-color: #00e5e5; color: #00e5e5; }}
        #btn-hint:hover {{ background: #00e5e5; color: #000; }}

        .center-text {{ display: flex; flex-direction: column; text-align: center; flex-grow: 1; padding: 0 20px; }}
        #instruction-prefix {{ font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 3px; }}
        #instruction-text {{ font-size: 18px; font-weight: 500; line-height: 1.2; }}

        /* Tela de Conclusão */
        #end-screen {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(17, 24, 39, 0.95); display: none; flex-direction: column;
            justify-content: center; align-items: center; color: white; z-index: 50;
        }}
        
        #wrong-click-area {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 5; cursor: default; }}
    </style>
</head>
<body>
    <div id="container">
        <img id="bg-image" src="" style="display:none;">
        <div id="wrong-click-area"></div>
        
        <div id="hotspot-btn" class="interactive-zone" style="display:none;"></div>
        <input type="text" id="hotspot-input" class="interactive-zone" style="display:none;" placeholder="Digite e aperte Enter..." autocomplete="off">
        
        <div id="error-mask"></div>
        
        <div id="instruction-bar" style="display:none;">
            <button class="nav-btn" id="btn-prev" onclick="slideAnterior()">
                <span>&larr;</span> Voltar
            </button>
            
            <div class="center-text">
                <span id="instruction-prefix"></span>
                <span id="instruction-text"></span>
            </div>
            
            <div style="display: flex; gap: 8px;">
                <button class="nav-btn" id="btn-hint" onclick="forcarDica()">Ajuda</button>
                <button class="nav-btn" id="btn-next" onclick="proximoSlide()">
                    Avançar <span>&rarr;</span>
                </button>
            </div>
        </div>
    </div>
    
    <div id="end-screen">
        <svg width="80" height="80" viewBox="0 0 24 24" fill="none" stroke="#00e5e5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom: 20px;"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        <h1 style="color: #f8fafc; font-size: 36px; margin-bottom: 10px; font-weight: 700;">Treinamento Concluído!</h1>
        <p style="font-size: 16px; color: #94a3b8;">A sua participação foi registrada na plataforma.</p>
        <button onclick="scorm.finish(); window.close();" style="margin-top:30px; padding:12px 35px; background:#00e5e5; color:#000; border:none; border-radius:50px; font-size:16px; cursor:pointer; font-weight:bold; transition: transform 0.2s; box-shadow: 0 4px 15px rgba(0,229,229,0.3);">Finalizar Treinamento</button>
    </div>

    <script>
        const slides = {slides_json};
        let currentSlide = 0;
        let hintTimeout = null;

        function iniciarSimulador() {{
            document.getElementById('wrong-click-area').addEventListener('mousedown', (e) => {{
                if (e.button === 0 || e.button === 2) errouClique();
            }});
            mostrarSlide(0);
        }}

        function mostrarSlide(index) {{
            clearTimeout(hintTimeout);
            const btn = document.getElementById('hotspot-btn');
            const inp = document.getElementById('hotspot-input');
            
            // Reseta estilos de acerto e dica
            btn.style.display = 'none';
            btn.classList.remove('hint-active', 'success-glow');
            inp.style.display = 'none';
            inp.classList.remove('success-glow');
            inp.value = '';
            
            if (index >= slides.length) {{
                document.getElementById('end-screen').style.display = 'flex';
                document.getElementById('instruction-bar').style.display = 'none';
                document.getElementById('bg-image').style.display = 'none';
                return;
            }}

            const slide = slides[index];
            const instructionBar = document.getElementById('instruction-bar');
            const instructionPrefix = document.getElementById('instruction-prefix');
            const instructionText = document.getElementById('instruction-text');
            const bgImage = document.getElementById('bg-image');
            const btnPrev = document.getElementById('btn-prev');
            const btnHint = document.getElementById('btn-hint');

            // Controle do botão voltar
            btnPrev.disabled = (index === 0);
            
            instructionBar.style.display = 'flex';
            instructionText.innerHTML = slide.texto || "Aguarde...";

            if (slide.imagem_b64) {{
                // TELA INTERATIVA
                btnHint.style.display = 'flex';
                bgImage.src = "data:image/jpeg;base64," + slide.imagem_b64;
                bgImage.style.display = 'block';
                
                // Prefixo Visual
                if (slide.acao === 'clique_direito') {{
                    instructionPrefix.innerHTML = "🖱️ CLIQUE DIREITO:";
                    instructionPrefix.style.color = "#fbbf24"; 
                }} else if (slide.acao === 'digitar_e_enter' || slide.acao === 'preencher_campo') {{
                    instructionPrefix.innerHTML = "⌨️ DIGITE O TEXTO:";
                    instructionPrefix.style.color = "#a78bfa"; 
                }} else if (slide.acao === 'duplo_clique') {{
                    instructionPrefix.innerHTML = "🖱️ DUPLO CLIQUE:";
                    instructionPrefix.style.color = "#60a5fa"; 
                }} else {{
                    instructionPrefix.innerHTML = "🎯 CLIQUE AQUI:";
                    instructionPrefix.style.color = "#00e5e5"; 
                }}
                
                bgImage.onload = () => {{
                    // 🟢 O CÁLCULO MÁGICO DO OBJECT-FIT (Posicionamento Perfeito)
                    const container = document.getElementById('container');
                    const imgRatio = bgImage.naturalWidth / bgImage.naturalHeight;
                    const containerRatio = container.clientWidth / container.clientHeight;
                    
                    let renderWidth, renderHeight, offsetX = 0, offsetY = 0;
                    
                    // Descobre as dimensões reais da imagem renderizada na tela
                    if (containerRatio > imgRatio) {{
                        renderHeight = container.clientHeight;
                        renderWidth = renderHeight * imgRatio;
                        offsetX = (container.clientWidth - renderWidth) / 2;
                    }} else {{
                        renderWidth = container.clientWidth;
                        renderHeight = renderWidth / imgRatio;
                        offsetY = (container.clientHeight - renderHeight) / 2;
                    }}

                    // Aplica as porcentagens sobre a área visível real
                    const xPix = offsetX + (slide.x_pct * renderWidth);
                    const yPix = offsetY + (slide.y_pct * renderHeight);
                    
                    // Gordurinha de segurança de +16px para facilitar o acerto
                    const wPix = Math.max((slide.w_pct || 0) * renderWidth + 16, 40);
                    const hPix = Math.max((slide.h_pct || 0) * renderHeight + 16, 40);
                    
                    let activeZone;

                    if (slide.acao === 'digitar_e_enter' || slide.acao === 'preencher_campo') {{
                        activeZone = inp;
                        inp.onkeydown = (e) => {{
                            if (e.key === 'Enter') {{
                                const valorEsperado = (slide.valor_input || "").trim().toLowerCase();
                                const valorDigitado = inp.value.trim().toLowerCase();
                                if (valorDigitado === valorEsperado || valorEsperado === "") {{
                                    acertouAcao(inp);
                                }} else {{
                                    errouClique();
                                }}
                            }}
                        }};
                    }} else {{
                        activeZone = btn;
                        btn.onmousedown = (e) => {{
                            e.stopPropagation(); 
                            if (slide.acao === 'clique_direito' && e.button === 2) acertouAcao(btn);
                            else if (slide.acao === 'clique_direito' && e.button !== 2) errouClique();
                            else if (slide.acao === 'clique' && e.button === 0) acertouAcao(btn);
                        }};
                        
                        btn.ondblclick = (e) => {{
                            e.stopPropagation();
                            if (slide.acao === 'duplo_clique') acertouAcao(btn);
                        }};
                    }}

                    activeZone.style.left = xPix + 'px';
                    activeZone.style.top = yPix + 'px';
                    activeZone.style.width = wPix + 'px';
                    activeZone.style.height = hPix + 'px';
                    activeZone.style.display = 'block';
                    
                    if(activeZone === inp) inp.focus();
                    
                    // Auto-Dica discreta após 7 segundos de inatividade
                    hintTimeout = setTimeout(() => {{
                        if(activeZone === btn) btn.classList.add('hint-active');
                    }}, 7000);
                }};
            }} else {{
                // TELA DE ÂNCORA (Só texto)
                instructionPrefix.innerHTML = "💡 PRESTE ATENÇÃO:";
                instructionPrefix.style.color = "#94a3b8";
                btnHint.style.display = 'none';
                bgImage.style.display = 'none';
            }}
        }}

        function acertouAcao(elemento) {{
            // Animação de sucesso (Glow Esmeralda)
            elemento.classList.remove('hint-active');
            elemento.classList.add('success-glow');
            
            // Avança após a animação de meio segundo
            setTimeout(proximoSlide, 500);
        }}

        function errouClique() {{
            const slide = slides[currentSlide];
            if(slide.tipo !== "interacao") return; 
            
            const mask = document.getElementById('error-mask');
            mask.classList.add('error-flash');
            
            try {{
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                oscillator.type = 'square';
                oscillator.frequency.setValueAtTime(120, audioCtx.currentTime); 
                oscillator.connect(audioCtx.destination);
                oscillator.start();
                oscillator.stop(audioCtx.currentTime + 0.15);
            }} catch(e) {{}}

            setTimeout(() => {{ mask.classList.remove('error-flash'); }}, 300);
        }}

        function forcarDica() {{
            clearTimeout(hintTimeout);
            const btn = document.getElementById('hotspot-btn');
            if(btn.style.display === 'block') btn.classList.add('hint-active');
        }}

        function proximoSlide() {{
            currentSlide++;
            mostrarSlide(currentSlide);
        }}

        function slideAnterior() {{
            if (currentSlide > 0) {{
                currentSlide--;
                mostrarSlide(currentSlide);
            }}
        }}
    </script>
</body>
</html>
"""
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

    # 6. Limpa os arquivos temporários
    shutil.rmtree(temp_dir)
    print(f"📦 Pacote SCORM gerado com sucesso: {zip_path}")
    return str(zip_path)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        criar_pacote_scorm(sys.argv[1])
    else:
        print("Uso: python scorm_builder.py <caminho_do_roteiro.json>")
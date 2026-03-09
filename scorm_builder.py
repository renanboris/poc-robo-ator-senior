import json
import os
import zipfile
import shutil
import re
from pathlib import Path

def criar_pacote_scorm(caminho_json, pasta_destino="scorm_exports"):
    """
    Lê o JSON do treinamento e os áudios, e empacota num arquivo .zip SCORM 1.2
    com um simulador interativo em HTML/JS moderno (Test Me / Guide Me).
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
        
        # Tela de transição (apenas fala/âncora)
        if ancora:
            slides.append({
                "tipo": "ancora",
                "texto": ancora,
                "audio_id": f"{id_p}_ancora",
                "imagem_b64": None
            })
            
        # Telas interativas (cliques)
        for i, acao in enumerate(passo.get("acoes_tecnicas", [])):
            if acao.get("acao") == "concluir_video":
                continue
                
            alvo = acao.get("elemento_alvo", {})
            coords = alvo.get("coordenadas_relativas", {"x_pct": 0.5, "y_pct": 0.5})
            
            slides.append({
                "tipo": "interacao",
                "texto": acao.get("micro_narracao", f"Clique em {alvo.get('label_curto', 'aqui')}"),
                "audio_id": f"{id_p}_micro_{i}",
                "imagem_b64": alvo.get("screenshot_referencia", ""),
                "x_pct": coords.get("x_pct", 0.5),
                "y_pct": coords.get("y_pct", 0.5)
            })

    # 4. Gera o index.html (O Player SCORM Interativo)
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
    </script>
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; background: #000; overflow: hidden; font-family: 'Segoe UI', sans-serif; }}
        #container {{ position: relative; width: 100%; height: 100%; display: flex; justify-content: center; align-items: center; user-select: none; }}
        #bg-image {{ max-width: 100%; max-height: 100%; object-fit: contain; box-shadow: 0 0 20px rgba(0,0,0,0.8); transition: opacity 0.3s; }}
        
        /* O Hotspot: Começa invisível, brilha se demorar */
        #hotspot {{
            position: absolute; width: 60px; height: 60px; transform: translate(-50%, -50%);
            border-radius: 8px; cursor: pointer; z-index: 10;
            background: transparent; border: 2px solid transparent;
            transition: all 0.3s;
        }}
        
        /* Classe ativada após 5 segundos de inatividade */
        .hint-active {{
            animation: pulse-neon 1.5s infinite alternate !important;
            background: rgba(0, 229, 229, 0.25) !important;
            border: 2px dashed #00e5e5 !important;
        }}
        
        @keyframes pulse-neon {{
            from {{ box-shadow: 0 0 5px rgba(0,229,229,0.3); }}
            to {{ box-shadow: 0 0 20px rgba(0,229,229,0.8); }}
        }}

        /* Máscara de erro (pisca vermelho quando erra) */
        #error-mask {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            box-shadow: inset 0 0 0 0 rgba(255, 0, 0, 0); pointer-events: none;
            transition: box-shadow 0.3s ease-out; z-index: 20;
        }}
        .error-flash {{ box-shadow: inset 0 0 100px 20px rgba(255, 0, 0, 0.6) !important; }}

        /* Barra Inferior (Instruções Claras) */
        #instruction-bar {{
            position: absolute; bottom: 30px; left: 50%; transform: translateX(-50%);
            background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(10px);
            color: #fff; padding: 15px 30px; border-radius: 50px; font-size: 20px;
            border: 1px solid rgba(255,255,255,0.1); box-shadow: 0 10px 25px rgba(0,0,0,0.8);
            display: flex; align-items: center; gap: 20px; z-index: 30;
        }}
        
        #instruction-prefix {{ color: #00e5e5; font-weight: bold; font-size: 16px; text-transform: uppercase; letter-spacing: 1px; }}
        
        #btn-hint {{
            background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.2); 
            color: white; padding: 8px 16px; border-radius: 20px; cursor: pointer; 
            font-weight: bold; transition: all 0.2s; font-size: 14px;
        }}
        #btn-hint:hover {{ background: #009999; border-color: #00e5e5; }}

        /* Tela de Fim */
        #end-screen {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.9); display: none; flex-direction: column;
            justify-content: center; align-items: center; color: white; z-index: 50;
        }}
        
        /* Hitbox para cliques errados */
        #wrong-click-area {{ position: absolute; top: 0; left: 0; width: 100%; height: 100%; z-index: 5; cursor: default; }}
    </style>
</head>
<body>
    <div id="container">
        <img id="bg-image" src="" style="display:none;">
        <div id="wrong-click-area" onclick="errouClique()"></div>
        <div id="hotspot" onclick="acertouClique()" style="display:none;"></div>
        <div id="error-mask"></div>
        
        <div id="instruction-bar" style="display:none;">
            <div style="display: flex; flex-direction: column; line-height: 1.2;">
                <span id="instruction-prefix"></span>
                <span id="instruction-text" style="font-weight: 500;"></span>
            </div>
            <button id="btn-hint" onclick="forcarDica()">Ajuda</button>
        </div>
    </div>
    
    <div id="end-screen">
        <h1 style="color: #00e5e5; font-size: 40px; margin-bottom: 10px;">Treinamento Concluído!</h1>
        <p style="font-size: 18px; color: #aaa;">Sua pontuação foi registrada no sistema.</p>
        <button onclick="scorm.finish(); window.close();" style="margin-top:30px; padding:12px 30px; background:#009999; color:white; border:none; border-radius:50px; font-size:18px; cursor:pointer; font-weight:bold; transition: transform 0.2s;">Concluir e Fechar</button>
    </div>

    <script>
        const slides = {slides_json};
        let currentSlide = 0;
        let hintTimeout = null;

        function iniciarSimulador() {{
            mostrarSlide(0);
        }}

        function mostrarSlide(index) {{
            clearTimeout(hintTimeout); // Limpa o timer antigo
            const hotspot = document.getElementById('hotspot');
            hotspot.classList.remove('hint-active'); // Reseta o estado invisível
            
            if (index >= slides.length) {{
                document.getElementById('end-screen').style.display = 'flex';
                document.getElementById('instruction-bar').style.display = 'none';
                document.getElementById('bg-image').style.display = 'none';
                hotspot.style.display = 'none';
                return;
            }}

            const slide = slides[index];
            const instructionBar = document.getElementById('instruction-bar');
            const instructionPrefix = document.getElementById('instruction-prefix');
            const instructionText = document.getElementById('instruction-text');
            const bgImage = document.getElementById('bg-image');
            const btnHint = document.getElementById('btn-hint');

            instructionBar.style.display = 'flex';
            instructionText.innerHTML = slide.texto || "Avance para o próximo passo";

            if (slide.imagem_b64) {{
                // TELA INTERATIVA (Test Me / Guide Me)
                instructionPrefix.innerHTML = "🎯 SUA VEZ:";
                btnHint.style.display = 'block';
                
                bgImage.src = "data:image/jpeg;base64," + slide.imagem_b64;
                bgImage.style.display = 'block';
                
                // Aguarda a imagem carregar para calcular proporção
                bgImage.onload = () => {{
                    const rect = bgImage.getBoundingClientRect();
                    const xPix = rect.left + (slide.x_pct * rect.width);
                    const yPix = rect.top + (slide.y_pct * rect.height);
                    
                    hotspot.style.left = xPix + 'px';
                    hotspot.style.top = yPix + 'px';
                    hotspot.style.display = 'block';
                    
                    // Se o aluno não fizer nada por 5 segundos, aciona o Auto-Hint
                    hintTimeout = setTimeout(() => {{
                        hotspot.classList.add('hint-active');
                    }}, 5000);
                }};
            }} else {{
                // TELA DE ÂNCORA (Explicação)
                instructionPrefix.innerHTML = "💡 PRESTE ATENÇÃO:";
                btnHint.style.display = 'none';
                bgImage.style.display = 'none';
                hotspot.style.display = 'none';
                
                // Avança sozinho após 5 segundos
                setTimeout(() => {{ if(currentSlide === index) proximoSlide(); }}, 5000);
            }}
        }}

        function acertouClique() {{
            const hs = document.getElementById('hotspot');
            hs.style.background = 'rgba(0, 255, 0, 0.5)';
            hs.style.border = '2px solid #00ff00';
            hs.classList.remove('hint-active');
            setTimeout(proximoSlide, 300);
        }}

        function errouClique() {{
            const slide = slides[currentSlide];
            if(slide.tipo !== "interacao") return; 
            
            const mask = document.getElementById('error-mask');
            mask.classList.add('error-flash');
            
            // Beep de erro (Feedback auditivo)
            try {{
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioCtx.createOscillator();
                oscillator.type = 'square';
                oscillator.frequency.setValueAtTime(150, audioCtx.currentTime); 
                oscillator.connect(audioCtx.destination);
                oscillator.start();
                oscillator.stop(audioCtx.currentTime + 0.1);
            }} catch(e) {{}}

            setTimeout(() => {{ mask.classList.remove('error-flash'); }}, 300);
        }}

        function forcarDica() {{
            clearTimeout(hintTimeout);
            document.getElementById('hotspot').classList.add('hint-active');
        }}

        function proximoSlide() {{
            currentSlide++;
            mostrarSlide(currentSlide);
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
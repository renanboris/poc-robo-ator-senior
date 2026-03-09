from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn
import os
import json
import subprocess
import sys
import threading
import re

app = FastAPI(title="Senior Training OS")

# Configuração de pastas
os.makedirs("templates", exist_ok=True)
ROTEIROS_DIR = "roteiros_salvos"
os.makedirs(ROTEIROS_DIR, exist_ok=True)
VIDEOS_DIR = "videos_prontos"
os.makedirs(VIDEOS_DIR, exist_ok=True)

templates = Jinja2Templates(directory="templates")

# Monta a pasta de vídeos para poder ser acessada pelo navegador
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# 🟢 ESTADO GLOBAL DE TAREFAS
estado_servidor = {"ocupado": False, "mensagem": "", "erro": "", "sucesso": ""}

def executar_processo_bg(comando, msg_executando, msg_sucesso):
    global estado_servidor
    estado_servidor["ocupado"] = True
    estado_servidor["mensagem"] = msg_executando
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""

    try:
        # A CORREÇÃO SUPREMA DE ENCODING:
        # Força o Python filho a usar UTF-8 no terminal do Windows para não quebrar com emojis (✅)
        env_vars = os.environ.copy()
        env_vars["PYTHONIOENCODING"] = "utf-8"
        
        processo = subprocess.run(
            comando, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='replace',
            env=env_vars
        )
        
        if processo.returncode != 0:
            linhas_erro = processo.stderr.strip().split('\n')
            erro_curto = linhas_erro[-1] if linhas_erro and linhas_erro[-1] else "Processo abortado pelo usuário."
            estado_servidor["erro"] = f"Falha: {erro_curto}"
        else:
            estado_servidor["sucesso"] = msg_sucesso
    except Exception as e:
        estado_servidor["erro"] = str(e)
    finally:
        estado_servidor["ocupado"] = False

class NovaAulaReq(BaseModel):
    nome_aula: str
    objetivo: str

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return estado_servidor

@app.post("/api/limpar-status")
async def limpar_status():
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""
    return {"status": "ok"}

@app.get("/api/roteiros")
async def listar_roteiros():
    arquivos = [f for f in os.listdir(ROTEIROS_DIR) if f.endswith('.json')]
    roteiros = []
    for arq in arquivos:
        try:
            caminho_completo = os.path.join(ROTEIROS_DIR, arq)
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                nome_aula = dados.get("metadata", {}).get("nome_aula", arq.replace(".json", ""))
                nome_arquivo_base = re.sub(r'[\\/*?:"<>|]', "", nome_aula).replace(" ", "_")
                
                # Verifica se o vídeo mp4 já existe para esta aula
                video_path = os.path.join(VIDEOS_DIR, f"{nome_arquivo_base}.mp4")
                tem_video = os.path.exists(video_path)
                
                roteiros.append({
                    "arquivo": arq,
                    "nome": nome_aula,
                    "qtd_passos": len(dados.get("passos", [])),
                    "mtime": os.path.getmtime(caminho_completo),
                    "tem_video": tem_video,
                    "video_url": f"/videos/{nome_arquivo_base}.mp4" if tem_video else None
                })
        except: pass
    
    # Ordena colocando os salvos mais recentemente no topo
    roteiros.sort(key=lambda x: x["mtime"], reverse=True)
    return roteiros

@app.get("/api/roteiros/{arquivo}")
async def get_roteiro(arquivo: str):
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)

@app.post("/api/roteiros/{arquivo}")
async def salvar_roteiro(arquivo: str, request: Request):
    dados = await request.json()
    with open(os.path.join(ROTEIROS_DIR, arquivo), 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return {"status": "sucesso"}

@app.delete("/api/roteiros/{arquivo}")
async def excluir_roteiro(arquivo: str):
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)
        return {"status": "sucesso", "mensagem": "Roteiro excluído permanentemente!"}
    return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

@app.post("/api/gravar")
async def gravar_aula(req: NovaAulaReq):
    if estado_servidor["ocupado"]: return JSONResponse(status_code=400, content={"erro": "O robô já está em uso."})
    threading.Thread(target=executar_processo_bg, args=(
        [sys.executable, "capture.py", req.nome_aula, req.objetivo, "--auto"],
        "Aguardando você mapear a tela no Senior X...",
        "✅ Mapeamento concluído! A aula foi salva."
    )).start()
    return {"status": "iniciado"}

@app.post("/api/executar-robo/{arquivo}")
async def executar_robo(arquivo: str):
    if estado_servidor["ocupado"]: return JSONResponse(status_code=400, content={"erro": "O robô já está em uso."})
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    threading.Thread(target=executar_processo_bg, args=(
        [sys.executable, "main.py", caminho, "--record"],
        "Robô atuando na tela... Por favor, não mexa no mouse nem no teclado!",
        "✅ Atuação concluída! Você já pode renderizar o vídeo final."
    )).start()
    return {"status": "iniciado"}

@app.post("/api/renderizar/{arquivo}")
async def renderizar_video(arquivo: str):
    if estado_servidor["ocupado"]: return JSONResponse(status_code=400, content={"erro": "O robô já está em uso."})
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    threading.Thread(target=executar_processo_bg, args=(
        [sys.executable, "main.py", caminho, "--render"],
        "🎬 Renderizando o vídeo e extraindo o SRT... Isso pode levar um tempinho.",
        "🎉 SUCESSO! Vídeo gerado na pasta 'videos_prontos'."
    )).start()
    return {"status": "iniciado"}

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 SENIOR TRAINING OS - SERVIDOR INICIADO")
    print("👉 Acesse no navegador: http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import os
import json
import subprocess
import sys
import threading
import asyncio
import re
import sqlite3
import uuid

# 🟢 Importa o motor de inteligência do DAP (Aura)
import dap_engine

app = FastAPI(title="Senior Training OS")

# 🟢 Permite que a Extensão do Chrome comunique com o servidor local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Em produção, substitua pelo ID da extensão
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================
# 📁 CONFIGURAÇÃO DE DIRETÓRIOS E ARQUIVOS ESTÁTICOS
# ==============================================================
os.makedirs("templates", exist_ok=True)
ROTEIROS_DIR = "roteiros_salvos"
os.makedirs(ROTEIROS_DIR, exist_ok=True)
VIDEOS_DIR = "videos_prontos"
os.makedirs(VIDEOS_DIR, exist_ok=True)
SCORM_DIR = "scorm_exports"
os.makedirs(SCORM_DIR, exist_ok=True)
AUDIOS_DIR = "audios_gerados"
os.makedirs(AUDIOS_DIR, exist_ok=True)
PDF_DIR = "documentacao_pdf"
os.makedirs(PDF_DIR, exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# ==============================================================
# 🔄 GERENCIADOR DE TAREFAS EM BACKGROUND E ESTADO GLOBAL
# ==============================================================
estado_servidor = {
    "ocupado": False, 
    "mensagem": "", 
    "erro": "", 
    "sucesso": ""
}
processo_atual = None

def executar_processo_bg(comando, msg_executando, msg_sucesso):
    global estado_servidor, processo_atual
    
    estado_servidor["ocupado"] = True
    estado_servidor["mensagem"] = msg_executando
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""

    try:
        env_vars = os.environ.copy()
        env_vars["PYTHONIOENCODING"] = "utf-8"
        
        processo_atual = subprocess.Popen(
            comando, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True, 
            encoding='utf-8', 
            errors='replace', 
            env=env_vars
        )
        
        stdout, stderr = processo_atual.communicate()
        
        if processo_atual.returncode != 0:
            todas_as_linhas = (stdout + "\n" + stderr).strip().split('\n')
            erro_real = [linha for linha in todas_as_linhas if linha.strip()][-1] if todas_as_linhas else "Erro desconhecido."
            
            if "KeyboardInterrupt" in stderr or processo_atual.returncode < 0:
                estado_servidor["erro"] = "Execução interrompida pelo utilizador."
            else:
                estado_servidor["erro"] = f"Falha: {erro_real}"
        else:
            estado_servidor["sucesso"] = msg_sucesso
            
    except Exception as e:
        estado_servidor["erro"] = str(e)
    finally:
        estado_servidor["ocupado"] = False
        processo_atual = None

# ==============================================================
# 🚀 MODELOS DE DADOS
# ==============================================================
class NovaAulaReq(BaseModel):
    nome_aula: str
    objetivo: str

class RenomearReq(BaseModel):
    novo_nome: str

class DapRequest(BaseModel):
    image: str
    url: str
    prompt: str

# ==============================================================
# 🌐 ROTAS DA API PRINCIPAIS
# ==============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/metricas")
async def get_metricas():
    try:
        total_memorizado = 0
        sucesso_recuperacao = 0
        if os.path.exists("brain.db"): 
            with sqlite3.connect("brain.db") as conn:
                total_memorizado = conn.execute("SELECT COUNT(*) FROM memoria_semantica").fetchone()[0]
                sucesso_recuperacao = conn.execute("SELECT SUM(hits) FROM memoria_semantica").fetchone()[0] or 0

        qtd_aulas = len([f for f in os.listdir(ROTEIROS_DIR) if f.endswith('.json')])
        horas_poupadas = qtd_aulas * 6
        dinheiro_poupado = horas_poupadas * 150 
            
        return {
            "total_memorizado": total_memorizado, 
            "self_healing_hits": sucesso_recuperacao, 
            "horas_poupadas": horas_poupadas,
            "dinheiro_poupado": dinheiro_poupado,
            "total_aulas": qtd_aulas
        }
    except Exception:
        return {
            "total_memorizado": 0, "self_healing_hits": 0,
            "horas_poupadas": 0, "dinheiro_poupado": 0, "total_aulas": 0
        }

@app.get("/api/status")
async def get_status():
    return estado_servidor

@app.get("/api/status-stream")
async def status_stream(request: Request):
    async def event_generator():
        last_state = None
        while True:
            if await request.is_disconnected():
                break
            current_state = estado_servidor.copy()
            if current_state != last_state:
                yield f"data: {json.dumps(current_state)}\n\n"
                last_state = current_state
            await asyncio.sleep(0.5)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/limpar-status")
async def limpar_status():
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""
    return {"status": "ok"}
    
@app.post("/api/cancelar")
async def cancelar_processo():
    global processo_atual
    if processo_atual:
        processo_atual.terminate()
        return {"status": "cancelado"}
    return {"status": "inativo"}

@app.get("/api/roteiros")
async def listar_roteiros():
    arquivos = [f for f in os.listdir(ROTEIROS_DIR) if f.endswith('.json')]
    roteiros = []
    
    for arquivo in arquivos:
        try:
            caminho_completo = os.path.join(ROTEIROS_DIR, arquivo)
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                nome_aula_raw = dados.get("metadata", {}).get("nome_aula", arquivo.replace(".json", ""))
                id_treinamento = dados.get("metadata", {}).get("id_treinamento", nome_aula_raw)
                
                # Regra dos 40 caracteres para encontrar as pastas e arquivos gerados
                nome_arquivo_base = re.sub(r'[\\/*?:"<>|]', "", id_treinamento).replace(" ", "_")[:40].strip("_")
                
                tem_audio = os.path.exists(os.path.join(AUDIOS_DIR, nome_arquivo_base))
                tem_video = os.path.exists(os.path.join(VIDEOS_DIR, f"{nome_arquivo_base}.mp4"))
                tem_scorm = os.path.exists(os.path.join(SCORM_DIR, f"{nome_arquivo_base}_SCORM.zip"))
                tem_pdf = os.path.exists(os.path.join(PDF_DIR, f"{nome_arquivo_base}_Playbook.pdf"))
                
                roteiros.append({
                    "arquivo": arquivo, 
                    "nome": nome_aula_raw, 
                    "qtd_passos": len(dados.get("passos", [])),
                    "mtime": os.path.getmtime(caminho_completo), 
                    "tem_audio": tem_audio,
                    "tem_video": tem_video,
                    "tem_scorm": tem_scorm,
                    "tem_pdf": tem_pdf,
                    "video_url": f"/videos/{nome_arquivo_base}.mp4" if tem_video else None,
                    "scorm_url": f"/api/download-scorm/{nome_arquivo_base}" if tem_scorm else None,
                    "pdf_url": f"/api/download-pdf/{nome_arquivo_base}" if tem_pdf else None
                })
        except Exception:
            pass
            
    roteiros.sort(key=lambda x: x["mtime"], reverse=True)
    return roteiros

@app.get("/api/roteiros/{arquivo}")
async def get_roteiro(arquivo: str):
    try:
        with open(os.path.join(ROTEIROS_DIR, arquivo), 'r', encoding='utf-8') as f: 
            return json.load(f)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})

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
        return {"status": "sucesso"}
    return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})

@app.post("/api/gravar")
async def gravar_aula(req: NovaAulaReq):
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "capture.py", req.nome_aula, req.objetivo, "--auto"]
    threading.Thread(target=executar_processo_bg, args=(comando, "A mapear o ecrã no Senior X...", "✅ Mapeamento guardado com sucesso.")).start()
    return {"status": "iniciado"}

@app.post("/api/executar-robo/{arquivo}")
async def executar_robo(arquivo: str):
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "main.py", os.path.join(ROTEIROS_DIR, arquivo), "--record"]
    threading.Thread(target=executar_processo_bg, args=(comando, "Robô a atuar e a gravar áudios...", "✅ Atuação e gravação de áudios concluídas.")).start()
    return {"status": "iniciado"}

@app.post("/api/renderizar/{arquivo}")
async def renderizar_video(arquivo: str):
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "main.py", os.path.join(ROTEIROS_DIR, arquivo), "--render"]
    threading.Thread(target=executar_processo_bg, args=(comando, "A montar o vídeo final...", "🎉 Vídeo pronto e disponível!")).start()
    return {"status": "iniciado"}

@app.post("/api/gerar-scorm/{arquivo}")
async def gerar_scorm(arquivo: str):
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "scorm_builder.py", os.path.join(ROTEIROS_DIR, arquivo)]
    threading.Thread(target=executar_processo_bg, args=(comando, "A montar Simulador Interativo...", "📦 Pacote SCORM gerado com sucesso!")).start()
    return {"status": "iniciado"}

@app.get("/api/download-scorm/{nome_base}")
async def download_scorm(nome_base: str):
    caminho_zip = os.path.join(SCORM_DIR, f"{nome_base}_SCORM.zip")
    
    if os.path.exists(caminho_zip):
        return FileResponse(
            path=caminho_zip, 
            filename=f"{nome_base}_SCORM.zip", 
            media_type='application/zip'
        )
        
    return JSONResponse(status_code=404, content={"erro": "Ficheiro SCORM não encontrado."})

@app.post("/api/gerar-pdf/{arquivo}")
async def gerar_pdf(arquivo: str):
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "pdf_builder.py", os.path.join(ROTEIROS_DIR, arquivo)]
    threading.Thread(target=executar_processo_bg, args=(comando, "A montar E-book Playbook...", "📔 Digital Playbook gerado com sucesso!")).start()
    return {"status": "iniciado"}

@app.get("/api/download-pdf/{nome_base}")
async def download_pdf(nome_base: str):
    caminho_pdf = os.path.join(PDF_DIR, f"{nome_base}_Playbook.pdf")
    if os.path.exists(caminho_pdf):
        return FileResponse(path=caminho_pdf, filename=f"{nome_base}_Playbook.pdf", media_type='application/pdf')
    return JSONResponse(status_code=404, content={"erro": "PDF não encontrado."})

@app.post("/api/duplicar/{arquivo}")
async def duplicar_roteiro(arquivo: str):
    caminho_origem = os.path.join(ROTEIROS_DIR, arquivo)
    if not os.path.exists(caminho_origem):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
        
    with open(caminho_origem, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    # Cria um ID totalmente novo para não misturar os áudios e vídeos
    novo_id = str(uuid.uuid4())[:8]
    dados["metadata"]["nome_aula"] = dados["metadata"].get("nome_aula", "") + " (Cópia)"
    dados["metadata"]["id_treinamento"] = f"treinamento_{novo_id}"

    novo_arquivo = f"roteiro_{novo_id}.json"
    with open(os.path.join(ROTEIROS_DIR, novo_arquivo), 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
        
    return {"status": "sucesso", "novo_arquivo": novo_arquivo}

@app.post("/api/renomear/{arquivo}")
async def renomear_roteiro(arquivo: str, req: RenomearReq):
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
        
    with open(caminho, 'r', encoding='utf-8') as f:
        dados = json.load(f)

    # Muda SÓ o nome de exibição. O ID de arquitetura continua o mesmo!
    if "metadata" not in dados:
        dados["metadata"] = {}
    dados["metadata"]["nome_aula"] = req.novo_nome
    
    with open(caminho, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
        
    return {"status": "sucesso"}

# ==============================================================
# 🟢 NOVAS ROTAS: DAP EXTENSION (AURA)
# ==============================================================

@app.post("/analyze")
async def analyze_screen(req: DapRequest):
    """
    Recebe a imagem do ecrã e o contexto da Extensão Chrome (Aura)
    e invoca a IA para orientar o utilizador em tempo real.
    """
    resultado = await dap_engine.analisar_tela_dap(req.image, req.url, req.prompt)
    return resultado

@app.post("/api/ingest/{arquivo}")
async def ingestar_no_dap(arquivo: str):
    """
    Lê o JSON de um treino concluído e envia o conhecimento
    para o Pinecone, ensinando o assistente virtual.
    """
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
        
    with open(caminho, 'r', encoding='utf-8') as f:
        dados = json.load(f)
        
    res = dap_engine.ingestar_para_pinecone(dados)
    return res

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 SENIOR TRAINING OS INICIADO")
    print("👉 Aceda no navegador: http://localhost:8000")
    print("="*50 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000)   
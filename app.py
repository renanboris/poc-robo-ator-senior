from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
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
import sqlite3

app = FastAPI(title="Senior Training OS")

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

templates = Jinja2Templates(directory="templates")

# Monta a pasta de vídeos para poder ser acessada pelo player HTML
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

# Variável global para rastrear o processo em execução e permitir o cancelamento (Stop)
processo_atual = None

def executar_processo_bg(comando, msg_executando, msg_sucesso):
    global estado_servidor, processo_atual
    
    estado_servidor["ocupado"] = True
    estado_servidor["mensagem"] = msg_executando
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""

    try:
        # Força o Python filho a usar UTF-8 para não quebrar com caracteres especiais e emojis
        env_vars = os.environ.copy()
        env_vars["PYTHONIOENCODING"] = "utf-8"
        
        # Usamos Popen para ter o controle do processo e poder usar o terminate()
        processo_atual = subprocess.Popen(
            comando, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True, 
            encoding='utf-8', 
            errors='replace', 
            env=env_vars
        )
        
        # Aguarda terminar e captura as saídas do terminal
        stdout, stderr = processo_atual.communicate()
        
        # Verifica se o processo falhou
        if processo_atual.returncode != 0:
            # Pega o último print real do Python (seja no stdout ou stderr)
            todas_as_linhas = (stdout + "\n" + stderr).strip().split('\n')
            erro_real = [linha for linha in todas_as_linhas if linha.strip()][-1] if todas_as_linhas else "Erro desconhecido."
            
            # Só considera cancelamento se o processo foi literalmente assassinado (< 0) ou interrompido pelo teclado
            if "KeyboardInterrupt" in stderr or processo_atual.returncode < 0:
                estado_servidor["erro"] = "Execução interrompida pelo usuário."
            else:
                # Agora sim, se faltar o .env ou o playwright, a mensagem exata aparecerá no painel!
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

# ==============================================================
# 🌐 ROTAS DA API
# ==============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Renderiza a interface principal do Painel (index.html)."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/metricas")
async def get_metricas():
    """Consulta o banco SQLite e os arquivos para calcular o ROI e a IA."""
    try:
        # 1. Métricas do SQLite (Zero-Touch)
        total_memorizado = 0
        sucesso_recuperacao = 0
        if os.path.exists("brain.db"): 
            with sqlite3.connect("brain.db") as conn:
                total_memorizado = conn.execute("SELECT COUNT(*) FROM memoria_semantica").fetchone()[0]
                sucesso_recuperacao = conn.execute("SELECT SUM(hits) FROM memoria_semantica").fetchone()[0] or 0

        # 2. Métricas de ROI (Negócios)
        # Assumindo: 1 Roteiro pronto = 6 horas poupadas. 1 hora = R$ 80,00.
        qtd_aulas = len([f for f in os.listdir(ROTEIROS_DIR) if f.endswith('.json')])
        horas_poupadas = qtd_aulas * 6
        dinheiro_poupado = horas_poupadas * 80
            
        return {
            "total_memorizado": total_memorizado, 
            "sucesso_recuperacao": sucesso_recuperacao,
            "horas_poupadas": horas_poupadas,
            "dinheiro_poupado": dinheiro_poupado,
            "total_aulas": qtd_aulas
        }
    except Exception:
        return {
            "total_memorizado": 0, "sucesso_recuperacao": 0,
            "horas_poupadas": 0, "dinheiro_poupado": 0, "total_aulas": 0
        }

@app.get("/api/status")
async def get_status():
    """Retorna o estado atual do servidor para o Polling da interface Web."""
    return estado_servidor

@app.post("/api/limpar-status")
async def limpar_status():
    """Limpa as mensagens de erro ou sucesso após elas serem exibidas na tela."""
    estado_servidor["erro"] = ""
    estado_servidor["sucesso"] = ""
    return {"status": "ok"}
    
@app.post("/api/cancelar")
async def cancelar_processo():
    """Rota chamada pelo Botão de Pânico vermelho para matar o robô na hora."""
    global processo_atual
    if processo_atual:
        processo_atual.terminate() # Interrompe o processo imediatamente
        return {"status": "cancelado"}
    return {"status": "inativo"}

@app.get("/api/roteiros")
async def listar_roteiros():
    """Varre a pasta e retorna a lista de todos os roteiros mapeados."""
    arquivos = [f for f in os.listdir(ROTEIROS_DIR) if f.endswith('.json')]
    roteiros = []
    
    for arquivo in arquivos:
        try:
            caminho_completo = os.path.join(ROTEIROS_DIR, arquivo)
            with open(caminho_completo, 'r', encoding='utf-8') as f:
                dados = json.load(f)
                nome_aula = dados.get("metadata", {}).get("nome_aula", arquivo.replace(".json", ""))
                nome_arquivo_base = re.sub(r'[\\/*?:"<>|]', "", nome_aula).replace(" ", "_")
                
                # Verifica status do Vídeo
                tem_video = os.path.exists(os.path.join(VIDEOS_DIR, f"{nome_arquivo_base}.mp4"))
                
                # Verifica status do pacote SCORM
                tem_scorm = os.path.exists(os.path.join(SCORM_DIR, f"{nome_arquivo_base}_SCORM.zip"))
                
                roteiros.append({
                    "arquivo": arquivo, 
                    "nome": nome_aula, 
                    "qtd_passos": len(dados.get("passos", [])),
                    "mtime": os.path.getmtime(caminho_completo), 
                    "tem_video": tem_video,
                    "video_url": f"/videos/{nome_arquivo_base}.mp4" if tem_video else None,
                    "tem_scorm": tem_scorm,
                    "scorm_url": f"/api/download-scorm/{nome_arquivo_base}" if tem_scorm else None
                })
        except Exception:
            pass
            
    # Ordena colocando os arquivos modificados/criados mais recentemente no topo
    roteiros.sort(key=lambda x: x["mtime"], reverse=True)
    return roteiros

@app.get("/api/roteiros/{arquivo}")
async def get_roteiro(arquivo: str):
    """Lê e retorna o conteúdo completo de um Roteiro JSON específico."""
    try:
        with open(os.path.join(ROTEIROS_DIR, arquivo), 'r', encoding='utf-8') as f: 
            return json.load(f)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

@app.post("/api/roteiros/{arquivo}")
async def salvar_roteiro(arquivo: str, request: Request):
    """Salva as alterações feitas pelo usuário no Estúdio de Edição."""
    dados = await request.json()
    with open(os.path.join(ROTEIROS_DIR, arquivo), 'w', encoding='utf-8') as f: 
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return {"status": "sucesso"}

@app.delete("/api/roteiros/{arquivo}")
async def excluir_roteiro(arquivo: str):
    """Apaga o roteiro JSON permanentemente (Lixeira)."""
    caminho = os.path.join(ROTEIROS_DIR, arquivo)
    if os.path.exists(caminho): 
        os.remove(caminho)
        return {"status": "sucesso"}
    return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

@app.post("/api/gravar")
async def gravar_aula(req: NovaAulaReq):
    """Dispara o Mapeador de Tela (capture.py)."""
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "capture.py", req.nome_aula, req.objetivo, "--auto"]
    threading.Thread(target=executar_processo_bg, args=(comando, "Mapeando a tela no Senior X...", "✅ Mapeamento salvo com sucesso.")).start()
    return {"status": "iniciado"}

@app.post("/api/executar-robo/{arquivo}")
async def executar_robo(arquivo: str):
    """Dispara o robô atuador (main.py --record)."""
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "main.py", os.path.join(ROTEIROS_DIR, arquivo), "--record"]
    threading.Thread(target=executar_processo_bg, args=(comando, "Robô atuando... Por favor, não mexa no mouse!", "✅ Atuação concluída.")).start()
    return {"status": "iniciado"}

@app.post("/api/renderizar/{arquivo}")
async def renderizar_video(arquivo: str):
    """Dispara a pós-produção do MoviePy (main.py --render)."""
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    comando = [sys.executable, "main.py", os.path.join(ROTEIROS_DIR, arquivo), "--render"]
    threading.Thread(target=executar_processo_bg, args=(comando, "Renderizando vídeo final e extraindo legendas...", "🎉 Vídeo pronto e disponível!")).start()
    return {"status": "iniciado"}

# ==============================================================
# 📦 SCORM (SIMULADOR INTERATIVO)
# ==============================================================

@app.post("/api/gerar-scorm/{arquivo}")
async def gerar_scorm(arquivo: str):
    """Aciona o scorm_builder.py para empacotar o Simulador SCORM."""
    if estado_servidor["ocupado"]: 
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
        
    caminho_json = os.path.join(ROTEIROS_DIR, arquivo)
    comando = [sys.executable, "scorm_builder.py", caminho_json]
    
    threading.Thread(
        target=executar_processo_bg, 
        args=(comando, "Montando o Simulador Interativo (SCORM)...", "📦 Pacote SCORM gerado com sucesso!")
    ).start()
    return {"status": "iniciado"}

@app.get("/api/download-scorm/{nome_base}")
async def download_scorm(nome_base: str):
    """Rota para disparar o download do arquivo ZIP do SCORM para o PC do usuário."""
    caminho_zip = os.path.join(SCORM_DIR, f"{nome_base}_SCORM.zip")
    
    if os.path.exists(caminho_zip):
        return FileResponse(
            path=caminho_zip, 
            filename=f"{nome_base}_SCORM.zip", 
            media_type='application/zip'
        )
        
    return JSONResponse(status_code=404, content={"erro": "Arquivo SCORM não encontrado."})

# ==============================================================
# 🚀 PONTO DE ENTRADA DA APLICAÇÃO
# ==============================================================
if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 SENIOR TRAINING OS - SERVIDOR INICIADO")
    print("👉 Acesse no navegador: http://localhost:8000")
    print("="*50 + "\n")
    # Removido o reload=True para estabilizar o servidor (não reiniciar sozinho ao gerar arquivos)
    uvicorn.run("app:app", host="0.0.0.0", port=8000)
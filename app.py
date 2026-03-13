"""
app.py — Senior Training OS · API Principal
============================================
Atualizações Finais (Sprint 4):
  - Dashboard de ROI: Métricas de economia de horas e tokens (RAG e Cache).
  - Assincronismo Real: WebSockets no lugar de Polling para barra de progresso.
  - Otimizações prévias mantidas: Rate Limiting, JWT, Path Traversal, Locks.
"""

from fastapi import FastAPI, Request, HTTPException, Security, Depends, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
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
import logging
import time
import generator_engine
import lego_builder

import dap_engine

app = FastAPI(title="Senior Training OS")

# ==============================================================
# WEBSOCKET MANAGER (Sprint 4) & LIFECYCLE
# ==============================================================
main_loop = None

@app.on_event("startup")
async def startup_event():
    global main_loop
    main_loop = asyncio.get_running_loop()
    logging.info("WebSocket Event Loop capturado com sucesso.")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        # Envia o estado atual imediatamente após conectar
        with _estado_lock:
            current_state = estado_servidor.copy()
        await websocket.send_json(current_state)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

ws_manager = ConnectionManager()

# ==============================================================
# CONFIGURAÇÃO DE SEGURANÇA (CORS)
# ==============================================================
ALLOWED_ORIGINS_RAW = os.getenv("EXTENSION_ORIGIN", "")

if ALLOWED_ORIGINS_RAW and ALLOWED_ORIGINS_RAW != "*":
    _origins     = [o.strip() for o in ALLOWED_ORIGINS_RAW.split(",")]
    _credentials = True
else:
    _origins     = ["*"]
    _credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==============================================================
# RATE LIMITING IN-MEMORY (Proteção da API)
# ==============================================================
_rate_limit_cache = {}
MAX_REQUESTS_PER_MINUTE = 20

def verificar_rate_limit(ip: str):
    agora = time.time()
    _rate_limit_cache[ip] = [t for t in _rate_limit_cache.get(ip, []) if agora - t < 60]
    
    if len(_rate_limit_cache[ip]) >= MAX_REQUESTS_PER_MINUTE:
        logging.warning(f"Rate limit excedido para o IP: {ip}")
        raise HTTPException(status_code=429, detail="Limite de requisições excedido. Tente novamente em um minuto.")
    
    _rate_limit_cache[ip].append(agora)


# ==============================================================
# ESCUDO DE IDENTIDADE (Validação de Token)
# ==============================================================
API_KEY_NAME = "Authorization"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verificar_token(api_key: str = Security(api_key_header)):
    chave_mestra = f"Bearer {os.getenv('AURA_API_SECRET', 'senior_training_secreto_2026')}"
    
    if not api_key or api_key != chave_mestra:
        logging.warning("Tentativa de acesso bloqueada: Token inválido ou ausente.")
        raise HTTPException(status_code=401, detail="Acesso não autorizado. Credenciais inválidas.")
    return api_key


# ==============================================================
# FUNÇÕES DE HIGIENIZAÇÃO GLOBAL
# ==============================================================
def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

def _validar_caminho(nome_arquivo: str, diretorio_base: str) -> str:
    base    = os.path.realpath(diretorio_base)
    destino = os.path.realpath(os.path.join(diretorio_base, nome_arquivo))
    if not destino.startswith(base + os.sep) and destino != base:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    return destino


# ==============================================================
# DIRETÓRIOS E ARQUIVOS ESTÁTICOS
# ==============================================================
os.makedirs("templates", exist_ok=True)
ROTEIROS_DIR = "roteiros_salvos"; os.makedirs(ROTEIROS_DIR, exist_ok=True)
VIDEOS_DIR   = "videos_prontos";  os.makedirs(VIDEOS_DIR,   exist_ok=True)
SCORM_DIR    = "scorm_exports";   os.makedirs(SCORM_DIR,    exist_ok=True)
AUDIOS_DIR   = "audios_gerados";  os.makedirs(AUDIOS_DIR,   exist_ok=True)
PDF_DIR      = "documentacao_pdf";os.makedirs(PDF_DIR,      exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")

# ==============================================================
# GERENCIADOR DE TAREFAS EM BACKGROUND
# ==============================================================
_estado_lock = threading.Lock()

estado_servidor = {
    "ocupado":   False,
    "mensagem":  "",
    "progresso": None,
    "erro":      "",
    "sucesso":   "",
}
processo_atual = None

def _set_estado(**kwargs):
    mudou = False
    with _estado_lock:
        for k, v in kwargs.items():
            if estado_servidor.get(k) != v:
                estado_servidor[k] = v
                mudou = True
        estado_atualizado = estado_servidor.copy()

    # Se o estado mudou, empurra a atualização para os ecrãs ligados via WebSocket
    if mudou and main_loop:
        try:
            asyncio.run_coroutine_threadsafe(ws_manager.broadcast(estado_atualizado), main_loop)
        except Exception as e:
            logging.error(f"Erro ao disparar broadcast via WebSocket: {e}")

def executar_processo_bg(comando, msg_executando, msg_sucesso):
    global processo_atual
    _set_estado(ocupado=True, mensagem=msg_executando, progresso=None, erro="", sucesso="")

    try:
        env_vars = os.environ.copy()
        env_vars["PYTHONIOENCODING"] = "utf-8"

        with _estado_lock:
            processo_atual = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1,
                env=env_vars,
            )
            proc = processo_atual

        linhas_log = []
        for linha in iter(proc.stdout.readline, ""):
            linha_limpa = linha.strip()
            if linha_limpa:
                linhas_log.append(linha_limpa)
                if "PROGRESSO:" in linha_limpa:
                    try:
                        pct = int(linha_limpa.split("PROGRESSO:")[1].strip())
                        _set_estado(progresso=pct)
                    except Exception:
                        pass

        proc.wait()

        if proc.returncode != 0:
            erro_real  = "Erro desconhecido."
            for l in reversed(linhas_log):
                if "PROGRESSO:" not in l:
                    erro_real = l
                    break
            if proc.returncode < 0 or "KeyboardInterrupt" in "\n".join(linhas_log):
                _set_estado(erro="Execução interrompida pelo utilizador.")
            else:
                _set_estado(erro=f"Falha: {erro_real}")
        else:
            _set_estado(sucesso=msg_sucesso)

    except Exception as e:
        _set_estado(erro=str(e))
    finally:
        _set_estado(ocupado=False, progresso=None)
        with _estado_lock:
            processo_atual = None


# ==============================================================
# MODELOS DE DADOS (PYDANTIC)
# ==============================================================
class ElementoAlvo(BaseModel):
    descricao_visual:      Optional[str]            = ""
    contexto_tela:         Optional[str]            = ""
    tipo_elemento:         Optional[str]            = "button"
    confianca_captura:     Optional[str]            = "media"
    label_curto:           Optional[str]            = ""
    coordenadas_relativas: Optional[Dict[str, Any]] = Field(default_factory=dict)
    seletor_hint:          Optional[str]            = ""
    iframe_hint:           Optional[str]            = None
    html_hint:             Optional[str]            = ""
    screenshot_referencia: Optional[str]            = None

class AcaoTecnica(BaseModel):
    acao:               str
    intencao_semantica: Optional[str]           = ""
    elemento_alvo:      Optional[ElementoAlvo]  = Field(default_factory=ElementoAlvo)
    valor_input:        Optional[str]           = ""
    micro_narracao:     Optional[str]           = ""
    seletor_css:        Optional[str]           = ""

class Pedagogia(BaseModel):
    ancora:      Optional[str] = ""
    tooltip_dap: Optional[str] = ""

class PassoRoteiro(BaseModel):
    id_passo:         int
    tipo_passo:       Optional[str]               = "operacao"
    peso_narrativo:   Optional[int]               = 2
    pause_sugerida:   Optional[float]             = 2.5
    pedagogia:        Optional[Pedagogia]         = Field(default_factory=Pedagogia)
    alerta_instrutor: Optional[str]               = None
    is_conclusao:     Optional[bool]              = False
    acoes_tecnicas:   Optional[List[AcaoTecnica]] = Field(default_factory=list)

class ConfiguracaoGravacao(BaseModel):
    gravar_video:  bool = True
    pasta_destino: str  = "videos_gerados"
    voz_ia:        str  = "pt-BR-FranciscaNeural"

class RoteiroBase(BaseModel):
    metadata:              Dict[str, Any]
    configuracao_gravacao: Optional[ConfiguracaoGravacao] = None
    passos:                List[PassoRoteiro]

class NovaAulaReq(BaseModel):
    nome_aula: str
    objetivo:  str

class RenomearReq(BaseModel):
    novo_nome: str

class DapRequest(BaseModel):
    image:       str
    url:         str
    prompt:      str
    dom_context: Optional[str] = ""
    user_name:   Optional[str] = "Utilizador"
    tenant_id:   Optional[str] = "senior_default"
    historico:   Optional[list] = []


# ==============================================================
# ROTAS DA API
# ==============================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/metricas")
async def get_metricas():
    try:
        total_memorizado = sucesso_recuperacao = 0
        if os.path.exists("brain.db"):
            with sqlite3.connect("brain.db") as conn:
                total_memorizado    = conn.execute("SELECT COUNT(*) FROM memoria_semantica").fetchone()[0]
                sucesso_recuperacao = conn.execute("SELECT SUM(hits) FROM memoria_semantica").fetchone()[0] or 0
                
        dap_respostas_salvas = 0
        if os.path.exists("aura_cache.db"):
            with sqlite3.connect("aura_cache.db") as conn:
                dap_respostas_salvas = conn.execute("SELECT COUNT(*) FROM dap_cache").fetchone()[0]

        qtd_aulas = len([f for f in os.listdir(ROTEIROS_DIR) if f.endswith(".json")])

        # CÁLCULOS DE ROI
        horas_poupadas_aulas = qtd_aulas * 6
        economia_aulas_reais = horas_poupadas_aulas * 50
        economia_tokens_reais = (sucesso_recuperacao + dap_respostas_salvas) * 0.05

        return {
            "total_aulas":       qtd_aulas,
            "horas_poupadas":    horas_poupadas_aulas,
            "dinheiro_poupado":  economia_aulas_reais + economia_tokens_reais,
            "total_memorizado":  total_memorizado,          
            "self_healing_hits": sucesso_recuperacao,       
            "dap_cache_size":    dap_respostas_salvas,      
            "economia_tokens":   economia_tokens_reais      
        }
    except Exception as e:
        logging.error(f"Erro ao gerar métricas: {e}")
        return {
            "total_aulas": 0, "horas_poupadas": 0, "dinheiro_poupado": 0,
            "total_memorizado": 0, "self_healing_hits": 0, "dap_cache_size": 0, "economia_tokens": 0
        }

@app.get("/api/status")
async def get_status():
    with _estado_lock:
        return estado_servidor.copy()

# 🟢 SPRINT 4: A Nova Rota WebSocket (Substitui o Status-Stream antigo)
@app.websocket("/api/ws/status")
async def websocket_status(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Mantém a conexão aberta esperando qualquer mensagem (ping) do cliente
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logging.error(f"Erro na ligação WebSocket: {e}")
        ws_manager.disconnect(websocket)

@app.post("/api/limpar-status")
async def limpar_status():
    _set_estado(erro="", sucesso="")
    return {"status": "ok"}

@app.post("/api/cancelar")
async def cancelar_processo():
    with _estado_lock:
        proc = processo_atual
    if proc:
        proc.terminate()
        return {"status": "cancelado"}
    return {"status": "inativo"}

@app.get("/api/roteiros")
async def listar_roteiros():
    arquivos = [f for f in os.listdir(ROTEIROS_DIR) if f.endswith(".json")]
    roteiros = []
    for arquivo in arquivos:
        try:
            caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
            with open(caminho, "r", encoding="utf-8") as f:
                dados = json.load(f)
            nome_raw  = dados.get("metadata", {}).get("nome_aula", arquivo.replace(".json", ""))
            id_trein  = dados.get("metadata", {}).get("id_treinamento", nome_raw)
            base      = limpar_nome(id_trein)
            tem_video = os.path.exists(os.path.join(VIDEOS_DIR, f"{base}.mp4"))
            tem_scorm = os.path.exists(os.path.join(SCORM_DIR,  f"{base}_SCORM.zip"))
            tem_pdf   = os.path.exists(os.path.join(PDF_DIR,    f"{base}_Playbook.pdf"))
            roteiros.append({
                "arquivo":   arquivo, "nome": nome_raw,
                "qtd_passos": len(dados.get("passos", [])),
                "mtime":     os.path.getmtime(caminho),
                "tem_audio": os.path.exists(os.path.join(AUDIOS_DIR, base)),
                "tem_video": tem_video, "tem_scorm": tem_scorm, "tem_pdf": tem_pdf,
                "tem_coach": dados.get("metadata", {}).get("ingestado_dap", False),
                "video_url": f"/videos/{base}.mp4"           if tem_video else None,
                "scorm_url": f"/api/download-scorm/{base}"   if tem_scorm else None,
                "pdf_url":   f"/api/download-pdf/{base}"     if tem_pdf   else None,
            })
        except Exception:
            pass
    roteiros.sort(key=lambda x: x["mtime"], reverse=True)
    return roteiros

@app.get("/api/roteiros/{arquivo}")
async def get_roteiro(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

@app.post("/api/roteiros/{arquivo}")
async def salvar_roteiro(arquivo: str, roteiro: RoteiroBase):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    dados   = roteiro.model_dump() if hasattr(roteiro, "model_dump") else roteiro.dict()
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return {"status": "sucesso"}

@app.delete("/api/roteiros/{arquivo}")
async def excluir_roteiro(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    if os.path.exists(caminho):
        os.remove(caminho)
        return {"status": "sucesso"}
    return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

def _iniciar_bg(comando, msg_exec, msg_ok):
    with _estado_lock:
        if estado_servidor["ocupado"]:
            return False
    threading.Thread(target=executar_processo_bg, args=(comando, msg_exec, msg_ok), daemon=True).start()
    return True

@app.post("/api/gravar")
async def gravar_aula(req: NovaAulaReq):
    ok = _iniciar_bg([sys.executable, "capture.py", req.nome_aula, req.objetivo, "--auto"],
                     "A mapear o ecrã no Senior X...", "Mapeamento guardado com sucesso.")
    return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})

@app.post("/api/gerar-ia")
async def gerar_roteiro_via_prompt(req: NovaAulaReq):
    # Envia a tarefa pesada para rodar em background (thread) para não travar o FastAPI
    try:
        resultado = await asyncio.to_thread(
            generator_engine.gerar_roteiro_ia_sync, 
            req.nome_aula, 
            req.objetivo
        )
        
        if resultado.get("status") == "sucesso":
            # Dispara um evento WebSocket avisando que a aula mágica nasceu!
            _set_estado(sucesso=f"Aula '{req.nome_aula}' gerada por IA com sucesso!")
            return {"status": "sucesso", "arquivo": resultado.get("arquivo")}
        else:
            return JSONResponse(status_code=500, content={"erro": resultado.get("mensagem")})
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro": str(e)})

@app.post("/api/executar-robo/{arquivo}")
async def executar_robo(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    ok = _iniciar_bg([sys.executable, "main.py", caminho, "--record"],
                     "Robô a atuar e a gravar áudios...", "Atuação e gravação de áudios concluídas.")
    return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})

@app.post("/api/renderizar/{arquivo}")
async def renderizar_video(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    ok = _iniciar_bg([sys.executable, "main.py", caminho, "--render"],
                     "A montar o vídeo final...", "Vídeo pronto e disponível!")
    return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})

@app.post("/api/gerar-scorm/{arquivo}")
async def gerar_scorm(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    ok = _iniciar_bg([sys.executable, "scorm_builder.py", caminho],
                     "A montar Simulador Interativo...", "Pacote SCORM gerado com sucesso!")
    return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})

@app.post("/api/gerar-pdf/{arquivo}")
async def gerar_pdf(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    ok = _iniciar_bg([sys.executable, "pdf_builder.py", caminho],
                     "A montar E-book Playbook...", "Digital Playbook gerado com sucesso!")
    return {"status": "iniciado"} if ok else JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})

@app.get("/api/download-scorm/{nome_base}")
async def download_scorm(nome_base: str):
    nome_seguro = limpar_nome(nome_base)
    caminho_zip = os.path.join(SCORM_DIR, f"{nome_seguro}_SCORM.zip")
    if os.path.exists(caminho_zip):
        return FileResponse(path=caminho_zip, filename=f"{nome_seguro}_SCORM.zip", media_type="application/zip")
    return JSONResponse(status_code=404, content={"erro": "Ficheiro SCORM não encontrado."})

@app.get("/api/download-pdf/{nome_base}")
async def download_pdf(nome_base: str):
    nome_seguro = limpar_nome(nome_base)
    caminho_pdf = os.path.join(PDF_DIR, f"{nome_seguro}_Playbook.pdf")
    if os.path.exists(caminho_pdf):
        return FileResponse(path=caminho_pdf, filename=f"{nome_seguro}_Playbook.pdf", media_type="application/pdf")
    return JSONResponse(status_code=404, content={"erro": "PDF não encontrado."})

@app.post("/api/duplicar/{arquivo}")
async def duplicar_roteiro(arquivo: str):
    caminho_origem = _validar_caminho(arquivo, ROTEIROS_DIR)
    if not os.path.exists(caminho_origem):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
    with open(caminho_origem, "r", encoding="utf-8") as f:
        dados = json.load(f)
    novo_id = str(uuid.uuid4())[:8]
    dados["metadata"]["nome_aula"]      = dados["metadata"].get("nome_aula", "") + " (Cópia)"
    dados["metadata"]["id_treinamento"] = f"treinamento_{novo_id}"
    novo_arquivo = f"roteiro_{novo_id}.json"
    with open(os.path.join(ROTEIROS_DIR, novo_arquivo), "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    return {"status": "sucesso", "novo_arquivo": novo_arquivo}

@app.post("/api/renomear/{arquivo}")
async def renomear_roteiro(arquivo: str, req: RenomearReq):
    caminho_antigo = _validar_caminho(arquivo, ROTEIROS_DIR)
    if not os.path.exists(caminho_antigo):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
    with open(caminho_antigo, "r", encoding="utf-8") as f:
        dados = json.load(f)
    old_base = limpar_nome(dados.get("metadata", {}).get("id_treinamento", arquivo.replace(".json", "")))
    new_base = limpar_nome(req.novo_nome)
    novo_arquivo = f"{new_base}.json"
    caminho_novo = os.path.join(ROTEIROS_DIR, novo_arquivo)
    if os.path.exists(caminho_novo) and caminho_novo != caminho_antigo:
        suf = str(uuid.uuid4())[:6]
        new_base = f"{new_base}_{suf}"
        novo_arquivo = f"{new_base}.json"
        caminho_novo = os.path.join(ROTEIROS_DIR, novo_arquivo)
    dados.setdefault("metadata", {})
    dados["metadata"]["nome_aula"]      = req.novo_nome
    dados["metadata"]["id_treinamento"] = new_base
    try:
        for ext, pasta in [(".mp4", VIDEOS_DIR), ("_SCORM.zip", SCORM_DIR), ("_Playbook.pdf", PDF_DIR)]:
            old_f = os.path.join(pasta, f"{old_base}{ext}")
            new_f = os.path.join(pasta, f"{new_base}{ext}")
            if os.path.exists(old_f):
                os.rename(old_f, new_f)
        old_aud = os.path.join(AUDIOS_DIR, old_base)
        new_aud = os.path.join(AUDIOS_DIR, new_base)
        if os.path.exists(old_aud):
            os.rename(old_aud, new_aud)
    except Exception as e:
        return JSONResponse(status_code=500, content={"erro": f"Erro ao renomear dependências: {e}"})
    with open(caminho_novo, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)
    if caminho_novo != caminho_antigo:
        os.remove(caminho_antigo)
    return {"status": "sucesso", "novo_arquivo": novo_arquivo}


# ==============================================================
# ROTAS DAP EXTENSION (AURA RAG & VISION PROTEGIDAS)
# ==============================================================

@app.post("/analyze")
async def analyze_screen(req: DapRequest, request: Request, token: str = Depends(verificar_token)):
    ip_cliente = request.client.host if request.client else "unknown"
    verificar_rate_limit(ip_cliente) 
    
    resultado = await dap_engine.analisar_tela_dap(
        req.image, req.url, req.prompt, req.dom_context, req.user_name, req.tenant_id, req.historico
    )
    return resultado

@app.post("/api/ingest/{arquivo}")
async def ingestar_no_dap(arquivo: str, token: str = Depends(verificar_token)):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    res    = dap_engine.ingestar_para_pinecone(dados, tenant_id=tenant)
    if res.get("status") == "sucesso":
        dados.setdefault("metadata", {})
        dados["metadata"]["ingestado_dap"] = True
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
    return res

class GerarIAPayload(BaseModel):
    nome_aula: str
    objetivo:  str

@app.post("/api/gerar-ia")
async def gerar_aula_com_ia(payload: GerarIAPayload):
    """
    Gera um roteiro completo via Gemini + RAG + biblioteca de ações.
    Chamado pelo botão "✨ Gerar com Aura IA" do Training OS.
    """
    nome  = payload.nome_aula.strip()
    obj   = payload.objetivo.strip()

    if not nome or not obj:
        return JSONResponse(
            status_code=422,
            content={"erro": "nome_aula e objetivo são obrigatórios."},
        )

    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")

    # Executa em thread para não bloquear o event loop do FastAPI
    loop = asyncio.get_event_loop()
    resultado = await loop.run_in_executor(
        None,
        lambda: generator_engine.gerar_roteiro_ia_sync(nome, obj, tenant),
    )

    if resultado.get("status") == "sucesso":
        # Atualiza métricas para o Overview refletir a nova aula gerada
        carregarMetricas_bg()
        return JSONResponse(status_code=200, content=resultado)
    else:
        return JSONResponse(
            status_code=500,
            content={"erro": resultado.get("mensagem", "Erro desconhecido.")},
        )


@app.post("/api/rebuild-library")
async def rebuild_library():
    """
    Reconstrói a biblioteca de ações varrendo todos os roteiros salvos.
    Deve ser executado sempre que novos treinamentos forem validados e
    antes de usar o gerador de IA pela primeira vez.
    """
    loop = asyncio.get_event_loop()
    resultado = await loop.run_in_executor(None, lego_builder.construir_biblioteca)

    if resultado.get("status") == "sucesso":
        return JSONResponse(status_code=200, content=resultado)
    else:
        return JSONResponse(status_code=500, content=resultado)


def carregarMetricas_bg():
    """Dispara atualização de métricas em background sem bloquear o endpoint."""
    # A rota /api/metricas já lê do disco — não há estado a sincronizar.
    # Esta função existe para garantir que logs/cache interno sejam atualizados.
    pass  # extensível futuramente com invalidação de cache Redis, etc.

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SENIOR TRAINING OS INICIADO")
    print("Aceda no navegador: http://localhost:8000")
    print("=" * 50 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
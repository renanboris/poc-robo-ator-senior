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
from contextlib import asynccontextmanager
import unicodedata
import glob
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
import tempfile
import hashlib
import generator_engine
import lego_builder
import dap_engine
import job_registry
import scorm_builder
from datetime import datetime
from utils import limpar_nome, validar_roteiro, salvar_versao_roteiro, aplicar_blur_screenshot


def _atomic_write_json(caminho: str, dados: dict) -> None:
    """Escreve dados JSON em disco de forma atômica via tempfile + os.replace().

    Garante que o arquivo destino nunca fique em estado parcialmente escrito:
    o arquivo temporário é criado no mesmo diretório (mesmo filesystem) e
    substituído atomicamente pelo destino final.
    """
    dir_destino = os.path.dirname(os.path.abspath(caminho))
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
            json.dump(dados, tmp_f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, caminho)
    except Exception:
        # Remove o temporário se algo falhar antes do replace
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise

# ==============================================================
# WEBSOCKET MANAGER (Sprint 4) & LIFECYCLE
# ==============================================================
main_loop = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global main_loop
    main_loop = asyncio.get_running_loop()
    logging.info("WebSocket Event Loop capturado com sucesso.")
    # Limpa writes atômicos interrompidos (tmp*.json.tmp deixados por kills externos)
    for _tmp in glob.glob("*.json.tmp"):
        try:
            os.remove(_tmp)
            logging.info(f"Cleanup startup: removido {_tmp}")
        except Exception:
            pass
    # Migração idempotente: tabela analytics_eventos no brain.db (Requisito 2.3)
    try:
        with sqlite3.connect("brain.db", timeout=5) as _conn:
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics_eventos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    roteiro_id TEXT NOT NULL,
                    passo_id INTEGER,
                    usuario_id TEXT,
                    evento TEXT NOT NULL,
                    ts INTEGER NOT NULL
                )
            """)
            _conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_roteiro
                ON analytics_eventos (roteiro_id, ts)
            """)
            _conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_analytics_usuario
                ON analytics_eventos (usuario_id, ts)
            """)
            _conn.commit()
            logging.info("Migração analytics_eventos: OK")
    except Exception as _e:
        logging.warning(f"Migração analytics_eventos falhou (startup não bloqueado): {_e}")
    # Migração idempotente: tabela sim_links no brain.db (Requisito 3.3)
    try:
        with sqlite3.connect("brain.db", timeout=5) as _conn:
            _conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_links (
                    token TEXT PRIMARY KEY,
                    roteiro_id TEXT NOT NULL,
                    criado_em INTEGER NOT NULL,
                    expira_em INTEGER NOT NULL,
                    total_acessos INTEGER NOT NULL DEFAULT 0
                )
            """)
            _conn.commit()
            logging.info("Migração sim_links: OK")
    except Exception as _e:
        logging.warning(f"Migração sim_links falhou (startup não bloqueado): {_e}")
    yield

def _norm(s: str) -> str:
    """Normaliza string para comparação: remove acentos, lowercase, strip."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower().strip()


app = FastAPI(title="Senior Training OS", lifespan=lifespan)

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
    # Expira entradas antigas por IP individualmente (evita clear() global que burla o limite)
    _rate_limit_cache[ip] = [t for t in _rate_limit_cache.get(ip, []) if agora - t < 60]

    if len(_rate_limit_cache[ip]) >= MAX_REQUESTS_PER_MINUTE:
        logging.warning(f"Rate limit excedido para o IP: {ip}")
        raise HTTPException(status_code=429, detail="Limite de requisições excedido. Tente novamente em um minuto.")

    _rate_limit_cache[ip].append(agora)

    # Purga IPs sem requisições recentes para evitar crescimento indefinido da memória.
    # Feito por expiração individual, não por clear() global.
    if len(_rate_limit_cache) > 10_000:
        expirados = [k for k, v in _rate_limit_cache.items() if not v]
        for k in expirados:
            del _rate_limit_cache[k]
        logging.info(f"Rate limit cache: {len(expirados)} IPs expirados removidos.")


# ==============================================================
# ESCUDO DE IDENTIDADE (Validação de Token)
# ==============================================================
API_KEY_NAME = "Authorization"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verificar_token(api_key: str = Security(api_key_header)):
    secret = os.getenv("AURA_API_SECRET")
    if not secret:
        logging.critical("AURA_API_SECRET não configurado. Defina a variável de ambiente.")
        raise HTTPException(status_code=500, detail="Configuração de segurança ausente no servidor.")
    chave_mestra = f"Bearer {secret}"

    if not api_key or api_key != chave_mestra:
        logging.warning("Tentativa de acesso bloqueada: Token inválido ou ausente.")
        raise HTTPException(status_code=401, detail="Acesso não autorizado. Credenciais inválidas.")
    return api_key


def _validar_caminho(nome_arquivo: str, diretorio_base: str) -> str:
    # Resolve o base em relação ao cwd no momento da chamada para garantir consistência
    base    = os.path.realpath(os.path.abspath(diretorio_base))
    destino = os.path.realpath(os.path.join(base, os.path.basename(nome_arquivo)))
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
SIM_LINKS_DIR = "sim_links";      os.makedirs(SIM_LINKS_DIR, exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/videos", StaticFiles(directory=VIDEOS_DIR), name="videos")
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==============================================================
# GERENCIADOR DE TAREFAS EM BACKGROUND
# ==============================================================
_estado_lock = threading.Lock()

estado_servidor = {
    "ocupado":     False,
    "mensagem":    "",
    "progresso":   None,
    "erro":        "",
    "sucesso":     "",
    "shadow_path": None,   # caminho do shadow JSONL gerado pelo modo dual
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


def executar_processo_bg(comando, msg_executando, msg_sucesso, job_id: str = None):
    global processo_atual
    _set_estado(ocupado=True, mensagem=msg_executando, progresso=None, erro="", sucesso="", shadow_path=None)

    if job_id:
        job_registry.atualizar_job(job_id, status="executando")

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
                print(f"[ROBÔ BASTIDORES]: {linha_limpa}")
                linhas_log.append(linha_limpa)
                if "PROGRESSO:" in linha_limpa:
                    try:
                        pct = int(linha_limpa.split("PROGRESSO:")[1].strip())
                        _set_estado(progresso=pct)
                        if job_id:
                            job_registry.atualizar_job(job_id, progresso=pct)
                    except Exception:
                        pass
                if linha_limpa.startswith("SHADOW_GERADO:"):
                    _shadow_path = linha_limpa.split("SHADOW_GERADO:", 1)[1].strip()
                    _set_estado(shadow_path=_shadow_path)

        proc.wait()

        # Persiste as últimas 100 linhas do log no job_registry (NFR-3.5)
        if job_id and linhas_log:
            job_registry.atualizar_job(job_id, log_execucao="\n".join(linhas_log[-100:]))

        if proc.returncode != 0:
            erro_real  = "Erro desconhecido."
            for l in reversed(linhas_log):
                if "PROGRESSO:" not in l:
                    erro_real = l
                    break
            if proc.returncode < 0 or "KeyboardInterrupt" in "\n".join(linhas_log):
                _set_estado(erro="Execução interrompida pelo utilizador.")
                if job_id:
                    job_registry.atualizar_job(job_id, status="cancelado", motivo_falha="Execução interrompida pelo utilizador.")
            else:
                nome_processo = os.path.basename(comando[1]) if len(comando) > 1 else str(comando)
                logging.error(
                    f"Processo '{nome_processo}' falhou (returncode={proc.returncode}). "
                    f"Comando: {' '.join(str(c) for c in comando)}. "
                    f"Última linha de saída: {erro_real}"
                )
                _set_estado(erro=f"Falha: {erro_real}")
                if job_id:
                    job_registry.atualizar_job(job_id, status="falhou", motivo_falha=erro_real)
        else:
            _set_estado(sucesso=msg_sucesso)
            if job_id:
                job_registry.atualizar_job(job_id, status="concluido")

            # AUTO-REBUILD: se o processo concluído era um mapeamento (capture.py),
            # reconstrói a biblioteca de peças automaticamente.
            # Usa daemon thread para não travar o broadcast do WebSocket.
            if "capture.py" in " ".join(comando) or "capture_dual_output.py" in " ".join(comando) or "capture_variants" in " ".join(comando):
                # Extrai o caminho exato do roteiro emitido pelo capture.py via stdout.
                # Isso evita o glob+mtime que lia o arquivo errado quando outros
                # roteiros tinham sido tocados mais recentemente.
                roteiro_gerado_path = None
                for _l in linhas_log:
                    if _l.startswith("ROTEIRO_GERADO:"):
                        roteiro_gerado_path = _l.split("ROTEIRO_GERADO:", 1)[1].strip()
                        break

                def _auto_rebuild(roteiro_path=roteiro_gerado_path):
                    """
                    Portão de qualidade para o caminho Dashboard.
                    Usa o caminho exato emitido pelo capture.py (ROTEIRO_GERADO:).
                    Fallback para glob+mtime apenas se a linha não foi encontrada.
                    """
                    try:
                        if roteiro_path and os.path.exists(roteiro_path):
                            roteiro_recente = roteiro_path
                        else:
                            # Fallback de segurança — não deveria ser necessário
                            import glob
                            arquivos = glob.glob(os.path.join(ROTEIROS_DIR, "*.json"))
                            if not arquivos:
                                logging.warning("Auto-rebuild: nenhum roteiro encontrado.")
                                return
                            roteiro_recente = max(arquivos, key=os.path.getmtime)
                            logging.warning(
                                "Auto-rebuild: ROTEIRO_GERADO não encontrado no stdout — "
                                "usando fallback mtime. Verifique capture.py."
                            )

                        # Portão de qualidade — mesmos critérios do capture.py
                        try:
                            with open(roteiro_recente, "r", encoding="utf-8") as f_r:
                                roteiro_dados = json.load(f_r)
                        except Exception as e_read:
                            logging.warning(f"Auto-rebuild: erro ao ler roteiro: {e_read}")
                            return

                        aprovado, motivo = validar_roteiro(roteiro_dados)
                        if not aprovado:
                            msg_rb = f"⚠️ Rebuild bloqueado: {motivo}"
                            _set_estado(sucesso=msg_rb)
                            logging.warning(f"Auto-rebuild Dashboard: {msg_rb}")
                            return

                        resultado = lego_builder.construir_biblioteca()
                        if resultado.get("status") == "sucesso":
                            novas = resultado.get("total_acoes_novas", 0)
                            total = resultado.get("total_acoes_lidas", 0)
                            msg_rb = (
                                f"🧩 Biblioteca atualizada! "
                                f"{total} peças ({novas} novas)."
                            )
                        else:
                            msg_rb = f"⚠️ Rebuild parcial: {resultado.get('mensagem', '')}"

                        _set_estado(sucesso=msg_rb)
                        logging.info(f"Auto-rebuild Dashboard: {msg_rb}")

                    except Exception as e_rb:
                        logging.warning(f"Auto-rebuild falhou (não crítico): {e_rb}")

                import threading
                threading.Thread(target=_auto_rebuild, daemon=True, name="lego-rebuild-bg").start()

    except Exception as e:
        _set_estado(erro=str(e))
        if job_id:
            job_registry.atualizar_job(job_id, status="falhou", motivo_falha=str(e))
    finally:
        _set_estado(ocupado=False, progresso=None)
        with _estado_lock:
            processo_atual = None

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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

class ValidacaoEsperada(BaseModel):
    tipo: Optional[str] = "estado_visual"
    alvo: Optional[str] = ""

class AcaoTecnica(BaseModel):
    acao:               str
    intencao_semantica: Optional[str]           = ""
    elemento_alvo:      Optional[ElementoAlvo]  = Field(default_factory=ElementoAlvo)
    valor_input:        Optional[str]           = ""
    micro_narracao:     Optional[str]           = ""
    seletor_css:        Optional[str]           = ""
    validacao_esperada: Optional[ValidacaoEsperada] = None

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

class EventoAnalyticsReq(BaseModel):
    roteiro_id: str
    passo_id:   Optional[int] = None
    usuario_id: Optional[str] = None
    evento:     str


# ==============================================================
# ROTAS DA API
# ==============================================================

_EVENTOS_VALIDOS = {"iniciou", "completou_passo", "repetiu_passo", "abandonou", "completou"}

@app.post("/api/analytics/evento")
async def ingerir_evento_analytics(payload: EventoAnalyticsReq, request: Request):
    """Recebe eventos de progresso do player SCORM e da extensão Aura.

    Não requer autenticação — dados de uso, não sensíveis (Requisito 2.2, 2.6).
    """
    if payload.evento not in _EVENTOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"Evento inválido: '{payload.evento}'. Valores aceitos: {sorted(_EVENTOS_VALIDOS)}"
        )

    # Gerar usuario_id anônimo quando não fornecido (Requisito 2.6)
    usuario_id = payload.usuario_id
    if not usuario_id:
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "")
        usuario_id = hashlib.md5(f"{ip}_{ua}".encode()).hexdigest()[:16]

    ts = int(time.time() * 1000)

    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            conn.execute(
                """
                INSERT INTO analytics_eventos (roteiro_id, passo_id, usuario_id, evento, ts)
                VALUES (?, ?, ?, ?, ?)
                """,
                (payload.roteiro_id, payload.passo_id, usuario_id, payload.evento, ts),
            )
            conn.commit()
    except Exception as e:
        logging.error(f"Falha ao persistir evento analytics: {e}")
        raise HTTPException(status_code=500, detail="Erro ao persistir evento no banco de dados.")

    return {"ok": True, "usuario_id": usuario_id}


@app.get("/api/analytics/{roteiro_id}")
def relatorio_analytics(roteiro_id: str):
    """Retorna relatório de analytics de engajamento para um roteiro.

    Sem autenticação — dados de uso, não sensíveis (Requisito 2.4).

    Campos retornados:
    - taxa_conclusao: count(evento="completou") / count(DISTINCT usuario_id)
      null se menos de 3 usuários distintos.
    - tempo_medio_por_passo: dict {passo_id: segundos}
      null se menos de 3 amostras por passo.
    - passos_mais_repetidos: top 5 passo_id por count(evento="repetiu_passo").
      Lista vazia se sem dados.
    - passo_maior_abandono: passo_id com maior count(evento="abandonou").
      null se sem dados.
    """
    _null_response = {
        "taxa_conclusao": None,
        "tempo_medio_por_passo": None,
        "passos_mais_repetidos": [],
        "passo_maior_abandono": None,
    }

    try:
        conn = sqlite3.connect("brain.db", timeout=5)
    except Exception as e:
        logging.warning(f"[analytics] Não foi possível conectar ao brain.db: {e}")
        return _null_response

    try:
        # Verificar se a tabela existe
        tabela_existe = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='analytics_eventos'"
        ).fetchone()
        if not tabela_existe:
            return _null_response

        # ── taxa_conclusao ────────────────────────────────────────────────────
        taxa_conclusao = None
        try:
            total_usuarios = conn.execute(
                "SELECT COUNT(DISTINCT usuario_id) FROM analytics_eventos WHERE roteiro_id = ?",
                (roteiro_id,),
            ).fetchone()[0]

            if total_usuarios >= 3:
                completaram = conn.execute(
                    "SELECT COUNT(*) FROM analytics_eventos "
                    "WHERE roteiro_id = ? AND evento = 'completou'",
                    (roteiro_id,),
                ).fetchone()[0]
                taxa_conclusao = round(completaram / total_usuarios, 4) if total_usuarios > 0 else None
        except Exception as e:
            logging.warning(f"[analytics] Erro ao calcular taxa_conclusao para '{roteiro_id}': {e}")

        # ── tempo_medio_por_passo ─────────────────────────────────────────────
        tempo_medio_por_passo = None
        try:
            # Para cada (usuario_id, passo_id): diferença entre ts de "iniciou" e "completou_passo"
            rows = conn.execute(
                """
                SELECT
                    i.passo_id,
                    AVG((c.ts - i.ts) / 1000.0) AS media_segundos,
                    COUNT(*) AS amostras
                FROM analytics_eventos i
                JOIN analytics_eventos c
                    ON  i.roteiro_id  = c.roteiro_id
                    AND i.passo_id    = c.passo_id
                    AND i.usuario_id  = c.usuario_id
                    AND i.evento      = 'iniciou'
                    AND c.evento      = 'completou_passo'
                    AND c.ts          > i.ts
                WHERE i.roteiro_id = ?
                GROUP BY i.passo_id
                HAVING COUNT(*) >= 3
                """,
                (roteiro_id,),
            ).fetchall()

            if rows:
                tempo_medio_por_passo = {
                    str(row[0]): round(row[1], 2) for row in rows
                }
        except Exception as e:
            logging.warning(f"[analytics] Erro ao calcular tempo_medio_por_passo para '{roteiro_id}': {e}")

        # ── passos_mais_repetidos ─────────────────────────────────────────────
        passos_mais_repetidos = []
        try:
            rows = conn.execute(
                """
                SELECT passo_id, COUNT(*) AS total_repeticoes
                FROM analytics_eventos
                WHERE roteiro_id = ? AND evento = 'repetiu_passo'
                GROUP BY passo_id
                ORDER BY total_repeticoes DESC
                LIMIT 5
                """,
                (roteiro_id,),
            ).fetchall()
            passos_mais_repetidos = [
                {"passo_id": row[0], "total_repeticoes": row[1]} for row in rows
            ]
        except Exception as e:
            logging.warning(f"[analytics] Erro ao calcular passos_mais_repetidos para '{roteiro_id}': {e}")

        # ── passo_maior_abandono ──────────────────────────────────────────────
        passo_maior_abandono = None
        try:
            row = conn.execute(
                """
                SELECT passo_id
                FROM analytics_eventos
                WHERE roteiro_id = ? AND evento = 'abandonou'
                GROUP BY passo_id
                ORDER BY COUNT(*) DESC
                LIMIT 1
                """,
                (roteiro_id,),
            ).fetchone()
            if row:
                passo_maior_abandono = row[0]
        except Exception as e:
            logging.warning(f"[analytics] Erro ao calcular passo_maior_abandono para '{roteiro_id}': {e}")

        return {
            "taxa_conclusao": taxa_conclusao,
            "tempo_medio_por_passo": tempo_medio_por_passo,
            "passos_mais_repetidos": passos_mais_repetidos,
            "passo_maior_abandono": passo_maior_abandono,
        }

    except Exception as e:
        logging.warning(f"[analytics] Erro inesperado no relatório para '{roteiro_id}': {e}")
        return _null_response
    finally:
        conn.close()


@app.get("/api/missoes")
def listar_missoes_ativas():
    """Retorna o catálogo de missões da Academia Operacional.
    
    Filtra automaticamente missões com status != 'producao' e nomes de teste
    (padrão: Teste*, TES_*, roteiros com sufixo numérico simples).
    Passe ?incluir_testes=1 para ver todas.
    """
    from fastapi import Request as _Req
    pasta = "missoes_ativas"
    if not os.path.exists(pasta):
        return []

    _PADRAO_TESTE = re.compile(
        r'^(teste|test|TES_|Teste_?\d|Teste\d|Teste\s*\d)',
        re.IGNORECASE
    )

    missoes = []
    for arq in glob.glob(os.path.join(pasta, "*.json")):
        try:
            with open(arq, "r", encoding="utf-8") as f:
                dados = json.load(f)

            # Filtra missões de rascunho/teste pelo campo status
            status = dados.get("status", "producao")
            if status not in ("producao", "production"):
                continue

            # Filtra pelo nome do arquivo (convenção de nomenclatura)
            nome_arq = os.path.basename(arq)
            if _PADRAO_TESTE.match(nome_arq):
                continue

            missoes.append({
                "id":          dados.get("mission_id"),
                "titulo":      dados.get("title"),
                "modulo":      dados.get("module"),
                "dificuldade": dados.get("difficulty"),
                "xp_maximo":   dados.get("scoring", {}).get("base_xp", 0),
                "arquivo":     nome_arq
            })
        except Exception as e:
            logging.warning(f"Erro ao ler missão '{arq}': {e}")
            continue
    return missoes

@app.get("/api/missoes/{mission_id}")
def obter_detalhes_missao(mission_id: str):
    """Retorna o JSON completo da missão com os passos e validações."""
    caminho = os.path.join("missoes_ativas", f"{mission_id}.json")
    if not os.path.exists(caminho):
        return {"erro": "Missão não encontrada"}
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/dashboard", response_class=HTMLResponse)
async def pagina_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/v2", response_class=HTMLResponse)
async def index_v2(request: Request):
    return templates.TemplateResponse("index_v2.html", {"request": request})

@app.get("/dashboard/v2", response_class=HTMLResponse)
async def dashboard_v2(request: Request):
    return templates.TemplateResponse("dashboard_v2.html", {"request": request})

@app.get("/api/metricas")
async def get_metricas():
    """Expõe métricas de observabilidade do Vision Engine e do pipeline.

    Requisitos: 1.4.2, NFR-3.2

    Regras:
    - Retorna `null` para campos sem dados (nunca omite ou retorna zero quando não há dados).
    - `horas_poupadas` = total_aulas * 2.5 horas por aula.
    - `economia_estimada` = horas_poupadas * 100 reais.
    - Se `total_aulas` for null, `horas_poupadas` e `economia_estimada` também são null.
    - `self_healing_hits` = soma de acertos de todas as camadas em telemetria_camadas.
    - `camadas_vision` inclui taxa_sucesso por camada: acertos / (acertos + falhas) se total > 0, senão null.
    """
    from vision_engine import obter_stats_brain

    # ── total_aulas ──────────────────────────────────────────────────────────
    total_aulas: Optional[int] = None
    try:
        if os.path.isdir(ROTEIROS_DIR):
            arquivos_json = [f for f in os.listdir(ROTEIROS_DIR) if f.endswith(".json")]
            total_aulas = len(arquivos_json)
    except Exception as e:
        logging.warning(f"[metricas] Não foi possível contar roteiros: {e}")

    # ── horas_poupadas / economia_estimada ───────────────────────────────────
    horas_poupadas: Optional[float] = None
    economia_estimada: Optional[float] = None
    if total_aulas is not None:
        horas_poupadas = round(total_aulas * 2.5, 2)
        economia_estimada = round(horas_poupadas * 100, 2)

    # ── Brain stats (total_memorizado, self_healing_hits, camadas_vision) ────
    total_memorizado: Optional[int] = None
    self_healing_hits: Optional[int] = None
    camadas_vision: Optional[list] = None

    try:
        stats = obter_stats_brain()
        if "erro" not in stats:
            total_memorizado = stats.get("total_memorias")

            camadas_raw = stats.get("camadas", [])
            if camadas_raw:
                camadas_vision = []
                hits_total = 0
                for c in camadas_raw:
                    acertos = c.get("acertos", 0)
                    falhas  = c.get("falhas", 0)
                    total_c = acertos + falhas
                    taxa    = round(acertos / total_c, 4) if total_c > 0 else None
                    camadas_vision.append({
                        "camada":      c.get("camada"),
                        "acertos":     acertos,
                        "falhas":      falhas,
                        "taxa_sucesso": taxa,
                    })
                    hits_total += acertos
                self_healing_hits = hits_total
            else:
                # brain.db existe mas sem registros de telemetria — retorna null
                self_healing_hits = None
                camadas_vision = None
    except Exception as e:
        logging.warning(f"[metricas] Não foi possível obter stats do Brain: {e}")

    # ── tamanho_cache_dap ────────────────────────────────────────────────────
    tamanho_cache_dap: Optional[int] = None
    try:
        if os.path.exists("aura_cache.db"):
            with sqlite3.connect("aura_cache.db") as conn:
                row = conn.execute("SELECT COUNT(*) FROM dap_cache").fetchone()
                if row is not None:
                    tamanho_cache_dap = row[0]
    except Exception as e:
        logging.warning(f"[metricas] Não foi possível consultar aura_cache.db: {e}")

    # ── Métricas de ROI (Task 23 — Requisitos 3.3.1–3.3.7) ──────────────────
    roi: dict = {
        "tempo_medio_criacao_segundos":  None,
        "taxa_correcao_hitl":            None,
        "indice_reuso_memoria":          None,
        "reducao_suporte_estimada":      None,
        "total_treinamentos_rastreados": None,
    }
    try:
        import roi_tracker as _roi
        roi = _roi.calcular_metricas_roi()
    except Exception as e_roi:
        logging.warning(f"[metricas] Não foi possível calcular métricas de ROI: {e_roi}")

    # ── Scores por ação e por fluxo (Task 25 — Requisito 3.2.4) ────────────────
    scores_por_acao: Optional[list] = None
    scores_por_fluxo: Optional[list] = None
    try:
        import score_engine as _se
        todos_scores = _se.obter_todos_scores()
        if todos_scores:
            scores_por_acao = [
                {
                    "acao_id":            s["acao_id"],
                    "score":              s["score"],
                    "requer_revisao":     bool(s["requer_revisao"]),
                    "total_execucoes":    s["total_execucoes"],
                    "taxa_sucesso":       round(s["taxa_sucesso"], 4),
                }
                for s in todos_scores
            ]

        # Score por fluxo: média dos scores das ações de cada roteiro
        if os.path.isdir(ROTEIROS_DIR):
            fluxos = []
            for arq in sorted(os.listdir(ROTEIROS_DIR)):
                if not arq.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(ROTEIROS_DIR, arq), "r", encoding="utf-8") as f_r:
                        rd = json.load(f_r)
                    id_trein = rd.get("metadata", {}).get("id_treinamento", arq.replace(".json", ""))
                    scores_acoes = []
                    for passo in rd.get("passos", []):
                        for acao in passo.get("acoes_tecnicas", []):
                            intencao = acao.get("intencao_semantica", "").strip().lower()
                            if intencao:
                                s = _se.obter_score(intencao)
                                if s is not None:
                                    scores_acoes.append(s)
                    score_fluxo = round(sum(scores_acoes) / len(scores_acoes), 4) if scores_acoes else None
                    fluxos.append({
                        "fluxo_id":    id_trein,
                        "nome_aula":   rd.get("metadata", {}).get("nome_aula", id_trein),
                        "score_fluxo": score_fluxo,
                        "n_acoes":     len(scores_acoes),
                    })
                except Exception:
                    continue
            if fluxos:
                scores_por_fluxo = fluxos
    except Exception as e_scores:
        logging.warning(f"[metricas] Não foi possível calcular scores: {e_scores}")

    # ── vision_layers — 12 camadas com métricas das últimas 24h (Task 11) ───
    CAMADAS_VISION = [
        "0_brain", "0_brain_coords", "0.5_menu_ctx", "1_foco_nativo",
        "1.5_heuristica_seniorx", "1_template_matching", "2_coords_capturadas",
        "2_sniper", "3_hint_original", "4_todos_frames", "5_gemini_vision", "falha_total",
    ]
    vision_layers: list = []
    taxa_hitl_1h: Optional[float] = None
    top_falhas: list = []
    acoes_requer_revisao: Optional[int] = None

    try:
        _brain_db = "brain.db"
        if os.path.exists(_brain_db):
            ts_24h = int(time.time() * 1000) - 86_400_000
            ts_1h  = int(time.time() * 1000) - 3_600_000

            with sqlite3.connect(_brain_db, timeout=5) as conn:
                # vision_layers — acertos/falhas por camada nas últimas 24h
                for camada in CAMADAS_VISION:
                    row = conn.execute(
                        "SELECT SUM(acertou), SUM(1 - acertou) FROM telemetria_execucoes "
                        "WHERE camada = ? AND ts >= ?",
                        (camada, ts_24h),
                    ).fetchone()
                    acertos_c = row[0] if row and row[0] is not None else None
                    falhas_c  = row[1] if row and row[1] is not None else None
                    if acertos_c is None and falhas_c is None:
                        taxa_c = None
                    else:
                        total_c = (acertos_c or 0) + (falhas_c or 0)
                        taxa_c  = round((acertos_c or 0) / total_c, 4) if total_c > 0 else None
                    vision_layers.append({
                        "camada":      camada,
                        "acertos":     acertos_c,
                        "falhas":      falhas_c,
                        "taxa_sucesso": taxa_c,
                    })

                # taxa_hitl_1h
                total_1h  = conn.execute(
                    "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ?",
                    (ts_1h,),
                ).fetchone()[0]
                falhas_1h = conn.execute(
                    "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ? AND camada = 'falha_total'",
                    (ts_1h,),
                ).fetchone()[0]
                taxa_hitl_1h = (falhas_1h / total_1h) if total_1h >= 5 else None

                # top_falhas — top 10 ações com maior falha_total nas últimas 24h
                rows = conn.execute(
                    """
                    SELECT te.intencao_semantica,
                           COUNT(*) AS total_falhas,
                           MAX(te.ts) AS ultima_ts,
                           (SELECT te2.camada FROM telemetria_execucoes te2
                            WHERE te2.intencao_semantica = te.intencao_semantica
                            ORDER BY te2.ts DESC LIMIT 1) AS ultima_camada
                    FROM telemetria_execucoes te
                    WHERE te.ts >= ? AND te.camada = 'falha_total'
                    GROUP BY te.intencao_semantica
                    ORDER BY total_falhas DESC
                    LIMIT 10
                    """,
                    (ts_24h,),
                ).fetchall()
                for r in rows:
                    ultima_ts_ms = r[2]
                    ultima_falha_em = None
                    if ultima_ts_ms is not None:
                        try:
                            import datetime as _dt
                            ultima_falha_em = _dt.datetime.utcfromtimestamp(
                                ultima_ts_ms / 1000
                            ).strftime("%Y-%m-%dT%H:%M:%S")
                        except Exception:
                            ultima_falha_em = None
                    top_falhas.append({
                        "intencao_semantica":  r[0],
                        "total_falhas":        r[1],
                        "ultima_falha_em":     ultima_falha_em,
                        "ultima_camada_tentada": r[3],
                    })
    except Exception as e_vl:
        logging.warning(f"[metricas] Não foi possível consultar telemetria_execucoes: {e_vl}")

    # acoes_requer_revisao — contagem de ações com requer_revisao: true
    try:
        biblioteca_path = "biblioteca_acoes.json"
        if os.path.exists(biblioteca_path):
            with open(biblioteca_path, encoding="utf-8") as _f_bib:
                _biblioteca = json.load(_f_bib)
            acoes_requer_revisao = sum(
                1 for a in _biblioteca if a.get("requer_revisao", False)
            )
    except Exception as e_bib:
        logging.warning(f"[metricas] Não foi possível ler biblioteca_acoes.json: {e_bib}")

    return {
        "total_aulas":       total_aulas,
        "horas_poupadas":    horas_poupadas,
        "economia_estimada": economia_estimada,
        "total_memorizado":  total_memorizado,
        "self_healing_hits": self_healing_hits,
        "tamanho_cache_dap": tamanho_cache_dap,
        "camadas_vision":    camadas_vision,
        # ROI
        "tempo_medio_criacao_segundos":  roi.get("tempo_medio_criacao_segundos"),
        "taxa_correcao_hitl":            roi.get("taxa_correcao_hitl"),
        "indice_reuso_memoria":          roi.get("indice_reuso_memoria"),
        "reducao_suporte_estimada":      roi.get("reducao_suporte_estimada"),
        "total_treinamentos_rastreados": roi.get("total_treinamentos_rastreados"),
        # Scores (Task 25)
        "scores_por_acao":   scores_por_acao,
        "scores_por_fluxo":  scores_por_fluxo,
        # Observabilidade Vision Engine (Task 11)
        "vision_layers":          vision_layers,
        "taxa_hitl_1h":           taxa_hitl_1h,
        "top_falhas":             top_falhas,
        "acoes_requer_revisao":   acoes_requer_revisao,
    }

@app.get("/api/status")
async def get_status():
    with _estado_lock:
        estado = estado_servidor.copy()
    estado["user_name"] = os.getenv("APP_USER_NAME", "Operador")
    return estado

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

        # Descobre o job ativo (o mais recente com status 'executando')
        job_id_ativo = None
        try:
            tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
            jobs_ativos = job_registry.listar_jobs_por_tenant(tenant, limit=10)
            for j in jobs_ativos:
                if j.get("status") == "executando":
                    job_id_ativo = j["job_id"]
                    break
        except Exception as e:
            logging.warning(f"[cancelar] Não foi possível localizar job ativo: {e}")

        # Atualiza o job para cancelado no registry
        if job_id_ativo:
            job_registry.atualizar_job(
                job_id_ativo,
                status="cancelado",
                motivo_falha="Cancelado pelo utilizador via POST /api/cancelar",
            )
            logging.info(f"[cancelar] Job {job_id_ativo} marcado como cancelado. Timestamp: {__import__('datetime').datetime.utcnow().isoformat()}")

        # Limpa arquivos temporários de escritas atômicas interrompidas (Req 2.2.6)
        removidos = []
        for tmp_file in glob.glob("*.json.tmp"):
            try:
                os.remove(tmp_file)
                removidos.append(tmp_file)
                logging.info(f"[cancelar] Temporário removido: {tmp_file}")
            except Exception as e:
                logging.warning(f"[cancelar] Não foi possível remover {tmp_file}: {e}")

        if removidos:
            logging.info(f"[cancelar] {len(removidos)} arquivo(s) temporário(s) removido(s): {removidos}")

        resposta = {"status": "cancelado"}
        if job_id_ativo:
            resposta["job_id"] = job_id_ativo
        return resposta

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
            tem_simlink = os.path.exists(os.path.join(SIM_LINKS_DIR, f"{base}_SimLink.html"))
            # Avalia qualidade do roteiro para exibir badge no card do Studio
            _q_aprovado, _q_motivo = validar_roteiro(dados)
            _q_status = "aprovado" if _q_aprovado else (
                "sem_acoes" if "Nenhuma ação" in _q_motivo or "passo(s)" in _q_motivo
                else "reprovado"
            )

            roteiros.append({
                "arquivo":   arquivo, "nome": nome_raw,
                "qtd_passos": len(dados.get("passos", [])),
                "mtime":     os.path.getmtime(caminho),
                "tem_audio": os.path.exists(os.path.join(AUDIOS_DIR, base)),
                "tem_video": tem_video, "tem_scorm": tem_scorm, "tem_pdf": tem_pdf,
                "tem_simlink": tem_simlink,
                "tem_coach": dados.get("metadata", {}).get("ingestado_dap", False),
                "video_url":   f"/videos/{base}.mp4"              if tem_video   else None,
                "scorm_url":   f"/api/download-scorm/{base}"      if tem_scorm   else None,
                "pdf_url":     f"/api/download-pdf/{base}"        if tem_pdf     else None,
                "simlink_url": f"/api/preview-simlink/{base}"     if tem_simlink else None,
                "qualidade":        _q_status,
                "qualidade_motivo": _q_motivo,
                "origem":          dados.get("metadata", {}).get("origem", "manual"),
                "hitl_validado":   dados.get("metadata", {}).get("hitl_validado", False),
            })
        except Exception as e:
            logging.warning(f"Erro ao processar roteiro '{arquivo}': {e}")
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
    aprovado, motivo = validar_roteiro(dados)
    if not aprovado:
        logging.warning(f"Salvar roteiro bloqueado — '{arquivo}': {motivo}")
        return JSONResponse(status_code=422, content={"erro": f"Roteiro inválido: {motivo}"})
    caminho_backup = salvar_versao_roteiro(caminho, dados)
    if caminho_backup:
        logging.info(f"[versioning] Versão anterior preservada em '{caminho_backup}'")
    return {"status": "sucesso"}

@app.delete("/api/roteiros/{arquivo}")
async def excluir_roteiro(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    if os.path.exists(caminho):
        os.remove(caminho)
        return {"status": "sucesso"}
    return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})

def _iniciar_bg(comando, msg_exec, msg_ok, tipo="processo", tenant_id="senior_default"):
    with _estado_lock:
        if estado_servidor["ocupado"]:
            return None
    job_id = job_registry.criar_job(tipo, tenant_id)
    threading.Thread(target=executar_processo_bg, args=(comando, msg_exec, msg_ok, job_id), daemon=True).start()
    return job_id

@app.post("/api/gravar")
async def gravar_aula(req: NovaAulaReq):
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg([sys.executable, "capture.py", req.nome_aula, req.objetivo, "--auto"],
                     "🔍 Vasculhando o DOM (com autorização)...", "🎯 Tela capturada. A IA já pode enxergar.",
                     tipo="captura", tenant_id=tenant)
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/gravar-dual")
async def gravar_aula_dual(req: NovaAulaReq):
    """Captura no modo dual: gera roteiro legado + shadow JSONL semântico em paralelo."""
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg(
        [sys.executable, "capture_variants/capture_dual_output.py", req.nome_aula, req.objetivo, "--auto"],
        "🔍 Captura Dual ativa — gerando roteiro + shadow semântico...",
        "🎯 Captura dual concluída. Roteiro e shadow prontos.",
        tipo="captura", tenant_id=tenant,
    )
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/gravar-hybrid")
async def gravar_aula_hybrid(req: NovaAulaReq):
    """
    Captura no modo híbrido — motor mais avançado.
    Gera shadow JSONL semântico enriquecido com contexto antes/depois de cada ação.
    Requer compilação posterior via scripts/compile_hybrid_to_executor.py para execução.
    """
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg(
        [sys.executable, "capture_variants/capture_hybrid_shadow.py", req.nome_aula, req.objetivo, "--auto"],
        "🧠 Captura Híbrida ativa — análise semântica antes/depois de cada ação...",
        "✅ Captura híbrida concluída. Shadow JSONL pronto para compilação.",
        tipo="captura", tenant_id=tenant,
    )
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

# FIX Bug #APP-01: Rota /api/gerar-ia duplicada removida aqui.
# A implementação correta (com tenant_id e validação) está abaixo (~linha 604).

@app.post("/api/executar-robo/{arquivo}")
async def executar_robo(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg([sys.executable, "main.py", caminho, "--record"],
                     "🎬 Contratando o locutor da IA...", "🎞️ Cenas gravadas. Ilha de edição, é com vocês!",
                     tipo="render", tenant_id=tenant)
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/renderizar/{arquivo}")
async def renderizar_video(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg([sys.executable, "main.py", caminho, "--render"],
                     "🎬 Equipe de produção na ilha de edição...", "🏆 Vídeo pronto para o Oscar.",
                     tipo="render", tenant_id=tenant)
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/gerar-scorm/{arquivo}")
async def gerar_scorm(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg([sys.executable, "scorm_builder.py", caminho],
                     "📦 Empacotando o conhecimento (Padrão SCORM)...", "✅ Módulo SCORM deployado. Pode subir para o LMS.",
                     tipo="scorm", tenant_id=tenant)
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/gerar-pdf/{arquivo}")
async def gerar_pdf(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg([sys.executable, "pdf_builder.py", caminho],
                     "📜 Forjando os pergaminhos sagrados (PDF)...", "📖 Playbook gerado. Conhecimento imortalizado.",
                     tipo="pdf", tenant_id=tenant)
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.post("/api/gerar-simlink/{arquivo}")
async def gerar_simlink(arquivo: str):
    """Gera um SimLink — simulador standalone sem necessidade de LMS."""
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg(
        [sys.executable, "scripts/sim_link_builder.py", caminho],
        "🔗 Construindo o SimLink (simulador standalone)...",
        "🎮 SimLink pronto. Compartilhe o link direto, sem LMS.",
        tipo="scorm", tenant_id=tenant,
    )
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.get("/api/preview-simlink/{nome_base}", response_class=HTMLResponse)
async def preview_simlink(nome_base: str):
    """Serve o SimLink diretamente no navegador (link compartilhável)."""
    nome_seguro = limpar_nome(nome_base)
    caminho_html = os.path.join(SIM_LINKS_DIR, f"{nome_seguro}_SimLink.html")
    if os.path.exists(caminho_html):
        with open(caminho_html, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return JSONResponse(status_code=404, content={"erro": "SimLink não encontrado."})

@app.get("/api/download-simlink/{nome_base}")
async def download_simlink(nome_base: str):
    """Faz download do arquivo HTML do SimLink."""
    nome_seguro = limpar_nome(nome_base)
    caminho_html = os.path.join(SIM_LINKS_DIR, f"{nome_seguro}_SimLink.html")
    if os.path.exists(caminho_html):
        return FileResponse(
            path=caminho_html,
            filename=f"{nome_seguro}_SimLink.html",
            media_type="text/html"
        )
    return JSONResponse(status_code=404, content={"erro": "SimLink não encontrado."})

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
    _atomic_write_json(os.path.join(ROTEIROS_DIR, novo_arquivo), dados)
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
        for ext, pasta in [(".mp4", VIDEOS_DIR), ("_SCORM.zip", SCORM_DIR), ("_Playbook.pdf", PDF_DIR), ("_SimLink.html", SIM_LINKS_DIR)]:
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
    _atomic_write_json(caminho_novo, dados)
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
async def ingestar_no_dap(arquivo: str):
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Ficheiro não encontrado"})
        
    with open(caminho, "r", encoding="utf-8") as f:
        dados = json.load(f)
        
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    
    # Chama o motor da Aura para enviar ao Pinecone
    res = dap_engine.ingestar_para_pinecone(dados, tenant_id=tenant)
    
    if res.get("status") == "sucesso":
        dados.setdefault("metadata", {})
        dados["metadata"]["ingestado_dap"] = True
        _atomic_write_json(caminho, dados)
        _set_estado(sucesso="✅ Indexação concluída na base de conhecimento.")

        # AUTO-REBUILD: roteiro validado e ingestado = momento ideal para atualizar
        # a biblioteca de peças. Background thread para não travar a resposta HTTP.
        def _rebuild_apos_ingest():
            """
            No caminho de ingest o roteiro já está salvo e foi explicitamente
            aprovado pelo instrutor (ele clicou em 'Coach IA'). Ainda assim
            validamos para garantir consistência — se a qualidade for baixa,
            logamos mas não bloqueamos o ingest em si (só o rebuild).
            """
            try:
                aprovado, motivo = validar_roteiro(dados)
                if not aprovado:
                    logging.warning(
                        f"Auto-rebuild pós-ingest bloqueado: {motivo}. "
                        "Use o botão 'Atualizar Biblioteca' após corrigir o roteiro."
                    )
                    return

                r = lego_builder.construir_biblioteca()
                if r.get("status") == "sucesso":
                    logging.info(
                        f"Auto-rebuild pós-ingest: {r.get('total_acoes_lidas', 0)} peças, "
                        f"{r.get('total_acoes_novas', 0)} novas."
                    )
            except Exception as e_rb:
                logging.warning(f"Auto-rebuild pós-ingest falhou: {e_rb}")

        import threading
        threading.Thread(target=_rebuild_apos_ingest, daemon=True, name="lego-rebuild-ingest").start()
    else:
        _set_estado(erro=res.get("mensagem", "Falha na indexação."))

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

    # FIX Bug #APP-02: asyncio.get_event_loop() deprecado em Python 3.10+
    # Substituído por asyncio.to_thread() — API moderna e correta.
    resultado = await asyncio.to_thread(
        generator_engine.gerar_roteiro_ia_sync, nome, obj, tenant
    )

    if resultado.get("status") == "sucesso":
        # Marca origem="ia" e hitl_validado=False no metadata do roteiro
        _arq = os.path.join(ROTEIROS_DIR, resultado.get("arquivo", ""))
        if os.path.exists(_arq):
            try:
                with open(_arq, "r", encoding="utf-8") as _f: _rd = json.load(_f)
                _rd.setdefault("metadata", {})
                _rd["metadata"]["origem"] = "ia"
                _rd["metadata"]["hitl_validado"] = False
                _atomic_write_json(_arq, _rd)
            except Exception: pass
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
    # FIX Bug #APP-02b: asyncio.get_event_loop() deprecado
    resultado = await asyncio.to_thread(lego_builder.construir_biblioteca)

    if resultado.get("status") == "sucesso":
        return JSONResponse(status_code=200, content=resultado)
    else:
        return JSONResponse(status_code=500, content=resultado)


def carregarMetricas_bg():
    """Reservado para futura invalidação de cache (ex: Redis). Atualmente no-op."""
    pass



# ══════════════════════════════════════════════════════════════════
# ENDPOINT GPS — Retorna passos de roteiro para o motor GPS da Aura
# ══════════════════════════════════════════════════════════════════


@app.post("/api/marcar-hitl-validado/{arquivo}")
async def marcar_hitl_validado(arquivo: str):
    """Chamado pelo validator_hitl após concluir — marca o roteiro como validado.

    Pipeline HITL → Rebuild → Promoção de Memória (Requisitos 1.6.1–1.6.5):
      1. Valida o roteiro antes de aceitar a promoção (1.6.2).
      2. Persiste hitl_validado: true via escrita atômica.
      3. Aciona construir_biblioteca() em background thread (1.6.1).
      4. Após rebuild bem-sucedido, atualiza estado via _set_estado() (1.6.3).
      5. Em caso de falha, preserva versão anterior e registra ERROR (1.6.4, 1.6.5).
    """
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    if not os.path.exists(caminho):
        return JSONResponse(status_code=404, content={"erro": "Arquivo não encontrado"})
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)

        # Portão de qualidade — bloqueia promoção se roteiro inválido (Req 1.6.2)
        aprovado, motivo = validar_roteiro(dados)
        if not aprovado:
            logging.warning(
                f"Promoção HITL bloqueada — '{arquivo}': {motivo}"
            )
            return JSONResponse(
                status_code=422,
                content={"erro": f"Promoção bloqueada: roteiro inválido — {motivo}"},
            )

        dados.setdefault("metadata", {})
        dados["metadata"]["hitl_validado"] = True
        _atomic_write_json(caminho, dados)

        # Auto-rebuild em background — não bloqueia a resposta HTTP (Req 1.6.1)
        def _rebuild_apos_hitl(nome_arquivo=arquivo):
            """
            Reconstrói a Biblioteca_de_Ações após aprovação HITL.
            - Usa safe_write_json via lego_builder (escrita atômica, Req 1.6.4).
            - Versão anterior preservada em caso de falha (Req 1.6.5).
            - Atualiza estado via _set_estado() com contagem de peças (Req 1.6.3).
            """
            try:
                resultado = lego_builder.construir_biblioteca()
                if resultado.get("status") == "sucesso":
                    novas = resultado.get("total_acoes_novas", 0)
                    total = resultado.get("total_acoes_lidas", 0)
                    msg_rb = (
                        f"🧩 Biblioteca atualizada após HITL! "
                        f"{total} peças ({novas} novas)."
                    )
                    _set_estado(sucesso=msg_rb)
                    logging.info(
                        f"Auto-rebuild HITL ('{nome_arquivo}'): "
                        f"{total} peças lidas, {novas} novas."
                    )
                else:
                    # Falha no rebuild — versão anterior já preservada pelo safe_write_json
                    motivo_rb = resultado.get("mensagem", "motivo desconhecido")
                    logging.error(
                        f"Auto-rebuild HITL falhou ('{nome_arquivo}'): {motivo_rb}. "
                        "Versão anterior de biblioteca_acoes.json preservada."
                    )
                    _set_estado(
                        sucesso=f"⚠️ Rebuild falhou após HITL: {motivo_rb}"
                    )
            except Exception as e_rb:
                logging.error(
                    f"Auto-rebuild HITL — exceção inesperada ('{nome_arquivo}'): {e_rb}. "
                    "Versão anterior de biblioteca_acoes.json preservada.",
                    exc_info=True,
                )
                _set_estado(
                    sucesso=f"⚠️ Rebuild falhou após HITL: {e_rb}"
                )

        threading.Thread(
            target=_rebuild_apos_hitl, daemon=True, name="lego-rebuild-hitl"
        ).start()

        # Registra no log quais renderizações existem para o fluxo (Req 3.1.2)
        try:
            fluxo_id = dados.get("metadata", {}).get("id_treinamento", "")
            if fluxo_id:
                base = limpar_nome(fluxo_id)
                renders_estado = {
                    "video":   os.path.exists(os.path.join(VIDEOS_DIR,   f"{base}.mp4")),
                    "scorm":   os.path.exists(os.path.join(SCORM_DIR,    f"{base}_SCORM.zip")),
                    "pdf":     os.path.exists(os.path.join(PDF_DIR,      f"{base}_Playbook.pdf")),
                    "simlink": os.path.exists(os.path.join(SIM_LINKS_DIR, f"{base}_SimLink.html")),
                    "dap":     dados.get("metadata", {}).get("ingestado_dap", False),
                }
                disponiveis = [k for k, v in renders_estado.items() if v]
                logging.info(
                    f"HITL validado — fluxo='{fluxo_id}' renderizações disponíveis: {disponiveis or 'nenhuma'}"
                )
        except Exception as e_log:
            logging.warning(f"Não foi possível registrar estado de renderizações pós-HITL: {e_log}")

        return {"status": "sucesso"}
    except Exception as e:
        logging.error(f"Erro ao processar validação HITL para '{arquivo}': {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"erro": "Erro interno ao processar a validação. Consulte os logs do servidor."})

@app.get("/api/renderizacoes/{fluxo_id}")
async def get_renderizacoes(fluxo_id: str):
    """Retorna todas as renderizações disponíveis para um fluxo.

    O fluxo_id corresponde ao campo metadata.id_treinamento do roteiro.
    Usa limpar_nome() para normalizar antes de buscar arquivos.

    Requisitos: 3.1.1, 3.1.4
    """
    base = limpar_nome(fluxo_id)

    # Localiza o roteiro correspondente ao fluxo_id
    roteiro_dados = None
    for arq in sorted(os.listdir(ROTEIROS_DIR)):
        if not arq.endswith(".json"):
            continue
        try:
            caminho_r = os.path.join(ROTEIROS_DIR, arq)
            with open(caminho_r, "r", encoding="utf-8") as f:
                rd = json.load(f)
            id_trein = rd.get("metadata", {}).get("id_treinamento", "")
            if limpar_nome(id_trein) == base:
                roteiro_dados = rd
                break
        except Exception:
            continue

    if roteiro_dados is None:
        return JSONResponse(status_code=404, content={"erro": f"Fluxo '{fluxo_id}' não encontrado."})

    meta = roteiro_dados.get("metadata", {})
    nome_aula = meta.get("nome_aula", fluxo_id)
    hitl_validado = bool(meta.get("hitl_validado", False))
    ingestado_dap = bool(meta.get("ingestado_dap", False))

    # Verifica existência de cada artefato
    tem_video   = os.path.exists(os.path.join(VIDEOS_DIR,    f"{base}.mp4"))
    tem_scorm   = os.path.exists(os.path.join(SCORM_DIR,     f"{base}_SCORM.zip"))
    tem_pdf     = os.path.exists(os.path.join(PDF_DIR,       f"{base}_Playbook.pdf"))
    tem_simlink = os.path.exists(os.path.join(SIM_LINKS_DIR, f"{base}_SimLink.html"))

    renderizacoes = {
        "video":   {"disponivel": tem_video,   "url": f"/videos/{base}.mp4"          if tem_video   else None},
        "scorm":   {"disponivel": tem_scorm,   "url": f"/api/download-scorm/{base}"  if tem_scorm   else None},
        "pdf":     {"disponivel": tem_pdf,     "url": f"/api/download-pdf/{base}"    if tem_pdf     else None},
        "simlink": {"disponivel": tem_simlink, "url": f"/api/preview-simlink/{base}" if tem_simlink else None},
        "dap":     {"disponivel": ingestado_dap, "url": None},
    }

    # Calcula score_fluxo como média dos scores das ações via score_engine
    score_fluxo = None
    try:
        import score_engine as _se
        scores = []
        for passo in roteiro_dados.get("passos", []):
            for acao in passo.get("acoes_tecnicas", []):
                intencao = acao.get("intencao_semantica", "").strip()
                if not intencao:
                    continue
                s = _se.obter_score(intencao.lower())
                if s is not None:
                    scores.append(s)
        if scores:
            score_fluxo = round(sum(scores) / len(scores), 4)
    except Exception as e_score:
        logging.warning(f"[renderizacoes] Não foi possível calcular score_fluxo para '{fluxo_id}': {e_score}")

    return {
        "fluxo_id":      fluxo_id,
        "nome_aula":     nome_aula,
        "renderizacoes": renderizacoes,
        "hitl_validado": hitl_validado,
        "score_fluxo":   score_fluxo,
    }


@app.post("/api/validar-hitl/{arquivo}")
async def validar_hitl(arquivo: str):
    """
    Abre o browser em modo HITL — o analista co-pilota a validação.
    O processo roda em janela própria do Chrome.
    """
    caminho = _validar_caminho(arquivo, ROTEIROS_DIR)
    tenant = os.getenv("DEFAULT_TENANT_ID", "senior_default")
    job_id = _iniciar_bg(
        [sys.executable, "validator_hitl.py", caminho],
        "🟡 Validação HITL iniciada — aguarde a janela do Chrome abrir...",
        "✅ Validação HITL concluída. Brain atualizado com as correções.",
        tipo="rebuild", tenant_id=tenant,
    )
    if job_id is None:
        return JSONResponse(status_code=400, content={"erro": "Sistema ocupado"})
    return {"status": "iniciado", "job_id": job_id}

@app.get("/api/brain-stats")
async def brain_stats():
    """Retorna estatísticas do Brain DB: memórias, camadas mais acionadas, etc."""
    from vision_engine import obter_stats_brain
    return obter_stats_brain()


@app.get("/api/jobs/{job_id}")
async def consultar_job(job_id: str):
    """Retorna o estado atual de um job pelo seu job_id.

    Requisitos: 2.1.3, 2.2.3
    """
    job = job_registry.consultar_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"erro": "Job não encontrado"})
    return job


@app.get("/api/jobs/{job_id}/log")
async def consultar_log_job(job_id: str):
    """Retorna o log de execução de um job pelo seu job_id.

    O log fica acessível por pelo menos 24 horas após a conclusão do job.
    Requisitos: 2.2.4, NFR-3.5
    """
    job = job_registry.consultar_job(job_id)
    if job is None:
        return JSONResponse(status_code=404, content={"erro": "Job não encontrado"})
    return {
        "job_id": job_id,
        "status": job.get("status"),
        "log_execucao": job.get("log_execucao"),
    }


@app.get("/api/jobs")
async def listar_jobs(tenant_id: str = "senior_default", limit: int = 50):
    """Lista os jobs do tenant, do mais recente ao mais antigo.

    Requisitos: 2.1.3, 2.2.3
    """
    return job_registry.listar_jobs_por_tenant(tenant_id, limit=limit)


async def get_gps_roteiro(
    objetivo: str = "",
    tenant_id: str = "senior_default",
    token: str = Depends(verificar_token),
):
    """
    Busca o roteiro mais relevante para um objetivo via RAG (Pinecone).
    Retorna os passos formatados para o Motor GPS da extensão Aura.
    
    Formato de cada passo GPS:
      { id_passo, tooltip, seletor, label, acao, ancora }
    """
    if not objetivo.strip():
        return JSONResponse(status_code=422, content={"erro": "objetivo é obrigatório"})

    # 1. Busca no Pinecone pelo roteiro mais relevante
    busca = await asyncio.to_thread(dap_engine.buscar_contexto, objetivo.strip(), tenant_id)
    if not busca or busca.get("score", 0) < 0.45:
        return {"status": "nao_encontrado", "passos": []}

    nome_aula_alvo = busca.get("melhor_aula", "")
    if not nome_aula_alvo:
        return {"status": "nao_encontrado", "passos": []}

    # 2. Localiza o arquivo JSON do roteiro em roteiros_salvos/
    passos_gps = []
    arquivo_encontrado = None

    try:
        for arquivo in sorted(os.listdir(ROTEIROS_DIR)):
            if not arquivo.endswith(".json"):
                continue
            caminho = os.path.join(ROTEIROS_DIR, arquivo)
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    roteiro = json.load(f)
                nome_roteiro = roteiro.get("metadata", {}).get("nome_aula", "")
                id_trein     = roteiro.get("metadata", {}).get("id_treinamento", "")

                # Match robusto: normaliza acentos e caixa antes de comparar.
                # O Pinecone pode retornar o nome com variação de capitalização
                # ou acento diferente do que está salvo no JSON.
                alvo_norm = _norm(nome_aula_alvo)
                if (_norm(nome_roteiro) == alvo_norm or
                        _norm(id_trein) == alvo_norm or
                        _norm(id_trein) == _norm(limpar_nome(nome_aula_alvo)) or
                        # Fallback: nome do arquivo contém o alvo (match parcial)
                        alvo_norm in _norm(nome_roteiro) or
                        _norm(nome_roteiro) in alvo_norm):
                    arquivo_encontrado = arquivo

                    for passo in roteiro.get("passos", []):
                        if passo.get("is_conclusao"):
                            continue
                        acoes = passo.get("acoes_tecnicas", [])
                        if not acoes:
                            continue

                        # Expõe CADA ação técnica como um step GPS separado.
                        # Isso resolve o caso onde um passo pedagógico tem múltiplos
                        # cliques (ex: Senior Flow → GED → Documentos).
                        ancora_passo  = passo.get("pedagogia", {}).get("ancora", "")[:120]
                        tooltip_passo = passo.get("pedagogia", {}).get("tooltip_dap", "")
                        id_passo      = passo.get("id_passo", len(passos_gps) + 1)

                        acoes_validas = [
                            ac for ac in acoes
                            if ac.get("acao") not in ("concluir_video",)
                            and (ac.get("elemento_alvo", {}).get("seletor_hint", "")
                                 or ac.get("elemento_alvo", {}).get("seletor_css", ""))
                        ]

                        if not acoes_validas:
                            continue

                        for i, ac in enumerate(acoes_validas):
                            alvo = ac.get("elemento_alvo", {})
                            s    = alvo.get("seletor_hint", "") or alvo.get("seletor_css", "")
                            micro = ac.get("micro_narracao", "").strip()

                            # Primeira ação do passo: usa a âncora pedagógica completa
                            # Ações seguintes: usa a micro-narração ou o label
                            if i == 0:
                                tooltip_step = ancora_passo or tooltip_passo
                            else:
                                tooltip_step = micro or alvo.get("label_curto", "") or tooltip_passo

                            passos_gps.append({
                                "id_passo":    f"{id_passo}.{i+1}",
                                "tooltip":     tooltip_step,
                                "ancora":      ancora_passo if i == 0 else micro,
                                "seletor":     s,
                                "label":       alvo.get("label_curto", ""),
                                "acao":        ac.get("acao", "clique"),
                            })
                    break
            except Exception:
                continue

    except Exception as e:
        logging.error(f"GPS: Erro ao varrer roteiros: {e}", exc_info=True)
        return {"status": "erro", "mensagem": "Erro interno ao buscar roteiro GPS. Consulte os logs do servidor."}

    if not passos_gps:
        return {"status": "nao_encontrado", "passos": []}

    logging.info(f"GPS: Roteiro '{nome_aula_alvo}' — {len(passos_gps)} passos retornados.")
    return {
        "status":    "sucesso",
        "nome_aula": nome_aula_alvo,
        "arquivo":   arquivo_encontrado,
        "score":     round(busca.get("score", 0), 3),
        "passos":    passos_gps,
    }

@app.post("/api/roteiros/{id}/aplicar-blur")
async def aplicar_blur_roteiro(id: str):
    """Reprocessa blur em screenshots de um roteiro existente.

    Percorre todos os passos e ações técnicas do roteiro. Para cada ação com
    `elemento_alvo.dados_blur.blur == True`, aplica retângulo sólido sobre a
    região marcada no `screenshot_referencia` e persiste o resultado.

    Retorna contagem de ações percorridas e quantas tiveram blur aplicado.

    Requisito: 1.6
    """
    caminho = _validar_caminho(id + ".json", ROTEIROS_DIR)

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            roteiro = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Roteiro não encontrado.")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {e}")

    passos_processados = 0
    passos_com_blur = 0

    for passo in roteiro.get("passos", []):
        for acao in passo.get("acoes_tecnicas", []):
            passos_processados += 1

            elemento_alvo = acao.get("elemento_alvo") or {}
            dados_blur = elemento_alvo.get("dados_blur") or {}

            if not dados_blur.get("blur"):
                continue

            regiao = dados_blur.get("regiao")
            if not regiao:
                logging.warning(
                    f"[aplicar-blur] Ação com blur=True mas sem regiao definida "
                    f"(passo {passo.get('id_passo')}) — ignorada."
                )
                continue

            screenshot = elemento_alvo.get("screenshot_referencia")
            if not screenshot:
                logging.warning(
                    f"[aplicar-blur] Ação com blur=True mas sem screenshot_referencia "
                    f"(passo {passo.get('id_passo')}) — ignorada."
                )
                continue

            # screenshot pode ser path de arquivo em disco ou base64 inline
            screenshot_b64 = screenshot
            is_file_path = not screenshot.startswith("data:") and len(screenshot) < 512 and os.path.exists(screenshot)

            if is_file_path:
                try:
                    import base64 as _b64
                    with open(screenshot, "rb") as f_img:
                        screenshot_b64 = _b64.b64encode(f_img.read()).decode("utf-8")
                except Exception as e:
                    logging.warning(f"[aplicar-blur] Não foi possível ler screenshot '{screenshot}': {e}")
                    continue

            screenshot_borrado = aplicar_blur_screenshot(screenshot_b64, [regiao])

            # Persiste de volta — arquivo em disco ou base64 inline
            if is_file_path:
                try:
                    import base64 as _b64
                    dados_img = screenshot_borrado
                    if "," in dados_img:
                        dados_img = dados_img.split(",", 1)[1]
                    with open(screenshot, "wb") as f_img:
                        f_img.write(_b64.b64decode(dados_img))
                except Exception as e:
                    logging.warning(f"[aplicar-blur] Não foi possível salvar screenshot borrado '{screenshot}': {e}")
                    continue
            else:
                acao["elemento_alvo"]["screenshot_referencia"] = screenshot_borrado

            passos_com_blur += 1
            logging.info(
                f"[aplicar-blur] Blur aplicado — passo {passo.get('id_passo')}, "
                f"regiao={regiao}"
            )

    _atomic_write_json(caminho, roteiro)

    return {
        "passos_processados": passos_processados,
        "passos_com_blur": passos_com_blur,
    }


# ==============================================================
# SHAREABLE TRAINING LINK (Requisito 3)
# ==============================================================

TTL_DIAS = int(os.getenv("LINK_TTL_DIAS", "30"))

_HTML_LINK_EXPIRADO = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Link Expirado</title>
<style>
body{font-family:"Segoe UI",system-ui,sans-serif;background:#0f172a;color:#f8fafc;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;margin:0;gap:16px;}
h1{font-size:2rem;color:#f87171;}
p{color:#94a3b8;max-width:420px;text-align:center;line-height:1.6;}
</style></head>
<body>
<h1>&#9200; Link Expirado</h1>
<p>Este link de treinamento expirou e n&#227;o est&#225; mais dispon&#237;vel.<br>
Solicite um novo link ao respons&#225;vel pelo treinamento.</p>
</body></html>"""

_HTML_LINK_NAO_ENCONTRADO = """<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"><title>Link Inv&#225;lido</title>
<style>
body{font-family:"Segoe UI",system-ui,sans-serif;background:#0f172a;color:#f8fafc;
  display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100vh;margin:0;gap:16px;}
h1{font-size:2rem;color:#f87171;}
p{color:#94a3b8;max-width:420px;text-align:center;line-height:1.6;}
</style></head>
<body>
<h1>&#128279; Link Inv&#225;lido</h1>
<p>Este link de treinamento n&#227;o foi encontrado.<br>
Verifique se o endere&#231;o est&#225; correto ou solicite um novo link.</p>
</body></html>"""


def _montar_slides_roteiro(roteiro: dict) -> str:
    """Monta a lista de slides JSON a partir de um roteiro, reutilizando a logica
    de scorm_builder.criar_pacote_scorm sem zipar."""
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
    return json.dumps(slides, ensure_ascii=False)


@app.post("/api/roteiros/{id}/gerar-link")
async def gerar_link_roteiro(id: str, request: Request):
    """Gera URL publica com TTL para acesso ao player SCORM sem autenticacao.

    Requisito: 3.1, 3.3
    """
    _validar_caminho(id + ".json", ROTEIROS_DIR)

    caminho = os.path.join(ROTEIROS_DIR, id + ".json")
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail="Roteiro nao encontrado.")

    token = str(uuid.uuid4())
    criado_em = int(time.time())
    expira_em = criado_em + TTL_DIAS * 86400

    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            conn.execute(
                "INSERT INTO sim_links (token, roteiro_id, criado_em, expira_em, total_acessos) "
                "VALUES (?, ?, ?, ?, 0)",
                (token, id, criado_em, expira_em),
            )
            conn.commit()
    except Exception as e:
        logging.error(f"[gerar-link] Falha ao persistir link: {e}")
        raise HTTPException(status_code=500, detail="Erro ao persistir link no banco de dados.")

    return {
        "url": f"/play/{token}",
        "expira_em": datetime.fromtimestamp(expira_em).isoformat(),
        "token": token,
    }


@app.get("/play/{token}", response_class=HTMLResponse)
async def acessar_player_via_link(token: str, request: Request):
    """Serve o player SCORM diretamente via link publico sem autenticacao.

    Requisito: 3.2, 3.4, 3.5
    """
    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            row = conn.execute(
                "SELECT roteiro_id, expira_em, total_acessos FROM sim_links WHERE token = ?",
                (token,),
            ).fetchone()
    except Exception as e:
        logging.error(f"[play] Erro ao consultar sim_links: {e}")
        return HTMLResponse(content=_HTML_LINK_NAO_ENCONTRADO)

    if row is None:
        return HTMLResponse(content=_HTML_LINK_NAO_ENCONTRADO)

    roteiro_id, expira_em, total_acessos = row

    if expira_em < int(time.time()):
        return HTMLResponse(content=_HTML_LINK_EXPIRADO)

    # Incrementar total_acessos
    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            conn.execute(
                "UPDATE sim_links SET total_acessos = total_acessos + 1 WHERE token = ?",
                (token,),
            )
            conn.commit()
    except Exception as e:
        logging.warning(f"[play] Falha ao incrementar total_acessos: {e}")

    # Registrar evento "iniciou" em analytics_eventos
    try:
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "")
        usuario_id = hashlib.md5(f"{ip}_{ua}".encode()).hexdigest()[:16]
        ts = int(time.time() * 1000)
        with sqlite3.connect("brain.db", timeout=5) as conn:
            conn.execute(
                "INSERT INTO analytics_eventos (roteiro_id, passo_id, usuario_id, evento, ts) "
                "VALUES (?, ?, ?, ?, ?)",
                (roteiro_id, None, usuario_id, "iniciou", ts),
            )
            conn.commit()
    except Exception as e:
        logging.warning(f"[play] Falha ao registrar evento 'iniciou': {e}")

    # Ler roteiro e gerar HTML do player
    caminho = os.path.join(ROTEIROS_DIR, roteiro_id + ".json")
    if not os.path.exists(caminho):
        return HTMLResponse(content=_HTML_LINK_NAO_ENCONTRADO)

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            roteiro = json.load(f)
    except Exception as e:
        logging.error(f"[play] Erro ao ler roteiro '{roteiro_id}': {e}")
        return HTMLResponse(content=_HTML_LINK_NAO_ENCONTRADO)

    nome_aula = roteiro.get("metadata", {}).get("nome_aula", "Treinamento")
    slides_json = _montar_slides_roteiro(roteiro)
    html_content = scorm_builder._gerar_player_html(nome_aula, slides_json, roteiro_id)

    return HTMLResponse(content=html_content)


@app.get("/api/links/{token}/progresso")
async def progresso_link(token: str):
    """Retorna metricas de acesso e conclusao de um link de treinamento.

    Requisito: 3.6
    """
    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            row = conn.execute(
                "SELECT roteiro_id, total_acessos FROM sim_links WHERE token = ?",
                (token,),
            ).fetchone()
    except Exception as e:
        logging.error(f"[progresso] Erro ao consultar sim_links: {e}")
        raise HTTPException(status_code=500, detail="Erro ao consultar banco de dados.")

    if row is None:
        raise HTTPException(status_code=404, detail="Link nao encontrado.")

    roteiro_id, total_acessos = row

    try:
        with sqlite3.connect("brain.db", timeout=5) as conn:
            # Verificar se houve evento "completou"
            completou_row = conn.execute(
                "SELECT COUNT(*) FROM analytics_eventos "
                "WHERE roteiro_id = ? AND evento = 'completou'",
                (roteiro_id,),
            ).fetchone()
            completado = bool(completou_row and completou_row[0] > 0)

            # Ultimo evento "iniciou" para o roteiro_id
            ultimo_row = conn.execute(
                "SELECT MAX(ts) FROM analytics_eventos "
                "WHERE roteiro_id = ? AND evento = 'iniciou'",
                (roteiro_id,),
            ).fetchone()
            ultimo_ts = ultimo_row[0] if ultimo_row and ultimo_row[0] is not None else None
    except Exception as e:
        logging.error(f"[progresso] Erro ao consultar analytics_eventos: {e}")
        raise HTTPException(status_code=500, detail="Erro ao consultar eventos.")

    ultimo_acesso = None
    if ultimo_ts is not None:
        try:
            # ts e armazenado em milissegundos
            ultimo_acesso = datetime.fromtimestamp(ultimo_ts / 1000).isoformat()
        except Exception:
            ultimo_acesso = None

    return {
        "total_acessos": total_acessos,
        "ultimo_acesso": ultimo_acesso,
        "completado": completado,
    }


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("SENIOR TRAINING OS INICIADO")
    print("Aceda no navegador: http://localhost:8000")
    print("=" * 50 + "\n")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)
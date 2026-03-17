"""
dap_engine.py — Cérebro da Aura (RAG + Gemini Vision + Memória + Resiliência)
=============================================================================
Atualizações:
  - Cache com TTL (5 min), limite de tamanho e Thread-Safety (Locks).
  - AI Gate: Bypass do Gemini para respostas já conhecidas no Pinecone.
  - Memória de Contexto (Histórico das últimas conversas injetado no prompt).
  - Resiliência: Retry com Exponential Backoff para falhas de rede nas APIs.
"""

import os
import json
import base64
import logging
import asyncio
import threading
import time
from functools import wraps
from dotenv import load_dotenv

load_dotenv()

from pinecone import Pinecone
from openai import OpenAI
from google import genai
from google.genai import types
import sqlite3

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aura_engine")

# =========================================================
# CONFIGURAÇÃO
# =========================================================
OPENAI_EMBED_MODEL  = "text-embedding-3-large"
GEMINI_LLM_MODEL    = "gemini-2.5-flash"
TARGET_DIM          = 3072
TOP_K               = 5
SCORE_THRESHOLD     = 0.45

# =========================================================
# CACHE PERSISTENTE (SQLite) - SPRINT 3
# =========================================================
_CACHE_TTL_SEGUNDOS = 2592000  # 30 DIAS (30 * 24 * 60 * 60)
_CACHE_MAX_REGISTOS = 5000     # Limite de segurança de tamanho
_DB_CACHE_FILE = "aura_cache.db"
_cache_lock = threading.Lock()

def _init_db_cache():
    """Cria a tabela de cache no SQLite se não existir."""
    with _cache_lock:
        with sqlite3.connect(_DB_CACHE_FILE) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS dap_cache (
                    cache_key TEXT PRIMARY KEY,
                    resposta_json TEXT,
                    timestamp REAL
                )
            """)
            conn.commit()

_init_db_cache()

def _limpar_cache_antigo(conn):
    """Limpeza Híbrida: Por tempo (30 dias) e por Tamanho (Máx 5000)."""
    # 1. Limpa os que passaram de 30 dias
    limite_tempo = time.time() - _CACHE_TTL_SEGUNDOS
    conn.execute("DELETE FROM dap_cache WHERE timestamp < ?", (limite_tempo,))
    
    # 2. Limpa os mais antigos se ultrapassar 5.000 registos
    conn.execute(f"""
        DELETE FROM dap_cache 
        WHERE cache_key NOT IN (
            SELECT cache_key FROM dap_cache 
            ORDER BY timestamp DESC 
            LIMIT {_CACHE_MAX_REGISTOS}
        )
    """)

# FIX Bug #DAP-02: _limpar_cache_antigo executava 2 DELETEs pesados a cada request.
# Throttle: limpeza apenas 1x/hora usando timestamp global.
_ultima_limpeza_cache: float = 0.0
_INTERVALO_LIMPEZA_S: float = 3600.0  # 1 hora

def _cache_get(key: str) -> dict | None:
    global _ultima_limpeza_cache
    with _cache_lock:
        try:
            with sqlite3.connect(_DB_CACHE_FILE) as conn:
                agora = time.time()
                if agora - _ultima_limpeza_cache > _INTERVALO_LIMPEZA_S:
                    _limpar_cache_antigo(conn)
                    _ultima_limpeza_cache = agora
                cursor = conn.execute("SELECT resposta_json FROM dap_cache WHERE cache_key = ?", (key,))
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"Erro ao ler cache SQLite: {e}")
    return None

def _cache_set(key: str, valor: dict) -> None:
    with _cache_lock:
        try:
            with sqlite3.connect(_DB_CACHE_FILE) as conn:
                resposta_str = json.dumps(valor, ensure_ascii=False)
                agora = time.time()
                conn.execute("""
                    INSERT OR REPLACE INTO dap_cache (cache_key, resposta_json, timestamp)
                    VALUES (?, ?, ?)
                """, (key, resposta_str, agora))
                conn.commit()
        except Exception as e:
            logger.error(f"Erro ao gravar cache SQLite: {e}")


# =========================================================
# MOTOR DE RESILIÊNCIA (Exponential Backoff)
# =========================================================
def retry_exponencial(max_tentativas=3, delay_inicial=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tentativas = 0
            while tentativas < max_tentativas:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    tentativas += 1
                    if tentativas == max_tentativas:
                        logger.error(f"Falha definitiva após {max_tentativas} tentativas: {e}")
                        raise e
                    tempo_espera = delay_inicial * (2 ** (tentativas - 1))
                    logger.warning(f"Falha na API. Tentando novamente em {tempo_espera}s... (Tentativa {tentativas}/{max_tentativas})")
                    time.sleep(tempo_espera)
        return wrapper
    return decorator


# =========================================================
# CLIENTES
# =========================================================
client_openai  = None
gemini_client  = None
pinecone_index = None

try:
    oa_key = os.getenv("OPENAI_API_KEY")
    if oa_key:
        client_openai = OpenAI(api_key=oa_key)
    else:
        logger.warning("OPENAI_API_KEY não configurada. Embeddings e RAG desativados.")

    g_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if g_key:
        gemini_client = genai.Client(api_key=g_key)
    else:
        logger.warning("GOOGLE_API_KEY não configurada. Gemini Vision desativado.")

    pc_key   = os.getenv("PINECONE_API_KEY")
    idx_name = os.getenv("PINECONE_INDEX_NAME")
    if pc_key and idx_name:
        pc = Pinecone(api_key=pc_key)
        pinecone_index = pc.Index(idx_name)
    else:
        logger.warning("PINECONE_API_KEY ou PINECONE_INDEX_NAME ausentes. RAG desativado.")

except Exception as e:
    logger.error(f"Erro na inicialização dos clientes: {e}")


# =========================================================
# MEMÓRIA VETORIAL (OPENAI) & INGESTÃO
# =========================================================

@retry_exponencial(max_tentativas=3)
def gerar_embedding(texto: str) -> list[float]:
    response = client_openai.embeddings.create(
        input=texto, model=OPENAI_EMBED_MODEL, dimensions=TARGET_DIM
    )
    return response.data[0].embedding


def ingestar_para_pinecone(roteiro: dict, tenant_id: str = "senior_default") -> dict:
    if not pinecone_index or not client_openai:
        return {"status": "erro", "mensagem": "Motores de IA não configurados."}

    try:
        nome_aula = roteiro.get("metadata", {}).get("nome_aula", "Treinamento")
        vetores   = []

        for passo in roteiro.get("passos", []):
            ancora  = passo.get("pedagogia", {}).get("ancora", "")
            tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
            if not ancora:
                continue

            seletor_exato = ""
            acoes = passo.get("acoes_tecnicas", [])
            if acoes:
                seletor_exato = (
                    acoes[0].get("seletor_css", "")
                    or acoes[0].get("elemento_alvo", {}).get("seletor_hint", "")
                )

            texto_vetorizar = f"AULA: {nome_aula}. INSTRUCAO: {ancora}. DICA: {tooltip}"
            embedding       = gerar_embedding(texto_vetorizar)
            id_vetor        = f"{nome_aula}_passo_{passo.get('id_passo')}".replace(" ", "_")

            vetores.append({
                "id":     id_vetor,
                "values": embedding,
                "metadata": {
                    "aula":    nome_aula,
                    "passo":   passo.get("id_passo"),
                    "texto":   ancora,
                    "tooltip": tooltip,
                    "seletor": seletor_exato,
                },
            })

        if vetores:
            pinecone_index.upsert(vectors=vetores, namespace=tenant_id)

        return {"status": "sucesso", "mensagem": f"{len(vetores)} passos indexados com sucesso."}

    except Exception as e:
        logger.error(f"Erro na ingestao: {e}")
        return {"status": "erro", "mensagem": str(e)}


def buscar_contexto(prompt_usuario: str, tenant_id: str = "senior_default") -> dict | None:
    if not pinecone_index or not client_openai:
        return None
    try:
        query_embedding = gerar_embedding(prompt_usuario)
        resultados      = pinecone_index.query(
            vector=query_embedding, top_k=TOP_K, namespace=tenant_id, include_metadata=True
        )

        contextos      = []
        melhor_seletor = None
        melhor_score   = 0.0
        melhor_aula    = None  # GPS: rastreia o nome da aula com maior score

        for match in resultados.matches:
            if match.score < SCORE_THRESHOLD:
                continue
            md      = match.metadata
            contexto = (
                f"MANUAL: {md.get('aula')}\n"
                f"INSTRUCAO: {md.get('texto')}\n"
                f"DICA: {md.get('tooltip')}"
            )
            if md.get("seletor"):
                contexto += f"\nSELETOR_EXATO: {md.get('seletor')}"
                if match.score > melhor_score:
                    melhor_score   = match.score
                    melhor_seletor = md.get("seletor")
                    melhor_aula    = md.get("aula")
            contextos.append(contexto)

        if not contextos:
            return None

        return {
            "texto_rag":      "\n\n---\n\n".join(contextos),
            "seletor_direto": melhor_seletor,
            "score":          melhor_score,
            "melhor_aula":    melhor_aula,  # GPS: nome da aula com maior score
        }

    except Exception as e:
        logger.error(f"Erro RAG: {e}")
        return None


# =========================================================
# SCHEMA DE RESPOSTA
# =========================================================
aura_schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "analise_interna": types.Schema(type=types.Type.STRING),
        "mensagem":        types.Schema(type=types.Type.STRING),
        "elemento_id":     types.Schema(type=types.Type.INTEGER, nullable=True),
        "seletor_css":     types.Schema(type=types.Type.STRING,  nullable=True),
        "sugestoes": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(type=types.Type.STRING),
            description="2 a 3 perguntas curtas (max 5 palavras) que o utilizador pode querer fazer.",
            nullable=True,
        ),
    },
    required=["analise_interna", "mensagem"],
)


# =========================================================
# CEREBRO DA AURA (VISÃO E MEMÓRIA)
# =========================================================

def _analisar_sync(
    image_b64: str,
    url: str,
    prompt_usuario: str,
    dom_context: str,
    user_name: str,
    tenant_id: str,
    historico: list
) -> dict:

    # 1. Verifica Cache (Considera o hash do DOM para evitar stale cache entre telas)
    # FIX Bug #DAP-01: hash() Python é não-determinístico entre sessões (PYTHONHASHSEED).
    # Isso invalidava TODO o cache SQLite a cada restart. Corrigido com hashlib.md5.
    import hashlib
    dom_hash  = hashlib.md5(dom_context.encode("utf-8", errors="replace")).hexdigest()[:12]
    cache_key = f"{tenant_id}_{url}_{prompt_usuario}_{dom_hash}"

    cached = _cache_get(cache_key)
    if cached:
        logger.info("Aura: Resposta servida via Cache!")
        return cached

    # 2. Busca RAG (Usa o histórico recente para dar contexto à busca vetorial)
    texto_busca_rag = f"{historico[-1]['texto']} {prompt_usuario}" if historico else prompt_usuario
    busca_rag = buscar_contexto(texto_busca_rag, tenant_id)

    # =========================================================
    # 3. AI GATE: Bypass do Gemini Vision
    # =========================================================
    if busca_rag and busca_rag["score"] > 0.80 and busca_rag["seletor_direto"]:
        logger.info(f"⚡ AI GATE ATIVADO | Confiança: {busca_rag['score']:.2f} | Seletor: {busca_rag['seletor_direto']}")
        contexto_texto  = busca_rag["texto_rag"]
        instrucao_limpa = (
            contexto_texto.split("INSTRUCAO: ")[1].split("\nDICA:")[0]
            if "INSTRUCAO: " in contexto_texto
            else "Siga a instrucao destacada na tela."
        )
        resultado_rapido = {
            "mensagem":    f"Encontrei isso no manual oficial:\n{instrucao_limpa}",
            "elemento_id": None,
            "seletor_css": busca_rag["seletor_direto"],
            "sugestoes":   ["O que mais posso fazer?", "Proximo passo"],
        }
        _cache_set(cache_key, resultado_rapido)
        return resultado_rapido

    # =========================================================
    # 4. FALLBACK: Gemini Vision com Memória Conversacional
    # =========================================================
    contexto_rag = busca_rag["texto_rag"] if busca_rag else "Nao ha manual para isto. Use a sua visao e o DOM para ajudar."
    rag_tem_seletor = busca_rag is not None and "SELETOR_EXATO" in contexto_rag

    # Constrói o bloco de memória para o prompt
    historico_formatado = "\n".join([f"[{msg['autor']}]: {msg['texto']}" for msg in historico])
    bloco_memoria = f"HISTÓRICO RECENTE DA CONVERSA:\n{historico_formatado}\n" if historico else ""

    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        image_bytes = base64.b64decode(image_b64)

        prompt_sistema = f"""Voce e a Aura, a assistente virtual inteligente do ecossistema Senior X.
Voce esta a guiar o utilizador: {user_name}.

{bloco_memoria}
PERSONALIDADE:
Moderna, agil e prestativa. NUNCA use saudacoes datadas. Proibido responder apenas "Pronto!".

CONHECIMENTO DA EMPRESA (Manual RAG):
{contexto_rag}

ESTRUTURA DA TELA ATUAL (DOM):
{dom_context}

INSTRUCOES DE CLIQUE E SUGESTOES (CRITICO):
1. PRIORIDADE: Procure SEMPRE o botao na lista do DOM acima. Se ele la estiver, preencha obrigatoriamente "elemento_id".
2. O Manual RAG pode conter "SELETOR_EXATO:". Somente se essa palavra estiver visivel no manual, copie o valor para "seletor_css".
3. PODE e DEVE preencher os dois campos ao mesmo tempo se ambos existirem.
4. GERE SUGESTOES: No campo "sugestoes", crie 2 ou 3 perguntas muito curtas (max 5 palavras).
"""
        
        # Chamada à API com Retry Embutido
        tentativas = 0
        resposta = None
        while tentativas < 3:
            try:
                resposta = gemini_client.models.generate_content(
                    model=GEMINI_LLM_MODEL,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                        f"URL: {url}\n{user_name} pergunta: {prompt_usuario}",
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=prompt_sistema,
                        response_mime_type="application/json",
                        response_schema=aura_schema,
                        temperature=0.4,
                    ),
                )
                break
            except Exception as e:
                tentativas += 1
                if tentativas == 3: raise e
                tempo_espera = 1 * (2 ** (tentativas - 1))
                logger.warning(f"Google API ocupada/falhou. Tentando novamente em {tempo_espera}s...")
                time.sleep(tempo_espera)

        dados          = json.loads(resposta.text)
        seletor_gerado = dados.get("seletor_css")

        if seletor_gerado and not rag_tem_seletor:
            logger.warning("Aura Vision inferiu um seletor CSS sem base no RAG. O Frontend tentará utilizá-lo com fallback.")

        print("\n" + "="*50)
        print("👁️ AURA VISION LOG:")
        print(f"Histórico: {len(historico)} mensagens anteriores lidas.")
        print(f"Raciocínio: {dados.get('analise_interna')}")
        print(f"Mensagem: {dados.get('mensagem')}")
        print(f"ID Escolhido: {dados.get('elemento_id')}")
        print(f"Seletor Brain: {seletor_gerado}")
        print("="*50 + "\n")

        resultado_final = {
            "mensagem":    dados.get("mensagem", f"Ola, {user_name}! Como posso ajudar?"),
            "elemento_id": dados.get("elemento_id"),
            "seletor_css": seletor_gerado,
            "sugestoes":   dados.get("sugestoes") or [],
        }

        _cache_set(cache_key, resultado_final)
        return resultado_final

    except Exception as e:
        logger.error(f"Erro Vision Fatal: {e}")
        return {
            "mensagem":    f"Ola, {user_name}! A minha conexão falhou após várias tentativas. Pode repetir?",
            "elemento_id": None,
            "seletor_css": None,
            "sugestoes":   ["Tentar novamente"],
        }


async def analisar_tela_dap(
    image_b64: str,
    url: str,
    prompt_usuario: str,
    dom_context: str = "",
    user_name: str   = "Utilizador",
    tenant_id: str   = "senior_default",
    historico: list  = None
) -> dict:
    if historico is None: historico = []
    
    if not gemini_client or not client_openai:
        return {
            "mensagem":    "Motores de IA desconectados. Verifique as chaves de API no .env",
            "elemento_id": None,
            "seletor_css": None,
            "sugestoes":   [],
        }
    return await asyncio.to_thread(
        _analisar_sync, image_b64, url, prompt_usuario, dom_context, user_name, tenant_id, historico
    )
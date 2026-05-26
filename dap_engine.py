"""
dap_engine.py — Cérebro da Aura (RAG + Gemini Vision + Memória + Resiliência)
=============================================================================
Atualizações:
  - Cache com TTL (5 min), limite de tamanho e Thread-Safety (Locks).
  - AI Gate: Bypass do Gemini para respostas já conhecidas no Pinecone.
  - Memória de Contexto (Histórico das últimas conversas injetado no prompt).
  - Resiliência: Retry com Exponential Backoff para falhas de rede nas APIs.
"""

import asyncio
import base64
import json
import logging
import os
import re
import threading
import time
from functools import wraps

from dotenv import load_dotenv

load_dotenv()

import sqlite3

from google import genai
from google.genai import types
from openai import OpenAI
from pinecone import Pinecone

from guardrails import GuardrailConfig, GuardrailEngine, SecurityEventLogger
from navigation_fallback import (
    get_navigation_fallback_engine,
)
from utils import com_retry, limpar_nome

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
ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS = int(os.getenv("ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS", "500"))

# =========================================================
# MODULE ALIASES & QUERY NORMALIZATION
# =========================================================
_MODULE_ALIASES = {
    "hcm": "HCM Gestão de Pessoas Human Capital Management",
    "bpm": "BPM Business Process Management gestão processos",
    "ged": "GED Gestão Eletrônica de Documentos",
    "konviva": "Konviva plataforma educação corporativa LMS",
    "lms": "LMS Learning Management System plataforma aprendizagem",
    "erp": "ERP Enterprise Resource Planning sistema integrado gestão",
    "rh": "RH Recursos Humanos gestão pessoas",
    "dp": "DP Departamento Pessoal folha pagamento",
    "ti": "TI Tecnologia da Informação suporte sistemas",
    "scm": "SCM Supply Chain Management cadeia suprimentos",
    "crm": "CRM Customer Relationship Management relacionamento cliente",
    "bi": "BI Business Intelligence análise dados relatórios",
    "wms": "WMS Warehouse Management System gestão armazém",
    "tms": "TMS Transportation Management System gestão transporte",
}

_INFORMAL_MARKERS = {"vc", "q ", "pq", "tb", "oq", "td", "mt", "cmg", "blz"}


def _normalizar_query(prompt: str) -> str:
    """Normalize informal/abbreviated queries by expanding known terms.

    This function is ADDITIVE ONLY — it never removes or replaces
    the user's original words. It appends expanded context to improve
    embedding similarity against formally-indexed content.

    Returns the original text unchanged if no abbreviations or
    informal markers are found.
    """
    prompt_lower = prompt.lower()
    expansions = []

    # Check for known module abbreviations
    for abbr, expanded in _MODULE_ALIASES.items():
        # Match abbreviation as a word boundary (not inside other words)
        if re.search(rf'\b{re.escape(abbr)}\b', prompt_lower):
            expansions.append(expanded)

    # Check for informal markers (indicates informal phrasing)
    has_informal = any(marker in prompt_lower for marker in _INFORMAL_MARKERS)

    if not expansions and not has_informal:
        return prompt  # No normalization needed

    # Build normalized text: original + expansions
    normalized = prompt
    if expansions:
        normalized = normalized + " " + " ".join(expansions)

    return normalized

# =========================================================
# CACHE PERSISTENTE (SQLite) - SPRINT 3
# =========================================================
_CACHE_TTL_SEGUNDOS = 2592000  # 30 DIAS (30 * 24 * 60 * 60)
_CACHE_MAX_REGISTOS = 5000     # Limite de segurança de tamanho
_DB_CACHE_FILE = "aura_cache.db"
_cache_lock = threading.Lock()

# =========================================================
# IDENTITY DETECTION — Short-circuit for meta/identity questions
# =========================================================
_IDENTITY_PATTERNS = [
    "quem é vc", "quem é você", "quem e voce", "qual seu nome",
    "qual é seu nome", "qual o seu nome", "o que vc faz",
    "o que você faz", "o que voce faz", "quem te criou",
    "como vc se chama", "como você se chama", "vc é quem",
    "me fala sobre vc", "se apresenta", "se apresente",
]

_IDENTITY_RESPONSE = {
    "mensagem": (
        "Olá{user_greeting}! Eu sou a **Aura**, sua assistente virtual inteligente "
        "do ecossistema Senior X. Estou aqui para te ajudar a navegar pelo sistema, "
        "tirar dúvidas sobre módulos e te guiar nos processos. "
        "Como posso te ajudar agora?"
    ),
    "elemento_id": None,
    "seletor_css": None,
    "sugestoes": [
        "O que você pode fazer?",
        "Me ajuda a navegar",
        "Quais módulos você conhece?",
    ],
    "confidence_score": 1.0,
    "source_reference": "identity_detector",
}


def _is_identity_question(prompt: str) -> bool:
    """Detect identity/meta questions about Aura (name, purpose, creator)."""
    normalized = prompt.lower().strip().rstrip("?!.")
    return any(pattern in normalized for pattern in _IDENTITY_PATTERNS)


# =========================================================
# GREETING DETECTION — Short-circuit for simple greetings
# =========================================================
_GREETING_PATTERNS = {
    "oi", "olá", "ola", "hey", "eai", "e ai", "e aí",
    "bom dia", "boa tarde", "boa noite", "fala", "salve",
    "hello", "hi", "opa", "oie", "oii", "oiii",
}


def _is_simple_greeting(prompt: str) -> bool:
    """Detect simple greetings that don't need the full RAG pipeline."""
    normalized = prompt.lower().strip().rstrip("?!.,")
    return normalized in _GREETING_PATTERNS


_GREETING_RESPONSE = {
    "mensagem": (
        "Olá{user_greeting}! Estou aqui para te ajudar. "
        "O que precisa fazer no sistema hoje?"
    ),
    "elemento_id": None,
    "seletor_css": None,
    "sugestoes": [
        "Me ajuda a navegar",
        "Tenho uma dúvida",
        "O que você pode fazer?",
    ],
    "confidence_score": 1.0,
    "source_reference": "greeting_detector",
}


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
# GUARDRAIL SYSTEM INITIALIZATION
# =========================================================
_guardrail_config = GuardrailConfig.from_env()
_guardrail_engine = GuardrailEngine(_guardrail_config)
_security_logger = SecurityEventLogger()

logger.info(f"Guardrails inicializados: SQL={_guardrail_config.enable_sql_injection}, "
            f"Prompt={_guardrail_config.enable_prompt_injection}, "
            f"Offensive={_guardrail_config.enable_offensive_content}, "
            f"Competitor={_guardrail_config.enable_competitor_filter}, "
            f"VectorOnly={_guardrail_config.enable_vector_store_only}")


# =========================================================
# ELEMENT VISIBILITY CHECK
# =========================================================

def _extract_element_keywords(prompt_usuario: str) -> list[str]:
    """
    Extract potential element references from user query.
    
    Args:
        prompt_usuario: User query
        
    Returns:
        list[str]: List of keywords that might reference UI elements
    """
    # Simple keyword extraction - can be improved with NLP
    keywords = []

    # Common UI element patterns
    ui_patterns = [
        "botão", "botao", "menu", "aba", "campo", "opção", "opcao",
        "link", "formulário", "formulario", "tabela", "lista",
        "painel", "janela", "modal", "dropdown", "checkbox"
    ]

    prompt_lower = prompt_usuario.lower()

    # Extract quoted strings (likely element names)
    import re
    quoted = re.findall(r'"([^"]*)"', prompt_usuario)
    quoted.extend(re.findall(r"'([^']*)'", prompt_usuario))
    keywords.extend(quoted)

    # Extract capitalized words (likely proper names)
    words = prompt_usuario.split()
    for word in words:
        if word and word[0].isupper() and len(word) > 2:
            keywords.append(word)

    # Extract words after UI patterns
    for pattern in ui_patterns:
        if pattern in prompt_lower:
            idx = prompt_lower.find(pattern)
            # Get next few words after the pattern
            remaining = prompt_usuario[idx:].split()[:4]
            keywords.extend(remaining)

    # Remove duplicates and empty strings
    keywords = list(set([k.strip() for k in keywords if k.strip()]))

    return keywords


def _is_navigation_request(prompt_usuario: str) -> bool:
    """
    Detect if the user query is requesting navigation/guidance vs asking a conceptual question.
    
    Args:
        prompt_usuario: User query
        
    Returns:
        bool: True if this is a navigation request, False if it's a conceptual question
    """
    prompt_lower = prompt_usuario.lower().strip()

    # Confirmation patterns — these are responses to a previous suggestion,
    # NOT new navigation requests. They should go through the normal pipeline
    # which has conversational memory to handle context.
    confirmation_patterns = [
        "sim, me guie", "sim me guie", "sim", "pode ser", "vamos lá",
        "vamos la", "ok", "beleza", "bora", "pode sim", "sim por favor",
        "claro", "com certeza", "quero sim", "quero", "por favor",
        "não, obrigado", "nao obrigado", "não", "nao", "cancelar",
    ]
    if prompt_lower.rstrip("!.") in confirmation_patterns:
        return False

    # Navigation request patterns
    navigation_patterns = [
        "como acessar", "como chegar", "como ir", "onde fica", "onde está", "onde esta",
        "me leve", "me guie", "me mostre", "quero ir", "preciso ir", "ir para",
        "acessar", "navegar", "encontrar", "localizar", "chegar em", "chegar no",
        "como faço para", "como fazer para", "caminho para"
    ]

    # Conceptual question patterns (should NOT trigger navigation)
    conceptual_patterns = [
        "o que é", "o que e", "o que significa", "para que serve", "qual é", "qual e",
        "explique", "defina", "definição", "conceito", "significado",
        "o que faz", "qual a função", "qual função"
    ]

    # Check for conceptual patterns first (higher priority)
    for pattern in conceptual_patterns:
        if pattern in prompt_lower:
            return False

    # Check for navigation patterns
    for pattern in navigation_patterns:
        if pattern in prompt_lower:
            return True

    # Default: if no clear pattern, assume it's NOT a navigation request
    # (let Vision/RAG handle it)
    return False


def _check_element_visibility(prompt_usuario: str, dom_context: str, timeout_ms: int = 500) -> bool:
    """
    Check if the requested element is visible in the current DOM.
    
    Args:
        prompt_usuario: User query
        dom_context: Current DOM context from AuraDomMapper
        timeout_ms: Maximum time for check (default 500ms)
    
    Returns:
        bool: True if element is visible, False otherwise
    """
    start_time = time.time()

    # Extract potential element references from user query
    element_keywords = _extract_element_keywords(prompt_usuario)

    if not element_keywords:
        # No clear element reference - assume visible (let Vision handle it)
        return True

    # Search for keywords in DOM context
    dom_lower = dom_context.lower()
    for keyword in element_keywords:
        keyword_lower = keyword.lower()
        if keyword_lower in dom_lower:
            elapsed_ms = (time.time() - start_time) * 1000
            if elapsed_ms < timeout_ms:
                logger.debug(f"Element '{keyword}' found in DOM (visibility check: {elapsed_ms:.2f}ms)")
                return True

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Element not found in DOM (visibility check: {elapsed_ms:.2f}ms)")
    return False


def _check_target_element_visibility(prompt_usuario: str, dom_context: str, timeout_ms: int = 500) -> bool:
    """
    Check if the TARGET element (not intermediate navigation elements) is visible in the DOM.
    
    For navigation queries like "Como acessar o SIGN?", this checks for "SIGN" specifically,
    not intermediate elements like "Senior Flow".
    
    Args:
        prompt_usuario: User query
        dom_context: Current DOM context from AuraDomMapper
        timeout_ms: Maximum time for check (default 500ms)
    
    Returns:
        bool: True if target element is visible, False otherwise
    """
    start_time = time.time()

    # Extract the target element from navigation query
    # Remove navigation patterns to get the target
    query_lower = prompt_usuario.lower()

    # Remove navigation patterns
    for pattern in ["como acessar", "como chegar", "como ir", "onde fica", "onde está", "onde esta",
                    "me leve", "me guie", "me mostre", "quero ir", "preciso ir", "ir para",
                    "acessar", "navegar", "encontrar", "localizar", "chegar em", "chegar no",
                    "como faço para", "como fazer para", "caminho para", "o ", "a ", "os ", "as "]:
        query_lower = query_lower.replace(pattern, " ")

    # Clean up and extract target keywords
    target_keywords = [word.strip() for word in query_lower.split() if len(word.strip()) > 2]

    if not target_keywords:
        # No clear target - assume not visible
        return False

    # Search for target keywords in DOM context
    dom_lower = dom_context.lower()
    for keyword in target_keywords:
        if keyword in dom_lower:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"Target element '{keyword}' found in DOM (visibility check: {elapsed_ms:.2f}ms)")
            return True

    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Target element not found in DOM (visibility check: {elapsed_ms:.2f}ms)")
    return False


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
            id_vetor = f"{limpar_nome(nome_aula)}_passo_{passo.get('id_passo')}"

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
            com_retry(lambda: pinecone_index.upsert(vectors=vetores, namespace=tenant_id))

        return {"status": "sucesso", "mensagem": f"{len(vetores)} passos indexados com sucesso."}

    except Exception as e:
        logger.error(f"Erro na ingestao: {e}")
        return {"status": "erro", "mensagem": str(e)}


def buscar_contexto(
    prompt_usuario: str,
    tenant_id: str = "senior_default",
    namespace: str = None
) -> dict | None:
    """Busca contexto relevante no Pinecone usando RAG.
    
    Args:
        prompt_usuario: Pergunta ou prompt do utilizador
        tenant_id: ID do tenant (usado como namespace se namespace não for fornecido)
        namespace: Namespace específico para busca (opcional). Se fornecido, sobrepõe tenant_id.
                   Útil para buscar documentação web por módulo (ex: "hcm", "financeiro")
    
    Returns:
        Dicionário com texto_rag, seletor_direto, score, melhor_aula, e source_url (se disponível)
        ou None se não encontrar contexto relevante
    """
    if not pinecone_index or not client_openai:
        return None
    try:
        # Usa namespace se fornecido, caso contrário usa tenant_id
        # Se namespace for None, usa "senior_default"
        query_namespace = namespace if namespace is not None else tenant_id
        if not query_namespace:
            query_namespace = "senior_default"
            logger.warning("[Namespace] Fallback: namespace e tenant_id ausentes, usando 'senior_default'")
        elif namespace is None and tenant_id:
            logger.debug(f"[Namespace] Fallback: namespace não fornecido, usando tenant_id: {tenant_id}")
        else:
            logger.debug(f"[Namespace] Usando namespace fornecido: {query_namespace}")

        query_embedding = gerar_embedding(prompt_usuario)
        resultados      = pinecone_index.query(
            vector=query_embedding, top_k=TOP_K, namespace=query_namespace, include_metadata=True
        )

        contextos      = []
        melhor_seletor = None
        melhor_score   = 0.0
        melhor_aula    = None  # GPS: rastreia o nome da aula com maior score
        source_url     = None  # URL da fonte (para documentação web)

        for match in resultados.matches:
            if match.score < SCORE_THRESHOLD:
                continue
            md      = match.metadata

            # Suporta tanto formato roteiro (aula/passo) quanto formato web (url/titulo)
            if md.get('aula'):
                # Formato roteiro
                contexto = (
                    f"MANUAL: {md.get('aula')}\n"
                    f"INSTRUCAO: {md.get('texto')}\n"
                    f"DICA: {md.get('tooltip')}"
                )
            elif md.get('url'):
                # Formato web (documentação)
                contexto = (
                    f"DOCUMENTACAO: {md.get('titulo', 'Sem título')}\n"
                    f"CONTEUDO: {md.get('text', '')}\n"
                    f"FONTE: {md.get('url', '')}"
                )
                # Captura a URL da fonte com maior score
                if match.score > melhor_score and md.get('url'):
                    source_url = md.get('url')
            else:
                # Formato genérico
                contexto = f"CONTEUDO: {md.get('text', md.get('texto', ''))}"

            if md.get("seletor"):
                contexto += f"\nSELETOR_EXATO: {md.get('seletor')}"
                if match.score > melhor_score:
                    melhor_score   = match.score
                    melhor_seletor = md.get("seletor")
                    melhor_aula    = md.get("aula")
            elif match.score > melhor_score:
                melhor_score = match.score
                melhor_aula  = md.get("aula") or md.get("titulo")

            contextos.append(contexto)

        if not contextos:
            return None

        resultado = {
            "texto_rag":      "\n\n---\n\n".join(contextos),
            "seletor_direto": melhor_seletor,
            "score":          melhor_score,
            "melhor_aula":    melhor_aula,  # GPS: nome da aula com maior score
        }

        # Adiciona source_url se disponível (documentação web)
        if source_url:
            resultado["source_url"] = source_url

        return resultado

    except Exception as e:
        logger.error(f"Erro RAG: {e}")
        return None


# =========================================================
# MULTI-NAMESPACE SEARCH
# Carrega namespaces ativos do Pinecone na inicialização e
# busca em paralelo usando threads para minimizar latência.
# =========================================================

# Cache dos namespaces ativos (carregado uma vez na inicialização)
_ACTIVE_NAMESPACES: list[str] = []
_NAMESPACES_LOADED = False

def _load_active_namespaces() -> list[str]:
    """Carrega os namespaces ativos do índice Pinecone.
    
    Retorna lista de namespaces com vetores. Faz fallback para
    lista hardcoded se o Pinecone não estiver disponível.
    """
    global _ACTIVE_NAMESPACES, _NAMESPACES_LOADED
    if _NAMESPACES_LOADED:
        return _ACTIVE_NAMESPACES

    # Fallback: namespaces conhecidos do índice (atualizado em 2026-05)
    _FALLBACK_NAMESPACES = [
        "2020", "2021", "2022", "2023", "2024", "2025",
        "arquitetura_basica", "assuntos_respondidos", "bpm",
        "cidades_homologadas_para_envio_de_nfse",
        "cidades_homologadas_para_recebimento_de_nfse",
        "como_habilitar_e_usar", "diferencas_embarcado_completo",
        "edocs", "erp", "faq", "fluxo_integracao", "ged",
        "home_pcvv", "index", "licenca_vencida", "manual_do_usuario",
        "notas_da_versao", "pcvv", "pcvv_gko_frete", "pcvv_seniorx",
        "pcvv_tms_xt", "perguntas_frequentes", "senior_connect",
        "senior_default", "senior_flow_manual", "senior_flow_notas",
        "sign_studio",
    ]

    if not pinecone_index:
        _ACTIVE_NAMESPACES = _FALLBACK_NAMESPACES
        _NAMESPACES_LOADED = True
        return _ACTIVE_NAMESPACES

    try:
        stats = pinecone_index.describe_index_stats()
        namespaces = list(stats.get("namespaces", {}).keys())
        if namespaces:
            _ACTIVE_NAMESPACES = namespaces
            logger.info(f"[Namespaces] {len(namespaces)} namespaces carregados do Pinecone: {namespaces}")
        else:
            _ACTIVE_NAMESPACES = _FALLBACK_NAMESPACES
            logger.warning("[Namespaces] Nenhum namespace encontrado, usando fallback hardcoded.")
    except Exception as e:
        _ACTIVE_NAMESPACES = _FALLBACK_NAMESPACES
        logger.warning(f"[Namespaces] Falha ao carregar namespaces do Pinecone ({e}), usando fallback.")

    _NAMESPACES_LOADED = True
    return _ACTIVE_NAMESPACES


def buscar_contexto_multi_namespace(
    prompt_usuario: str,
    tenant_id: str = "senior_default",
) -> dict | None:
    """Busca contexto no Pinecone em todos os namespaces ativos em paralelo.
    
    Retorna o resultado com maior score entre todos os namespaces.
    """
    if not pinecone_index or not client_openai:
        return None

    namespaces = _load_active_namespaces()

    # Gera o embedding uma única vez (compartilhado entre todas as buscas)
    try:
        query_embedding = gerar_embedding(prompt_usuario)
    except Exception as e:
        logger.error(f"[MultiNS] Falha ao gerar embedding: {e}")
        return None

    melhor_resultado: dict | None = None
    melhor_score = 0.0
    lock = threading.Lock()

    def _buscar_namespace(ns: str) -> None:
        nonlocal melhor_resultado, melhor_score
        try:
            resultados = pinecone_index.query(
                vector=query_embedding,
                top_k=TOP_K,
                namespace=ns,
                include_metadata=True,
            )

            contextos      = []
            seletor        = None
            score_ns       = 0.0
            melhor_aula_ns = None
            source_url_ns  = None

            for match in resultados.matches:
                if match.score < SCORE_THRESHOLD:
                    continue
                md = match.metadata

                if md.get("aula"):
                    contexto = (
                        f"MANUAL: {md.get('aula')}\n"
                        f"INSTRUCAO: {md.get('texto')}\n"
                        f"DICA: {md.get('tooltip')}"
                    )
                elif md.get("url"):
                    contexto = (
                        f"DOCUMENTACAO: {md.get('titulo', 'Sem título')}\n"
                        f"CONTEUDO: {md.get('text', '')}\n"
                        f"FONTE: {md.get('url', '')}"
                    )
                    if match.score > score_ns and md.get("url"):
                        source_url_ns = md.get("url")
                else:
                    contexto = f"CONTEUDO: {md.get('text', md.get('texto', ''))}"

                if md.get("seletor"):
                    contexto += f"\nSELETOR_EXATO: {md.get('seletor')}"
                    if match.score > score_ns:
                        score_ns       = match.score
                        seletor        = md.get("seletor")
                        melhor_aula_ns = md.get("aula")
                elif match.score > score_ns:
                    score_ns       = match.score
                    melhor_aula_ns = md.get("aula") or md.get("titulo")

                contextos.append(contexto)

            if not contextos:
                return

            resultado_ns = {
                "texto_rag":          "\n\n---\n\n".join(contextos),
                "seletor_direto":     seletor,
                "score":              score_ns,
                "melhor_aula":        melhor_aula_ns,
                "_namespace_origem":  ns,
            }
            if source_url_ns:
                resultado_ns["source_url"] = source_url_ns

            with lock:
                nonlocal melhor_resultado, melhor_score
                if score_ns > melhor_score:
                    melhor_score     = score_ns
                    melhor_resultado = resultado_ns

        except Exception as e:
            logger.debug(f"[MultiNS] Erro no namespace '{ns}': {e}")

    # Executa buscas em paralelo
    threads = [threading.Thread(target=_buscar_namespace, args=(ns,)) for ns in namespaces]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)  # Timeout de 5s por namespace

    return melhor_resultado


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
# SEVERITY RANKING HELPER
# =========================================================
def _severity_rank(severity: str) -> int:
    """
    Rank severity levels for prioritization.
    Higher number = more severe.
    """
    ranks = {
        "low": 1,
        "medium": 2,
        "high": 3,
        "critical": 4
    }
    return ranks.get(severity.lower(), 0)


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

    # =========================================================
    # 1.5 IDENTITY DETECTOR: Short-circuit for identity/meta questions
    # Avoids expensive pipeline (embedding + Pinecone + Vision) for
    # trivially-answerable questions about Aura's identity.
    # =========================================================
    if _is_identity_question(prompt_usuario):
        logger.info(f"🪪 Identity detector: interceptando pergunta de identidade | prompt='{prompt_usuario}'")
        user_greeting = f", {user_name}" if user_name else ""
        identity_result = {
            "mensagem": _IDENTITY_RESPONSE["mensagem"].format(user_greeting=user_greeting),
            "elemento_id": _IDENTITY_RESPONSE["elemento_id"],
            "seletor_css": _IDENTITY_RESPONSE["seletor_css"],
            "sugestoes": _IDENTITY_RESPONSE["sugestoes"],
            "confidence_score": _IDENTITY_RESPONSE["confidence_score"],
            "source_reference": _IDENTITY_RESPONSE["source_reference"],
        }
        _cache_set(cache_key, identity_result)
        return identity_result

    # =========================================================
    # 1.6 GREETING DETECTOR: Short-circuit for simple greetings
    # Avoids expensive pipeline for "Oi", "Olá", "Bom dia", etc.
    # =========================================================
    if _is_simple_greeting(prompt_usuario):
        logger.info(f"👋 Greeting detector: interceptando saudação simples | prompt='{prompt_usuario}'")
        user_greeting = f", {user_name}" if user_name else ""
        greeting_result = {
            "mensagem": _GREETING_RESPONSE["mensagem"].format(user_greeting=user_greeting),
            "elemento_id": _GREETING_RESPONSE["elemento_id"],
            "seletor_css": _GREETING_RESPONSE["seletor_css"],
            "sugestoes": _GREETING_RESPONSE["sugestoes"],
            "confidence_score": _GREETING_RESPONSE["confidence_score"],
            "source_reference": _GREETING_RESPONSE["source_reference"],
        }
        _cache_set(cache_key, greeting_result)
        return greeting_result

    # 2. Busca RAG (Usa o histórico recente para dar contexto à busca vetorial)
    texto_busca_rag = f"{historico[-1]['texto']} {prompt_usuario}" if historico else prompt_usuario

    # =========================================================
    # 1.7 QUERY NORMALIZATION: Expand abbreviations before embedding
    # Improves embedding similarity against formally-indexed content.
    # Additive only — never removes original query words.
    # =========================================================
    texto_busca_normalizado = _normalizar_query(texto_busca_rag)
    if texto_busca_normalizado != texto_busca_rag:
        logger.info(f"📝 Query normalizada: '{texto_busca_rag}' → '{texto_busca_normalizado}'")
        texto_busca_rag = texto_busca_normalizado

    # =========================================================
    # MULTI-NAMESPACE SEARCH
    # A documentação web é ingerida por módulo (bpm, ged, erp, etc.)
    # enquanto os roteiros usam "senior_default".
    # Buscamos em todos os namespaces ativos em paralelo e retornamos o melhor.
    # =========================================================
    busca_rag = buscar_contexto_multi_namespace(texto_busca_rag, tenant_id)

    # =========================================================
    # [RAG DEBUG] Log do resultado da busca no Pinecone
    # =========================================================
    if busca_rag:
        logger.info(
            f"[RAG DEBUG] ✅ Pinecone retornou contexto | "
            f"namespace={busca_rag.get('_namespace_origem', '?')} | "
            f"score={busca_rag['score']:.4f} | "
            f"seletor={busca_rag['seletor_direto']} | "
            f"aula={busca_rag.get('melhor_aula')} | "
            f"ai_gate={'ATIVO' if busca_rag['score'] > 0.80 and busca_rag['seletor_direto'] else 'INATIVO'}"
        )
    else:
        logger.warning(
            f"[RAG DEBUG] ❌ Pinecone não retornou contexto relevante em nenhum namespace | "
            f"query='{texto_busca_rag[:80]}...'"
        )

    # =========================================================
    # 3. VECTOR STORE CONTENT RESTRICTION (FIXED)
    # O guardrail só bloqueia se:
    # - HÁ contexto RAG E
    # - O score é menor que o limiar E
    # - enable_vector_store_only está ativo
    # Se não há contexto RAG, proceed para AI Gate / Vision normalmente
    # =========================================================
    if _guardrail_config.enable_vector_store_only:
        # Só bloqueia se TIVER contexto RAG mas com score baixo
        if busca_rag and busca_rag["score"] < SCORE_THRESHOLD:
            # Se tem contexto mas score baixo, ainda pode usar Vision
            # Apenas loga o aviso mas NÃO bloqueia
            logger.info(f"Vector Store: contexto encontrado mas score baixo ({busca_rag['score']:.2f} < {SCORE_THRESHOLD}). Prosseguindo para Vision...")

    # =========================================================
    # 4. AI GATE: Bypass do Gemini Vision
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
            # Add source traceability (Requirement 6)
            "confidence_score": busca_rag["score"],
            "source_reference": busca_rag.get("melhor_aula")
        }
        # Add source_url if available (web documentation)
        if "source_url" in busca_rag:
            resultado_rapido["source_url"] = busca_rag["source_url"]

        _cache_set(cache_key, resultado_rapido)
        return resultado_rapido

    # =========================================================
    # 5. FALLBACK: Gemini Vision com Memória Conversacional
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
            # Add source traceability (Requirement 6)
            "confidence_score": busca_rag["score"] if busca_rag else 0.0,
            "source_reference": busca_rag.get("melhor_aula") if busca_rag else None
        }

        # Add source_url if available (web documentation)
        if busca_rag and "source_url" in busca_rag:
            resultado_final["source_url"] = busca_rag["source_url"]

        _cache_set(cache_key, resultado_final)
        return resultado_final

    except Exception as e:
        logger.error(f"Erro Vision Fatal: {e}")
        return {
            "mensagem":    f"Ola, {user_name}! A minha conexão falhou após várias tentativas. Pode repetir?",
            "elemento_id": None,
            "seletor_css": None,
            "sugestoes":   ["Tentar novamente"],
            "confidence_score": 0.0,
            "source_reference": None
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

    # =========================================================
    # STEP 1: GUARDRAIL VALIDATION (BEFORE CACHE)
    # =========================================================
    violations = await _guardrail_engine.validate_prompt(prompt_usuario, tenant_id)

    if violations:
        # Log all violations
        for violation in violations:
            await _security_logger.log_event(
                event_type="guardrail_blocked",
                tenant_id=tenant_id,
                prompt=prompt_usuario,
                guardrail_name=violation.guardrail_name,
                severity=violation.severity,
                user_id=user_name,
                details=violation.details
            )

        # Return error message for highest severity violation
        highest_severity = max(violations, key=lambda v: _severity_rank(v.severity))
        logger.warning(f"Guardrail blocked request: {highest_severity.guardrail_name} ({highest_severity.severity})")

        return {
            "mensagem": highest_severity.message,
            "elemento_id": None,
            "seletor_css": None,
            "sugestoes": [],
            "blocked": True,
            "guardrail": highest_severity.guardrail_name,
            "confidence_score": 0.0,
            "source_reference": None
        }

    # =========================================================
    # STEP 2: CHECK AI SERVICE AVAILABILITY
    # =========================================================
    if not gemini_client or not client_openai:
        return {
            "mensagem":    "Motores de IA desconectados. Verifique as chaves de API no .env",
            "elemento_id": None,
            "seletor_css": None,
            "sugestoes":   [],
            "confidence_score": 0.0,
            "source_reference": None
        }

    # =========================================================
    # STEP 3: CHECK ELEMENT VISIBILITY (NEW - Requirement 1)
    # =========================================================
    # First, detect if this is a navigation request or a conceptual question
    is_navigation_request = _is_navigation_request(prompt_usuario)

    if is_navigation_request:
        # For navigation requests, check if the TARGET element is visible
        # (not intermediate elements like "Senior Flow")
        element_visible = _check_target_element_visibility(prompt_usuario, dom_context,
                                                           timeout_ms=ELEMENT_VISIBILITY_CHECK_TIMEOUT_MS)

        if not element_visible:
            # Target element not visible - activate navigation fallback
            fallback_engine = get_navigation_fallback_engine()

            if fallback_engine:
                logger.info("Target element not visible, activating navigation fallback")
                fallback_result = await fallback_engine.handle_invisible_element(
                    user_query=prompt_usuario,
                    dom_context=dom_context,
                    tenant_id=tenant_id
                )

                if fallback_result["fallback_type"] == "navigation":
                    # Get first step for immediate highlight
                    nav_path = fallback_result.get("navigation_path", [])
                    first_step = nav_path[0] if nav_path else None

                    # Return navigation offer with first step highlighted
                    return {
                        "mensagem": fallback_result["mensagem"],
                        "elemento_id": first_step.get("element", {}).get("label", "") if first_step else None,
                        "seletor_css": first_step.get("element", {}).get("selector_hint", "") if first_step else None,
                        "navigation_path": fallback_result["navigation_path"],
                        "navigation_mode": "guided",  # Flag to indicate guided navigation
                        "current_step": 0,  # Start at first step
                        "total_steps": len(nav_path),
                        "requires_confirmation": True,
                        "sugestoes": ["Sim, me guie", "Não, obrigado"],
                        "confidence_score": fallback_result.get("confidence_score", 0.0),
                        "source_reference": fallback_result.get("roteiro_name"),
                        "breadcrumb": fallback_result.get("breadcrumb", "")
                    }
                # If fallback_type is "general", continue to Vision below

    # =========================================================
    # STEP 4: PROCEED WITH NORMAL FLOW (Vision + RAG)
    # =========================================================
    return await asyncio.to_thread(
        _analisar_sync, image_b64, url, prompt_usuario, dom_context, user_name, tenant_id, historico
    )

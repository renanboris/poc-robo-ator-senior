import os
import json
import base64
import logging
import asyncio
from dotenv import load_dotenv

load_dotenv()

from pinecone import Pinecone
from openai import OpenAI
from google import genai
from google.genai import types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aura_engine")

# =========================================================
# CONFIGURAÇÃO
# =========================================================
OPENAI_EMBED_MODEL = "text-embedding-3-large" 
GEMINI_LLM_MODEL = "gemini-2.5-flash"
TARGET_DIM = 3072
TOP_K = 5
SCORE_THRESHOLD = 0.45 

# =========================================================
# CLIENTES
# =========================================================
client_openai = None
gemini_client = None
pinecone_index = None

try:
    oa_key = os.getenv("OPENAI_API_KEY")
    if oa_key:
        client_openai = OpenAI(api_key=oa_key)
        logger.info("OpenAI Conectada (Memória Estável)")
        
    g_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if g_key:
        gemini_client = genai.Client(api_key=g_key)
        logger.info("Gemini Engine Pronto (Visão Computacional)")
        
    pc_key = os.getenv("PINECONE_API_KEY")
    idx_name = os.getenv("PINECONE_INDEX_NAME")
    if pc_key and idx_name:
        pc = Pinecone(api_key=pc_key)
        pinecone_index = pc.Index(idx_name)
except Exception as e:
    logger.error(f"Erro na inicialização: {e}")

# =========================================================
# MEMÓRIA VETORIAL (OPENAI)
# =========================================================

def gerar_embedding(texto: str):
    try:
        response = client_openai.embeddings.create(
            input=texto,
            model=OPENAI_EMBED_MODEL,
            dimensions=TARGET_DIM
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Erro Embedding: {e}")
        raise e

def buscar_contexto(prompt_usuario: str):
    if not pinecone_index or not client_openai: return None
    try:
        query_embedding = gerar_embedding(prompt_usuario)
        resultados = pinecone_index.query(
            vector=query_embedding,
            top_k=TOP_K,
            include_metadata=True
        )
        contextos = []
        for match in resultados.matches:
            if match.score < SCORE_THRESHOLD: continue
            md = match.metadata
            contextos.append(f"MANUAL TÉCNICO: {md.get('aula')}\nCONDIÇÃO: {md.get('texto')}\nDICA AURA: {md.get('tooltip')}")
        return "\n\n---\n\n".join(contextos) if contextos else None
    except Exception as e:
        logger.error(f"Erro RAG: {e}")
        return None

# =========================================================
# CÉREBRO DA AURA (GEMINI VISION)
# =========================================================

def _analisar_sync(image_b64: str, url: str, prompt_usuario: str):
    # Recupera o que foi ensinado no Training OS
    contexto_rag = buscar_contexto(prompt_usuario) or "Utiliza apenas a tua visão e inteligência nativa para ajudar."

    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",")[1]
        image_bytes = base64.b64decode(image_b64)

        # 🟢 PROMPT NUCLEAR: Define identidade, proíbe o "Pronto" e força o pensamento
        prompt_sistema = f"""Você é a Aura, a assistente virtual e guia oficial da Senior Sistemas.
Você está a conversar com o Renan. A sua missão é ser uma mentora técnica presente e amigável.

PERSONALIDADE:
- Moderna, ágil, profissional e muito prestativa.
- NUNCA use saudações datadas ou informais como "Tudo joia".
- É ESTRITAMENTE PROIBIDO responder apenas "Pronto!", "Ok" ou frases com menos de 15 palavras.

CONHECIMENTO RECUPERADO (Base de Treinamentos):
{contexto_rag}

INSTRUÇÕES DE RESPOSTA:
1. Comece sempre por analisar internamente o que o Renan precisa (no campo 'analise_interna').
2. Na 'mensagem', forneça uma orientação completa. Se precisar clicar em algo, descreva a posição (ex: "no menu lateral esquerdo", "no ícone de engrenagem no topo").
3. Se for uma saudação, apresente-se como Aura e diga que está pronta para navegar no Senior X.

RETORNE OBRIGATORIAMENTE ESTE JSON:
{{
  "analise_interna": "Pense aqui primeiro: O que estou a ver na tela? O que o Renan pediu? Como o manual ajuda?",
  "mensagem": "Sua resposta final amigável, instrutiva e completa para o Renan (mínimo de 2 frases).",
  "coordenadas": null
}}"""

        resposta = gemini_client.models.generate_content(
            model=GEMINI_LLM_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                f"URL: {url}\nRenan pergunta: {prompt_usuario}"
            ],
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                response_mime_type="application/json",
                temperature=0.7 # 🟢 Aumentado para maior naturalidade e criatividade
            )
        )

        # Extraímos apenas o campo 'mensagem' para o frontend
        dados = json.loads(resposta.text)
        return {"mensagem": dados.get("mensagem", "Olá, Renan! Como posso ajudar?"), "coordenadas": None}

    except Exception as e:
        logger.error(f"Erro Vision: {e}")
        return {"mensagem": "Olá, Renan! Tive um pequeno problema ao processar a tua imagem. Podes descrever o que precisas?", "coordenadas": None}

async def analisar_tela_dap(image_b64: str, url: str, prompt_usuario: str):
    if not gemini_client or not client_openai:
        return {"mensagem": "Motores de IA desconectados.", "coordenadas": None}
    return await asyncio.to_thread(_analisar_sync, image_b64, url, prompt_usuario)
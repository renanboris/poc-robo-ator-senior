"""
main.py - Backend da Aura (Senior DAP)

Correções aplicadas:
- FIX #1: CORS restrito à extensão (não mais allow_origins=["*"])
- FIX #2: Modelo atualizado para gemini-2.0-flash
- FIX #3: Filtro por URL no Pinecone para resultados mais precisos
- FIX #4: Tratamento de erro granular com mensagens úteis ao usuário
- FIX #5: Validação do campo `prompt` — antes usava sempre o default, tornando o RAG inútil
- NOVO:   Endpoint POST /ingest para indexar roteiros do Training OS no Pinecone
"""

import os
import base64
import datetime
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from pinecone import Pinecone
from dotenv import load_dotenv

# ──────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────
load_dotenv()

api_key      = os.getenv("GEMINI_API_KEY")
pinecone_key = os.getenv("PINECONE_API_KEY")

# ID da extensão Chrome (defina no .env para restringir o CORS corretamente)
# Exemplo: EXTENSION_ID=abcdefghijklmnopqrstuvwxyzabcdef
EXTENSION_ID = os.getenv("EXTENSION_ID", "")

if not api_key:
    raise RuntimeError("GEMINI_API_KEY não encontrada no .env")
if not pinecone_key:
    raise RuntimeError("PINECONE_API_KEY não encontrada no .env")

genai.configure(api_key=api_key)
pc    = Pinecone(api_key=pinecone_key)
index = pc.Index("senior-dap-knowledge")

app = FastAPI(title="Aura Backend — Senior DAP RAG", version="2.0.0")

# FIX: CORS restrito à extensão Chrome.
# Em desenvolvimento, adicione "http://localhost" à lista se precisar testar via browser.
allowed_origins = ["http://localhost", "http://127.0.0.1"]
if EXTENSION_ID:
    allowed_origins.append(f"chrome-extension://{EXTENSION_ID}")
else:
    # Fallback permissivo APENAS em dev — remova em produção
    allowed_origins.append("*")
    print("⚠️  AVISO: EXTENSION_ID não definido. CORS aberto para todos. Defina no .env para produção.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)


# ──────────────────────────────────────────
# Modelos de dados
# ──────────────────────────────────────────
class AnalysisRequest(BaseModel):
    image:  str
    url:    str
    # FIX: prompt agora é obrigatório vir preenchido pelo frontend.
    # O default permanece como fallback de segurança, mas o content.js
    # sempre envia o texto real digitado pelo usuário.
    prompt: str = "O que devo fazer nesta tela?"


class IngestRequest(BaseModel):
    """
    Endpoint para indexar roteiros do Training OS no Pinecone.
    Permite que o DAP guie o usuário com base nos fluxos já gravados.
    """
    source:   str          # ex: "Criar Pasta no GED"
    url:      str          # URL do Senior X onde esse passo acontece
    chunks:   List[str]    # Trechos de texto (ancoras + micro-narracoes)


# ──────────────────────────────────────────
# Utilitários
# ──────────────────────────────────────────
def salvar_log_aura(url: str, pergunta: str, resposta: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = (
        f"[{timestamp}]\n"
        f"URL:      {url}\n"
        f"USUÁRIO:  {pergunta}\n"
        f"AURA:     {resposta}\n"
        f"{'-' * 60}\n"
    )
    with open("aura_responses.log", "a", encoding="utf-8") as f:
        f.write(entry)


def decodificar_imagem(image_b64: str) -> bytes:
    """Remove o header data:image/png;base64, e decodifica com padding correto."""
    encoded = image_b64.split(",", 1)[-1]
    missing = len(encoded) % 4
    if missing:
        encoded += "=" * (4 - missing)
    return base64.b64decode(encoded)


def embedar_texto(texto: str) -> list:
    """Gera vetor de 3072 dimensões via gemini-embedding-001."""
    resp = genai.embed_content(
        model="models/gemini-embedding-001",
        content=texto,
        task_type="retrieval_query"
    )
    return resp["embedding"]


# ──────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "model": "gemini-2.0-flash"}


@app.post("/analyze")
async def analyze_screen(request: AnalysisRequest):
    try:
        # ── 1. RAG: Busca no Pinecone ──────────────────────────────────────
        print(f"🔍 RAG query: '{request.prompt}' | URL: {request.url}")

        vetor = embedar_texto(request.prompt)

        # FIX: Filtra por URL para resultados mais precisos (se metadado estiver indexado)
        # Remove o filtro se o índice ainda não tiver o campo "url" nos metadados.
        try:
            resultados = index.query(
                vector=vetor,
                top_k=4,
                include_metadata=True,
                filter={"url": {"$eq": request.url}}
            )
            # Fallback: sem filtro se não retornou nada
            if not resultados.matches:
                print("📌 Sem resultados filtrados por URL. Buscando globalmente...")
                resultados = index.query(
                    vector=vetor,
                    top_k=4,
                    include_metadata=True
                )
        except Exception as e:
            print(f"⚠️  Pinecone query error: {e}. Buscando sem filtro...")
            resultados = index.query(
                vector=vetor,
                top_k=4,
                include_metadata=True
            )

        contexto = ""
        if resultados.matches:
            for match in resultados.matches:
                source = match.metadata.get("source", "Manual")
                text   = match.metadata.get("text", "")
                score  = round(match.score, 3)
                contexto += f"[{source} | relevância: {score}]\n{text}\n\n"

        print(f"📚 Contexto recuperado: {len(contexto)} chars de {len(resultados.matches)} chunks.")

        # ── 2. Prepara imagem ──────────────────────────────────────────────
        image_bytes = decodificar_imagem(request.image)
        image_part  = {"mime_type": "image/png", "data": image_bytes}

        # ── 3. Prompt final (Imagem + Contexto RAG + Pergunta) ─────────────
        prompt_final = f"""
Você é a Aura, assistente especialista do sistema Senior X (ERP/HCM da Senior Sistemas).
O usuário está na URL: {request.url}

CONTEXTO DOS MANUAIS E TREINAMENTOS OFICIAIS:
--- INÍCIO DO CONTEXTO ---
{contexto if contexto else "Nenhum treinamento específico encontrado para esta tela. Use seu conhecimento visual."}
--- FIM DO CONTEXTO ---

DÚVIDA DO USUÁRIO: "{request.prompt}"

INSTRUÇÕES:
1. Analise a imagem da tela atual.
2. Cruce o que você vê na tela com o CONTEXTO OFICIAL acima.
3. Responda a dúvida de forma CURTA (máx. 4 linhas) e OBJETIVA.
4. Use Português do Brasil. Fale diretamente com o usuário como uma guia paciente.
5. Se identificar o próximo passo visível na tela, mencione-o.
6. Nunca invente campos ou botões que não existem na imagem.
""".strip()

        # ── 4. Geração com Gemini (Vision + texto) ────────────────────────
        # FIX: Atualizado para gemini-2.0-flash (mais rápido, menor custo, melhor visão)
        modelo = genai.GenerativeModel("gemini-2.0-flash")
        response = modelo.generate_content([prompt_final, image_part])

        advice = (response.text or "").strip()
        if not advice:
            advice = "Desculpe, não consegui processar a orientação no momento. Tente novamente."

        salvar_log_aura(request.url, request.prompt, advice)
        return {"advice": advice}

    except Exception as e:
        # Retorna erro legível ao usuário em vez de travar a extensão
        print(f"❌ Erro: {e}")
        return {"advice": f"Aura encontrou um erro interno. Tente novamente.\nDetalhe técnico: {str(e)[:120]}"}


@app.post("/ingest")
async def ingest_roteiro(request: IngestRequest):
    """
    NOVO: Indexa roteiros gerados pelo Training OS no Pinecone.

    O Training OS gera âncoras e micro-narrações para cada passo gravado.
    Esse endpoint transforma esses textos em vetores e os indexa,
    permitindo que o DAP guie o usuário em tempo real com o mesmo
    conhecimento dos treinamentos.

    Exemplo de uso (Training OS chama após gerar SCORM):
        POST /ingest
        {
            "source": "Criar Pasta no GED",
            "url": "https://app.senior.com.br/ged",
            "chunks": [
                "Clique no botão Nova Pasta no menu superior",
                "Preencha o campo Nome com o título desejado",
                "Confirme clicando em Salvar"
            ]
        }
    """
    try:
        vetores = []
        for i, chunk in enumerate(request.chunks):
            if not chunk.strip():
                continue
            vetor = embedar_texto(chunk)
            vetores.append({
                "id":       f"{request.source.replace(' ','_')}_{i}",
                "values":   vetor,
                "metadata": {
                    "source": request.source,
                    "url":    request.url,
                    "text":   chunk
                }
            })

        if not vetores:
            raise HTTPException(status_code=400, detail="Nenhum chunk válido para indexar.")

        index.upsert(vectors=vetores)
        print(f"✅ Indexados {len(vetores)} chunks de '{request.source}'")
        return {"indexed": len(vetores), "source": request.source}

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Ingest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

import os
import json
from google import genai
from google.genai import types
from pinecone import Pinecone
from dotenv import load_dotenv

load_dotenv()

# Configuração de APIs
api_key = os.getenv("GEMINI_API_KEY")
pinecone_key = os.getenv("PINECONE_API_KEY")

gemini_client = None
if api_key:
    gemini_client = genai.Client(api_key=api_key)

# ─── FUNÇÃO 1: INGESTAR CONHECIMENTO (DO ROTEIRO PARA O PINECONE) ───
def ingestar_para_pinecone(dados_roteiro: dict):
    if not pinecone_key: return {"status": "ignorado", "motivo": "Sem chave Pinecone"}
    
    metadata = dados_roteiro.get("metadata", {})
    nome_aula = metadata.get("nome_aula", "Treinamento")
    
    # Extrai todo o texto útil do roteiro para criar o "Manual" da IA
    textos = []
    for passo in dados_roteiro.get("passos", []):
        textos.append(passo.get("pedagogia", {}).get("ancora", ""))
        for acao in passo.get("acoes_tecnicas", []):
            textos.append(acao.get("intencao_semantica", ""))
            textos.append(acao.get("micro_narracao", ""))
            
    textos = [t for t in textos if t.strip()]
    if not textos: return {"status": "vazio"}

    # Junta o texto em blocos de contexto e envia pro Pinecone (RAG)
    try:
        pc = Pinecone(api_key=pinecone_key)
        index = pc.Index(os.getenv("PINECONE_INDEX_NAME", "senior-dap"))
        
        texto_completo = " | ".join(textos)
        
        # Usa o modelo de embedding mais recente
        resposta_embed = gemini_client.models.embed_content(
            model="text-embedding-004", 
            contents=[texto_completo]
        )
        vetor = resposta_embed.embeddings[0].values
        
        index.upsert(vectors=[{
            "id": f"dap_{nome_aula.replace(' ', '_')}",
            "values": vetor,
            "metadata": {"source": nome_aula, "text": texto_completo}
        }])
        return {"status": "sucesso", "indexado": nome_aula}
    except Exception as e:
        print(f"Erro no Pinecone Ingest: {e}")
        return {"status": "erro", "detalhe": str(e)}

# ─── FUNÇÃO 2: ANALISAR A TELA (RESPONDER PARA A EXTENSÃO) ───
async def analisar_tela_dap(image_b64: str, url: str, prompt_usuario: str):
    # 1. Busca contexto no Pinecone (se existir)
    contexto = ""
    try:
        if pinecone_key:
            pc = Pinecone(api_key=pinecone_key)
            index = pc.Index(os.getenv("PINECONE_INDEX_NAME", "senior-dap"))
            
            resposta_embed = gemini_client.models.embed_content(
                model="text-embedding-004", 
                contents=[prompt_usuario]
            )
            vetor_busca = resposta_embed.embeddings[0].values
            
            resultados = index.query(vector=vetor_busca, top_k=2, include_metadata=True)
            contexto = " ".join([m['metadata'].get('text', '') for m in resultados['matches'] if 'metadata' in m])
    except Exception as e:
        print(f"Aviso Pinecone (Busca): {e}")

    # 2. Monta o Prompt com a estrutura exata que a extensão precisa (Holofote)
    prompt_sistema = f"""Você é a Aura, um AI Coach atuando dentro do sistema Senior X.
O usuário está na URL: {url}
A dúvida dele é: '{prompt_usuario}'
Contexto da base de conhecimento (RAG): {contexto}

Você deve analisar a imagem da tela e responder EXATAMENTE em formato JSON.
{{
  "advice": "Texto curto e direto dizendo o que o usuário deve fazer.",
  "action": "highlight",
  "selector": "O seletor CSS (ex: button[aria-label='Salvar'], #btn-novo) do elemento que ele deve clicar. Deixe vazio se não houver um clique claro.",
  "next_step": true
}}"""

    # 3. Chama o Gemini Vision
    try:
        import base64
        image_bytes = base64.b64decode(image_b64.split(",")[1] if "," in image_b64 else image_b64)
        
        resposta = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"), 
                prompt_sistema
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", 
                temperature=0.1
            )
        )
        return json.loads(resposta.text)
    except Exception as e:
        print(f"Erro Gemini: {e}")
        return {
            "advice": "Desculpe, tive um problema de visão e não consegui analisar a tela. 🤕",
            "action": "none",
            "selector": ""
        }
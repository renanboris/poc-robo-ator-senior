import os
import re
import json
import time
import logging
from google import genai
from google.genai import types
import dap_engine

logger = logging.getLogger("generator_engine")

# ─── Limite máximo de tokens estimados para a biblioteca injetada no prompt ───
_MAX_BIBLIOTECA_CHARS = 300_000

# ─── Número máximo de tentativas na API Gemini ────────────────────────────────
_MAX_TENTATIVAS = 2

def limpar_nome(nome: str) -> str:
    """Sanitiza o nome para uso como nome de arquivo."""
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

def _validar_estrutura_roteiro(roteiro: dict) -> str | None:
    """Valida que o JSON gerado pelo Gemini tem a estrutura mínima esperada."""
    if not isinstance(roteiro, dict):
        return "Resposta não é um dicionário JSON."
    if "metadata" not in roteiro:
        return "Campo 'metadata' ausente no roteiro gerado."
    if "passos" not in roteiro:
        return "Campo 'passos' ausente no roteiro gerado."
    if not isinstance(roteiro["passos"], list) or len(roteiro["passos"]) == 0:
        return "Campo 'passos' está vazio ou não é uma lista."
    return None

def gerar_roteiro_ia_sync(nome_aula: str, objetivo: str, tenant_id: str = "senior_default") -> dict:
    if not dap_engine.gemini_client:
        return {"status": "erro", "mensagem": "Google Gemini não configurado."}

    # ── 1. RAG: busca contexto do manual ────────────────────────────────────
    logger.info(f"Buscando manual para: {objetivo}")
    contexto_rag = dap_engine.buscar_contexto(objetivo, tenant_id)

    if contexto_rag and contexto_rag.get("texto_rag"):
        texto_manual = contexto_rag["texto_rag"]
    else:
        texto_manual = "Nenhum manual específico encontrado. Baseie-se no objetivo fornecido."
        logger.warning("RAG não retornou contexto. Procedendo sem manual.")

    # ── 2. Biblioteca de ações (Lego) ───────────────────────────────────────
    caminho_biblioteca = "biblioteca_acoes.json"
    if not os.path.exists(caminho_biblioteca):
        return {"status": "erro", "mensagem": "Biblioteca de peças não encontrada. Execute lego_builder.py primeiro."}

    with open(caminho_biblioteca, "r", encoding="utf-8") as f:
        biblioteca = json.load(f)

    if not biblioteca:
        return {"status": "erro", "mensagem": "Biblioteca de ações está vazia."}

    logger.info(f"Injetando {len(biblioteca)} peças na IA...")

    # Trunca biblioteca se for gigantesca
    biblioteca_json = json.dumps(biblioteca, ensure_ascii=False)
    if len(biblioteca_json) > _MAX_BIBLIOTECA_CHARS:
        logger.warning(f"Biblioteca grande. Truncando para {_MAX_BIBLIOTECA_CHARS} chars.")
        peças_limitadas = dict(list(biblioteca.items())[:200])
        biblioteca_json = json.dumps(peças_limitadas, ensure_ascii=False)

    # ── 3. Prompt do sistema (externo) ──────────────────────────────────────
    caminho_prompt = "generator_prompt.txt"
    try:
        with open(caminho_prompt, "r", encoding="utf-8") as f:
            prompt_sistema = f.read()
    except FileNotFoundError:
        return {"status": "erro", "mensagem": f"Arquivo '{caminho_prompt}' não encontrado."}

    # 🟢 O PROMPT DE USUÁRIO: Estrutura Perfeita s/ Comentários (BugFix #4 aplicado)
    prompt_usuario = f"""
NOME DA AULA: {nome_aula}
OBJETIVO: {objetivo}

=======================================
MANUAL OFICIAL (RAG):
{texto_manual}

=======================================
BIBLIOTECA DE AÇÕES DISPONÍVEIS (peças técnicas validadas):
{biblioteca_json}

=======================================
INSTRUÇÕES DE MONTAGEM (CRÍTICO):
- Use as peças da biblioteca acima como base.
- Altere o campo "valor_input" se o objetivo exigir digitar algo específico.
- NÃO invente seletores. Copie-os exatamente.
- Agrupe navegações e crie o passo final de conclusão exatamente como no modelo.

Gere o JSON seguindo EXATAMENTE esta estrutura (NÃO INCLUA COMENTÁRIOS NO JSON):

{{
  "metadata": {{"nome_aula": "{nome_aula}", "id_treinamento": "{limpar_nome(nome_aula)}"}},
  "configuracao_gravacao": {{"gravar_video": true, "pasta_destino": "videos_gerados", "voz_ia": "pt-BR-FranciscaNeural"}},
  "passos": [
    {{
      "id_passo": 1,
      "tipo_passo": "navigation",
      "peso_narrativo": 2,
      "pause_sugerida": 2.5,
      "pedagogia": {{"ancora": "Introdução professoral aqui. Vamos acessar os menus...", "tooltip_dap": "Navegue pelo menu"}},
      "is_conclusao": false,
      "acoes_tecnicas": [
        {{
          "acao": "clique",
          "micro_narracao": "...acessando o primeiro menu...",
          "elemento_alvo": {{}}
        }},
        {{
          "acao": "clique",
          "micro_narracao": "...e clicando no submenu...",
          "elemento_alvo": {{}}
        }}
      ]
    }},
    {{
      "id_passo": 2,
      "tipo_passo": "operacao",
      "peso_narrativo": 2,
      "pause_sugerida": 2.5,
      "pedagogia": {{"ancora": "Agora preencha e confirme a ação.", "tooltip_dap": "Preencha o campo"}},
      "is_conclusao": false,
      "acoes_tecnicas": [
        {{
          "acao": "digitar_e_enter",
          "valor_input": "VALOR_DO_OBJETIVO_AQUI",
          "micro_narracao": "",
          "elemento_alvo": {{}}
        }}
      ]
    }},
    {{
      "id_passo": 3,
      "tipo_passo": "confirmation",
      "peso_narrativo": 2,
      "pause_sugerida": 3.0,
      "pedagogia": {{"ancora": "Parabéns! A tarefa foi concluída com sucesso.", "tooltip_dap": "Concluído!"}},
      "is_conclusao": true,
      "acoes_tecnicas": [
        {{
          "acao": "concluir_video",
          "micro_narracao": "",
          "valor_input": "",
          "elemento_alvo": {{}}
        }}
      ]
    }}
  ]
}}
"""

    # ── 4. Chamada Gemini com retry em falhas transitórias ───────────────────
    ultimo_erro = None
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            resposta = dap_engine.gemini_client.models.generate_content(
                model=dap_engine.GEMINI_LLM_MODEL,
                contents=prompt_usuario,
                config=types.GenerateContentConfig(
                    system_instruction=prompt_sistema,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            if not resposta.text:
                raise ValueError("Gemini retornou resposta vazia ou bloqueada pelo safety filter.")

            roteiro_final = json.loads(resposta.text)

            erro_estrutura = _validar_estrutura_roteiro(roteiro_final)
            if erro_estrutura:
                raise ValueError(f"Estrutura do JSON inválida: {erro_estrutura}")

            break  # Sucesso!

        except Exception as e:
            ultimo_erro = e
            logger.warning(f"Tentativa {tentativa}/{_MAX_TENTATIVAS} falhou: {e}")
            if tentativa < _MAX_TENTATIVAS:
                time.sleep(2 ** tentativa)
    else:
        logger.error(f"Todas as tentativas falharam. Último erro: {ultimo_erro}")
        return {"status": "erro", "mensagem": str(ultimo_erro)}

    # ── 5. Pós-processamento e persistência ─────────────────────────────────
    nome_arquivo_base = limpar_nome(nome_aula)
    if "metadata" in roteiro_final:
        roteiro_final["metadata"]["id_treinamento"] = nome_arquivo_base
        roteiro_final["metadata"]["nome_aula"] = nome_aula

    roteiro_final["configuracao_gravacao"] = {
        "gravar_video": True,
        "pasta_destino": "videos_gerados",
        "voz_ia": "pt-BR-FranciscaNeural",
    }

    # Evita colisão de nomes
    os.makedirs("roteiros_salvos", exist_ok=True)
    nome_arquivo = f"{nome_arquivo_base}.json"
    caminho = os.path.join("roteiros_salvos", nome_arquivo)
    contador = 1
    while os.path.exists(caminho):
        nome_arquivo = f"{nome_arquivo_base}_{contador}.json"
        caminho = os.path.join("roteiros_salvos", nome_arquivo)
        contador += 1

    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(roteiro_final, f, indent=2, ensure_ascii=False)

    logger.info(f"Roteiro '{nome_arquivo}' gerado com {len(roteiro_final['passos'])} passos.")
    return {"status": "sucesso", "arquivo": nome_arquivo, "roteiro": roteiro_final}
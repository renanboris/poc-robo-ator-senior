import os
import re
import json
import time
import logging
from google import genai
from google.genai import types
import dap_engine
from utils import limpar_nome, validar_roteiro

logger = logging.getLogger("generator_engine")

# ─── Limite máximo de tokens estimados para a biblioteca injetada no prompt ───
_MAX_BIBLIOTECA_CHARS = 300_000

# ─── Número máximo de tentativas na API Gemini ────────────────────────────────
_MAX_TENTATIVAS = 2


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
        texto_manual = "Nenhum manual específico encontrado. Baseie-se no objetivo fornecido para deduzir o fluxo padrão de ERP."
        logger.warning("RAG não retornou contexto. Procedendo de forma autônoma.")

    # ── 2. Biblioteca de ações (Lego) ───────────────────────────────────────
    caminho_biblioteca = "biblioteca_acoes.json"
    biblioteca = {}
    if os.path.exists(caminho_biblioteca):
        with open(caminho_biblioteca, "r", encoding="utf-8") as f:
            biblioteca = json.load(f)

    logger.info(f"Injetando {len(biblioteca)} peças mapeadas na IA...")

    # Trunca biblioteca se for gigantesca
    biblioteca_json = json.dumps(biblioteca, ensure_ascii=False)
    if len(biblioteca_json) > _MAX_BIBLIOTECA_CHARS:
        logger.warning(f"Biblioteca grande. Truncando para {_MAX_BIBLIOTECA_CHARS} chars.")
        peças_limitadas = dict(list(biblioteca.items())[:200])
        biblioteca_json = json.dumps(peças_limitadas, ensure_ascii=False)

# 🟢 O PROMPT DE USUÁRIO: Estrutura Profunda com Validação de Estado (Agentic UI)
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
- Use as peças da biblioteca acima como base. NUNCA invente seletores HTML no "elemento_alvo".
- Altere o campo "valor_input" se o objetivo exigir digitar algo específico.
- Se a ação não existir na biblioteca, crie com o "elemento_alvo" VAZIO ({{}}).
- OBRIGATÓRIO: Crie o bloco "validacao_esperada" para cada ação técnica, prevendo o resultado visual na tela.

Gere o JSON seguindo EXATAMENTE esta estrutura (NÃO INCLUA COMENTÁRIOS NO JSON):

{{
  "metadata": {{
    "nome_aula": "{nome_aula}", 
    "id_treinamento": "{limpar_nome(nome_aula)}",
    "gerado_por_ia": true,
    "validado_hitl": false
  }},
  "configuracao_gravacao": {{
    "gravar_video": true, 
    "pasta_destino": "videos_gerados", 
    "voz_ia": "pt-BR-FranciscaNeural"
  }},
  "passos": [
    {{
      "id_passo": 1,
      "tipo_passo": "navigation",
      "peso_narrativo": 2,
      "pause_sugerida": 2.5,
      "pedagogia": {{"ancora": "Introdução professoral explicando o POR QUÊ...", "tooltip_dap": "Navegue pelo menu"}},
      "is_conclusao": false,
      "acoes_tecnicas": [
        {{
          "acao": "clique",
          "micro_narracao": "Explicação do COMO (ex: Clique no menu X...)",
          "elemento_alvo": {{
             "label_curto": "COPIADO DA BIBLIOTECA",
             "seletor_hint": "COPIADO DA BIBLIOTECA",
             "iframe_hint": "COPIADO DA BIBLIOTECA"
          }},
          "validacao_esperada": {{
             "tipo": "elemento_visivel",
             "alvo": "text='Título da Próxima Tela' ou '.toast-success'"
          }}
        }}
      ]
    }},
    {{
      "id_passo": 2,
      "tipo_passo": "confirmation",
      "peso_narrativo": 3,
      "pause_sugerida": 3.0,
      "pedagogia": {{"ancora": "Parabéns! A tarefa foi concluída.", "tooltip_dap": "Concluído!"}},
      "is_conclusao": true,
    "acoes_tecnicas": [
        {{
          "acao": "clique",
          "micro_narracao": "...acessando o primeiro menu...",
          "elemento_alvo": {{}},
          "validacao_esperada": {{
            "tipo": "estado_visual",
            "alvo": "O que deve acontecer na tela"
          }}
        }}
      ]
    }}
  ]
}}
"""
    # ── 4. Chamada Gemini ───────────────────
    ultimo_erro = None
    for tentativa in range(1, _MAX_TENTATIVAS + 1):
        try:
            # Não dependemos mais do arquivo .txt externo para o System Prompt, 
            # a instrução completa e atômica já está no prompt_usuario, garantindo força total.
            resposta = dap_engine.gemini_client.models.generate_content(
                model=dap_engine.GEMINI_LLM_MODEL,
                contents=prompt_usuario,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )

            if not resposta.text:
                raise ValueError("Gemini retornou resposta vazia.")

            roteiro_final = json.loads(resposta.text)

            erro_estrutura = _validar_estrutura_roteiro(roteiro_final)
            if erro_estrutura:
                raise ValueError(f"Estrutura do JSON inválida: {erro_estrutura}")

            break

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
    
    # Previne quebra se a IA esquecer campos críticos da raiz
    roteiro_final.setdefault("metadata", {})
    roteiro_final["metadata"]["id_treinamento"] = nome_arquivo_base
    roteiro_final["metadata"]["nome_aula"] = nome_aula
    roteiro_final["metadata"]["gerado_por_ia"] = True
    roteiro_final["metadata"]["validado_hitl"] = False

    roteiro_final.setdefault("configuracao_gravacao", {})
    roteiro_final["configuracao_gravacao"]["gravar_video"] = True
    roteiro_final["configuracao_gravacao"]["pasta_destino"] = "videos_gerados"
    roteiro_final["configuracao_gravacao"]["voz_ia"] = "pt-BR-FranciscaNeural"

    # Força a criação da conclusão no último passo se a IA não tiver feito
    if roteiro_final["passos"] and not roteiro_final["passos"][-1].get("is_conclusao", False):
         roteiro_final["passos"][-1]["is_conclusao"] = True
         roteiro_final["passos"][-1]["acoes_tecnicas"].append({
             "acao": "concluir_video",
             "micro_narracao": ""
         })

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

    # ── Portão de qualidade semântico (não bloqueia o retorno) ──────────────
    aprovado, motivo_qualidade = validar_roteiro(roteiro_final)
    if not aprovado:
        logger.warning(
            f"[Generator] Portão de qualidade: REPROVADO — {motivo_qualidade}. "
            f"Roteiro salvo em '{caminho}' para revisão manual."
        )
    # ────────────────────────────────────────────────────────────────────────

    return {"status": "sucesso", "arquivo": nome_arquivo, "roteiro": roteiro_final}
import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
gemini_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

def reprocessar_json(caminho_arquivo):
    if not os.path.exists(caminho_arquivo):
        print(f"❌ Erro: Arquivo '{caminho_arquivo}' não encontrado.")
        return

    with open(caminho_arquivo, 'r', encoding='utf-8') as f:
        roteiro_antigo = json.load(f)

    nome_aula = roteiro_antigo.get("metadata", {}).get("nome_aula", "Aula Reprocessada")

    print(f"\n📦 Lendo o arquivo: {nome_aula}")

    # 1. Reconstruir o log de ações brutas a partir do roteiro antigo
    log_mapeador = []
    id_acao_count = 1

    for passo in roteiro_antigo.get("passos", []):
        for acao in passo.get("acoes_tecnicas", []):
            if acao.get("acao") == "concluir_video":
                continue
            log_mapeador.append({
                "id_acao": id_acao_count,
                "acao": acao.get("acao"),
                "intencao_semantica": acao.get("intencao_semantica", ""),
                "elemento_alvo": acao.get("elemento_alvo", {}),
                "valor_input": acao.get("valor_input", "")
            })
            id_acao_count += 1

    print(f"🔄 Encontradas {len(log_mapeador)} ações brutas. Acordando a nova Aura V2...")

    # 2. Ler o novo Prompt
    try:
        with open("aura_prompt.txt", "r", encoding="utf-8") as f:
            prompt_sistema = f.read()
    except FileNotFoundError:
        print("❌ Arquivo 'aura_prompt.txt' não encontrado na raiz!")
        return

    # 3. Preparar a lista para a IA (Ocultando os screenshots gigantes para economizar tokens)
    lista_para_ia = []
    for a in log_mapeador:
        alvo_sem_foto = {k: v for k, v in a["elemento_alvo"].items() if k != "screenshot_referencia"}
        lista_para_ia.append({
            "id_acao": a["id_acao"],
            "acao": a["acao"],
            "intencao_semantica": a["intencao_semantica"],
            "elemento_alvo_resumido": alvo_sem_foto,
            "valor_input": a["valor_input"]
        })

    prompt_usuario = f"AULA: {nome_aula}\nOBJETIVO: Reprocessamento de aula existente com novo Cognitive Load Tiering.\nCONTEXTO MANUAL: Nenhum.\nAÇÕES CAPTURADAS:\n{json.dumps(lista_para_ia, indent=2, ensure_ascii=False)}"

    # 4. Chamar a IA
    try:
        resposta = gemini_client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt_usuario,
            config=types.GenerateContentConfig(
                system_instruction=prompt_sistema,
                response_mime_type="application/json",
                temperature=0.2
            )
        )
        dados_da_ia = json.loads(resposta.text)
    except Exception as e:
        print(f"❌ Erro ao chamar a IA: {e}")
        return

    # 5. Costurar a resposta da IA com os screenshots originais do JSON antigo
    roteiro_final = {
        "metadata": roteiro_antigo.get("metadata", {}),
        "configuracao_gravacao": roteiro_antigo.get("configuracao_gravacao", {
            "gravar_video": True,
            "pasta_destino": "videos_gerados",
            "voz_ia": "pt-BR-FranciscaNeural"
        }),
        "passos": []
    }

    for passo_ia in dados_da_ia.get("passos", []):
        passo_mesclado = {
            "id_passo": passo_ia.get("id_passo"),
            "tipo_passo": passo_ia.get("tipo_passo", "operacao"),
            "peso_narrativo": passo_ia.get("peso_narrativo", 2),
            "pause_sugerida": passo_ia.get("pause_sugerida", 2.5),
            "pedagogia": passo_ia.get("pedagogia", {"ancora": "", "tooltip_dap": ""}),
            "alerta_instrutor": passo_ia.get("alerta_instrutor", None),
            "is_conclusao": passo_ia.get("is_conclusao", False),
            "acoes_tecnicas": []
        }
        micro_narracoes = passo_ia.get("micro_narracoes", [])

        for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):
            acao_bruta = next((item for item in log_mapeador if item["id_acao"] == id_tec), None)
            if acao_bruta:
                passo_mesclado["acoes_tecnicas"].append({
                    "acao": acao_bruta["acao"],
                    "intencao_semantica": acao_bruta["intencao_semantica"],
                    "elemento_alvo": acao_bruta["elemento_alvo"], # 🟢 Traz o screenshot de volta!
                    "valor_input": acao_bruta["valor_input"],
                    "micro_narracao": micro_narracoes[i] if i < len(micro_narracoes) else ""
                })

        if passo_mesclado["is_conclusao"]:
            passo_mesclado["acoes_tecnicas"].append({"acao": "concluir_video"})

        roteiro_final["passos"].append(passo_mesclado)

    # 6. Salvar (Criando backup por segurança)
    backup_path = caminho_arquivo.replace(".json", "_backup.json")
    os.rename(caminho_arquivo, backup_path)

    with open(caminho_arquivo, 'w', encoding='utf-8') as f:
        json.dump(roteiro_final, f, indent=2, ensure_ascii=False)

    print("✨ MÁGICA FEITA! O Roteiro foi atualizado com pesos e pausas dinâmicas.")
    print(f"✅ Salvo em: {caminho_arquivo}")
    print(f"ℹ️ O seu arquivo original está a salvo em: {backup_path}\n")

if __name__ == "__main__":
    import sys
    arquivo = sys.argv[1] if len(sys.argv) > 1 else input("Digite o caminho do arquivo JSON (ex: roteiros_salvos/minha_aula.json):\n> ")
    reprocessar_json(arquivo)

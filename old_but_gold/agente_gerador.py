import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# Configura a chave da API do Gemini (Adicione GEMINI_API_KEY no seu .env)
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def gerar_roteiro_inteligente(objetivo_aula, log_mapeador):
    print("🧠 Acordando a Diretora de Cena (Aura)...")
    
    # O SEGREDO DO SAAS: Forçar a saída estritamente em JSON
    configuracao = {
        "response_mime_type": "application/json",
        "temperature": 0.2 # Temperatura baixa para garantir precisão técnica e evitar alucinações
    }

    # A ENGENHARIA DE PROMPT (System Instruction)
    prompt_sistema = """
    Você é a Aura, a Agente de Inteligência Artificial Especialista em Design Instrucional da Blaze Code.
    Sua missão é receber anotações brutas de instrutores e transformá-las em um arquivo JSON estrito que alimentará um motor de automação Playwright.

    REGRAS DE OURO PARA A NARRAÇÃO (narracao_ia):
    1. NUNCA use o imperativo (ex: "Clique aqui", "Faça isso"). O aluno está assistindo a um vídeo passivo.
    2. USE SEMPRE a primeira pessoa do plural (nós) com tom descritivo e profissional de Universidade Corporativa.
       - Errado: "Clique no menu Documentos."
       - Certo: "Em seguida, nós acessamos a área de Documentos."
       - Errado: "Digite o nome e dê enter."
       - Certo: "Agora, nós digitamos o nome do arquivo na barra de busca e pressionamos Enter."
    3. Explique o PORQUÊ da ação baseando-se no contexto geral do objetivo da aula.

    REGRAS DE MAPEAMENTO DE AÇÕES (acao):
    - Se o instrutor disser para clicar, use "clique".
    - Se for um duplo clique para abrir pastas/arquivos, use "duplo_clique".
    - Se for botão direito, use "clique_direito".
    - Se for para digitar algo e dar enter, use "digitar_e_enter" e crie a chave "valor_input" no passo.
    - Se for apenas para esperar a tela carregar, use "aguardar_carregamento".

    ESTRUTURA OBRIGATÓRIA DO JSON:
    O JSON deve seguir exatamente este formato. O último passo DEVE SEMPRE ser a ação "concluir_video" com uma mensagem de encerramento amigável.

    {
      "metadata": {
        "id_treinamento": "GERADO_AUTOMATICAMENTE",
        "titulo": "TÍTULO BASEADO NO OBJETIVO",
        "modulo": "Senior Flow"
      },
      "configuracao_gravacao": {
        "gravar_video": true,
        "pasta_destino": "videos_gerados",
        "voz_ia": "pt-BR-FranciscaNeural"
      },
      "passos": [
        {
          "id_passo": 1,
          "acao": "clique",
          "alvo_semantico": { ... },
          "narracao_ia": "..."
        }
      ]
    }
    """

    # Montando a mensagem do usuário (O que o Instrutor colou na interface)
    prompt_usuario = f"""
    OBJETIVO DA AULA:
    {objetivo_aula}

    CLIQUES MAPEADOS (NA ORDEM):
    {log_mapeador}
    """

    print("⚙️ Processando a didática e os seletores DOM...")
    
    # Inicializando o modelo com a instrução de sistema
    modelo = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=prompt_sistema,
        generation_config=configuracao
    )

    # Chamada para a IA
    resposta = modelo.generate_content(prompt_usuario)
    
    # Salvando o resultado impecável no roteiro.json
    caminho_saida = "roteiro.json"
    with open(caminho_saida, 'w', encoding='utf-8') as f:
        f.write(resposta.text)

    print(f"\n✅ MÁGICA CONCLUÍDA! O arquivo '{caminho_saida}' foi gerado perfeitamente.")
    print("O seu motor main.py já pode ser executado.")

# ==========================================
# SIMULANDO A INTERFACE WEB DO INSTRUTOR
# ==========================================
if __name__ == "__main__":
    
    # 1. O que o instrutor escreveria no campo de "Objetivo"
    input_objetivo = "Quero ensinar o usuário a excluir um documento chamado 'Relatório de Férias' no GED."
    
    # 2. O que o instrutor colaria do terminal do nosso mapeador.py
    input_mapeador = """
    1. Clicar no menu principal:
    {"seletor": "[id='menu-label-Senior Flow']", "pegar_pai": true}
    
    2. Clicar no módulo GED:
    {"seletor": "span", "com_texto": "GED", "primeiro": true, "pegar_pai": true}
    
    3. Clicar na área Documentos:
    {"seletor": "span", "com_texto": "Documentos", "primeiro": true, "pegar_pai": true}
    
    4. Clicar com o botão direito em cima do arquivo na tabela:
    {"seletor": "#itemTitle", "texto_esperado": "Relatório de Férias", "primeiro": true}
    
    5. No menu suspenso, clicar em Excluir:
    {"seletor": "span", "texto_esperado": "Excluir", "pegar_pai": true}
    """
    
    # Aciona a Aura
    gerar_roteiro_inteligente(input_objetivo, input_mapeador)
import asyncio
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent

# Cortando a telemetria do browser-use
os.environ["ANONYMIZED_TELEMETRY"] = "false"
os.environ["BROWSER_USE_TELEMETRY"] = "false"

# Carrega as variáveis do .env
load_dotenv()

# ---------------------------------------------------------
# A NOSSA CLASSE BLINDADA (Versão OpenAI)
# Estendemos o ChatOpenAI para entregar o "provider" que o 
# browser-use exige e blindamos contra os erros do Pydantic.
# ---------------------------------------------------------
class OpenAIParaBrowserUse(ChatOpenAI):
    @property
    def provider(self):
        return "openai"

    # Escudo Anti-Pydantic: ignora bloqueios de injeção dinâmica
    def __setattr__(self, name, value):
        try:
            super().__setattr__(name, value)
        except ValueError:
            object.__setattr__(self, name, value)

async def main():
    # 1. Puxa as credenciais do .env
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    # Trava de segurança caso falte algo no .env
    if not usuario or not senha:
        print("❌ ERRO: Por favor, defina SENIOR_USER e SENIOR_PASS no seu arquivo .env")
        return

    # 2. A JOGADA DE MESTRE: Instanciamos a NOSSA classe compatível
    chave_google = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    llm = OpenAIParaBrowserUse(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=chave_google,
        model="gemini-2.0-flash", 
    )
    
    # 3. O Roteiro Dinâmico (injetando o usuário e a senha)
    roteiro = f"""
    Você está automatizando o portal da Senior X. Siga os passos rigorosamente:
    1. Acesse a URL: 'https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/'
    2. Aguarde a página carregar completamente.
    3. Encontre o campo de 'Usuário' (ou e-mail) e digite o valor: '{usuario}'
    4. Se houver um botão de 'Avançar' ou 'Continuar' para revelar a senha, clique nele. Caso os campos de usuário e senha estejam na mesma tela, pule este passo.
    5. Encontre o campo de 'Senha' e digite o valor: '{senha}'
    6. Encontre o botão de 'Entrar', 'Autenticar' ou 'Login' e clique nele.
    7. Aguarde o carregamento da tela inicial do sistema (dashboard principal).
    8. Olhe para o menu lateral esquerdo, procure pelo item 'Senior Flow' e clique nele.
    9. Pare a execução para eu avaliar.
    """
    
    agent = Agent(
        task=roteiro,
        llm=llm,
    )
    
    print("🎬 Ação! O robô está assumindo o controle com suas credenciais...")
    
    result = await agent.run()
    
    print("\n✅ Corte! Cena finalizada.")
    print("Resumo:", result)

if __name__ == "__main__":
    asyncio.run(main())
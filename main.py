import asyncio
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent, Browser, BrowserConfig

# 1. Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

async def main():
    # Inicializa o cérebro do agente
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash") 
    
    # 2. Roteiro Direto ao Ponto (Sem passos de login)
    roteiro = """
    1. Acesse a URL 'https://homologacao.senior.com.br/seniorx/ged' (ajuste para a URL exata do módulo).
    2. Aguarde o carregamento da tela principal de Documentos.
    3. Localize o botão azul chamado 'Nova Pasta' no topo da tela e clique nele.
    4. Digite 'Treinamento Onboarding PoC' no campo de nome da pasta.
    5. Clique no botão de Salvar.
    6. Aguarde 3 segundos na tela para finalizar a gravação.
    """
    
    # 3. O Pulo do Gato: Configurando o Chrome para manter a sessão (Login persistente)
    # Definimos um diretório local para o Playwright salvar os cookies de sessão.
    # Se a pasta não existir, ele cria. Se existir, ele usa os dados salvos.
    caminho_sessao = os.path.join(os.getcwd(), "sessao_chrome_senior")

    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
            # Comando extra do Playwright para usar um perfil de usuário persistente
            extra_chromium_args=[f"--user-data-dir={caminho_sessao}"] 
        )
    )
    
    agent = Agent(
        task=roteiro,
        llm=llm,
        browser=browser,
    )
    
    print("🎬 Gravando! O robô está assumindo o controle...")
    
    result = await agent.run()
    
    print("\n✅ Corte! Cena finalizada.")
    print("Resumo da execução:", result)

    await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
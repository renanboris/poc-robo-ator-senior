# GenUCS - Automação Inteligente Senior X 🤖

Este projeto é um Agente de IA capaz de navegar de forma autônoma pelo portal **Senior X**, realizar login e navegar até o módulo de Documentos do GED via Senior Flow. 

Desenvolvido para a **Senior Sistemas**, o projeto utiliza o framework `browser-use` com o modelo **Gemini 2.0 Flash** da Google.

## 🛠️ Desafios Técnicos Superados

Durante o desenvolvimento, implementamos soluções avançadas para contornar limitações de bibliotecas em estado *bleeding edge*:

- **Bypass de Pydantic V2:** Implementação de herança de classe (`OpenAIParaBrowserUse`) para permitir injeção dinâmica de atributos exigidos pelo `browser-use` que são nativamente bloqueados pelo Pydantic.
- **Gemini 2.0 OpenAI Compatibility:** Uso do endpoint de compatibilidade da OpenAI para mitigar o erro de estruturação de JSON (`items` vs `action`) comum na integração direta do Gemini com Langchain.
- **Gestão de Telemetria:** Desativação forçada de telemetria via variáveis de ambiente para evitar conflitos de performance e privacidade.

## 🚀 Como Rodar o Projeto

### 1. Pré-requisitos
- Python 3.11+ (Testado com sucesso no 3.13)
- Google Gemini API Key

### 2. Instalação
Clone o repositório e configure o ambiente virtual:
```powershell
# Criar ambiente virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar dependências
pip install browser-use langchain-openai python-dotenv playwright
playwright install

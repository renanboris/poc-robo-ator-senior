# 🎓 Senior Sistemas - Training OS (Auto Training Generator)

Um motor avançado de Inteligência Artificial para a Universidade Corporativa da Senior Sistemas. 
Este sistema transforma o conhecimento tácito de um instrutor em treinamentos corporativos completos (Vídeo, Áudio, Legendas e JSON Universal para DAP) de forma 100% automatizada.



## 🚀 Como Funciona (A Arquitetura)

O **Training OS** foi construído com a filosofia de *Self-Documenting Software* e está dividido em 4 módulos principais:

1. **Capture Engine (O Mapeador):** Usa Playwright e um Radar JS injetado ("Raio-X") para capturar cliques, inputs e interações do instrutor no Senior X, contornando elementos invisíveis e IDs dinâmicos.
2. **Intent Engine (Aura IA + Pinecone RAG):** O motor de Design Instrucional. Analisa o log bruto, consulta a documentação técnica da Senior num Banco Vetorial (Pinecone) e agrupa ações num **Universal Lesson JSON**.
3. **Playback Engine (Estúdio ao Vivo):** Recria as ações no navegador aplicando um "Holofote" corporativo (`#009999`), injeta legendas nativas no HTML e toca a narração gerada (Edge-TTS + Pygame) em tempo real.
4. **Render Engine (Ilha de Edição):** Usa o MoviePy para aplicar a tesoura (cortar tempo de login), aplicar a moldura (`overlay.png`), mixar trilha sonora (`trilha.mp3`) e concatenar o Lottie final (`outro.mp4`).

## 🛠️ Configuração do Ambiente (Setup)

### Pré-requisitos
- Python 3.10+ instalado.
- Chaves de API do Google Gemini (`google-genai`) e Pinecone.

### Instalação Passo a Passo
1. Clone o repositório:
   ```bash
   git clone https://github.com/renanboris/poc-robo-ator-senior.git
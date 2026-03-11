# 🎓 Senior Training OS & Aura DAP

**Um ecossistema completo de autoria de treinamentos corporativos guiado por Inteligência Artificial, construído nativamente para o Senior X.**

---

## 🚀 A Revolução na Criação de Conhecimento

Criar treinamentos de software tradicionais é um processo exaustivo. Gravar a tela, editar vídeos, roteirizar, narrar, exportar para LMS e documentar em PDF costuma levar cerca de **6 horas para cada aula de 5 minutos**. Pior ainda: quando a interface do sistema atualiza, todo esse material é perdido.

O **Senior Training OS** inova ao inverter essa lógica. Você não "edita" um treinamento; você **ensina a máquina uma única vez**. 

**⏱️ O Benchmark:** De **6 horas** de trabalho manual para **15 minutos** de processamento automatizado.

### 🎯 Os 4 Pilares de Saída (Outputs)
A partir de um único mapeamento feito pelo Especialista, o sistema gera automaticamente:
1. **🎬 Vídeo Narrado (MP4):** Captura em alta fidelidade com cursor humanizado e narração neural (TTS) perfeitamente sincronizada com o *Cognitive Load Tiering*.
2. **🕹️ Simulador SCORM (ZIP):** Um player interativo HTML/JS com navegação livre, permitindo que o usuário "clique" na tela simulada antes de usar o sistema real.
3. **📔 Digital Playbook (PDF):** Documentação técnica formatada como E-book, contendo os *screenshots*, as áreas de clique mapeadas e o passo a passo escrito.
4. **🤖 Coach IA / DAP (Pinecone RAG):** O mesmo roteiro que gera os vídeos alimenta o banco vetorial da **Aura**. Quando o usuário acessa o Senior X e tem dúvidas, a extensão da Aura injeta *tooltips* e dicas visuais na tela em tempo real.

---

## 🧠 Arquitetura do Sistema (Engines Independentes)

A separação de responsabilidades permite que o sistema escale sem gargalos:

```text
[ Especialista usa o Senior X ] ──> [ capture.py ] ──> (Log Técnico de Intenções)
                                          │
                                          ▼
                                 [ Aura (Gemini) ] ──> (Roteiro Pedagógico JSON)
                                          │
       ┌──────────────────────┬───────────┴─────────┬─────────────────────┐
       ▼                      ▼                     ▼                     ▼
  [ main.py ]         [ scorm_builder.py ]  [ pdf_builder.py ]    [ dap_engine.py ]
 (Vídeo & Áudio)      (Simulador SCORM)     (E-book PDF)         (Pinecone Vetorial)
       │                      │                     │                     │
       ▼                      ▼                     ▼                     ▼
 [ Render MP4 ]         [ LMS Export ]        [ Confluence ]       [ Aura Extension ]

 ⚙️ Módulos Principais
app.py: O coração do sistema. Backend FastAPI assíncrono que serve o Dashboard Web, faz a gestão de concorrência e o ciclo de vida dos processos (com proteção Anti-Zombie).

capture.py: O "Olho". Injeta um radar DOM no navegador para capturar coordenadas exatas, metadados HTML e screenshots da ação do usuário.

vision_engine.py: O "Localizador". Utiliza estratégias de Self-Healing com 6 camadas de fallback (Selectors > Aria > Text > Gemini Vision) para garantir que o robô encontre o botão mesmo que o frontend do Senior X sofra alterações.

cursor_engine.py: O "Ator". Aplica matemática de curvas de Bézier Cúbicas para simular o movimento humano do rato (Overshoot, Jitter, Desvio), impedindo que o vídeo pareça mecânico.

Aura Prompt: O "Designer Instrucional". Aplica a teoria de aprendizagem Cognitive Load Tiering (Sweller, 1988). A inteligência decide o "peso" de cada ação (1, 2 ou 3) e calibra o nível de detalhes narrados e o tempo de pausa do robô automaticamente.

🛡️ Segurança e Resiliência (Enterprise-Grade)
Desenvolvido para ambientes corporativos, o Training OS inclui:

Zero-Touch Self-Healing: O banco de dados local (brain.db) constrói uma "memória muscular" da interface. Se um botão mudar de XPath, a IA visualiza o novo ecrã e corrige o clique automaticamente, registrando a correção para o futuro.

Contratos Pydantic Estritos: Cada passo, intenção e coordenada é rigorosamente validado antes de ser persistido.

Higiene de Dados: Nenhuma credencial ou base local é commitada no repositório. O conhecimento vetorial fica segregado e seguro no Pinecone corporativo.

🛠️ Como Iniciar
Instalação das Dependências:

Bash
pip install -r requirements.txt
playwright install
Configuração de Variáveis (.env):
Configure as chaves da API (Gemini, Pinecone) e credenciais de acesso padrão no ficheiro .env.

Iniciar o Training OS:

Bash
python app.py
Acesse o Dashboard interativo em http://localhost:8000.
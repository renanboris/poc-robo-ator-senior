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

## 🌐 Web Knowledge Ingestion Pipeline (RAG)

O **Web Knowledge Ingestion Pipeline** é um sistema ETL automatizado que extrai, transforma e injeta conteúdo de documentação web no Pinecone, alimentando o sistema Aura DAP com conhecimento estruturado e pesquisável.

### Funcionalidades Principais

- **Descoberta Automática**: Extrai URLs de documentação a partir de sitemap.xml
- **Extração Semântica**: Converte páginas HTML em Markdown limpo, preservando estrutura
- **Segregação por Namespace**: Organiza vetores por módulo (HCM, Financeiro, etc.) para recuperação com escopo
- **Modo Incremental**: Pula URLs com conteúdo inalterado usando cache local
- **Resiliência**: Retry com backoff exponencial, continua processamento mesmo com falhas individuais

### Pipeline de 5 Estágios

1. **Discovery**: Busca e analisa sitemap.xml, filtra URLs de documentação
2. **Extraction**: Extrai conteúdo semântico limpo como Markdown
3. **Validation**: Valida qualidade do conteúdo (comprimento, cabeçalhos, densidade de links)
4. **Chunking**: Divide conteúdo em chunks semânticos (~800 tokens, 100 tokens de sobreposição)
5. **Embedding**: Gera embeddings usando OpenAI text-embedding-3-large (3072 dims)
6. **Injection**: Faz upsert de vetores no Pinecone com segregação por namespace

### Integração com Aura DAP

O pipeline integra-se perfeitamente com o motor Aura DAP existente:

```python
from dap_engine import buscar_contexto

# Buscar em namespace específico (módulo HCM)
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default",
    namespace="hcm"  # Novo parâmetro opcional
)
```

### 🎯 Detecção Automática de Namespace (RAG)

O sistema agora detecta automaticamente o namespace (módulo) correto para queries RAG, melhorando significativamente a precisão da recuperação de documentação específica de módulos.

#### Como Funciona

A detecção segue uma ordem de prioridade:

1. **URL** → Extrai `nivel_2` da URL (ex: `/senior-x/hcm/admissao` → `"hcm"`)
2. **Metadata** → Busca em campos do roteiro (`module`, `source_url`, `nome_aula`)
3. **Keywords** → Matching case-insensitive com mapeamento configurável
4. **Fallback** → Usa `tenant_id` se nenhum namespace for detectado

#### Exemplos de Uso

```python
from namespace_detector import detectar_namespace

# Detecção por URL
contexto = {"url": "https://docs.senior.com.br/senior-x/hcm/admissao"}
namespace = detectar_namespace(contexto)  # Retorna: "hcm"

# Detecção por keywords no objetivo
contexto = {"objetivo": "Criar admissão no HCM"}
namespace = detectar_namespace(contexto)  # Retorna: "hcm"

# Detecção por metadata
contexto = {"metadata": {"module": "financeiro"}}
namespace = detectar_namespace(contexto)  # Retorna: "financeiro"

# Integração automática com buscar_contexto
from dap_engine import buscar_contexto

# O namespace é detectado automaticamente em generator_engine.py e capture.py
resultado = buscar_contexto(objetivo, tenant_id, namespace=namespace_detectado)
```

#### Configuração de Keywords

O mapeamento de keywords para namespaces pode ser customizado via:

1. **Arquivo JSON** (prioridade 1): `namespace_keywords.json`
2. **Variável de ambiente** (prioridade 2): `NAMESPACE_KEYWORDS`
3. **Defaults hardcoded** (fallback): Mapeamento interno com 5+ módulos

Exemplo de `namespace_keywords.json`:

```json
{
  "hcm": [
    "recursos humanos", "admissao", "admissão", "folha", "folha de pagamento",
    "rh", "colaborador", "funcionario", "funcionário", "ponto", "ferias", "férias"
  ],
  "financeiro": [
    "contas a pagar", "contas a receber", "tesouraria", "financas", "finanças",
    "pagamento", "recebimento", "faturamento", "nota fiscal", "boleto"
  ],
  "ged": [
    "documentos", "arquivos", "pastas", "ged", "gestao documental",
    "gestão documental", "documento eletronico", "documento eletrônico"
  ]
}
```

#### Performance

- ⚡ **< 10ms** de tempo de detecção (média: 0.34ms)
- 🔄 **Cache automático** de configuração
- 🚫 **Sem chamadas externas** (API, DB)
- ✅ **100% retrocompatível** - sistema funciona sem namespace hints

#### Troubleshooting

**Namespace não detectado:**
- Verifique se o objetivo/URL contém keywords mapeadas
- Adicione keywords customizadas em `namespace_keywords.json`
- Verifique logs: `[Namespace] Não detectado em nenhuma fonte, fallback para tenant_id`

**Performance lenta:**
- Verifique se o cache está funcionando (segunda chamada deve ser mais rápida)
- Verifique se não há chamadas externas bloqueantes

**Namespace incorreto:**
- Revise o mapeamento de keywords em `namespace_keywords.json`
- Verifique a ordem de prioridade (URL > metadata > keywords)
- Adicione logging DEBUG para ver qual fonte foi usada

### Uso Rápido

```bash
# Processar sitemap completo
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml

# Modo incremental (pula URLs inalteradas)
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental

# Listar namespaces
python -m ingestion_pipeline --list-namespaces

# Deletar namespace
python -m ingestion_pipeline --delete-namespace hcm
```

### Documentação Completa

Para detalhes completos sobre instalação, configuração, arquitetura e uso avançado, consulte:

- **[ingestion_pipeline/README.md](ingestion_pipeline/README.md)**: Guia de instalação e uso
- **[ingestion_pipeline/ARCHITECTURE.md](ingestion_pipeline/ARCHITECTURE.md)**: Arquitetura e design técnico

---

## 📦 Releases e Changelog

### Versão Atual: v1.0.0-consolidation (2026-04-29)

Esta release marca um milestone importante na evolução do Training OS, consolidando múltiplas features críticas:

- ✅ **Repo Security Hardening & CI Setup**
- ✅ **Web Knowledge Ingestion Pipeline (RAG)** completo
- ✅ **Aura DAP Redesign** com chat panel v2
- ✅ **Consolidação de Captura Cognitiva**
- ✅ **25+ Specs Documentados** em `.kiro/specs/`
- ✅ **50+ Novos Testes** implementados
- ✅ **Roadmaps Completos**: Training OS, Market-Driven, Playback Resilience

Para detalhes completos sobre mudanças, correções e melhorias, consulte o **[CHANGELOG.md](CHANGELOG.md)**.

---

## 🛠️ Como Iniciar

### Instalação das Dependências:

```bash
pip install -r requirements.txt
playwright install
```

### Configuração de Variáveis (.env):
Configure as chaves da API (Gemini, Pinecone, OpenAI) e credenciais de acesso padrão no ficheiro .env.

### Iniciar o Training OS:

```bash
python app.py
```

Acesse o Dashboard interativo em http://localhost:8000.
# Web Knowledge Ingestion Pipeline

Pipeline automatizado de ETL para extrair, transformar e injetar conteúdo de documentação web no Pinecone, alimentando o sistema Aura DAP com conhecimento estruturado e pesquisável.

## Visão Geral

O Web Knowledge Ingestion Pipeline substitui o fluxo manual de leitura de PDFs por um motor automatizado de extração web que:

- Descobre URLs de documentação a partir de sitemap.xml
- Extrai conteúdo semântico limpo convertido para Markdown
- Estrutura dados com hierarquia breadcrumb
- Injeta vetores no Pinecone segregados por namespaces
- Permite recuperação com escopo de módulo durante interações Aura DAP

## Instalação

### 1. Dependências Python

```bash
# Instalar dependências do pipeline
pip install -r ingestion_pipeline/requirements.txt
```

### 2. Backend de Extração

Escolha um dos backends de extração:

#### Opção A: Crawl4AI (Recomendado - Auto-hospedado, sem custos de API)

```bash
# Instalar Crawl4AI
pip install crawl4ai

# Instalar Playwright (necessário para Crawl4AI)
playwright install chromium
```

#### Opção B: Firecrawl (Alternativa - Serviço gerenciado, pago por uso)

```bash
# Instalar cliente Firecrawl
pip install firecrawl-py

# Obter chave API em https://firecrawl.dev
```

## Configuração

### Variáveis de Ambiente

Crie ou atualize o arquivo `.env` na raiz do projeto:

```bash
# OpenAI (obrigatório)
OPENAI_API_KEY=sk-...

# Pinecone (obrigatório)
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=senior-training-os

# Backend de Extração (escolha um)
# Opção 1: Crawl4AI (auto-hospedado)
CRAWL4AI_BACKEND=playwright  # ou "selenium"
CRAWL4AI_HEADLESS=true

# Opção 2: Firecrawl (serviço gerenciado)
FIRECRAWL_API_KEY=fc-...
```

### Decisão: Índice Separado ou Compartilhado?

**OPÇÃO 1 - Índice Separado (RECOMENDADO para testes):**

✅ **Vantagens:**
- Protege dados de produção durante testes
- Permite experimentação sem riscos
- Fácil de deletar e recriar

❌ **Desvantagens:**
- Custo adicional de índice Pinecone (~$70/mês por índice)
- Requer migração posterior para produção

**Como configurar:**
```bash
# 1. Criar novo índice no Pinecone Console
#    Nome: senior-training-os-rag-test
#    Dimensões: 3072
#    Métrica: cosine

# 2. Configurar no .env
PINECONE_INDEX_NAME=senior-training-os-rag-test
```

**OPÇÃO 2 - Mesmo Índice (RECOMENDADO para produção):**

✅ **Vantagens:**
- Sem custo adicional
- Segregação por namespace (ex: "hcm", "financeiro")
- Não interfere com vetores existentes

❌ **Desvantagens:**
- Requer cuidado ao testar (use --module para limitar escopo)
- Vetores de teste ficam misturados (mas isolados por namespace)

**Como configurar:**
```bash
# Usar o índice existente
PINECONE_INDEX_NAME=senior-training-os

# IMPORTANTE: Sempre teste com --module primeiro!
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm
```

**Nossa Recomendação:**
1. **Fase de Teste**: Use índice separado ou --module com índice compartilhado
2. **Produção**: Use índice compartilhado com namespaces

### Validação da Configuração

```bash
# Verificar se todas as variáveis obrigatórias estão configuradas
python -m ingestion_pipeline --list-namespaces
```

## Uso

### 🚀 Guia Rápido para Primeiro Teste

**RECOMENDADO**: Antes de processar toda a documentação, siga o [Guia Rápido (QUICKSTART.md)](ingestion_pipeline/QUICKSTART.md) para fazer um teste seguro com um módulo específico.

```bash
# Teste rápido com módulo HCM (5-10 minutos)
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm
```

### Teste Inicial Recomendado (Módulo Único)

**IMPORTANTE**: Para validar o pipeline antes de processar toda a documentação, recomendamos começar com um módulo específico:

```bash
# Processar apenas o módulo HCM (recomendado para primeiro teste)
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm

# Verificar os vetores criados
python -m ingestion_pipeline --list-namespaces
```

Isso permite:
- ✅ Validar a qualidade da extração
- ✅ Testar a integração com Aura DAP
- ✅ Economizar processamento e custos de API
- ✅ Iterar rapidamente se ajustes forem necessários

### Uso Básico

```bash
# Processar sitemap completo
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml
```

### Modo Incremental

Pula URLs com conteúdo inalterado usando cache local:

```bash
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental
```

O modo incremental:
- Calcula hash SHA-256 do conteúdo Markdown
- Compara com cache local (`.ingestion_cache.json`)
- Pula processamento se o hash corresponder
- Atualiza cache após processamento bem-sucedido

### Modo Dry-Run

Simula operações sem fazer upsert no Pinecone:

```bash
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --dry-run
```

### Especificar Backend de Extração

```bash
# Usar Firecrawl em vez de Crawl4AI
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --backend firecrawl
```

### Filtrar por Módulo Específico

```bash
# Processar apenas URLs do módulo HCM
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm

# Processar apenas URLs do módulo Financeiro
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module financeiro

# Combinar com modo incremental
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm --incremental
```

O filtro de módulo:
- Extrai o `nivel_2` de cada URL (ex: `/senior-x/hcm/admissao` → `hcm`)
- Processa apenas URLs que correspondem ao módulo especificado
- Reduz drasticamente o tempo de processamento e custos de API
- Ideal para testes e validação incremental por módulo

### Gerenciamento de Namespaces

#### Listar Namespaces

```bash
python -m ingestion_pipeline --list-namespaces
```

Saída:
```
Pinecone Namespaces
============================================================
Index: senior-training-os
Total vectors: 15,234

Namespaces:
------------------------------------------------------------
  hcm                            3,456 vectors
  financeiro                     2,789 vectors
  senior_default                 9,089 vectors
============================================================
```

#### Deletar Namespace

```bash
# Deletar todos os vetores em um namespace (com confirmação)
python -m ingestion_pipeline --delete-namespace hcm
```

Será solicitada confirmação antes da exclusão:
```
Namespace: hcm
Vectors: 3,456

WARNING: This will permanently delete all vectors in this namespace!
Type 'yes' to confirm deletion: 
```

## Arquitetura do Pipeline

O pipeline executa 5 estágios sequenciais:

1. **Discovery**: Busca e analisa sitemap.xml, extrai URLs de documentação
2. **Extraction**: Busca páginas HTML, extrai conteúdo semântico como Markdown
3. **Validation**: Valida qualidade do conteúdo (comprimento mínimo, presença de cabeçalhos)
4. **Chunking**: Divide conteúdo em chunks semânticos (~800 tokens, 100 tokens de sobreposição)
5. **Embedding**: Gera embeddings vetoriais usando OpenAI text-embedding-3-large
6. **Injection**: Faz upsert de vetores no Pinecone com segregação por namespace

Para detalhes arquiteturais completos, consulte [ARCHITECTURE.md](./ARCHITECTURE.md).

## Integração com Aura DAP

O pipeline integra-se com o motor Aura DAP existente (`dap_engine.py`) através de:

### Namespace Segregation

Vetores são segregados por namespace derivado do campo `nivel_2` (nome do módulo):

- URL: `https://docs.senior.com.br/senior-x/hcm/admissao`
- Namespace: `hcm`

### Recuperação com Escopo de Módulo

```python
from dap_engine import buscar_contexto

# Buscar em namespace específico (módulo HCM)
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default",
    namespace="hcm"  # Novo parâmetro opcional
)

# Buscar em namespace padrão (comportamento existente)
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default"
)
```

### Formato de Metadados

Vetores de documentação web incluem metadados estruturados:

```python
{
    "url": "https://docs.senior.com.br/senior-x/hcm/admissao",
    "nivel_1": "senior-x",      # Produto/plataforma
    "nivel_2": "hcm",            # Módulo (usado para namespace)
    "titulo": "Admissão de Colaborador",
    "text": "Conteúdo do chunk..."
}
```

O campo `source_url` é incluído na resposta de `buscar_contexto()` quando disponível.

## Tratamento de Erros

O pipeline é projetado para resiliência:

### Estratégia de Retry

Todas as chamadas de API externas usam retry com backoff exponencial:
- Tentativas máximas: 3
- Delays: 1s, 2s, 4s
- Aplica-se a: OpenAI, Pinecone, buscas HTTP

### Erros Transitórios (retry)
- Timeouts de rede
- Limites de taxa de API (429)
- Indisponibilidade temporária de serviço (503)

### Erros Permanentes (pular e continuar)
- URL inválida (404)
- Conteúdo malformado
- Falha na validação de conteúdo
- Erros de parsing

### Erros Fatais (abortar pipeline)
- Variáveis de ambiente obrigatórias ausentes
- Nome de índice Pinecone inválido
- Falhas de autenticação (401, 403)

## Gerenciamento de Cache

### Estrutura do Cache

O modo incremental usa `.ingestion_cache.json`:

```json
{
  "https://docs.senior.com.br/senior-x/hcm/admissao": {
    "content_hash": "a1b2c3d4e5f6...",
    "last_updated": "2024-01-15T10:30:00Z",
    "vector_count": 12
  }
}
```

### Invalidação de Cache

```bash
# Manual: deletar arquivo de cache para forçar re-ingestão completa
rm .ingestion_cache.json

# Automático: entradas de cache com mais de 30 dias são ignoradas
```

## Monitoramento e Logs

### Níveis de Log

- **INFO**: Progresso do pipeline, transições de estágio
- **WARNING**: Erros recuperáveis, falhas de validação
- **ERROR**: Falhas de processamento, erros de API

### Relatório de Resumo

Após a execução, o pipeline imprime um relatório detalhado:

```
============================================================
PIPELINE EXECUTION SUMMARY
============================================================

⏱️  Timing:
   Start: 2024-01-15 10:00:00
   End:   2024-01-15 10:18:23
   Duration: 1103.45 seconds

✅ Stage Metrics:
   URLs Discovered:      487
   URLs Fetched:         485
   URLs Validated:       478
   Chunks Created:       5,234
   Embeddings Generated: 5,234
   Vectors Injected:     5,234

❌ Failure Counts:
   Failed Fetches:       2
   Failed Validations:   7
   Failed Embeddings:    0
   Failed Upserts:       0
   Skipped Low Quality:  7

📊 Success Rate: 98.2%
============================================================
```

## Considerações de Performance

### Gargalos

1. **Extração de Conteúdo**: Estágio mais lento (I/O de rede, parsing HTML)
2. **Geração de Embeddings**: Limites de taxa de API (3000 requisições/minuto para OpenAI)
3. **Upsert Pinecone**: Tamanho de lote e latência de rede

### Estratégias de Otimização

1. **Extração Paralela**: Processa múltiplas URLs concorrentemente (ThreadPoolExecutor, máx 10 workers)
2. **Embedding em Lote**: Gera embeddings em lotes de 100 chunks
3. **Upsert em Lote**: Faz upsert de vetores em lotes de 100 no Pinecone
4. **Modo Incremental**: Pula URLs inalteradas usando cache de hash de conteúdo

### Performance Esperada

Para sitemap típico da documentação Senior com ~500 URLs:

- Discovery: ~5 segundos
- Extraction: ~10 minutos (paralelo, 10 workers)
- Chunking: ~30 segundos
- Embedding: ~5 minutos (em lote)
- Injection: ~2 minutos (em lote)
- **Total**: ~18 minutos

## Solução de Problemas

### Erro: "Missing required environment variables"

```bash
# Verificar se .env existe e contém as chaves necessárias
cat .env | grep -E "OPENAI_API_KEY|PINECONE_API_KEY|PINECONE_INDEX_NAME"
```

### Erro: "Failed to connect to Pinecone index"

```bash
# Verificar nome do índice
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('PINECONE_INDEX_NAME'))"

# Verificar se o índice existe no console Pinecone
```

### Erro: "Crawl4AI not found"

```bash
# Instalar Crawl4AI e Playwright
pip install crawl4ai
playwright install chromium
```

### Baixa Taxa de Sucesso (<80%)

1. Verificar logs para padrões de falha
2. Verificar regras de filtragem de URL
3. Verificar regras de validação de conteúdo
4. Considerar ajustar limites de validação em `validator.py`

## Exemplos

### Exemplo 1: Teste Inicial com Módulo Único

```bash
# PASSO 1: Processar apenas módulo HCM (teste seguro)
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm

# PASSO 2: Verificar namespaces criados
python -m ingestion_pipeline --list-namespaces

# PASSO 3: Testar recuperação no Aura DAP
# (usar interface web ou API com namespace="hcm")

# PASSO 4: Se satisfeito, processar outros módulos
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module financeiro
```

### Exemplo 2: Ingestão Inicial Completa

```bash
# Primeira execução: processar todo o sitemap
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml

# Verificar namespaces criados
python -m ingestion_pipeline --list-namespaces
```

### Exemplo 3: Atualizações Incrementais Diárias

```bash
# Executar diariamente via cron
0 2 * * * cd /path/to/project && python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental
```

### Exemplo 4: Re-ingestão de Módulo Específico

```bash
# Deletar namespace existente
python -m ingestion_pipeline --delete-namespace hcm

# Re-ingerir (URLs HCM serão reprocessadas)
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental
```

## Suporte

Para problemas ou dúvidas:

1. Verificar logs de execução do pipeline
2. Consultar [ARCHITECTURE.md](./ARCHITECTURE.md) para detalhes de design
3. Verificar documentação do Pinecone: https://docs.pinecone.io
4. Verificar documentação do OpenAI: https://platform.openai.com/docs

## Licença

Este módulo faz parte do Senior Training OS e está sujeito aos mesmos termos de licença do projeto principal.

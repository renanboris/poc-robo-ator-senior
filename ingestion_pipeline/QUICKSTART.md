# Guia Rápido: Primeiro Teste do Pipeline RAG

Este guia mostra como fazer o primeiro teste do pipeline de forma segura e econômica.

## 🎯 Objetivo

Validar o pipeline processando **apenas um módulo** (ex: HCM) antes de processar toda a documentação.

## ⚙️ Pré-requisitos

1. **Dependências instaladas:**
```bash
pip install -r ingestion_pipeline/requirements.txt
pip install crawl4ai
playwright install chromium
```

2. **Variáveis de ambiente configuradas** (`.env`):
```bash
OPENAI_API_KEY=sk-...
PINECONE_API_KEY=...
PINECONE_INDEX_NAME=senior-training-os  # ou índice de teste
```

## 🚀 Passo a Passo

### 1. Validar Configuração

```bash
# Verificar se as variáveis estão configuradas
python -m ingestion_pipeline --list-namespaces
```

**Saída esperada:**
```
Pinecone Namespaces
============================================================
Index: senior-training-os
Total vectors: X,XXX

Namespaces:
------------------------------------------------------------
  senior_default                 X,XXX vectors
============================================================
```

### 2. Processar Módulo de Teste (HCM)

```bash
# Processar apenas URLs do módulo HCM
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm
```

**O que acontece:**
- ✅ Descobre todas as URLs do sitemap
- ✅ Filtra apenas URLs com `/hcm/` no caminho
- ✅ Extrai conteúdo → Markdown
- ✅ Cria chunks semânticos
- ✅ Gera embeddings (OpenAI)
- ✅ Injeta vetores no namespace `hcm`

**Tempo estimado:** 5-10 minutos (dependendo do número de páginas HCM)

**Saída esperada:**
```
Web Knowledge Ingestion Pipeline
============================================================
Sitemap URL: https://docs.senior.com.br/sitemap.xml
Backend: crawl4ai
Incremental: False
Dry-run: False
Module filter: hcm
============================================================

Starting pipeline execution...

[INFO] Stage: discovery - Starting
[INFO] Stage: discovery - Completed (487 items in 5.23s)
[INFO] Module filter applied: 45 URLs match module 'hcm'
[INFO] Processing URL: https://docs.senior.com.br/senior-x/hcm/admissao
...

============================================================
PIPELINE EXECUTION SUMMARY
============================================================

⏱️  Timing:
   Start: 2024-01-15 10:00:00
   End:   2024-01-15 10:08:23
   Duration: 503.45 seconds

✅ Stage Metrics:
   URLs Discovered:      487
   URLs Fetched:         45
   URLs Validated:       43
   Chunks Created:       234
   Embeddings Generated: 234
   Vectors Injected:     234

❌ Failure Counts:
   Failed Fetches:       0
   Failed Validations:   2
   Failed Embeddings:    0
   Failed Upserts:       0
   Skipped Low Quality:  2

🔍 Module Filter:
   URLs Skipped (Filter): 442

📊 Success Rate: 95.6%
============================================================
```

### 3. Verificar Vetores Criados

```bash
# Listar namespaces
python -m ingestion_pipeline --list-namespaces
```

**Saída esperada:**
```
Pinecone Namespaces
============================================================
Index: senior-training-os
Total vectors: X,XXX

Namespaces:
------------------------------------------------------------
  hcm                              234 vectors  ← NOVO!
  senior_default                 X,XXX vectors
============================================================
```

### 4. Testar Recuperação no Aura DAP

**Opção A: Via código Python**
```python
from dap_engine import buscar_contexto

# Buscar apenas no namespace HCM
resultado = buscar_contexto(
    prompt_usuario="Como admitir um colaborador?",
    tenant_id="senior_default",
    namespace="hcm"  # Filtra apenas vetores HCM
)

print(resultado["resposta"])
print(resultado["contexto_usado"])
```

**Opção B: Via interface web**
- Abrir dashboard do Training OS
- Usar Aura DAP com contexto de módulo HCM
- Fazer perguntas sobre admissão, férias, etc.

### 5. Validar Qualidade

**Checklist de validação:**
- [ ] Vetores foram criados no namespace correto (`hcm`)
- [ ] Aura DAP retorna respostas relevantes sobre HCM
- [ ] Respostas incluem URLs de origem (`source_url`)
- [ ] Conteúdo extraído está limpo (sem menus/rodapés)
- [ ] Hierarquia de breadcrumbs está correta

### 6. Próximos Passos

**Se o teste foi satisfatório:**

```bash
# Opção A: Processar outros módulos individualmente
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module financeiro
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module folha

# Opção B: Processar toda a documentação
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml
```

**Se precisa ajustar:**

```bash
# Deletar namespace de teste
python -m ingestion_pipeline --delete-namespace hcm

# Ajustar configurações (validator.py, chunker.py, etc.)
# Rodar novamente
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --module hcm
```

## 🔍 Troubleshooting

### Erro: "Missing required environment variables"
```bash
# Verificar .env
cat .env | grep -E "OPENAI_API_KEY|PINECONE_API_KEY|PINECONE_INDEX_NAME"
```

### Erro: "Failed to connect to Pinecone index"
```bash
# Verificar nome do índice
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('PINECONE_INDEX_NAME'))"
```

### Erro: "Crawl4AI not found"
```bash
pip install crawl4ai
playwright install chromium
```

### Taxa de sucesso baixa (<80%)
1. Verificar logs para padrões de falha
2. Ajustar regras de validação em `validator.py`
3. Verificar se URLs estão acessíveis

## 💡 Dicas

1. **Use --module para todos os testes iniciais** - economiza tempo e dinheiro
2. **Monitore os logs** - eles mostram cada URL sendo processada
3. **Valide a qualidade antes de escalar** - processe 1 módulo → valide → escale
4. **Use modo incremental em produção** - `--incremental` pula URLs inalteradas
5. **Considere índice separado para testes** - protege dados de produção

## 📊 Custos Estimados

**Teste com módulo HCM (~45 URLs, ~234 chunks):**
- OpenAI Embeddings: ~$0.01 (234 chunks × 3072 dims)
- Pinecone Storage: incluído no plano
- **Total: ~$0.01**

**Documentação completa (~500 URLs, ~5000 chunks):**
- OpenAI Embeddings: ~$0.10
- Pinecone Storage: incluído no plano
- **Total: ~$0.10**

## ✅ Checklist Final

Antes de processar toda a documentação:

- [ ] Teste com --module funcionou
- [ ] Aura DAP retorna respostas de qualidade
- [ ] Metadados (url, nivel_1, nivel_2) estão corretos
- [ ] Conteúdo Markdown está limpo
- [ ] Namespaces estão segregados corretamente
- [ ] Decisão tomada: índice separado ou compartilhado
- [ ] Estratégia de atualização definida (incremental, cron, etc.)

## 🎉 Pronto!

Agora você pode processar toda a documentação com confiança:

```bash
python -m ingestion_pipeline https://docs.senior.com.br/sitemap.xml --incremental
```

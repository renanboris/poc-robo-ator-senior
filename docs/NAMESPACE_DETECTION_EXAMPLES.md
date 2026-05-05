# Exemplos de Uso: Detecção Automática de Namespace

Este documento fornece exemplos práticos de como usar a detecção automática de namespace no Senior Training OS.

## 📚 Índice

1. [Uso Básico](#uso-básico)
2. [Integração com Generator Engine](#integração-com-generator-engine)
3. [Integração com Capture Engine](#integração-com-capture-engine)
4. [Customização de Keywords](#customização-de-keywords)
5. [Debugging e Logging](#debugging-e-logging)
6. [Casos de Uso Avançados](#casos-de-uso-avançados)

---

## Uso Básico

### Exemplo 1: Detecção por URL

```python
from namespace_detector import detectar_namespace

# URL de documentação do módulo HCM
contexto = {
    "url": "https://documentation.senior.com.br/senior-x/hcm/admissao"
}

namespace = detectar_namespace(contexto)
print(f"Namespace detectado: {namespace}")  # Output: hcm
```

### Exemplo 2: Detecção por Keywords no Objetivo

```python
from namespace_detector import detectar_namespace

# Objetivo com keywords do módulo Financeiro
contexto = {
    "objetivo": "Configurar contas a pagar no sistema"
}

namespace = detectar_namespace(contexto)
print(f"Namespace detectado: {namespace}")  # Output: financeiro
```

### Exemplo 3: Detecção por Metadata

```python
from namespace_detector import detectar_namespace

# Metadata com campo module explícito
contexto = {
    "metadata": {
        "module": "ged",
        "nome_aula": "Gerenciamento de Documentos"
    }
}

namespace = detectar_namespace(contexto)
print(f"Namespace detectado: {namespace}")  # Output: ged
```

### Exemplo 4: Fallback quando não detectado

```python
from namespace_detector import detectar_namespace

# Contexto sem hints de namespace
contexto = {
    "objetivo": "Realizar operação genérica"
}

namespace = detectar_namespace(contexto)
print(f"Namespace detectado: {namespace}")  # Output: None (fallback para tenant_id)
```

---

## Integração com Generator Engine

O `generator_engine.py` usa detecção automática ao gerar roteiros:

```python
# Em generator_engine.py (já integrado)

from namespace_detector import detectar_namespace
import dap_engine

def gerar_roteiro_ia_sync(nome_aula: str, objetivo: str, tenant_id: str = "senior_default"):
    # Detecta namespace do objetivo
    contexto_deteccao = {"objetivo": objetivo}
    namespace_detectado = detectar_namespace(contexto_deteccao)
    
    if namespace_detectado:
        logger.info(f"[Namespace] Detectado: {namespace_detectado} (fonte: objetivo)")
        contexto_rag = dap_engine.buscar_contexto(objetivo, tenant_id, namespace=namespace_detectado)
    else:
        logger.info(f"[Namespace] Não detectado, usando tenant_id: {tenant_id}")
        contexto_rag = dap_engine.buscar_contexto(objetivo, tenant_id)
    
    # ... resto da lógica de geração
```

### Exemplo de Uso no Dashboard

Quando você cria um roteiro no dashboard com objetivo "Criar admissão no HCM":

1. O sistema detecta automaticamente `namespace="hcm"`
2. Busca contexto RAG apenas no namespace HCM
3. Gera roteiro com documentação específica do módulo HCM

**Log esperado:**
```
INFO:generator_engine:Buscando manual para: Criar admissão no HCM
INFO:namespace_detector:[Namespace] Detectado: hcm (fonte: keyword)
INFO:generator_engine:[Namespace] Detectado: hcm (fonte: objetivo)
```

---

## Integração com Capture Engine

O `capture.py` usa detecção automática ao buscar contexto Pinecone:

```python
# Em capture.py (já integrado)

from namespace_detector import detectar_namespace

def _buscar_pinecone_sync(objetivo_aula: str) -> str:
    # Detecta namespace do objetivo_aula
    contexto_deteccao = {"objetivo": objetivo_aula}
    namespace_detectado = detectar_namespace(contexto_deteccao)
    
    if namespace_detectado:
        namespace_query = namespace_detectado
        logger.info(f"[Namespace] Detectado: {namespace_detectado} (fonte: objetivo_aula)")
    else:
        namespace_query = os.getenv("DEFAULT_TENANT_ID", "senior_default")
        logger.info(f"[Namespace] Não detectado, usando tenant_id: {namespace_query}")
    
    # Query Pinecone com namespace detectado
    resultado = index.query(
        vector=embedding, 
        top_k=3, 
        namespace=namespace_query,
        include_metadata=True
    )
    # ... resto da lógica
```

### Exemplo de Uso na Captura

Quando você inicia uma captura com objetivo "Gerenciar documentos no GED":

1. O sistema detecta automaticamente `namespace="ged"`
2. Busca contexto RAG apenas no namespace GED durante a captura
3. Aura usa documentação específica do módulo GED

**Log esperado:**
```
INFO:capture:[Namespace] Detectado: ged (fonte: objetivo_aula)
```

---

## Customização de Keywords

### Método 1: Arquivo JSON (Recomendado)

Crie `namespace_keywords.json` na raiz do projeto:

```json
{
  "hcm": [
    "recursos humanos",
    "admissao",
    "admissão",
    "folha",
    "folha de pagamento",
    "rh",
    "colaborador",
    "funcionario",
    "funcionário",
    "ponto",
    "ferias",
    "férias",
    "beneficios",
    "benefícios"
  ],
  "financeiro": [
    "contas a pagar",
    "contas a receber",
    "tesouraria",
    "financas",
    "finanças",
    "pagamento",
    "recebimento",
    "faturamento",
    "nota fiscal",
    "boleto",
    "conciliacao",
    "conciliação"
  ],
  "ged": [
    "documentos",
    "arquivos",
    "pastas",
    "ged",
    "gestao documental",
    "gestão documental",
    "documento eletronico",
    "documento eletrônico",
    "workflow documental"
  ],
  "compras": [
    "compras",
    "requisicao",
    "requisição",
    "pedido de compra",
    "cotacao",
    "cotação",
    "fornecedor",
    "ordem de compra",
    "solicitacao de compra",
    "solicitação de compra"
  ],
  "estoque": [
    "estoque",
    "inventario",
    "inventário",
    "movimentacao",
    "movimentação",
    "armazem",
    "armazém",
    "produto",
    "item",
    "material",
    "entrada de estoque",
    "saida de estoque",
    "saída de estoque"
  ],
  "vendas": [
    "vendas",
    "pedido de venda",
    "orcamento",
    "orçamento",
    "cliente",
    "proposta comercial",
    "faturamento de vendas"
  ],
  "producao": [
    "producao",
    "produção",
    "ordem de producao",
    "ordem de produção",
    "planejamento de producao",
    "planejamento de produção",
    "apontamento",
    "chao de fabrica",
    "chão de fábrica"
  ],
  "fiscal": [
    "fiscal",
    "nota fiscal",
    "nfe",
    "nf-e",
    "sped",
    "obrigacoes fiscais",
    "obrigações fiscais",
    "apuracao de impostos",
    "apuração de impostos"
  ]
}
```

**Vantagens:**
- ✅ Fácil de editar e versionar
- ✅ Não requer restart do sistema (cache invalidado automaticamente)
- ✅ Suporta caracteres especiais (ã, ç, é, etc.)

### Método 2: Variável de Ambiente

Configure no `.env`:

```bash
NAMESPACE_KEYWORDS='{"hcm": ["recursos humanos", "admissao", "folha"], "financeiro": ["contas a pagar", "tesouraria"]}'
```

**Vantagens:**
- ✅ Útil para ambientes containerizados
- ✅ Não requer arquivo adicional

### Método 3: Defaults Hardcoded (Fallback)

Se nenhum dos métodos acima estiver configurado, o sistema usa defaults internos com 5+ módulos.

---

## Debugging e Logging

### Níveis de Log

O sistema usa diferentes níveis de log para diferentes eventos:

```python
import logging

# Configurar nível de log
logging.basicConfig(level=logging.DEBUG)  # Para ver todos os logs
logging.basicConfig(level=logging.INFO)   # Para ver apenas detecções bem-sucedidas
logging.basicConfig(level=logging.WARNING) # Para ver apenas fallbacks e erros
```

### Exemplos de Logs

**Detecção bem-sucedida (INFO):**
```
INFO:namespace_detector:[Namespace] Detectado: hcm (fonte: URL)
INFO:namespace_detector:[Namespace] Detectado: financeiro (fonte: metadata)
INFO:namespace_detector:[Namespace] Detectado: ged (fonte: keyword)
```

**Fallback (WARNING):**
```
WARNING:namespace_detector:[Namespace] Não detectado em nenhuma fonte, fallback para tenant_id
WARNING:dap_engine:[Namespace] Fallback: namespace e tenant_id ausentes, usando 'senior_default'
```

**Erro (ERROR):**
```
ERROR:namespace_detector:[Namespace] Erro na detecção: 'NoneType' object has no attribute 'lower'
ERROR:namespace_detector:[Namespace] Falha ao importar extractor: No module named 'ingestion_pipeline'
```

**Debug (DEBUG):**
```
DEBUG:namespace_detector:[Namespace] URL extraction: https://...senior-x/hcm/admissao → hcm
DEBUG:namespace_detector:[Namespace] Metadata extraction: module field → financeiro
DEBUG:namespace_detector:[Namespace] Keyword match: 'admissão' → hcm
DEBUG:dap_engine:[Namespace] Fallback: namespace não fornecido, usando tenant_id: senior_default
```

### Script de Debug

Crie um script para testar a detecção:

```python
# debug_namespace.py
import logging
from namespace_detector import detectar_namespace

# Ativar logs DEBUG
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s:%(name)s:%(message)s')

# Testar diferentes contextos
test_cases = [
    {"objetivo": "Criar admissão no HCM"},
    {"objetivo": "Configurar contas a pagar"},
    {"url": "https://docs.senior.com.br/senior-x/ged/pastas"},
    {"metadata": {"module": "compras"}},
    {},  # Sem hints
]

for i, contexto in enumerate(test_cases, 1):
    print(f"\n{'='*60}")
    print(f"Test {i}: {contexto}")
    print('='*60)
    resultado = detectar_namespace(contexto)
    print(f"→ Resultado: {resultado}")
```

Execute:
```bash
python debug_namespace.py
```

---

## Casos de Uso Avançados

### Caso 1: Múltiplos Hints (Prioridade)

```python
from namespace_detector import detectar_namespace

# Contexto com múltiplos hints - URL tem prioridade
contexto = {
    "url": "https://docs.senior.com.br/senior-x/hcm/admissao",
    "objetivo": "Configurar contas a pagar",  # Keyword de financeiro
    "metadata": {"module": "ged"}  # Metadata de GED
}

namespace = detectar_namespace(contexto)
print(f"Namespace: {namespace}")  # Output: hcm (URL tem prioridade)
```

### Caso 2: Integração com DAP Engine

```python
from namespace_detector import detectar_namespace
from dap_engine import buscar_contexto

def buscar_com_auto_namespace(prompt: str, tenant_id: str = "senior_default"):
    """Busca contexto RAG com detecção automática de namespace"""
    
    # Detecta namespace do prompt
    contexto = {"objetivo": prompt}
    namespace = detectar_namespace(contexto)
    
    # Busca com namespace detectado
    resultado = buscar_contexto(prompt, tenant_id, namespace=namespace)
    
    if resultado:
        print(f"✅ Contexto encontrado (namespace: {namespace or tenant_id})")
        print(f"Score: {resultado['score']:.2f}")
        print(f"Fonte: {resultado.get('melhor_aula', 'N/A')}")
        return resultado
    else:
        print(f"❌ Nenhum contexto encontrado")
        return None

# Uso
buscar_com_auto_namespace("Como criar uma admissão?")
```

### Caso 3: Validação de Namespace Antes de Processar

```python
from namespace_detector import detectar_namespace

def validar_namespace_obrigatorio(contexto: dict, namespaces_validos: list) -> bool:
    """Valida se o namespace detectado está na lista de namespaces válidos"""
    
    namespace = detectar_namespace(contexto)
    
    if namespace is None:
        print("⚠️  Namespace não detectado")
        return False
    
    if namespace not in namespaces_validos:
        print(f"❌ Namespace '{namespace}' não é válido")
        print(f"Namespaces válidos: {', '.join(namespaces_validos)}")
        return False
    
    print(f"✅ Namespace '{namespace}' válido")
    return True

# Uso
contexto = {"objetivo": "Criar admissão no HCM"}
namespaces_validos = ["hcm", "financeiro", "ged"]

if validar_namespace_obrigatorio(contexto, namespaces_validos):
    # Processar...
    pass
```

### Caso 4: Estatísticas de Detecção

```python
from namespace_detector import detectar_namespace
from collections import Counter

def analisar_deteccoes(roteiros: list) -> dict:
    """Analisa estatísticas de detecção de namespace em múltiplos roteiros"""
    
    namespaces = []
    fontes = []
    
    for roteiro in roteiros:
        contexto = {
            "objetivo": roteiro.get("objetivo", ""),
            "metadata": roteiro.get("metadata", {})
        }
        
        namespace = detectar_namespace(contexto)
        
        if namespace:
            namespaces.append(namespace)
            # Inferir fonte pelo log (simplificado)
            if "url" in contexto:
                fontes.append("URL")
            elif "module" in contexto.get("metadata", {}):
                fontes.append("metadata")
            else:
                fontes.append("keyword")
        else:
            namespaces.append("(não detectado)")
            fontes.append("fallback")
    
    return {
        "total": len(roteiros),
        "detectados": len([n for n in namespaces if n != "(não detectado)"]),
        "namespaces": Counter(namespaces),
        "fontes": Counter(fontes)
    }

# Uso
roteiros = [
    {"objetivo": "Criar admissão no HCM"},
    {"objetivo": "Configurar contas a pagar"},
    {"objetivo": "Gerenciar documentos"},
    {"objetivo": "Operação genérica"},
]

stats = analisar_deteccoes(roteiros)
print(f"Total: {stats['total']}")
print(f"Detectados: {stats['detectados']}")
print(f"Namespaces: {dict(stats['namespaces'])}")
print(f"Fontes: {dict(stats['fontes'])}")
```

---

## Referências

- **Código fonte**: `namespace_detector.py`
- **Testes**: `test_backward_compatibility.py`, `test_performance.py`
- **Spec completa**: `.kiro/specs/rag-namespace-auto-detection/`
- **Documentação principal**: `README.md`

---

## Suporte

Para problemas ou dúvidas:

1. Verifique os logs com `logging.basicConfig(level=logging.DEBUG)`
2. Execute os testes de backward compatibility: `python test_backward_compatibility.py`
3. Execute os testes de performance: `python test_performance.py`
4. Consulte a spec completa em `.kiro/specs/rag-namespace-auto-detection/`

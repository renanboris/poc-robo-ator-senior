# Design Document — Repo Security and CI Setup

## Overview

Este documento descreve o design técnico para a feature **repo-security-and-ci-setup**, que cobre três objetivos complementares:

1. **Higiene de segurança do repositório** — garantir que arquivos sensíveis (`.env`, `brain.db`, `aura_cache.db`) nunca estejam rastreados pelo Git, nem no estado atual nem no histórico.
2. **Limpeza permanente do histórico Git** — remover `brain.db` e `aura_cache.db` de todos os commits existentes usando `git-filter-repo`.
3. **Pipeline de CI com GitHub Actions** — executar lint (`ruff`) e testes unitários (`pytest`) automaticamente a cada push e pull request.

Esta feature não altera nenhuma lógica de aplicação. Todos os artefatos produzidos são arquivos de configuração, scripts de procedimento e um workflow YAML. O risco de regressão no pipeline de produção é zero.

---

## Architecture

A feature é composta por quatro camadas independentes:

```
┌─────────────────────────────────────────────────────────────┐
│                    Repositório GitHub                        │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────────────────┐  │
│  │  Segurança Local │    │     CI Pipeline (Actions)    │  │
│  │                  │    │                              │  │
│  │  .gitignore      │    │  .github/workflows/ci.yml    │  │
│  │  .env.example    │    │                              │  │
│  │                  │    │  ┌──────────┐ ┌───────────┐  │  │
│  └──────────────────┘    │  │  ruff    │ │  pytest   │  │  │
│                           │  │  check   │ │  -m "not  │  │  │
│  ┌──────────────────┐    │  │    .     │ │  integr." │  │  │
│  │  Linter Config   │    │  └──────────┘ └───────────┘  │  │
│  │                  │    └──────────────────────────────┘  │
│  │  ruff.toml       │                                       │
│  │                  │    ┌──────────────────────────────┐  │
│  └──────────────────┘    │  Limpeza de Histórico        │  │
│                           │  (procedimento one-shot)     │  │
│                           │                              │  │
│                           │  git-filter-repo             │  │
│                           │  + force-push                │  │
│                           └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

As quatro partes são independentes e podem ser executadas em qualquer ordem, mas a sequência recomendada é:

1. Atualizar `.gitignore` e `.env.example` (já existem, apenas verificar/complementar)
2. Criar `ruff.toml`
3. Executar limpeza de histórico com `git-filter-repo`
4. Criar `.github/workflows/ci.yml`
5. Adicionar `conftest.py` com registro do marker `integration`

---

## Components and Interfaces

### 1. `.gitignore`

**Arquivo existente** — verificar e complementar se necessário.

Entradas obrigatórias (já presentes no arquivo atual):
```
.env
brain.db
brain.db-journal
brain.db-shm
brain.db-wal
aura_cache.db
venv/
```

Nenhuma alteração estrutural necessária — o `.gitignore` atual já cobre todos os requisitos.

---

### 2. `.env.example`

**Arquivo existente** — verificar se todas as variáveis estão documentadas.

O arquivo atual já contém as variáveis principais. Deve ser mantido sem valores reais. Qualquer nova variável de ambiente adicionada ao projeto deve ser espelhada aqui com um valor placeholder.

---

### 3. `ruff.toml`

**Arquivo novo** — criado na raiz do repositório.

```toml
# ruff.toml — Configuração do linter para Senior Training OS

[lint]
# Categorias obrigatórias:
#   E — erros de estilo PEP8 (pycodestyle)
#   F — erros lógicos Pyflakes
# Categorias adicionais recomendadas para o projeto:
#   I — ordenação de imports (isort)
#   W — avisos de estilo PEP8
select = ["E", "F", "I", "W"]

# Regras ignoradas intencionalmente:
#   E501 — linha muito longa (o projeto tem linhas longas em templates e prompts)
#   E402 — module level import not at top (sys.path.insert nos testes)
ignore = ["E501", "E402"]

[lint.per-file-ignores]
# Arquivos de teste: permitir imports não utilizados e assert statements
"tests/**/*.py" = ["F401", "F811"]
# Arquivos legados: ignorar todos os erros
"old_but_gold/**/*.py" = ["E", "F", "W"]

[exclude]
# Diretórios excluídos da verificação
paths = [
    "venv/",
    "old_but_gold/",
    ".hypothesis/",
    ".git/",
    "__pycache__/",
    ".pytest_cache/",
]
```

**Decisão de design**: `E501` (linha longa) é ignorado porque o projeto contém prompts de IA, templates Jinja2 e strings longas que são intencionais e não devem ser quebradas. `E402` é ignorado porque os arquivos de teste usam `sys.path.insert(0, ...)` antes dos imports do projeto — padrão já estabelecido em toda a suite de testes.

---

### 4. `.github/workflows/ci.yml`

**Arquivo novo** — criado no diretório `.github/workflows/`.

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: ["**"]

jobs:
  lint-and-test:
    name: Lint & Unit Tests
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Install ruff
        run: pip install ruff==0.4.4

      - name: Lint with ruff
        run: ruff check .

      - name: Run unit tests
        env:
          # Stubs para variáveis de ambiente — valores fictícios não funcionais
          # Permitem importação dos módulos sem credenciais reais
          GOOGLE_API_KEY: "stub-google-key"
          OPENAI_API_KEY: "stub-openai-key"
          SENIOR_USER: "ci@stub.local"
          SENIOR_PASS: "stub-password"
          PINECONE_API_KEY: "stub-pinecone-key"
          PINECONE_INDEX_NAME: "stub-index"
          ELEVENLABS_API_KEY: "stub-elevenlabs-key"
          AURA_API_SECRET: "stub-aura-secret"
          APP_USER_NAME: "CI Runner"
          BLUR_SELECTORS: ""
        run: pytest tests/ -m "not integration" -x --timeout=60
```

**Decisões de design**:

- `ruff` é instalado com versão pinada (`0.4.4`) para evitar quebras por atualizações automáticas do linter.
- `actions/checkout@v4` e `actions/setup-python@v5` são as versões estáveis atuais.
- Os stubs de variáveis de ambiente são valores claramente fictícios (prefixo `stub-`) — não funcionais, mas suficientes para que os módulos sejam importados sem lançar `KeyError` ou `ValueError` na inicialização.
- `pytest-timeout` precisa estar em `requirements.txt` para que `--timeout=60` funcione. Se não estiver, adicionar `pytest-timeout>=2.3.0`.
- O flag `-x` (fail-fast) interrompe na primeira falha, tornando o feedback mais rápido.
- Playwright **não** é instalado no CI — testes que dependem de browser devem ser marcados com `@pytest.mark.integration`.

---

### 5. `conftest.py` (raiz do projeto)

**Arquivo novo** — registra o marker `integration` para evitar warnings do pytest e documentar a convenção.

```python
# conftest.py
import pytest


def pytest_configure(config):
    """Registra markers customizados do projeto."""
    config.addinivalue_line(
        "markers",
        "integration: marca testes que dependem de serviços externos "
        "(Gemini, OpenAI, Playwright, Pinecone). "
        "Excluídos da execução no CI com: pytest -m 'not integration'",
    )
```

**Decisão de design**: O `conftest.py` na raiz é o local canônico para registrar markers. Isso elimina o warning `PytestUnknownMarkWarning` que apareceria ao usar `-m "not integration"` sem o marker registrado.

---

### 6. Procedimento de Limpeza de Histórico Git

Este é um procedimento **one-shot** executado manualmente pelo responsável do repositório. Não é automatizado via CI.

**Pré-requisitos**:
```bash
pip install git-filter-repo
```

**Execução**:
```bash
# 1. Garantir que o working tree está limpo
git status

# 2. Remover brain.db e aura_cache.db de todo o histórico
git filter-repo --path brain.db --invert-paths --force
git filter-repo --path aura_cache.db --invert-paths --force

# 3. Verificar que os arquivos foram removidos do histórico
git log --all --full-history -- brain.db
git log --all --full-history -- aura_cache.db
# Ambos devem retornar vazio

# 4. Reconfigurar o remote (git-filter-repo remove o remote por segurança)
git remote add origin <URL_DO_REPOSITORIO>

# 5. Force-push com proteção contra sobrescrita acidental
git push --force-with-lease origin <branch>
```

**Ação necessária para colaboradores após o force-push**:
```bash
# Opção A: re-clonar (mais seguro)
git clone <URL_DO_REPOSITORIO>

# Opção B: sincronizar o clone existente
git fetch --all
git reset --hard origin/<branch>
```

> **Atenção**: `git-filter-repo` reescreve todos os SHAs do histórico. Qualquer branch ou tag local baseada nos SHAs antigos ficará desatualizada. Coordenar com todos os colaboradores antes de executar.

---

## Data Models

Esta feature não introduz novos modelos de dados. Os artefatos produzidos são:

| Artefato | Tipo | Localização |
|---|---|---|
| `.gitignore` | Configuração Git | raiz do repositório |
| `.env.example` | Documentação de ambiente | raiz do repositório |
| `ruff.toml` | Configuração de linter | raiz do repositório |
| `.github/workflows/ci.yml` | Workflow YAML | `.github/workflows/` |
| `conftest.py` | Configuração pytest | raiz do repositório |

Nenhum schema de banco de dados, modelo Pydantic ou contrato de roteiro é alterado.

---

## Correctness Properties

Property-based testing **não se aplica** a esta feature.

Todos os requisitos desta feature envolvem:
- Verificação de existência e conteúdo de arquivos de configuração (SMOKE)
- Comportamento de infraestrutura do GitHub Actions (INTEGRATION)
- Procedimentos operacionais one-shot (SMOKE)

Nenhum critério de aceitação envolve lógica de código com espaço de entrada variável que justifique testes baseados em propriedades. A estratégia de teste adequada é descrita na seção Testing Strategy abaixo.

---

## Error Handling

### Falhas no CI

| Cenário | Comportamento esperado |
|---|---|
| `ruff check .` encontra violações | Job falha com saída listando arquivo, linha e regra violada |
| `pytest` encontra teste falhando | Job falha com saída do pytest mostrando o teste e o traceback |
| `pip install -r requirements.txt` falha | Job falha na etapa de instalação; verificar compatibilidade de versões |
| Secret não configurado no GitHub | Variável de ambiente fica vazia; testes unitários usam stubs e não dependem de secrets reais |

### Falhas na Limpeza de Histórico

| Cenário | Ação corretiva |
|---|---|
| `git filter-repo` não encontrado | `pip install git-filter-repo` |
| Remote removido após execução | `git remote add origin <URL>` |
| Conflito no force-push | Verificar se outro colaborador fez push; coordenar antes de reexecutar |
| Arquivo ainda aparece no histórico após limpeza | Verificar se foi executado com `--force`; reexecutar se necessário |

### Falhas de Lint

| Cenário | Ação corretiva |
|---|---|
| Violação `E501` em arquivo legítimo | Já ignorado globalmente em `ruff.toml` |
| Violação `E402` em arquivo de teste | Já ignorado globalmente em `ruff.toml` |
| Violação legítima em código de produção | Corrigir o código ou adicionar `# noqa: <CÓDIGO>` com comentário explicativo |
| Falso positivo em padrão intencional | Adicionar `# noqa: <CÓDIGO>` com comentário explicando a intenção |

---

## Testing Strategy

Esta feature não possui testes automatizados próprios — ela **é** a infraestrutura de testes. A validação é feita por verificações manuais e smoke checks.

### Smoke Checks — Verificação de Configuração

Após implementar cada artefato, verificar:

**`.gitignore`**:
```bash
git check-ignore -v .env brain.db aura_cache.db venv/
# Cada arquivo deve retornar o path do .gitignore e a regra correspondente
```

**`ruff.toml`**:
```bash
ruff check . --statistics
# Deve executar sem erros de configuração
# Deve ignorar venv/, old_but_gold/, .hypothesis/
```

**`conftest.py`**:
```bash
pytest --co -q 2>&1 | grep -i "warning"
# Não deve aparecer PytestUnknownMarkWarning para o marker 'integration'
```

**`.github/workflows/ci.yml`**:
```bash
# Validação local do YAML (opcional, requer actionlint)
actionlint .github/workflows/ci.yml
```

### Smoke Check — Limpeza de Histórico

Após executar `git-filter-repo`:
```bash
git log --all --full-history -- brain.db
git log --all --full-history -- aura_cache.db
# Ambos devem retornar vazio (sem output)
```

### Teste de Integração — CI Pipeline

O próprio pipeline é validado ao fazer push para o repositório. O primeiro push após criar o workflow deve:

1. Acionar o job `lint-and-test`
2. Passar na etapa de lint (ou reportar violações reais a corrigir)
3. Passar na etapa de testes unitários

### Testes Unitários Existentes — Separação por Marker

Os testes que dependem de Playwright, Gemini, OpenAI ou Pinecone devem ser marcados com `@pytest.mark.integration`. Identificação inicial dos candidatos:

- `tests/test_robot_execution_wrong_clicks_exploration.py` — usa `async_playwright` diretamente
- `tests/test_robot_execution_wrong_clicks_preservation.py` — usa `async_playwright` diretamente
- Qualquer teste que faça chamadas reais a APIs externas sem mock

Os demais testes (a grande maioria) já usam mocks e `tmp_path` — são seguros para execução no CI sem credenciais reais.

### Não Aplicável

- **Property-based testing**: não aplicável (ver seção Correctness Properties)
- **Snapshot tests**: não aplicável (sem UI rendering)
- **Integration tests automatizados no CI**: não aplicável para esta feature (o CI em si é o artefato)

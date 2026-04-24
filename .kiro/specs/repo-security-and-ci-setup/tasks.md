# Implementation Plan: Repo Security and CI Setup

## Overview

Configuração incremental de segurança e CI para o repositório Senior Training OS. Os artefatos são independentes entre si e podem ser implementados em qualquer ordem, mas a sequência abaixo minimiza o risco de falhas no CI ao garantir que lint e markers de teste estejam corretos antes de ativar o pipeline.

Nenhuma lógica de aplicação é alterada. Risco de regressão no pipeline de produção: zero.

## Tasks

- [x] 1. Verificar `.gitignore` e `.env.example`
  - Confirmar que `.gitignore` contém todas as entradas obrigatórias: `.env`, `brain.db`, `brain.db-journal`, `brain.db-shm`, `brain.db-wal`, `aura_cache.db`, `venv/`
  - Confirmar que `.env.example` documenta todas as variáveis de ambiente sem valores reais
  - Executar `git check-ignore -v .env brain.db aura_cache.db venv/` e verificar que cada arquivo retorna a regra correspondente
  - Se alguma entrada estiver faltando, adicionar ao `.gitignore`
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Criar `ruff.toml` na raiz do repositório
  - [x] 2.1 Criar o arquivo `ruff.toml` com as regras de lint do projeto
    - Selecionar categorias `E`, `F`, `I`, `W`
    - Ignorar `E501` (linhas longas em prompts e templates) e `E402` (sys.path.insert nos testes)
    - Configurar `per-file-ignores` para `tests/**/*.py` (F401, F811) e `old_but_gold/**/*.py` (E, F, W)
    - Excluir `venv/`, `old_but_gold/`, `.hypothesis/`, `.git/`, `__pycache__/`, `.pytest_cache/`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 2.2 Smoke check do `ruff.toml`
    - Executar `ruff check . --statistics` e confirmar que não há erros de configuração
    - Confirmar que `venv/`, `old_but_gold/` e `.hypothesis/` são ignorados na saída

- [x] 3. Criar `conftest.py` na raiz com registro do marker `integration`
  - [x] 3.1 Criar `conftest.py` na raiz do projeto
    - Implementar `pytest_configure` registrando o marker `integration` com descrição clara
    - Documentar que testes marcados com `@pytest.mark.integration` dependem de Playwright, Gemini, OpenAI ou Pinecone e são excluídos do CI
    - _Requirements: 3.7_

  - [ ]* 3.2 Smoke check do `conftest.py`
    - Executar `pytest --co -q 2>&1` e confirmar ausência de `PytestUnknownMarkWarning` para o marker `integration`

- [x] 4. Marcar testes Playwright com `@pytest.mark.integration`
  - [x] 4.1 Adicionar `@pytest.mark.integration` em `tests/test_robot_execution_wrong_clicks_exploration.py`
    - Marcar as três funções de teste: `test_bug1_resolver_contexto_returns_framelocator_not_frame`, `test_bug2_coordinates_not_adjusted_correctly`, `test_bug3_wrong_element_found_parent_container`
    - Todas usam `async_playwright` diretamente e requerem Chromium instalado
    - _Requirements: 3.7_

  - [x] 4.2 Adicionar `@pytest.mark.integration` em `tests/test_robot_execution_wrong_clicks_preservation.py`
    - Marcar todas as funções de teste que usam `async_playwright`: `test_preservation_no_iframe_hint_uses_automatic_detection`, `test_preservation_generic_iframe_hint_returns_page`, `test_preservation_main_page_clicks_work_without_adjustment`, `test_preservation_resolver_contexto_fallback_to_page`, `test_preservation_clicks_outside_iframes_work_correctly`, `test_property_generic_hints_always_return_page`, `test_property_main_page_coordinates_no_adjustment`
    - _Requirements: 3.7_

  - [x] 4.3 Adicionar `@pytest.mark.integration` em `tests/test_iframe_element_location_bug_exploration.py` e `tests/test_iframe_element_location_preservation.py`
    - Ambos os arquivos usam `async_playwright` diretamente
    - _Requirements: 3.7_

  - [ ]* 4.4 Verificar separação de testes
    - Executar `pytest tests/ -m "not integration" --collect-only -q` e confirmar que nenhum teste Playwright aparece na coleção
    - Executar `pytest tests/ -m "integration" --collect-only -q` e confirmar que os testes Playwright aparecem

- [x] 5. Checkpoint — Lint e testes unitários passando localmente
  - Executar `ruff check .` e corrigir quaisquer violações reais encontradas no código de produção
  - Executar `pytest tests/ -m "not integration" -x --timeout=60` e confirmar que todos os testes unitários passam
  - Garantir que `pytest-timeout` está em `requirements.txt`; se não estiver, adicionar `pytest-timeout>=2.3.0`
  - Perguntar ao usuário se há dúvidas antes de prosseguir para a criação do workflow de CI

- [x] 6. Criar `.github/workflows/ci.yml`
  - [x] 6.1 Criar o diretório `.github/workflows/` e o arquivo `ci.yml`
    - Configurar trigger em `push` e `pull_request` para todas as branches (`"**"`)
    - Definir job `lint-and-test` rodando em `ubuntu-latest` com Python 3.11
    - Etapas: checkout (`actions/checkout@v4`), setup Python (`actions/setup-python@v5`), install dependencies (`pip install -r requirements.txt`), install ruff com versão pinada (`pip install ruff==0.4.4`), lint (`ruff check .`), testes unitários (`pytest tests/ -m "not integration" -x --timeout=60`)
    - Fornecer todas as variáveis de ambiente stub no step de testes (GOOGLE_API_KEY, OPENAI_API_KEY, SENIOR_USER, SENIOR_PASS, PINECONE_API_KEY, PINECONE_INDEX_NAME, ELEVENLABS_API_KEY, AURA_API_SECRET, APP_USER_NAME, BLUR_SELECTORS) com valores fictícios prefixados com `stub-`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.9, 3.10, 3.11, 4.1, 4.2_

  - [ ]* 6.2 Validar sintaxe do YAML localmente
    - Se `actionlint` estiver disponível, executar `actionlint .github/workflows/ci.yml`
    - Alternativamente, validar o YAML com `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`

- [x] 7. Documentar procedimento de limpeza de histórico Git
  - [x] 7.1 Criar arquivo `docs/runbook-git-history-cleanup.md` com o procedimento completo
    - Documentar pré-requisitos: `pip install git-filter-repo`, working tree limpo
    - Documentar os comandos de execução: `git filter-repo --path brain.db --invert-paths --force` e `git filter-repo --path aura_cache.db --invert-paths --force`
    - Documentar verificação pós-limpeza: `git log --all --full-history -- brain.db` e `git log --all --full-history -- aura_cache.db` (ambos devem retornar vazio)
    - Documentar reconfiguração do remote após execução: `git remote add origin <URL>`
    - Documentar force-push: `git push --force-with-lease origin <branch>`
    - Documentar ação necessária para colaboradores: re-clone ou `git fetch --all && git reset --hard origin/<branch>`
    - Incluir aviso sobre reescrita de SHAs e necessidade de coordenação com colaboradores
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

- [x] 8. Checkpoint final — Verificação completa
  - Confirmar que todos os arquivos criados existem: `ruff.toml`, `conftest.py`, `.github/workflows/ci.yml`, `docs/runbook-git-history-cleanup.md`
  - Executar `ruff check .` uma última vez para confirmar zero violações
  - Executar `pytest tests/ -m "not integration" -x --timeout=60` para confirmar que todos os testes unitários passam
  - Garantir que o próximo push ao repositório acionará o CI corretamente
  - Perguntar ao usuário se há dúvidas antes de concluir

## Notes

- Tarefas marcadas com `*` são opcionais (smoke checks) e podem ser puladas para MVP mais rápido
- O procedimento de limpeza de histórico Git (Tarefa 7) é um runbook manual — não é automatizado pelo CI
- `pytest-timeout` deve estar em `requirements.txt` para que `--timeout=60` funcione no CI
- Playwright **não** é instalado no CI — todos os testes que usam `async_playwright` devem ter `@pytest.mark.integration`
- Os stubs de variáveis de ambiente no CI são valores claramente fictícios (prefixo `stub-`) — suficientes para importação dos módulos sem credenciais reais
- `ruff` é instalado com versão pinada (`0.4.4`) no CI para evitar quebras por atualizações automáticas

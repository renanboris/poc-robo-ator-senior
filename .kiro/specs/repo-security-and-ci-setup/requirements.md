# Requirements Document

## Introduction

Este documento define os requisitos para a melhoria de segurança e infraestrutura de CI do repositório **Senior Training OS**.

O projeto atualmente possui um `.gitignore` que exclui `.env` e `brain.db` de novos commits, mas não há garantia de que esses arquivos não estejam presentes no histórico git. Além disso, não existe pipeline de integração contínua (CI) configurado para validar qualidade de código automaticamente.

O escopo desta feature cobre três objetivos:
1. Garantir que dados sensíveis (secrets, banco de dados local) não estejam acessíveis no repositório — nem no estado atual nem no histórico.
2. Remover `brain.db` e `aura_cache.db` do histórico git de forma permanente e segura.
3. Configurar um pipeline de CI com GitHub Actions que execute lint e testes mínimos a cada push/PR.

## Glossary

- **Repository**: O repositório Git do projeto Senior Training OS hospedado no GitHub.
- **Sensitive_File**: Arquivo que contém credenciais, tokens, chaves de API ou dados operacionais locais (ex: `.env`, `brain.db`, `aura_cache.db`).
- **Git_History**: O conjunto completo de commits e objetos armazenados no repositório Git, incluindo commits anteriores.
- **Gitignore**: O arquivo `.gitignore` que instrui o Git a não rastrear determinados arquivos.
- **CI_Pipeline**: O pipeline de integração contínua configurado via GitHub Actions.
- **Lint_Check**: Verificação estática de estilo e qualidade de código usando `ruff`.
- **Test_Suite**: Conjunto de testes automatizados executados com `pytest`.
- **Secrets**: Variáveis de ambiente sensíveis como `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `AURA_API_SECRET`, entre outras definidas em `.env.example`.
- **GitHub_Actions**: Plataforma de CI/CD integrada ao GitHub usada para automatizar workflows.
- **git-filter-repo**: Ferramenta recomendada pelo Git para reescrita de histórico e remoção de arquivos sensíveis.
- **Environment_Variable**: Variável de configuração fornecida ao runtime via `.env` ou via secrets do GitHub Actions.
- **Unit_Test**: Teste que não depende de serviços externos (Gemini, OpenAI, Playwright, banco de dados remoto), executável no CI sem credenciais reais.
- **Integration_Test**: Teste que depende de serviços externos ou infraestrutura real, marcado com `@pytest.mark.integration` e excluído da execução no CI.

---

## Requirements

### Requirement 1: Garantia de Exclusão de Arquivos Sensíveis do Repositório

**User Story:** Como desenvolvedor do projeto, quero garantir que arquivos sensíveis nunca sejam rastreados pelo Git, para que credenciais e dados operacionais locais não sejam expostos acidentalmente.

#### Acceptance Criteria

1. THE Repository SHALL conter um arquivo `.gitignore` que inclua entradas para `.env`, `brain.db`, `brain.db-journal`, `brain.db-shm`, `brain.db-wal`, `aura_cache.db` e `venv/`.
2. WHEN um desenvolvedor tenta fazer commit de um arquivo listado no `.gitignore`, THE Repository SHALL ignorar o arquivo e não incluí-lo no commit.
3. THE Repository SHALL conter um arquivo `.env.example` com todas as variáveis de ambiente necessárias documentadas, sem valores reais de credenciais.
4. IF um arquivo sensível for detectado como rastreado pelo Git (via `git ls-files`), THEN THE Repository SHALL exigir que o arquivo seja removido do índice com `git rm --cached` antes de qualquer novo push.

---

### Requirement 2: Remoção de `brain.db` e `aura_cache.db` do Histórico Git

**User Story:** Como responsável pela segurança do projeto, quero remover `brain.db` e `aura_cache.db` permanentemente do histórico git, para que dados operacionais locais não sejam acessíveis em commits anteriores.

#### Acceptance Criteria

1. WHEN o processo de limpeza de histórico for executado, THE Repository SHALL utilizar `git-filter-repo` para remover `brain.db` e `aura_cache.db` de todos os commits existentes em uma única operação.
2. WHEN a limpeza for concluída, THE Repository SHALL não conter nenhuma referência a `brain.db` em nenhum objeto do histórico git (verificável via `git log --all --full-history -- brain.db`).
3. WHEN a limpeza for concluída, THE Repository SHALL não conter nenhuma referência a `aura_cache.db` em nenhum objeto do histórico git (verificável via `git log --all --full-history -- aura_cache.db`).
4. WHEN o histórico for reescrito, THE Repository SHALL exigir um force-push para a branch remota (`git push --force-with-lease`).
5. IF outros colaboradores possuírem clones locais do repositório, THEN THE Repository SHALL requerer que esses colaboradores façam `git clone` novamente ou executem `git fetch --all` seguido de `git reset --hard origin/<branch>`.
6. THE Repository SHALL manter o arquivo `.gitignore` atualizado para prevenir que `brain.db` e `aura_cache.db` sejam adicionados novamente ao histórico após a limpeza.

---

### Requirement 3: Configuração do Pipeline de CI com GitHub Actions

**User Story:** Como desenvolvedor, quero um pipeline de CI configurado no GitHub Actions, para que lint e testes sejam executados automaticamente a cada push e pull request, garantindo qualidade mínima do código.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL ser definido em um arquivo YAML localizado em `.github/workflows/ci.yml`.
2. WHEN um push for feito para qualquer branch, THE CI_Pipeline SHALL ser acionado automaticamente.
3. WHEN um pull request for aberto ou atualizado, THE CI_Pipeline SHALL ser acionado automaticamente.
4. THE CI_Pipeline SHALL executar o Lint_Check usando `ruff check .` no código Python do projeto.
5. IF o Lint_Check detectar violações, THEN THE CI_Pipeline SHALL falhar e reportar as violações encontradas.
6. THE CI_Pipeline SHALL executar o Test_Suite usando `pytest tests/ -m "not integration" -x --timeout=60` após o Lint_Check passar, excluindo testes que dependem de serviços externos.
7. THE Test_Suite SHALL utilizar a marker `@pytest.mark.integration` para identificar testes que dependem de Gemini, OpenAI, Playwright ou outros serviços externos, de forma que possam ser excluídos da execução no CI.
8. IF qualquer Unit_Test do Test_Suite falhar, THEN THE CI_Pipeline SHALL falhar e reportar o teste com falha.
9. THE CI_Pipeline SHALL instalar as dependências do projeto a partir de `requirements.txt` antes de executar lint e testes.
10. THE CI_Pipeline SHALL utilizar Python 3.11 como versão de runtime.
11. WHERE o Test_Suite requer variáveis de ambiente, THE CI_Pipeline SHALL fornecer valores fictícios (stubs) via `env:` no workflow para permitir a execução de Unit_Tests sem credenciais reais.

---

### Requirement 4: Proteção de Secrets no GitHub Actions

**User Story:** Como responsável pela segurança do projeto, quero que credenciais reais nunca apareçam nos logs ou arquivos do CI, para que o pipeline não exponha dados sensíveis.

#### Acceptance Criteria

1. THE CI_Pipeline SHALL referenciar credenciais reais exclusivamente via GitHub Actions Secrets (ex: `${{ secrets.GOOGLE_API_KEY }}`), nunca como valores literais no arquivo YAML.
2. THE CI_Pipeline SHALL utilizar apenas variáveis de ambiente stub (valores fictícios não funcionais) para execução de Unit_Tests que não requerem conectividade com serviços externos.
3. IF um Secret necessário não estiver configurado no repositório GitHub, THEN THE CI_Pipeline SHALL falhar com mensagem de erro descritiva em vez de continuar com valor vazio.
4. THE Repository SHALL conter documentação em `README` ou arquivo dedicado descrevendo quais Secrets precisam ser configurados no GitHub para o CI funcionar corretamente.

---

### Requirement 5: Configuração de Lint com Ruff

**User Story:** Como desenvolvedor, quero que o linter `ruff` esteja configurado com regras adequadas ao projeto, para que verificações de qualidade sejam consistentes e não gerem falsos positivos desnecessários.

#### Acceptance Criteria

1. THE Repository SHALL conter um arquivo de configuração `ruff.toml` ou seção `[tool.ruff]` em `pyproject.toml` com as regras de lint aplicáveis ao projeto.
2. THE Lint_Check SHALL ignorar os diretórios `venv/`, `old_but_gold/`, e `.hypothesis/` durante a verificação.
3. WHERE o projeto utiliza padrões de código legado ou intencionais que violam regras do ruff, THE Lint_Check SHALL conter supressões explícitas (`# noqa`) documentadas no código ou exclusões no arquivo de configuração.
4. THE Lint_Check SHALL verificar no mínimo as regras de categoria `E` (erros de estilo PEP8) e `F` (erros lógicos Pyflakes).

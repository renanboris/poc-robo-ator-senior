# Runbook: Limpeza de Arquivos Sensíveis do Histórico Git

## Objetivo

Remover permanentemente `brain.db` e `aura_cache.db` de todos os commits do histórico git, garantindo que dados operacionais locais não sejam acessíveis em versões anteriores do repositório.

> **⚠️ Atenção:** Este procedimento reescreve o histórico git. Todos os SHAs de commits serão alterados. Coordene com todos os colaboradores antes de executar.

---

## Pré-requisitos

1. Working tree limpo (sem alterações pendentes):
   ```bash
   git status
   # Deve retornar: nothing to commit, working tree clean
   ```

2. Instalar `git-filter-repo`:
   ```bash
   pip install git-filter-repo
   ```

3. Fazer backup local do repositório (recomendado):
   ```bash
   cp -r . ../senior-training-os-backup
   ```

---

## Execução

### Passo 1 — Remover `brain.db` do histórico

```bash
git filter-repo --path brain.db --invert-paths --force
```

### Passo 2 — Remover `aura_cache.db` do histórico

```bash
git filter-repo --path aura_cache.db --invert-paths --force
```

> **Nota:** `git-filter-repo` remove o remote configurado por segurança após a execução. Isso é esperado.

---

## Verificação

Confirmar que os arquivos foram removidos de todo o histórico:

```bash
git log --all --full-history -- brain.db
git log --all --full-history -- aura_cache.db
```

Ambos os comandos devem retornar **vazio** (sem output). Se retornarem commits, o procedimento não foi concluído corretamente.

---

## Reconfigurar o Remote

Após a execução, o remote é removido automaticamente pelo `git-filter-repo`. Reconfigurá-lo:

```bash
git remote add origin <URL_DO_REPOSITORIO>
# Exemplo: git remote add origin https://github.com/org/senior-training-os.git
```

---

## Force-Push

Enviar o histórico reescrito para o repositório remoto:

```bash
git push --force-with-lease origin <branch>
# Exemplo: git push --force-with-lease origin main
```

> **`--force-with-lease`** é mais seguro que `--force`: falha se outro colaborador tiver feito push desde o último fetch, evitando sobrescrita acidental.

---

## Ação Necessária para Colaboradores

Após o force-push, **todos os colaboradores com clones locais** devem sincronizar:

**Opção A — Re-clonar (mais seguro):**
```bash
git clone <URL_DO_REPOSITORIO>
```

**Opção B — Sincronizar o clone existente:**
```bash
git fetch --all
git reset --hard origin/<branch>
```

> Clones locais baseados nos SHAs antigos ficarão incompatíveis com o repositório remoto após o force-push.

---

## Prevenção de Reincidência

O arquivo `.gitignore` já contém as entradas necessárias para evitar que esses arquivos sejam adicionados novamente:

```
brain.db
brain.db-journal
brain.db-shm
brain.db-wal
aura_cache.db
```

Para verificar que os arquivos estão sendo ignorados corretamente:

```bash
git check-ignore -v brain.db aura_cache.db
```

---

## Referências

- [git-filter-repo documentation](https://github.com/newren/git-filter-repo)
- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)

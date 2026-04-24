# Browser Disconnect & Dual Tenant — Bugfix Design

## Overview

Este documento cobre o design técnico para dois bugs independentes no Senior Training OS.

**Bug 1 — Fechar o navegador não cancela o robô:** o handler `websocket_status` em `app.py` remove o cliente da lista de conexões mas não encerra o `processo_atual`. O patch é cirúrgico: após `ws_manager.disconnect()`, verificar se a lista ficou vazia e, se sim, terminar o processo filho e atualizar o estado via `_set_estado()`.

**Bug 2 — Tenant único contamina a execução:** todos os módulos do pipeline leem `SENIOR_USER` / `SENIOR_PASS`, apontando para o mesmo tenant do Senior X. O patch substitui essas leituras por variáveis específicas por contexto (`SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE` para captura; `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE` para execução e validação) em 8 módulos, e atualiza `.env.example` e `tests/test_capture_adapter.py`.

Nenhum dos dois patches altera a arquitetura, contratos de roteiro, ou fluxo de automação Playwright.

---

## Glossary

- **Bug_Condition (C)**: A condição que ativa o bug — C₁ para desconexão sem encerramento; C₂ para leitura de credencial genérica.
- **Property (P)**: O comportamento correto esperado quando C é verdadeiro.
- **Preservation**: Comportamentos existentes que não devem ser alterados pelo patch.
- **`processo_atual`**: Variável global em `app.py` que referencia o `subprocess.Popen` do processo filho ativo (capture ou main).
- **`ws_manager.active_connections`**: Lista de WebSockets ativos gerenciada por `ConnectionManager` em `app.py`.
- **`_set_estado()`**: Função canônica de mutação de estado do servidor em `app.py`. Todo patch que altera estado deve usá-la.
- **`_estado_lock`**: `threading.Lock` que protege leitura/escrita de `processo_atual` e `estado_servidor`.
- **`SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`**: Novas variáveis de ambiente para o tenant de captura.
- **`SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`**: Novas variáveis de ambiente para o tenant de execução e validação.
- **Módulo de captura**: `capture.py`, `capture_variants/capture_dual_output.py`, `CIL/capture/capture_semantic.py`, `contracts/capture_adapter.py`.
- **Módulo de execução**: `main.py`, `validator.py`, `validator_hitl.py`, `CIL/main_cil.py`.

---

## Bug Details

### Bug 1 — Condição de desconexão sem encerramento

O bug manifesta quando o último cliente WebSocket desconecta enquanto `processo_atual` não é `None`. O handler `websocket_status` chama `ws_manager.disconnect(websocket)` mas não verifica se a lista ficou vazia nem encerra o processo filho.

**Formal Specification:**

```
FUNCTION isBugCondition_Disconnect(event)
  INPUT: event de WebSocketDisconnect em /api/ws/status
  OUTPUT: boolean

  RETURN ws_manager.active_connections IS EMPTY AFTER disconnect
     AND processo_atual IS NOT None
END FUNCTION
```

**Exemplos:**

- Usuário inicia captura, fecha a aba do navegador → `capture.py` continua rodando com Playwright aberto indefinidamente.
- Usuário inicia execução de roteiro, fecha o navegador → `main.py` continua reproduzindo passos no Senior X sem nenhum cliente observando.
- Dois clientes conectados, um fecha → processo continua (correto — não é bug condition).
- Nenhum processo ativo, cliente fecha → nada a encerrar (correto — não é bug condition).

---

### Bug 2 — Condição de tenant único

O bug manifesta em qualquer módulo que leia `os.getenv("SENIOR_USER")` ou `os.getenv("SENIOR_PASS")` sem distinção de contexto. Todos os 8 módulos afetados usam o mesmo par de credenciais, fazendo captura e execução operarem no mesmo tenant.

**Formal Specification:**

```
FUNCTION isBugCondition_Tenant(module)
  INPUT: nome do módulo (string)
  OUTPUT: boolean

  RETURN module reads "SENIOR_USER" OR "SENIOR_PASS"
     AND no distinction between capture and execute context
END FUNCTION
```

**Exemplos:**

- `capture.py` cria pastas e registros no tenant A → `main.py` encontra esses dados ao executar o roteiro no mesmo tenant A → validação inválida.
- `validator.py` valida no tenant A (contaminado pela captura) → resultado falso positivo.
- `CIL/capture/capture_semantic.py` usa `SENIOR_USER` → captura semântica opera no tenant de execução.
- `contracts/capture_adapter.py` retorna `SENIOR_USER` em `obter_credenciais()` → adapter de captura usa credenciais erradas.

---

## Expected Behavior

### Preservation Requirements

**Comportamentos que não devem mudar:**

- Quando há clientes WebSocket ativos e um processo está em execução, o processo continua normalmente sem interrupção.
- Quando um cliente desconecta mas ainda existem outros clientes ativos, o processo não é encerrado.
- Quando o usuário chama `POST /api/cancelar` explicitamente, o comportamento atual é preservado integralmente (terminate + job registry + remoção de temporários).
- O fluxo de automação Playwright em `capture.py`, `main.py`, `validator.py` e `validator_hitl.py` não é alterado — apenas a leitura da variável de credencial muda.
- `SENIOR_URL` continua sendo a mesma para todos os módulos, independentemente do par de credenciais.
- O `.env.example` continua servindo como documentação de referência de todas as variáveis necessárias.
- `tests/test_capture_adapter.py` continua passando após a atualização das variáveis.

**Escopo do patch:**

Todos os inputs que não envolvem desconexão do último cliente WebSocket com processo ativo (Bug 1) ou leitura de `SENIOR_USER`/`SENIOR_PASS` (Bug 2) são completamente não afetados.

---

## Hypothesized Root Cause

### Bug 1

1. **Handler incompleto**: O bloco `except WebSocketDisconnect` em `websocket_status` foi implementado apenas para remover o cliente da lista de conexões. A lógica de encerramento de processo (equivalente ao `POST /api/cancelar`) nunca foi adicionada ao handler de desconexão.

2. **Ausência de guarda de múltiplos clientes**: Não há verificação de `ws_manager.active_connections` após o `disconnect()`, o que seria necessário para distinguir "último cliente saiu" de "um de vários clientes saiu".

3. **Processo filho desacoplado do ciclo de vida do WebSocket**: O `processo_atual` é gerenciado pelo thread de background `executar_processo_bg`, que não tem conhecimento de eventos de desconexão WebSocket.

### Bug 2

1. **Variável única para dois contextos**: O projeto nasceu com um único tenant de desenvolvimento. Quando o pipeline cresceu para incluir captura + execução + validação, as variáveis `SENIOR_USER`/`SENIOR_PASS` foram reusadas em todos os módulos sem distinção.

2. **Ausência de contrato de credenciais por contexto**: Não existe nenhuma convenção ou validação que force módulos de captura a usar credenciais diferentes dos módulos de execução.

3. **`contracts/capture_adapter.py` sem isolamento**: O `SeniorXAdapter.obter_credenciais()` retorna `SENIOR_USER`/`SENIOR_PASS` diretamente, sem indicar que é um adapter de captura.

---

## Correctness Properties

Property 1: Bug Condition — Encerramento automático ao desconectar

_For any_ evento de `WebSocketDisconnect` onde `ws_manager.active_connections` fica vazio após o `disconnect()` e `processo_atual` não é `None`, o handler `websocket_status` corrigido SHALL encerrar o processo filho via `proc.terminate()` e atualizar o estado via `_set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.")`.

**Validates: Requirements 1.1, 1.2, 1.3**

Property 2: Preservation — Processo não encerrado com clientes ativos

_For any_ evento de `WebSocketDisconnect` onde `ws_manager.active_connections` ainda contém pelo menos um cliente após o `disconnect()`, o handler corrigido SHALL produzir exatamente o mesmo resultado que o handler original, preservando o processo em execução e os demais clientes conectados.

**Validates: Requirements 3.1, 3.2**

Property 3: Bug Condition — Credenciais corretas por contexto

_For any_ módulo onde `isBugCondition_Tenant` é verdadeiro, o módulo corrigido SHALL ler as variáveis específicas ao seu contexto: módulos de captura usam `SENIOR_USER_CAPTURE`/`SENIOR_PASS_CAPTURE`; módulos de execução usam `SENIOR_USER_EXECUTE`/`SENIOR_PASS_EXECUTE`.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6**

Property 4: Preservation — Fluxo Playwright inalterado

_For any_ módulo corrigido com credenciais válidas nas novas variáveis, o fluxo de automação Playwright SHALL produzir o mesmo comportamento que o módulo original com credenciais válidas nas variáveis antigas, preservando toda a lógica de login, captura e execução.

**Validates: Requirements 3.4, 3.5, 3.6, 3.7, 3.8**

---

## Fix Implementation

### Bug 1 — Patch em `app.py`

**Arquivo:** `app.py`

**Função:** `websocket_status` (rota `/api/ws/status`)

**Mudança específica:** No bloco `except WebSocketDisconnect`, após `ws_manager.disconnect(websocket)`, adicionar verificação de lista vazia e encerramento do processo.

```python
# ANTES
except WebSocketDisconnect:
    ws_manager.disconnect(websocket)

# DEPOIS
except WebSocketDisconnect:
    ws_manager.disconnect(websocket)
    if not ws_manager.active_connections:
        with _estado_lock:
            proc = processo_atual
        if proc:
            logging.info("[ws-disconnect] Último cliente desconectou com processo ativo — cancelando.")
            proc.terminate()
            _set_estado(ocupado=False, progresso=None, erro="Execução interrompida: navegador fechado.")
            with _estado_lock:
                processo_atual = None
```

**Invariante de preservação:** A lógica só dispara quando `ws_manager.active_connections` está vazio. Se ainda há outros clientes, o processo continua normalmente.

**Nota sobre `_estado_lock`:** A leitura de `processo_atual` e a escrita de `None` são feitas dentro de `_estado_lock` separadamente (não em um único bloco) para evitar deadlock com `_set_estado()`, que também adquire o lock internamente. O `proc.terminate()` é chamado fora do lock, pois é uma operação de sistema operacional que não precisa de proteção.

---

### Bug 2 — Patches nos módulos de credenciais

#### `capture.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).", flush=True)

# DEPOIS
usuario = os.getenv("SENIOR_USER_CAPTURE")
senha   = os.getenv("SENIOR_PASS_CAPTURE")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais de captura ausentes no .env (SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE).", flush=True)
```

#### `capture_variants/capture_dual_output.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).", flush=True)

# DEPOIS
usuario = os.getenv("SENIOR_USER_CAPTURE")
senha   = os.getenv("SENIOR_PASS_CAPTURE")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais de captura ausentes no .env (SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE).", flush=True)
```

#### `CIL/capture/capture_semantic.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).")

# DEPOIS
usuario = os.getenv("SENIOR_USER_CAPTURE")
senha   = os.getenv("SENIOR_PASS_CAPTURE")
if not usuario or not senha:
    print("ERRO FATAL: Credenciais de captura ausentes no .env (SENIOR_USER_CAPTURE / SENIOR_PASS_CAPTURE).")
```

#### `contracts/capture_adapter.py` — `SeniorXAdapter.obter_credenciais()`

```python
# ANTES
def obter_credenciais(self) -> dict:
    return {
        "usuario": os.getenv("SENIOR_USER", ""),
        "senha":   os.getenv("SENIOR_PASS", ""),
    }

# DEPOIS
def obter_credenciais(self) -> dict:
    return {
        "usuario": os.getenv("SENIOR_USER_CAPTURE", ""),
        "senha":   os.getenv("SENIOR_PASS_CAPTURE", ""),
    }
```

#### `main.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")
if not usuario or not senha:
    print("ERRO: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS)")

# DEPOIS
usuario = os.getenv("SENIOR_USER_EXECUTE")
senha   = os.getenv("SENIOR_PASS_EXECUTE")
if not usuario or not senha:
    print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)")
```

#### `validator.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")

# DEPOIS
usuario = os.getenv("SENIOR_USER_EXECUTE")
senha   = os.getenv("SENIOR_PASS_EXECUTE")
if not usuario or not senha:
    print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)", flush=True)
    return
```

#### `validator_hitl.py`

```python
# ANTES
usuario = os.getenv("SENIOR_USER")
senha   = os.getenv("SENIOR_PASS")
if not usuario or not senha:
    print("ERRO: Credenciais ausentes no .env", flush=True)

# DEPOIS
usuario = os.getenv("SENIOR_USER_EXECUTE")
senha   = os.getenv("SENIOR_PASS_EXECUTE")
if not usuario or not senha:
    print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)", flush=True)
```

#### `CIL/main_cil.py`

```python
# ANTES
SENIOR_USER = os.getenv("SENIOR_USER")
SENIOR_PASS = os.getenv("SENIOR_PASS")

# DEPOIS
SENIOR_USER = os.getenv("SENIOR_USER_EXECUTE")
SENIOR_PASS = os.getenv("SENIOR_PASS_EXECUTE")
```

#### `.env.example`

```dotenv
# ANTES
SENIOR_USER=email@tenant.com.br
SENIOR_PASS=password123

# DEPOIS
# Credenciais do tenant de CAPTURA (usado por capture.py, capture_dual_output.py,
# capture_semantic.py e capture_adapter.py)
SENIOR_USER_CAPTURE=email@tenant-captura.com.br
SENIOR_PASS_CAPTURE=password_captura

# Credenciais do tenant de EXECUÇÃO (usado por main.py, validator.py,
# validator_hitl.py e main_cil.py)
SENIOR_USER_EXECUTE=email@tenant-execucao.com.br
SENIOR_PASS_EXECUTE=password_execucao
```

#### `tests/test_capture_adapter.py`

Os testes `test_senior_x_credenciais_de_env` e `test_senior_x_credenciais_nao_hardcoded` devem ser atualizados para usar `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`:

```python
# ANTES
def test_senior_x_credenciais_de_env(monkeypatch):
    monkeypatch.setenv("SENIOR_USER", "usuario_teste")
    monkeypatch.setenv("SENIOR_PASS", "senha_teste")
    creds = SeniorXAdapter().obter_credenciais()
    assert creds["usuario"] == "usuario_teste"
    assert creds["senha"] == "senha_teste"

# DEPOIS
def test_senior_x_credenciais_de_env(monkeypatch):
    monkeypatch.setenv("SENIOR_USER_CAPTURE", "usuario_teste")
    monkeypatch.setenv("SENIOR_PASS_CAPTURE", "senha_teste")
    creds = SeniorXAdapter().obter_credenciais()
    assert creds["usuario"] == "usuario_teste"
    assert creds["senha"] == "senha_teste"
```

---

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não corrigido (exploratory); depois, verificar que o fix funciona (fix checking) e que nada quebrou (preservation checking).

---

### Exploratory Bug Condition Checking

**Goal:** Demonstrar o bug no código não corrigido e confirmar a análise de causa raiz.

**Bug 1 — Test Plan:**

Simular desconexão WebSocket com processo ativo e verificar que `processo_atual` continua rodando após o disconnect.

**Test Cases:**

1. **Disconnect com processo ativo**: Iniciar um processo mock, conectar um WebSocket, desconectar — verificar que `processo_atual.returncode` ainda é `None` (processo não foi terminado). Deve falhar no código não corrigido.
2. **Disconnect sem processo ativo**: Desconectar sem processo ativo — verificar que nenhum erro é lançado. Deve passar em ambas as versões.
3. **Disconnect com múltiplos clientes**: Dois clientes conectados, um desconecta — verificar que o processo continua. Deve passar em ambas as versões.

**Expected Counterexamples (código não corrigido):**

- `processo_atual.returncode is None` após o último cliente desconectar com processo ativo — confirma que o processo não foi encerrado.

**Bug 2 — Test Plan:**

Verificar que `SeniorXAdapter().obter_credenciais()` retorna `SENIOR_USER` / `SENIOR_PASS` no código não corrigido.

**Test Cases:**

1. **Adapter retorna variável errada**: Setar `SENIOR_USER_CAPTURE=capture_user` e `SENIOR_USER=old_user`, chamar `obter_credenciais()` — verificar que retorna `old_user` (bug). Deve falhar no código corrigido.
2. **Módulo de captura usa variável errada**: Verificar via inspeção de código que `capture.py` lê `SENIOR_USER` em vez de `SENIOR_USER_CAPTURE`.

---

### Fix Checking

**Goal:** Verificar que para todos os inputs onde a bug condition é verdadeira, o código corrigido produz o comportamento esperado.

**Bug 1:**

```
FOR ALL event WHERE isBugCondition_Disconnect(event) DO
  websocket_status_fixed(event)
  ASSERT processo_atual.returncode IS NOT None  // processo foi terminado
  ASSERT estado_servidor["ocupado"] == False
  ASSERT estado_servidor["erro"] == "Execução interrompida: navegador fechado."
  ASSERT processo_atual IS None
END FOR
```

**Bug 2:**

```
FOR ALL module WHERE isBugCondition_Tenant(module) DO
  IF module IN [capture.py, capture_dual_output.py, capture_semantic.py, capture_adapter.py] THEN
    ASSERT credentials_used == (SENIOR_USER_CAPTURE, SENIOR_PASS_CAPTURE)
  ELSE IF module IN [main.py, validator.py, validator_hitl.py, main_cil.py] THEN
    ASSERT credentials_used == (SENIOR_USER_EXECUTE, SENIOR_PASS_EXECUTE)
  END IF
END FOR
```

---

### Preservation Checking

**Goal:** Verificar que para todos os inputs onde a bug condition é falsa, o código corrigido produz o mesmo resultado que o original.

**Bug 1:**

```
FOR ALL event WHERE NOT isBugCondition_Disconnect(event) DO
  // active_connections não vazio OU processo_atual é None
  ASSERT websocket_status_original(event) == websocket_status_fixed(event)
END FOR
```

**Bug 2:**

```
FOR ALL module WHERE NOT isBugCondition_Tenant(module) DO
  // módulos que não leem SENIOR_USER/SENIOR_PASS
  ASSERT module_behavior_original == module_behavior_fixed
END FOR
```

**Testing Approach:** Property-based testing é recomendado para preservation checking do Bug 1 porque:
- Gera muitos cenários de conexão/desconexão automaticamente.
- Cobre edge cases como múltiplos clientes, reconexões rápidas, e processo `None`.
- Garante que a invariante "processo continua com clientes ativos" é preservada para qualquer combinação de estado.

---

### Unit Tests

**Bug 1:**
- Testar `websocket_status` com `active_connections` vazio e `processo_atual` ativo → processo encerrado.
- Testar `websocket_status` com `active_connections` não vazio → processo não encerrado.
- Testar `websocket_status` com `processo_atual = None` → nenhum erro lançado.
- Testar que `_set_estado()` é chamado com os parâmetros corretos após encerramento.

**Bug 2:**
- Testar `SeniorXAdapter().obter_credenciais()` com `SENIOR_USER_CAPTURE` setado → retorna valor correto.
- Testar cada módulo de captura: verificar que lê `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`.
- Testar cada módulo de execução: verificar que lê `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`.
- Testar mensagem de erro de cada módulo quando variável ausente → mensagem identifica a variável correta.

---

### Property-Based Tests

**Bug 1 — Preservation:**
- Gerar estados aleatórios de `active_connections` (0 a N clientes) e `processo_atual` (None ou ativo) → verificar que o processo só é encerrado quando `active_connections` fica vazio E `processo_atual` não é `None`.
- Gerar sequências aleatórias de connect/disconnect → verificar que o processo nunca é encerrado enquanto há clientes ativos.

**Bug 2 — Fix:**
- Gerar pares aleatórios de valores para `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE` → verificar que `SeniorXAdapter().obter_credenciais()` sempre retorna exatamente esses valores.
- Gerar pares aleatórios para `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE` → verificar que módulos de execução sempre retornam esses valores.

---

### Integration Tests

**Bug 1:**
- Iniciar captura real via dashboard, fechar o navegador → verificar que o processo filho é encerrado e o estado do servidor reflete o encerramento.
- Iniciar execução de roteiro, fechar o navegador → mesmo comportamento.
- Dois clientes conectados, fechar um → processo continua, segundo cliente ainda recebe broadcasts.

**Bug 2:**
- Configurar `.env` com tenants diferentes para captura e execução → executar captura completa e verificar que o login ocorre no tenant de captura.
- Executar roteiro gerado e verificar que o login ocorre no tenant de execução (tenant limpo).
- Verificar que `validator.py` opera no tenant de execução após o patch.

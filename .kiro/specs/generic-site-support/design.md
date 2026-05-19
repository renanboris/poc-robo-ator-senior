# Design Document — generic-site-support

## Overview

A feature **generic-site-support** completa o desacoplamento do pipeline Senior Training OS
do ERP Senior X, permitindo que qualquer site web seja mapeado, executado e transformado em
artefatos de treinamento sem modificação de código.

O pipeline atual tem três pontos de acoplamento com o Senior X:

1. **Captura** (`capture_variants/capture_dual_output.py`): lê `SENIOR_URL`,
   `SENIOR_USER_CAPTURE` e `SENIOR_PASS_CAPTURE` diretamente, e usa seletores de login
   hardcoded para o portal Senior X.
2. **Execução** (`main.py`): lê `SENIOR_URL`, `SENIOR_USER_EXECUTE` e
   `SENIOR_PASS_EXECUTE` diretamente, com seletores de login hardcoded.
3. **Vision Engine** (`vision_engine.py`): camada 1.5 contém heurísticas específicas para
   componentes Angular/PrimeNG do Senior X (ícones Home, Lixeira, etc.).

A abstração `CaptureAdapter` já existe em `contracts/capture_adapter.py` e define o
protocolo correto. Esta feature implementa um `GenericAdapter` que satisfaz esse protocolo
e refatora os três pontos de acoplamento para consumir a abstração em vez de variáveis de
ambiente hardcoded.

O artefato central (roteiro JSON) permanece inalterado. Nenhuma mudança é feita nos
estágios downstream (SCORM, PDF, Aura DAP, lego_builder) além de garantir que roteiros
gerados de sites genéricos passem nas validações existentes.

---

## Architecture

### Princípio Central

O pipeline já possui a abstração correta (`CaptureAdapter`). O trabalho desta feature é
**completar a implementação** — não redesenhar a arquitetura.

```
┌─────────────────────────────────────────────────────────────────┐
│                        .env                                     │
│  CAPTURE_ADAPTER=generic | senior_x                             │
│  TARGET_URL, TARGET_SYSTEM_NAME, LOGIN_REQUIRED, ...            │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  get_capture_adapter() │  ← contracts/capture_adapter.py
              │  (factory existente)   │
              └────────────┬───────────┘
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
   ┌──────────────────┐      ┌──────────────────────┐
   │  SeniorXAdapter  │      │   GenericAdapter      │  ← NOVO
   │  (existente)     │      │   (a implementar)     │
   └──────────────────┘      └──────────────────────┘
              │                         │
              └────────────┬────────────┘
                           │ CaptureAdapter protocol
                           ▼
         ┌─────────────────────────────────────┐
         │  capture_dual_output.py             │  ← refatorar
         │  main.py                            │  ← refatorar
         │  vision_engine.py                   │  ← refatorar (camada 1.5)
         │  generator_engine.py                │  ← refatorar (prompt)
         └─────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │  Roteiro JSON          │  ← inalterado
              │  (contrato central)    │
              └────────────────────────┘
```

### Fluxo de Decisão do Adapter

```
get_capture_adapter()
  ├── CAPTURE_ADAPTER não definida  → SeniorXAdapter  (comportamento atual preservado)
  ├── CAPTURE_ADAPTER=senior_x      → SeniorXAdapter
  ├── CAPTURE_ADAPTER=generic       → GenericAdapter  (NOVO)
  └── qualquer outro valor          → SeniorXAdapter + WARNING no log
```

### Fluxo de Login no GenericAdapter

```
GenericAdapter.iniciar_sessao(page)
  ├── LOGIN_REQUIRED=false (ou ausente)
  │     └── page.goto(TARGET_URL)
  │         └── aguarda load state
  │             └── injeta radar JavaScript
  │
  └── LOGIN_REQUIRED=true
        ├── valida seletores (LOGIN_SELECTOR_USER, _PASS, _SUBMIT)
        ├── page.goto(TARGET_URL)
        ├── preenche campo usuário (LOGIN_SELECTOR_USER)
        ├── preenche campo senha (LOGIN_SELECTOR_PASS)
        ├── clica submit (LOGIN_SELECTOR_SUBMIT)
        ├── aguarda navegação (timeout 30s)
        └── injeta radar JavaScript
```

### Fluxo de Decisão da Camada 1.5 no vision_engine

```
encontrar_e_clicar(page, acao_tec)
  ├── Camada 0: Brain (sempre)
  ├── Camada 0.5: Menu contexto (sempre)
  ├── Camada 1: Foco nativo (sempre)
  ├── Camada 1.5: Heurísticas Senior X
  │     ├── adapter é SeniorXAdapter → EXECUTA
  │     └── adapter é GenericAdapter ou desconhecido → PULA
  ├── Camada 1_T: Template Matching (sempre)
  ├── Camada 2: Sniper semântico (sempre)
  ├── Camada 3: Seletor hint (sempre)
  ├── Camada 3.5: Coordenadas (sempre)
  ├── Camada 4: Busca frames (sempre)
  └── Camada 5: Gemini Vision (sempre)
```

---

## Components and Interfaces

### 1. `GenericAdapter` — `contracts/capture_adapter.py`

Novo adaptador adicionado ao arquivo existente. Implementa o protocolo `CaptureAdapter`.

```python
class GenericAdapter:
    """
    Adaptador para sites web genéricos.
    Lê toda configuração de variáveis de ambiente.
    Suporta modo sem login (LOGIN_REQUIRED=false) e login genérico (LOGIN_REQUIRED=true).
    """

    @property
    def nome_sistema(self) -> str:
        """Retorna TARGET_SYSTEM_NAME ou 'Site Genérico' como fallback."""
        ...

    @property
    def url_base(self) -> str:
        """Retorna TARGET_URL. Falha com erro descritivo se ausente ou inválida."""
        ...

    def obter_credenciais(self) -> dict:
        """
        Retorna {'usuario': LOGIN_USER, 'senha': LOGIN_PASS}.
        Retorna strings vazias se LOGIN_REQUIRED=false.
        """
        ...

    def obter_seletores_login(self) -> dict:
        """
        Retorna seletores de LOGIN_SELECTOR_USER, _PASS, _SUBMIT.
        Retorna strings vazias se LOGIN_REQUIRED=false.
        """
        ...

    def obter_configuracao_browser(self) -> dict:
        """Retorna configuração padrão sem flags específicas do Senior X."""
        ...

    def login_requerido(self) -> bool:
        """Retorna True se LOGIN_REQUIRED=true (case-insensitive). Default: False."""
        ...

    def validar_configuracao(self) -> None:
        """
        Valida todas as variáveis obrigatórias.
        Levanta SystemExit com mensagem descritiva se inválida.
        Chamado no __init__ para falha rápida antes de abrir o navegador.
        """
        ...
```

**Variáveis de ambiente consumidas:**

| Variável | Obrigatória | Descrição |
|---|---|---|
| `TARGET_URL` | Sim | URL do site alvo (deve iniciar com `http://` ou `https://`) |
| `TARGET_SYSTEM_NAME` | Não | Nome do sistema para prompts de IA (fallback: `"Site Genérico"`) |
| `LOGIN_REQUIRED` | Não | `true` ou `false` (default: `false`) |
| `LOGIN_USER` | Se LOGIN_REQUIRED=true | Usuário para login |
| `LOGIN_PASS` | Se LOGIN_REQUIRED=true | Senha para login |
| `LOGIN_SELECTOR_USER` | Se LOGIN_REQUIRED=true | Seletor CSS do campo de usuário |
| `LOGIN_SELECTOR_PASS` | Se LOGIN_REQUIRED=true | Seletor CSS do campo de senha |
| `LOGIN_SELECTOR_SUBMIT` | Se LOGIN_REQUIRED=true | Seletor CSS do botão de submit |

**Atualização em `get_capture_adapter()`:**

```python
if adapter_name in ("generic", "generico", "generico"):
    return GenericAdapter()
```

### 2. `capture_variants/capture_dual_output.py` — Desacoplamento do Login

**Mudanças cirúrgicas** na função `capturar_cliques_na_tela()`:

```python
# ANTES (hardcoded)
SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/...")
usuario    = os.getenv("SENIOR_USER_CAPTURE")
senha      = os.getenv("SENIOR_PASS_CAPTURE")

# DEPOIS (via adapter)
from contracts.capture_adapter import get_capture_adapter
adapter    = get_capture_adapter()
SENIOR_URL = adapter.url_base          # nome mantido para minimizar diff
usuario    = adapter.obter_credenciais()["usuario"]
senha      = adapter.obter_credenciais()["senha"]
seletores  = adapter.obter_seletores_login()
```

**Bloco de login condicional:**

```python
# Modo sem login (GenericAdapter com LOGIN_REQUIRED=false)
from contracts.capture_adapter import GenericAdapter
if isinstance(adapter, GenericAdapter) and not adapter.login_requerido():
    logger.info(f"[Adapter] Modo sem login ativo. Navegando para: {adapter.url_base}")
    await page.goto(adapter.url_base)
    await page.wait_for_load_state("load", timeout=30_000)
    await injetar_radar_event_driven(page)
else:
    # Fluxo de login existente, usando seletores do adapter
    campo_usr = page.locator(seletores["campo_usuario"]).first
    # ... resto do fluxo de login existente ...
```

**Log de observabilidade** adicionado no início de `capturar_cliques_na_tela()`:

```python
logger.info(f"[Pipeline] Adapter ativo: {type(adapter).__name__} | Sistema: {adapter.nome_sistema}")
```

### 3. `main.py` — Desacoplamento do Login

**Mudanças cirúrgicas** na função `executar_roteiro()`:

```python
# ANTES (hardcoded)
SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/...")
usuario    = os.getenv("SENIOR_USER_EXECUTE")
senha      = os.getenv("SENIOR_PASS_EXECUTE")

# DEPOIS (via adapter)
from contracts.capture_adapter import get_capture_adapter
adapter    = get_capture_adapter()
SENIOR_URL = adapter.url_base
creds      = adapter.obter_credenciais()
usuario    = creds["usuario"]
senha      = creds["senha"]
seletores  = adapter.obter_seletores_login()
```

**Bloco de login condicional** (mesmo padrão da captura):

```python
from contracts.capture_adapter import GenericAdapter
if isinstance(adapter, GenericAdapter) and not adapter.login_requerido():
    logger.info(f"[Adapter] Modo sem login. Navegando para: {adapter.url_base}")
    await page.goto(adapter.url_base)
    await page.wait_for_load_state("load", timeout=30_000)
    # Overlay "Pronto para gravar?" exibido normalmente
else:
    # Fluxo de login existente com seletores do adapter
    campo_usr = page.locator(seletores["campo_usuario"]).first
    # ... resto do fluxo existente ...
```

**Validação de credenciais** adaptada:

```python
# SeniorXAdapter: mantém comportamento atual (sys.exit se ausentes)
# GenericAdapter com LOGIN_REQUIRED=false: não valida credenciais
from contracts.capture_adapter import SeniorXAdapter, GenericAdapter
if isinstance(adapter, SeniorXAdapter):
    if not usuario or not senha:
        print("ERRO: Credenciais de execução ausentes no .env ...")
        sys.exit(1)
elif isinstance(adapter, GenericAdapter) and adapter.login_requerido():
    if not usuario or not senha:
        print("ERRO: LOGIN_REQUIRED=true mas LOGIN_USER/LOGIN_PASS ausentes.")
        sys.exit(1)
```

### 4. `vision_engine.py` — Camada 1.5 Condicional

**Mudança cirúrgica** no início da camada 1.5 dentro de `encontrar_e_clicar()`:

```python
# ── Camada 1.5: Heurísticas Senior X ─────────────────────────────────────
# Ativada APENAS quando SeniorXAdapter está ativo.
from contracts.capture_adapter import get_capture_adapter, SeniorXAdapter

# Avaliado uma vez por sessão (cache em variável de módulo para evitar overhead)
_adapter_ativo = get_capture_adapter()
_usar_heuristica_seniorx = isinstance(_adapter_ativo, SeniorXAdapter)

if _usar_heuristica_seniorx and (is_tag_generica or not label_curto):
    # ... lógica existente da camada 1.5 inalterada ...
```

**Log no primeiro passo** (adicionado no início de `encontrar_e_clicar()`):

```python
# Registra adapter ativo no primeiro passo da sessão
if not hasattr(encontrar_e_clicar, "_adapter_logado"):
    adapter = get_capture_adapter()
    logger.info(f"[Pipeline] Adapter ativo: {type(adapter).__name__} | Sistema: {adapter.nome_sistema}")
    encontrar_e_clicar._adapter_logado = True
```

**Nota de implementação:** O adapter é instanciado uma vez por sessão via `get_capture_adapter()`.
Para evitar overhead de I/O repetido, o resultado é cacheado em uma variável de módulo
`_adapter_cache` inicializada no `_init_db()` ou em um bloco de inicialização de módulo.

### 5. `generator_engine.py` — Prompts Parametrizáveis

**Mudança cirúrgica** na função `gerar_roteiro_ia_sync()`, antes da construção do `prompt_usuario`:

```python
from contracts.capture_adapter import get_capture_adapter, SeniorXAdapter

adapter = get_capture_adapter()
_system_name = os.getenv("TARGET_SYSTEM_NAME", "").strip()

# Substituição de nome de sistema no prompt (apenas para adapter não-SeniorX)
def _adaptar_prompt_sistema(texto: str) -> str:
    """Substitui referências ao Senior X pelo sistema alvo no prompt."""
    if isinstance(adapter, SeniorXAdapter):
        return texto  # preserva prompt original para Senior X
    if not _system_name:
        return texto  # sem substituição se nome não definido
    import re
    return re.sub(r"(?i)\b(Senior\s*X|ERP)\b", _system_name, texto)

# Aplicar ao prompt_usuario antes de enviar ao Gemini
prompt_usuario = _adaptar_prompt_sistema(prompt_usuario)
```

**Inclusão do nome do sistema no contexto do prompt de captura** em `capture_dual_output.py`:

```python
# No prompt enviado ao Gemini para análise de elementos:
sistema_context = f"\nSistema alvo: {adapter.nome_sistema}"
prompt = f"...{sistema_context}\n..."
```

### 6. `.env.example` — Documentação das Novas Variáveis

Bloco a ser adicionado ao `.env.example` existente:

```dotenv
# =========================================================
# Suporte a Sites Genéricos (CAPTURE_ADAPTER=generic)
# =========================================================

# Tipo de adapter: "senior_x" (padrão) ou "generic"
CAPTURE_ADAPTER=senior_x

# URL do site alvo (obrigatória quando CAPTURE_ADAPTER=generic)
# Deve iniciar com http:// ou https://
TARGET_URL=https://meu-sistema.exemplo.com.br

# Nome do sistema para prompts de IA (opcional, fallback: "Site Genérico")
TARGET_SYSTEM_NAME=Meu Sistema ERP

# Requer login automático? "true" ou "false" (padrão: false)
LOGIN_REQUIRED=false

# Credenciais de login (obrigatórias quando LOGIN_REQUIRED=true)
LOGIN_USER=meu_usuario@empresa.com
LOGIN_PASS=minha_senha_aqui

# Seletores CSS para o fluxo de login (obrigatórios quando LOGIN_REQUIRED=true)
# Exemplos de seletores comuns:
LOGIN_SELECTOR_USER=input[type='email']
LOGIN_SELECTOR_PASS=input[type='password']
LOGIN_SELECTOR_SUBMIT=button[type='submit']
```

---

## Data Models

### Protocolo `CaptureAdapter` (existente, sem alteração)

```python
@runtime_checkable
class CaptureAdapter(Protocol):
    @property
    def nome_sistema(self) -> str: ...
    @property
    def url_base(self) -> str: ...
    def obter_credenciais(self) -> dict: ...       # {'usuario': str, 'senha': str}
    def obter_seletores_login(self) -> dict: ...   # {'campo_usuario': str, 'campo_senha': str, 'botao_proximo': str}
    def obter_configuracao_browser(self) -> dict: ... # {'args': list, 'locale': str, 'headless': bool}
```

### Extensão do protocolo para suporte a login condicional

O método `login_requerido()` é adicionado ao `GenericAdapter` mas **não** ao protocolo
`CaptureAdapter` para preservar retrocompatibilidade com `SeniorXAdapter` e `MockAdapter`.
O código que precisa verificar o modo de login usa `isinstance(adapter, GenericAdapter)`.

### Estrutura de configuração do `GenericAdapter`

```python
@dataclass
class GenericAdapterConfig:
    target_url: str           # TARGET_URL (validada: http:// ou https://)
    system_name: str          # TARGET_SYSTEM_NAME (fallback: "Site Genérico")
    login_required: bool      # LOGIN_REQUIRED (default: False)
    login_user: str           # LOGIN_USER (vazio se login_required=False)
    login_pass: str           # LOGIN_PASS (vazio se login_required=False)
    selector_user: str        # LOGIN_SELECTOR_USER
    selector_pass: str        # LOGIN_SELECTOR_PASS
    selector_submit: str      # LOGIN_SELECTOR_SUBMIT
```

### Roteiro JSON — sem alteração de schema

O roteiro JSON permanece com a mesma estrutura. O campo `metadata.nome_aula` refletirá
o nome do sistema alvo via `TARGET_SYSTEM_NAME`, mas o schema não muda:

```json
{
  "metadata": {
    "nome_aula": "...",
    "id_treinamento": "...",
    "gerado_por_ia": true,
    "validado_hitl": false
  },
  "configuracao_gravacao": { ... },
  "passos": [ ... ]
}
```

### Variáveis de ambiente — mapeamento completo

| Variável | Adapter | Obrigatória | Validação |
|---|---|---|---|
| `CAPTURE_ADAPTER` | Ambos | Não | `senior_x`, `generic` ou ausente |
| `TARGET_URL` | Generic | Sim | Deve iniciar com `http://` ou `https://` |
| `TARGET_SYSTEM_NAME` | Generic | Não | Qualquer string; fallback `"Site Genérico"` |
| `LOGIN_REQUIRED` | Generic | Não | `true` ou `false` (case-insensitive); default `false` |
| `LOGIN_USER` | Generic | Se LOGIN_REQUIRED=true | Não vazio |
| `LOGIN_PASS` | Generic | Se LOGIN_REQUIRED=true | Não vazio |
| `LOGIN_SELECTOR_USER` | Generic | Se LOGIN_REQUIRED=true | Não vazio |
| `LOGIN_SELECTOR_PASS` | Generic | Se LOGIN_REQUIRED=true | Não vazio |
| `LOGIN_SELECTOR_SUBMIT` | Generic | Se LOGIN_REQUIRED=true | Não vazio |
| `SENIOR_URL` | SeniorX | Não | URL do Senior X (fallback hardcoded) |
| `SENIOR_USER_CAPTURE` | SeniorX | Sim (captura) | Não vazio |
| `SENIOR_PASS_CAPTURE` | SeniorX | Sim (captura) | Não vazio |
| `SENIOR_USER_EXECUTE` | SeniorX | Sim (execução) | Não vazio |
| `SENIOR_PASS_EXECUTE` | SeniorX | Sim (execução) | Não vazio |

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions
of a system — essentially, a formal statement about what the system should do. Properties
serve as the bridge between human-readable specifications and machine-verifiable correctness
guarantees.*

### Property 1: GenericAdapter satisfaz o protocolo CaptureAdapter

*Para qualquer* combinação válida de variáveis de ambiente com `CAPTURE_ADAPTER=generic` e
`TARGET_URL` definida, a instância retornada por `get_capture_adapter()` deve satisfazer
`isinstance(adapter, CaptureAdapter)` e todos os métodos do protocolo devem retornar os
tipos corretos (`nome_sistema: str`, `url_base: str`, `obter_credenciais(): dict`,
`obter_seletores_login(): dict`, `obter_configuracao_browser(): dict`).

**Validates: Requirements 1.1, 1.2**

---

### Property 2: url_base reflete TARGET_URL sem transformação

*Para qualquer* URL válida (iniciando com `http://` ou `https://`) definida em `TARGET_URL`,
`adapter.url_base` deve retornar exatamente o mesmo valor sem modificação.

**Validates: Requirements 1.3, 6.1**

---

### Property 3: nome_sistema com fallback correto

*Para qualquer* valor de `TARGET_SYSTEM_NAME` — incluindo string não vazia, string vazia
e variável ausente — `adapter.nome_sistema` deve retornar o valor de `TARGET_SYSTEM_NAME`
quando não vazio, e `"Site Genérico"` quando vazio ou ausente.

**Validates: Requirements 1.8**

---

### Property 4: Validação de LOGIN_REQUIRED rejeita valores inválidos

*Para qualquer* string que não seja uma variante de `"true"` ou `"false"`
(case-insensitive) definida em `LOGIN_REQUIRED`, o `GenericAdapter` deve encerrar o
processo com um erro descritivo antes de abrir o navegador.

**Validates: Requirements 1.5, 6.4**

---

### Property 5: Seletores de login usados são os do adapter

*Para qualquer* conjunto de seletores CSS válidos definidos em `LOGIN_SELECTOR_USER`,
`LOGIN_SELECTOR_PASS` e `LOGIN_SELECTOR_SUBMIT`, quando `LOGIN_REQUIRED=true`, o fluxo
de login em `capture_dual_output.py` e `main.py` deve usar exatamente esses seletores
(verificável via mock do Playwright).

**Validates: Requirements 1.7, 2.2, 3.2**

---

### Property 6: Modo sem login não executa nenhuma chamada de autenticação

*Para qualquer* `TARGET_URL` válida com `LOGIN_REQUIRED=false` (ou ausente), o fluxo de
captura e execução não deve realizar nenhuma chamada de `fill()` ou `click()` relacionada
a login — apenas `page.goto(TARGET_URL)` seguido de injeção do radar.

**Validates: Requirements 1.6, 2.4, 3.4, 6.3**

---

### Property 7: Fallback manual ativado para qualquer adapter em caso de falha de login

*Para qualquer* adapter ativo (SeniorXAdapter ou GenericAdapter), quando o login automático
falha (timeout ou erro Playwright), o sistema deve ativar o fallback para login manual,
exibindo mensagem ao usuário e aguardando confirmação — sem diferença de comportamento
entre adapters.

**Validates: Requirements 2.6, 3.6**

---

### Property 8: Dual output preservado independente do adapter

*Para qualquer* adapter ativo, ao final de uma sessão de captura com pelo menos um evento
registrado, o sistema deve produzir tanto o roteiro JSON quanto o shadow JSONL, com a
mesma estrutura de campos independente do adapter.

**Validates: Requirements 2.8**

---

### Property 9: Camada 1.5 pulada para qualquer adapter não-SeniorX

*Para qualquer* elemento com tag genérica (span, div, button, etc.) e qualquer adapter
que não seja `SeniorXAdapter`, a camada 1.5 (Heurísticas Senior X) não deve ser executada
— o sistema deve avançar diretamente para a camada 1_T (Template Matching).

**Validates: Requirements 4.2, 4.5**

---

### Property 10: Camadas 0, 2, 3, 4, 5 preservadas para qualquer adapter

*Para qualquer* adapter ativo e qualquer elemento alvo, as camadas Brain (0), Sniper (2),
Template Matching (1_T), Gemini Vision (5) e Coordenadas (3.5) devem ser tentadas na
ordem definida, sem alteração de comportamento em relação ao adapter.

**Validates: Requirements 4.3**

---

### Property 11: Substituição de nome de sistema no prompt é completa e não afeta SeniorX

*Para qualquer* `TARGET_SYSTEM_NAME` não vazio com `GenericAdapter` ativo, o prompt
enviado ao Gemini não deve conter nenhuma ocorrência de "Senior X" ou "ERP"
(case-insensitive). Simetricamente, *para qualquer* valor de `TARGET_SYSTEM_NAME` com
`SeniorXAdapter` ativo, o prompt deve ser enviado sem nenhuma substituição.

**Validates: Requirements 5.1, 5.3**

---

### Property 12: Roteiro de site genérico satisfaz o contrato estrutural

*Para qualquer* roteiro gerado a partir de um site genérico, `validar_roteiro_ia()` deve
retornar `(True, ...)` e o roteiro deve conter os campos obrigatórios `metadata`,
`configuracao_gravacao` e `passos`, com pelo menos um passo com `is_conclusao: true` e
cada passo com `pedagogia.ancora` e `acoes_tecnicas[].elemento_alvo` presentes.

**Validates: Requirements 7.1, 7.6**

---

### Property 13: Ações de sites genéricos indexadas com campos obrigatórios

*Para qualquer* ação capturada de um site genérico com `intencao_semantica` não vazia,
após `construir_biblioteca()`, a entrada correspondente na `biblioteca_acoes.json` deve
conter os campos `intencao_semantica` (em letras minúsculas), `_source` e
`_versao_biblioteca`.

**Validates: Requirements 7.5**

---

### Property 14: Log de login genérico contém seletores mas não credenciais

*Para qualquer* configuração de login genérico, as mensagens de log emitidas durante o
fluxo de autenticação devem conter os valores de `LOGIN_SELECTOR_USER`,
`LOGIN_SELECTOR_PASS` e `LOGIN_SELECTOR_SUBMIT`, mas não devem conter os valores de
`LOGIN_USER` ou `LOGIN_PASS`.

**Validates: Requirements 8.3**

---

### Property 15: Factory retorna SeniorXAdapter para qualquer valor não reconhecido

*Para qualquer* string definida em `CAPTURE_ADAPTER` que não seja `"generic"` (e suas
variantes) nem `"senior_x"` (e suas variantes), `get_capture_adapter()` deve retornar
uma instância de `SeniorXAdapter` e registrar um aviso no log.

**Validates: Requirements 9.3**

---

### Property 16: Roteiros existentes do SeniorX passam na validação sem modificação

*Para qualquer* roteiro com estrutura válida gerado anteriormente com o `SeniorXAdapter`
(contendo `metadata`, `configuracao_gravacao` e `passos` com `acoes_tecnicas` e
`pedagogia.ancora`), `_validar_roteiro_gravacao()` em `main.py` deve retornar lista vazia
de erros.

**Validates: Requirements 9.6**

---

### Property 17: TARGET_URL inválida é rejeitada antes de abrir o navegador

*Para qualquer* string que não inicie com `http://` ou `https://` definida em
`TARGET_URL`, o `GenericAdapter` deve encerrar o processo com erro descritivo sem abrir
o navegador.

**Validates: Requirements 6.6, 1.4**

---

### Property 18: Variáveis SENIOR_* ausentes não causam erros no modo genérico

*Para qualquer* configuração com `CAPTURE_ADAPTER=generic` e `TARGET_URL` válida, a
ausência das variáveis `SENIOR_URL`, `SENIOR_USER_CAPTURE`, `SENIOR_PASS_CAPTURE`,
`SENIOR_USER_EXECUTE` e `SENIOR_PASS_EXECUTE` não deve causar nenhum erro ou aviso
relacionado a essas variáveis.

**Validates: Requirements 6.5**

---

## Error Handling

### Falhas de Configuração (fail-fast antes de abrir o navegador)

Todas as validações de configuração são executadas no `__init__` do `GenericAdapter` via
`validar_configuracao()`. O padrão é **fail-fast com mensagem descritiva**:

```python
def validar_configuracao(self) -> None:
    erros = []

    # TARGET_URL obrigatória e válida
    url = os.getenv("TARGET_URL", "").strip()
    if not url:
        erros.append("TARGET_URL não definida no .env")
    elif not (url.startswith("http://") or url.startswith("https://")):
        erros.append(f"TARGET_URL inválida: '{url}' (deve iniciar com http:// ou https://)")

    # LOGIN_REQUIRED deve ser true ou false
    login_req_raw = os.getenv("LOGIN_REQUIRED", "false").strip().lower()
    if login_req_raw not in ("true", "false"):
        erros.append(
            f"LOGIN_REQUIRED inválido: '{login_req_raw}' (valores aceitos: 'true' ou 'false')"
        )

    # Seletores obrigatórios quando LOGIN_REQUIRED=true
    if login_req_raw == "true":
        for var in ("LOGIN_SELECTOR_USER", "LOGIN_SELECTOR_PASS", "LOGIN_SELECTOR_SUBMIT"):
            if not os.getenv(var, "").strip():
                erros.append(f"{var} não definida (obrigatória quando LOGIN_REQUIRED=true)")
        for var in ("LOGIN_USER", "LOGIN_PASS"):
            if not os.getenv(var, "").strip():
                erros.append(f"{var} não definida (obrigatória quando LOGIN_REQUIRED=true)")

    if erros:
        msg = "Configuração inválida para CAPTURE_ADAPTER=generic:\n" + "\n".join(
            f"  - {e}" for e in erros
        )
        print(msg, flush=True)
        sys.exit(1)
```

### Falhas de Login em Runtime

| Cenário | Comportamento |
|---|---|
| Seletor de login não encontrado no DOM (timeout 10s) | Log ERROR com seletor e mensagem Playwright; ativa fallback manual |
| Navegação não concluída após submit (timeout 30s) | Log ERROR com mensagem de timeout; ativa fallback manual |
| Fallback manual: usuário não confirma em 60s | `sys.exit(1)` com mensagem de timeout |

### Preservação do Fallback Manual Existente

O bloco de fallback manual existente em `capture_dual_output.py` e `main.py` é preservado
sem alteração. A única mudança é que ele é ativado tanto para falhas do `SeniorXAdapter`
quanto do `GenericAdapter`:

```python
except Exception as e:
    logging.warning(f"O auto-login falhou: {e}")
    print("AVISO: Login automático falhou. Conclua o login manualmente em até 60 segundos!", flush=True)
    try:
        await page.wait_for_load_state("networkidle", timeout=60000)
    except Exception:
        print("ERRO FATAL: Tempo esgotado para login manual.", flush=True)
        await browser.close()
        return
```

### Erros de Seletor em Runtime (vision_engine)

Quando a camada 1.5 é pulada para o `GenericAdapter`, os erros de localização de ícones
mudos (Home, Lixeira) são tratados pelas camadas subsequentes (Sniper, Gemini Vision).
Não há degradação de comportamento — apenas a heurística específica do Senior X não é
tentada.

### Erros de Substituição de Prompt

A função `_adaptar_prompt_sistema()` em `generator_engine.py` é defensiva:

```python
def _adaptar_prompt_sistema(texto: str) -> str:
    try:
        if isinstance(adapter, SeniorXAdapter):
            return texto
        if not _system_name:
            return texto
        return re.sub(r"(?i)\b(Senior\s*X|ERP)\b", _system_name, texto)
    except Exception as e:
        logger.warning(f"[Prompt] Falha na substituição de nome de sistema: {e}. Usando prompt original.")
        return texto  # fail-safe: retorna prompt original
```

---

## Testing Strategy

### Abordagem Dual

Esta feature combina testes unitários baseados em exemplos com testes de propriedade
(property-based testing via **Hypothesis**) para cobrir o espaço de entradas de
configuração e comportamento do adapter.

A biblioteca Hypothesis já está em uso no projeto (evidenciado pelo diretório
`.hypothesis/` com exemplos salvos), portanto não há nova dependência.

### Testes de Propriedade (Hypothesis)

Cada propriedade listada na seção "Correctness Properties" deve ser implementada como
um teste Hypothesis com mínimo de **100 iterações** (`@settings(max_examples=100)`).

**Arquivo:** `tests/test_generic_adapter_properties.py`

**Tag format:** `# Feature: generic-site-support, Property N: <texto>`

Exemplos de estratégias de geração:

```python
from hypothesis import given, settings, strategies as st

# Estratégia para URLs válidas
valid_urls = st.one_of(
    st.builds(lambda path: f"https://example.com/{path}",
              st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")), min_size=1)),
    st.builds(lambda path: f"http://localhost/{path}",
              st.text(min_size=0, max_size=50)),
)

# Estratégia para strings inválidas de LOGIN_REQUIRED
invalid_login_required = st.text().filter(
    lambda s: s.strip().lower() not in ("true", "false", "")
)

# Estratégia para nomes de sistema
system_names = st.one_of(st.just(""), st.none(), st.text(min_size=1, max_size=100))
```

**Propriedades prioritárias para PBT:**

| Property | Estratégia principal | Verificação |
|---|---|---|
| P1: Protocolo satisfeito | URLs válidas × nomes de sistema | `isinstance(adapter, CaptureAdapter)` |
| P2: url_base sem transformação | URLs válidas aleatórias | `adapter.url_base == TARGET_URL` |
| P3: nome_sistema com fallback | Strings aleatórias + vazio + None | Valor correto ou "Site Genérico" |
| P4: LOGIN_REQUIRED inválido rejeitado | Strings não-bool aleatórias | `SystemExit` levantado |
| P5: Seletores usados são os do adapter | Seletores CSS aleatórios | Mock verifica chamadas |
| P6: Modo sem login sem chamadas de auth | URLs válidas | Nenhum `fill()`/`click()` de login |
| P7: Fallback manual universal | Adapters × falhas simuladas | Fallback ativado em todos |
| P11: Substituição completa no prompt | Nomes de sistema aleatórios | Sem "Senior X"/"ERP" no prompt |
| P15: Factory retorna SeniorX para desconhecidos | Strings aleatórias não reconhecidas | `isinstance(result, SeniorXAdapter)` |
| P17: TARGET_URL inválida rejeitada | Strings sem http/https | `SystemExit` levantado |
| P18: Variáveis SENIOR_* ignoradas | Configurações genéricas sem SENIOR_* | Sem erros de ausência |

### Testes de Exemplo (pytest)

**Arquivo:** `tests/test_generic_adapter_examples.py`

Cobrem os critérios classificados como EXAMPLE e INTEGRATION:

```python
# Exemplos de casos de teste
def test_factory_retorna_generic_quando_configurado():
    os.environ["CAPTURE_ADAPTER"] = "generic"
    os.environ["TARGET_URL"] = "https://example.com"
    adapter = get_capture_adapter()
    assert isinstance(adapter, GenericAdapter)

def test_factory_retorna_seniorx_por_padrao():
    os.environ.pop("CAPTURE_ADAPTER", None)
    adapter = get_capture_adapter()
    assert isinstance(adapter, SeniorXAdapter)

def test_modo_sem_login_pula_autenticacao(mock_playwright):
    # Verifica que page.fill() não é chamado quando LOGIN_REQUIRED=false
    ...

def test_log_contem_nome_adapter_no_primeiro_passo(caplog):
    # Verifica que o log INFO contém o nome da classe do adapter
    ...
```

### Testes de Integração

Os critérios 7.2, 7.3 e 7.4 (SCORM, PDF, MP4) são verificados manualmente com um
roteiro de site genérico de exemplo (ex: `https://example.com`), pois requerem
Playwright real e infraestrutura de renderização.

**Plano de teste manual mínimo:**

1. Configurar `.env` com `CAPTURE_ADAPTER=generic`, `TARGET_URL=https://example.com`,
   `LOGIN_REQUIRED=false`
2. Executar captura: verificar que roteiro JSON e shadow JSONL são gerados
3. Executar `lego_builder`: verificar que ações são indexadas com campos obrigatórios
4. Executar `scorm_builder`: verificar ZIP em `scorm_exports/`
5. Executar `pdf_builder`: verificar PDF em `documentacao_pdf/`
6. Verificar que `CAPTURE_ADAPTER=senior_x` (ou ausente) continua funcionando normalmente

### Cobertura de Regressão

Para garantir que o comportamento do Senior X não foi alterado, os testes existentes
devem continuar passando sem modificação. Especificamente:

- `tests/test_lego_builder.py` — indexação de ações
- Qualquer teste que instancie `SeniorXAdapter` ou `get_capture_adapter()` sem
  `CAPTURE_ADAPTER` definido deve retornar `SeniorXAdapter`

### Configuração dos Testes de Propriedade

```python
# conftest.py ou no próprio arquivo de testes
from hypothesis import settings, HealthCheck

settings.register_profile("ci", max_examples=100, suppress_health_check=[HealthCheck.too_slow])
settings.load_profile("ci")
```

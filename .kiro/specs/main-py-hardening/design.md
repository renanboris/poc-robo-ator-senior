# main-py-hardening Bugfix Design

## Overview

Este documento formaliza o design técnico para três bugs confirmados em `main.py`.

- **C-01** — `_estado.json` persiste `caminho_webm` e `timeline[].arquivo` como paths absolutos, expondo a estrutura de diretório local e quebrando portabilidade entre máquinas.
- **C-02** — O dict global `_audio_manifest` é mutado diretamente por múltiplas coroutines em `asyncio.gather()`, criando risco de corrupção silenciosa do manifesto em gravações longas.
- **C-04** — O cálculo de `tempo_corte_segundos` não possui documentação inline, tornando o invariante opaco e quebrável por qualquer desenvolvedor que não conheça o contexto do login híbrido.

A estratégia de fix é cirúrgica: nenhuma refatoração estrutural, apenas as menores alterações seguras que eliminam cada bug sem risco de regressão no pipeline de gravação e renderização.

---

## Glossary

- **Bug_Condition (C)**: Condição que identifica entradas ou estados que manifestam o bug.
- **Property (P)**: Comportamento correto esperado quando a condição de bug é satisfeita.
- **Preservation**: Comportamento existente que NÃO deve ser alterado pelo fix.
- **`executar_roteiro()`**: Função assíncrona em `main.py` que orquestra gravação, geração de áudio e persistência do estado.
- **`renderizar_video_final()`**: Função em `main.py` que lê `_estado.json` e compõe o vídeo final com MoviePy.
- **`gerar_audio()`**: Coroutine em `main.py` que gera ou recupera do cache um arquivo MP3 e escreve em `_audio_manifest`.
- **`_audio_manifest`**: Dict global `dict[str, str]` que mapeia `id_unico → path` dos áudios gerados.
- **`tempo_corte_segundos`**: Delta `tempo_inicio_gravacao - tempo_inicio_contexto`, usado como argumento de `.subclip()` para remover o prefixo de login do vídeo bruto.
- **CWD**: Diretório de trabalho corrente (`os.getcwd()`), raiz de todos os paths relativos do projeto.

---

## Bug Details

### C-01 — Paths Absolutos no `_estado.json`

O bug manifesta-se quando `executar_roteiro()` persiste o estado ao final da gravação. Os valores de `caminho_webm` (retornado por `page.video.path()`) e de `timeline[].arquivo` (construídos com `os.path.join`) são paths absolutos do sistema de ficheiros local. Ao salvar esses valores diretamente no JSON, o arquivo torna-se não-portável e expõe a estrutura de diretório da máquina.

**Formal Specification:**
```
FUNCTION isBugCondition_C01(estado)
  INPUT: estado of type dict  // conteúdo de _estado.json
  OUTPUT: boolean

  RETURN os.path.isabs(estado["caminho_webm"])
         OR EXISTS item IN estado["timeline"]
            WHERE os.path.isabs(item["arquivo"])
END FUNCTION
```

**Exemplos:**
- `caminho_webm = "/home/user/projeto/videos_gerados/abc.webm"` → bug presente
- `caminho_webm = "videos_gerados/abc.webm"` → correto
- `timeline[0]["arquivo"] = "/home/user/projeto/audios_gerados/Aula/audio_passo_1_ancora.mp3"` → bug presente
- `timeline[0]["arquivo"] = "audios_gerados/Aula/audio_passo_1_ancora.mp3"` → correto

---

### C-02 — Race Condition em `_audio_manifest`

O bug manifesta-se quando `asyncio.gather(*tarefas_audio)` executa múltiplas coroutines `gerar_audio()` concorrentemente. Cada coroutine escreve diretamente em `_audio_manifest[id_unico] = ...` sem nenhum mecanismo de sincronização. Embora o GIL do CPython proteja operações atômicas simples, o padrão é frágil e não-determinístico em gravações longas com muitos passos.

**Formal Specification:**
```
FUNCTION isBugCondition_C02(execucao)
  INPUT: execucao of type ExecutionContext
  OUTPUT: boolean

  RETURN execucao.num_coroutines_concorrentes > 1
         AND _audio_manifest IS shared_mutable_global
         AND NOT EXISTS synchronization_mechanism(_audio_manifest)
END FUNCTION
```

**Exemplos:**
- 10 passos com ancora + ações → 10+ coroutines concorrentes → bug presente
- 1 passo com ancora → 1 coroutine → sem risco imediato, mas padrão ainda frágil
- Após fix com `asyncio.Lock()`: escritas serializadas → sem risco

---

### C-04 — Invariante de `tempo_corte_segundos` não documentado

O bug manifesta-se como ausência de documentação inline no cálculo `tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto`. O delta inclui intencionalmente o tempo de login (automático ou manual de até 60s), e esse valor é passado para `.subclip(tempo_corte)` para remover o prefixo do vídeo antes do início real da gravação. Sem esse comentário, qualquer desenvolvedor pode "otimizar" o cálculo e quebrar silenciosamente o corte do vídeo.

**Formal Specification:**
```
FUNCTION isBugCondition_C04(source_code)
  INPUT: source_code of type str
  OUTPUT: boolean

  RETURN "tempo_corte_segundos" IN source_code
         AND NOT has_inline_comment_explaining_login_delta(source_code)
         AND NOT has_inline_comment_linking_to_subclip(source_code)
END FUNCTION
```

---

## Expected Behavior

### Preservation Requirements

**Comportamentos que NÃO devem mudar:**

- `renderizar_video_final()` deve continuar localizando e abrindo o `.webm` corretamente após ler `_estado.json`
- `renderizar_video_final()` deve continuar localizando e abrindo cada `.mp3` da `timeline` corretamente
- `salvar_manifesto_audio()` deve continuar salvando o manifesto JSON com todas as entradas geradas
- `gerar_audio()` com cache hit deve continuar retornando o path sem regenerar o áudio
- O valor numérico de `tempo_corte_segundos` e o comportamento de `.subclip()` devem permanecer idênticos após C-04

**Escopo:**
Todos os inputs que NÃO envolvem persistência de paths ou concorrência de manifesto devem ser completamente inalterados. Isso inclui:
- Lógica de clique e automação Playwright
- Geração de legendas e SRT
- Reprodução de áudio via pygame
- Score engine e cursor engine
- Lógica de login híbrido

---

## Hypothesized Root Cause

### C-01
1. **`page.video.path()` retorna path absoluto**: A API do Playwright retorna o path absoluto do arquivo de vídeo gravado. O código salva esse valor diretamente sem conversão.
2. **`os.path.join()` constrói paths absolutos**: Os paths de áudio são construídos com `os.path.join("audios_gerados", ...)` que, dependendo do CWD, pode produzir paths absolutos ao ser serializado.
3. **Ausência de normalização na serialização**: Não há nenhuma chamada a `os.path.relpath()` antes do `json.dump()`.

### C-02
1. **Dict global mutado sem lock**: `_audio_manifest[id_unico] = ...` é executado diretamente dentro de `gerar_audio()`, que é chamada concorrentemente via `asyncio.gather()`.
2. **Padrão frágil mesmo com GIL**: O GIL protege operações de dict individuais, mas não garante consistência em sequências de operações (check-then-act) que podem intercalar.

### C-04
1. **Ausência de comentário inline**: O cálculo foi implementado corretamente mas sem documentação do invariante, tornando a intenção opaca.
2. **Contexto de login híbrido não óbvio**: O fato de que `tempo_inicio_contexto` é capturado antes do login (que pode levar até 60s manualmente) não é evidente sem conhecimento do fluxo completo.

---

## Correctness Properties

Property 1: Bug Condition C-01 — Paths Relativos no Estado JSON

_For any_ estado persistido em `_estado.json` onde `isBugCondition_C01(estado)` é verdadeiro (i.e., algum path é absoluto), a função `executar_roteiro()` corrigida SHALL persistir `caminho_webm` e todos os `timeline[].arquivo` como paths relativos ao CWD, de modo que `os.path.isabs(valor)` retorne `False` para todos esses campos.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation C-01 — Resolução de Paths na Renderização

_For any_ estado lido de `_estado.json` onde os paths são relativos (isBugCondition_C01 é falso), a função `renderizar_video_final()` corrigida SHALL resolver os paths para absolutos antes de abrir os arquivos, produzindo o mesmo resultado de renderização que produziria com paths absolutos originais.

**Validates: Requirements 3.1, 3.2**

Property 3: Bug Condition C-02 — Manifesto Íntegro Após Gather Concorrente

_For any_ execução onde `isBugCondition_C02(execucao)` é verdadeiro (N > 1 coroutines concorrentes), a versão corrigida de `gerar_audio()` SHALL garantir que `_audio_manifest` contenha exatamente N entradas distintas ao final do `asyncio.gather()`, sem entradas duplicadas ou ausentes.

**Validates: Requirements 2.3**

Property 4: Preservation C-02 — Manifesto Idêntico para Execução Serial

_For any_ execução com uma única coroutine (isBugCondition_C02 é falso), a versão corrigida SHALL produzir um `_audio_manifest` idêntico ao da versão original, preservando o comportamento de cache hit e a estrutura do manifesto.

**Validates: Requirements 3.3, 3.4**

Property 5: Bug Condition C-04 — Comentário Inline Presente

_For any_ leitura do source code de `main.py` onde `isBugCondition_C04(source)` é verdadeiro (comentário ausente), a versão corrigida SHALL conter um comentário inline junto ao cálculo de `tempo_corte_segundos` que explique: (a) que o delta inclui intencionalmente o tempo de login, (b) que o login pode ser automático ou manual de até 60s, e (c) que o valor é usado em `.subclip()` para cortar o prefixo do vídeo.

**Validates: Requirements 2.4**

Property 6: Preservation C-04 — Valor Numérico de `tempo_corte_segundos` Inalterado

_For any_ execução onde o cálculo de `tempo_corte_segundos` é realizado, a versão corrigida SHALL produzir exatamente o mesmo valor numérico que a versão original, pois o fix é exclusivamente documental (adição de comentário).

**Validates: Requirements 3.5**

---

## Fix Implementation

### C-01 — Conversão para Paths Relativos

**Arquivo:** `main.py`

**Localização:** Bloco de persistência do estado ao final de `executar_roteiro()` (~linha onde `json.dump` é chamado com `caminho_webm` e `timeline_audios`)

**Mudanças específicas:**

1. **Converter `caminho_video_webm` para relativo antes de salvar:**
   ```python
   caminho_webm_rel = os.path.relpath(caminho_video_webm)
   ```

2. **Converter cada `arquivo` da timeline para relativo antes de salvar:**
   ```python
   timeline_rel = [
       {**item, "arquivo": os.path.relpath(item["arquivo"])}
       for item in timeline_audios
   ]
   ```

3. **Salvar os valores relativos no JSON:**
   ```python
   json.dump({
       "caminho_webm": caminho_webm_rel,
       "timeline":     timeline_rel,
       "tempo_corte":  tempo_corte_segundos,
   }, f, indent=2)
   ```

4. **Resolver para absoluto ao ler no `--render` e no fluxo padrão:**
   ```python
   st["caminho_webm"] = os.path.abspath(st["caminho_webm"])
   st["timeline"] = [
       {**item, "arquivo": os.path.abspath(item["arquivo"])}
       for item in st["timeline"]
   ]
   ```
   Aplicar nos dois pontos de leitura: bloco `--render` e bloco `else` no `__main__`.

---

### C-02 — Serialização de Escritas com `asyncio.Lock()`

**Arquivo:** `main.py`

**Localização:** Declaração de `_audio_manifest` (topo do módulo) e função `gerar_audio()`

**Mudanças específicas:**

1. **Declarar o lock junto ao manifest global:**
   ```python
   _audio_manifest: dict[str, str] = {}
   _audio_manifest_lock = asyncio.Lock()
   ```

2. **Proteger a escrita em `gerar_audio()` com o lock:**
   ```python
   async with _audio_manifest_lock:
       _audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"
   ```
   Substituir a linha de escrita direta existente.

**Nota:** O lock é `asyncio.Lock()` (não `threading.Lock()`), compatível com o event loop existente e sem overhead de threads.

---

### C-04 — Comentário Inline no Invariante

**Arquivo:** `main.py`

**Localização:** Linha `tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto`

**Mudança específica:**

Substituir a linha simples por bloco comentado:
```python
# INVARIANTE: Este delta captura intencionalmente todo o tempo desde a criação
# do contexto Playwright (tempo_inicio_contexto), incluindo o login automático
# ou o login manual de até 60 s (fallback humano). O valor é passado para
# .subclip(tempo_corte) em renderizar_video_final() para remover o prefixo
# do vídeo bruto antes do início real da gravação do roteiro.
tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto
```

---

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não-corrigido (exploração); depois, verificar o fix e a preservação. Para C-01 e C-02, property-based testing com Hypothesis é recomendado. Para C-04, um teste de exemplo simples sobre o source code é suficiente.

---

### Exploratory Bug Condition Checking

**Goal:** Demonstrar os bugs no código atual antes de aplicar qualquer fix.

**Test Plan:** Escrever testes que exercitem os caminhos de código afetados e assertar as condições de bug. Executar no código NÃO-CORRIGIDO para observar falhas e confirmar a hipótese de root cause.

**Test Cases:**

1. **C-01 — Path absoluto em `caminho_webm`**: Simular o retorno de `page.video.path()` com um path absoluto e verificar que `_estado.json` salvo contém path absoluto (confirma bug).
2. **C-01 — Path absoluto em `timeline`**: Construir uma `timeline_audios` com paths absolutos e verificar que o JSON salvo os preserva (confirma bug).
3. **C-02 — Escrita concorrente sem lock**: Executar 20 coroutines `gerar_audio()` mock concorrentemente e verificar se `_audio_manifest` tem exatamente 20 entradas (pode falhar ou passar dependendo do timing — confirma fragilidade).
4. **C-04 — Ausência de comentário**: Ler o source de `main.py` e assertar que o comentário do invariante NÃO está presente (confirma bug).

**Expected Counterexamples:**
- `os.path.isabs(estado["caminho_webm"])` retorna `True` → C-01 confirmado
- `os.path.isabs(estado["timeline"][0]["arquivo"])` retorna `True` → C-01 confirmado
- `len(_audio_manifest) < 20` após gather concorrente → C-02 confirmado (intermitente)
- Comentário ausente no source → C-04 confirmado

---

### Fix Checking

**Goal:** Verificar que para todos os inputs onde a condição de bug se aplica, a versão corrigida produz o comportamento esperado.

**C-01 Pseudocode:**
```
FOR ALL estado WHERE isBugCondition_C01(estado) DO
  estado_corrigido := executar_roteiro_fixed(estado)
  ASSERT NOT os.path.isabs(estado_corrigido["caminho_webm"])
  ASSERT FOR ALL item IN estado_corrigido["timeline"]:
    NOT os.path.isabs(item["arquivo"])
END FOR
```

**C-02 Pseudocode:**
```
FOR ALL execucao WHERE isBugCondition_C02(execucao) DO
  resultado := asyncio.gather(*tarefas_audio_fixed)
  ASSERT len(_audio_manifest) = execucao.num_coroutines
  ASSERT no_duplicate_keys(_audio_manifest)
END FOR
```

**C-04 Pseudocode:**
```
FOR ALL source WHERE isBugCondition_C04(source) DO
  source_corrigido := apply_fix_C04(source)
  ASSERT has_comment_explaining_login_delta(source_corrigido)
  ASSERT has_comment_linking_to_subclip(source_corrigido)
END FOR
```

---

### Preservation Checking

**Goal:** Verificar que para todos os inputs onde a condição de bug NÃO se aplica, a versão corrigida produz o mesmo resultado que a versão original.

**Pseudocode geral:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT original_function(input) = fixed_function(input)
END FOR
```

**Testing Approach:** Property-based testing com Hypothesis para C-01 e C-02 (gera muitos cenários automaticamente). Teste de exemplo para C-04 (apenas verificação de valor numérico).

**Test Cases:**

1. **C-01 Preservation — Renderização com paths relativos**: Dado um `_estado.json` com paths relativos, verificar que `renderizar_video_final()` resolve para absolutos e os arquivos são acessíveis.
2. **C-02 Preservation — Manifesto serial**: Dado 1 coroutine, verificar que o manifesto produzido é idêntico antes e depois do fix.
3. **C-04 Preservation — Valor numérico**: Verificar que `tempo_corte_segundos` calculado é numericamente idêntico antes e depois da adição do comentário.

---

### Unit Tests

- Testar `os.path.relpath()` aplicado a paths absolutos de `caminho_webm` e `timeline[].arquivo`
- Testar `os.path.abspath()` na leitura do estado para resolução correta
- Testar `gerar_audio()` com mock de `asyncio.Lock()` para verificar serialização
- Testar que o source de `main.py` contém o comentário do invariante após o fix

### Property-Based Tests

- Gerar paths absolutos aleatórios para `caminho_webm` e verificar que após fix `os.path.isabs()` retorna `False` (Hypothesis)
- Gerar N aleatório de coroutines concorrentes (N entre 2 e 50) e verificar que `_audio_manifest` tem exatamente N entradas após gather (Hypothesis)
- Gerar pares `(tempo_inicio_contexto, tempo_inicio_gravacao)` aleatórios e verificar que o delta é preservado após o fix de C-04

### Integration Tests

- Executar `executar_roteiro()` com um roteiro mínimo de 2 passos e verificar que `_estado.json` salvo contém apenas paths relativos
- Executar `renderizar_video_final()` lendo o `_estado.json` corrigido e verificar que o vídeo é gerado sem erros de path
- Verificar que o manifesto de áudio tem o número correto de entradas após gravação com múltiplos passos

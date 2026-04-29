# Implementation Plan

- [x] 1. Escrever teste de exploração da condição de bug (Bug Condition)
  - **Property 1: Bug Condition** - Paths Absolutos e Manifesto Sem Lock
  - **CRITICAL**: Este teste DEVE FALHAR no código não-corrigido — a falha confirma que os bugs existem
  - **DO NOT attempt to fix the test or the code when it fails**
  - **GOAL**: Surfaçar contraexemplos que demonstrem os bugs C-01, C-02 e C-04
  - **Scoped PBT Approach**: Para C-01, usar Hypothesis para gerar paths absolutos arbitrários e verificar que `_estado.json` os persiste como absolutos (confirma bug). Para C-02, executar 20 coroutines mock concorrentes e verificar que `_audio_manifest` pode ter menos de 20 entradas. Para C-04, ler o source de `main.py` e assertar que o comentário do invariante NÃO está presente.
  - Criar `tests/test_bugfix_exploration.py`
  - **C-01**: Usar `@given(st.text(min_size=1))` para gerar sufixos de path; construir path absoluto com `os.path.abspath()`; simular `executar_roteiro()` salvando o estado; assertar `os.path.isabs(estado["caminho_webm"]) is True` (confirma bug)
  - **C-01 timeline**: Construir `timeline_audios` com paths absolutos; assertar `os.path.isabs(item["arquivo"]) is True` para cada item (confirma bug)
  - **C-02**: Criar 20 coroutines mock de `gerar_audio()` sem lock; executar com `asyncio.gather()`; assertar que `len(_audio_manifest)` pode ser < 20 ou que o padrão é frágil (confirma ausência de sincronização)
  - **C-04**: Ler `main.py` como string; assertar que `"INVARIANTE"` ou `"login"` NÃO aparece como comentário inline junto a `tempo_corte_segundos` (confirma bug)
  - Executar no código NÃO-CORRIGIDO
  - **EXPECTED OUTCOME**: Testes FALHAM (isso é correto — prova que os bugs existem)
  - Documentar contraexemplos encontrados para entender o root cause
  - Marcar tarefa como completa quando os testes estiverem escritos, executados e as falhas documentadas
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Escrever testes de preservação (ANTES de implementar o fix)
  - **Property 2: Preservation** - Renderização, Manifesto Serial e Valor Numérico de Corte
  - **IMPORTANT**: Seguir metodologia observation-first
  - Criar `tests/test_bugfix_preservation.py`
  - **Observar no código não-corrigido:**
    - `renderizar_video_final()` com paths absolutos válidos abre os arquivos corretamente
    - `gerar_audio()` com 1 coroutine produz exatamente 1 entrada em `_audio_manifest`
    - `tempo_corte_segundos = t2 - t1` produz o delta numérico correto para quaisquer `t1, t2`
  - **C-01 Preservation**: `@given(st.floats(...), st.lists(...))` — dado `_estado.json` com paths já relativos, verificar que `renderizar_video_final()` resolve para absolutos e os arquivos são acessíveis (mock de `VideoFileClip` e `AudioFileClip`)
  - **C-02 Preservation**: `@given(st.integers(min_value=1, max_value=1))` — dado 1 coroutine, verificar que `_audio_manifest` tem exatamente 1 entrada após gather; comportamento de cache hit preservado
  - **C-04 Preservation**: `@given(st.floats(...), st.floats(...))` — para quaisquer `tempo_inicio_contexto` e `tempo_inicio_gravacao`, verificar que `delta = tempo_inicio_gravacao - tempo_inicio_contexto` é numericamente idêntico antes e depois do fix (o fix é puramente documental)
  - Executar no código NÃO-CORRIGIDO
  - **EXPECTED OUTCOME**: Testes PASSAM (confirma comportamento baseline a preservar)
  - Marcar tarefa como completa quando os testes estiverem escritos, executados e passando no código não-corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix C-01 — Converter paths para relativos ao salvar e resolver ao ler

  - [x] 3.1 Converter `caminho_video_webm` e `timeline[].arquivo` para paths relativos antes do `json.dump()`
    - Localizar o bloco `if caminho_video_webm and tempo_corte_segundos is not None` em `executar_roteiro()`
    - Adicionar antes do `json.dump()`:
      ```python
      caminho_webm_rel = os.path.relpath(caminho_video_webm)
      timeline_rel = [
          {**item, "arquivo": os.path.relpath(item["arquivo"])}
          for item in timeline_audios
      ]
      ```
    - Substituir `caminho_video_webm` por `caminho_webm_rel` e `timeline_audios` por `timeline_rel` dentro do dict passado ao `json.dump()`
    - _Bug_Condition: isBugCondition_C01(estado) — os.path.isabs(estado["caminho_webm"]) OR EXISTS item WHERE os.path.isabs(item["arquivo"])_
    - _Expected_Behavior: NOT os.path.isabs(estado["caminho_webm"]) AND FOR ALL item: NOT os.path.isabs(item["arquivo"])_
    - _Preservation: renderizar_video_final() deve continuar localizando e abrindo .webm e .mp3 corretamente_
    - _Requirements: 2.1, 2.2_

  - [x] 3.2 Resolver paths para absolutos ao ler `_estado.json` no bloco `--render`
    - Localizar o bloco `if "--render" in sys.argv:` no `__main__`
    - Após `st = json.load(f)`, adicionar:
      ```python
      st["caminho_webm"] = os.path.abspath(st["caminho_webm"])
      st["timeline"] = [
          {**item, "arquivo": os.path.abspath(item["arquivo"])}
          for item in st["timeline"]
      ]
      ```
    - _Requirements: 3.1, 3.2_

  - [x] 3.3 Resolver paths para absolutos ao ler `_estado.json` no bloco `else` (record + render)
    - Localizar o bloco `else:` no `__main__` que lê `caminho_estado` após `executar_roteiro()`
    - Após `st = json.load(f)`, adicionar a mesma resolução de paths do passo 3.2
    - _Requirements: 3.1, 3.2_

  - [x] 3.4 Verificar que o teste de exploração C-01 agora passa
    - **Property 1: Expected Behavior** - Paths Relativos no Estado JSON
    - **IMPORTANT**: Re-executar o MESMO teste do passo 1 — NÃO escrever novo teste
    - O teste do passo 1 encoda o comportamento esperado (paths relativos)
    - Quando este teste passar, confirma que C-01 está corrigido
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o bug C-01 foi corrigido)
    - _Requirements: 2.1, 2.2_

  - [x] 3.5 Verificar que os testes de preservação C-01 ainda passam
    - **Property 2: Preservation** - Renderização com Paths Relativos
    - **IMPORTANT**: Re-executar os MESMOS testes do passo 2 — NÃO escrever novos testes
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma ausência de regressão em renderização)
    - _Requirements: 3.1, 3.2_

- [x] 4. Fix C-02 — Serializar escritas em `_audio_manifest` com `asyncio.Lock()`

  - [x] 4.1 Declarar `_audio_manifest_lock` junto ao global `_audio_manifest`
    - Localizar a linha `_audio_manifest: dict[str, str] = {}` no topo do módulo (seção UTILITARIOS GERAIS)
    - Adicionar imediatamente abaixo:
      ```python
      _audio_manifest_lock = asyncio.Lock()
      ```
    - _Bug_Condition: isBugCondition_C02 — num_coroutines > 1 AND _audio_manifest is shared mutable global AND no synchronization mechanism_
    - _Requirements: 2.3_

  - [x] 4.2 Proteger a escrita em `_audio_manifest` dentro de `gerar_audio()` com o lock
    - Localizar a linha `_audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"` em `gerar_audio()`
    - Substituir por:
      ```python
      async with _audio_manifest_lock:
          _audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"
      ```
    - _Expected_Behavior: len(_audio_manifest) = num_coroutines AND no_duplicate_keys(_audio_manifest) após asyncio.gather()_
    - _Preservation: gerar_audio() com cache hit deve continuar retornando o path sem regenerar o áudio; salvar_manifesto_audio() deve continuar salvando todas as entradas_
    - _Requirements: 2.3, 3.3, 3.4_

  - [x] 4.3 Verificar que o teste de exploração C-02 agora passa
    - **Property 1: Expected Behavior** - Manifesto Íntegro Após Gather Concorrente
    - **IMPORTANT**: Re-executar o MESMO teste do passo 1 — NÃO escrever novo teste
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que C-02 está corrigido)
    - _Requirements: 2.3_

  - [x] 4.4 Verificar que os testes de preservação C-02 ainda passam
    - **Property 2: Preservation** - Manifesto Idêntico para Execução Serial
    - **IMPORTANT**: Re-executar os MESMOS testes do passo 2 — NÃO escrever novos testes
    - **EXPECTED OUTCOME**: Testes PASSAM (confirma ausência de regressão no manifesto serial e cache hit)
    - _Requirements: 3.3, 3.4_

- [x] 5. Fix C-04 — Adicionar comentário inline documentando o invariante de `tempo_corte_segundos`

  - [x] 5.1 Substituir a linha simples pelo bloco comentado
    - Localizar a linha `tempo_corte_segundos  = tempo_inicio_gravacao - tempo_inicio_contexto` em `executar_roteiro()`
    - Substituir por:
      ```python
      # INVARIANTE: Este delta captura intencionalmente todo o tempo desde a criação
      # do contexto Playwright (tempo_inicio_contexto), incluindo o login automático
      # ou o login manual de até 60 s (fallback humano). O valor é passado para
      # .subclip(tempo_corte) em renderizar_video_final() para remover o prefixo
      # do vídeo bruto antes do início real da gravação do roteiro.
      tempo_corte_segundos  = tempo_inicio_gravacao - tempo_inicio_contexto
      ```
    - _Bug_Condition: isBugCondition_C04 — "tempo_corte_segundos" IN source AND no_inline_comment_explaining_invariant(source)_
    - _Expected_Behavior: has_comment_explaining_login_delta(source) AND has_comment_linking_to_subclip(source)_
    - _Preservation: valor numérico de tempo_corte_segundos e comportamento de .subclip() permanecem idênticos_
    - _Requirements: 2.4, 3.5_

  - [x] 5.2 Verificar que o teste de exploração C-04 agora passa
    - **Property 1: Expected Behavior** - Comentário Inline Presente
    - **IMPORTANT**: Re-executar o MESMO teste do passo 1 — NÃO escrever novo teste
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que C-04 está corrigido)
    - _Requirements: 2.4_

  - [x] 5.3 Verificar que o teste de preservação C-04 ainda passa
    - **Property 2: Preservation** - Valor Numérico de `tempo_corte_segundos` Inalterado
    - **IMPORTANT**: Re-executar os MESMOS testes do passo 2 — NÃO escrever novos testes
    - **EXPECTED OUTCOME**: Teste PASSA (confirma que o fix é puramente documental e não altera o cálculo)
    - _Requirements: 3.5_

- [x] 6. Checkpoint — Garantir que todos os testes passam
  - Executar a suite completa: `pytest tests/test_bugfix_exploration.py tests/test_bugfix_preservation.py -v`
  - Todos os testes de exploração devem PASSAR (bugs corrigidos)
  - Todos os testes de preservação devem PASSAR (sem regressões)
  - Se algum teste falhar, investigar antes de prosseguir
  - Perguntar ao usuário se surgirem dúvidas sobre comportamento esperado

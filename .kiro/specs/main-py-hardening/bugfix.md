# Bugfix Requirements Document

## Introduction

Este documento cobre três bugs confirmados em `main.py` que afetam segurança, confiabilidade e manutenibilidade do pipeline de gravação e renderização do Training OS.

- **C-01 (Segurança):** O arquivo `_estado.json` salvo em `videos_gerados/` contém paths absolutos locais (`caminho_webm` e entradas de `timeline`), expondo estrutura de diretório da máquina caso o diretório seja commitado ou compartilhado.
- **C-02 (Race Condition):** O dict global `_audio_manifest` é mutado diretamente por múltiplas coroutines em `asyncio.gather(*tarefas_audio)`, criando um padrão frágil que pode corromper o manifesto em gravações longas.
- **C-04 (Lógica):** O invariante de `tempo_corte_segundos` não está documentado no código, tornando a lógica de corte do vídeo opaca e quebrável por qualquer desenvolvedor que não conheça o contexto do login híbrido.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN `executar_roteiro()` conclui com sucesso e salva `_estado.json` THEN o sistema persiste `caminho_webm` como path absoluto local (ex: `/home/user/projeto/videos_gerados/abc.webm`) no arquivo JSON

1.2 WHEN `_estado.json` contém entradas de `timeline` THEN o sistema persiste o campo `arquivo` de cada entrada como path absoluto local (ex: `/home/user/projeto/audios_gerados/nome/audio_passo_1_ancora.mp3`)

1.3 WHEN `gerar_audio()` é chamado concorrentemente via `asyncio.gather(*tarefas_audio)` THEN o sistema realiza múltiplas escritas simultâneas no dict global `_audio_manifest` sem nenhum mecanismo de sincronização

1.4 WHEN um desenvolvedor lê o cálculo `tempo_corte_segundos = tempo_inicio_gravacao - tempo_inicio_contexto` THEN o sistema não fornece nenhuma documentação inline explicando por que o delta inclui o tempo de login (até 60s de login manual) e como isso se relaciona com `.subclip(tempo_corte)`

### Expected Behavior (Correct)

2.1 WHEN `executar_roteiro()` conclui com sucesso e salva `_estado.json` THEN o sistema SHALL persistir `caminho_webm` como path relativo (ex: `videos_gerados/abc.webm`) em vez de path absoluto

2.2 WHEN `_estado.json` contém entradas de `timeline` THEN o sistema SHALL persistir o campo `arquivo` de cada entrada como path relativo (ex: `audios_gerados/nome/audio_passo_1_ancora.mp3`) em vez de path absoluto

2.3 WHEN `gerar_audio()` é chamado concorrentemente via `asyncio.gather(*tarefas_audio)` THEN o sistema SHALL garantir que escritas em `_audio_manifest` sejam thread-safe, eliminando o risco de corrupção do manifesto

2.4 WHEN um desenvolvedor lê o cálculo de `tempo_corte_segundos` THEN o sistema SHALL apresentar um comentário inline que documente o invariante: que o delta captura intencionalmente o tempo desde a criação do contexto (incluindo login automático ou manual de até 60s) e que esse valor é usado para cortar o prefixo do vídeo antes do início real da gravação

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `renderizar_video_final()` é chamado com dados lidos de `_estado.json` THEN o sistema SHALL CONTINUE TO localizar e abrir o arquivo `.webm` corretamente para renderização

3.2 WHEN `renderizar_video_final()` itera sobre `timeline` para compor o áudio THEN o sistema SHALL CONTINUE TO localizar e abrir cada arquivo `.mp3` corretamente para composição

3.3 WHEN `salvar_manifesto_audio()` é chamado ao final da gravação THEN o sistema SHALL CONTINUE TO salvar o manifesto JSON com todas as entradas de áudio geradas

3.4 WHEN `gerar_audio()` é chamado para um `id_unico` já existente (cache hit) THEN o sistema SHALL CONTINUE TO retornar o path do arquivo sem regenerar o áudio

3.5 WHEN `tempo_corte_segundos` é calculado e passado para `.subclip()` THEN o sistema SHALL CONTINUE TO cortar o prefixo do vídeo no ponto correto, preservando o comportamento de edição existente

---

## Bug Condition Pseudocode

### C-01 — Paths Absolutos no Estado JSON

```pascal
FUNCTION isBugCondition_C01(estado)
  INPUT: estado of type dict (conteúdo de _estado.json)
  OUTPUT: boolean

  RETURN os.path.isabs(estado["caminho_webm"])
         OR EXISTS item IN estado["timeline"] WHERE os.path.isabs(item["arquivo"])
END FUNCTION

// Property: Fix Checking
FOR ALL estado WHERE isBugCondition_C01(estado) DO
  ASSERT NOT os.path.isabs(estado["caminho_webm"])
  ASSERT FOR ALL item IN estado["timeline"]: NOT os.path.isabs(item["arquivo"])
END FOR

// Property: Preservation Checking
FOR ALL estado WHERE NOT isBugCondition_C01(estado) DO
  ASSERT F(estado) = F'(estado)  // renderização produz o mesmo resultado
END FOR
```

### C-02 — Race Condition em `_audio_manifest`

```pascal
FUNCTION isBugCondition_C02(chamadas_concorrentes)
  INPUT: chamadas_concorrentes of type int
  OUTPUT: boolean

  RETURN chamadas_concorrentes > 1
         AND _audio_manifest is shared mutable global
         AND no synchronization mechanism exists
END FUNCTION

// Property: Fix Checking
FOR ALL execucao WHERE isBugCondition_C02(execucao) DO
  resultado ← asyncio.gather(*tarefas_audio)'
  ASSERT len(_audio_manifest) = numero_esperado_de_entradas
  ASSERT no_data_corruption(_audio_manifest)
END FOR

// Property: Preservation Checking
FOR ALL execucao WHERE NOT isBugCondition_C02(execucao) DO
  ASSERT F(execucao) = F'(execucao)  // manifesto idêntico para execução serial
END FOR
```

### C-04 — Invariante de `tempo_corte_segundos` não documentado

```pascal
FUNCTION isBugCondition_C04(codigo)
  INPUT: codigo of type source
  OUTPUT: boolean

  RETURN "tempo_corte_segundos" IN codigo
         AND no_inline_comment_explaining_invariant(codigo)
END FUNCTION

// Property: Fix Checking
FOR ALL codigo WHERE isBugCondition_C04(codigo) DO
  ASSERT has_comment_explaining_login_delta(codigo)
  ASSERT has_comment_linking_to_subclip_usage(codigo)
END FOR
```

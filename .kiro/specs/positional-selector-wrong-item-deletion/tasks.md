# Implementation Plan

- [x] 1. Escrever teste exploratório da bug condition (ANTES do fix)
  - **Property 1: Bug Condition** - Seletor Posicional Clica Item Errado
  - **CRÍTICO**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste nem o código quando ele falhar**
  - **NOTA**: O teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **OBJETIVO**: Surfaçar contraexemplos que demonstram o bug
  - **Abordagem PBT Escoped**: Para o bug determinístico, escopar a propriedade ao caso concreto de falha para garantir reprodutibilidade
  - Criar mock de `page` com `locator()` retornando elemento cujo `inner_text()` é "Jurídico"
  - Configurar `acao_tec` com `seletor_hint = "item#file_1 .ui-chkbox .ui-chkbox-box"` e `label_curto = "GED 102"`
  - Chamar `encontrar_e_clicar` no código não corrigido e verificar que a ação é executada no elemento errado
  - Testar também: `seletor_hint = "tr:nth-child(2) .btn-delete"`, `label_curto = "Fechar Período"`, elemento na posição tem texto "Abrir Período"
  - Usar `hypothesis` ou `pytest-quickcheck` para gerar variações de índices posicionais (`#file_1`, `#row3`, `tr:nth-child(2)`, `li:nth-of-type(3)`)
  - Executar no código NÃO corrigido
  - **RESULTADO ESPERADO**: Teste FALHA (correto — prova que o bug existe)
  - Documentar contraexemplos encontrados (ex: `"item#file_1 .ui-chkbox .ui-chkbox-box"` clica em "Jurídico" em vez de "GED 102")
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Escrever testes de preservation (ANTES do fix)
  - **Property 2: Preservation** - Seletores Não-Posicionais Inalterados
  - **IMPORTANTE**: Seguir metodologia observation-first
  - Observar: `encontrar_e_clicar` com `seletor_hint = "[aria-label='Excluir']"` executa normalmente no código não corrigido
  - Observar: `seletor_hint = "[id='menu-item-Senior Flow']"` passa pela camada Hint sem validação adicional
  - Observar: `seletor_hint = "[data-testid='item-102']"` (número no valor do atributo, não índice posicional) é tratado normalmente
  - Observar: `seletor_hint = "text='Confirmar'"` não é afetado
  - Observar: `label_curto = ""` com seletor posicional — sem validação de identidade, escala normalmente
  - Usar `hypothesis` para gerar seletores semânticos aleatórios (aria-label, data-testid, text=, #id-semantico) e verificar que `isBugCondition` retorna `False` para todos
  - Escrever propriedade: para todo `acao_tec` onde `NOT isBugCondition(acao_tec)`, o comportamento de `encontrar_e_clicar` é idêntico entre original e corrigido
  - Executar no código NÃO corrigido
  - **RESULTADO ESPERADO**: Testes PASSAM (confirma baseline a preservar)
  - Marcar tarefa como completa quando os testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 3. Fix: validação de identidade para seletores posicionais na camada Hint

  - [x] 3.1 Adicionar `_contem_indice_posicional(seletor: str) -> bool` em `vision_engine.py`
    - Detectar padrões via regex: `#\w*\d+` (ex: `#file_1`, `#row3`), `nth-child\(\d+\)`, `nth-of-type\(\d+\)`, `item#\w+\d+`
    - Retornar `True` se qualquer padrão for encontrado, `False` caso contrário
    - Testar unitariamente com bateria de seletores posicionais e não-posicionais
    - _Bug_Condition: `isBugCondition(acao_tec)` onde `contem_indice_posicional(seletor_hint)` é verdadeiro_
    - _Requirements: 1.1, 2.1_

  - [x] 3.2 Adicionar `_verificar_identidade_elemento(locator, label_curto: str) -> bool` em `vision_engine.py`
    - Tentar `await locator.inner_text(timeout=1000)` — verificar se contém `label_curto` (case-insensitive, strip)
    - Se não encontrar no elemento, tentar `await locator.locator("..").inner_text(timeout=1000)` (elemento pai imediato)
    - Retornar `True` se confirmar identidade, `False` se texto não bater
    - Retornar `True` em caso de exceção (fail-open — não bloquear quando texto não é acessível)
    - Testar unitariamente: texto correspondente, texto diferente, exceção (fail-open)
    - _Expected_Behavior: quando identidade bate → executa; quando não bate → descarta e escala_
    - _Requirements: 2.1, 2.2_

  - [x] 3.3 Modificar bloco da camada 3 (Hint) em `encontrar_e_clicar`
    - Antes de chamar `_tentar_candidato` com `seletor_hint`, verificar `_contem_indice_posicional(seletor_hint)`
    - Se posicional E `label_curto` não vazio E não é tag genérica:
      - Emitir `logger.warning` indicando seletor posicional detectado e que validação de identidade será aplicada
      - Localizar o elemento sem executar a ação (`locator.wait_for(state="visible")`)
      - Chamar `_verificar_identidade_elemento(locator, label_curto)`
      - Se identidade falhar: logar aviso e **não** executar — deixar escalar para próxima camada
      - Se identidade passar: executar normalmente via `_tentar_candidato`
    - Se não posicional: comportamento atual inalterado (sem toque)
    - Se `label_curto` vazio ou tag genérica com seletor posicional: comportamento atual inalterado
    - _Bug_Condition: `isBugCondition(acao_tec)` — `seletor_hint` contém índice posicional_
    - _Expected_Behavior: identidade verificada antes da ação; fallback acionado se não bater_
    - _Preservation: seletores não-posicionais, Brain, Sniper, Frames, Vision e Coordenadas inalterados_
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 3.4, 3.5_

  - [x] 3.4 Verificar que o teste exploratório da bug condition agora passa
    - **Property 1: Expected Behavior** - Seletor Posicional com Identidade Incorreta Descarta e Escala
    - **IMPORTANTE**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado está satisfeito
    - Executar teste exploratório da etapa 1 no código corrigido
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.5 Verificar que os testes de preservation ainda passam
    - **Property 2: Preservation** - Seletores Não-Posicionais Inalterados
    - **IMPORTANTE**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar testes de preservation da etapa 2 no código corrigido
    - **RESULTADO ESPERADO**: Testes PASSAM (confirma ausência de regressões)
    - Confirmar que todos os testes passam após o fix

- [x] 4. Checkpoint — Garantir que todos os testes passam
  - Executar suite completa: testes unitários de `_contem_indice_posicional`, `_verificar_identidade_elemento`, bloco da camada 3
  - Executar Property 1 (bug condition) e Property 2 (preservation) no código corrigido
  - Verificar que o log emite `WARNING` quando seletor posicional é detectado na camada Hint
  - Confirmar que nenhuma outra camada (Brain, Sniper, Frames, Vision, Coordenadas) foi afetada
  - Se algum teste falhar, investigar antes de prosseguir — perguntar ao usuário se necessário

# Implementation Plan

- [x] 1. Escrever teste exploratório de bug condition (ANTES do fix)
  - **Property 1: Bug Condition** - Prioridade de Menu de Contexto Ativo
  - **CRÍTICO**: Este teste DEVE FALHAR no código não corrigido — a falha confirma que o bug existe
  - **NÃO tente corrigir o teste ou o código quando ele falhar**
  - **NOTA**: Este teste codifica o comportamento esperado — ele validará o fix quando passar após a implementação
  - **OBJETIVO**: Surfaçar contraexemplos que demonstrem que o bug existe
  - **Abordagem PBT Scoped**: Para o caso determinístico GED, escopar a propriedade ao caso concreto: DOM com elemento "Nova Pasta" na toolbar + `.p-contextmenu` visível com `role=menuitem` "Nova Pasta"
  - Criar DOM simulado com Playwright contendo: (a) botão "Nova Pasta" na tela principal, (b) overlay `.p-contextmenu` visível com item de mesmo texto
  - Chamar `encontrar_e_clicar` no código não corrigido com `label_curto="Nova Pasta"`
  - Verificar que o elemento clicado NÃO está dentro do `.p-contextmenu` (confirma root cause — Sniper sem escopo)
  - Testar também com Brain pré-populado com seletor `text="Renomear"` apontando para tela principal + menu ativo (confirma root cause — Brain sem consciência de overlay)
  - Verificar que `.p-contextmenu` permanece visível após o clique errado (confirma consequência 1.4)
  - Executar teste no código NÃO corrigido
  - **RESULTADO ESPERADO**: Teste FALHA (correto — prova que o bug existe)
  - Documentar contraexemplos encontrados (ex: "encontrar_e_clicar clicou em button.toolbar-nova-pasta em vez de .p-contextmenu >> role=menuitem")
  - Marcar tarefa como completa quando o teste estiver escrito, executado e a falha documentada
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 2. Escrever testes de preservação (ANTES do fix)
  - **Property 2: Preservation** - Comportamento sem Menu de Contexto Ativo
  - **IMPORTANTE**: Seguir metodologia observation-first
  - Observar: `encontrar_e_clicar` com clique simples em botão da tela principal sem menu ativo funciona normalmente no código não corrigido
  - Observar: Brain com memória válida é acionado como primeira estratégia quando `contextMenuIsActive=False`
  - Observar: `clique_direito` em si é executado normalmente sem alteração
  - Observar: `role=menuitem` em menus de navegação fixos (sidebar, topbar) funciona normalmente
  - Escrever property-based tests: para todo `AcaoTecnica` onde `isBugCondition` retorna `False` (sem menu de contexto ativo), o comportamento de `encontrar_e_clicar` deve ser idêntico ao original
  - Gerar variações de `tipo_elemento`, `acao`, `label_curto` e estado do DOM sem menu ativo
  - Verificar que os testes PASSAM no código não corrigido (confirma baseline a preservar)
  - Marcar tarefa como completa quando os testes estiverem escritos, executados e passando no código não corrigido
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

- [x] 3. Fix — Prioridade de Menu de Contexto no `encontrar_e_clicar`

  - [x] 3.1 Implementar função auxiliar `_detectar_menu_contexto_ativo`
    - Adicionar em `vision_engine.py` função que verifica seletores conhecidos de menu de contexto
    - Seletores a verificar: `.p-contextmenu`, `[role="menu"]`, `.context-menu`, `ul[class*="menu"]`, `.p-menu-list`
    - Retornar o `Locator` do primeiro menu visível encontrado, ou `None` se nenhum estiver ativo
    - Usar `timeout=300` para não penalizar o caminho feliz (sem menu ativo)
    - _Bug_Condition: `contextMenuIsActive(page)` — parte (a) de `isBugCondition`_
    - _Requirements: 2.1_

  - [x] 3.2 Implementar função auxiliar `_buscar_em_escopo_menu`
    - Adicionar em `vision_engine.py` função que localiza o elemento dentro do container do menu
    - Estratégias em ordem de confiança: `get_by_role("menuitem", name=label_curto)`, `get_by_text(label_curto, exact=True)`, `locator(":has-text(label_curto)").last`
    - Todas as estratégias prefixadas com `menu_locator` (escopo restrito ao container do menu)
    - Retornar o seletor usado em caso de sucesso, ou `None` se não encontrado
    - _Expected_Behavior: `elementClickedIsInsideContextMenu(result) = True`_
    - _Requirements: 2.3_

  - [x] 3.3 Inserir camada 0.5 no orquestrador `encontrar_e_clicar`
    - Inserir verificação de menu de contexto ativo ANTES da cascata existente (após Brain, antes de Foco Nativo)
    - Se `_detectar_menu_contexto_ativo` retornar locator: chamar `_buscar_em_escopo_menu`
    - Se elemento encontrado no menu: registrar sucesso no Brain e retornar `True`
    - Se elemento NÃO encontrado no menu: logar warning e escalar direto para Gemini Vision (camada 5) — NÃO acionar Sniper na tela principal coberta pelo overlay
    - Quando `contextMenuIsActive=False`: camada 0.5 é transparente, cascata original não é alterada
    - _Bug_Condition: `isBugCondition(X)` — as três condições (a), (b), (c) do pseudocódigo_
    - _Expected_Behavior: `contextMenuIsDismissedAfterClick(page) = True` após clique no item correto_
    - _Preservation: toda a cascata Brain → Foco Nativo → Sniper → Hint → Frames → Gemini → Coordenadas permanece inalterada quando `contextMenuIsActive=False`_
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 3.4 Modificar Brain (camada 0) para consciência de overlay
    - Quando `contextMenuIsActive=True`, verificar se o seletor memorizado contém prefixo de menu de contexto
    - Se o seletor memorizado não contém prefixo de menu (ex: `text="Nova Pasta"` apontando para toolbar), pular o Brain e deixar a camada 0.5 tratar
    - Preservar comportamento original do Brain quando `contextMenuIsActive=False`
    - _Bug_Condition: parte (b) de `isBugCondition` — Brain sem consciência de overlay_
    - _Requirements: 2.2, 3.3_

  - [x] 3.5 Verificar que o teste exploratório de bug condition agora passa
    - **Property 1: Expected Behavior** - Prioridade de Menu de Contexto Ativo
    - **IMPORTANTE**: Re-executar o MESMO teste da tarefa 1 — NÃO escrever novo teste
    - O teste da tarefa 1 codifica o comportamento esperado
    - Quando este teste passar, confirma que o comportamento esperado está satisfeito
    - Executar teste exploratório de bug condition do passo 1
    - **RESULTADO ESPERADO**: Teste PASSA (confirma que o bug foi corrigido)
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 3.6 Verificar que os testes de preservação ainda passam
    - **Property 2: Preservation** - Comportamento sem Menu de Contexto Ativo
    - **IMPORTANTE**: Re-executar os MESMOS testes da tarefa 2 — NÃO escrever novos testes
    - Executar property-based tests de preservação do passo 2
    - **RESULTADO ESPERADO**: Testes PASSAM (confirma ausência de regressões)
    - Confirmar que toda a cascata existente continua funcionando para ações sem menu de contexto ativo

- [x] 4. Checkpoint — Garantir que todos os testes passam
  - Executar suite completa: teste de bug condition (passo 1) + testes de preservação (passo 2)
  - Verificar que nenhum roteiro existente sem menus de contexto foi afetado
  - Confirmar que o fluxo GED completo funciona: `clique_direito` em pasta → menu abre → clicar em "Nova Pasta" → pasta criada
  - Confirmar que `clique_direito` em arquivo → menu abre → "Renomear" → campo de renomeação ativado
  - Perguntar ao usuário se houver dúvidas antes de fechar

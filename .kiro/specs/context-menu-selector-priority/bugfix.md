# Bugfix Requirements Document

## Introduction

Quando o robô executa uma ação de `clique_direito`, o menu de contexto abre corretamente sobre a tela principal. Porém, ao tentar localizar a opção do menu na etapa seguinte, o sistema (`vision_engine.py`) encontra o mesmo texto na tela principal subjacente — que está coberta pelo overlay do menu — e clica nesse elemento errado, ignorando o menu de contexto visível. O resultado é que a opção do menu nunca é acionada, o fluxo falha silenciosamente ou executa a ação errada, e o menu permanece aberto bloqueando a interface.

O impacto é direto: qualquer roteiro que dependa de menus de contexto (ex: criar pasta, renomear, excluir via botão direito no GED) falha na etapa imediatamente após o `clique_direito`.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o robô executa uma ação de `clique_direito` em um elemento e um menu de contexto é exibido como overlay THEN o sistema localiza o texto da opção do menu na tela principal subjacente (por baixo do overlay) e clica nesse elemento, ignorando o menu de contexto sobreposto

1.2 WHEN o Brain (`brain.db`) possui memória de seletor para uma intenção cujo texto também existe na tela principal THEN o sistema usa esse seletor memorizado para encontrar o elemento na tela principal, sem verificar se um menu de contexto está ativo e deve ter prioridade

1.3 WHEN o Sniper semântico gera candidatos por `text=`, `role=menuitem`, `aria-label` ou `get_by_text` para uma opção de menu de contexto THEN o sistema retorna o primeiro elemento visível que corresponde ao texto, podendo ser o elemento da tela principal em vez do item do menu sobreposto

1.4 WHEN o clique errado é executado na tela principal (em vez do item do menu) THEN o menu de contexto permanece aberto na tela, bloqueando interações subsequentes e deixando a interface em estado inconsistente

### Expected Behavior (Correct)

2.1 WHEN o robô tenta localizar um elemento e um menu de contexto está ativo como overlay na tela THEN o sistema SHALL restringir a busca ao escopo do menu de contexto antes de buscar na tela principal

2.2 WHEN o Brain possui memória de seletor para uma intenção e um menu de contexto está ativo THEN o sistema SHALL verificar primeiro se o elemento memorizado existe dentro do menu de contexto ativo antes de tentar o seletor na tela principal

2.3 WHEN o Sniper semântico gera candidatos para uma ação cujo `tipo_elemento` é `menu_item` ou cuja `intencao_semantica` indica uma opção de menu de contexto THEN o sistema SHALL priorizar elementos contidos em seletores de menu de contexto conhecidos (ex: `.p-contextmenu`, `[role="menu"]`, `.context-menu`, `ul[class*="menu"]`) antes de buscar no DOM geral

2.4 WHEN nenhum elemento correspondente é encontrado dentro do escopo do menu de contexto ativo THEN o sistema SHALL escalar para as camadas seguintes de fallback sem clicar em elementos da tela principal que estejam cobertos pelo overlay

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o robô executa uma ação de clique simples em um elemento da tela principal sem nenhum menu de contexto ativo THEN o sistema SHALL CONTINUE TO localizar e clicar no elemento usando a cascata de estratégias existente (Brain → Foco Nativo → Sniper → Hint → Frames → Gemini → Coordenadas)

3.2 WHEN o robô executa uma ação de `clique_direito` para abrir o menu de contexto THEN o sistema SHALL CONTINUE TO executar o clique direito normalmente sem alteração no comportamento atual

3.3 WHEN o Brain possui memória válida de seletor para uma intenção sem menu de contexto ativo THEN o sistema SHALL CONTINUE TO usar essa memória como primeira estratégia de localização

3.4 WHEN o Sniper semântico localiza um elemento por `role=menuitem` em um menu de navegação fixo (não um menu de contexto overlay) THEN o sistema SHALL CONTINUE TO clicar nesse elemento normalmente

3.5 WHEN o Gemini Vision é acionado como fallback e identifica coordenadas de um item de menu de contexto visível na screenshot THEN o sistema SHALL CONTINUE TO usar essas coordenadas para executar o clique

3.6 WHEN múltiplos frames estão presentes na página e o elemento alvo está em um iframe THEN o sistema SHALL CONTINUE TO buscar em todos os frames como camada de fallback

---

## Bug Condition (Pseudocódigo)

```pascal
FUNCTION isBugCondition(X)
  INPUT: X de tipo AcaoTecnica
  OUTPUT: boolean

  // O bug ocorre quando:
  // (a) existe um menu de contexto ativo como overlay na tela, E
  // (b) o texto/label do elemento alvo também existe na tela principal subjacente
  RETURN contextMenuIsActive(page) AND
         elementExistsInMainPage(X.elemento_alvo.label_curto) AND
         NOT searchScopedToContextMenu(X)
END FUNCTION
```

```pascal
// Property: Fix Checking — Prioridade de Menu de Contexto
FOR ALL X WHERE isBugCondition(X) DO
  result ← encontrar_e_clicar'(page, X)
  ASSERT elementClickedIsInsideContextMenu(result) AND
         contextMenuIsDismissedAfterClick(page)
END FOR
```

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT encontrar_e_clicar(page, X) = encontrar_e_clicar'(page, X)
END FOR
```

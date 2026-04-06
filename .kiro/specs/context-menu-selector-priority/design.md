# Context Menu Selector Priority — Bugfix Design

## Overview

Quando o robô executa um `clique_direito` e um menu de contexto (overlay) é exibido, a etapa seguinte de localização falha silenciosamente: o `encontrar_e_clicar` em `vision_engine.py` encontra o texto da opção do menu na tela principal subjacente — coberta pelo overlay — e clica nesse elemento errado. O menu permanece aberto, bloqueando a interface.

A correção consiste em introduzir uma camada de detecção de menu de contexto ativo **antes** das camadas existentes (Brain, Sniper, Hint), restringindo o escopo de busca ao overlay do menu quando ele estiver presente. Nenhuma camada existente será removida; apenas uma pré-verificação de escopo é inserida no orquestrador `encontrar_e_clicar`.

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug — existe um menu de contexto ativo como overlay E o label do elemento alvo também existe na tela principal subjacente E a busca não está restrita ao escopo do menu.
- **Property (P)**: O comportamento correto esperado — quando o bug condition é verdadeiro, o clique deve ocorrer dentro do menu de contexto ativo, e o menu deve ser dispensado após o clique.
- **Preservation**: O comportamento existente que não deve ser alterado — toda a cascata de estratégias (Brain → Foco Nativo → Sniper → Hint → Frames → Gemini → Coordenadas) para ações sem menu de contexto ativo.
- **`encontrar_e_clicar`**: Função orquestradora em `vision_engine.py` que roteia a tentativa pelas 7 camadas de fallback.
- **`_gerar_candidatos`**: Função em `vision_engine.py` que produz a lista de `TentativaLocalizacao` para o Sniper semântico.
- **`_tentar_candidato`**: Função em `vision_engine.py` que tenta localizar e executar a ação em um candidato específico.
- **`contextMenuIsActive`**: Condição que indica que um overlay de menu de contexto está visível na página (detectável via seletores conhecidos como `.p-contextmenu`, `[role="menu"]`).
- **Seletores de menu de contexto conhecidos**: `.p-contextmenu`, `[role="menu"]`, `.context-menu`, `ul[class*="menu"]`, `.p-menu-list`.

## Bug Details

### Bug Condition

O bug se manifesta quando um menu de contexto está ativo como overlay na tela E o label do elemento alvo (ex: "Nova Pasta") também existe na tela principal subjacente. O `encontrar_e_clicar` não verifica a presença do overlay antes de iniciar a cascata de busca, então o Sniper (ou o Brain) encontra e clica no elemento da tela principal em vez do item do menu.

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X de tipo AcaoTecnica
  OUTPUT: boolean

  // O bug ocorre quando:
  // (a) existe um menu de contexto ativo como overlay na tela, E
  // (b) o texto/label do elemento alvo também existe na tela principal subjacente, E
  // (c) a busca não está restrita ao escopo do menu de contexto
  RETURN contextMenuIsActive(page)
         AND elementExistsInMainPage(X.elemento_alvo.label_curto)
         AND NOT searchScopedToContextMenu(X)
END FUNCTION
```

```
FUNCTION contextMenuIsActive(page)
  SELETORES = ['.p-contextmenu', '[role="menu"]', '.context-menu',
               'ul[class*="menu"]', '.p-menu-list']
  FOR EACH sel IN SELETORES DO
    IF page.locator(sel).is_visible() THEN
      RETURN True
    END IF
  END FOR
  RETURN False
END FUNCTION
```

### Examples

- **Caso GED — Nova Pasta**: Robô faz `clique_direito` em uma pasta. Menu de contexto abre com opção "Nova Pasta". Na etapa seguinte, `label_curto="Nova Pasta"` também existe como botão na toolbar da tela principal. O Sniper encontra o botão da toolbar e clica nele. Menu permanece aberto. **Esperado**: clicar em "Nova Pasta" dentro do `.p-contextmenu`.

- **Caso GED — Renomear**: Robô faz `clique_direito` em um arquivo. Menu abre com "Renomear". O texto "Renomear" existe em outro contexto da tela. O Brain pode ter memorizado o seletor do elemento da tela principal. **Esperado**: verificar primeiro se "Renomear" existe dentro do menu ativo antes de usar a memória do Brain.

- **Caso GED — Excluir**: Robô faz `clique_direito`. Menu abre com "Excluir". O Sniper encontra `text="Excluir"` na tela principal (ex: botão de exclusão em massa). Clique errado é executado. **Esperado**: clicar em "Excluir" dentro do escopo do menu de contexto.

- **Edge case — label exclusivo do menu**: `label_curto="Mover para"` existe apenas no menu de contexto, não na tela principal. O bug não ocorre neste caso, mas a nova camada deve funcionar corretamente (encontrar o item no menu e clicar).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Cliques simples em elementos da tela principal sem nenhum menu de contexto ativo devem continuar funcionando exatamente como antes, usando a cascata completa (Brain → Foco Nativo → Sniper → Hint → Frames → Gemini → Coordenadas).
- A ação `clique_direito` em si deve continuar sendo executada normalmente sem alteração.
- O Brain com memória válida de seletor para intenções sem menu de contexto ativo deve continuar sendo a primeira estratégia de localização.
- O Sniper semântico com `role=menuitem` em menus de navegação fixos (não overlay) deve continuar funcionando normalmente.
- O Gemini Vision como fallback com coordenadas de itens de menu visíveis deve continuar funcionando.
- A busca em todos os frames como camada de fallback deve continuar funcionando.

**Scope:**
Todas as ações que NÃO envolvem um menu de contexto overlay ativo devem ser completamente não afetadas por esta correção. Isso inclui:
- Cliques em botões, links, inputs da tela principal.
- Ações de digitação (`digitar_e_enter`, `preencher_campo`).
- Cliques em menus de navegação fixos (sidebar, topbar, breadcrumb).
- Qualquer ação executada quando `contextMenuIsActive(page)` retorna `False`.

## Hypothesized Root Cause

Com base na análise do código em `vision_engine.py`:

1. **Ausência de verificação de escopo no orquestrador**: A função `encontrar_e_clicar` não possui nenhuma lógica para detectar se um menu de contexto está ativo antes de iniciar a cascata. A cascata começa diretamente pelo Brain (camada 0), que pode ter memorizado um seletor da tela principal para a mesma intenção.

2. **Brain sem consciência de contexto de overlay**: `_consultar_cache` retorna o seletor memorizado sem verificar se o elemento está dentro ou fora de um overlay ativo. Se o Brain memorizou `text="Nova Pasta"` apontando para a toolbar, ele tentará esse seletor mesmo com o menu aberto — e pode ter sucesso no elemento errado.

3. **Sniper sem escopo de menu**: `_gerar_candidatos` gera candidatos como `text="Nova Pasta"` e `role=menuitem name='Nova Pasta'` sem prefixar com o escopo do menu de contexto. O `_tentar_candidato` usa `page.get_by_text(...)` ou `page.locator(...)` que busca em todo o DOM, retornando o primeiro elemento visível — que pode ser o da tela principal.

4. **Prioridade de visibilidade sem hierarquia de overlay**: O Playwright considera elementos "visíveis" mesmo quando cobertos por um overlay (a verificação `state="visible"` não garante que o elemento está no topo da pilha de z-index). O elemento da tela principal pode passar no `wait_for(state="visible")` mesmo estando coberto pelo menu.

## Correctness Properties

Property 1: Bug Condition — Prioridade de Menu de Contexto Ativo

_For any_ `AcaoTecnica` onde `isBugCondition` retorna `True` (menu de contexto ativo E label do alvo existe na tela principal E busca não está restrita ao menu), a função `encontrar_e_clicar` corrigida SHALL localizar e clicar no elemento dentro do escopo do menu de contexto ativo, resultando em `elementClickedIsInsideContextMenu(result) = True` e no menu sendo dispensado após o clique.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation — Comportamento sem Menu de Contexto Ativo

_For any_ `AcaoTecnica` onde `isBugCondition` retorna `False` (menu de contexto NÃO está ativo), a função `encontrar_e_clicar` corrigida SHALL produzir o mesmo resultado que a função original, preservando toda a cascata de estratégias existente (Brain → Foco Nativo → Sniper → Hint → Frames → Gemini → Coordenadas) sem alteração de comportamento.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assumindo que a análise de root cause está correta:

**File**: `vision_engine.py`

**Function**: `encontrar_e_clicar` (orquestrador principal)

**Specific Changes**:

1. **Nova função auxiliar `_detectar_menu_contexto_ativo`**: Verifica se algum seletor de menu de contexto conhecido está visível na página. Retorna o locator do menu ativo ou `None`.
   ```
   FUNCTION _detectar_menu_contexto_ativo(page) -> Optional[Locator]
     SELETORES_MENU = [
       '.p-contextmenu', '[role="menu"]', '.context-menu',
       'ul[class*="menu"]', '.p-menu-list'
     ]
     FOR EACH sel IN SELETORES_MENU DO
       loc = page.locator(sel).first
       IF loc.is_visible(timeout=300) THEN
         RETURN loc
       END IF
     END FOR
     RETURN None
   END FUNCTION
   ```

2. **Nova camada 0.5 no orquestrador** (inserida entre Brain e Foco Nativo): Antes de iniciar a cascata completa, verificar se um menu de contexto está ativo. Se sim, tentar localizar o elemento dentro do escopo do menu usando os candidatos do Sniper prefixados com o seletor do menu.
   ```
   // Camada 0.5: Menu de Contexto Ativo (inserida após Brain, antes de Foco Nativo)
   menu_locator = await _detectar_menu_contexto_ativo(page)
   IF menu_locator IS NOT None THEN
     resultado = await _buscar_em_escopo_menu(page, menu_locator, label_curto, acao, valor)
     IF resultado THEN
       _registrar_sucesso_cache(intencao, seletor=resultado)
       RETURN True
     END IF
     // Se não encontrou no menu, NÃO escalar para tela principal
     // (evita clicar em elemento coberto pelo overlay)
     logger.warning("Elemento não encontrado no menu de contexto ativo. Escalando para Gemini.")
     // Pular direto para camada 5 (Gemini Vision) para não clicar na tela coberta
   END IF
   ```

3. **Nova função auxiliar `_buscar_em_escopo_menu`**: Tenta localizar o elemento dentro do escopo do menu de contexto usando estratégias semânticas restritas ao container do menu.
   ```
   FUNCTION _buscar_em_escopo_menu(page, menu_locator, label_curto, acao, valor)
     // Estratégias em ordem de confiança:
     // 1. role=menuitem dentro do menu
     // 2. text= dentro do menu
     // 3. :has-text() dentro do menu
     candidatos_menu = [
       menu_locator.get_by_role("menuitem", name=label_curto),
       menu_locator.get_by_text(label_curto, exact=True),
       menu_locator.locator(f":has-text('{label_curto}')").last,
     ]
     FOR EACH cand IN candidatos_menu DO
       IF cand.is_visible(timeout=500) THEN
         await _executar_acao(cand, page, acao, valor)
         RETURN seletor_usado
       END IF
     END FOR
     RETURN None
   END FUNCTION
   ```

4. **Modificação no Brain (camada 0)**: Quando `contextMenuIsActive` é `True`, o Brain deve verificar se o seletor memorizado está dentro do escopo do menu antes de tentar. Se o seletor não contém prefixo de menu, pular o Brain e deixar a camada 0.5 tratar.

5. **Sem alteração nas camadas 1–6**: As camadas existentes (Foco Nativo, Heurísticas Senior X, Sniper, Hint, Frames, Gemini, Coordenadas) não são modificadas. A camada 0.5 atua como um desvio condicional que só é ativado quando `contextMenuIsActive = True`.

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não corrigido com testes exploratórios; depois, verificar que a correção funciona (fix checking) e que o comportamento existente não foi alterado (preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug no código atual ANTES de implementar a correção. Confirmar ou refutar a análise de root cause.

**Test Plan**: Criar um DOM simulado com Playwright (ou mock) contendo: (a) um elemento com `label_curto` na tela principal, (b) um overlay `.p-contextmenu` visível com um item de mesmo texto. Chamar `encontrar_e_clicar` no código não corrigido e verificar qual elemento foi clicado.

**Test Cases**:
1. **Teste GED Nova Pasta**: DOM com botão "Nova Pasta" na toolbar + `.p-contextmenu` visível com `role=menuitem` "Nova Pasta". Chamar `encontrar_e_clicar` com `label_curto="Nova Pasta"`. **Esperado no código bugado**: clique no botão da toolbar (falha). Confirma root cause 3 (Sniper sem escopo).
2. **Teste Brain com menu ativo**: Pré-popular `brain.db` com seletor `text="Renomear"` apontando para elemento da tela principal. Ativar menu de contexto com "Renomear". Chamar `encontrar_e_clicar`. **Esperado no código bugado**: Brain usa seletor memorizado e clica no elemento errado. Confirma root cause 2.
3. **Teste menu permanece aberto**: Após o clique errado, verificar que `.p-contextmenu` ainda está visível. Confirma consequência 1.4.
4. **Edge case — label exclusivo do menu**: DOM sem duplicata na tela principal. **Esperado**: funciona corretamente mesmo no código bugado (sem regressão neste caso).

**Expected Counterexamples**:
- O elemento clicado não está dentro do `.p-contextmenu` (verificável via `bounding_box` ou `evaluate` para checar ancestral).
- Possíveis causas confirmadas: Sniper sem escopo de menu, Brain sem consciência de overlay.

### Fix Checking

**Goal**: Verificar que para todas as entradas onde `isBugCondition` é verdadeiro, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL X WHERE isBugCondition(X) DO
  result ← encontrar_e_clicar_corrigido(page, X)
  ASSERT elementClickedIsInsideContextMenu(result) = True
  ASSERT contextMenuIsDismissedAfterClick(page) = True
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as entradas onde `isBugCondition` é falso, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL X WHERE NOT isBugCondition(X) DO
  ASSERT encontrar_e_clicar_original(page, X) = encontrar_e_clicar_corrigido(page, X)
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente cobrindo variações de `tipo_elemento`, `acao`, `label_curto` e estado do DOM.
- Captura edge cases que testes manuais podem perder (ex: label vazio, seletor_hint frágil, iframe_hint presente).
- Fornece garantia forte de que o comportamento é preservado para todas as entradas não-bugadas.

**Test Plan**: Observar o comportamento no código não corrigido para cliques simples e outras interações, depois escrever property-based tests capturando esse comportamento.

**Test Cases**:
1. **Preservation — Clique simples sem menu**: Verificar que cliques em botões da tela principal sem menu ativo continuam funcionando identicamente após a correção.
2. **Preservation — Brain sem menu ativo**: Verificar que o Brain continua sendo a primeira estratégia quando não há menu de contexto ativo.
3. **Preservation — clique_direito**: Verificar que a ação `clique_direito` em si não é alterada pela correção.
4. **Preservation — menu de navegação fixo**: Verificar que `role=menuitem` em menus de navegação fixos (sidebar, topbar) não é afetado pela detecção de overlay.
5. **Preservation — Gemini Vision fallback**: Verificar que o fallback Gemini continua funcionando quando todas as camadas anteriores falham (sem menu ativo).

### Unit Tests

- Testar `_detectar_menu_contexto_ativo` com DOM simulado: menu visível retorna locator, menu ausente retorna None, menu presente mas não visível retorna None.
- Testar `_buscar_em_escopo_menu` com container de menu simulado: encontra item por `role=menuitem`, encontra por `text=`, retorna None quando item não existe no menu.
- Testar a lógica de desvio no orquestrador: quando `contextMenuIsActive=True` e item encontrado no menu, retorna True sem acionar Sniper na tela principal.
- Testar edge case: menu ativo mas item não encontrado no menu — deve escalar para Gemini sem clicar na tela principal.

### Property-Based Tests

- Gerar estados aleatórios de DOM (com e sem menu de contexto ativo) e verificar que `isBugCondition` é detectado corretamente.
- Gerar configurações aleatórias de `AcaoTecnica` com `contextMenuIsActive=False` e verificar que o comportamento da função corrigida é idêntico ao original (preservation property).
- Gerar variações de `label_curto` (strings com caracteres especiais, labels longos, labels com espaços) e verificar que a busca no escopo do menu funciona corretamente.
- Testar que para qualquer `acao` diferente de `clique` (ex: `digitar_e_enter`, `clique_direito`, `duplo_clique`) sem menu ativo, o comportamento é preservado.

### Integration Tests

- Teste de fluxo completo GED: `clique_direito` em pasta → menu abre → clicar em "Nova Pasta" → verificar que pasta é criada (menu dispensado, campo de nome ativo).
- Teste de fluxo completo GED: `clique_direito` em arquivo → menu abre → clicar em "Renomear" → verificar que campo de renomeação é ativado.
- Teste de switching de contexto: executar clique simples → depois clique_direito + opção de menu → depois clique simples novamente. Verificar que cada etapa funciona corretamente.
- Teste de regressão: executar roteiro existente sem menus de contexto e verificar que nenhuma etapa é afetada pela correção.

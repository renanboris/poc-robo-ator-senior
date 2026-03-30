# Positional Selector Wrong Item Deletion — Bugfix Design

## Overview

Durante a execução do roteiro "Senior Flow - GED 102", o robô deveria selecionar o
checkbox do item "GED 102" para exclusão em lote. Em vez disso, o seletor posicional
`item#file_1 .ui-chkbox .ui-chkbox-box` apontou para o item "Jurídico" — que ocupava
a posição `file_1` no momento da execução — e a exclusão foi aplicada ao item errado.

A correção consiste em adicionar uma **verificação de identidade** na camada Hint do
`vision_engine.py`: antes de executar a ação, confirmar que o elemento encontrado pelo
seletor posicional contém o texto do `label_curto` ou corresponde à `intencao_semantica`.
Se a verificação falhar, o resultado é descartado e o pipeline escala para o Sniper
semântico ou Gemini Vision.

A mudança é cirúrgica: afeta apenas o bloco da camada 3 (Hint) para seletores
posicionais, sem tocar nas demais camadas nem no contrato do roteiro.

---

## Glossary

- **Bug_Condition (C)**: Condição que ativa o bug — `seletor_hint` contém índice
  posicional (ex: `#file_1`, `:nth-child(2)`) e a camada Hint é acionada sem
  verificar se o elemento encontrado corresponde ao item esperado.
- **Property (P)**: Comportamento correto esperado — quando C é verdadeiro, a camada
  Hint deve verificar a identidade do elemento antes de executar a ação; se a
  identidade não bater, deve descartar e escalar.
- **Preservation**: Comportamento que não deve mudar — seletores não-posicionais
  continuam sendo usados diretamente; o Brain, Sniper, Frames, Vision e Fallback de
  coordenadas permanecem inalterados.
- **`encontrar_e_clicar`**: Orquestrador principal em `vision_engine.py` que roteia
  a tentativa pelas 7 camadas de fallback.
- **`_tentar_candidato`**: Função auxiliar que tenta localizar e clicar em um elemento
  dado um `TentativaLocalizacao`.
- **`seletor_hint`**: Seletor CSS capturado durante o mapeamento, armazenado no campo
  `elemento_alvo.seletor_hint` do roteiro JSON.
- **`label_curto`**: Texto curto identificador do elemento alvo, armazenado em
  `elemento_alvo.label_curto` do roteiro JSON.
- **`intencao_semantica`**: Descrição semântica da ação, usada como chave de memória
  no Brain e como contexto para o Gemini Vision.
- **`_e_seletor_fragil`**: Função que classifica seletores como frágeis (tags genéricas
  sem atributos estáveis). Seletores posicionais passam nesse filtro hoje — esse é o
  gap que o fix endereça.

---

## Bug Details

### Bug Condition

O bug se manifesta quando o `seletor_hint` contém um índice posicional (ex: `item#file_1`,
`tr:nth-child(2)`, `li:nth-of-type(3)`) e a camada Hint é acionada. A função
`encontrar_e_clicar` usa o seletor cegamente via `_tentar_candidato` sem verificar se
o elemento encontrado corresponde ao item esperado pelo roteiro.

**Formal Specification:**

```
FUNCTION isBugCondition(acao_tec)
  INPUT: acao_tec de tipo dict (campo do roteiro JSON)
  OUTPUT: boolean

  seletor := acao_tec["elemento_alvo"]["seletor_hint"]

  RETURN contem_indice_posicional(seletor)

  // contem_indice_posicional(s) retorna True se s corresponde a qualquer padrão:
  //   - #\w*\d+          ex: #file_1, #row3, #item_42
  //   - :nth-child(\d+)  ex: tr:nth-child(2)
  //   - :nth-of-type(\d+) ex: li:nth-of-type(3)
  //   - item#\w+\d+      ex: item#file_1
END FUNCTION
```

### Examples

- **Caso real (bug)**: `seletor_hint = "item#file_1 .ui-chkbox .ui-chkbox-box"`,
  `label_curto = "GED 102"`. Na execução, `file_1` era "Jurídico". O robô clicou em
  "Jurídico" e a exclusão foi aplicada ao item errado.
- **Caso 2**: `seletor_hint = "tr:nth-child(3) .action-btn"`, `label_curto = "Fechar Período"`.
  Se a tabela tiver uma linha a mais no topo, o botão da linha errada é clicado.
- **Caso 3**: `seletor_hint = "li:nth-of-type(2) input[type='checkbox']"`,
  `label_curto = "Logística"`. Se a lista for reordenada, o checkbox errado é marcado.
- **Edge case (sem label)**: `label_curto = ""` ou tag genérica — a verificação de
  identidade não pode ser aplicada; o sistema deve continuar o comportamento atual
  (escalar para Sniper/Vision sem tentar validar).

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Seletores não-posicionais (ex: `[aria-label='Salvar']`, `[id='menu-item-Senior Flow']`,
  `text="Confirmar"`) continuam sendo usados diretamente pela camada Hint sem validação
  adicional.
- O Brain (camada 0) continua sendo consultado primeiro e com prioridade total.
- O Sniper semântico (camada 2) continua operando antes da camada Hint.
- As camadas 4 (Todos os Frames), 5 (Gemini Vision) e 6 (Coordenadas) permanecem
  inalteradas.
- Quando a verificação de identidade passa (elemento correto encontrado), a ação é
  executada normalmente sem degradação de performance.
- Quando `label_curto` está vazio ou é uma tag genérica, a camada Hint continua
  operando sem tentar validação de identidade.

**Scope:**
Todas as ações cujo `seletor_hint` não contém índice posicional devem ser completamente
não afetadas por esta correção. Isso inclui:
- Cliques em menus, botões com `aria-label` ou `data-testid` estáveis.
- Ações de digitação em campos identificados por `placeholder` ou `label`.
- Qualquer ação onde o Sniper semântico já resolve antes de chegar na camada Hint.

---

## Hypothesized Root Cause

Com base na análise do código em `vision_engine.py` (função `encontrar_e_clicar`,
bloco da camada 3):

1. **Ausência de validação de identidade na camada Hint**: O bloco da camada 3 cria
   um `TentativaLocalizacao` com o `seletor_hint` bruto e chama `_tentar_candidato`
   diretamente. Não há nenhuma verificação de que o elemento encontrado corresponde
   ao `label_curto` ou à `intencao_semantica`.

2. **`_e_seletor_fragil` não detecta seletores posicionais como frágeis**: A função
   verifica tags genéricas e ausência de atributos semânticos, mas não classifica
   `#file_1` ou `:nth-child(2)` como frágeis. Portanto, seletores posicionais passam
   pelo filtro e chegam à camada Hint sem restrição.

3. **O Sniper semântico (camada 2) não consegue resolver checkboxes sem texto visível**:
   O seletor `item#file_1 .ui-chkbox .ui-chkbox-box` aponta para um checkbox que não
   tem `aria-label`, `role` ou texto associado ao item pai. O Sniper não tem como
   identificar o item correto sem o contexto do elemento pai — por isso a camada Hint
   é acionada e o bug se manifesta.

4. **Ordem dos itens na lista não é garantida**: A lista do GED pode ser ordenada
   diferentemente entre a captura e a execução (ex: novo item adicionado, ordenação
   alterada pelo usuário). O índice posicional capturado no mapeamento não é estável.

---

## Correctness Properties

Property 1: Bug Condition — Validação de Identidade em Seletores Posicionais

_For any_ `acao_tec` onde `isBugCondition(acao_tec)` é verdadeiro (seletor_hint contém
índice posicional) e `label_curto` não está vazio nem é tag genérica, a função
`encontrar_e_clicar` corrigida SHALL verificar se o elemento encontrado pelo seletor
posicional contém o texto do `label_curto` (ou texto do elemento pai imediato) antes
de executar a ação. Se a verificação falhar, SHALL descartar o resultado e escalar para
a próxima camada de fallback.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Preservation — Seletores Não-Posicionais Inalterados

_For any_ `acao_tec` onde `isBugCondition(acao_tec)` é falso (seletor_hint não contém
índice posicional), a função `encontrar_e_clicar` corrigida SHALL produzir exatamente
o mesmo resultado que a função original, preservando todo o comportamento existente
para seletores semânticos, Brain, Sniper, Frames, Vision e Coordenadas.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

---

## Fix Implementation

### Changes Required

Assumindo que a causa raiz está confirmada:

**File**: `vision_engine.py`

**Function**: `encontrar_e_clicar` (bloco da camada 3 — Seletor Hint Original)

**Specific Changes**:

1. **Adicionar função `_contem_indice_posicional(seletor: str) -> bool`**:
   Detecta padrões posicionais com regex:
   - `#\w*\d+` — IDs com sufixo numérico (ex: `#file_1`, `#row3`)
   - `nth-child\(\d+\)` — seletores nth-child
   - `nth-of-type\(\d+\)` — seletores nth-of-type
   - `item#\w+\d+` — padrão específico do Senior X GED

2. **Adicionar função `_verificar_identidade_elemento(locator, label_curto: str) -> bool`**:
   Tenta extrair o texto visível do elemento ou do elemento pai imediato e verifica se
   contém `label_curto` (case-insensitive, strip). Retorna `True` se confirmar, `False`
   se não confirmar, `True` se não conseguir extrair texto (fail-open para não bloquear
   casos onde o texto não é acessível).

3. **Modificar o bloco da camada 3** em `encontrar_e_clicar`:
   - Antes de chamar `_tentar_candidato` com o `seletor_hint`, verificar se
     `_contem_indice_posicional(seletor_hint)` é verdadeiro.
   - Se sim, e se `label_curto` não estiver vazio e não for tag genérica:
     - Localizar o elemento sem executar a ação.
     - Chamar `_verificar_identidade_elemento` no locator encontrado.
     - Se a identidade não bater: logar aviso e **não** executar — deixar escalar.
     - Se a identidade bater: executar normalmente.
   - Se não (seletor não-posicional): comportamento atual inalterado.

4. **Log de aviso para seletores posicionais detectados** (requisito 2.3):
   Emitir `logger.warning` quando um seletor posicional é detectado na camada Hint,
   indicando que a validação de identidade será aplicada.

5. **Sem alteração no contrato do roteiro JSON**: Nenhum campo novo é necessário no
   roteiro. A correção é inteiramente interna ao `vision_engine.py`.

---

## Testing Strategy

### Validation Approach

A estratégia segue duas fases: primeiro, confirmar o bug no código não corrigido com
testes exploratórios; depois, verificar que o fix funciona (Fix Checking) e que o
comportamento existente não regrediu (Preservation Checking).

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES do fix. Confirmar ou refutar a hipótese de causa raiz.
Se refutada, re-hipotetisar antes de implementar.

**Test Plan**: Criar testes unitários que simulam o orquestrador `encontrar_e_clicar`
com um `page` mockado. Configurar o mock para que o seletor posicional resolva para um
elemento cujo texto visível é diferente do `label_curto`. Observar que a ação é
executada mesmo assim (comportamento bugado).

**Test Cases**:

1. **Seletor posicional aponta para item errado**: `seletor_hint = "item#file_1 .ui-chkbox .ui-chkbox-box"`,
   `label_curto = "GED 102"`, elemento na posição `file_1` tem texto "Jurídico".
   Esperado no código não corrigido: ação executada em "Jurídico" (demonstra o bug).

2. **nth-child aponta para linha errada**: `seletor_hint = "tr:nth-child(2) .btn-delete"`,
   `label_curto = "Fechar Período"`, linha 2 contém "Abrir Período".
   Esperado no código não corrigido: ação executada na linha errada.

3. **Seletor posicional com item correto na posição**: `seletor_hint = "item#file_1 .ui-chkbox"`,
   `label_curto = "GED 102"`, elemento na posição `file_1` tem texto "GED 102".
   Esperado: ação executada corretamente (não é bug neste caso).

4. **label_curto vazio com seletor posicional**: `seletor_hint = "item#file_1 .ui-chkbox"`,
   `label_curto = ""`. Esperado: comportamento atual mantido (sem validação de identidade).

**Expected Counterexamples**:
- No teste 1 e 2, o elemento errado é clicado sem qualquer aviso ou verificação.
- Causa confirmada: ausência de validação de identidade na camada Hint para seletores posicionais.

### Fix Checking

**Goal**: Verificar que, para todos os inputs onde a bug condition é verdadeira, a
função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL acao_tec WHERE isBugCondition(acao_tec) DO
  resultado := encontrar_e_clicar_corrigido(page_mock, acao_tec)

  IF elemento_na_posicao.texto != label_curto THEN
    ASSERT acao_NAO_executada_no_elemento_errado
    ASSERT fallback_acionado  // Sniper ou Vision tentados a seguir
  ELSE
    ASSERT acao_executada_no_elemento_correto
  END IF
END FOR
```

### Preservation Checking

**Goal**: Verificar que, para todos os inputs onde a bug condition é falsa, a função
corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL acao_tec WHERE NOT isBugCondition(acao_tec) DO
  ASSERT encontrar_e_clicar_original(page, acao_tec)
       = encontrar_e_clicar_corrigido(page, acao_tec)
END FOR
```

**Testing Approach**: Testes baseados em propriedades são recomendados para preservation
checking porque:
- Geram automaticamente muitos `seletor_hint` não-posicionais (aria-label, data-testid,
  text=, #id-semantico) e verificam que o comportamento é idêntico.
- Cobrem edge cases que testes manuais podem perder (seletores com números no meio do
  nome mas não posicionais, ex: `[data-testid='item-102']`).
- Fornecem garantia forte de que nenhuma regressão foi introduzida.

**Test Cases**:

1. **Seletor semântico aria-label**: `seletor_hint = "[aria-label='Excluir']"` — deve
   passar pela camada Hint sem validação de identidade, comportamento idêntico ao original.

2. **Seletor por ID semântico**: `seletor_hint = "[id='menu-item-Senior Flow']"` — não
   contém índice posicional, deve ser tratado normalmente.

3. **Seletor text=**: `seletor_hint = "text='Confirmar'"` — não-posicional, inalterado.

4. **Seletor com número no valor de atributo (não-posicional)**:
   `seletor_hint = "[data-testid='item-102']"` — o número faz parte do valor do
   atributo, não é índice posicional; deve ser tratado normalmente.

5. **label_curto vazio com seletor posicional**: sem validação de identidade, escala
   normalmente — comportamento preservado conforme requisito 3.3.

### Unit Tests

- Testar `_contem_indice_posicional` com bateria de seletores posicionais e não-posicionais.
- Testar `_verificar_identidade_elemento` com locators mockados que retornam texto
  correspondente, texto diferente, e texto inacessível (exceção).
- Testar o bloco da camada 3 em `encontrar_e_clicar` com page mockado para os quatro
  cenários: posicional+identidade ok, posicional+identidade falha, não-posicional,
  label vazio.

### Property-Based Tests

- Gerar seletores posicionais aleatórios (variando padrão, índice, sufixo) e verificar
  que `_contem_indice_posicional` retorna `True` para todos.
- Gerar seletores semânticos aleatórios (aria-label, data-testid, text=, #id) e
  verificar que `_contem_indice_posicional` retorna `False` para todos.
- Gerar pares `(seletor_hint não-posicional, label_curto)` e verificar que o
  comportamento de `encontrar_e_clicar` é idêntico entre original e corrigido.

### Integration Tests

- Executar o roteiro "Senior Flow - GED 102" completo com a lista do GED em ordem
  diferente da captura e verificar que o item "GED 102" é selecionado corretamente.
- Executar um roteiro com seletores semânticos (ex: `[aria-label='Salvar']`) e
  verificar que o comportamento não mudou após o fix.
- Verificar que o log emite `WARNING` quando um seletor posicional é detectado na
  camada Hint.

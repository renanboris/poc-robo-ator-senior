# Bugfix Requirements Document

## Introduction

Durante a execução do roteiro "Senior Flow - GED 102", o robô deveria selecionar o item "GED 102" via checkbox para realizar uma exclusão em lote. Em vez disso, selecionou e excluiu a pasta "Jurídico" — um item diferente que ocupava a posição `file_1` no momento da execução.

A causa raiz é que a estratégia **Hint** do `vision_engine.py` usa cegamente o `seletor_hint` capturado durante o mapeamento (`item#file_1 .ui-chkbox .ui-chkbox-box`), que contém um índice posicional fixo (`file_1`). Na hora da execução, a ordem dos itens na lista era diferente da ordem no momento da captura, fazendo com que o seletor apontasse para o item errado sem qualquer verificação de identidade.

O impacto é crítico: ações destrutivas (exclusão, processamento, fechamento de período) podem ser aplicadas ao item errado quando a lista está em ordem diferente da captura.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o `seletor_hint` contém um índice posicional (ex: `item#file_1`, `tr:nth-child(2)`, `li:nth-of-type(3)`) E a ordem dos itens na lista é diferente da ordem no momento da captura THEN o sistema clica no item que ocupa aquela posição, ignorando o `label_curto` e a `intencao_semantica` da ação.

1.2 WHEN a estratégia Hint é acionada para um seletor posicional THEN o sistema não verifica se o texto visível ou atributo identificador do elemento encontrado corresponde ao item esperado pelo roteiro.

1.3 WHEN o item errado é selecionado via seletor posicional THEN o sistema prossegue com as ações subsequentes (ex: "Excluir", "Confirmar") sobre o item incorreto, sem emitir aviso ou abortar.

### Expected Behavior (Correct)

2.1 WHEN o `seletor_hint` contém um índice posicional E a estratégia Hint é acionada THEN o sistema SHALL verificar se o elemento encontrado contém o texto do `label_curto` ou corresponde à `intencao_semantica` antes de executar a ação.

2.2 WHEN a verificação de identidade falha (o elemento na posição não corresponde ao item esperado) THEN o sistema SHALL descartar o resultado da estratégia Hint e escalar para a próxima camada de fallback (Sniper semântico ou Gemini Vision).

2.3 WHEN o `seletor_hint` é identificado como posicional durante a resolução THEN o sistema SHALL registrar um aviso no log indicando que o seletor posicional foi detectado e que a validação de identidade será aplicada.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o `seletor_hint` não contém índice posicional (ex: `[id='menu-item-Senior Flow']`, `[aria-label='Salvar']`) THEN o sistema SHALL CONTINUE TO usar o seletor hint diretamente sem validação adicional de identidade.

3.2 WHEN a estratégia Hint encontra o elemento correto e a verificação de identidade passa THEN o sistema SHALL CONTINUE TO executar a ação normalmente, sem degradação de performance ou comportamento.

3.3 WHEN o `label_curto` está vazio ou é uma tag genérica (ex: `div`, `span`) THEN o sistema SHALL CONTINUE TO aplicar as demais estratégias de fallback sem tentar validação de identidade por texto.

3.4 WHEN a estratégia Sniper semântico (texto exato, role, aria-label) já localizou o elemento antes de chegar na camada Hint THEN o sistema SHALL CONTINUE TO usar o resultado do Sniper sem alteração.

3.5 WHEN o Brain (memória SQLite) possui um seletor válido para a intenção THEN o sistema SHALL CONTINUE TO priorizar o Brain antes de tentar qualquer outra estratégia, incluindo a Hint validada.

---

## Bug Condition (Pseudocódigo)

```pascal
FUNCTION isBugCondition(acao_tec)
  INPUT: acao_tec de tipo AcaoTecnica (campo do roteiro JSON)
  OUTPUT: boolean

  seletor := acao_tec.elemento_alvo.seletor_hint
  RETURN contem_indice_posicional(seletor)
    // onde contem_indice_posicional detecta padrões como:
    //   #file_\d+, :nth-child(\d+), :nth-of-type(\d+),
    //   item#\w+\d+, tr:nth-child, li:nth-of-type
END FUNCTION
```

```pascal
// Property: Fix Checking — Validação de Identidade em Seletores Posicionais
FOR ALL acao_tec WHERE isBugCondition(acao_tec) DO
  elemento := hint_strategy_resolve(acao_tec.seletor_hint)
  identidade_ok := verificar_identidade(elemento, acao_tec.label_curto)
  IF NOT identidade_ok THEN
    ASSERT hint_strategy_descarta(elemento)
    ASSERT fallback_acionado(acao_tec)
  END IF
END FOR
```

```pascal
// Property: Preservation Checking
FOR ALL acao_tec WHERE NOT isBugCondition(acao_tec) DO
  ASSERT F(acao_tec) = F'(acao_tec)
  // O comportamento para seletores não-posicionais permanece idêntico
END FOR
```

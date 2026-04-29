# Bugfix Requirements Document

## Introduction

O robô está falhando sistematicamente na localização de elementos durante a execução de roteiros mapeados no Senior X. A taxa de sucesso da camada `2_coords_capturadas` caiu para 5-6% (esperado: >90%), e a validação de identidade sempre falha reportando encontrar "iframe platform" em vez dos elementos esperados (ex: "Acompanhar assinaturas", "Histórico").

O problema ocorre porque a verificação de identidade usa `document.elementFromPoint(x, y)` no contexto da página principal, mas os elementos do Senior X estão dentro de iframes. Quando as coordenadas apontam para dentro de um iframe, `elementFromPoint` retorna o elemento `<iframe>` em si (cujo texto visível é "iframe platform"), não o elemento interno que está nas coordenadas.

**Impacto:**
- Taxa de sucesso de coordenadas capturadas: 5-6% (esperado: >90%)
- Taxa de intervenção manual (HITL): 29%
- Todos os novos mapeamentos falham sistematicamente
- Fallbacks (Sniper, Vision) também degradados ou bloqueados (rate limit 429)
- Sistema inutilizável para novos fluxos

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a camada `2_coords_capturadas` tenta verificar a identidade de um elemento que está dentro de um iframe THEN o sistema executa `page.evaluate("document.elementFromPoint(x, y)")` no contexto da página principal e retorna o elemento `<iframe>` em vez do elemento interno

1.2 WHEN `elementFromPoint` retorna o iframe e o sistema lê o texto visível desse iframe THEN o sistema encontra "iframe platform" em vez do texto do elemento esperado (ex: "Acompanhar assinaturas")

1.3 WHEN a verificação de identidade compara "iframe platform" com o `label_curto` esperado THEN a verificação sempre falha e a camada `2_coords_capturadas` escala para a próxima camada mesmo quando as coordenadas estão corretas

1.4 WHEN o sistema não possui `iframe_hint` ou o `iframe_hint` está vazio/genérico THEN o sistema não tem informação de qual iframe usar para resolver o contexto correto antes de verificar a identidade

1.5 WHEN todos os fallbacks (Sniper, Todos os Frames, Gemini Vision) também falham THEN o sistema registra falha total mesmo quando as coordenadas capturadas estavam corretas mas a verificação de identidade foi feita no contexto errado

### Expected Behavior (Correct)

2.1 WHEN a camada `2_coords_capturadas` precisa verificar a identidade de um elemento THEN o sistema SHALL primeiro determinar se as coordenadas apontam para dentro de um iframe e, se sim, executar `elementFromPoint` no contexto daquele iframe

2.2 WHEN as coordenadas apontam para dentro de um iframe THEN o sistema SHALL usar `iframe.contentWindow.document.elementFromPoint(x_relativo, y_relativo)` com coordenadas ajustadas para o sistema de coordenadas do iframe

2.3 WHEN o sistema identifica que `elementFromPoint` retornou um elemento `<iframe>` THEN o sistema SHALL recursivamente buscar dentro daquele iframe usando as coordenadas ajustadas até encontrar o elemento final (não-iframe)

2.4 WHEN o `iframe_hint` está disponível no `elemento_alvo` THEN o sistema SHALL usar esse hint para resolver o contexto do iframe antes de executar `elementFromPoint`

2.5 WHEN a verificação de identidade é executada no contexto correto (dentro do iframe) THEN o sistema SHALL encontrar o texto correto do elemento e confirmar a identidade com sucesso quando as coordenadas estão corretas

### Unchanged Behavior (Regression Prevention)

3.1 WHEN as coordenadas apontam para um elemento na página principal (fora de iframes) THEN o sistema SHALL CONTINUE TO usar `page.evaluate("document.elementFromPoint(x, y)")` diretamente sem alteração de comportamento

3.2 WHEN a verificação de identidade falha legitimamente (coordenadas incorretas, elemento mudou) THEN o sistema SHALL CONTINUE TO escalar para a próxima camada (`2_sniper`) como esperado

3.3 WHEN `label_curto` está vazio ou `page.evaluate` lança exceção THEN o sistema SHALL CONTINUE TO aplicar fail-open e aceitar o clique normalmente

3.4 WHEN o elemento encontrado por `elementFromPoint` contém o `label_curto` esperado THEN o sistema SHALL CONTINUE TO confirmar a identidade e retornar sucesso

3.5 WHEN todas as camadas de fallback (Brain, Template Matching, Sniper, Hint Original, Todos os Frames, Gemini Vision) são acionadas THEN o sistema SHALL CONTINUE TO funcionar exatamente como antes sem degradação

3.6 WHEN o sistema registra telemetria e emite logs de WARNING para fallbacks THEN o sistema SHALL CONTINUE TO registrar e emitir logs da mesma forma

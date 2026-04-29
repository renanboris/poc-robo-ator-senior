# Bugfix Requirements Document

## Introduction

Os ícones de like e dislike no painel de feedback da Aura DAP estão renderizando incorretamente devido a um conflito entre os atributos SVG e as regras CSS. O código JavaScript define `fill="currentColor"` nos elementos SVG, mas o CSS sobrescreve com `fill: none !important`, resultando em ícones mal formados que aparecem como símbolos não reconhecidos (descritos pelo usuário como "capivaras"). Este bug afeta a identidade visual do produto e a experiência do usuário ao interagir com o sistema de feedback.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN os botões de feedback like/dislike são renderizados no painel Aura DAP THEN os ícones SVG aparecem como símbolos mal formados ou não reconhecidos devido ao conflito entre `fill="currentColor"` no JavaScript e `fill: none !important` no CSS

1.2 WHEN o usuário visualiza a barra de feedback após uma resposta da IA THEN os ícones não correspondem à identidade visual esperada (thumbs up/down) e aparecem distorcidos

### Expected Behavior (Correct)

2.1 WHEN os botões de feedback like/dislike são renderizados no painel Aura DAP THEN os ícones SVG SHALL exibir corretamente os símbolos de thumbs up e thumbs down com preenchimento sólido usando `currentColor`

2.2 WHEN o usuário visualiza a barra de feedback após uma resposta da IA THEN os ícones SHALL ser visualmente reconhecíveis como thumbs up (like) e thumbs down (dislike) com a cor padrão `#94a3b8` em estado de repouso

2.3 WHEN o usuário passa o cursor sobre o botão like THEN o ícone SHALL mudar para a cor `#00ddb3` mantendo o preenchimento sólido correto

2.4 WHEN o usuário passa o cursor sobre o botão dislike THEN o ícone SHALL mudar para a cor `#ef4444` mantendo o preenchimento sólido correto

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o usuário clica em like ou dislike THEN o sistema SHALL CONTINUE TO registrar o feedback no localStorage com os campos `tipo`, `prompt`, `url` e `ts`

3.2 WHEN o feedback é registrado THEN a barra de feedback SHALL CONTINUE TO desaparecer com fade-out após 350ms e ser removida do DOM após 850ms

3.3 WHEN os botões são desabilitados após votação THEN o sistema SHALL CONTINUE TO aplicar `opacity: 0.5` e `cursor: not-allowed`

3.4 WHEN o botão like recebe votação THEN o sistema SHALL CONTINUE TO aplicar a classe `voted-yes` com cor `#00ddb3`

3.5 WHEN o botão dislike recebe votação THEN o sistema SHALL CONTINUE TO aplicar a classe `voted-no` com cor `#ef4444`

3.6 WHEN a barra de feedback é criada THEN o sistema SHALL CONTINUE TO usar os atributos de acessibilidade `aria-label` e `aria-hidden="true"` nos elementos apropriados

3.7 WHEN o usuário interage com outros elementos do painel Aura THEN o sistema SHALL CONTINUE TO funcionar normalmente sem regressões na Thread_Area, Typing_Indicator, ou histórico de conversa

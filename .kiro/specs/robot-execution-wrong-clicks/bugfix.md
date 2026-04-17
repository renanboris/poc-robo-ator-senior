# Bugfix Requirements Document

## Introduction

Durante a execução de um roteiro gravado, o robô reporta "sucesso" em todas as etapas — incluindo camadas de fallback como coordenadas capturadas e Sniper semântico — mas os cliques e ações realizados são totalmente incorretos na tela. O sistema não detecta nem sinaliza que as ações foram executadas no elemento errado ou na posição errada. O impacto é crítico: o vídeo gerado registra ações incorretas, o treinamento produzido é inválido, e o usuário não recebe nenhum aviso de falha.

O log analisado evidencia dois padrões de falha simultâneos:
- **Passo 1**: template matching falhou (camada `1_template_matching`), o fallback para coordenadas relativas da gravação (`2_coords_capturadas`) foi acionado e reportou sucesso com score 0.700 — mas as coordenadas (33, 769) podem estar deslocadas por diferença de resolução ou scroll entre a gravação e a execução.
- **Passos 2 e 3**: o Sniper semântico (`2_sniper`) reportou acerto com score 0.910, mas pode ter encontrado um elemento diferente com texto parcialmente coincidente (falso positivo semântico).

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o template matching falha e o sistema usa coordenadas relativas da gravação como fallback THEN o sistema executa o clique nas coordenadas calculadas e reporta sucesso sem verificar se o elemento clicado corresponde ao elemento esperado

1.2 WHEN as coordenadas relativas da gravação foram capturadas em uma resolução ou estado de scroll diferente do ambiente de execução THEN o sistema clica em posição incorreta na tela e reporta sucesso com score 0.700

1.3 WHEN o Sniper semântico encontra um candidato com texto parcialmente coincidente ao label esperado THEN o sistema executa a ação nesse candidato e reporta sucesso sem confirmar que o elemento encontrado é o elemento correto da intenção

1.4 WHEN qualquer camada de fallback (coordenadas capturadas ou Sniper) executa uma ação THEN o sistema retorna `True` e registra telemetria de sucesso independentemente de o elemento atingido ser o correto

1.5 WHEN múltiplas camadas de fallback são acionadas em sequência para um mesmo passo THEN o sistema não emite nenhum aviso ao usuário de que o passo foi resolvido por fallback em vez da estratégia primária

### Expected Behavior (Correct)

2.1 WHEN o sistema usa coordenadas relativas da gravação como fallback THEN o sistema SHALL verificar se o elemento presente nas coordenadas calculadas corresponde ao label ou intenção esperada antes de confirmar o sucesso

2.2 WHEN as coordenadas relativas resultam em um clique em posição que não contém o elemento esperado THEN o sistema SHALL registrar a tentativa como falha e escalar para a próxima camada em vez de retornar sucesso

2.3 WHEN o Sniper semântico encontra um candidato por texto parcial THEN o sistema SHALL aplicar verificação de identidade do elemento (via `_verificar_identidade_elemento`) antes de confirmar o acerto, rejeitando falsos positivos

2.4 WHEN qualquer camada de fallback é acionada com sucesso THEN o sistema SHALL emitir um log de WARNING indicando que o passo foi resolvido por fallback, incluindo a camada utilizada e o score de confiança

2.5 WHEN o score de confiança de uma camada de fallback está abaixo de um limiar mínimo aceitável THEN o sistema SHALL tratar o resultado como inconclusivo e escalar para a próxima camada em vez de aceitar o clique como correto

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o template matching encontra o elemento com score acima do threshold (≥ 0.80) THEN o sistema SHALL CONTINUE TO executar o clique e retornar sucesso normalmente

3.2 WHEN o Brain (memória SQLite) possui um seletor válido memorizado para a intenção THEN o sistema SHALL CONTINUE TO usar esse seletor como primeira estratégia antes de qualquer fallback

3.3 WHEN o Sniper semântico encontra um candidato por `aria-label` exato, `data-testid`, ou `role` + `name` exato THEN o sistema SHALL CONTINUE TO executar a ação e registrar sucesso sem verificação adicional

3.4 WHEN o Gemini Vision é acionado e retorna coordenadas com confiança "alta" THEN o sistema SHALL CONTINUE TO executar o clique por coordenadas e tentar aprender o seletor DOM resultante

3.5 WHEN nenhuma camada consegue localizar o elemento THEN o sistema SHALL CONTINUE TO registrar falha total, emitir log de erro e retornar `False`

3.6 WHEN a execução do roteiro ocorre na mesma resolução e estado de scroll da gravação original THEN o sistema SHALL CONTINUE TO usar coordenadas relativas como fallback válido sem degradação de comportamento

# Bugfix Requirements Document

## Introduction

Dois bugs afetam o fluxo de execução do robô no Senior Training OS. O primeiro faz com que execuções bem-sucedidas de roteiros longos sejam incorretamente reportadas como falha por timeout, pois o limite de 3 minutos hardcoded no frontend é insuficiente para roteiros com muitos passos. O segundo impede que a etapa de indexação na base de conhecimento da Aura seja exibida e executada após a produção, pois o array de steps do stepper está com a definição do endpoint truncada/incompleta no código do frontend.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a execução do robô (`/api/executar-robo/`) demora mais de 3 minutos THEN o sistema reporta "Tempo esgotado. O processo excedeu 3 minutos." mesmo que o robô esteja executando corretamente

1.2 WHEN o robô conclui com sucesso um roteiro longo (acima de 3 minutos) THEN o sistema exibe a mensagem de falha no chat e oferece a opção "Tentar Robô Novamente", interrompendo o fluxo de produção

1.3 WHEN o usuário aciona a linha de produção (stepper) após a execução do robô THEN o sistema não exibe nem executa a etapa "🧠 Indexação na base de conhecimento da Aura"

1.4 WHEN o lego_builder executa com sucesso (retorna `ok`) durante a linha de produção THEN o sistema não chama o endpoint `/api/ingest/` para indexar o roteiro na base de conhecimento da Aura

### Expected Behavior (Correct)

2.1 WHEN a execução do robô demora mais de 3 minutos THEN o sistema SHALL aguardar a conclusão do processo sem reportar timeout prematuro

2.2 WHEN o robô conclui com sucesso um roteiro de qualquer duração THEN o sistema SHALL exibir a mensagem de sucesso e avançar o fluxo normalmente para a linha de produção

2.3 WHEN o usuário aciona a linha de produção (stepper) THEN o sistema SHALL exibir e executar a etapa "🧠 Indexação na base de conhecimento da Aura" como parte do pipeline

2.4 WHEN o stepper chega na etapa de indexação THEN o sistema SHALL chamar o endpoint `/api/ingest/{arquivo}` e aguardar sua conclusão antes de marcar a etapa como concluída

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a execução do robô falha com erro real (returncode != 0) THEN o sistema SHALL CONTINUE TO reportar a falha corretamente com a mensagem de erro do processo

3.2 WHEN o usuário cancela a execução via `/api/cancelar` THEN o sistema SHALL CONTINUE TO reportar a interrupção corretamente

3.3 WHEN a execução do robô conclui em menos de 3 minutos THEN o sistema SHALL CONTINUE TO reportar o sucesso imediatamente sem aguardar o timeout

3.4 WHEN o WebSocket está desconectado THEN o sistema SHALL CONTINUE TO usar o fallback de polling (`_pollFallback`) para aguardar o status

3.5 WHEN as etapas de renderização de vídeo, geração de SCORM e geração de PDF são executadas no stepper THEN o sistema SHALL CONTINUE TO executá-las na mesma ordem e com o mesmo comportamento atual

3.6 WHEN a indexação na Aura falha (endpoint retorna erro) THEN o sistema SHALL CONTINUE TO reportar a falha da etapa no stepper sem interromper as etapas anteriores já concluídas

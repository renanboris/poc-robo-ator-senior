# Bugfix Requirements Document

## Introduction

Durante a etapa de renderização do vídeo (MP4) no pipeline de produção, o `index.html` não exibe nenhum indicador de progresso real ao usuário. O step de renderização permanece com o spinner girando indefinidamente, sem qualquer feedback de quanto falta para concluir — mesmo que o backend já emita dados de progresso via WebSocket.

O impacto é direto na experiência do operador: a renderização é a etapa mais longa da produção (podendo durar vários minutos), e a ausência de feedback cria a percepção de que o sistema travou, levando a interrupções desnecessárias ou incerteza sobre o estado do processo.

A infraestrutura necessária já existe em ambas as pontas: `main.py` emite `PROGRESSO:{pct}` via stdout, `app.py` captura e faz broadcast do campo `progresso` via WebSocket, e o frontend já tem WebSocket conectado. O bug está na camada de apresentação: o `onmessage` do frontend ignora completamente o campo `data.progresso` enquanto o processo está ocupado.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN a renderização do vídeo está em andamento e o backend emite atualizações de progresso via WebSocket THEN o frontend ignora o campo `data.progresso` e não atualiza nenhum elemento visual no step de renderização

1.2 WHEN o usuário observa o stepper de produção durante a renderização THEN o sistema exibe apenas o spinner estático no step "🎬 Renderização do vídeo (MP4)", sem porcentagem, barra de progresso ou qualquer indicação de avanço

1.3 WHEN a renderização conclui e o backend emite `ocupado: false` THEN o step passa diretamente de spinner estático para ícone de conclusão, sem nenhuma transição de progresso intermediária

### Expected Behavior (Correct)

2.1 WHEN a renderização do vídeo está em andamento e o backend emite `data.progresso` via WebSocket THEN o sistema SHALL atualizar visualmente o step de renderização com o valor de progresso recebido (porcentagem ou barra)

2.2 WHEN o usuário observa o stepper de produção durante a renderização THEN o sistema SHALL exibir um indicador de progresso (ex: "47%" ou barra preenchida proporcionalmente) que aumenta gradualmente conforme o backend reporta avanço

2.3 WHEN a renderização conclui (`data.progresso` atinge 100% ou `ocupado` passa a `false` com sucesso) THEN o sistema SHALL exibir o step como concluído com o indicador em 100% antes de transicionar para o ícone de conclusão

### Unchanged Behavior (Regression Prevention)

3.1 WHEN qualquer step diferente de renderização de vídeo está em execução (SCORM, PDF, SimLink) THEN o sistema SHALL CONTINUE TO exibir o spinner padrão sem indicador de progresso, pois esses processos não emitem `PROGRESSO:` via stdout

3.2 WHEN a renderização falha e o backend emite `data.erro` THEN o sistema SHALL CONTINUE TO marcar o step com estado de erro e interromper o stepper normalmente

3.3 WHEN o WebSocket está desconectado e o fallback de polling está ativo THEN o sistema SHALL CONTINUE TO aguardar a conclusão via polling sem quebrar o fluxo do stepper

3.4 WHEN a renderização conclui com sucesso THEN o sistema SHALL CONTINUE TO avançar para os próximos steps (SCORM, PDF, SimLink) normalmente após a conclusão

3.5 WHEN o usuário inicia uma nova sessão ou recarrega a página THEN o sistema SHALL CONTINUE TO conectar o WebSocket e iniciar o stepper normalmente sem estado residual de progresso anterior

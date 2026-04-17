# Bugfix Requirements Document

## Introduction

Este documento define os requisitos para corrigir o bug onde a execução do robô não para adequadamente quando o utilizador fecha manualmente a janela do Chrome durante a execução dos passos do roteiro. O bug afeta a função `executar_roteiro()` em `main.py`, que usa Playwright para automação do browser Chrome durante gravação de vídeo e execução de ações técnicas.

O impacto deste bug inclui:
- Continuação da execução em background mesmo após o browser ser fechado
- Tentativas de operações em objetos Playwright já destruídos
- Limpeza inadequada de recursos (áudio, vídeo parcial)
- Falta de feedback ao utilizador sobre a interrupção

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o utilizador fecha manualmente a janela do Chrome durante a execução do loop de passos THEN o sistema continua executando o código sem detectar que o browser foi fechado

1.2 WHEN o browser é fechado prematuramente THEN o bloco finally executa normalmente tentando acessar objetos Playwright já destruídos (page, context, browser)

1.3 WHEN ocorre uma exceção genérica durante a gravação THEN o sistema captura a exceção mas não distingue entre erro de execução normal e fechamento manual do browser

1.4 WHEN o browser é fechado pelo utilizador THEN o sistema não informa adequadamente que a execução foi interrompida manualmente

### Expected Behavior (Correct)

2.1 WHEN o utilizador fecha manualmente a janela do Chrome durante a execução do loop de passos THEN o sistema SHALL detectar o fechamento através de exceções específicas do Playwright e interromper a execução de forma limpa

2.2 WHEN o browser é fechado prematuramente THEN o sistema SHALL verificar o estado dos objetos Playwright antes de tentar acessá-los no bloco finally

2.3 WHEN ocorre uma exceção relacionada ao fechamento do browser THEN o sistema SHALL identificar especificamente esse tipo de erro e tratá-lo de forma diferenciada

2.4 WHEN o browser é fechado pelo utilizador THEN o sistema SHALL informar claramente que a execução foi interrompida manualmente e limpar recursos adequadamente

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a execução completa normalmente sem interrupção manual THEN o sistema SHALL CONTINUE TO salvar o estado, processar o vídeo e limpar recursos como antes

3.2 WHEN ocorrem erros de execução não relacionados ao fechamento do browser THEN o sistema SHALL CONTINUE TO capturar e reportar esses erros normalmente

3.3 WHEN o bloco finally executa após conclusão normal THEN o sistema SHALL CONTINUE TO fechar page, context e browser na sequência correta

3.4 WHEN o sistema gera áudios e vídeos durante execução normal THEN o sistema SHALL CONTINUE TO manter a timeline e manifesto de áudio intactos

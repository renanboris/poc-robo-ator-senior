# Bugfix Requirements Document

## Introduction

Este documento cobre dois bugs relacionados ao ciclo de vida de processos e ao isolamento de ambientes no Senior Training OS.

**Bug 1 — Fechar o navegador não cancela o robô em execução:** quando o último cliente WebSocket desconecta enquanto há um processo filho ativo (`capture.py` ou `main.py`), o processo continua rodando em background indefinidamente. O handler `websocket_status` em `app.py` remove o cliente da lista de conexões mas não encerra o `processo_atual`, causando consumo de recursos e estado inconsistente no servidor.

**Bug 2 — Tenant único contamina o ambiente de execução com dados da captura:** todos os módulos do pipeline (captura, execução, validação) compartilham as mesmas variáveis de credenciais `SENIOR_USER` e `SENIOR_PASS`, apontando para o mesmo tenant do Senior X. Isso faz com que dados criados durante a captura de um workflow já existam no ambiente usado para executar e validar o roteiro gerado, invalidando os testes de qualidade.

---

## Bug Analysis

### Current Behavior (Defect)

#### Bug 1 — Desconexão do navegador não encerra o processo

1.1 QUANDO o último cliente WebSocket desconecta via `WebSocketDisconnect` ENTÃO o sistema remove o websocket de `ws_manager.active_connections` mas mantém `processo_atual` rodando em background

1.2 QUANDO o navegador é fechado no meio de uma execução de `main.py` ENTÃO o sistema continua consumindo recursos do processo filho sem nenhum mecanismo de encerramento automático

1.3 QUANDO o navegador é fechado no meio de uma captura de `capture.py` ENTÃO o sistema mantém o Playwright e o browser abertos indefinidamente sem liberar os recursos

#### Bug 2 — Tenant único contamina o ambiente de execução

2.1 QUANDO `capture.py` executa o login no Senior X ENTÃO o sistema usa `SENIOR_USER` / `SENIOR_PASS`, criando pastas, registros e dados no mesmo tenant que será usado pela execução

2.2 QUANDO `main.py` executa o roteiro gerado ENTÃO o sistema usa `SENIOR_USER` / `SENIOR_PASS`, encontrando dados pré-existentes criados durante a captura, o que invalida a validação do roteiro

2.3 QUANDO `validator.py` ou `validator_hitl.py` valida um roteiro ENTÃO o sistema usa `SENIOR_USER` / `SENIOR_PASS`, operando no mesmo tenant contaminado pela captura

2.4 QUANDO `CIL/capture_semantic.py` realiza captura semântica ENTÃO o sistema usa `SENIOR_USER` / `SENIOR_PASS`, misturando credenciais de captura com as de execução

2.5 QUANDO `contracts/capture_adapter.py` fornece credenciais via `obter_credenciais()` ENTÃO o sistema retorna um único par de credenciais sem distinção entre o contexto de captura e o de execução

2.6 QUANDO `CIL/main_cil.py` executa o fluxo CIL ENTÃO o sistema usa `SENIOR_USER` / `SENIOR_PASS`, sem isolamento do tenant de execução

---

### Expected Behavior (Correct)

#### Bug 1 — Desconexão do navegador deve encerrar o processo

1.1 QUANDO o último cliente WebSocket desconecta e `processo_atual` não é None ENTÃO o sistema SHALL encerrar o processo filho via `proc.terminate()` e atualizar o estado via `_set_estado()`

1.2 QUANDO o navegador é fechado no meio de uma execução de `main.py` ENTÃO o sistema SHALL terminar o processo filho automaticamente, equivalente ao comportamento de `POST /api/cancelar`

1.3 QUANDO o navegador é fechado no meio de uma captura de `capture.py` ENTÃO o sistema SHALL terminar o processo filho automaticamente, liberando o Playwright e o browser

#### Bug 2 — Dois pares de credenciais devem isolar os tenants

2.1 QUANDO `capture.py` executa o login no Senior X ENTÃO o sistema SHALL usar `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`, operando exclusivamente no tenant de captura

2.2 QUANDO `main.py` executa o roteiro gerado ENTÃO o sistema SHALL usar `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`, operando em um tenant limpo e isolado do tenant de captura

2.3 QUANDO `validator.py` ou `validator_hitl.py` valida um roteiro ENTÃO o sistema SHALL usar `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`, garantindo que a validação ocorra no tenant de execução

2.4 QUANDO `CIL/capture_semantic.py` realiza captura semântica ENTÃO o sistema SHALL usar `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`

2.5 QUANDO `contracts/capture_adapter.py` fornece credenciais via `obter_credenciais()` ENTÃO o sistema SHALL retornar `SENIOR_USER_CAPTURE` / `SENIOR_PASS_CAPTURE`, pois o adapter é usado exclusivamente no contexto de captura

2.6 QUANDO `CIL/main_cil.py` executa o fluxo CIL ENTÃO o sistema SHALL usar `SENIOR_USER_EXECUTE` / `SENIOR_PASS_EXECUTE`

2.7 QUANDO as variáveis `SENIOR_USER_CAPTURE`, `SENIOR_PASS_CAPTURE`, `SENIOR_USER_EXECUTE` ou `SENIOR_PASS_EXECUTE` estiverem ausentes no `.env` ENTÃO o sistema SHALL emitir um erro claro identificando qual variável está faltando e em qual módulo

---

### Unchanged Behavior (Regression Prevention)

3.1 QUANDO há clientes WebSocket ativos conectados e um processo está em execução ENTÃO o sistema SHALL CONTINUE TO manter o processo rodando normalmente sem interrupção

3.2 QUANDO um único cliente WebSocket desconecta mas ainda existem outros clientes ativos ENTÃO o sistema SHALL CONTINUE TO manter o processo rodando e os demais clientes conectados

3.3 QUANDO o usuário chama `POST /api/cancelar` explicitamente ENTÃO o sistema SHALL CONTINUE TO encerrar o processo, atualizar o job registry e remover arquivos temporários conforme o comportamento atual

3.4 QUANDO `capture.py` executa com credenciais de captura válidas ENTÃO o sistema SHALL CONTINUE TO realizar a captura do workflow no Senior X sem alteração no fluxo de automação Playwright

3.5 QUANDO `main.py` executa com credenciais de execução válidas ENTÃO o sistema SHALL CONTINUE TO reproduzir o roteiro no Senior X sem alteração no fluxo de automação Playwright

3.6 QUANDO `validator.py` valida um roteiro com credenciais de execução válidas ENTÃO o sistema SHALL CONTINUE TO executar a validação headless sem alteração no comportamento de validação

3.7 QUANDO `validator_hitl.py` valida um roteiro com credenciais de execução válidas ENTÃO o sistema SHALL CONTINUE TO executar a validação HITL sem alteração no comportamento interativo

3.8 QUANDO `SENIOR_URL` é configurada no `.env` ENTÃO o sistema SHALL CONTINUE TO usar a mesma URL base para todos os módulos, independentemente do par de credenciais utilizado

3.9 QUANDO o `.env.example` é consultado como referência de configuração ENTÃO o sistema SHALL CONTINUE TO servir como documentação de todas as variáveis de ambiente necessárias para o projeto

---

## Bug Condition Pseudocode

### Bug 1 — Condição de desconexão sem encerramento

```pascal
FUNCTION isBugCondition_Disconnect(event)
  INPUT: event de WebSocketDisconnect
  OUTPUT: boolean

  RETURN ws_manager.active_connections IS EMPTY
     AND processo_atual IS NOT None
END FUNCTION

// Property: Fix Checking — Encerramento automático ao desconectar
FOR ALL event WHERE isBugCondition_Disconnect(event) DO
  handle_disconnect'(event)
  ASSERT processo_atual.returncode IS NOT None  // processo foi terminado
  ASSERT estado reflects termination            // _set_estado() foi chamado
END FOR

// Property: Preservation Checking
FOR ALL event WHERE NOT isBugCondition_Disconnect(event) DO
  ASSERT handle_disconnect(event) = handle_disconnect'(event)
END FOR
```

### Bug 2 — Condição de tenant único

```pascal
FUNCTION isBugCondition_Tenant(module)
  INPUT: module name (string)
  OUTPUT: boolean

  RETURN module reads "SENIOR_USER" OR "SENIOR_PASS"
     AND no distinction between capture and execute context
END FUNCTION

// Property: Fix Checking — Credenciais corretas por contexto
FOR ALL module WHERE isBugCondition_Tenant(module) DO
  IF module IN [capture.py, CIL/capture_semantic.py, contracts/capture_adapter.py] THEN
    ASSERT credentials_used = (SENIOR_USER_CAPTURE, SENIOR_PASS_CAPTURE)
  ELSE IF module IN [main.py, validator.py, validator_hitl.py, CIL/main_cil.py] THEN
    ASSERT credentials_used = (SENIOR_USER_EXECUTE, SENIOR_PASS_EXECUTE)
  END IF
END FOR

// Property: Preservation Checking
FOR ALL module WHERE NOT isBugCondition_Tenant(module) DO
  ASSERT module_behavior(module) = module_behavior'(module)
END FOR
```

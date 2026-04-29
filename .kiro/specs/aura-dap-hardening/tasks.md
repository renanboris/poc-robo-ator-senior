# Plano de Implementação — Aura DAP Hardening

## Visão Geral

Patches cirúrgicos nos módulos existentes para consolidar governança de modos, endurecer GPS e Mission, formalizar analytics, documentar configuração e adicionar testes de integração. Nenhum módulo é reescrito do zero.

## Tarefas

- [x] 1. Atualizar `contracts/step_model.json` com campos opcionais
  - Adicionar campo opcional `scenario_id` (string) com descrição de uso futuro em roleplay
  - Adicionar campo opcional `branch_id` (string) com descrição de uso futuro em roleplay
  - Adicionar campo opcional `timeout_penalty_type` (enum: "none"|"soft"|"hard", default: "soft")
  - Documentar os três campos como "reservados para uso futuro em fluxos de roleplay adaptativo"
  - _Requirements: 2.1, 2.2, 2.3, 8.5_

- [x] 2. Endurecer `aura_state.js` — maestro completo para modos compostos
  - [x] 2.1 Adicionar `_activeRoteiro` e `_activeScoringConfig` ao estado interno
    - Implementar `setActiveRoteiro(roteiro, scoringConfig)` que armazena roteiro e scoring na sessão
    - Implementar `getActiveRoteiro()` e `getActiveScoringConfig()` como leitores seguros
    - Adicionar `steps_total: 0` e `tenant_id: 'senior_default'` ao `_buildInitialSession()`
    - _Requirements: 1.6, 2.4_

  - [x] 2.2 Atualizar `setMode()` para inicialização composta de `train`/`prove`
    - Para `train` e `prove`: chamar `AuraGpsEngine.init(roteiro)` depois `AuraMissionEngine.init(scoringConfig)` automaticamente
    - Para teardown de `train`/`prove`: chamar `AuraMissionEngine.teardown()` depois `AuraGpsEngine.teardown()` (ordem inversa)
    - Aceitar `options = { roteiro?, scoringConfig? }` como segundo parâmetro de `setMode()`
    - Logar aviso se `setMode('train'|'prove')` for chamado sem roteiro ativo
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7_

- [x] 3. Endurecer `aura_gps_engine.js`
  - [x] 3.1 Adicionar flag `_isActive` e proteção contra reentrada
    - Declarar `var _isActive = false` no estado privado
    - No início de `init()`: se `_isActive === true`, executar `teardown()` antes de prosseguir
    - Definir `_isActive = true` após inicialização bem-sucedida
    - Definir `_isActive = false` no início de `teardown()`
    - Expor `isActive()` na interface pública
    - _Requirements: 3.1, 3.2, 3.7_

  - [x] 3.2 Propagar `steps_total` para `AuraState.session`
    - Após normalizar `_passos` no `init()`, escrever `AuraState.session.steps_total = _passos.length`
    - _Requirements: 2.4_

  - [x] 3.3 Implementar evento `gps:step_timeout` e reinício do validador
    - Renomear `_falharPasso()` para `_timeoutPasso()` internamente
    - Em `_timeoutPasso()`: emitir `gps:step_timeout` com `{ step, stepIndex, timeout_sec }` antes de `gps:step_failed`
    - Após emitir os eventos: reiniciar o validador do passo corrente (nova tentativa sem reiniciar GPS)
    - Reiniciar o timeout após cada expiração
    - _Requirements: 3.3, 3.4_

  - [x] 3.4 Corrigir `_validadorElementAbsent` com delay mínimo de 500ms
    - Adicionar `_delayHandle` ao closure do validador
    - Quando seletor ausente: aguardar 500ms antes de confirmar ausência
    - Verificar novamente após o delay — se elemento apareceu, cancelar validação e continuar observando
    - Incluir `clearTimeout(_delayHandle)` na função de cleanup
    - _Requirements: 3.5_

  - [x] 3.5 Implementar suporte a `onBranchDecision` e evento `gps:branch_point`
    - `init()` aceita segundo parâmetro `options = { onBranchDecision? }`
    - Em `_avancarPasso()`: se passo tem `branch_id`, emitir `gps:branch_point` e aguardar um tick (setTimeout 0)
    - Após o tick: chamar `onBranchDecision(step, proximoIndex)` se fornecido; usar retorno como próximo índice
    - Se `onBranchDecision` não fornecido ou não retornar número: avançar sequencialmente
    - Capturar exceção em `onBranchDecision` com log e fallback sequencial
    - _Requirements: 8.1, 8.2, 8.6, 8.7_

- [x] 4. Endurecer `aura_mission_engine.js`
  - [x] 4.1 Corrigir dots de progresso com `steps_total` real
    - No `init()`: ler `AuraState.session.steps_total` e armazenar em `_stepsTotal`
    - Passar `_stepsTotal` para `_criarHud()` e `_atualizarHud()`
    - Se `_stepsTotal === 0`: ocultar área de dots do HUD (`display: none`)
    - _Requirements: 4.1, 4.2_

  - [x] 4.2 Corrigir abandono para usar `AuraState.setMode('assist')`
    - No botão "Abandonar" do HUD: substituir chamada direta a `AuraGpsEngine.teardown()` por `AuraState.setMode('assist')`
    - _Requirements: 4.3_

  - [x] 4.3 Adicionar listener para `gps:step_timeout` com penalidades distintas
    - Registrar listener `gps:step_timeout` em `_addListener()` durante `init()`
    - No modo `prove`: aplicar `scoringConfig.timeout_penalty` (default: 10)
    - No modo `train`: exibir mensagem de encorajamento via `AuraUI.exibirBalao()` sem penalidade
    - _Requirements: 4.4, 4.5_

  - [x] 4.4 Remover emissão duplicada de `step_error` em `_onStepFailed()`
    - Remover a chamada `_emitAnalytics('step_error', ...)` de `_onStepFailed()`
    - Manter apenas a penalidade de XP e incremento de `_errorsCount`
    - _Requirements: 4.6, 5.6_

  - [x] 4.5 Atualizar `_onStepValidated()` para re-renderizar dots corretamente
    - Após atualizar `_currentStepIdx`, chamar `_atualizarHud(_stepsTotal)` com o total correto
    - _Requirements: 4.7_

  - [x] 4.6 Expor `getScore()` e implementar `onOutcomeEvaluated`
    - Adicionar `getScore()` à interface pública retornando `{ xp, hintsUsed, errorsCount, durationSec }`
    - Em `init()`: ler `scoringConfig.onOutcomeEvaluated` e armazenar em `_onOutcomeEvaluated`
    - Em `_onCompleted()`: chamar `_onOutcomeEvaluated(score, mode)` se definido, antes de exibir resumo padrão
    - _Requirements: 4.8, 8.3, 8.4_

  - [x] 4.7 Emitir `mission_start` no `init()`
    - Após criar o HUD, emitir analytics `mission_start` com `{ roteiro_id, mode, base_xp, steps_total, timestamp }`
    - _Requirements: 5.5_

- [x] 5. Atualizar `aura_assist_engine.js` com novos eventos de analytics
  - [x] 5.1 Emitir `assist_prompt_sent` em `dispararAnalise()`
    - Após montar o prompt, emitir analytics `assist_prompt_sent` com `{ prompt_length, tenant_id, timestamp }`
    - Ler `tenant_id` de `AuraState.session.tenant_id` com fallback `'senior_default'`
    - _Requirements: 5.1_

  - [x] 5.2 Emitir `assist_response_received` em `_handleMessage()`
    - Ao processar `AURA_RESPONSE`, emitir analytics `assist_response_received` com `{ has_gps, has_spotlight, tenant_id, timestamp }`
    - _Requirements: 5.2_

- [x] 6. Atualizar `aura_gps_engine.js` com eventos de analytics faltantes
  - [x] 6.1 Emitir `gps_step_started` no início de cada passo
    - Em `_iniciarPasso()`: emitir analytics `gps_step_started` com `{ step_id, step_index, roteiro_id, tenant_id, timestamp }`
    - Ler `tenant_id` de `AuraState.session.tenant_id` com fallback `'senior_default'`
    - _Requirements: 5.3_

  - [x] 6.2 Adicionar `tenant_id` ao payload de `gps_start`
    - No `init()`, ao emitir `gps_start`: incluir `tenant_id` lido de `AuraState.session.tenant_id`
    - _Requirements: 5.4_

- [x] 7. Criar `extension/aura_config.js` e atualizar `background.js`
  - [x] 7.1 Criar `extension/aura_config.js`
    - Definir `var AURA_CONFIG = { authToken: '', endpoints: { analyze, missions, gps, analytics } }`
    - Incluir comentário explicando que este arquivo deve ser substituído pelo build pipeline em produção
    - _Requirements: 6.1, 6.2_

  - [x] 7.2 Atualizar `background.js` para ler `AURA_CONFIG` e usar `Object.freeze`
    - Ler `AURA_CONFIG` no topo do arquivo (definido por `aura_config.js`)
    - Aplicar `Object.freeze()` em `AURA_ENDPOINTS` após inicialização
    - Implementar `getConfig()` que retorna endpoints sem expor token
    - Adicionar aviso de console para endpoints sem `https://` ou `http://localhost`
    - _Requirements: 6.1, 6.2, 6.3, 6.5, 6.6_

  - [x] 7.3 Adicionar validação de `event_type` no handler `analytics_event`
    - Definir `ANALYTICS_EVENT_TYPES` como `Set` com todos os tipos canônicos
    - Rejeitar eventos com `event_type` desconhecido retornando `{ ok: false, reason: 'event_type_unknown' }`
    - _Requirements: 5.7_

  - [x] 7.4 Atualizar `manifest.json` para declarar `aura_config.js` antes de `background.js`
    - Adicionar `aura_config.js` à lista de scripts de background antes de `background.js`
    - Adicionar campo `_config_injection_note` com instrução de injeção para produção
    - _Requirements: 6.4_

- [x] 8. Criar `extension/tests/integration.test.js`
  - [x] 8.1 Testes de transição de modo (6 transições)
    - `assist → gps`: teardown assist, init gps
    - `assist → train`: teardown assist, init gps + mission (ordem correta)
    - `assist → prove`: teardown assist, init gps + mission (ordem correta)
    - `gps → assist`: teardown gps, init assist
    - `train → assist`: teardown mission + gps, init assist
    - `prove → assist`: teardown mission + gps, init assist
    - _Requirements: 7.2, 7.3_

  - [x] 8.2 Teste de proteção contra reentrada do GPS
    - Chamar `AuraGpsEngine.init()` duas vezes sem `teardown()` entre elas
    - Verificar que o número de listeners no document é igual ao de uma única chamada
    - _Requirements: 3.1, 7.6_

  - [x] 8.3 Teste de `element_absent` com delay mínimo
    - Criar passo com `validation_type: 'element_absent'` e seletor ausente no DOM
    - Verificar que `gps:step_validated` não é emitido antes de 500ms
    - _Requirements: 3.5, 7.7_

  - [x] 8.4 Teste de penalidades distintas em modo `prove`
    - Simular `gps:step_timeout` e verificar que penalidade é `timeout_penalty` (10)
    - Simular `gps:step_failed` e verificar que penalidade é `error_penalty` (15)
    - _Requirements: 4.4, 7.5_

  - [x] 8.5 Teste de ciclo completo de missão em modo `train`
    - `setMode('train')` → HUD criado → passo iniciado → passo validado → XP incrementado → dots atualizados → `gps:completed` → resumo exibido → HUD removido
    - _Requirements: 7.4_

  - [x] 8.6 Teste de fluxo GPS fim a fim via Magic Link
    - Simular `?aura_gps=objetivo` → `AURA_FETCH_GPS` → `AURA_GPS_EXPLICIT_RESPONSE` → `setMode('gps')` → `init()` → validação → `gps:completed` → `setMode('assist')`
    - _Requirements: 7.1_

  - [x] 8.7 Teste de `step_error` não duplicado
    - Simular `gps:step_failed` e verificar que `step_error` é emitido exatamente uma vez (pelo GPS, não pela Mission)
    - _Requirements: 5.6, 5.8_

  - [ ]* 8.8 Testes de propriedade com fast-check (opcional)
    - Instalar `fast-check` como devDependency
    - Criar `extension/tests/property.test.js` com as 6 propriedades de correção do design
    - Usar `{ numRuns: 100 }` mínimo por propriedade
    - _Requirements: 1.7, 3.1, 3.5, 4.4, 5.6, 8.2_

## Notas

- Tarefas marcadas com `*` são opcionais
- A ordem das tarefas importa: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
- Nenhum módulo é reescrito — apenas patches cirúrgicos
- Os 6 testes de regressão existentes em `regression.test.js` devem continuar passando após cada tarefa
- `aura_config.js` nunca deve conter tokens reais — usar apenas em desenvolvimento local
- O `manifest.json` pode ser MV2 ou MV3 — verificar a versão atual antes de editar `background.scripts`

# Plano de Implementação: Aura DAP Restructure

## Visão Geral

Reorganização modular do `content.js` monolítico em oito módulos com responsabilidades explícitas, introdução do estado global `aura_mode`, separação do GPS como fluxo intencional independente, consolidação do fluxo Background → Bridge → Content, e formalização do contrato Step_Model. O backend Python é afetado minimamente.

## Tarefas

- [x] 1. Criar contrato canônico Step_Model e estrutura de diretórios
  - Criar `contracts/step_model.json` com todos os campos definidos no design
  - Criar o diretório `extension/modules/` para os módulos futuros
  - Criar `extension/modules/aura_state.js` com interface pública `window.AuraState` (mode, session, setMode, getMode, resetSession) — sem lógica de teardown/init ainda, apenas o esqueleto de estado
  - _Requirements: 3.5, 7.1, 7.2_

- [x] 2. Implementar `aura_state` com transição de modo
  - [x] 2.1 Implementar `setMode(newMode)` com chamada a `teardown()` do módulo ativo e `init()` do novo módulo
  - Garantir que `aura_mode` sempre contenha exatamente um valor válido: `assist`, `gps`, `train`, `prove`
  - Tratar exceção em `teardown()` com log e continuação da transição
  - _Requirements: 1.1, 1.5, 1.6_

  - [ ]* 2.2 Escrever property test para exclusividade de modo (Property 1)
    - **Property 1: Exclusividade de modo**
    - **Validates: Requirements 1.1, 1.5, 1.6**
    - Usar `fc.constantFrom('assist','gps','train','prove')` para sequências de chamadas a `setMode`
    - Verificar que `getMode()` retorna exatamente um valor válido após qualquer sequência

- [x] 3. Implementar módulos de UI e utilitários base
  - [x] 3.1 Criar `extension/modules/aura_ui.js` com `window.AuraUI`
    - Extrair de `content.js`: `exibirBalao`, `exibirBaloesSequenciais`, `esconderBalao`, `ativarBadge`, `desativarBadge`, `tocarAnimacao`
    - Preservar lógica de drag, auto-hide e trava de engajamento (`_bubbleEngajada`)
    - _Requirements: 7.1, 11.1_

  - [x] 3.2 Criar `extension/modules/aura_dom_mapper.js` com `window.AuraDomMapper`
    - Extrair `capturarDOMParaIA()` de `content.js` para `AuraDomMapper.capturar()`
    - _Requirements: 7.3_

  - [x] 3.3 Criar `extension/modules/aura_spotlight.js` com `window.AuraSpotlight`
    - Extrair `aplicarHolofoteDom`, `encontrarElementoNaTela`, `criarBackdrop` de `content.js`
    - Expor `aplicar(seletorOuId, isSeletor)`, `remover()`, `encontrarElemento(seletor)`
    - Preservar suporte a iframes do Senior X
    - _Requirements: 7.4, 11.3, 11.7_

  - [x] 3.4 Criar `extension/modules/aura_feedback.js` com `window.AuraFeedback`
    - Extrair `_criarBarraFeedback` de `content.js` para `AuraFeedback.criar(prompt, resposta)`
    - _Requirements: 7.8_

- [x] 4. Checkpoint — Verificar módulos base
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 5. Implementar `aura_gps_engine` com Step_Model canônico
  - [x] 5.1 Criar `extension/modules/aura_gps_engine.js` com `window.AuraGpsEngine`
    - Implementar `init(roteiro)` e `teardown()`
    - Implementar `normalizeStep(step)` aplicando defaults do Step_Model para campos ausentes (validation_type, timeout_sec, xp_value, xp_penalty_per_hint, difficulty, hint)
    - Emitir aviso no console para cada campo com default aplicado
    - Consumir Step_Model diretamente sem achatamento
    - _Requirements: 3.2, 3.4, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.2 Escrever property test para Step_Model com campos ausentes (Property 3)
    - **Property 3: Step_Model com campos ausentes não falha silenciosamente**
    - **Validates: Requirements 3.4**
    - Usar `fc.record({ intent: fc.string() })` como passo mínimo
    - Verificar que `normalizeStep` retorna objeto com todos os campos obrigatórios preenchidos

  - [x] 5.3 Implementar validadores por `validation_type`
    - Implementar listeners para: `click`, `right_click`, `double_click`, `type`, `enter`
    - Implementar observers para: `url_change`, `element_present`, `element_absent`
    - Implementar fallback para `visual_state` (log de aviso + trata como `click`)
    - Implementar fallback para `validation_type` não reconhecido (log de aviso + `click`)
    - Cada validador bem-sucedido emite `CustomEvent('gps:step_validated')` no `document`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [ ]* 5.4 Escrever property test para validação orientada a tipo (Property 4)
    - **Property 4: Validação orientada a tipo — round trip de ação**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**
    - Para cada `validation_type` suportado, simular a ação correspondente e verificar emissão de `gps:step_validated`
    - Verificar que não simular a ação não emite o evento

  - [x] 5.5 Implementar painel de navegação GPS e eventos de ciclo de vida
    - Exibir intent do passo atual em painel sem HUD gamificado
    - Aplicar `AuraSpotlight.aplicar()` no `target_selector` do passo atual
    - Emitir `gps:step_failed`, `gps:completed`, `gps:abandoned` nos momentos corretos
    - Ao concluir último passo: exibir mensagem de conclusão e chamar `AuraState.setMode('assist')`
    - Ao abandonar: emitir `gps:abandoned` e chamar `AuraState.setMode('assist')`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 6. Implementar `aura_assist_engine`
  - [x] 6.1 Criar `extension/modules/aura_assist_engine.js` com `window.AuraAssistEngine`
    - Extrair de `content.js`: idle timer, balões proativos, input de pergunta, `dispararAnalise`
    - Implementar `init()`, `teardown()`, `dispararAnalise(textoOpcional)`, `resetarProatividade()`
    - _Requirements: 7.5, 11.1, 11.2, 11.5, 11.6_

  - [x] 6.2 Implementar CTA explícito para GPS ao receber `gps_passos`
    - Ao receber `AURA_RESPONSE` com `gps_passos`, apresentar opção explícita ao usuário via `AuraUI.exibirBalao`
    - Não alterar `aura_mode` automaticamente — aguardar confirmação do usuário
    - Somente após confirmação: chamar `AuraState.setMode('gps')` e `AuraGpsEngine.init(roteiro)`
    - _Requirements: 2.2, 2.4_

  - [ ]* 6.3 Escrever property test para GPS não iniciar automaticamente (Property 2)
    - **Property 2: GPS não inicia automaticamente a partir de resposta IA**
    - **Validates: Requirements 2.2, 2.4**
    - Para qualquer payload com `gps_passos`, verificar que `AuraState.getMode()` permanece `assist` sem ação explícita do usuário

- [x] 7. Implementar `aura_mission_engine`
  - [x] 7.1 Criar `extension/modules/aura_mission_engine.js` com `window.AuraMissionEngine`
    - Implementar `init(scoringConfig)` e `teardown()`
    - Registrar listeners para `gps:step_validated`, `gps:step_failed`, `gps:completed`
    - Exibir HUD apenas quando `aura_mode` for `train` ou `prove`
    - Extrair lógica de HUD, XP, hints e resumo do `_mission` atual em `content.js`
    - _Requirements: 6.1, 6.2, 7.7_

  - [x] 7.2 Implementar lógica de hints por modo
    - Modo `train`: hints permitidos com custo `xp_penalty_per_hint` do Step_Model
    - Modo `prove`: hints desabilitados ou limitados a 1 por sessão
    - _Requirements: 6.3, 6.4_

  - [ ]* 7.3 Escrever property test para instrumentação GPS sem acoplamento (Property 5)
    - **Property 5: Instrumentação GPS pela Mission sem acoplamento**
    - **Validates: Requirements 6.1, 6.2, 4.5**
    - Em modo `train`/`prove`: verificar que eventos GPS são recebidos e XP é atualizado
    - Em modo `gps`: verificar que os mesmos eventos não acionam lógica de XP ou HUD

  - [ ]* 7.4 Escrever property test para hints em modo prove (Property 6)
    - **Property 6: Hints desabilitados ou limitados em modo prove**
    - **Validates: Requirements 6.3, 6.4**
    - Verificar que em modo `prove` o total de hints concedidos é ≤ 1 por sessão
    - Verificar que em modo `train` hints são permitidos com custo de XP

  - [x] 7.5 Implementar cálculo de score final e resumo de performance
    - Calcular bônus de autonomia quando nenhum hint for solicitado
    - Distinguir Modo_Treinar e Modo_Provar no resumo exibido
    - Aplicar penalidade de XP em `gps:step_failed` conforme `scoring.error_penalty`
    - _Requirements: 6.5, 6.6, 6.7, 6.8_

- [x] 8. Checkpoint — Verificar motores GPS e Mission
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 9. Implementar Analytics Events
  - [x] 9.1 Adicionar emissão de `gps_start` no `aura_gps_engine.init()`
    - Payload: `roteiro_id`, `timestamp`, `mode`
    - _Requirements: 9.1_

  - [x] 9.2 Adicionar emissão de `step_complete` e `step_error` no `aura_gps_engine`
    - `step_complete` payload: `step_id`, `step_index`, `validation_type`, `duration_sec`
    - `step_error` payload: `step_id`, `step_index`, `validation_type`
    - _Requirements: 9.2, 9.4_

  - [x] 9.3 Adicionar emissão de `session_abandoned` e `hint_requested` nos engines
    - `session_abandoned` no `aura_gps_engine`: `step_index_at_abandon`, `steps_total`
    - `hint_requested` no `aura_mission_engine`: `step_id`, `step_index`, `hints_total_session`
    - _Requirements: 9.3, 9.5_

  - [x] 9.4 Adicionar emissão de `mission_complete` no `aura_mission_engine`
    - Payload: `roteiro_id`, `mode`, `score_final`, `xp_final`, `hints_used`, `errors_count`, `duration_sec`
    - _Requirements: 9.6_

  - [x] 9.5 Implementar envio de analytics via `postMessage` para o Background
    - Content script envia evento via `postMessage` com `type: "AURA_ANALYTICS_EVENT"`
    - _Requirements: 9.7_

  - [ ]* 9.6 Escrever property test para campos obrigatórios em analytics events (Property 7)
    - **Property 7: Analytics events contêm campos obrigatórios**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6**
    - Para cada `event_type`, verificar que o payload contém todos os campos obrigatórios definidos

- [x] 10. Consolidar `background.js`
  - [x] 10.1 Centralizar token e endpoints no topo do arquivo
    - Substituir todas as strings de URL inline por constantes em `AURA_ENDPOINTS`
    - Substituir todos os tokens inline por constante `AURA_AUTH_TOKEN` lida de configuração injetada
    - _Requirements: 8.5, 8.6, 10.1, 10.2_

  - [x] 10.2 Remover ação `buscar_gps` e adicionar `fetch_gps_explicit` e `analytics_event`
    - Remover o handler `buscar_gps` e a lógica de regex de intenção GPS do fluxo `analisar_agora`
    - Adicionar handler `fetch_gps_explicit` para chamada explícita de roteiro GPS
    - Adicionar handler `analytics_event` que encaminha ao endpoint `/api/analytics/event`
    - Implementar fila local em memória para retry de analytics quando endpoint indisponível (máx 3 tentativas)
    - _Requirements: 2.5, 8.1, 8.2, 9.7, 9.8_

  - [x] 10.3 Implementar retorno `{ error: "unknown_action" }` para ações não reconhecidas
    - _Requirements: 8.7_

  - [ ]* 10.4 Escrever property test para background com ação desconhecida (Property 9)
    - **Property 9: Background retorna erro para ação desconhecida**
    - **Validates: Requirements 8.7**
    - Para qualquer string de ação não reconhecida, verificar que a resposta é `{ error: "unknown_action" }` sem exceção

- [x] 11. Implementar segurança operacional no Content Script
  - [x] 11.1 Adicionar validação de origem em todos os `window.addEventListener("message")`
    - Rejeitar mensagens com `event.origin !== window.location.origin`
    - Ignorar silenciosamente mensagens sem campo `type` esperado
    - _Requirements: 10.3, 10.4, 10.5_

  - [ ]* 11.2 Escrever property test para validação de origem de mensagens (Property 8)
    - **Property 8: Validação de origem de mensagens**
    - **Validates: Requirements 10.3, 10.4, 10.5**
    - Para qualquer mensagem com `origin` diferente de `window.location.origin`, verificar que é ignorada
    - Para mensagens sem campo `type`, verificar descarte silencioso

- [x] 12. Implementar entradas explícitas para o modo GPS
  - [x] 12.1 Implementar handler de Magic Link no `content.js` orquestrador
    - Detectar `?aura_mission` na URL e chamar `AuraState.setMode('train')` ou `'prove'` conforme payload
    - Remover parâmetro da URL após detecção (já existe, preservar comportamento)
    - _Requirements: 2.1, 11.4_

  - [x] 12.2 Implementar handler `AURA_GPS_EXPLICIT_RESPONSE` no content script
    - Remover listener `AURA_GPS_RESPONSE` como caminho paralelo
    - Consolidar resposta GPS em `AURA_RESPONSE` ou em `AURA_GPS_EXPLICIT_RESPONSE`
    - _Requirements: 8.3_

- [x] 13. Refatorar `content.js` como orquestrador
  - Reescrever `content.js` como entry point que importa e inicializa os módulos via `<script>` sequencial ou IIFE com namespace `window.AuraModules`
  - Remover toda lógica de negócio inline — apenas orquestração e wiring
  - Garantir que `bridge.js` permanece sem lógica de negócio própria
  - Preservar detecção de SPA (MutationObserver de URL) chamando `AuraAssistEngine.resetarProatividade()`
  - _Requirements: 7.1, 8.4, 11.6_

- [x] 14. Checkpoint final — Regressão e integração
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 15. Testes de regressão das funcionalidades existentes
  - [x] 15.1 Escrever testes de exemplo para funcionalidades preservadas
    - Clique no mascote → `AuraUI.exibirBalao` chamado com input
    - Resposta com `seletor_css` → `AuraSpotlight.aplicar` chamado
    - URL com `aura_mission` → missão carregada via `AuraState.setMode`
    - Idle 15s → `AuraAssistEngine` exibe balões sequenciais proativos
    - Troca de URL SPA → `AuraAssistEngine.resetarProatividade()` chamado
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [ ]* 15.2 Escrever teste de exemplo para spotlight dentro de iframe
    - Verificar que `AuraSpotlight.encontrarElemento` busca em `document` e em iframes
    - _Requirements: 11.7_

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- Cada tarefa referencia requirements específicos para rastreabilidade
- Os módulos usam namespace global `window.AuraModules` — sem bundler, carregados via `<script>` sequencial
- Testes de propriedade usam [fast-check](https://github.com/dubzzz/fast-check) com `{ numRuns: 100 }` mínimo
- Cada property test deve incluir comentário: `// Feature: aura-dap-restructure, Property N: <texto>`
- O `background.js` deve ler `AURA_AUTH_TOKEN` de configuração injetada, nunca hardcoded

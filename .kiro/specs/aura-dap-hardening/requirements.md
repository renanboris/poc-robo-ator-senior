# Documento de Requisitos — aura-dap-hardening

## Introdução

Esta spec consolida o endurecimento da arquitetura Aura DAP após a modularização bem-sucedida da spec `aura-dap-restructure`. O objetivo é corrigir lacunas de governança identificadas no código atual: a máquina de estado não é maestro completo para os modos `train`/`prove`, o `AuraGpsEngine` tem vulnerabilidades de reentrada e timeout silencioso, o `AuraMissionEngine` tem dots de progresso quebrados e abandono não coordenado, o catálogo de analytics tem eventos duplicados e faltantes, e não há mecanismo formal de injeção de configuração. A spec também prepara a arquitetura para suportar roleplay adaptativo no futuro, sem implementá-lo agora.

---

## Glossário

- **AuraState**: Módulo de máquina de estado — única fonte de verdade para `aura_mode` e estado de sessão.
- **AuraGpsEngine**: Motor GPS — executa roteiros passo a passo com validação por `validation_type`.
- **AuraMissionEngine**: Motor de gamificação — instrumenta o GPS com HUD, XP, hints e penalidades.
- **AuraAssistEngine**: Motor de assistência — gerencia idle timer, proatividade e análise IA.
- **Content_Script**: `content.js` — orquestrador puro da extensão (sem lógica de negócio inline).
- **Background_Script**: `background.js` — service worker da extensão; gerencia endpoints e token.
- **Bridge**: `bridge.js` — ponte entre o mundo MAIN e o service worker via `chrome.runtime.sendMessage`.
- **Step_Model**: Contrato canônico de um passo GPS, definido em `contracts/step_model.json`.
- **HUD**: Heads-Up Display do `AuraMissionEngine` — painel flutuante com XP, dots e botões.
- **Magic_Link**: URL com parâmetro `?aura_mission=` ou `?aura_gps=` que dispara um fluxo automaticamente.
- **AURA_CONFIG**: Objeto de configuração injetado no `Background_Script` com token e endpoints.
- **Roteiro**: Artefato JSON central do sistema — lista de passos com metadados pedagógicos e técnicos.
- **Tenant_ID**: Identificador do cliente/organização usado em chamadas de analytics e GPS.
- **scenario_id**: Campo opcional do Step_Model para identificar o cenário de roleplay ao qual o passo pertence.
- **branch_id**: Campo opcional do Step_Model para identificar o ramo de decisão em fluxos com múltiplos desfechos.
- **gps:step_timeout**: Evento customizado emitido quando o timeout de um passo expira antes da validação.
- **gps:step_failed**: Evento customizado emitido quando um passo falha por ação incorreta.
- **steps_total**: Campo de `AuraState.session` que armazena o total de passos do roteiro ativo.

---

## Requisitos

---

### Requisito 1 — AuraState como Maestro Completo

**User Story:** Como desenvolvedor da extensão, quero que `AuraState.setMode('train')` e `setMode('prove')` inicializem automaticamente tanto o `AuraGpsEngine` quanto o `AuraMissionEngine`, para que o orquestrador não precise fazer wiring manual e o HUD apareça sempre que o modo de missão for ativado.

#### Critérios de Aceitação

1. QUANDO `AuraState.setMode('train')` for chamado, O `AuraState` DEVE chamar `AuraGpsEngine.init()` e `AuraMissionEngine.init()` na ordem correta, sem que o `Content_Script` precise chamá-los manualmente.
2. QUANDO `AuraState.setMode('prove')` for chamado, O `AuraState` DEVE chamar `AuraGpsEngine.init()` e `AuraMissionEngine.init()` na ordem correta, sem que o `Content_Script` precise chamá-los manualmente.
3. QUANDO `AuraState.setMode('assist')` for chamado a partir de `train` ou `prove`, O `AuraState` DEVE chamar `AuraMissionEngine.teardown()` e `AuraGpsEngine.teardown()` antes de inicializar o `AuraAssistEngine`.
4. THE `AuraState` DEVE aceitar um objeto de configuração de scoring como parâmetro opcional de `setMode('train')` e `setMode('prove')`, repassando-o ao `AuraMissionEngine.init()`.
5. QUANDO `AuraState.setMode()` for chamado com um roteiro já ativo, O `AuraState` DEVE executar o teardown completo do modo anterior antes de inicializar o novo modo.
6. THE `AuraState` DEVE expor um método `setActiveRoteiro(roteiro, scoringConfig)` que armazena o roteiro e a configuração de scoring na sessão, para que `setMode` possa acessá-los sem parâmetros adicionais.
7. PARA QUALQUER sequência válida de chamadas a `setMode()`, O `AuraState` DEVE garantir que exatamente um módulo esteja ativo por vez, sem listeners órfãos de módulos anteriores.

---

### Requisito 2 — Contrato Canônico do Step_Model Endurecido

**User Story:** Como desenvolvedor, quero que o `Step_Model` inclua campos opcionais para `scenario_id`, `branch_id` e `timeout_penalty_type`, e que `steps_total` seja propagado para `AuraState.session` no momento do `init()` do GPS, para que os dots de progresso do HUD funcionem e a arquitetura esteja preparada para roleplay futuro.

#### Critérios de Aceitação

1. THE `Step_Model` DEVE incluir o campo opcional `scenario_id` do tipo `string`, com descrição indicando que identifica o cenário de roleplay ao qual o passo pertence.
2. THE `Step_Model` DEVE incluir o campo opcional `branch_id` do tipo `string`, com descrição indicando que identifica o ramo de decisão em fluxos com múltiplos desfechos.
3. THE `Step_Model` DEVE incluir o campo opcional `timeout_penalty_type` do tipo `string` com enum `["none", "soft", "hard"]` e default `"soft"`, indicando o tipo de penalidade aplicada quando o timeout expira no modo `prove`.
4. QUANDO `AuraGpsEngine.init(roteiro)` for chamado, O `AuraGpsEngine` DEVE escrever `AuraState.session.steps_total` com o número de passos normalizados do roteiro.
5. QUANDO `AuraGpsEngine.normalizeStep()` processar um passo com `scenario_id` ou `branch_id` presentes, O `AuraGpsEngine` DEVE preservar esses campos no objeto normalizado sem modificação.
6. QUANDO `AuraGpsEngine.normalizeStep()` processar um passo sem `scenario_id` ou `branch_id`, O `AuraGpsEngine` DEVE deixar esses campos ausentes (não aplicar default `null`), para não poluir o payload de analytics.
7. PARA QUALQUER Step_Model válido, a operação de serialização para JSON e desserialização de volta DEVE produzir um objeto com os mesmos campos obrigatórios e opcionais presentes.

---

### Requisito 3 — AuraGpsEngine Endurecido

**User Story:** Como desenvolvedor, quero que o `AuraGpsEngine` seja robusto contra reentrada, timeouts silenciosos e falsos positivos no `element_absent`, para que sessões GPS não deixem listeners órfãos nem validem passos incorretamente em páginas com carregamento lento.

#### Critérios de Aceitação

1. QUANDO `AuraGpsEngine.init()` for chamado enquanto uma sessão GPS já está ativa, O `AuraGpsEngine` DEVE executar `teardown()` completo da sessão anterior antes de inicializar a nova, garantindo que nenhum listener da sessão anterior permaneça ativo.
2. QUANDO `_iniciarPasso()` for chamado enquanto outro passo está em execução, O `AuraGpsEngine` DEVE limpar o validador e o timeout do passo anterior antes de registrar os do novo passo.
3. QUANDO o timeout de um passo expirar, O `AuraGpsEngine` DEVE emitir o evento `gps:step_timeout` com `{ step, stepIndex, timeout_sec }` antes de emitir `gps:step_failed`.
4. QUANDO o timeout de um passo expirar, O `AuraGpsEngine` DEVE reiniciar o validador do passo corrente após emitir `gps:step_timeout`, permitindo que o usuário tente novamente sem precisar reiniciar o GPS.
5. QUANDO `element_absent` for o `validation_type` de um passo e o seletor não existir no DOM no momento da chamada, O `AuraGpsEngine` DEVE aguardar um delay mínimo de 500ms antes de validar a ausência, para evitar falso positivo em carregamentos lentos.
6. QUANDO `AuraGpsEngine.teardown()` for chamado, O `AuraGpsEngine` DEVE remover todos os listeners e observers registrados, limpar todos os timeouts pendentes e remover o painel GPS do DOM.
7. THE `AuraGpsEngine` DEVE expor um método `isActive()` que retorna `true` se uma sessão GPS está em execução e `false` caso contrário, para que outros módulos possam verificar o estado sem acessar variáveis privadas.

---

### Requisito 4 — AuraMissionEngine Endurecido

**User Story:** Como usuário em modo de treino ou certificação, quero que os dots de progresso do HUD reflitam corretamente o avanço nos passos, que o abandono seja coordenado via `AuraState`, e que o modo `prove` aplique penalidades diferentes para timeout e erro de ação, para que a experiência gamificada seja precisa e justa.

#### Critérios de Aceitação

1. QUANDO `AuraMissionEngine.init()` for chamado, O `AuraMissionEngine` DEVE ler `AuraState.session.steps_total` para renderizar os dots de progresso do HUD, exibindo o número correto de dots desde o primeiro passo.
2. QUANDO `AuraState.session.steps_total` for zero ou indefinido no momento do `init()`, O `AuraMissionEngine` DEVE ocultar a área de dots do HUD em vez de renderizar zero dots.
3. QUANDO o botão "Abandonar" do HUD for clicado, O `AuraMissionEngine` DEVE chamar `AuraState.setMode('assist')` e NÃO DEVE chamar `AuraGpsEngine.teardown()` diretamente, delegando o teardown ao ciclo de modo do `AuraState`.
4. QUANDO `gps:step_timeout` for recebido no modo `prove`, O `AuraMissionEngine` DEVE aplicar a penalidade de XP definida em `scoringConfig.timeout_penalty` (default: 10), distinta da penalidade de erro de ação `scoringConfig.error_penalty` (default: 15).
5. QUANDO `gps:step_timeout` for recebido no modo `train`, O `AuraMissionEngine` DEVE exibir uma mensagem de encorajamento via `AuraUI.exibirBalao()` sem aplicar penalidade de XP.
6. QUANDO `gps:step_failed` for recebido, O `AuraMissionEngine` DEVE aplicar a penalidade `scoringConfig.error_penalty` e NÃO DEVE emitir o evento de analytics `step_error` (pois o `AuraGpsEngine` já o emite).
7. QUANDO `gps:step_validated` for recebido, O `AuraMissionEngine` DEVE atualizar `_currentStepIdx` para o índice do próximo passo e re-renderizar os dots de progresso.
8. THE `AuraMissionEngine` DEVE expor um método `getScore()` que retorna o objeto `{ xp, hintsUsed, errorsCount, durationSec }` para uso em testes e em resumos externos.

---

### Requisito 5 — Catálogo de Analytics Formalizado

**User Story:** Como analista de dados, quero que todos os eventos de analytics da extensão Aura tenham payloads canônicos documentados, sem duplicação entre módulos, e que os eventos faltantes sejam adicionados, para que os dados coletados sejam confiáveis e completos.

#### Critérios de Aceitação

1. THE `AuraAssistEngine` DEVE emitir o evento `assist_prompt_sent` com payload `{ prompt_length: number, tenant_id: string, timestamp: string }` ao disparar uma análise IA.
2. THE `AuraAssistEngine` DEVE emitir o evento `assist_response_received` com payload `{ has_gps: boolean, has_spotlight: boolean, tenant_id: string, timestamp: string }` ao processar uma resposta `AURA_RESPONSE`.
3. THE `AuraGpsEngine` DEVE emitir o evento `gps_step_started` com payload `{ step_id: string|null, step_index: number, roteiro_id: string|null, tenant_id: string, timestamp: string }` ao iniciar cada passo.
4. THE `AuraGpsEngine` DEVE incluir `tenant_id` no payload do evento `gps_start`, lendo o valor de `AuraState.session.tenant_id` ou usando `"senior_default"` como fallback.
5. THE `AuraMissionEngine` DEVE emitir o evento `mission_start` com payload `{ roteiro_id: string|null, mode: string, base_xp: number, steps_total: number, timestamp: string }` ao inicializar.
6. QUANDO `AuraMissionEngine` receber `gps:step_failed`, O `AuraMissionEngine` NÃO DEVE emitir o evento `step_error` via analytics, pois o `AuraGpsEngine` já o emite, eliminando a duplicação atual.
7. THE `Background_Script` DEVE rejeitar eventos de analytics com `event_type` não presente no catálogo canônico, retornando `{ ok: false, reason: "event_type_unknown" }` ao remetente.
8. PARA QUALQUER fluxo GPS completo (init → passos → conclusão), a sequência de eventos de analytics emitidos DEVE conter exatamente um `gps_start`, N `gps_step_started`, N `step_complete` e um `mission_complete` ou `session_abandoned`, sem repetições do mesmo `event_type` para o mesmo `step_index`.

---

### Requisito 6 — Mecanismo de Configuração do Background Script

**User Story:** Como engenheiro de implantação, quero que o mecanismo de injeção do `AURA_CONFIG` esteja documentado e que os endpoints possam ser trocados para produção sem alterar o código-fonte, para que a extensão possa ser distribuída em ambientes diferentes sem recompilação.

#### Critérios de Aceitação

1. THE `Background_Script` DEVE ler `AURA_CONFIG.authToken`, `AURA_CONFIG.endpoints.analyze`, `AURA_CONFIG.endpoints.missions`, `AURA_CONFIG.endpoints.gps` e `AURA_CONFIG.endpoints.analytics` quando o objeto `AURA_CONFIG` estiver definido no escopo global do service worker.
2. QUANDO `AURA_CONFIG` não estiver definido, O `Background_Script` DEVE usar os valores de fallback de `localhost` para endpoints e string vazia para o token, sem lançar exceção.
3. THE `Background_Script` DEVE expor uma função `getConfig()` que retorna o objeto de configuração ativo (sem expor o token), para fins de diagnóstico e testes.
4. THE `manifest.json` DEVE incluir um comentário ou campo `_config_injection_note` documentando que `AURA_CONFIG` deve ser injetado via script declarado em `background.scripts` antes de `background.js`.
5. QUANDO `AURA_CONFIG.endpoints` contiver uma URL que não começa com `https://` ou `http://localhost`, O `Background_Script` DEVE registrar um aviso no console sem bloquear a inicialização.
6. THE `Background_Script` DEVE expor `AURA_ENDPOINTS` como objeto imutável (via `Object.freeze`) após a inicialização, para evitar mutação acidental em runtime.

---

### Requisito 7 — Testes de Integração e Transição de Modos

**User Story:** Como desenvolvedor, quero testes automatizados que cubram o fluxo GPS fim a fim, as transições de modo e o ciclo completo de missão, para que regressões nos fluxos críticos sejam detectadas antes de chegar à produção.

#### Critérios de Aceitação

1. THE `Regression_Test_Suite` DEVE incluir um teste que simule o fluxo completo: Magic Link `?aura_gps=objetivo` → `AURA_FETCH_GPS` → `AURA_GPS_EXPLICIT_RESPONSE` → `setMode('gps')` → `AuraGpsEngine.init()` → validação de passo → `gps:completed` → `setMode('assist')`.
2. THE `Regression_Test_Suite` DEVE incluir testes para as transições de modo: `assist → gps`, `assist → train`, `assist → prove`, `gps → assist`, `train → assist`, `prove → assist`.
3. PARA CADA transição de modo testada, O teste DEVE verificar que o módulo do modo anterior teve `teardown()` chamado e o módulo do novo modo teve `init()` chamado.
4. THE `Regression_Test_Suite` DEVE incluir um teste para o ciclo completo de missão no modo `train`: `setMode('train')` → HUD criado → passo iniciado → passo validado → XP incrementado → dots atualizados → `gps:completed` → resumo exibido → HUD removido.
5. THE `Regression_Test_Suite` DEVE incluir um teste para o ciclo completo de missão no modo `prove`: verificando que penalidade de timeout (`timeout_penalty`) é diferente da penalidade de erro (`error_penalty`).
6. THE `Regression_Test_Suite` DEVE incluir um teste que verifique que `AuraGpsEngine.init()` chamado duas vezes sem `teardown()` não deixa listeners duplicados (proteção contra reentrada).
7. THE `Regression_Test_Suite` DEVE incluir um teste que verifique que `element_absent` não valida imediatamente quando o seletor está ausente no DOM, aguardando o delay mínimo de 500ms.
8. PARA QUALQUER sequência de transições de modo válidas, O `AuraState` DEVE garantir que `getMode()` retorna exatamente o último modo definido e que nenhum módulo anterior permanece ativo.

---

### Requisito 8 — Preparação Arquitetural para Roleplay

**User Story:** Como arquiteto do sistema, quero que o `AuraGpsEngine` e o `AuraMissionEngine` exponham interfaces extensíveis para suportar futuramente cenários, branching e múltiplos desfechos, sem implementar roleplay agora, para que a evolução futura não exija reescrita dos módulos.

#### Critérios de Aceitação

1. THE `AuraGpsEngine` DEVE aceitar um campo opcional `onBranchDecision(step, nextStepIndex)` no objeto de configuração do `init()`, chamado quando um passo com `branch_id` é concluído, permitindo que o chamador redirecione o fluxo para um índice diferente.
2. QUANDO `onBranchDecision` não for fornecido, O `AuraGpsEngine` DEVE continuar o fluxo sequencial normal, sem alteração de comportamento.
3. THE `AuraMissionEngine` DEVE aceitar um campo opcional `onOutcomeEvaluated(score, mode)` no objeto de configuração do `init()`, chamado ao final da missão antes de exibir o resumo, permitindo que o chamador injete lógica de avaliação customizada.
4. QUANDO `onOutcomeEvaluated` não for fornecido, O `AuraMissionEngine` DEVE usar a lógica de resumo padrão baseada em XP e hints.
5. THE `Step_Model` DEVE documentar os campos `scenario_id` e `branch_id` como "reservados para uso futuro em fluxos de roleplay adaptativo" no arquivo `contracts/step_model.json`.
6. THE `AuraGpsEngine` DEVE emitir o evento `gps:branch_point` com `{ step, stepIndex, branch_id, scenario_id }` quando um passo com `branch_id` for concluído, para que listeners externos possam reagir sem modificar o motor.
7. QUANDO `gps:branch_point` for emitido e nenhum listener externo redirecionar o fluxo dentro de um tick síncrono, O `AuraGpsEngine` DEVE avançar para o próximo passo sequencial normalmente.

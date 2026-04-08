# Requirements Document

## Introduction

Este spec define a reorganização estrutural da extensão Aura DAP, separando as três camadas lógicas que hoje coexistem acopladas em `content.js`: o Assistente contextual (Aura Assist), o GPS de navegação passo a passo (Aura GPS) e o motor de Gamificação/Academia. O objetivo é transformar a extensão em uma arquitetura clara, evolutiva e com fronteiras explícitas entre modos de operação, sem redesign visual completo e sem refactor do backend Python além do necessário para consolidar contratos.

## Glossary

- **Aura_Assist**: Camada de assistente conversacional e contextual — mascote, input/chat, proatividade, sugestões, feedback e spotlight de ajuda.
- **Aura_GPS**: Motor de navegação passo a passo operacional — carregamento explícito de roteiros, execução de steps, validação por tipo de ação, progresso operacional.
- **Aura_Mission**: Motor de gamificação que instrumenta o GPS — XP, score, hints com custo, penalidade por erro, modo treino, modo certificação.
- **Step_Model**: Estrutura canônica de um passo GPS contendo: `id`, `title`, `intent`, `ancora`, `tooltip`, `acao`, `target_selector`, `label`, `validation_type`, `expected_state`, `timeout_sec`, `hint`, `difficulty`, `xp_value`, `xp_penalty_per_hint`.
- **Validation_Type**: Tipo de ação esperada para validar conclusão de um passo: `click`, `right_click`, `double_click`, `type`, `enter`, `url_change`, `element_present`, `element_absent`, `visual_state`.
- **HUD**: Heads-Up Display gamificado exibido durante missões — mostra XP, progresso, intent do passo atual e botão de hint.
- **Magic_Link**: URL com parâmetro `?aura_mission=<id>` que dispara carregamento direto de uma missão.
- **Bridge**: Arquivo `bridge.js` responsável por intermediar mensagens entre o mundo isolado do content script e o service worker.
- **Background**: Service worker `background.js` responsável por chamadas de rede, captura de screenshot e roteamento de mensagens.
- **Content_Script**: Arquivo `content.js` (e seus módulos derivados) injetado na página do Senior X.
- **Spotlight**: Efeito visual de destaque (sonar + backdrop) aplicado sobre um elemento da tela para guiar o usuário.
- **Modo_Assistir**: Modo em que apenas o Aura_Assist está ativo — conversação contextual sem GPS ou missão.
- **Modo_Guiar**: Modo em que o Aura_GPS está ativo sem gamificação — navegação passo a passo operacional pura.
- **Modo_Treinar**: Modo em que o Aura_GPS está ativo com Aura_Mission em modo treino — HUD, XP, hints e score.
- **Modo_Provar**: Modo em que o Aura_GPS está ativo com Aura_Mission em modo certificação — menos ajuda, critérios mais rígidos.
- **Analytics_Event**: Evento registrado para fins de observabilidade: `gps_start`, `mission_start`, `step_complete`, `hint_requested`, `step_error`, `session_abandoned`, `mission_complete`.
- **DOM_Mapper**: Módulo responsável por capturar e mapear elementos interativos visíveis na tela para envio ao backend.
- **Senior_X**: Plataforma ERP alvo onde a extensão Aura opera.

---

## Requirements

### Requirement 1: Separação Explícita dos Modos de Operação

**User Story:** Como desenvolvedor da extensão, quero que Assistente, GPS e Missão sejam modos explicitamente separados, para que cada camada possa evoluir e ser testada de forma independente.

#### Acceptance Criteria

1. THE Content_Script SHALL manter uma variável de estado global `aura_mode` com valores possíveis: `assist`, `gps`, `train`, `prove`.
2. WHEN `aura_mode` é `assist`, THE Aura_Assist SHALL operar normalmente e THE Aura_GPS SHALL permanecer inativo.
3. WHEN `aura_mode` é `gps`, THE Aura_GPS SHALL operar e THE Aura_Mission SHALL permanecer inativo.
4. WHEN `aura_mode` é `train` ou `prove`, THE Aura_GPS SHALL operar e THE Aura_Mission SHALL instrumentar o Aura_GPS.
5. THE Content_Script SHALL expor uma função `setAuraMode(mode)` que realiza a transição entre modos, encerrando o estado anterior antes de iniciar o novo.
6. IF uma transição de modo for solicitada enquanto outro modo está ativo, THEN THE Content_Script SHALL encerrar o modo atual de forma limpa antes de iniciar o novo.

---

### Requirement 2: Entrada Explícita para o Modo GPS

**User Story:** Como usuário do Senior X, quero iniciar o GPS de forma explícita e intencional, para que a navegação guiada não apareça de forma oportunista ou inesperada.

#### Acceptance Criteria

1. THE Aura_GPS SHALL ser ativado exclusivamente por uma das seguintes entradas explícitas: botão/CTA na interface da Aura, opção contextual apresentada pelo Aura_Assist, Magic_Link com parâmetro `aura_mission`, ou mensagem `AURA_START_GPS` enviada via `postMessage`.
2. WHEN o backend retorna `gps_passos` em uma resposta `AURA_RESPONSE`, THE Aura_Assist SHALL apresentar ao usuário uma opção explícita de iniciar o GPS, sem iniciar automaticamente.
3. THE Aura_GPS SHALL operar sem exigir que o Aura_Mission esteja ativo.
4. IF o usuário não confirmar a entrada no modo GPS, THEN THE Aura_Assist SHALL permanecer no Modo_Assistir sem alterar `aura_mode`.
5. THE Background SHALL remover a lógica de detecção heurística por regex de intenção GPS do fluxo principal de análise, consolidando o GPS como fluxo explícito.

---

### Requirement 3: Step Model Canônico

**User Story:** Como desenvolvedor, quero um modelo de passo GPS rico e padronizado, para que os dados não sejam descartados ou achatados ao serem consumidos por diferentes motores.

#### Acceptance Criteria

1. THE Step_Model SHALL conter os campos: `id` (string), `title` (string), `intent` (string), `ancora` (string), `tooltip` (string), `acao` (string), `target_selector` (string), `label` (string), `validation_type` (Validation_Type), `expected_state` (object), `timeout_sec` (number), `hint` (string), `difficulty` (string), `xp_value` (number), `xp_penalty_per_hint` (number).
2. THE Aura_GPS SHALL consumir o Step_Model diretamente sem transformação de achatamento.
3. THE Aura_Mission SHALL ler os campos de scoring (`xp_value`, `xp_penalty_per_hint`, `difficulty`) do Step_Model sem sobrescrever os demais campos.
4. IF um campo obrigatório do Step_Model estiver ausente na resposta do backend, THEN THE Aura_GPS SHALL aplicar o valor padrão definido para aquele campo sem falhar silenciosamente.
5. THE Step_Model SHALL ser definido como contrato compartilhado entre o backend Python e o Content_Script, documentado em `contracts/step_model.json`.

---

### Requirement 4: Motor GPS Independente

**User Story:** Como usuário, quero percorrer um roteiro GPS passo a passo sem que o HUD gamificado seja obrigatório, para que a navegação assistida seja utilizável em contextos operacionais sem gamificação.

#### Acceptance Criteria

1. THE Aura_GPS SHALL carregar um roteiro de passos e exibir o intent do passo atual em um painel de navegação sem HUD gamificado.
2. THE Aura_GPS SHALL avançar para o próximo passo após a validação bem-sucedida do passo atual.
3. THE Aura_GPS SHALL aplicar Spotlight no `target_selector` do passo atual para guiar o usuário visualmente.
4. WHEN o usuário conclui o último passo, THE Aura_GPS SHALL exibir uma mensagem de conclusão e retornar `aura_mode` para `assist`.
5. THE Aura_GPS SHALL expor eventos internos `gps:step_validated`, `gps:step_failed`, `gps:completed` que o Aura_Mission pode escutar para instrumentar sem acoplar.
6. IF o usuário abandonar o GPS explicitamente, THEN THE Aura_GPS SHALL emitir o evento `gps:abandoned` e retornar `aura_mode` para `assist`.

---

### Requirement 5: Validação Orientada a Tipo de Ação

**User Story:** Como desenvolvedor, quero que a validação de conclusão de passo suporte múltiplos tipos de ação, para que missões e GPS não fiquem restritos a clique simples.

#### Acceptance Criteria

1. THE Aura_GPS SHALL suportar os seguintes `validation_type`: `click`, `right_click`, `double_click`, `type`, `enter`, `url_change`, `element_present`, `element_absent`, `visual_state`.
2. WHEN `validation_type` é `click`, THE Aura_GPS SHALL validar o passo ao detectar um clique no elemento correspondente ao `target_selector`.
3. WHEN `validation_type` é `type`, THE Aura_GPS SHALL validar o passo quando o valor do campo `target_selector` corresponder ao `expected_state.value`.
4. WHEN `validation_type` é `enter`, THE Aura_GPS SHALL validar o passo ao detectar a tecla Enter pressionada enquanto o foco está no `target_selector`.
5. WHEN `validation_type` é `url_change`, THE Aura_GPS SHALL validar o passo quando a URL atual corresponder ao padrão definido em `expected_state.url_pattern`.
6. WHEN `validation_type` é `element_present`, THE Aura_GPS SHALL validar o passo quando o seletor em `expected_state.selector` estiver presente no DOM.
7. WHEN `validation_type` é `element_absent`, THE Aura_GPS SHALL validar o passo quando o seletor em `expected_state.selector` não estiver presente no DOM.
8. IF `validation_type` não for reconhecido, THEN THE Aura_GPS SHALL registrar um aviso no console e tratar o passo como validação por `click` como fallback.

---

### Requirement 6: Motor de Gamificação como Instrumentação do GPS

**User Story:** Como designer instrucional, quero que a gamificação opere sobre o GPS sem substituí-lo, para que o modelo de passo rico seja preservado e a gamificação seja uma camada opcional.

#### Acceptance Criteria

1. THE Aura_Mission SHALL escutar os eventos `gps:step_validated`, `gps:step_failed` e `gps:completed` emitidos pelo Aura_GPS para calcular score e XP.
2. THE Aura_Mission SHALL exibir o HUD apenas quando `aura_mode` for `train` ou `prove`.
3. WHEN `aura_mode` é `train`, THE Aura_Mission SHALL permitir hints com custo de XP definido em `xp_penalty_per_hint` do Step_Model.
4. WHEN `aura_mode` é `prove`, THE Aura_Mission SHALL desabilitar hints ou limitar a quantidade máxima de hints por sessão a 1.
5. WHEN o evento `gps:step_failed` é emitido, THE Aura_Mission SHALL aplicar penalidade de XP definida em `scoring.error_penalty`.
6. WHEN o evento `gps:completed` é emitido, THE Aura_Mission SHALL calcular o score final, exibir o resumo de performance e registrar o Analytics_Event `mission_complete`.
7. THE Aura_Mission SHALL calcular bônus de autonomia quando nenhum hint for solicitado durante toda a sessão.
8. THE Aura_Mission SHALL distinguir entre Modo_Treinar e Modo_Provar no resumo de performance exibido ao usuário.

---

### Requirement 7: Reorganização Modular do Content Script

**User Story:** Como desenvolvedor, quero que o content.js seja reorganizado em módulos lógicos com responsabilidades claras, para que o código seja mais legível, testável e evolutivo.

#### Acceptance Criteria

1. THE Content_Script SHALL ser reorganizado nos seguintes módulos lógicos: `aura_state`, `aura_ui`, `aura_dom_mapper`, `aura_spotlight`, `aura_assist_engine`, `aura_gps_engine`, `aura_mission_engine`, `aura_feedback`.
2. THE `aura_state` SHALL ser o único módulo responsável por ler e escrever `aura_mode` e o estado compartilhado da sessão.
3. THE `aura_dom_mapper` SHALL encapsular toda a lógica de captura e mapeamento de elementos interativos do DOM.
4. THE `aura_spotlight` SHALL encapsular toda a lógica de criação de backdrop, highlight sonar e scroll para elemento.
5. THE `aura_assist_engine` SHALL encapsular proatividade, idle timer, balões sequenciais, input de pergunta e disparo de análise IA.
6. THE `aura_gps_engine` SHALL encapsular carregamento de roteiro, execução de passos, validação por tipo de ação e emissão de eventos GPS.
7. THE `aura_mission_engine` SHALL encapsular HUD, cálculo de XP, hints, penalidades e resumo de performance.
8. THE `aura_feedback` SHALL encapsular a barra de feedback de qualidade de resposta da IA.
9. WHILE qualquer módulo estiver ativo, THE `aura_state` SHALL ser a única fonte de verdade para o estado global da sessão.

---

### Requirement 8: Consolidação do Fluxo Background/Bridge/Content

**User Story:** Como desenvolvedor, quero um fluxo único e oficial de comunicação entre background, bridge e content, para que caminhos redundantes ou parcialmente mortos sejam eliminados.

#### Acceptance Criteria

1. THE Background SHALL processar as seguintes ações exclusivas: `analisar_agora`, `fetch_mission`, `pre_capture`.
2. THE Background SHALL remover a ação `buscar_gps` como caminho independente, consolidando o GPS no fluxo de `analisar_agora` ou em chamada explícita separada via `fetch_gps_explicit`.
3. THE Content_Script SHALL remover o listener `AURA_GPS_RESPONSE` como caminho paralelo, consolidando a resposta GPS dentro de `AURA_RESPONSE` ou em mensagem `AURA_GPS_EXPLICIT_RESPONSE`.
4. THE Bridge SHALL ser o único intermediário entre o mundo isolado do content script e o Background, sem lógica de negócio própria.
5. THE Background SHALL centralizar todas as URLs de endpoint em constantes no topo do arquivo, lidas a partir de variáveis de ambiente ou configuração injetada.
6. THE Background SHALL centralizar o token de autenticação em uma única constante, sem repetição inline em múltiplas chamadas fetch.
7. IF o Background receber uma ação não reconhecida, THEN THE Background SHALL retornar `{ error: "unknown_action" }` sem lançar exceção.

---

### Requirement 9: Persistência e Analytics Mínimos

**User Story:** Como gestor de treinamento, quero que eventos de sessão sejam registrados, para que seja possível analisar desempenho, abandono e uso de hints ao longo do tempo.

#### Acceptance Criteria

1. THE Aura_GPS SHALL registrar o Analytics_Event `gps_start` ao iniciar uma sessão GPS, contendo: `roteiro_id`, `timestamp`, `mode`.
2. THE Aura_GPS SHALL registrar o Analytics_Event `step_complete` ao validar cada passo, contendo: `step_id`, `step_index`, `validation_type`, `duration_sec`.
3. THE Aura_Mission SHALL registrar o Analytics_Event `hint_requested` ao exibir um hint, contendo: `step_id`, `step_index`, `hints_total_session`.
4. THE Aura_GPS SHALL registrar o Analytics_Event `step_error` ao detectar uma ação incorreta em um passo, contendo: `step_id`, `step_index`, `validation_type`.
5. THE Aura_GPS SHALL registrar o Analytics_Event `session_abandoned` quando o usuário encerrar o GPS antes da conclusão, contendo: `step_index_at_abandon`, `steps_total`.
6. THE Aura_Mission SHALL registrar o Analytics_Event `mission_complete` ao concluir uma missão, contendo: `roteiro_id`, `mode`, `score_final`, `xp_final`, `hints_used`, `errors_count`, `duration_sec`.
7. THE Content_Script SHALL enviar os Analytics_Events ao backend via `postMessage` para o Background, que os encaminhará ao endpoint `/api/analytics/event`.
8. IF o endpoint de analytics estiver indisponível, THEN THE Background SHALL registrar o evento em fila local e retentar no próximo ciclo de atividade.

---

### Requirement 10: Segurança Operacional da Extensão

**User Story:** Como responsável técnico, quero que credenciais e endpoints estejam centralizados e isolados, para que a extensão não exponha configuração sensível espalhada pelo código.

#### Acceptance Criteria

1. THE Background SHALL ler o token de autenticação exclusivamente de uma constante `AURA_AUTH_TOKEN` definida em um arquivo de configuração separado ou injetada via manifest/build, nunca hardcoded inline.
2. THE Background SHALL ler todas as URLs de endpoint de uma constante `AURA_ENDPOINTS` centralizada, sem repetição de strings de URL em múltiplas chamadas.
3. THE Content_Script SHALL validar a origem de todas as mensagens recebidas via `window.addEventListener("message")` antes de processar o payload.
4. THE Content_Script SHALL rejeitar mensagens cuja `event.origin` não corresponda a `window.location.origin`.
5. IF uma mensagem recebida não contiver o campo `type` esperado, THEN THE Content_Script SHALL ignorar a mensagem silenciosamente sem lançar exceção.

---

### Requirement 11: Regressão — Preservação das Funcionalidades Existentes

**User Story:** Como usuário atual da Aura, quero que o spotlight, a bolha principal, o magic link e o fluxo conversacional continuem funcionando após a reorganização, para que a reestruturação não quebre o que já funciona.

#### Acceptance Criteria

1. WHEN o usuário clica no mascote da Aura em Modo_Assistir, THE Aura_Assist SHALL exibir o balão principal com input de pergunta.
2. WHEN o usuário envia uma pergunta, THE Aura_Assist SHALL disparar a análise IA e exibir a resposta com opções de sugestão.
3. WHEN a resposta da IA contém `seletor_css` ou `elemento_id`, THE Aura_Spotlight SHALL aplicar o spotlight no elemento correspondente.
4. WHEN a URL contém o parâmetro `aura_mission`, THE Content_Script SHALL detectar o Magic_Link e iniciar o carregamento da missão correspondente.
5. WHEN o usuário permanece inativo por 15 segundos, THE Aura_Assist SHALL exibir os balões sequenciais proativos conforme comportamento atual.
6. WHEN a URL da SPA muda, THE Content_Script SHALL detectar a troca de tela e resetar o estado proativo do Aura_Assist.
7. THE Aura_Spotlight SHALL continuar funcionando dentro de iframes do Senior X após a reorganização modular.

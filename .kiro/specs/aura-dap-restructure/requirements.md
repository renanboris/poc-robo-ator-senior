# Requirements Document

## Introduction

Este spec descreve a **segunda passada** da reestruturação da extensão Aura DAP. A primeira passada entregou oito módulos coesos sob `extension/modules/` (aura_state, aura_ui, aura_dom_mapper, aura_spotlight, aura_assist_engine, aura_gps_engine, aura_mission_engine, aura_feedback) e formalizou o Step_Model como contrato compartilhado. Essas decisões permanecem válidas e são preservadas aqui.

Após o lançamento da primeira passada, o código sofreu erosão: foram adicionados scripts soltos no nível raiz da extensão e novos arquivos dentro de `extension/modules/` que não respeitam o desenho original. O resultado é um emaranhado com responsabilidades duplicadas, três motores de navegação passo-a-passo, três sistemas de highlight, três sistemas de tooltip e três convenções paralelas de analytics. O `content.js` cresceu para amarrar tudo isso e o `manifest.json` normalizou a presença dos scripts soltos via `web_accessible_resources`.

Esta segunda passada **não redesenha** os módulos da primeira — ela **enforça a disciplina** que a primeira definiu. O objetivo é eliminar caminhos paralelos, absorver comportamento útil dos scripts soltos para dentro dos módulos canônicos, retirar o que é puramente duplicado, e definir contratos verificáveis que evitam regressão futura: disciplina de manifest, contrato de orquestração, responsabilidade única por domínio funcional, transporte único de rede e proibição explícita de caminhos paralelos.

## Glossary

- **Aura_Assist**: Camada de assistente conversacional e contextual — mascote, input/chat, proatividade, sugestões, feedback de qualidade e spotlight de ajuda.
- **Aura_GPS**: Motor de navegação passo a passo operacional — carregamento explícito de roteiros, execução de steps, validação por tipo de ação, progresso operacional.
- **Aura_Mission**: Motor de gamificação que instrumenta o Aura_GPS — XP, score, hints com custo, penalidade por erro, modo treino, modo certificação.
- **Step_Model**: Estrutura canônica de um passo GPS contendo: `id`, `title`, `intent`, `ancora`, `tooltip`, `acao`, `target_selector`, `label`, `validation_type`, `expected_state`, `timeout_sec`, `hint`, `difficulty`, `xp_value`, `xp_penalty_per_hint`.
- **Validation_Type**: Tipo de ação esperada para validar conclusão de um passo: `click`, `right_click`, `double_click`, `type`, `enter`, `url_change`, `element_present`, `element_absent`, `visual_state`.
- **HUD**: Heads-Up Display gamificado exibido durante missões — mostra XP, progresso, intent do passo atual e botão de hint.
- **Magic_Link**: URL com parâmetro `?aura_mission=<id>` ou `?aura_gps=<objetivo>` que dispara carregamento direto de uma missão ou roteiro GPS.
- **Bridge**: Arquivo `bridge.js` responsável por intermediar mensagens entre o mundo MAIN do content script e o service worker.
- **Background**: Service worker `background.js` responsável por chamadas de rede, captura de screenshot e roteamento de mensagens.
- **Content_Script**: Arquivo `content.js` injetado na página do Senior_X, atuando exclusivamente como Orchestrator.
- **Spotlight**: Efeito visual de destaque (sonar + backdrop) aplicado sobre um elemento da tela para guiar o usuário.
- **Modo_Assistir**: Modo em que apenas o Aura_Assist está ativo — conversação contextual sem GPS ou missão.
- **Modo_Guiar**: Modo em que o Aura_GPS está ativo sem gamificação — navegação passo a passo operacional pura.
- **Modo_Treinar**: Modo em que o Aura_GPS está ativo com Aura_Mission em modo treino — HUD, XP, hints e score.
- **Modo_Provar**: Modo em que o Aura_GPS está ativo com Aura_Mission em modo certificação — menos ajuda, critérios mais rígidos.
- **Analytics_Event**: Evento registrado para fins de observabilidade: `gps_start`, `gps_step_started`, `mission_start`, `step_complete`, `hint_requested`, `step_error`, `session_abandoned`, `mission_complete`, `assist_prompt_sent`, `assist_response_received`.
- **DOM_Mapper**: Módulo responsável por capturar e mapear elementos interativos visíveis na tela para envio ao backend.
- **Senior_X**: Plataforma ERP alvo onde a extensão Aura opera.
- **Loose_Script**: Arquivo JavaScript localizado fora de `extension/modules/` ou que registra um global próprio sem passar pela disciplina dos módulos canônicos. Forma indesejada que esta segunda passada elimina, com a única exceção do Boot_Shield.
- **Module_Namespace**: Conjunto de globals oficialmente reconhecidos da extensão, todos prefixados por `Aura` (`AuraState`, `AuraUI`, `AuraDomMapper`, `AuraSpotlight`, `AuraAssistEngine`, `AuraGpsEngine`, `AuraMissionEngine`, `AuraFeedback`). Nenhum outro global pode ser introduzido por código de feature.
- **Orchestration_Contract**: Contrato que define quem orquestra o quê — `content.js` é o único ponto que injeta módulos, registra handlers de ciclo de vida da página e roteia mensagens; `bridge.js` é Transport_Layer puro; cada módulo expõe apenas `init`/`teardown` (e métodos de domínio bem delimitados).
- **Parallel_Path**: Implementação concorrente de uma capacidade que já existe em um módulo canônico (por exemplo: um segundo motor de navegação além do Aura_GPS, um segundo sistema de highlight além do Aura_Spotlight, um segundo canal de analytics além do canal oficial). Forma proibida.
- **Boot_Shield**: Script `shield.js` carregado em `document_start` no mundo MAIN cuja única responsabilidade é proteger e restaurar `window.define` (RequireJS/AMD) durante a janela de boot do Senior_X. É a única exceção tolerada à regra de Module_Namespace, com escopo estritamente delimitado.
- **Transport_Layer**: Camada `bridge.js` cujo único propósito é encaminhar mensagens entre o mundo MAIN e o Background. Não contém regras de negócio, parsing de payload de domínio, nem decisões sobre o que mostrar ao usuário.

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

**User Story:** Como usuário do Senior_X, quero iniciar o GPS de forma explícita e intencional, para que a navegação guiada não apareça de forma oportunista ou inesperada.

#### Acceptance Criteria

1. THE Aura_GPS SHALL ser ativado exclusivamente por uma das seguintes entradas explícitas: botão/CTA na interface da Aura, opção contextual apresentada pelo Aura_Assist, Magic_Link com parâmetro `aura_mission` ou `aura_gps`, ou mensagem `AURA_START_GPS` enviada via `postMessage`.
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
6. THE Aura_GPS SHALL ser o único consumidor do Step_Model — nenhum outro módulo ou Loose_Script pode introduzir um modelo de passo concorrente (`navigation_path`, `steps`, `passos` com schema próprio).

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

**User Story:** Como desenvolvedor, quero que o `content.js` permaneça reorganizado em módulos lógicos com responsabilidades claras, para que o código seja legível, testável e evolutivo.

#### Acceptance Criteria

1. THE Content_Script SHALL ser composto exclusivamente pelos seguintes módulos canônicos sob `extension/modules/`: `aura_state`, `aura_ui`, `aura_dom_mapper`, `aura_spotlight`, `aura_assist_engine`, `aura_gps_engine`, `aura_mission_engine`, `aura_feedback`.
2. THE `aura_state` SHALL ser o único módulo responsável por ler e escrever `aura_mode` e o estado compartilhado da sessão.
3. THE `aura_dom_mapper` SHALL encapsular toda a lógica de captura e mapeamento de elementos interativos do DOM.
4. THE `aura_spotlight` SHALL encapsular toda a lógica de criação de backdrop, highlight sonar e scroll para elemento.
5. THE `aura_assist_engine` SHALL encapsular proatividade, idle timer, balões sequenciais, input de pergunta, disparo de análise IA e detecção proativa de hesitação em campos de input.
6. THE `aura_gps_engine` SHALL encapsular carregamento de roteiro, execução de passos, validação por tipo de ação e emissão de eventos GPS.
7. THE `aura_mission_engine` SHALL encapsular HUD, cálculo de XP, hints, penalidades e resumo de performance.
8. THE `aura_feedback` SHALL encapsular toda coleta de feedback de qualidade — barra inline (👍/👎) e modal de NPS pós-treinamento.
9. WHILE qualquer módulo estiver ativo, THE `aura_state` SHALL ser a única fonte de verdade para o estado global da sessão.
10. THE Content_Script SHALL não conter, em `extension/modules/`, nenhum arquivo além dos oito módulos canônicos listados em 7.1.

---

### Requirement 8: Consolidação do Fluxo Background/Bridge/Content

**User Story:** Como desenvolvedor, quero um fluxo único e oficial de comunicação entre background, bridge e content, para que caminhos redundantes ou parcialmente mortos sejam eliminados.

#### Acceptance Criteria

1. THE Background SHALL processar exclusivamente as seguintes ações: `analisar_agora`, `fetch_mission`, `fetch_gps_explicit`, `pre_capture`, `analytics_event`, `fetch_hint`.
2. THE Background SHALL remover a ação `buscar_gps` como caminho independente, consolidando o GPS no fluxo de `analisar_agora` ou em chamada explícita separada via `fetch_gps_explicit`.
3. THE Content_Script SHALL remover o listener `AURA_GPS_RESPONSE` como caminho paralelo, consolidando a resposta GPS dentro de `AURA_RESPONSE` ou em mensagem `AURA_GPS_EXPLICIT_RESPONSE`.
4. THE Bridge SHALL ser o único intermediário entre o mundo MAIN do Content_Script e o Background, atuando como Transport_Layer puro sem lógica de negócio própria, sem fetch direto a endpoints e sem parsing de payload de domínio.
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
7. THE Content_Script SHALL enviar os Analytics_Events ao backend exclusivamente via `postMessage` do tipo `AURA_ANALYTICS_EVENT`, encaminhado pelo Bridge ao Background, que os roteia ao endpoint canônico de analytics.
8. IF o endpoint de analytics estiver indisponível, THEN THE Background SHALL registrar o evento em fila local e retentar no próximo ciclo de atividade até o limite de 3 tentativas.
9. THE Content_Script SHALL não emitir eventos de analytics por nenhum outro canal — em particular, nenhum módulo ou script pode chamar `fetch` diretamente para endpoints de analytics, e nenhum módulo pode usar tipos de `postMessage` paralelos como `aura_analytics` para esse fim.

---

### Requirement 10: Segurança Operacional da Extensão

**User Story:** Como responsável técnico, quero que credenciais e endpoints estejam centralizados e isolados, para que a extensão não exponha configuração sensível espalhada pelo código.

#### Acceptance Criteria

1. THE Background SHALL ler o token de autenticação exclusivamente de uma constante `AURA_AUTH_TOKEN` definida em arquivo de configuração separado ou injetada via manifest/build, nunca hardcoded inline.
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
7. THE Aura_Spotlight SHALL continuar funcionando dentro de iframes do Senior_X após a reorganização modular.
8. WHEN o usuário hesita por 5 segundos sobre um campo de input não-senha, THE Aura_Assist SHALL consultar o backend por uma dica contextual e exibir a dica próximo ao campo, preservando o comportamento atualmente entregue por `hesitation_detector.js`.
9. WHEN uma sessão em Modo_Treinar ou Modo_Provar é concluída, THE Aura_Feedback SHALL apresentar o modal de NPS pós-treinamento no máximo uma vez por usuário por roteiro, preservando o comportamento atualmente entregue por `nps_modal.js`.

---

### Requirement 12: Consolidação dos Scripts Soltos (Second Pass)

**User Story:** Como mantenedor da extensão, quero que cada script solto introduzido após a primeira reestruturação tenha um destino explícito — absorvido por um módulo canônico, retirado por duplicação, ou mantido com escopo estritamente delimitado — para que o emaranhado atual seja desfeito de uma vez.

#### Acceptance Criteria

1. THE Loose_Script `extension/guided_execution.js` SHALL ser retirado do código fonte, do `manifest.json` e do carregamento sequencial em `content.js`, por configurar um Parallel_Path do Aura_GPS.
2. THE Loose_Script `extension/modules/guided_navigation_controller.js` SHALL ser retirado do código fonte, do `manifest.json` e do carregamento sequencial em `content.js`, por configurar um Parallel_Path do Aura_GPS.
3. THE Loose_Script `extension/modules/navigation_highlighter.js` SHALL ser retirado do código fonte, do `manifest.json` e do carregamento sequencial em `content.js`, por configurar um Parallel_Path do Aura_Spotlight.
4. THE Loose_Script `extension/hesitation_detector.js` SHALL ser absorvido pelo `aura_assist_engine`, com a lógica de detecção de hesitação, consulta ao backend e exibição de dica passando a viver dentro do módulo canônico de proatividade, e o arquivo solto SHALL ser retirado.
5. THE Loose_Script `extension/checklist_widget.js` SHALL ser absorvido pelo `aura_ui` quando o widget for mantido como UX, ou retirado quando não houver decisão de produto que justifique sua presença; em qualquer dos casos, o arquivo solto SHALL ser retirado e seu canal próprio de mensagens (`postMessage` do tipo `aura_analytics`) SHALL ser eliminado.
6. THE Loose_Script `extension/nps_modal.js` SHALL ser absorvido pelo `aura_feedback`, com a lógica de modal NPS, persistência de exibição e envio de score passando a viver dentro do módulo canônico de feedback, e o arquivo solto SHALL ser retirado.
7. THE Loose_Script `extension/shield.js` SHALL ser preservado como Boot_Shield com escopo estritamente delimitado: pode apenas guardar e restaurar `window.define`, não pode introduzir globals adicionais e não pode acoplar-se a nenhum módulo canônico.
8. WHEN um comportamento for absorvido por um módulo canônico, THE módulo absorvedor SHALL preservar a regressão funcional descrita nos critérios 11.8 e 11.9 — a UX entregue ao usuário não pode degradar.
9. THE retirada dos Loose_Scripts SHALL incluir a remoção das entradas correspondentes em `manifest.json#web_accessible_resources` e da lista de módulos carregados sequencialmente por `_carregarModulos` em `content.js`.

---

### Requirement 13: Responsabilidade Única por Domínio

**User Story:** Como mantenedor, quero que cada domínio funcional tenha um único módulo dono, para que novas features estendam o módulo correto em vez de criar caminhos paralelos.

#### Acceptance Criteria

1. THE Aura_Spotlight SHALL ser o único componente autorizado a aplicar destaque visual sobre elementos da página — backdrop, highlight, outline ou borda animada destinados a guiar o olhar do usuário.
2. THE Aura_GPS SHALL ser o único componente autorizado a conduzir navegação passo-a-passo guiada na tela do Senior_X, incluindo o avanço entre passos, a validação de conclusão por `validation_type` e o controle do `target_selector` corrente.
3. THE Aura_Assist SHALL ser o único componente autorizado a executar lógica proativa — idle timer, hesitação em campos, sugestões contextuais, abertura espontânea de balão.
4. THE Aura_Feedback SHALL ser o único componente autorizado a coletar avaliação de qualidade do usuário, seja via barra inline (👍/👎), modal NPS ou outras superfícies de avaliação que venham a existir.
5. THE Aura_UI SHALL ser o único componente autorizado a renderizar superfícies persistentes da Aura na página — balão principal (Speech_Bubble), badge de notificação, chat stack proativo e quaisquer painéis de checklist ou progresso.
6. THE Aura_Mission SHALL ser o único componente autorizado a renderizar HUD gamificado e a calcular XP, score, hints e penalidades.
7. IF uma nova capacidade pertencer a um domínio coberto por um módulo canônico, THEN ela SHALL ser implementada estendendo o módulo dono — nunca criando um arquivo novo fora de `extension/modules/` nem registrando um global concorrente.

---

### Requirement 14: Disciplina do Manifest e Allowlist de Scripts

**User Story:** Como mantenedor, quero que o `manifest.json` declare explicitamente o conjunto autorizado de scripts da extensão, para que adicionar um novo script solto seja uma decisão visível e revisável.

#### Acceptance Criteria

1. THE `manifest.json` SHALL declarar em `content_scripts` no mundo MAIN, em `run_at: document_start`, exclusivamente os arquivos: `shield.js`, `dotlottie-player.js`, `content.js`.
2. THE `manifest.json` SHALL declarar em `content_scripts` no mundo ISOLATED, em `run_at: document_start`, exclusivamente o arquivo: `bridge.js`.
3. THE `manifest.json` SHALL declarar em `web_accessible_resources` exclusivamente os oito módulos canônicos sob `modules/` (`aura_state.js`, `aura_ui.js`, `aura_dom_mapper.js`, `aura_spotlight.js`, `aura_assist_engine.js`, `aura_gps_engine.js`, `aura_mission_engine.js`, `aura_feedback.js`) e os assets estáticos necessários (`aura.json`, `aura_config.js`).
4. THE `manifest.json` SHALL não declarar nenhum dos seguintes arquivos: `guided_execution.js`, `checklist_widget.js`, `hesitation_detector.js`, `nps_modal.js`, `modules/guided_navigation_controller.js`, `modules/navigation_highlighter.js`.
5. IF um novo arquivo precisar ser declarado em `content_scripts` ou em `web_accessible_resources`, THEN a adição SHALL exigir aprovação documentada no spec correspondente — o `manifest.json` não pode crescer por inércia.

---

### Requirement 15: Contrato de Orquestração

**User Story:** Como mantenedor, quero um contrato claro sobre quem orquestra o quê, para que `content.js`, `bridge.js` e os módulos não vazem responsabilidades uns para os outros.

#### Acceptance Criteria

1. THE `content.js` SHALL ser o único Orchestrator da extensão — responsável por: (a) detectar o estado de login do Senior_X, (b) injetar os módulos canônicos via `<script>` em ordem determinística, (c) construir o container DOM da Aura, (d) registrar listeners globais de página (clique no mascote, troca de URL SPA, Magic_Link), (e) chamar `AuraState.setMode('assist')` para iniciar.
2. THE `content.js` SHALL não conter regras de negócio de proatividade, navegação guiada, gamificação, feedback ou highlight — todas vivem nos módulos canônicos correspondentes.
3. THE `bridge.js` SHALL atuar como Transport_Layer puro: encaminhar mensagens entre o mundo MAIN e o Background, sem fetch próprio, sem parsing de payload de domínio, sem decisões sobre exibição de balões ou tooltips.
4. THE módulos canônicos SHALL expor publicamente apenas as funções `init` e `teardown` mais os métodos de domínio explicitamente documentados no design — nenhum módulo pode declarar globals adicionais fora do Module_Namespace.
5. WHEN um módulo precisa coordenar com outro, THE módulo SHALL fazê-lo via `CustomEvent` no `document` (eventos `gps:*`, `mission:*`, `assist:*`) ou via API pública do módulo destino — nunca via leitura direta de estado interno alheio.
6. THE `aura_state` SHALL ser o único módulo autorizado a chamar `init`/`teardown` de outros módulos como parte de uma transição de modo, garantindo a propriedade de exclusividade descrita em 1.5 e 1.6.

---

### Requirement 16: Proibição de Caminhos Paralelos

**User Story:** Como mantenedor, quero uma regra explícita contra caminhos paralelos, para que tentativas futuras de "criar do zero" uma capacidade já existente sejam bloqueadas no review.

#### Acceptance Criteria

1. IF uma funcionalidade já existe em um módulo canônico, THEN a evolução dessa funcionalidade SHALL ocorrer dentro do módulo dono, sem criação de arquivo paralelo.
2. THE Content_Script SHALL não conter dois ou mais componentes ativos que executem a mesma capacidade primária — em particular: nunca dois motores de navegação passo-a-passo, nunca dois sistemas de highlight visual, nunca dois sistemas de tooltip persistente, nunca dois detectores de proatividade.
3. THE Content_Script SHALL não conter, em produção, código identificado como predecessor de um módulo canônico — quando uma absorção ocorre, o predecessor SHALL ser retirado integralmente em vez de mantido como fallback.
4. IF uma resposta do backend chegar com um shape proprietário (por exemplo `navigation_mode === 'guided'` com `navigation_path`) que represente um Parallel_Path do Step_Model, THEN o Aura_Assist SHALL traduzi-la para o Step_Model canônico antes de delegar ao Aura_GPS, ou rejeitá-la com log de aviso — nunca acionando um motor concorrente.
5. THE Content_Script SHALL não introduzir tipos de `postMessage` proprietários que dupliquem canais já existentes — em particular, o tipo `aura_analytics` (genérico) é proibido em favor de `AURA_ANALYTICS_EVENT` (canônico).

---

### Requirement 17: Disciplina de Rede

**User Story:** Como responsável técnico, quero que toda chamada de rede da extensão passe pelo Background, para que autenticação, retry e observabilidade fiquem centralizados em um único ponto.

#### Acceptance Criteria

1. THE módulos canônicos SHALL não chamar `fetch` diretamente para endpoints do backend — toda comunicação de domínio SHALL passar por `postMessage` para o Bridge e por `chrome.runtime.sendMessage` do Bridge para o Background.
2. THE Background SHALL ser o único ponto da extensão que executa `fetch` para endpoints externos, aplicando o `AURA_AUTH_TOKEN` e lendo URLs apenas de `AURA_ENDPOINTS`.
3. WHEN um módulo precisar de uma chamada de backend, THE módulo SHALL usar uma das ações canônicas do Background (`analisar_agora`, `fetch_mission`, `fetch_gps_explicit`, `pre_capture`, `analytics_event`, `fetch_hint`) — nunca um endpoint inventado por feature.
4. IF um novo tipo de chamada de backend for necessário, THEN a ação correspondente SHALL ser adicionada ao Background com nome canônico, registrada no design, e exposta no Bridge — não pode ser introduzida por fetch direto em um Loose_Script ou módulo.
5. THE Bridge SHALL não executar `fetch` próprio em nenhuma hipótese, mantendo seu papel de Transport_Layer puro descrito em 8.4 e 15.3.

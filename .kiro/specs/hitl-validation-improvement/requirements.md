# Requirements Document

## Introduction

Este documento especifica os requisitos para a melhoria do sistema HITL (Human-in-the-Loop) do Senior Training OS. O sistema atual (`validator_hitl.py`) apresenta problemas de UX que comprometem a eficácia da validação assistida por humanos, especialmente em roteiros longos onde o analista precisa corrigir apenas passos específicos. A melhoria visa implementar um modo de operação híbrido com auto-play e controle manual de pausa, navegação livre entre passos, e esclarecimento dos dois momentos de validação (pré-execução preventiva e pós-execução checkpoint).

## Glossary

- **HITL_System**: Sistema de validação Human-in-the-Loop que permite intervenção humana durante a execução automatizada de roteiros
- **Validator**: Componente responsável por executar roteiros com assistência humana sob demanda
- **Overlay**: Interface visual injetada na janela do Chrome para comunicação com o analista
- **Radar**: Modo de captura que detecta o próximo clique do analista para identificar elementos corretos
- **Brain_DB**: Banco de dados SQLite que armazena seletores aprendidos pelo sistema
- **Validacao_Preventiva**: Validação ANTES de executar uma ação quando a confiança é baixa (mostra o elemento que VAI clicar)
- **Validacao_Checkpoint**: Validação DEPOIS de executar um passo para confirmar se o resultado está correto
- **Roteiro**: Artefato JSON estruturado que representa um workflow capturado
- **Vision_Engine**: Motor de localização de elementos com 7 camadas de fallback
- **Playwright_Page**: Instância da página do navegador controlada pelo Playwright
- **WebSocket_Manager**: Gerenciador de conexões WebSocket para comunicação em tempo real com o dashboard
- **Navegador_de_Passos**: Interface que permite navegação livre entre passos quando a execução está pausada
- **Botao_Pausar**: Botão flutuante sempre visível que permite ao analista pausar a execução a qualquer momento
- **Auto_Play**: Modo de execução contínua sem pausas, exceto em falhas reais

## Requirements

### Requirement 1: Modo Auto-Play com Controle Manual

**User Story:** Como analista de treinamento, quero que o sistema execute automaticamente sem pausas por padrão, mas com controle para pausar quando eu precisar intervir, para que eu possa validar roteiros longos de forma eficiente sem responder perguntas em cada passo que funciona.

#### Acceptance Criteria

1. THE HITL_System SHALL executar em modo auto-play por padrão, sem pausas preventivas ou checkpoints, exceto em falhas reais
2. THE HITL_System SHALL exibir botão flutuante "⏸ PAUSAR" sempre visível no canto inferior direito da tela durante toda a execução
3. THE Botao_Pausar SHALL ter z-index máximo (2147483647) para garantir visibilidade sobre todos os elementos
4. THE Botao_Pausar SHALL usar estilo visual destacado com background laranja (#f97316), padding 12px 24px, border-radius 100px e box-shadow
5. WHEN o analista clica no Botao_Pausar, THE HITL_System SHALL pausar a execução imediatamente após concluir a ação atual e abrir o Navegador_de_Passos

### Requirement 2: Navegador de Passos

**User Story:** Como analista de treinamento, quero navegar livremente entre os passos do roteiro quando pausado, para que eu possa corrigir um passo específico sem passar por todos os passos anteriores.

#### Acceptance Criteria

1. WHEN a execução é pausada (manualmente ou por falha), THE HITL_System SHALL exibir o Navegador_de_Passos como overlay centralizado
2. THE Navegador_de_Passos SHALL exibir: número do passo atual, total de passos, descrição do passo (tooltip_dap), status (executado/pendente/erro)
3. THE Navegador_de_Passos SHALL incluir botões de navegação: "◄ Anterior" e "Próximo ►" para navegar entre passos
4. THE Navegador_de_Passos SHALL incluir cinco opções de ação: "▶ Continuar auto", "🔄 Refazer este passo", "✏️ Corrigir seletor", "⏭ Pular para passo X", "◄ ► Navegar"
5. WHEN o analista clica em "▶ Continuar auto", THE HITL_System SHALL fechar o Navegador_de_Passos e retomar a execução automática a partir do passo atual
6. WHEN o analista clica em "🔄 Refazer este passo", THE HITL_System SHALL executar todas as ações do passo atual novamente
7. WHEN o analista clica em "✏️ Corrigir seletor", THE HITL_System SHALL ativar o Radar para remapear o elemento da ação atual
8. WHEN o analista clica em "⏭ Pular para passo X", THE HITL_System SHALL exibir input numérico e navegar diretamente para o passo especificado
9. THE Navegador_de_Passos SHALL usar cores de status: verde para executado, amarelo para pendente, vermelho para erro

### Requirement 3: Pausas Automáticas em Falhas Reais

**User Story:** Como analista de treinamento, quero que o sistema pause automaticamente apenas quando ocorrem falhas reais de execução, para que eu seja notificado de problemas sem interrupções desnecessárias.

#### Acceptance Criteria

1. WHEN todas as 7 camadas do Vision_Engine falham ao localizar um elemento, THE HITL_System SHALL pausar automaticamente e abrir o Navegador_de_Passos com status "erro"
2. WHEN um timeout de ação é atingido, THE HITL_System SHALL pausar automaticamente e abrir o Navegador_de_Passos
3. WHEN um erro de execução ocorre (exception não tratada), THE HITL_System SHALL pausar automaticamente e abrir o Navegador_de_Passos
4. WHEN uma pausa automática ocorre, THE Navegador_de_Passos SHALL exibir mensagem de erro contextual descrevendo a falha
5. WHEN uma pausa automática ocorre, THE Navegador_de_Passos SHALL oferecer opções de correção: "✏️ Corrigir seletor", "🔄 Refazer este passo", "⏭ Pular para passo X"

### Requirement 4: Validação Preventiva (Pré-Execução)

**User Story:** Como analista de treinamento, quero ser notificado ANTES de executar uma ação de baixa confiança, para que eu possa confirmar ou corrigir o elemento que o sistema VAI clicar.

#### Acceptance Criteria

1. WHEN uma ação tem confiança baixa (seletor frágil ou sem histórico no Brain_DB) e o modo auto-play está pausado, THE HITL_System SHALL destacar o elemento encontrado com outline âmbar antes de executar
2. WHEN a validação preventiva é acionada, THE Navegador_de_Passos SHALL exibir mensagem "O elemento destacado em âmbar é o correto?"
3. WHEN o analista confirma o elemento, THE HITL_System SHALL executar a ação imediatamente
4. WHEN o analista rejeita o elemento, THE HITL_System SHALL oferecer opção "✏️ Corrigir seletor" para ativar o Radar
5. THE validação preventiva SHALL ser desabilitada durante o modo auto-play (só ativa quando pausado manualmente)

### Requirement 5: Validação Checkpoint (Pós-Execução)

**User Story:** Como analista de treinamento, quero que o sistema valide o estado da tela DEPOIS de executar um passo, para que eu possa confirmar se o resultado está correto e detectar desvios de estado.

#### Acceptance Criteria

1. WHEN um passo é concluído e o modo auto-play está pausado, THE HITL_System SHALL capturar screenshot e validar via Gemini Vision se a tela corresponde ao estado esperado
2. WHEN a validação checkpoint detecta desvio de estado, THE Navegador_de_Passos SHALL exibir mensagem "A tela parece diferente do esperado" com observação do Gemini
3. WHEN o analista confirma que a tela está correta apesar do desvio, THE HITL_System SHALL continuar normalmente
4. WHEN o analista decide refazer o passo, THE HITL_System SHALL executar todas as ações do passo novamente
5. THE validação checkpoint SHALL ser desabilitada durante o modo auto-play (só ativa quando pausado manualmente)
6. WHEN um desvio de estado é detectado e o analista continua, THE HITL_System SHALL propagar flag `_desvio_anterior` para o próximo passo

### Requirement 6: Correção de Seletores via Radar

**User Story:** Como analista de treinamento, quero corrigir seletores incorretos clicando no elemento certo na tela, para que o sistema aprenda e não precise de ajuda nas próximas execuções.

#### Acceptance Criteria

1. WHEN o analista seleciona "✏️ Corrigir seletor" no Navegador_de_Passos, THE HITL_System SHALL ativar o Radar e exibir mensagem "Radar ativo — clique no elemento correto na tela"
2. WHEN o Radar está ativo, THE HITL_System SHALL bloquear a execução e aguardar o clique do analista
3. WHEN o analista clica em um elemento com o Radar ativo, THE HITL_System SHALL capturar o seletor usando getBestSelector
4. WHEN o seletor é capturado, THE HITL_System SHALL salvar no Brain_DB com a intencao_semantica como chave
5. WHEN o seletor é salvo no Brain_DB, THE HITL_System SHALL atualizar o score_engine com sucesso=True e confianca_captura=1.0
6. WHEN o seletor é salvo, THE HITL_System SHALL executar a ação com o novo seletor e remover o indicador de Radar
7. THE Radar SHALL exibir feedback visual imediato no elemento clicado (outline ciano pulsante por 1.2 segundos)

### Requirement 7: Navegação Livre Entre Passos

**User Story:** Como analista de treinamento, quero navegar livremente entre os passos do roteiro, para que eu possa pular diretamente para o passo que precisa de correção sem executar todos os passos intermediários.

#### Acceptance Criteria

1. WHEN o Navegador_de_Passos está aberto, THE HITL_System SHALL permitir navegação para qualquer passo usando os botões "◄ Anterior" e "Próximo ►"
2. WHEN o analista clica em "◄ Anterior", THE HITL_System SHALL navegar para o passo anterior e atualizar a exibição do Navegador_de_Passos
3. WHEN o analista clica em "Próximo ►", THE HITL_System SHALL navegar para o próximo passo e atualizar a exibição do Navegador_de_Passos
4. WHEN o analista seleciona "⏭ Pular para passo X", THE HITL_System SHALL exibir input numérico com validação (1 até total de passos)
5. WHEN o analista confirma o número do passo, THE HITL_System SHALL navegar diretamente para o passo especificado
6. THE navegação livre SHALL atualizar o índice interno do loop de execução para refletir o passo atual
7. THE navegação livre SHALL preservar o histórico de passos executados para o relatório final

### Requirement 8: Feedback Visual de Estado

**User Story:** Como analista de treinamento, quero feedback visual claro sobre o estado atual do sistema, para que eu saiba se o sistema está executando, pausado, aguardando ou em erro.

#### Acceptance Criteria

1. WHEN o HITL_System está em modo auto-play, THE Botao_Pausar SHALL exibir texto "⏸ PAUSAR" com cor laranja (#f97316)
2. WHEN o HITL_System está pausado, THE Botao_Pausar SHALL mudar para "▶ CONTINUAR" com cor verde (#22c55e)
3. WHEN uma ação é executada com sucesso, THE HITL_System SHALL exibir ícone "✅" no log do terminal
4. WHEN uma ação falha, THE HITL_System SHALL exibir ícone "❌" no log do terminal
5. WHEN o Radar está ativo, THE Navegador_de_Passos SHALL exibir mensagem "Radar ativo — clique no elemento correto na tela" com ponto pulsante vermelho
6. WHEN um desvio de estado anterior é detectado, THE Navegador_de_Passos SHALL exibir aviso "⚠️ Atenção: o passo anterior teve desvio de estado"
7. THE Navegador_de_Passos SHALL usar badge colorido para indicar status do passo: verde (executado), amarelo (pendente), vermelho (erro)

### Requirement 9: Persistência de Correções

**User Story:** Como analista de treinamento, quero que as correções que eu fizer sejam salvas permanentemente, para que o sistema aprenda com minhas intervenções e não precise de ajuda nas próximas execuções.

#### Acceptance Criteria

1. WHEN o analista captura um seletor correto via Radar, THE HITL_System SHALL salvar o seletor no Brain_DB com a intencao_semantica como chave
2. WHEN o seletor é salvo no Brain_DB, THE HITL_System SHALL atualizar o score_engine com sucesso=True e confianca_captura=1.0
3. WHEN a execução é concluída, THE HITL_System SHALL reescrever o roteiro JSON com os seletores corrigidos
4. WHEN o roteiro é reescrito, THE HITL_System SHALL atualizar o campo `elemento_alvo.seletor_hint` com o novo seletor e `elemento_alvo.confianca_captura` para "alta"
5. WHEN o roteiro é atualizado com sucesso, THE HITL_System SHALL exibir mensagem "✅ Roteiro atualizado com N seletor(es) corrigido(s)."
6. THE correções SHALL ser armazenadas no mapa in-memory `_correcoes_seletores` durante a execução para reescrita do JSON ao final

### Requirement 10: Integração com Dashboard

**User Story:** Como analista de treinamento, quero que o dashboard seja notificado quando um roteiro é validado via HITL, para que eu possa acompanhar o status de validação de todos os roteiros.

#### Acceptance Criteria

1. WHEN a execução HITL é concluída com sucesso, THE HITL_System SHALL enviar requisição POST para `/api/marcar-hitl-validado/{nome_arquivo}`
2. WHEN a requisição é enviada, THE HITL_System SHALL usar timeout de 5 segundos
3. WHEN a requisição é bem-sucedida, THE HITL_System SHALL exibir mensagem "✅ Roteiro marcado como HITL validado no Dashboard."
4. WHEN a requisição falha (servidor offline), THE HITL_System SHALL exibir mensagem "(Servidor offline — marcar HITL manualmente: {erro})" sem interromper a execução
5. THE endpoint `/api/marcar-hitl-validado` SHALL atualizar o metadata do roteiro com campo `hitl_validado: true` e timestamp

### Requirement 11: Relatório de Execução

**User Story:** Como analista de treinamento, quero ver um relatório detalhado ao final da validação HITL, para que eu possa avaliar a qualidade do roteiro e quantas intervenções foram necessárias.

#### Acceptance Criteria

1. WHEN a execução HITL é concluída, THE HITL_System SHALL exibir relatório com os seguintes campos: "Passos executados", "Passos com erro", "Correções salvas", "Pausas manuais", "Pausas automáticas"
2. THE relatório SHALL ser exibido no terminal com formatação visual clara usando linhas separadoras "═"
3. WHEN existem correções salvas, THE HITL_System SHALL exibir mensagem adicional "✅ N correção(ões) salvas no Brain. Próxima execução vai acertar sem precisar de ajuda."
4. THE HITL_System SHALL incrementar `passos_executados` quando um passo é concluído
5. THE HITL_System SHALL incrementar `passos_com_erro` quando uma falha real ocorre
6. THE HITL_System SHALL incrementar `correcoes_salvas` quando o analista captura um seletor correto
7. THE HITL_System SHALL incrementar `pausas_manuais` quando o analista clica no Botao_Pausar
8. THE HITL_System SHALL incrementar `pausas_automaticas` quando uma falha real aciona pausa automática

### Requirement 12: Screenshot de Referência em Falhas

**User Story:** Como analista de treinamento, quero ver o screenshot de referência da gravação original quando uma falha ocorre, para que eu possa comparar visualmente o estado esperado com o estado atual.

#### Acceptance Criteria

1. WHEN uma falha ocorre e o elemento_alvo contém `screenshot_referencia`, THE Navegador_de_Passos SHALL exibir miniatura da imagem de referência com label "📸 Como a tela deveria estar"
2. THE miniatura SHALL ser exibida como imagem base64 com largura 100%, borda arredondada e opacidade 0.85
3. WHEN o screenshot_referencia não está disponível, THE Navegador_de_Passos SHALL omitir a seção de miniatura
4. THE screenshot_referencia SHALL ser lido do campo `elemento_alvo.screenshot_referencia` do roteiro JSON
5. THE miniatura SHALL ser posicionada na seção de detalhes do passo no Navegador_de_Passos

### Requirement 13: Highlight de Elementos

**User Story:** Como analista de treinamento, quero que o elemento encontrado pelo sistema seja destacado visualmente quando eu pausar, para que eu possa avaliar se o elemento está correto.

#### Acceptance Criteria

1. WHEN a validação preventiva é acionada e um seletor foi encontrado, THE HITL_System SHALL aplicar outline âmbar (3px solid #f59e0b) no elemento
2. THE highlight SHALL incluir box-shadow âmbar (0 0 16px #f59e0b88) para maior visibilidade
3. WHEN o analista toma uma decisão no Navegador_de_Passos, THE HITL_System SHALL remover o highlight restaurando o outline original
4. THE elemento destacado SHALL ser rolado para o centro da viewport usando scrollIntoView com behavior:'smooth' e block:'center'
5. THE highlight SHALL ser aplicado via page.evaluate com timeout de 3 segundos

### Requirement 14: Timeout de Inatividade

**User Story:** Como analista de treinamento, quero que o sistema tenha um timeout razoável quando pausado, para que execuções não fiquem travadas indefinidamente se eu me ausentar.

#### Acceptance Criteria

1. WHEN o Navegador_de_Passos está aberto aguardando decisão do analista, THE HITL_System SHALL usar timeout padrão de 300 segundos (5 minutos)
2. WHEN o timeout é atingido sem resposta do analista, THE HITL_System SHALL fechar o Navegador_de_Passos e retomar a execução automática
3. WHEN o timeout ocorre, THE HITL_System SHALL exibir mensagem de aviso "Timeout de 5min atingido. Retomando execução automática."
4. THE timeout SHALL ser configurável via constante `TIMEOUT_NAVEGADOR` no início do módulo
5. THE timeout SHALL ser aplicado usando `asyncio.wait_for` com tratamento de `asyncio.TimeoutError`
6. THE timeout SHALL ser reiniciado sempre que o analista interage com o Navegador_de_Passos

### Requirement 15: Binding Python-JavaScript para Captura

**User Story:** Como desenvolvedor, quero que o sistema use binding nativo do Playwright para comunicação entre Python e JavaScript, para que a captura de cliques seja confiável e performática.

#### Acceptance Criteria

1. WHEN o HITL_System é inicializado, THE HITL_System SHALL expor binding `__hitl_captura__` no contexto do navegador via `page.context.expose_binding`
2. WHEN o Radar está ativo e o analista clica em um elemento, THE JavaScript SHALL chamar `window.__hitl_captura__` com payload JSON contendo seletor e label
3. WHEN o binding Python recebe o payload, THE HITL_System SHALL parsear o JSON, extrair o seletor e setar o evento `_evento_humano`
4. THE binding SHALL usar `handle=True` para receber o objeto `source` com referência ao frame
5. THE binding SHALL tratar exceções silenciosamente e logar avisos sem interromper a execução
6. THE binding SHALL ser usado também para capturar cliques nos botões do Navegador_de_Passos

### Requirement 16: Interface do Navegador de Passos

**User Story:** Como analista de treinamento, quero que o Navegador de Passos seja visualmente claro e fácil de usar, para que eu possa navegar e corrigir passos de forma eficiente.

#### Acceptance Criteria

1. THE Navegador_de_Passos SHALL ser posicionado centralizado na tela (top:50%, left:50%, transform:translate(-50%,-50%)) com largura de 480px
2. THE Navegador_de_Passos SHALL usar background escuro semi-transparente (rgba(15,23,42,0.97)) com backdrop-filter blur(12px)
3. THE Navegador_de_Passos SHALL ter borda de 2px com cor baseada no status (verde para executado, amarelo para pendente, vermelho para erro)
4. THE Navegador_de_Passos SHALL incluir animação de entrada (fade-in + scale) com duração de 0.3s
5. THE Navegador_de_Passos SHALL ter z-index máximo (2147483647) para garantir visibilidade
6. THE Navegador_de_Passos SHALL incluir header com badge de status, número do passo (X/Total) e título do passo
7. THE Navegador_de_Passos SHALL incluir body com descrição do passo, screenshot de referência (se disponível) e botões de ação
8. THE botões de ação SHALL ter ícones e labels claros: "▶ Continuar auto", "🔄 Refazer este passo", "✏️ Corrigir seletor", "⏭ Pular para passo X"
9. THE Navegador_de_Passos SHALL incluir footer com botões de navegação "◄ Anterior" e "Próximo ►"

### Requirement 17: Execução Fluida por Padrão

**User Story:** Como analista de treinamento, quero que o sistema execute de forma fluida sem interrupções desnecessárias, para que eu possa validar roteiros de forma rápida e eficiente.

#### Acceptance Criteria

1. THE HITL_System SHALL executar em modo auto-play por padrão sem pausas preventivas ou checkpoints
2. THE HITL_System SHALL pausar automaticamente APENAS quando: elemento não encontrado (7 camadas falharam), timeout de ação, ou erro de execução
3. THE HITL_System SHALL exibir log contínuo no terminal mostrando progresso da execução (passo atual, ações executadas, status)
4. THE HITL_System SHALL usar delays mínimos entre ações (0.6s) para execução rápida
5. THE HITL_System SHALL permitir que o analista pause a qualquer momento via Botao_Pausar sem interromper a ação atual

### Requirement 18: Compatibilidade com Cursor Humanizado

**User Story:** Como desenvolvedor, quero que o sistema HITL seja compatível com o cursor humanizado do Training OS, para que a experiência visual seja consistente durante a validação.

#### Acceptance Criteria

1. WHEN o HITL_System é inicializado, THE HITL_System SHALL tentar importar e instalar o cursor_engine
2. WHEN a importação do cursor_engine falha, THE HITL_System SHALL continuar a execução sem cursor humanizado
3. THE cursor humanizado SHALL ser instalado via `instalar_cursor(page)` após a criação da página
4. THE instalação do cursor SHALL ser protegida por try/except para não interromper a execução em caso de falha
5. THE cursor humanizado SHALL ser visível durante toda a execução HITL para feedback visual de depuração

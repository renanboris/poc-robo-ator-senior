# Requirements: HITL Step-by-Step Validation

## Introduction

O HITL atual executa em modo auto-play e só pausa quando falha. Isso torna impossível validar proativamente se cada ação está correta antes de avançar. O resultado é que o Brain aprende seletores incorretos de falsos positivos, e o analista só descobre os erros ao assistir o vídeo final.

Este spec implementa um **modo step-by-step** onde o HITL pausa após cada ação, mostra o resultado ao analista, e aguarda confirmação (✅ Ok) ou correção (✏️ Corrigir) antes de avançar. Ao final da validação completa, o sistema dispara automaticamente a gravação (`--record`), que executa limpa porque o Brain já tem todos os seletores corretos.

## Fluxo Principal

```
Roteiro gerado → HITL step-by-step → Brain atualizado → --record automático → MP4 final
```

## Requirements

### Requirement 1: Modo Step-by-Step por Padrão

**User Story:** Como analista, quero que o HITL pause após cada ação executada, para que eu possa verificar visualmente se o clique foi no elemento correto antes de avançar.

#### Acceptance Criteria

1. WHEN o HITL é iniciado em modo step-by-step, THEN o sistema SHALL executar uma ação técnica por vez e pausar imediatamente após cada execução
2. WHEN uma ação é executada com sucesso, THEN o sistema SHALL exibir overlay com "✅ Ok" e "✏️ Corrigir" e aguardar decisão do analista
3. WHEN uma ação falha (todas as camadas do vision_engine falharam), THEN o sistema SHALL exibir overlay com "❌ Falhou" e "✏️ Corrigir" e aguardar decisão do analista
4. WHEN o analista clica "✅ Ok", THEN o sistema SHALL avançar para a próxima ação
5. WHEN o analista clica "✏️ Corrigir", THEN o sistema SHALL ativar o Radar para captura do seletor correto

### Requirement 2: Visor de Progresso

**User Story:** Como analista, quero ver em qual passo/ação estou e quantos faltam, para ter noção do progresso da validação.

#### Acceptance Criteria

1. WHEN o overlay de validação é exibido, THEN o sistema SHALL mostrar: "Passo X/Y — Ação Z/W" (ex: "Passo 3/12 — Ação 1/3")
2. WHEN o overlay é exibido, THEN o sistema SHALL mostrar a descrição da ação (intencao_semantica resumida em até 60 caracteres)
3. WHEN o overlay é exibido, THEN o sistema SHALL mostrar qual camada acertou (ex: "Brain", "Sniper", "Gemini Vision")
4. WHEN o overlay é exibido, THEN o sistema SHALL destacar o elemento que foi clicado com outline verde (sucesso) ou vermelho (falha)

### Requirement 3: Correção via Radar

**User Story:** Como analista, quero corrigir um seletor incorreto clicando no elemento certo na tela, para que o Brain aprenda e não erre na próxima execução.

#### Acceptance Criteria

1. WHEN o analista clica "✏️ Corrigir", THEN o sistema SHALL ativar o Radar e exibir mensagem "Clique no elemento correto"
2. WHEN o analista clica em um elemento com o Radar ativo, THEN o sistema SHALL capturar o seletor via getBestSelector
3. WHEN o seletor é capturado, THEN o sistema SHALL salvar no Brain DB com a intencao_semantica como chave e hitl_corrigido=1
4. WHEN o seletor é salvo, THEN o sistema SHALL executar a ação com o novo seletor e avançar automaticamente
5. WHEN o seletor é salvo, THEN o sistema SHALL atualizar o roteiro JSON com o novo seletor_hint

### Requirement 4: Modo Rápido (Skip Automático)

**User Story:** Como analista, quero poder alternar para modo rápido quando estou confiante que os próximos passos estão corretos, para não ter que confirmar cada um manualmente.

#### Acceptance Criteria

1. WHEN o overlay é exibido, THEN o sistema SHALL incluir botão "⏩ Auto (próximos N)" que avança N ações sem pausa
2. WHEN o analista clica "⏩ Auto (próximos N)", THEN o sistema SHALL executar as próximas N ações sem pausa, parando apenas em falhas
3. WHEN o modo rápido encontra uma falha, THEN o sistema SHALL pausar imediatamente e voltar ao modo step-by-step
4. WHEN todas as N ações do modo rápido são concluídas sem falha, THEN o sistema SHALL voltar ao modo step-by-step

### Requirement 5: Disparo Automático de Gravação

**User Story:** Como analista, quero que após validar todos os passos com sucesso, o sistema ofereça gravar automaticamente, para que eu não precise navegar no dashboard e clicar em outro botão.

#### Acceptance Criteria

1. WHEN todas as ações do roteiro são validadas com sucesso, THEN o sistema SHALL exibir relatório final com contagem de correções
2. WHEN o relatório final é exibido, THEN o sistema SHALL oferecer botão "🎬 Gravar agora" que dispara o --record
3. WHEN o analista clica "🎬 Gravar agora", THEN o sistema SHALL fechar a sessão HITL e iniciar o processo de gravação com o mesmo roteiro
4. WHEN a gravação é disparada, THEN o sistema SHALL usar o Brain atualizado (com todas as correções do HITL)
5. WHEN o analista não quer gravar imediatamente, THEN o sistema SHALL oferecer "Fechar" que encerra o HITL sem gravar

### Requirement 6: Integração com Dashboard

**User Story:** Como analista, quero iniciar o HITL step-by-step diretamente do dashboard, para que o fluxo seja integrado e não precise de CLI.

#### Acceptance Criteria

1. WHEN um roteiro não tem `hitl_validado: true`, THEN o dashboard SHALL exibir botão "🔍 Validar" como ação principal (antes de "Gravar")
2. WHEN o analista clica "🔍 Validar", THEN o dashboard SHALL iniciar o HITL step-by-step para o roteiro selecionado
3. WHEN o HITL conclui com sucesso e marca `hitl_validado: true`, THEN o dashboard SHALL atualizar o status do roteiro e exibir botão "🎬 Gravar"
4. WHEN um roteiro já tem `hitl_validado: true`, THEN o dashboard SHALL exibir "🎬 Gravar" como ação principal

### Requirement 7: Persistência e Aprendizado

**User Story:** Como analista, quero que todas as correções feitas durante o HITL sejam permanentes, para que o sistema nunca mais erre nos mesmos elementos.

#### Acceptance Criteria

1. WHEN o analista corrige um seletor via Radar, THEN o sistema SHALL salvar no Brain DB com hitl_corrigido=1 e falhas_consecutivas=0
2. WHEN o analista confirma "✅ Ok" para uma ação, THEN o sistema SHALL registrar sucesso no Brain (reforçar a memória existente)
3. WHEN o HITL é concluído, THEN o sistema SHALL reescrever o roteiro JSON com todos os seletores corrigidos
4. WHEN o Brain tem uma memória com hitl_corrigido=1, THEN o sistema SHALL nunca invalidar essa memória automaticamente (proteção contra limpeza)

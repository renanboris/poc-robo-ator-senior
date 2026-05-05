# Implementation Plan: HITL Validation Improvement

## Overview

Este plano implementa a melhoria do sistema HITL (Human-in-the-Loop) do Senior Training OS, transformando o `validator_hitl.py` existente em um sistema híbrido com auto-play por padrão, controle manual de pausa, navegação livre entre passos, e dois momentos distintos de validação (pré-execução preventiva e pós-execução checkpoint).

A implementação será feita através de refatoração incremental do código existente, introduzindo novos componentes de interface e controle de fluxo mantendo compatibilidade com o pipeline existente.

## Tasks

- [x] 1. Refatorar estrutura base do validator_hitl.py
  - [x] 1.1 Criar classes base para novos componentes
    - Implementar AutoPlayController para gerenciar execução automática
    - Implementar StepNavigator para interface de navegação
    - Implementar FloatingPauseButton para controle de pausa
    - Implementar EnhancedRadarSystem para captura melhorada
    - Implementar ValidationEngine para validações preventivas/checkpoint
    - Implementar PersistenceManager para salvamento de correções
    - _Requirements: 1.1, 2.1, 6.1, 9.1_

  - [ ]* 1.2 Escrever testes de propriedade para estrutura base
    - **Property 1: Auto-Play Execution Continuity**
    - **Validates: Requirements 1.1**

  - [x] 1.3 Integrar novos componentes na classe HitlValidator existente
    - Modificar __init__ para instanciar novos componentes
    - Preservar compatibilidade com métodos existentes
    - _Requirements: 1.1, 17.1_

- [x] 2. Implementar Auto-Play Controller e Botão de Pausa
  - [x] 2.1 Implementar lógica de execução automática contínua
    - Criar método execute_continuous para loop automático
    - Implementar controle de pausas via flags _pause_requested
    - Adicionar delays mínimos (0.6s) para execução rápida
    - _Requirements: 1.1, 17.4_

  - [ ]* 2.2 Escrever teste de propriedade para continuidade de execução
    - **Property 1: Auto-Play Execution Continuity**
    - **Validates: Requirements 1.1**

  - [x] 2.3 Implementar botão flutuante de pausa sempre visível
    - Criar JavaScript para botão com z-index máximo (2147483647)
    - Implementar estilo visual destacado (laranja #f97316, padding 12px 24px)
    - Adicionar handler de clique via binding Python-JavaScript
    - _Requirements: 1.2, 1.3, 1.4, 15.1, 15.2_

  - [ ]* 2.4 Escrever teste de propriedade para responsividade do botão
    - **Property 2: Pause Button Responsiveness**
    - **Validates: Requirements 1.5**

  - [x] 2.5 Implementar feedback visual de estado do botão
    - Alternar texto entre "⏸ PAUSAR" (laranja) e "▶ CONTINUAR" (verde)
    - Atualizar visual baseado no estado de execução
    - _Requirements: 8.1, 8.2_

- [x] 3. Checkpoint - Verificar execução automática e controle de pausa
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implementar Step Navigator (Interface de Navegação)
  - [x] 4.1 Criar overlay centralizado do navegador de passos
    - Implementar posicionamento centralizado (top:50%, left:50%)
    - Criar background escuro semi-transparente com backdrop-filter
    - Adicionar animação de entrada (fade-in + scale)
    - _Requirements: 2.1, 16.1, 16.2, 16.4, 16.5_

  - [ ]* 4.2 Escrever teste de propriedade para exibição do navegador
    - **Property 3: Navigator Display on Pause**
    - **Validates: Requirements 2.1**

  - [x] 4.3 Implementar informações do passo atual
    - Exibir número do passo (X/Total), descrição (tooltip_dap)
    - Mostrar status com cores (verde/amarelo/vermelho)
    - Incluir screenshot de referência quando disponível
    - _Requirements: 2.2, 2.9, 12.1, 12.2, 16.6, 16.7_

  - [x] 4.4 Implementar botões de ação do navegador
    - Criar botões: "▶ Continuar auto", "🔄 Refazer este passo"
    - Criar botões: "✏️ Corrigir seletor", "⏭ Pular para passo X"
    - Adicionar handlers via binding Python-JavaScript
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.8, 16.8_

  - [ ]* 4.5 Escrever testes de propriedade para ações do navegador
    - **Property 4: Continue Auto Functionality**
    - **Property 5: Step Redo Execution**
    - **Property 6: Radar Activation for Selector Correction**
    - **Validates: Requirements 2.5, 2.6, 2.7**

  - [x] 4.6 Implementar navegação livre entre passos
    - Criar botões "◄ Anterior" e "Próximo ►"
    - Implementar input numérico para "Pular para passo X"
    - Atualizar índice interno do loop de execução
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 16.9_

  - [ ]* 4.7 Escrever teste de propriedade para navegação de passos
    - **Property 7: Step Navigation Accuracy**
    - **Validates: Requirements 2.8**

- [x] 5. Implementar Enhanced Radar System
  - [x] 5.1 Refatorar sistema de captura de cliques existente
    - Melhorar binding Python-JavaScript para captura confiável
    - Implementar feedback visual imediato (outline ciano pulsante)
    - Adicionar bloqueio de execução durante radar ativo
    - _Requirements: 6.1, 6.2, 6.7, 15.3, 15.4_

  - [ ]* 5.2 Escrever teste de propriedade para ativação do radar
    - **Property 12: Radar Activation and Blocking**
    - **Validates: Requirements 6.1, 6.2**

  - [x] 5.3 Implementar captura e processamento de seletores
    - Usar getBestSelector para capturar seletor do elemento clicado
    - Processar payload JSON via binding Python
    - Tratar exceções silenciosamente sem interromper execução
    - _Requirements: 6.3, 15.5, 15.6_

  - [ ]* 5.4 Escrever teste de propriedade para captura de seletores
    - **Property 13: Selector Capture and Processing**
    - **Validates: Requirements 6.3**

- [x] 6. Implementar Validation Engine
  - [x] 6.1 Implementar validação preventiva (pré-execução)
    - Avaliar confiança baseada em Brain DB e qualidade do seletor
    - Destacar elemento com outline âmbar quando confiança baixa
    - Desabilitar durante auto-play (só ativa quando pausado)
    - _Requirements: 4.1, 4.2, 4.5, 13.1, 13.2, 13.4_

  - [x] 6.2 Implementar validação checkpoint (pós-execução)
    - Capturar screenshot e validar via Gemini Vision
    - Comparar com screenshot de referência quando disponível
    - Desabilitar durante auto-play (só ativa quando pausado)
    - _Requirements: 5.1, 5.2, 5.5, 5.6_

  - [ ]* 6.3 Escrever testes unitários para validações
    - Testar lógica de determinação de confiança
    - Testar integração com Gemini Vision
    - Testar casos de erro e fallbacks
    - _Requirements: 4.1, 5.1_

- [x] 7. Implementar pausas automáticas em falhas reais
  - [x] 7.1 Integrar com Vision Engine para detectar falhas
    - Capturar falhas quando todas as 7 camadas falharam
    - Detectar timeouts de ação e exceções não tratadas
    - Pausar automaticamente e abrir Step Navigator
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 7.2 Escrever testes de propriedade para pausas automáticas
    - **Property 8: Automatic Pause on Vision Engine Failure**
    - **Property 9: Automatic Pause on Timeout**
    - **Property 10: Automatic Pause on Exception**
    - **Validates: Requirements 3.1, 3.2, 3.3**

  - [x] 7.3 Implementar mensagens de erro contextuais
    - Exibir descrição específica da falha no Step Navigator
    - Oferecer opções de correção apropriadas para cada tipo de erro
    - _Requirements: 3.4, 3.5_

  - [ ]* 7.4 Escrever teste de propriedade para mensagens contextuais
    - **Property 11: Contextual Error Messages**
    - **Validates: Requirements 3.4**

- [x] 8. Checkpoint - Verificar sistema de pausas e navegação
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implementar Persistence Manager
  - [x] 9.1 Implementar salvamento no Brain DB
    - Salvar seletor capturado com intencao_semantica como chave
    - Atualizar score_engine com sucesso=True e confianca_captura=1.0
    - Armazenar correções no mapa in-memory durante execução
    - _Requirements: 6.4, 6.5, 9.1, 9.2, 9.6_

  - [ ]* 9.2 Escrever testes de propriedade para persistência
    - **Property 14: Brain DB Persistence**
    - **Property 16: Correction Persistence**
    - **Validates: Requirements 6.4, 6.5, 9.1, 9.2**

  - [x] 9.3 Implementar reescrita do roteiro JSON
    - Atualizar campo elemento_alvo.seletor_hint com novo seletor
    - Definir elemento_alvo.confianca_captura como "alta"
    - Usar escrita atômica para preservar integridade do arquivo
    - _Requirements: 9.3, 9.4, 9.5_

  - [ ]* 9.4 Escrever teste de propriedade para atualização do roteiro
    - **Property 17: Roteiro JSON Update**
    - **Validates: Requirements 9.3, 9.4**

  - [x] 9.5 Implementar execução com novo seletor
    - Executar ação imediatamente após captura do seletor
    - Remover indicador de radar após execução bem-sucedida
    - _Requirements: 6.6_

  - [ ]* 9.6 Escrever teste de propriedade para execução com novo seletor
    - **Property 15: Action Execution with New Selector**
    - **Validates: Requirements 6.6**

- [x] 10. Implementar timeout de inatividade e integração com dashboard
  - [x] 10.1 Implementar timeout configurável para Step Navigator
    - Usar timeout padrão de 300 segundos (5 minutos)
    - Retomar execução automática após timeout
    - Reiniciar timeout a cada interação do usuário
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6_

  - [x] 10.2 Implementar integração com dashboard
    - Enviar POST para /api/marcar-hitl-validado/{nome_arquivo}
    - Usar timeout de 5 segundos para requisição
    - Tratar falhas graciosamente sem interromper execução
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [ ]* 10.3 Escrever testes unitários para timeout e integração
    - Testar comportamento de timeout do navegador
    - Testar integração com API do dashboard
    - Testar tratamento de erros de rede
    - _Requirements: 14.1, 10.1_

- [x] 11. Implementar relatório de execução e compatibilidade
  - [x] 11.1 Implementar relatório detalhado de execução
    - Coletar estatísticas: passos executados, erros, correções, pausas
    - Exibir relatório formatado no terminal ao final
    - Incluir mensagem sobre correções salvas no Brain
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

  - [x] 11.2 Implementar compatibilidade com cursor humanizado
    - Tentar importar e instalar cursor_engine
    - Continuar execução mesmo se cursor falhar
    - Proteger instalação com try/except
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_

  - [ ]* 11.3 Escrever testes unitários para relatório e compatibilidade
    - Testar geração de estatísticas de execução
    - Testar formatação do relatório final
    - Testar compatibilidade com cursor humanizado
    - _Requirements: 11.1, 18.1_

- [x] 12. Integração final e testes de sistema
  - [x] 12.1 Integrar todos os componentes no fluxo principal
    - Modificar loop principal de execução para usar auto-play
    - Integrar pausas automáticas e manuais
    - Conectar Step Navigator com todas as ações
    - _Requirements: 1.1, 2.1, 3.1, 17.1_

  - [x] 12.2 Implementar highlight de elementos e feedback visual
    - Aplicar outline âmbar para validação preventiva
    - Implementar scroll automático para centro da viewport
    - Remover highlights após decisões do usuário
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

  - [ ]* 12.3 Escrever testes de integração de sistema
    - Testar fluxo completo de execução com pausas
    - Testar integração entre todos os componentes
    - Testar compatibilidade com roteiros existentes
    - _Requirements: 1.1, 2.1, 3.1_

- [x] 13. Checkpoint final - Validação completa do sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties from design
- Unit tests validate specific examples and edge cases
- Integration tests ensure compatibility with existing pipeline
- The implementation preserves backward compatibility with existing roteiros
- All new components integrate seamlessly with the current validator_hitl.py structure
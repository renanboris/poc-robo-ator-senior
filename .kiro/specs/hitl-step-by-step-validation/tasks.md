# Implementation Tasks

## Task List

- [x] 1. Refatorar loop de execução do validator_hitl.py para modo step-by-step
  - [x] 1.1 Modificar o loop principal `_executar_acao_com_hitl` para pausar após cada ação (não só em falhas)
  - [x] 1.2 Adicionar flag `_modo_auto_restante` para controle do modo rápido (skip N ações)
  - [x] 1.3 Adicionar lógica: se modo_auto e ação falha → voltar para step-by-step
  - [x] 1.4 Remover lógica de auto-play por padrão (inverter: step-by-step é o padrão)

- [x] 2. Criar overlay minimalista de validação step-by-step
  - [x] 2.1 Criar HTML/CSS do overlay compacto (canto inferior esquerdo, semi-transparente, max 400px)
  - [x] 2.2 Incluir: progresso (Passo X/Y — Ação Z/W), descrição da ação, camada que acertou
  - [x] 2.3 Incluir botões: "✅ Ok", "✏️ Corrigir", "⏩ Auto 5", "⏭ Pular"
  - [x] 2.4 Implementar highlight do elemento clicado (outline verde=sucesso, vermelho=falha)
  - [x] 2.5 Implementar binding JavaScript para capturar cliques nos botões do overlay

- [x] 3. Implementar lógica de decisão do analista
  - [x] 3.1 Implementar `_aguardar_decisao()` que espera clique em um dos botões do overlay (com timeout de 5min)
  - [x] 3.2 Implementar ação "Ok" → reforçar memória no Brain (`_registrar_sucesso_cache`) e avançar
  - [x] 3.3 Implementar ação "Corrigir" → ativar Radar, capturar seletor, salvar no Brain com hitl_corrigido=1
  - [x] 3.4 Implementar ação "Auto N" → setar `_modo_auto_restante = N` e avançar sem pausa
  - [x] 3.5 Implementar ação "Pular" → avançar sem registrar sucesso no Brain

- [x] 4. Implementar proteção de memórias HITL no Brain
  - [x] 4.1 Em `_init_db()` do vision_engine.py: excluir memórias com `hitl_corrigido=1` da limpeza TTL
  - [x] 4.2 Em `_registrar_falha_cache()`: não incrementar falhas para memórias com `hitl_corrigido=1`
  - [x] 4.3 Garantir que correções HITL nunca são invalidadas automaticamente

- [x] 5. Implementar relatório final e disparo de gravação
  - [x] 5.1 Ao final de todas as ações, exibir overlay com relatório: total de ações, correções feitas, taxa de acerto
  - [x] 5.2 Incluir botão "🎬 Gravar agora" que dispara `main.py --record` com o mesmo roteiro
  - [x] 5.3 Incluir botão "Fechar" que encerra sem gravar
  - [x] 5.4 Marcar roteiro como `hitl_validado: true` via POST `/api/marcar-hitl-validado`

- [x] 6. Ajustar dashboard para fluxo Validar → Gravar
  - [x] 6.1 No template do dashboard: se roteiro não tem `hitl_validado`, mostrar "🔍 Validar" como botão principal
  - [x] 6.2 Se roteiro tem `hitl_validado: true`, mostrar "🎬 Gravar" como botão principal
  - [x] 6.3 Manter "🎬 Gravar" disponível sempre (para re-gravações), mas com destaque menor quando não validado

- [x] 7. Testes e validação
  - [x] 7.1 Testar fluxo completo: HITL step-by-step → correção → gravação
  - [x] 7.2 Testar modo auto: ⏩ Auto 5 → falha no meio → volta para step-by-step
  - [x] 7.3 Testar persistência: correção HITL sobrevive a limpeza do Brain
  - [x] 7.4 Testar integração dashboard: botão muda de "Validar" para "Gravar" após HITL


- [x] 8. Fix do Radar no Step-by-Step (Correção de Bug)
  - [x] 8.1 Problema: Quando analista clica em "Corrigir", o Radar não funciona (cronômetro não aparece, clique não é capturado)
  - [x] 8.2 Causa raiz: Binding `__hitl_captura__` não funciona em iframes (Senior X usa iframes extensivamente)
  - [x] 8.3 Solução: Implementar comunicação via `postMessage` entre iframes e frame principal
  - [x] 8.4 Injetar CSS de animação ANTES de usar a classe `.hitl-radar-pulse-dot`
  - [x] 8.5 Adicionar validação e logging detalhado para diagnosticar problemas
  - [x] 8.6 Testar em todos os frames (principal + iframes)
  - [x] 8.7 Implementar 5 testes unitários para validar o fix (todos passando ✅)

# Plano de Implementação: Senior Training OS Roadmap

## Visão Geral

Implementação em três fases (0–360 dias) para evoluir o monólito atual em uma plataforma de proficiência operacional enterprise. Cada fase constrói sobre a anterior, preservando o roteiro como contrato central do sistema.

---

## Fase 1 (0–90 dias) — Estabilizar o Monólito

- [x] 1. Centralizar utilitários canônicos em `utils.py`
  - Garantir que `limpar_nome()`, `validar_roteiro()` e `validar_roteiro_ia()` sejam as únicas implementações canônicas dessas funções no projeto
  - Remover qualquer duplicação dessas funções em outros módulos (`app.py`, `generator_engine.py`, `main.py`)
  - Adicionar docstrings com contrato explícito (parâmetros, retorno, exceções) em cada função
  - `validar_roteiro()` deve retornar `(bool, str)` — resultado e motivo legível
  - _Requisitos: 1.1.5, 1.2.3, 1.2.5_

  - [ ]* 1.1 Escrever testes unitários para `limpar_nome()`
    - Cobrir: string vazia, caracteres especiais, espaços, unicode, nomes já limpos
    - _Requisitos: 1.3.1_

  - [ ]* 1.2 Escrever testes unitários para `validar_roteiro()`
    - Cobrir: roteiro válido mínimo, sem campo `metadata`, sem `passos`, `is_conclusao` ausente no último passo
    - _Requisitos: 1.3.1_

  - [ ]* 1.3 Escrever testes unitários para `validar_roteiro_ia()`
    - Cobrir: roteiro com âncora pedagógica, sem âncora, com `gerado_por_ia: false`
    - _Requisitos: 1.3.2_

- [x] 2. Implementar contratos de validação de roteiro
  - Em `app.py`, chamar `validar_roteiro()` antes de aceitar qualquer roteiro salvo em `roteiros_salvos/`
  - Bloquear promoção e registrar motivo em log com nível `WARNING` quando validação falhar
  - Implementar escrita atômica via `tempfile.mkstemp` + `os.replace()` em todos os pontos de escrita de roteiro
  - _Requisitos: 1.2.3, 1.2.4, 1.2.6_

  - [ ]* 2.1 Escrever property test — Property 1: Rejeição de roteiro com menos de 2 passos
    - **Property 1: Rejeição de roteiro com menos de 2 passos**
    - **Validates: Requisito 1.2.2**
    - Usar `@given(roteiro_strategy())` com `passos` de tamanho 0 ou 1
    - `@settings(max_examples=100)`

  - [ ]* 2.2 Escrever property test — Property 2: Aceitação de roteiro estruturalmente válido
    - **Property 2: Aceitação de roteiro estruturalmente válido**
    - **Validates: Requisitos 1.2.1, 1.2.2**
    - Gerar roteiros com N >= 2 passos, >= 50% com `seletor_hint` preenchido, <= 70% com `confianca_captura == 'baixa'`
    - `@settings(max_examples=100)`

  - [ ]* 2.3 Escrever property test — Property 5: Bloqueio de promoção de roteiro inválido
    - **Property 5: Bloqueio de promoção de roteiro inválido**
    - **Validates: Requisito 1.6.2**
    - Para qualquer roteiro que falhe em `validar_roteiro()`, verificar que a promoção é bloqueada e o motivo é registrado
    - `@settings(max_examples=100)`

- [x] 3. Implementar escrita atômica e validação de path em operações de I/O
  - Criar função `safe_write_json(path, data)` em `utils.py` usando `tempfile` + `os.replace()`
  - Criar função `safe_resolve_path(base_dir, user_path)` em `utils.py` que valida path traversal
  - Substituir todas as escritas diretas de JSON de roteiro e biblioteca por `safe_write_json()`
  - Substituir todas as construções de caminho com concatenação direta por `safe_resolve_path()`
  - _Requisitos: 1.2.6, 1.6.4, 2.3.2, 2.3.3, 2.3.4, NFR-1.6, NFR-1.7_

  - [ ]* 3.1 Escrever testes unitários para `safe_write_json()`
    - Cobrir: escrita bem-sucedida, falha no `os.replace()` (arquivo temporário removido), arquivo destino preservado em caso de erro
    - _Requisitos: 1.2.6, 1.6.4_

  - [ ]* 3.2 Escrever testes unitários para `safe_resolve_path()`
    - Cobrir: path válido dentro do base_dir, path com `../` tentando sair, path absoluto fora do base_dir
    - _Requisitos: NFR-1.6, NFR-1.7_

- [x] 4. Implementar pipeline HITL → Rebuild → Promoção de Memória
  - Em `app.py`, ao receber roteiro com `hitl_validado: true`, acionar `construir_biblioteca()` em background
  - Bloquear promoção se `validar_roteiro()` retornar `False`, registrar motivo
  - Após Rebuild bem-sucedido, chamar `_set_estado()` com contagem de peças novas
  - Usar `safe_write_json()` para escrita de `biblioteca_acoes.json`
  - Em caso de falha no Rebuild, preservar versão anterior e registrar `ERROR`
  - _Requisitos: 1.6.1, 1.6.2, 1.6.3, 1.6.4, 1.6.5_

  - [ ]* 4.1 Escrever property test — Property 3: Idempotência do Rebuild
    - **Property 3: Idempotência do Rebuild**
    - **Validates: Requisitos 1.3.4, 1.6**
    - Executar `construir_biblioteca()` duas vezes sobre o mesmo conjunto de roteiros e comparar o resultado
    - `@settings(max_examples=50)`

  - [ ]* 4.2 Escrever property test — Property 4: Round-trip de serialização de roteiro
    - **Property 4: Round-trip de serialização de roteiro**
    - **Validates: Requisitos 1.3.5, NFR-4.3**
    - Para qualquer roteiro válido R, verificar que `json.loads(json.dumps(R))` preserva todos os campos e `validar_roteiro()` retorna o mesmo resultado
    - `@settings(max_examples=100)`

- [x] 5. Implementar telemetria de camadas no `vision_engine.py`
  - Registrar em `telemetria_camadas` (brain.db) acertos e falhas por camada após cada tentativa de localização
  - Emitir log `INFO` com estratégia utilizada e resultado para cada tentativa
  - Emitir log `WARNING` quando taxa de sucesso de uma estratégia cair abaixo de 60% em 1 hora
  - Registrar estratégia vencedora no Brain após localização bem-sucedida
  - _Requisitos: 1.4.1, 1.4.3, 1.4.4_

  - [ ]* 5.1 Escrever property test — Property 6: Telemetria de camadas do Vision Engine
    - **Property 6: Telemetria de camadas do Vision Engine**
    - **Validates: Requisito 1.4.1**
    - Para qualquer tentativa de localização simulada, verificar que `telemetria_camadas` contém registro atualizado com `acertos` ou `falhas` incrementado corretamente
    - `@settings(max_examples=100)`

- [x] 6. Implementar endpoint `/api/metricas` com métricas de Vision Engine
  - Expor taxa de sucesso agregada por estratégia do Vision Engine nas últimas 24 horas
  - Expor: `total_aulas`, `horas_poupadas`, `economia_estimada`, `total_memorizado`, `self_healing_hits`, `tamanho_cache_dap`
  - Retornar `null` para campos sem dados (nunca omitir ou retornar zero)
  - _Requisitos: 1.4.2, NFR-3.2_

  - [ ]* 6.1 Escrever testes unitários para `/api/metricas`
    - Cobrir: resposta com dados, resposta com campos `null` quando sem dados, estrutura de campos obrigatórios
    - _Requisitos: 1.4.2, NFR-3.2_

- [x] 7. Padronizar logs estruturados em todos os módulos
  - Garantir que todos os módulos emitam logs com campos: `timestamp`, `level`, `module`, `message`
  - Usar níveis `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` de forma consistente
  - Nunca expor stack traces ou detalhes internos nas respostas da API
  - Registrar `ERROR` com nome do processo, comando e última linha de saída em falhas de background
  - _Requisitos: 1.5.1, 1.5.2, 1.5.3, 1.5.4, 1.5.5_

- [x] 8. Implementar testes de regressão por camada
  - Criar `tests/test_lego_builder.py`: rebuild da biblioteca, extração de ações com `intencao_semantica`
  - Criar `tests/test_generator_engine.py`: estrutura mínima do JSON gerado (campos obrigatórios presentes)
  - Criar `tests/test_vision_engine.py`: fallbacks do Brain e Sniper quando seletor primário falha
  - Criar `tests/test_scorm_builder.py`: geração sem erro para roteiro de referência
  - Criar `tests/test_pdf_builder.py`: geração sem erro para roteiro de referência
  - _Requisitos: 1.3.3, 1.3.4, 1.3.5, 1.3.6_

  - [ ]* 8.1 Escrever property test — Property 16: Tolerância a campos extras no roteiro
    - **Property 16: Tolerância a campos extras no roteiro**
    - **Validates: Requisito NFR-4.4**
    - Para qualquer roteiro válido R, adicionar campos desconhecidos e verificar que `validar_roteiro(R)` retorna o mesmo resultado
    - `@settings(max_examples=100)`

  - [ ]* 8.2 Escrever property test — Property 17: Idempotência de aplicação de defaults
    - **Property 17: Idempotência de aplicação de defaults**
    - **Validates: Requisito NFR-4.3**
    - Para qualquer roteiro já completo, aplicar defaults e verificar que nenhum campo existente foi alterado
    - `@settings(max_examples=100)`

- [x] 9. Checkpoint Fase 1 — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas antes de avançar para a Fase 2.

---

## Fase 2 (90–180 dias) — Separar Plataforma de Estúdio

- [x] 10. Implementar `JobRegistry` com persistência em SQLite
  - Criar tabela `jobs` em `brain.db` (ou `jobs.db`) conforme schema do design
  - Implementar funções: `criar_job()`, `atualizar_job()`, `consultar_job()`, `listar_jobs_por_tenant()`
  - `criar_job()` deve gerar `job_id` via `uuid.uuid4()` e persistir com status `pendente`
  - _Requisitos: 2.2.1, 2.2.3, 2.2.4_

  - [ ]* 10.1 Escrever property test — Property 7: Unicidade de job_id
    - **Property 7: Unicidade de job_id**
    - **Validates: Requisito 2.2.1**
    - Para qualquer sequência de N operações de background iniciadas, verificar que todos os `job_id` são distintos
    - `@settings(max_examples=200)`

  - [ ]* 10.2 Escrever property test — Property 8: Round-trip de estado de job
    - **Property 8: Round-trip de estado de job**
    - **Validates: Requisito 2.2.3**
    - Para qualquer job criado, consultar o registro e verificar que o estado retornado é idêntico ao gravado
    - `@settings(max_examples=100)`

- [x] 11. Implementar separação Control Plane / Worker Plane em `app.py`
  - Refatorar `app.py` para despachar jobs pesados (captura, render, SCORM, PDF, rebuild) para workers assíncronos
  - Control Plane retorna imediatamente com `job_id` e status `iniciado` ao cliente
  - Garantir que apenas um job por tipo de operação pesada esteja ativo simultaneamente por tenant
  - Workers notificam Control Plane via callback ao concluir ou falhar (sem polling ativo)
  - _Requisitos: 2.1.1, 2.1.2, 2.1.3, 2.1.4, 2.1.5_

- [x] 12. Implementar ciclo de vida completo de jobs (progresso, cancelamento, limpeza)
  - Expor progresso percentual via WebSocket em `/api/ws/status` com granularidade mínima de 10%
  - Implementar `POST /api/cancelar` que interrompe o job e limpa arquivos temporários
  - Registrar motivo de falha em `jobs.motivo_falha` e disponibilizar via API
  - Manter logs de execução de cada job acessíveis via API por pelo menos 24 horas
  - _Requisitos: 2.2.2, 2.2.4, 2.2.5, 2.2.6, NFR-3.3, NFR-3.5_

  - [ ]* 12.1 Escrever testes unitários para ciclo de vida de jobs
    - Cobrir: criação, transição de status, cancelamento, limpeza de temporários, consulta de motivo de falha
    - _Requisitos: 2.2.1, 2.2.5, 2.2.6_

- [x] 13. Implementar `StorageAdapter` com backend local
  - Criar protocolo `StorageAdapter` em `utils.py` ou módulo dedicado com métodos: `read`, `write`, `exists`, `list`
  - Implementar `LocalStorageAdapter` usando os diretórios existentes (`roteiros_salvos/`, `videos_prontos/`, etc.)
  - Substituir todos os acessos diretos a diretórios de artefatos pelo `StorageAdapter`
  - Toda escrita via adapter deve usar `safe_write_json()` / escrita atômica
  - _Requisitos: 2.3.1, 2.3.2, 2.3.3, 2.3.4_

  - [ ]* 13.1 Escrever testes unitários para `LocalStorageAdapter`
    - Cobrir: `write` + `read` round-trip, `exists` antes e depois de escrita, `list` retorna apenas artefatos do tipo correto
    - _Requisitos: 2.3.1, 2.3.3_

- [x] 14. Implementar interface `BrainBackend` com suporte a backend intercambiável
  - Definir protocolo `BrainBackend` com métodos: `get`, `set`, `query`
  - Implementar `SQLiteBrainBackend` preservando comportamento atual do `brain.db`
  - Adicionar suporte a backend remoto via variável de ambiente (stub que pode ser substituído)
  - Modo degradado: quando backend indisponível, continuar sem self-healing e registrar `WARNING`
  - _Requisitos: 2.4.1, 2.4.2, 2.4.3, 2.4.4_

  - [ ]* 14.1 Escrever testes unitários para `SQLiteBrainBackend`
    - Cobrir: `set` + `get` round-trip, `query` por tenant, comportamento quando DB indisponível (modo degradado)
    - _Requisitos: 2.4.1, 2.4.4_

- [x] 15. Implementar isolamento por tenant no Brain e no Pinecone
  - Adicionar `tenant_id` como campo obrigatório em todas as operações do Brain
  - Garantir que `query()` do Brain filtra por `tenant_id` (sem contaminação entre tenants)
  - Garantir que todas as operações Pinecone usam `namespace=tenant_id`
  - Usar `senior_default` como tenant padrão quando `tenant_id` ausente, registrar `WARNING`
  - Retornar HTTP 403 quando requisição tentar acessar artefatos de tenant diferente do autenticado
  - _Requisitos: 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.5_

  - [ ]* 15.1 Escrever property test — Property 9: Isolamento de tenant no Brain
    - **Property 9: Isolamento de tenant no Brain**
    - **Validates: Requisito 2.5.4**
    - Para quaisquer dois tenants A e B distintos, verificar que entrada gravada para A não é retornada em consultas para B
    - `@settings(max_examples=100)`

  - [ ]* 15.2 Escrever property test — Property 10: Isolamento de tenant no Pinecone
    - **Property 10: Isolamento de tenant no Pinecone**
    - **Validates: Requisito 2.5.3**
    - Para qualquer requisição com `tenant_id` T, verificar que upsert e query usam exclusivamente o namespace de T (mock do cliente Pinecone)
    - `@settings(max_examples=100)`

- [x] 16. Implementar versionamento explícito de roteiros
  - Ao sobrescrever um roteiro em `roteiros_salvos/`, preservar versão anterior com sufixo de timestamp ou versão incremental
  - Implementar `restaurar_versao(arquivo, versao)` que executa `validar_roteiro()` antes de tornar a versão ativa
  - Versionar `biblioteca_acoes.json` com identificador gerado a cada Rebuild bem-sucedido
  - Adicionar `timestamp` de criação e última atualização em entradas do Brain
  - _Requisitos: 2.6.1, 2.6.2, 2.6.3, 2.6.4, 2.6.5_

  - [ ]* 16.1 Escrever property test — Property 11: Preservação de versões de roteiro
    - **Property 11: Preservação de versões de roteiro**
    - **Validates: Requisitos 2.6.1, 2.6.2**
    - Para qualquer sequência de N >= 2 escritas sobre o mesmo roteiro, verificar que pelo menos as 2 versões mais recentes distintas são preservadas
    - `@settings(max_examples=50)`

- [x] 17. Implementar retry com exponential backoff para APIs externas
  - Criar decorator ou função `com_retry(fn, tentativas=3, delays=[1, 2, 4])` em `utils.py`
  - Aplicar em todas as chamadas a Gemini, OpenAI e Pinecone
  - Após esgotar tentativas, retornar resposta de erro estruturada sem expor detalhes internos
  - Modo degradado: sem Pinecone → gerar sem RAG; sem Gemini → retornar erro estruturado; sem Brain → continuar sem self-healing
  - _Requisitos: NFR-2.1, NFR-2.2, NFR-2.3, NFR-2.4, NFR-2.5_

  - [ ]* 17.1 Escrever property test — Property 18: Retry com backoff em falhas de API externa
    - **Property 18: Retry com backoff em falhas de API externa**
    - **Validates: Requisito NFR-2.1**
    - Para qualquer chamada de API que falhe na primeira tentativa (mock), verificar que o sistema realiza pelo menos 2 tentativas adicionais com delay crescente
    - `@settings(max_examples=50)`

- [x] 18. Implementar autenticação e rate limiting
  - Exigir token Bearer válido lido de `AURA_API_SECRET` em todas as rotas de pipeline
  - Retornar HTTP 401 com log do IP de origem para token inválido ou ausente
  - Implementar rate limiting de 20 req/min por IP; retornar HTTP 429 quando excedido
  - _Requisitos: NFR-1.1, NFR-1.2, NFR-1.3, NFR-1.4, NFR-1.5_

  - [ ]* 18.1 Escrever property test — Property 15: Rate limiting por IP
    - **Property 15: Rate limiting por IP**
    - **Validates: Requisito NFR-1.4**
    - Para qualquer IP que faça mais de 20 requisições em 60 segundos, verificar que a 21ª retorna HTTP 429
    - `@settings(max_examples=30)`

- [x] 19. Checkpoint Fase 2 — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas antes de avançar para a Fase 3.

---

## Fase 3 (180–360 dias) — Productizar o Conhecimento Operacional

- [x] 20. Implementar tabela e engine de Score de Confiabilidade
  - Criar tabela `scores_confiabilidade` em `brain.db` conforme schema do design
  - Implementar `calcular_score(acao_id)` como média ponderada de `taxa_sucesso`, `confianca_captura` e fator de execuções
  - Implementar `registrar_execucao(acao_id, sucesso: bool)` que atualiza `taxa_sucesso` e `total_execucoes`
  - Marcar `requer_revisao = True` quando `score < 0.5`
  - _Requisitos: 3.2.1, 3.2.3, 3.2.5_

  - [ ]* 20.1 Escrever property test — Property 12: Invariante de score de confiabilidade
    - **Property 12: Invariante de score de confiabilidade**
    - **Validates: Requisito 3.2.1**
    - Para qualquer ação com qualquer histórico de execuções, verificar que `0.0 <= score(A) <= 1.0`
    - `@settings(max_examples=200)`

  - [ ]* 20.2 Escrever property test — Property 13: Monotonicidade de score com execuções bem-sucedidas
    - **Property 13: Monotonicidade de score com execuções bem-sucedidas**
    - **Validates: Requisito 3.2.3**
    - Para qualquer ação A, registrar uma execução bem-sucedida e verificar que `score(A, N+1) >= score(A, N)`
    - `@settings(max_examples=100)`

  - [ ]* 20.3 Escrever property test — Property 14: Score de fluxo como função determinística das ações
    - **Property 14: Score de fluxo como função determinística das ações**
    - **Validates: Requisito 3.2.2**
    - Para qualquer roteiro R com ações A1..An, chamar `calcular_score(R)` duas vezes com os mesmos scores de ações e verificar que o resultado é idêntico
    - `@settings(max_examples=100)`

- [x] 21. Integrar Score de Confiabilidade ao Executor e à Biblioteca de Ações
  - Em `main.py`, após cada ação executada, chamar `registrar_execucao(acao_id, sucesso)` com o resultado real
  - Em `lego_builder.py`, ao construir a biblioteca, incluir `_score_confiabilidade` em cada entrada
  - Atualizar `biblioteca_acoes.json` com campo `_score_confiabilidade` e flag `requer_revisao`
  - _Requisitos: 3.2.3, 3.2.5_

  - [ ]* 21.1 Escrever testes unitários para integração Executor → Score
    - Cobrir: execução bem-sucedida incrementa score, execução com falha decrementa, `requer_revisao` ativado quando score < 0.5
    - _Requisitos: 3.2.3, 3.2.5_

- [x] 22. Implementar API semântica e propagação de atualizações entre renderizações
  - Implementar endpoint de consulta semântica que retorna todas as renderizações disponíveis para um fluxo ou ação
  - Ao promover roteiro via HITL, propagar atualizações automaticamente para missão, DAP e playbook derivados do mesmo fluxo
  - Garantir que a mesma ação semântica produza comportamento consistente em todas as renderizações
  - _Requisitos: 3.1.1, 3.1.2, 3.1.3, 3.1.4_

  - [ ]* 22.1 Escrever testes unitários para propagação de atualizações
    - Cobrir: atualização de roteiro propaga para DAP, missão e playbook; ação semântica consistente entre renderizações
    - _Requisitos: 3.1.2, 3.1.3_

- [x] 23. Implementar métricas de ROI em `/api/metricas`
  - Registrar tempo de criação de cada treinamento (captura → primeiro artefato)
  - Registrar taxa de correção HITL por roteiro (número de edições antes da aprovação)
  - Registrar índice de reuso de memória (ações recuperadas da biblioteca vs. criadas do zero)
  - Calcular redução estimada de suporte (consultas Aura respondidas via cache/RAG sem Gemini Vision)
  - Calcular tempo médio até proficiência por fluxo a partir de dados de execução de missões
  - Retornar `null` para campos sem dados (nunca omitir ou retornar zero)
  - _Requisitos: 3.3.1, 3.3.2, 3.3.3, 3.3.4, 3.3.5, 3.3.6, 3.3.7_

  - [ ]* 23.1 Escrever testes unitários para métricas de ROI
    - Cobrir: todos os campos presentes na resposta, campos `null` quando sem dados, cálculo correto de índice de reuso
    - _Requisitos: 3.3.6, 3.3.7_

- [x] 24. Implementar isolamento de módulos de captura por ERP via adaptadores
  - Definir contrato de integração para módulos de captura em `contracts/` (interface mínima compatível com Gerador e Executor)
  - Isolar toda referência específica ao Senior X em módulos de adaptador (fora dos módulos centrais do pipeline)
  - Suportar configuração de novos módulos de captura via variável de ambiente sem alteração de código central
  - _Requisitos: 3.4.1, 3.4.2, 3.4.3, 3.4.4, 3.4.5_

  - [ ]* 24.1 Escrever testes unitários para contrato de adaptador de captura
    - Cobrir: adaptador Senior X satisfaz o contrato, pipeline central funciona com adaptador mock
    - _Requisitos: 3.4.3, 3.4.4_

- [x] 25. Expor scores via `/api/metricas` com granularidade por ação e por fluxo
  - Adicionar campos `scores_por_acao` e `scores_por_fluxo` ao endpoint `/api/metricas`
  - Incluir `requer_revisao` por ação na resposta
  - _Requisitos: 3.2.4_

  - [ ]* 25.1 Escrever testes unitários para scores em `/api/metricas`
    - Cobrir: estrutura de resposta, scores dentro do intervalo [0,1], flag `requer_revisao` correta
    - _Requisitos: 3.2.1, 3.2.4_

- [x] 26. Checkpoint Final — Garantir que todos os testes passam
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas antes de considerar o roadmap concluído.

---

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia requisitos específicos para rastreabilidade
- Checkpoints garantem validação incremental ao final de cada fase
- Testes de propriedade (Hypothesis) validam invariantes universais; testes unitários validam exemplos concretos e casos de borda
- Todas as propriedades usam `@settings(max_examples=100)` como mínimo, salvo indicação contrária

# Documento de Requisitos

## Introdução

Este documento descreve os requisitos de evolução da plataforma **Senior Training OS** ao longo de três fases estratégicas, cobrindo um horizonte de 0 a 360 dias. O objetivo é transformar o sistema atual — um monólito funcional e capaz, porém sensível — em uma plataforma de proficiência operacional enterprise, confiável, escalável e reutilizável.

O roteiro é o contrato central do sistema em todas as fases. Qualquer evolução deve preservar a compatibilidade entre as camadas de captura, geração, execução e entrega de artefatos.

---

## Glossário

- **Sistema**: a plataforma Senior Training OS como um todo
- **Pipeline**: sequência de estágios captura → roteiro → execução → artefatos
- **Roteiro**: artefato JSON central que representa um fluxo de trabalho estruturado; consumido por todos os geradores de saída
- **Captura**: estágio de gravação de interação do usuário via Playwright, produzindo dados brutos de workflow
- **Gerador**: módulo `generator_engine.py` que transforma captura em roteiro estruturado via IA
- **Executor**: módulo `main.py` que reproduz o roteiro para gravação ou renderização
- **Biblioteca_de_Ações**: arquivo `biblioteca_acoes.json` contendo ações técnicas reutilizáveis extraídas de roteiros validados
- **Brain**: banco SQLite `brain.db` com memória semântica de seletores para self-healing
- **Sniper**: lógica de localização resiliente em `vision_engine.py` com estratégias de fallback
- **HITL**: Human-In-The-Loop — revisão manual de roteiros gerados por IA antes da promoção
- **Rebuild**: processo de reconstrução da Biblioteca_de_Ações a partir dos roteiros salvos
- **Aura**: camada de assistência DAP (Digital Adoption Platform) alimentada por Gemini Vision e RAG
- **DAP**: Digital Adoption Platform — guia contextual in-app para o usuário final do Senior X
- **SCORM**: pacote de e-learning exportável para LMS, gerado a partir do roteiro
- **Playbook**: documento PDF gerado a partir do roteiro com instruções passo a passo
- **Tenant**: unidade de isolamento lógico de dados e configuração por cliente ou organização
- **Control_Plane**: camada de coordenação e orquestração de tarefas (app.py como coordenador)
- **Worker_Plane**: camada de execução pesada e assíncrona (jobs de captura, render, geração)
- **GPS**: mecanismo de rastreamento de missão e progresso do usuário no DAP
- **Missão**: unidade gamificada de aprendizagem com passos, validações e pontuação XP
- **Score_de_Confiabilidade**: métrica calculada por fluxo e por ação indicando probabilidade de execução bem-sucedida
- **ROI**: retorno sobre investimento medido em horas poupadas, taxa de reuso e redução de suporte

---

## Fase 1 (0–90 dias) — Estabilizar o Monólito

### Requisito 1.1: Congelamento de Expansão Estrutural

**User Story:** Como engenheiro de plataforma, quero que os módulos centrais tenham responsabilidades estáveis, para que novas funcionalidades não aumentem a fragilidade do sistema.

#### Acceptance Criteria

1. THE Sistema SHALL manter `app.py` exclusivamente como coordenador de rotas, estado e orquestração de background tasks, sem lógica de negócio inline.
2. THE Sistema SHALL manter `capture.py` exclusivamente como produtor de dados brutos de captura, sem lógica de geração de artefatos.
3. THE Sistema SHALL manter `vision_engine.py` exclusivamente como provedor de estratégias de localização resiliente, sem dependências de geração de conteúdo.
4. THE Sistema SHALL manter `main.py` exclusivamente como executor e renderizador de roteiros, sem lógica de captura ou geração.
5. WHEN uma nova funcionalidade for adicionada ao Sistema, THE Sistema SHALL acomodá-la sem adicionar responsabilidades novas aos quatro módulos centrais acima.

---

### Requisito 1.2: Contratos Estáveis de Roteiro

**User Story:** Como desenvolvedor, quero que o schema do roteiro seja explícito e validado, para que mudanças em um módulo não quebrem silenciosamente os demais.

#### Acceptance Criteria

1. THE Roteiro SHALL conter obrigatoriamente os campos `metadata`, `configuracao_gravacao` e `passos`.
2. THE Roteiro SHALL conter ao menos 2 passos, sendo o último marcado com `is_conclusao: true`.
3. WHEN um roteiro for salvo em `roteiros_salvos/`, THE Sistema SHALL executar `validar_roteiro()` de `utils.py` antes de aceitar o arquivo como válido.
4. IF um roteiro não passar na validação de `validar_roteiro()`, THEN THE Sistema SHALL rejeitar a promoção do roteiro e registrar o motivo em log.
5. THE Sistema SHALL usar `limpar_nome()` de `utils.py` como única função canônica de sanitização de nomes de arquivo em todos os módulos.
6. WHEN um roteiro for escrito em disco, THE Sistema SHALL usar escrita atômica via arquivo temporário seguido de `os.replace()` para evitar corrupção parcial.

---

### Requisito 1.3: Testes de Regressão por Camada

**User Story:** Como engenheiro de qualidade, quero testes automatizados cobrindo os contratos críticos do pipeline, para que regressões sejam detectadas antes de chegarem à produção.

#### Acceptance Criteria

1. THE Sistema SHALL ter testes de regressão cobrindo `validar_roteiro()` para roteiros válidos, inválidos e casos de borda.
2. THE Sistema SHALL ter testes de regressão cobrindo `validar_roteiro_ia()` para roteiros gerados por IA com e sem âncora pedagógica.
3. THE Sistema SHALL ter testes de regressão cobrindo a geração de JSON pelo Gerador, verificando que a estrutura mínima obrigatória está presente.
4. THE Sistema SHALL ter testes de regressão cobrindo o Rebuild da Biblioteca_de_Ações, verificando que ações com `intencao_semantica` são extraídas corretamente.
5. THE Sistema SHALL ter testes de regressão cobrindo o render de PDF e SCORM, verificando que os arquivos de saída são gerados sem erro para um roteiro válido de referência.
6. THE Sistema SHALL ter testes de regressão cobrindo os fallbacks do Brain e do Sniper, verificando que o sistema retorna uma estratégia alternativa quando o seletor primário falha.
7. WHEN qualquer teste de regressão falhar, THE Sistema SHALL impedir o merge da mudança causadora até que o teste seja corrigido.

#### Propriedades de Corretude (Property-Based Testing)

- **Invariante de validação**: para qualquer roteiro com N passos onde N >= 2 e pelo menos 50% das ações têm `seletor_hint` preenchido, `validar_roteiro()` SHALL retornar `True`.
- **Invariante de rejeição**: para qualquer roteiro com menos de 2 passos, `validar_roteiro()` SHALL retornar `False`.
- **Idempotência do Rebuild**: executar `construir_biblioteca()` duas vezes consecutivas sobre o mesmo conjunto de roteiros SHALL produzir o mesmo `biblioteca_acoes.json`.
- **Round-trip de serialização**: para qualquer roteiro válido R, `json.loads(json.dumps(R)) == R` SHALL ser verdadeiro (sem perda de dados na serialização).

---

### Requisito 1.4: Métricas de Confiabilidade do Vision Engine

**User Story:** Como operador de plataforma, quero visibilidade sobre a taxa de sucesso de cada estratégia de localização, para que eu possa identificar quais fluxos estão degradados.

#### Acceptance Criteria

1. THE Vision_Engine SHALL registrar em log, para cada tentativa de localização, a estratégia utilizada (`seletor_css`, `seletor_hint`, `label_curto`, `vision_fallback`) e o resultado (`sucesso` ou `falha`).
2. THE Sistema SHALL expor via `/api/metricas` a taxa de sucesso agregada por estratégia do Vision_Engine nas últimas 24 horas.
3. WHEN a taxa de sucesso de uma estratégia cair abaixo de 60% em um período de 1 hora, THE Sistema SHALL registrar um alerta de nível `WARNING` no log.
4. THE Sistema SHALL registrar no Brain a estratégia vencedora após cada localização bem-sucedida para alimentar o self-healing futuro.

---

### Requisito 1.5: Padronização de Logs e Erros

**User Story:** Como desenvolvedor, quero que todos os módulos emitam logs em formato estruturado e consistente, para que eu possa monitorar e depurar o sistema de forma eficiente.

#### Acceptance Criteria

1. THE Sistema SHALL emitir todos os logs em formato estruturado com os campos: `timestamp`, `level`, `module`, `message`.
2. THE Sistema SHALL usar os níveis de log `DEBUG`, `INFO`, `WARNING`, `ERROR` e `CRITICAL` de forma consistente em todos os módulos.
3. WHEN um processo de background falhar, THE Sistema SHALL registrar o erro com nível `ERROR` incluindo o nome do processo, o comando executado e a última linha de saída.
4. IF uma exceção não tratada ocorrer em qualquer módulo do pipeline, THEN THE Sistema SHALL registrar o stack trace completo com nível `ERROR` antes de propagar ou encerrar.
5. THE Sistema SHALL nunca expor stack traces ou detalhes internos de implementação nas respostas da API para o cliente.

---

### Requisito 1.6: Pipeline HITL → Rebuild → Promoção de Memória

**User Story:** Como instrutor, quero que roteiros validados manualmente sejam promovidos automaticamente para a Biblioteca_de_Ações, para que o conhecimento validado seja reutilizado em gerações futuras.

#### Acceptance Criteria

1. WHEN um roteiro receber aprovação HITL (campo `hitl_validado: true`), THE Sistema SHALL acionar automaticamente o Rebuild da Biblioteca_de_Ações em background.
2. THE Sistema SHALL bloquear a promoção de um roteiro para a Biblioteca_de_Ações se `validar_roteiro()` retornar `False` para esse roteiro.
3. WHEN o Rebuild for concluído com sucesso, THE Sistema SHALL atualizar o estado do servidor via `_set_estado()` com a contagem de peças novas adicionadas.
4. THE Sistema SHALL garantir que o Rebuild use escrita atômica para `biblioteca_acoes.json`, preservando a versão anterior em caso de falha.
5. WHEN o Rebuild falhar por qualquer motivo, THE Sistema SHALL manter a versão anterior da Biblioteca_de_Ações intacta e registrar o erro em log.

#### Propriedades de Corretude (Property-Based Testing)

- **Monotonicidade do Rebuild**: para qualquer conjunto de roteiros R1 ⊂ R2, `len(biblioteca(R2)) >= len(biblioteca(R1))` — adicionar roteiros nunca reduz a biblioteca.
- **Integridade de proveniência**: para toda ação na Biblioteca_de_Ações, o campo `_source` SHALL referenciar um arquivo existente em `roteiros_salvos/`.

---

## Fase 2 (90–180 dias) — Separar Plataforma de Estúdio

### Requisito 2.1: Separação de Control Plane e Worker Plane

**User Story:** Como arquiteto de plataforma, quero que a orquestração e a execução pesada sejam separadas, para que o dashboard permaneça responsivo enquanto jobs longos rodam em background.

#### Acceptance Criteria

1. THE Control_Plane SHALL ser responsável exclusivamente por receber requisições, gerenciar estado e despachar jobs para o Worker_Plane.
2. THE Worker_Plane SHALL executar todas as operações pesadas (captura, render de vídeo, geração de SCORM, geração de PDF, rebuild de biblioteca) de forma assíncrona.
3. WHEN um job for despachado para o Worker_Plane, THE Control_Plane SHALL retornar imediatamente ao cliente com um identificador de job e status `iniciado`.
4. THE Sistema SHALL garantir que apenas um job por tipo de operação pesada esteja ativo simultaneamente por tenant.
5. WHEN um job for concluído ou falhar, THE Worker_Plane SHALL notificar o Control_Plane via mecanismo de callback ou fila, sem polling ativo.

---

### Requisito 2.2: Jobs Assíncronos Reais

**User Story:** Como operador, quero que operações longas sejam gerenciadas como jobs com ciclo de vida rastreável, para que eu possa monitorar progresso, cancelar e reintentar sem perder visibilidade.

#### Acceptance Criteria

1. THE Sistema SHALL atribuir um `job_id` único a cada operação de background iniciada.
2. WHEN um job estiver em execução, THE Sistema SHALL expor seu progresso percentual via WebSocket em `/api/ws/status`.
3. THE Sistema SHALL persistir o estado de cada job (pendente, em execução, concluído, falhou) em armazenamento durável.
4. WHEN um job falhar, THE Sistema SHALL registrar o motivo da falha e disponibilizá-lo via API para consulta posterior.
5. THE Sistema SHALL permitir o cancelamento de um job em execução via `POST /api/cancelar` sem corromper artefatos parcialmente gerados.
6. IF um job for cancelado, THEN THE Sistema SHALL limpar arquivos temporários gerados até o momento do cancelamento.

---

### Requisito 2.3: Abstração de Storage de Artefatos

**User Story:** Como engenheiro de plataforma, quero que o acesso a artefatos seja feito via interface abstrata, para que o storage local possa ser substituído por storage remoto sem alterar os módulos de geração.

#### Acceptance Criteria

1. THE Sistema SHALL acessar todos os diretórios de artefatos (`roteiros_salvos/`, `videos_prontos/`, `scorm_exports/`, `documentacao_pdf/`, `audios_gerados/`) exclusivamente via funções de acesso centralizadas.
2. THE Sistema SHALL nunca construir caminhos de arquivo com concatenação de strings direta fora das funções de acesso centralizadas.
3. WHEN um artefato for escrito, THE Sistema SHALL usar escrita atômica independentemente do tipo de artefato.
4. THE Sistema SHALL validar que o caminho resolvido de qualquer artefato está dentro do diretório base esperado antes de qualquer operação de leitura ou escrita.

---

### Requisito 2.4: Brain com Persistência Menos Local-Dependente

**User Story:** Como arquiteto, quero que o Brain possa operar com backends de persistência intercambiáveis, para que a memória semântica não fique presa ao filesystem local de uma única máquina.

#### Acceptance Criteria

1. THE Brain SHALL expor uma interface de acesso com operações `get`, `set` e `query` independentes do backend de armazenamento.
2. THE Sistema SHALL suportar SQLite como backend padrão do Brain sem alteração de comportamento existente.
3. WHERE um backend remoto for configurado via variável de ambiente, THE Brain SHALL usar o backend remoto no lugar do SQLite local.
4. WHEN o backend do Brain estiver indisponível, THE Sistema SHALL operar em modo degradado sem o self-healing semântico, registrando o estado em log com nível `WARNING`.

---

### Requisito 2.5: Fronteiras por Tenant e Usuário

**User Story:** Como administrador de plataforma, quero que dados de diferentes tenants sejam isolados, para que um tenant não acesse ou interfira nos dados de outro.

#### Acceptance Criteria

1. THE Sistema SHALL associar cada roteiro, artefato e entrada de memória a um `tenant_id` explícito.
2. WHEN uma requisição for recebida sem `tenant_id` válido, THE Sistema SHALL usar o tenant padrão `senior_default` e registrar um aviso em log.
3. THE Sistema SHALL garantir que consultas ao Pinecone usem o `namespace` correspondente ao `tenant_id` da requisição.
4. THE Sistema SHALL garantir que consultas ao Brain usem particionamento por `tenant_id` para evitar contaminação de memória entre tenants.
5. IF uma requisição tentar acessar artefatos de um tenant diferente do autenticado, THEN THE Sistema SHALL retornar HTTP 403 e registrar a tentativa em log.

---

### Requisito 2.6: Versionamento Explícito de Artefatos

**User Story:** Como instrutor, quero que versões anteriores de roteiros, memória validada e variantes de captura sejam preservadas, para que eu possa reverter para uma versão anterior sem perda de trabalho.

#### Acceptance Criteria

1. THE Sistema SHALL manter um histórico de versões para cada roteiro em `roteiros_salvos/`, identificado por timestamp ou número de versão incremental.
2. WHEN um roteiro for sobrescrito, THE Sistema SHALL preservar a versão anterior antes de aplicar a nova versão.
3. THE Sistema SHALL versionar a Biblioteca_de_Ações com um identificador de versão gerado a cada Rebuild bem-sucedido.
4. THE Sistema SHALL versionar entradas de memória validada no Brain com timestamp de criação e de última atualização.
5. WHEN uma versão anterior de um roteiro for restaurada, THE Sistema SHALL executar `validar_roteiro()` na versão restaurada antes de torná-la ativa.

#### Propriedades de Corretude (Property-Based Testing)

- **Preservação de versão**: para qualquer sequência de N escritas sobre o mesmo roteiro, o Sistema SHALL preservar pelo menos as últimas 2 versões distintas.
- **Idempotência de restauração**: restaurar a versão V de um roteiro e depois restaurar V novamente SHALL produzir o mesmo estado que restaurar V uma única vez.

---

## Fase 3 (180–360 dias) — Productizar o Conhecimento Operacional

### Requisito 3.1: Brain e Biblioteca como Núcleo do Produto

**User Story:** Como product manager, quero que o Brain e a Biblioteca_de_Ações sejam a camada semântica central do produto, para que missões, GPS, DAP e playbooks sejam renderizações diferentes do mesmo conhecimento estruturado.

#### Acceptance Criteria

1. THE Sistema SHALL derivar missões, GPS, DAP e playbooks a partir da mesma representação semântica armazenada no Brain e na Biblioteca_de_Ações.
2. WHEN um roteiro for atualizado e promovido via HITL, THE Sistema SHALL propagar automaticamente as atualizações para todas as renderizações derivadas (missão, DAP, playbook) do mesmo fluxo.
3. THE Sistema SHALL garantir que a mesma ação semântica produza comportamento consistente independentemente da renderização (vídeo, SCORM, DAP, PDF).
4. THE Sistema SHALL expor uma API de consulta semântica que retorne todas as renderizações disponíveis para um dado fluxo ou ação.

---

### Requisito 3.2: Score de Confiabilidade por Fluxo e por Ação

**User Story:** Como operador de plataforma, quero um score de confiabilidade calculado por fluxo e por ação, para que eu possa priorizar revisões e melhorias nos pontos mais frágeis do sistema.

#### Acceptance Criteria

1. THE Sistema SHALL calcular um Score_de_Confiabilidade para cada ação na Biblioteca_de_Ações com base em: taxa de sucesso histórica de execução, confiança de captura e número de execuções registradas.
2. THE Sistema SHALL calcular um Score_de_Confiabilidade para cada fluxo (roteiro) como a média ponderada dos scores das ações que o compõem.
3. WHEN o Score_de_Confiabilidade de uma ação cair abaixo de 0.5, THE Sistema SHALL marcar a ação como `requer_revisao` na Biblioteca_de_Ações.
4. THE Sistema SHALL expor os scores via `/api/metricas` com granularidade por ação e por fluxo.
5. WHEN um roteiro for executado pelo Executor, THE Sistema SHALL atualizar os scores das ações envolvidas com base no resultado da execução.

#### Propriedades de Corretude (Property-Based Testing)

- **Invariante de score**: para qualquer ação A, `0.0 <= score(A) <= 1.0` SHALL ser sempre verdadeiro.
- **Monotonicidade de score com sucesso**: para qualquer ação A com N execuções bem-sucedidas consecutivas, `score(A, N+1) >= score(A, N)` SHALL ser verdadeiro.
- **Score de fluxo como agregação**: para qualquer roteiro R com ações A1..An, `score(R)` SHALL ser uma função determinística de `[score(A1), ..., score(An)]`.

---

### Requisito 3.3: Instrumentação de ROI Real

**User Story:** Como gestor de treinamento, quero métricas de ROI calculadas a partir de dados reais de uso, para que eu possa demonstrar o valor da plataforma com evidências concretas.

#### Acceptance Criteria

1. THE Sistema SHALL registrar o tempo de criação de cada treinamento desde a captura até a geração do primeiro artefato.
2. THE Sistema SHALL registrar a taxa de correção HITL por roteiro (número de edições manuais antes da aprovação).
3. THE Sistema SHALL registrar o índice de reuso de memória: proporção de ações geradas que foram recuperadas da Biblioteca_de_Ações versus criadas do zero.
4. THE Sistema SHALL calcular a redução estimada de suporte com base no número de consultas Aura respondidas via cache ou RAG sem acionar o Gemini Vision.
5. THE Sistema SHALL calcular o tempo médio até proficiência por fluxo com base nos dados de execução de missões.
6. THE Sistema SHALL expor todas as métricas de ROI via `/api/metricas` em formato consumível por dashboards externos.
7. WHEN uma métrica de ROI não puder ser calculada por falta de dados, THE Sistema SHALL retornar o valor `null` para esse campo em vez de omiti-lo ou retornar zero.

---

### Requisito 3.4: Arquitetura Preparada para Novos Módulos

**User Story:** Como arquiteto, quero que a plataforma suporte a adição de novos módulos além do Senior X sem alterações nos contratos centrais, para que o produto possa expandir para outros ERPs e sistemas.

#### Acceptance Criteria

1. THE Sistema SHALL definir o contrato do roteiro de forma independente de qualquer ERP ou sistema específico.
2. THE Sistema SHALL permitir a configuração de novos módulos de captura via variáveis de ambiente sem alteração de código nos módulos centrais.
3. WHERE um novo módulo de ERP for configurado, THE Sistema SHALL usar o mesmo pipeline de geração, execução e entrega de artefatos sem modificações.
4. THE Sistema SHALL isolar toda referência específica ao Senior X em módulos de adaptador, não nos módulos centrais do pipeline.
5. THE Sistema SHALL documentar o contrato de integração necessário para que um novo módulo de captura seja compatível com o Gerador e o Executor.

---

## Requisitos Não-Funcionais Transversais

### Requisito NFR-1: Segurança e Autenticação

**User Story:** Como administrador, quero que todas as rotas da API sejam protegidas por autenticação, para que apenas clientes autorizados possam acionar operações do pipeline.

#### Acceptance Criteria

1. THE Sistema SHALL exigir um token Bearer válido em todas as rotas da API que acionam operações de pipeline.
2. THE Sistema SHALL ler o segredo de autenticação exclusivamente da variável de ambiente `AURA_API_SECRET`, nunca de código-fonte.
3. WHEN uma requisição chegar sem token ou com token inválido, THE Sistema SHALL retornar HTTP 401 e registrar a tentativa em log com o IP de origem.
4. THE Sistema SHALL aplicar rate limiting de no máximo 20 requisições por minuto por IP em todas as rotas da API.
5. WHEN o rate limit for excedido, THE Sistema SHALL retornar HTTP 429 com mensagem de orientação ao cliente.
6. THE Sistema SHALL validar todos os caminhos de arquivo fornecidos pelo cliente contra o diretório base esperado antes de qualquer operação de I/O.
7. IF um caminho de arquivo resolver para fora do diretório base, THEN THE Sistema SHALL retornar HTTP 400 e registrar a tentativa em log.

---

### Requisito NFR-2: Confiabilidade e Resiliência

**User Story:** Como operador, quero que o sistema se recupere de falhas transitórias de APIs externas sem interromper o fluxo do usuário, para que a experiência seja previsível mesmo em condições adversas.

#### Acceptance Criteria

1. THE Sistema SHALL implementar retry com exponential backoff para todas as chamadas às APIs externas (Gemini, OpenAI, Pinecone) com no mínimo 2 tentativas adicionais após a primeira falha.
2. WHEN todas as tentativas de uma chamada de API externa falharem, THE Sistema SHALL retornar uma resposta de erro estruturada com mensagem legível ao usuário, sem expor detalhes internos.
3. THE Sistema SHALL operar em modo degradado quando o Pinecone estiver indisponível, gerando roteiros sem contexto RAG e registrando o estado em log.
4. THE Sistema SHALL operar em modo degradado quando o Gemini estiver indisponível, retornando erro estruturado ao invés de travar o processo.
5. WHEN o Brain estiver indisponível, THE Sistema SHALL continuar a execução do Executor sem self-healing semântico, registrando cada fallback em log.

---

### Requisito NFR-3: Observabilidade

**User Story:** Como engenheiro de operações, quero que o sistema emita métricas e logs suficientes para diagnosticar problemas sem acesso direto ao servidor, para que incidentes possam ser investigados remotamente.

#### Acceptance Criteria

1. THE Sistema SHALL emitir um log de início e fim para cada operação de background, incluindo duração total em milissegundos.
2. THE Sistema SHALL expor via `/api/metricas` as métricas: total de aulas, horas poupadas, economia estimada, total memorizado no Brain, hits de self-healing e tamanho do cache DAP.
3. THE Sistema SHALL emitir progresso percentual via WebSocket para todas as operações longas com granularidade mínima de 10%.
4. WHEN um processo de background for cancelado pelo usuário, THE Sistema SHALL registrar o evento com timestamp e identificador do processo.
5. THE Sistema SHALL manter os logs de execução de cada job acessíveis via API por pelo menos 24 horas após a conclusão do job.

---

### Requisito NFR-4: Compatibilidade do Roteiro

**User Story:** Como desenvolvedor, quero que o schema do roteiro seja retrocompatível entre versões do sistema, para que roteiros existentes continuem funcionando após atualizações da plataforma.

#### Acceptance Criteria

1. THE Sistema SHALL processar roteiros gerados por versões anteriores do sistema sem erro, aplicando valores padrão para campos ausentes.
2. WHEN um campo obrigatório estiver ausente em um roteiro legado, THE Sistema SHALL aplicar o valor padrão documentado e registrar um aviso em log.
3. THE Sistema SHALL nunca remover campos do schema do roteiro sem um período de deprecação de pelo menos uma fase (90 dias).
4. THE Sistema SHALL documentar explicitamente qualquer mudança de schema do roteiro com versão, data e campos afetados.

#### Propriedades de Corretude (Property-Based Testing)

- **Round-trip de roteiro**: para qualquer roteiro válido R, serializar para JSON e desserializar SHALL produzir um roteiro R' tal que `validar_roteiro(R') == validar_roteiro(R)`.
- **Tolerância a campos extras**: para qualquer roteiro válido R, adicionar campos desconhecidos ao JSON SHALL não alterar o resultado de `validar_roteiro(R)`.
- **Idempotência de defaults**: aplicar defaults a um roteiro já completo SHALL não alterar nenhum campo existente.

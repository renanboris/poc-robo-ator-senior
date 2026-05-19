# Requirements Document

## Introduction

A plataforma GenUCS / Senior Training OS é hoje acoplada ao Senior X ERP em três pontos principais: (1) o fluxo de login automático em `capture_variants/capture_dual_output.py` e `main.py`, que usa credenciais e seletores específicos do Senior X; (2) a camada de heurísticas de localização em `vision_engine.py`, que contém lógica específica para componentes Angular/PrimeNG do Senior X; e (3) os prompts de IA (`aura_prompt.txt`, `generator_prompt.txt`) que referenciam a Senior Sistemas e o contexto de ERP.

Esta feature tem como objetivo validar se o pipeline completo — captura → roteiro → execução → vídeo → SCORM → PDF → Aura DAP — funciona de ponta a ponta com qualquer site web genérico, sem exigir credenciais do Senior X nem depender de componentes Angular/PrimeNG. O artefato central (roteiro JSON) permanece inalterado; o que muda é a camada de entrada (captura) e a camada de execução (login/navegação).

O módulo de captura ativo é `capture_variants/capture_dual_output.py` (dual output com shadow JSONL). O arquivo `capture.py` que existia na raiz foi movido para `old_but_gold/` por ser uma versão anterior sem suporte a dual output.

A abstração `CaptureAdapter` já existe em `contracts/capture_adapter.py` e define o protocolo correto. Esta feature completa a implementação desse contrato nos módulos que ainda ignoram a abstração.

## Glossary

- **Sistema_Alvo**: qualquer aplicação web que o usuário deseja mapear — pode ser o Senior X, um e-commerce, um portal público, um sistema de RH genérico ou qualquer outro site.
- **Adapter**: implementação do protocolo `CaptureAdapter` para um Sistema_Alvo específico.
- **Adapter_Genérico**: implementação do protocolo `CaptureAdapter` para sites que não requerem login automático ou que usam login padrão HTML.
- **Roteiro**: artefato JSON central do sistema, produzido pela captura e consumido por todos os estágios downstream.
- **Pipeline**: sequência completa captura → geração de roteiro → execução → vídeo → SCORM → PDF → Aura DAP.
- **Captura**: fase em que o usuário navega no Sistema_Alvo enquanto o radar JavaScript registra interações.
- **Execução**: fase em que o robô Playwright reproduz o roteiro no Sistema_Alvo para gravar o vídeo.
- **Heurística_Senior_X**: lógica específica da camada 1.5 do `vision_engine.py` que usa seletores de componentes Angular/PrimeNG do Senior X.
- **Modo_Sem_Login**: configuração do Adapter_Genérico em que o robô navega diretamente para a URL alvo sem executar fluxo de autenticação.
- **Modo_Login_Genérico**: configuração do Adapter_Genérico em que o robô executa login com seletores HTML padrão configuráveis via `.env`.
- **Tenant_ID**: identificador de namespace no Pinecone para segregação de contexto RAG por cliente ou sistema.

---

## Requirements

### Requirement 1: Adapter Genérico para Captura

**User Story:** Como analista de treinamento, quero mapear um fluxo em qualquer site web sem precisar configurar credenciais do Senior X, para que eu possa usar a plataforma com sistemas além do ERP.

#### Acceptance Criteria

1. THE `Adapter_Genérico` SHALL implementar o protocolo `CaptureAdapter` definido em `contracts/capture_adapter.py`, satisfazendo todos os métodos abstratos declarados nesse protocolo.
2. WHEN `CAPTURE_ADAPTER=generic` está definido no `.env`, THE `Pipeline` SHALL instanciar o `Adapter_Genérico` via `get_capture_adapter()` em vez do `SeniorXAdapter`.
3. THE `Adapter_Genérico` SHALL ler a URL alvo exclusivamente da variável de ambiente `TARGET_URL`, sem nenhum valor padrão hardcoded no código.
4. IF `TARGET_URL` não estiver definida no `.env` ou for uma string vazia, THEN THE `Adapter_Genérico` SHALL emitir um erro descritivo identificando a variável ausente e encerrar o processo antes de abrir o navegador.
5. IF `LOGIN_REQUIRED` contiver um valor diferente de `true` ou `false` (case-insensitive), THEN THE `Adapter_Genérico` SHALL emitir um erro descritivo indicando os valores aceitos e encerrar o processo antes de abrir o navegador.
6. WHERE `LOGIN_REQUIRED=false` está configurado, THE `Adapter_Genérico` SHALL navegar diretamente para `TARGET_URL` sem executar nenhum fluxo de autenticação.
7. WHERE `LOGIN_REQUIRED=true` está configurado, THE `Adapter_Genérico` SHALL executar o fluxo de login usando os seletores definidos em `LOGIN_SELECTOR_USER`, `LOGIN_SELECTOR_PASS` e `LOGIN_SELECTOR_SUBMIT`.
8. THE `Adapter_Genérico` SHALL retornar `nome_sistema` como o valor da variável de ambiente `TARGET_SYSTEM_NAME`, com fallback para `"Site Genérico"` quando não definida ou vazia.
9. IF `LOGIN_REQUIRED=true` e qualquer seletor de login (`LOGIN_SELECTOR_USER`, `LOGIN_SELECTOR_PASS` ou `LOGIN_SELECTOR_SUBMIT`) estiver ausente ou vazio no `.env`, THEN THE `Adapter_Genérico` SHALL emitir um erro descritivo listando todas as variáveis ausentes e encerrar o processo antes de abrir o navegador.
10. IF `LOGIN_REQUIRED=true` e o fluxo de autenticação não resultar em navegação bem-sucedida para `TARGET_URL` dentro de 30 segundos, THEN THE `Adapter_Genérico` SHALL encerrar o processo com uma mensagem de erro descritiva indicando timeout de autenticação.
11. IF `LOGIN_REQUIRED=true` e qualquer seletor de login estiver presente no `.env` mas não for encontrado no DOM da página dentro de 10 segundos, THEN THE `Adapter_Genérico` SHALL encerrar o processo com uma mensagem de erro descritiva identificando o seletor não encontrado.

---

### Requirement 2: Desacoplamento do Login em `capture_dual_output.py`

**User Story:** Como desenvolvedor, quero que o `capture_variants/capture_dual_output.py` use o `CaptureAdapter` para obter URL, credenciais e seletores de login, para que o módulo de captura funcione com qualquer sistema sem modificação de código.

#### Acceptance Criteria

1. WHEN `capture_dual_output.py` inicia a sessão de captura, THE `Captura` SHALL obter a URL alvo exclusivamente via `adapter.url_base`, nunca lendo `SENIOR_URL` diretamente.
2. WHEN `capture_dual_output.py` executa o fluxo de login automático, THE `Captura` SHALL usar os seletores retornados por `adapter.obter_seletores_login()`, nunca seletores hardcoded.
3. WHEN `capture_dual_output.py` executa o fluxo de login automático, THE `Captura` SHALL usar as credenciais retornadas por `adapter.obter_credenciais()`, nunca lendo `SENIOR_USER_CAPTURE` ou `SENIOR_PASS_CAPTURE` diretamente.
4. WHEN o `Adapter_Genérico` está ativo e `LOGIN_REQUIRED=false`, THE `Captura` SHALL pular completamente o bloco de login e injetar o radar JavaScript dentro de 5 segundos após a navegação para `TARGET_URL` retornar estado `load`.
5. WHEN o `Adapter_Genérico` está ativo e `LOGIN_REQUIRED=true`, THE `Captura` SHALL injetar o radar JavaScript dentro de 5 segundos após a conclusão confirmada do login, sem aguardar nenhuma etapa adicional.
6. IF o login automático falhar (timeout ou erro Playwright), THEN THE `Captura` SHALL ativar o fallback para login manual, exibindo uma mensagem ao usuário e aguardando confirmação manual, independentemente do adapter em uso.
7. THE `Captura` SHALL capturar e registrar os eventos de clique, digitação, blur, duplo clique e clique direito com o mesmo comportamento independentemente do adapter ativo.
8. THE `Captura` SHALL preservar o comportamento de dual output (roteiro JSON + shadow JSONL) independentemente do adapter ativo.

---

### Requirement 3: Desacoplamento do Login em `main.py`

**User Story:** Como desenvolvedor, quero que o `main.py` use o `CaptureAdapter` para obter URL e credenciais de execução, para que o robô de gravação funcione com qualquer sistema sem modificação de código.

#### Acceptance Criteria

1. WHEN `main.py` inicia a execução do roteiro, THE `Executor` SHALL obter a URL alvo exclusivamente via `adapter.url_base`, nunca lendo `SENIOR_URL` diretamente.
2. WHEN `main.py` executa o fluxo de login, THE `Executor` SHALL usar os seletores retornados por `adapter.obter_seletores_login()`, nunca seletores hardcoded.
3. WHEN `main.py` executa o fluxo de login, THE `Executor` SHALL usar as credenciais retornadas por `adapter.obter_credenciais()`, nunca lendo `SENIOR_USER_EXECUTE` ou `SENIOR_PASS_EXECUTE` diretamente.
4. WHEN o `Adapter_Genérico` está ativo e `LOGIN_REQUIRED=false`, THE `Executor` SHALL pular o bloco de login e aguardar o evento `load` da página alvo antes de exibir o overlay de confirmação de gravação.
5. THE `Executor` SHALL exibir o overlay de confirmação "Pronto para gravar?" independentemente do adapter em uso e independentemente de o login ter sido executado ou pulado.
6. IF o login automático falhar (timeout ou erro Playwright), THEN THE `Executor` SHALL ativar o fallback para login manual, exibindo uma mensagem ao usuário e aguardando confirmação manual, independentemente do adapter em uso.

---

### Requirement 4: Heurísticas de Localização Agnósticas de Sistema

**User Story:** Como analista de treinamento, quero que o robô consiga localizar elementos em sites genéricos sem depender das heurísticas específicas do Senior X, para que a execução funcione em qualquer sistema web.

#### Acceptance Criteria

1. IF o adapter ativo for o `SeniorXAdapter`, THEN THE `vision_engine` SHALL executar a camada 1.5 (Heurísticas Senior X), tentando os seletores de ícone Senior X declarados na ordem definida para elementos com generic-tag ou label vazia.
2. IF o adapter ativo for o `Adapter_Genérico`, THEN THE `vision_engine` SHALL pular a camada 1.5 e avançar diretamente para a camada 2 (Sniper semântico).
3. THE `vision_engine` SHALL preservar as camadas Brain (0), Sniper semântico (2), Template Matching (3), Gemini Vision (4) e coordenadas (5) sem alteração para qualquer adapter ativo.
4. WHEN o primeiro passo do roteiro é executado em uma sessão, THE `vision_engine` SHALL registrar no log em nível INFO o nome da classe do adapter ativo.
5. IF o adapter ativo não for reconhecido como `SeniorXAdapter` nem como `Adapter_Genérico`, THEN THE `vision_engine` SHALL pular a camada 1.5 e prosseguir com as camadas 0, 2, 3, 4 e 5.

---

### Requirement 5: Prompts de IA Parametrizáveis por Sistema

**User Story:** Como analista de treinamento, quero que os prompts enviados ao Gemini reflitam o sistema alvo correto, para que o roteiro gerado e as narrações façam sentido para o site que está sendo mapeado.

#### Acceptance Criteria

1. WHEN `generator_engine.py` gera um roteiro e o adapter ativo não for o `SeniorXAdapter` e `TARGET_SYSTEM_NAME` for uma string não vazia, THE `Gerador` SHALL substituir todas as ocorrências de "ERP" e "Senior X" (sem distinção de maiúsculas e minúsculas) pelo valor de `TARGET_SYSTEM_NAME` no prompt enviado ao Gemini, preservando o restante do texto do prompt sem modificação.
2. WHEN `capture_dual_output.py` invoca a Aura para processar o log de captura, THE `Captura` SHALL incluir o valor de `adapter.nome_sistema` em um campo de contexto nomeado e distinguível do restante do conteúdo do prompt.
3. WHILE o `SeniorXAdapter` está ativo, THE `Gerador` SHALL enviar ao Gemini o prompt original sem nenhuma substituição de nome de sistema, independentemente do valor de `TARGET_SYSTEM_NAME`.
4. IF `TARGET_SYSTEM_NAME` não estiver definida ou for uma string vazia e o adapter ativo for o `Adapter_Genérico`, THEN THE `Gerador` SHALL omitir a substituição e enviar o prompt original sem modificação.
5. THE `Gerador` SHALL preservar o contrato do roteiro JSON (campos `metadata`, `configuracao_gravacao`, `passos`) independentemente do sistema alvo.

---

### Requirement 6: Configuração via `.env` para Sites Genéricos

**User Story:** Como analista de treinamento, quero configurar um site genérico apenas editando o arquivo `.env`, sem precisar modificar código Python, para que a adoção seja simples e segura.

#### Acceptance Criteria

1. THE `Pipeline` SHALL reconhecer e processar as variáveis de ambiente `CAPTURE_ADAPTER`, `TARGET_URL`, `TARGET_SYSTEM_NAME`, `LOGIN_REQUIRED`, `LOGIN_SELECTOR_USER`, `LOGIN_SELECTOR_PASS` e `LOGIN_SELECTOR_SUBMIT` quando `CAPTURE_ADAPTER=generic`, instanciando o `Adapter_Genérico` via `get_capture_adapter()` com os valores lidos.
2. THE `.env.example` SHALL conter todas as variáveis listadas no critério 1 com valores de exemplo e comentários explicativos em português.
3. IF `CAPTURE_ADAPTER=generic` e `TARGET_URL` for uma URL válida (iniciando com `http://` ou `https://`) e `LOGIN_REQUIRED=false`, THEN THE `Pipeline` SHALL iniciar a captura sem solicitar nenhuma credencial ao usuário e sem emitir erros por ausência de variáveis de credencial.
4. IF `CAPTURE_ADAPTER=generic` e `LOGIN_REQUIRED` não estiver definida no `.env`, THEN THE `Pipeline` SHALL tratar `LOGIN_REQUIRED` como `false` para o `Adapter_Genérico`.
5. WHILE o `Adapter_Genérico` está ativo, THE `Pipeline` SHALL ignorar as variáveis `SENIOR_URL`, `SENIOR_USER_CAPTURE`, `SENIOR_PASS_CAPTURE`, `SENIOR_USER_EXECUTE` e `SENIOR_PASS_EXECUTE` sem emitir erros por ausência delas.
6. IF `CAPTURE_ADAPTER=generic` e `TARGET_URL` não estiver definida ou não iniciar com `http://` ou `https://`, THEN THE `Pipeline` SHALL emitir um erro descritivo identificando o problema e encerrar o processo antes de abrir o navegador.
7. IF `CAPTURE_ADAPTER=generic` e `LOGIN_REQUIRED=true` e qualquer seletor de login estiver ausente ou vazio, THEN THE `Pipeline` SHALL emitir um erro descritivo listando todas as variáveis ausentes e encerrar o processo antes de abrir o navegador.

---

### Requirement 7: Compatibilidade do Roteiro com o Pipeline Downstream

**User Story:** Como analista de treinamento, quero que um roteiro gerado a partir de um site genérico produza vídeo, SCORM, PDF e Aura DAP com a mesma qualidade de um roteiro do Senior X, para que todos os artefatos de treinamento sejam gerados corretamente.

#### Acceptance Criteria

1. THE `Roteiro` gerado a partir de um site genérico SHALL conter os campos obrigatórios `metadata`, `configuracao_gravacao` e `passos`, com pelo menos um passo com `is_conclusao: true`, e cada passo SHALL conter os sub-campos `pedagogia.ancora` e `acoes_tecnicas[].elemento_alvo`.
2. WHEN `scorm_builder.py` processa um roteiro gerado de site genérico, THE `SCORM_Builder` SHALL produzir um arquivo ZIP no diretório `scorm_exports/` com o nome derivado do roteiro.
3. WHEN `pdf_builder.py` processa um roteiro gerado de site genérico, THE `PDF_Builder` SHALL produzir um arquivo PDF no diretório `documentacao_pdf/` com o nome derivado do roteiro.
4. WHEN `main.py` executa um roteiro gerado de site genérico, THE `Executor` SHALL produzir um arquivo MP4 no diretório `videos_prontos/` com o nome derivado do roteiro.
5. THE `lego_builder` SHALL indexar ações capturadas de sites genéricos na `biblioteca_acoes.json` com os campos `intencao_semantica`, `_source` e `_versao_biblioteca` presentes e com `intencao_semantica` em letras minúsculas.
6. FOR ALL roteiros válidos gerados de sites genéricos, `validar_roteiro_ia()` de `utils.py` SHALL retornar `(True, ...)` sem modificação da função de validação.

---

### Requirement 8: Observabilidade e Diagnóstico do Modo Genérico

**User Story:** Como desenvolvedor, quero que o sistema registre claramente qual adapter está ativo e qual sistema está sendo mapeado, para que eu possa diagnosticar problemas rapidamente.

#### Acceptance Criteria

1. WHEN qualquer estágio do `Pipeline` é iniciado, THE `Pipeline` SHALL registrar em nível INFO no log o nome da classe do adapter ativo e o valor de `adapter.nome_sistema`.
2. WHEN o `Adapter_Genérico` pula o fluxo de login, THE `Captura` SHALL registrar no log em nível INFO uma mensagem indicando o modo sem login e o valor de `adapter.url_alvo`.
3. WHEN o `Adapter_Genérico` executa o fluxo de login genérico, THE `Captura` SHALL registrar no log em nível INFO os valores de `LOGIN_SELECTOR_USER`, `LOGIN_SELECTOR_PASS` e `LOGIN_SELECTOR_SUBMIT`, sem registrar os valores das variáveis de credencial.
4. IF o login genérico for tentado e falhar, THEN THE `Captura` SHALL registrar no log em nível ERROR o seletor que falhou e a mensagem de erro Playwright correspondente antes de ativar o fallback manual.

---

### Requirement 9: Preservação do Comportamento do Senior X

**User Story:** Como usuário do Senior X, quero que a adição de suporte a sites genéricos não altere nenhum comportamento existente do pipeline com o Senior X, para que meus fluxos de treinamento atuais continuem funcionando.

#### Acceptance Criteria

1. IF `CAPTURE_ADAPTER` não estiver definida no `.env`, THEN `get_capture_adapter()` SHALL retornar uma instância de `SeniorXAdapter`.
2. IF `CAPTURE_ADAPTER=senior_x` estiver definida, THEN `get_capture_adapter()` SHALL retornar uma instância de `SeniorXAdapter`.
3. IF `CAPTURE_ADAPTER` contiver um valor não reconhecido (diferente de `generic` e `senior_x`), THEN `get_capture_adapter()` SHALL registrar um aviso no log e retornar uma instância de `SeniorXAdapter` como fallback.
4. WHILE o `SeniorXAdapter` está ativo, THE `vision_engine` SHALL executar a camada 1.5 tentando os seletores de ícone Senior X declarados na ordem definida para elementos com generic-tag ou label vazia.
5. WHEN o `SeniorXAdapter` está ativo, THE `Captura` SHALL ler credenciais de `SENIOR_USER_CAPTURE` e `SENIOR_PASS_CAPTURE`, e THE `Executor` SHALL encerrar o processo com erro descritivo se `SENIOR_USER_EXECUTE` ou `SENIOR_PASS_EXECUTE` não estiverem definidas.
6. FOR ALL roteiros existentes gerados com o `SeniorXAdapter`, `main.py` SHALL carregar o roteiro sem erro de validação, executar todos os passos e produzir os artefatos de saída sem falha de compatibilidade.
7. THE `lego_builder` SHALL indexar ações do Senior X na `biblioteca_acoes.json` com os campos `intencao_semantica` (em letras minúsculas), `_source` e `_versao_biblioteca` presentes, sem alteração do formato atual.

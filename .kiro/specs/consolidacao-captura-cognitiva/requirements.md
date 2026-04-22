# Documento de Requisitos

## Introdução

Esta feature consolida a arquitetura de captura e inferência semântica do Senior Training OS, eliminando acoplamentos indevidos, duplicações de lógica e fragilidades estruturais identificadas no roadmap de curto prazo.

O escopo abrange quatro eixos de melhoria:

1. **Separação de responsabilidades** — desacoplar a inferência Gemini Vision do loop síncrono de captura no `capture_dual_output.py`, tornando a captura resiliente a falhas de IA.
2. **Consolidação semântica** — unificar as funções de inferência semântica duplicadas em `shadow_builder.py` como fonte canônica de verdade.
3. **Reordenação da cascata** — corrigir a ordem das camadas de localização no `vision_engine.py` para priorizar estratégias mais baratas e confiáveis antes de coordenadas e Gemini.
4. **Telemetria unificada** — adicionar view SQL e função de relatório que consolide as tabelas fragmentadas de telemetria no `brain.db`.
5. **Cobertura de testes** — introduzir testes automatizados para os módulos puros (`shadow_builder`, Brain do `vision_engine`, `utils`), executáveis sem Playwright, Gemini, OpenAI ou Pinecone.

Nenhuma dessas mudanças deve quebrar o contrato do roteiro JSON, as interfaces públicas dos módulos envolvidos, ou o pipeline captura → roteiro → vídeo/SCORM/PDF.

---

## Glossário

- **Capture_Dual_Output**: Módulo `capture_variants/capture_dual_output.py` — motor principal de captura de interações do usuário no Senior X via Playwright.
- **Shadow_Builder**: Módulo `shadow_builder.py` — módulo puro de inferência semântica e montagem de eventos Shadow JSONL. Fonte canônica de toda inferência semântica.
- **Capture_Hybrid_Shadow**: Módulo `capture_variants/capture_hybrid_shadow.py` — variante híbrida de captura com inferência local.
- **Vision_Engine**: Módulo `vision_engine.py` — motor de localização de elementos com cascata de estratégias de resiliência.
- **Brain**: Subsistema de memória semântica de longo prazo do `vision_engine.py`, persistido em `brain.db` (SQLite).
- **Evento_Bruto**: Evento de captura gerado pelo loop de captura, sem enriquecimento Gemini Vision — contém apenas dados mecânicos (seletor, coordenadas, tag, label, screenshot).
- **Evento_Enriquecido**: Evento_Bruto após processamento pela função `enriquecer_eventos_com_gemini()`, com campos semânticos preenchidos por Gemini Vision ou por fallback heurístico.
- **Evento_Shadow**: Estrutura completa de evento persistida no Shadow JSONL, produzida por `_montar_evento_shadow()`.
- **Semantic_Action**: Classificação semântica da intenção do usuário. Vocabulário controlado: `fill | search | confirm | delete | save | open | navigate | select | close`.
- **Cascata_Vision**: Sequência ordenada de estratégias de localização de elementos no `vision_engine.py`, do mais barato ao mais caro.
- **Template_Matching**: Estratégia de localização por comparação de imagem de referência com o estado atual da tela.
- **Sniper_Semantico**: Estratégia de localização por seletores Playwright nativos semânticos (`getByRole`, `getByLabel`, `getByPlaceholder`, `getByTitle`).
- **Telemetria_Camadas**: Tabela `telemetria_camadas` no `brain.db` — contadores agregados de acertos/falhas por camada da cascata.
- **Telemetria_Execucoes**: Tabela `telemetria_execucoes` no `brain.db` — registros granulares por execução individual.
- **View_Telemetria_Unificada**: View SQL `v_telemetria_unificada` que consolida `telemetria_camadas` e `telemetria_execucoes` em uma única superfície de consulta.
- **Roteiro**: Artefato JSON central do sistema com campos obrigatórios `metadata`, `configuracao_gravacao` e `passos`. Contrato imutável entre captura, geração e entrega.
- **Shadow_JSONL**: Arquivo de saída da captura no formato JSON Lines, persistido em `shadow_exports/`.
- **Migração_Idempotente**: Script ou operação de banco de dados que pode ser executada múltiplas vezes sem erro e sem efeito colateral adicional após a primeira execução bem-sucedida.

---

## Requisitos

### Requisito 1: Separação de Captura e Inferência Gemini

**User Story:** Como desenvolvedor do pipeline de captura, quero que a captura de eventos e a análise Gemini Vision sejam etapas independentes, para que uma falha ou lentidão da API Gemini não interrompa nem atrase a gravação do workflow do usuário.

#### Critérios de Aceitação

1. THE `Capture_Dual_Output` SHALL executar o loop de captura de eventos sem chamar a API Gemini Vision durante a interação do usuário.

2. WHEN o usuário encerra a sessão de captura, THE `Capture_Dual_Output` SHALL produzir uma lista de `Evento_Bruto` com todos os campos mecânicos preenchidos (`seletor_hint`, `coordenadas_relativas`, `tag`, `label_curto`, `screenshot_referencia`, `iframe_hint`).

3. THE `Capture_Dual_Output` SHALL expor uma função `enriquecer_eventos_com_gemini(eventos_brutos: list[dict]) -> list[dict]` que recebe a lista de `Evento_Bruto` e retorna a lista de `Evento_Enriquecido` com campos semânticos preenchidos.

4. WHEN `gemini_client` for `None` ou a chamada à API Gemini falhar, THE `enriquecer_eventos_com_gemini` SHALL preencher os campos semânticos de cada evento usando as funções de inferência heurística do `Shadow_Builder`, sem lançar exceção.

5. IF a chamada Gemini Vision falhar para um evento específico, THEN THE `enriquecer_eventos_com_gemini` SHALL registrar um `logger.warning` com o `id_acao` e o motivo da falha, e continuar processando os demais eventos da lista.

6. THE `Capture_Dual_Output` SHALL preservar a interface de saída existente: o Shadow JSONL gerado ao final da sessão deve conter `Evento_Shadow` com a mesma estrutura de campos que a versão anterior.

7. WHEN a captura for concluída sem Gemini disponível, THE `Capture_Dual_Output` SHALL emitir no stdout a mensagem `CAPTURA_SEM_GEMINI:N` onde `N` é o número de eventos capturados, para rastreabilidade no painel.

#### Propriedades de Corretude (PBT)

**P1.1 — Invariante de separação:** Para qualquer lista de `Evento_Bruto` gerada pelo loop de captura, nenhum evento deve conter os campos `intencao_semantica`, `semantic_action` ou `descricao_visual` preenchidos com valores não-padrão antes de `enriquecer_eventos_com_gemini()` ser chamada.

**P1.2 — Completude do enriquecimento:** Para qualquer lista de `Evento_Bruto` com `N >= 1` eventos, `enriquecer_eventos_com_gemini()` deve retornar uma lista com exatamente `N` eventos, cada um com `semantic_action` pertencente ao vocabulário controlado, independentemente de Gemini estar disponível ou não.

**P1.3 — Resiliência a falhas parciais:** Para qualquer lista de `N` eventos onde `K` deles causam falha na API Gemini (`0 <= K <= N`), `enriquecer_eventos_com_gemini()` deve retornar `N` eventos enriquecidos (os `K` com fallback heurístico, os `N-K` com Gemini), sem lançar exceção.

---

### Requisito 2: Consolidação da Inferência Semântica no Shadow_Builder

**User Story:** Como desenvolvedor de manutenção, quero que toda a lógica de inferência semântica esteja centralizada em `shadow_builder.py`, para que correções e melhorias precisem ser feitas em um único lugar e não se percam em implementações paralelas.

#### Critérios de Aceitação

1. THE `Shadow_Builder` SHALL conter uma função unificada `inferir_acao_semantica(acao: str, label: str, seletor: str, tag: str, valor_input: str, hints: dict) -> str` que substitui tanto `_infer_semantic_action_from_capture()` quanto `infer_semantic_action_from_hints()`.

2. THE `inferir_acao_semantica` SHALL retornar sempre um valor do vocabulário controlado: `fill | search | confirm | delete | save | open | navigate | select | close`.

3. THE `Shadow_Builder` SHALL conter uma função unificada `inferir_entidade_negocio(label: str, seletor: str, tag: str, contexto_tela: str, hints: dict) -> str` que substitui tanto `_infer_business_entity_from_capture()` quanto `infer_business_entity_from_hints()`.

4. THE `Shadow_Builder` SHALL conter uma função unificada `inferir_padrao_interacao(acao: str, label: str, seletor: str, tag: str, capture_scope: str, hints: dict) -> str` que substitui tanto `_infer_pattern_from_capture()` quanto `infer_pattern_from_hints()`.

5. THE `Shadow_Builder` SHALL conter uma função unificada `classificar_ruido(label: str, seletor: str, acao: str, tag: str, capture_scope: str, valor_input: str, hints: dict) -> bool` que substitui tanto `_is_noise_event()` quanto `is_noise_event()`.

6. WHEN `Capture_Hybrid_Shadow` precisar de inferência semântica, THE `Capture_Hybrid_Shadow` SHALL importar as funções unificadas de `Shadow_Builder` em vez de manter implementações locais.

7. THE `Shadow_Builder` SHALL permanecer um módulo puro: sem imports de `playwright`, `google.genai`, `openai`, `pinecone`, `asyncio` ou `subprocess`.

8. THE `Shadow_Builder` SHALL preservar as assinaturas públicas existentes `_montar_evento_shadow()` e `_salvar_shadow_jsonl()` sem alteração de parâmetros ou tipo de retorno.

#### Propriedades de Corretude (PBT)

**P2.1 — Vocabulário controlado:** Para qualquer combinação de `(acao, label, seletor, tag, valor_input, hints)` com strings não-nulas, `inferir_acao_semantica()` deve retornar um valor pertencente ao conjunto `{"fill", "search", "confirm", "delete", "save", "open", "navigate", "select", "close"}`.

**P2.2 — Determinismo:** Para os mesmos inputs, `inferir_acao_semantica()` deve retornar sempre o mesmo resultado (função pura sem estado global).

**P2.3 — Equivalência de implementações:** Para qualquer input que era aceito por `_infer_semantic_action_from_capture()` ou por `infer_semantic_action_from_hints()`, a função unificada `inferir_acao_semantica()` deve retornar o mesmo valor que a implementação original correspondente (propriedade metamórfica de consolidação).

**P2.4 — Pureza do módulo:** A importação de `shadow_builder` em ambiente de teste sem Playwright, Gemini, OpenAI ou Pinecone instalados não deve lançar `ImportError` nem `ModuleNotFoundError`.

---

### Requisito 3: Reordenação da Cascata do Vision_Engine

**User Story:** Como operador do robô de execução, quero que o `vision_engine.py` tente estratégias mais confiáveis antes de recorrer a coordenadas absolutas ou Gemini Vision, para que a taxa de sucesso de localização de elementos aumente e o custo de execução diminua.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL executar as estratégias de localização na seguinte ordem fixa:
   - Camada 0: Brain (memória SQLite)
   - Camada 0.5: Menu de contexto ativo
   - Camada 1: Foco nativo / active element
   - Camada 1.5: Heurísticas Senior X
   - Camada 1_T: Template Matching
   - Camada 2_S: Sniper Semântico
   - Camada 2: Coordenadas capturadas
   - Camada 3: Seletor hint original
   - Camada 4: Busca em frames
   - Camada 5: Gemini Vision

2. WHEN Template Matching for acionado, THE `Vision_Engine` SHALL tentar localizar o elemento por comparação de imagem de referência antes de tentar coordenadas absolutas.

3. WHEN Sniper Semântico for acionado, THE `Vision_Engine` SHALL tentar seletores Playwright nativos (`getByRole`, `getByLabel`, `getByPlaceholder`, `getByTitle`) antes de tentar coordenadas absolutas.

4. THE `Vision_Engine` SHALL documentar cada camada da cascata com um comentário inline descrevendo sua responsabilidade e condição de ativação.

5. THE `Vision_Engine` SHALL preservar a assinatura pública `encontrar_e_clicar(page, passo, acao_tecnica, ...)` sem alteração de parâmetros ou tipo de retorno.

6. THE `Vision_Engine` SHALL registrar telemetria para cada camada tentada, incluindo Template Matching, usando `_registrar_telemetria(camada, acertou, intencao_semantica)`.

7. IF Template Matching não encontrar correspondência com confiança suficiente, THEN THE `Vision_Engine` SHALL prosseguir para a próxima camada sem lançar exceção.

#### Propriedades de Corretude (PBT)

**P3.1 — Invariante de ordem:** Para qualquer execução da cascata que resulte em sucesso na Camada 2 (Coordenadas), as camadas 1_T (Template Matching) e 2_S (Sniper Semântico) devem ter sido tentadas antes, conforme registrado na telemetria.

**P3.2 — Telemetria completa:** Para qualquer execução da cascata, o número de registros em `telemetria_execucoes` deve ser igual ao número de camadas tentadas (incluindo a camada vencedora).

---

### Requisito 4: Consolidação da Telemetria no Brain

**User Story:** Como desenvolvedor de observabilidade, quero uma superfície unificada de consulta de telemetria, para que seja possível gerar relatórios de desempenho da cascata sem precisar fazer joins manuais entre tabelas.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL criar a view SQL `v_telemetria_unificada` no `brain.db` durante a inicialização, se ela não existir, unindo dados de `telemetria_camadas` e `telemetria_execucoes`.

2. THE `v_telemetria_unificada` SHALL expor no mínimo os campos: `camada`, `acertos_total`, `falhas_total`, `taxa_sucesso`, `ultima_execucao_ts`.

3. THE `Vision_Engine` SHALL expor uma função pública `obter_relatorio_telemetria() -> dict` que consulta `v_telemetria_unificada` e retorna um dicionário com a lista de camadas e suas métricas.

4. WHEN `brain.db` estiver vazio ou a view não contiver dados, THE `obter_relatorio_telemetria` SHALL retornar um dicionário com a chave `"camadas"` contendo uma lista vazia, sem lançar exceção.

5. THE criação da view `v_telemetria_unificada` SHALL ser idempotente: executar a inicialização múltiplas vezes no mesmo banco não deve causar erro nem duplicar dados.

6. THE `obter_relatorio_telemetria` SHALL incluir no retorno a chave `"taxa_hitl_1h"` com o valor calculado por `_calcular_taxa_hitl_1h()`, ou `null` se dados insuficientes.

7. IF a consulta à view falhar por qualquer motivo (banco corrompido, permissão, lock), THEN THE `obter_relatorio_telemetria` SHALL retornar `{"camadas": [], "erro": "<mensagem>"}` sem propagar a exceção.

#### Propriedades de Corretude (PBT)

**P4.1 — Idempotência da migração:** Executar a função de inicialização do banco (`_init_db()`) `N` vezes consecutivas no mesmo arquivo `brain.db` deve produzir o mesmo estado final que executar uma única vez, para qualquer `N >= 1`.

**P4.2 — Consistência da view:** Para qualquer estado do banco com `K` registros em `telemetria_execucoes`, a soma de `acertos_total + falhas_total` em `v_telemetria_unificada` deve ser igual a `K` (todos os registros granulares são contabilizados).

---

### Requisito 5: Testes Automatizados para Shadow_Builder

**User Story:** Como desenvolvedor, quero testes automatizados para o módulo `shadow_builder.py`, para que refatorações futuras sejam validadas sem precisar executar o Playwright ou chamar APIs externas.

#### Critérios de Aceitação

1. THE `tests/test_shadow_builder.py` SHALL conter testes para `inferir_acao_semantica()` cobrindo todos os valores do vocabulário controlado.

2. THE `tests/test_shadow_builder.py` SHALL conter testes para `inferir_entidade_negocio()` cobrindo os tipos de entidade: `pasta`, `documento`, `menu`, `campo`, `selecao`, `elemento`.

3. THE `tests/test_shadow_builder.py` SHALL conter testes para `classificar_ruido()` cobrindo os três critérios de ruído: breadcrumb/home, Enter sem valor, ícone sem label semântico.

4. THE `tests/test_shadow_builder.py` SHALL conter testes para `_montar_evento_shadow()` verificando que todos os campos obrigatórios do schema estão presentes no retorno.

5. THE `tests/test_shadow_builder.py` SHALL conter testes para `_salvar_shadow_jsonl()` verificando que o arquivo é criado em `shadow_exports/` e que cada linha é JSON válido.

6. THE testes do `test_shadow_builder.py` SHALL executar sem Playwright, Gemini, OpenAI ou Pinecone instalados ou configurados.

7. THE `tests/test_shadow_builder.py` SHALL conter testes de propriedade (usando `hypothesis`) para `inferir_acao_semantica()` verificando o invariante do vocabulário controlado.

#### Propriedades de Corretude (PBT)

**P5.1 — Vocabulário controlado (property test):** Para qualquer string gerada pelo Hypothesis para os parâmetros `(acao, label, seletor, tag, valor_input)`, `inferir_acao_semantica()` deve retornar um valor pertencente ao vocabulário controlado.

**P5.2 — Campos obrigatórios do Evento_Shadow:** Para qualquer combinação válida de parâmetros de `_montar_evento_shadow()`, o dicionário retornado deve conter as chaves: `id_acao`, `captured_at`, `acao`, `capture_scope`, `is_noise`, `intencao_semantica`, `semantic_action`, `business_entity`, `business_target`, `pattern_detectado`, `elemento_alvo`, `technical`.

**P5.3 — Ordenação do Shadow JSONL:** Para qualquer lista de eventos com `id_acao` em ordem arbitrária, `_salvar_shadow_jsonl()` deve persistir os eventos em ordem crescente de `id_acao` no arquivo de saída.

---

### Requisito 6: Testes Automatizados para Vision_Engine Brain

**User Story:** Como desenvolvedor, quero testes automatizados para o subsistema Brain do `vision_engine.py`, para que a lógica de memória semântica seja validada sem precisar de um browser Playwright.

#### Critérios de Aceitação

1. THE `tests/test_vision_engine_brain.py` SHALL conter testes para `_registrar_sucesso_cache()` verificando que `hits` é incrementado corretamente após múltiplos registros.

2. THE `tests/test_vision_engine_brain.py` SHALL conter testes para `_registrar_falha_cache()` verificando que `falhas_consecutivas` é incrementado e que a memória é apagada quando `falhas_consecutivas >= MAX_FALHAS_CACHE`.

3. THE `tests/test_vision_engine_brain.py` SHALL conter testes para `_consultar_cache()` verificando que retorna `None` para intenções não registradas e `EntradaCache` para intenções registradas.

4. THE `tests/test_vision_engine_brain.py` SHALL conter testes para `_registrar_telemetria()` verificando que os contadores em `telemetria_camadas` são atualizados corretamente.

5. THE `tests/test_vision_engine_brain.py` SHALL conter testes para `obter_relatorio_telemetria()` verificando que retorna a estrutura esperada com banco vazio e com dados.

6. THE testes do `test_vision_engine_brain.py` SHALL usar banco SQLite em memória (`:memory:`) ou arquivo temporário, nunca o `brain.db` de produção.

7. THE testes do `test_vision_engine_brain.py` SHALL executar sem Playwright, Gemini, OpenAI ou Pinecone instalados ou configurados.

#### Propriedades de Corretude (PBT)

**P6.1 — Monotonicidade de hits:** Para qualquer sequência de `N` chamadas a `_registrar_sucesso_cache()` com a mesma intenção, o valor de `hits` após a N-ésima chamada deve ser maior ou igual ao valor após a (N-1)-ésima chamada.

**P6.2 — Invariante de apagamento:** Para qualquer intenção com `falhas_consecutivas >= MAX_FALHAS_CACHE`, `_consultar_cache()` deve retornar `None` (memória obsoleta apagada).

**P6.3 — Idempotência de _init_db:** Chamar `_init_db()` com o mesmo banco `N` vezes deve resultar no mesmo schema (mesmas tabelas, mesmas colunas), sem erro, para qualquer `N >= 1`.

---

### Requisito 7: Testes Automatizados para Utils

**User Story:** Como desenvolvedor, quero testes automatizados para as funções utilitárias de `utils.py`, para que a sanitização de nomes, validação de roteiros e escrita segura de arquivos sejam verificadas de forma contínua.

#### Critérios de Aceitação

1. THE `tests/test_utils.py` SHALL conter testes para `limpar_nome()` verificando: remoção de acentos, remoção de caracteres proibidos (`/`, `\`, `*`, `?`, `:`, `"`, `<`, `>`, `|`), conversão de espaços em underscores, limite de 40 caracteres, e ausência de underscores nas extremidades.

2. THE `tests/test_utils.py` SHALL conter testes para `validar_roteiro()` cobrindo: roteiro com menos de 2 passos (reprovado), roteiro com menos de 50% de seletores preenchidos (reprovado), roteiro com mais de 70% de confiança baixa (reprovado), e roteiro válido (aprovado).

3. THE `tests/test_utils.py` SHALL conter testes para `safe_write_json()` verificando: arquivo criado com conteúdo correto, escrita atômica (arquivo temporário removido após sucesso), e comportamento em caso de diretório inexistente (criado automaticamente).

4. THE `tests/test_utils.py` SHALL conter testes para `safe_resolve_path()` verificando: caminho válido dentro do diretório base (aceito), e tentativa de path traversal com `../` (lança `ValueError`).

5. THE `tests/test_utils.py` SHALL conter testes para `com_retry()` verificando: sucesso na primeira tentativa, sucesso após falhas iniciais, e falha após esgotar todas as tentativas.

6. THE testes do `test_utils.py` SHALL executar sem dependências externas além da biblioteca padrão do Python e do `pytest`.

#### Propriedades de Corretude (PBT)

**P7.1 — ASCII puro:** Para qualquer string Unicode de entrada, `limpar_nome()` deve retornar uma string contendo apenas caracteres ASCII imprimíveis, underscores e sem caracteres proibidos de sistema de arquivos.

**P7.2 — Limite de comprimento:** Para qualquer string de entrada, `limpar_nome()` deve retornar uma string com no máximo 40 caracteres.

**P7.3 — Sem underscores nas extremidades:** Para qualquer string de entrada não-vazia, `limpar_nome()` não deve retornar string que comece ou termine com underscore.

**P7.4 — Idempotência de limpar_nome:** Para qualquer string de entrada, `limpar_nome(limpar_nome(s)) == limpar_nome(s)` (aplicar duas vezes é igual a aplicar uma vez).

**P7.5 — Determinismo de validar_roteiro:** Para o mesmo dicionário de roteiro, `validar_roteiro()` deve retornar sempre o mesmo par `(bool, str)`.

**P7.6 — Atomicidade de safe_write_json:** Após `safe_write_json(path, data)` completar sem exceção, o arquivo em `path` deve conter exatamente `data` serializado como JSON válido, sem arquivos temporários residuais no mesmo diretório.

---

### Requisito 8: Preservação de Contratos e Não-Regressão

**User Story:** Como responsável pelo pipeline de produção, quero garantir que todas as consolidações arquiteturais desta feature não quebrem nenhuma etapa do pipeline captura → roteiro → vídeo/SCORM/PDF, para que o sistema continue operacional durante e após a refatoração.

#### Critérios de Aceitação

1. THE `Roteiro` gerado pelo pipeline após as modificações SHALL conter os campos obrigatórios `metadata`, `configuracao_gravacao` e `passos`, e SHALL passar em `validar_roteiro()` sem alteração nos critérios de validação.

2. THE `Vision_Engine` SHALL preservar a assinatura pública `encontrar_e_clicar(page, passo, acao_tecnica, ...)` sem alteração de parâmetros, tipo de retorno ou semântica observável.

3. THE `Shadow_Builder` SHALL preservar as assinaturas públicas `_montar_evento_shadow(**kwargs) -> dict` e `_salvar_shadow_jsonl(nome_aula, objetivo_aula, eventos) -> str | None` sem alteração.

4. THE migrações de banco de dados no `brain.db` SHALL ser idempotentes: executar qualquer script de migração desta feature em um banco já migrado não deve causar erro nem alterar dados existentes.

5. WHEN qualquer módulo desta feature for importado em ambiente sem Playwright, Gemini, OpenAI ou Pinecone, THE módulo SHALL importar sem lançar `ImportError` ou `ModuleNotFoundError` para as funções puras.

6. THE `Capture_Dual_Output` SHALL continuar emitindo `SHADOW_GERADO:<caminho>` no stdout ao final de uma sessão de captura bem-sucedida, para compatibilidade com o painel de controle em `app.py`.

7. THE `Capture_Dual_Output` SHALL continuar emitindo `ROTEIRO_GERADO:<caminho>` no stdout ao final de uma sessão de captura bem-sucedida, para compatibilidade com o painel de controle em `app.py`.

#### Propriedades de Corretude (PBT)

**P8.1 — Contrato do roteiro:** Para qualquer roteiro gerado pelo pipeline modificado com `N >= 2` passos e pelo menos 50% de seletores preenchidos, `validar_roteiro(roteiro)` deve retornar `(True, motivo)`.

**P8.2 — Estabilidade de interface:** Para qualquer chamada a `_montar_evento_shadow()` com os mesmos parâmetros, o conjunto de chaves do dicionário retornado deve ser idêntico antes e depois da refatoração (sem chaves adicionadas ou removidas).

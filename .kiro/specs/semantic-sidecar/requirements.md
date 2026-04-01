# Documento de Requisitos

## Introdução

Esta especificação cobre a **Fase 2 — Integração do Sidecar Semântico** do Senior Training OS.

A Fase 1 (`legacy-stabilization`) centralizou `limpar_nome` e `validar_roteiro` em `utils.py`. A Fase 2 avança sobre essa base para consolidar a camada de inferência semântica e expô-la ao dashboard.

O contexto atual é:

- `capture_dual_output.py` gera dois outputs em paralelo: o roteiro legado (`cliques_capturados`) e um shadow JSONL semântico (`shadow_capturado`) gravado em `shadow_exports/`.
- As funções de inferência semântica (`_montar_evento_shadow`, `_infer_capture_scope`, `_infer_semantic_action_from_capture`, etc.) estão duplicadas entre `capture_dual_output.py` e `capture_hybrid_shadow.py`.
- O dashboard (`app.py`) não expõe o modo dual — não há rota `/api/gravar-dual` nem monitoramento de `SHADOW_GERADO:` no stdout.

Esta fase resolve três problemas em sequência:

1. Extrai as funções de inferência para um módulo puro `shadow_builder.py`.
2. Refatora `capture_dual_output.py` e `capture_hybrid_shadow.py` para importar de `shadow_builder.py`.
3. Adiciona a rota `/api/gravar-dual` em `app.py` com monitoramento de `SHADOW_GERADO:` via WebSocket.

**Restrições absolutas:**
- O schema do roteiro JSON não pode ser alterado.
- O fluxo legado (`capture.py` + `/api/gravar`) não pode ser afetado.
- `shadow_builder.py` não pode depender de Playwright.
- A rota `/api/gravar-dual` deve respeitar o lock de tarefa única do `app.py`.
- Compatibilidade com roteiros existentes em `roteiros_salvos/` deve ser preservada.

---

## Glossário

- **Sistema**: conjunto de módulos do Senior Training OS.
- **Shadow_Builder**: módulo `shadow_builder.py`, fonte canônica das funções de inferência e montagem semântica.
- **Capture_Dual**: módulo `capture_dual_output.py`, motor de captura com saída dupla (roteiro legado + shadow JSONL).
- **Capture_Hybrid**: módulo `capture_hybrid_shadow.py`, variante de captura com suporte a Shadow DOM e análise Gemini.
- **App_Module**: módulo `app.py`, entrypoint FastAPI e orquestrador de tarefas em background.
- **Shadow_JSONL**: arquivo `.jsonl` em `shadow_exports/` contendo os eventos semânticos capturados, um por linha.
- **Evento_Shadow**: objeto JSON que representa um evento capturado com campos semânticos enriquecidos (`semantic_action`, `business_entity`, `pattern_detectado`, etc.).
- **capture_scope**: campo do `Evento_Shadow` que indica se o evento ocorreu no shell ou em um módulo iframe (`"shell"` ou `"module_iframe"`).
- **semantic_action**: campo do `Evento_Shadow` que classifica a intenção do evento (`"fill"`, `"search"`, `"confirm"`, `"delete"`, `"save"`, `"open"`, `"navigate"`, `"select"`, `"close"`).
- **business_entity**: campo do `Evento_Shadow` que identifica a entidade de negócio envolvida (`"pasta"`, `"documento"`, `"cliente"`, `"pedido"`, `"menu"`, `"campo"`, `"elemento"`).
- **pattern_detectado**: campo do `Evento_Shadow` que classifica o padrão de interação (`"modal_action"`, `"toolbar_action"`, `"menu_navigation"`, `"form_fill"`, `"search_debounce"`, `"tree_item_open"`, `"table_selection"`, `"button_click"`, `"breadcrumb_navigation"`, `"unknown"`).
- **is_noise**: campo booleano do `Evento_Shadow` que indica se o evento provavelmente não deve virar passo de treinamento.
- **ROTEIRO_GERADO**: linha emitida no stdout pelo `Capture_Dual` no formato `ROTEIRO_GERADO:{caminho}`, já monitorada pelo `App_Module`.
- **SHADOW_GERADO**: linha emitida no stdout pelo `Capture_Dual` no formato `SHADOW_GERADO:{caminho}`, a ser monitorada pelo `App_Module`.
- **estado_servidor**: dicionário de estado global do `App_Module`, gerenciado exclusivamente via `_set_estado()`.
- **_iniciar_bg**: função do `App_Module` que verifica o lock de tarefa única antes de iniciar um processo em background.
- **Utils**: módulo `utils.py`, fonte canônica de `limpar_nome` e `validar_roteiro`.

---

## Requisitos

### Requisito 1: Criação do módulo `shadow_builder.py`

**User Story:** Como mantenedor do sistema, quero que as funções de inferência semântica existam em um único módulo puro, para que `capture_dual_output.py` e `capture_hybrid_shadow.py` compartilhem a mesma lógica sem duplicação.

#### Critérios de Aceitação

1. THE `Shadow_Builder` SHALL expor as seguintes funções extraídas de `capture_dual_output.py`: `utc_now`, `_infer_capture_scope`, `_infer_semantic_action_from_capture`, `_infer_business_entity_from_capture`, `_infer_pattern_from_capture`, `_is_noise_event`, `_montar_evento_shadow`, `_salvar_shadow_jsonl`.
2. THE `Shadow_Builder` SHALL ser importável sem dependência de Playwright, Google Gemini, OpenAI ou Pinecone.
3. THE `Shadow_Builder` SHALL importar `limpar_nome` de `utils.py` para uso em `_salvar_shadow_jsonl`.
4. WHEN `_salvar_shadow_jsonl` é chamada, THE `Shadow_Builder` SHALL criar o diretório `shadow_exports/` se ele não existir.
5. WHEN `_salvar_shadow_jsonl` é chamada com uma lista de eventos, THE `Shadow_Builder` SHALL ordenar os eventos por `id_acao` antes de gravar, garantindo ordem cronológica independente de race conditions.
6. WHEN `_salvar_shadow_jsonl` grava o arquivo com sucesso, THE `Shadow_Builder` SHALL emitir `print(f"SHADOW_GERADO:{caminho}", flush=True)` no stdout.
7. IF `_salvar_shadow_jsonl` falhar ao gravar o arquivo, THEN THE `Shadow_Builder` SHALL emitir `logger.warning` com o motivo da falha e retornar `None` sem propagar a exceção.
8. FOR ALL entradas válidas, THE `Shadow_Builder` SHALL produzir `Evento_Shadow` com estrutura idêntica à produzida pela implementação atual em `capture_dual_output.py`.
9. THE `Shadow_Builder` SHALL não conter lógica de captura de browser, injeção de JavaScript ou controle de Playwright.

---

### Requisito 2: Refatoração de `capture_dual_output.py` para importar de `shadow_builder.py`

**User Story:** Como mantenedor do sistema, quero que `capture_dual_output.py` use `shadow_builder.py` como fonte das funções de inferência, para que a lógica de montagem semântica não seja mantida em dois lugares.

#### Critérios de Aceitação

1. THE `Capture_Dual` SHALL importar `utc_now`, `_infer_capture_scope`, `_infer_semantic_action_from_capture`, `_infer_business_entity_from_capture`, `_infer_pattern_from_capture`, `_is_noise_event`, `_montar_evento_shadow`, `_salvar_shadow_jsonl` de `shadow_builder`.
2. THE `Capture_Dual` SHALL remover as definições locais das funções listadas no critério anterior após a importação.
3. WHEN `capture_dual_output.py` é executado como subprocess pelo `App_Module`, THE `Capture_Dual` SHALL emitir `ROTEIRO_GERADO:{caminho}` e `SHADOW_GERADO:{caminho}` no stdout com comportamento idêntico ao atual.
4. THE `Capture_Dual` SHALL preservar o comportamento externo completo: geração do roteiro legado em `roteiros_salvos/`, geração do shadow JSONL em `shadow_exports/`, e emissão das linhas de protocolo no stdout.
5. THE `Capture_Dual` SHALL preservar compatibilidade com roteiros existentes em `roteiros_salvos/`.

---

### Requisito 3: Avaliação e refatoração de `capture_hybrid_shadow.py` para reutilizar `shadow_builder.py`

**User Story:** Como mantenedor do sistema, quero que `capture_hybrid_shadow.py` reutilize as funções de `shadow_builder.py` onde a lógica for equivalente, para reduzir duplicação sem perder a qualidade das inferências específicas do modo híbrido.

#### Critérios de Aceitação

1. THE `Capture_Hybrid` SHALL importar `utc_now` de `shadow_builder` e remover sua definição local.
2. THE `Capture_Hybrid` SHALL avaliar se `infer_semantic_action_from_hints`, `infer_pattern_from_hints`, `is_noise_event` e `infer_business_entity_from_hints` podem ser substituídas pelas versões de `shadow_builder` sem perda de qualidade semântica.
3. WHERE a lógica de uma função do `Capture_Hybrid` for genuinamente diferente da versão em `Shadow_Builder` (por exemplo, suporte a `acao == "selecionar_opcao"`, `acao == "tecla"`, ou campos `aria_hint`/`title_hint` ausentes no modo dual), THE `Capture_Hybrid` SHALL manter sua implementação local específica.
4. WHERE a lógica de uma função do `Capture_Hybrid` for equivalente à versão em `Shadow_Builder`, THE `Capture_Hybrid` SHALL importar e usar a versão de `shadow_builder` em vez de manter uma cópia local.
5. THE `Capture_Hybrid` SHALL preservar o comportamento funcional completo de `capturar_hibrido` após qualquer refatoração.
6. THE `Capture_Hybrid` SHALL preservar a integração com Gemini em `analisar_semantica_hibrida` sem alteração.

---

### Requisito 4: Adição da rota `/api/gravar-dual` em `app.py`

**User Story:** Como operador do dashboard, quero iniciar uma captura no modo dual pelo painel, para que o shadow JSONL semântico seja gerado junto com o roteiro legado sem precisar executar o script manualmente.

#### Critérios de Aceitação

1. THE `App_Module` SHALL expor uma rota `POST /api/gravar-dual` que aceita o mesmo payload de `POST /api/gravar` (`nome_aula: str`, `objetivo: str`).
2. WHEN `/api/gravar-dual` é chamada e o sistema está ocupado, THE `App_Module` SHALL retornar HTTP 400 com `{"erro": "Sistema ocupado"}`, respeitando o lock de tarefa única via `_iniciar_bg`.
3. WHEN `/api/gravar-dual` é chamada e o sistema está livre, THE `App_Module` SHALL iniciar `capture_dual_output.py` como subprocess via `_iniciar_bg`, passando `nome_aula`, `objetivo` e `--auto` como argumentos.
4. WHILE o subprocess de `/api/gravar-dual` está em execução, THE `App_Module` SHALL monitorar o stdout para a linha `ROTEIRO_GERADO:{caminho}` com o mesmo comportamento já implementado para `/api/gravar`.
5. WHILE o subprocess de `/api/gravar-dual` está em execução, THE `App_Module` SHALL monitorar o stdout para a linha `SHADOW_GERADO:{caminho}`.
6. WHEN a linha `SHADOW_GERADO:{caminho}` é detectada no stdout, THE `App_Module` SHALL chamar `_set_estado(shadow_path=caminho)` para registrar o caminho no estado do servidor.
7. WHEN `_set_estado(shadow_path=caminho)` é chamado, THE `App_Module` SHALL propagar o campo `shadow_path` para todos os clientes conectados via WebSocket através do broadcast existente.
8. WHEN o subprocess de `/api/gravar-dual` conclui com sucesso, THE `App_Module` SHALL executar o auto-rebuild da biblioteca de ações com o mesmo comportamento do fluxo `/api/gravar`, usando o caminho extraído de `ROTEIRO_GERADO:`.
9. THE `App_Module` SHALL inicializar `estado_servidor` com o campo `shadow_path` definido como `None`.
10. WHEN uma nova tarefa é iniciada via `/api/gravar-dual` ou `/api/gravar`, THE `App_Module` SHALL redefinir `shadow_path` para `None` no início da execução via `_set_estado`.

---

### Requisito 5: Garantia de emissão de `SHADOW_GERADO:` pelo `capture_dual_output.py`

**User Story:** Como operador do sistema, quero ter certeza de que `capture_dual_output.py` sempre emite `SHADOW_GERADO:{caminho}` no stdout quando o shadow JSONL é salvo com sucesso, para que o dashboard possa capturar o caminho de forma confiável.

#### Critérios de Aceitação

1. WHEN `_salvar_shadow_jsonl` grava o arquivo com sucesso, THE `Capture_Dual` SHALL emitir exatamente uma linha no formato `SHADOW_GERADO:{caminho}` no stdout com `flush=True`.
2. THE `Capture_Dual` SHALL emitir `SHADOW_GERADO:{caminho}` após `ROTEIRO_GERADO:{caminho}` na sequência de stdout, nunca antes.
3. IF `_salvar_shadow_jsonl` falhar, THEN THE `Capture_Dual` SHALL não emitir `SHADOW_GERADO:` no stdout.
4. THE `Capture_Dual` SHALL preservar a emissão de `ROTEIRO_GERADO:{caminho}` sem alteração de formato ou timing.
5. FOR ALL execuções bem-sucedidas de `capture_dual_output.py`, THE `Capture_Dual` SHALL emitir ambas as linhas `ROTEIRO_GERADO:` e `SHADOW_GERADO:` no stdout antes de encerrar o processo.

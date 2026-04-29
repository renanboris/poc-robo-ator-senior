# Tasks de Implementação — Consolidação da Captura Cognitiva

## Visão Geral

6 grupos de tasks em ordem de dependência:
1. `shadow_builder.py` — funções unificadas (base de tudo)
2. `capture_hybrid_shadow.py` — remoção de duplicatas (depende do 1)
3. `vision_engine.py` — view SQL + relatório de telemetria (independente)
4. `vision_engine.py` — reordenação da cascata (depende do 3)
5. `capture_dual_output.py` — separação captura/enriquecimento (depende do 1)
6. `tests/` — testes automatizados (depende de 1, 3, utils)

---

## Tasks

- [x] 1. Adicionar funções unificadas ao `shadow_builder.py`
  - [x] 1.1 Adicionar `inferir_acao_semantica(acao, label, seletor, tag, valor_input="", hints=None) -> str` como wrapper público das funções privadas existentes, com suporte ao parâmetro `hints` para compatibilidade com o formato de payload do `capture_hybrid_shadow`
  - [x] 1.2 Adicionar `inferir_entidade_negocio(label, seletor, tag, contexto_tela="", hints=None) -> str` como wrapper público de `_infer_business_entity_from_capture()`
  - [x] 1.3 Adicionar `inferir_padrao_interacao(acao, label, seletor, tag, capture_scope, hints=None) -> str` como wrapper público de `_infer_pattern_from_capture()`
  - [x] 1.4 Adicionar `classificar_ruido(label, seletor, acao, tag, capture_scope, valor_input="", hints=None) -> bool` como wrapper público de `_is_noise_event()`
  - [x] 1.5 Atualizar o docstring do módulo para listar as 4 novas funções exportadas na seção "Funções exportadas"
  - [x] 1.6 Verificar que o módulo permanece puro: confirmar que nenhum import de `playwright`, `google.genai`, `openai`, `pinecone`, `asyncio` ou `subprocess` foi introduzido
  - [x] 1.7 Verificar que as funções privadas originais (`_infer_semantic_action_from_capture`, `_infer_business_entity_from_capture`, `_infer_pattern_from_capture`, `_is_noise_event`) permanecem intactas e funcionais

- [x] 2. Consolidar inferência semântica no `capture_hybrid_shadow.py`
  - [x] 2.1 Adicionar imports das 4 funções unificadas do `shadow_builder` no bloco de imports do arquivo: `inferir_acao_semantica`, `inferir_entidade_negocio`, `inferir_padrao_interacao`, `classificar_ruido`
  - [x] 2.2 Remover a função local `infer_semantic_action_from_hints(payload: dict) -> str` e substituir todos os seus call sites por `inferir_acao_semantica("", "", "", "", hints=payload)`
  - [x] 2.3 Remover a função local `infer_pattern_from_hints(payload: dict) -> str` e substituir todos os seus call sites por `inferir_padrao_interacao("", "", "", "", "", hints=payload)`
  - [x] 2.4 Remover a função local `is_noise_event(payload: dict) -> bool` e substituir todos os seus call sites por `classificar_ruido("", "", "", "", "", hints=payload)`
  - [x] 2.5 Remover a função local `infer_business_entity_from_hints(payload) -> str` e substituir todos os seus call sites por `inferir_entidade_negocio("", "", "", hints=payload)`
  - [x] 2.6 Verificar que o arquivo importa corretamente e que a lógica de captura híbrida continua funcionando (sem erros de importação ou chamadas quebradas)

- [x] 3. Adicionar view SQL e `obter_relatorio_telemetria()` ao `vision_engine.py`
  - [x] 3.1 Adicionar `CREATE VIEW IF NOT EXISTS v_telemetria_unificada` ao bloco `_init_db()`, dentro do `try/except` existente, com os campos: `camada`, `acertos_total`, `falhas_total`, `taxa_sucesso` (CASE WHEN), `ultima_execucao_ts`
  - [x] 3.2 Adicionar função pública `obter_relatorio_telemetria() -> dict` que consulta `v_telemetria_unificada` com `ORDER BY camada`, retorna `{"camadas": [...], "taxa_hitl_1h": float | None}` em caso de sucesso e `{"camadas": [], "erro": "<mensagem>"}` em caso de falha, sem propagar exceção
  - [x] 3.3 Verificar idempotência: executar `_init_db()` duas vezes no mesmo banco não deve causar erro (o `CREATE VIEW IF NOT EXISTS` garante isso)
  - [x] 3.4 Verificar que `obter_relatorio_telemetria()` retorna `{"camadas": [], "taxa_hitl_1h": None}` quando o banco está vazio

- [x] 4. Reordenar a cascata de estratégias no `vision_engine.py`
  - [x] 4.1 Ler o código atual da função `encontrar_e_clicar()` e identificar exatamente onde estão os blocos das camadas 2 (Coordenadas) e 2_S (Sniper Semântico) para planejar a movimentação cirúrgica
  - [x] 4.2 Integrar `template_match()` como Camada 1_T na cascata: adicionar o bloco de chamada após a Camada 1.5 (Heurísticas Senior X) e antes da geração de candidatos do Sniper, capturando o screenshot atual para o matching e registrando telemetria com `_registrar_telemetria("1_template_matching", acertou, intencao)`
  - [x] 4.3 Mover o bloco de Coordenadas Capturadas (camada 2) para depois do bloco do Sniper Semântico (camada 2_S), mantendo toda a lógica interna do bloco intacta
  - [x] 4.4 Adicionar comentário inline em cada camada da cascata descrevendo sua responsabilidade e condição de ativação (formato: `# ── Camada X: <nome> — <descrição> ──`)
  - [x] 4.5 Verificar que a assinatura pública `encontrar_e_clicar()` não foi alterada (mesmos parâmetros, mesmo tipo de retorno `bool`)
  - [x] 4.6 Verificar que a telemetria é registrada para a camada 1_T com `_registrar_telemetria("1_template_matching", ...)` tanto em caso de sucesso quanto de falha

- [x] 5. Separar captura e enriquecimento no `capture_dual_output.py`
  - [x] 5.1 Adicionar import de `inferir_acao_semantica` do `shadow_builder` no bloco de imports do arquivo
  - [x] 5.2 Modificar `on_capturar_elemento()` para remover a chamada a `_analisar_elemento_com_gemini()` do handler: o evento deve ser montado apenas com dados mecânicos (`label`, `coords`, `seletor_hint`, `iframe_hint`, `html_hint`, `screenshot_referencia`, `tipo_elemento`) e campos semânticos com valores padrão vazios (`intencao_semantica=""`, `descricao_visual=""`, `contexto_tela=""`, `confianca_captura="media"`)
  - [x] 5.3 Criar função `async def enriquecer_eventos_com_gemini(eventos_brutos: list[dict]) -> list[dict]` que itera sobre os eventos, chama `_analisar_elemento_com_gemini()` para cada um com screenshot disponível, usa fallback heurístico via `inferir_acao_semantica()` quando Gemini falha ou não está disponível, registra `logger.warning` com `id_acao` em caso de falha individual, e nunca lança exceção
  - [x] 5.4 Adicionar emissão de `CAPTURA_SEM_GEMINI:N` no stdout (com `flush=True`) dentro de `enriquecer_eventos_com_gemini()` quando `gemini_client` for `None` ou todos os eventos usarem fallback
  - [x] 5.5 Atualizar o fluxo de encerramento da sessão (após o loop `while not page.is_closed()`) para chamar `enriquecer_eventos_com_gemini(cliques_capturados)` antes de montar os eventos shadow e salvar o JSONL
  - [x] 5.6 Verificar que `SHADOW_GERADO:<caminho>` continua sendo emitido no stdout ao final da sessão (emitido por `_salvar_shadow_jsonl()` — não deve ser removido)
  - [x] 5.7 Verificar que `ROTEIRO_GERADO:<caminho>` continua sendo emitido no stdout ao final da sessão
  - [x] 5.8 Verificar que o Shadow JSONL gerado contém `Evento_Shadow` com a mesma estrutura de campos que a versão anterior (todos os campos obrigatórios presentes)

- [-] 6. Criar testes automatizados
  - [x] 6.1 Criar diretório `tests/` com arquivo `tests/__init__.py` vazio
  - [x] 6.2 Criar `tests/test_shadow_builder.py` com fixture `params_shadow_minimos`, testes unitários para `inferir_acao_semantica()` cobrindo todos os 9 valores do vocabulário controlado (`fill`, `search`, `confirm`, `delete`, `save`, `open`, `navigate`, `select`, `close`), testes para `inferir_entidade_negocio()` cobrindo `pasta`, `documento`, `menu`, `campo`, `selecao`, `elemento`, testes para `classificar_ruido()` cobrindo breadcrumb, Enter sem valor e ícone sem label, testes para `_montar_evento_shadow()` verificando as 12 chaves obrigatórias, e testes para `_salvar_shadow_jsonl()` verificando criação do arquivo, JSON válido por linha e ordenação por `id_acao`
  - [x] 6.3 Adicionar testes de propriedade (Hypothesis) ao `tests/test_shadow_builder.py`: `test_inferir_acao_semantica_vocabulario_controlado` com `@given(st.text())` para todos os parâmetros e `max_examples=200`, e `test_montar_evento_shadow_campos_obrigatorios_property` com `@given` para `id_acao`, `acao` e `label`
  - [x] 6.4 Criar `tests/test_vision_engine_brain.py` com fixture `brain_db` usando `tmp_path` e `monkeypatch` para isolar o banco SQLite de produção, testes unitários para `_consultar_cache()` (None para intenção nova, EntradaCache para registrada), `_registrar_sucesso_cache()` (hits incrementado), `_registrar_falha_cache()` (falhas incrementadas e memória apagada quando >= MAX_FALHAS_CACHE), `_registrar_telemetria()` (contadores atualizados), e `obter_relatorio_telemetria()` (estrutura correta com banco vazio e com dados, chave `taxa_hitl_1h` presente)
  - [x] 6.5 Adicionar testes de propriedade (Hypothesis) ao `tests/test_vision_engine_brain.py`: `test_init_db_idempotente` com `@given(st.integers(min_value=1, max_value=10))`, `test_registrar_sucesso_hits_monotonicos` com `@given(st.integers(min_value=1, max_value=20))`, e `test_memoria_obsoleta_apagada` com `@given(st.integers(min_value=0, max_value=5))`
  - [x] 6.6 Criar `tests/test_utils.py` com testes unitários para `limpar_nome()` (remoção de acentos, caracteres proibidos, espaços→underscore, limite 40 chars, sem underscore nas extremidades), `validar_roteiro()` (< 2 passos reprovado, < 50% seletores reprovado, > 70% baixa confiança reprovado, roteiro válido aprovado), `safe_write_json()` (arquivo criado com conteúdo correto, sem `.json.tmp` residual, diretório criado automaticamente), `safe_resolve_path()` (caminho válido aceito, `../` lança ValueError), e `com_retry()` (sucesso na 1ª tentativa, sucesso após falhas, esgota tentativas)
  - [ ] 6.7 Adicionar testes de propriedade (Hypothesis) ao `tests/test_utils.py`: `test_limpar_nome_ascii_puro_e_limite` com `@given(st.text(max_size=200))` e `max_examples=500`, `test_limpar_nome_idempotente` com `@given(st.text(max_size=200))` e `max_examples=300`, e `test_safe_write_json_atomico` com `@given(st.dictionaries(st.text(max_size=20), st.integers()))` e `max_examples=100`
  - [ ] 6.8 Executar todos os testes com `pytest tests/ -v` e confirmar que passam sem erros, sem dependências externas (Playwright, Gemini, OpenAI, Pinecone) e sem usar o `brain.db` de produção

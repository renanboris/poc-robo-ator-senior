# Plano de Implementação: Roadmap de Resiliência do Playback

## Visão Geral

Implementação incremental dos 6 eixos de resiliência do playback, priorizando as mudanças de maior impacto imediato. O Eixo 1 (reordenação da cascata + template matching) elimina 60–90% dos casos de HITL e deve ser implementado primeiro. Os demais eixos adicionam observabilidade, qualidade de captura, estabilidade de mídia e geração semântica.

Cada tarefa referencia os requisitos específicos que valida. Tarefas marcadas com `*` são opcionais (testes de propriedade Hypothesis) e podem ser puladas para um MVP mais rápido.

---

## Tarefas

### Eixo 1 — Resiliência do Playback

- [x] 1. Reordenar a cascata de seletores no `vision_engine.py`
  - Mover a tentativa de `coordenadas_relativas` para Layer 2, imediatamente após Brain_DB (Layer 0/0.5) e foco nativo (Layer 1)
  - Renumerar as camadas subsequentes: Sniper passa a ser `2_sniper`, Hint Original `3_hint_original`, Todos os Frames `4_todos_frames`, Gemini Vision `5_gemini_vision`
  - Preservar Layer 0 (Brain_DB seletor/coords), Layer 0.5 (menu de contexto) e Layer 1 (foco nativo para inputs) sem alteração de comportamento
  - Adicionar verificação `alvo.get("coordenadas_relativas")` antes de tentar Layer 2 — pular silenciosamente se ausente
  - Registrar `"2_coords_capturadas"` como estratégia vencedora na telemetria quando Layer 2 resolver
  - _Requisitos: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ]* 1.1 Teste de propriedade P1 — Ordem da cascata para ações com coordenadas
    - **Propriedade 1: Para qualquer ação com `coordenadas_relativas` preenchidas, `"2_coords_capturadas"` deve aparecer antes de `"2_sniper"`, `"3_"`, `"4_"` ou `"5_"` na sequência de telemetria**
    - **Valida: Requisitos 1.1, 1.5**
    - Arquivo: `tests/test_vision_engine_props.py`
    - Gerador: `st.fixed_dictionaries` para ação com `coordenadas_relativas` preenchidas

  - [ ]* 1.2 Teste de propriedade P2 — Ausência de coords pula Layer 2 silenciosamente
    - **Propriedade 2: Para qualquer ação sem `coordenadas_relativas`, a telemetria não deve conter nenhuma entrada para `"2_coords_capturadas"`**
    - **Valida: Requisito 1.6**
    - Arquivo: `tests/test_vision_engine_props.py`
    - Gerador: `st.fixed_dictionaries` para ação sem `coordenadas_relativas`

- [x] 2. Reduzir timeout do Sniper Semântico para 800ms
  - Localizar a chamada de `page.wait_for_selector` ou equivalente na camada Sniper em `vision_engine.py`
  - Alterar o timeout por candidato de 3500ms para 800ms
  - Preservar o número total de candidatos tentados — apenas o timeout por candidato muda
  - Adicionar log `DEBUG` com o tempo gasto em cada candidato Sniper para diagnóstico
  - Garantir que ao esgotar todos os candidatos dentro do timeout reduzido, a cascata escale normalmente para a próxima camada
  - _Requisitos: 2.1, 2.2, 2.3, 2.4, 2.5_

- [x] 3. Implementar o componente `Template_Matcher` em `vision_engine.py`
  - Criar função `template_match(referencia, tela_atual, coords_relativas, viewport, threshold=0.80)` usando exclusivamente Pillow e NumPy
  - Implementar algoritmo NCC (Normalized Cross-Correlation) via `np.lib.stride_tricks` para sliding window sem OpenCV
  - Implementar busca regional: se `coords_relativas` fornecido, recortar janela ±20% do viewport antes de buscar na tela inteira
  - Retornar `{"x": int, "y": int, "score": float}` quando `score >= threshold`, ou `None` caso contrário
  - Criar função auxiliar `_resolver_screenshot_ref(path)` para carregar bytes do arquivo de referência com tratamento de erro
  - _Requisitos: 3.1, 3.5, 3.6, 3.8, 3.9_

  - [ ]* 3.1 Teste de propriedade P3 — Self-match do Template Matcher
    - **Propriedade 3: Para qualquer screenshot de elemento com tamanho > 0 bytes, aplicar `template_match` com a própria imagem como referência e como tela deve retornar `score >= 0.95`**
    - **Valida: Requisito 3.9**
    - Arquivo: `tests/test_template_matcher_props.py`
    - Gerador: `st.binary(min_size=100)` → imagem JPEG sintética via Pillow

  - [ ]* 3.2 Teste de propriedade P4 — Template Matcher detecta elemento presente
    - **Propriedade 4: Para qualquer par (referência, tela_atual) onde o elemento está embutido visivelmente na tela, `template_match` deve retornar `score >= 0.80`**
    - **Valida: Requisito 3.8**
    - Arquivo: `tests/test_template_matcher_props.py`
    - Gerador: imagens sintéticas com elemento embutido em posição aleatória

- [x] 4. Integrar o `Template_Matcher` na cascata do `vision_engine.py` como Layer 1_T
  - Capturar screenshot atual da página uma única vez por execução de `encontrar_e_clicar` e reutilizá-la no Template_Matcher e no Gemini Vision
  - Inserir chamada ao `template_match` após Layer 1.5 (Heurísticas Senior X) e antes de Layer 2 (coordenadas)
  - Verificar presença de `screenshot_elemento` no roteiro antes de tentar a camada — pular silenciosamente se ausente ou `None`
  - Registrar `"1_template_matching"` como acerto na telemetria quando resolver, ou como falha quando `score < threshold`
  - Tratar exceções do cálculo NumPy com `logger.warning` e continuar para Layer 2 sem interromper a execução
  - _Requisitos: 3.2, 3.3, 3.4, 3.7_

- [x] 5. Checkpoint — Validar Eixo 1 completo
  - Garantir que todos os testes do Eixo 1 passam
  - Verificar nos logs que a ordem das camadas está correta para ações com e sem `coordenadas_relativas`
  - Verificar que o timeout do Sniper está em 800ms nos logs DEBUG
  - Perguntar ao usuário se há dúvidas antes de continuar.

---

### Eixo 2 — Qualidade da Captura

- [x] 6. Capturar `coordenadas_absolutas` e `coordenadas_relativas` em `capture.py`
  - Em `on_capturar_elemento`, após registrar o clique, calcular `x_pct = x / viewport_width` e `y_pct = y / viewport_height` usando as dimensões reais do viewport
  - Armazenar `coordenadas_absolutas: {"x": int, "y": int}` e `coordenadas_relativas: {"x_pct": float, "y_pct": float}` no campo `elemento_alvo` da ação técnica
  - Emitir `logger.warning` com o id da ação se `coordenadas_relativas` não puder ser calculado (viewport indisponível)
  - Preservar todos os campos existentes de `elemento_alvo` sem alteração — os novos campos são adicionais
  - _Requisitos: 6.1, 6.2, 6.3, 6.4, 6.5, 7.1, 7.2, 7.4_

  - [ ]* 6.1 Teste de propriedade P5 — Invariante de range de coordenadas relativas
    - **Propriedade 5: Para qualquer clique capturado com coordenadas absolutas dentro do viewport, `0.0 <= x_pct <= 1.0` e `0.0 <= y_pct <= 1.0`**
    - **Valida: Requisitos 6.2, 6.3**
    - Arquivo: `tests/test_capture_props.py`
    - Gerador: `st.integers` para x, y, viewport_width, viewport_height com restrição `x <= viewport_width`

- [x] 7. Capturar `screenshot_elemento` via `locator.screenshot()` em `capture.py`
  - Após capturar o screenshot de tela inteira, chamar `locator_elemento.screenshot(type="jpeg", quality=85)` para capturar o elemento alvo
  - Construir o `locator_elemento` a partir de `dados["seletor"]` via `page_ref.locator(dados["seletor"]).first`
  - Salvar o JPEG em `audios_gerados/{nome_aula}/screenshots/elemento_acao_{id_acao}.jpg` usando `os.makedirs(exist_ok=True)`
  - Armazenar o path relativo em `elemento_alvo.screenshot_elemento`; armazenar `None` em caso de falha com `logger.warning`
  - Preservar o campo `screenshot_referencia` (tela inteira) sem alteração — `screenshot_elemento` é campo adicional
  - _Requisitos: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

---

### Eixo 3 — Observabilidade do Executor

- [x] 8. Expandir o schema do `brain.db` com telemetria granular
  - Criar migração idempotente: `ALTER TABLE telemetria_camadas ADD COLUMN ultima_atualizacao_ts INTEGER` (epoch ms)
  - Criar tabela `telemetria_execucoes` com campos `id`, `camada`, `acertou`, `intencao_semantica`, `ts` (epoch ms)
  - Criar índices `idx_tel_exec_ts` e `idx_tel_exec_camada` para performance das consultas de métricas
  - Executar migração em `_init_db()` de forma idempotente (usar `IF NOT EXISTS` e `try/except` para `ALTER TABLE`)
  - _Requisitos: 5.1, 5.4, 10.4_

- [x] 9. Expandir a função `_registrar_telemetria` em `vision_engine.py`
  - Atualizar contadores agregados na tabela `telemetria_camadas` existente (sem breaking changes)
  - Inserir registro granular em `telemetria_execucoes` com `camada`, `acertou`, `intencao_semantica` e `ts` (epoch ms)
  - Tratar falha de escrita no `brain.db` com `logger.warning` silencioso — nunca interromper a execução
  - Usar `sqlite3.connect(timeout=5)` para lidar com SQLite lock
  - Registrar `"falha_total"` quando todas as camadas falharem
  - _Requisitos: 5.1, 5.2, 5.3, 9.1_

  - [ ]* 9.1 Teste de propriedade P6 — Invariante de contagem da telemetria (acertos)
    - **Propriedade 6: Para qualquer sequência de N execuções bem-sucedidas de `encontrar_e_clicar`, a soma de `acertos` em `telemetria_camadas` deve ser igual a N**
    - **Valida: Requisito 5.5**
    - Arquivo: `tests/test_telemetria_props.py`
    - Gerador: `st.integers(min_value=1, max_value=50)` para N

  - [ ]* 9.2 Teste de propriedade P7 — Invariante de contagem da telemetria (total)
    - **Propriedade 7: Para qualquer sequência de N execuções (com ou sem sucesso), `soma(acertos) + contador("falha_total")` deve ser igual a N**
    - **Valida: Requisito 5.6**
    - Arquivo: `tests/test_telemetria_props.py`
    - Gerador: `st.integers` para N com mix aleatório de sucesso/falha

  - [ ]* 9.3 Teste de propriedade P10 — Taxa de HITL dispara alerta
    - **Propriedade 10: Para qualquer janela de 1 hora com mais de 5 ações onde `taxa_hitl > 0.20`, deve haver pelo menos um registro de `WARNING` no log**
    - **Valida: Requisito 9.5**
    - Arquivo: `tests/test_telemetria_props.py`
    - Gerador: `st.integers` para sequências com taxa > 0.20

- [x] 10. Implementar cálculo de `taxa_hitl_1h` e alerta no `vision_engine.py`
  - Após cada registro de `"falha_total"`, consultar `telemetria_execucoes` para a janela deslizante de 1 hora
  - Calcular `taxa_hitl_1h = total_falhas_1h / total_acoes_1h` quando `total_acoes_1h > 5`
  - Emitir `logger.warning` com o valor da taxa e número de falhas quando `taxa_hitl > 0.20`
  - _Requisitos: 9.1, 9.2, 9.5_

- [x] 11. Expandir o endpoint `GET /api/metricas` em `app.py`
  - Adicionar campo `vision_layers`: lista de todas as 12 camadas com `camada`, `acertos`, `falhas`, `taxa_sucesso` das últimas 24h
  - Retornar `null` para campos de camadas sem dados nas últimas 24h (nunca zero ou omitir)
  - Adicionar campo `taxa_hitl_1h`: valor atual da taxa de HITL na última hora (ou `null` se dados insuficientes)
  - Adicionar campo `top_falhas`: top 10 ações com maior `falha_total` nas últimas 24h, com `intencao_semantica`, `total_falhas`, `ultima_falha_em`, `ultima_camada_tentada`
  - Retornar lista vazia para `top_falhas` quando não houver falhas (nunca `null`)
  - Adicionar campo `acoes_requer_revisao`: contagem de ações na `biblioteca_acoes.json` com `requer_revisao: true`
  - _Requisitos: 5.4, 8.1, 8.2, 8.3, 8.4, 9.3, 9.4, 10.1, 10.2, 10.3, 12.3_

- [x] 12. Checkpoint — Validar Eixos 2 e 3
  - Garantir que todos os testes dos Eixos 2 e 3 passam
  - Verificar que `GET /api/metricas` retorna `vision_layers`, `taxa_hitl_1h`, `top_falhas` e `acoes_requer_revisao`
  - Perguntar ao usuário se há dúvidas antes de continuar.

---

### Eixo 4 — Pipeline de Mídia

- [x] 13. Corrigir race condition no manifesto de áudio em `main.py`
  - Verificar que `_audio_manifest.clear()` no início de `executar_roteiro()` está protegido pelo `_audio_manifest_lock`
  - Garantir que `salvar_manifesto_audio()` é chamado **após** `await asyncio.gather(*tarefas_audio)` e não antes
  - Usar `return_exceptions=True` no `asyncio.gather` para capturar falhas individuais sem cancelar as demais tarefas
  - Registrar `logger.error` com o id do passo quando a geração de áudio de um passo falhar, continuando os demais
  - Preservar o comportamento de cache: se o áudio já existir em disco, não regenerar
  - _Requisitos: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [ ]* 13.1 Teste de propriedade P8 — Invariante de contagem do manifesto de áudio
    - **Propriedade 8: Para qualquer roteiro com N passos (N >= 1), após `asyncio.gather(*tarefas_audio)`, o manifesto deve conter exatamente N entradas sem duplicatas**
    - **Valida: Requisitos 11.1, 11.3**
    - Arquivo: `tests/test_audio_pipeline_props.py`
    - Gerador: `st.integers(min_value=1, max_value=30)` para N passos com mock de `gerar_audio`

---

### Eixo 5 — Geração Semântica

- [x] 14. Implementar seleção por score de confiabilidade em `generator_engine.py`
  - Modificar `_selecionar_acao_biblioteca` para filtrar ações com `requer_revisao: true` antes de selecionar
  - Ordenar candidatos válidos por `_score_confiabilidade` decrescente
  - Retornar `None` se o melhor candidato tiver `_score_confiabilidade < 0.5`
  - Registrar `logger.debug` quando uma ação for descartada por `requer_revisao: true`
  - _Requisitos: 12.1, 12.2, 12.4_

  - [ ]* 14.1 Teste de propriedade P9 — Score de confiabilidade das ações selecionadas
    - **Propriedade 9: Para qualquer ação selecionada pelo `Generator_Engine` da biblioteca, `0.5 <= _score_confiabilidade <= 1.0` e `requer_revisao == False`**
    - **Valida: Requisitos 12.1, 12.2, 12.4**
    - Arquivo: `tests/test_generator_props.py`
    - Gerador: `st.lists` de ações com scores aleatórios em [0.0, 1.0] e `requer_revisao` aleatório

---

### Eixo 6 — Integração e Checkpoint Final

- [x] 15. Verificar compatibilidade retroativa com roteiros existentes
  - Confirmar que roteiros sem `coordenadas_relativas` continuam funcionando (Layer 2 pulada silenciosamente)
  - Confirmar que roteiros sem `screenshot_elemento` continuam funcionando (Template_Matcher pulado silenciosamente)
  - Confirmar que `brain.db` existente não perde dados após a migração de schema
  - Confirmar que `biblioteca_acoes.json` sem `_score_confiabilidade` não quebra o `generator_engine.py` (usar `.get("_score_confiabilidade", 0.0)`)
  - _Requisitos: 1.6, 3.3, 4.6, 6.4_

- [x] 16. Checkpoint final — Garantir que todos os testes passam
  - Executar suite completa de testes: `pytest tests/ -v`
  - Garantir que todos os testes obrigatórios (sem `*`) passam sem erros
  - Verificar ausência de regressões nos módulos `capture.py`, `vision_engine.py`, `main.py`, `generator_engine.py` e `app.py`
  - Perguntar ao usuário se há dúvidas antes de encerrar.

---

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia requisitos específicos para rastreabilidade
- Os Eixos 1 e 2 têm dependência direta: o Template_Matcher (Eixo 1) depende do `screenshot_elemento` capturado (Eixo 2) — implementar Eixo 1 primeiro com dados de teste sintéticos, depois integrar com captura real
- A migração do `brain.db` (tarefa 8) deve ser executada antes das tarefas de telemetria (tarefa 9)
- Todos os novos campos no roteiro são opcionais e retrocompatíveis — roteiros existentes não são afetados
- Os bugs dos Eixo 6 (Requisitos 13, 14, 15) possuem specs dedicados e não são implementados aqui

# Documento de Requisitos

## Introdução

Este documento cobre o **Roadmap de Resiliência do Playback** do Senior Training OS — um conjunto de melhorias críticas identificadas a partir de análise diagnóstica profunda do comportamento do executor em produção.

A raiz do problema é arquitetural: o `vision_engine.py` tenta re-descobrir elementos em um DOM vivo e dinâmico (Angular com IDs gerados por sessão), percorrendo até 9 camadas de fallback durante 60–90 segundos antes de falhar. As coordenadas de clique — que o operador HITL usa com sucesso imediato — estão na **Layer 6**, quase no fim da cascata.

A análise diagnóstica identificou duas mudanças de impacto imediato:
1. **Reordenação da cascata**: mover coordenadas para Layer 2 e reduzir timeout do Sniper para 800ms — elimina 60%+ dos casos de HITL sem nenhuma mudança no capture.
2. **Template matching visual como Layer 1**: usar `locator.screenshot()` no capture e Pillow+NumPy no playback — resolve 90%+ dos casos em 200ms antes de qualquer tentativa DOM.

Os demais eixos cobrem qualidade de captura, observabilidade, pipeline de mídia, geração semântica e referências a bugs já especificados em outros specs.

**Specs existentes referenciados (não duplicados):**
- `training-os-roadmap` — roadmap de 26 tarefas em 3 fases
- `main-py-hardening` — paths absolutos, race condition em audio_manifest, invariante tempo_corte
- `vision-quality` — externalização de screenshots, validator contextual, portão de qualidade IA
- `semantic-sidecar` — shadow_builder.py, rota /api/gravar-dual
- `aura-dap-restructure` — reestruturação do Aura DAP
- `robot-execution-timeout-and-aura-indexing` — timeout do robot sem sinal de conclusão
- `positional-selector-wrong-item-deletion` — seletor posicional deletando item errado
- `context-menu-selector-priority` — ações de contexto-menu com prioridade incorreta
- `video-render-progress-bar` — barra de progresso de renderização de vídeo

---

## Glossário

- **Vision_Engine**: módulo `vision_engine.py`, responsável pela localização resiliente de elementos no browser durante o playback.
- **Capture_Module**: módulo `capture.py`, responsável pela captura de interações e geração do roteiro.
- **Executor**: módulo `main.py`, responsável por orquestrar o playback do roteiro.
- **Brain_DB**: banco SQLite `brain.db`, memória de seletores para self-healing de longo prazo.
- **Cascata**: sequência ordenada de estratégias de localização tentadas pelo Vision_Engine até encontrar o elemento ou falhar.
- **Layer**: camada numerada da Cascata. Camadas menores têm prioridade maior.
- **Sniper**: conjunto de candidatos de seletor DOM gerados a partir do `seletor_hint` e `label_curto`, tentados na Layer 2 da Cascata atual (Layer 3 após reordenação).
- **Template_Matcher**: componente novo que realiza matching visual entre o screenshot do elemento capturado e a tela atual usando Pillow e NumPy.
- **screenshot_elemento**: bytes JPEG do elemento alvo capturado via `locator.screenshot()` no momento do clique, armazenado no roteiro como path relativo em disco.
- **coordenadas_relativas**: dict com campos `x_pct` e `y_pct` representando a posição do clique como fração do viewport (valores em [0.0, 1.0]).
- **coordenadas_absolutas**: dict com campos `x` e `y` em pixels no viewport no momento da captura.
- **HITL**: Human-In-The-Loop — intervenção manual do operador quando o playback falha em localizar um elemento.
- **taxa_hitl**: proporção de ações que requerem intervenção HITL em relação ao total de ações executadas em uma janela de tempo.
- **telemetria_camadas**: tabela em `brain.db` que registra acertos e falhas por camada da Cascata.
- **score_matching**: valor float em [0.0, 1.0] que representa a similaridade visual entre o screenshot de referência e a região da tela atual.
- **threshold_matching**: valor mínimo de `score_matching` para considerar o elemento encontrado (padrão: 0.80).
- **Roteiro**: artefato JSON central que representa um fluxo de treinamento estruturado.
- **App_Module**: módulo `app.py`, entrypoint FastAPI e orquestrador de tarefas em background.
- **Audio_Pipeline**: conjunto de funções em `main.py` responsáveis pela geração e composição de áudio narrado.

---

## Requisitos

---

## Eixo 1 — Resiliência do Playback

### Requisito 1: Reordenação da Cascata de Seletores

**User Story:** Como operador do pipeline, quero que as coordenadas de clique capturadas sejam tentadas logo no início do playback, para que o executor não desperdice 60–90 segundos percorrendo camadas DOM antes de usar a informação que já sabe onde está.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL tentar as coordenadas relativas capturadas na **Layer 2** da Cascata, imediatamente após a consulta ao Brain_DB (Layer 1) e antes de qualquer tentativa de seletor DOM.
2. WHEN a Layer 2 de coordenadas for tentada e o clique for bem-sucedido, THE `Vision_Engine` SHALL registrar `"2_coords_capturadas"` como estratégia vencedora na telemetria e retornar `True` sem tentar camadas subsequentes.
3. THE `Vision_Engine` SHALL manter a Layer 0 (Brain_DB por seletor), Layer 0.5 (menu de contexto), e Layer 1 (foco nativo para inputs) em suas posições atuais, sem alteração de comportamento.
4. THE `Vision_Engine` SHALL renumerar as camadas subsequentes à inserção de coordenadas de forma que a ordem relativa entre Sniper, Hint Original, Todos os Frames e Gemini Vision seja preservada.
5. FOR ALL ações com `coordenadas_relativas` preenchidas no roteiro, THE `Vision_Engine` SHALL tentar a Layer 2 de coordenadas antes de gerar candidatos de seletor DOM.
6. FOR ALL ações sem `coordenadas_relativas` no roteiro, THE `Vision_Engine` SHALL pular a Layer 2 silenciosamente e continuar para a próxima camada sem erro.

---

### Requisito 2: Redução do Timeout do Sniper

**User Story:** Como operador do pipeline, quero que o Sniper Semântico abandone candidatos inválidos mais rapidamente, para que o tempo total de falha caia de 90 segundos para menos de 10 segundos.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL usar timeout máximo de **800ms** por candidato na camada Sniper Semântico.
2. WHEN um candidato Sniper não for encontrado dentro de 800ms, THE `Vision_Engine` SHALL descartar esse candidato e tentar o próximo sem aguardar.
3. THE `Vision_Engine` SHALL preservar o comportamento de tentativa de todos os candidatos gerados — a redução de timeout não deve reduzir o número de candidatos tentados.
4. IF todos os candidatos Sniper falharem dentro do timeout reduzido, THEN THE `Vision_Engine` SHALL escalar para a próxima camada da Cascata normalmente.
5. THE `Vision_Engine` SHALL registrar em log `DEBUG` o tempo gasto em cada candidato Sniper para diagnóstico.

---

### Requisito 3: Template Matching Visual como Layer 1 da Cascata

**User Story:** Como operador do pipeline, quero que o executor use o screenshot do elemento capturado para localizar visualmente o alvo na tela atual, para que ações com UI estável sejam resolvidas em menos de 200ms sem nenhuma tentativa DOM.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL implementar uma camada `Template_Matcher` que recebe o `screenshot_elemento` do roteiro e a screenshot atual da página e retorna as coordenadas do melhor match encontrado.
2. WHEN `screenshot_elemento` estiver presente no roteiro e o `score_matching` for maior ou igual ao `threshold_matching` (padrão 0.80), THE `Vision_Engine` SHALL usar as coordenadas retornadas pelo `Template_Matcher` para executar o clique e registrar `"1_template_matching"` como estratégia vencedora.
3. WHEN `screenshot_elemento` estiver ausente ou for `None`, THE `Vision_Engine` SHALL pular a camada de template matching silenciosamente e continuar para a Layer 2.
4. IF o `score_matching` for menor que o `threshold_matching`, THEN THE `Vision_Engine` SHALL registrar `"1_template_matching"` como falha na telemetria e continuar para a Layer 2.
5. THE `Template_Matcher` SHALL usar exclusivamente Pillow e NumPy para o cálculo de similaridade, sem introduzir novas dependências de biblioteca.
6. THE `Template_Matcher` SHALL realizar a busca na região da tela próxima às `coordenadas_relativas` capturadas (janela de ±20% do viewport) antes de buscar na tela inteira, para reduzir falsos positivos.
7. THE `Vision_Engine` SHALL capturar a screenshot atual da página apenas uma vez por execução de `encontrar_e_clicar` e reutilizá-la nas camadas que precisarem dela (Template_Matcher e Gemini Vision).
8. FOR ALL pares (screenshot_referencia, screenshot_atual) onde o elemento está presente e visível, THE `Template_Matcher` SHALL retornar `score_matching >= threshold_matching`.
9. FOR ALL screenshots de referência de um elemento aplicadas contra a própria imagem de origem (self-match), THE `Template_Matcher` SHALL retornar `score_matching >= 0.95`.

---

### Requisito 4: Captura de Screenshot do Elemento no Capture

**User Story:** Como operador do pipeline, quero que o capture salve um screenshot do elemento alvo no momento do clique, para que o playback tenha uma referência visual precisa do elemento independente de mudanças no DOM.

#### Critérios de Aceitação

1. WHEN `on_capturar_elemento` registra um clique, THE `Capture_Module` SHALL capturar o screenshot do elemento alvo via `locator.screenshot()` do Playwright e salvar em disco no formato JPEG.
2. THE `Capture_Module` SHALL salvar o `screenshot_elemento` no path `audios_gerados/{nome_aula}/screenshots/elemento_acao_{id_acao}.jpg`, distinto do `screenshot_referencia` de tela inteira já existente.
3. THE `Capture_Module` SHALL armazenar o path relativo do `screenshot_elemento` no campo `elemento_alvo.screenshot_elemento` da ação técnica no roteiro.
4. IF `locator.screenshot()` falhar (elemento não visível, timeout, etc.), THEN THE `Capture_Module` SHALL registrar `logger.warning` com o motivo e armazenar `None` no campo `screenshot_elemento`, sem interromper a captura.
5. THE `Capture_Module` SHALL preservar o campo `screenshot_referencia` (screenshot de tela inteira) sem alteração — o `screenshot_elemento` é um campo adicional, não substituto.
6. FOR ALL roteiros existentes sem o campo `screenshot_elemento`, THE `Vision_Engine` SHALL continuar funcionando normalmente, pulando a camada de template matching.

---

### Requisito 5: Telemetria de Camadas do Vision Engine

**User Story:** Como mantenedor do sistema, quero saber qual camada da cascata resolveu cada ação executada, para que eu possa identificar gargalos e otimizar a ordem das camadas com dados reais.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL registrar em `telemetria_camadas` (Brain_DB) o nome da camada, o resultado (acerto ou falha) e o timestamp para cada tentativa de localização.
2. WHEN uma ação é resolvida com sucesso, THE `Vision_Engine` SHALL registrar exatamente uma entrada de acerto para a camada vencedora e uma entrada de falha para cada camada tentada antes dela.
3. WHEN uma ação falha em todas as camadas, THE `Vision_Engine` SHALL registrar uma entrada de falha para cada camada tentada, incluindo `"falha_total"`.
4. THE `App_Module` SHALL expor as métricas de telemetria de camadas no endpoint `GET /api/metricas` sob o campo `vision_layers`, contendo para cada camada: `nome`, `acertos`, `falhas` e `taxa_sucesso` nas últimas 24 horas.
5. FOR ALL sequências de N ações executadas com sucesso, THE `Vision_Engine` SHALL garantir que a soma de `acertos` em `telemetria_camadas` seja igual a N.
6. FOR ALL sequências de N ações executadas (com ou sem sucesso), THE `Vision_Engine` SHALL garantir que a soma de `acertos` mais `falha_total` seja igual a N.

---

## Eixo 2 — Qualidade da Captura

### Requisito 6: Captura de Coordenadas Absolutas e Relativas

**User Story:** Como operador do pipeline, quero que o capture registre tanto as coordenadas absolutas quanto as relativas ao viewport no momento de cada clique, para que o playback tenha dados de posição precisos independente da resolução de tela.

#### Critérios de Aceitação

1. WHEN `on_capturar_elemento` registra um clique, THE `Capture_Module` SHALL calcular e armazenar `coordenadas_absolutas` (campos `x` e `y` em pixels) e `coordenadas_relativas` (campos `x_pct` e `y_pct` como fração do viewport) no campo `elemento_alvo` da ação técnica.
2. THE `Capture_Module` SHALL calcular `x_pct = x / viewport_width` e `y_pct = y / viewport_height` usando as dimensões reais do viewport no momento da captura.
3. FOR ALL cliques capturados, THE `Capture_Module` SHALL garantir que `0.0 <= x_pct <= 1.0` e `0.0 <= y_pct <= 1.0`.
4. FOR ALL roteiros existentes sem `coordenadas_relativas`, THE `Vision_Engine` SHALL continuar funcionando normalmente, pulando a Layer 2 de coordenadas.
5. THE `Capture_Module` SHALL preservar todos os campos existentes de `elemento_alvo` sem alteração — `coordenadas_absolutas` e `coordenadas_relativas` são campos adicionais.

---

### Requisito 7: Enriquecimento do Roteiro com Dados de Posição

**User Story:** Como operador do pipeline, quero que o roteiro gerado contenha dados de posição suficientes para o fallback visual, para que o playback possa usar coordenadas mesmo quando o DOM falha completamente.

#### Critérios de Aceitação

1. THE `Capture_Module` SHALL incluir `coordenadas_relativas` e `screenshot_elemento` em cada ação técnica do roteiro gerado, quando disponíveis.
2. WHEN o roteiro é salvo em `roteiros_salvos/`, THE `Capture_Module` SHALL garantir que ações com `acao` do tipo `clique`, `clique_duplo` ou `clique_direito` possuam `coordenadas_relativas` preenchidas.
3. THE `Vision_Engine` SHALL usar `coordenadas_relativas` do roteiro como entrada para a Layer 2 (coordenadas capturadas) e como janela de busca para o `Template_Matcher`.
4. IF `coordenadas_relativas` estiver ausente em uma ação de clique, THEN THE `Capture_Module` SHALL emitir `logger.warning` com o id da ação, sem interromper a captura.

---

## Eixo 3 — Observabilidade do Executor

### Requisito 8: Dashboard de Taxa de Sucesso por Camada

**User Story:** Como mantenedor do sistema, quero visualizar no dashboard a taxa de sucesso de cada camada do Vision Engine, para que eu possa identificar quais camadas estão contribuindo e quais estão desperdiçando tempo.

#### Critérios de Aceitação

1. THE `App_Module` SHALL expor no endpoint `GET /api/metricas` o campo `vision_layers` com a lista de camadas e suas métricas agregadas das últimas 24 horas.
2. WHEN não houver dados de telemetria para uma camada nas últimas 24 horas, THE `App_Module` SHALL retornar `null` para os campos dessa camada, nunca zero ou omitir a entrada.
3. THE `App_Module` SHALL incluir no campo `vision_layers` as seguintes camadas: `0_brain`, `0_brain_coords`, `0.5_menu_ctx`, `1_foco_nativo`, `1.5_heuristica_seniorx`, `1_template_matching`, `2_coords_capturadas`, `2_sniper`, `3_hint_original`, `4_todos_frames`, `5_gemini_vision`, `falha_total`.
4. THE `App_Module` SHALL calcular `taxa_sucesso` de cada camada como `acertos / (acertos + falhas)` para o período solicitado.

---

### Requisito 9: Alertas de Taxa de HITL

**User Story:** Como operador do pipeline, quero receber alertas quando a taxa de intervenção manual superar um threshold, para que eu possa identificar regressões no Vision Engine antes que afetem a produção.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL calcular a `taxa_hitl` como a proporção de ações com `"falha_total"` em relação ao total de ações executadas em uma janela deslizante de 1 hora.
2. WHEN a `taxa_hitl` superar **0.20** (20%) na janela de 1 hora, THE `Vision_Engine` SHALL emitir `logger.warning` com o valor atual da taxa e o número de falhas no período.
3. THE `App_Module` SHALL expor o campo `taxa_hitl_1h` no endpoint `GET /api/metricas` com o valor atual da taxa de HITL na última hora.
4. WHEN `taxa_hitl_1h` for `null` (sem dados suficientes), THE `App_Module` SHALL retornar `null` para esse campo, nunca zero.
5. FOR ALL janelas de 1 hora com mais de 5 ações executadas onde `taxa_hitl > 0.20`, THE `Vision_Engine` SHALL garantir que pelo menos um registro de `WARNING` foi emitido no log.

---

### Requisito 10: Relatório de Ações com Maior Taxa de Falha

**User Story:** Como mantenedor do sistema, quero saber quais ações específicas falham com mais frequência e por qual motivo, para que eu possa priorizar correções de seletores ou de captura.

#### Critérios de Aceitação

1. THE `App_Module` SHALL expor no endpoint `GET /api/metricas` o campo `top_falhas` com as 10 ações com maior número de `falha_total` nas últimas 24 horas.
2. WHEN `top_falhas` for calculado, THE `App_Module` SHALL incluir para cada entrada: `intencao_semantica`, `total_falhas`, `ultima_falha_em` e `ultima_camada_tentada`.
3. WHEN não houver falhas nas últimas 24 horas, THE `App_Module` SHALL retornar lista vazia para `top_falhas`, nunca `null`.
4. THE `Vision_Engine` SHALL registrar em `telemetria_camadas` o campo `intencao_semantica` junto com cada entrada de telemetria para permitir o agrupamento por ação.

---

## Eixo 4 — Pipeline de Mídia

### Requisito 11: Estabilidade do Pipeline de Áudio em Roteiros Longos

**User Story:** Como operador do pipeline, quero que a geração de áudio seja estável em roteiros com mais de 20 passos, para que o manifesto de áudio não fique corrompido ou incompleto em gravações longas.

#### Critérios de Aceitação

1. WHEN `gerar_audio()` é chamado concorrentemente para N passos via `asyncio.gather`, THE `Audio_Pipeline` SHALL garantir que o manifesto de áudio resultante contenha exatamente N entradas, sem duplicatas e sem entradas faltando.
2. THE `Audio_Pipeline` SHALL usar um mecanismo de sincronização (ex: `asyncio.Lock`) para proteger escritas concorrentes no manifesto de áudio.
3. FOR ALL roteiros com N >= 20 passos, THE `Audio_Pipeline` SHALL garantir que `len(manifesto_audio) == N` após a conclusão de `asyncio.gather(*tarefas_audio)`.
4. IF a geração de áudio de um passo falhar, THEN THE `Audio_Pipeline` SHALL registrar `logger.error` com o id do passo e continuar gerando os demais passos sem interromper o pipeline.
5. THE `Audio_Pipeline` SHALL preservar o comportamento de cache: se o áudio de um passo já existir em disco, não regenerar.

> **Nota:** A barra de progresso de renderização de vídeo está coberta pelo spec `video-render-progress-bar` (já com design e tasks). Este requisito cobre apenas a estabilidade do pipeline de áudio, que é um problema distinto.

---

## Eixo 5 — Aura DAP e Geração Semântica

### Requisito 12: Score de Confiabilidade na Seleção de Ações da Biblioteca

**User Story:** Como operador do pipeline, quero que o gerador de roteiros priorize ações da biblioteca com maior score de confiabilidade, para que roteiros gerados por IA reutilizem ações que funcionam bem no playback.

#### Critérios de Aceitação

1. WHEN o `Generator_Engine` busca ações na `biblioteca_acoes.json` para reutilização, THE `Generator_Engine` SHALL ordenar os candidatos por `_score_confiabilidade` decrescente antes de selecionar.
2. THE `Generator_Engine` SHALL ignorar ações com `requer_revisao: true` na seleção automática, registrando `logger.debug` quando uma ação for descartada por esse motivo.
3. THE `App_Module` SHALL expor no endpoint `GET /api/metricas` o campo `acoes_requer_revisao` com a contagem de ações na biblioteca com `requer_revisao: true`.
4. FOR ALL ações selecionadas da biblioteca pelo `Generator_Engine`, THE `Generator_Engine` SHALL garantir que `_score_confiabilidade >= 0.5`.

> **Nota:** A implementação do engine de score de confiabilidade está coberta pelo spec `training-os-roadmap` (Fase 3, tarefas 20–21). Este requisito cobre apenas a integração do score na seleção do gerador.

---

## Eixo 6 — Bugs Conhecidos (Referências)

Os bugs listados abaixo possuem specs dedicados com análise de condição de bug, design e plano de tarefas. Este roadmap os referencia para rastreabilidade, mas **não duplica** seus requisitos.

### Requisito 13: Referência — Timeout do Robot sem Sinal de Conclusão

**User Story:** Como operador do pipeline, quero que o robot sinalize conclusão de forma confiável, para que o executor não fique bloqueado indefinidamente aguardando um sinal que nunca chega.

#### Critérios de Aceitação

1. THE `Executor` SHALL implementar o mecanismo de timeout e sinalização de conclusão conforme especificado no spec `robot-execution-timeout-and-aura-indexing`.
2. WHEN o robot não emitir sinal de conclusão dentro do timeout configurado, THE `Executor` SHALL encerrar o processo, registrar `logger.error` e retornar estado de falha ao `App_Module`.

> **Referência completa:** `.kiro/specs/robot-execution-timeout-and-aura-indexing/bugfix.md`

---

### Requisito 14: Referência — Seletor Posicional Deletando Item Errado

**User Story:** Como operador do pipeline, quero que seletores posicionais sejam validados antes de executar ações destrutivas, para que o executor não delete ou modifique o item errado quando a lista muda entre sessões.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL implementar a validação de identidade de seletores posicionais conforme especificado no spec `positional-selector-wrong-item-deletion`.
2. WHEN um seletor posicional não confirmar a identidade do elemento esperado, THE `Vision_Engine` SHALL descartar o seletor e escalar para a próxima camada da Cascata.

> **Referência completa:** `.kiro/specs/positional-selector-wrong-item-deletion/bugfix.md`

---

### Requisito 15: Referência — Ações de Menu de Contexto com Prioridade Incorreta

**User Story:** Como operador do pipeline, quero que ações de menu de contexto usem a camada dedicada de detecção de overlay antes de tentar seletores DOM genéricos, para que itens de menu sejam encontrados de forma confiável.

#### Critérios de Aceitação

1. THE `Vision_Engine` SHALL implementar a priorização de seletores para menu de contexto conforme especificado no spec `context-menu-selector-priority`.
2. WHEN um menu de contexto estiver ativo na página, THE `Vision_Engine` SHALL usar a camada `0.5_menu_ctx` antes de qualquer tentativa de seletor DOM genérico.

> **Referência completa:** `.kiro/specs/context-menu-selector-priority/bugfix.md`

---

## Propriedades de Corretude

As propriedades abaixo são candidatas a testes baseados em propriedades (Hypothesis) para validar invariantes críticos dos requisitos acima.

### Propriedade 1: Ordem da Cascata (Requisito 1)

Para qualquer ação com `coordenadas_relativas` preenchidas, a camada `"2_coords_capturadas"` deve ser tentada antes de qualquer camada com prefixo `"2_sniper"`, `"3_"`, `"4_"` ou `"5_"` na sequência de registros de telemetria.

```
PARA TODO roteiro R com ação A onde A.elemento_alvo.coordenadas_relativas != None:
  sequencia_camadas = [t.camada for t in telemetria(A)]
  idx_coords = sequencia_camadas.index("2_coords_capturadas")
  idx_sniper = sequencia_camadas.index("2_sniper") se existir
  ASSERT idx_coords < idx_sniper (quando ambos presentes)
```

### Propriedade 2: Invariante de Range de Coordenadas (Requisito 6)

Para qualquer clique capturado pelo Capture_Module, as coordenadas relativas devem estar no intervalo válido.

```
PARA TODO clique C capturado:
  ASSERT 0.0 <= C.elemento_alvo.coordenadas_relativas.x_pct <= 1.0
  ASSERT 0.0 <= C.elemento_alvo.coordenadas_relativas.y_pct <= 1.0
```

### Propriedade 3: Self-Match do Template Matcher (Requisito 3)

Para qualquer screenshot de elemento aplicado contra si mesmo, o score deve ser >= 0.95.

```
PARA TODO screenshot_bytes S de tamanho > 0:
  score = template_matcher.match(referencia=S, tela=S)
  ASSERT score >= 0.95
```

### Propriedade 4: Invariante de Contagem da Telemetria (Requisito 5)

Para qualquer sequência de N ações executadas, a soma de acertos mais falhas totais deve ser igual a N.

```
PARA TODO conjunto de N execuções de encontrar_e_clicar:
  total_acertos = sum(t.acertos for t in telemetria_camadas)
  total_falhas_totais = telemetria_camadas["falha_total"].falhas
  ASSERT total_acertos + total_falhas_totais == N
```

### Propriedade 5: Invariante de Contagem do Manifesto de Áudio (Requisito 11)

Para qualquer roteiro com N passos, o manifesto de áudio deve conter exatamente N entradas após geração completa.

```
PARA TODO roteiro R com N passos (N >= 1):
  manifesto = await gerar_todos_audios(R)
  ASSERT len(manifesto) == N
  ASSERT len(set(manifesto.keys())) == N  // sem duplicatas
```

### Propriedade 6: Score de Confiabilidade das Ações Selecionadas (Requisito 12)

Para qualquer ação selecionada da biblioteca pelo Generator_Engine, o score deve estar no intervalo válido e acima do threshold.

```
PARA TODO acao A selecionada pelo Generator_Engine da biblioteca:
  ASSERT 0.0 <= A._score_confiabilidade <= 1.0
  ASSERT A._score_confiabilidade >= 0.5
  ASSERT A.requer_revisao == False
```

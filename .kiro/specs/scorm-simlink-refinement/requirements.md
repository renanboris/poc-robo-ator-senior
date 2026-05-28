# Requirements Document

## Introduction

Este documento especifica os refinamentos do gerador SCORM (`scorm_builder.py`) e do gerador SimLink (`scripts/sim_link_builder.py`). Os problemas identificados são:

1. **Ancora com screenshot errada** — a ancora do passo N usa a primeira `screenshot_referencia` do passo N-1, ignorando que o passo anterior pode ter multiplas acoes. O estado visual correto e o da ultima acao concluida do passo anterior, representado por `screenshot_depois`.
2. **Leitura incorreta de `_vp_w`/`_vp_h`** — no roteiro gerado por `capture_dual_output.py`, os campos `_vp_w` e `_vp_h` ficam no nivel da acao tecnica (fora de `elemento_alvo`). O `scorm_builder` le esses campos de `alvo.get("_vp_w")`, que sempre retorna o valor padrao 1920x1080, ignorando o viewport real da gravacao.
3. **`sim_link_builder` nao usa SoM** — o SimLink usa apenas `coordenadas_relativas` para posicionar a zona interativa, ignorando `som_box_clicada` + `_vp_w`/`_vp_h`, que fornecem coordenadas absolutas mais precisas.
4. **Inconsistencia entre os dois builders** — `scorm_builder` e `sim_link_builder` usam estrategias diferentes para ancora e coordenadas, produzindo artefatos visualmente divergentes a partir do mesmo roteiro.
5. **Espera fixa de 1,2 s para `screenshot_depois`** — `capture_semantic.py` usa `asyncio.sleep(1.2)` antes de capturar o estado pos-clique, o que pode capturar telas em estado de carregamento em ERPs lentos.

As mudancas devem preservar o contrato do roteiro JSON e nao quebrar os pipelines de video, PDF e DAP.

---

## Glossary

- **Roteiro**: artefato JSON central do sistema, contendo `metadata`, `configuracao_gravacao` e `passos`.
- **Passo**: unidade pedagogica do roteiro, contendo `pedagogia` (com `ancora`) e `acoes_tecnicas`.
- **Acao Tecnica**: acao individual dentro de um passo, contendo `elemento_alvo`, `acao`, `valor_input`, `micro_narracao`, `_vp_w` e `_vp_h`.
- **Elemento_Alvo**: sub-objeto da acao tecnica com `coordenadas_relativas`, `screenshot_referencia`, `screenshot_depois`, `som_box_clicada`, `som_idx_clicado`, `_vp_w` e `_vp_h`.
- **SoM (Set of Marks)**: conjunto de bounding boxes de elementos interativos detectados no DOM no momento da captura, armazenado em `som_box_clicada` com campos `x`, `y`, `w`, `h` em pixels absolutos.
- **Ancora**: slide de contexto exibido antes de um passo interativo, com imagem de fundo que mostra o estado da tela no inicio daquele passo.
- **SCORM_Builder**: modulo `scorm_builder.py` que gera pacotes SCORM 1.2 a partir do roteiro.
- **SimLink_Builder**: modulo `scripts/sim_link_builder.py` que gera HTML standalone a partir do roteiro.
- **screenshot_referencia**: screenshot capturado no momento do `mousedown` (estado pre-clique).
- **screenshot_depois**: screenshot capturado apos o clique, representando o estado pos-navegacao.
- **coordenadas_relativas**: objeto `{x_pct, y_pct, w_pct, h_pct}` com valores percentuais relativos ao viewport.
- **Viewport**: dimensoes da janela do navegador no momento da captura, armazenadas em `_vp_w` e `_vp_h`.

---

## Requirements

### Requirement 1: Selecao Correta da Imagem de Ancora

**User Story:** Como instrutor, quero que o slide de ancora de cada passo mostre o estado real da tela no inicio daquele passo, para que o aprendiz veja exatamente o que vera ao comecar a interacao.

#### Acceptance Criteria

1. QUANDO o SCORM_Builder processar um passo com indice N > 0, O SCORM_Builder SHALL selecionar como imagem de ancora a `screenshot_depois` da ultima acao tecnica (ultima por posicao na lista `acoes_tecnicas`) do passo N-1 cujo campo `screenshot_depois` seja uma string nao nula e nao vazia.
2. IF nenhuma acao tecnica do passo N-1 possuir `screenshot_depois` como string nao nula e nao vazia, THEN O SCORM_Builder SHALL usar a `screenshot_referencia` da ultima acao tecnica do passo N-1 cujo campo `screenshot_referencia` seja uma string nao nula e nao vazia.
3. IF nenhuma acao tecnica do passo N-1 possuir `screenshot_referencia` nem `screenshot_depois` como string nao nula e nao vazia, THEN O SCORM_Builder SHALL definir a imagem de ancora como `None`, sem lancar excecao.
4. QUANDO o SCORM_Builder processar o passo com indice N = 0, O SCORM_Builder SHALL definir a imagem de ancora como `None`, sem lancar excecao.
5. QUANDO o SimLink_Builder processar um passo com indice N > 0, O SimLink_Builder SHALL selecionar a imagem de ancora aplicando a mesma logica dos criterios 1, 2 e 3: priorizar `screenshot_depois` da ultima acao tecnica do passo N-1 com valor nao nulo e nao vazio, com fallback para `screenshot_referencia`, e `None` se nenhum estiver disponivel.
6. QUANDO o SimLink_Builder processar o passo com indice N = 0, O SimLink_Builder SHALL definir a imagem de ancora como `None`, sem lancar excecao.
7. THE SCORM_Builder e o SimLink_Builder SHALL produzir, para cada passo do mesmo roteiro de entrada, o mesmo valor de `imagem_b64` no slide de ancora correspondente.

---

### Requirement 2: Leitura Correta de _vp_w e _vp_h

**User Story:** Como desenvolvedor, quero que os builders leiam o viewport real da gravacao para calcular coordenadas percentuais precisas, para que a zona interativa seja posicionada corretamente independentemente da resolucao usada na captura.

#### Acceptance Criteria

1. QUANDO o SCORM_Builder calcular coordenadas percentuais a partir de `som_box_clicada`, O SCORM_Builder SHALL ler `_vp_w` e `_vp_h` do nivel da acao tecnica (campo irmao de `elemento_alvo`), nao do interior de `elemento_alvo`.
2. QUANDO o SimLink_Builder calcular coordenadas percentuais a partir de `som_box_clicada`, O SimLink_Builder SHALL ler `_vp_w` e `_vp_h` do nivel da acao tecnica.
3. IF `_vp_w` ou `_vp_h` forem ausentes ou iguais a zero no nivel da acao tecnica, THEN os builders SHALL verificar os mesmos campos dentro de `elemento_alvo` como fallback secundario.
4. IF `_vp_w` e `_vp_h` nao forem encontrados em nenhum dos dois niveis, ou forem zero ou negativos em ambos os niveis, THEN os builders SHALL usar os valores padrao 1920 e 1080 respectivamente.
5. QUANDO o SCORM_Builder calcular `x_pct` e `y_pct` a partir de um `som_box_clicada` valido (campos numericos com valores >= 0) e viewport positivo, O SCORM_Builder SHALL produzir valores dentro do intervalo [0.0, 1.0], aplicando clamping se as coordenadas absolutas excederem os limites do viewport.

---

### Requirement 3: Uso de SoM no SimLink_Builder

**User Story:** Como instrutor, quero que o SimLink use as coordenadas SoM quando disponiveis, para que a zona interativa seja posicionada com a mesma precisao geometrica que o SCORM.

#### Acceptance Criteria

1. QUANDO o SimLink_Builder processar uma acao tecnica cujo `elemento_alvo` contenha `som_box_clicada` com campos numericos `x`, `y`, `w > 0`, `h > 0` e `_vp_w > 0`/`_vp_h > 0` positivos, O SimLink_Builder SHALL calcular as coordenadas usando a formula: `x_pct = x / _vp_w`, `y_pct = y / _vp_h`, `w_pct = w / _vp_w`, `h_pct = h / _vp_h`.
2. IF `som_box_clicada` for `None`, ausente, contiver campos nao numericos, tiver `w <= 0` ou `h <= 0`, ou o viewport for `_vp_w <= 0` ou `_vp_h <= 0`, THEN O SimLink_Builder SHALL usar `coordenadas_relativas` como fonte de coordenadas.
3. IF `coordenadas_relativas` tambem for ausente ou vazia, THEN O SimLink_Builder SHALL usar os valores padrao `x_pct=0.5`, `y_pct=0.5`, `w_pct=0.05`, `h_pct=0.05`.
4. IF o calculo via `som_box_clicada` produzir valores fora do intervalo [0.0, 1.0], THEN O SimLink_Builder SHALL aplicar clamping para manter os valores dentro desse intervalo, sem lancar excecao.
5. THE SCORM_Builder e o SimLink_Builder SHALL produzir, para a mesma acao tecnica com `som_box_clicada` valido, valores de `x_pct` e `y_pct` com diferenca absoluta menor que 0.0001.

---

### Requirement 4: Consistencia de Artefatos entre os Dois Builders

**User Story:** Como desenvolvedor, quero que SCORM e SimLink produzam a mesma sequencia visual e as mesmas coordenadas interativas a partir do mesmo roteiro, para que o comportamento do aprendiz seja equivalente nos dois formatos.

#### Acceptance Criteria

1. QUANDO o SCORM_Builder e o SimLink_Builder processarem o mesmo roteiro de entrada, OS dois builders SHALL produzir o mesmo valor de `imagem_b64` para o slide de ancora de cada passo.
2. QUANDO o SCORM_Builder e o SimLink_Builder processarem o mesmo roteiro de entrada, OS dois builders SHALL produzir os mesmos valores de `x_pct`, `y_pct`, `w_pct` e `h_pct` para o slide de interacao de cada acao tecnica.
3. QUANDO ambos os builders processarem o mesmo roteiro, O numero de slides de ancora gerados SHALL ser igual entre os dois artefatos, contando apenas os passos cujo campo `ancora` seja uma string nao vazia.
4. QUANDO ambos os builders processarem o mesmo roteiro, O numero de slides de interacao gerados SHALL ser igual entre os dois artefatos, excluindo acoes tecnicas com `acao == "concluir_video"`.

---

### Requirement 5: Espera Observavel Apos Clique na Captura

**User Story:** Como instrutor, quero que o `screenshot_depois` capture o estado estabilizado da tela apos a navegacao, para que a ancora do proximo passo mostre a tela correta mesmo em ERPs com carregamento lento.

#### Acceptance Criteria

1. QUANDO o Capturador Semantico (`capture_semantic.py`) capturar o `screenshot_depois` apos um clique, O Capturador SHALL aguardar o evento `networkidle` da pagina antes de tirar o screenshot, com timeout maximo de 3 segundos.
2. IF o evento `networkidle` nao ocorrer dentro de 3 segundos, THEN O Capturador SHALL tirar o screenshot no estado renderizado naquele momento, sem aguardar condicao adicional e sem lancar excecao.
3. IF a pagina estiver fechada ou inacessivel no momento da captura do `screenshot_depois`, THEN O Capturador SHALL registrar o campo `screenshot_depois` como string vazia e prosseguir para o proximo passo da sequencia de captura sem lancar excecao.
4. IF a captura do `screenshot_depois` for concluida (com ou sem o evento `networkidle`), THEN O Capturador SHALL gravar o resultado no campo `screenshot_depois` dentro de `elemento_alvo` da acao tecnica correspondente.

---

### Requirement 6: Robustez com Roteiros sem Screenshots

**User Story:** Como desenvolvedor, quero que os builders funcionem corretamente com roteiros gerados por IA (sem captura real), para que o fluxo de geracao de SCORM e SimLink nao quebre quando `screenshot_referencia` e `screenshot_depois` estiverem ausentes.

#### Acceptance Criteria

1. QUANDO o SCORM_Builder processar um roteiro cujas acoes tecnicas nao possuam `screenshot_referencia` nem `screenshot_depois`, O SCORM_Builder SHALL gerar o pacote SCORM sem lancar excecao, usando um retangulo solido branco com as dimensoes do slide como imagem de fundo para os slides afetados.
2. QUANDO o SimLink_Builder processar um roteiro cujas acoes tecnicas nao possuam `screenshot_referencia` nem `screenshot_depois`, O SimLink_Builder SHALL gerar o arquivo HTML sem lancar excecao, usando um retangulo solido branco com as dimensoes do slide como imagem de fundo para os slides afetados.
3. QUANDO o SCORM_Builder ou o SimLink_Builder processarem um roteiro sem `som_box_clicada` e sem `coordenadas_relativas`, OS builders SHALL usar os valores padrao `x_pct=0.5`, `y_pct=0.5`, `w_pct=0.05`, `h_pct=0.05` para posicionar a zona interativa.
4. THE SCORM_Builder e o SimLink_Builder SHALL aceitar `None`, string vazia ou campo ausente como valor valido para `screenshot_referencia`, `screenshot_depois` e `som_box_clicada`, sem interromper a geracao do artefato de saida.

# Implementation Plan: scorm-simlink-refinement

## Overview

Quatro mudanças cirúrgicas em três módulos Python para corrigir seleção de âncora, leitura de viewport, uso de SoM no SimLink e espera observável no capturador. Nenhum contrato do roteiro JSON é alterado; os pipelines de vídeo, PDF e DAP não são afetados.

## Tasks

- [x] 1. Adicionar funções auxiliares compartilhadas em `scorm_builder.py`
  - Implementar `_selecionar_imagem_ancora(passos, idx)` com prioridade `screenshot_depois` → `screenshot_referencia` → `None`
  - Implementar `_ler_viewport(acao)` com fallback em dois níveis (ação → `elemento_alvo` → 1920×1080)
  - Implementar `_som_box_valido(som_box)` com validação de campos numéricos e dimensões positivas
  - Implementar `_calcular_coords_som(som_box, vp_w, vp_h)` com clamping para `[0.0, 1.0]`
  - Implementar `_resolver_coords(acao)` com prioridade SoM → `coordenadas_relativas` → padrão 0.5/0.05
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.3, 2.4, 2.5, 3.4, 6.3, 6.4_

  - [x] 1.1 Implementar `_selecionar_imagem_ancora` em `scorm_builder.py`
    - Percorrer `acoes_tecnicas` do passo anterior de trás para frente
    - Retornar `None` diretamente para `idx == 0`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 1.2 Implementar `_ler_viewport`, `_som_box_valido`, `_calcular_coords_som` e `_resolver_coords` em `scorm_builder.py`
    - Garantir que `_ler_viewport` lê do nível da ação antes de `elemento_alvo`
    - Garantir clamping em `_calcular_coords_som`
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 3.4, 6.3, 6.4_

  - [ ]* 1.3 Escrever testes de unidade para as funções auxiliares de `scorm_builder.py`
    - Verificar que `_selecionar_imagem_ancora` retorna `None` para `idx=0`
    - Verificar que `_ler_viewport` retorna 1920×1080 quando ambos os níveis estão ausentes
    - Verificar que `_som_box_valido` rejeita dicts com campos não-numéricos e `w <= 0`
    - Verificar que `_calcular_coords_som` aplica clamping para valores extremos
    - _Requirements: 1.3, 1.4, 2.4, 2.5_

- [x] 2. Integrar funções auxiliares na lógica de geração de slides do `scorm_builder.py`
  - Substituir a lógica atual de seleção de âncora pela chamada a `_selecionar_imagem_ancora`
  - Substituir a leitura direta de `alvo.get("_vp_w")` pela chamada a `_ler_viewport`
  - Substituir o cálculo de coordenadas pela chamada a `_resolver_coords`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.3, 2.4, 2.5, 6.1, 6.4_

  - [x] 2.1 Substituir lógica de âncora em `scorm_builder.py`
    - Localizar o ponto onde `pedagogia.ancora` é resolvido para `imagem_b64`
    - Substituir pela chamada a `_selecionar_imagem_ancora(passos, idx)`
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [x] 2.2 Substituir leitura de viewport e cálculo de coordenadas em `scorm_builder.py`
    - Substituir `alvo.get("_vp_w")` / `alvo.get("_vp_h")` por `_ler_viewport(acao)`
    - Substituir cálculo inline de `x_pct`/`y_pct` por `_resolver_coords(acao)`
    - _Requirements: 2.1, 2.3, 2.4, 2.5_

  - [x]* 2.3 Escrever teste de propriedade P2 — leitura de viewport no nível correto
    - **Property 2: Viewport reading at action level**
    - Usar `@given(acao=st_acao_com_viewport_apenas_no_nivel_acao())`
    - Verificar que `_ler_viewport(acao)` retorna os valores do nível da ação, não 1920×1080
    - **Validates: Requirements 2.1, 2.2**

  - [x]* 2.4 Escrever teste de propriedade P3 — invariante de clamping de coordenadas
    - **Property 3: Coordinate clamping invariant**
    - Usar `@given(som_box=st_som_box_qualquer(), vp=st_viewport_positivo())`
    - Verificar que todos os valores retornados por `_calcular_coords_som` estão em `[0.0, 1.0]`
    - **Validates: Requirements 2.5, 3.4**

- [x] 3. Checkpoint — verificar `scorm_builder.py`
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 4. Adicionar funções auxiliares em `scripts/sim_link_builder.py`
  - Duplicar `_selecionar_imagem_ancora`, `_ler_viewport`, `_som_box_valido`, `_calcular_coords_som` e `_resolver_coords` de forma idêntica ao `scorm_builder.py`
  - Manter as funções como standalone no módulo (sem criar módulo compartilhado)
  - _Requirements: 1.5, 1.6, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 6.2, 6.4_

  - [x] 4.1 Implementar as cinco funções auxiliares em `scripts/sim_link_builder.py`
    - Código idêntico ao de `scorm_builder.py` para garantir consistência
    - _Requirements: 1.5, 1.6, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2_

  - [ ]* 4.2 Escrever testes de unidade para as funções auxiliares de `sim_link_builder.py`
    - Mesmos casos de borda dos testes de `scorm_builder.py`
    - _Requirements: 1.6, 2.4, 3.4_

- [x] 5. Integrar funções auxiliares na lógica de geração de slides do `sim_link_builder.py`
  - Substituir a lógica atual de seleção de âncora pela chamada a `_selecionar_imagem_ancora`
  - Substituir a leitura de viewport e cálculo de coordenadas pelas novas funções
  - _Requirements: 1.5, 1.6, 1.7, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 4.4, 6.2, 6.4_

  - [x] 5.1 Substituir lógica de âncora em `scripts/sim_link_builder.py`
    - Localizar o ponto onde a âncora é resolvida para `imagem_b64`
    - Substituir pela chamada a `_selecionar_imagem_ancora(passos, idx)`
    - _Requirements: 1.5, 1.6, 1.7, 4.1_

  - [x] 5.2 Substituir leitura de viewport e cálculo de coordenadas em `scripts/sim_link_builder.py`
    - Substituir uso de `coordenadas_relativas` direto por `_resolver_coords(acao)`
    - Garantir que SoM é priorizado sobre `coordenadas_relativas`
    - _Requirements: 2.2, 3.1, 3.2, 3.3, 4.2_

  - [ ]* 5.3 Escrever teste de propriedade P1 — seleção correta da imagem de âncora
    - **Property 1: Anchor image selection**
    - Usar `@given(roteiro=st_roteiro())`
    - Verificar que `imagem_b64` do slide de âncora em ambos os builders é igual a `_selecionar_imagem_ancora(passos, idx)`
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 4.1**

  - [ ]* 5.4 Escrever teste de propriedade P4 — consistência de coordenadas entre os dois builders
    - **Property 4: Coordinate consistency between builders**
    - Usar `@given(roteiro=st_roteiro())`
    - Verificar que `x_pct`, `y_pct`, `w_pct`, `h_pct` diferem menos de 0.0001 entre SCORM e SimLink para cada ação
    - **Validates: Requirements 3.5, 4.2**

  - [ ]* 5.5 Escrever teste de propriedade P5 — consistência de contagem de slides
    - **Property 5: Slide count consistency**
    - Usar `@given(roteiro=st_roteiro())`
    - Verificar que o número de slides de âncora e de interação é igual entre os dois builders
    - **Validates: Requirements 4.3, 4.4**

  - [ ]* 5.6 Escrever teste de propriedade P6 — robustez com screenshots ausentes
    - **Property 6: Robustness with missing screenshots**
    - Usar `@given(roteiro=st_roteiro_sem_screenshots())`
    - Verificar que ambos os builders concluem sem lançar exceção
    - **Validates: Requirements 6.1, 6.2, 6.4**

- [x] 6. Checkpoint — verificar `sim_link_builder.py`
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

- [x] 7. Substituir `asyncio.sleep(1.2)` por espera observável em `CIL/capture/capture_semantic.py`
  - Localizar o bloco de captura de `screenshot_depois` após cada clique
  - Substituir `await asyncio.sleep(1.2)` por `await page.wait_for_load_state("networkidle", timeout=3000)` dentro de `try/except`
  - Envolver a captura do screenshot em bloco `try/except` separado com fallback para `b64_img_depois = ""`
  - Preservar o campo `screenshot_depois` dentro de `elemento_alvo` da ação técnica correspondente
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 7.1 Substituir `asyncio.sleep(1.2)` por `wait_for_load_state("networkidle", timeout=3000)` em `capture_semantic.py`
    - Adicionar `try/except` ao redor do `wait_for_load_state` para absorver `TimeoutError` e exceções genéricas
    - Adicionar `try/except` separado ao redor do `page.screenshot(...)` com fallback `b64_img_depois = ""`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 7.2 Escrever testes de exemplo (pytest + AsyncMock) para o capturador
    - Testar que `wait_for_load_state("networkidle", timeout=3000)` é chamado (Req 5.1)
    - Testar que `TimeoutError` no `wait_for_load_state` não propaga e o screenshot ainda é capturado (Req 5.2)
    - Testar que exceção no `page.screenshot` retorna `screenshot_depois = ""` sem lançar exceção (Req 5.3)
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 8. Checkpoint final — garantir que todos os testes passam
  - Executar `pytest` na suíte completa de testes do projeto
  - Verificar que nenhum teste de vídeo, PDF ou DAP foi quebrado
  - Garantir que todos os testes passam, perguntar ao usuário se houver dúvidas.

## Notes

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia requisitos específicos para rastreabilidade
- As funções auxiliares são duplicadas nos dois builders (sem módulo compartilhado) para minimizar risco de regressão no pipeline
- Os testes de propriedade usam Hypothesis (já presente no projeto em `.hypothesis/`)
- Os testes de exemplo do capturador usam `pytest` + `unittest.mock.AsyncMock`
- Nenhuma nova dependência é necessária
- A estratégia `st_roteiro()` e `st_som_box_qualquer()` devem ser definidas no arquivo de testes antes dos testes de propriedade
- Checkpoints garantem validação incremental antes de avançar para o próximo módulo

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1", "2.2"] },
    { "id": 2, "tasks": ["2.3", "2.4", "4.1"] },
    { "id": 3, "tasks": ["4.2", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "5.6", "7.1"] },
    { "id": 5, "tasks": ["7.2"] }
  ]
}
```

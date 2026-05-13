# Implementation Tasks

## Task List

- [x] 1. Escrever testes exploratórios de bug condition (demonstrar os 3 cenários de falso positivo ANTES do fix)
  - [x] 1.1 Criar `test_identity_verification_bug_exploration.py` com testes que demonstram falso positivo no Sniper para candidatos posicionais
  - [x] 1.2 Adicionar teste que demonstra substring matching aceitando `"1" in "EMPRESA 1"` em `_verificar_identidade_por_coordenadas()`
  - [x] 1.3 Adicionar teste que demonstra substring matching em `_verificar_identidade_elemento()`
  - [x] 1.4 Executar os testes no código NÃO corrigido e confirmar que os bugs existem (testes devem PASSAR demonstrando o comportamento buggy)

- [x] 2. Escrever testes de preservation (capturar comportamento de fail-open ANTES do fix)
  - [x] 2.1 Criar `test_identity_verification_preservation.py` com testes para fail-open em `_verificar_identidade_por_coordenadas()`: label vazio, cross-origin, sem texto, exceção
  - [x] 2.2 Adicionar testes para candidatos semânticos de alta confiança no Sniper (`[aria-label=]`, `[name=]`, `[data-testid=]`) — sem verificação adicional
  - [x] 2.3 Adicionar testes para candidatos `text=` no Sniper — match exato já existente deve permanecer inalterado
  - [x] 2.4 Executar os testes no código NÃO corrigido e confirmar que todos PASSAM (baseline de preservation)

- [x] 3. Implementar match exato em `_verificar_identidade_elemento()` e `_verificar_identidade_por_coordenadas()`
  - [x] 3.1 Em `_verificar_identidade_elemento()`: substituir `needle in texto.strip().lower()` por `texto.strip().lower() == needle` (e mesma lógica para o pai)
  - [x] 3.2 Em `_verificar_identidade_por_coordenadas()`: substituir `label_curto.strip().lower() in texto_elemento.strip().lower()` por `texto_elem_norm == label_norm` com match exato
  - [x] 3.3 Atualizar mensagens de log para indicar "match exato requerido"
  - [x] 3.4 Executar testes de bug condition — devem FALHAR agora (bug corrigido nessas funções)
  - [x] 3.5 Executar testes de preservation — devem continuar PASSANDO (fail-open inalterado)

- [x] 4. Implementar verificação de identidade no Sniper para candidatos CSS posicionais
  - [x] 4.1 Criar função helper `_e_candidato_posicional(cand: TentativaLocalizacao) -> bool` que reutiliza `_contem_indice_posicional()`
  - [x] 4.2 No bloco do Sniper em `encontrar_e_clicar()`, após `_tentar_candidato()` retornar True para candidato posicional: verificar identidade com match exato e rejeitar se não confirmar
  - [x] 4.3 Adicionar log de warning quando candidato posicional é rejeitado por identidade não confirmada
  - [x] 4.4 Executar testes de bug condition do Sniper — devem FALHAR agora (bug corrigido)
  - [x] 4.5 Executar testes de preservation do Sniper — devem continuar PASSANDO

- [x] 5. Reordenar cascata: mover coordenadas capturadas para depois do seletor_hint (Camada 3.5)
  - [x] 5.1 Em `encontrar_e_clicar()`, mover o bloco `if coords_relativas and coords_relativas.get("x_pct"):` para depois do bloco da Camada 3 (seletor_hint original)
  - [x] 5.2 Atualizar comentário do bloco para indicar "Camada 3.5"
  - [x] 5.3 Atualizar docstring do módulo no topo de `vision_engine.py` com o novo mapa de camadas
  - [x] 5.4 Executar todos os testes — devem continuar PASSANDO

- [x] 6. Checkpoint: executar suite completa de testes e validar
  - [x] 6.1 Executar `test_identity_verification_bug_exploration.py` — todos os testes de bug condition devem FALHAR (confirmando que os bugs foram corrigidos)
  - [x] 6.2 Executar `test_identity_verification_preservation.py` — todos os testes de preservation devem PASSAR
  - [x] 6.3 Executar testes existentes relacionados: `test_primeng_preservation.py`, `test_executor_seletor_hint_preservation.py`, `test_iframe_element_location_preservation.py`
  - [x] 6.4 Confirmar que nenhuma regressão foi introduzida

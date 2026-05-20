# Implementation Plan: generic-site-support

## Overview

Implementação do suporte a sites genéricos no pipeline Senior Training OS. O trabalho consiste em: (1) criar o `GenericAdapter` no arquivo de contratos existente, (2) refatorar os módulos de captura e execução para consumir o adapter via factory, (3) condicionar a camada 1.5 do vision_engine ao adapter ativo, (4) parametrizar prompts de IA pelo sistema alvo, e (5) documentar as novas variáveis no `.env.example`. Testes de propriedade com Hypothesis validam as 18 propriedades de corretude definidas no design.

## Tasks

- [x] 1. Implementar GenericAdapter e atualizar factory
  - [x] 1.1 Criar classe `GenericAdapter` em `contracts/capture_adapter.py`
    - Implementar todos os métodos do protocolo `CaptureAdapter`: `nome_sistema`, `url_base`, `obter_credenciais()`, `obter_seletores_login()`, `obter_configuracao_browser()`
    - Adicionar método `login_requerido()` que retorna `True` se `LOGIN_REQUIRED=true` (case-insensitive), default `False`
    - Implementar `validar_configuracao()` no `__init__` com fail-fast: valida `TARGET_URL` (obrigatória, deve iniciar com `http://` ou `https://`), `LOGIN_REQUIRED` (deve ser `true` ou `false`), e seletores/credenciais quando login requerido
    - Usar `sys.exit(1)` com mensagem descritiva listando todas as variáveis inválidas/ausentes
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 6.1, 6.6, 6.7_

  - [x] 1.2 Atualizar `get_capture_adapter()` para reconhecer `CAPTURE_ADAPTER=generic`
    - Adicionar branch na factory: `if adapter_name in ("generic", "generico"): return GenericAdapter()`
    - Preservar fallback para `SeniorXAdapter` com WARNING no log para valores não reconhecidos
    - _Requirements: 1.2, 9.1, 9.2, 9.3_

  - [ ]* 1.3 Escrever testes de propriedade para GenericAdapter (Properties 1-4, 15, 17, 18)
    - **Property 1: GenericAdapter satisfaz o protocolo CaptureAdapter**
    - **Property 2: url_base reflete TARGET_URL sem transformação**
    - **Property 3: nome_sistema com fallback correto**
    - **Property 4: Validação de LOGIN_REQUIRED rejeita valores inválidos**
    - **Property 15: Factory retorna SeniorXAdapter para qualquer valor não reconhecido**
    - **Property 17: TARGET_URL inválida é rejeitada antes de abrir o navegador**
    - **Property 18: Variáveis SENIOR_* ausentes não causam erros no modo genérico**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 6.1, 6.4, 6.5, 6.6, 9.3**

- [-] 2. Checkpoint - Validar adapter isolado
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Desacoplar login em `capture_variants/capture_dual_output.py`
  - [x] 3.1 Refatorar `capturar_cliques_na_tela()` para usar adapter
    - Substituir leitura direta de `SENIOR_URL`, `SENIOR_USER_CAPTURE`, `SENIOR_PASS_CAPTURE` por chamadas ao adapter via `get_capture_adapter()`
    - Implementar bloco condicional: se `GenericAdapter` com `login_requerido()=False`, navegar direto para `adapter.url_base` e injetar radar sem login
    - Se `GenericAdapter` com `login_requerido()=True`, usar seletores de `adapter.obter_seletores_login()` para login genérico
    - Preservar fallback manual existente para ambos os adapters
    - Adicionar log INFO no início: `[Pipeline] Adapter ativo: {type(adapter).__name__} | Sistema: {adapter.nome_sistema}`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 8.1, 8.2, 8.3, 8.4_

  - [ ]* 3.2 Escrever testes de propriedade para captura desacoplada (Properties 5, 6, 8, 14)
    - **Property 5: Seletores de login usados são os do adapter**
    - **Property 6: Modo sem login não executa nenhuma chamada de autenticação**
    - **Property 8: Dual output preservado independente do adapter**
    - **Property 14: Log de login genérico contém seletores mas não credenciais**
    - **Validates: Requirements 1.7, 2.2, 2.4, 2.8, 6.3, 8.3**

- [x] 4. Desacoplar login em `main.py`
  - [x] 4.1 Refatorar `executar_roteiro()` para usar adapter
    - Substituir leitura direta de `SENIOR_URL`, `SENIOR_USER_EXECUTE`, `SENIOR_PASS_EXECUTE` por chamadas ao adapter via `get_capture_adapter()`
    - Implementar bloco condicional: se `GenericAdapter` com `login_requerido()=False`, navegar direto e exibir overlay "Pronto para gravar?"
    - Se `GenericAdapter` com `login_requerido()=True`, usar seletores do adapter para login
    - Adaptar validação de credenciais: `SeniorXAdapter` mantém `sys.exit(1)` se ausentes; `GenericAdapter` com login requerido valida `LOGIN_USER`/`LOGIN_PASS`; sem login não valida
    - Preservar fallback manual existente para ambos os adapters
    - Adicionar log INFO no início: `[Pipeline] Adapter ativo: {type(adapter).__name__} | Sistema: {adapter.nome_sistema}`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 8.1, 9.5_

  - [ ]* 4.2 Escrever testes de propriedade para executor desacoplado (Property 7)
    - **Property 7: Fallback manual ativado para qualquer adapter em caso de falha de login**
    - **Validates: Requirements 2.6, 3.6**

- [x] 5. Checkpoint - Validar captura e execução desacoplados
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Condicionar camada 1.5 do vision_engine ao adapter ativo
  - [x] 6.1 Refatorar `vision_engine.py` para pular camada 1.5 quando adapter não é SeniorX
    - Importar `get_capture_adapter` e `SeniorXAdapter` de `contracts.capture_adapter`
    - Cachear resultado de `get_capture_adapter()` em variável de módulo para evitar overhead de I/O repetido
    - No início da camada 1.5 dentro de `encontrar_e_clicar()`, verificar `isinstance(_adapter_ativo, SeniorXAdapter)` — se False, pular camada 1.5
    - Adicionar log INFO no primeiro passo da sessão com nome do adapter ativo
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 6.2 Escrever testes de propriedade para vision_engine condicional (Properties 9, 10)
    - **Property 9: Camada 1.5 pulada para qualquer adapter não-SeniorX**
    - **Property 10: Camadas 0, 2, 3, 4, 5 preservadas para qualquer adapter**
    - **Validates: Requirements 4.2, 4.3, 4.5**

- [x] 7. Parametrizar prompts de IA pelo sistema alvo
  - [x] 7.1 Implementar `_adaptar_prompt_sistema()` em `generator_engine.py`
    - Criar função que substitui "Senior X" e "ERP" (case-insensitive) por `TARGET_SYSTEM_NAME` no prompt quando adapter não é `SeniorXAdapter`
    - Preservar prompt original sem substituição quando `SeniorXAdapter` ativo ou `TARGET_SYSTEM_NAME` vazio
    - Implementar try/except defensivo: em caso de erro, retornar prompt original com log WARNING
    - Aplicar substituição ao `prompt_usuario` antes de enviar ao Gemini
    - _Requirements: 5.1, 5.3, 5.4, 5.5_

  - [x] 7.2 Incluir contexto do sistema alvo no prompt de captura em `capture_dual_output.py`
    - Adicionar `adapter.nome_sistema` como campo de contexto nomeado no prompt enviado ao Gemini durante análise de elementos
    - _Requirements: 5.2_

  - [ ]* 7.3 Escrever testes de propriedade para substituição de prompt (Property 11)
    - **Property 11: Substituição de nome de sistema no prompt é completa e não afeta SeniorX**
    - **Validates: Requirements 5.1, 5.3**

- [x] 8. Atualizar `.env.example` com novas variáveis
  - [x] 8.1 Adicionar bloco de configuração para sites genéricos no `.env.example`
    - Incluir variáveis: `CAPTURE_ADAPTER`, `TARGET_URL`, `TARGET_SYSTEM_NAME`, `LOGIN_REQUIRED`, `LOGIN_USER`, `LOGIN_PASS`, `LOGIN_SELECTOR_USER`, `LOGIN_SELECTOR_PASS`, `LOGIN_SELECTOR_SUBMIT`
    - Adicionar comentários explicativos em português para cada variável
    - Incluir valores de exemplo realistas
    - _Requirements: 6.1, 6.2_

- [ ] 9. Testes de integração e regressão
  - [ ]* 9.1 Escrever testes de exemplo para compatibilidade do roteiro (Properties 12, 13, 16)
    - **Property 12: Roteiro de site genérico satisfaz o contrato estrutural**
    - **Property 13: Ações de sites genéricos indexadas com campos obrigatórios**
    - **Property 16: Roteiros existentes do SeniorX passam na validação sem modificação**
    - **Validates: Requirements 7.1, 7.5, 7.6, 9.6**

  - [ ]* 9.2 Escrever testes unitários de regressão para SeniorXAdapter
    - Verificar que `get_capture_adapter()` sem `CAPTURE_ADAPTER` retorna `SeniorXAdapter`
    - Verificar que camada 1.5 executa com `SeniorXAdapter`
    - Verificar que credenciais `SENIOR_USER_*` são lidas corretamente
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [x] 10. Final checkpoint - Validação completa
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (18 properties total)
- Unit tests validate specific examples and edge cases
- O módulo de captura ativo é `capture_variants/capture_dual_output.py` — NÃO referenciar `capture.py` (legado em `old_but_gold/`)
- A abstração `CaptureAdapter` já existe — o trabalho é completar a implementação, não redesenhar
- Stack: Python 3.11+, Hypothesis para PBT, pytest como runner
- Arquivo de testes de propriedade: `tests/test_generic_adapter_properties.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "8.1"] },
    { "id": 3, "tasks": ["3.1", "4.1"] },
    { "id": 4, "tasks": ["3.2", "4.2", "6.1", "7.1", "7.2"] },
    { "id": 5, "tasks": ["6.2", "7.3"] },
    { "id": 6, "tasks": ["9.1", "9.2"] }
  ]
}
```

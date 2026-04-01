# Plano de Implementação: Fase 3 — Melhoria de Vision e Seletores

## Overview

Implementação em ordem de dependência: utilitários sem dependências primeiro, depois consumidores. Cada tarefa é atômica e segura — nenhuma quebra o pipeline existente antes de ser concluída.

## Tasks

- [x] 1. Adicionar `validar_roteiro_ia` em `utils.py`
  - [x] 1.1 Implementar a função `validar_roteiro_ia(roteiro: dict) -> tuple[bool, str]`
    - Adicionar após `validar_roteiro` existente, sem modificá-la
    - Critérios: mínimo 2 passos, pelo menos uma `ancora` preenchida, pelo menos um `elemento_alvo` não vazio (excluindo `concluir_video`), nenhum passo não-conclusão sem ações
    - Ignorar passo com `is_conclusao: true` nos critérios de elemento e ações
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.10_

  - [ ]* 1.2 Escrever teste de propriedade — Property 5: reprova roteiros com menos de 2 passos
    - **Property 5: validar_roteiro_ia reprova roteiros com menos de 2 passos**
    - **Validates: Requirements 3.2**

  - [ ]* 1.3 Escrever teste de propriedade — Property 6: reprova roteiros sem âncora pedagógica
    - **Property 6: validar_roteiro_ia reprova roteiros sem âncora pedagógica**
    - **Validates: Requirements 3.3**

  - [ ]* 1.4 Escrever teste de propriedade — Property 7: reprova roteiros sem elemento_alvo
    - **Property 7: validar_roteiro_ia reprova roteiros sem elemento_alvo em nenhuma ação**
    - **Validates: Requirements 3.4, 3.6**

  - [ ]* 1.5 Escrever teste de propriedade — Property 8: reprova passo não-conclusão sem ações
    - **Property 8: validar_roteiro_ia reprova roteiros com passo não-conclusão sem ações**
    - **Validates: Requirements 3.5, 3.6**

  - [ ]* 1.6 Escrever teste de propriedade — Property 9: aprova roteiros bem formados
    - **Property 9: validar_roteiro_ia aprova roteiros bem formados**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

  - [ ]* 1.7 Escrever teste de propriedade — Property 10: validar_roteiro não-regressão
    - **Property 10: validar_roteiro não-regressão**
    - Verificar que roteiros capturados válidos continuam retornando `(True, ...)` após a adição
    - **Validates: Requirements 3.10, 3.11**

- [x] 2. Atualizar `generator_engine.py` para usar `validar_roteiro_ia`
  - [x] 2.1 Substituir chamada de `validar_roteiro` por `validar_roteiro_ia` no portão de qualidade de `gerar_roteiro_ia_sync`
    - Atualizar import: adicionar `validar_roteiro_ia` ao import de `utils`
    - Substituir apenas a chamada dentro do bloco `gerado_por_ia: true` — não alterar outros usos de `validar_roteiro`
    - Garantir que reprovação emite `logger.warning` sem interromper retorno nem persistência
    - _Requirements: 3.7, 3.8, 3.9_

  - [ ]* 2.2 Escrever teste de propriedade — Property 11: Generator persiste roteiro independentemente da validação
    - **Property 11: Generator_Engine persiste roteiro independentemente do resultado de validar_roteiro_ia**
    - **Validates: Requirements 3.9**

- [x] 3. Checkpoint — Portão de qualidade semântico
  - Garantir que todos os testes das tarefas 1 e 2 passam
  - Verificar manualmente que `validar_roteiro` original permanece inalterado
  - Perguntar ao usuário se há dúvidas antes de continuar

- [x] 4. Adicionar `_resolver_screenshot_ref` em `vision_engine.py`
  - [x] 4.1 Implementar a função `_resolver_screenshot_ref(ref: str | None) -> bytes | None`
    - Inserir antes de `_gemini_localizar_elemento`
    - Detectar automaticamente: path existente em disco → lê bytes; caso contrário → tenta base64 decode; falha → retorna `None`
    - Nunca lançar exceção — todos os caminhos de erro retornam `None`
    - _Requirements: 1.6, 1.7, 1.8, 1.9_

  - [x] 4.2 Atualizar `_gemini_localizar_elemento` para usar `_resolver_screenshot_ref`
    - Substituir o bloco `base64.b64decode(screenshot_ref_b64)` por chamada a `_resolver_screenshot_ref`
    - Manter o nome do parâmetro `screenshot_ref_b64` (misnomer aceitável — documentar com comentário)
    - Comportamento quando retorna `None` deve ser idêntico ao atual quando `screenshot_ref_b64` é falsy
    - _Requirements: 1.6, 1.7, 1.8, 1.9_

  - [ ]* 4.3 Escrever teste de propriedade — Property 1: _resolver_screenshot_ref retorna bytes para referência válida
    - **Property 1: _resolver_screenshot_ref retorna bytes para qualquer referência válida**
    - Cobrir: path existente em disco, base64 válido, `None`, path inexistente, base64 inválido
    - **Validates: Requirements 1.6, 1.7, 1.8, 1.9**

- [x] 5. Externalizar screenshots em `capture.py`
  - [x] 5.1 Adicionar variável global `_nome_aula_sessao: str = ""` ao topo do módulo
    - Inserir junto às outras variáveis globais existentes
    - _Requirements: 1.4_

  - [x] 5.2 Definir `_nome_aula_sessao` em `iniciar_esteira_de_producao` antes de chamar `_pipeline()`
    - Atribuir `_nome_aula_sessao = nome_aula` (usando `global`) antes da chamada ao pipeline
    - _Requirements: 1.4_

  - [x] 5.3 Substituir o bloco de base64 em `on_capturar_elemento` pela lógica de externalização
    - Construir `pasta_screenshots = os.path.join("audios_gerados", limpar_nome(_nome_aula_sessao), "screenshots")`
    - Criar diretório com `os.makedirs(pasta_screenshots, exist_ok=True)`
    - Tentar escrever `acao_{meu_id_acao}.jpg` em disco; em caso de exceção, usar base64 como fallback
    - Armazenar path relativo (ou base64 fallback) em `screenshot_referencia`
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ]* 5.4 Escrever teste de propriedade — Property 2: on_capturar_elemento armazena path relativo
    - **Property 2: on_capturar_elemento armazena path relativo (não base64) quando escrita bem-sucedida**
    - **Validates: Requirements 1.1, 1.2**

- [x] 6. Checkpoint — Externalização de screenshots
  - Garantir que todos os testes das tarefas 4 e 5 passam
  - Verificar que roteiros existentes com base64 ainda funcionam via `_resolver_screenshot_ref`
  - Perguntar ao usuário se há dúvidas antes de continuar

- [x] 7. Reescrever `validator.py` com navegação contextual
  - [x] 7.1 Adicionar constante `_PALAVRAS_NAVEGACAO` e função `_e_acao_navegacao(acao_tec: dict) -> bool`
    - Lista de palavras-chave: `["menu", "breadcrumb", "fa-home", "home", "inicio", "módulo", "apps-menu", "menu-item", "nav-item", "sidebar"]`
    - Heurística: verificar `label_curto` e `seletor_hint` do `elemento_alvo` — não depende de `tipo_passo`
    - _Requirements: 2.2, 2.3, 2.9_

  - [ ]* 7.2 Escrever teste de propriedade — Property 4: _e_acao_navegacao classifica por palavras-chave
    - **Property 4: _e_acao_navegacao classifica corretamente por palavras-chave**
    - **Validates: Requirements 2.2, 2.3, 2.9**

  - [x] 7.3 Implementar `_executar_navegacao(page, acao_tec: dict)` e `_validar_seletor(page, passo, acao_tec, resultados)`
    - `_executar_navegacao`: clique real no seletor + `wait_for_load_state("networkidle", timeout=10000)`
    - `_validar_seletor`: `wait_for(state="visible")` + `wait_for(state="enabled")`; mock para `acao == "upload"`; acumular falhas em `resultados["falhas"]`
    - _Requirements: 2.4, 2.5, 2.8_

  - [x] 7.4 Reescrever `dry_run_validador` com loop de navegação contextual
    - Percorrer passos em ordem sequencial
    - Para cada `acao_tec`: se `_e_acao_navegacao` e não `dry_run` → `_executar_navegacao` (com try/except + aviso); senão → `_validar_seletor`
    - Pular ações `concluir_video`
    - Inicializar `resultados = {"validados": 0, "falhas": [], "navegacoes": 0}`
    - Exibir resumo ao final: total validados, navegações, falhas e lista de seletores com problema
    - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 2.8, 2.10_

  - [x] 7.5 Adicionar suporte a `--dry-run` via `if __name__ == "__main__"`
    - Parsear `sys.argv` para detectar `--dry-run`
    - Exibir mensagem de uso se `len(sys.argv) < 2`
    - _Requirements: 2.6_

- [x] 8. Escrever testes de propriedade com Hypothesis
  - [ ]* 8.1 Escrever teste de propriedade — Property 3: lego_builder remove screenshot_referencia independentemente do formato
    - **Property 3: lego_builder remove screenshot_referencia independentemente do formato**
    - Testar com path relativo e com base64 como valor de `screenshot_referencia`
    - **Validates: Requirements 1.5**

  - [x]* 8.2 Consolidar arquivo de testes `tests/test_vision_quality_properties.py`
    - Reunir todos os testes de propriedade das tarefas 1–7 em um único arquivo organizado por seção
    - Cada teste deve incluir comentário `# Feature: vision-quality, Property N: <texto>`
    - Configurar `@settings(max_examples=100)` em todos os testes
    - _Requirements: 1.1, 1.2, 1.5, 1.6, 1.7, 1.8, 1.9, 2.2, 2.3, 2.9, 3.1–3.11_

- [x] 9. Checkpoint final — Garantir que todos os testes passam
  - Executar `pytest tests/test_vision_quality_properties.py --tb=short`
  - Verificar que nenhum módulo existente regrediu
  - Perguntar ao usuário se há dúvidas antes de encerrar

## Notes

- Tarefas marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- A ordem 1 → 2 → 4 → 5 → 7 é obrigatória por dependência: `utils` antes de `generator_engine`, `vision_engine` antes de `capture`, `validator` por último (sem dependências das anteriores)
- `validar_roteiro` original em `utils.py` não deve ser tocado em nenhuma tarefa
- O schema do roteiro JSON permanece inalterado em todas as tarefas
- Roteiros existentes em `roteiros_salvos/` devem continuar funcionando após cada tarefa individualmente

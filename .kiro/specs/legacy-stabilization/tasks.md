# Plano de Implementação: Fase 1 de Estabilização do Legado

## Overview

Correções cirúrgicas em 9 módulos do Senior Training OS. A ordem de execução respeita o grafo de dependências: `utils.py` é a fonte canônica e deve ser implementado primeiro. Todos os consumidores dependem dele.

## Tasks

- [x] 1. Implementar `validar_roteiro` em `utils.py` (fonte canônica)
  - Adicionar a função `validar_roteiro(roteiro: dict) -> tuple[bool, str]` em `utils.py`, após a definição de `limpar_nome`
  - Implementar os três critérios: (a) >= 2 passos, (b) >= 50% das ações com `seletor_hint` preenchido, (c) <= 70% das ações com `confianca_captura == "baixa"`
  - Ignorar ações com `acao == "concluir_video"` nos cálculos de percentual
  - Verificar que `limpar_nome` já existe em `utils.py` com limite de 40 chars e remoção de acentos via `unicodedata.normalize`
  - _Requirements: 3.1, 3.7, 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 1.1 Escrever teste de propriedade para `limpar_nome` (Property 1)
    - **Property 1: `limpar_nome` produz strings ASCII seguras com no máximo 40 chars**
    - **Validates: Requirements 3.7**
    - Usar `@given(st.text(min_size=0, max_size=200))` com `@settings(max_examples=100)`
    - Verificar: `len(resultado) <= 40`, `resultado.isascii()`, `" " not in resultado`, nenhum char de `\/*?:"<>|`
    - Tag: `# Feature: legacy-stabilization, Property 1: limpar_nome produz strings ASCII seguras com no máximo 40 chars`

  - [ ]* 1.2 Escrever teste de propriedade para `validar_roteiro` (Property 2)
    - **Property 2: `validar_roteiro` aplica os três critérios de qualidade corretamente**
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5**
    - Criar strategy `roteiros_aleatorios()` com Hypothesis para gerar roteiros com passos e ações variados
    - Verificar que `aprovado == False` se e somente se algum critério for violado
    - Tag: `# Feature: legacy-stabilization, Property 2: validar_roteiro aplica os três critérios de qualidade corretamente`

- [x] 2. Corrigir `capture.py`: centralizar `limpar_nome` e `validar_roteiro`
  - Remover a definição local de `limpar_nome` (linha ~44) e adicionar `from utils import limpar_nome, validar_roteiro` no bloco de imports
  - Remover a definição local `_validar_roteiro` (linha ~536)
  - Substituir a única chamada `_validar_roteiro(roteiro_final)` por `validar_roteiro(roteiro_final)`
  - Nenhuma chamada a `limpar_nome` precisa ser alterada — assinatura idêntica
  - _Requirements: 3.2, 4.6_

- [x] 3. Corrigir `capture.py`: validação de IDs alucinados em `_invocar_aura_sync`
  - Localizar o loop `for i, id_tec in enumerate(passo_ia.get("ids_acoes_tecnicas", [])):`
  - Substituir o `if acao_bruta:` implícito por verificação explícita: `if acao_bruta is None: logger.warning(...); continue`
  - O warning deve incluir `id_tec` e `nome_aula`
  - O `next(..., None)` já existe — apenas adicionar o bloco de guarda com warning e `continue`
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ]* 3.1 Escrever teste de propriedade para IDs válidos (Property 3)
    - **Property 3: IDs válidos do `log_mapeador` sempre aparecem no roteiro final**
    - **Validates: Requirements 1.1, 1.4**
    - Gerar `log_mapeador` aleatório e `ids_acoes_tecnicas` como subconjunto dos IDs do log
    - Verificar que todas as ações referenciadas aparecem no `acoes_tecnicas` do passo
    - Tag: `# Feature: legacy-stabilization, Property 3: IDs válidos do log_mapeador sempre aparecem no roteiro final`

  - [ ]* 3.2 Escrever teste de propriedade para IDs ausentes (Property 4)
    - **Property 4: IDs ausentes no `log_mapeador` não interrompem o processamento**
    - **Validates: Requirements 1.2, 1.3**
    - Gerar `ids_acoes_tecnicas` com IDs inexistentes misturados a IDs válidos
    - Verificar que nenhuma exceção é lançada e que os IDs válidos são processados normalmente
    - Tag: `# Feature: legacy-stabilization, Property 4: IDs ausentes no log_mapeador não interrompem o processamento`

- [x] 4. Corrigir `capture.py`: adicionar `getRectComFallback` ao JS injetado
  - Localizar `_injetar_em_contexto` e o `script_radar` dentro dela
  - Inserir a função JS `getRectComFallback(el)` antes da definição de `processarEvento`
  - A função sobe a árvore DOM até 5 níveis buscando elemento com `width > 0` e `height > 0`
  - Substituir `target.getBoundingClientRect()` por `getRectComFallback(target)` dentro de `processarEvento`
  - Nenhuma outra linha de `processarEvento` deve ser alterada
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 5. Checkpoint — Verificar `capture.py`
  - Garantir que todos os testes passam. Verificar que `capture.py` não define mais `limpar_nome` nem `_validar_roteiro` localmente. Perguntar ao usuário se houver dúvidas.

- [x] 6. Corrigir `main.py`: eliminar importação de `app.py`
  - Remover o bloco `try/except` que importa `limpar_nome` de `app.py` com fallback local (linhas ~48–51)
  - Substituir por `from utils import limpar_nome`
  - Verificar que nenhuma chamada a `limpar_nome` no módulo precisa ser alterada
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 7. Corrigir `app.py`: centralizar `limpar_nome` e `validar_roteiro`
  - Adicionar `from utils import limpar_nome, validar_roteiro` no bloco de imports existente
  - Remover a definição local de `limpar_nome` (linha ~150)
  - Remover a definição local de `_validar_roteiro_app` (linha ~209)
  - Substituir a única chamada `_validar_roteiro_app(...)` por `validar_roteiro(...)`
  - _Requirements: 3.3, 4.7_

- [x] 8. Corrigir `capture_dual_output.py`: centralizar `limpar_nome`
  - Remover a definição local de `limpar_nome` (linha ~54)
  - Adicionar `from utils import limpar_nome` no bloco de imports
  - Nenhuma chamada a `limpar_nome` no módulo precisa ser alterada
  - _Requirements: 3.4_

- [x] 9. Corrigir `capture_hybrid_shadow.py`: centralizar `limpar_nome` e remover `return` duplicado
  - Remover a definição local de `limpar_nome` (linha ~294) — atenção: a versão local usa limite de 60 chars (bug silencioso), a canônica usa 40
  - Adicionar `from utils import limpar_nome` no bloco de imports
  - Localizar `analisar_semantica_hibrida` e remover o segundo `return fallback` duplicado (dead code, linha ~507)
  - _Requirements: 3.5, 7.1, 7.2_

- [x] 10. Corrigir `generator_engine.py`: centralizar `limpar_nome` e adicionar portão de qualidade
  - Remover a definição local de `limpar_nome` (linha ~19)
  - Adicionar `from utils import limpar_nome, validar_roteiro` no bloco de imports
  - Em `gerar_roteiro_ia_sync`, após o `json.dump` de persistência e antes do `return`, inserir chamada a `validar_roteiro(roteiro_final)`
  - Se reprovado, emitir `logger.warning` com o motivo — não bloquear o retorno `{"status": "sucesso", ...}`
  - A função `_validar_estrutura_roteiro` (validação estrutural mínima) deve ser mantida como verificação prévia separada
  - _Requirements: 3.6, 4.8, 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 11. Corrigir `vision_engine.py`: expandir filtro de seletores no Brain
  - Localizar `_registrar_sucesso_cache` (linha ~142)
  - Substituir o filtro atual `if seletor and not seletor.startswith(("text=", "[", "#")):` pelo filtro expandido
  - Novo filtro: `_PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")` + condição `:has-text(`
  - Nenhuma outra linha de `_registrar_sucesso_cache` deve ser alterada
  - As 7 camadas de resiliência do orquestrador não devem ser tocadas
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 11.1 Escrever teste de propriedade para o filtro de seletores (Property 5)
    - **Property 5: Filtro de seletores do Brain aceita prefixos Angular/PrimeNG e `:has-text(`**
    - **Validates: Requirements 6.1, 6.2, 6.4**
    - Testar seletores válidos: `button.p-button`, `p-dropdown`, `mat-select`, `text=Salvar`, `[aria-label='x']`, `#meu-id`, `div:has-text('ok')`
    - Testar seletores inválidos: `div`, `span`, `h1`, `form`
    - Verificar que válidos são preservados e inválidos resultam em `None`
    - Tag: `# Feature: legacy-stabilization, Property 5: filtro de seletores aceita prefixos Angular/PrimeNG e :has-text(`

- [x] 12. Corrigir `dap_engine.py`: sanitizar ID do vetor Pinecone
  - Adicionar `from utils import limpar_nome` no bloco de imports de `dap_engine.py`
  - Localizar `ingestar_para_pinecone` (linha ~184) e a linha que constrói `id_vetor`
  - Substituir `f"{nome_aula}_passo_{passo.get('id_passo')}".replace(" ", "_")` por `f"{limpar_nome(nome_aula)}_passo_{passo.get('id_passo')}"`
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 12.1 Escrever teste de propriedade para `id_vetor` do Pinecone (Property 6)
    - **Property 6: `id_vetor` do Pinecone contém apenas caracteres ASCII seguros**
    - **Validates: Requirements 8.2, 8.3, 8.4**
    - Usar `@given(st.text(min_size=1, max_size=100), st.integers(min_value=1, max_value=50))`
    - Verificar: `id_vetor.isascii()`, `" " not in id_vetor`, formato `{nome_sanitizado}_passo_{id_passo}`
    - Tag: `# Feature: legacy-stabilization, Property 6: id_vetor contém apenas caracteres ASCII seguros`

- [x] 13. Escrever testes de propriedade com Hypothesis
  - Criar arquivo `tests/test_legacy_stabilization_properties.py`
  - Importar `from hypothesis import given, settings, strategies as st`
  - Implementar todas as properties marcadas como opcionais nas tarefas anteriores (Properties 1–6)
  - Incluir a strategy `roteiros_aleatorios()` para geração de roteiros sintéticos (Property 2)
  - Cada teste deve ter `@settings(max_examples=100)` e o comentário de rastreabilidade `# Feature: legacy-stabilization, Property N: ...`
  - _Requirements: 3.7, 4.2, 4.3, 4.4, 4.5, 1.1, 1.2, 1.3, 1.4, 6.1, 6.2, 6.4, 8.2, 8.3, 8.4_

  - [ ]* 13.1 Escrever teste de propriedade para `getRectComFallback` (Property 7)
    - **Property 7: `getRectComFallback` retorna rect com dimensões válidas quando existe ancestral com dimensões**
    - **Validates: Requirements 5.3, 5.4**
    - Simular árvore DOM com mocks: elemento raiz com `width=0, height=0` e ancestral com `width>0, height>0`
    - Verificar que o rect retornado tem `width > 0` e `height > 0`
    - Tag: `# Feature: legacy-stabilization, Property 7: getRectComFallback retorna rect com dimensões válidas quando existe ancestral`

- [x] 14. Checkpoint final — Garantir que todos os testes passam
  - Executar `pytest tests/test_legacy_stabilization_properties.py -v` para validar as properties
  - Verificar que nenhum módulo define `limpar_nome` ou `validar_roteiro` localmente (exceto `utils.py`)
  - Verificar que `main.py` não importa `app` em `sys.modules` após inicialização
  - Perguntar ao usuário se houver dúvidas antes de encerrar.

## Notes

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- A ordem das tarefas é obrigatória: `utils.py` (tarefa 1) deve ser concluído antes de qualquer consumidor
- Cada tarefa é atômica e segura para executar independentemente após suas dependências estarem prontas
- O portão de qualidade em `generator_engine.py` (tarefa 10) não bloqueia o fluxo — apenas emite warning
- A mudança em `capture_hybrid_shadow.py` (tarefa 9) corrige um bug silencioso de limite de 60 chars → 40 chars
- Vetores existentes no Pinecone com IDs antigos não são afetados — apenas novas ingestões usarão o formato sanitizado

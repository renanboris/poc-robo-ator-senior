# Plano de Implementação: pdf-scorm-playbook-builders

## Visão Geral

Substituição cirúrgica dos builders de PDF e SCORM pelos novos `pdf_builder_playbook_v3.py` e
`scorm_builder_playbook_v2.py`, preservando o contrato externo esperado por `app.py`.
A estratégia é: arquivar os antigos, corrigir os novos (imports, `limpar_nome`, entrypoint CLI,
defaults defensivos) e renomeá-los para os nomes canônicos.

## Tarefas

- [x] 1. Arquivar builders antigos em `old_but_gold/`
  - Criar o diretório `old_but_gold/` se não existir
  - Copiar `pdf_builder.py` para `old_but_gold/pdf_builder_v2.2.py`
  - Copiar `scorm_builder.py` para `old_but_gold/scorm_builder_v1.py`
  - Não remover os arquivos originais ainda (serão sobrescritos na tarefa 4)
  - _Requirements: 6.1, 6.2_

- [x] 2. Corrigir `pdf_builder_playbook_v3.py`
  - [x] 2.1 Substituir a definição local de `limpar_nome` por `from utils import limpar_nome`
    - Remover a função `limpar_nome` definida localmente no arquivo
    - Adicionar `from utils import limpar_nome` no bloco de imports
    - _Requirements: 1.3, 1.5_

  - [x] 2.2 Corrigir o entrypoint CLI para o padrão defensivo do design
    - Substituir o bloco `if __name__ == "__main__":` pelo padrão do design:
      captura `FileNotFoundError` separadamente, imprime mensagem descritiva e chama `sys.exit(1)`
    - Garantir que qualquer exceção interna também seja capturada, impressa e resulte em `sys.exit(1)`
    - _Requirements: 6.4, 6.6_

  - [x] 2.3 Auditar e aplicar defaults defensivos em todos os `.get()` do builder
    - `peso_narrativo` → default `2`
    - `tooltip_dap` → default `""`
    - `alerta_instrutor` → default `None`
    - `screenshot_referencia` → default `None`
    - `coordenadas_relativas` → default `{}`
    - `id_treinamento` → fallback para `nome_aula`
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [ ]* 2.4 Escrever testes unitários para `pdf_builder_playbook_v3.py` (pré-renomeação)
    - Testar geração com roteiro mínimo (2 passos, sem screenshots) → arquivo com assinatura `%PDF`
    - Testar roteiro sem `tooltip_dap` → sem exceção
    - Testar roteiro sem `alerta_instrutor` → sem exceção
    - Testar roteiro com `peso_narrativo` ausente → sem exceção, usa default 2
    - Testar nome do PDF usa `limpar_nome(id_treinamento)`
    - _Requirements: 2.1, 2.2, 2.3, 2.6, 2.8, 1.3, 1.5_

- [x] 3. Corrigir `scorm_builder_playbook_v2.py`
  - [x] 3.1 Substituir a definição local de `limpar_nome` por `from utils import limpar_nome`
    - Remover a função `limpar_nome` definida localmente no arquivo
    - Adicionar `from utils import limpar_nome` no bloco de imports
    - _Requirements: 1.4, 1.6_

  - [x] 3.2 Corrigir o entrypoint CLI para o padrão defensivo do design
    - Substituir o bloco `if __name__ == "__main__":` pelo padrão do design:
      captura `FileNotFoundError` separadamente, imprime mensagem descritiva e chama `sys.exit(1)`
    - Garantir que qualquer exceção interna também seja capturada, impressa e resulte em `sys.exit(1)`
    - _Requirements: 6.5, 6.7_

  - [x] 3.3 Auditar e aplicar defaults defensivos em todos os `.get()` do builder
    - `tooltip_dap` → default `""`
    - `alerta_instrutor` → default `None`
    - `screenshot_referencia` → default `None`
    - `coordenadas_relativas` → default `{}`
    - `id_treinamento` → fallback para `nome_aula`
    - Garantir que `temp_dir` seja removido em bloco `finally` mesmo em caso de erro
    - _Requirements: 2.4, 2.5, 2.7_

  - [ ]* 3.4 Escrever testes unitários para `scorm_builder_playbook_v2.py` (pré-renomeação)
    - Testar geração com roteiro mínimo → ZIP contém `imsmanifest.xml` e `index.html`
    - Testar `imsmanifest.xml` contém `nome_aula`
    - Testar `index.html` contém JSON de slides válido (`json.loads`)
    - Testar roteiro sem `tooltip_dap` → sem exceção
    - Testar roteiro sem `alerta_instrutor` → sem exceção
    - Testar nome do SCORM usa `limpar_nome(id_treinamento)`
    - _Requirements: 2.4, 2.5, 2.7, 2.9, 3.2, 3.3, 3.5, 1.4, 1.6_

- [x] 4. Checkpoint — Validar builders corrigidos antes da substituição
  - Garantir que todos os testes unitários das tarefas 2.4 e 3.4 passam
  - Confirmar que nenhum `limpar_nome` local permanece nos arquivos `_playbook_v3` e `_v2`
  - Perguntar ao usuário se há dúvidas antes de prosseguir com a substituição

- [x] 5. Criar `test_builders.py` com testes de propriedade (Hypothesis)
  - [x] 5.1 Implementar a estratégia `roteiros_validos()` com `@st.composite`
    - Gerar roteiros com 2–8 passos, campos opcionais presentes ou ausentes aleatoriamente
    - Incluir `seletor_hint` e `confianca_captura` para que `validar_roteiro` aprove
    - _Requirements: 2.8, 2.9_

  - [ ]* 5.2 Escrever property test — Property 1: PDF gerado para todo roteiro válido
    - `@given(roteiros_validos()) @settings(max_examples=100)`
    - Verificar que o arquivo existe e começa com `b"%PDF"`
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 1`
    - _Requirements: 2.8, 3.1_

  - [ ]* 5.3 Escrever property test — Property 2: SCORM gerado para todo roteiro válido
    - `@given(roteiros_validos()) @settings(max_examples=100)`
    - Verificar que o ZIP contém `imsmanifest.xml` e `index.html`
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 2`
    - _Requirements: 2.9, 3.2_

  - [ ]* 5.4 Escrever property test — Property 3: Nome do artefato derivado de `limpar_nome`
    - `@given(roteiros_validos()) @settings(max_examples=100)`
    - Verificar que o nome base do PDF e do SCORM é igual a `limpar_nome(id_treinamento)`
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 3`
    - _Requirements: 1.3, 1.4, 1.5, 1.6_

  - [ ]* 5.5 Escrever property test — Property 4: Campos opcionais ausentes não causam exceção
    - `@given(roteiros_validos())` com variante que remove campos opcionais aleatoriamente
    - Verificar que ambos os builders concluem sem exceção
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 4`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ]* 5.6 Escrever property test — Property 5: Contagem mínima de páginas do PDF
    - `@given(roteiros_validos()) @settings(max_examples=50)`
    - Verificar que o PDF tem pelo menos N + 2 páginas (capa + mapa + N cenas)
    - Usar `pypdf` ou `reportlab` para contar páginas
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 5`
    - _Requirements: 3.4_

  - [ ]* 5.7 Escrever property test — Property 6: Slides SCORM são JSON válido
    - `@given(roteiros_validos()) @settings(max_examples=100)`
    - Extrair o array de slides do `index.html` e verificar `json.loads` sem erro
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 6`
    - _Requirements: 3.5_

  - [ ]* 5.8 Escrever property test — Property 7: Título preservado no imsmanifest.xml
    - `@given(roteiros_validos()) @settings(max_examples=100)`
    - Verificar que `nome_aula` aparece no conteúdo do `imsmanifest.xml` dentro do ZIP
    - Comentário: `# Feature: pdf-scorm-playbook-builders, Property 7`
    - _Requirements: 3.3_

- [x] 6. Substituir `pdf_builder.py` e `scorm_builder.py` pelos builders corrigidos
  - Sobrescrever `pdf_builder.py` com o conteúdo de `pdf_builder_playbook_v3.py` (já corrigido)
  - Sobrescrever `scorm_builder.py` com o conteúdo de `scorm_builder_playbook_v2.py` (já corrigido)
  - Verificar que os arquivos `_playbook_v3.py` e `_v2.py` originais permanecem intactos (não remover)
  - _Requirements: 1.1, 1.2, 6.3_

- [x] 7. Checkpoint final — Garantir que todos os testes passam
  - Executar `pytest test_builders.py -v` e confirmar que todos os testes passam
  - Verificar que `pdf_builder.py` e `scorm_builder.py` não contêm definição local de `limpar_nome`
  - Perguntar ao usuário se há dúvidas antes de encerrar

## Notas

- Tarefas marcadas com `*` são opcionais e podem ser puladas para um MVP mais rápido
- Cada tarefa referencia requisitos específicos para rastreabilidade
- Os checkpoints garantem validação incremental antes de cada etapa destrutiva
- Os testes de propriedade usam Hypothesis (já presente no projeto via `.hypothesis/`)
- A substituição na tarefa 6 é a única operação destrutiva — as tarefas anteriores são seguras

# Implementation Plan: Project Cleanup and Organization

## Overview

Este plano implementa um sistema seguro e reversível para reorganizar a estrutura do projeto Senior Training OS. A implementação segue um modelo de execução em estágios com verificação após cada etapa, garantindo que toda funcionalidade seja preservada durante o processo de limpeza.

A abordagem é incremental e defensiva: cada estágio move um conjunto específico de arquivos, atualiza imports, verifica integridade, e só então prossegue para o próximo estágio. Um sistema de backup completo permite rollback em caso de problemas.

## Tasks

- [-] 1. Implementar estrutura base e modelos de dados
  - [x] 1.1 Criar módulo cleanup_project.py com estrutura principal
    - Implementar dataclasses: CleanupResult, MoveResult, TestResult, Stage
    - Criar enums para estágios e status
    - Implementar estrutura de logging com níveis apropriados
    - _Requirements: 5.1, 6.1_

  - [x] 1.2 Implementar BackupManager para sistema de backup/rollback
    - Criar método create_backup() que copia arquivos preservando estrutura
    - Implementar restore_backup() para rollback completo
    - Adicionar cleanup_old_backups() para manter apenas últimos 3 backups
    - Gerar metadata JSON com mapeamento de localizações originais
    - _Requirements: 5.5, 6.3_

  - [ ]* 1.3 Escrever testes unitários para BackupManager
    - Testar criação de backup com múltiplos arquivos
    - Testar restauração completa e parcial
    - Testar limpeza de backups antigos
    - Validar preservação de estrutura de diretórios
    - _Requirements: 5.1_

- [ ] 2. Implementar FileMover com atualização de imports
  - [ ] 2.1 Criar classe FileMover com método move_file()
    - Implementar movimentação segura de arquivos com verificações
    - Adicionar tracking de operações para rollback
    - Validar paths dentro do projeto root
    - Tratar conflitos de arquivos existentes
    - _Requirements: 1.2, 2.3, 3.3_

  - [ ] 2.2 Implementar update_imports() usando AST parsing
    - Parsear arquivos Python com ast.parse()
    - Identificar statements: import, from...import, sys.path.insert()
    - Calcular novos caminhos relativos baseado em destino
    - Atualizar imports preservando formatação original
    - Tratar casos especiais: sys.path.insert(0, str(Path(__file__).parent))
    - _Requirements: 1.2, 2.3_

  - [ ] 2.3 Implementar find_references() para detectar dependências
    - Escanear projeto buscando imports do arquivo movido
    - Usar grep ou ast para encontrar referências
    - Retornar lista de arquivos que precisam atualização
    - _Requirements: 1.2, 7.1_

  - [ ]* 2.4 Escrever testes para FileMover
    - Testar movimentação de arquivo simples
    - Testar atualização de sys.path.insert()
    - Testar atualização de imports relativos
    - Testar detecção de referências em outros arquivos
    - _Requirements: 1.4_

- [ ] 3. Implementar TestVerifier para validação de testes
  - [ ] 3.1 Criar classe TestVerifier com método run_tests()
    - Executar pytest via subprocess capturando output
    - Parsear resultados: total, passed, failed, skipped
    - Extrair nomes de testes descobertos
    - Capturar duração de execução
    - _Requirements: 5.1, 5.2_

  - [ ] 3.2 Implementar compare_results() para comparação de baseline
    - Comparar contagens: total, passed, failed
    - Verificar que nenhum teste foi perdido
    - Detectar novos testes ou testes duplicados
    - Gerar relatório de diferenças
    - _Requirements: 5.2, 8.4_

  - [ ] 3.3 Implementar verify_discovery() para validação de descoberta
    - Executar pytest --collect-only
    - Verificar que todos os testes esperados foram descobertos
    - Detectar testes duplicados entre tests/ e ingestion_pipeline/tests/
    - _Requirements: 8.4, 8.5_

  - [ ]* 3.4 Escrever testes para TestVerifier
    - Testar execução de pytest e parsing de resultados
    - Testar comparação de resultados com diferenças
    - Testar detecção de testes duplicados
    - _Requirements: 5.1_

- [ ] 4. Checkpoint - Verificar componentes base
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Implementar Stage 1: Move Test Files
  - [ ] 5.1 Criar método execute_stage_move_tests() no CleanupOrchestrator
    - Identificar 17 arquivos de teste no root directory
    - Verificar se tests/ directory existe, criar se necessário
    - Para cada arquivo: verificar duplicatas, mover, atualizar imports
    - Atualizar sys.path.insert(0, parent) para sys.path.insert(0, parent.parent)
    - Tratar conftest.py com cuidado especial (merge se necessário)
    - _Requirements: 1.1, 1.2, 1.3_

  - [ ] 5.2 Implementar verificação pós-movimentação de testes
    - Executar pytest para descobrir todos os testes
    - Comparar com baseline estabelecido antes da movimentação
    - Verificar que todos os 17 arquivos foram movidos
    - Confirmar que nenhum test file permanece no root
    - _Requirements: 1.4, 1.5_

  - [ ]* 5.3 Escrever teste de integração para Stage 1
    - Criar projeto mock com test files
    - Executar Stage 1 completo
    - Verificar movimentação e atualização de imports
    - Validar que testes continuam passando
    - _Requirements: 1.4_

- [ ] 6. Implementar Stage 2: Move Analysis Scripts
  - [ ] 6.1 Criar método execute_stage_move_analysis() no CleanupOrchestrator
    - Criar scripts/analysis/ directory se não existir
    - Identificar 5 scripts de análise no root
    - Mover cada script atualizando imports
    - Testar execução de cada script após movimentação
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 6.2 Implementar geração automática de README.md para scripts
    - Extrair docstrings de cada script movido
    - Detectar dependências via import analysis
    - Gerar README.md com template estruturado
    - Incluir: purpose, usage, dependencies, last modified
    - _Requirements: 2.4_

  - [ ] 6.3 Implementar verificação de execução de scripts
    - Tentar executar cada script com --help ou modo dry-run
    - Capturar erros de import ou execução
    - Reportar scripts que falharam verificação
    - _Requirements: 2.5_

  - [ ]* 6.4 Escrever teste de integração para Stage 2
    - Criar projeto mock com analysis scripts
    - Executar Stage 2 completo
    - Verificar geração de README.md
    - Validar execução dos scripts
    - _Requirements: 2.5_

- [ ] 7. Implementar Stage 3: Archive Exploratory Scripts
  - [ ] 7.1 Criar método execute_stage_archive_exploratory() no CleanupOrchestrator
    - Criar old_but_gold/exploratory/ directory
    - Identificar 6 scripts exploratórios no root
    - Para cada script: analisar se funcionalidade existe em ingestion_pipeline/
    - Mover scripts para old_but_gold/exploratory/
    - Adicionar header comment explicando razão do arquivamento
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ] 7.2 Implementar análise de funcionalidade duplicada
    - Comparar nomes de funções/classes entre script e ingestion_pipeline
    - Usar AST para extrair definições principais
    - Identificar correspondências e diferenças
    - Gerar mapeamento de migração
    - _Requirements: 3.2_

  - [ ] 7.3 Gerar MIGRATION.md com guia de migração
    - Para cada script arquivado: documentar razão, migration path, diferenças
    - Incluir exemplos de uso da nova implementação
    - Adicionar timestamp e metadata
    - _Requirements: 3.5_

  - [ ]* 7.4 Escrever teste de integração para Stage 3
    - Criar projeto mock com exploratory scripts
    - Executar Stage 3 completo
    - Verificar geração de MIGRATION.md
    - Validar header comments nos arquivos arquivados
    - _Requirements: 3.3, 3.5_

- [ ] 8. Checkpoint - Verificar stages de movimentação
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implementar Stage 4: Clean Generated Artifacts
  - [ ] 9.1 Criar método execute_stage_clean_artifacts() no CleanupOrchestrator
    - Identificar 2 arquivos gerados: erp_page_content.html, erp_pattern_analysis.json
    - Verificar se são realmente arquivos gerados (não source)
    - Determinar se devem ser removidos ou movidos para diagnostico_falhas/
    - Executar remoção ou movimentação
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 9.2 Atualizar .gitignore com padrões de artifacts
    - Adicionar padrões: erp_page_content.html, erp_pattern_analysis.json
    - Adicionar padrões genéricos: *_analysis.json, *_debug.html
    - Verificar que padrões não existem antes de adicionar
    - _Requirements: 4.4_

  - [ ] 9.3 Verificar que root está limpo de artifacts
    - Escanear root directory por arquivos HTML e JSON
    - Confirmar que apenas source files permanecem
    - Reportar qualquer artifact não esperado
    - _Requirements: 4.5_

- [ ] 10. Implementar Stage 5: Update Documentation
  - [ ] 10.1 Criar classe DocumentationUpdater
    - Implementar scan_references() para encontrar referências a arquivos movidos
    - Usar regex para detectar padrões: ./test_*.py, [text](path), code blocks
    - Construir mapa de referências: {doc_path: [references]}
    - _Requirements: 7.1_

  - [ ] 10.2 Implementar update_reference() para atualizar paths
    - Para cada referência encontrada: calcular novo path
    - Atualizar preservando formatação do markdown
    - Tratar diferentes formatos: links, code blocks, plain text
    - _Requirements: 7.2, 7.3_

  - [ ] 10.3 Implementar verify_links() para validação
    - Verificar que todos os paths atualizados apontam para arquivos existentes
    - Gerar lista de broken links se houver
    - Reportar referências que não puderam ser atualizadas
    - _Requirements: 7.5_

  - [ ] 10.4 Escanear e atualizar documentação do projeto
    - Escanear: README.md, docs/, ingestion_pipeline/README.md, ingestion_pipeline/QUICKSTART.md
    - Aplicar atualizações usando DocumentationUpdater
    - Verificar links após atualização
    - _Requirements: 7.3, 7.4_

  - [ ]* 10.5 Escrever testes para DocumentationUpdater
    - Testar detecção de referências em markdown
    - Testar atualização de diferentes formatos de path
    - Testar verificação de links
    - _Requirements: 7.5_

- [ ] 11. Implementar CleanupOrchestrator principal
  - [ ] 11.1 Criar método pre_flight_check()
    - Verificar que git working directory está limpo
    - Verificar que Python environment está ativo
    - Verificar que pytest está disponível
    - Verificar que não há backups conflitantes
    - _Requirements: 5.1_

  - [ ] 11.2 Implementar método execute() com workflow completo
    - Executar pre_flight_check()
    - Criar backup com BackupManager
    - Estabelecer baseline executando test suite
    - Executar cada stage em sequência
    - Após cada stage: verificar e comparar com baseline
    - Se falha: trigger rollback automático
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 11.3 Implementar método rollback()
    - Detectar condições de rollback: test failure, import error, user abort
    - Usar BackupManager.restore_backup()
    - Verificar completude da restauração
    - Executar test suite para confirmar restauração
    - Gerar relatório de rollback
    - _Requirements: 5.5_

  - [ ] 11.4 Implementar generate_report() para CLEANUP_REPORT.md
    - Gerar relatório estruturado com todas as seções
    - Incluir: summary, stage details, verification results, files kept
    - Adicionar tabelas formatadas para files moved/archived/removed
    - Incluir métricas: duration, test results, documentation updates
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 12. Implementar CLI e modos de execução
  - [ ] 12.1 Criar interface CLI com argparse
    - Adicionar flags: --dry-run, --interactive, --auto
    - Adicionar opções: --rollback, --restore-backup
    - Implementar help text descritivo
    - _Requirements: 5.1_

  - [ ] 12.2 Implementar modo dry-run
    - Simular todas as operações sem modificar arquivos
    - Gerar preview report mostrando o que seria mudado
    - Mostrar estatísticas: files to move, imports to update, etc.
    - _Requirements: 5.1_

  - [ ] 12.3 Implementar modo interactive
    - Prompt para confirmação antes de cada stage
    - Permitir skip de stages individuais
    - Oferecer opção de rollback após cada stage
    - Mostrar progress em tempo real
    - _Requirements: 5.1_

  - [ ] 12.4 Implementar modo automated
    - Executar todos os stages automaticamente
    - Stop on first error com rollback automático
    - Gerar relatório final completo
    - _Requirements: 5.1_

- [ ] 13. Checkpoint - Verificar orchestrator completo
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 14. Implementar logging e progress reporting
  - [ ] 14.1 Configurar sistema de logging
    - Criar logger com níveis: DEBUG, INFO, WARNING, ERROR
    - Configurar output para console e arquivo .cleanup_<timestamp>.log
    - Implementar formatação clara com timestamps
    - _Requirements: 6.5_

  - [ ] 14.2 Implementar progress reporting no console
    - Mostrar barra de progresso para operações em lote
    - Exibir checkmarks (✓) para operações bem-sucedidas
    - Mostrar warnings (⚠) e errors (✗) inline
    - Incluir estatísticas em tempo real
    - _Requirements: 6.5_

  - [ ] 14.3 Implementar coleta de métricas
    - Coletar: files moved, imports updated, test execution time, total duration
    - Calcular: backup size, documentation updates count
    - Armazenar métricas em CleanupResult
    - _Requirements: 6.5_

- [ ] 15. Implementar validações de segurança
  - [ ] 15.1 Adicionar validação de paths
    - Verificar que todos os paths estão dentro do project root
    - Prevenir directory traversal attacks
    - Detectar e rejeitar symlinks suspeitos
    - _Requirements: 5.1_

  - [ ] 15.2 Implementar verificação de integridade de backup
    - Calcular checksums de arquivos antes do backup
    - Verificar checksums após restore
    - Validar que permissions foram preservadas
    - _Requirements: 5.5_

  - [ ] 15.3 Adicionar validação de import safety
    - Usar AST parsing ao invés de exec() para análise
    - Validar que import paths são seguros
    - Prevenir code injection via imports maliciosos
    - _Requirements: 1.2, 2.3_

- [ ] 16. Implementar preservação de ingestion_pipeline
  - [ ] 16.1 Adicionar verificação de exclusão para ingestion_pipeline/tests/
    - Detectar testes em ingestion_pipeline/tests/
    - Garantir que esses testes NÃO sejam movidos
    - Documentar preservação no relatório
    - _Requirements: 8.1, 8.3_

  - [ ] 16.2 Verificar independência dos testes do ingestion_pipeline
    - Executar: pytest ingestion_pipeline/tests/ isoladamente
    - Verificar que testes rodam sem dependências externas
    - Confirmar que conftest.py separado funciona se existir
    - _Requirements: 8.2_

  - [ ] 16.3 Validar ausência de duplicatas entre test directories
    - Executar: pytest --collect-only | grep "test_" | sort | uniq -d
    - Reportar qualquer teste duplicado encontrado
    - Sugerir renomeação se duplicatas existirem
    - _Requirements: 8.5_

- [ ] 17. Testes de integração end-to-end
  - [ ]* 17.1 Criar projeto mock completo para teste
    - Criar estrutura com test files, analysis scripts, exploratory scripts
    - Adicionar artifacts gerados
    - Criar documentação com referências
    - Incluir ingestion_pipeline mock com testes próprios
    - _Requirements: 5.1_

  - [ ]* 17.2 Testar workflow completo em modo dry-run
    - Executar cleanup em modo dry-run no projeto mock
    - Verificar que nenhum arquivo foi modificado
    - Validar que preview report está correto
    - _Requirements: 5.1_

  - [ ]* 17.3 Testar workflow completo em modo automated
    - Executar cleanup em modo automated no projeto mock
    - Verificar que todos os arquivos foram movidos corretamente
    - Validar que imports foram atualizados
    - Confirmar que testes passam após cleanup
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 17.4 Testar rollback após falha simulada
    - Injetar falha em um dos stages
    - Verificar que rollback é triggered automaticamente
    - Confirmar que todos os arquivos foram restaurados
    - Validar que testes passam após rollback
    - _Requirements: 5.5_

- [ ] 18. Documentação e finalização
  - [ ] 18.1 Criar documentação de uso no README do script
    - Documentar prerequisites: clean git state, venv active
    - Explicar modos de execução: dry-run, interactive, automated
    - Incluir exemplos de uso
    - Documentar procedimento de rollback
    - _Requirements: 6.1_

  - [ ] 18.2 Adicionar docstrings completas em todas as classes e métodos
    - Documentar parâmetros, retornos, exceções
    - Incluir exemplos de uso onde apropriado
    - Seguir convenções Python (Google ou NumPy style)
    - _Requirements: 6.1_

  - [ ] 18.3 Criar guia de troubleshooting
    - Documentar erros comuns e soluções
    - Explicar como interpretar logs
    - Incluir checklist de verificação pré-execução
    - Documentar quando usar cada modo de execução
    - _Requirements: 6.5_

- [ ] 19. Final checkpoint - Verificação completa do sistema
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marcadas com `*` são opcionais e podem ser puladas para MVP mais rápido
- Cada task referencia requirements específicos para rastreabilidade
- Checkpoints garantem validação incremental
- Testes de propriedade não são aplicáveis (não há Correctness Properties no design)
- Foco em testes unitários e de integração para componentes críticos
- Sistema de backup/rollback é crítico - implementar e testar cedo
- Preservação da estrutura do ingestion_pipeline é mandatória
- Atualização de imports é complexa - usar AST parsing, não regex
- Modo dry-run deve ser usado primeiro em qualquer execução real

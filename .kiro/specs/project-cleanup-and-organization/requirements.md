# Requirements Document

## Introduction

Este documento define os requisitos para organizar e limpar arquivos de teste e scripts temporários no projeto Senior Training OS. O objetivo é melhorar a manutenibilidade do projeto movendo arquivos de teste para o diretório `tests/`, scripts de análise para `scripts/analysis/`, e arquivando ou removendo código exploratório obsoleto.

## Glossary

- **Root_Directory**: O diretório raiz do projeto Senior Training OS
- **Test_Files**: Arquivos Python que começam com `test_` ou são configurações de teste (conftest.py)
- **Analysis_Scripts**: Scripts Python usados para análise, debug ou investigação (analyze_*, check_*, debug_*, investigate_*)
- **Exploratory_Scripts**: Scripts Python criados durante exploração de funcionalidades (enhanced_*, fix_*, intelligent_*, manual_*)
- **Generated_Artifacts**: Arquivos gerados por scripts (HTML, JSON) que não fazem parte do código-fonte
- **Tests_Directory**: O diretório `tests/` que contém os testes organizados do projeto
- **Scripts_Directory**: O diretório `scripts/` que contém scripts utilitários
- **Analysis_Subdirectory**: O subdiretório `scripts/analysis/` para scripts de análise e debug
- **Ingestion_Pipeline**: O módulo `ingestion_pipeline/` que contém o código de produção do pipeline de ingestão
- **Project_Organizer**: O sistema responsável por mover e organizar arquivos

## Requirements

### Requirement 1: Move Test Files to Tests Directory

**User Story:** Como desenvolvedor, eu quero que todos os arquivos de teste estejam no diretório `tests/`, para que eu possa encontrar e executar testes facilmente.

#### Acceptance Criteria

1. WHEN THE Project_Organizer executes, THE System SHALL move all Test_Files from Root_Directory to Tests_Directory
2. THE System SHALL preserve the functionality of moved test files by updating import statements if necessary
3. THE System SHALL move conftest.py from Root_Directory to Tests_Directory
4. FOR ALL moved test files, running pytest SHALL produce the same test results as before the move
5. THE System SHALL verify that no test files remain in Root_Directory after the move

### Requirement 2: Organize Analysis and Debug Scripts

**User Story:** Como desenvolvedor, eu quero que scripts de análise e debug estejam organizados em um subdiretório dedicado, para que eu possa distinguir entre scripts de produção e scripts de investigação.

#### Acceptance Criteria

1. THE System SHALL create Analysis_Subdirectory if it does not exist
2. WHEN THE Project_Organizer executes, THE System SHALL move all Analysis_Scripts from Root_Directory to Analysis_Subdirectory
3. THE System SHALL preserve the functionality of moved scripts by updating import statements if necessary
4. THE System SHALL create a README.md in Analysis_Subdirectory documenting the purpose of each script
5. FOR ALL moved scripts, execution SHALL produce the same results as before the move

### Requirement 3: Archive or Remove Exploratory Scripts

**User Story:** Como desenvolvedor, eu quero que scripts exploratórios obsoletos sejam arquivados ou removidos, para que o diretório raiz contenha apenas código de produção ativo.

#### Acceptance Criteria

1. THE System SHALL identify all Exploratory_Scripts in Root_Directory
2. FOR EACH Exploratory_Script, THE System SHALL determine if the functionality is implemented in Ingestion_Pipeline
3. IF an Exploratory_Script functionality is implemented in Ingestion_Pipeline, THEN THE System SHALL move the script to `old_but_gold/exploratory/`
4. IF an Exploratory_Script functionality is not implemented and is still needed, THEN THE System SHALL keep the script in Root_Directory with a comment explaining its purpose
5. THE System SHALL create a migration document in `old_but_gold/exploratory/MIGRATION.md` mapping old scripts to new implementations

### Requirement 4: Clean Generated Artifacts

**User Story:** Como desenvolvedor, eu quero que arquivos gerados temporários sejam removidos ou movidos para diretórios apropriados, para que o diretório raiz contenha apenas código-fonte.

#### Acceptance Criteria

1. THE System SHALL identify all Generated_Artifacts in Root_Directory
2. WHEN a Generated_Artifact is temporary debug output, THE System SHALL remove it
3. WHEN a Generated_Artifact is useful for reference, THE System SHALL move it to `diagnostico_falhas/` or appropriate directory
4. THE System SHALL add Generated_Artifacts patterns to .gitignore if not already present
5. THE System SHALL verify that no HTML or JSON artifacts remain in Root_Directory after cleanup

### Requirement 5: Verify Project Integrity After Cleanup

**User Story:** Como desenvolvedor, eu quero garantir que o projeto continue funcionando após a reorganização, para que eu possa confiar que nenhuma funcionalidade foi quebrada.

#### Acceptance Criteria

1. AFTER all moves are complete, THE System SHALL run the complete test suite
2. THE System SHALL verify that all tests pass with the same results as before cleanup
3. THE System SHALL verify that the main application (app.py) starts successfully
4. THE System SHALL verify that ingestion_pipeline can be imported and executed
5. IF any verification fails, THEN THE System SHALL provide a detailed error report with rollback instructions

### Requirement 6: Document Cleanup Changes

**User Story:** Como desenvolvedor, eu quero documentação clara das mudanças realizadas, para que eu possa entender o que foi movido e por quê.

#### Acceptance Criteria

1. THE System SHALL create a CLEANUP_REPORT.md in the Root_Directory
2. THE CLEANUP_REPORT.md SHALL list all files moved with their old and new locations
3. THE CLEANUP_REPORT.md SHALL list all files removed with justification
4. THE CLEANUP_REPORT.md SHALL list all files kept in Root_Directory with justification
5. THE CLEANUP_REPORT.md SHALL include verification results and any issues encountered

### Requirement 7: Update Documentation References

**User Story:** Como desenvolvedor, eu quero que toda documentação seja atualizada para refletir a nova estrutura, para que instruções e referências permaneçam corretas.

#### Acceptance Criteria

1. THE System SHALL scan all markdown files for references to moved files
2. WHEN a reference to a moved file is found, THE System SHALL update the path
3. THE System SHALL update README.md if it contains references to moved files
4. THE System SHALL update any documentation in docs/ directory
5. THE System SHALL verify that all updated references point to existing files

### Requirement 8: Preserve Ingestion Pipeline Tests

**User Story:** Como desenvolvedor, eu quero garantir que os testes do ingestion_pipeline permaneçam em sua estrutura atual, para que o módulo mantenha sua independência.

#### Acceptance Criteria

1. THE System SHALL NOT move tests from ingestion_pipeline/tests/ directory
2. THE System SHALL verify that ingestion_pipeline tests continue to run independently
3. THE System SHALL document in CLEANUP_REPORT.md that ingestion_pipeline tests were preserved
4. THE System SHALL verify that pytest can discover and run both root tests/ and ingestion_pipeline/tests/
5. THE System SHALL ensure no duplicate test names exist between the two test directories

## Files Identified for Organization

### Test Files to Move (17 files):
- test_aura_search.py
- test_builders.py
- test_erp_discovery.py
- test_final_search.py
- test_ged_access.py
- test_gestao_page.py
- test_important_urls_pipeline.py
- test_important_urls.py
- test_openai.py
- test_recursive_erp.py
- test_single_url.py
- test_sitemap_modules.py
- test_skill_memory.py
- test_spa_discovery.py
- conftest.py

### Analysis Scripts to Move (5 files):
- analyze_erp_patterns.py
- analyze_sitemap_structure.py
- check_sitemap_content.py
- debug_crawler.py
- debug_erp_discovery.py

### Exploratory Scripts to Archive (6 files):
- enhanced_crawler.py
- enhanced_erp_discovery.py
- fix_erp_discovery.py
- intelligent_spa_crawler.py
- investigate_sitemaps.py
- manual_important_urls.py

### Generated Artifacts to Clean (2 files):
- erp_page_content.html
- erp_pattern_analysis.json

## Success Criteria

The cleanup is considered successful when:

1. All test files are in tests/ directory and passing
2. All analysis scripts are in scripts/analysis/ with documentation
3. All exploratory scripts are archived with migration documentation
4. No generated artifacts remain in root directory
5. All tests pass after reorganization
6. Main application starts successfully
7. Complete documentation of changes exists
8. All documentation references are updated

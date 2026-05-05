# Changelog

Todas as mudanças notáveis neste projeto serão documentadas neste arquivo.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.0.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [v1.0.0-consolidation] - 2026-04-29

### 🎉 Release Milestone - Consolidação de Features Críticas

Esta release marca a consolidação de múltiplas features críticas do Training OS, estabelecendo uma base sólida para futuras evoluções.

### ✨ Features Principais Adicionadas

#### Segurança e CI/CD
- **Repo Security Hardening**: Implementação de práticas de segurança no repositório
- **CI Setup Completo**: Pipeline de integração contínua configurado
- **Ruff Linting**: Configuração de linting com ruff.toml para qualidade de código

#### Pipeline de Ingestão de Conhecimento (RAG)
- **Web Knowledge Ingestion Pipeline**: Sistema ETL completo para extração de documentação web
  - Descoberta automática via sitemap.xml
  - Extração semântica com conversão HTML → Markdown
  - Segregação por namespace (módulos HCM, Financeiro, etc.)
  - Modo incremental com cache local
  - Resiliência com retry e backoff exponencial
- **Integração com Aura DAP**: Busca contextual por namespace
- **Documentação Completa**: README, ARCHITECTURE, QUICKSTART e SPA_DISCOVERY

#### ERP Discovery Enhancement
- **Mapeamento Manual de URLs**: Sistema abrangente de mapeamento de URLs importantes
- **Intelligent SPA Crawler**: Crawler inteligente para Single Page Applications
- **Pattern Analysis**: Análise de padrões de navegação no ERP

#### Consolidação de Captura Cognitiva
- **Monitor Auxiliar Automático**: Detecção e uso automático de monitor secundário
- **Melhorias na Qualidade de Vídeo**: Otimizações no processo de gravação
- **Gap Inicial de Narração**: Sincronização melhorada entre áudio e vídeo
- **Botão PLAY**: Interface melhorada para controle de gravação

#### Otimização do Lego Builder
- **Display Optimization**: Saída configurável com verbosidade ajustável
- **Enriquecimento Seletivo**: Processamento otimizado de ações
- **Paralelização em Lotes**: Performance melhorada no processamento

### 🤖 Aura DAP - Melhorias Significativas

#### Redesign do Painel de Chat
- **Nova Interface**: Painel de chat completamente redesenhado
- **Histórico de Conversas**: Persistência e navegação em conversas anteriores
- **UX Melhorada**: Experiência de usuário aprimorada

#### Hardening da Arquitetura
- **Arquitetura Modular**: Reorganização completa da extensão
- **Separação de Responsabilidades**: Código mais manutenível e testável
- **Contratos Bem Definidos**: Interfaces claras entre módulos

#### Correções Críticas
- **Fix 422 no Endpoint de Analytics**: Correção de erro na extensão
- **Feedback Icons Bug**: Correção de bug nos ícones de feedback

### 🐛 Bug Fixes Críticos

#### Timing e Sincronização
- **Coordinates Identity Verification**: Correção de bug de timing na verificação de identidade de coordenadas
- **WebSocket Disconnect**: Fix de desconexão WebSocket com cancelamento do robô
- **Dual Tenant Credentials**: Suporte adequado para credenciais de múltiplos tenants

#### Menu de Contexto e UI
- **ngx-contextmenu**: Múltiplas correções para detecção de menu de contexto
  - Timeout ajustado para 2000ms
  - Sleep de 300ms para animação de entrada
  - Busca em todos os frames
  - Seletor único otimizado
- **CDK Overlay**: Busca no DOM principal primeiro
- **Animação de Cursor**: Correção de animação no menu de contexto

#### Iframes e Elementos
- **Menu Contexto em Iframes**: Correção de detecção em iframes
- **Element Location in Iframes**: Correção de localização de elementos em iframes
- **Dialog Sim**: Correção de detecção de diálogos de confirmação

#### Maximização e Display
- **F11 após PLAY**: Maximização via F11 após início da gravação
- **CDP Browser.setWindowBounds**: Maximização via Chrome DevTools Protocol
- **Overlay PLAY Centralizado**: Posicionamento correto do overlay

### 📋 Roadmaps Implementados

#### Training OS Roadmap (Fases 1-3)
- **Fase 1**: Estabilização da plataforma
- **Fase 2**: Separação de plataforma
- **Fase 3**: Productização

#### Market-Driven Roadmap
- **Fase 1**: Smart Blur, Analytics, Shareable Link
- **Fase 2**: Magic Updates, Multi-idioma, Guided Execution, Onboarding
- **Fase 3**: Smart Tips, Adaptive Learning, NPS

#### Playback Resilience Roadmap
- **Cascata Reordenada**: Estratégias de fallback otimizadas
- **Template Matching Visual**: Matching visual de templates
- **Telemetria Granular**: Telemetria detalhada de execução
- **Estabilidade de Áudio**: Melhorias na sincronização de áudio

### 🧪 Testes e Qualidade

#### Property-Based Testing
- **Bug Condition Tests**: Testes de exploração de condições de bug
- **Preservation Tests**: Testes de preservação de comportamento
- **Integration Tests**: Testes de integração completos
- **Regression Tests**: Testes de regressão

#### Novos Módulos de Teste
- `tests/test_bugfix_exploration.py`
- `tests/test_bugfix_preservation.py`
- `tests/test_coordinates_identity_bug.py`
- `tests/test_iframe_element_location_bug_exploration.py`
- `tests/test_iframe_element_location_preservation.py`
- `tests/test_robot_execution_wrong_clicks_exploration.py`
- `tests/test_robot_execution_wrong_clicks_preservation.py`
- `tests/test_vision_engine_bug_condition.py`
- `tests/test_vision_telemetry_properties.py`
- `tests/test_websocket_disconnect.py`
- E muitos outros...

### 📚 Specs Documentados

25+ specs completos em `.kiro/specs/`, incluindo:
- `aura-chat-panel-v2`
- `aura-dap-hardening`
- `aura-dap-restructure`
- `consolidacao-captura-cognitiva`
- `lego-builder-display-optimization`
- `next-legacy-diamond-integration`
- `playback-resilience-roadmap`
- `repo-security-and-ci-setup`
- `robot-element-location-failure`
- `robot-execution-wrong-clicks`
- `training-os-roadmap`
- `web-knowledge-ingestion-rag`
- `suporte-acentuacao-pt-br`

### 🏗️ Novos Módulos e Arquivos

#### Core Modules
- `job_registry.py`: Registro e gerenciamento de jobs
- `legacy_bridge.py`: Ponte para integração com sistemas legados
- `next_integration.py`: Integração Next Legacy Diamond
- `brain_backend.py`: Backend para memória do sistema
- `skill_memory.py`: Memória de habilidades aprendidas
- `skill_models.py`: Modelos de dados para habilidades
- `storage_adapter.py`: Adaptador de armazenamento
- `promotion_engine.py`: Engine de promoção de skills
- `promotion_models.py`: Modelos de promoção
- `score_engine.py`: Engine de pontuação
- `roi_tracker.py`: Rastreamento de ROI
- `triage_models.py`: Modelos de triagem
- `triage_pipeline.py`: Pipeline de triagem

#### Shadow System
- `shadow_builder.py`: Construtor de shadow exports
- `shadow_schema.py`: Schema para shadow system
- `shadow_exports/`: Diretório com exports shadow
- `sim_links/`: Diretório com sim links

#### Observed Actions
- `observed_action_adapter.py`: Adaptador para ações observadas
- `observed_action_models.py`: Modelos de ações observadas

#### Contracts
- `contracts/capture_adapter.py`: Contrato para adaptador de captura
- `contracts/step_model.json`: Modelo JSON para steps

#### Documentation
- `docs/DUAL_SHADOW_SCHEMA.md`
- `docs/LEGACY_NEXT_INTEGRATION.md`
- `docs/OBSERVED_ACTION_ADAPTER.md`
- `docs/PROMOTION_GATES.md`
- `docs/SKILL_PROMOTION_POLICY.md`
- `docs/runbook-git-history-cleanup.md`

### 🔧 Melhorias Técnicas

#### Arquitetura
- **Separação de Responsabilidades**: Módulos mais coesos e desacoplados
- **Contratos Bem Definidos**: Interfaces claras entre componentes
- **Testabilidade**: Código mais testável com mocks e stubs

#### Performance
- **Paralelização**: Processamento paralelo em lotes
- **Cache Inteligente**: Cache local para evitar reprocessamento
- **Otimização de Queries**: Queries mais eficientes no Pinecone

#### Manutenibilidade
- **Documentação**: Documentação abrangente de módulos e APIs
- **Specs**: Especificações detalhadas de features e bugfixes
- **Testes**: Cobertura de testes significativamente aumentada

### 📊 Estatísticas

- **10,609 arquivos** processados durante o merge
- **~62,900 linhas** adicionadas
- **~1,400 linhas** removidas
- **34 commits** consolidados
- **25+ specs** documentados
- **50+ novos testes** implementados

### 🔄 Mudanças de Breaking

Nenhuma mudança de breaking nesta release. Todas as alterações são retrocompatíveis.

### 🚀 Próximos Passos

- Implementação de features do roadmap Fase 4
- Expansão do pipeline de ingestão para mais fontes
- Melhorias contínuas na resiliência do playback
- Expansão da cobertura de testes

---

## [Unreleased]

### Em Desenvolvimento
- Features futuras serão listadas aqui

---

## Formato de Versionamento

Este projeto usa [Semantic Versioning](https://semver.org/lang/pt-BR/):
- **MAJOR**: Mudanças incompatíveis na API
- **MINOR**: Funcionalidades adicionadas de forma retrocompatível
- **PATCH**: Correções de bugs retrocompatíveis

## Categorias de Mudanças

- **✨ Added**: Novas features
- **🔧 Changed**: Mudanças em funcionalidades existentes
- **🗑️ Deprecated**: Features que serão removidas em breve
- **🔥 Removed**: Features removidas
- **🐛 Fixed**: Correções de bugs
- **🔒 Security**: Correções de vulnerabilidades

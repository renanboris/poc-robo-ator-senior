# Roadmap Orientado por Mercado — Senior Training OS

## Contexto

Este documento é resultado de uma análise cruzada entre a pesquisa competitiva realizada (ScribeHow, Tango, Iorad, Guidde, UserGuiding, Usetiful, Driveway, GetDemo) e o estado atual do Senior Training OS.

O objetivo não é copiar concorrentes. É identificar **gaps reais de valor** que o mercado já validou e que o Training OS pode implementar com vantagem competitiva — porque já tem o roteiro como fonte única de verdade, já tem Playwright, já tem Gemini, já tem SCORM, já tem Aura DAP.

---

## Análise: O que o Training OS já tem (e os concorrentes não)

Antes de listar o que falta, é importante registrar o que o projeto já entrega que **nenhum concorrente entrega sozinho**:

| Capacidade | Training OS | ScribeHow | Tango | Iorad | Guidde |
|---|---|---|---|---|---|
| Vídeo com narração IA | ✅ | ❌ | ❌ | ❌ | ✅ |
| SCORM interativo | ✅ | ❌ | ❌ | ✅ | ❌ |
| PDF playbook | ✅ | ✅ | ❌ | ❌ | ❌ |
| DAP in-app (Aura) | ✅ | ❌ | ✅ (Nuggets) | ❌ | ❌ |
| RAG sobre manuais | ✅ | ❌ | ❌ | ❌ | ❌ |
| Self-healing de UI | ✅ | ❌ | ❌ | ❌ | ❌ |
| Roteiro como fonte única | ✅ | ❌ | ❌ | ❌ | ❌ |

O Training OS é o único produto que fecha o ciclo completo: captura → roteiro → vídeo + SCORM + PDF + DAP.

---

## Gaps Identificados (priorizados por impacto × esforço)

### Gap 1 — Privacidade de Dados na Gravação (Smart Blur)
**Fonte:** ScribeHow, Iorad  
**Problema atual:** O Training OS grava telas sem nenhum mecanismo de redação automática de dados sensíveis (senhas, CPFs, tokens, dados pessoais visíveis em campos).  
**Impacto:** Bloqueador para adoção enterprise. Qualquer cliente com política de segurança vai rejeitar treinamentos com dados reais expostos.

### Gap 2 — Analytics de Engajamento por Passo
**Fonte:** Tango, Guidde, UserGuiding  
**Problema atual:** O Training OS não sabe quem assistiu o treinamento, até onde chegou, qual passo foi repetido mais vezes, ou onde o usuário desistiu.  
**Impacto:** Sem analytics, o produto é cego. Não há como medir eficácia, identificar onde o treinamento falha, ou justificar ROI para o cliente.

### Gap 3 — Modo de Execução Guiada (Copiloto In-App)
**Fonte:** Tango Nuggets, UserGuiding  
**Problema atual:** A Aura DAP responde perguntas, mas não guia o usuário passo a passo dentro do Senior X em tempo real. O treinamento é passivo (vídeo/SCORM), não ativo (copiloto).  
**Impacto:** É a diferença entre "assistir um tutorial" e "ter um instrutor ao lado". Tango tem 400k installs por isso.

### Gap 4 — Atualização Parcial de Roteiro (Magic Updates)
**Fonte:** Guidde Magic Updates, ScribeHow Inline Update  
**Problema atual:** Quando a UI do Senior X muda (e muda frequentemente), o operador precisa regravar o treinamento inteiro. Não existe mecanismo de diff + regeneração seletiva.  
**Impacto:** Custo de manutenção alto. Treinamentos ficam desatualizados. Operadores perdem confiança no sistema.

### Gap 5 — Multi-idioma Automático
**Fonte:** Guidde (100+ idiomas)  
**Problema atual:** O Training OS gera narração apenas em pt-BR. Clientes com operações em outros países (ES, EN) precisam regravar tudo.  
**Impacto:** Bloqueador para expansão internacional e para clientes multinacionais do ecossistema Senior.

### Gap 6 — Shareable Training Link + Progress Tracking
**Fonte:** Driveway, Tango  
**Problema atual:** Não existe URL pública para compartilhar um treinamento por e-mail. Não existe rastreamento de quem completou cada módulo.  
**Impacto:** Sem isso, o Training OS não pode ser usado como LMS leve. O cliente precisa de outra ferramenta para distribuir e rastrear.

### Gap 7 — Modo Interativo Simulado (Sandbox Clicável)
**Fonte:** Iorad Interactive Mode, Driveway Demo Mode  
**Problema atual:** O SCORM atual tem interatividade básica (clicar no passo certo). Não existe um modo onde o treinando simula executar o fluxo completo sem risco no sistema real.  
**Impacto:** O SCORM atual é mais "quiz guiado" do que "simulação real". Iorad cobra $200/mês por isso.

### Gap 8 — Onboarding Gamificado + Segmentação de Conteúdo
**Fonte:** UserGuiding  
**Problema atual:** Não existe checklist de onboarding injetável no Senior X. Não existe lógica de mostrar módulos diferentes por perfil de usuário (Admin vs Analista vs Diretor).  
**Impacto:** Onboarding sem gamificação tem taxa de conclusão baixa. Segmentação é básica para qualquer DAP moderno.

### Gap 9 — Smart Tips de Hesitação
**Fonte:** Usetiful Smart Tips  
**Problema atual:** A Aura só responde quando o usuário pergunta. Não existe detecção proativa de hesitação (usuário parado em um campo por N segundos).  
**Impacto:** A diferença entre DAP reativo e DAP proativo. Usetiful foi adquirido pelo Fullstory por isso.

### Gap 10 — Adaptive Learning Path
**Fonte:** GetDemo Branching  
**Problema atual:** O roteiro é linear. Não existe lógica de ramificação: se o usuário já domina o passo 1, pula para o 3; se travar, aprofunda com sub-passos.  
**Impacto:** Treinamentos lineares são ineficientes para usuários com níveis diferentes de maturidade.

---

## Requisitos por Fase

---

## Fase 1 — Fundação de Confiança (Bloqueadores Enterprise)
*Prazo sugerido: 6–8 semanas*

### Requisito 1: Smart Blur Automático na Gravação

**User Story:** Como operador de treinamento, quero que campos sensíveis (senhas, CPFs, tokens, dados pessoais) sejam automaticamente detectados e borrados nos screenshots e no vídeo final, para que eu possa distribuir treinamentos sem expor dados reais.

#### Critérios de Aceitação

1. THE `Capture_Module` SHALL detectar campos de senha (`type="password"`) e aplicar blur automático no `screenshot_referencia` antes de salvar no roteiro.
2. THE `Video_Pipeline` SHALL aplicar blur nas regiões marcadas como sensíveis durante a composição do vídeo final em `main.py`.
3. THE system SHALL suportar uma lista configurável de seletores CSS adicionais para blur manual via `.env` (`BLUR_SELECTORS`).
4. WHEN um campo sensível for detectado e borrado, THE `Capture_Module` SHALL registrar `logger.info` com o id da ação e o tipo de campo, sem registrar o valor.
5. THE blur SHALL ser aplicado como retângulo sólido (não gaussiano) para garantir que o dado não seja recuperável por processamento de imagem.
6. FOR ALL screenshots existentes no roteiro sem blur, THE system SHALL oferecer endpoint `POST /api/roteiros/{id}/aplicar-blur` para reprocessamento.

---

### Requisito 2: Analytics de Engajamento por Passo

**User Story:** Como gestor de treinamento, quero saber quais passos do treinamento os usuários mais repetem, onde desistem, e qual a taxa de conclusão por módulo, para que eu possa identificar onde o treinamento falha e justificar ROI.

#### Critérios de Aceitação

1. THE `SCORM_Player` SHALL emitir eventos de progresso para cada passo concluído via `LMSSetValue("cmi.interactions")` no padrão SCORM 1.2.
2. THE `App_Module` SHALL implementar endpoint `POST /api/analytics/evento` para receber eventos de progresso do player SCORM e da extensão Aura.
3. THE `App_Module` SHALL persistir eventos de engajamento em tabela `analytics_eventos` no `brain.db` com campos: `roteiro_id`, `passo_id`, `usuario_id`, `evento` (iniciou/completou/repetiu/abandonou), `ts`.
4. THE `App_Module` SHALL expor endpoint `GET /api/analytics/{roteiro_id}` retornando: taxa de conclusão, tempo médio por passo, passos com maior taxa de repetição, e passo de maior abandono.
5. WHEN um usuário completar todos os passos de um roteiro, THE system SHALL registrar evento `"completou"` com timestamp.
6. THE analytics SHALL funcionar sem autenticação de usuário individual — usar `usuario_id` anônimo baseado em hash do IP + user-agent quando não houver sessão.

---

### Requisito 3: Shareable Training Link

**User Story:** Como operador de treinamento, quero gerar uma URL pública para um treinamento e enviá-la por e-mail para o treinando acessar no próprio ritmo, com rastreamento de progresso, para que eu não precise de um LMS externo para distribuição básica.

#### Critérios de Aceitação

1. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/gerar-link` que retorna uma URL única e de curta duração (TTL configurável, padrão 30 dias) para acesso ao player SCORM.
2. THE link SHALL ser acessível via `GET /play/{token}` sem autenticação, servindo o player SCORM diretamente.
3. THE `App_Module` SHALL persistir links gerados em tabela `sim_links` no `brain.db` com campos: `token`, `roteiro_id`, `criado_em`, `expira_em`, `total_acessos`.
4. WHEN o link for acessado, THE system SHALL registrar o acesso em `analytics_eventos` com `evento="iniciou"`.
5. WHEN o link expirar, THE `GET /play/{token}` SHALL retornar página de expiração amigável, não erro 404.
6. THE `App_Module` SHALL implementar endpoint `GET /api/links/{token}/progresso` retornando total de acessos, último acesso e se o treinamento foi completado.

---

## Fase 2 — Diferenciação Competitiva
*Prazo sugerido: 8–12 semanas após Fase 1*

### Requisito 4: Magic Updates — Atualização Parcial de Roteiro

**User Story:** Como operador de treinamento, quero que o sistema detecte quais passos de um roteiro existente foram afetados por uma mudança na UI do Senior X e regenere apenas esses passos, para que eu não precise regravar o treinamento inteiro quando a interface muda.

#### Critérios de Aceitação

1. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/detectar-diff` que recebe um novo roteiro capturado e compara com o roteiro existente passo a passo.
2. THE diff SHALL comparar `screenshot_referencia` dos passos usando o `Template_Matcher` existente — passos com `score_matching < 0.70` são marcados como "alterados".
3. THE `App_Module` SHALL retornar lista de `passos_alterados` com `id_passo`, `score_matching` e `motivo` (screenshot divergente, seletor inválido, elemento não encontrado).
4. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/regenerar-passos` que aceita lista de `ids_passo` e regenera apenas esses passos via `generator_engine`, preservando os demais.
5. WHEN um passo for regenerado, THE system SHALL criar versão do roteiro anterior via `salvar_versao_roteiro` antes de aplicar as mudanças.
6. THE regeneração parcial SHALL preservar o `id_passo` original e todos os campos não-alterados do passo.
7. FOR ALL passos não incluídos na lista de regeneração, THE system SHALL garantir que seus dados permanecem idênticos ao roteiro original.

---

### Requisito 5: Multi-idioma Automático

**User Story:** Como operador de treinamento, quero duplicar um treinamento em inglês e espanhol com voiceover diferente gerado automaticamente, para que eu possa atender clientes com operações internacionais sem regravar nada.

#### Critérios de Aceitação

1. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/traduzir` que aceita `idioma_destino` (ex: `"en-US"`, `"es-ES"`) e retorna novo roteiro com textos traduzidos.
2. THE tradução SHALL usar Gemini para traduzir os campos `ancora`, `tooltip_dap`, `micro_narracao` e `alerta_instrutor` de cada passo.
3. THE roteiro traduzido SHALL ter `voz_ia` atualizada para a voz correspondente ao idioma (ex: `"en-US-JennyNeural"` para inglês, `"es-ES-ElviraNeural"` para espanhol).
4. THE roteiro traduzido SHALL ser salvo como novo arquivo em `roteiros_salvos/` com sufixo `_{idioma}` (ex: `meu_roteiro_en-US.json`).
5. THE `metadata` do roteiro traduzido SHALL incluir campo `idioma` e `roteiro_origem_id` para rastreabilidade.
6. WHEN o idioma solicitado não tiver voz edge-tts disponível, THE system SHALL retornar erro com lista de vozes disponíveis para o idioma.

---

### Requisito 6: Modo de Execução Guiada (Copiloto In-App)

**User Story:** Como treinando, quero que o treinamento me acompanhe dentro do Senior X mostrando onde clicar em tempo real, passo a passo, para que eu aprenda fazendo e não apenas assistindo.

#### Critérios de Aceitação

1. THE `Extension_Module` SHALL implementar modo "Guided Execution" que lê um roteiro JSON e injeta tooltips sequenciais sobre os elementos alvo no Senior X.
2. WHEN o usuário clicar no elemento correto, THE extension SHALL avançar automaticamente para o próximo passo e registrar evento `"completou_passo"` via `POST /api/analytics/evento`.
3. WHEN o usuário clicar em elemento errado, THE extension SHALL exibir feedback visual (highlight vermelho) e manter o tooltip do passo atual.
4. THE guided execution SHALL usar `seletor_hint` e `coordenadas_relativas` do roteiro para localizar o elemento alvo na tela.
5. THE extension SHALL expor botão "Iniciar Guia" no painel Aura que lista roteiros disponíveis para o módulo atual do Senior X (baseado na URL).
6. WHEN o guided execution for iniciado, THE extension SHALL registrar evento `"iniciou_guia"` com `roteiro_id` e `usuario_id` via analytics.
7. THE guided execution SHALL funcionar offline — o roteiro JSON deve ser cacheado localmente na extensão após o primeiro carregamento.

---

### Requisito 7: Onboarding Gamificado + Segmentação

**User Story:** Como gestor de treinamento, quero gerar automaticamente um checklist de onboarding a partir dos passos do roteiro e injetá-lo no Senior X como widget, com barra de progresso e segmentação por perfil de usuário.

#### Critérios de Aceitação

1. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/gerar-checklist` que extrai os passos `is_conclusao: false` e retorna estrutura de checklist com `id`, `titulo` (ancora do passo), `completado: false`.
2. THE `Extension_Module` SHALL renderizar o checklist como widget flutuante no Senior X com barra de progresso visual.
3. WHEN um passo do checklist for completado (via guided execution ou marcação manual), THE extension SHALL atualizar o estado do checklist e registrar evento de analytics.
4. THE checklist SHALL suportar segmentação por perfil: campo `perfis_alvo` no roteiro (ex: `["admin", "analista"]`) filtra quais checklists são exibidos para cada usuário.
5. THE `App_Module` SHALL implementar endpoint `GET /api/checklists/usuario/{perfil}` que retorna apenas os checklists relevantes para o perfil informado.
6. WHEN todos os itens do checklist forem completados, THE extension SHALL exibir animação de celebração e registrar evento `"onboarding_completo"`.

---

## Fase 3 — Inteligência Avançada
*Prazo sugerido: 12–16 semanas após Fase 2*

### Requisito 8: Smart Tips de Hesitação

**User Story:** Como treinando, quero que o sistema detecte automaticamente quando estou parado em um campo do Senior X por mais de N segundos e me mostre o snippet de treinamento relevante, para que eu receba ajuda proativa sem precisar perguntar.

#### Critérios de Aceitação

1. THE `Extension_Module` SHALL monitorar eventos de foco em campos de input e detectar inatividade superior a `HESITATION_THRESHOLD_MS` (padrão: 5000ms, configurável via `.env`).
2. WHEN inatividade for detectada em um campo, THE extension SHALL consultar `GET /api/dap/hint?url={url}&seletor={seletor}` para buscar o snippet de treinamento relevante.
3. THE `App_Module` SHALL implementar endpoint `GET /api/dap/hint` que busca no Pinecone o passo de roteiro mais relevante para a URL e seletor informados.
4. WHEN um hint relevante for encontrado (score >= 0.60), THE extension SHALL exibir tooltip com o texto `micro_narracao` do passo e botão "Ver passo completo".
5. WHEN "Ver passo completo" for clicado, THE extension SHALL iniciar o guided execution a partir do passo relevante.
6. THE hint SHALL ser descartado automaticamente quando o usuário começar a digitar no campo.
7. FOR ALL campos com `type="password"`, THE extension SHALL nunca exibir hints (privacidade).

---

### Requisito 9: Adaptive Learning Path

**User Story:** Como operador de treinamento, quero que o roteiro suporte ramificações — se o usuário já domina um passo, pula para o próximo; se travar, aprofunda com sub-passos — para que o treinamento seja eficiente para usuários com diferentes níveis de maturidade.

#### Critérios de Aceitação

1. THE roteiro SHALL suportar campo opcional `ramificacoes` em cada passo com estrutura: `{"se_completou_em_menos_de": int (segundos), "ir_para_passo": int}` e `{"se_errou_mais_de": int (tentativas), "ir_para_passo": int}`.
2. THE `SCORM_Player` SHALL avaliar as condições de ramificação após cada passo e navegar para o passo indicado quando a condição for satisfeita.
3. THE `Generator_Engine` SHALL suportar campo `adaptive: true` no request de geração que instrui o Gemini a criar ramificações automáticas baseadas no `peso_narrativo` dos passos.
4. WHEN `adaptive: true`, THE `Generator_Engine` SHALL criar sub-passos de aprofundamento para passos com `peso_narrativo >= 3` e ramificações de skip para passos com `peso_narrativo == 1`.
5. THE `App_Module` SHALL implementar endpoint `POST /api/roteiros/{id}/gerar-adaptive` que recebe o roteiro existente e retorna versão com ramificações geradas por IA.
6. FOR ALL roteiros sem `ramificacoes`, THE `SCORM_Player` SHALL continuar funcionando de forma linear sem alteração de comportamento.

---

### Requisito 10: NPS Pós-Treinamento

**User Story:** Como gestor de treinamento, quero que uma pesquisa de NPS seja automaticamente injetada no Senior X após o usuário completar um treinamento, para que eu possa medir a eficácia percebida e identificar treinamentos que precisam de revisão.

#### Critérios de Aceitação

1. WHEN um usuário completar todos os passos de um roteiro (evento `"completou"`), THE `Extension_Module` SHALL exibir modal de NPS com pergunta "Em uma escala de 0 a 10, o quanto este treinamento te ajudou?" após delay de 3 segundos.
2. THE `App_Module` SHALL implementar endpoint `POST /api/analytics/nps` que persiste a resposta com `roteiro_id`, `score`, `comentario` (opcional) e `ts`.
3. THE `App_Module` SHALL expor endpoint `GET /api/analytics/{roteiro_id}/nps` retornando score médio, distribuição de scores e comentários recentes.
4. THE NPS modal SHALL ser exibido no máximo uma vez por usuário por roteiro (controle via localStorage na extensão).
5. WHEN o score NPS for <= 6 (detrator), THE `App_Module` SHALL registrar alerta em log para revisão manual do roteiro.

---

## Propriedades de Corretude

### Propriedade 1: Blur Irreversível (Requisito 1)
Para qualquer screenshot com blur aplicado, não deve ser possível recuperar o valor original por processamento de imagem simples.
```
PARA TODO screenshot S com blur aplicado na região R:
  pixels_regiao = S.crop(R).getdata()
  ASSERT len(set(pixels_regiao)) == 1  // região é cor sólida uniforme
```

### Propriedade 2: Consistência de Analytics (Requisito 2)
Para qualquer sequência de N eventos de "completou_passo" para um roteiro com N passos, a taxa de conclusão deve ser 100%.
```
PARA TODO roteiro R com N passos:
  SE count(eventos "completou_passo" para R) == N:
    ASSERT taxa_conclusao(R) == 1.0
```

### Propriedade 3: Integridade do Link (Requisito 3)
Para qualquer link gerado antes de sua expiração, o acesso deve retornar o player, nunca 404.
```
PARA TODO token T com expira_em > agora:
  resposta = GET /play/{T}
  ASSERT resposta.status_code == 200
```

### Propriedade 4: Preservação de Passos Não-Alterados (Requisito 4)
Para qualquer regeneração parcial de roteiro, os passos não incluídos na lista de regeneração devem ser bit-a-bit idênticos ao original.
```
PARA TODO passo P não incluído em ids_regenerar:
  ASSERT roteiro_novo["passos"][P] == roteiro_original["passos"][P]
```

### Propriedade 5: Linearidade Preservada sem Ramificações (Requisito 9)
Para qualquer roteiro sem campo `ramificacoes`, o SCORM player deve navegar linearmente de passo 1 a passo N.
```
PARA TODO roteiro R sem ramificacoes:
  sequencia = simular_navegacao(R)
  ASSERT sequencia == list(range(1, len(R.passos) + 1))
```

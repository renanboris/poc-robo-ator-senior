# Plano de Implementação: Roadmap Orientado por Mercado

## Visão Geral

Este plano traduz os 10 requisitos do roadmap competitivo em tarefas concretas, organizadas em 3 fases com dependências explícitas.

A lógica de priorização é:
- **Fase 1** resolve bloqueadores enterprise (privacidade + distribuição + visibilidade)
- **Fase 2** cria diferenciação competitiva real (copiloto + atualizações parciais + multi-idioma)
- **Fase 3** adiciona inteligência que nenhum concorrente tem integrado ao pipeline de roteiro

Cada tarefa referencia o requisito que implementa. Tarefas com `*` são opcionais para MVP.

---

## Fase 1 — Fundação de Confiança

### Bloco 1.A — Smart Blur (Requisito 1)

- [x] 1. Implementar detecção de campos sensíveis em `capture.py`
  - Após capturar `screenshot_referencia`, verificar se o elemento alvo tem `type="password"` via `element_handle.get_attribute("type")`
  - Verificar também seletores da lista `BLUR_SELECTORS` do `.env` (separados por vírgula)
  - Se campo sensível detectado, armazenar `{"blur": true, "regiao": {"x": int, "y": int, "w": int, "h": int}}` em `elemento_alvo.dados_blur`
  - Registrar `logger.info` com id da ação e tipo do campo (nunca o valor)
  - _Requisito: 1.1, 1.4_

- [x] 2. Implementar aplicação de blur nos screenshots do roteiro
  - Criar função `aplicar_blur_screenshot(imagem_b64: str, regioes: list) -> str` em `utils.py` usando Pillow
  - O blur deve ser retângulo sólido cinza (`#1a1a1a`) sobre a região — não gaussiano
  - Integrar chamada na função de salvamento de screenshot em `capture.py` quando `dados_blur.blur == true`
  - _Requisito: 1.1, 1.5_

- [x] 3. Implementar blur no pipeline de vídeo em `main.py`
  - Antes de compor o frame de vídeo, verificar se o passo tem `dados_blur` preenchido
  - Aplicar `aplicar_blur_screenshot` no frame antes de passar para o moviepy
  - _Requisito: 1.2_

- [x] 4. Implementar endpoint de reprocessamento de blur
  - `POST /api/roteiros/{id}/aplicar-blur` em `app.py`
  - Lê o roteiro, percorre todos os passos, aplica blur nos screenshots marcados, salva roteiro atualizado via `_atomic_write_json`
  - Retorna `{"passos_processados": int, "passos_com_blur": int}`
  - _Requisito: 1.6_

---

### Bloco 1.B — Analytics de Engajamento (Requisito 2)

- [x] 5. Criar tabela `analytics_eventos` no `brain.db`
  - Migração idempotente em `app.py` no startup (lifespan)
  - Schema: `id INTEGER PRIMARY KEY, roteiro_id TEXT, passo_id INTEGER, usuario_id TEXT, evento TEXT, ts INTEGER`
  - Índices: `idx_analytics_roteiro` em `(roteiro_id, ts)` e `idx_analytics_usuario` em `(usuario_id, ts)`
  - _Requisito: 2.3_

- [x] 6. Implementar endpoint de ingestão de eventos
  - `POST /api/analytics/evento` em `app.py`
  - Payload: `{"roteiro_id": str, "passo_id": int, "usuario_id": str, "evento": str}`
  - Eventos válidos: `"iniciou"`, `"completou_passo"`, `"repetiu_passo"`, `"abandonou"`, `"completou"`
  - Gerar `usuario_id` anônimo via hash MD5 de IP + user-agent quando não fornecido
  - _Requisito: 2.2, 2.6_

- [x] 7. Implementar endpoint de relatório de analytics
  - `GET /api/analytics/{roteiro_id}` em `app.py`
  - Retornar: `taxa_conclusao`, `tempo_medio_por_passo` (dict passo_id → segundos), `passos_mais_repetidos` (top 5), `passo_maior_abandono`
  - Retornar `null` para campos sem dados suficientes (mínimo 3 eventos)
  - _Requisito: 2.4_

- [x] 8. Integrar emissão de eventos no SCORM player em `scorm_builder.py`
  - Adicionar chamada `fetch("/api/analytics/evento", {method: "POST", ...})` no JavaScript do player quando passo for completado
  - Emitir evento `"completou"` quando `mostrar(slides.length)` for chamado (fim do treinamento)
  - Usar `navigator.sendBeacon` como fallback para garantir envio mesmo ao fechar a aba
  - _Requisito: 2.1, 2.5_

---

### Bloco 1.C — Shareable Training Link (Requisito 3)

- [x] 9. Criar tabela `sim_links` no `brain.db`
  - Migração idempotente no startup
  - Schema: `token TEXT PRIMARY KEY, roteiro_id TEXT, criado_em INTEGER, expira_em INTEGER, total_acessos INTEGER DEFAULT 0`
  - _Requisito: 3.3_

- [x] 10. Implementar geração de link
  - `POST /api/roteiros/{id}/gerar-link` em `app.py`
  - Gerar token UUID4, calcular `expira_em = agora + TTL_DIAS * 86400` (TTL_DIAS do `.env`, padrão 30)
  - Persistir em `sim_links`, retornar `{"url": "/play/{token}", "expira_em": str, "token": str}`
  - _Requisito: 3.1, 3.3_

- [x] 11. Implementar rota de acesso ao player via link
  - `GET /play/{token}` em `app.py`
  - Verificar expiração — retornar template `link_expirado.html` se expirado
  - Incrementar `total_acessos`, registrar evento `"iniciou"` em `analytics_eventos`
  - Servir o player SCORM do roteiro correspondente diretamente (sem redirect)
  - _Requisito: 3.2, 3.4, 3.5_

- [x] 12. Implementar endpoint de progresso do link
  - `GET /api/links/{token}/progresso` em `app.py`
  - Retornar `{"total_acessos": int, "ultimo_acesso": str, "completado": bool}`
  - _Requisito: 3.6_

---

## Fase 2 — Diferenciação Competitiva

### Bloco 2.A — Magic Updates (Requisito 4)

- [ ] 13. Implementar endpoint de detecção de diff entre roteiros
  - `POST /api/roteiros/{id}/detectar-diff` em `app.py`
  - Recebe `{"roteiro_novo_id": str}` — compara passo a passo usando `Template_Matcher` existente
  - Para cada passo, comparar `screenshot_referencia` do roteiro original vs novo
  - Retornar `{"passos_alterados": [{"id_passo": int, "score_matching": float, "motivo": str}], "passos_inalterados": int}`
  - _Requisito: 4.1, 4.2, 4.3_

- [ ] 14. Implementar regeneração parcial de passos
  - `POST /api/roteiros/{id}/regenerar-passos` em `app.py`
  - Recebe `{"ids_passo": [int]}` — regenera apenas os passos listados via `generator_engine`
  - Criar versão do roteiro original via `salvar_versao_roteiro` antes de qualquer mudança
  - Preservar `id_passo` e todos os campos não-alterados dos passos regenerados
  - Salvar roteiro atualizado via `_atomic_write_json`
  - _Requisito: 4.4, 4.5, 4.6, 4.7_

---

### Bloco 2.B — Multi-idioma (Requisito 5)

- [ ] 15. Mapear vozes edge-tts disponíveis por idioma
  - Criar dict `VOZES_POR_IDIOMA` em `utils.py` com mapeamento `idioma → voz_ia` para pt-BR, en-US, es-ES, fr-FR
  - Incluir fallback para idiomas sem voz mapeada
  - _Requisito: 5.6_

- [ ] 16. Implementar endpoint de tradução de roteiro
  - `POST /api/roteiros/{id}/traduzir` em `app.py`
  - Recebe `{"idioma_destino": str}` (ex: `"en-US"`)
  - Usar Gemini para traduzir campos `ancora`, `tooltip_dap`, `micro_narracao`, `alerta_instrutor` de todos os passos
  - Atualizar `voz_ia` para a voz do idioma destino via `VOZES_POR_IDIOMA`
  - Salvar como novo roteiro com sufixo `_{idioma}`, incluir `idioma` e `roteiro_origem_id` no metadata
  - _Requisito: 5.1, 5.2, 5.3, 5.4, 5.5_

---

### Bloco 2.C — Guided Execution na Extensão (Requisito 6)

- [ ] 17. Implementar endpoint de listagem de roteiros por URL
  - `GET /api/roteiros/por-url?url={url}` em `app.py`
  - Busca no Pinecone roteiros com metadata de URL correspondente (ou busca textual no nome_aula)
  - Retorna lista de `{"roteiro_id": str, "nome_aula": str, "total_passos": int}`
  - _Requisito: 6.5_

- [ ] 18. Implementar modo Guided Execution na extensão
  - Em `extension/`, criar `guided_execution.js` que lê roteiro JSON e injeta tooltips sequenciais
  - Tooltip deve mostrar `micro_narracao` do passo atual com seta apontando para o elemento alvo
  - Usar `seletor_hint` para localizar o elemento; fallback para `coordenadas_relativas` se seletor falhar
  - Detectar clique correto via MutationObserver ou comparação de URL após clique
  - Emitir `POST /api/analytics/evento` com `"completou_passo"` a cada passo concluído
  - _Requisito: 6.1, 6.2, 6.3, 6.4, 6.6_

- [ ] 19. Implementar cache local do roteiro na extensão
  - Usar `chrome.storage.local` para cachear o JSON do roteiro após primeiro carregamento
  - TTL de cache: 24h (configurável)
  - _Requisito: 6.7_

---

### Bloco 2.D — Onboarding Gamificado (Requisito 7)

- [ ] 20. Implementar geração de checklist a partir do roteiro
  - `POST /api/roteiros/{id}/gerar-checklist` em `app.py`
  - Extrair passos com `is_conclusao: false`, retornar `[{"id": int, "titulo": str (ancora), "completado": false}]`
  - Salvar checklist em `missoes_ativas/{id}_checklist.json`
  - _Requisito: 7.1_

- [ ] 21. Implementar widget de checklist na extensão
  - Em `extension/`, criar `checklist_widget.js` que renderiza checklist flutuante com barra de progresso
  - Atualizar estado via eventos de analytics recebidos do guided execution
  - Exibir animação de celebração (confetti CSS) quando todos os itens forem completados
  - _Requisito: 7.2, 7.3, 7.6_

- [ ] 22. Implementar segmentação por perfil
  - Adicionar campo `perfis_alvo: list[str]` no schema do roteiro (opcional, default `[]` = todos)
  - `GET /api/checklists/usuario/{perfil}` em `app.py` — filtra roteiros onde `perfis_alvo` contém o perfil ou está vazio
  - _Requisito: 7.4, 7.5_

---

## Fase 3 — Inteligência Avançada

### Bloco 3.A — Smart Tips de Hesitação (Requisito 8)

- [ ] 23. Implementar endpoint de hint contextual
  - `GET /api/dap/hint?url={url}&seletor={seletor}` em `app.py`
  - Busca no Pinecone o passo mais relevante para a URL + seletor informados
  - Retorna `{"passo_id": int, "roteiro_id": str, "micro_narracao": str, "score": float}` ou `null` se score < 0.60
  - Nunca retornar hints para campos com `type="password"` (verificar via seletor)
  - _Requisito: 8.2, 8.3, 8.4, 8.7_

- [ ] 24. Implementar detecção de hesitação na extensão
  - Em `extension/`, criar `hesitation_detector.js` que monitora eventos `focus` em campos de input
  - Após `HESITATION_THRESHOLD_MS` (padrão 5000ms) sem `keydown`, consultar `/api/dap/hint`
  - Exibir tooltip com `micro_narracao` e botão "Ver passo completo" se hint encontrado
  - Descartar tooltip ao primeiro `keydown` no campo
  - _Requisito: 8.1, 8.5, 8.6_

---

### Bloco 3.B — Adaptive Learning Path (Requisito 9)

- [ ] 25. Adicionar suporte a `ramificacoes` no schema do roteiro
  - Atualizar `PassoRoteiro` em `app.py` com campo opcional `ramificacoes: Optional[List[RamificacaoRoteiro]]`
  - `RamificacaoRoteiro`: `{"condicao": str, "valor": int, "ir_para_passo": int}`
  - Condições suportadas: `"completou_em_menos_de"` (segundos), `"errou_mais_de"` (tentativas)
  - Garantir retrocompatibilidade: roteiros sem `ramificacoes` continuam lineares
  - _Requisito: 9.1, 9.6_

- [ ] 26. Implementar navegação adaptativa no SCORM player
  - Em `scorm_builder.py`, adicionar lógica de avaliação de `ramificacoes` após cada passo concluído
  - Medir tempo de conclusão do passo (timestamp início → timestamp clique correto)
  - Contar tentativas erradas por passo
  - Navegar para `ir_para_passo` quando condição for satisfeita
  - _Requisito: 9.2_

- [ ] 27. Implementar geração de roteiro adaptativo via IA
  - `POST /api/roteiros/{id}/gerar-adaptive` em `app.py`
  - Usar Gemini para analisar o roteiro e sugerir ramificações baseadas em `peso_narrativo`
  - Passos com `peso_narrativo >= 3`: criar sub-passo de aprofundamento
  - Passos com `peso_narrativo == 1`: criar ramificação de skip se completado rapidamente
  - _Requisito: 9.3, 9.4, 9.5_

---

### Bloco 3.C — NPS Pós-Treinamento (Requisito 10)

- [ ] 28. Criar tabela `nps_respostas` no `brain.db`
  - Schema: `id INTEGER PRIMARY KEY, roteiro_id TEXT, score INTEGER, comentario TEXT, ts INTEGER`
  - Migração idempotente no startup
  - _Requisito: 10.2_

- [ ] 29. Implementar endpoints de NPS
  - `POST /api/analytics/nps` — persiste resposta, registra alerta em log se score <= 6
  - `GET /api/analytics/{roteiro_id}/nps` — retorna score médio, distribuição e comentários recentes (últimos 10)
  - _Requisito: 10.2, 10.3, 10.5_

- [ ] 30. Implementar modal de NPS na extensão
  - Em `extension/`, criar `nps_modal.js` que escuta evento `"completou"` do analytics
  - Exibir modal após 3 segundos com escala 0–10 e campo de comentário opcional
  - Controlar exibição via `chrome.storage.local` — máximo 1x por usuário por roteiro
  - Enviar resposta via `POST /api/analytics/nps`
  - _Requisito: 10.1, 10.4_

---

## Dependências entre Tarefas

```
Fase 1:
  Tarefa 2 depende de Tarefa 1 (blur precisa da detecção)
  Tarefa 3 depende de Tarefa 2 (vídeo usa a função de blur)
  Tarefa 4 depende de Tarefa 2 (endpoint usa a função de blur)
  Tarefa 6 depende de Tarefa 5 (endpoint precisa da tabela)
  Tarefa 7 depende de Tarefa 6 (relatório precisa dos eventos)
  Tarefa 8 depende de Tarefa 6 (SCORM emite para o endpoint)
  Tarefa 10 depende de Tarefa 9 (geração precisa da tabela)
  Tarefa 11 depende de Tarefa 10 (acesso precisa do link gerado)
  Tarefa 12 depende de Tarefa 11 (progresso precisa dos acessos)

Fase 2:
  Tarefa 13 depende de Tarefa 3 do playback-resilience-roadmap (Template_Matcher)
  Tarefa 14 depende de Tarefa 13 (regeneração usa o diff)
  Tarefa 16 depende de Tarefa 15 (tradução usa o mapeamento de vozes)
  Tarefa 18 depende de Tarefa 6 (guided execution emite analytics)
  Tarefa 19 depende de Tarefa 18 (cache é parte do guided execution)
  Tarefa 20 depende de Tarefa 5 (checklist usa analytics)
  Tarefa 21 depende de Tarefa 20 (widget usa o checklist gerado)
  Tarefa 22 depende de Tarefa 20 (segmentação é extensão do checklist)

Fase 3:
  Tarefa 23 depende de Tarefa 6 (hint usa o mesmo pipeline de analytics)
  Tarefa 24 depende de Tarefa 23 (detector usa o endpoint de hint)
  Tarefa 26 depende de Tarefa 25 (player usa o schema de ramificações)
  Tarefa 27 depende de Tarefa 25 (geração usa o schema de ramificações)
  Tarefa 29 depende de Tarefa 28 (endpoints usam a tabela)
  Tarefa 30 depende de Tarefa 29 (modal usa o endpoint de NPS)
```

---

## Notas de Implementação

- Todas as novas tabelas SQLite devem usar migração idempotente no startup do `app.py`
- Todos os novos campos no roteiro são opcionais — retrocompatibilidade é obrigatória
- Novos endpoints devem seguir o padrão de autenticação existente (`verificar_token`) onde aplicável
- Analytics de engajamento não requer autenticação — é dado de uso, não dado sensível
- A extensão (`extension/`) deve ser tratada como módulo separado — não importar diretamente de `app.py`
- Usar `_atomic_write_json` para qualquer escrita em roteiros
- Usar `limpar_nome()` para qualquer sanitização de nomes de arquivo

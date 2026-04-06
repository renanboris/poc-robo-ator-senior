# Senior Training OS — Roadmap de Melhorias

> Gerado a partir da análise técnica de Abril/2026.
> Organizado em 3 fases por impacto e risco.

---

## Fase 1 — Limpeza e Taxonomia (Baixo Risco, Alto Impacto Imediato)

### 1.1 Deletar arquivos lixo da raiz
- `capture copy.py` — cópia literal de `capture.py`, sem diferença funcional
- `teste_voz.py` — usa ElevenLabs com API key hardcoded `"xxx"`, nunca funciona
- `tmp*.json.tmp` — writes atômicos do `lego_builder.py` que não foram limpos (processo interrompido)

### 1.2 Mover utilitários para `scripts/`
- `extrai_design_tokens.py` → `scripts/extrai_design_tokens.py`
- `reprocessar.py` → `scripts/reprocessar.py`
- `sim_link_builder.py` → `scripts/sim_link_builder.py` (ou integrar ao app.py)
- `mission_builder.py` → `scripts/mission_builder.py`

### 1.3 Mover variantes de capture para `capture_variants/`
- `capture_dual_output.py` → `capture_variants/capture_dual_output.py`
- `capture_hybrid_shadow.py` → `capture_variants/capture_hybrid_shadow.py`

### 1.4 Corrigir bug de env var em reprocessar.py
- `reprocessar.py` usa `GEMINI_API_KEY` mas o projeto usa `GOOGLE_API_KEY`
- Alinhar para `GOOGLE_API_KEY` em todos os módulos

### 1.5 Atualizar app.py para imports movidos
- `sim_link_builder` importado diretamente em `app.py` — ajustar path após mover
- Rota `/api/gravar-dual` aponta para `capture_dual_output.py` — ajustar path

---

## Fase 2 — Self-Healing: Observabilidade e Robustez (Médio Risco)

### 2.1 TTL por tempo no Brain DB
**Problema:** memórias no `brain.db` nunca expiram por tempo — só por falhas consecutivas.
Um seletor pode ficar obsoleto por meses sem ser usado e nunca ser limpo.

**Solução:** adicionar coluna `ultima_atualizacao` (já existe) e limpeza periódica de entradas
não usadas há mais de 90 dias. Implementar em `_init_db()` como `DELETE WHERE ultima_atualizacao < now - 90d`.

### 2.2 Telemetria de camadas do vision_engine
**Problema:** não há visibilidade de qual camada está sendo mais acionada.
Não sabemos se o Brain cobre 80% ou 20% dos casos.

**Solução:** adicionar tabela `telemetria_camadas` no `brain.db` com contagem por camada.
Expor endpoint `/api/brain-stats` no dashboard para visualização.

### 2.3 Gemini Vision deve tentar aprender seletor após acerto por coordenada
**Problema:** quando a camada 5 (Gemini Vision) acerta por coordenada, salva apenas coords no Brain.
Na próxima execução, usa coordenada de novo em vez de tentar aprender o seletor DOM.

**Solução:** após clique por coordenada bem-sucedido, tentar `document.elementFromPoint(x, y)`
para extrair o seletor do elemento e salvar no Brain junto com as coords.

### 2.4 Threshold do Brain no validator_hitl
**Problema:** `BRAIN_HITS_ALTA = 3` pode ser conservador demais — pausa preventiva desnecessária
em elementos que já foram corrigidos 2 vezes.

**Solução:** baixar para `BRAIN_HITS_ALTA = 2` e adicionar flag `hitl_corrigido` no Brain
para elementos ensinados manualmente (confiança imediata após correção humana).

### 2.5 Modo silencioso no validator_hitl
**Problema:** não há modo de re-execução rápida para roteiros já validados.

**Solução:** adicionar flag `--silent` que desativa pausas preventivas e checkpoints,
só pausa em falha dura. Útil para re-execuções de roteiros com Brain aquecido.

---

## Fase 3 — validator.py: Integração com vision_engine (Alto Impacto)

### 3.1 Substituir validação direta de seletor por vision_engine
**Problema:** `validator.py` valida seletores diretamente com `page.locator().wait_for()`.
Se o seletor falhar, não tenta fallback — reporta como falha mesmo que o elemento exista.

**Solução:** substituir `_validar_seletor` por chamada ao `encontrar_e_clicar` do `vision_engine`
em modo dry-run (sem executar a ação, só verificar se encontra o elemento).

### 3.2 Heurística de navegação mais robusta no validator
**Problema:** `_e_acao_navegacao` classifica por palavras no label/seletor.
Se um menu não tiver "menu" no seletor, o validator tenta validar sem ter navegado.

**Solução:** usar o campo `capture_scope` e `pattern_detectado` do roteiro (disponíveis
nos roteiros gerados por `capture_hybrid_shadow.py`) para classificação mais precisa.

### 3.3 Checkpoint Gemini com screenshot de referência
**Problema:** o checkpoint do `validator_hitl.py` usa prompt genérico sem referência visual.

**Solução:** passar `screenshot_referencia` do roteiro para o Gemini junto com o screenshot atual,
pedindo comparação visual direta entre "como estava na gravação" e "como está agora".

---

## Fase 4 — capture_hybrid_shadow: Promoção para Capture Principal (Longo Prazo)

### 4.1 Integrar capture_hybrid_shadow ao app.py como rota principal
**Situação atual:** `app.py` usa `capture.py` como padrão e `capture_dual_output.py` como dual.
`capture_hybrid_shadow.py` é o mais avançado mas não está exposto no dashboard.

**Plano:**
1. Adicionar rota `/api/gravar-hybrid` no `app.py`
2. Validar que o output do hybrid é compatível com `main.py` (executor)
3. Usar `scripts/compile_hybrid_to_executor.py` como etapa de compilação automática
4. Após validação, promover hybrid como padrão e deprecar `capture.py`

### 4.2 Cleanup automático de tmp files
**Problema:** `tmp*.json.tmp` na raiz indicam que o `lego_builder.py` foi interrompido.
O `os.remove(caminho_tmp)` no `except` não roda se o processo for killed externamente.

**Solução:** adicionar limpeza de `*.json.tmp` no startup do `app.py` (lifespan event).

---

## Estrutura de Pastas Alvo

```
/                              ← pipeline principal apenas
  app.py
  capture.py                   ← capture padrão atual
  generator_engine.py
  main.py
  vision_engine.py
  cursor_engine.py
  validator.py
  validator_hitl.py
  scorm_builder.py
  pdf_builder.py
  lego_builder.py
  dap_engine.py
  shadow_builder.py
  utils.py

scripts/                       ← utilitários operacionais
  compile_hybrid_to_executor.py
  extrai_design_tokens.py
  reprocessar.py
  sim_link_builder.py
  mission_builder.py

capture_variants/              ← variantes experimentais
  capture_dual_output.py
  capture_hybrid_shadow.py

old_but_gold/                  ← arquivo histórico (já existe)
```

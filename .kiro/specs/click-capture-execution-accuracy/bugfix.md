# Bugfix Requirements Document

## Introduction

Após análise completa do código (`capture_variants/capture_dual_output.py` e `vision_engine.py`), identificamos que o problema NÃO é apenas "coordenadas imprecisas". O bug real é uma **FALHA EM CASCATA** nas 7 camadas de localização do `vision_engine.py`, onde as camadas semânticas (Sniper, Template Matching, Brain) falham ANTES de chegar nas coordenadas.

**Arquitetura Real do vision_engine.py — Cascata de 7 Camadas:**
- **Camada 0**: Brain (memória SQLite — seletores que funcionaram antes)
- **Camada 0.5**: Menu de contexto ativo
- **Camada 1**: Foco nativo / active element
- **Camada 1.5**: Heurísticas Senior X (ícones mudos)
- **Camada 1_T**: Template Matching visual (screenshot_elemento)
- **Camada 2_S**: **Sniper Semântico** (15+ seletores Playwright: getByRole, getByLabel, aria-label, data-testid, text=, etc.)
- **Camada 2**: **Coordenadas Capturadas** (última alternativa semântica)
- **Camada 3**: Seletor hint original
- **Camada 4**: Busca em todos os frames
- **Camada 5**: Gemini Vision (self-healing supremo)

**Problema Real:** Quando as camadas 2_S, 1_T, 2, e 0 falham em sequência, o sistema escala até Gemini Vision (Camada 5) para TUDO, tornando execução lenta, cara, e não confiável.

**Impacto:** Impossibilidade de escalar a produção de treinamentos automatizados, necessidade de intervenção manual constante (HITL), perda de confiança no sistema de self-healing, custo elevado de API Gemini.

**Arquivos principais envolvidos:**
- `capture_variants/capture_dual_output.py` — captura de elementos e geração de seletores via `getBestSelector()`
- `vision_engine.py` — cascata de 7 camadas de localização e execução
- `main.py` — orquestração da execução

**Nota sobre o arquivo de captura:**
O arquivo principal de captura é `capture_variants/capture_dual_output.py`, não `capture.py`. Este arquivo implementa:
- **Enriquecimento pós-captura**: Gemini Vision roda APÓS a sessão de captura terminar (via `enriquecer_eventos_com_gemini()`), não durante a captura, evitando bloqueio por latência da API
- **Fallback heurístico**: Eventos com labels descritivos suficientes usam fallback heurístico direto (sem chamar Gemini), economizando chamadas de API
- **Processamento em lotes**: Eventos que precisam de Gemini são processados em lotes paralelos de até 8 eventos simultâneos
- **Shadow JSONL**: Além do roteiro oficial, gera um arquivo shadow JSONL com metadados semânticos adicionais
- **Retry com backoff exponencial**: Implementa retry automático para Gemini com backoff exponencial (até 5 tentativas)
- **Fallback OpenAI**: Se Gemini falha completamente, usa OpenAI GPT-4o como fallback para gerar o roteiro

---

## Bug Analysis

### 1. Current Behavior (Defect)

**O que está quebrado — Falha em Cascata nas Camadas Semânticas:**

#### 1.1 Camada 2_S (Sniper Semântico) está falhando

1.1.1 QUANDO `capture_dual_output.py` gera seletores via `getBestSelector()` para checkboxes PrimeNG/Angular ENTÃO o seletor `item:has-text("Nome") .ui-chkbox .ui-chkbox-box` funciona na captura mas **falha na execução se o texto mudou** (ex: "Nome da Pasta" → "Nome").

1.1.2 QUANDO o elemento é um toggle on/off, ícone SVG sem texto, ou menu de contexto sobre iframe ENTÃO `getBestSelector()` **não captura aria-label, data-testid, ou atributos semânticos suficientemente robustos**, gerando seletores posicionais frágeis (`:nth-child(2)`, `#file_8`).

1.1.3 QUANDO o elemento está dentro de um overlay CDK (menu de contexto) ENTÃO o seletor gerado **não considera o escopo do overlay**, falhando ao tentar localizar no DOM principal.

#### 1.2 Camada 1_T (Template Matching) não está sendo usada corretamente

1.2.1 QUANDO `capture_dual_output.py` captura `screenshot_elemento` via `locator.screenshot()` ENTÃO o screenshot **pode não estar sendo capturado para TODOS os elementos** (apenas alguns), impedindo Template Matching na execução.

1.2.2 QUANDO `vision_engine.py` tenta usar Template Matching via NCC (Normalized Cross-Correlation) ENTÃO o threshold de 0.80 **pode ser muito alto para elementos pequenos** (checkboxes 16x16px), causando falsos negativos.

1.2.3 QUANDO elementos pequenos não têm features visuais suficientes ENTÃO Template Matching **falha silenciosamente** sem fallback para threshold mais baixo (0.60-0.70).

#### 1.3 Camada 2 (Coordenadas) está falhando como última alternativa

1.3.1 QUANDO `getBoundingClientRect()` retorna rect zerado para elementos Angular em transição ENTÃO `getRectComFallback()` **pode não estar sendo chamado corretamente**, resultando em coordenadas padrão (0.5, 0.5).

1.3.2 QUANDO o elemento está dentro de um iframe ENTÃO as coordenadas capturadas **não somam `iframe.getBoundingClientRect()`**, gerando coordenadas relativas ao iframe ao invés do viewport principal.

1.3.3 QUANDO `vision_engine.py` usa coordenadas na execução ENTÃO o sistema **não recalcula via `locator.boundingBox()`**, confiando cegamente nas coordenadas capturadas que podem estar desatualizadas.

1.3.4 QUANDO `_verificar_identidade_por_coordenadas()` tenta validar o elemento ENTÃO a função **pode estar falhando em iframes** ou elementos com offsets complexos.

#### 1.4 Camada 0 (Brain) não está aprendendo

1.4.1 QUANDO o Brain tenta registrar sucesso via `_registrar_sucesso_cache()` ENTÃO seletores PrimeNG/Angular com `:has-text(` **são descartados** porque não começam com prefixos válidos (`text=`, `[`, `#`, `button.`, `p-`, `mat-`).

1.4.2 QUANDO TODAS as camadas falham ENTÃO o Brain **nunca aprende o seletor correto**, perpetuando a falha em cascata.

1.4.3 QUANDO o Sniper acerta mas o seletor é considerado "vago" ENTÃO o Brain **descarta a memória** ao invés de registrar o candidato que funcionou.

---

### 2. Expected Behavior (Correct)

**O que deveria acontecer — Fortalecer Camadas Semânticas ANTES de Coordenadas:**

#### 2.1 Camada 2_S (Sniper Semântico) deve ser fortalecida

2.1.1 QUANDO `capture_dual_output.py` gera seletores via `getBestSelector()` para checkboxes PrimeNG ENTÃO SHALL capturar TANTO o seletor `:has-text()` QUANTO o ID do item pai como fallback, permitindo que o Sniper tente múltiplas estratégias.

2.1.2 QUANDO o elemento é um toggle/ícone sem texto ENTÃO `getBestSelector()` SHALL **forçar captura de aria-label ou data-testid via JavaScript injection**, garantindo atributos semânticos estáveis.

2.1.3 QUANDO o elemento está dentro de um overlay CDK (menu de contexto) ENTÃO `getBestSelector()` SHALL **detectar o overlay e gerar seletores escopados** (ex: `p-dialog button:has-text("Sim")`).

2.1.4 QUANDO `vision_engine.py` tenta localizar via Sniper ENTÃO SHALL **tentar TODOS os candidatos gerados** (não apenas o primeiro), registrando no Brain qual funcionou.

#### 2.2 Camada 1_T (Template Matching) deve ser fortalecida

2.2.1 QUANDO `capture_dual_output.py` captura um elemento ENTÃO SHALL **garantir que `screenshot_elemento` é capturado para TODOS os elementos** (não apenas alguns), permitindo Template Matching na execução.

2.2.2 QUANDO `vision_engine.py` tenta Template Matching ENTÃO SHALL **reduzir threshold de 0.80 para 0.70 para elementos pequenos** (< 50x50px), aumentando taxa de acerto.

2.2.3 QUANDO Template Matching falha com threshold 0.70 ENTÃO SHALL **tentar novamente com threshold 0.60** como fallback antes de desistir.

#### 2.3 Camada 2 (Coordenadas) deve ser consertada como último recurso

2.3.1 QUANDO `capture_dual_output.py` captura coordenadas ENTÃO SHALL **chamar `getRectComFallback()` SEMPRE** (não apenas em fallback), garantindo rect válido para elementos Angular em transição.

2.3.2 QUANDO o elemento está dentro de um iframe ENTÃO SHALL **somar offsets de `iframe.getBoundingClientRect()`** ao calcular coordenadas absolutas e relativas.

2.3.3 QUANDO `vision_engine.py` usa coordenadas na execução ENTÃO SHALL **recalcular via `locator.boundingBox()`** do Playwright ao invés de usar coordenadas capturadas diretamente, usando-as apenas como hint de posição aproximada.

2.3.4 QUANDO `capture_dual_output.py` armazena coordenadas no roteiro JSON ENTÃO SHALL incluir metadados completos:
   - `coordenadas_absolutas`: {x, y} em pixels do centro do elemento
   - `coordenadas_relativas`: {x_pct, y_pct} percentuais relativos ao viewport
   - `viewport_size`: {width, height} do viewport no momento da captura
   - `offsets`: {iframe, scroll, sidebar} se aplicável
   - `elemento_rect`: {x, y, width, height} do bounding box completo

#### 2.4 Camada 0 (Brain) deve aprender corretamente

2.4.1 QUANDO `_registrar_sucesso_cache()` recebe um seletor PrimeNG/Angular ENTÃO SHALL **aceitar `:has-text(` como prefixo válido**, permitindo que o Brain aprenda seletores compostos.

2.4.2 QUANDO o Sniper acerta com um candidato ENTÃO SHALL **registrar TODOS os candidatos que funcionaram** (não apenas o primeiro), implementando "Brain proativo".

2.4.3 QUANDO todas as camadas falham ENTÃO SHALL **registrar falha apenas UMA VEZ** (não duplicar registro), evitando apagar memórias válidas prematuramente.

---

### 3. Unchanged Behavior (Regression Prevention)

**O que deve continuar funcionando:**

3.1 QUANDO o sistema captura elementos com texto visível e seletores estáveis (botões com aria-label, inputs com placeholder, links com texto) ENTÃO o sistema SHALL CONTINUE TO usar a cascata de estratégias do `vision_engine.py` (Brain → Sniper → Coordenadas → Vision) sem regressão na taxa de sucesso atual.

3.2 QUANDO o sistema executa roteiros existentes que já foram validados e funcionam corretamente ENTÃO o sistema SHALL CONTINUE TO executá-los com sucesso, sem quebrar compatibilidade com roteiros salvos.

3.3 QUANDO o sistema usa o Brain (memória SQLite) para localizar elementos previamente mapeados ENTÃO o sistema SHALL CONTINUE TO priorizar seletores semânticos sobre coordenadas, mantendo o comportamento de self-healing.

3.4 QUANDO o sistema captura screenshots de referência e screenshots de elementos ENTÃO o sistema SHALL CONTINUE TO salvá-los em disco e aplicar blur em campos sensíveis conforme requisitos de segurança existentes.

3.5 QUANDO o sistema injeta o radar de captura (`_injetar_em_contexto`) ENTÃO o sistema SHALL CONTINUE TO capturar eventos de clique, duplo clique, clique direito, digitação e blur sem interferir na experiência do usuário durante a gravação.

3.6 QUANDO o sistema gera áudios, vídeos, SCORM e PDFs a partir do roteiro ENTÃO o sistema SHALL CONTINUE TO usar os campos `coordenadas_relativas` e `screenshot_referencia` sem quebrar a pipeline de geração de assets.

---

## Bug Condition Derivation

### Bug Condition Function — Falha em Cascata

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AcaoCapturada
  OUTPUT: boolean
  
  // Retorna true quando as camadas semânticas falham em cascata
  RETURN (
    sniper_falhou(X) AND
    template_matching_falhou(X) AND
    coords_falhou(X) AND
    brain_nao_aprendeu(X)
  )
END FUNCTION

FUNCTION sniper_falhou(X)
  // Sniper falha quando seletores são fracos ou posicionais
  RETURN (
    X.elemento_alvo.seletor_hint CONTAINS ":nth-child" OR
    X.elemento_alvo.seletor_hint CONTAINS ":has-text(" AND texto_mudou(X) OR
    X.elemento_alvo.tipo_elemento IN ["checkbox", "toggle", "icon"] AND
    NOT (X.elemento_alvo.seletor_hint CONTAINS "aria-label" OR
         X.elemento_alvo.seletor_hint CONTAINS "data-testid")
  )
END FUNCTION

FUNCTION template_matching_falhou(X)
  // Template Matching falha quando screenshot_elemento ausente ou threshold alto
  RETURN (
    X.elemento_alvo.screenshot_elemento == null OR
    X.elemento_alvo.elemento_rect.width < 50 AND threshold_template_matching > 0.70
  )
END FUNCTION

FUNCTION coords_falhou(X)
  // Coordenadas falham quando offsets não calculados ou rect zerado
  RETURN (
    X.elemento_alvo.coordenadas_absolutas == null OR
    X.elemento_alvo.coordenadas_absolutas == {x: 0.5 * viewport_w, y: 0.5 * viewport_h} OR
    X.elemento_alvo.iframe_hint != null AND offsets_iframe_nao_calculados(X) OR
    distancia_entre_clique_real_e_capturado(X) > 5_pixels
  )
END FUNCTION

FUNCTION brain_nao_aprendeu(X)
  // Brain não aprende quando seletores são descartados
  RETURN (
    X.elemento_alvo.seletor_hint CONTAINS ":has-text(" AND
    NOT X.elemento_alvo.seletor_hint STARTS_WITH ("text=", "[", "#", "button.", "p-", "mat-")
  )
END FUNCTION
```

### Property Specification — Fix Checking por Camada

```pascal
// Property 1: Sniper Semântico deve acertar ANTES de Coordenadas
FOR ALL X WHERE sniper_falhou(X) DO
  seletores_fortalecidos ← gerar_seletores_robustos(X)
  resultado_sniper ← tentar_sniper(seletores_fortalecidos)
  
  ASSERT resultado_sniper.sucesso == true
  ASSERT resultado_sniper.camada == "2_S_sniper"
  ASSERT NOT resultado_sniper.escalou_para_gemini_vision
END FOR

// Property 2: Template Matching deve funcionar para elementos pequenos
FOR ALL X WHERE template_matching_falhou(X) DO
  screenshot_elem ← capturar_screenshot_elemento(X)
  resultado_template ← tentar_template_matching(screenshot_elem, threshold=0.70)
  
  ASSERT screenshot_elem != null
  ASSERT resultado_template.sucesso == true OR threshold_reduzido_tentado(resultado_template)
END FOR

// Property 3: Coordenadas devem ser precisas quando usadas
FOR ALL X WHERE coords_falhou(X) DO
  coords_corrigidas ← capturar_coordenadas_com_offsets(X)
  coords_recalculadas ← recalcular_via_bounding_box(X)
  
  ASSERT coords_corrigidas.offsets_calculados == true IF X.iframe_hint != null
  ASSERT coords_recalculadas != coords_capturadas  // deve recalcular, não reusar
  ASSERT distancia(coords_recalculadas, centro_real_elemento(X)) <= 5px
END FOR

// Property 4: Brain deve aprender seletores que funcionaram
FOR ALL X WHERE brain_nao_aprendeu(X) DO
  seletor_vencedor ← obter_seletor_que_funcionou(X)
  brain_registrou ← registrar_sucesso_cache(X.intencao, seletor_vencedor)
  
  ASSERT brain_registrou == true
  ASSERT seletor_vencedor IN prefixos_validos OR seletor_vencedor CONTAINS ":has-text("
END FOR
```

### Preservation Goal

```pascal
// Property: Preservation Checking — Elementos com Seletores Estáveis
FOR ALL X WHERE NOT isBugCondition(X) DO
  // F = função de captura/execução original
  // F' = função de captura/execução corrigida
  
  ASSERT F(X) == F'(X)
  // Elementos com texto visível, aria-label, data-testid devem continuar
  // sendo localizados e clicados da mesma forma, sem regressão
END FOR
```

---

## Solution Strategy — Fortalecer Camadas Semânticas

A solução NÃO é "consertar coordenadas". A solução é **fortalecer as camadas semânticas (Sniper, Template Matching, Brain) para que o sistema NÃO precise escalar até Gemini Vision**.

### Fase 1: Fortalecer Camada 2_S (Sniper Semântico) — PRIORIDADE MÁXIMA

**Objetivo:** Fazer o Sniper acertar 80% dos casos que hoje escalam para Gemini Vision.

**Mudanças em `capture_dual_output.py`:**
1. Melhorar `getBestSelector()` para gerar seletores mais robustos:
   - Checkboxes PrimeNG: capturar TANTO `:has-text()` QUANTO ID do item pai como fallback
   - Toggles/ícones: forçar captura de `aria-label` ou `data-testid` via JavaScript injection
   - Menus de contexto: detectar overlay CDK e gerar seletores escopados (`p-dialog button:has-text("Sim")`)

2. Adicionar metadados de confiança ao seletor:
   - `confianca_seletor`: "alta" (data-testid, aria-label), "media" (text, :has-text), "baixa" (nth-child, ID numérico)
   - Permitir que `vision_engine.py` priorize candidatos por confiança

**Mudanças em `vision_engine.py`:**
1. `_gerar_candidatos()` deve gerar MÚLTIPLOS candidatos para checkboxes:
   - Candidato 1: `item:has-text("Nome") .ui-chkbox .ui-chkbox-box`
   - Candidato 2: `item#file_8 .ui-chkbox .ui-chkbox-box`
   - Candidato 3: `[aria-label="Nome"] .ui-chkbox-box`

2. Tentar TODOS os candidatos (não apenas o primeiro) e registrar qual funcionou no Brain

### Fase 2: Fortalecer Camada 1_T (Template Matching)

**Objetivo:** Fazer Template Matching funcionar para elementos pequenos (checkboxes 16x16px).

**Mudanças em `capture_dual_output.py`:**
1. Garantir que `screenshot_elemento` é capturado para TODOS os elementos (não apenas alguns)
2. Adicionar retry com timeout maior se `locator.screenshot()` falhar

**Mudanças em `vision_engine.py`:**
1. Reduzir threshold de 0.80 para 0.70 para elementos pequenos (< 50x50px)
2. Implementar fallback: se Template Matching falha com 0.70, tentar com 0.60
3. Logar quando Template Matching é usado com sucesso (telemetria)

### Fase 3: Consertar Camada 2 (Coordenadas) como Último Recurso

**Objetivo:** Coordenadas devem ser precisas quando TODAS as outras camadas falharem.

**Mudanças em `capture_dual_output.py`:**
1. Chamar `getRectComFallback()` SEMPRE (não apenas em fallback)
2. Somar offsets de `iframe.getBoundingClientRect()` ao calcular coordenadas
3. Armazenar metadados completos: `viewport_size`, `offsets`, `elemento_rect`

**Mudanças em `vision_engine.py`:**
1. Recalcular coordenadas via `locator.boundingBox()` na execução (não reusar coordenadas capturadas)
2. Usar coordenadas capturadas apenas como hint de posição aproximada
3. Implementar `_verificar_identidade_por_coordenadas()` robusto para iframes

### Fase 4: Melhorar Brain (Camada 0)

**Objetivo:** Brain deve aprender seletores que funcionaram, incluindo seletores PrimeNG/Angular.

**Mudanças em `vision_engine.py`:**
1. Adicionar `:has-text(` aos `_PREFIXOS_VALIDOS` em `_registrar_sucesso_cache()`
2. Implementar "Brain proativo": quando Sniper acerta, registrar TODOS os candidatos que funcionaram
3. Evitar registro duplo de falhas (flag `brain_falhou` para controlar)

---

## Key Definitions

- **F**: Função original de captura/execução — código atual em `capture.py` e `vision_engine.py` antes da correção
- **F'**: Função corrigida de captura/execução — código após aplicar o bugfix
- **isBugCondition(X)**: Predicate que identifica ações onde as camadas semânticas falharam em cascata
- **Counterexample**: Roteiro `Senior_Flow_-_SIGN_-_Templates_de_Envelo.json` — ação de ativar "Visualização obrigatória" (toggle) quebra porque Sniper falha (seletor frágil), Template Matching falha (screenshot_elemento ausente), Coordenadas falham (offsets incorretos), Brain não aprende (seletor descartado)

---

## Root Cause Analysis — Cascade Failure

### Causa Raiz Real

A causa raiz NÃO é "coordenadas imprecisas". A causa raiz é uma **FALHA EM CASCATA** nas camadas semânticas que ocorre ANTES de chegar nas coordenadas:

```
┌─────────────────────────────────────────────────────────────┐
│ CASCATA DE FALHAS (do mais barato ao mais caro)            │
├─────────────────────────────────────────────────────────────┤
│ Camada 0 (Brain)           → FALHA (não aprende seletores) │
│ Camada 2_S (Sniper)        → FALHA (seletores fracos)      │
│ Camada 1_T (Template)      → FALHA (threshold alto)        │
│ Camada 2 (Coordenadas)     → FALHA (offsets incorretos)    │
│ Camada 5 (Gemini Vision)   → SUCESSO (caro e lento)        │
└─────────────────────────────────────────────────────────────┘
```

**Resultado:** Sistema escala até Gemini Vision para TUDO, tornando execução lenta, cara, e não confiável.

### Análise Detalhada por Camada

#### Camada 2_S (Sniper Semântico) — 80% do Problema

**Por que falha:**
1. `getBestSelector()` no `capture.py` gera seletores baseados em texto (`:has-text()`) que quebram quando o texto muda ligeiramente
2. Checkboxes PrimeNG: seletor `item:has-text("Nome") .ui-chkbox .ui-chkbox-box` funciona na captura mas falha se "Nome" virar "Nome da Pasta"
3. Toggles/ícones sem texto: não têm aria-label, data-testid, ou atributos semânticos — seletor gerado é posicional (`:nth-child(2)`)
4. Menus de contexto sobre iframes: seletor não considera escopo do overlay CDK

**Evidência no código:**
- `capture_dual_output.py` linha ~350: `getBestSelector()` prioriza `:has-text()` sobre atributos estáveis
- `vision_engine.py` linha ~450: `_gerar_candidatos()` tenta `:has-text()` mas não tem fallbacks robustos

#### Camada 1_T (Template Matching) — 10% do Problema

**Por que falha:**
1. `screenshot_elemento` não é capturado para TODOS os elementos (apenas alguns)
2. Threshold de 0.80 é muito alto para elementos pequenos (checkboxes 16x16px)
3. Não há fallback para threshold mais baixo (0.60-0.70) quando falha

**Evidência no código:**
- `capture_dual_output.py` linha ~580: `screenshot_elemento` capturado via `locator.screenshot()` mas pode falhar silenciosamente
- `vision_engine.py` (não visível no trecho lido): Template Matching usa threshold fixo 0.80

#### Camada 2 (Coordenadas) — 10% do Problema

**Por que falha:**
1. `getBoundingClientRect()` retorna rect zerado para elementos Angular em transição
2. `getRectComFallback()` existe mas pode não estar sendo chamado corretamente
3. Coordenadas não somam offsets de iframe (`iframe.getBoundingClientRect()`)
4. `vision_engine.py` não recalcula via `locator.boundingBox()` na execução

**Evidência no código:**
- `capture_dual_output.py` linha ~350: `getRectComFallback()` implementado mas pode não ser chamado sempre
- `capture_dual_output.py` linha ~120: `_extrair_coordenadas_relativas()` usa `rect.x` que pode estar errado
- `vision_engine.py` (não visível): não há recálculo via `locator.boundingBox()`

#### Camada 0 (Brain) — Consequência, não Causa

**Por que não aprende:**
1. `_registrar_sucesso_cache()` descarta seletores que não começam com prefixos válidos
2. Seletores PrimeNG com `:has-text(` são descartados
3. Quando TODAS as camadas falham, Brain nunca aprende o seletor correto

**Evidência no código:**
- `vision_engine.py` linha ~250: `_PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")` — não inclui `:has-text(`

### Proporção do Problema

```
┌──────────────────────────────────────────────────┐
│ 80% → Sniper Semântico (seletores fracos)       │
│ 10% → Template Matching (threshold alto)        │
│ 10% → Coordenadas (offsets incorretos)          │
└──────────────────────────────────────────────────┘
```

**Coordenadas são apenas 10% do problema. 90% do problema é que as camadas semânticas (Sniper, Template Matching, Brain) estão falhando ANTES de chegar nas coordenadas.**

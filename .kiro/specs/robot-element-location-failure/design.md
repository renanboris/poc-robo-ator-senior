# Robot Element Location Failure - Bugfix Design

## Overview

O robô falha sistematicamente ao localizar elementos dentro de iframes porque a verificação de identidade na camada `2_coords_capturadas` executa `document.elementFromPoint(x, y)` no contexto da página principal. Quando as coordenadas apontam para dentro de um iframe, o método retorna o elemento `<iframe>` em si (cujo texto visível é "iframe platform"), não o elemento interno que está nas coordenadas.

A solução implementa detecção recursiva de iframes: quando `elementFromPoint` retorna um iframe, o sistema ajusta as coordenadas para o sistema de coordenadas do iframe e executa `elementFromPoint` novamente no contexto do iframe até encontrar o elemento final (não-iframe).

**Impacto esperado:**
- Taxa de sucesso da camada `2_coords_capturadas`: de 5-6% para >90%
- Taxa de intervenção manual (HITL): de 29% para <10%
- Novos mapeamentos funcionarão sem fallbacks desnecessários

## Glossary

- **Bug_Condition (C)**: A condição que dispara o bug - quando coordenadas capturadas apontam para dentro de um iframe e `elementFromPoint` é executado no contexto da página principal
- **Property (P)**: O comportamento desejado - `elementFromPoint` deve ser executado no contexto correto (dentro do iframe) com coordenadas ajustadas
- **Preservation**: Comportamento existente para elementos fora de iframes que deve permanecer inalterado
- **elementFromPoint**: Método JavaScript que retorna o elemento presente em coordenadas (x, y) específicas
- **iframe_hint**: Metadado opcional no `elemento_alvo` que indica qual iframe contém o elemento
- **coordenadas_relativas**: Coordenadas percentuais (x_pct, y_pct) capturadas durante a gravação, relativas ao viewport
- **coords_capturadas**: Camada 2 da cascata de fallback que usa coordenadas da gravação para localizar elementos

## Bug Details

### Bug Condition

O bug manifesta-se quando a camada `2_coords_capturadas` tenta verificar a identidade de um elemento que está dentro de um iframe. O sistema executa `page.evaluate("document.elementFromPoint(x, y)")` no contexto da página principal, que retorna o elemento `<iframe>` em vez do elemento interno.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type {x: int, y: int, page: Page, label_curto: str}
  OUTPUT: boolean
  
  RETURN input.x > 0 AND input.y > 0
         AND elementAtCoords(input.page, input.x, input.y).tagName == "IFRAME"
         AND elementAtCoords(input.page, input.x, input.y).innerText == "iframe platform"
         AND input.label_curto NOT IN elementAtCoords(input.page, input.x, input.y).innerText
END FUNCTION
```

### Examples

- **Exemplo 1**: Coordenadas (960, 540) apontam para botão "Acompanhar assinaturas" dentro de iframe Senior X
  - **Atual**: `elementFromPoint(960, 540)` retorna `<iframe>`, texto encontrado: "iframe platform"
  - **Esperado**: Detectar iframe, ajustar coordenadas, executar `iframe.contentWindow.document.elementFromPoint(x_rel, y_rel)`, encontrar botão com texto "Acompanhar assinaturas"

- **Exemplo 2**: Coordenadas (500, 300) apontam para link "Histórico" dentro de iframe aninhado
  - **Atual**: `elementFromPoint(500, 300)` retorna `<iframe>`, verificação de identidade falha
  - **Esperado**: Recursivamente detectar iframes aninhados, ajustar coordenadas em cada nível, encontrar link correto

- **Exemplo 3**: Coordenadas (100, 100) apontam para botão "Salvar" na página principal (fora de iframe)
  - **Atual**: `elementFromPoint(100, 100)` retorna `<button>`, texto "Salvar", verificação passa
  - **Esperado**: Comportamento inalterado - nenhuma detecção de iframe necessária

- **Edge case**: Coordenadas (800, 400) apontam para iframe cross-origin (sem acesso ao contentWindow)
  - **Esperado**: Detectar cross-origin, aplicar fail-open (aceitar clique sem verificação de identidade), registrar warning

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Elementos na página principal (fora de iframes) devem continuar a ser localizados exatamente como antes
- Verificação de identidade fail-open (quando `label_curto` vazio ou `page.evaluate` falha) deve continuar funcionando
- Todas as outras camadas de fallback (Brain, Template Matching, Sniper, Hint Original, Todos os Frames, Gemini Vision) devem continuar funcionando sem alteração
- Telemetria e logs de WARNING para fallbacks devem continuar sendo registrados da mesma forma
- Comportamento de scroll e highlight visual deve permanecer inalterado

**Scope:**
Todas as entradas que NÃO envolvem coordenadas apontando para dentro de iframes devem ser completamente inalteradas por esta correção. Isso inclui:
- Cliques em elementos da página principal
- Digitação em campos fora de iframes
- Ações em elementos localizados por seletores (Sniper, Brain, Hint Original)
- Fallback para Gemini Vision quando coordenadas falham

## Hypothesized Root Cause

Baseado na análise do código e nos logs de falha, as causas mais prováveis são:

1. **Contexto de Execução Incorreto**: O método `page.evaluate("document.elementFromPoint(x, y)")` é executado no contexto da página principal (`document`), não no contexto do iframe. Quando as coordenadas apontam para dentro de um iframe, o método retorna o elemento `<iframe>` em si, não o elemento interno.

2. **Coordenadas Não Ajustadas**: As coordenadas (x, y) são absolutas em relação ao viewport da página principal. Para acessar elementos dentro de um iframe, as coordenadas precisam ser ajustadas para o sistema de coordenadas do iframe (subtraindo a posição do iframe: `x_rel = x - iframe.offsetLeft`, `y_rel = y - iframe.offsetTop`).

3. **Falta de Detecção de Iframe**: O código atual não verifica se o elemento retornado por `elementFromPoint` é um iframe. Não há lógica para detectar essa situação e recursivamente buscar dentro do iframe.

4. **iframe_hint Não Utilizado**: O campo `iframe_hint` está disponível no `elemento_alvo`, mas não é usado pela camada `2_coords_capturadas` para resolver o contexto correto antes de executar `elementFromPoint`.

## Correctness Properties

Property 1: Bug Condition - Iframe Detection and Context Resolution

_For any_ input where coordenadas capturadas apontam para dentro de um iframe (isBugCondition returns true), o sistema fixado SHALL detectar o iframe, ajustar as coordenadas para o sistema de coordenadas do iframe, executar `elementFromPoint` no contexto do iframe, e encontrar o elemento correto com o texto esperado (`label_curto`).

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5**

Property 2: Preservation - Non-Iframe Element Behavior

_For any_ input onde coordenadas apontam para elementos fora de iframes (isBugCondition returns false), o sistema fixado SHALL produzir exatamente o mesmo resultado que o sistema original, preservando o comportamento de verificação de identidade, clique, e telemetria para elementos na página principal.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assumindo que nossa análise de causa raiz está correta:

**File**: `vision_engine.py`

**Function**: `encontrar_e_clicar` (camada `2_coords_capturadas`, linhas ~1456-1503)

**Specific Changes**:

1. **Criar Função Auxiliar `_resolver_elemento_em_iframe`**: Nova função que detecta recursivamente iframes e ajusta coordenadas
   - **Input**: `page: Page, x: int, y: int, max_depth: int = 5`
   - **Output**: `tuple[Any, int, int]` - (elemento_final, x_ajustado, y_ajustado)
   - **Lógica**:
     - Executar `elementFromPoint(x, y)` no contexto atual
     - Se elemento retornado é iframe:
       - Obter bounding box do iframe (`iframe.getBoundingClientRect()`)
       - Calcular coordenadas relativas: `x_rel = x - bbox.left`, `y_rel = y - bbox.top`
       - Verificar se iframe é cross-origin (try/catch em `iframe.contentWindow`)
       - Se cross-origin: retornar (iframe, x, y) com flag de cross-origin
       - Se acessível: recursivamente chamar `_resolver_elemento_em_iframe` no contexto do iframe com (x_rel, y_rel)
     - Se elemento não é iframe: retornar (elemento, x, y)
     - Se max_depth atingido: retornar (elemento_atual, x, y) com warning

2. **Modificar Verificação de Identidade na Camada `2_coords_capturadas`**: Substituir `page.evaluate("document.elementFromPoint(x, y)")` por chamada a `_resolver_elemento_em_iframe`
   - Antes: `texto_elemento = await page.evaluate("([x, y]) => { const el = document.elementFromPoint(x, y); return el ? el.innerText : ''; }", [x, y])`
   - Depois: `elemento, x_final, y_final = await _resolver_elemento_em_iframe(page, x, y)`
   - Ler `innerText` do elemento retornado (não do iframe)
   - Se cross-origin detectado: aplicar fail-open (aceitar clique sem verificação)

3. **Usar `iframe_hint` Quando Disponível**: Se `iframe_hint` presente no `elemento_alvo`, usar `_resolver_contexto(page, iframe_hint)` para obter o frame correto antes de executar `elementFromPoint`
   - Ajustar coordenadas para o sistema de coordenadas do iframe usando bounding box
   - Executar `elementFromPoint` diretamente no contexto do iframe

4. **Adicionar Logs de Diagnóstico**: Emitir logs INFO quando iframe é detectado e coordenadas são ajustadas
   - `logger.info(f"[Coords Capturadas] Iframe detectado em ({x}, {y}), ajustando para ({x_rel}, {y_rel})")`
   - `logger.warning(f"[Coords Capturadas] Iframe cross-origin detectado - aplicando fail-open")`

5. **Preservar Fail-Open Existente**: Manter comportamento fail-open quando `label_curto` vazio ou `page.evaluate` lança exceção
   - Adicionar fail-open específico para iframes cross-origin
   - Registrar warning quando fail-open é aplicado

### Pseudocode da Solução

```python
async def _resolver_elemento_em_iframe(
    page: Page, x: int, y: int, max_depth: int = 5
) -> tuple[Any, int, int, bool]:
    """
    Resolve recursivamente o elemento em coordenadas (x, y), detectando iframes.
    
    Returns: (elemento_final, x_ajustado, y_ajustado, is_cross_origin)
    """
    if max_depth <= 0:
        logger.warning("[iframe] Max depth atingido - retornando elemento atual")
        elemento = await page.evaluate("([x, y]) => document.elementFromPoint(x, y)", [x, y])
        return (elemento, x, y, False)
    
    try:
        resultado = await page.evaluate("""
            ([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return {tipo: 'null'};
                
                if (el.tagName === 'IFRAME') {
                    const bbox = el.getBoundingClientRect();
                    return {
                        tipo: 'iframe',
                        left: bbox.left,
                        top: bbox.top,
                        src: el.src || '',
                        name: el.name || ''
                    };
                }
                
                return {
                    tipo: 'elemento',
                    tagName: el.tagName,
                    innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                };
            }
        """, [x, y])
        
        if resultado['tipo'] == 'iframe':
            # Ajustar coordenadas para o sistema do iframe
            x_rel = x - resultado['left']
            y_rel = y - resultado['top']
            
            logger.info(f"[iframe] Detectado em ({x}, {y}), ajustando para ({x_rel}, {y_rel})")
            
            # Tentar acessar o iframe
            iframe_src = resultado.get('src', '')
            iframe_name = resultado.get('name', '')
            
            # Resolver o frame usando Playwright
            frame = None
            for f in page.frames:
                if iframe_src and iframe_src in f.url:
                    frame = f
                    break
                if iframe_name and iframe_name == f.name:
                    frame = f
                    break
            
            if not frame:
                # Cross-origin ou frame não encontrado
                logger.warning(f"[iframe] Cross-origin ou não acessível - fail-open")
                return (None, x, y, True)
            
            # Recursivamente resolver no contexto do iframe
            return await _resolver_elemento_em_iframe_frame(frame, x_rel, y_rel, max_depth - 1)
        
        else:
            # Elemento final encontrado
            return (resultado, x, y, False)
    
    except Exception as exc:
        logger.warning(f"[iframe] Erro ao resolver elemento: {exc}")
        return (None, x, y, False)


async def _resolver_elemento_em_iframe_frame(
    frame: Frame, x: int, y: int, max_depth: int
) -> tuple[Any, int, int, bool]:
    """Versão da função para contexto de Frame (não Page)."""
    # Implementação similar, mas usando frame.evaluate em vez de page.evaluate
    # ... (lógica idêntica adaptada para Frame)
```

**Integração na Camada `2_coords_capturadas`:**

```python
# ── 2. Coordenadas Capturadas (gravação original) ────────────────────────
if coords_relativas and coords_relativas.get("x_pct"):
    logger.info("   [Coords Capturadas] Tentando coordenadas relativas da gravação...")
    try:
        vp = page.viewport_size or {"width": 1920, "height": 1080}
        x  = int(coords_relativas["x_pct"] * vp["width"])
        y  = int(coords_relativas["y_pct"] * vp["height"])
        
        # [FIX] Usar iframe_hint se disponível
        contexto_inicial = page
        if iframe_hint:
            contexto_inicial = await _resolver_contexto(page, iframe_hint)
            # Ajustar coordenadas se contexto é um frame
            if hasattr(contexto_inicial, 'bounding_box'):
                bbox = await contexto_inicial.bounding_box()
                if bbox:
                    x = x - int(bbox['x'])
                    y = y - int(bbox['y'])
        
        if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
            # [FIX] Verificar identidade com detecção de iframe
            identidade_confirmada = False
            if label_curto:
                try:
                    elemento, x_final, y_final, is_cross_origin = await _resolver_elemento_em_iframe(page, x, y)
                    
                    if is_cross_origin:
                        # Fail-open para iframes cross-origin
                        logger.warning(f"[Coords Capturadas] Iframe cross-origin - fail-open aplicado")
                        identidade_confirmada = True
                    elif elemento and elemento.get('innerText'):
                        texto_elemento = elemento['innerText']
                        if label_curto.strip().lower() in texto_elemento.strip().lower():
                            identidade_confirmada = True
                        else:
                            logger.warning(
                                f"[Coords Capturadas] Identidade não confirmada: "
                                f"esperado '{label_curto}', encontrado '{texto_elemento[:50]}' em ({x_final}, {y_final})"
                            )
                    else:
                        # Fail-open: elemento sem texto
                        identidade_confirmada = True
                        
                except Exception as exc_verify:
                    # Fail-open: se verificação falhar
                    logger.warning(f"[Coords Capturadas] Verificação falhou (fail-open): {exc_verify}")
                    identidade_confirmada = True
            else:
                # Fail-open: label_curto vazio
                identidade_confirmada = True

            if identidade_confirmada:
                logger.info(f"[Coords Capturadas] Clique em ({x}, {y}) bem-sucedido.")
                _registrar_telemetria("2_coords_capturadas", True)
                _registrar_estrategia_vencedora(intencao, "2_coords_capturadas")
                return True
            else:
                logger.info("[Coords Capturadas] Escalando (identidade não confirmada).")
    except Exception as exc:
        logger.warning(f"[Coords Capturadas] Falhou: {exc}")
    _registrar_telemetria("2_coords_capturadas", False)
```

## Testing Strategy

### Validation Approach

A estratégia de testes segue uma abordagem de duas fases: primeiro, demonstrar o bug no código não corrigido (exploratory bug condition checking), depois verificar que a correção funciona e preserva o comportamento existente (fix checking e preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotetisar.

**Test Plan**: Escrever testes que simulam coordenadas apontando para dentro de iframes e verificam que `elementFromPoint` retorna o iframe (não o elemento interno). Executar esses testes no código NÃO CORRIGIDO para observar falhas e confirmar a causa raiz.

**Test Cases**:
1. **Iframe Simples**: Coordenadas (960, 540) apontam para botão "Salvar" dentro de iframe (falhará no código não corrigido - retorna "iframe platform")
2. **Iframe Aninhado**: Coordenadas (500, 300) apontam para link dentro de iframe aninhado (falhará no código não corrigido - retorna iframe externo)
3. **Iframe Cross-Origin**: Coordenadas (800, 400) apontam para iframe cross-origin (falhará no código não corrigido - sem fail-open específico)
4. **Elemento Fora de Iframe**: Coordenadas (100, 100) apontam para botão na página principal (passará no código não corrigido - comportamento correto)

**Expected Counterexamples**:
- `elementFromPoint(960, 540)` retorna `<iframe>` com texto "iframe platform" em vez de `<button>` com texto "Salvar"
- Verificação de identidade falha porque "Salvar" não está em "iframe platform"
- Taxa de sucesso da camada `2_coords_capturadas` permanece em 5-6%

### Fix Checking

**Goal**: Verificar que para todas as entradas onde a condição de bug é verdadeira (coordenadas apontam para dentro de iframe), a função corrigida produz o comportamento esperado (detecta iframe, ajusta coordenadas, encontra elemento correto).

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  elemento, x_final, y_final, is_cross_origin := _resolver_elemento_em_iframe(input.page, input.x, input.y)
  ASSERT elemento.innerText CONTAINS input.label_curto OR is_cross_origin == True
  ASSERT elemento.tagName != "IFRAME" OR is_cross_origin == True
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todas as entradas onde a condição de bug NÃO é verdadeira (coordenadas apontam para elementos fora de iframes), a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  resultado_original := encontrar_e_clicar_original(input)
  resultado_fixado := encontrar_e_clicar_fixed(input)
  ASSERT resultado_original == resultado_fixado
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente através do domínio de entrada
- Captura edge cases que testes unitários manuais podem perder
- Fornece garantias fortes de que o comportamento é inalterado para todas as entradas não-buggy

**Test Plan**: Observar comportamento no código NÃO CORRIGIDO primeiro para elementos fora de iframes, depois escrever testes baseados em propriedades capturando esse comportamento.

**Test Cases**:
1. **Elementos na Página Principal**: Verificar que cliques em botões, links, inputs fora de iframes continuam funcionando exatamente como antes
2. **Verificação de Identidade Fail-Open**: Verificar que fail-open (label_curto vazio, page.evaluate falha) continua funcionando
3. **Outras Camadas de Fallback**: Verificar que Brain, Sniper, Gemini Vision continuam funcionando sem degradação
4. **Telemetria e Logs**: Verificar que telemetria e logs são registrados da mesma forma

### Unit Tests

- Testar `_resolver_elemento_em_iframe` com mock de page que retorna iframe em coordenadas específicas
- Testar ajuste de coordenadas (x_rel = x - bbox.left, y_rel = y - bbox.top)
- Testar detecção de cross-origin (contentWindow inacessível)
- Testar recursão com iframes aninhados (max_depth)
- Testar integração com `iframe_hint` (usar hint para resolver contexto antes de elementFromPoint)

### Property-Based Tests

- Gerar coordenadas aleatórias e verificar que elementos fora de iframes são localizados corretamente
- Gerar configurações aleatórias de iframes e verificar que elementos dentro de iframes são localizados
- Testar que taxa de sucesso da camada `2_coords_capturadas` aumenta de 5-6% para >90% após correção
- Testar que todas as outras camadas de fallback continuam funcionando sem degradação

### Integration Tests

- Testar fluxo completo de execução de roteiro com elementos em iframes (Senior X)
- Testar que taxa de HITL cai de 29% para <10% após correção
- Testar que novos mapeamentos funcionam sem fallbacks desnecessários
- Testar que telemetria registra corretamente acertos/falhas da camada `2_coords_capturadas`

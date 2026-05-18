# SoM Box Matching Tolerance Fix - Bugfix Design

## Overview

O sistema de captura usa Set-of-Mark (SoM) para detectar elementos interativos na tela e associar cliques do usuário a esses elementos através da função `identificar_box_clicada` em `som_annotator.py`. A função atual usa matching estrito de boundaries (x <= click_x <= x+w AND y <= click_y <= y+h), que falha quando o clique está alguns pixels fora da box detectada devido a offsets de ícones, padding, ou imprecisão do radar.

Este bugfix implementa uma estratégia de matching com tolerância baseada em distância ao centro da box, permitindo que cliques próximos (mas não exatamente dentro) sejam corretamente associados às boxes detectadas pelo SoM.

**Impacto do Bug:**
- SCORM gerado usa labels genéricos em vez de labels descritivos do SoM
- Zonas interativas aparecem em locais imprecisos
- Experiência de treinamento degradada
- Afeta todos os roteiros onde o clique não está exatamente dentro da box detectada

**Estratégia de Fix:**
Implementar matching com tolerância baseado em distância ao centro da box, mantendo a priorização de boxes menores (mais específicas) em caso de overlap ou proximidade similar.

## Glossary

- **Bug_Condition (C)**: A condição que desencadeia o bug - quando o clique está próximo de uma box detectada (dentro de tolerância razoável) mas o matching estrito falha
- **Property (P)**: O comportamento desejado quando o bug ocorre - o sistema deve retornar o `som_idx_clicado` e `som_box_clicada` da box mais próxima dentro da tolerância
- **Preservation**: O comportamento existente que deve permanecer inalterado - cliques exatamente dentro de boxes devem continuar funcionando, cliques muito distantes devem continuar retornando null
- **identificar_box_clicada**: A função em `som_annotator.py` (linha ~58) que recebe a lista de boxes e coordenadas do clique e retorna o idx da box clicada
- **SoM (Set-of-Mark)**: Sistema que detecta elementos interativos na tela e desenha bounding boxes numeradas sobre eles
- **Box**: Caixa delimitadora ao redor de um elemento interativo, com campos: idx, x, y, w, h, role, label
- **Tolerância**: Distância máxima permitida entre o clique e o centro da box para considerar um match válido (30% da maior dimensão da box)
- **Matching Estrito**: Estratégia atual que verifica se o clique está dentro dos boundaries da box (x <= click_x <= x+w AND y <= click_y <= y+h)
- **Matching com Tolerância**: Estratégia proposta que calcula a distância do clique ao centro da box e aceita matches dentro de uma tolerância razoável

## Bug Details

### Bug Condition

O bug manifesta-se quando um usuário clica em um elemento interativo e as coordenadas do clique estão alguns pixels fora da box detectada pelo SoM (devido a offsets de ícones, padding, ou imprecisão do radar). A função `identificar_box_clicada` usa matching estrito de boundaries sem tolerância, resultando em falha de matching mesmo quando o clique está claramente próximo de uma box detectada.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type ClickEvent with fields:
    - click_x: integer (coordenada x do clique)
    - click_y: integer (coordenada y do clique)
    - boxes: array of Box (boxes detectadas pelo SoM)
    - Box has fields: x, y, w, h, idx
  OUTPUT: boolean
  
  // Retorna true quando o clique está próximo de uma box mas o matching estrito falha
  FOR EACH box IN input.boxes DO
    // Verifica se o clique está dentro da box (matching estrito)
    IF (box.x <= input.click_x <= box.x + box.w) AND 
       (box.y <= input.click_y <= box.y + box.h) THEN
      RETURN false  // Matching estrito funciona, não é bug
    END IF
    
    // Verifica se o clique está próximo da box (dentro de tolerância razoável)
    distance_to_center = SQRT((input.click_x - (box.x + box.w/2))^2 + 
                              (input.click_y - (box.y + box.h/2))^2)
    max_dimension = MAX(box.w, box.h)
    tolerance = max_dimension * 0.3  // 30% da maior dimensão
    
    IF distance_to_center <= tolerance THEN
      RETURN true  // Clique próximo mas matching estrito falhou = BUG
    END IF
  END FOR
  
  RETURN false  // Clique muito distante de qualquer box, não é bug
END FUNCTION
```

### Examples

- **Ação 6 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos"**: Clique em coordenadas (x=256, y=205) com 20 boxes detectadas. O matching estrito falhou, retornando `som_idx_clicado: null` e `som_box_clicada: null`. Esperado: retornar o idx da box mais próxima dentro da tolerância.

- **Ação 7 do mesmo roteiro**: Clique em coordenadas (x=1199, y=27) com 20 boxes detectadas. O matching estrito falhou, retornando `som_idx_clicado: null` e `som_box_clicada: null`. Esperado: retornar o idx da box mais próxima dentro da tolerância.

- **Clique em ícone com padding**: Usuário clica no centro visual de um ícone, mas o SoM detectou a box ao redor do botão pai. O clique está 5 pixels fora da box detectada. Esperado: matching bem-sucedido com a box do botão pai.

- **Edge case - Clique muito distante**: Usuário clica em coordenadas (x=50, y=50) e a box mais próxima está em (x=500, y=500). Esperado: retornar null (comportamento preservado).

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Cliques exatamente dentro de uma box detectada pelo SoM (coordenadas dentro dos boundaries estritos) devem continuar retornando o `som_idx_clicado` e `som_box_clicada` corretos
- O SoM deve continuar detectando e numerando as boxes corretamente
- Cliques muito distantes de qualquer box detectada (fora de qualquer tolerância razoável) devem continuar retornando `som_idx_clicado: null` e `som_box_clicada: null`
- Múltiplas boxes se sobrepondo com clique dentro de múltiplas boxes devem continuar retornando a box com menor área (mais específica)

**Scope:**
Todos os inputs que NÃO envolvem cliques próximos mas fora da box detectada devem ser completamente inalterados por este fix. Isso inclui:
- Cliques exatamente dentro de boxes (matching estrito bem-sucedido)
- Cliques muito distantes de qualquer box (fora de tolerância)
- Casos de overlap onde o clique está dentro de múltiplas boxes

## Hypothesized Root Cause

Baseado na análise do código em `som_annotator.py` (função `identificar_box_clicada`, linha ~58), as causas mais prováveis são:

1. **Matching Estrito Sem Tolerância**: A função usa apenas verificação de boundaries estritos (bx <= x <= bx + bw and by <= y <= by + bh), sem considerar proximidade ou tolerância para cliques que estão alguns pixels fora da box.

2. **Imprecisão do Radar JavaScript**: O script radar que captura as coordenadas do clique pode ter pequenos offsets devido a:
   - Transformações CSS (translate, scale)
   - Padding/margin dos elementos
   - Diferença entre o elemento visual clicado e o elemento interativo detectado pelo SoM
   - Timing entre o clique e a captura das coordenadas

3. **Diferença entre Elemento Visual e Box Detectada**: O SoM detecta elementos interativos (buttons, links, inputs), mas o usuário pode clicar em elementos visuais filhos (ícones, spans, texto) que estão alguns pixels fora da box do elemento pai.

4. **Ausência de Estratégia de Fallback**: A função não tem uma estratégia de fallback para encontrar a box mais próxima quando o matching estrito falha, resultando em retorno imediato de null.

## Correctness Properties

Property 1: Bug Condition - Matching com Tolerância

_For any_ input where the bug condition holds (clique próximo de uma box mas matching estrito falha), the fixed `identificar_box_clicada` function SHALL return the `som_idx_clicado` and `som_box_clicada` of the closest box within tolerance, ensuring that clicks near interactive elements are correctly associated with their corresponding SoM boxes.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4**

Property 2: Preservation - Comportamento Existente Inalterado

_For any_ input where the bug condition does NOT hold (cliques exatamente dentro de boxes ou muito distantes), the fixed `identificar_box_clicada` function SHALL produce exactly the same result as the original function, preserving all existing matching behavior for non-buggy inputs.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

Assumindo que nossa análise de causa raiz está correta:

**File**: `som_annotator.py`

**Function**: `identificar_box_clicada` (linha ~58)

**Specific Changes**:

1. **Preservar Matching Estrito Existente**: Manter a lógica atual que verifica se o clique está dentro dos boundaries da box. Se encontrar match estrito, retornar imediatamente (comportamento preservado).

2. **Adicionar Cálculo de Distância ao Centro**: Para cada box, calcular a distância euclidiana do clique ao centro da box:
   ```python
   center_x = box["x"] + box["w"] / 2
   center_y = box["y"] + box["h"] / 2
   distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
   ```

3. **Definir Tolerância Dinâmica**: Calcular tolerância baseada na maior dimensão da box (30% da maior dimensão):
   ```python
   max_dimension = max(box["w"], box["h"])
   tolerance = max_dimension * 0.3
   ```

4. **Coletar Candidatos Dentro da Tolerância**: Criar lista de boxes candidatas onde `distance <= tolerance`.

5. **Priorizar Box Mais Próxima**: Se houver candidatos, ordenar por distância crescente e retornar o idx da box mais próxima (menor distância). Em caso de empate na distância, priorizar a box com menor área (mais específica).

6. **Fallback para Null**: Se não houver candidatos dentro da tolerância, retornar None (comportamento preservado para cliques muito distantes).

7. **Adicionar Logging de Debug**: Adicionar logs informativos quando o matching com tolerância é usado (para observabilidade e debugging).

### Pseudocode da Implementação

```python
def identificar_box_clicada(boxes: List[Dict], x: int, y: int) -> Optional[int]:
    """
    Dado o (x, y) do clique e a lista de boxes, retorna o idx da box.
    Usa matching estrito primeiro, depois matching com tolerância.
    Em caso de múltiplos candidatos, retorna a box mais próxima (menor distância).
    """
    import math
    
    # Fase 1: Matching Estrito (comportamento preservado)
    strict_matches = []
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        if bx <= x <= bx + bw and by <= y <= by + bh:
            strict_matches.append(box)
    
    if strict_matches:
        # Prioriza a menor box (mais específica)
        strict_matches.sort(key=lambda b: b["w"] * b["h"])
        return strict_matches[0]["idx"]
    
    # Fase 2: Matching com Tolerância (novo comportamento)
    tolerance_candidates = []
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        
        # Calcula distância ao centro
        center_x = bx + bw / 2
        center_y = by + bh / 2
        distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        # Calcula tolerância (30% da maior dimensão)
        max_dimension = max(bw, bh)
        tolerance = max_dimension * 0.3
        
        if distance <= tolerance:
            tolerance_candidates.append({
                "box": box,
                "distance": distance,
                "area": bw * bh
            })
    
    if tolerance_candidates:
        # Ordena por distância (crescente), depois por área (crescente)
        tolerance_candidates.sort(key=lambda c: (c["distance"], c["area"]))
        logger.info(f"SoM tolerance match: click ({x}, {y}) matched box #{tolerance_candidates[0]['box']['idx']} at distance {tolerance_candidates[0]['distance']:.1f}px")
        return tolerance_candidates[0]["box"]["idx"]
    
    # Fase 3: Nenhum match (comportamento preservado)
    return None
```

## Testing Strategy

### Validation Approach

A estratégia de testes segue uma abordagem de duas fases: primeiro, surfacear contraexemplos que demonstram o bug no código não corrigido, depois verificar que o fix funciona corretamente e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Surfacear contraexemplos que demonstram o bug ANTES de implementar o fix. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisaremos re-hipotetisar.

**Test Plan**: Escrever testes que simulam cliques próximos mas fora de boxes detectadas e verificar que a função não corrigida retorna None. Executar esses testes no código NÃO CORRIGIDO para observar falhas e entender a causa raiz.

**Test Cases**:
1. **Clique Próximo Horizontal**: Simular clique 5 pixels à direita de uma box (x=105, y=50) quando a box está em (x=50, y=50, w=50, h=30). Esperado: função não corrigida retorna None (falha no unfixed code).

2. **Clique Próximo Vertical**: Simular clique 5 pixels abaixo de uma box (x=75, y=85) quando a box está em (x=50, y=50, w=50, h=30). Esperado: função não corrigida retorna None (falha no unfixed code).

3. **Clique em Ícone com Padding**: Simular clique no centro visual de um ícone (x=256, y=205) quando a box detectada está ligeiramente deslocada. Esperado: função não corrigida retorna None (falha no unfixed code - caso real da Ação 6).

4. **Clique Muito Distante**: Simular clique muito distante (x=500, y=500) quando a box mais próxima está em (x=50, y=50, w=50, h=30). Esperado: função não corrigida retorna None (comportamento correto no unfixed code).

**Expected Counterexamples**:
- Função retorna None para cliques próximos mas fora da box (dentro de tolerância razoável)
- Possíveis causas confirmadas: matching estrito sem tolerância, ausência de estratégia de fallback

### Fix Checking

**Goal**: Verificar que para todos os inputs onde a condição de bug se aplica, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := identificar_box_clicada_fixed(input.boxes, input.click_x, input.click_y)
  
  // Verifica que o resultado não é null
  ASSERT result IS NOT null
  
  // Verifica que o resultado é a box mais próxima
  closest_box := find_closest_box_within_tolerance(input.boxes, input.click_x, input.click_y)
  ASSERT result = closest_box.idx
  
  // Verifica que a box retornada está dentro da tolerância
  distance_to_center := calculate_distance_to_center(closest_box, input.click_x, input.click_y)
  max_dimension := MAX(closest_box.w, closest_box.h)
  tolerance := max_dimension * 0.3
  ASSERT distance_to_center <= tolerance
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos os inputs onde a condição de bug NÃO se aplica, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  result_original := identificar_box_clicada_original(input.boxes, input.click_x, input.click_y)
  result_fixed := identificar_box_clicada_fixed(input.boxes, input.click_x, input.click_y)
  
  // Verifica que o comportamento é idêntico
  ASSERT result_original = result_fixed
END FOR
```

**Testing Approach**: Property-based testing é recomendado para preservation checking porque:
- Gera muitos casos de teste automaticamente através do domínio de entrada
- Captura edge cases que testes unitários manuais podem perder
- Fornece garantias fortes de que o comportamento é inalterado para todos os inputs não-buggy

**Test Plan**: Observar comportamento no código NÃO CORRIGIDO primeiro para cliques exatamente dentro de boxes e cliques muito distantes, depois escrever testes property-based capturando esse comportamento.

**Test Cases**:
1. **Preservation - Clique Exatamente Dentro**: Observar que cliques exatamente dentro de boxes retornam o idx correto no código não corrigido, depois escrever teste para verificar que isso continua após o fix.

2. **Preservation - Clique Muito Distante**: Observar que cliques muito distantes retornam None no código não corrigido, depois escrever teste para verificar que isso continua após o fix.

3. **Preservation - Overlap com Clique Dentro**: Observar que cliques dentro de múltiplas boxes retornam a box com menor área no código não corrigido, depois escrever teste para verificar que isso continua após o fix.

### Unit Tests

- Testar matching estrito para cliques exatamente dentro de boxes (comportamento preservado)
- Testar matching com tolerância para cliques próximos mas fora de boxes (novo comportamento)
- Testar edge cases (clique muito distante, múltiplas boxes candidatas, empate na distância)
- Testar que cliques muito distantes continuam retornando None

### Property-Based Tests

- Gerar coordenadas de clique aleatórias e boxes aleatórias, verificar que matching com tolerância funciona corretamente
- Gerar configurações de boxes aleatórias com overlap, verificar que a priorização por distância e área funciona
- Testar que todos os inputs não-buggy continuam produzindo o mesmo resultado através de muitos cenários

### Integration Tests

- Testar fluxo completo de captura com cliques próximos mas fora de boxes
- Testar que `som_idx_clicado` e `som_box_clicada` são corretamente populados após o fix
- Testar que labels descritivos do SoM são usados em vez de labels genéricos do radar
- Testar que a imagem anotada com bounding boxes numeradas é gerada corretamente

# Bugfix Requirements Document

## Introduction

O sistema de captura usa Set-of-Mark (SoM) para detectar elementos interativos na tela e associar cliques do usuário a esses elementos. O SoM detecta boxes (caixas delimitadoras) ao redor de elementos clicáveis e tenta fazer matching entre as coordenadas do clique e essas boxes através da função `identificar_box_clicada` em `som_annotator.py`.

**Problema:** A função `identificar_box_clicada` usa matching estrito de boundaries sem tolerância. Quando o clique está alguns pixels fora da box detectada (devido a offsets de ícones, padding, ou imprecisão do radar), o match falha, resultando em `som_idx_clicado: null` e `som_box_clicada: null`.

**Impacto:** 
- SCORM gerado usa labels genéricos em vez de labels descritivos do SoM
- Zonas interativas podem aparecer em locais imprecisos
- Experiência de treinamento degradada
- Afeta todos os roteiros onde o clique não está exatamente dentro da box detectada

**Casos Afetados:**
- Ação 6 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos": clique em coordenadas (x=256, y=205) com 20 boxes detectadas, mas matching falhou
- Ação 7 do mesmo roteiro: clique em coordenadas (x=1199, y=27) com 20 boxes detectadas, mas matching falhou

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o usuário clica em um elemento interativo e as coordenadas do clique estão alguns pixels fora da box detectada pelo SoM (devido a offsets de ícones, padding, ou imprecisão do radar) THEN o sistema retorna `som_idx_clicado: null` e `som_box_clicada: null`, falhando em associar o clique a qualquer box detectada

1.2 WHEN o SoM detecta 20 boxes corretamente mas a função `identificar_box_clicada` usa matching estrito de boundaries (x <= click_x <= x+w AND y <= click_y <= y+h) THEN o matching falha para cliques que estão próximos mas não exatamente dentro da box

1.3 WHEN o matching de SoM falha THEN o sistema usa labels genéricos capturados pelo radar (como "Visualizar", "span") em vez dos labels descritivos do SoM

### Expected Behavior (Correct)

2.1 WHEN o usuário clica em um elemento interativo e as coordenadas do clique estão próximas (dentro de uma tolerância razoável) de uma box detectada pelo SoM THEN o sistema SHALL retornar o `som_idx_clicado` e `som_box_clicada` correspondentes, associando o clique à box mais próxima

2.2 WHEN a função `identificar_box_clicada` avalia as coordenadas do clique THEN o sistema SHALL usar uma estratégia de matching com tolerância que considere:
   - Distância do clique ao centro da box
   - Distância do clique às bordas da box
   - Priorização de boxes menores (mais específicas) em caso de overlap

2.3 WHEN o matching de SoM é bem-sucedido THEN o sistema SHALL usar os labels descritivos do SoM em vez de labels genéricos do radar

2.4 WHEN múltiplas boxes são candidatas (overlap ou proximidade similar) THEN o sistema SHALL retornar a box com menor área (mais específica)

### Unchanged Behavior (Regression Prevention)

3.1 WHEN o usuário clica exatamente dentro de uma box detectada pelo SoM (coordenadas dentro dos boundaries estritos) THEN o sistema SHALL CONTINUE TO retornar o `som_idx_clicado` e `som_box_clicada` corretos como antes

3.2 WHEN o SoM detecta boxes ao redor de elementos interativos THEN o sistema SHALL CONTINUE TO detectar e numerar as boxes corretamente como antes

3.3 WHEN o clique está muito distante de qualquer box detectada (fora de qualquer tolerância razoável) THEN o sistema SHALL CONTINUE TO retornar `som_idx_clicado: null` e `som_box_clicada: null` como antes

3.4 WHEN múltiplas boxes se sobrepõem e o clique está dentro de múltiplas boxes THEN o sistema SHALL CONTINUE TO retornar a box com menor área (mais específica) como antes

## Bug Condition and Property Specification

### Bug Condition Function

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type ClickEvent with fields:
    - click_x: integer (coordenada x do clique)
    - click_y: integer (coordenada y do clique)
    - boxes: array of Box (boxes detectadas pelo SoM)
    - Box has fields: x, y, w, h, idx
  OUTPUT: boolean
  
  // Retorna true quando o clique está próximo de uma box mas o matching estrito falha
  FOR EACH box IN X.boxes DO
    // Verifica se o clique está dentro da box (matching estrito)
    IF (box.x <= X.click_x <= box.x + box.w) AND 
       (box.y <= X.click_y <= box.y + box.h) THEN
      RETURN false  // Matching estrito funciona, não é bug
    END IF
    
    // Verifica se o clique está próximo da box (dentro de tolerância razoável)
    distance_to_center = SQRT((X.click_x - (box.x + box.w/2))^2 + 
                              (X.click_y - (box.y + box.h/2))^2)
    max_dimension = MAX(box.w, box.h)
    tolerance = max_dimension * 0.3  // 30% da maior dimensão
    
    IF distance_to_center <= tolerance THEN
      RETURN true  // Clique próximo mas matching estrito falhou = BUG
    END IF
  END FOR
  
  RETURN false  // Clique muito distante de qualquer box, não é bug
END FUNCTION
```

### Property Specification - Fix Checking

```pascal
// Property: Fix Checking - Matching com Tolerância
FOR ALL X WHERE isBugCondition(X) DO
  result ← identificar_box_clicada'(X.boxes, X.click_x, X.click_y)
  
  // Verifica que o resultado não é null (matching bem-sucedido)
  ASSERT result IS NOT null
  
  // Verifica que o resultado é a box mais próxima
  closest_box ← find_closest_box(X.boxes, X.click_x, X.click_y)
  ASSERT result.idx = closest_box.idx
  
  // Verifica que a box retornada está dentro da tolerância
  distance_to_center = SQRT((X.click_x - (result.x + result.w/2))^2 + 
                            (X.click_y - (result.y + result.h/2))^2)
  max_dimension = MAX(result.w, result.h)
  tolerance = max_dimension * 0.3
  ASSERT distance_to_center <= tolerance
END FOR
```

### Property Specification - Preservation Checking

```pascal
// Property: Preservation Checking - Comportamento Existente Preservado
FOR ALL X WHERE NOT isBugCondition(X) DO
  // Para cliques que já funcionam ou estão muito distantes
  result_original ← identificar_box_clicada(X.boxes, X.click_x, X.click_y)
  result_fixed ← identificar_box_clicada'(X.boxes, X.click_x, X.click_y)
  
  // Verifica que o comportamento é idêntico
  ASSERT result_original = result_fixed
END FOR
```

### Key Definitions

- **F**: `identificar_box_clicada` - A função original (não corrigida) em `som_annotator.py` que usa matching estrito de boundaries
- **F'**: `identificar_box_clicada'` - A função corrigida que usa matching com tolerância baseado em distância ao centro da box
- **C(X)**: Bug Condition - Identifica cliques que estão próximos de uma box mas falham no matching estrito
- **¬C(X)**: Non-buggy inputs - Cliques que já funcionam (dentro da box) ou estão muito distantes (fora de qualquer tolerância)

### Counterexample

**Caso Real - Ação 6:**
```
Input:
  click_x = 256
  click_y = 205
  boxes = [20 boxes detectadas]
  
Comportamento Atual (F):
  identificar_box_clicada(boxes, 256, 205) → null
  
Comportamento Esperado (F'):
  identificar_box_clicada'(boxes, 256, 205) → box com idx correspondente
  (box mais próxima do clique, dentro da tolerância)
```

**Caso Real - Ação 7:**
```
Input:
  click_x = 1199
  click_y = 27
  boxes = [20 boxes detectadas]
  
Comportamento Atual (F):
  identificar_box_clicada(boxes, 1199, 27) → null
  
Comportamento Esperado (F'):
  identificar_box_clicada'(boxes, 1199, 27) → box com idx correspondente
  (box mais próxima do clique, dentro da tolerância)
```

# Robot Execution Wrong Clicks — Bugfix Design

## Overview

Durante a execução de um roteiro gravado, o robô reporta "sucesso" em todas as etapas mas os cliques e ações realizados são incorretos na tela. O bug tem dois vetores simultâneos no arquivo `vision_engine.py`:

1. **Camada `2_coords_capturadas`**: coordenadas relativas da gravação são convertidas para coordenadas absolutas e o clique é executado sem verificar se o elemento presente naquelas coordenadas corresponde ao elemento esperado (`label_curto` / `intencao_semantica`). Diferenças de resolução, zoom ou scroll entre o ambiente de gravação e o de execução deslocam o alvo real, mas o sistema reporta sucesso.

2. **Camada `2_sniper`**: candidatos encontrados por texto parcial (`text=label_curto` com `exact=False`) são aceitos e executados sem passar por `_verificar_identidade_elemento()`. A função já existe no módulo e é usada na camada `3_hint_original` para seletores posicionais, mas foi omitida no Sniper para candidatos de texto parcial.

A estratégia de correção é **mínima e cirúrgica**: adicionar verificação de identidade nos dois pontos exatos onde ela está ausente, sem alterar a arquitetura de cascata, sem remover camadas e sem introduzir novas dependências.

## Glossary

- **Bug_Condition (C)**: A condição que ativa o bug — quando uma camada de fallback executa uma ação em um elemento que não corresponde ao elemento esperado e reporta sucesso.
- **Property (P)**: O comportamento correto esperado — uma camada só deve reportar sucesso se o elemento atingido corresponde ao `label_curto` ou `intencao_semantica` da ação.
- **Preservation**: O comportamento existente que não deve ser alterado pela correção — todas as camadas que já funcionam corretamente (Brain, Template Matching, Gemini Vision, Hint Original com seletor exato, Sniper com candidatos de alta confiança como `aria-label` exato e `data-testid`) devem continuar funcionando sem degradação.
- **`encontrar_e_clicar`**: Função orquestradora em `vision_engine.py` que roteia a tentativa pelas camadas de fallback.
- **`_verificar_identidade_elemento`**: Função em `vision_engine.py` que verifica se um locator contém o texto do `label_curto` (via `inner_text()` do elemento ou do pai). Já existe e é usada na camada `3_hint_original`.
- **`_clicar_por_coordenadas`**: Função em `vision_engine.py` que executa um clique em coordenadas absolutas (x, y) na página.
- **`_tentar_candidato`**: Função em `vision_engine.py` que tenta localizar e executar uma ação via um `TentativaLocalizacao`.
- **`coords_relativas`**: Dicionário `{"x_pct": float, "y_pct": float}` capturado durante a gravação, representando a posição do elemento como fração do viewport.
- **`label_curto`**: Texto visível ou rótulo semântico do elemento alvo, extraído do roteiro.
- **Candidato de texto parcial**: `TentativaLocalizacao` gerado por `_gerar_candidatos` com `seletor=f"text={label_curto}"` e `exact=False`.
- **Candidato de alta confiança**: `TentativaLocalizacao` com `aria-label` exato, `data-testid`, `role+name` exato ou `placeholder` — não requer verificação adicional.

## Bug Details

### Bug Condition

O bug se manifesta quando a camada `2_coords_capturadas` ou a camada `2_sniper` é acionada como fallback. Em `2_coords_capturadas`, o clique é executado nas coordenadas calculadas sem verificar o elemento presente naquelas coordenadas. Em `2_sniper`, candidatos de texto parcial são aceitos sem verificação de identidade.

**Formal Specification:**
```
FUNCTION isBugCondition(acao_tec, camada_acionada)
  INPUT: acao_tec (dict com elemento_alvo, intencao_semantica, label_curto)
         camada_acionada (string: "2_coords_capturadas" | "2_sniper_texto_parcial")
  OUTPUT: boolean

  label_curto    := acao_tec.elemento_alvo.label_curto
  coords_rel     := acao_tec.elemento_alvo.coordenadas_relativas

  IF camada_acionada = "2_coords_capturadas" THEN
    RETURN coords_rel IS NOT NULL
           AND coords_rel.x_pct IS NOT NULL
           AND elemento_em_coords_calculadas(coords_rel) != elemento_esperado(label_curto)
  END IF

  IF camada_acionada = "2_sniper_texto_parcial" THEN
    RETURN candidato.exact = FALSE
           AND candidato.seletor STARTS_WITH "text="
           AND elemento_encontrado_por_texto_parcial != elemento_esperado(label_curto)
  END IF

  RETURN FALSE
END FUNCTION
```

### Examples

- **Passo 1 (coords deslocadas)**: Gravação feita em 1920×1080 com scroll=0. Execução em 1366×768 com scroll=200px. Coordenadas relativas (x_pct=0.017, y_pct=0.711) resultam em (23, 546) em vez de (33, 769). O sistema clica em um elemento diferente (ex: item de menu adjacente) e reporta sucesso com score 0.700.
- **Passos 2 e 3 (falso positivo semântico)**: Label esperado é "Novo Documento". O Sniper gera candidato `text=Novo Documento` com `exact=False`. A página contém "Novo Documento de Texto" e "Novo Documento de Planilha". O Sniper acerta o primeiro elemento visível com texto parcialmente coincidente e reporta sucesso com score 0.910, mas o elemento correto era o segundo.
- **Caso sem bug (coords corretas)**: Gravação e execução na mesma resolução e scroll. Coordenadas relativas resultam nas coordenadas absolutas corretas. O elemento presente naquelas coordenadas corresponde ao `label_curto`. Comportamento correto — não deve ser alterado.
- **Caso sem bug (Sniper com aria-label exato)**: Candidato gerado com `seletor="[aria-label='Salvar']"`. Elemento encontrado tem `aria-label` exato. Não requer verificação adicional — não deve ser alterado.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- A camada `0_brain` (memória SQLite) deve continuar funcionando exatamente como antes — seletor memorizado é tentado sem verificação adicional.
- A camada `1_template_matching` deve continuar funcionando exatamente como antes — match visual por NCC já é uma verificação de identidade por natureza.
- A camada `1.5_heuristica_seniorx` deve continuar funcionando exatamente como antes.
- A camada `3_hint_original` com seletor não-posicional deve continuar funcionando sem verificação adicional.
- A camada `3_hint_original` com seletor posicional já aplica `_verificar_identidade_elemento` — não deve ser alterada.
- A camada `4_todos_frames` deve continuar funcionando exatamente como antes.
- A camada `5_gemini_vision` deve continuar funcionando exatamente como antes.
- Candidatos do Sniper com `aria-label` exato, `data-testid`, `role+name` exato, `placeholder` e `title` devem continuar sendo aceitos sem verificação adicional.
- O comportamento de `_verificar_identidade_elemento` (fail-open quando texto não é acessível) deve ser preservado — checkboxes e ícones sem texto visível não devem ser bloqueados.
- A telemetria (`_registrar_telemetria`) deve continuar sendo chamada com os mesmos nomes de camada.
- O registro no Brain (`_registrar_sucesso_cache`) deve continuar sendo chamado após acerto confirmado.

**Scope:**
Todos os inputs que NÃO envolvem as camadas `2_coords_capturadas` ou `2_sniper` com candidatos de texto parcial devem ser completamente inalterados por esta correção. Isso inclui:
- Ações resolvidas pelo Brain (camada 0)
- Ações resolvidas por Template Matching (camada 1_T)
- Ações resolvidas por Heurísticas Senior X (camada 1.5)
- Ações resolvidas pelo Sniper com candidatos de alta confiança (aria-label exato, data-testid, role+name)
- Ações resolvidas pelo Hint Original (camada 3)
- Ações resolvidas por busca em frames (camada 4)
- Ações resolvidas pelo Gemini Vision (camada 5)

## Hypothesized Root Cause

Com base na análise do código em `vision_engine.py`:

1. **Ausência de verificação pós-clique em `2_coords_capturadas`** (linhas ~1390-1402): A camada calcula `x = int(coords_relativas["x_pct"] * vp["width"])` e `y = int(coords_relativas["y_pct"] * vp["height"])`, chama `_clicar_por_coordenadas` e, se retornar `True`, imediatamente registra sucesso e retorna `True`. Não há nenhuma verificação do elemento presente naquelas coordenadas. `_clicar_por_coordenadas` retorna `True` sempre que o clique mecânico não lança exceção — independentemente do elemento atingido.

2. **Ausência de `_verificar_identidade_elemento` para candidatos de texto parcial no Sniper** (linhas ~1405-1420): O loop do Sniper chama `_tentar_candidato` para todos os candidatos. Para candidatos com `exact=False` (texto parcial), `_tentar_candidato` localiza o primeiro elemento visível que contém o texto e executa a ação. A função `_verificar_identidade_elemento` já existe e é chamada na camada `3_hint_original` para seletores posicionais, mas não é chamada no Sniper para candidatos de texto parcial.

3. **`_clicar_por_coordenadas` não tem acesso ao `label_curto`**: A função recebe apenas `page`, `coords`, `acao` e `valor`. Para verificar identidade pós-clique por coordenadas, é necessário usar `page.evaluate("document.elementFromPoint(x, y)")` para obter o elemento e então verificar seu texto — padrão já usado na camada `5_gemini_vision` para aprender seletores.

4. **Candidatos de texto parcial são gerados intencionalmente como último recurso no Sniper**: Em `_gerar_candidatos`, os candidatos `text=label_curto` com `exact=False` são adicionados ao final da lista (após candidatos de alta confiança). A correção deve aplicar verificação apenas a esses candidatos de baixa confiança, sem afetar os de alta confiança.

## Correctness Properties

Property 1: Bug Condition — Verificação de Identidade em Coordenadas Capturadas

_For any_ ação onde a camada `2_coords_capturadas` é acionada (coords_relativas não nulo), a função `encontrar_e_clicar` corrigida SHALL verificar se o elemento presente nas coordenadas calculadas corresponde ao `label_curto` da ação antes de reportar sucesso. Se o elemento não corresponder, a camada SHALL registrar falha e escalar para a próxima camada (`2_sniper`).

**Validates: Requirements 2.1, 2.2**

Property 2: Bug Condition — Verificação de Identidade em Candidatos de Texto Parcial do Sniper

_For any_ ação onde o Sniper (`2_sniper`) encontra um candidato via texto parcial (`exact=False`), a função `encontrar_e_clicar` corrigida SHALL aplicar `_verificar_identidade_elemento` antes de confirmar o acerto. Se a identidade não for confirmada, o candidato SHALL ser rejeitado e o Sniper SHALL continuar tentando os próximos candidatos.

**Validates: Requirements 2.3, 2.4**

Property 3: Preservation — Candidatos de Alta Confiança do Sniper Não São Afetados

_For any_ ação onde o Sniper encontra um candidato via `aria-label` exato, `data-testid`, `role+name` exato, `placeholder` ou `title`, a função `encontrar_e_clicar` corrigida SHALL produzir exatamente o mesmo resultado que a função original, sem verificação adicional de identidade.

**Validates: Requirements 3.3**

Property 4: Preservation — Camadas Não Modificadas Produzem Resultado Idêntico

_For any_ ação resolvida pelas camadas `0_brain`, `1_template_matching`, `1.5_heuristica_seniorx`, `3_hint_original`, `4_todos_frames` ou `5_gemini_vision`, a função `encontrar_e_clicar` corrigida SHALL produzir exatamente o mesmo resultado que a função original.

**Validates: Requirements 3.1, 3.2, 3.4, 3.5, 3.6**

## Fix Implementation

### Changes Required

Assumindo que a análise de causa raiz está correta:

**File**: `vision_engine.py`

**Function**: `encontrar_e_clicar`

**Specific Changes**:

1. **Camada `2_coords_capturadas` — Adicionar verificação de identidade pós-clique**:
   - Após calcular `x` e `y` a partir de `coords_relativas`, antes de retornar `True`, usar `page.evaluate("([x,y]) => { const el = document.elementFromPoint(x,y); return el ? el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || '' : ''; }", [x, y])` para obter o texto do elemento nas coordenadas.
   - Comparar o texto obtido com `label_curto` (case-insensitive, strip). Se `label_curto` não estiver contido no texto do elemento, registrar falha na telemetria e **não** retornar `True` — deixar a cascata continuar para `2_sniper`.
   - Aplicar fail-open: se `label_curto` estiver vazio ou se a avaliação JS falhar, aceitar o clique normalmente (preserva comportamento para ações sem label definido).
   - Manter a chamada a `_registrar_telemetria("2_coords_capturadas", True)` apenas quando a identidade for confirmada.

2. **Camada `2_sniper` — Aplicar `_verificar_identidade_elemento` para candidatos de texto parcial**:
   - Identificar candidatos de texto parcial: `cand.seletor.startswith("text=") and not cand.exact` ou `cand.via_pierce and "text=" in cand.seletor`.
   - Para esses candidatos, após `_tentar_candidato` retornar `True`, obter o locator resultante e chamar `_verificar_identidade_elemento(locator, label_curto)`.
   - **Problema**: `_tentar_candidato` não retorna o locator — retorna apenas `bool`. Solução: extrair a lógica de verificação inline no loop do Sniper para candidatos de texto parcial, ou adicionar um parâmetro opcional `verificar_identidade: bool = False` a `_tentar_candidato`.
   - Alternativa mais simples e de menor risco: no loop do Sniper, para candidatos identificados como texto parcial, construir o locator diretamente (sem passar por `_tentar_candidato`) e chamar `_verificar_identidade_elemento` antes de `_executar_acao`. Isso evita alterar a assinatura de `_tentar_candidato`.
   - Candidatos de alta confiança (sem `seletor` — usam `role`, `label`, `placeholder`, `title` — e candidatos com `aria-label`, `data-testid`) devem continuar passando por `_tentar_candidato` sem verificação adicional.

3. **Emitir WARNING quando fallback é acionado com sucesso** (Requisito 2.4):
   - Após confirmar sucesso em `2_coords_capturadas` ou `2_sniper` (com verificação de identidade aprovada), emitir `logger.warning(f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '{camada}' — verifique se o elemento correto foi atingido.")`.
   - Isso é informativo e não altera o fluxo de execução.

4. **Sem alterações em outras funções**: `_verificar_identidade_elemento`, `_clicar_por_coordenadas`, `_tentar_candidato`, `_gerar_candidatos` e todas as outras camadas permanecem inalteradas.

5. **Sem novas dependências**: A correção usa apenas recursos já presentes no módulo (`page.evaluate`, `_verificar_identidade_elemento`, `logger`).

## Testing Strategy

### Validation Approach

A estratégia de testes segue duas fases: primeiro, confirmar o bug no código não corrigido com testes exploratórios que demonstram o falso positivo; depois, verificar que a correção elimina o falso positivo e preserva o comportamento existente.

### Exploratory Bug Condition Checking

**Goal**: Demonstrar o bug ANTES de implementar a correção. Confirmar ou refutar a análise de causa raiz. Se refutarmos, precisamos re-hipotetizar.

**Test Plan**: Criar mocks de `page` e `acao_tec` que simulam os cenários de falha. Executar `encontrar_e_clicar` no código não corrigido e observar que retorna `True` mesmo quando o elemento atingido é incorreto.

**Test Cases**:
1. **Coords deslocadas — elemento errado**: Simular `page` onde `elementFromPoint(x, y)` retorna elemento com texto "Cancelar" quando `label_curto="Salvar"`. Executar camada `2_coords_capturadas`. Espera-se que o código não corrigido retorne `True` (demonstra o bug).
2. **Sniper texto parcial — falso positivo**: Simular página com dois elementos: "Novo Documento de Texto" e "Novo Documento". `label_curto="Novo Documento"`. Sniper com `exact=False` acerta "Novo Documento de Texto" primeiro. Espera-se que o código não corrigido retorne `True` com o elemento errado.
3. **Sniper texto parcial — múltiplos candidatos**: Simular página com "Excluir Arquivo" e "Excluir Pasta". `label_curto="Excluir Pasta"`. Espera-se que o código não corrigido acerte "Excluir Arquivo" (primeiro visível) e retorne `True`.
4. **Coords corretas — mesmo elemento**: Simular `page` onde `elementFromPoint(x, y)` retorna elemento com texto "Salvar" e `label_curto="Salvar"`. Espera-se que o código não corrigido retorne `True` (não é bug — baseline para preservation).

**Expected Counterexamples**:
- `encontrar_e_clicar` retorna `True` quando o elemento atingido por coordenadas não contém `label_curto`.
- `encontrar_e_clicar` retorna `True` quando o Sniper acerta um elemento com texto parcialmente coincidente mas diferente do esperado.

### Fix Checking

**Goal**: Verificar que para todos os inputs onde a condição de bug se aplica, a função corrigida produz o comportamento esperado.

**Pseudocode:**
```
FOR ALL acao_tec WHERE isBugCondition(acao_tec, "2_coords_capturadas") DO
  resultado := encontrar_e_clicar_corrigida(page_mock, acao_tec)
  ASSERT resultado = False OR elemento_atingido_corresponde_ao_label(resultado)
END FOR

FOR ALL acao_tec WHERE isBugCondition(acao_tec, "2_sniper_texto_parcial") DO
  resultado := encontrar_e_clicar_corrigida(page_mock, acao_tec)
  ASSERT resultado = False OR elemento_atingido_corresponde_ao_label(resultado)
END FOR
```

### Preservation Checking

**Goal**: Verificar que para todos os inputs onde a condição de bug NÃO se aplica, a função corrigida produz o mesmo resultado que a função original.

**Pseudocode:**
```
FOR ALL acao_tec WHERE NOT isBugCondition(acao_tec, camada) DO
  ASSERT encontrar_e_clicar_original(page_mock, acao_tec)
       = encontrar_e_clicar_corrigida(page_mock, acao_tec)
END FOR
```

**Testing Approach**: Testes baseados em propriedades são recomendados para preservation checking porque:
- Geram automaticamente muitos cenários de `acao_tec` com diferentes combinações de `label_curto`, `coords_relativas`, `seletor_hint` e `tipo_elemento`.
- Capturam edge cases que testes manuais podem perder (label vazio, coords nulas, candidatos sem seletor).
- Fornecem garantia forte de que o comportamento é preservado para todos os inputs não-bugados.

**Test Plan**: Observar o comportamento no código não corrigido para candidatos de alta confiança e coordenadas corretas, depois escrever testes de propriedade que capturam esse comportamento.

**Test Cases**:
1. **Preservation — Sniper aria-label exato**: Verificar que candidatos com `seletor="[aria-label='X']"` continuam sendo aceitos sem verificação adicional após a correção.
2. **Preservation — Sniper data-testid**: Verificar que candidatos com `seletor="[data-testid='X']"` continuam sendo aceitos sem verificação adicional.
3. **Preservation — Coords corretas (label presente)**: Verificar que quando `elementFromPoint` retorna elemento com texto contendo `label_curto`, a camada `2_coords_capturadas` continua retornando `True`.
4. **Preservation — label_curto vazio (fail-open)**: Verificar que quando `label_curto=""`, a camada `2_coords_capturadas` continua retornando `True` sem verificação (fail-open).
5. **Preservation — Sniper role+name exato**: Verificar que candidatos com `role` e `label` (get_by_role) continuam sendo aceitos sem verificação adicional.

### Unit Tests

- Testar `2_coords_capturadas` com mock de `page.evaluate` retornando texto que corresponde ao `label_curto` → deve retornar `True`.
- Testar `2_coords_capturadas` com mock de `page.evaluate` retornando texto que NÃO corresponde ao `label_curto` → deve retornar `False` e escalar.
- Testar `2_coords_capturadas` com `label_curto=""` → deve retornar `True` (fail-open).
- Testar `2_coords_capturadas` com `page.evaluate` lançando exceção → deve retornar `True` (fail-open).
- Testar Sniper com candidato `text=X exact=False` onde elemento encontrado contém `label_curto` → deve retornar `True`.
- Testar Sniper com candidato `text=X exact=False` onde elemento encontrado NÃO contém `label_curto` → deve rejeitar e tentar próximo candidato.
- Testar Sniper com candidato `[aria-label='X']` → deve aceitar sem verificação adicional.
- Testar Sniper com candidato `[data-testid='X']` → deve aceitar sem verificação adicional.

### Property-Based Tests

- Gerar aleatoriamente `label_curto` (strings de 3-50 chars) e `texto_elemento` (strings de 3-80 chars). Verificar que a lógica de verificação de identidade retorna `True` se e somente se `label_curto.lower() in texto_elemento.lower()`.
- Gerar aleatoriamente listas de candidatos com tipos mistos (alta confiança + texto parcial). Verificar que candidatos de alta confiança nunca são submetidos à verificação de identidade adicional.
- Gerar aleatoriamente `coords_relativas` com `x_pct` e `y_pct` entre 0.0 e 1.0 e viewports variados. Verificar que as coordenadas absolutas calculadas estão sempre dentro dos limites do viewport.
- Verificar que quando `label_curto` está vazio, a verificação de identidade sempre retorna `True` (fail-open) independentemente do texto do elemento.

### Integration Tests

- Executar um roteiro de teste com passo que usa `2_coords_capturadas` em ambiente com resolução diferente da gravação. Verificar que o sistema escala para `2_sniper` em vez de reportar falso sucesso.
- Executar um roteiro de teste com passo onde o Sniper encontra candidato de texto parcial ambíguo. Verificar que o sistema rejeita o candidato errado e encontra o correto (ou escala para próxima camada).
- Verificar que passos resolvidos pelo Brain (camada 0) continuam funcionando sem alteração após a correção.
- Verificar que passos resolvidos pelo Template Matching (camada 1_T) continuam funcionando sem alteração.
- Verificar que o log de WARNING é emitido quando `2_coords_capturadas` ou `2_sniper` resolvem com sucesso após verificação de identidade.

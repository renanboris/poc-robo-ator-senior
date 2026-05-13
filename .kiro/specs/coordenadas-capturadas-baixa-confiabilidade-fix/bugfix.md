# Bugfix Requirements Document

## Introduction

O executor Python (`vision_engine.py`) não tem verificação de identidade uniforme entre as camadas da cascata de execução. Cada camada usa uma lógica diferente — ou nenhuma — para confirmar que o elemento atingido é o correto. Isso permite que qualquer camada retorne "sucesso" ao clicar no elemento errado, corrompendo o estado da aplicação e causando falhas em cascata em todas as ações seguintes.

**Três pontos de falha identificados:**

1. **Sniper sem verificação para candidatos CSS posicionais**: O Sniper aplica verificação de identidade apenas para candidatos `text=`. Para candidatos CSS posicionais (`:nth-child`, `:nth-of-type`), executa o clique sem verificar se o elemento é o correto — falso positivo silencioso.

2. **Substring matching na verificação de coordenadas e seletor_hint posicional**: O sistema usa `label_curto in texto_elemento` que aceita falsos positivos — busca `"1"` mas aceita `"EMPRESA 1"`.

3. **Coordenadas tentadas antes de seletor_hint**: Coordenadas capturadas (Camada 2) são tentadas antes do seletor_hint original (Camada 3), mesmo sendo menos confiáveis.

**Evidência concreta do log:**
```
❌ Ação 2: [Sniper] Acerto: seletor_hint priority '[role="dialog"] span:nth-child(1)'
   → Falso positivo no Sniper — clicou em "EMPRESA 1" ao invés do número "1"
   → Modal fechou incorretamente
❌ Ação 3: Escalou para coordenadas (modal já fechado)
❌ Ação 4: [Coords Capturadas] Identidade não confirmada: esperado 'ui-btn', encontrado 'Código Nome 1 Empresa Padrão'
   → Taxa de sucesso da camada 2_coords_capturadas: 29.4%
```

A falha em cascata começou no **Sniper (Ação 2)**, não nas coordenadas. As coordenadas são apenas o sintoma mais visível porque têm telemetria explícita.

**Impacto**: Taxa de sucesso da execução ~29.4% (deveria ser >90%). Sistema marca falsos positivos como "sucesso" e continua executando com estado incorreto.

**Evidência do Log**:
```
[Coords Capturadas] Identidade não confirmada: esperado 'ui-btn', encontrado 'Código Nome 1 Empresa Padrão'
Taxa de sucesso da camada 2_coords_capturadas: 29.4% (70 acertos / 238 tentativas)
```

**Exemplo de Falha em Cascata**:
- ✅ **Ação 1 (Lupa de empresa)**: `[Sniper] Acerto: seletor_hint priority '[name='e070emp'] button'` - **SUCESSO!**
- ❌ **Ação 2 (Clicar no "1")**: `[Sniper] Acerto: seletor_hint priority '[role="dialog"] span:nth-child(1)'` - **FALSO POSITIVO!** (sistema achou que acertou mas clicou no elemento errado - buscou "1" mas clicou em "EMPRESA 1")
- ❌ **Ação 3 (Botão "Selecionar")**: Escalou para coordenadas porque modal já estava fechado (devido ao erro anterior)
- ❌ **Ação 4 (Segunda lupa)**: Escalou para coordenadas e clicou no lugar errado

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN o Sniper tenta um candidato CSS posicional (`:nth-child`, `:nth-of-type`, `#id-numerico`) THEN o executor não aplica verificação de identidade, aceitando o elemento encontrado mesmo que seu texto não corresponda ao `label_curto` esperado

1.2 WHEN qualquer camada executa um clique e o elemento atingido tem texto diferente do `label_curto` esperado THEN o sistema pode marcar a ação como "sucesso" (falso positivo) e continuar executando com estado incorreto da aplicação

1.3 WHEN a verificação de identidade usa substring matching (`label_curto in texto_elemento`) THEN o sistema aceita falsos positivos onde o texto esperado é substring de um texto maior (ex: `"1" in "EMPRESA 1"` → True)

1.4 WHEN o sistema executa um falso positivo (clica no elemento errado mas marca como sucesso) THEN as ações seguintes falham porque o contexto está errado (ex: modal fechado quando deveria estar aberto), causando falhas em cascata

1.5 WHEN coordenadas capturadas são tentadas ANTES do `seletor_hint` original (Camada 2 < Camada 3) THEN o sistema usa uma estratégia menos confiável antes de tentar a mais confiável

1.6 WHEN a taxa de sucesso da camada `2_coords_capturadas` é de apenas 29.4% THEN o sistema está confiando em uma estratégia não-confiável como fallback de alta prioridade

### Expected Behavior (Correct)

2.1 WHEN coordenadas capturadas são consideradas como estratégia de fallback THEN o sistema SHALL tentar coordenadas DEPOIS do `seletor_hint` original (Camada 3), tornando coordenadas a última opção semântica antes de Gemini Vision

2.2 WHEN qualquer camada verifica a identidade de um elemento THEN o sistema SHALL usar match exato de texto (após normalização: strip, lowercase) ao invés de substring matching, rejeitando casos onde `label_curto` é apenas parte de um texto maior

2.3 WHEN o Sniper tenta um candidato CSS posicional e `label_curto` não é vazio nem genérico THEN o sistema SHALL verificar a identidade do elemento encontrado com match exato antes de retornar sucesso

2.4 WHEN a verificação de identidade falha (texto não corresponde exatamente) THEN o sistema SHALL rejeitar o candidato e escalar para a próxima estratégia, ao invés de clicar no elemento errado

2.5 WHEN coordenadas capturadas são rejeitadas pela verificação de identidade rigorosa THEN o sistema SHALL logar claramente o motivo da rejeição para facilitar debugging

2.6 WHEN todas as camadas semânticas falham THEN o sistema SHALL escalar para Gemini Vision como última camada de self-healing

### Unchanged Behavior (Regression Prevention)

3.1 WHEN `label_curto` está vazio ou é None THEN o sistema SHALL CONTINUE TO aplicar fail-open (aceitar sem verificação) em todas as camadas

3.2 WHEN coordenadas capturadas são usadas em iframe cross-origin THEN o sistema SHALL CONTINUE TO aplicar fail-open (aceitar sem verificação)

3.3 WHEN a verificação de identidade lança exceção THEN o sistema SHALL CONTINUE TO aplicar fail-open (aceitar sem verificação)

3.4 WHEN o Sniper tenta candidatos semânticos de alta confiança (`[aria-label=]`, `[data-testid=]`, `[name=]`, `[id=]`) THEN o sistema SHALL CONTINUE TO executar sem verificação adicional de identidade (esses seletores já são específicos o suficiente)

3.5 WHEN o Sniper tenta candidatos `text=` THEN o sistema SHALL CONTINUE TO usar o match exato já implementado (comportamento inalterado)

3.6 WHEN o sistema registra telemetria de sucesso/falha THEN o sistema SHALL CONTINUE TO usar a mesma lógica de telemetria e aprendizado de longo prazo no Brain

---

## Bug Condition Analysis

### Bug Condition Function

A condição de bug ocorre em três cenários distintos, todos com a mesma raiz: ausência de verificação de identidade uniforme na cascata.

```pascal
FUNCTION isBugCondition(X)
  INPUT: X of type AcaoTecnica
  OUTPUT: boolean

  alvo ← X.elemento_alvo
  label_curto ← alvo.label_curto
  seletor_hint ← alvo.seletor_hint
  coords_relativas ← alvo.coordenadas_relativas

  // Cenário A: Sniper tenta candidato posicional sem verificação de identidade
  cenario_A := (
    EXISTS candidato IN _gerar_candidatos(X) WHERE
      _contem_indice_posicional(candidato.seletor) AND
      label_curto IS NOT NULL AND label_curto ≠ "" AND
      NOT _e_label_generico(label_curto) AND
      verificacao_identidade_ausente_para_css_no_sniper
  )

  // Cenário B: Coordenadas antes de seletor_hint + substring matching
  cenario_B := (
    coords_relativas IS NOT NULL AND
    coords_relativas.x_pct IS NOT NULL AND
    camada_coords = 2 AND  // antes de seletor_hint (Camada 3)
    verificacao_usa_substring_matching
  )

  // Cenário C: _verificar_identidade_elemento usa substring matching
  cenario_C := (
    _contem_indice_posicional(seletor_hint) AND
    verificacao_usa_substring_matching_em_verificar_identidade_elemento
  )

  RETURN cenario_A OR cenario_B OR cenario_C
END FUNCTION
```

### Property Specification - Fix Checking

```pascal
// Property 1: Sniper rejeita candidatos posicionais com identidade errada
FOR ALL X WHERE cenario_A(X) DO
  candidatos ← _gerar_candidatos'(X)
  FOR ALL cand IN candidatos WHERE _contem_indice_posicional(cand.seletor) DO
    elemento_texto ← texto do elemento encontrado por cand.seletor
    IF elemento_texto.strip().lower() ≠ label_curto.strip().lower() THEN
      ASSERT Sniper NÃO retorna True para este candidato
    END IF
  END FOR
END FOR

// Property 2: Match exato nas coordenadas
FOR ALL (label, texto) WHERE label IN texto AND label ≠ texto DO
  resultado ← _verificar_identidade_por_coordenadas'(label, texto)
  ASSERT resultado = (False, False)
END FOR

// Property 3: Coordenadas depois de seletor_hint
ASSERT posicao_coords_na_cascata > posicao_seletor_hint_na_cascata

// Property 4: Match exato em _verificar_identidade_elemento
FOR ALL (label, texto) WHERE label IN texto AND label ≠ texto DO
  resultado ← _verificar_identidade_elemento'(locator_com_texto=texto, label)
  ASSERT resultado = False
END FOR
```

### Property Specification - Preservation Checking

```pascal
FOR ALL X WHERE NOT isBugCondition(X) DO
  // Fail-open cases inalterados
  IF label_curto(X) = "" OR label_curto(X) IS NULL THEN
    ASSERT verificacao_retorna_True_sem_verificar
  END IF

  IF is_cross_origin(X) THEN
    ASSERT _verificar_identidade_por_coordenadas(X) = (True, True)
    ASSERT _verificar_identidade_por_coordenadas'(X) = (True, True)
  END IF

  IF elemento_sem_texto(X) THEN
    ASSERT _verificar_identidade_por_coordenadas(X) = (True, False)
    ASSERT _verificar_identidade_por_coordenadas'(X) = (True, False)
  END IF

  // Candidatos semânticos de alta confiança no Sniper: inalterados
  IF candidato.seletor contém "[aria-label=", "[data-testid=", "[name=", "[id=" THEN
    ASSERT comportamento_sniper_inalterado
  END IF

  // Candidatos text= no Sniper: já têm match exato, inalterados
  IF candidato.seletor.startswith("text=") THEN
    ASSERT comportamento_sniper_inalterado
  END IF
END FOR
```

### Counterexamples

**Exemplo 1: Falso positivo no Sniper — seletor posicional (Cenário A)**

```json
{
  "label_curto": "1",
  "seletor_hint": "[role=\"dialog\"] span:nth-child(1)"
}
```

**Comportamento Atual (Buggy)**:
- Sniper tenta `[role="dialog"] span:nth-child(1)` via `_tentar_candidato()`
- Elemento encontrado tem texto "EMPRESA 1"
- Nenhuma verificação → retorna `True` (FALSO POSITIVO)
- Modal fecha incorretamente → ações seguintes falham em cascata

**Comportamento Esperado (Fixed)**:
- Sniper tenta `[role="dialog"] span:nth-child(1)`
- Elemento encontrado tem texto "EMPRESA 1"
- Verificação: `"1" == "empresa 1"` → False → rejeita candidato
- Escala para Gemini Vision → localiza o número "1" correto

**Exemplo 2: Falso positivo nas coordenadas — substring matching (Cenário B)**

```json
{
  "label_curto": "1",
  "coordenadas_relativas": {"x_pct": 0.5, "y_pct": 0.3}
}
```

**Comportamento Atual (Buggy)**:
- `elementFromPoint` retorna elemento com texto "EMPRESA 1"
- `"1" in "EMPRESA 1"` → True (FALSO POSITIVO)
- Clica no elemento errado, marca como sucesso

**Comportamento Esperado (Fixed)**:
- `elementFromPoint` retorna "EMPRESA 1"
- `"1" == "empresa 1"` → False → rejeita
- Escala para Gemini Vision

**Exemplo 3: Preservation — candidato semântico sem verificação adicional**

```json
{
  "label_curto": "Salvar",
  "seletor_hint": "[aria-label='Salvar']"
}
```

**Comportamento Atual e Esperado (Preservation)**:
- Sniper tenta `[aria-label='Salvar']` — seletor semântico de alta confiança
- Sem verificação adicional (seletor já é específico)
- Comportamento inalterado

---

## Technical Context

### Affected Module
- **File**: `vision_engine.py`
- **Functions**:
  - `encontrar_e_clicar()` — bloco do Sniper (linhas ~2090-2170) e ordem da cascata (linhas ~2170-2260)
  - `_verificar_identidade_por_coordenadas()` — linhas ~1820-1845
  - `_verificar_identidade_elemento()` — linhas ~490-520

### Root Cause Summary

1. **Sniper sem verificação para candidatos CSS posicionais**: `_tentar_candidato()` é chamado diretamente sem verificar identidade para candidatos CSS
2. **Substring matching em duas funções**: `_verificar_identidade_por_coordenadas()` e `_verificar_identidade_elemento()` usam `in` ao invés de `==`
3. **Ordem incorreta na cascata**: coordenadas (Camada 2) antes de seletor_hint (Camada 3)

### Proposed Fix Strategy

**Fase 1: Verificação de identidade no Sniper para candidatos posicionais**
- Após `_tentar_candidato()` retornar True para candidato posicional, verificar identidade com match exato
- Rejeitar e continuar para próximo candidato se identidade não confirmada

**Fase 2: Match exato nas funções de verificação**
- `_verificar_identidade_por_coordenadas()`: substituir `in` por `==`
- `_verificar_identidade_elemento()`: substituir `in` por `==`

**Fase 3: Reordenar cascata**
- Mover bloco de coordenadas para depois da Camada 3 (seletor_hint)

### Success Criteria
- Taxa de sucesso da execução: >90% (atualmente ~29.4%)
- Zero falsos positivos onde `label_curto` é substring de texto maior
- Zero falhas em cascata causadas por cliques no elemento errado
- Candidatos posicionais no Sniper verificados antes de retornar sucesso
- Coordenadas tentadas DEPOIS de seletor_hint
- Nenhuma regressão em casos de preservation (fail-open, candidatos semânticos)

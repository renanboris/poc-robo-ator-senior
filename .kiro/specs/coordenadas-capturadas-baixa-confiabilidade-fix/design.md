# Cascata de Execução — Verificação de Identidade Uniforme (Bugfix Design)

## Overview

O problema raiz não é apenas as coordenadas capturadas. É que a cascata de execução em `vision_engine.py` **não tem verificação de identidade uniforme entre camadas**. Cada camada usa uma lógica diferente (ou nenhuma) para confirmar que o elemento atingido é o correto:

| Camada | Verificação atual | Problema |
|---|---|---|
| Sniper — candidatos `text=` | Match exato ✅ | OK |
| Sniper — candidatos CSS posicionais | Nenhuma ❌ | Falso positivo silencioso |
| Camada 3 — seletor_hint posicional | Substring matching via `_verificar_identidade_elemento()` ⚠️ | Aceita parciais |
| Camada 2 — coordenadas capturadas | Substring matching ❌ | Aceita `"1" in "EMPRESA 1"` |

O resultado é uma cascata que pode marcar "sucesso" ao clicar no elemento errado, corrompendo o estado da aplicação e causando falhas em cascata em todas as ações seguintes.

**Evidência concreta do log:**
```
❌ Ação 2: [Sniper] Acerto: seletor_hint priority '[role="dialog"] span:nth-child(1)'
   → Sistema achou que acertou, mas clicou no elemento errado
   → Modal fechou incorretamente
❌ Ação 3: Escalou para coordenadas (modal já fechado)
❌ Ação 4: Coordenadas clicaram no lugar errado
   → [Coords Capturadas] Identidade não confirmada: esperado 'ui-btn', encontrado 'Código Nome 1 Empresa Padrão'
```

A falha em cascata começou na **Ação 2 no Sniper**, não nas coordenadas. As coordenadas são apenas o sintoma mais visível porque têm telemetria explícita (29.4%).

**Solução arquitetural:** Introduzir uma função central de verificação de identidade — `_verificar_identidade_pos_clique()` — e aplicá-la de forma consistente em todas as camadas que executam cliques em elementos potencialmente ambíguos. Complementar com a reordenação das coordenadas para depois do seletor_hint.

## Glossary

- **Falso positivo**: Sistema executa ação e retorna `True`, mas clicou no elemento errado
- **Falha em cascata**: Ações seguintes falham porque o estado da aplicação ficou incorreto após um falso positivo
- **Verificação de identidade**: Confirmar que o elemento atingido corresponde ao `label_curto` esperado
- **Match exato**: `label.strip().lower() == texto.strip().lower()` — sem aceitar substrings
- **Fail-open**: Aceitar sem verificação quando não é possível verificar (cross-origin, sem texto, exceção)
- **Candidato posicional**: Seletor CSS com `:nth-child()`, `:nth-of-type()`, `#id-numerico` — frágil por natureza
- **`_verificar_identidade_pos_clique()`**: Nova função central de verificação pós-clique (a ser criada)
- **`_verificar_identidade_por_coordenadas()`**: Função existente de verificação por coordenadas (a ser corrigida)
- **`_verificar_identidade_elemento()`**: Função existente de verificação por locator (usa substring — a ser corrigida)
- **Camada 2_S (Sniper)**: Camada de candidatos semânticos — precisa de verificação para candidatos posicionais
- **Camada 2 (Coords)**: Camada de coordenadas capturadas — precisa de match exato e reposicionamento
- **Camada 3 (Hint)**: Camada de seletor_hint original — precisa de match exato na verificação posicional

## Bug Details

### Bug Condition

O bug manifesta em qualquer camada que executa um clique sem verificar rigorosamente se o elemento atingido é o correto. Há três pontos de falha:

**Formal Specification:**
```
FUNCTION isBugCondition(X)
  INPUT: X of type AcaoTecnica
  OUTPUT: boolean

  // Bug ocorre em qualquer um dos três cenários:

  // Cenário A: Sniper tenta candidato CSS posicional sem verificação de identidade
  cenario_A := (
    candidato.seletor contém ":nth-child" OR ":nth-of-type" OR "#id-numerico" AND
    verificacao_identidade_ausente_no_sniper_para_css
  )

  // Cenário B: Coordenadas usadas antes de seletor_hint + substring matching
  cenario_B := (
    coords_relativas IS NOT NULL AND
    camada_coords = 2 AND  // antes de seletor_hint (Camada 3)
    verificacao_usa_substring_matching
  )

  // Cenário C: Seletor_hint posicional verificado com substring matching
  cenario_C := (
    _contem_indice_posicional(seletor_hint) AND
    verificacao_usa_substring_matching_via_verificar_identidade_elemento
  )

  RETURN cenario_A OR cenario_B OR cenario_C
END FUNCTION
```

### Root Cause Analysis

**Causa 1 — Sniper sem verificação para candidatos CSS posicionais** (mais crítica):

O Sniper aplica verificação de identidade apenas para candidatos `text=`. Para candidatos CSS (incluindo posicionais como `span:nth-child(1)`), usa `_tentar_candidato()` diretamente sem verificação. Isso permite que um seletor posicional acerte o elemento errado silenciosamente.

```python
# ATUAL — candidatos CSS não têm verificação de identidade:
_acertou = await _tentar_candidato(page, cand, acao, valor, timeout_ms=_timeout_cand)
if _acertou:
    return True  # ← sem verificar se era o elemento certo
```

**Causa 2 — Coordenadas antes de seletor_hint** (ordem incorreta):

```python
# ATUAL (incorreto):
# Sniper → Coordenadas (Camada 2) → Seletor Hint (Camada 3)

# CORRETO:
# Sniper → Seletor Hint (Camada 3) → Coordenadas (Camada 3.5)
```

**Causa 3 — Substring matching na verificação de coordenadas**:

```python
# ATUAL — aceita "1" in "EMPRESA 1" → True (falso positivo):
if label_curto.strip().lower() in texto_elemento.strip().lower():
    return (True, False)
```

**Causa 4 — Substring matching em `_verificar_identidade_elemento()`**:

```python
# ATUAL — usado na Camada 3 para seletores posicionais:
if needle in texto.strip().lower():  # needle = label_curto
    return True  # aceita substrings
```

### Examples

**Exemplo 1: Falso positivo no Sniper — seletor posicional**

```json
{
  "label_curto": "1",
  "seletor_hint": "[role=\"dialog\"] span:nth-child(1)",
  "intencao_semantica": "Selecionar o primeiro item da lista"
}
```

**Comportamento Atual (Buggy)**:
- Sniper tenta `[role="dialog"] span:nth-child(1)` via `_tentar_candidato()`
- Elemento encontrado e clicado — mas é "EMPRESA 1", não o número "1"
- Nenhuma verificação de identidade → retorna `True` (FALSO POSITIVO)
- Modal fecha incorretamente → ações seguintes falham em cascata

**Comportamento Esperado (Fixed)**:
- Sniper tenta `[role="dialog"] span:nth-child(1)`
- Elemento encontrado → verifica identidade: `"1" == "empresa 1"` → False
- Rejeita candidato, tenta próximo
- Escala para Gemini Vision → localiza o número "1" correto

**Exemplo 2: Falso positivo nas coordenadas — substring matching**

```json
{
  "label_curto": "1",
  "coordenadas_relativas": {"x_pct": 0.5, "y_pct": 0.3}
}
```

**Comportamento Atual (Buggy)**:
- Coordenadas calculadas (x=960, y=324)
- `elementFromPoint` retorna elemento com texto "EMPRESA 1"
- `"1" in "EMPRESA 1"` → True (FALSO POSITIVO)
- Clica no elemento errado, marca como sucesso

**Comportamento Esperado (Fixed)**:
- Coordenadas calculadas (x=960, y=324)
- `elementFromPoint` retorna "EMPRESA 1"
- `"1" == "empresa 1"` → False → rejeita
- Escala para Gemini Vision

**Exemplo 3: Preservation — candidato CSS semântico sem label**

```json
{
  "label_curto": "",
  "seletor_hint": "[name='e070emp'] button"
}
```

**Comportamento Atual e Esperado (Preservation)**:
- Sniper tenta `[name='e070emp'] button`
- `label_curto` vazio → fail-open, sem verificação de identidade
- Clica normalmente
- Comportamento inalterado

**Exemplo 4: Preservation — cross-origin iframe**

```json
{
  "label_curto": "Confirmar",
  "iframe_hint": "iframe#external-payment",
  "coordenadas_relativas": {"x_pct": 0.5, "y_pct": 0.5}
}
```

**Comportamento Atual e Esperado (Preservation)**:
- Cross-origin detectado → fail-open `(True, True)`
- Clica sem verificação
- Comportamento inalterado

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- Fail-open para `label_curto` vazio/None: sem verificação, aceitar
- Fail-open para iframe cross-origin: aceitar sem verificação
- Fail-open para elemento sem texto: aceitar sem verificação
- Fail-open para exceção durante verificação: aceitar sem verificação
- Candidatos semânticos de alta confiança (`[aria-label=]`, `[data-testid=]`, `[name=]`, `[id=]`) com `label_curto` específico: comportamento inalterado
- Candidatos `text=` no Sniper: já têm match exato, comportamento inalterado
- Toda a lógica de Brain, Menu de Contexto, Foco Nativo, Heurísticas: inalterada
- Telemetria e Brain learning: inalterados

**Scope:**
Apenas candidatos CSS posicionais no Sniper, a verificação de coordenadas, e a verificação de seletor_hint posicional são afetados. Candidatos semânticos de alta confiança não recebem verificação adicional para não degradar performance.

## Correctness Properties

### Property 1: Verificação de identidade para candidatos posicionais no Sniper

_For any_ candidato CSS no Sniper que contém índice posicional (`:nth-child`, `:nth-of-type`, `#id-numerico`) e `label_curto` não-vazio e não-genérico, o executor corrigido SHALL verificar identidade com match exato após localizar o elemento, rejeitando o candidato se o texto não corresponder exatamente.

**Validates: Requirements 1.2, 2.2, 2.3**

### Property 2: Match exato na verificação de coordenadas

_For any_ chamada a `_verificar_identidade_por_coordenadas()` onde o elemento tem texto e não é cross-origin, o executor corrigido SHALL usar match exato (`==`) ao invés de substring matching (`in`).

**Validates: Requirements 1.2, 2.2, 2.4**

### Property 3: Coordenadas depois de seletor_hint na cascata

_For any_ ação técnica com coordenadas capturadas e seletor_hint presente, o executor corrigido SHALL tentar o seletor_hint (Camada 3) antes das coordenadas (Camada 3.5).

**Validates: Requirements 2.1, 2.6**

### Property 4: Match exato em `_verificar_identidade_elemento()`

_For any_ chamada a `_verificar_identidade_elemento()` (usada na Camada 3 para seletores posicionais), o executor corrigido SHALL usar match exato ao invés de substring matching.

**Validates: Requirements 1.2, 2.2**

### Property 5: Preservation — fail-open inalterado

_For any_ caso de fail-open (label vazio, cross-origin, sem texto, exceção), o executor corrigido SHALL retornar exatamente o mesmo resultado que o executor original.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5**

## Fix Implementation

### Mudança 1 — Nova função central `_e_candidato_posicional()`

Criar função helper para detectar se um candidato CSS é posicional (reutiliza `_contem_indice_posicional()` existente):

```python
def _e_candidato_posicional(cand: TentativaLocalizacao) -> bool:
    """Retorna True se o candidato usa seletor CSS posicional instável."""
    return bool(cand.seletor and _contem_indice_posicional(cand.seletor))
```

### Mudança 2 — Verificação de identidade no Sniper para candidatos posicionais

Em `encontrar_e_clicar()`, no bloco do Sniper, adicionar verificação de identidade para candidatos CSS posicionais:

```python
# ANTES — candidatos CSS sem verificação:
else:
    _acertou = await _tentar_candidato(page, cand, acao, valor, timeout_ms=_timeout_cand)
    if _acertou:
        return True

# DEPOIS — candidatos posicionais com verificação de identidade:
else:
    _acertou = await _tentar_candidato(page, cand, acao, valor, timeout_ms=_timeout_cand)
    if _acertou:
        # Verificação de identidade para candidatos posicionais
        if _e_candidato_posicional(cand) and label_curto and not _e_label_generico(label_curto):
            locator = await _resolver_contexto(page, cand.iframe_hint)
            locator = locator.locator(cand.seletor).first
            identidade_ok = await _verificar_identidade_elemento_exato(locator, label_curto)
            if not identidade_ok:
                logger.warning(
                    f"   [Sniper] Candidato posicional '{cand.descricao}' — "
                    f"identidade não confirmada, rejeitando"
                )
                continue  # Rejeitar e tentar próximo candidato
        return True
```

### Mudança 3 — Corrigir `_verificar_identidade_elemento()` para match exato

A função existente usa substring matching. Criar variante com match exato ou corrigir a existente:

```python
async def _verificar_identidade_elemento(locator, label_curto: str) -> bool:
    """
    Verifica identidade com MATCH EXATO (não substring).
    
    ANTES: needle in texto (substring — aceita falsos positivos)
    DEPOIS: texto_norm == needle (match exato — rejeita falsos positivos)
    """
    if not label_curto:
        return True
    needle = label_curto.strip().lower()
    
    try:
        texto = await locator.inner_text(timeout=1000)
        texto_norm = texto.strip().lower()
        if texto_norm == needle:
            return True
        # Tenta o pai
        try:
            texto_pai = await locator.locator("..").inner_text(timeout=1000)
            return texto_pai.strip().lower() == needle
        except Exception:
            return False  # texto foi lido mas não bateu
    except Exception:
        return True  # fail-open: não conseguiu ler texto
```

**ATENÇÃO**: Esta mudança afeta a Camada 3 (seletor_hint posicional). Verificar se há outros usos de `_verificar_identidade_elemento()` que dependem do comportamento de substring antes de aplicar.

### Mudança 4 — Corrigir `_verificar_identidade_por_coordenadas()` para match exato

```python
# ANTES:
if label_curto.strip().lower() in texto_elemento.strip().lower():
    return (True, False)

# DEPOIS:
texto_elem_norm = texto_elemento.strip().lower()
label_norm = label_curto.strip().lower()
if texto_elem_norm == label_norm:
    return (True, False)
else:
    logger.warning(
        f"   [Coords Capturadas] Identidade não confirmada: "
        f"esperado '{label_curto}', encontrado '{texto_elemento[:50]}' "
        f"(match exato requerido)"
    )
    return (False, False)
```

### Mudança 5 — Reordenar cascata: coordenadas para depois de seletor_hint

Em `encontrar_e_clicar()`, mover o bloco de coordenadas capturadas para depois da Camada 3:

```python
# ORDEM ATUAL (incorreta):
# ... Sniper ...
# ── 2. Coordenadas Capturadas ────
if coords_relativas and coords_relativas.get("x_pct"):
    ...
# ── Camada 3: Seletor hint original ────
if seletor_hint and not _e_seletor_fragil(seletor_hint):
    ...

# ORDEM CORRETA:
# ... Sniper ...
# ── Camada 3: Seletor hint original ────
if seletor_hint and not _e_seletor_fragil(seletor_hint):
    ...
# ── Camada 3.5: Coordenadas Capturadas ────
if coords_relativas and coords_relativas.get("x_pct"):
    ...
```

### Mudança 6 — Atualizar docstring do módulo

```python
# Camadas de Resiliência:
#   0    Brain (Memória SQLite Permanente)
#   0.5  Menu de contexto ativo
#   1    Foco nativo / active element
#   1.5  Heurísticas Senior X
#   1_T  Template Matching visual
#   2_S  Sniper semântico (com verificação de identidade para candidatos posicionais)
#   3    Seletor hint original (com match exato na verificação posicional)
#   3.5  Coordenadas capturadas (com match exato, movido de Camada 2)
#   4    Busca em todos os frames
#   5    Gemini Vision
```

### Resumo das mudanças por arquivo

| Arquivo | Função | Mudança |
|---|---|---|
| `vision_engine.py` | `_verificar_identidade_elemento()` | Substring → match exato |
| `vision_engine.py` | `_verificar_identidade_por_coordenadas()` | Substring → match exato |
| `vision_engine.py` | `encontrar_e_clicar()` — bloco Sniper | Adicionar verificação para candidatos posicionais |
| `vision_engine.py` | `encontrar_e_clicar()` — ordem da cascata | Mover coordenadas para depois de seletor_hint |
| `vision_engine.py` | docstring do módulo | Atualizar mapa de camadas |

## Testing Strategy

### Exploratory Bug Condition Checking

**Goal**: Demonstrar os três cenários de bug ANTES do fix.

**Test Cases**:

1. **Sniper — falso positivo em candidato posicional** (falhará no código não corrigido)
   - Simular Sniper tentando `span:nth-child(1)` quando elemento tem texto "EMPRESA 1" mas `label_curto="1"`
   - Verificar: retorna `True` sem verificação → FALSO POSITIVO confirmado

2. **Coordenadas — substring matching aceita falso positivo** (falhará no código não corrigido)
   - Simular `_verificar_identidade_por_coordenadas` com `label_curto="1"`, `texto_elemento="EMPRESA 1"`
   - Verificar: retorna `(True, False)` → FALSO POSITIVO confirmado

3. **`_verificar_identidade_elemento()` — substring matching** (falhará no código não corrigido)
   - Simular com `label_curto="Sim"`, `texto_elemento="Sim, confirmar operação"`
   - Verificar: retorna `True` → FALSO POSITIVO confirmado

### Fix Checking

**Pseudocode:**
```
// Property 1: Sniper rejeita candidatos posicionais com identidade errada
FOR ALL cand WHERE _e_candidato_posicional(cand) AND label_curto não-vazio DO
  elemento_texto := texto do elemento encontrado pelo seletor
  IF elemento_texto.strip().lower() ≠ label_curto.strip().lower() THEN
    ASSERT Sniper rejeita candidato (não retorna True)
  END IF
END FOR

// Property 2: Match exato nas coordenadas
FOR ALL (label, texto) WHERE label IN texto AND label ≠ texto DO
  resultado := _verificar_identidade_por_coordenadas'(label, texto)
  ASSERT resultado = (False, False)
END FOR

// Property 3: Coordenadas depois de seletor_hint
ASSERT posicao_coords_na_cascata > posicao_seletor_hint_na_cascata

// Property 4: Match exato em _verificar_identidade_elemento
FOR ALL (label, texto) WHERE label IN texto AND label ≠ texto DO
  resultado := _verificar_identidade_elemento'(locator_com_texto=texto, label)
  ASSERT resultado = False
END FOR
```

**Test Cases**:

1. **Sniper posicional rejeitado** (deve passar no código corrigido)
   - `seletor="span:nth-child(1)"`, elemento tem texto "EMPRESA 1", `label_curto="1"` → rejeitado

2. **Sniper posicional aceito** (deve passar no código corrigido)
   - `seletor="span:nth-child(1)"`, elemento tem texto "1", `label_curto="1"` → aceito

3. **Coordenadas — falso positivo rejeitado** (deve passar no código corrigido)
   - `label="1"`, `texto="EMPRESA 1"` → `(False, False)`

4. **Coordenadas — match correto aceito** (deve passar no código corrigido)
   - `label="Confirmar"`, `texto="Confirmar"` → `(True, False)`

5. **`_verificar_identidade_elemento` — falso positivo rejeitado** (deve passar no código corrigido)
   - `label="Sim"`, `texto="Sim, confirmar"` → `False`

### Preservation Checking

**Test Cases**:

1. **label_curto vazio — fail-open** (deve passar antes e depois)
   - `label_curto=""` → `(True, False)` nas coordenadas, `True` no elemento

2. **Cross-origin — fail-open** (deve passar antes e depois)
   - `is_cross_origin=True` → `(True, True)`

3. **Elemento sem texto — fail-open** (deve passar antes e depois)
   - `innerText=""` → `(True, False)`

4. **Candidato semântico de alta confiança no Sniper** (deve passar antes e depois)
   - `seletor="[name='e070emp'] button"` (não posicional) → sem verificação adicional, comportamento inalterado

5. **Candidato `text=` no Sniper** (deve passar antes e depois)
   - Já tem match exato → comportamento inalterado

### Property-Based Tests

- Gerar pares `(label, texto)` onde `label` é substring de `texto` mas não igual → todos rejeitados
- Gerar pares onde `label.strip().lower() == texto.strip().lower()` → todos aceitos
- Gerar seletores CSS aleatórios com e sem índices posicionais → `_e_candidato_posicional()` classifica corretamente
- Gerar ações com e sem coordenadas + seletor_hint → ordem da cascata sempre correta

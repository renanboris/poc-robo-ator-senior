# Design Document — scorm-simlink-refinement

## Overview

Este documento descreve o design técnico para os quatro refinamentos do pipeline de geração de artefatos de treinamento:

1. **Correção da imagem de âncora** — `scorm_builder.py` e `sim_link_builder.py` devem usar `screenshot_depois` da *última* ação do passo anterior como âncora, com fallback para `screenshot_referencia`.
2. **Leitura correta de `_vp_w`/`_vp_h`** — ambos os builders devem ler o viewport do nível da ação técnica (irmão de `elemento_alvo`), não de dentro de `elemento_alvo`.
3. **Uso de SoM no SimLink** — `sim_link_builder.py` deve adotar a mesma estratégia de coordenadas do SCORM: priorizar `som_box_clicada` + viewport sobre `coordenadas_relativas`.
4. **Espera observável no capturador** — `capture_semantic.py` deve substituir `asyncio.sleep(1.2)` por `wait_for_load_state("networkidle")` com timeout de 3 s.

As mudanças são cirúrgicas: nenhum contrato do roteiro JSON é alterado, nenhum pipeline downstream (vídeo, PDF, DAP) é afetado.

---

## Architecture

O sistema segue um pipeline linear de transformação:

```
capture_semantic.py
        │
        ▼  (roteiro JSON)
generator_engine.py
        │
        ├──► scorm_builder.py  ──► SCORM .zip
        ├──► sim_link_builder.py ──► HTML standalone
        ├──► pdf_builder.py    ──► PDF
        └──► video pipeline    ──► MP4
```

Os quatro módulos afetados são independentes entre si no pipeline — as mudanças em `capture_semantic.py` melhoram a qualidade dos dados de entrada; as mudanças nos dois builders corrigem como esses dados são consumidos.

### Módulos afetados

| Módulo | Mudança |
|---|---|
| `scorm_builder.py` | Lógica de âncora + leitura de viewport |
| `scripts/sim_link_builder.py` | Lógica de âncora + leitura de viewport + uso de SoM |
| `CIL/capture/capture_semantic.py` | Substituição de `asyncio.sleep(1.2)` por `networkidle` |

### Módulos não afetados

`generator_engine.py`, `pdf_builder.py`, `main.py`, `dap_engine.py`, `app.py` — nenhuma mudança de contrato ou comportamento.

---

## Components and Interfaces

### 1. Função auxiliar `_selecionar_imagem_ancora(passos, idx)`

Ambos os builders precisam da mesma lógica de seleção de âncora. Para garantir consistência (Requirement 4.1), essa lógica deve ser extraída para uma função auxiliar compartilhada ou duplicada de forma idêntica nos dois módulos.

**Opção adotada**: função standalone `_selecionar_imagem_ancora` definida em cada builder (sem criar um novo módulo compartilhado, para minimizar risco de regressão no pipeline).

```python
def _selecionar_imagem_ancora(passos: list, idx: int) -> str | None:
    """
    Retorna a imagem de âncora para o passo de índice `idx`.

    Prioridade:
      1. screenshot_depois da última ação do passo anterior com valor não-vazio
      2. screenshot_referencia da última ação do passo anterior com valor não-vazio
      3. None (sem exceção)

    Para idx == 0, retorna None diretamente.
    """
    if idx == 0:
        return None
    acoes = passos[idx - 1].get("acoes_tecnicas", [])
    # Percorre de trás para frente para encontrar a última ação com screenshot_depois
    for acao in reversed(acoes):
        val = acao.get("elemento_alvo", {}).get("screenshot_depois")
        if val and isinstance(val, str):
            return val
    # Fallback: última ação com screenshot_referencia
    for acao in reversed(acoes):
        val = acao.get("elemento_alvo", {}).get("screenshot_referencia")
        if val and isinstance(val, str):
            return val
    return None
```

### 2. Função auxiliar `_ler_viewport(acao: dict) -> tuple[int, int]`

Lê `_vp_w`/`_vp_h` com a hierarquia correta: nível da ação → dentro de `elemento_alvo` → padrão 1920×1080.

```python
def _ler_viewport(acao: dict) -> tuple[int, int]:
    """
    Lê _vp_w/_vp_h com fallback em dois níveis:
      1. Nível da ação técnica (irmão de elemento_alvo) — fonte primária
      2. Dentro de elemento_alvo — fallback para roteiros legados
      3. 1920 × 1080 — padrão final
    """
    vp_w = acao.get("_vp_w") or 0
    vp_h = acao.get("_vp_h") or 0
    if not (vp_w > 0 and vp_h > 0):
        alvo = acao.get("elemento_alvo", {}) or {}
        vp_w = alvo.get("_vp_w") or 0
        vp_h = alvo.get("_vp_h") or 0
    if not (vp_w > 0 and vp_h > 0):
        vp_w, vp_h = 1920, 1080
    return int(vp_w), int(vp_h)
```

### 3. Função auxiliar `_calcular_coords_som(som_box: dict, vp_w: int, vp_h: int) -> tuple[float, float, float, float]`

Converte `som_box_clicada` em percentuais com clamping. Usada por ambos os builders.

```python
def _calcular_coords_som(
    som_box: dict, vp_w: int, vp_h: int
) -> tuple[float, float, float, float]:
    """
    Converte som_box_clicada (coordenadas absolutas) em percentuais [0.0, 1.0].
    Aplica clamping se os valores excederem os limites do viewport.
    """
    x_pct = min(max((som_box["x"] + som_box["w"] / 2) / vp_w, 0.0), 1.0)
    y_pct = min(max((som_box["y"] + som_box["h"] / 2) / vp_h, 0.0), 1.0)
    w_pct = min(max(som_box["w"] / vp_w, 0.0), 1.0)
    h_pct = min(max(som_box["h"] / vp_h, 0.0), 1.0)
    return x_pct, y_pct, w_pct, h_pct
```

### 4. Função auxiliar `_som_box_valido(som_box) -> bool`

Valida se `som_box_clicada` tem todos os campos numéricos necessários com dimensões positivas.

```python
def _som_box_valido(som_box) -> bool:
    if not isinstance(som_box, dict):
        return False
    try:
        return (
            float(som_box["x"]) >= 0
            and float(som_box["y"]) >= 0
            and float(som_box["w"]) > 0
            and float(som_box["h"]) > 0
        )
    except (KeyError, TypeError, ValueError):
        return False
```

### 5. Lógica de coordenadas unificada (ambos os builders)

```python
def _resolver_coords(acao: dict) -> tuple[float, float, float, float]:
    """
    Resolve x_pct, y_pct, w_pct, h_pct para uma ação técnica.
    Prioridade: SoM → coordenadas_relativas → padrão 0.5/0.05
    """
    alvo = acao.get("elemento_alvo", {}) or {}
    som_box = alvo.get("som_box_clicada")
    vp_w, vp_h = _ler_viewport(acao)

    if _som_box_valido(som_box) and vp_w > 0 and vp_h > 0:
        return _calcular_coords_som(som_box, vp_w, vp_h)

    coords = alvo.get("coordenadas_relativas") or {}
    return (
        coords.get("x_pct", 0.5),
        coords.get("y_pct", 0.5),
        coords.get("w_pct", 0.05),
        coords.get("h_pct", 0.05),
    )
```

### 6. Mudança em `capture_semantic.py` — espera observável

Substituição do `asyncio.sleep(1.2)` fixo por `wait_for_load_state("networkidle")` com timeout de 3 s e tratamento de exceção:

```python
# ANTES (buggy):
await asyncio.sleep(1.2)
screenshot_depois = await page.screenshot(type="jpeg", quality=60, full_page=False)

# DEPOIS (correto):
try:
    await page.wait_for_load_state("networkidle", timeout=3000)
except Exception:
    pass  # timeout ou página inacessível — captura no estado atual
try:
    screenshot_depois = await page.screenshot(type="jpeg", quality=60, full_page=False)
    b64_img_depois = base64.b64encode(screenshot_depois).decode("utf-8")
except Exception:
    b64_img_depois = ""
```

---

## Data Models

### Roteiro JSON — campos relevantes (sem alteração de contrato)

```
passo
├── id_passo: int
├── pedagogia.ancora: str
└── acoes_tecnicas: list[acao_tecnica]

acao_tecnica
├── acao: str
├── _vp_w: int          ← nível da ação (fonte primária)
├── _vp_h: int          ← nível da ação (fonte primária)
└── elemento_alvo
    ├── coordenadas_relativas: {x_pct, y_pct, w_pct, h_pct}
    ├── screenshot_referencia: str | None
    ├── screenshot_depois: str | None
    ├── som_box_clicada: {x, y, w, h} | None
    ├── _vp_w: int      ← dentro de elemento_alvo (fallback legado)
    └── _vp_h: int      ← dentro de elemento_alvo (fallback legado)
```

### Slide de âncora (saída dos builders)

```
{
  "tipo": "ancora",
  "imagem_b64": str | None,   ← screenshot_depois da última ação do passo anterior
  "texto": str,
  ...
}
```

### Slide de interação (saída dos builders)

```
{
  "tipo": "interacao",
  "x_pct": float,   ← [0.0, 1.0], calculado via SoM ou coordenadas_relativas
  "y_pct": float,
  "w_pct": float,
  "h_pct": float,
  ...
}
```

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Seleção correta da imagem de âncora

*Para qualquer* roteiro com N passos (N ≥ 2), para todo passo de índice `i > 0`, a imagem de âncora produzida por ambos os builders deve ser igual a `screenshot_depois` da última ação técnica do passo `i-1` que tenha `screenshot_depois` não-vazio; se nenhuma ação tiver `screenshot_depois` não-vazio, deve ser `screenshot_referencia` da última ação com valor não-vazio; se nenhuma existir, deve ser `None`. Para `i = 0`, a âncora deve ser sempre `None`.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 4.1**

### Property 2: Leitura de viewport no nível correto

*Para qualquer* ação técnica onde `_vp_w` e `_vp_h` existam apenas no nível da ação (não dentro de `elemento_alvo`), ambos os builders devem calcular `x_pct` e `y_pct` usando esses valores — e não os valores padrão 1920×1080.

**Validates: Requirements 2.1, 2.2**

### Property 3: Invariante de clamping de coordenadas

*Para qualquer* `som_box_clicada` com campos numéricos (incluindo valores fora dos limites do viewport) e qualquer viewport positivo, os valores `x_pct`, `y_pct`, `w_pct` e `h_pct` produzidos por ambos os builders devem estar no intervalo `[0.0, 1.0]`.

**Validates: Requirements 2.5, 3.4**

### Property 4: Consistência de coordenadas entre os dois builders

*Para qualquer* roteiro de entrada, para toda ação técnica, os valores de `x_pct`, `y_pct`, `w_pct` e `h_pct` produzidos pelo SCORM_Builder e pelo SimLink_Builder devem ser idênticos (diferença absoluta < 0.0001).

**Validates: Requirements 3.5, 4.2**

### Property 5: Consistência de contagem de slides entre os dois builders

*Para qualquer* roteiro de entrada, o número de slides de âncora gerados pelo SCORM_Builder deve ser igual ao número gerado pelo SimLink_Builder (contando apenas passos com `ancora` não-vazio); e o número de slides de interação deve ser igual entre os dois (excluindo ações com `acao == "concluir_video"`).

**Validates: Requirements 4.3, 4.4**

### Property 6: Robustez com screenshots ausentes ou nulos

*Para qualquer* roteiro cujas ações técnicas tenham `screenshot_referencia`, `screenshot_depois` e `som_box_clicada` com valores `None`, string vazia ou campo ausente (em qualquer combinação), ambos os builders devem concluir a geração do artefato sem lançar exceção.

**Validates: Requirements 6.1, 6.2, 6.4**

---

## Error Handling

### Builders (`scorm_builder.py`, `sim_link_builder.py`)

| Condição | Comportamento |
|---|---|
| `screenshot_depois` ausente/None/vazio | Fallback para `screenshot_referencia`; se também ausente, âncora = `None` |
| `_vp_w`/`_vp_h` ausentes no nível da ação | Fallback para `elemento_alvo`; se também ausentes, usar 1920×1080 |
| `_vp_w`/`_vp_h` zero ou negativos | Tratar como ausente, aplicar fallback |
| `som_box_clicada` None ou inválido | Fallback para `coordenadas_relativas` |
| `coordenadas_relativas` ausente | Usar padrão `x_pct=0.5, y_pct=0.5, w_pct=0.05, h_pct=0.05` |
| Coordenadas SoM fora de `[0.0, 1.0]` | Aplicar clamping silencioso |
| `som_box_clicada` com campos não-numéricos | Tratar como inválido, usar fallback |

Nenhuma dessas condições deve interromper a geração do artefato.

### Capturador (`capture_semantic.py`)

| Condição | Comportamento |
|---|---|
| `networkidle` não ocorre em 3 s | Capturar screenshot no estado atual, sem exceção |
| Página fechada/inacessível no momento da captura | `screenshot_depois = ""`, continuar sem exceção |
| Exceção genérica no bloco de captura | Logar warning, `screenshot_depois = ""`, continuar |

O bloco de captura do `screenshot_depois` deve ser completamente isolado com `try/except` para não interromper o fluxo de processamento da fila.

---

## Testing Strategy

### Abordagem dual

- **Testes de propriedade** (Hypothesis): validam invariantes universais sobre os builders com entradas geradas aleatoriamente.
- **Testes de exemplo** (pytest): validam comportamentos específicos do capturador e casos de borda concretos.

### Biblioteca de property-based testing

**Hypothesis** (já presente no projeto, conforme `.hypothesis/` no workspace).

Configuração mínima: `@settings(max_examples=100)` por propriedade.

Tag de rastreabilidade: `# Feature: scorm-simlink-refinement, Property {N}: {texto}`

### Testes de propriedade (Hypothesis)

Cada propriedade do design deve ter um teste correspondente:

**P1 — Seleção de âncora**
```python
# Feature: scorm-simlink-refinement, Property 1: anchor image selection
@given(roteiro=st_roteiro())
@settings(max_examples=100)
def test_ancora_selection(roteiro):
    scorm_slides = _extrair_slides_scorm(roteiro)
    simlink_slides = _extrair_slides_simlink(roteiro)
    passos = roteiro["passos"]
    for idx, passo in enumerate(passos):
        if not passo.get("pedagogia", {}).get("ancora"):
            continue
        ancora_esperada = _selecionar_imagem_ancora(passos, idx)
        scorm_ancora = next(s for s in scorm_slides if s["tipo"] == "ancora" and s["scene_id"] == passo["id_passo"])
        simlink_ancora = next(s for s in simlink_slides if s["tipo"] == "ancora")
        assert scorm_ancora["imagem_b64"] == ancora_esperada
        assert simlink_ancora["imagem_b64"] == ancora_esperada
```

**P2 — Leitura de viewport**
```python
# Feature: scorm-simlink-refinement, Property 2: viewport reading at action level
@given(acao=st_acao_com_viewport_apenas_no_nivel_acao())
@settings(max_examples=100)
def test_viewport_lido_do_nivel_correto(acao):
    vp_w, vp_h = _ler_viewport(acao)
    assert vp_w == acao["_vp_w"]
    assert vp_h == acao["_vp_h"]
```

**P3 — Clamping**
```python
# Feature: scorm-simlink-refinement, Property 3: coordinate clamping invariant
@given(som_box=st_som_box_qualquer(), vp=st_viewport_positivo())
@settings(max_examples=100)
def test_coords_sempre_em_range(som_box, vp):
    x, y, w, h = _calcular_coords_som(som_box, vp[0], vp[1])
    assert 0.0 <= x <= 1.0
    assert 0.0 <= y <= 1.0
    assert 0.0 <= w <= 1.0
    assert 0.0 <= h <= 1.0
```

**P4 — Consistência de coordenadas**
```python
# Feature: scorm-simlink-refinement, Property 4: coordinate consistency between builders
@given(roteiro=st_roteiro())
@settings(max_examples=100)
def test_coords_identicas_entre_builders(roteiro):
    scorm_slides = [s for s in _extrair_slides_scorm(roteiro) if s["tipo"] == "interacao"]
    simlink_slides = [s for s in _extrair_slides_simlink(roteiro) if s["tipo"] == "interacao"]
    for s, sl in zip(scorm_slides, simlink_slides):
        assert abs(s["x_pct"] - sl["x_pct"]) < 0.0001
        assert abs(s["y_pct"] - sl["y_pct"]) < 0.0001
        assert abs(s["w_pct"] - sl["w_pct"]) < 0.0001
        assert abs(s["h_pct"] - sl["h_pct"]) < 0.0001
```

**P5 — Contagem de slides**
```python
# Feature: scorm-simlink-refinement, Property 5: slide count consistency
@given(roteiro=st_roteiro())
@settings(max_examples=100)
def test_contagem_slides_identica(roteiro):
    scorm_slides = _extrair_slides_scorm(roteiro)
    simlink_slides = _extrair_slides_simlink(roteiro)
    assert sum(1 for s in scorm_slides if s["tipo"] == "ancora") == \
           sum(1 for s in simlink_slides if s["tipo"] == "ancora")
    assert sum(1 for s in scorm_slides if s["tipo"] == "interacao") == \
           sum(1 for s in simlink_slides if s["tipo"] == "interacao")
```

**P6 — Robustez com screenshots ausentes**
```python
# Feature: scorm-simlink-refinement, Property 6: robustness with missing screenshots
@given(roteiro=st_roteiro_sem_screenshots())
@settings(max_examples=100)
def test_builders_nao_explodem_sem_screenshots(roteiro, tmp_path):
    # Não deve lançar exceção
    _extrair_slides_scorm(roteiro)
    _extrair_slides_simlink(roteiro)
```

### Testes de exemplo (pytest)

Para o capturador (`capture_semantic.py`), usar mocks do Playwright:

```python
# Req 5.1 — networkidle é aguardado
async def test_captura_aguarda_networkidle(mock_page):
    mock_page.wait_for_load_state = AsyncMock()
    mock_page.screenshot = AsyncMock(return_value=b"fake_jpeg")
    await processar_screenshot_depois(mock_page)
    mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=3000)

# Req 5.2 — timeout não propaga exceção
async def test_captura_timeout_nao_propaga(mock_page):
    mock_page.wait_for_load_state = AsyncMock(side_effect=TimeoutError)
    mock_page.screenshot = AsyncMock(return_value=b"fake_jpeg")
    result = await processar_screenshot_depois(mock_page)
    assert result != ""  # screenshot ainda é capturado

# Req 5.3 — página fechada retorna string vazia
async def test_captura_pagina_fechada_retorna_vazio(mock_page):
    mock_page.wait_for_load_state = AsyncMock(side_effect=Exception("Target closed"))
    mock_page.screenshot = AsyncMock(side_effect=Exception("Target closed"))
    result = await processar_screenshot_depois(mock_page)
    assert result == ""
```

### Estratégias de geração (Hypothesis)

```python
# Estratégia para som_box com valores potencialmente fora dos limites
@st.composite
def st_som_box_qualquer(draw):
    return {
        "x": draw(st.floats(min_value=-100, max_value=3000)),
        "y": draw(st.floats(min_value=-100, max_value=2000)),
        "w": draw(st.floats(min_value=0.1, max_value=2000)),
        "h": draw(st.floats(min_value=0.1, max_value=2000)),
    }

# Estratégia para roteiro completo com variação em todos os campos relevantes
@st.composite
def st_roteiro(draw):
    n_passos = draw(st.integers(min_value=1, max_value=5))
    passos = []
    for i in range(n_passos):
        n_acoes = draw(st.integers(min_value=1, max_value=4))
        acoes = []
        for _ in range(n_acoes):
            acoes.append({
                "_vp_w": draw(st.one_of(st.none(), st.integers(min_value=0, max_value=2560))),
                "_vp_h": draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1440))),
                "acao": draw(st.sampled_from(["clique", "preencher_campo", "concluir_video"])),
                "elemento_alvo": {
                    "screenshot_referencia": draw(st.one_of(st.none(), st.text(min_size=0, max_size=10))),
                    "screenshot_depois": draw(st.one_of(st.none(), st.text(min_size=0, max_size=10))),
                    "som_box_clicada": draw(st.one_of(st.none(), st_som_box_qualquer())),
                    "coordenadas_relativas": draw(st.one_of(
                        st.none(),
                        st.fixed_dictionaries({
                            "x_pct": st.floats(0.0, 1.0),
                            "y_pct": st.floats(0.0, 1.0),
                            "w_pct": st.floats(0.0, 0.5),
                            "h_pct": st.floats(0.0, 0.5),
                        })
                    )),
                    "_vp_w": draw(st.one_of(st.none(), st.integers(min_value=0, max_value=2560))),
                    "_vp_h": draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1440))),
                },
            })
        passos.append({
            "id_passo": i + 1,
            "tipo_passo": "action",
            "pedagogia": {"ancora": draw(st.one_of(st.just(""), st.text(min_size=1, max_size=50)))},
            "acoes_tecnicas": acoes,
        })
    return {"metadata": {"nome_aula": "Teste", "id_treinamento": "teste"}, "passos": passos}
```

### Testes de unidade complementares

- Verificar que `_selecionar_imagem_ancora` retorna `None` para `idx=0`
- Verificar que `_ler_viewport` retorna 1920×1080 quando ambos os níveis estão ausentes
- Verificar que `_som_box_valido` rejeita dicts com campos não-numéricos
- Verificar que `_calcular_coords_som` aplica clamping corretamente para valores extremos

### Plano de teste manual mínimo

1. Gerar um roteiro real com `capture_semantic.py` em um ERP com carregamento lento (> 1,2 s).
2. Verificar que `screenshot_depois` captura a tela estabilizada (não a tela de loading).
3. Gerar SCORM e SimLink a partir do mesmo roteiro.
4. Abrir ambos os artefatos e verificar que:
   - As imagens de âncora mostram o estado correto (tela após a última ação do passo anterior).
   - As zonas interativas estão posicionadas no elemento correto.
   - SCORM e SimLink mostram as mesmas imagens e as mesmas zonas.
5. Testar com um roteiro gerado por IA (sem screenshots) e verificar que ambos os builders concluem sem erro.

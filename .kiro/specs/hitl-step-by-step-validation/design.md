# Design: HITL Step-by-Step Validation

## Overview

Refatorar o `validator_hitl.py` existente para operar em modo step-by-step por padrão: executa uma ação, pausa, mostra resultado ao analista com overlay minimalista (✅ Ok / ✏️ Corrigir), e aguarda decisão antes de avançar. Ao final, dispara `--record` automaticamente.

O sistema já tem a infraestrutura necessária (Playwright bindings, Radar, Brain DB, overlay injection). A mudança principal é no **loop de execução** — de auto-play para step-by-step — e na **interface do overlay** — de complexa para minimalista.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│              validator_hitl.py (Refatorado)              │
├─────────────────────────────────────────────────────────┤
│  Loop Step-by-Step                                      │
│  ┌───────────────────────────────────────────────────┐  │
│  │ Para cada ação:                                   │  │
│  │   1. Executar via encontrar_e_clicar()            │  │
│  │   2. Destacar elemento clicado                    │  │
│  │   3. Exibir overlay: ✅ Ok | ✏️ Corrigir | ⏩ Auto│  │
│  │   4. Aguardar decisão do analista                 │  │
│  │   5. Se Ok → avançar                             │  │
│  │   6. Se Corrigir → Radar → Brain → avançar       │  │
│  │   7. Se Auto → executar N ações sem pausa         │  │
│  └───────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│  Componentes Existentes (sem mudança)                   │
│  • vision_engine.encontrar_e_clicar()                   │
│  • Brain DB (_registrar_sucesso_cache)                   │
│  • Radar (getBestSelector via binding)                   │
│  • Score Engine                                          │
└─────────────────────────────────────────────────────────┘
```

## Overlay Minimalista

O overlay atual é complexo demais (navegador de passos com múltiplos botões). O novo overlay é minimalista:

```
┌─────────────────────────────────────────────────────┐
│  Passo 3/12 — Ação 1/3                              │
│  "Clicou em 'Finanças'" via Brain                   │
│                                                      │
│  [✅ Ok]  [✏️ Corrigir]  [⏩ Auto 5]  [⏭ Pular]   │
└─────────────────────────────────────────────────────┘
```

- Posição: canto inferior esquerdo (não bloqueia a tela)
- Tamanho: compacto (max 400px largura)
- Transparência: semi-transparente para ver a tela por trás
- Z-index máximo para ficar sobre tudo

## Mudanças no Loop de Execução

### Antes (auto-play):
```python
for passo in passos:
    for acao in passo.acoes_tecnicas:
        resultado = await encontrar_e_clicar(page, acao)
        if not resultado:
            # pausa automática (falha)
```

### Depois (step-by-step):
```python
for passo in passos:
    for acao in passo.acoes_tecnicas:
        resultado = await encontrar_e_clicar(page, acao)
        
        if self._modo_auto_restante > 0:
            self._modo_auto_restante -= 1
            if resultado:
                continue  # não pausa em modo auto
            # falha em modo auto → volta para step-by-step
        
        # Destacar elemento e exibir overlay
        await self._mostrar_overlay_step(passo, acao, resultado)
        decisao = await self._aguardar_decisao()
        
        if decisao == "ok":
            continue
        elif decisao == "corrigir":
            seletor = await self._ativar_radar()
            await self._salvar_correcao(acao, seletor)
        elif decisao.startswith("auto_"):
            self._modo_auto_restante = int(decisao.split("_")[1])
        elif decisao == "pular":
            continue
```

## Integração com Dashboard

### Endpoint existente (sem mudança):
```
POST /api/validar-hitl/{arquivo}  → abre validator_hitl.py
```

### Mudança no dashboard:
- Roteiro sem `hitl_validado` → botão principal é "🔍 Validar"
- Roteiro com `hitl_validado: true` → botão principal é "🎬 Gravar"

### Disparo automático de gravação:
Ao final do HITL, se todas as ações foram validadas:
```python
# Opção 1: Perguntar ao analista
resposta = await self._perguntar_gravar()
if resposta == "gravar":
    subprocess.Popen([sys.executable, "main.py", caminho_json, "--record"])
```

## Persistência

### Brain DB:
- `✅ Ok` → `_registrar_sucesso_cache(intencao)` (reforça memória)
- `✏️ Corrigir` → `_registrar_sucesso_cache(intencao, seletor=novo)` com `hitl_corrigido=1`

### Roteiro JSON:
- Ao final, reescreve o JSON com seletores corrigidos (já implementado em `_correcoes_seletores`)

### Proteção de memórias HITL:
- Memórias com `hitl_corrigido=1` não são invalidadas pela limpeza automática do `_init_db()`

## Componentes a Modificar

| Arquivo | Mudança |
|---------|---------|
| `validator_hitl.py` | Refatorar loop para step-by-step, simplificar overlay |
| `vision_engine.py` | Adicionar proteção para memórias `hitl_corrigido=1` no TTL |
| `app.py` | Ajustar lógica de botões no dashboard (validar vs gravar) |
| `templates/dashboard_v2.html` | Botão "🔍 Validar" condicional |

## Decisões de Design

1. **Overlay no browser, não no terminal** — o analista precisa ver a tela e o overlay ao mesmo tempo
2. **Binding Python-JavaScript** — já existe (`__hitl_captura__`), reutilizar
3. **Modo auto com fallback** — permite acelerar quando confiante, mas volta ao step-by-step em falhas
4. **Não gravar durante HITL** — gravação é processo separado, limpo, sem pausas
5. **Reforçar memórias corretas** — "✅ Ok" incrementa hits no Brain, fortalecendo seletores bons

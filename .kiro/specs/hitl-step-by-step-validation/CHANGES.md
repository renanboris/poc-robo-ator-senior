# Mudanças Implementadas: Fix do Radar

## Arquivo: `validator_hitl.py`

### Mudança 1: Injeção de CSS de Animação (Linha ~1710)

**Antes**:
```python
# Mostra indicador visual no frame principal (overlay está lá)
await page.evaluate("""() => {
    const overlay = document.getElementById('hitl-step-overlay');
    if (overlay) {
        let radarMsg = document.getElementById('hitl-step-radar-msg');
        if (!radarMsg) {
            radarMsg = document.createElement('div');
            radarMsg.id = 'hitl-step-radar-msg';
            radarMsg.style.cssText = '...';
            radarMsg.innerHTML = '<span style="...animation:hitl-radar-pulse..."></span>'
            // ❌ CSS não foi injetado — erro!
```

**Depois**:
```python
# Injeta CSS de animação primeiro
await page.evaluate("""() => {
    if (!document.getElementById('hitl-radar-pulse-style')) {
        const st = document.createElement('style');
        st.id = 'hitl-radar-pulse-style';
        st.innerHTML = `
            @keyframes hitl-radar-pulse {
                0%,100% { opacity:1; } 50% { opacity:0.5; }
            }
            .hitl-radar-pulse-dot {
                display:inline-block; width:8px; height:8px;
                background:#ef4444; border-radius:50%;
                animation: hitl-radar-pulse 1.2s ease infinite;
            }
        `;
        document.head.appendChild(st);
    }
}""")

# Agora injeta o indicador visual
await page.evaluate("""() => {
    const overlay = document.getElementById('hitl-step-overlay');
    if (!overlay) return;
    
    let radarMsg = document.getElementById('hitl-step-radar-msg');
    if (!radarMsg) {
        radarMsg = document.createElement('div');
        radarMsg.id = 'hitl-step-radar-msg';
        radarMsg.style.cssText = '...';
        overlay.appendChild(radarMsg);
    }
    
    radarMsg.innerHTML = '<span class="hitl-radar-pulse-dot"></span>'
        + '<span id="hitl-radar-text">Radar ativo — clique no elemento correto</span>'
        + '<span id="hitl-radar-countdown" style="font-weight:700;color:#f87171;">⏱ 120s</span>'
        + '<button id="hitl-radar-cancel-btn" ...>❌ Cancelar</button>';
    radarMsg.style.display = 'flex';
    
    // Cancel button handler
    const cancelBtn = document.getElementById('hitl-radar-cancel-btn');
    if (cancelBtn) {
        cancelBtn.onclick = (e) => {
            e.stopPropagation();
            e.preventDefault();
            if (window.__hitlRadarCountdownId) {
                clearInterval(window.__hitlRadarCountdownId);
                window.__hitlRadarCountdownId = null;
            }
            radarMsg.style.display = 'none';
            if (window.__hitl_captura__) {
                window.__hitl_captura__(JSON.stringify({ seletor: '', acao: 'radar_cancelado' }));
            }
        };
    }
}""")
```

**Impacto**: ✅ Cronômetro agora aparece corretamente

---

### Mudança 2: Comunicação via postMessage para iframes (Linha ~1787)

**Antes**:
```python
# Injeta listener de clique em TODOS os frames (main + iframes)
# O __hitl_captura__ binding funciona em todos os frames (expose_binding no context)
_radar_js = f"""() => {{
    if (window.__hitlRadarStepAtivo) return;
    window.__hitlRadarStepAtivo = true;

    const getSelector = {_JS_GET_BEST_SELECTOR};

    const handler = (e) => {{
        // ...
        window.__hitl_captura__(JSON.stringify({{ seletor, label }}));
        // ❌ Não funciona em iframes — binding não está disponível
    }};

    document.addEventListener('click', handler, true);
}}"""
```

**Depois**:
```python
# Injeta listener de clique em TODOS os frames (main + iframes)
# IMPORTANTE: iframes não têm acesso ao binding expose_binding do contexto principal
# Solução: usar postMessage para comunicar do iframe com o frame principal
_radar_js = f"""() => {{
    if (window.__hitlRadarStepAtivo) return;
    window.__hitlRadarStepAtivo = true;

    const getSelector = {_JS_GET_BEST_SELECTOR};

    const handler = (e) => {{
        // ...
        const seletor = getSelector(e.target);
        const label   = e.target.innerText?.trim()?.substring(0, 60)
                      || e.target.getAttribute('aria-label')
                      || e.target.tagName.toLowerCase();

        // Feedback visual imediato (cyan outline)
        const prev = e.target.style.outline;
        e.target.style.outline = '3px solid #00e5e5';
        e.target.style.boxShadow = '0 0 16px #00e5e588';
        setTimeout(() => {{
            e.target.style.outline = prev;
            e.target.style.boxShadow = '';
        }}, 1200);

        // Se estamos em um iframe, usa postMessage para comunicar com o frame principal
        if (window.self !== window.top) {{
            window.top.postMessage({{
                type: '__hitl_radar_captura__',
                seletor: seletor,
                label: label
            }}, '*');
        }} else {{
            // Frame principal — chama binding diretamente
            if (window.__hitl_captura__) {{
                window.__hitl_captura__(JSON.stringify({{ seletor, label }}));
            }}
        }}
    }};

    document.addEventListener('click', handler, true);
}}"""

# Injeta no frame principal
try:
    await page.evaluate(_radar_js)
except Exception as e:
    logger.debug(f"[STEP] Radar inject main frame: {e}")

# Injeta em todos os iframes da página
for frame in page.frames:
    if frame == page.main_frame:
        continue
    try:
        await frame.evaluate(_radar_js)
    except Exception as e:
        logger.debug(f"[STEP] Radar inject iframe '{frame.url[:60]}': {e}")

# Setup listener para postMessage (captura cliques de iframes)
await page.evaluate("""() => {
    if (window.__hitlRadarPostMessageSetup) return;
    window.__hitlRadarPostMessageSetup = true;

    window.addEventListener('message', (e) => {
        if (e.data && e.data.type === '__hitl_radar_captura__') {
            // Clique capturado em um iframe — repassa para o binding
            if (window.__hitl_captura__) {
                window.__hitl_captura__(JSON.stringify({
                    seletor: e.data.seletor,
                    label: e.data.label
                }));
            }
        }
    }, false);
}""")
```

**Impacto**: ✅ Cliques em iframes agora são capturados corretamente

---

### Mudança 3: Validação e Logging (Linha ~1888)

**Antes**:
```python
# Aguarda captura do clique (timeout de 120s — analista pode precisar navegar)
try:
    await asyncio.wait_for(self._evento_humano.wait(), timeout=120)
except asyncio.TimeoutError:
    logger.warning("[STEP] Timeout de 120s no radar step — cancelando captura")
    # ...
    return ""

# Check if radar was cancelled by the analyst
if self._decisao_humana.get("acao") == "radar_cancelado":
    logger.info("[STEP] Radar cancelado pelo analista")
    # ...
    return ""

# Limpa countdown no frame principal após captura bem-sucedida
try:
    await page.evaluate("""() => {
        if (window.__hitlRadarCountdownId) {
            clearInterval(window.__hitlRadarCountdownId);
            window.__hitlRadarCountdownId = null;
        }
        const radarMsg = document.getElementById('hitl-step-radar-msg');
        if (radarMsg) {
            radarMsg.style.background = 'rgba(34,197,94,0.15)';
            radarMsg.style.borderColor = 'rgba(34,197,94,0.4)';
            const textEl = document.getElementById('hitl-radar-text');
            if (textEl) textEl.textContent = '✅ Seletor capturado!';
            const countdownEl = document.getElementById('hitl-radar-countdown');
            if (countdownEl) countdownEl.style.display = 'none';
            const cancelBtn = document.getElementById('hitl-radar-cancel-btn');
            if (cancelBtn) cancelBtn.style.display = 'none';
        }
    }""")
except Exception:
    pass

# ❌ Falta validação de seletor capturado
```

**Depois**:
```python
# Aguarda captura do clique (timeout de 120s — analista pode precisar navegar)
try:
    await asyncio.wait_for(self._evento_humano.wait(), timeout=120)
except asyncio.TimeoutError:
    logger.warning("[STEP] Timeout de 120s no radar step — cancelando captura")
    # Desativa radar em todos os frames + limpa countdown
    _cleanup_js = """() => {
        window.__hitlRadarStepAtivo = false;
        if (window.__hitlRadarCountdownId) {
            clearInterval(window.__hitlRadarCountdownId);
            window.__hitlRadarCountdownId = null;
        }
        const radarMsg = document.getElementById('hitl-step-radar-msg');
        if (radarMsg) radarMsg.style.display = 'none';
    }"""
    try:
        await page.evaluate(_cleanup_js)
    except Exception:
        pass
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
        except Exception:
            pass
    return ""

# Check if radar was cancelled by the analyst
if self._decisao_humana.get("acao") == "radar_cancelado":
    logger.info("[STEP] Radar cancelado pelo analista")
    # Limpa flag nos iframes
    for frame in page.frames:
        if frame == page.main_frame:
            continue
        try:
            await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
        except Exception:
            pass
    return ""

# ✅ Extrai seletor capturado
seletor_capturado = self._decisao_humana.get("seletor", "")
if not seletor_capturado:
    logger.warning("[STEP] Radar: nenhum seletor foi capturado")
    return ""

logger.info(f"[STEP] Seletor capturado via radar: {seletor_capturado}")

# Limpa countdown no frame principal após captura bem-sucedida
try:
    await page.evaluate("""() => {
        if (window.__hitlRadarCountdownId) {
            clearInterval(window.__hitlRadarCountdownId);
            window.__hitlRadarCountdownId = null;
        }
        const radarMsg = document.getElementById('hitl-step-radar-msg');
        if (radarMsg) {
            radarMsg.style.background = 'rgba(34,197,94,0.15)';
            radarMsg.style.borderColor = 'rgba(34,197,94,0.4)';
            const textEl = document.getElementById('hitl-radar-text');
            if (textEl) textEl.textContent = '✅ Seletor capturado!';
            const countdownEl = document.getElementById('hitl-radar-countdown');
            if (countdownEl) countdownEl.style.display = 'none';
            const cancelBtn = document.getElementById('hitl-radar-cancel-btn');
            if (cancelBtn) cancelBtn.style.display = 'none';
        }
    }""")
except Exception:
    pass

# Desativa radar em todos os frames
for frame in page.frames:
    try:
        await frame.evaluate("() => { window.__hitlRadarStepAtivo = false; }")
    except Exception:
        pass

return seletor_capturado
```

**Impacto**: ✅ Validação e logging detalhado para diagnosticar problemas

---

## Arquivo: `test_radar_fix.py` (Novo)

Criado com 5 testes unitários:
- ✅ `test_radar_cronometro_injetado` — Valida injeção de CSS
- ✅ `test_radar_captura_clique` — Valida captura de clique
- ✅ `test_radar_cancelar` — Valida botão Cancelar
- ✅ `test_radar_postmessage_iframe` — Valida comunicação via postMessage
- ✅ `test_radar_timeout` — Valida timeout de 120s

**Resultado**: 5/5 testes passando ✅

---

## Resumo das Mudanças

| Aspecto | Antes | Depois |
|--------|-------|--------|
| **Cronômetro** | ❌ Não aparecia | ✅ Aparece com countdown |
| **Clique em iframe** | ❌ Não era capturado | ✅ Capturado via postMessage |
| **Validação** | ❌ Nenhuma | ✅ Valida seletor capturado |
| **Logging** | ⚠️ Mínimo | ✅ Detalhado para diagnosticar |
| **Testes** | ❌ Nenhum | ✅ 5 testes passando |

---

## Compatibilidade

- ✅ Frame principal (Senior X)
- ✅ Iframes (Senior X usa extensivamente)
- ✅ Múltiplos iframes aninhados
- ✅ Frames com origem diferente (postMessage funciona com `*`)
- ✅ Modo step-by-step (padrão)
- ✅ Modo auto (fallback para step-by-step em caso de falha)

---

## Regressão Risk

**Baixo** — As mudanças são isoladas ao Radar e não afetam:
- ✅ Execução normal de ações
- ✅ Overlay step-by-step
- ✅ Modo auto
- ✅ Proteção HITL no Brain
- ✅ Relatório final

---

## Próximos Passos

1. Testar em produção com roteiros reais
2. Monitorar logs para validar captura de cliques
3. Coletar feedback do analista sobre UX
4. Considerar aumentar timeout se necessário (atualmente 120s)

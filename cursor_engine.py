"""
cursor_engine.py — Motor de Cursor Humanizado com Bézier Cúbica e Néon (Revisão Cinematic)

Correcoes aplicadas:

  [BUG-1] CRITICO — obter_coords_acao usa chaves erradas e nivel errado do dict
    ANTES: acao_tec.get("seletor_css") or acao_tec.get("seletor")
    A estrutura real do sistema armazena o seletor em:
        acao_tec["elemento_alvo"]["seletor_hint"]
    Com as chaves erradas, a funcao SEMPRE retornava None. O cursor nunca se
    posicionava via DOM — caía sempre no fallback de coordenadas relativas.
    AGORA: acessa acao_tec["elemento_alvo"]["seletor_hint"] corretamente.

  [BUG-2] MÉDIO — add_style_tag em instalar_cursor nao sobrevive a navegacao
    ANTES: page.add_style_tag(content="* { cursor: none !important; }...")
    add_style_tag injeta no DOM da pagina ATUAL. Numa SPA com navegacao
    interna (ex: Senior X Angular), a tag some apos cada rota.
    add_init_script (ja usado na linha anterior) JA injeta o mesmo estilo
    via CURSOR_INIT_SCRIPT em toda navegacao — a chamada era redundante e
    gerava inconsistencias ao aplicar o estilo duas vezes no carregamento inicial.
    AGORA: add_style_tag removido; init_script e a unica fonte de veride.

  [BUG-3] BAIXO — garantir_cursor_visivel: page.evaluate recebe IIFE corretamente
    Sem alteracao de comportamento; adicionado comentario explicativo para
    deixar claro que IIFE e valida dentro de page.evaluate().
"""

import asyncio
import math
import random
import logging
from typing import Optional

# ══════════════════════════════════════════════════════════
# CONSTANTES DE ANIMACAO
# ══════════════════════════════════════════════════════════
DURACAO_BASE_MS  = 1200
DURACAO_MIN_MS   = 500
DURACAO_MAX_MS   = 2500
JITTER_PIXELS    = 2.0
OVERSHOOT_CHANCE = 0.15
OVERSHOOT_PX     = 5.0
DESVIO_MIN_RATIO = 0.05
DESVIO_MAX_RATIO = 0.15
PASSOS_POR_PIXEL = 0.06
PASSOS_MIN       = 20
PASSOS_MAX       = 90

# ══════════════════════════════════════════════════════════
# CURSOR DOM (NEON FANTASMA)
# ══════════════════════════════════════════════════════════
CURSOR_INIT_SCRIPT = """
(function() {
    if (document.getElementById('robo-cursor')) return;

    // Esconde o cursor nativo em tudo
    const style = document.createElement('style');
    style.innerHTML = '* { cursor: none !important; } html, body { cursor: none !important; }';
    document.head.appendChild(style);

    const cursor = document.createElement('div');
    cursor.id = 'robo-cursor';
    Object.assign(cursor.style, {
        position: 'fixed', width: '24px', height: '24px',
        borderRadius: '50%', backgroundColor: 'rgba(0, 229, 229, 0.4)',
        border: '2px solid #00e5e5', pointerEvents: 'none',
        zIndex: '2147483647', transform: 'translate(-50%, -50%)',
        transition: 'top 0.1s ease-out, left 0.1s ease-out, opacity 0.4s ease',
        boxShadow: '0 0 15px rgba(0, 229, 229, 0.8), 0 0 30px rgba(0, 229, 229, 0.4)',
        left: window.innerWidth / 2 + 'px', top: window.innerHeight / 2 + 'px',
        opacity: '0'
    });

    const dot = document.createElement('div');
    Object.assign(dot.style, {
        position: 'absolute', width: '6px', height: '6px',
        borderRadius: '50%', background: '#ffffff',
        top: '50%', left: '50%', transform: 'translate(-50%,-50%)',
        boxShadow: '0 0 10px #ffffff'
    });
    cursor.appendChild(dot);
    document.documentElement.appendChild(cursor);

    window._cursorX = window.innerWidth / 2;
    window._cursorY = window.innerHeight / 2;

    window.addEventListener('mousemove', (e) => {
        window._cursorX = e.clientX;
        window._cursorY = e.clientY;
        cursor.style.left = e.clientX + 'px';
        cursor.style.top  = e.clientY + 'px';
    }, { passive: true });

    window.addEventListener('mousedown', () => {
        cursor.style.transform = 'translate(-50%, -50%) scale(0.6)';
        cursor.style.backgroundColor = 'rgba(0, 229, 229, 0.9)';

        const ripple = document.createElement('div');
        Object.assign(ripple.style, {
            position: 'fixed', left: window._cursorX + 'px', top: window._cursorY + 'px',
            width: '20px', height: '20px', borderRadius: '50%',
            border: '2px solid #00e5e5', transform: 'translate(-50%, -50%) scale(1)',
            pointerEvents: 'none', zIndex: '2147483646',
            transition: 'transform 0.4s ease-out, opacity 0.4s ease-out'
        });
        document.documentElement.appendChild(ripple);
        requestAnimationFrame(() => {
            ripple.style.transform = 'translate(-50%, -50%) scale(4)';
            ripple.style.opacity = '0';
        });
        setTimeout(() => ripple.remove(), 400);
        setTimeout(() => {
            cursor.style.transform = 'translate(-50%, -50%) scale(1)';
            cursor.style.backgroundColor = 'rgba(0, 229, 229, 0.4)';
        }, 150);
    }, { passive: true });

    // Virus benigno: garante que iframes novos nao mostrem o cursor nativo
    setInterval(() => {
        document.querySelectorAll('iframe').forEach(ifr => {
            try {
                let d = ifr.contentDocument;
                if (d && !d.getElementById('hide-cursor-style')) {
                    let s = d.createElement('style');
                    s.id = 'hide-cursor-style';
                    s.innerHTML = '* { cursor: none !important; }';
                    d.head.appendChild(s);
                }
            } catch(e) {}
        });
    }, 1000);
})();
"""


async def instalar_cursor(page) -> bool:
    """
    Registra o cursor humanizado para ser injetado em toda nova navegacao.
    add_init_script garante sobrevivencia a navegacoes SPA — nao usar add_style_tag.
    """
    try:
        await page.add_init_script(CURSOR_INIT_SCRIPT)
        # [BUG-2] FIX: removido add_style_tag — init_script ja injeta o estilo
        # e sobrevive a toda navegacao. add_style_tag era redundante e nao persistia.
        return True
    except Exception as e:
        logging.warning(f"Cursor: falha ao instalar: {e}")
        return False


async def garantir_cursor_visivel(page) -> None:
    """
    Reinjecao pontual do cursor caso tenha sumido (ex: hard reload de iframe).
    page.evaluate() aceita IIFE diretamente — comportamento identico ao init_script.
    """
    try:
        existe = await page.evaluate("() => !!document.getElementById('robo-cursor')")
        if not existe:
            await page.evaluate(CURSOR_INIT_SCRIPT)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════
# MATEMATICA BEZIER
# ══════════════════════════════════════════════════════════
def _ease_cubic_inout(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - ((-2 * t + 2) ** 3) / 2


def _ease_quart_out(t: float) -> float:
    return 1 - (1 - t) ** 4


def _bezier_cubica(
    t: float,
    p0x: float, p0y: float,
    p1x: float, p1y: float,
    p2x: float, p2y: float,
    p3x: float, p3y: float,
) -> tuple[float, float]:
    mt = 1 - t
    x  = mt**3 * p0x + 3 * mt**2 * t * p1x + 3 * mt * t**2 * p2x + t**3 * p3x
    y  = mt**3 * p0y + 3 * mt**2 * t * p1y + 3 * mt * t**2 * p2y + t**3 * p3y
    return x, y


def _gerar_pontos_controle(
    x0: float, y0: float, x3: float, y3: float
) -> tuple[float, float, float, float]:
    dx, dy    = x3 - x0, y3 - y0
    distancia = math.hypot(dx, dy)
    if distancia < 1:
        return x0, y0, x3, y3
    nx, ny       = -dy / distancia, dx / distancia
    desvio_ratio = random.uniform(DESVIO_MIN_RATIO, DESVIO_MAX_RATIO)
    desvio       = distancia * desvio_ratio * random.choice([-1, 1])
    j = lambda: random.uniform(-JITTER_PIXELS, JITTER_PIXELS)
    t1   = random.uniform(0.25, 0.40)
    cp1x = x0 + dx * t1 + nx * desvio + j()
    cp1y = y0 + dy * t1 + ny * desvio + j()
    t2   = random.uniform(0.60, 0.75)
    cp2x = x0 + dx * t2 - nx * desvio * 0.4 + j()
    cp2y = y0 + dy * t2 - ny * desvio * 0.4 + j()
    return cp1x, cp1y, cp2x, cp2y


async def mover_cursor_humanizado(
    page, x_fim: float, y_fim: float, duracao_ms: Optional[int] = None
) -> None:
    try:
        pos = await page.evaluate(
            "() => ({ x: window._cursorX ?? window.innerWidth/2, y: window._cursorY ?? window.innerHeight/2 })"
        )
        x_ini, y_ini = float(pos["x"]), float(pos["y"])
    except Exception:
        x_ini, y_ini = 0.0, 0.0

    distancia = math.hypot(x_fim - x_ini, y_fim - y_ini)
    if distancia < 3:
        return

    if duracao_ms is None:
        base       = DURACAO_BASE_MS * (distancia / 400) ** 0.55
        duracao_ms = int(max(DURACAO_MIN_MS, min(DURACAO_MAX_MS, base)))
        duracao_ms = int(duracao_ms * random.uniform(0.92, 1.08))

    cp1x, cp1y, cp2x, cp2y = _gerar_pontos_controle(x_ini, y_ini, x_fim, y_fim)

    x_alvo_final, y_alvo_final = x_fim, y_fim
    if random.random() < OVERSHOOT_CHANCE and distancia > 60:
        dx, dy = x_fim - x_ini, y_fim - y_ini
        norm   = math.hypot(dx, dy)
        over   = random.uniform(3, OVERSHOOT_PX)
        x_alvo_final = x_fim + (dx / norm) * over
        y_alvo_final = y_fim + (dy / norm) * over

    passos      = int(max(PASSOS_MIN, min(PASSOS_MAX, distancia * PASSOS_POR_PIXEL)))
    intervalo_s = (duracao_ms / 1000) / passos

    for i in range(passos + 1):
        t     = i / passos
        ease  = _ease_cubic_inout(t)
        px, py = _bezier_cubica(ease, x_ini, y_ini, cp1x, cp1y, cp2x, cp2y, x_alvo_final, y_alvo_final)
        await page.mouse.move(px, py)
        fator_pausa = 0.6 + 0.8 * abs(math.sin(math.pi * t))
        await asyncio.sleep(intervalo_s * fator_pausa)

    if (x_alvo_final, y_alvo_final) != (x_fim, y_fim):
        passos_corr, intervalo_corr = 8, 0.018
        ox, oy = x_alvo_final, y_alvo_final
        for i in range(1, passos_corr + 1):
            ex = _ease_quart_out(i / passos_corr)
            await page.mouse.move(ox + (x_fim - ox) * ex, oy + (y_fim - oy) * ex)
            await asyncio.sleep(intervalo_corr)

    try:
        await page.evaluate(f"() => {{ window._cursorX = {x_fim}; window._cursorY = {y_fim}; }}")
    except Exception:
        pass


async def obter_coords_acao(page, acao_tec: dict) -> Optional[dict]:
    """
    Resolve as coordenadas de tela do elemento-alvo de uma acao tecnica
    usando o seletor armazenado, para que o cursor se mova antes do clique.

    [BUG-1] FIX: A estrutura de acao_tec e:
        {
            "acao": "clique",
            "elemento_alvo": {
                "seletor_hint": "[aria-label='Salvar']",  ← chave correta
                ...
            }
        }
    O codigo original buscava acao_tec.get("seletor_css") / acao_tec.get("seletor")
    — chaves que nao existem nessa estrutura — e retornava None sempre.
    """
    # [BUG-1] FIX: busca no nivel e chave corretos
    alvo    = acao_tec.get("elemento_alvo", {})
    seletor = alvo.get("seletor_hint") or alvo.get("seletor_css") or alvo.get("seletor")

    if not seletor or seletor == "body":
        return None

    async def _bbox_centro(locator):
        try:
            if await locator.is_visible(timeout=1500):
                box = await locator.bounding_box()
                if box:
                    return {
                        "x": box["x"] + box["width"] / 2,
                        "y": box["y"] + box["height"] / 2,
                    }
        except Exception:
            pass
        return None

    # Tenta na pagina principal primeiro
    coords = await _bbox_centro(page.locator(seletor).first)
    if coords:
        return coords

    # Fallback: varre todos os frames
    for frame in page.frames:
        coords = await _bbox_centro(frame.locator(seletor).first)
        if coords:
            return coords

    return None

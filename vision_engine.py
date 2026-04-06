"""
vision_engine.py — Motor de localização e execução de ações no browser.

Filosofia: cascata de estratégias do mais barato ao mais caro.
Cada camada só é acionada se a anterior falhar completamente.

Camadas de Resiliência:
  0  Brain (Memória SQLite Permanente - Auto-Cura e Zero-Touch)
  1  Foco nativo / active element (campos de digitação inline e novas pastas)
  1.5 Heurísticas Senior X (Ícones mudos como Home, Lixeira, etc)
  2  Sniper semântico — 15+ seletores Playwright nativos (getByRole, getByLabel…)
  3  Seletor hint original (se não for frágil)
  4  Busca em todos os frames da página (sem depender do hint de iframe)
  5  Gemini Vision — screenshot atual + referência da gravação
  6  Coordenadas relativas da gravação (corrigidas por scroll)

Correcoes aplicadas:

  [BUG-1] ALTO — gemini_client sem guard de chave ausente
    ANTES: genai.Client(api_key=os.getenv("GOOGLE_API_KEY")) no nivel do modulo
    → crash com AttributeError confuso se chave ausente.
    AGORA: guard + warning; Vision retorna None graciosamente sem chave.

  [BUG-2] ALTO — Brain salva cand.descricao como seletor quando cand.seletor=""
    ANTES: _registrar_sucesso_cache(intencao, seletor=cand.seletor or cand.descricao, ...)
    Quando cand.seletor="" (candidatos get_by_role/label/placeholder/title), Python
    avalia "" como falsy e passa cand.descricao — ex: "role=button name='Salvar'".
    O filtro interno (_registrar_sucesso_cache) descarta por nao comecar com [/#/text=,
    entao o Brain NUNCA aprende nada via Sniper para esses candidatos.
    AGORA: passa seletor=cand.seletor or None (sem fallback pra descricao).

  [BUG-3] ALTO — Double _registrar_falha_cache quando Brain seletor falha
    ANTES: quando cache.seletor existe e _tentar_candidato falha, a funcao chama
    _registrar_falha_cache() no bloco do Brain (+1 imediato) E depois chama
    novamente no final do orquestrador se TODAS as camadas falharam (+1 final).
    Total: 2 falhas no mesmo ciclo → self-healing apaga memorias validas 2x mais rapido.
    AGORA: flag brain_falhou controla o registro duplo; apenas uma falha e contada.

  [BUG-4] MÉDIO — _init_db() chamado no nivel do modulo sem try/except
    ANTES: crash na importacao se o diretorio corrente nao tiver permissao de escrita.
    AGORA: _init_db() com try/except; erro logado, modulo importa normalmente.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from playwright.async_api import Page

load_dotenv()

logger = logging.getLogger(__name__)

# [BUG-1] FIX: guard de chave ausente
_g_key = os.getenv("GOOGLE_API_KEY")
gemini_client = genai.Client(api_key=_g_key) if _g_key else None
if not gemini_client:
    logger.warning("GOOGLE_API_KEY ausente. Gemini Vision desativado (fallback: coordenadas).")

# ──────────────────────────────────────────────────────────────
# BRAIN - MEMORIA DE LONGO PRAZO (SQLITE)
# ──────────────────────────────────────────────────────────────
DB_PATH          = "brain.db"
MAX_FALHAS_CACHE = 3


def _init_db():
    """Inicializa o banco de dados SQLite. Erro de permissao e logado, nao propagado."""
    # [BUG-4] FIX: try/except para nao crashar na importacao
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memoria_semantica (
                    hash_intencao TEXT PRIMARY KEY,
                    intencao TEXT,
                    seletor TEXT,
                    coords TEXT,
                    iframe TEXT,
                    hits INTEGER DEFAULT 0,
                    falhas_consecutivas INTEGER DEFAULT 0,
                    hitl_corrigido INTEGER DEFAULT 0,
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Migração segura: adiciona colunas novas se não existirem (idempotente)
            for col_sql in [
                "ALTER TABLE memoria_semantica ADD COLUMN hitl_corrigido INTEGER DEFAULT 0",
            ]:
                try:
                    conn.execute(col_sql)
                except Exception:
                    pass  # coluna já existe

            # Tabela de telemetria de camadas (Fase 2.2)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetria_camadas (
                    camada TEXT PRIMARY KEY,
                    acertos INTEGER DEFAULT 0,
                    falhas INTEGER DEFAULT 0,
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # TTL: remove memórias não usadas há mais de 90 dias (Fase 2.1)
            conn.execute("""
                DELETE FROM memoria_semantica
                WHERE ultima_atualizacao < datetime('now', '-90 days')
                  AND hits < 2
            """)
    except Exception as e:
        logger.error(f"Nao foi possivel inicializar Brain DB em '{DB_PATH}': {e}")


_init_db()


def _chave_cache(intencao: str) -> str:
    return hashlib.md5(intencao.strip().lower().encode()).hexdigest()[:16]


@dataclass
class EntradaCache:
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    hits: int = 0
    falhas_consecutivas: int = 0
    hitl_corrigido: int = 0


def _registrar_telemetria(camada: str, acertou: bool) -> None:
    """Registra acerto/falha por camada para observabilidade do self-healing."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                INSERT INTO telemetria_camadas (camada, acertos, falhas)
                VALUES (?, ?, ?)
                ON CONFLICT(camada) DO UPDATE SET
                    acertos = acertos + ?,
                    falhas  = falhas  + ?,
                    ultima_atualizacao = CURRENT_TIMESTAMP
            """, (
                camada,
                1 if acertou else 0,
                0 if acertou else 1,
                1 if acertou else 0,
                0 if acertou else 1,
            ))
    except Exception:
        pass


def obter_stats_brain() -> dict:
    """Retorna estatísticas do Brain para o endpoint /api/brain-stats."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) as n FROM memoria_semantica").fetchone()["n"]
            hitl  = conn.execute("SELECT COUNT(*) as n FROM memoria_semantica WHERE hitl_corrigido = 1").fetchone()["n"]
            camadas = conn.execute(
                "SELECT camada, acertos, falhas FROM telemetria_camadas ORDER BY acertos DESC"
            ).fetchall()
            return {
                "total_memorias": total,
                "memorias_hitl": hitl,
                "camadas": [dict(r) for r in camadas],
            }
    except Exception as e:
        return {"erro": str(e)}


def _consultar_cache(intencao: str) -> Optional[EntradaCache]:
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM memoria_semantica WHERE hash_intencao = ?", (chave,)
            ).fetchone()

            if row:
                if row["falhas_consecutivas"] >= MAX_FALHAS_CACHE:
                    logger.debug(f"   [Brain] Memoria obsoleta apagada: '{intencao[:40]}'")
                    conn.execute("DELETE FROM memoria_semantica WHERE hash_intencao = ?", (chave,))
                    return None

                logger.info(f"   [Brain] Memoria ativada para: '{intencao[:50]}'")
                return EntradaCache(
                    seletor=row["seletor"],
                    coords=json.loads(row["coords"]) if row["coords"] else None,
                    iframe_src=row["iframe"],
                    hits=row["hits"],
                    falhas_consecutivas=row["falhas_consecutivas"],
                )
    except Exception as e:
        logger.error(f"Erro ao ler Brain DB: {e}")
    return None


def _registrar_sucesso_cache(
    intencao: str,
    seletor: Optional[str] = None,
    coords: Optional[dict] = None,
    iframe: Optional[str] = None,
):
    chave      = _chave_cache(intencao)
    coords_str = json.dumps(coords) if coords else None

    # Descarta seletores muito vagos — aceita prefixos Angular/PrimeNG e :has-text(
    _PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")
    if seletor and not seletor.startswith(_PREFIXOS_VALIDOS) and ":has-text(" not in seletor:
        seletor = None

    try:
        with sqlite3.connect(DB_PATH) as conn:
            existente = conn.execute(
                "SELECT hits FROM memoria_semantica WHERE hash_intencao = ?", (chave,)
            ).fetchone()

            if existente:
                query  = "UPDATE memoria_semantica SET hits = hits + 1, falhas_consecutivas = 0, ultima_atualizacao = CURRENT_TIMESTAMP"
                params: list = []
                if seletor:
                    query += ", seletor = ?"; params.append(seletor)
                if coords_str:
                    query += ", coords = ?"; params.append(coords_str)
                if iframe:
                    query += ", iframe = ?"; params.append(iframe)
                query += " WHERE hash_intencao = ?"; params.append(chave)
                conn.execute(query, params)
            else:
                conn.execute("""
                    INSERT INTO memoria_semantica
                        (hash_intencao, intencao, seletor, coords, iframe, hits, falhas_consecutivas)
                    VALUES (?, ?, ?, ?, ?, 1, 0)
                """, (chave, intencao, seletor, coords_str, iframe))
    except Exception as e:
        logger.error(f"Erro ao salvar no Brain DB: {e}")


def _registrar_falha_cache(intencao: str):
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "UPDATE memoria_semantica SET falhas_consecutivas = falhas_consecutivas + 1 WHERE hash_intencao = ?",
                (chave,),
            )
    except Exception:
        pass


# ──────────────────────────────────────────────────────────────
# ESTRUTURAS DE CANDIDATOS (SNIPER)
# ──────────────────────────────────────────────────────────────
@dataclass
class TentativaLocalizacao:
    seletor: str
    iframe_hint: Optional[str] = None
    exact: bool = False
    via_pierce: bool = False
    role: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    title: Optional[str] = None
    descricao: str = ""


# ──────────────────────────────────────────────────────────────
# ANALISE DE SELETORES E ATRIBUTOS
# ──────────────────────────────────────────────────────────────
_TAGS_FRAGEIS = {
    "h1", "h2", "h3", "h4", "span", "div", "em", "p", "li",
    "ul", "a", "button", "input", "section", "article", "td", "tr", "svg", "i", "path",
}


def _e_seletor_fragil(seletor: str) -> bool:
    if not seletor:
        return True
    for prefixo in ("text=", "has-text", "[aria-label=", "[data-testid=", "[id=", "[name=", "[placeholder=", "[role="):
        if prefixo in seletor:
            return False
    tag = seletor.strip().split(":")[0].split("[")[0].split(".")[0].split(">")[0].strip()
    return tag in _TAGS_FRAGEIS


def _contem_indice_posicional(seletor: str) -> bool:
    """
    Detecta se um seletor CSS contém índice posicional instável.

    Padrões detectados:
      - #\\w*\\d+          ex: #file_1, #row3, #item_42
      - :nth-child(\\d+)   ex: tr:nth-child(2)
      - :nth-of-type(\\d+) ex: li:nth-of-type(3)
      - item#\\w+\\d+      ex: item#file_1

    ATENÇÃO: [data-testid='item-102'] NÃO é posicional — o número está dentro
    de aspas como valor de atributo. O lookahead (?![^'\"]*['\"]) garante que
    o padrão #\\w*\\d+ não dispare dentro de valores de atributos.
    """
    if not seletor:
        return False
    padroes = [
        r"#\w*\d+(?![^'\"]*['\"])",   # #file_1, #row3 — mas não dentro de ['...']
        r":nth-child\(\d+\)",
        r":nth-of-type\(\d+\)",
        r"item#\w+\d+",
    ]
    return any(re.search(p, seletor) for p in padroes)


async def _verificar_identidade_elemento(locator, label_curto: str) -> bool:
    """
    Verifica se o elemento (ou seu pai imediato) contém o texto do label_curto.

    Estratégia:
      1. Tenta inner_text() do próprio elemento.
      2. Se não bater, tenta inner_text() do elemento pai ("..").
      3. Retorna True se qualquer um contiver label_curto (case-insensitive, strip).
      4. Retorna True em caso de exceção APENAS se nenhum texto foi lido com sucesso
         (fail-open — não bloquear quando texto não é acessível, ex: checkboxes sem
         texto visível). Se o texto foi lido mas não bate, retorna False.
    """
    if not label_curto:
        return True
    needle = label_curto.strip().lower()
    texto_lido = False

    try:
        texto = await locator.inner_text(timeout=1000)
        texto_lido = True
        if needle in texto.strip().lower():
            return True
    except Exception:
        return True  # fail-open: não conseguiu ler texto, não bloquear

    # Texto foi lido mas não bateu — tenta o pai
    try:
        texto_pai = await locator.locator("..").inner_text(timeout=1000)
        texto_lido = True
        if needle in texto_pai.strip().lower():
            return True
    except Exception:
        # Pai inacessível — se o elemento principal foi lido e não bateu, retorna False
        if texto_lido:
            return False
        return True  # fail-open

    return False


def _extrair_atributo(seletor: str, atributo: str) -> Optional[str]:
    # FIX Bug #VIS-01: O primeiro regex tinha character class [\'\",]+
    # que incluía vírgula e aspas como caracteres válidos DENTRO do valor —
    # capturava lixo como 'aria-label="Salvar,"' com a vírgula incluída,
    # gerando seletores quebrados. Mantido apenas o regex correto.
    match = re.search(rf"{atributo}=['\"]([^'\"]+)['\"]", seletor)
    return match.group(1) if match else None


# ──────────────────────────────────────────────────────────────
# GERACAO DE CANDIDATOS (SNIPER)
# ──────────────────────────────────────────────────────────────
def _gerar_candidatos(
    seletor_hint: str, label_curto: str, iframe_hint: Optional[str],
    acao: str, tipo_elemento: str, html_hint: str,
) -> list[TentativaLocalizacao]:
    candidatos: list[TentativaLocalizacao] = []
    eh_digitacao    = acao in ("digitar_e_enter", "preencher_campo")
    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS

    if label_curto and not is_tag_generica:
        if not eh_digitacao:
            candidatos.append(TentativaLocalizacao(
                seletor=f'text="{label_curto}"', iframe_hint=iframe_hint,
                exact=True, descricao=f"texto exato '{label_curto}'",
            ))

        role_map = {"button": "button", "link": "link", "menu_item": "menuitem",
                    "checkbox": "checkbox", "tab": "tab", "input": "textbox"}
        role = role_map.get(tipo_elemento)
        if role:
            candidatos.append(TentativaLocalizacao(
                seletor="", role=role, label=label_curto,
                iframe_hint=iframe_hint, descricao=f"role={role} name='{label_curto}'",
            ))

        if eh_digitacao or tipo_elemento in ("input",):
            candidatos.append(TentativaLocalizacao(
                seletor="", label=label_curto, iframe_hint=iframe_hint,
                descricao=f"label '{label_curto}'",
            ))

        candidatos.append(TentativaLocalizacao(
            seletor=f"[aria-label='{label_curto}']", iframe_hint=iframe_hint,
            descricao=f"aria-label='{label_curto}'",
        ))
        if label_curto != label_curto.lower():
            candidatos.append(TentativaLocalizacao(
                seletor=f"[aria-label='{label_curto.lower()}']",
                iframe_hint=iframe_hint, descricao="aria-label lowercase",
            ))

    aria_hint = _extrair_atributo(seletor_hint, "aria-label")
    if aria_hint and aria_hint != label_curto:
        candidatos.append(TentativaLocalizacao(
            seletor=f"[aria-label='{aria_hint}']", iframe_hint=iframe_hint,
            descricao=f"aria-label do hint '{aria_hint}'",
        ))

    testid = _extrair_atributo(seletor_hint, "data-testid")
    if testid:
        candidatos.append(TentativaLocalizacao(
            seletor=f"[data-testid='{testid}']", iframe_hint=iframe_hint,
            descricao=f"data-testid='{testid}'",
        ))
        variante = testid.replace("-", "_") if "-" in testid else testid.replace("_", "-")
        candidatos.append(TentativaLocalizacao(
            seletor=f"[data-testid='{variante}']", iframe_hint=iframe_hint,
            descricao=f"data-testid variante '{variante}'",
        ))

    if html_hint:
        ph_match = re.search(r"placeholder=['\"]([^'\"]+)['\"]", html_hint)
        if ph_match:
            ph = ph_match.group(1)
            candidatos.append(TentativaLocalizacao(
                seletor=f"[placeholder='{ph}']", iframe_hint=iframe_hint, descricao=f"placeholder='{ph}'",
            ))
            candidatos.append(TentativaLocalizacao(
                seletor="", placeholder=ph, iframe_hint=iframe_hint, descricao=f"getByPlaceholder '{ph}'",
            ))

        title_match = re.search(r"title=['\"]([^'\"]+)['\"]", html_hint)
        if title_match:
            t = title_match.group(1)
            candidatos.append(TentativaLocalizacao(
                seletor=f"[title='{t}']", iframe_hint=iframe_hint, descricao=f"title='{t}'",
            ))
            candidatos.append(TentativaLocalizacao(
                seletor="", title=t, iframe_hint=iframe_hint, descricao=f"getByTitle '{t}'",
            ))

        id_match = re.search(r"\bid=['\"]([^'\"]+)['\"]", html_hint)
        if id_match:
            elem_id = id_match.group(1)
            if not re.search(r"(ng-|mat-|cdk-|\d{5,})", elem_id):
                candidatos.append(TentativaLocalizacao(
                    seletor=f"#{elem_id}", iframe_hint=iframe_hint, descricao=f"id='{elem_id}'",
                ))

    if label_curto and not is_tag_generica and not eh_digitacao and len(label_curto) > 3:
        candidatos.append(TentativaLocalizacao(
            seletor=f">> text={label_curto}", via_pierce=True, iframe_hint=iframe_hint,
            descricao=f"shadow DOM pierce texto '{label_curto}'",
        ))
        candidatos.append(TentativaLocalizacao(
            seletor=f"text={label_curto}", iframe_hint=iframe_hint,
            exact=False, descricao=f"texto parcial '{label_curto}'",
        ))

    return candidatos


# ──────────────────────────────────────────────────────────────
# RESOLUCAO DE IFRAME E SCROLL
# ──────────────────────────────────────────────────────────────
async def _resolver_contexto(page: Page, iframe_hint: Optional[str]):
    if not iframe_hint or iframe_hint in ("Pagina Principal", "Página Principal", "iframe-cross-origin"):
        return page

    for seletor_iframe in [
        f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']",
        f"iframe[id='{iframe_hint}']",   f"iframe[title*='{iframe_hint}']",
    ]:
        try:
            fl = page.frame_locator(seletor_iframe)
            await fl.locator("body").wait_for(state="attached", timeout=800)
            return fl
        except Exception:
            continue

    try:
        for frame in page.frames:
            try:
                if iframe_hint in frame.url or iframe_hint in frame.name:
                    return frame
            except Exception:
                continue
    except Exception:
        pass

    return page


async def _scroll_para_area_esperada(page: Page, coords_relativas: Optional[dict]) -> int:
    try:
        if coords_relativas and coords_relativas.get("y_pct"):
            vp            = page.viewport_size or {"width": 1920, "height": 1080}
            altura_est    = coords_relativas["y_pct"] * vp["height"] * 2
            if altura_est > vp["height"] * 0.8:
                await page.evaluate(f"window.scrollTo(0, {max(0, int(altura_est - 300))})")
                await asyncio.sleep(0.3)
        scroll_y = await page.evaluate("() => window.scrollY") or 0
        return int(scroll_y)
    except Exception:
        return 0


# ──────────────────────────────────────────────────────────────
# HIGHLIGHT VISUAL
# ──────────────────────────────────────────────────────────────
async def _highlight_elemento(locator, page) -> None:
    try:
        await locator.evaluate("""el => {
            // Focamos APENAS no elemento exato, sem invadir o CSS dos pais
            const alvoVisual = el;
            
            const oldOutline = alvoVisual.style.outline;
            const oldBoxShadow = alvoVisual.style.boxShadow;
            const oldBorderRadius = alvoVisual.style.borderRadius;

            alvoVisual.style.outline = '2px solid #00e5e5';
            alvoVisual.style.boxShadow = '0 0 8px rgba(0,229,229,0.5)';
            alvoVisual.style.borderRadius = '4px';
            
            setTimeout(() => {
                alvoVisual.style.outline = oldOutline; 
                alvoVisual.style.boxShadow = oldBoxShadow;
                alvoVisual.style.borderRadius = oldBorderRadius;
            }, 1200);
        }""")
        await asyncio.sleep(0.2)
    except Exception:
        pass


async def _highlight_coords(page: Page, x: int, y: int) -> None:
    try:
        await page.evaluate(f"""() => {{
            const dot = document.createElement('div');
            dot.style.cssText = 'position:fixed;left:{x-18}px;top:{y-18}px;width:36px;height:36px;border-radius:50%;background:rgba(0,229,229,0.5);border:3px solid #00e5e5;z-index:999999;pointer-events:none;animation:ping 0.6s ease-out;';
            document.body.appendChild(dot);
            setTimeout(() => dot.remove(), 900);
        }}""")
    except Exception:
        pass


async def _aguardar_estabilidade(page: Page, timeout_ms: int = 2000) -> None:
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        await asyncio.sleep(0.4)


async def _digitar_humanizado(page: Page, valor: str) -> None:
    """
    Digita um valor caractere por caractere com delay variável,
    simulando ritmo humano real. Usa press_sequentially (keydown/keyup
    por char) em vez de keyboard.type, que é mais mecânico.

    Delay base: 65ms por caractere.
    Variação aleatória: ±30ms por caractere (ruído natural).
    Pausa extra: 10% de chance de micro-pausa de 120-250ms
    (simula hesitação humana ao digitar).
    """
    import random
    for char in valor:
        delay = random.randint(45, 95)  # 45–95ms por caractere
        await page.keyboard.press(char, delay=delay)
        # micro-pausa ocasional (~10% dos caracteres)
        if random.random() < 0.10:
            await asyncio.sleep(random.uniform(0.12, 0.25))


async def _executar_acao(locator, page, acao: str, valor: str) -> None:
    try:
        await locator.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass

    # 1. O Mouse viaja suavemente até ao centro exato
    try:
        box = await locator.bounding_box(timeout=1000)
        if box:
            cx = box["x"] + box["width"] / 2
            cy = box["y"] + box["height"] / 2
            from cursor_engine import mover_cursor_humanizado
            await page.evaluate("() => { const c = document.getElementById('robo-cursor'); if(c) c.style.opacity = '1'; }")
            await mover_cursor_humanizado(page, cx, cy)
            
            # 🟢 A PEÇA QUE FALTAVA: O Hover estabilizador
            # Como o rato já está em (cx, cy), não há teleporte visual. 
            # Ele apenas protege contra o bug de "Abre e logo Fecha" do Angular.
            await locator.hover(timeout=2000)
    except Exception:
        pass

    await _highlight_elemento(locator, page)

    # 2. AUTO-DETECT DE UPLOAD (A Mágica Cinematográfica)
    is_file = False
    try:
        html_do_botao = await locator.evaluate("el => el.outerHTML", timeout=1000)
        if 'type="file"' in html_do_botao.lower() or 'upload' in html_do_botao.lower():
            is_file = True
    except Exception:
        pass

    if acao == "upload" or is_file:
        import tempfile
        import os
        nome_arquivo = valor if valor else "documento_treinamento.pdf"
        nome_arquivo = nome_arquivo.split("\\")[-1].split("/")[-1] 
        
        tmp_path = os.path.join(tempfile.gettempdir(), nome_arquivo)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"{nome_arquivo.upper()}\n\nLorem ipsum dolor sit amet. Este documento é uma simulação.")
        
        await page.evaluate(f"""(nome) => {{
            const overlay = document.createElement('div');
            overlay.id = 'senior-upload-overlay';
            overlay.style.cssText = `
                position:fixed; top:0; left:0; width:100vw; height:100vh;
                background:rgba(15,23,42,0.92); backdrop-filter:blur(8px);
                display:flex; flex-direction:column; align-items:center; justify-content:center;
                z-index:2147483647; color:#fff; font-family:'Segoe UI', sans-serif;
                opacity:0; transition:opacity 0.6s ease;
            `;
            overlay.innerHTML = `
                <div style="font-size:64px; margin-bottom:15px; animation: bounce-vertical 1s infinite alternate;">📁</div>
                <h2 style="font-weight:400; font-size:28px; margin:0;">Buscando arquivo local no computador...</h2>
                <p style="color:#00e5e5; font-size:22px; font-weight:bold; margin-top:20px; letter-spacing:1px;">Selecionando: ${{nome}}</p>
            `;
            document.body.appendChild(overlay);
            setTimeout(() => overlay.style.opacity = '1', 50);
        }}""", nome_arquivo)
        
        await asyncio.sleep(2.5)
        
        try:
            await locator.set_input_files(tmp_path, timeout=2000)
        except Exception:
            try:
                async with page.expect_file_chooser(timeout=5000) as fc_info:
                    await locator.click(timeout=2000)
                file_chooser = await fc_info.value
                await file_chooser.set_files(tmp_path)
            except Exception:
                pass
        
        await page.evaluate("""() => {
            const overlay = document.getElementById('senior-upload-overlay');
            if(overlay) {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.remove(), 600);
            }
        }""")
        await asyncio.sleep(0.5)
        return

    # 3. CLIQUES PADRÃO E SEGUROS (Sem force=True)
    if acao == "duplo_clique":
        await locator.dblclick(timeout=3000)
    elif acao == "clique_direito":
        await locator.click(button="right", timeout=3000)
    elif acao == "digitar_e_enter":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await _digitar_humanizado(page, valor)
        await page.keyboard.press("Enter")
    elif acao == "preencher_campo":
        await locator.click(timeout=2000)
        await asyncio.sleep(0.2)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await _digitar_humanizado(page, valor)
    else:
        await locator.click(timeout=3000)

    await _aguardar_estabilidade(page)


# ──────────────────────────────────────────────────────────────
# TENTATIVA DE SELETOR E FOCO NATIVO
# ──────────────────────────────────────────────────────────────
async def _tentar_candidato(
    page: Page, candidato: TentativaLocalizacao, acao: str, valor: str, timeout_ms: int = 3500
) -> bool:
    try:
        contexto = await _resolver_contexto(page, candidato.iframe_hint)

        if not candidato.seletor:
            if hasattr(contexto, "get_by_role") and candidato.role and candidato.label:
                loc = contexto.get_by_role(candidato.role, name=candidato.label).first
            elif hasattr(contexto, "get_by_label") and candidato.label:
                loc = contexto.get_by_label(candidato.label).first
            elif hasattr(contexto, "get_by_placeholder") and candidato.placeholder:
                loc = contexto.get_by_placeholder(candidato.placeholder).first
            elif hasattr(contexto, "get_by_title") and candidato.title:
                loc = contexto.get_by_title(candidato.title).first
            else:
                return False
        elif candidato.seletor.startswith("text="):
            texto = candidato.seletor[5:].strip('"').strip("'")
            loc   = contexto.get_by_text(texto, exact=candidato.exact).first
        elif candidato.via_pierce:
            loc = page.locator(candidato.seletor).first
        else:
            loc = contexto.locator(candidato.seletor).first

        await loc.wait_for(state="visible", timeout=timeout_ms)
        await _executar_acao(loc, page, acao, valor)
        return True
    except Exception:
        return False


async def _digitar_no_active_element(page: Page, acao: str, valor: str) -> bool:
    try:
        is_editable = False
        for _ in range(5):
            is_editable = await page.evaluate("""() => {
                const el = document.activeElement;
                if (!el || el.tagName === 'BODY') return false;
                return el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable || el.getAttribute('contenteditable') === 'true';
            }""")
            if is_editable:
                break
            await asyncio.sleep(0.3)

        if not is_editable:
            return False

        await page.evaluate("""() => {
            const el = document.activeElement;
            el.style.transition = 'all 0.3s';
            el.style.outline = '4px solid #00e5e5';
            el.style.boxShadow = '0 0 25px rgba(0,229,229,0.5)';
        }""")
        await asyncio.sleep(0.8)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Backspace")
        if valor:
            await page.keyboard.type(valor, delay=40)
        if acao == "digitar_e_enter":
            await page.keyboard.press("Enter")
        await asyncio.sleep(0.3)
        try:
            await page.evaluate("() => { const el = document.activeElement; if (el) { el.style.outline = ''; el.style.boxShadow = ''; } }")
        except Exception:
            pass
        await _aguardar_estabilidade(page)
        return True
    except Exception:
        return False


# ──────────────────────────────────────────────────────────────
# BUSCA EM TODOS OS FRAMES
# ──────────────────────────────────────────────────────────────
async def _buscar_em_todos_os_frames(
    page: Page, candidatos: list[TentativaLocalizacao], acao: str, valor: str
) -> Optional[str]:
    try:
        frames = page.frames
    except Exception:
        return None

    frames_filhos = [f for f in frames if f != page.main_frame]

    for frame in frames_filhos:
        for candidato in candidatos[:8]:
            cand_frame = TentativaLocalizacao(
                seletor=candidato.seletor, iframe_hint=None, exact=candidato.exact,
                via_pierce=candidato.via_pierce, role=candidato.role, label=candidato.label,
                placeholder=candidato.placeholder, title=candidato.title, descricao=candidato.descricao,
            )
            try:
                contexto = frame
                if not cand_frame.seletor:
                    if hasattr(contexto, "get_by_role") and cand_frame.role and cand_frame.label:
                        loc = contexto.get_by_role(cand_frame.role, name=cand_frame.label).first
                    elif hasattr(contexto, "get_by_label") and cand_frame.label:
                        loc = contexto.get_by_label(cand_frame.label).first
                    elif hasattr(contexto, "get_by_placeholder") and cand_frame.placeholder:
                        loc = contexto.get_by_placeholder(cand_frame.placeholder).first
                    elif hasattr(contexto, "get_by_title") and cand_frame.title:
                        loc = contexto.get_by_title(cand_frame.title).first
                    else:
                        continue
                elif cand_frame.seletor.startswith("text="):
                    texto = cand_frame.seletor[5:].strip('"').strip("'")
                    loc   = contexto.get_by_text(texto, exact=cand_frame.exact).first
                else:
                    loc = contexto.locator(cand_frame.seletor).first

                await loc.wait_for(state="visible", timeout=1500)
                await _executar_acao(loc, page, acao, valor)
                logger.info(f"   [Todos os Frames] Encontrado em frame: {frame.url[:60]}")
                return frame.url
            except Exception:
                continue
    return None


# ──────────────────────────────────────────────────────────────
# GEMINI VISION & COORDENADAS
# ──────────────────────────────────────────────────────────────

def _resolver_screenshot_ref(ref: Optional[str]) -> Optional[bytes]:
    """
    Resolve screenshot_referencia para bytes, independentemente do formato.

    Suporta:
      - Path relativo em disco (ex: "audios_gerados/Aula/screenshots/acao_1.jpg")
      - String base64 JPEG (roteiros legados pré-Fase 3)
      - None / ausente

    Nunca lança exceção — retorna None em caso de falha.
    """
    if not ref:
        return None
    # Tenta como path de arquivo primeiro
    if os.path.exists(ref):
        try:
            with open(ref, "rb") as f:
                return f.read()
        except Exception:
            return None
    # Fallback: tenta decodificar como base64
    try:
        return base64.b64decode(ref)
    except Exception:
        return None


async def _gemini_localizar_elemento(
    screenshot_atual: bytes, screenshot_ref_b64: Optional[str],
    descricao_visual: str, intencao: str, contexto_tela: str,
    viewport: dict, scroll_y: int,
) -> Optional[dict]:
    # [BUG-1] FIX: retorna None graciosamente sem chave
    if not gemini_client:
        return None

    logger.info("   [Gemini Vision] Acionando a IA para reparar o script...")
    contents: list = []

    # screenshot_ref_b64 pode ser base64 (legado) ou path relativo (Fase 3)
    # _resolver_screenshot_ref detecta automaticamente o formato
    if screenshot_ref_b64:
        ref_bytes = _resolver_screenshot_ref(screenshot_ref_b64)
        if ref_bytes:
            contents.append("IMAGEM 1 - REFERENCIA (estado da tela na gravacao original):")
            contents.append(types.Part.from_bytes(data=ref_bytes, mime_type="image/jpeg"))

    contents.append("IMAGEM 2 - TELA ATUAL (onde o elemento deve ser clicado agora):")
    contents.append(types.Part.from_bytes(data=screenshot_atual, mime_type="image/jpeg"))
    contents.append(
        f"Voce esta controlando um navegador com resolucao {viewport['width']}x{viewport['height']}px.\n"
        f"O scroll vertical atual da pagina e {scroll_y}px.\n\n"
        f"Localize este elemento na IMAGEM 2 (tela atual):\n"
        f"- Intencao do usuario: {intencao}\n"
        f"- Descricao visual: {descricao_visual}\n"
        f"- Contexto da tela: {contexto_tela}\n\n"
        f'Responda ESTRITAMENTE com JSON:\n'
        f'{{"metodo": "coordenadas", "coordenadas": {{"x": 500, "y": 300}}, "confianca": "alta|media|baixa"}}\n'
        f'ou {{"metodo": "nao_encontrado"}}'
    )

    try:
        resposta = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.05),
        )
        resultado = json.loads(resposta.text)
        if resultado.get("metodo") == "nao_encontrado":
            return None
        return resultado
    except Exception:
        return None


def _parse_coords(coords):
    try:
        if isinstance(coords, dict):
            return int(coords.get("x", 0)), int(coords.get("y", 0))
        elif isinstance(coords, list):
            if len(coords) > 0 and isinstance(coords[0], dict):
                return int(coords[0].get("x", 0)), int(coords[0].get("y", 0))
            elif len(coords) >= 2:
                return int(coords[0]), int(coords[1])
        elif isinstance(coords, str):
            nums = re.findall(r"\d+", coords)
            if len(nums) >= 2:
                return int(nums[0]), int(nums[1])
    except Exception:
        pass
    return 0, 0


async def _clicar_por_coordenadas(page: Page, coords, acao: str, valor: str) -> bool:
    try:
        x, y = _parse_coords(coords)
        if x <= 0 or y <= 0:
            raise ValueError(f"Coordenadas invalidas: x={x}, y={y}")

        await _highlight_coords(page, x, y)
        await asyncio.sleep(0.3)

        if acao == "duplo_clique":
            await page.mouse.dblclick(x, y)
        elif acao == "clique_direito":
            await page.mouse.click(x, y, button="right")
        else:
            await page.mouse.click(x, y)

        if acao in ("digitar_e_enter", "preencher_campo") and valor:
            await asyncio.sleep(0.3)
            await page.keyboard.press("Control+A")
            await page.keyboard.press("Backspace")
            await page.keyboard.type(valor, delay=40)
            if acao == "digitar_e_enter":
                await page.keyboard.press("Enter")

        await _aguardar_estabilidade(page)
        return True
    except Exception as exc:
        logger.warning(f"Clique por coordenadas falhou: {exc}")
        return False


# ──────────────────────────────────────────────────────────────
# DETECÇÃO DE MENU DE CONTEXTO ATIVO (CAMADA 0.5)
# ──────────────────────────────────────────────────────────────
async def _detectar_menu_contexto_ativo(page) -> object | None:
    """
    Verifica se um menu de contexto está visível como overlay na página.
    Retorna o Locator do primeiro menu visível encontrado, ou None.
    Usa timeout=300ms para não penalizar o caminho feliz (sem menu ativo).
    """
    seletores_menu = [
        ".p-contextmenu",
        "[role='menu']",
        ".context-menu",
        "ul[class*='contextmenu']",
        ".p-menu-list",
    ]
    for seletor in seletores_menu:
        try:
            locator = page.locator(seletor).first
            await locator.wait_for(state="visible", timeout=300)
            return locator
        except Exception:
            continue
    return None


async def _buscar_em_escopo_menu(menu_locator, label_curto: str) -> str | None:
    """
    Localiza o elemento dentro do container do menu de contexto.
    Estratégias em ordem de confiança, todas escopadas ao menu_locator.
    Retorna o seletor usado em caso de sucesso, ou None se não encontrado.
    """
    estrategias = [
        ("role_menuitem", lambda: menu_locator.get_by_role("menuitem", name=label_curto)),
        ("text_exact",    lambda: menu_locator.get_by_text(label_curto, exact=True)),
        ("has_text",      lambda: menu_locator.locator(f":has-text('{label_curto}')").last),
    ]
    for nome, fn in estrategias:
        try:
            el = fn()
            await el.wait_for(state="visible", timeout=1000)
            await el.click()
            return nome
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────
# ORQUESTRADOR PRINCIPAL (A MAQUINA DE DECISAO)
# ──────────────────────────────────────────────────────────────
async def encontrar_e_clicar(page: Page, acao_tec: dict) -> bool:
    """
    Roteia a tentativa pelas 7 camadas de fallback ate encontrar o elemento.
    """
    alvo:     dict         = acao_tec.get("elemento_alvo", {})
    acao:     str          = acao_tec.get("acao", "clique")
    intencao: str          = acao_tec.get("intencao_semantica", "Acao na interface")
    valor:    str          = acao_tec.get("valor_input", "") or ""

    label_curto:     str           = alvo.get("label_curto", "")
    iframe_hint:     Optional[str] = alvo.get("iframe_hint")
    seletor_hint:    str           = alvo.get("seletor_hint", "")
    descricao_visual: str          = alvo.get("descricao_visual", label_curto)
    contexto_tela:   str           = alvo.get("contexto_tela", "")
    tipo_elemento:   str           = alvo.get("tipo_elemento", "button")
    html_hint:       str           = alvo.get("html_hint", "")
    coords_relativas: Optional[dict] = alvo.get("coordenadas_relativas")

    logger.info(f"\n   Executando: {intencao[:80]}")
    scroll_y = await _scroll_para_area_esperada(page, coords_relativas)

    # ── 0. BRAIN (Memoria SQLite de longo prazo) ──────────────────────────────
    # [BUG-3] FIX: flag impede double-registration de falha
    brain_registrou_falha = False
    cache = _consultar_cache(intencao)
    if cache:
        if cache.seletor:
            # [CTX-MENU] Consciência de overlay: se menu de contexto ativo e seletor
            # não aponta para dentro de um menu, pular Brain e deixar camada 0.5 tratar.
            _menu_ativo_check = await _detectar_menu_contexto_ativo(page)
            _seletor_aponta_menu = any(
                p in (cache.seletor or "")
                for p in (".p-contextmenu", "[role='menu']", ".context-menu", "p-menu", "menuitem")
            )
            if _menu_ativo_check is not None and not _seletor_aponta_menu:
                logger.debug(
                    f"[BRAIN] Menu de contexto ativo — pulando seletor memorizado "
                    f"'{cache.seletor}' (não aponta para menu)"
                )
                # Não usar o Brain — deixar camada 0.5 tratar
            else:
                cand_cache = TentativaLocalizacao(
                    seletor=cache.seletor,
                    iframe_hint=cache.iframe_src or iframe_hint,
                    descricao="brain knowledge",
                )
                if await _tentar_candidato(page, cand_cache, acao, valor):
                    _registrar_sucesso_cache(intencao)
                    _registrar_telemetria("0_brain", True)
                    return True
                else:
                    _registrar_falha_cache(intencao)
                    _registrar_telemetria("0_brain", False)
                    brain_registrou_falha = True
        elif cache.coords:
            if await _clicar_por_coordenadas(page, cache.coords, acao, valor):
                _registrar_sucesso_cache(intencao)
                _registrar_telemetria("0_brain_coords", True)
                return True
            else:
                _registrar_falha_cache(intencao)
                _registrar_telemetria("0_brain_coords", False)
                brain_registrou_falha = True

    # ── Camada 0.5: Menu de contexto ativo ──────────────────────────────────
    menu_locator = await _detectar_menu_contexto_ativo(page)
    if menu_locator is not None:
        seletor_usado = await _buscar_em_escopo_menu(menu_locator, label_curto)
        if seletor_usado:
            _registrar_sucesso_cache(intencao, seletor_usado)
            _registrar_telemetria("0.5_menu_ctx", True)
            logger.info(f"[MENU-CTX] Clicou em '{label_curto}' dentro do menu de contexto via '{seletor_usado}'")
            return True
        else:
            # Elemento não encontrado no menu — escalar direto para Gemini Vision
            logger.warning(f"[MENU-CTX] Menu ativo mas '{label_curto}' não encontrado no escopo — escalando para Gemini")
            try:
                screenshot_atual = await page.screenshot(type="jpeg", quality=60, full_page=False)
            except Exception as exc:
                logger.warning(f"Screenshot falhou antes do Gemini (camada 0.5): {exc}")
                screenshot_atual = None
            if screenshot_atual:
                vp = page.viewport_size or {"width": 1920, "height": 1080}
                resultado_gemini = await _gemini_localizar_elemento(
                    screenshot_atual=screenshot_atual,
                    screenshot_ref_b64=alvo.get("screenshot_referencia"),
                    descricao_visual=descricao_visual,
                    intencao=intencao,
                    contexto_tela=contexto_tela,
                    viewport=vp,
                    scroll_y=scroll_y,
                )
                if resultado_gemini:
                    coords_ia = resultado_gemini.get("coordenadas")
                    if coords_ia and await _clicar_por_coordenadas(page, coords_ia, acao, valor):
                        logger.info("[MENU-CTX] Gemini Vision resolveu o item de menu.")
                        _registrar_sucesso_cache(intencao, coords=coords_ia)
                        _registrar_telemetria("5_gemini_vision", True)
                        return True
            _registrar_telemetria("0.5_menu_ctx", False)
            return False

    # ── 1. Foco Nativo (exclusivo para inputs) ────────────────────────────────
    if acao in ("digitar_e_enter", "preencher_campo"):
        logger.info("   [Foco Nativo] Verificando se cursor ja esta posicionado...")
        if await _digitar_no_active_element(page, acao, valor):
            logger.info("   [Foco Nativo] Texto inserido no campo ja focado!")
            _registrar_telemetria("1_foco_nativo", True)
            return True

        logger.info("   [Foco Nativo] Buscando div contenteditable generica...")
        contexto = await _resolver_contexto(page, iframe_hint)
        try:
            loc_edit = contexto.locator("[contenteditable='true']")
            if await loc_edit.count() > 0 and await loc_edit.first.is_visible():
                await _executar_acao(loc_edit.first, page, acao, valor)
                _registrar_telemetria("1_foco_nativo", True)
                return True
        except Exception:
            pass

    # ── 1.5. HEURISTICAS SENIOR X (icones mudos) ─────────────────────────────
    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS
    if is_tag_generica or not label_curto:
        intencao_low          = intencao.lower()
        contexto_heuristica   = await _resolver_contexto(page, iframe_hint)

        if any(p in intencao_low for p in ["pagina inicial", "página inicial", "home", "inicio", "início", "raiz", "dashboard"]):
            logger.info("   [Senior X] Heuristica ativada para icone Home/Breadcrumb...")
            seletores_home = [
                "li.ng-star-inserted:first-child", "p-breadcrumb li:first-child",
                ".pi-home", ".fa-home", ".ph-house",
                "i[class*='home']", "span[class*='home']",
                # Variantes Senior X (fas fa-home, fas fa-house)
                ".fas.fa-home", ".fas.fa-house", "span.fas.fa-home",
                "[class*='fa-home']", "[class*='fa-house']",
            ]
            for sel in seletores_home:
                try:
                    loc = contexto_heuristica.locator(sel).first
                    if await loc.count() > 0 and await loc.is_visible():
                        await _executar_acao(loc, page, acao, valor)
                        logger.info("   [Heuristica] Icone Home atingido com sucesso.")
                        _registrar_sucesso_cache(intencao, seletor=sel, iframe=iframe_hint)
                        _registrar_telemetria("1.5_heuristica_seniorx", True)
                        return True
                except Exception:
                    pass

    # ── Gera candidatos ───────────────────────────────────────────────────────
    candidatos = _gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)

    # ── 2. Sniper Semantico ───────────────────────────────────────────────────
    if candidatos:
        logger.info(f"   [Sniper] {len(candidatos)} candidatos para '{label_curto}'...")
        for cand in candidatos:
            if await _tentar_candidato(page, cand, acao, valor):
                logger.info(f"   [Sniper] Acerto: {cand.descricao}")
                # [BUG-2] FIX: passa apenas cand.seletor (None quando vazio, nao cand.descricao)
                _registrar_sucesso_cache(
                    intencao,
                    seletor=cand.seletor if cand.seletor else None,
                    iframe=iframe_hint,
                )
                _registrar_telemetria("2_sniper", True)
                return True

    # ── 3. Seletor Hint Original ──────────────────────────────────────────────
    if seletor_hint and not _e_seletor_fragil(seletor_hint):
        # Verificação de identidade para seletores posicionais (fix bug item errado)
        if _contem_indice_posicional(seletor_hint) and label_curto and not is_tag_generica:
            logger.warning("[Hint] Seletor posicional detectado — validando identidade antes de executar")
            locator = page.locator(seletor_hint).first
            identidade_ok = await _verificar_identidade_elemento(locator, label_curto)
            if not identidade_ok:
                logger.warning("[Hint] Identidade não confirmada — descartando seletor posicional, escalando")
            else:
                cand_hint = TentativaLocalizacao(
                    seletor=seletor_hint, iframe_hint=iframe_hint,
                    descricao=f"hint original '{seletor_hint[:40]}'",
                )
                if await _tentar_candidato(page, cand_hint, acao, valor):
                    logger.info(f"   [Hint] Seletor original funcionou: {seletor_hint[:60]}")
                    _registrar_sucesso_cache(intencao, seletor=seletor_hint, iframe=iframe_hint)
                    _registrar_telemetria("3_hint_original", True)
                    return True
        else:
            cand_hint = TentativaLocalizacao(
                seletor=seletor_hint, iframe_hint=iframe_hint,
                descricao=f"hint original '{seletor_hint[:40]}'",
            )
            if await _tentar_candidato(page, cand_hint, acao, valor):
                logger.info(f"   [Hint] Seletor original funcionou: {seletor_hint[:60]}")
                _registrar_sucesso_cache(intencao, seletor=seletor_hint, iframe=iframe_hint)
                _registrar_telemetria("3_hint_original", True)
                return True

    # ── 4. Busca Profunda em Todos os Frames ──────────────────────────────────
    if candidatos:
        logger.info("   [Todos os Frames] Procurando o elemento em frames filhos...")
        frame_url = await _buscar_em_todos_os_frames(page, candidatos, acao, valor)
        if frame_url:
            _registrar_sucesso_cache(intencao, iframe=frame_url)
            _registrar_telemetria("4_todos_frames", True)
            return True

    # ── 5. Gemini Vision (Self-Healing Supremo) ───────────────────────────────
    logger.info("   [Vision] DOM esgotado. Acionando Gemini Visual...")
    try:
        screenshot_atual = await page.screenshot(type="jpeg", quality=60, full_page=False)
    except Exception as exc:
        logger.warning(f"Screenshot falhou antes do Gemini: {exc}")
        screenshot_atual = None

    if screenshot_atual:
        vp       = page.viewport_size or {"width": 1920, "height": 1080}
        resultado = await _gemini_localizar_elemento(
            screenshot_atual=screenshot_atual,
            screenshot_ref_b64=alvo.get("screenshot_referencia"),
            descricao_visual=descricao_visual,
            intencao=intencao,
            contexto_tela=contexto_tela,
            viewport=vp,
            scroll_y=scroll_y,
        )
        if resultado:
            coords_ia = resultado.get("coordenadas")
            if coords_ia:
                if await _clicar_por_coordenadas(page, coords_ia, acao, valor):
                    logger.info("   [Vision] Clique por coordenadas da IA bem-sucedido.")
                    # [Fase 2.3] Tenta aprender o seletor DOM após acerto por coordenada
                    try:
                        x_ia, y_ia = _parse_coords(coords_ia)
                        seletor_aprendido = await page.evaluate(
                            """([x, y]) => {
                                const el = document.elementFromPoint(x, y);
                                if (!el) return null;
                                const tid = el.getAttribute('data-testid');
                                if (tid) return `[data-testid='${tid}']`;
                                const aria = el.getAttribute('aria-label');
                                if (aria) return `[aria-label='${aria}']`;
                                const name = el.getAttribute('name');
                                if (name) return `[name='${name}']`;
                                if (el.id && !el.id.match(/^(ng-|mat-|cdk-|\\d)/)) return `#${el.id}`;
                                return null;
                            }""",
                            [x_ia, y_ia]
                        )
                        _registrar_sucesso_cache(intencao, coords=coords_ia, seletor=seletor_aprendido)
                        if seletor_aprendido:
                            logger.info(f"   [Vision] Seletor aprendido após coordenada: {seletor_aprendido}")
                    except Exception:
                        _registrar_sucesso_cache(intencao, coords=coords_ia)
                    _registrar_telemetria("5_gemini_vision", True)
                    return True

    # ── 6. Fallback Cego (Coordenadas Relativas Originais) ───────────────────
    if coords_relativas and coords_relativas.get("x_pct"):
        logger.info("   [Fallback Final] Coordenadas da gravacao original...")
        try:
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            x  = int(coords_relativas["x_pct"] * vp["width"])
            y  = int(coords_relativas["y_pct"] * vp["height"])
            if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
                logger.info(f"   [Fallback Final] Clique em ({x}, {y}) executado.")
                _registrar_telemetria("6_coords_originais", True)
                return True
        except Exception as exc:
            logger.warning(f"Fallback de coordenadas falhou: {exc}")

    # ── Falha Total ───────────────────────────────────────────────────────────
    # [BUG-3] FIX: registra falha apenas se o Brain nao registrou uma neste ciclo
    if not brain_registrou_falha:
        _registrar_falha_cache(intencao)
    _registrar_telemetria("falha_total", False)
    logger.error(f"   [FALHA TOTAL] Impossivel executar: '{intencao[:70]}'")
    return False
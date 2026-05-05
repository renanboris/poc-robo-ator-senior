"""
screen_fingerprint.py — Identificação de Tela por DOM
======================================================
Responde "onde estou?" sem gastar um único token.

PRINCÍPIO:
  Cada tela tem uma assinatura DOM única e estável. Em vez de mandar um
  screenshot para o Gemini toda vez, extraímos ~10 sinais do DOM e
  comparamos com o que já conhecemos. Se bater: retorna instantaneamente.
  Se não conhecer: deixa o Gemini identificar e aprende para a próxima vez.

CUSTO:
  - identificar_tela():  0 tokens, ~30ms (DOM query)
  - registrar_tela():    0 tokens, ~50ms (DOM query + SQLite write)
  - Gemini só é chamado para telas NOVAS (nunca vistas antes)

COMO FUNCIONA O FINGERPRINT:
  Não é um hash da tela inteira — isso quebraria com qualquer mudança.
  É uma combinação de 5 sinais estáveis:
    1. url_pattern    → path sem IDs dinâmicos
    2. elementos_dom  → quais seletores estão presentes (hash de set)
    3. estado_aria    → aria-selected/expanded/current (o que está ativo)
    4. iframes        → quais iframes estão visíveis
    5. titulo_dom     → título da página (document.title normalizado)

  Cada sinal tem um peso. Pontuação ≥ 80% = match confirmado.
  Pontuação 60-79% = match provável (retorna com flag `incerto=True`).
  Abaixo de 60% = desconhecido → precisa do Gemini.
"""

import hashlib
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field

from playwright.async_api import Page

logger = logging.getLogger(__name__)

DB_PATH = "brain_v2.db"

# Pesos de cada sinal no score total (devem somar 100)
PESOS = {
    "elementos_dom":  35,   # quais seletores estão presentes
    "estado_aria":    25,   # o que está ativo/selecionado
    "iframes":        20,   # quais iframes estão visíveis
    "url_pattern":    12,   # padrão da URL
    "titulo_dom":      8,   # document.title normalizado
}

LIMIAR_CONFIRMADO  = 80   # pontuação mínima para match seguro
LIMIAR_PROVAVEL    = 60   # pontuação mínima para match incerto


@dataclass
class ResultadoIdentificacao:
    tela_id: str = ""
    confianca: float = 0.0        # 0.0 a 1.0
    incerto: bool = False         # True se entre 60-79%
    desconhecida: bool = False    # True se < 60%
    tempo_ms: float = 0.0
    sinais_bateram: list = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════
# EXTRAÇÃO DE FINGERPRINT
# ══════════════════════════════════════════════════════════════════

# Script JS que extrai os sinais da tela de forma eficiente (uma única roundtrip)
_JS_EXTRAIR_SINAIS = r"""
() => {
    const sinais = {};

    // 1. URL pattern — remove IDs numéricos e GUIDs da URL
    const url = location.href
        .replace(/\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '/:guid')
        .replace(/\/\d{4,}/g, '/:id')
        .replace(/[?&][^=]+=\d+/g, '')
        .split('#')[0];
    sinais.url_pattern = url.slice(0, 120);

    // 2. Título normalizado
    sinais.titulo_dom = (document.title || '')
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 80);

    // 3. Iframes visíveis — nome, src pattern, dimensões relativas
    const iframes = [];
    document.querySelectorAll('iframe').forEach(f => {
        const r = f.getBoundingClientRect();
        if (r.width > 100 && r.height > 80) {
            const src = (f.src || '').replace(/[?].*/, '').slice(-50);
            iframes.push(f.name || f.id || src.split('/').pop() || 'iframe');
        }
    });
    sinais.iframes = iframes.sort().join('|');

    // 4. Estado ARIA — o que está ativo/selecionado agora
    const aria_sinais = [];
    document.querySelectorAll(
        '[aria-current="page"],[aria-selected="true"],[aria-expanded="true"],[aria-checked="true"]'
    ).forEach(el => {
        const id = el.id || el.getAttribute('aria-label') ||
                   (el.innerText || el.textContent || '').trim().slice(0, 30);
        const estado = el.getAttribute('aria-current') ||
                       el.getAttribute('aria-selected') ||
                       el.getAttribute('aria-expanded') ? 'ativo' : '';
        if (id) aria_sinais.push(id.toLowerCase().replace(/\s+/g, '_'));
    });
    // Limita a 8 sinais mais relevantes para evitar instabilidade
    sinais.estado_aria = aria_sinais.slice(0, 8).sort().join('|');

    // 5. Elementos DOM presentes — seletores diagnósticos
    // Esta lista é a chave: seletores que são únicos por tela
    const seletores_diagnosticos = [
        // Senior X — sidebar
        '#menu-item-Senior\\ Flow',
        '[id*="apps-menu-item"]',
        '.mat-drawer-opened',
        '[aria-expanded="true"]',
        // GED
        '#newFolderButton',
        '#itemTitle',
        '.ui-breadcrumb',
        'iframe[name="ci"]',
        // Formulários
        'form mat-form-field',
        'p-table',
        'p-dialog',
        // Gerais
        'mat-sidenav',
        'mat-dialog-container',
        'mat-tab-group',
    ];
    const presentes = seletores_diagnosticos.filter(s => {
        try { return !!document.querySelector(s); } catch(e) { return false; }
    });
    sinais.elementos_dom = presentes.sort().join('|');

    return sinais;
}
"""


async def extrair_sinais(page: Page) -> dict:
    """
    Extrai os sinais DOM da tela atual.
    Uma única chamada JavaScript, ~30ms.
    """
    try:
        return await page.evaluate(_JS_EXTRAIR_SINAIS)
    except Exception as e:
        logger.warning(f"[Fingerprint] Erro ao extrair sinais: {e}")
        return {}


def _hash_sinal(valor: str) -> str:
    """Hash curto de um sinal para armazenamento compacto."""
    return hashlib.md5(valor.encode()).hexdigest()[:12]


def calcular_score(sinais_atual: dict, sinais_salvo: dict) -> tuple[float, list]:
    """
    Compara dois conjuntos de sinais e retorna (score_0_100, sinais_que_bateram).

    Lógica de comparação por sinal:
    - elementos_dom: Jaccard similarity (interseção / união dos seletores presentes)
    - estado_aria:   exato ou parcial (quantos itens em comum)
    - iframes:       exato ou parcial
    - url_pattern:   exato ou prefix match
    - titulo_dom:    contains match
    """
    score = 0.0
    bateram = []

    def _jaccard_sets(a: str, b: str) -> float:
        sa = set(a.split("|")) - {""}
        sb = set(b.split("|")) - {""}
        if not sa and not sb:
            return 1.0   # ambos vazios = match perfeito
        if not sa or not sb:
            return 0.3   # um vazio, outro não = match parcial (telas em transição)
        inter = len(sa & sb)
        union = len(sa | sb)
        return inter / union if union > 0 else 0.0

    def _partial_match(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        items_a = set(a.split("|")) - {""}
        items_b = set(b.split("|")) - {""}
        if not items_a and not items_b:
            return 1.0
        common = len(items_a & items_b)
        total  = max(len(items_a), len(items_b))
        return common / total if total > 0 else 0.0

    # ── elementos_dom (peso 35) ───────────────────────────────────
    sim_dom = _jaccard_sets(
        sinais_atual.get("elementos_dom", ""),
        sinais_salvo.get("elementos_dom", "")
    )
    score += sim_dom * PESOS["elementos_dom"]
    if sim_dom >= 0.7:
        bateram.append(f"elementos_dom ({sim_dom:.0%})")

    # ── estado_aria (peso 25) ─────────────────────────────────────
    sim_aria = _partial_match(
        sinais_atual.get("estado_aria", ""),
        sinais_salvo.get("estado_aria", "")
    )
    score += sim_aria * PESOS["estado_aria"]
    if sim_aria >= 0.6:
        bateram.append(f"estado_aria ({sim_aria:.0%})")

    # ── iframes (peso 20) ─────────────────────────────────────────
    sim_iframe = _partial_match(
        sinais_atual.get("iframes", ""),
        sinais_salvo.get("iframes", "")
    )
    score += sim_iframe * PESOS["iframes"]
    if sim_iframe >= 0.8:
        bateram.append(f"iframes ({sim_iframe:.0%})")

    # ── url_pattern (peso 12) ─────────────────────────────────────
    url_a = sinais_atual.get("url_pattern", "")
    url_b = sinais_salvo.get("url_pattern", "")
    if url_a == url_b:
        score += PESOS["url_pattern"]
        bateram.append("url_pattern (exato)")
    elif url_a and url_b:
        # Prefix match parcial
        common_prefix = len(
            re.match(r'^(.{0,60})', _common_prefix(url_a, url_b)).group(1)
        )
        sim_url = min(common_prefix / max(len(url_a), len(url_b), 1), 1.0)
        score += sim_url * PESOS["url_pattern"]
        if sim_url >= 0.7:
            bateram.append(f"url_pattern ({sim_url:.0%})")

    # ── titulo_dom (peso 8) ───────────────────────────────────────
    titulo_a = sinais_atual.get("titulo_dom", "")
    titulo_b = sinais_salvo.get("titulo_dom", "")
    if titulo_a and titulo_b:
        if titulo_a == titulo_b:
            score += PESOS["titulo_dom"]
            bateram.append("titulo_dom (exato)")
        elif titulo_a in titulo_b or titulo_b in titulo_a:
            score += PESOS["titulo_dom"] * 0.7
            bateram.append("titulo_dom (parcial)")

    return round(score, 1), bateram


def _common_prefix(a: str, b: str) -> str:
    i = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        i += 1
    return a[:i]


# ══════════════════════════════════════════════════════════════════
# PERSISTÊNCIA NO BRAIN DB
# ══════════════════════════════════════════════════════════════════

def _init_tabela_fingerprints():
    """Cria a tabela de fingerprints no Brain DB se não existir."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS telas_conhecidas (
                    tela_id             TEXT PRIMARY KEY,
                    nome_descritivo     TEXT DEFAULT '',
                    sinais_json         TEXT NOT NULL,
                    descricao_gemini    TEXT DEFAULT '',
                    acoes_disponiveis   TEXT DEFAULT '[]',
                    elementos_chave     TEXT DEFAULT '{}',
                    hits                INTEGER DEFAULT 0,
                    ultima_vista        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    criada_em           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    except Exception as e:
        logger.warning(f"[Fingerprint] Erro ao criar tabela: {e}")


_init_tabela_fingerprints()


def _carregar_todos_fingerprints() -> list[dict]:
    """Carrega todos os fingerprints conhecidos do banco."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT * FROM telas_conhecidas ORDER BY hits DESC"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def registrar_tela(
    tela_id: str,
    sinais: dict,
    nome_descritivo: str = "",
    descricao_gemini: str = "",
    acoes_disponiveis: list = None,
    elementos_chave: dict = None,
):
    """
    Registra ou atualiza o fingerprint de uma tela conhecida.
    Chamado pelo screen_reader quando o Gemini identifica uma tela nova.
    """
    try:
        with sqlite3.connect(DB_PATH) as c:
            existe = c.execute(
                "SELECT tela_id FROM telas_conhecidas WHERE tela_id=?", (tela_id,)
            ).fetchone()

            if existe:
                # Atualiza sinais e incrementa hits
                c.execute("""
                    UPDATE telas_conhecidas
                    SET sinais_json=?, hits=hits+1, ultima_vista=CURRENT_TIMESTAMP,
                        nome_descritivo=COALESCE(NULLIF(?,NULL),nome_descritivo)
                    WHERE tela_id=?
                """, (json.dumps(sinais), nome_descritivo or None, tela_id))
                logger.info(f"[Fingerprint] Atualizado: '{tela_id}'")
            else:
                c.execute("""
                    INSERT INTO telas_conhecidas
                        (tela_id, nome_descritivo, sinais_json, descricao_gemini,
                         acoes_disponiveis, elementos_chave, hits)
                    VALUES (?,?,?,?,?,?,1)
                """, (
                    tela_id,
                    nome_descritivo,
                    json.dumps(sinais),
                    descricao_gemini,
                    json.dumps(acoes_disponiveis or []),
                    json.dumps(elementos_chave or {}),
                ))
                logger.info(f"[Fingerprint] ✅ Nova tela aprendida: '{tela_id}' — {nome_descritivo}")
    except Exception as e:
        logger.warning(f"[Fingerprint] Erro ao registrar: {e}")


# ══════════════════════════════════════════════════════════════════
# IDENTIFICAÇÃO
# ══════════════════════════════════════════════════════════════════

async def identificar_tela(page: Page) -> ResultadoIdentificacao:
    """
    Identifica qual tela está sendo exibida comparando o DOM com fingerprints conhecidos.

    Retorna em ~30ms se a tela for conhecida.
    Se desconhecida, retorna ResultadoIdentificacao(desconhecida=True)
    para que o screen_reader chame o Gemini.

    Uso típico:
        resultado = await identificar_tela(page)
        if resultado.desconhecida:
            # Chama Gemini para identificar e aprender
            estado = await screen_reader.ler_tela_com_gemini(page, objetivo)
            registrar_tela(estado.tela_id, sinais, ...)
        else:
            # Usa o conhecimento existente — 0 tokens
            return estado_do_cache[resultado.tela_id]
    """
    t0 = time.monotonic()

    sinais_atuais = await extrair_sinais(page)
    if not sinais_atuais:
        return ResultadoIdentificacao(desconhecida=True, tempo_ms=0)

    conhecidas = _carregar_todos_fingerprints()
    if not conhecidas:
        return ResultadoIdentificacao(desconhecida=True, tempo_ms=(time.monotonic()-t0)*1000)

    melhor_score = 0.0
    melhor_id    = ""
    melhor_sinais_bateram = []

    for tela in conhecidas:
        try:
            sinais_salvo = json.loads(tela["sinais_json"])
            score, bateram = calcular_score(sinais_atuais, sinais_salvo)
            if score > melhor_score:
                melhor_score = score
                melhor_id    = tela["tela_id"]
                melhor_sinais_bateram = bateram
        except Exception:
            continue

    tempo_ms = (time.monotonic() - t0) * 1000

    if melhor_score >= LIMIAR_CONFIRMADO:
        logger.info(
            f"[Fingerprint] ✅ '{melhor_id}' ({melhor_score:.0f}pts) em {tempo_ms:.0f}ms"
            f" | sinais: {', '.join(melhor_sinais_bateram)}"
        )
        # Incrementa hits
        try:
            with sqlite3.connect(DB_PATH) as c:
                c.execute(
                    "UPDATE telas_conhecidas SET hits=hits+1, ultima_vista=CURRENT_TIMESTAMP WHERE tela_id=?",
                    (melhor_id,)
                )
        except Exception:
            pass
        return ResultadoIdentificacao(
            tela_id=melhor_id,
            confianca=melhor_score / 100,
            incerto=False,
            desconhecida=False,
            tempo_ms=tempo_ms,
            sinais_bateram=melhor_sinais_bateram,
        )

    if melhor_score >= LIMIAR_PROVAVEL:
        logger.info(
            f"[Fingerprint] ⚠ Provável '{melhor_id}' ({melhor_score:.0f}pts) — confirmação recomendada"
        )
        return ResultadoIdentificacao(
            tela_id=melhor_id,
            confianca=melhor_score / 100,
            incerto=True,
            desconhecida=False,
            tempo_ms=tempo_ms,
            sinais_bateram=melhor_sinais_bateram,
        )

    logger.info(f"[Fingerprint] 🆕 Tela desconhecida (melhor score: {melhor_score:.0f}pts) — Gemini necessário")
    return ResultadoIdentificacao(
        desconhecida=True,
        confianca=melhor_score / 100,
        tempo_ms=tempo_ms,
    )


# ══════════════════════════════════════════════════════════════════
# PRÉ-CARREGAMENTO DO SCHEMA JSON (conhecimento manual)
# ══════════════════════════════════════════════════════════════════

def carregar_conhecimento_de_schema(schema_path: str):
    """
    Importa as telas mapeadas manualmente no schema JSON para o Brain DB.
    Permite pre-popularizar fingerprints antes da primeira execução.

    Os sinais serão aproximados até a primeira execução real — quando
    identificar_tela() registrar os sinais DOM reais da tela.
    """
    import os
    if not os.path.exists(schema_path):
        return

    try:
        with open(schema_path, encoding="utf-8") as f:
            schema = json.load(f)

        telas = schema.get("conhecimento_do_sistema", {}).get("telas_mapeadas", [])
        for tela in telas:
            tela_id = tela.get("id", "")
            if not tela_id:
                continue

            # Constrói sinais aproximados a partir do conhecimento manual
            sinais_aproximados = {
                "url_pattern": "",
                "titulo_dom": tela.get("nome", "").lower(),
                "iframes": "",
                "estado_aria": "",
                "elementos_dom": "|".join([
                    el.get("seletor_css", "")
                    for el in tela.get("elementos_chave", [])
                    if el.get("seletor_css") and not el.get("iframe_hint")
                ]),
            }

            # Extrai iframes dos elementos
            iframes = set()
            for el in tela.get("elementos_chave", []):
                if el.get("iframe_hint"):
                    iframes.add(el["iframe_hint"])
            if iframes:
                sinais_aproximados["iframes"] = "|".join(sorted(iframes))

            acoes = tela.get("acoes_disponiveis_aqui", [])
            elementos = {
                el.get("nome", ""): {
                    "seletor_css": el.get("seletor_css", ""),
                    "iframe_hint": el.get("iframe_hint"),
                    "descricao": el.get("descricao", ""),
                }
                for el in tela.get("elementos_chave", [])
            }

            # Só registra se ainda não existe (não sobrescreve sinais DOM reais)
            try:
                with sqlite3.connect(DB_PATH) as c:
                    existe = c.execute(
                        "SELECT tela_id FROM telas_conhecidas WHERE tela_id=?", (tela_id,)
                    ).fetchone()
                    if not existe:
                        c.execute("""
                            INSERT INTO telas_conhecidas
                                (tela_id, nome_descritivo, sinais_json,
                                 descricao_gemini, acoes_disponiveis, elementos_chave, hits)
                            VALUES (?,?,?,?,?,?,0)
                        """, (
                            tela_id,
                            tela.get("nome", tela_id),
                            json.dumps(sinais_aproximados),
                            tela.get("como_identificar", ""),
                            json.dumps(acoes),
                            json.dumps(elementos),
                        ))
                        logger.info(f"[Fingerprint] Pré-carregado do schema: '{tela_id}'")
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"[Fingerprint] Erro ao carregar schema: {e}")


# ══════════════════════════════════════════════════════════════════
# UTILITÁRIO DE DIAGNÓSTICO
# ══════════════════════════════════════════════════════════════════

def listar_telas_conhecidas() -> list[dict]:
    """Lista todas as telas conhecidas com estatísticas. Útil para debug."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            c.row_factory = sqlite3.Row
            rows = c.execute(
                "SELECT tela_id, nome_descritivo, hits, ultima_vista FROM telas_conhecidas ORDER BY hits DESC"
            ).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []

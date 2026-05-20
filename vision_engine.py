"""
vision_engine.py — Motor de localização e execução de ações no browser.

Filosofia: cascata de estratégias do mais barato ao mais caro.
Cada camada só é acionada se a anterior falhar completamente.

Camadas de Resiliência:
  0    Brain (Memória SQLite Permanente - Auto-Cura e Zero-Touch)
  0.5  Menu de contexto ativo
  1    Foco nativo / active element (campos de digitação inline e novas pastas)
  1.5  Heurísticas Senior X (Ícones mudos como Home, Lixeira, etc)
  1_T  Template Matching visual (screenshot_elemento vs tela atual)
  2_S  Sniper semântico — 15+ seletores Playwright nativos (getByRole, getByLabel…)
       [FIX] Candidatos CSS posicionais verificam identidade com match exato
  3    Seletor hint original (se não for frágil)
       [FIX] Verificação de identidade com match exato para seletores posicionais
  3.5  Coordenadas capturadas da gravação (corrigidas por scroll) ← MOVIDO de Camada 2
       [FIX] Match exato na verificação de identidade — elimina falsos positivos
  4    Busca em todos os frames da página (sem depender do hint de iframe)
  5    Gemini Vision — screenshot atual + referência da gravação

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
import io
import json
import logging
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image as _PILImage
from playwright.async_api import Frame, Page
from som_annotator import get_som_boxes

from contracts.capture_adapter import get_capture_adapter, SeniorXAdapter

load_dotenv()

logger = logging.getLogger(__name__)

# ── Cache do adapter ativo (lazy init na primeira chamada) ────────────────
# Evita overhead de I/O repetido em get_capture_adapter() a cada passo.
_adapter_cache: object = None  # será preenchido na primeira chamada
_adapter_logado: bool = False  # flag para logar apenas uma vez por sessão


def _obter_adapter_cached():
    """Retorna o adapter ativo, cacheando na primeira chamada."""
    global _adapter_cache
    if _adapter_cache is None:
        _adapter_cache = get_capture_adapter()
    return _adapter_cache


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

# ── Última camada vencedora (para HITL overlay) ──────────────────────────────
# Atualizado por _registrar_estrategia_vencedora() após cada localização bem-sucedida.
# Permite que o validator_hitl consulte qual camada resolveu a última ação sem
# precisar acessar o banco de dados.
_ultima_camada_vencedora: str = ""


def obter_ultima_camada_vencedora() -> str:
    """Retorna o nome amigável da última camada que localizou um elemento com sucesso.

    Mapeamento interno → nome exibido no overlay HITL:
      0_brain             → Brain
      0_brain_coords      → Brain (coords)
      0.5_menu_ctx        → Menu Contexto
      1_foco_nativo       → Foco Nativo
      1.5_heuristica_seniorx → Heurística Senior X
      1_template_matching → Template Matching
      2_sniper            → Sniper
      3_hint_original     → Seletor Hint
      3.5_coords_capturadas → Coords Capturadas
      4_todos_frames      → Busca Frames
      5_gemini_vision     → Gemini Vision
    """
    global _ultima_camada_vencedora
    mapa = {
        "0_brain": "Brain",
        "0_brain_coords": "Brain (coords)",
        "0.5_menu_ctx": "Menu Contexto",
        "1_foco_nativo": "Foco Nativo",
        "1.5_heuristica_seniorx": "Heurística Senior X",
        "1_template_matching": "Template Matching",
        "2_sniper": "Sniper",
        "3_hint_original": "Seletor Hint",
        "3.5_coords_capturadas": "Coords Capturadas",
        "4_todos_frames": "Busca Frames",
        "5_gemini_vision": "Gemini Vision",
    }
    return mapa.get(_ultima_camada_vencedora, _ultima_camada_vencedora or "—")


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
            # Migração idempotente: adiciona coluna de timestamp granular (Req 5.1, 5.4)
            try:
                conn.execute(
                    "ALTER TABLE telemetria_camadas ADD COLUMN ultima_atualizacao_ts INTEGER"
                )
            except Exception:
                pass  # coluna já existe

            # Tabela de telemetria granular por execução (Req 5.1, 5.4, 10.4)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetria_execucoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camada TEXT NOT NULL,
                    acertou INTEGER NOT NULL,
                    intencao_semantica TEXT,
                    ts INTEGER NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tel_exec_ts ON telemetria_execucoes(ts)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tel_exec_camada ON telemetria_execucoes(camada)"
            )
            # TTL: remove memórias não usadas há mais de 90 dias (Fase 2.1)
            # Memórias com hitl_corrigido=1 NUNCA são removidas pela limpeza automática
            # (Requisito 7.4 — proteção de correções do analista)
            conn.execute("""
                DELETE FROM memoria_semantica
                WHERE ultima_atualizacao < datetime('now', '-90 days')
                  AND hits < 2
                  AND (hitl_corrigido IS NULL OR hitl_corrigido = 0)
            """)
            # [FIX] Invalida seletores posicionais memorizados — eles causam falsos
            # positivos porque :nth-child, :nth-of-type e IDs numéricos são frágeis
            # e podem apontar para elementos diferentes em cada execução.
            # Preserva a entrada (intencao, hits) mas limpa o seletor posicional,
            # forçando o sistema a redescobrir um seletor semântico estável.
            # Padrões: :nth-child(N), :nth-of-type(N), #word123 (exceto checkboxes PrimeNG)
            conn.execute("""
                UPDATE memoria_semantica
                SET seletor = NULL
                WHERE seletor IS NOT NULL
                  AND (
                    seletor LIKE '%:nth-child(%'
                    OR seletor LIKE '%:nth-of-type(%'
                  )
                  AND seletor NOT LIKE '%.ui-chkbox%'
                  AND seletor NOT LIKE '%p-checkbox%'
                  AND (hitl_corrigido IS NULL OR hitl_corrigido = 0)
            """)
            # View unificada de telemetria — idempotente (CREATE VIEW IF NOT EXISTS)
            conn.execute("""
                CREATE VIEW IF NOT EXISTS v_telemetria_unificada AS
                SELECT
                    tc.camada,
                    tc.acertos                                                    AS acertos_total,
                    tc.falhas                                                     AS falhas_total,
                    CASE
                        WHEN (tc.acertos + tc.falhas) > 0
                        THEN CAST(tc.acertos AS REAL) / (tc.acertos + tc.falhas)
                        ELSE NULL
                    END                                                           AS taxa_sucesso,
                    tc.ultima_atualizacao_ts                                      AS ultima_execucao_ts
                FROM telemetria_camadas tc
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


def _registrar_telemetria(camada: str, acertou: bool, intencao_semantica: str = "") -> None:
    """Registra acerto/falha por camada e emite logs de observabilidade.

    - Emite INFO com estratégia e resultado (Requisito 1.4.1).
    - Emite WARNING quando taxa de sucesso acumulada cair abaixo de 60% (Requisito 1.4.3).
    - Insere registro granular em telemetria_execucoes (Requisitos 5.1, 5.2, 5.3, 9.1).
    - Usa sqlite3.connect(timeout=5) para lidar com SQLite lock.
    - Falha de escrita é tratada com logger.warning silencioso — nunca interrompe a execução.
    """
    resultado_str = "sucesso" if acertou else "falha"
    logger.info(f"   [Telemetria] camada={camada} resultado={resultado_str}")

    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            ts_agora = int(time.time() * 1000)

            # 1. Atualiza contadores agregados na tabela existente (sem breaking changes)
            conn.execute("""
                INSERT INTO telemetria_camadas (camada, acertos, falhas, ultima_atualizacao_ts)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(camada) DO UPDATE SET
                    acertos = acertos + ?,
                    falhas  = falhas  + ?,
                    ultima_atualizacao = CURRENT_TIMESTAMP,
                    ultima_atualizacao_ts = ?
            """, (
                camada,
                1 if acertou else 0,
                0 if acertou else 1,
                ts_agora,
                1 if acertou else 0,
                0 if acertou else 1,
                ts_agora,
            ))

            # 2. Insere registro granular por execução (Requisitos 5.1, 10.4)
            conn.execute(
                "INSERT INTO telemetria_execucoes (camada, acertou, intencao_semantica, ts) VALUES (?, ?, ?, ?)",
                (camada, 1 if acertou else 0, intencao_semantica, ts_agora)
            )

            # 3. Verifica taxa de sucesso acumulada — alerta se < 60% (Requisito 1.4.3)
            row = conn.execute(
                "SELECT acertos, falhas FROM telemetria_camadas WHERE camada = ?", (camada,)
            ).fetchone()
            if row:
                total = row[0] + row[1]
                if total >= 5:  # mínimo de amostras para evitar falso-positivo no início
                    taxa = row[0] / total
                    if taxa < 0.60:
                        logger.warning(
                            f"[Telemetria] Taxa de sucesso da camada '{camada}' abaixo de 60%: "
                            f"{taxa:.1%} ({row[0]} acertos / {total} tentativas)"
                        )
    except Exception as e:
        logger.warning(f"[Telemetria] Falha ao registrar telemetria para camada '{camada}': {e}")


def _calcular_taxa_hitl_1h() -> Optional[float]:
    """Calcula a taxa de HITL (falha_total / total_acoes) na janela deslizante de 1 hora.

    Retorna None se houver menos de 5 ações no período (dados insuficientes).
    Requisitos: 9.1, 9.2, 9.5
    """
    try:
        ts_1h_atras = int(time.time() * 1000) - 3_600_000
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            total_acoes = conn.execute(
                "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ?",
                (ts_1h_atras,)
            ).fetchone()[0]
            if total_acoes < 5:
                return None
            total_falhas = conn.execute(
                "SELECT COUNT(*) FROM telemetria_execucoes WHERE ts >= ? AND camada = 'falha_total'",
                (ts_1h_atras,)
            ).fetchone()[0]
            return total_falhas / total_acoes
    except Exception as e:
        logger.warning(f"[HITL] Falha ao calcular taxa_hitl_1h: {e}")
        return None


def _registrar_estrategia_vencedora(intencao: str, camada: str) -> None:
    """Registra a estratégia vencedora no Brain após localização bem-sucedida (Requisito 1.4.4).

    Atualiza o campo `ultima_estrategia_vencedora` em `memoria_semantica` para que o
    self-healing futuro saiba qual camada resolveu a intenção mais recentemente.
    A operação é best-effort — falha silenciosa para não interromper a execução.
    """
    global _ultima_camada_vencedora
    _ultima_camada_vencedora = camada

    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Migração segura: garante que a coluna existe antes de usá-la
            try:
                conn.execute(
                    "ALTER TABLE memoria_semantica ADD COLUMN ultima_estrategia_vencedora TEXT"
                )
            except Exception:
                pass  # coluna já existe

            conn.execute("""
                UPDATE memoria_semantica
                SET ultima_estrategia_vencedora = ?,
                    ultima_atualizacao = CURRENT_TIMESTAMP
                WHERE hash_intencao = ?
            """, (camada, chave))
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


def obter_relatorio_telemetria() -> dict:
    """
    Consulta v_telemetria_unificada e retorna métricas consolidadas da cascata.

    Retorno em caso de sucesso:
    {
        "camadas": [
            {"camada": "0_brain", "acertos_total": 42, "falhas_total": 3,
             "taxa_sucesso": 0.933, "ultima_execucao_ts": 1718000000000},
            ...
        ],
        "taxa_hitl_1h": 0.05  # ou None se dados insuficientes
    }

    Retorno em caso de erro:
    {"camadas": [], "erro": "<mensagem>"}
    """
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM v_telemetria_unificada ORDER BY camada"
            ).fetchall()
            camadas = [dict(r) for r in rows]
        taxa_hitl = _calcular_taxa_hitl_1h()
        return {"camadas": camadas, "taxa_hitl_1h": taxa_hitl}
    except Exception as e:
        logger.warning(f"[Telemetria] obter_relatorio_telemetria falhou: {e}")
        return {"camadas": [], "erro": str(e)}


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
    hitl_corrigido: bool = False,
):
    chave      = _chave_cache(intencao)
    coords_str = json.dumps(coords) if coords else None

    # Descarta seletores muito vagos — aceita prefixos Angular/PrimeNG e :has-text(
    _PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")
    if seletor and not seletor.startswith(_PREFIXOS_VALIDOS) and ":has-text(" not in seletor:
        seletor = None

    # [FIX] Não memoriza seletores posicionais — eles são frágeis e causam falsos
    # positivos no Brain em execuções futuras. Seletores com :nth-child, :nth-of-type
    # ou IDs numéricos não devem ser reutilizados como memória de longo prazo.
    if seletor and _contem_indice_posicional(seletor):
        logger.debug(f"[Brain] Seletor posicional descartado (não memorizado): {seletor[:60]}")
        seletor = None

    # [FIX] Não memoriza seletores text= com texto muito curto (1-2 chars) ou puramente numérico.
    # Ex: text="6", text="1", text="2" são ambíguos — encontram qualquer elemento com esse
    # número na página (ex: "2026" contém "6"). O executor deve redescobrir via Sniper/Gemini.
    if seletor and seletor.startswith("text="):
        _texto_seletor = seletor[5:].strip('"').strip("'").strip()
        if len(_texto_seletor) <= 2 or _texto_seletor.isdigit():
            logger.debug(f"[Brain] Seletor text= com texto curto/numérico descartado (não memorizado): {seletor[:60]}")
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
                if hitl_corrigido:
                    query += ", hitl_corrigido = 1"; 
                query += " WHERE hash_intencao = ?"; params.append(chave)
                conn.execute(query, params)
            else:
                conn.execute("""
                    INSERT INTO memoria_semantica
                        (hash_intencao, intencao, seletor, coords, iframe, hits, falhas_consecutivas, hitl_corrigido)
                    VALUES (?, ?, ?, ?, ?, 1, 0, ?)
                """, (chave, intencao, seletor, coords_str, iframe, 1 if hitl_corrigido else 0))
    except Exception as e:
        logger.error(f"Erro ao salvar no Brain DB: {e}")


def _registrar_falha_cache(intencao: str):
    chave = _chave_cache(intencao)
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Proteção HITL: memórias corrigidas pelo analista nunca são invalidadas
            row = conn.execute(
                "SELECT hitl_corrigido FROM memoria_semantica WHERE hash_intencao = ?",
                (chave,)
            ).fetchone()
            if row and row[0] == 1:
                logger.debug(f"[Brain] Falha ignorada para memória HITL-corrigida: {intencao[:60]}")
                return
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
    # Seletores PrimeNG compostos com identificador são resilientes
    if any(p in seletor for p in (
        "p-autocomplete", "p-calendar", "p-dropdown", "p-multiselect",
        "p-spinner", "p-splitbutton", "p-inputswitch", "ui-autocomplete",
        "ui-calendar", "ui-dropdown", "button-addon"
    )):
        return False
    tag = seletor.strip().split(":")[0].split("[")[0].split(".")[0].split(">")[0].strip()
    return tag in _TAGS_FRAGEIS


def _e_label_generico(label: str) -> bool:
    """
    Detecta se label_curto é genérico/cosmético e não deve ser priorizado.
    
    Retorna True se o label é genérico (tag HTML, texto PrimeNG cosmético, muito curto).
    Retorna False se o label é específico e pode ser usado para localização.
    
    Validações:
    - Tags HTML genéricas (button, input, span, div, etc.)
    - Textos PrimeNG cosmético internos (ui-btn, ui-button-text, p-button, etc.)
    - Textos muito curtos (< 3 caracteres) ou vazios
    
    Validates: Requirements 2.1, 2.4
    """
    if not label or not label.strip():
        return True
    
    label_lower = label.strip().lower()
    
    # Tags HTML genéricas
    if label_lower in _TAGS_FRAGEIS:
        return True
    
    # Textos PrimeNG cosmético internos
    TEXTOS_PRIMENG_COSMETICOS = {
        "ui-btn", "ui-button", "ui-button-text", "ui-clickable",
        "ui-widget", "ui-state-default", "p-button", "p-element"
    }
    if label_lower in TEXTOS_PRIMENG_COSMETICOS:
        return True
    
    # Textos muito curtos ou genéricos
    if len(label.strip()) < 3:
        return True
    
    return False


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

    EXCEÇÃO: seletores compostos com .ui-chkbox (checkboxes PrimeNG) como
    item#file_8 .ui-chkbox .ui-chkbox-box NÃO são posicionais — o ID é do
    arquivo/item real, não uma posição de lista.
    """
    if not seletor:
        return False
    # Seletores de checkbox PrimeNG com ID de arquivo são legítimos — não posicionais
    if ".ui-chkbox" in seletor or "p-checkbox" in seletor:
        return False
    padroes = [
        r"#\w*\d+(?![^'\"]*['\"])",   # #file_1, #row3 — mas não dentro de ['...']
        r":nth-child\(\d+\)",
        r":nth-of-type\(\d+\)",
        r"item#\w+\d+",
    ]
    return any(re.search(p, seletor) for p in padroes)


def _e_candidato_posicional(cand: "TentativaLocalizacao") -> bool:
    """
    Retorna True se o candidato usa seletor CSS posicional instável.

    Candidatos posicionais (`:nth-child`, `:nth-of-type`, `#id-numerico`) são
    frágeis por natureza — podem apontar para o elemento errado quando o DOM
    muda. O Sniper deve verificar identidade antes de aceitar esses candidatos.

    Reutiliza `_contem_indice_posicional()` para detecção consistente.

    [FIX] Usado na Task 4 para adicionar verificação de identidade no Sniper
    para candidatos CSS posicionais.

    Validates: Requirements 2.3 (bugfix.md coordenadas-capturadas-baixa-confiabilidade-fix)
    """
    return bool(cand.seletor and _contem_indice_posicional(cand.seletor))


async def _verificar_identidade_elemento(locator, label_curto: str) -> bool:
    """
    Verifica se o elemento (ou seu pai imediato) tem o texto EXATO do label_curto.

    Estratégia:
      1. Tenta inner_text() do próprio elemento.
      2. Se não bater, tenta inner_text() do elemento pai ("..").
      3. Retorna True se qualquer um CORRESPONDER EXATAMENTE ao label_curto
         (case-insensitive, strip). Match exato — não aceita substrings.
      4. Retorna True em caso de exceção APENAS se nenhum texto foi lido com sucesso
         (fail-open — não bloquear quando texto não é acessível, ex: checkboxes sem
         texto visível). Se o texto foi lido mas não bate, retorna False.

    [FIX] Substituído substring matching (needle in texto) por match exato
    (texto_norm == needle) para eliminar falsos positivos onde label_curto é
    apenas parte de um texto maior (ex: "1" in "EMPRESA 1" → True era falso positivo).

    Validates: Requirements 2.2, 2.3 (bugfix.md coordenadas-capturadas-baixa-confiabilidade-fix)
    """
    if not label_curto:
        return True
    needle = label_curto.strip().lower()
    texto_lido = False

    try:
        texto = await locator.inner_text(timeout=1000)
        texto_lido = True
        # [FIX] Match exato — não aceita substrings
        if texto.strip().lower() == needle:
            return True
    except Exception:
        return True  # fail-open: não conseguiu ler texto, não bloquear

    # Texto foi lido mas não bateu — tenta o pai
    try:
        texto_pai = await locator.locator("..").inner_text(timeout=1000)
        texto_lido = True
        # [FIX] Match exato no pai também
        if texto_pai.strip().lower() == needle:
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

    # ── Candidato especial: checkbox PrimeNG/Angular ──────────────────────────
    # O seletor capturado pelo JS do capture para checkboxes tem o formato:
    #   item:has-text("Nome") .ui-chkbox .ui-chkbox-box   (ideal — com texto)
    #   item#file_8 .ui-chkbox .ui-chkbox-box             (fallback — com ID)
    # Ambos são seletores compostos legítimos e devem ser tentados primeiro.
    if seletor_hint and (".ui-chkbox" in seletor_hint or "p-checkbox" in seletor_hint):
        candidatos.append(TentativaLocalizacao(
            seletor=seletor_hint, iframe_hint=iframe_hint,
            descricao=f"checkbox PrimeNG hint '{seletor_hint[:60]}'",
        ))
        # Se o seletor usa ID (fallback), também tenta a variante :has-text com label
        if label_curto and "#file_" in seletor_hint:
            # Extrai a parte do seletor após o ID para reusar (ex: .ui-chkbox .ui-chkbox-box)
            partes = seletor_hint.split(" ", 1)
            sufixo = partes[1] if len(partes) > 1 else ".ui-chkbox .ui-chkbox-box"
            # Tenta com o label da pasta como :has-text
            label_clean = label_curto.replace("'", "").replace('"', "")[:40]
            candidatos.append(TentativaLocalizacao(
                seletor=f'item:has-text("{label_clean}") {sufixo}',
                iframe_hint=iframe_hint,
                descricao=f"checkbox has-text '{label_clean}'",
            ))

    # ── Candidato especial: botão em dialog de confirmação PrimeNG ────────────
    # Botões "Sim", "Confirmar", "Não", "Cancelar" dentro de p-confirmDialog
    # têm IDs dinâmicos (s-button-5, etc.) que mudam a cada renderização.
    # O Sniper deve buscar dentro do escopo do dialog antes de tentar o DOM geral.
    _LABELS_CONFIRMACAO = {"sim", "não", "nao", "confirmar", "cancelar", "ok", "yes", "no", "cancel"}
    if label_curto and label_curto.strip().lower() in _LABELS_CONFIRMACAO:
        _SELETORES_DIALOG = [
            "p-confirmdialog", "p-dialog", ".p-dialog", ".ui-dialog",
            "[role='dialog']", ".p-confirm-dialog",
            # Senior X / GED usa s-dialog e ui-confirmdialog
            "s-dialog", ".ui-confirmdialog", ".ui-dialog-content",
            ".p-dialog-content",
        ]
        for _sel_dialog in _SELETORES_DIALOG:
            candidatos.append(TentativaLocalizacao(
                seletor=f"{_sel_dialog} button:has-text('{label_curto}')",
                iframe_hint=iframe_hint,
                descricao=f"dialog button '{label_curto}' em {_sel_dialog}",
            ))
            candidatos.append(TentativaLocalizacao(
                seletor=f"{_sel_dialog} span:has-text('{label_curto}')",
                iframe_hint=iframe_hint,
                descricao=f"dialog span '{label_curto}' em {_sel_dialog}",
            ))

    # ── Candidato especial: PrimeNG composite widgets ─────────────────────────
    # Quando o capture envia um seletor composto para widgets PrimeNG,
    # ele já ancorou no componente correto e apontou para o sub-elemento.
    if seletor_hint and any(p in seletor_hint for p in (
        "p-autocomplete", "p-calendar", "p-dropdown", "p-multiselect",
        "p-spinner", "p-splitbutton", "p-inputswitch", "p-chips", "p-fileupload",
        "ui-autocomplete", "ui-calendar", "ui-dropdown", "button-addon"
    )):
        # 1. O próprio hint composto é a melhor aposta
        candidatos.append(TentativaLocalizacao(
            seletor=seletor_hint, iframe_hint=iframe_hint,
            descricao=f"PrimeNG composite hint '{seletor_hint[:40]}'",
        ))
        
        # 2. Fallback resiliente: tenta usar o sibling combinator (~) caso
        # o DOM mude a estrutura pai-filho e o botão seja irmão do input
        try:
            partes = seletor_hint.split(" ", 1)
            if len(partes) == 2:
                ancora, sufixo = partes
                match_name = re.search(r"\[name=['\"]([^'\"]+)['\"]\]", ancora)
                match_id = re.search(r"\[id=['\"]([^'\"]+)['\"]\]", ancora)
                if match_name:
                    candidatos.append(TentativaLocalizacao(
                        seletor=f"input[name='{match_name.group(1)}'] ~ {sufixo}", iframe_hint=iframe_hint,
                        descricao=f"PrimeNG sibling fallback name",
                    ))
                elif match_id:
                    candidatos.append(TentativaLocalizacao(
                        seletor=f"input[id='{match_id.group(1)}'] ~ {sufixo}", iframe_hint=iframe_hint,
                        descricao=f"PrimeNG sibling fallback id",
                    ))
        except Exception:
            pass

    # ── NOVO: Candidato de alta prioridade para seletor_hint ──────────────────
    # Quando seletor_hint é válido, não-frágil, e label_curto é genérico,
    # adiciona seletor_hint como candidato de alta prioridade
    # Validates: Requirements 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4
    if (seletor_hint and 
        not _e_seletor_fragil(seletor_hint) and 
        _e_label_generico(label_curto)):
        
        logger.debug(f"[Sniper] Adicionando seletor_hint como alta prioridade: {seletor_hint[:60]}")
        candidatos.append(TentativaLocalizacao(
            seletor=seletor_hint,
            iframe_hint=iframe_hint,
            descricao=f"seletor_hint priority '{seletor_hint[:60]}'",
        ))

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

    # ── Fingerprint estável (formato "fp:tipo=valor") ─────────────────────
    # Gerado pelo radar_script.js v2.2.0+ para iframes com atributos estáveis.
    # Estratégias em ordem de preferência: name, id, src (path), title, index.
    if iframe_hint.startswith("fp:"):
        fp_type, _, fp_value = iframe_hint[3:].partition("=")

        # Índice ordinal — usa diretamente
        if fp_type == "index":
            try:
                idx = int(fp_value)
                frames = page.frames
                if idx < len(frames):
                    return frames[idx]
            except (ValueError, IndexError):
                pass

        # Atributos do elemento <iframe> no DOM
        elif fp_type in ("name", "id", "title", "src"):
            attr_map = {
                "name":  f"iframe[name='{fp_value}']",
                "id":    f"iframe[id='{fp_value}']",
                "title": f"iframe[title='{fp_value}']",
                "src":   f"iframe[src*='{fp_value}']",
            }
            seletor_iframe = attr_map[fp_type]
            try:
                fl = page.frame_locator(seletor_iframe)
                await fl.locator("body").wait_for(state="attached", timeout=800)
                # Encontra o Frame object correspondente
                for frame in page.frames:
                    try:
                        frame_el = await frame.frame_element()
                        attr_val = await frame_el.get_attribute(fp_type)
                        if attr_val and fp_value in attr_val:
                            return frame
                    except Exception:
                        continue
            except Exception:
                pass

            # Fallback: busca por URL/name do frame
            for frame in page.frames:
                try:
                    if fp_value in (frame.name or "") or fp_value in (frame.url or ""):
                        return frame
                except Exception:
                    continue

        # Se fingerprint não resolveu, cai no fallback legado abaixo
        logger.debug(f"[iframe] Fingerprint '{iframe_hint}' não resolveu — tentando fallback legado")

    # ── Fallback legado: busca por name/url (formato antigo) ─────────────
    for seletor_iframe in [
        f"iframe[name='{iframe_hint}']", f"iframe[src*='{iframe_hint}']",
        f"iframe[id='{iframe_hint}']",   f"iframe[title*='{iframe_hint}']",
    ]:
        try:
            fl = page.frame_locator(seletor_iframe)
            await fl.locator("body").wait_for(state="attached", timeout=800)

            for frame in page.frames:
                try:
                    if iframe_hint in frame.url or iframe_hint in frame.name:
                        return frame
                except Exception:
                    continue
        except Exception:
            continue

    # Fallback final: itera frames diretamente
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


async def _scroll_para_area_esperada(
    page: Page,
    coords_relativas: Optional[dict],
    tipo_elemento: str = "",
    seletor_hint: str = "",
) -> int:
    try:
        # [FIX] Não faz scroll para elementos de navegação/menu/sidebar.
        # Esses elementos são sempre visíveis independente do scroll da página.
        # Coordenadas capturadas para menus frequentemente apontam para o centro
        # da tela (erro de captura), causando scroll desnecessário que quebra a execução.
        _TIPOS_SEM_SCROLL = {"menu_item", "navigation", "nav", "sidebar", "tab"}
        if tipo_elemento and tipo_elemento.lower() in _TIPOS_SEM_SCROLL:
            scroll_y = await page.evaluate("() => window.scrollY") or 0
            return int(scroll_y)

        # [FIX] Não faz scroll quando o seletor hint é um aria-label de menu
        # (ex: [aria-label='Grupo de menus GED']) — esses elementos são fixos na UI.
        if seletor_hint and "aria-label" in seletor_hint and any(
            kw in seletor_hint.lower() for kw in ("menu", "nav", "sidebar", "grupo")
        ):
            scroll_y = await page.evaluate("() => window.scrollY") or 0
            return int(scroll_y)

        if coords_relativas and coords_relativas.get("y_pct"):
            vp         = page.viewport_size or {"width": 1920, "height": 1080}
            altura_est = coords_relativas["y_pct"] * vp["height"] * 2
            if altura_est > vp["height"] * 0.8:
                scroll_atual = await page.evaluate("() => window.scrollY") or 0
                scroll_alvo  = max(0, int(altura_est - 300))
                delta_total  = scroll_alvo - scroll_atual

                if abs(delta_total) > 10:
                    # Scroll em passos de ~120px (equivale a ~1 tick de roda do mouse)
                    # com pausa entre cada passo para suavidade visual no vídeo.
                    # NOTA: mouse.wheel() não requer posição específica do cursor —
                    # o cursor permanece no último clique e só se move ao próximo alvo.
                    passo_px   = 120
                    n_passos   = max(1, abs(delta_total) // passo_px)
                    delta_passo = int(delta_total / n_passos)
                    for _ in range(n_passos):
                        await page.mouse.wheel(0, delta_passo)
                        await asyncio.sleep(0.06)
                    # Passo residual para acertar o alvo exato
                    scroll_pos = await page.evaluate("() => window.scrollY") or 0
                    residual   = scroll_alvo - scroll_pos
                    if abs(residual) > 5:
                        await page.mouse.wheel(0, residual)
                    await asyncio.sleep(0.2)

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
    Digita um valor com delay variável, simulando ritmo humano real.
    Usa keyboard.type com delay para suportar caracteres acentuados
    corretamente (como ã, ç, é, etc.).

    Delay base: 65ms por caractere.
    Variação aleatória: ±30ms por caractere (ruído natural).
    Pausa extra: 10% de chance de micro-pausa de 120-250ms
    (simula hesitação humana ao digitar).
    """
    import random

    # Calcula delay médio com variação aleatória
    delay = random.randint(45, 95)  # 45–95ms por caractere

    # Usa keyboard.type que suporta caracteres Unicode/acentuados
    await page.keyboard.type(valor, delay=delay)

    # micro-pausa ocasional para simular hesitação humana
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
        import os
        import tempfile
        nome_arquivo = valor if valor else "documento_treinamento.pdf"
        nome_arquivo = nome_arquivo.split("\\")[-1].split("/")[-1]

        tmp_path = os.path.join(tempfile.gettempdir(), nome_arquivo)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(f"{nome_arquivo.upper()}\n\nLorem ipsum dolor sit amet. Este documento é uma simulação.")

        await page.evaluate("""(nome) => {
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
                <p style="color:#00e5e5; font-size:22px; font-weight:bold; margin-top:20px; letter-spacing:1px;">Selecionando: ${nome}</p>
            `;
            document.body.appendChild(overlay);
            setTimeout(() => overlay.style.opacity = '1', 50);
        }""", nome_arquivo)

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
        # [FIX] Detecta se coordenadas são relativas (x_pct/y_pct) ou absolutas (x/y)
        if isinstance(coords, dict) and "x_pct" in coords and "y_pct" in coords:
            # Coordenadas relativas do Brain - converte para absolutas
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            x = int(coords["x_pct"] * vp["width"])
            y = int(coords["y_pct"] * vp["height"])
            logger.debug(f"[Coords] Convertendo relativas para absolutas: {coords['x_pct']:.4f}, {coords['y_pct']:.4f} → {x}, {y}")
        else:
            # Coordenadas absolutas (legado ou Gemini Vision)
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


# ── Template Matching Visual ──────────────────────────────────
# Componente Template_Matcher: matching visual via Pillow + NumPy
# sem dependência de OpenCV. Usado como Layer 1_T na cascata.
# ──────────────────────────────────────────────────────────────


def _resolver_screenshot_ref_tm(path_ou_b64: str) -> Optional[bytes]:
    """
    Resolve um screenshot de referência para bytes, suportando:
      - Base64 JPEG (começa com '/9j/')
      - Base64 PNG (começa com 'iVBOR')
      - Path de arquivo em disco

    Nunca lança exceção — retorna None em caso de falha.
    """
    if not path_ou_b64:
        return None
    # Detecta base64 JPEG ou PNG pelos magic bytes
    if path_ou_b64.startswith("/9j/") or path_ou_b64.startswith("iVBOR"):
        try:
            return base64.b64decode(path_ou_b64)
        except Exception as exc:
            logger.warning(f"[TemplateMatcher] Falha ao decodificar base64: {exc}")
            return None
    # Trata como path de arquivo
    if os.path.exists(path_ou_b64):
        try:
            with open(path_ou_b64, "rb") as f:
                return f.read()
        except Exception as exc:
            logger.warning(f"[TemplateMatcher] Falha ao ler arquivo '{path_ou_b64}': {exc}")
            return None
    logger.warning(f"[TemplateMatcher] Arquivo não encontrado: '{path_ou_b64}'")
    return None


def _ncc_score(template: np.ndarray, region: np.ndarray) -> float:
    """Calcula o score NCC (Normalized Cross-Correlation) entre template e região."""
    t = template.astype(np.float32)
    r = region.astype(np.float32)
    t_norm = (t - t.mean()) / (t.std() + 1e-8)
    r_norm = (r - r.mean()) / (r.std() + 1e-8)
    return float(np.sum(t_norm * r_norm) / t_norm.size)


def _sliding_ncc(template_arr: np.ndarray, tela_arr: np.ndarray):
    """
    Sliding window NCC — retorna (best_score, best_y, best_x).
    Usa step adaptativo para performance sem OpenCV.
    """
    th, tw = template_arr.shape[:2]
    sh, sw = tela_arr.shape[:2]
    best_score, best_y, best_x = -1.0, 0, 0
    step = max(1, min(th, tw) // 4)  # step adaptativo
    for y in range(0, sh - th + 1, step):
        for x in range(0, sw - tw + 1, step):
            region = tela_arr[y:y + th, x:x + tw]
            score = _ncc_score(template_arr, region)
            if score > best_score:
                best_score, best_y, best_x = score, y, x
    return best_score, best_y, best_x


def template_match(
    referencia: bytes,
    tela_atual: bytes,
    coords_relativas: Optional[dict],
    viewport: dict,
    threshold: float = 0.80,
) -> Optional[dict]:
    """
    Realiza template matching visual entre o screenshot de referência e a tela atual.

    Estratégia:
      1. Converte referencia e tela_atual para arrays NumPy RGB via Pillow.
      2. Se coords_relativas fornecido, busca primeiro na janela ±20% do viewport.
      3. Se score regional >= threshold, retorna coords absolutas do centro do match.
      4. Caso contrário, busca na tela inteira.
      5. Retorna None se score < threshold em ambas as buscas.

    Retorna {"x": int, "y": int, "score": float} ou None.
    """
    try:
        # Converte bytes → arrays NumPy RGB
        ref_img = _PILImage.open(io.BytesIO(referencia)).convert("RGB")
        tela_img = _PILImage.open(io.BytesIO(tela_atual)).convert("RGB")
        ref_arr = np.array(ref_img)
        tela_arr = np.array(tela_img)

        th, tw = ref_arr.shape[:2]
        sh, sw = tela_arr.shape[:2]

        # Template maior que a tela — impossível fazer match
        if th > sh or tw > sw:
            logger.warning(
                f"[TemplateMatcher] Template ({tw}x{th}) maior que tela ({sw}x{sh}) — pulando"
            )
            return None

        vp_w = viewport.get("width", 1920)
        vp_h = viewport.get("height", 1080)

        # ── Busca regional (±20% do viewport ao redor das coords) ──
        if coords_relativas and coords_relativas.get("x_pct") is not None:
            cx = int(coords_relativas["x_pct"] * vp_w)
            cy = int(coords_relativas["y_pct"] * vp_h)
            margin_x = int(vp_w * 0.20)
            margin_y = int(vp_h * 0.20)

            rx1 = max(0, cx - margin_x)
            ry1 = max(0, cy - margin_y)
            rx2 = min(sw, cx + margin_x)
            ry2 = min(sh, cy + margin_y)

            # Região deve ser pelo menos do tamanho do template
            if (rx2 - rx1) >= tw and (ry2 - ry1) >= th:
                regiao = tela_arr[ry1:ry2, rx1:rx2]
                score_r, by_r, bx_r = _sliding_ncc(ref_arr, regiao)
                if score_r >= threshold:
                    abs_x = rx1 + bx_r + tw // 2
                    abs_y = ry1 + by_r + th // 2
                    logger.info(
                        f"[TemplateMatcher] Match regional: score={score_r:.3f} "
                        f"em ({abs_x}, {abs_y})"
                    )
                    return {"x": int(abs_x), "y": int(abs_y), "score": float(score_r)}

        # ── Busca na tela inteira ──
        score_g, by_g, bx_g = _sliding_ncc(ref_arr, tela_arr)
        if score_g >= threshold:
            abs_x = bx_g + tw // 2
            abs_y = by_g + th // 2
            logger.info(
                f"[TemplateMatcher] Match global: score={score_g:.3f} "
                f"em ({abs_x}, {abs_y})"
            )
            return {"x": int(abs_x), "y": int(abs_y), "score": float(score_g)}

        logger.debug(f"[TemplateMatcher] Score abaixo do threshold ({score_g:.3f} < {threshold})")
        return None

    except Exception as exc:
        logger.warning(f"[TemplateMatcher] Erro no cálculo de matching: {exc}")
        return None


# ──────────────────────────────────────────────────────────────
# DETECÇÃO DE MENU DE CONTEXTO ATIVO (CAMADA 0.5)
# ──────────────────────────────────────────────────────────────
async def _detectar_menu_contexto_ativo(page, iframe_hint: str | None = None, timeout_ms: int = 150) -> object | None:
    """
    Verifica se um menu de contexto está visível como overlay na página ou em frames.
    Retorna o Locator do primeiro menu visível encontrado, ou None.

    timeout_ms=150 para o caminho feliz (sem menu ativo) — retorna rápido.
    timeout_ms=2000 quando chamado após clique_direito — aguarda animação de entrada
                    e busca em todos os frames.
    """
    SELETOR_MENU = (
        ".ngx-contextmenu, "
        ".cdk-overlay-pane.ngx-contextmenu, "
        "[class*='ngx-contextmenu'], "
        ".p-contextmenu, "
        "[role='menu']"
    )

    # 1. Busca no DOM principal
    try:
        locator = page.locator(SELETOR_MENU).first
        await locator.wait_for(state="visible", timeout=timeout_ms)
        return locator
    except Exception:
        pass

    # 2. Quando timeout maior (após clique_direito), busca em todos os frames
    if timeout_ms > 150:
        for frame in page.frames:
            if frame == page.main_frame:
                continue
            try:
                locator = frame.locator(SELETOR_MENU).first
                await locator.wait_for(state="visible", timeout=timeout_ms)
                logger.debug(f"[MENU-CTX] Menu encontrado em frame: {frame.name or frame.url[:40]}")
                return locator
            except Exception:
                continue

    return None


async def _buscar_em_escopo_menu(menu_locator, label_curto: str, page=None) -> str | None:
    """
    Localiza e clica em um item dentro do container do menu de contexto ngx-contextmenu.

    O ngx-contextmenu (Angular CDK Overlay) renderiza itens como:
      <ul class="ngx-menu-content">
        <li><a><em class="fa ..."></em> Excluir</a></li>
      </ul>

    Os itens NÃO têm role="menuitem" — são <li>/<a> simples com texto misto
    (ícone + texto). Por isso usamos :has-text() escopado ao container.
    """
    label_safe = label_curto.replace("'", "\\'")

    estrategias = [
        # ngx-contextmenu: item <li> ou <a> com o texto (ignora ícones internos)
        ("li_has_text",   lambda: menu_locator.locator(f"li:has-text('{label_safe}')").first),
        ("a_has_text",    lambda: menu_locator.locator(f"a:has-text('{label_safe}')").first),
        # Fallback genérico: qualquer elemento visível com o texto exato
        ("text_exact",    lambda: menu_locator.get_by_text(label_curto, exact=True).first),
        # Último recurso: texto parcial
        ("has_text",      lambda: menu_locator.locator(f":has-text('{label_safe}')").last),
    ]
    for nome, fn in estrategias:
        try:
            el = fn()
            await el.wait_for(state="visible", timeout=1000)
            # Anima o cursor até o item do menu antes de clicar
            if page is not None:
                try:
                    box = await el.bounding_box(timeout=500)
                    if box:
                        cx = box["x"] + box["width"] / 2
                        cy = box["y"] + box["height"] / 2
                        from cursor_engine import mover_cursor_humanizado
                        await mover_cursor_humanizado(page, cx, cy)
                except Exception:
                    pass
            await el.click()
            return nome
        except Exception:
            continue
    return None


# ──────────────────────────────────────────────────────────────
# RESOLUÇÃO DE ELEMENTOS EM IFRAMES (BUGFIX: robot-element-location-failure)
# ──────────────────────────────────────────────────────────────
async def _resolver_elemento_em_iframe(
    page: Page, x: int, y: int, max_depth: int = 5
) -> tuple[dict, int, int, bool]:
    """
    Resolve recursivamente o elemento em coordenadas (x, y), detectando iframes.
    
    Quando elementFromPoint retorna um iframe, ajusta as coordenadas para o sistema
    de coordenadas do iframe e recursivamente busca o elemento interno.
    
    Args:
        page: Página Playwright
        x: Coordenada X absoluta no viewport
        y: Coordenada Y absoluta no viewport
        max_depth: Profundidade máxima de recursão (proteção contra loops infinitos)
    
    Returns:
        tuple[dict, int, int, bool]: (elemento_info, x_ajustado, y_ajustado, is_cross_origin)
        - elemento_info: Dicionário com informações do elemento (tagName, innerText, etc.)
        - x_ajustado: Coordenada X ajustada (relativa ao iframe se aplicável)
        - y_ajustado: Coordenada Y ajustada (relativa ao iframe se aplicável)
        - is_cross_origin: True se iframe cross-origin foi detectado (fail-open)
    
    Requisitos: 2.1, 2.2, 2.3
    """
    if max_depth <= 0:
        logger.warning(f"[iframe] Max depth atingido na resolução de iframes aninhados em ({x}, {y})")
        try:
            elemento = await page.evaluate(
                "([x, y]) => { const el = document.elementFromPoint(x, y); return el ? { tagName: el.tagName, innerText: el.innerText || '' } : null; }",
                [x, y]
            )
            return (elemento or {}, x, y, False)
        except Exception:
            return ({}, x, y, False)

    try:
        resultado = await page.evaluate("""
            ([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return {tipo: 'null'};
                
                if (el.tagName === 'IFRAME') {
                    const bbox = el.getBoundingClientRect();
                    return {
                        tipo: 'iframe',
                        left: bbox.left,
                        top: bbox.top,
                        src: el.src || '',
                        name: el.name || '',
                        innerText: el.innerText || 'iframe platform'
                    };
                }
                
                return {
                    tipo: 'elemento',
                    tagName: el.tagName,
                    innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                };
            }
        """, [x, y])

        if resultado['tipo'] == 'iframe':
            # Ajustar coordenadas para o sistema do iframe
            x_rel = int(x - resultado['left'])
            y_rel = int(y - resultado['top'])

            logger.info(f"[iframe] Detectado em ({x}, {y}), ajustando para ({x_rel}, {y_rel})")

            # Tentar acessar o iframe
            iframe_src = resultado.get('src', '')
            iframe_name = resultado.get('name', '')

            # Resolver o frame usando Playwright
            frame = None
            for f in page.frames:
                try:
                    if iframe_src and iframe_src in f.url:
                        frame = f
                        break
                    if iframe_name and iframe_name == f.name:
                        frame = f
                        break
                except Exception:
                    continue

            if not frame:
                # Cross-origin ou frame não encontrado
                logger.warning(f"[iframe] Cross-origin ou não acessível em ({x}, {y}) - aplicando fail-open")
                return (resultado, x, y, True)

            # Recursivamente resolver no contexto do iframe
            return await _resolver_elemento_em_iframe_frame(frame, x_rel, y_rel, max_depth - 1)

        else:
            # Elemento final encontrado (não é iframe)
            return (resultado, x, y, False)

    except Exception as exc:
        logger.warning(f"[iframe] Erro ao resolver elemento em ({x}, {y}): {exc}")
        return ({}, x, y, False)


async def _resolver_elemento_em_iframe_frame(
    frame, x: int, y: int, max_depth: int
) -> tuple[dict, int, int, bool]:
    """
    Versão da função _resolver_elemento_em_iframe para contexto de Frame.
    
    Implementa a mesma lógica de detecção recursiva de iframes, mas usando
    frame.evaluate em vez de page.evaluate.
    
    Args:
        frame: Frame Playwright
        x: Coordenada X relativa ao frame
        y: Coordenada Y relativa ao frame
        max_depth: Profundidade máxima de recursão
    
    Returns:
        tuple[dict, int, int, bool]: (elemento_info, x_ajustado, y_ajustado, is_cross_origin)
    
    Requisitos: 2.2, 2.3
    """
    if max_depth <= 0:
        logger.warning(f"[iframe] Max depth atingido na resolução de iframes aninhados (frame) em ({x}, {y})")
        try:
            elemento = await frame.evaluate(
                "([x, y]) => { const el = document.elementFromPoint(x, y); return el ? { tagName: el.tagName, innerText: el.innerText || '' } : null; }",
                [x, y]
            )
            return (elemento or {}, x, y, False)
        except Exception:
            return ({}, x, y, False)

    try:
        resultado = await frame.evaluate("""
            ([x, y]) => {
                const el = document.elementFromPoint(x, y);
                if (!el) return {tipo: 'null'};
                
                if (el.tagName === 'IFRAME') {
                    const bbox = el.getBoundingClientRect();
                    return {
                        tipo: 'iframe',
                        left: bbox.left,
                        top: bbox.top,
                        src: el.src || '',
                        name: el.name || '',
                        innerText: el.innerText || 'iframe platform'
                    };
                }
                
                return {
                    tipo: 'elemento',
                    tagName: el.tagName,
                    innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                };
            }
        """, [x, y])

        if resultado['tipo'] == 'iframe':
            # Ajustar coordenadas para o sistema do iframe aninhado
            x_rel = int(x - resultado['left'])
            y_rel = int(y - resultado['top'])

            logger.info(f"[iframe] Iframe aninhado detectado em ({x}, {y}), ajustando para ({x_rel}, {y_rel})")

            # Tentar acessar o iframe aninhado
            iframe_src = resultado.get('src', '')
            iframe_name = resultado.get('name', '')

            # Buscar frame aninhado
            nested_frame = None
            for f in frame.child_frames:
                try:
                    if iframe_src and iframe_src in f.url:
                        nested_frame = f
                        break
                    if iframe_name and iframe_name == f.name:
                        nested_frame = f
                        break
                except Exception:
                    continue

            if not nested_frame:
                # Cross-origin ou frame não encontrado
                logger.warning(f"[iframe] Iframe aninhado cross-origin ou não acessível em ({x}, {y}) - aplicando fail-open")
                return (resultado, x, y, True)

            # Recursivamente resolver no contexto do iframe aninhado
            return await _resolver_elemento_em_iframe_frame(nested_frame, x_rel, y_rel, max_depth - 1)

        else:
            # Elemento final encontrado (não é iframe)
            return (resultado, x, y, False)

    except Exception as exc:
        logger.warning(f"[iframe] Erro ao resolver elemento (frame) em ({x}, {y}): {exc}")
        return ({}, x, y, False)


async def _verificar_identidade_por_coordenadas(
    page: Page,
    x: int,
    y: int,
    label_curto: str,
    iframe_hint: Optional[str] = None
) -> tuple[bool, bool]:
    """
    Verifica identidade do elemento nas coordenadas (x, y) ANTES de executar o clique.
    
    Esta função implementa o fix para o bug de timing onde cliques eram executados
    ANTES da verificação de identidade. Agora a verificação acontece PRIMEIRO, e o
    clique só é executado se a identidade for confirmada.
    
    Args:
        page: Página Playwright
        x: Coordenada X absoluta no viewport
        y: Coordenada Y absoluta no viewport
        label_curto: Texto esperado para verificação de identidade
        iframe_hint: Hint opcional sobre qual iframe contém o elemento
    
    Returns:
        tuple[bool, bool]: (identidade_confirmada, is_cross_origin)
        - identidade_confirmada: True se identidade verificada OU fail-open aplicado
        - is_cross_origin: True se iframe cross-origin detectado (para logging)
    
    Fail-open cases (retorna True sem verificação):
        - label_curto vazio/None → retorna (True, False)
        - Exceção durante verificação → retorna (True, False)
        - Iframe cross-origin → retorna (True, True)
    
    Bug Fix: Requirements 2.2, 2.3, 2.4
    Preservation: Requirements 3.1, 3.2, 3.3
    """
    # Fail-open: se label_curto vazio, aceitar sem verificação
    if not label_curto:
        return (True, False)

    try:
        # Determinar se deve usar iframe_hint ou detecção automática
        usar_iframe_hint = (
            iframe_hint and
            iframe_hint not in ("Pagina Principal", "Página Principal", "iframe-cross-origin")
        )

        if usar_iframe_hint:
            logger.info(f"   [Coords Capturadas] Usando iframe_hint: '{iframe_hint}'")
            contexto = await _resolver_contexto(page, iframe_hint)
            x_ajustado, y_ajustado = x, y
            is_cross_origin = False

            if isinstance(contexto, Frame):
                try:
                    # Ajustar coordenadas para iframe offset
                    iframe_bbox = await page.evaluate(f"""
                        () => {{
                            const iframes = document.querySelectorAll('iframe');
                            for (const iframe of iframes) {{
                                if (iframe.name === '{iframe_hint}' ||
                                    iframe.src.includes('{iframe_hint}') ||
                                    iframe.id === '{iframe_hint}' ||
                                    (iframe.title && iframe.title.includes('{iframe_hint}'))) {{
                                    const bbox = iframe.getBoundingClientRect();
                                    return {{ left: bbox.left, top: bbox.top }};
                                }}
                            }}
                            return null;
                        }}
                    """)
                    if iframe_bbox:
                        x_ajustado = int(x - iframe_bbox['left'])
                        y_ajustado = int(y - iframe_bbox['top'])
                        logger.info(f"   [Coords Capturadas] Coordenadas ajustadas para iframe: ({x}, {y}) -> ({x_ajustado}, {y_ajustado})")

                    # Obter elemento no iframe
                    elemento_info = await contexto.evaluate("""
                        ([x, y]) => {
                            const el = document.elementFromPoint(x, y);
                            if (!el) return null;
                            return {
                                tagName: el.tagName,
                                innerText: el.innerText || el.getAttribute('aria-label') || el.getAttribute('title') || ''
                            };
                        }
                    """, [x_ajustado, y_ajustado])
                except Exception as exc_frame:
                    logger.warning(f"   [Coords Capturadas] Erro ao usar iframe_hint - fallback para detecção automática: {exc_frame}")
                    # Fallback para detecção automática
                    elemento_info, x_ajustado, y_ajustado, is_cross_origin = \
                        await _resolver_elemento_em_iframe(page, x, y)
            else:
                logger.info("   [Coords Capturadas] iframe_hint não resolveu para Frame - usando detecção automática")
                # Fallback para detecção automática
                elemento_info, x_ajustado, y_ajustado, is_cross_origin = \
                    await _resolver_elemento_em_iframe(page, x, y)
        else:
            logger.info("   [Coords Capturadas] Detecção automática de iframe ativada")
            # Detecção automática de iframe
            elemento_info, x_ajustado, y_ajustado, is_cross_origin = \
                await _resolver_elemento_em_iframe(page, x, y)

        # Fail-open: iframe cross-origin
        if is_cross_origin:
            logger.warning("   [Coords Capturadas] Iframe cross-origin detectado - fail-open aplicado")
            return (True, True)

        # Verificar identidade
        if elemento_info and elemento_info.get('innerText'):
            texto_elemento = elemento_info['innerText']
            # [FIX] Match exato — não aceita substrings para evitar falsos positivos
            # Ex: "1" in "EMPRESA 1" → True era falso positivo; agora "1" == "empresa 1" → False
            texto_elem_norm = texto_elemento.strip().lower()
            label_norm = label_curto.strip().lower()
            if texto_elem_norm == label_norm:
                return (True, False)  # Identidade confirmada — match exato
            else:
                logger.warning(
                    f"   [Coords Capturadas] Identidade não confirmada: "
                    f"esperado '{label_curto}', encontrado '{texto_elemento[:50]}' "
                    f"(match exato requerido) em ({x_ajustado}, {y_ajustado})"
                )
                return (False, False)  # Identidade NÃO confirmada
        else:
            # Fail-open: elemento sem texto
            return (True, False)

    except Exception as exc_verify:
        # Fail-open: exceção durante verificação
        logger.warning(f"   [Coords Capturadas] Verificação de identidade falhou (fail-open): {exc_verify}")
        return (True, False)

async def _som_vision_matching(page: Page, alvo: dict, label_curto: str) -> Optional[dict]:
    """
    Camada 3.4: SoM Vision Matching
    Obtém as Bounding Boxes do Set-of-Marks e cruza com os dados do AXTree ou índice
    capturados na gravação para encontrar as coordenadas exatas do elemento na tela atual.
    """
    try:
        ax_node = alvo.get("ax_node")
        ax_name = ax_node.get("ax_name", "").strip().lower() if ax_node else ""
        som_idx_clicado = alvo.get("som_idx_clicado")
        
        if not ax_name and som_idx_clicado is None:
            return None

        boxes = await get_som_boxes(page)
        if not boxes:
            return None

        if ax_name:
            for box in boxes:
                if box.get("label", "").strip().lower() == ax_name:
                    return {"x": box["x"] + box["w"] // 2, "y": box["y"] + box["h"] // 2, "match_type": "ax_name"}

        if som_idx_clicado is not None:
            for box in boxes:
                if box.get("idx") == som_idx_clicado:
                    box_label = box.get("label", "").strip().lower()
                    if label_curto and label_curto.lower() in box_label or not label_curto:
                        return {"x": box["x"] + box["w"] // 2, "y": box["y"] + box["h"] // 2, "match_type": "som_idx"}
                    
        return None
    except Exception as exc:
        logger.warning(f"Erro em _som_vision_matching: {exc}")
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

    # ── Log do adapter ativo (apenas uma vez por sessão) ─────────────────────
    global _adapter_logado
    if not _adapter_logado:
        _adapter_inst = _obter_adapter_cached()
        logger.info(
            f"[Pipeline] Adapter ativo: {type(_adapter_inst).__name__} | "
            f"Sistema: {_adapter_inst.nome_sistema}"
        )
        _adapter_logado = True

    # ── Atalho: item de menu de contexto ─────────────────────────────────────
    # Quando is_context_menu_item=True, a ação é um item do menu de contexto
    # que foi aberto por um clique_direito anterior. Vai direto para o menu
    # sem passar pelas camadas normais (Brain, Sniper, Coords, etc.).
    if acao_tec.get("is_context_menu_item"):
        logger.info(f"\n   Executando (menu de contexto): {intencao[:80]}")
        # Aguarda a animação de entrada do ngx-contextmenu (CDK overlay tem fade-in)
        await asyncio.sleep(0.3)
        menu_locator = await _detectar_menu_contexto_ativo(page, iframe_hint, timeout_ms=2000)
        if menu_locator is not None:
            seletor_usado = await _buscar_em_escopo_menu(menu_locator, label_curto, page)
            if seletor_usado:
                _registrar_sucesso_cache(intencao, seletor=seletor_usado, iframe=iframe_hint)
                _registrar_telemetria("0.5_menu_ctx", True)
                _registrar_estrategia_vencedora(intencao, "0.5_menu_ctx")
                logger.info(f"   [Menu-CTX] Clicou em '{label_curto}' via '{seletor_usado}'")
                return True
            else:
                logger.warning(f"   [Menu-CTX] Menu ativo mas '{label_curto}' não encontrado no escopo")
                _registrar_telemetria("0.5_menu_ctx", False)
        else:
            logger.warning("   [Menu-CTX] is_context_menu_item=True mas menu não detectado")
            _registrar_telemetria("0.5_menu_ctx", False)
        # IMPORTANTE: não escala para Sniper/Coords — qualquer clique fora do menu
        # fecha o overlay CDK. Retorna falha para que o executor possa reportar.
        _registrar_falha_cache(intencao)
        _registrar_telemetria("falha_total", False)
        logger.error(f"   [FALHA TOTAL] Menu de contexto não encontrado para: '{label_curto}'")
        return False

    # ── Guard: intenção vazia desativa o Brain ────────────────────────────────
    _intencao_valida = bool(intencao and intencao.strip())
    if not _intencao_valida:
        intencao = f"clique em '{label_curto}'" if label_curto else "Acao na interface"
        logger.debug(
            f"   [Brain] intencao_semantica vazia — Brain desativado para esta ação. "
            f"Usando label_curto como proxy: '{label_curto}'"
        )

    logger.info(f"\n   Executando: {intencao[:80]}")
    scroll_y = await _scroll_para_area_esperada(page, coords_relativas, tipo_elemento, seletor_hint)

    # ── Camada 0: Brain (Memória SQLite permanente) ──────────────────────────
    # Ativada apenas quando intencao_semantica está preenchida. Consulta memória
    # de longo prazo para reutilizar seletores ou coordenadas que funcionaram em
    # execuções anteriores (zero-touch).
    # [BUG-3] FIX: flag impede double-registration de falha
    brain_registrou_falha = False
    cache = _consultar_cache(intencao) if _intencao_valida else None
    if cache:
        if cache.seletor:
            # [CTX-MENU] Consciência de overlay: se menu de contexto ativo e seletor
            # não aponta para dentro de um menu, pular Brain e deixar camada 0.5 tratar.
            _menu_ativo_check = await _detectar_menu_contexto_ativo(page, iframe_hint)
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
                # [FIX] Seletores text= do Brain devem usar match exato para evitar
                # que "text=\"6\"" encontre "2026" (substring matching).
                _brain_exact = cache.seletor.startswith("text=")
                cand_cache = TentativaLocalizacao(
                    seletor=cache.seletor,
                    iframe_hint=cache.iframe_src or iframe_hint,
                    exact=_brain_exact,
                    descricao="brain knowledge",
                )
                if await _tentar_candidato(page, cand_cache, acao, valor):
                    # [FIX] Verificação de identidade no Brain para seletores posicionais
                    # Se o seletor memorizado é posicional, verificar identidade antes de aceitar.
                    # Se label_curto é genérico/vazio, não há como confirmar → rejeitar e escalar.
                    if _e_candidato_posicional(cand_cache):
                        if not label_curto or _e_label_generico(label_curto):
                            logger.warning(
                                f"[Brain] Seletor posicional memorizado '{cache.seletor[:60]}' — "
                                f"label genérico/vazio ('{label_curto}'), não é possível confirmar identidade. "
                                f"Invalidando memória e escalando."
                            )
                            _registrar_falha_cache(intencao)
                            _registrar_telemetria("0_brain", False)
                            brain_registrou_falha = True
                        else:
                            try:
                                ctx_brain = await _resolver_contexto(page, cand_cache.iframe_hint)
                                locator_brain = ctx_brain.locator(cand_cache.seletor).first
                                identidade_ok = await _verificar_identidade_elemento(locator_brain, label_curto)
                                if not identidade_ok:
                                    logger.warning(
                                        f"[Brain] Seletor posicional memorizado '{cache.seletor[:60]}' — "
                                        f"identidade não confirmada (label='{label_curto}'). "
                                        f"Invalidando memória e escalando."
                                    )
                                    _registrar_falha_cache(intencao)
                                    _registrar_telemetria("0_brain", False)
                                    brain_registrou_falha = True
                                else:
                                    _registrar_sucesso_cache(intencao)
                                    _registrar_telemetria("0_brain", True)
                                    _registrar_estrategia_vencedora(intencao, "0_brain")
                                    return True
                            except Exception as exc_brain_verif:
                                # Fail-open: se não conseguir verificar, aceitar
                                logger.debug(f"[Brain] Verificação de identidade falhou (fail-open): {exc_brain_verif}")
                                _registrar_sucesso_cache(intencao)
                                _registrar_telemetria("0_brain", True)
                                _registrar_estrategia_vencedora(intencao, "0_brain")
                                return True
                    else:
                        _registrar_sucesso_cache(intencao)
                        _registrar_telemetria("0_brain", True)
                        _registrar_estrategia_vencedora(intencao, "0_brain")
                        return True
                else:
                    _registrar_falha_cache(intencao)
                    _registrar_telemetria("0_brain", False)
                    brain_registrou_falha = True
        elif cache.coords:
            if await _clicar_por_coordenadas(page, cache.coords, acao, valor):
                _registrar_sucesso_cache(intencao)
                _registrar_telemetria("0_brain_coords", True)
                _registrar_estrategia_vencedora(intencao, "0_brain_coords")
                return True
            else:
                _registrar_falha_cache(intencao)
                _registrar_telemetria("0_brain_coords", False)
                brain_registrou_falha = True

    # ── Camada 0.5: Menu de contexto ativo ───────────────────────────────────
    # Ativada quando um overlay de menu de contexto está visível na página.
    # Escopa a busca dentro do menu para evitar cliques fora do overlay.
    menu_locator = await _detectar_menu_contexto_ativo(page, iframe_hint)
    if menu_locator is not None:
        seletor_usado = await _buscar_em_escopo_menu(menu_locator, label_curto, page)
        if seletor_usado:
            _registrar_sucesso_cache(intencao, seletor_usado)
            _registrar_telemetria("0.5_menu_ctx", True)
            _registrar_estrategia_vencedora(intencao, "0.5_menu_ctx")
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
                        # [POLICY] Não salva coordenadas puras no Brain - são frágeis
                        # Menu de contexto é efêmero e não deve ser memorizado
                        _registrar_telemetria("5_gemini_vision", True)
                        _registrar_estrategia_vencedora(intencao, "5_gemini_vision")
                        return True
            _registrar_telemetria("0.5_menu_ctx", False)
            return False

    # ── Camada 1: Foco nativo / active element ───────────────────────────────
    # Ativada para ações de digitação. Verifica se o cursor já está posicionado
    # em um campo editável (inline edit, nova pasta, etc.) sem precisar localizar.
    if acao in ("digitar_e_enter", "preencher_campo"):
        logger.info("   [Foco Nativo] Verificando se cursor ja esta posicionado...")
        if await _digitar_no_active_element(page, acao, valor):
            logger.info("   [Foco Nativo] Texto inserido no campo ja focado!")
            _registrar_telemetria("1_foco_nativo", True)
            _registrar_estrategia_vencedora(intencao, "1_foco_nativo")
            return True

        logger.info("   [Foco Nativo] Buscando div contenteditable generica...")
        contexto = await _resolver_contexto(page, iframe_hint)
        try:
            loc_edit = contexto.locator("[contenteditable='true']")
            if await loc_edit.count() > 0 and await loc_edit.first.is_visible():
                await _executar_acao(loc_edit.first, page, acao, valor)
                _registrar_telemetria("1_foco_nativo", True)
                _registrar_estrategia_vencedora(intencao, "1_foco_nativo")
                return True
        except Exception:
            pass

    # ── Camada 1.5: Heurísticas Senior X ─────────────────────────────────────
    # Ativada para ícones mudos (Home, Lixeira, etc.) sem label semântico.
    # Usa seletores específicos do Senior X para ícones conhecidos.
    # Pulada quando adapter ativo NÃO é SeniorXAdapter (sites genéricos não têm esses ícones).
    _adapter_ativo = _obter_adapter_cached()
    _usar_heuristica_seniorx = isinstance(_adapter_ativo, SeniorXAdapter)

    is_tag_generica = label_curto.lower() in _TAGS_FRAGEIS
    if _usar_heuristica_seniorx and (is_tag_generica or not label_curto):
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
                        _registrar_estrategia_vencedora(intencao, "1.5_heuristica_seniorx")
                        return True
                except Exception:
                    pass

    # Captura screenshot uma vez para Template_Matcher e Gemini Vision
    screenshot_atual_tm: Optional[bytes] = None
    try:
        screenshot_atual_tm = await page.screenshot(type="jpeg", quality=60, full_page=False)
    except Exception as exc:
        logger.warning(f"   [Screenshot] Falha ao capturar screenshot para Template_Matcher: {exc}")

    # ── Camada 1_T: Template Matching visual ─────────────────────────────────
    # Ativada quando screenshot_elemento está disponível no roteiro.
    # Compara imagem de referência com tela atual via NCC (sem OpenCV).
    # Acionada ANTES do Sniper e das Coordenadas — mais confiável que posição absoluta.
    screenshot_elemento_path = alvo.get("screenshot_elemento")
    if screenshot_elemento_path and screenshot_atual_tm is not None:
        try:
            ref_bytes = _resolver_screenshot_ref_tm(screenshot_elemento_path)
            if ref_bytes:
                vp = page.viewport_size or {"width": 1920, "height": 1080}
                resultado_tm = template_match(
                    referencia=ref_bytes,
                    tela_atual=screenshot_atual_tm,
                    coords_relativas=coords_relativas,
                    viewport=vp,
                    threshold=0.80,
                )
                if resultado_tm:
                    coords_tm = {"x": resultado_tm["x"], "y": resultado_tm["y"]}
                    if await _clicar_por_coordenadas(page, coords_tm, acao, valor):
                        logger.info(f"   [TemplateMatcher] Clique em {coords_tm} bem-sucedido (score={resultado_tm['score']:.3f}).")
                        _registrar_telemetria("1_template_matching", True, intencao)
                        _registrar_estrategia_vencedora(intencao, "1_template_matching")
                        return True
                _registrar_telemetria("1_template_matching", False, intencao)
        except Exception as exc:
            logger.warning(f"   [TemplateMatcher] Erro na camada 1_T: {exc}")

    # ── Gera candidatos ───────────────────────────────────────────────────────
    candidatos = _gerar_candidatos(seletor_hint, label_curto, iframe_hint, acao, tipo_elemento, html_hint)

    # ── Camada 2_S: Sniper Semântico ─────────────────────────────────────────
    # Ativada sempre. Tenta 15+ seletores Playwright nativos (getByRole, getByLabel,
    # getByPlaceholder, getByTitle, text=, aria-label, data-testid, etc.).
    # Acionada ANTES das Coordenadas — seletores semânticos são mais resilientes
    # a mudanças de layout do que posições absolutas.
    # ── 2_sniper. Sniper Semantico ────────────────────────────────────────────
    if candidatos:
        logger.info(f"   [Sniper] {len(candidatos)} candidatos para '{label_curto}'...")
        for cand in candidatos:
            _t0 = time.monotonic()

            # [FIX] Identificar candidatos de texto (exato ou parcial) que requerem verificação de identidade
            is_candidato_texto = (
                cand.seletor and
                (cand.seletor.startswith("text=") or (cand.via_pierce and "text=" in cand.seletor))
            )

            if is_candidato_texto and label_curto:
                # Candidato de texto (exato ou parcial) — aplicar verificação de identidade
                logger.debug(f"   [Sniper] Candidato texto detectado: {cand.descricao}")
                try:
                    ctx = await _resolver_contexto(page, cand.iframe_hint)
                    # Extrair o texto do seletor "text=..." e usar get_by_text
                    texto = cand.seletor[5:].strip('"').strip("'")  # Remove "text=" prefix
                    locator = ctx.get_by_text(texto, exact=cand.exact).first
                    # Verificar se o elemento está visível antes de verificar identidade
                    await locator.wait_for(state="visible", timeout=800)
                    # Verificar identidade: exigir correspondência exata do label_curto
                    try:
                        texto_elemento = await locator.inner_text(timeout=1000)
                        # Normalizar: strip e lowercase
                        texto_elem_norm = texto_elemento.strip().lower()
                        label_norm = label_curto.strip().lower()
                        # Aceitar APENAS se o texto do elemento É exatamente o label_curto (após normalização)
                        # Não aceitar substring parcial ou word boundary — apenas match exato
                        identidade_ok = (texto_elem_norm == label_norm)
                    except Exception:
                        # Fail-open: se não conseguir ler o texto, aceitar
                        identidade_ok = True

                    if not identidade_ok:
                        _elapsed_ms = (time.monotonic() - _t0) * 1000
                        logger.debug(
                            f"   [Sniper] '{cand.descricao}' — {_elapsed_ms:.0f}ms — "
                            f"miss (identidade não confirmada: '{texto_elemento[:50]}' != '{label_curto}')"
                        )
                        continue  # Rejeitar candidato e tentar o próximo
                    # Identidade confirmada — executar ação
                    await _executar_acao(locator, page, acao, valor)
                    _elapsed_ms = (time.monotonic() - _t0) * 1000
                    logger.debug(f"   [Sniper] '{cand.descricao}' — {_elapsed_ms:.0f}ms — OK (identidade confirmada)")
                    logger.info(f"   [Sniper] Acerto: {cand.descricao}")
                    logger.warning(
                        f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '2_sniper' (texto parcial) — "
                        f"verifique se o elemento correto foi atingido."
                    )
                    _registrar_sucesso_cache(
                        intencao,
                        seletor=cand.seletor if cand.seletor else None,
                        iframe=iframe_hint,
                    )
                    _registrar_telemetria("2_sniper", True)
                    _registrar_estrategia_vencedora(intencao, "2_sniper")
                    return True
                except Exception as exc_sniper:
                    _elapsed_ms = (time.monotonic() - _t0) * 1000
                    logger.debug(f"   [Sniper] '{cand.descricao}' — {_elapsed_ms:.0f}ms — miss ({exc_sniper})")
                    continue
            else:
                # Candidato de alta confiança (aria-label exato, data-testid, role+name, etc.) — sem verificação adicional
                # Candidatos aria-label e data-testid recebem timeout maior (2000ms) pois são seletores
                # semânticos confiáveis que podem precisar de mais tempo em SPAs com renderização assíncrona.
                _is_alta_confianca = cand.seletor and any(
                    p in cand.seletor for p in ("[aria-label=", "[data-testid=", "[id=", "[name=")
                )
                _timeout_cand = 2000 if _is_alta_confianca else 800
                _acertou = await _tentar_candidato(page, cand, acao, valor, timeout_ms=_timeout_cand)
                _elapsed_ms = (time.monotonic() - _t0) * 1000
                logger.debug(f"   [Sniper] '{cand.descricao}' — {_elapsed_ms:.0f}ms — {'OK' if _acertou else 'miss'}")
                if _acertou:
                    # [FIX] Verificação de identidade para candidatos CSS posicionais
                    # Candidatos com :nth-child, :nth-of-type, #id-numerico são frágeis
                    # e podem apontar para o elemento errado silenciosamente.
                    # A verificação é aplicada SEMPRE que o seletor é posicional —
                    # independentemente de label_curto ser genérico ou não.
                    # Se label_curto é genérico/vazio, não há como confirmar identidade
                    # → rejeitar o candidato posicional diretamente (não é seguro usar).
                    if _e_candidato_posicional(cand):
                        if not label_curto or _e_label_generico(label_curto):
                            # Sem label para verificar identidade → candidato posicional rejeitado
                            _elapsed_ms = (time.monotonic() - _t0) * 1000
                            logger.warning(
                                f"   [Sniper] Candidato posicional '{cand.descricao}' — "
                                f"label genérico/vazio ('{label_curto}'), não é possível confirmar identidade. Rejeitando."
                            )
                            continue
                        try:
                            ctx_verif = await _resolver_contexto(page, cand.iframe_hint)
                            locator_verif = ctx_verif.locator(cand.seletor).first
                            identidade_ok = await _verificar_identidade_elemento(locator_verif, label_curto)
                            if not identidade_ok:
                                _elapsed_ms = (time.monotonic() - _t0) * 1000
                                logger.warning(
                                    f"   [Sniper] Candidato posicional '{cand.descricao}' — "
                                    f"identidade não confirmada (label='{label_curto}'), rejeitando"
                                )
                                continue  # Rejeitar candidato posicional com identidade errada
                        except Exception as exc_verif:
                            # Fail-open: se não conseguir verificar, aceitar
                            logger.debug(f"   [Sniper] Verificação de identidade posicional falhou (fail-open): {exc_verif}")

                    logger.info(f"   [Sniper] Acerto: {cand.descricao}")
                    # [BUG-2] FIX: passa apenas cand.seletor (None quando vazio, nao cand.descricao)
                    _registrar_sucesso_cache(
                        intencao,
                        seletor=cand.seletor if cand.seletor else None,
                        iframe=iframe_hint,
                    )
                    _registrar_telemetria("2_sniper", True)
                    _registrar_estrategia_vencedora(intencao, "2_sniper")
                    return True

    # ── Camada 3: Seletor hint original ──────────────────────────────────────
    # Ativada quando o seletor hint não é frágil (não é tag genérica, não é posicional).
    # Usa o seletor CSS capturado na gravação original como última tentativa semântica.
    # [FIX] Movida para ANTES das coordenadas capturadas — seletores semânticos são
    # mais confiáveis que posições absolutas que dependem de layout estável.
    if seletor_hint and not _e_seletor_fragil(seletor_hint):
        logger.info(f"   [Hint] Tentando seletor original: {seletor_hint[:60]}")
        # [FIX] Verificação de identidade para seletores posicionais
        # Se o seletor_hint é posicional, verificar identidade antes de executar.
        # Se label_curto é genérico/vazio, não há como confirmar → descartar diretamente.
        if _contem_indice_posicional(seletor_hint):
            if not label_curto or _e_label_generico(label_curto):
                logger.warning(
                    f"[Hint] Seletor posicional '{seletor_hint[:60]}' com label genérico/vazio "
                    f"('{label_curto}') — não é possível confirmar identidade. Descartando."
                )
                # Não tenta — escala para próxima camada
            else:
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
                        _registrar_estrategia_vencedora(intencao, "3_hint_original")
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
                _registrar_estrategia_vencedora(intencao, "3_hint_original")
                return True

    # ── Camada 3.4: SoM Vision Matching ──────────────────────────────────────
    # Ativada se tivermos os dados de AXTree ou Set-of-Marks vindos da gravação.
    # Evita adivinhar por coordenadas. Em vez disso, pede para o JS recalcular as Bounding
    # Boxes (SoM) atuais, e tenta fazer o match exato do AX Name ou fallback pelo índice numérico.
    match_som = await _som_vision_matching(page, alvo, label_curto)
    if match_som:
        logger.info(f"   [SoM Matching] Encontrado via {match_som['match_type']}. Tentando clique em {match_som['x']},{match_som['y']}...")
        if await _clicar_por_coordenadas(page, {"x": match_som["x"], "y": match_som["y"]}, acao, valor):
            logger.info("   [SoM Matching] Clique executado com sucesso.")
            _registrar_sucesso_cache(intencao, coords={"x_pct": match_som["x"]/page.viewport_size["width"] if page.viewport_size else 0, "y_pct": match_som["y"]/page.viewport_size["height"] if page.viewport_size else 0})
            _registrar_telemetria("3.4_som_matching", True)
            _registrar_estrategia_vencedora(intencao, "3.4_som_matching")
            return True
        else:
            _registrar_telemetria("3.4_som_matching", False)

    # ── Camada 3.5: Coordenadas Capturadas (gravação original) ───────────────
    # [FIX] Movida de Camada 2 para Camada 3.5 — coordenadas são menos confiáveis
    # que seletores semânticos pois dependem de layout estável. Agora tentadas
    # DEPOIS do seletor_hint original, como penúltima opção antes de Gemini Vision.
    #
    # [FIX] Bug de timing corrigido: Agora verifica identidade ANTES de clicar.
    # Ordem correta: (1) calcular coords → (2) verificar identidade → (3) clicar se OK
    # [FIX] Match exato na verificação de identidade — elimina falsos positivos
    # onde label_curto é substring de um texto maior (ex: "1" in "EMPRESA 1").
    if coords_relativas and coords_relativas.get("x_pct"):
        logger.info("   [Coords Capturadas] Tentando coordenadas relativas da gravação...")
        try:
            # Calcular coordenadas absolutas
            vp = page.viewport_size or {"width": 1920, "height": 1080}
            x = int(coords_relativas["x_pct"] * vp["width"])
            y = int(coords_relativas["y_pct"] * vp["height"])

            # Verificar identidade ANTES de executar o clique
            identidade_confirmada, is_cross_origin = await _verificar_identidade_por_coordenadas(
                page, x, y, label_curto, iframe_hint
            )

            if identidade_confirmada:
                # Identidade confirmada (ou fail-open aplicado) - executar clique
                if await _clicar_por_coordenadas(page, {"x": x, "y": y}, acao, valor):
                    logger.info(f"   [Coords Capturadas] Clique em ({x}, {y}) bem-sucedido.")
                    if is_cross_origin:
                        logger.warning(
                            f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '3.5_coords_capturadas' "
                            f"(iframe cross-origin - fail-open aplicado)"
                        )
                    else:
                        logger.warning(
                            f"[Fallback] Ação '{intencao[:60]}' resolvida por camada '3.5_coords_capturadas' — "
                            f"verifique se o elemento correto foi atingido."
                        )
                    _registrar_telemetria("2_coords_capturadas", True)
                    _registrar_estrategia_vencedora(intencao, "3.5_coords_capturadas")
                    return True
                else:
                    # Clique falhou
                    logger.warning(f"   [Coords Capturadas] Clique falhou em ({x}, {y})")
            else:
                # Identidade NÃO confirmada - escalar para próxima camada
                logger.info("   [Coords Capturadas] Escalando para próxima camada (identidade não confirmada).")

        except Exception as exc:
            logger.warning(f"   [Coords Capturadas] Falhou: {exc}")

        _registrar_telemetria("2_coords_capturadas", False)

    # ── Camada 4: Busca em todos os frames ───────────────────────────────────
    # Ativada quando o elemento pode estar em um iframe não identificado pelo hint.
    # Itera por todos os frames filhos da página sem depender do iframe_hint.
    if candidatos:
        logger.info("   [Todos os Frames] Procurando o elemento em frames filhos...")
        frame_url = await _buscar_em_todos_os_frames(page, candidatos, acao, valor)
        if frame_url:
            _registrar_sucesso_cache(intencao, iframe=frame_url)
            _registrar_telemetria("4_todos_frames", True)
            _registrar_estrategia_vencedora(intencao, "4_todos_frames")
            return True

    # ── Camada 5: Gemini Vision (Self-Healing supremo) ───────────────────────
    # Ativada como último recurso quando todas as camadas anteriores falharam.
    # Envia screenshot atual + referência da gravação para o Gemini localizar o elemento.
    # Custo: latência + tokens de API. Reutiliza screenshot já capturado para 1_T.
    logger.info("   [Vision] DOM esgotado. Acionando Gemini Visual...")
    # Reutiliza screenshot já capturado para Template_Matcher (evita captura dupla)
    screenshot_atual = screenshot_atual_tm
    if screenshot_atual is None:
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
                        
                        # [POLICY] Só salva no Brain se conseguiu aprender um seletor estável
                        # Coordenadas puras do Gemini Vision são frágeis e não devem ser memorizadas
                        if seletor_aprendido:
                            logger.info(f"   [Vision] Seletor aprendido após coordenada: {seletor_aprendido}")
                            _registrar_sucesso_cache(intencao, seletor=seletor_aprendido)
                        else:
                            logger.debug(f"   [Vision] Nenhum seletor estável encontrado - não memorizado no Brain")
                    except Exception as e:
                        logger.debug(f"   [Vision] Falha ao aprender seletor: {e}")
                    _registrar_telemetria("5_gemini_vision", True)
                    _registrar_estrategia_vencedora(intencao, "5_gemini_vision")
                    return True

    # ── Falha Total ───────────────────────────────────────────────────────────
    # [BUG-3] FIX: registra falha apenas se o Brain nao registrou uma neste ciclo
    if not brain_registrou_falha:
        _registrar_falha_cache(intencao)
    _registrar_telemetria("falha_total", False)
    # Verifica taxa de HITL da última hora e emite alerta se > 20% (Req 9.1, 9.2, 9.5)
    _taxa_hitl = _calcular_taxa_hitl_1h()
    if _taxa_hitl is not None and _taxa_hitl > 0.20:
        logger.warning(
            f"[HITL] Taxa de intervenção manual elevada na última hora: "
            f"{_taxa_hitl:.1%} — verifique o Vision Engine."
        )
    logger.error(f"   [FALHA TOTAL] Impossivel executar: '{intencao[:70]}'")
    return False

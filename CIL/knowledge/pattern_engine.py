"""
pattern_engine.py — Motor de Padrões do CIL
============================================
Carrega o patterns_registry.json e fornece consultas semânticas sobre padrões.

Responsabilidades:
  - Carregar e validar o registry em disco
  - Resolver qual pattern se aplica a uma ação (por nome ou por signals)
  - Fornecer os strategy_steps e known_failures do pattern
  - Consultar o Brain DB v2 para enriquecer decisões com histórico
  - Registrar outcomes para aprendizado contínuo

Uso no vision_engine_cil.py:
    from knowledge.pattern_engine import PatternEngine
    engine = PatternEngine()
    pattern = engine.get("menu_navigation")
    steps   = engine.strategy_steps("menu_navigation")
    guardrail = engine.guardrail("menu_navigation", "x_pct_max")
"""

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "knowledge/patterns_registry.json")
DB_PATH       = "data/brain_v2.db"


@dataclass
class PatternInfo:
    """Informações completas de um padrão carregado do registry."""
    name: str
    description: str
    strategy_steps: list
    known_failures: list
    signals: dict
    preconditions: list
    validation: dict
    iframe_aware: bool
    version: int
    # Enriquecido pelo Brain DB em runtime
    best_strategy: str = ""
    taxa_sucesso: float = 0.0


class PatternEngine:
    """
    Carrega o patterns_registry.json e responde perguntas sobre padrões.

    É intencionalmente simples na v1 — sem ML, sem embeddings.
    O match é por nome exato (pattern_detectado do capture_semantic).
    O enriquecimento vem do Brain DB v2 consultado em runtime.

    Evolução futura (v2):
    - match semântico por signals (encontrar pattern sem nome exato)
    - score de confiança por combinação de signals
    - auto-atualização do registry com padrões aprendidos em execução
    """

    def __init__(self, registry_path: str = REGISTRY_PATH, db_path: str = DB_PATH):
        self._registry_path = registry_path
        self._db_path       = db_path
        self._patterns: dict[str, dict] = {}
        self._load()

    def _load(self):
        """Carrega o registry do disco. Re-carregável em runtime sem reiniciar."""
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                lista = json.load(f)
            self._patterns = {p["name"]: p for p in lista}
            logger.info(f"[PatternEngine] Registry carregado: {list(self._patterns.keys())}")
        except FileNotFoundError:
            logger.warning(f"[PatternEngine] Registry não encontrado em {self._registry_path}. Usando defaults.")
            self._patterns = {}
        except json.JSONDecodeError as e:
            logger.error(f"[PatternEngine] JSON inválido no registry: {e}")
            self._patterns = {}

    def reload(self):
        """Recarrega o registry sem reiniciar o processo — útil ao adicionar padrões."""
        self._load()

    # ──────────────────────────────────────────────────────────────
    # CONSULTAS PRINCIPAIS
    # ──────────────────────────────────────────────────────────────

    def get(self, pattern_name: str) -> Optional[dict]:
        """Retorna o dict completo do padrão, ou None se não existir."""
        return self._patterns.get(pattern_name)

    def exists(self, pattern_name: str) -> bool:
        """Verifica se o padrão está registrado."""
        return pattern_name in self._patterns

    def strategy_steps(self, pattern_name: str) -> list:
        """Retorna a lista ordenada de strategy_steps do padrão."""
        p = self._patterns.get(pattern_name)
        return p.get("strategy_steps", []) if p else []

    def preconditions(self, pattern_name: str) -> list:
        """Retorna as preconditions do padrão."""
        p = self._patterns.get(pattern_name)
        return p.get("preconditions", []) if p else []

    def known_failures(self, pattern_name: str) -> list:
        """Retorna os known_failures do padrão (útil para diagnóstico)."""
        p = self._patterns.get(pattern_name)
        return p.get("known_failures", []) if p else []

    def validation_config(self, pattern_name: str) -> dict:
        """Retorna a configuração de validação do padrão."""
        p = self._patterns.get(pattern_name)
        return p.get("validation", {}) if p else {}

    def guardrail(self, pattern_name: str, campo: str, default=None):
        """
        Retorna um valor de guardrail/signal do padrão.
        Ex: engine.guardrail("menu_navigation", "x_pct_max") → 0.35
        """
        p = self._patterns.get(pattern_name)
        if not p:
            return default
        return p.get("signals", {}).get(campo, default)

    def is_iframe_aware(self, pattern_name: str) -> bool:
        """Retorna se o padrão pode ocorrer dentro de um iframe."""
        p = self._patterns.get(pattern_name)
        return bool(p.get("iframe_aware", False)) if p else False

    def all_names(self) -> list:
        """Lista todos os nomes de padrões registrados."""
        return list(self._patterns.keys())

    # ──────────────────────────────────────────────────────────────
    # ENRIQUECIMENTO COM BRAIN DB v2
    # ──────────────────────────────────────────────────────────────

    def melhor_strategy_historica(self, pattern_name: str, contexto_sistema: str = "") -> str:
        """
        Consulta o Brain DB v2 e retorna qual strategy_usada teve mais sucesso
        para este pattern neste contexto_sistema.

        Retorna string vazia se não houver histórico suficiente.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT strategy_usada, COUNT(*) as total,
                           SUM(validacao_ok) as sucessos
                    FROM memoria_semantica
                    WHERE pattern = ?
                      AND validacao_ok = 1
                      AND (contexto_sistema = ? OR ? = '')
                    GROUP BY strategy_usada
                    ORDER BY sucessos DESC
                    LIMIT 1
                    """,
                    (pattern_name, contexto_sistema, contexto_sistema),
                ).fetchall()
                if rows and rows[0]["total"] >= 3:  # mínimo de 3 amostras para confiar
                    best = rows[0]["strategy_usada"]
                    logger.info(
                        f"[PatternEngine] Melhor strategy para '{pattern_name}': "
                        f"'{best}' ({rows[0]['sucessos']}/{rows[0]['total']} sucessos)"
                    )
                    return best
        except Exception:
            pass
        return ""

    def taxa_sucesso_pattern(self, pattern_name: str) -> float:
        """
        Retorna a taxa de sucesso geral do padrão com base no Brain DB v2.
        Útil para diagnóstico e logging.
        """
        try:
            with sqlite3.connect(self._db_path) as conn:
                row = conn.execute(
                    """
                    SELECT COUNT(*) as total, SUM(validacao_ok) as ok
                    FROM memoria_semantica WHERE pattern = ?
                    """,
                    (pattern_name,),
                ).fetchone()
                if row and row[0] > 0:
                    return round(row[1] / row[0], 2)
        except Exception:
            pass
        return 0.0

    def log_status(self):
        """Loga o status atual de todos os padrões com taxas do Brain DB."""
        logger.info("[PatternEngine] Status dos padrões:")
        for name in self.all_names():
            taxa = self.taxa_sucesso_pattern(name)
            best = self.melhor_strategy_historica(name)
            logger.info(f"  {name}: taxa={taxa:.0%} | melhor strategy: '{best or 'sem histórico'}'")

    # ──────────────────────────────────────────────────────────────
    # MATCH POR SIGNALS (v1 simples — evolução futura)
    # ──────────────────────────────────────────────────────────────

    def match_por_signals(self, dom_tags: list, x_pct: float = 0.5, tem_iframe: bool = False) -> Optional[str]:
        """
        Tenta identificar o padrão com base em signals do DOM e coordenadas.
        Usado quando pattern_detectado não está disponível (ex: replay sem capture).

        Algoritmo de score simples:
        - +2 por cada dom tag que bate com os signals do padrão
        - +1 se x_pct está dentro do x_pct_max do padrão
        - +1 se tem_iframe e pattern é iframe_aware

        Retorna o nome do padrão com maior score, ou None.
        """
        scores: dict[str, int] = {}
        dom_tags_lower = {t.lower() for t in dom_tags}

        for name, p in self._patterns.items():
            score = 0
            pattern_signals = {s.lower() for s in p.get("signals", {}).get("dom", [])}
            score += 2 * len(dom_tags_lower & pattern_signals)

            x_max = p.get("signals", {}).get("x_pct_max", 1.0)
            if x_pct <= x_max:
                score += 1

            if tem_iframe and p.get("iframe_aware", False):
                score += 1

            if score > 0:
                scores[name] = score

        if not scores:
            return None

        best = max(scores, key=scores.__getitem__)
        logger.info(f"[PatternEngine] Match por signals: '{best}' (score={scores[best]})")
        return best


# ──────────────────────────────────────────────────────────────────
# INSTÂNCIA GLOBAL — importada pelo vision_engine_cil
# ──────────────────────────────────────────────────────────────────
# Carregada uma vez quando o módulo é importado.
# Use pattern_engine.reload() se o registry for alterado em disco.
pattern_engine = PatternEngine()
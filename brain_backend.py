"""
brain_backend.py — Senior Training OS · Interface BrainBackend
===============================================================
Task 14: Implementar interface BrainBackend com suporte a backend intercambiável.

Expõe:
  - EntradaBrain: dataclass com os campos da memória semântica
  - BrainBackend: Protocol com operações get, set, query
  - SQLiteBrainBackend: implementação SQLite preservando comportamento atual do brain.db
  - NullBrainBackend: modo degradado — retorna None/[] em todas as operações
  - get_brain_backend(): factory que lê BRAIN_BACKEND_URL e retorna o backend adequado
  - brain: instância padrão exportada

Variáveis de ambiente:
  BRAIN_BACKEND_URL — se definida, tenta usar backend remoto (stub).
                      Se indisponível, cai para NullBrainBackend com WARNING.

Requisitos: 2.4.1, 2.4.2, 2.4.3, 2.4.4
"""

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Protocol, runtime_checkable

from utils import configurar_logging

logger = configurar_logging(__name__)

# ──────────────────────────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────────────────────────

DB_PATH = "brain.db"
MAX_FALHAS_CACHE = 3


# ──────────────────────────────────────────────────────────────
# Data Model
# ──────────────────────────────────────────────────────────────

@dataclass
class EntradaBrain:
    """Representa uma entrada de memória semântica no Brain."""
    intencao: str
    seletor: Optional[str] = None
    coords: Optional[dict] = None
    iframe_src: Optional[str] = None
    hits: int = 0
    falhas_consecutivas: int = 0
    tenant_id: str = "senior_default"


# ──────────────────────────────────────────────────────────────
# Protocolo BrainBackend
# ──────────────────────────────────────────────────────────────

@runtime_checkable
class BrainBackend(Protocol):
    """
    Interface de acesso à memória semântica do Brain.

    Operações independentes do backend de armazenamento (SQLite, remoto, null).
    Requisito 2.4.1: get, set, query independentes do backend.
    """

    def get(self, intencao: str, tenant_id: str = "senior_default") -> Optional[EntradaBrain]:
        """Retorna a entrada de memória para a intenção, ou None se não existir."""
        ...

    def set(self, entrada: EntradaBrain) -> None:
        """Persiste ou atualiza uma entrada de memória semântica."""
        ...

    def query(self, tenant_id: str, limit: int = 50) -> List[EntradaBrain]:
        """Retorna entradas de memória do tenant, ordenadas por hits DESC."""
        ...


# ──────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────

def _chave(intencao: str) -> str:
    return hashlib.md5(intencao.strip().lower().encode()).hexdigest()[:16]


def _init_schema(db_path: str) -> None:
    """Garante que o schema mínimo existe no banco."""
    try:
        with sqlite3.connect(db_path) as conn:
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
                    tenant_id TEXT DEFAULT 'senior_default',
                    ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            try:
                conn.execute(
                    "ALTER TABLE memoria_semantica ADD COLUMN tenant_id TEXT DEFAULT 'senior_default'"
                )
            except Exception:
                pass  # coluna já existe
    except Exception as e:
        logger.error(f"[brain_backend] Erro ao inicializar schema: {e}")


# ──────────────────────────────────────────────────────────────
# SQLiteBrainBackend
# ──────────────────────────────────────────────────────────────

class SQLiteBrainBackend:
    """
    Implementação SQLite do BrainBackend.

    Preserva o comportamento atual do brain.db (Requisito 2.4.2).
    Adiciona suporte a tenant_id para isolamento futuro (Requisito 2.5.4).
    """

    def __init__(self, db_path: str = DB_PATH) -> None:
        self.db_path = db_path
        _init_schema(db_path)

    def get(self, intencao: str, tenant_id: str = "senior_default") -> Optional[EntradaBrain]:
        """Retorna a entrada de memória para a intenção e tenant, ou None."""
        chave = _chave(intencao)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM memoria_semantica WHERE hash_intencao = ? AND tenant_id = ?",
                    (chave, tenant_id),
                ).fetchone()

                if row is None:
                    return None

                if row["falhas_consecutivas"] >= MAX_FALHAS_CACHE:
                    conn.execute(
                        "DELETE FROM memoria_semantica WHERE hash_intencao = ? AND tenant_id = ?",
                        (chave, tenant_id),
                    )
                    return None

                coords = json.loads(row["coords"]) if row["coords"] else None
                return EntradaBrain(
                    intencao=row["intencao"],
                    seletor=row["seletor"],
                    coords=coords,
                    iframe_src=row["iframe"],
                    hits=row["hits"],
                    falhas_consecutivas=row["falhas_consecutivas"],
                    tenant_id=row["tenant_id"],
                )
        except Exception as e:
            logger.error(f"[brain_backend] Erro ao ler memória '{intencao[:40]}': {e}")
            return None

    def set(self, entrada: EntradaBrain) -> None:
        """Persiste ou atualiza uma entrada de memória semântica."""
        chave = _chave(entrada.intencao)
        coords_str = json.dumps(entrada.coords) if entrada.coords else None

        _PREFIXOS_VALIDOS = ("text=", "[", "#", "button.", "p-", "mat-")
        seletor = entrada.seletor
        if seletor and not seletor.startswith(_PREFIXOS_VALIDOS) and ":has-text(" not in seletor:
            seletor = None

        try:
            with sqlite3.connect(self.db_path) as conn:
                existente = conn.execute(
                    "SELECT hits FROM memoria_semantica WHERE hash_intencao = ? AND tenant_id = ?",
                    (chave, entrada.tenant_id),
                ).fetchone()

                if existente:
                    query = (
                        "UPDATE memoria_semantica SET hits = hits + 1, "
                        "falhas_consecutivas = 0, ultima_atualizacao = CURRENT_TIMESTAMP"
                    )
                    params: list = []
                    if seletor:
                        query += ", seletor = ?"
                        params.append(seletor)
                    if coords_str:
                        query += ", coords = ?"
                        params.append(coords_str)
                    if entrada.iframe_src:
                        query += ", iframe = ?"
                        params.append(entrada.iframe_src)
                    query += " WHERE hash_intencao = ? AND tenant_id = ?"
                    params.extend([chave, entrada.tenant_id])
                    conn.execute(query, params)
                else:
                    conn.execute(
                        """
                        INSERT INTO memoria_semantica
                            (hash_intencao, intencao, seletor, coords, iframe,
                             hits, falhas_consecutivas, tenant_id)
                        VALUES (?, ?, ?, ?, ?, 1, 0, ?)
                        """,
                        (chave, entrada.intencao, seletor, coords_str,
                         entrada.iframe_src, entrada.tenant_id),
                    )
        except Exception as e:
            logger.error(f"[brain_backend] Erro ao salvar memória '{entrada.intencao[:40]}': {e}")

    def query(self, tenant_id: str, limit: int = 50) -> List[EntradaBrain]:
        """Retorna entradas de memória do tenant, ordenadas por hits DESC."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    """
                    SELECT * FROM memoria_semantica
                    WHERE tenant_id = ?
                    ORDER BY hits DESC
                    LIMIT ?
                    """,
                    (tenant_id, limit),
                ).fetchall()

                result = []
                for row in rows:
                    coords = json.loads(row["coords"]) if row["coords"] else None
                    result.append(EntradaBrain(
                        intencao=row["intencao"],
                        seletor=row["seletor"],
                        coords=coords,
                        iframe_src=row["iframe"],
                        hits=row["hits"],
                        falhas_consecutivas=row["falhas_consecutivas"],
                        tenant_id=row["tenant_id"],
                    ))
                return result
        except Exception as e:
            logger.error(f"[brain_backend] Erro ao consultar tenant '{tenant_id}': {e}")
            return []


# ──────────────────────────────────────────────────────────────
# NullBrainBackend — modo degradado
# ──────────────────────────────────────────────────────────────

class NullBrainBackend:
    """
    Backend nulo para modo degradado (Requisito 2.4.4).
    Retorna None/[] sem lançar exceções.
    """

    def get(self, intencao: str, tenant_id: str = "senior_default") -> Optional[EntradaBrain]:
        return None

    def set(self, entrada: EntradaBrain) -> None:
        pass

    def query(self, tenant_id: str, limit: int = 50) -> List[EntradaBrain]:
        return []


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────

def get_brain_backend() -> "SQLiteBrainBackend | NullBrainBackend":
    """
    Retorna o backend adequado com base em BRAIN_BACKEND_URL.

    - Sem BRAIN_BACKEND_URL: SQLiteBrainBackend (padrão).
    - Com BRAIN_BACKEND_URL: stub remoto → cai para NullBrainBackend com WARNING.

    Requisitos: 2.4.2, 2.4.3, 2.4.4
    """
    backend_url = os.getenv("BRAIN_BACKEND_URL")
    if not backend_url:
        return SQLiteBrainBackend(DB_PATH)

    logger.warning(
        f"[brain_backend] BRAIN_BACKEND_URL='{backend_url}' definida mas backend remoto "
        "não implementado. Operando em modo degradado (NullBrainBackend)."
    )
    return NullBrainBackend()


# Instância padrão exportada
brain: "SQLiteBrainBackend | NullBrainBackend" = get_brain_backend()

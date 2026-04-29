"""
job_registry.py — Senior Training OS · Registro de Jobs Assíncronos
====================================================================
Task 10: Implementar JobRegistry com persistência em SQLite.

Persiste o ciclo de vida de jobs de background na tabela `jobs` do brain.db.
Operações são thread-safe via context manager `with sqlite3.connect(DB_PATH)`.
Falhas do registry nunca propagam para o pipeline — todas as operações têm try/except.

Requisitos: 2.2.1, 2.2.3, 2.2.4
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Optional

from utils import configurar_logging

logger = configurar_logging(__name__)

# Usa o mesmo brain.db do Vision Engine para simplicidade (tabela separada)
DB_PATH = "brain.db"

# Status válidos para jobs
STATUS_VALIDOS = {"pendente", "executando", "concluido", "falhou", "cancelado"}

# Status que marcam o job como finalizado (preenchem concluido_em)
STATUS_FINAIS = {"concluido", "falhou", "cancelado"}


def _init_jobs_table() -> None:
    """Cria a tabela jobs no brain.db se ainda não existir."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    tipo TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pendente',
                    progresso INTEGER,
                    motivo_falha TEXT,
                    log_execucao TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    concluido_em TIMESTAMP
                )
            """)
    except Exception as e:
        logger.error(f"[job_registry] Não foi possível inicializar tabela jobs: {e}")


# Inicializa a tabela na importação do módulo
_init_jobs_table()


def criar_job(tipo: str, tenant_id: str = "senior_default") -> str:
    """Cria um novo job e retorna o job_id (UUID).

    Persiste o job com status 'pendente' no brain.db.
    Em caso de falha de persistência, retorna o job_id gerado mesmo assim
    para não bloquear o pipeline.

    Parâmetros:
        tipo (str): Tipo do job (ex: 'captura', 'render', 'scorm', 'pdf', 'rebuild').
        tenant_id (str): Identificador do tenant. Padrão: 'senior_default'.

    Retorna:
        str: UUID único do job criado.
    """
    job_id = str(uuid.uuid4())
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, tipo, tenant_id, status)
                VALUES (?, ?, ?, 'pendente')
                """,
                (job_id, tipo, tenant_id),
            )
        logger.info(f"[job_registry] Job criado: job_id={job_id} tipo={tipo} tenant={tenant_id}")
    except Exception as e:
        logger.error(f"[job_registry] Erro ao criar job {job_id}: {e}")
    return job_id


def atualizar_job(
    job_id: str,
    status: str = None,
    progresso: int = None,
    motivo_falha: str = None,
    log_execucao: str = None,
) -> bool:
    """Atualiza campos de um job existente. Retorna True se encontrado.

    Preenche `concluido_em` automaticamente quando status for 'concluido',
    'falhou' ou 'cancelado'.

    Parâmetros:
        job_id (str): UUID do job a atualizar.
        status (str, optional): Novo status. Deve ser um dos STATUS_VALIDOS.
        progresso (int, optional): Percentual de progresso (0–100).
        motivo_falha (str, optional): Descrição do motivo de falha.
        log_execucao (str, optional): Log de execução do job.

    Retorna:
        bool: True se o job foi encontrado e atualizado, False caso contrário.
    """
    if status is not None and status not in STATUS_VALIDOS:
        logger.warning(f"[job_registry] Status inválido '{status}' para job {job_id}")
        return False

    campos = []
    valores = []

    if status is not None:
        campos.append("status = ?")
        valores.append(status)
        if status in STATUS_FINAIS:
            campos.append("concluido_em = ?")
            valores.append(datetime.now(timezone.utc).isoformat())

    if progresso is not None:
        campos.append("progresso = ?")
        valores.append(progresso)

    if motivo_falha is not None:
        campos.append("motivo_falha = ?")
        valores.append(motivo_falha)

    if log_execucao is not None:
        campos.append("log_execucao = ?")
        valores.append(log_execucao)

    if not campos:
        logger.warning(f"[job_registry] atualizar_job chamado sem campos para job {job_id}")
        return False

    try:
        with sqlite3.connect(DB_PATH) as conn:
            valores.append(job_id)
            cursor = conn.execute(
                f"UPDATE jobs SET {', '.join(campos)} WHERE job_id = ?",
                valores,
            )
            encontrado = cursor.rowcount > 0

        if encontrado:
            logger.info(f"[job_registry] Job atualizado: job_id={job_id} campos={campos}")
        else:
            logger.warning(f"[job_registry] Job não encontrado para atualização: {job_id}")
        return encontrado
    except Exception as e:
        logger.error(f"[job_registry] Erro ao atualizar job {job_id}: {e}")
        return False


def consultar_job(job_id: str) -> Optional[dict]:
    """Retorna o job como dict ou None se não encontrado.

    Parâmetros:
        job_id (str): UUID do job a consultar.

    Retorna:
        dict | None: Dicionário com todos os campos do job, ou None se não existir.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(row)
    except Exception as e:
        logger.error(f"[job_registry] Erro ao consultar job {job_id}: {e}")
        return None


def listar_jobs_por_tenant(tenant_id: str, limit: int = 50) -> list[dict]:
    """Retorna lista de jobs do tenant, ordenados por criado_em DESC.

    Parâmetros:
        tenant_id (str): Identificador do tenant.
        limit (int): Número máximo de jobs a retornar. Padrão: 50.

    Retorna:
        list[dict]: Lista de jobs como dicionários, do mais recente ao mais antigo.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE tenant_id = ?
                ORDER BY criado_em DESC
                LIMIT ?
                """,
                (tenant_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"[job_registry] Erro ao listar jobs do tenant {tenant_id}: {e}")
        return []

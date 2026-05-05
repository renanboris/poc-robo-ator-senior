"""
tests/test_job_registry.py
===========================
Testes unitários e de propriedade para o módulo job_registry.py (Task 10).

Cobre:
- Criação de jobs com UUID único
- Transições de status (ciclo de vida completo)
- Consulta de job por job_id
- Listagem por tenant
- Preenchimento automático de concluido_em em status finais
- Property 7: Unicidade de job_id
- Property 8: Round-trip de estado de job

**Validates: Requisitos 2.2.1, 2.2.3, 2.2.4**
"""

import os
import sqlite3
import sys
import tempfile

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job_registry

# ──────────────────────────────────────────────────────────────
# Fixture: banco de dados isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def db_isolado(tmp_path, monkeypatch):
    """Redireciona DB_PATH para um banco temporário isolado por teste."""
    db_path = str(tmp_path / "jobs_test.db")
    monkeypatch.setattr(job_registry, "DB_PATH", db_path)
    # Reinicializa a tabela no banco temporário
    job_registry._init_jobs_table()
    yield db_path


# ──────────────────────────────────────────────────────────────
# Testes unitários — criação de jobs
# ──────────────────────────────────────────────────────────────

def test_criar_job_retorna_uuid():
    """criar_job() deve retornar uma string UUID não vazia."""
    job_id = job_registry.criar_job("render")
    assert isinstance(job_id, str)
    assert len(job_id) == 36  # formato UUID padrão: 8-4-4-4-12


def test_criar_job_persiste_com_status_pendente():
    """Job criado deve ter status 'pendente' no banco."""
    job_id = job_registry.criar_job("captura", tenant_id="tenant_a")
    job = job_registry.consultar_job(job_id)
    assert job is not None
    assert job["status"] == "pendente"


def test_criar_job_persiste_tipo_e_tenant():
    """criar_job() deve persistir tipo e tenant_id corretamente."""
    job_id = job_registry.criar_job("scorm", tenant_id="empresa_xyz")
    job = job_registry.consultar_job(job_id)
    assert job["tipo"] == "scorm"
    assert job["tenant_id"] == "empresa_xyz"


def test_criar_job_tenant_padrao():
    """criar_job() sem tenant_id deve usar 'senior_default'."""
    job_id = job_registry.criar_job("pdf")
    job = job_registry.consultar_job(job_id)
    assert job["tenant_id"] == "senior_default"


def test_criar_job_ids_distintos():
    """Dois jobs criados devem ter job_ids diferentes."""
    id1 = job_registry.criar_job("render")
    id2 = job_registry.criar_job("render")
    assert id1 != id2


# ──────────────────────────────────────────────────────────────
# Testes unitários — atualização de jobs
# ──────────────────────────────────────────────────────────────

def test_atualizar_job_status():
    """atualizar_job() deve alterar o status do job."""
    job_id = job_registry.criar_job("render")
    resultado = job_registry.atualizar_job(job_id, status="executando")
    assert resultado is True
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "executando"


def test_atualizar_job_progresso():
    """atualizar_job() deve atualizar o campo progresso."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, progresso=50)
    job = job_registry.consultar_job(job_id)
    assert job["progresso"] == 50


def test_atualizar_job_motivo_falha():
    """atualizar_job() deve persistir motivo_falha."""
    job_id = job_registry.criar_job("captura")
    job_registry.atualizar_job(job_id, status="falhou", motivo_falha="Timeout ao conectar")
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "falhou"
    assert job["motivo_falha"] == "Timeout ao conectar"


def test_atualizar_job_log_execucao():
    """atualizar_job() deve persistir log_execucao."""
    job_id = job_registry.criar_job("rebuild")
    job_registry.atualizar_job(job_id, log_execucao="Passo 1 OK\nPasso 2 OK")
    job = job_registry.consultar_job(job_id)
    assert "Passo 1 OK" in job["log_execucao"]


def test_atualizar_job_inexistente_retorna_false():
    """atualizar_job() com job_id inexistente deve retornar False."""
    resultado = job_registry.atualizar_job("uuid-inexistente", status="executando")
    assert resultado is False


def test_atualizar_job_status_invalido_retorna_false():
    """atualizar_job() com status inválido deve retornar False."""
    job_id = job_registry.criar_job("render")
    resultado = job_registry.atualizar_job(job_id, status="status_invalido")
    assert resultado is False
    # Status original deve permanecer inalterado
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "pendente"


def test_atualizar_job_sem_campos_retorna_false():
    """atualizar_job() sem nenhum campo para atualizar deve retornar False."""
    job_id = job_registry.criar_job("render")
    resultado = job_registry.atualizar_job(job_id)
    assert resultado is False


# ──────────────────────────────────────────────────────────────
# Testes unitários — concluido_em automático
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("status_final", ["concluido", "falhou", "cancelado"])
def test_concluido_em_preenchido_em_status_final(status_final):
    """concluido_em deve ser preenchido automaticamente em status finais."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, status=status_final)
    job = job_registry.consultar_job(job_id)
    assert job["concluido_em"] is not None, (
        f"concluido_em deveria estar preenchido para status '{status_final}'"
    )


def test_concluido_em_nulo_em_status_nao_final():
    """concluido_em deve permanecer nulo para status não-finais."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, status="executando")
    job = job_registry.consultar_job(job_id)
    assert job["concluido_em"] is None


# ──────────────────────────────────────────────────────────────
# Testes unitários — consulta de jobs
# ──────────────────────────────────────────────────────────────

def test_consultar_job_inexistente_retorna_none():
    """consultar_job() com job_id inexistente deve retornar None."""
    resultado = job_registry.consultar_job("uuid-que-nao-existe")
    assert resultado is None


def test_consultar_job_retorna_todos_os_campos():
    """consultar_job() deve retornar dict com todos os campos esperados."""
    job_id = job_registry.criar_job("pdf", tenant_id="tenant_b")
    job = job_registry.consultar_job(job_id)
    campos_esperados = {
        "job_id", "tipo", "tenant_id", "status",
        "progresso", "motivo_falha", "log_execucao",
        "criado_em", "concluido_em",
    }
    assert campos_esperados.issubset(set(job.keys()))


# ──────────────────────────────────────────────────────────────
# Testes unitários — listagem por tenant
# ──────────────────────────────────────────────────────────────

def test_listar_jobs_por_tenant_retorna_apenas_do_tenant():
    """listar_jobs_por_tenant() deve retornar apenas jobs do tenant especificado."""
    job_registry.criar_job("render", tenant_id="tenant_a")
    job_registry.criar_job("scorm", tenant_id="tenant_a")
    job_registry.criar_job("pdf", tenant_id="tenant_b")

    jobs_a = job_registry.listar_jobs_por_tenant("tenant_a")
    assert len(jobs_a) == 2
    assert all(j["tenant_id"] == "tenant_a" for j in jobs_a)


def test_listar_jobs_por_tenant_vazio():
    """listar_jobs_por_tenant() para tenant sem jobs deve retornar lista vazia."""
    resultado = job_registry.listar_jobs_por_tenant("tenant_sem_jobs")
    assert resultado == []


def test_listar_jobs_por_tenant_ordenado_por_criado_em_desc(db_isolado):
    """listar_jobs_por_tenant() deve retornar jobs do mais recente ao mais antigo."""
    import time as _time

    # Insere com timestamps explícitos para garantir ordenação determinística
    with sqlite3.connect(db_isolado) as conn:
        conn.execute(
            "INSERT INTO jobs (job_id, tipo, tenant_id, status, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("id-antigo", "render", "tenant_c", "pendente", "2024-01-01 10:00:00"),
        )
        conn.execute(
            "INSERT INTO jobs (job_id, tipo, tenant_id, status, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("id-medio", "scorm", "tenant_c", "pendente", "2024-01-01 11:00:00"),
        )
        conn.execute(
            "INSERT INTO jobs (job_id, tipo, tenant_id, status, criado_em) VALUES (?, ?, ?, ?, ?)",
            ("id-recente", "pdf", "tenant_c", "pendente", "2024-01-01 12:00:00"),
        )

    jobs = job_registry.listar_jobs_por_tenant("tenant_c")
    ids_retornados = [j["job_id"] for j in jobs]

    # O mais recente deve vir primeiro
    assert ids_retornados[0] == "id-recente"
    assert ids_retornados[-1] == "id-antigo"


def test_listar_jobs_por_tenant_respeita_limit():
    """listar_jobs_por_tenant() deve respeitar o parâmetro limit."""
    for _ in range(10):
        job_registry.criar_job("render", tenant_id="tenant_d")

    jobs = job_registry.listar_jobs_por_tenant("tenant_d", limit=3)
    assert len(jobs) == 3


# ──────────────────────────────────────────────────────────────
# Testes unitários — ciclo de vida completo
# ──────────────────────────────────────────────────────────────

def test_ciclo_de_vida_completo():
    """Simula o ciclo completo: pendente → executando → concluido."""
    job_id = job_registry.criar_job("render", tenant_id="tenant_e")

    # Inicia execução
    job_registry.atualizar_job(job_id, status="executando", progresso=0)
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "executando"
    assert job["concluido_em"] is None

    # Progresso intermediário
    job_registry.atualizar_job(job_id, progresso=50)
    job = job_registry.consultar_job(job_id)
    assert job["progresso"] == 50

    # Conclusão
    job_registry.atualizar_job(job_id, status="concluido", progresso=100)
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "concluido"
    assert job["progresso"] == 100
    assert job["concluido_em"] is not None


def test_ciclo_de_vida_com_falha():
    """Simula o ciclo: pendente → executando → falhou com motivo."""
    job_id = job_registry.criar_job("captura")
    job_registry.atualizar_job(job_id, status="executando")
    job_registry.atualizar_job(
        job_id,
        status="falhou",
        motivo_falha="Elemento não encontrado na tela",
        log_execucao="Tentativa 1: falhou\nTentativa 2: falhou",
    )
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "falhou"
    assert job["motivo_falha"] == "Elemento não encontrado na tela"
    assert job["concluido_em"] is not None


# ──────────────────────────────────────────────────────────────
# Property 7: Unicidade de job_id
# **Validates: Requisito 2.2.1**
# ──────────────────────────────────────────────────────────────

@given(
    n=st.integers(min_value=2, max_value=50),
    tipo=st.sampled_from(["captura", "render", "scorm", "pdf", "rebuild"]),
    tenant_id=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
)
@settings(max_examples=200, deadline=None)
def test_property7_unicidade_de_job_id(n, tipo, tenant_id):
    """
    **Property 7: Unicidade de job_id**
    **Validates: Requisito 2.2.1**

    Para qualquer sequência de N operações de background iniciadas,
    todos os job_id gerados SHALL ser distintos entre si.
    """
    ids = [job_registry.criar_job(tipo, tenant_id=tenant_id) for _ in range(n)]
    assert len(ids) == len(set(ids)), (
        f"job_ids duplicados encontrados em {n} criações: {ids}"
    )


# ──────────────────────────────────────────────────────────────
# Property 8: Round-trip de estado de job
# **Validates: Requisito 2.2.3**
# ──────────────────────────────────────────────────────────────

@given(
    tipo=st.sampled_from(["captura", "render", "scorm", "pdf", "rebuild"]),
    tenant_id=st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="_-")),
    status=st.sampled_from(["pendente", "executando", "concluido", "falhou", "cancelado"]),
    progresso=st.one_of(st.none(), st.integers(min_value=0, max_value=100)),
    motivo_falha=st.one_of(st.none(), st.text(min_size=0, max_size=100)),
)
@settings(max_examples=100, deadline=None)
def test_property8_round_trip_estado_job(tipo, tenant_id, status, progresso, motivo_falha):
    """
    **Property 8: Round-trip de estado de job**
    **Validates: Requisito 2.2.3**

    Para qualquer job criado com um job_id, consultar o registro de jobs
    SHALL retornar o mesmo job com seu estado atual, sem perda de dados.
    """
    job_id = job_registry.criar_job(tipo, tenant_id=tenant_id)

    # Aplica atualizações
    kwargs = {"status": status}
    if progresso is not None:
        kwargs["progresso"] = progresso
    if motivo_falha is not None:
        kwargs["motivo_falha"] = motivo_falha

    job_registry.atualizar_job(job_id, **kwargs)

    # Consulta e verifica round-trip
    job = job_registry.consultar_job(job_id)
    assert job is not None, f"Job {job_id} não encontrado após criação e atualização"
    assert job["job_id"] == job_id
    assert job["tipo"] == tipo
    assert job["tenant_id"] == tenant_id
    assert job["status"] == status

    if progresso is not None:
        assert job["progresso"] == progresso, (
            f"progresso esperado={progresso}, obtido={job['progresso']}"
        )

    if motivo_falha is not None:
        assert job["motivo_falha"] == motivo_falha, (
            f"motivo_falha esperado='{motivo_falha}', obtido='{job['motivo_falha']}'"
        )

    # Verifica concluido_em para status finais
    if status in job_registry.STATUS_FINAIS:
        assert job["concluido_em"] is not None, (
            f"concluido_em deveria estar preenchido para status '{status}'"
        )
    else:
        assert job["concluido_em"] is None, (
            f"concluido_em deveria ser None para status '{status}'"
        )

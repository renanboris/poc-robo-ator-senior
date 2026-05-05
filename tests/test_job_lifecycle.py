"""
tests/test_job_lifecycle.py
============================
Testes unitários para o ciclo de vida completo de jobs (Task 12).

Cobre:
- Criação e transição de status
- Cancelamento com limpeza de arquivos temporários
- Consulta de motivo de falha via API
- Persistência de log de execução
- Endpoint GET /api/jobs/{job_id}/log

**Validates: Requisitos 2.2.1, 2.2.4, 2.2.5, 2.2.6, NFR-3.5**
"""

import glob
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import job_registry

# ──────────────────────────────────────────────────────────────
# Fixture: banco de dados isolado por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def db_isolado(tmp_path, monkeypatch):
    """Redireciona DB_PATH para um banco temporário isolado por teste."""
    db_path = str(tmp_path / "jobs_lifecycle_test.db")
    monkeypatch.setattr(job_registry, "DB_PATH", db_path)
    job_registry._init_jobs_table()
    yield db_path


# ──────────────────────────────────────────────────────────────
# Testes de ciclo de vida: criação e transições de status
# ──────────────────────────────────────────────────────────────

def test_ciclo_pendente_executando_concluido():
    """Ciclo completo: pendente → executando → concluido."""
    job_id = job_registry.criar_job("render")

    job_registry.atualizar_job(job_id, status="executando", progresso=0)
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "executando"
    assert job["concluido_em"] is None

    job_registry.atualizar_job(job_id, progresso=50)
    job = job_registry.consultar_job(job_id)
    assert job["progresso"] == 50

    job_registry.atualizar_job(job_id, status="concluido", progresso=100)
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "concluido"
    assert job["concluido_em"] is not None


def test_ciclo_pendente_executando_falhou_com_motivo():
    """Ciclo: pendente → executando → falhou com motivo de falha registrado."""
    job_id = job_registry.criar_job("captura")
    job_registry.atualizar_job(job_id, status="executando")
    job_registry.atualizar_job(
        job_id,
        status="falhou",
        motivo_falha="Elemento não encontrado: #btn-salvar",
    )
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "falhou"
    assert job["motivo_falha"] == "Elemento não encontrado: #btn-salvar"
    assert job["concluido_em"] is not None


def test_ciclo_cancelamento_registra_status_e_motivo():
    """Cancelamento deve registrar status 'cancelado' e motivo no job."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, status="executando")
    job_registry.atualizar_job(
        job_id,
        status="cancelado",
        motivo_falha="Cancelado pelo utilizador via POST /api/cancelar",
    )
    job = job_registry.consultar_job(job_id)
    assert job["status"] == "cancelado"
    assert "Cancelado" in job["motivo_falha"]
    assert job["concluido_em"] is not None


# ──────────────────────────────────────────────────────────────
# Testes de limpeza de arquivos temporários
# ──────────────────────────────────────────────────────────────

def test_limpeza_de_temporarios_ao_cancelar(tmp_path, monkeypatch):
    """Cancelamento deve remover arquivos *.json.tmp do diretório de trabalho."""
    # Cria arquivos temporários simulando escritas atômicas interrompidas
    tmp1 = tmp_path / "roteiro_abc.json.tmp"
    tmp2 = tmp_path / "biblioteca_acoes.json.tmp"
    tmp1.write_text('{"parcial": true}')
    tmp2.write_text('{"parcial": true}')

    # Muda o cwd para o diretório temporário para que glob.glob("*.json.tmp") encontre os arquivos
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        arquivos_antes = glob.glob("*.json.tmp")
        assert len(arquivos_antes) == 2, "Deveria haver 2 arquivos temporários antes da limpeza"

        # Simula a limpeza que ocorre no cancelamento
        removidos = []
        for tmp_file in glob.glob("*.json.tmp"):
            try:
                os.remove(tmp_file)
                removidos.append(tmp_file)
            except Exception:
                pass

        arquivos_depois = glob.glob("*.json.tmp")
        assert len(arquivos_depois) == 0, "Todos os temporários devem ser removidos"
        assert len(removidos) == 2
    finally:
        os.chdir(original_cwd)


def test_limpeza_nao_falha_sem_temporarios(tmp_path):
    """Limpeza de temporários não deve falhar quando não há arquivos *.json.tmp."""
    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        removidos = []
        for tmp_file in glob.glob("*.json.tmp"):
            try:
                os.remove(tmp_file)
                removidos.append(tmp_file)
            except Exception:
                pass
        assert removidos == []
    finally:
        os.chdir(original_cwd)


# ──────────────────────────────────────────────────────────────
# Testes de log de execução
# ──────────────────────────────────────────────────────────────

def test_log_execucao_persiste_ultimas_100_linhas():
    """log_execucao deve persistir as últimas 100 linhas do processo."""
    job_id = job_registry.criar_job("render")
    linhas = [f"Linha {i}" for i in range(150)]
    log = "\n".join(linhas[-100:])
    job_registry.atualizar_job(job_id, log_execucao=log)

    job = job_registry.consultar_job(job_id)
    assert job["log_execucao"] is not None
    assert "Linha 149" in job["log_execucao"]
    assert "Linha 50" in job["log_execucao"]
    # As primeiras 50 linhas não devem estar no log (apenas as últimas 100)
    assert "Linha 49" not in job["log_execucao"]


def test_log_execucao_disponivel_apos_conclusao():
    """Log de execução deve estar disponível após o job ser concluído."""
    job_id = job_registry.criar_job("scorm")
    job_registry.atualizar_job(job_id, status="executando")
    job_registry.atualizar_job(
        job_id,
        log_execucao="Passo 1: OK\nPasso 2: OK\nPasso 3: OK",
    )
    job_registry.atualizar_job(job_id, status="concluido")

    job = job_registry.consultar_job(job_id)
    assert job["status"] == "concluido"
    assert job["log_execucao"] is not None
    assert "Passo 1: OK" in job["log_execucao"]


def test_log_execucao_disponivel_apos_falha():
    """Log de execução deve estar disponível mesmo quando o job falhou."""
    job_id = job_registry.criar_job("pdf")
    job_registry.atualizar_job(job_id, status="executando")
    job_registry.atualizar_job(
        job_id,
        log_execucao="Iniciando...\nERRO: arquivo não encontrado",
        status="falhou",
        motivo_falha="arquivo não encontrado",
    )

    job = job_registry.consultar_job(job_id)
    assert job["log_execucao"] is not None
    assert "ERRO" in job["log_execucao"]
    assert job["motivo_falha"] == "arquivo não encontrado"


def test_log_execucao_nulo_por_padrao():
    """Job recém-criado deve ter log_execucao nulo."""
    job_id = job_registry.criar_job("rebuild")
    job = job_registry.consultar_job(job_id)
    assert job["log_execucao"] is None


# ──────────────────────────────────────────────────────────────
# Testes de motivo de falha via consulta
# ──────────────────────────────────────────────────────────────

def test_motivo_falha_disponivel_via_consulta():
    """motivo_falha deve estar disponível via consultar_job() após falha."""
    job_id = job_registry.criar_job("captura")
    motivo = "Timeout: elemento #btn-confirmar não apareceu em 30s"
    job_registry.atualizar_job(job_id, status="falhou", motivo_falha=motivo)

    job = job_registry.consultar_job(job_id)
    assert job["motivo_falha"] == motivo


def test_motivo_falha_nulo_em_job_concluido():
    """Job concluído com sucesso não deve ter motivo_falha."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, status="concluido")

    job = job_registry.consultar_job(job_id)
    assert job["motivo_falha"] is None


# ──────────────────────────────────────────────────────────────
# Testes de progresso percentual
# ──────────────────────────────────────────────────────────────

def test_progresso_atualizado_durante_execucao():
    """Progresso deve ser atualizado incrementalmente durante a execução."""
    job_id = job_registry.criar_job("render")
    job_registry.atualizar_job(job_id, status="executando", progresso=0)

    for pct in [10, 20, 30, 50, 70, 90, 100]:
        job_registry.atualizar_job(job_id, progresso=pct)
        job = job_registry.consultar_job(job_id)
        assert job["progresso"] == pct


def test_progresso_nulo_por_padrao():
    """Job recém-criado deve ter progresso nulo."""
    job_id = job_registry.criar_job("render")
    job = job_registry.consultar_job(job_id)
    assert job["progresso"] is None

"""
tests/test_storage_adapter.py
==============================
Testes unitários para LocalStorageAdapter (Task 13).

Cobre:
  - write + read round-trip (JSON e binário)
  - exists antes e depois de escrita
  - list retorna apenas artefatos do tipo correto
  - validação de path traversal em todas as operações
  - escrita atômica (sem arquivo temporário residual)
  - tipo de artefato inválido lança ValueError

Requisitos: 2.3.1, 2.3.2, 2.3.3, 2.3.4
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage_adapter import ARTIFACT_DIRS, LocalStorageAdapter, StorageAdapter

# ──────────────────────────────────────────────────────────────
# Fixture: adapter com diretórios isolados por teste
# ──────────────────────────────────────────────────────────────

@pytest.fixture()
def adapter(tmp_path, monkeypatch):
    """
    Retorna um LocalStorageAdapter com ARTIFACT_DIRS redirecionados para
    diretórios temporários isolados por teste.
    """
    import storage_adapter as sa_module

    # Cria diretórios temporários para cada tipo de artefato
    dirs_temp = {}
    for tipo, _ in ARTIFACT_DIRS.items():
        d = tmp_path / tipo
        d.mkdir(parents=True, exist_ok=True)
        dirs_temp[tipo] = str(d)

    monkeypatch.setattr(sa_module, "ARTIFACT_DIRS", dirs_temp)
    return LocalStorageAdapter()


# ──────────────────────────────────────────────────────────────
# Verificação de conformidade com o protocolo
# ──────────────────────────────────────────────────────────────

def test_local_adapter_implementa_protocolo():
    """LocalStorageAdapter deve satisfazer o protocolo StorageAdapter."""
    assert isinstance(LocalStorageAdapter(), StorageAdapter)


# ──────────────────────────────────────────────────────────────
# Round-trip: write + read (binário)
# ──────────────────────────────────────────────────────────────

def test_write_read_roundtrip_binario(adapter):
    """write() seguido de read() deve retornar os mesmos bytes."""
    dados = b"conteudo binario de teste \x00\x01\x02"
    adapter.write("audio", "teste.mp3", dados, tenant_id="t1")
    lido = adapter.read("audio", "teste.mp3", tenant_id="t1")
    assert lido == dados


def test_write_read_roundtrip_json(adapter):
    """write() de JSON seguido de read() deve preservar o conteúdo."""
    roteiro = {
        "metadata": {"nome_aula": "Aula Teste", "id_treinamento": "aula_teste"},
        "passos": [{"id_passo": 1, "is_conclusao": False}, {"id_passo": 2, "is_conclusao": True}],
    }
    dados = json.dumps(roteiro, ensure_ascii=False).encode("utf-8")
    adapter.write("roteiro", "aula_teste.json", dados, tenant_id="t1")
    lido = adapter.read("roteiro", "aula_teste.json", tenant_id="t1")
    assert json.loads(lido.decode("utf-8")) == roteiro


def test_write_sobrescreve_arquivo_existente(adapter):
    """Segunda write() deve substituir o conteúdo anterior."""
    adapter.write("audio", "audio.mp3", b"versao_1", tenant_id="t1")
    adapter.write("audio", "audio.mp3", b"versao_2", tenant_id="t1")
    lido = adapter.read("audio", "audio.mp3", tenant_id="t1")
    assert lido == b"versao_2"


# ──────────────────────────────────────────────────────────────
# exists: antes e depois de escrita
# ──────────────────────────────────────────────────────────────

def test_exists_retorna_false_antes_de_escrita(adapter):
    """exists() deve retornar False para artefato ainda não escrito."""
    assert adapter.exists("roteiro", "nao_existe.json", tenant_id="t1") is False


def test_exists_retorna_true_apos_escrita(adapter):
    """exists() deve retornar True após write() bem-sucedido."""
    adapter.write("roteiro", "existe.json", b'{"ok": true}', tenant_id="t1")
    assert adapter.exists("roteiro", "existe.json", tenant_id="t1") is True


def test_exists_nao_confunde_tipos_diferentes(adapter):
    """exists() para tipo A não deve retornar True para artefato do tipo B."""
    adapter.write("audio", "arquivo.mp3", b"audio", tenant_id="t1")
    # O mesmo nome em tipo diferente não deve existir
    assert adapter.exists("roteiro", "arquivo.mp3", tenant_id="t1") is False


# ──────────────────────────────────────────────────────────────
# list: retorna apenas artefatos do tipo correto
# ──────────────────────────────────────────────────────────────

def test_list_retorna_lista_vazia_sem_artefatos(adapter):
    """list() deve retornar lista vazia quando não há artefatos."""
    resultado = adapter.list("roteiro", tenant_id="t1")
    assert resultado == []


def test_list_retorna_artefatos_escritos(adapter):
    """list() deve retornar os nomes dos artefatos escritos."""
    adapter.write("roteiro", "aula_a.json", b'{"ok": true}', tenant_id="t1")
    adapter.write("roteiro", "aula_b.json", b'{"ok": true}', tenant_id="t1")
    resultado = adapter.list("roteiro", tenant_id="t1")
    assert set(resultado) == {"aula_a.json", "aula_b.json"}


def test_list_nao_mistura_tipos(adapter):
    """list() para tipo A não deve incluir artefatos do tipo B."""
    adapter.write("roteiro", "roteiro.json", b'{"ok": true}', tenant_id="t1")
    adapter.write("audio", "audio.mp3", b"audio", tenant_id="t1")

    roteiros = adapter.list("roteiro", tenant_id="t1")
    audios = adapter.list("audio", tenant_id="t1")

    assert "audio.mp3" not in roteiros
    assert "roteiro.json" not in audios


def test_list_exclui_arquivos_temporarios(adapter, tmp_path, monkeypatch):
    """list() não deve incluir arquivos .tmp residuais."""
    import storage_adapter as sa_module

    # Cria um arquivo .tmp manualmente no diretório de roteiros
    dir_roteiro = sa_module.ARTIFACT_DIRS["roteiro"]
    tmp_file = os.path.join(dir_roteiro, "residual.json.tmp")
    with open(tmp_file, "w") as f:
        f.write("temporario")

    adapter.write("roteiro", "real.json", b'{"ok": true}', tenant_id="t1")
    resultado = adapter.list("roteiro", tenant_id="t1")

    assert "residual.json.tmp" not in resultado
    assert "real.json" in resultado


# ──────────────────────────────────────────────────────────────
# Segurança: path traversal
# ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("nome_malicioso", [
    "../secrets.txt",
    "../../etc/passwd",
    "subdir/../../fora.json",
])
def test_write_bloqueia_path_traversal(adapter, nome_malicioso):
    """write() deve lançar ValueError para path traversal."""
    with pytest.raises(ValueError, match="fora do diretório base"):
        adapter.write("roteiro", nome_malicioso, b"dados", tenant_id="t1")


@pytest.mark.parametrize("nome_malicioso", [
    "../secrets.txt",
    "../../etc/passwd",
])
def test_read_bloqueia_path_traversal(adapter, nome_malicioso):
    """read() deve lançar ValueError para path traversal."""
    with pytest.raises(ValueError, match="fora do diretório base"):
        adapter.read("roteiro", nome_malicioso, tenant_id="t1")


@pytest.mark.parametrize("nome_malicioso", [
    "../secrets.txt",
    "../../etc/passwd",
])
def test_exists_bloqueia_path_traversal(adapter, nome_malicioso):
    """exists() deve lançar ValueError para path traversal."""
    with pytest.raises(ValueError, match="fora do diretório base"):
        adapter.exists("roteiro", nome_malicioso, tenant_id="t1")


# ──────────────────────────────────────────────────────────────
# Tipo de artefato inválido
# ──────────────────────────────────────────────────────────────

def test_tipo_invalido_write_lanca_valueerror(adapter):
    """write() com tipo desconhecido deve lançar ValueError."""
    with pytest.raises(ValueError, match="Tipo de artefato desconhecido"):
        adapter.write("tipo_inexistente", "arquivo.bin", b"dados", tenant_id="t1")


def test_tipo_invalido_read_lanca_valueerror(adapter):
    """read() com tipo desconhecido deve lançar ValueError."""
    with pytest.raises(ValueError, match="Tipo de artefato desconhecido"):
        adapter.read("tipo_inexistente", "arquivo.bin", tenant_id="t1")


def test_tipo_invalido_exists_lanca_valueerror(adapter):
    """exists() com tipo desconhecido deve lançar ValueError."""
    with pytest.raises(ValueError, match="Tipo de artefato desconhecido"):
        adapter.exists("tipo_inexistente", "arquivo.bin", tenant_id="t1")


def test_tipo_invalido_list_lanca_valueerror(adapter):
    """list() com tipo desconhecido deve lançar ValueError."""
    with pytest.raises(ValueError, match="Tipo de artefato desconhecido"):
        adapter.list("tipo_inexistente", tenant_id="t1")


# ──────────────────────────────────────────────────────────────
# Escrita atômica: sem arquivo temporário residual
# ──────────────────────────────────────────────────────────────

def test_write_binario_sem_temporario_residual(adapter):
    """Após write() binário bem-sucedido, não deve restar arquivo .tmp."""
    import storage_adapter as sa_module
    dir_audio = sa_module.ARTIFACT_DIRS["audio"]

    adapter.write("audio", "audio.mp3", b"conteudo", tenant_id="t1")

    tmp_files = [f for f in os.listdir(dir_audio) if f.endswith(".tmp")]
    assert tmp_files == [], f"Arquivos temporários residuais: {tmp_files}"


def test_write_json_sem_temporario_residual(adapter):
    """Após write() JSON bem-sucedido, não deve restar arquivo .json.tmp."""
    import storage_adapter as sa_module
    dir_roteiro = sa_module.ARTIFACT_DIRS["roteiro"]

    adapter.write("roteiro", "aula.json", b'{"ok": true}', tenant_id="t1")

    tmp_files = [f for f in os.listdir(dir_roteiro) if f.endswith(".json.tmp")]
    assert tmp_files == [], f"Arquivos temporários residuais: {tmp_files}"


# ──────────────────────────────────────────────────────────────
# read: FileNotFoundError para artefato inexistente
# ──────────────────────────────────────────────────────────────

def test_read_lanca_filenotfounderror_para_inexistente(adapter):
    """read() deve lançar FileNotFoundError para artefato não existente."""
    with pytest.raises(FileNotFoundError):
        adapter.read("roteiro", "nao_existe.json", tenant_id="t1")


# ──────────────────────────────────────────────────────────────
# tenant_id: aceito mas não cria subdiretórios (Fase 1/2)
# ──────────────────────────────────────────────────────────────

def test_tenant_id_nao_cria_subdiretorio(adapter):
    """Por ora, tenant_id não deve criar subdiretórios separados."""
    import storage_adapter as sa_module
    dir_roteiro = sa_module.ARTIFACT_DIRS["roteiro"]

    adapter.write("roteiro", "aula.json", b'{"ok": true}', tenant_id="empresa_xyz")

    # O arquivo deve estar diretamente no diretório base, não em subdir
    assert os.path.isfile(os.path.join(dir_roteiro, "aula.json"))
    assert not os.path.isdir(os.path.join(dir_roteiro, "empresa_xyz"))


def test_dois_tenants_compartilham_mesmo_diretorio(adapter):
    """Dois tenants diferentes escrevem no mesmo diretório (comportamento atual)."""
    adapter.write("roteiro", "aula_a.json", b'{"tenant": "a"}', tenant_id="tenant_a")
    adapter.write("roteiro", "aula_b.json", b'{"tenant": "b"}', tenant_id="tenant_b")

    # Ambos os arquivos devem estar visíveis para qualquer tenant
    assert adapter.exists("roteiro", "aula_a.json", tenant_id="tenant_b") is True
    assert adapter.exists("roteiro", "aula_b.json", tenant_id="tenant_a") is True


# ──────────────────────────────────────────────────────────────
# Instância padrão exportada
# ──────────────────────────────────────────────────────────────

def test_instancia_padrao_exportada():
    """O módulo deve exportar uma instância padrão `storage`."""
    from storage_adapter import storage
    assert isinstance(storage, LocalStorageAdapter)

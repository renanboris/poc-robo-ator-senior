"""
storage_adapter.py — Senior Training OS · Abstração de Storage de Artefatos
=============================================================================
Task 13: Implementar StorageAdapter com backend local.

Expõe:
  - Protocolo `StorageAdapter` com métodos: read, write, exists, list
  - Implementação `LocalStorageAdapter` usando os diretórios existentes
  - Instância padrão `storage = LocalStorageAdapter()` para uso direto

Toda escrita usa escrita atômica:
  - JSON: via safe_write_json() de utils.py
  - Binário: via tempfile + os.replace()

Toda operação de path usa safe_resolve_path() de utils.py para prevenir
ataques de path traversal.

Requisitos: 2.3.1, 2.3.2, 2.3.3, 2.3.4
"""

import json
import logging
import os
import tempfile
from typing import List, Protocol, runtime_checkable

from utils import safe_resolve_path, safe_write_json, configurar_logging

logger = configurar_logging(__name__)

# ──────────────────────────────────────────────────────────────
# Mapeamento de tipos de artefato → diretórios
# ──────────────────────────────────────────────────────────────

ARTIFACT_DIRS: dict[str, str] = {
    "roteiro":    "roteiros_salvos",
    "video":      "videos_prontos",
    "scorm":      "scorm_exports",
    "pdf":        "documentacao_pdf",
    "audio":      "audios_gerados",
    "simlink":    "sim_links",
    "biblioteca": ".",  # biblioteca_acoes.json na raiz
}


# ──────────────────────────────────────────────────────────────
# Protocolo StorageAdapter
# ──────────────────────────────────────────────────────────────

@runtime_checkable
class StorageAdapter(Protocol):
    """
    Interface de acesso a artefatos do pipeline.

    Todos os métodos recebem `tenant_id` para compatibilidade futura com
    isolamento por tenant em filesystem (Fase 3). Por ora, o parâmetro é
    aceito mas não cria subdiretórios separados — todos os artefatos ficam
    no mesmo diretório base do tipo.
    """

    def read(self, artifact_type: str, name: str, tenant_id: str) -> bytes:
        """Lê o artefato como bytes. Lança FileNotFoundError se não existir."""
        ...

    def write(self, artifact_type: str, name: str, data: bytes, tenant_id: str) -> None:
        """Escreve o artefato atomicamente."""
        ...

    def exists(self, artifact_type: str, name: str, tenant_id: str) -> bool:
        """Retorna True se o artefato existir."""
        ...

    def list(self, artifact_type: str, tenant_id: str) -> List[str]:
        """Lista os nomes de artefatos do tipo especificado."""
        ...


# ──────────────────────────────────────────────────────────────
# Implementação LocalStorageAdapter
# ──────────────────────────────────────────────────────────────

class LocalStorageAdapter:
    """
    Implementação de StorageAdapter usando o filesystem local.

    Usa os diretórios definidos em ARTIFACT_DIRS. Toda escrita é atômica:
    - JSON (.json): via safe_write_json() de utils.py
    - Binário (outros): via tempfile.mkstemp() + os.replace()

    Toda operação de path é validada via safe_resolve_path() para prevenir
    path traversal.
    """

    def _base_dir(self, artifact_type: str) -> str:
        """Retorna o diretório base para o tipo de artefato."""
        if artifact_type not in ARTIFACT_DIRS:
            raise ValueError(
                f"Tipo de artefato desconhecido: '{artifact_type}'. "
                f"Tipos válidos: {list(ARTIFACT_DIRS.keys())}"
            )
        return ARTIFACT_DIRS[artifact_type]

    def _resolve(self, artifact_type: str, name: str) -> str:
        """
        Resolve e valida o caminho completo do artefato.

        Lança ValueError se o caminho resolver para fora do diretório base
        (proteção contra path traversal).
        """
        base = self._base_dir(artifact_type)
        return safe_resolve_path(base, name)

    def read(self, artifact_type: str, name: str, tenant_id: str) -> bytes:
        """
        Lê o artefato como bytes.

        Parâmetros:
            artifact_type: tipo do artefato (chave em ARTIFACT_DIRS)
            name: nome do arquivo relativo ao diretório base
            tenant_id: identificador do tenant (aceito para compatibilidade futura)

        Retorna:
            bytes: conteúdo do arquivo

        Lança:
            ValueError: se artifact_type inválido ou path traversal detectado
            FileNotFoundError: se o artefato não existir
        """
        path = self._resolve(artifact_type, name)
        logger.debug(f"[storage] read: {artifact_type}/{name} (tenant={tenant_id})")
        with open(path, "rb") as f:
            return f.read()

    def write(self, artifact_type: str, name: str, data: bytes, tenant_id: str) -> None:
        """
        Escreve o artefato atomicamente.

        Para arquivos .json, usa safe_write_json() (serialização + atomic write).
        Para outros tipos, usa tempfile.mkstemp() + os.replace() (atomic write binário).

        Parâmetros:
            artifact_type: tipo do artefato (chave em ARTIFACT_DIRS)
            name: nome do arquivo relativo ao diretório base
            data: conteúdo a ser escrito como bytes
            tenant_id: identificador do tenant (aceito para compatibilidade futura)

        Lança:
            ValueError: se artifact_type inválido ou path traversal detectado
            OSError: se a escrita falhar
        """
        path = self._resolve(artifact_type, name)
        dir_destino = os.path.dirname(os.path.abspath(path))
        os.makedirs(dir_destino, exist_ok=True)

        logger.debug(f"[storage] write: {artifact_type}/{name} ({len(data)} bytes, tenant={tenant_id})")

        if name.endswith(".json"):
            # Para JSON, decodifica e usa safe_write_json para garantir
            # serialização correta + escrita atômica
            try:
                dados_dict = json.loads(data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                raise ValueError(
                    f"Dados inválidos para artefato JSON '{name}': {e}"
                ) from e
            safe_write_json(path, dados_dict)
        else:
            # Escrita atômica binária via tempfile + os.replace()
            fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".tmp")
            try:
                with os.fdopen(fd, "wb") as tmp_f:
                    tmp_f.write(data)
                os.replace(tmp_path, path)
            except Exception:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise

    def exists(self, artifact_type: str, name: str, tenant_id: str) -> bool:
        """
        Verifica se o artefato existe.

        Parâmetros:
            artifact_type: tipo do artefato (chave em ARTIFACT_DIRS)
            name: nome do arquivo relativo ao diretório base
            tenant_id: identificador do tenant (aceito para compatibilidade futura)

        Retorna:
            bool: True se o arquivo existir, False caso contrário

        Lança:
            ValueError: se artifact_type inválido ou path traversal detectado
        """
        path = self._resolve(artifact_type, name)
        return os.path.isfile(path)

    def list(self, artifact_type: str, tenant_id: str) -> List[str]:
        """
        Lista os nomes de artefatos do tipo especificado.

        Retorna apenas arquivos (não diretórios) presentes no diretório base
        do tipo. Não inclui subdiretórios nem arquivos temporários (.tmp).

        Parâmetros:
            artifact_type: tipo do artefato (chave em ARTIFACT_DIRS)
            tenant_id: identificador do tenant (aceito para compatibilidade futura)

        Retorna:
            List[str]: lista de nomes de arquivo (sem caminho completo)

        Lança:
            ValueError: se artifact_type inválido
        """
        base = self._base_dir(artifact_type)
        base_abs = os.path.realpath(os.path.abspath(base))

        if not os.path.isdir(base_abs):
            logger.debug(f"[storage] list: diretório '{base}' não existe, retornando lista vazia")
            return []

        result = []
        for entry in os.listdir(base_abs):
            full = os.path.join(base_abs, entry)
            # Apenas arquivos, sem temporários
            if os.path.isfile(full) and not entry.endswith(".tmp"):
                result.append(entry)

        logger.debug(f"[storage] list: {artifact_type} → {len(result)} artefatos (tenant={tenant_id})")
        return result


# ──────────────────────────────────────────────────────────────
# Instância padrão para uso direto
# ──────────────────────────────────────────────────────────────

storage = LocalStorageAdapter()

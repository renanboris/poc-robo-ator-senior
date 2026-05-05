"""
tests/test_safe_io_utils.py
============================
Testes unitários para safe_write_json() e safe_resolve_path() de utils.py.

Cobre os requisitos: 1.2.6, 1.6.4, NFR-1.6, NFR-1.7
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import safe_resolve_path, safe_write_json

# ──────────────────────────────────────────────────────────────
# safe_write_json
# ──────────────────────────────────────────────────────────────

class TestSafeWriteJson(unittest.TestCase):

    def test_escrita_bem_sucedida(self):
        """Arquivo destino é criado com o conteúdo correto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "saida.json")
            dados = {"chave": "valor", "numero": 42}

            safe_write_json(destino, dados)

            assert os.path.exists(destino)
            with open(destino, "r", encoding="utf-8") as f:
                lido = json.load(f)
            assert lido == dados

    def test_sobrescreve_arquivo_existente(self):
        """Arquivo existente é substituído atomicamente pelo novo conteúdo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "saida.json")
            dados_antigos = {"versao": 1}
            dados_novos = {"versao": 2}

            safe_write_json(destino, dados_antigos)
            safe_write_json(destino, dados_novos)

            with open(destino, "r", encoding="utf-8") as f:
                lido = json.load(f)
            assert lido == dados_novos

    def test_nenhum_arquivo_temporario_residual_em_sucesso(self):
        """Nenhum arquivo .json.tmp deve restar após escrita bem-sucedida."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "saida.json")
            safe_write_json(destino, {"ok": True})

            tmp_files = [f for f in os.listdir(tmpdir) if f.endswith(".json.tmp")]
            assert tmp_files == [], f"Arquivos temporários residuais: {tmp_files}"

    def test_arquivo_temporario_removido_em_falha(self):
        """Se os.replace() falhar, o arquivo temporário deve ser removido."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "saida.json")

            with patch("os.replace", side_effect=OSError("replace falhou")):
                with self.assertRaises(OSError):
                    safe_write_json(destino, {"dados": "teste"})

            tmp_files = [f for f in os.listdir(tmpdir) if f.endswith(".json.tmp")]
            assert tmp_files == [], f"Arquivo temporário não foi removido: {tmp_files}"

    def test_arquivo_destino_preservado_em_falha(self):
        """Arquivo destino original deve permanecer intacto se a escrita falhar."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "saida.json")
            dados_originais = {"versao": "original"}

            # Escreve versão original
            safe_write_json(destino, dados_originais)

            # Simula falha no replace durante a segunda escrita
            with patch("os.replace", side_effect=OSError("replace falhou")):
                with self.assertRaises(OSError):
                    safe_write_json(destino, {"versao": "nova"})

            # Arquivo original deve estar intacto
            with open(destino, "r", encoding="utf-8") as f:
                lido = json.load(f)
            assert lido == dados_originais

    def test_cria_diretorio_pai_se_nao_existir(self):
        """Diretório pai é criado automaticamente se não existir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "subdir", "nested", "saida.json")
            safe_write_json(destino, {"criado": True})
            assert os.path.exists(destino)

    def test_unicode_preservado(self):
        """Caracteres unicode (acentos, emojis) são preservados corretamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            destino = os.path.join(tmpdir, "unicode.json")
            dados = {"nome": "Criação de Pasta 🧩", "descricao": "Ação técnica"}

            safe_write_json(destino, dados)

            with open(destino, "r", encoding="utf-8") as f:
                lido = json.load(f)
            assert lido == dados


# ──────────────────────────────────────────────────────────────
# safe_resolve_path
# ──────────────────────────────────────────────────────────────

class TestSafeResolvePath(unittest.TestCase):

    def test_path_valido_dentro_do_base_dir(self):
        """Caminho simples dentro do base_dir é resolvido corretamente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resultado = safe_resolve_path(tmpdir, "arquivo.json")
            assert resultado == os.path.realpath(os.path.join(tmpdir, "arquivo.json"))

    def test_path_com_subdiretorio_valido(self):
        """Caminho com subdiretório dentro do base_dir é aceito."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resultado = safe_resolve_path(tmpdir, "subdir/arquivo.json")
            esperado = os.path.realpath(os.path.join(tmpdir, "subdir", "arquivo.json"))
            assert resultado == esperado

    def test_path_traversal_com_pontos_duplos(self):
        """Path com ../ tentando sair do base_dir deve lançar ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError) as ctx:
                safe_resolve_path(tmpdir, "../secrets.txt")
            assert "fora do diretório base" in str(ctx.exception)

    def test_path_traversal_aninhado(self):
        """Path traversal aninhado (subdir/../../etc) deve ser bloqueado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with self.assertRaises(ValueError):
                safe_resolve_path(tmpdir, "subdir/../../etc/passwd")

    def test_path_absoluto_fora_do_base_dir(self):
        """Caminho absoluto fora do base_dir deve lançar ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_externo = tempfile.gettempdir()
            with self.assertRaises(ValueError):
                safe_resolve_path(tmpdir, caminho_externo)

    def test_mensagem_de_erro_descritiva(self):
        """A mensagem de ValueError deve identificar o caminho problemático."""
        with tempfile.TemporaryDirectory() as tmpdir:
            caminho_malicioso = "../fora"
            with self.assertRaises(ValueError) as ctx:
                safe_resolve_path(tmpdir, caminho_malicioso)
            assert caminho_malicioso in str(ctx.exception)

    def test_path_exatamente_igual_ao_base_dir(self):
        """Caminho que resolve para o próprio base_dir é aceito."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resultado = safe_resolve_path(tmpdir, ".")
            assert resultado == os.path.realpath(tmpdir)

    def test_retorna_caminho_absoluto(self):
        """O caminho retornado deve ser sempre absoluto."""
        with tempfile.TemporaryDirectory() as tmpdir:
            resultado = safe_resolve_path(tmpdir, "arquivo.json")
            assert os.path.isabs(resultado)


if __name__ == "__main__":
    unittest.main()

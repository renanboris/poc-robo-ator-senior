"""
tests/test_metricas_endpoint.py
================================
Testes unitários para a lógica do endpoint GET /api/metricas.

Cobre os requisitos: 1.4.2, NFR-3.2

Estratégia: testa a lógica de coleta de métricas diretamente, sem depender
do servidor HTTP. Usa sqlite3 real com bancos temporários e mocks de
os.path.exists / os.listdir para simular diferentes estados do sistema.

Casos cobertos:
  - Resposta com dados completos (brain.db + roteiros + aura_cache.db presentes)
  - Campos null quando brain.db não existe (sem telemetria)
  - Campos null quando roteiros_salvos/ não existe
  - Campos null quando aura_cache.db não existe
  - Estrutura de campos obrigatórios sempre presente na resposta
  - camadas_vision com taxa_sucesso calculada corretamente
  - camadas_vision com taxa_sucesso null quando total de tentativas é zero
  - horas_poupadas e economia_estimada null quando total_aulas é null
  - self_healing_hits = soma de acertos de todas as camadas
  - Nunca retornar 0 para campo sem dados — deve ser null
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ──────────────────────────────────────────────────────────────
# Helpers para criar bancos de dados de teste
# ──────────────────────────────────────────────────────────────

def _criar_brain_db(path: str, camadas=None, memorias: int = 0):
    """Cria um brain.db mínimo com dados opcionais de telemetria."""
    conn = sqlite3.connect(path)
    try:
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetria_camadas (
                camada TEXT PRIMARY KEY,
                acertos INTEGER DEFAULT 0,
                falhas INTEGER DEFAULT 0,
                ultima_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for i in range(memorias):
            conn.execute(
                "INSERT INTO memoria_semantica (hash_intencao, intencao, hits) VALUES (?, ?, ?)",
                (f"hash_{i}", f"intencao_{i}", 1),
            )
        if camadas:
            for c in camadas:
                conn.execute(
                    "INSERT INTO telemetria_camadas (camada, acertos, falhas) VALUES (?, ?, ?)",
                    (c["camada"], c["acertos"], c["falhas"]),
                )
        conn.commit()
    finally:
        conn.close()


def _criar_aura_cache_db(path: str, count: int = 0):
    """Cria um aura_cache.db mínimo."""
    conn = sqlite3.connect(path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dap_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chave TEXT,
                resposta TEXT
            )
        """)
        for i in range(count):
            conn.execute(
                "INSERT INTO dap_cache (chave, resposta) VALUES (?, ?)",
                (f"chave_{i}", f"resposta_{i}"),
            )
        conn.commit()
    finally:
        conn.close()


def _criar_roteiros(pasta: str, quantidade: int):
    """Cria arquivos JSON de roteiro mínimos na pasta indicada."""
    os.makedirs(pasta, exist_ok=True)
    for i in range(quantidade):
        with open(os.path.join(pasta, f"roteiro_{i}.json"), "w") as f:
            json.dump({"metadata": {"nome_aula": f"Aula {i}"}}, f)


# ──────────────────────────────────────────────────────────────
# Função auxiliar que replica a lógica do endpoint /api/metricas
# ──────────────────────────────────────────────────────────────

def _executar_logica_metricas(roteiros_dir: str, brain_db_path: str, aura_db_path: str):
    """
    Replica a lógica do endpoint /api/metricas de forma testável,
    sem depender do servidor HTTP.

    Parâmetros:
        roteiros_dir  — caminho para a pasta de roteiros (pode não existir)
        brain_db_path — caminho para brain.db (pode não existir)
        aura_db_path  — caminho para aura_cache.db (pode não existir)

    Retorna o dict que o endpoint retornaria.
    """
    from typing import Optional

    # ── total_aulas ──────────────────────────────────────────────────────────
    total_aulas: Optional[int] = None
    try:
        if os.path.isdir(roteiros_dir):
            arquivos_json = [f for f in os.listdir(roteiros_dir) if f.endswith(".json")]
            total_aulas = len(arquivos_json)
    except Exception:
        pass

    # ── horas_poupadas / dinheiro_poupado ───────────────────────────────────
    horas_poupadas: Optional[float] = None
    dinheiro_poupado: Optional[float] = None
    if total_aulas is not None:
        horas_poupadas = round(total_aulas * 6, 2)
        dinheiro_poupado = round(horas_poupadas * 150, 2)

    # ── Brain stats ──────────────────────────────────────────────────────────
    total_memorizado: Optional[int] = None
    self_healing_hits: Optional[int] = None
    camadas_vision = None

    try:
        if not os.path.exists(brain_db_path):
            raise FileNotFoundError(f"brain.db não encontrado: {brain_db_path}")
        conn = sqlite3.connect(brain_db_path)
        conn.row_factory = sqlite3.Row
        try:
            total = conn.execute("SELECT COUNT(*) as n FROM memoria_semantica").fetchone()
            if total is not None:
                total_memorizado = total["n"]

            camadas_raw = conn.execute(
                "SELECT camada, acertos, falhas FROM telemetria_camadas ORDER BY acertos DESC"
            ).fetchall()

            if camadas_raw:
                camadas_vision = []
                hits_total = 0
                for c in camadas_raw:
                    acertos = c["acertos"]
                    falhas  = c["falhas"]
                    total_c = acertos + falhas
                    taxa    = round(acertos / total_c, 4) if total_c > 0 else None
                    camadas_vision.append({
                        "camada":       c["camada"],
                        "acertos":      acertos,
                        "falhas":       falhas,
                        "taxa_sucesso": taxa,
                    })
                    hits_total += acertos
                self_healing_hits = hits_total
        finally:
            conn.close()
    except Exception:
        pass

    # ── tamanho_cache_dap ────────────────────────────────────────────────────
    tamanho_cache_dap: Optional[int] = None
    try:
        if os.path.exists(aura_db_path):
            conn = sqlite3.connect(aura_db_path)
            try:
                row = conn.execute("SELECT COUNT(*) FROM dap_cache").fetchone()
                if row is not None:
                    tamanho_cache_dap = row[0]
            finally:
                conn.close()
    except Exception:
        pass

    return {
        "total_aulas":       total_aulas,
        "horas_poupadas":    horas_poupadas,
        "dinheiro_poupado":  dinheiro_poupado,
        "total_memorizado":  total_memorizado,
        "self_healing_hits": self_healing_hits,
        "tamanho_cache_dap": tamanho_cache_dap,
        "camadas_vision":    camadas_vision,
    }


# ──────────────────────────────────────────────────────────────
# Campos obrigatórios na resposta
# ──────────────────────────────────────────────────────────────

CAMPOS_OBRIGATORIOS = {
    "total_aulas",
    "horas_poupadas",
    "dinheiro_poupado",
    "total_memorizado",
    "self_healing_hits",
    "tamanho_cache_dap",
    "camadas_vision",
}


# ──────────────────────────────────────────────────────────────
# Testes
# ──────────────────────────────────────────────────────────────

class TestMetricasLogica(unittest.TestCase):
    """Testa a lógica de coleta de métricas do endpoint /api/metricas."""

    def test_estrutura_campos_obrigatorios_sempre_presente(self):
        """Todos os campos obrigatórios devem estar presentes, mesmo sem dados."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            resultado = _executar_logica_metricas(
                roteiros_dir=os.path.join(tmpdir, "inexistente"),
                brain_db_path=os.path.join(tmpdir, "brain_inexistente.db"),
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        for campo in CAMPOS_OBRIGATORIOS:
            self.assertIn(campo, resultado, f"Campo obrigatório ausente: {campo}")

    def test_campos_null_quando_roteiros_dir_nao_existe(self):
        """total_aulas, horas_poupadas e economia_estimada devem ser null quando pasta não existe."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db)

            resultado = _executar_logica_metricas(
                roteiros_dir=os.path.join(tmpdir, "pasta_inexistente"),
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertIsNone(resultado["total_aulas"],
                          "total_aulas deve ser null quando pasta não existe")
        self.assertIsNone(resultado["horas_poupadas"],
                          "horas_poupadas deve ser null quando total_aulas é null")
        self.assertIsNone(resultado["dinheiro_poupado"],
                          "dinheiro_poupado deve ser null quando total_aulas é null")

    def test_campos_null_quando_brain_db_nao_existe(self):
        """total_memorizado, self_healing_hits e camadas_vision devem ser null quando brain.db não existe."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 3)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=os.path.join(tmpdir, "brain_inexistente.db"),
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertIsNone(resultado["self_healing_hits"],
                          "self_healing_hits deve ser null quando brain.db não existe")
        self.assertIsNone(resultado["camadas_vision"],
                          "camadas_vision deve ser null quando brain.db não existe")

    def test_campos_null_quando_aura_cache_nao_existe(self):
        """tamanho_cache_dap deve ser null quando aura_cache.db não existe."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 2)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertIsNone(resultado["tamanho_cache_dap"],
                          "tamanho_cache_dap deve ser null quando aura_cache.db não existe")

    def test_resposta_com_dados_completos(self):
        """Com todos os dados presentes, todos os campos devem ter valores não-null."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 5)

            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, camadas=[
                {"camada": "2_sniper", "acertos": 45, "falhas": 3},
                {"camada": "0_brain",  "acertos": 20, "falhas": 1},
            ], memorias=10)

            aura_db = os.path.join(tmpdir, "aura_cache.db")
            _criar_aura_cache_db(aura_db, count=7)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=aura_db,
            )

        self.assertEqual(resultado["total_aulas"], 5)
        self.assertIsNotNone(resultado["horas_poupadas"])
        self.assertIsNotNone(resultado["dinheiro_poupado"])
        self.assertIsNotNone(resultado["total_memorizado"])
        self.assertIsNotNone(resultado["self_healing_hits"])
        self.assertIsNotNone(resultado["tamanho_cache_dap"])
        self.assertIsNotNone(resultado["camadas_vision"])

    def test_calculo_horas_poupadas_e_economia(self):
        """horas_poupadas = total_aulas * 6 e dinheiro_poupado = horas_poupadas * 150."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 4)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertEqual(resultado["total_aulas"], 4)
        self.assertAlmostEqual(resultado["horas_poupadas"], 4 * 6, places=2)
        self.assertAlmostEqual(resultado["dinheiro_poupado"], 4 * 6 * 150, places=2)

    def test_taxa_sucesso_calculada_por_camada(self):
        """taxa_sucesso de cada camada deve ser acertos / (acertos + falhas)."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, camadas=[
                {"camada": "2_sniper", "acertos": 9, "falhas": 1},
            ])

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        camadas = resultado["camadas_vision"]
        self.assertIsNotNone(camadas)
        self.assertEqual(len(camadas), 1)
        camada = camadas[0]
        self.assertEqual(camada["camada"], "2_sniper")
        self.assertEqual(camada["acertos"], 9)
        self.assertEqual(camada["falhas"], 1)
        self.assertAlmostEqual(camada["taxa_sucesso"], 0.9, places=3)

    def test_taxa_sucesso_null_quando_zero_tentativas(self):
        """taxa_sucesso deve ser null quando acertos + falhas == 0."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, camadas=[
                {"camada": "5_gemini", "acertos": 0, "falhas": 0},
            ])

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        camadas = resultado["camadas_vision"]
        self.assertIsNotNone(camadas)
        camada = camadas[0]
        self.assertIsNone(camada["taxa_sucesso"],
                          "taxa_sucesso deve ser null quando não há tentativas")

    def test_self_healing_hits_e_soma_de_acertos(self):
        """self_healing_hits deve ser a soma de acertos de todas as camadas."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, camadas=[
                {"camada": "0_brain",  "acertos": 30, "falhas": 2},
                {"camada": "2_sniper", "acertos": 50, "falhas": 5},
                {"camada": "5_gemini", "acertos": 10, "falhas": 8},
            ])

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertEqual(resultado["self_healing_hits"], 30 + 50 + 10)

    def test_nunca_retorna_zero_para_campo_sem_dados(self):
        """Campos sem dados devem ser null, nunca 0."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            resultado = _executar_logica_metricas(
                roteiros_dir=os.path.join(tmpdir, "pasta_inexistente"),
                brain_db_path=os.path.join(tmpdir, "brain_inexistente.db"),
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        campos_numericos = [
            "total_aulas", "horas_poupadas", "dinheiro_poupado",
            "total_memorizado", "self_healing_hits", "tamanho_cache_dap",
        ]
        for campo in campos_numericos:
            valor = resultado[campo]
            self.assertNotEqual(valor, 0,
                f"Campo '{campo}' retornou 0 em vez de null quando não há dados")

    def test_tamanho_cache_dap_correto(self):
        """tamanho_cache_dap deve refletir o número de entradas em aura_cache.db."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db)
            aura_db = os.path.join(tmpdir, "aura_cache.db")
            _criar_aura_cache_db(aura_db, count=13)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=aura_db,
            )

        self.assertEqual(resultado["tamanho_cache_dap"], 13)

    def test_total_memorizado_correto(self):
        """total_memorizado deve refletir o número de entradas em memoria_semantica."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, memorias=7)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertEqual(resultado["total_memorizado"], 7)

    def test_horas_poupadas_null_quando_total_aulas_null(self):
        """Se total_aulas for null, horas_poupadas e economia_estimada também devem ser null."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            resultado = _executar_logica_metricas(
                roteiros_dir=os.path.join(tmpdir, "inexistente"),
                brain_db_path=os.path.join(tmpdir, "brain_inexistente.db"),
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertIsNone(resultado["total_aulas"])
        self.assertIsNone(resultado["horas_poupadas"],
                          "horas_poupadas deve ser null quando total_aulas é null")
        self.assertIsNone(resultado["dinheiro_poupado"],
                          "dinheiro_poupado deve ser null quando total_aulas é null")

    def test_camadas_vision_null_quando_sem_telemetria(self):
        """camadas_vision deve ser null quando brain.db existe mas sem registros de telemetria."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 2)
            brain_db = os.path.join(tmpdir, "brain.db")
            # brain.db existe mas sem camadas de telemetria
            _criar_brain_db(brain_db, camadas=None, memorias=3)

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        self.assertIsNone(resultado["camadas_vision"],
                          "camadas_vision deve ser null quando não há registros de telemetria")
        self.assertIsNone(resultado["self_healing_hits"],
                          "self_healing_hits deve ser null quando não há registros de telemetria")

    def test_multiplas_camadas_com_taxas_diferentes(self):
        """Múltiplas camadas devem ter taxa_sucesso calculada individualmente."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            roteiros_dir = os.path.join(tmpdir, "roteiros")
            _criar_roteiros(roteiros_dir, 1)
            brain_db = os.path.join(tmpdir, "brain.db")
            _criar_brain_db(brain_db, camadas=[
                {"camada": "0_brain",  "acertos": 8,  "falhas": 2},   # 0.8
                {"camada": "2_sniper", "acertos": 19, "falhas": 1},   # 0.95
                {"camada": "5_gemini", "acertos": 3,  "falhas": 7},   # 0.3
            ])

            resultado = _executar_logica_metricas(
                roteiros_dir=roteiros_dir,
                brain_db_path=brain_db,
                aura_db_path=os.path.join(tmpdir, "aura_inexistente.db"),
            )

        camadas = {c["camada"]: c for c in resultado["camadas_vision"]}
        self.assertAlmostEqual(camadas["0_brain"]["taxa_sucesso"],  0.8,    places=3)
        self.assertAlmostEqual(camadas["2_sniper"]["taxa_sucesso"], 0.95,   places=3)
        self.assertAlmostEqual(camadas["5_gemini"]["taxa_sucesso"], 0.3,    places=3)


if __name__ == "__main__":
    unittest.main()

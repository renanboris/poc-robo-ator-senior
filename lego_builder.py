"""
lego_builder.py — A Fábrica de Peças (Biblioteca de Ações)
===========================================================
Varre todos os treinamentos validados e extrai as ações técnicas
para criar o "Cérebro Montador" do Gerador por Prompt.

Pode ser executado diretamente:
    python lego_builder.py [--verbose]

Ou chamado programaticamente (ex: via endpoint /api/rebuild-library):
    from lego_builder import construir_biblioteca
    resultado = construir_biblioteca(verbosity="concise")
"""
import os
import sys
import copy
import json
import logging
from datetime import datetime
from typing import Literal, List, Dict, Any

from utils import safe_write_json
import score_engine as _score_engine

logger = logging.getLogger("lego_builder")

ROTEIROS_DIR = "roteiros_salvos"
BIBLIOTECA_FILE = "biblioteca_acoes.json"

VerbosityLevel = Literal["concise", "verbose"]


# ═══════════════════════════════════════════════════════════════════════════
# Display Controller Classes
# ═══════════════════════════════════════════════════════════════════════════

class _OutputFormatter:
    """Standardize visual presentation of output."""
    
    def __init__(self, separator_length: int = 35):
        self.separator_length = separator_length
    
    def create_separator(self) -> str:
        """Generate consistent separator line."""
        return "=" * self.separator_length
    
    def create_header(self, title: str) -> str:
        """Create concise header with title."""
        sep = self.create_separator()
        return f"{sep}\n{title}\n{sep}"
    
    def format_summary_block(self, stats: Dict[str, Any]) -> str:
        """Format consolidated summary block with aligned columns."""
        sep = self.create_separator()
        lines = [
            "",
            sep,
            "CONCLUIDO",
            sep,
            f"Roteiros processados : {stats['total_roteiros']}",
            f"Ações encontradas    : {stats['total_acoes_lidas']}",
            f"Peças únicas novas   : {stats['total_acoes_novas']}",
            f"Arquivo salvo        : {stats['arquivo']}",
            f"Versão               : {stats['versao_biblioteca']}",
        ]
        
        if stats.get('erros'):
            lines.append(f"Arquivos com erro    : {len(stats['erros'])}")
        
        lines.append(sep)
        return "\n".join(lines)
    
    def highlight_critical(self, message: str) -> str:
        """Highlight critical information."""
        return f"[!] {message}"


class _ProgressTracker:
    """Track and report progress during batch processing."""
    
    def __init__(self):
        self.total_files = 0
        self.processed_files = 0
        self.new_actions = 0
        self.errors: List[str] = []
        self.batch_size = 10
        self.last_progress_update = 0
    
    def update_progress(self, files_processed: int) -> None:
        """Update progress counters."""
        self.processed_files = files_processed
    
    def add_error(self, error_message: str) -> None:
        """Add error to aggregation list."""
        self.errors.append(error_message)
    
    def should_show_progress(self) -> bool:
        """Determine if progress update should be shown."""
        if self.processed_files == 0:
            return False
        
        # Show progress every batch_size files or at completion
        if (self.processed_files % self.batch_size == 0 or 
            self.processed_files == self.total_files):
            if self.processed_files != self.last_progress_update:
                self.last_progress_update = self.processed_files
                return True
        return False
    
    def get_progress_string(self) -> str:
        """Format progress string with percentage."""
        if self.total_files == 0:
            return ""
        
        percentage = int((self.processed_files / self.total_files) * 100)
        return f"[Progresso] Processados {self.processed_files}/{self.total_files} roteiros ({percentage}%)"


class _VerbosityManager:
    """Manage different verbosity levels and filtering."""
    
    def __init__(self, level: VerbosityLevel = "concise"):
        self.level = level
    
    def should_show_individual_actions(self) -> bool:
        """Check if individual action logging should be shown."""
        return self.level == "verbose"
    
    def should_show_batch_progress(self) -> bool:
        """Check if batch progress should be shown."""
        return self.level == "concise"


class _DisplayController:
    """Central coordination of all display-related functionality."""
    
    def __init__(self, verbosity: VerbosityLevel = "concise"):
        self.verbosity = verbosity
        self.progress_tracker = _ProgressTracker()
        self.formatter = _OutputFormatter()
        self.verbosity_manager = _VerbosityManager(verbosity)
    
    def start_execution(self, total_files: int) -> None:
        """Display execution start header."""
        self.progress_tracker.total_files = total_files
        header = self.formatter.create_header("Extração de Peças de Lego")
        _log(header)
        _log(f"Encontrados {total_files} roteiros para análise.\n")
    
    def log_progress(self) -> None:
        """Log batch progress if appropriate."""
        if (self.verbosity_manager.should_show_batch_progress() and 
            self.progress_tracker.should_show_progress()):
            progress_str = self.progress_tracker.get_progress_string()
            if progress_str:
                _log(progress_str)
    
    def log_new_action(self, intencao: str, arquivo: str) -> None:
        """Log new action cataloging."""
        self.progress_tracker.new_actions += 1
        
        if self.verbosity_manager.should_show_individual_actions():
            _log(f"  + Peça catalogada: '{intencao}' (de {arquivo})")
    
    def log_error(self, message: str) -> None:
        """Log error (always shown regardless of verbosity)."""
        formatted = self.formatter.highlight_critical(message)
        _log(f"  {formatted}")
        self.progress_tracker.add_error(message)
    
    def complete_execution(self, stats: Dict[str, Any]) -> None:
        """Display final summary."""
        summary = self.formatter.format_summary_block(stats)
        _log(summary)


# ═══════════════════════════════════════════════════════════════════════════
# Main Function
# ═══════════════════════════════════════════════════════════════════════════

def construir_biblioteca(
    roteiros_dir: str = ROTEIROS_DIR,
    biblioteca_file: str = BIBLIOTECA_FILE,
    verbosity: VerbosityLevel = "concise"
) -> dict:
    """
    Varre roteiros_dir, extrai ações técnicas únicas e salva em biblioteca_file.

    Args:
        roteiros_dir: Diretório contendo os roteiros salvos
        biblioteca_file: Arquivo de saída da biblioteca
        verbosity: Nível de verbosidade ("concise" ou "verbose")

    Retorna um dict de status com:
        status              : "sucesso" | "erro"
        total_roteiros      : int — quantos arquivos foram processados
        total_acoes_lidas   : int — total de ações encontradas (com duplicatas)
        total_acoes_novas   : int — peças únicas adicionadas à biblioteca
        arquivo             : str — caminho do arquivo gerado
        versao_biblioteca   : str — identificador de versão gerado neste rebuild (timestamp ISO)
        mensagem            : str — mensagem de erro (somente se status == "erro")
    """
    # Resolve verbosity from environment if not explicitly set
    if verbosity == "concise":
        env_verbosity = os.environ.get("LEGO_BUILDER_VERBOSITY", "").lower()
        if env_verbosity in ["verbose", "v"]:
            verbosity = "verbose"
    
    display = _DisplayController(verbosity)
    
    if not os.path.exists(roteiros_dir):
        msg = f"Pasta '{roteiros_dir}' não encontrada."
        _log(f"Erro: {msg}")
        return {"status": "erro", "mensagem": msg}

    biblioteca: dict = {}
    total_acoes_lidas = 0
    total_acoes_novas = 0
    total_roteiros = 0
    erros = []

    # Identificador de versão gerado a cada Rebuild bem-sucedido
    versao_biblioteca = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # sorted() garante ordem determinística entre execuções e SOs
    arquivos = sorted(f for f in os.listdir(roteiros_dir) if f.endswith(".json"))
    
    display.start_execution(len(arquivos))

    for idx, arquivo in enumerate(arquivos, 1):
        caminho = os.path.join(roteiros_dir, arquivo)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                roteiro = json.load(f)

            total_roteiros += 1
            display.progress_tracker.update_progress(total_roteiros)

            for passo in roteiro.get("passos", []):
                for acao in passo.get("acoes_tecnicas", []):
                    intencao = acao.get("intencao_semantica", "").strip()

                    # Ignora ações sem intenção semântica ou passos de encerramento
                    if not intencao or acao.get("acao") == "concluir_video":
                        continue

                    total_acoes_lidas += 1
                    chave = intencao.lower()

                    if chave not in biblioteca:
                        # deepcopy antes de qualquer mutação
                        acao_limpa = copy.deepcopy(acao)

                        # Remove screenshot Base64
                        if "elemento_alvo" in acao_limpa:
                            acao_limpa["elemento_alvo"].pop("screenshot_referencia", None)

                        # Adiciona proveniência para rastreabilidade
                        acao_limpa["_source"] = arquivo
                        acao_limpa["_versao_biblioteca"] = versao_biblioteca

                        # Score de confiabilidade da ação
                        try:
                            score_info = _score_engine.obter_score(chave)
                            requer_revisao = (score_info is not None and score_info < 0.5)
                        except Exception:
                            score_info = None
                            requer_revisao = False

                        acao_limpa["_score_confiabilidade"] = score_info
                        acao_limpa["_requer_revisao"] = requer_revisao

                        biblioteca[chave] = acao_limpa
                        total_acoes_novas += 1
                        display.log_new_action(intencao, arquivo)

            # Log batch progress
            display.log_progress()

        except json.JSONDecodeError as e:
            msg = f"JSON inválido em '{arquivo}': {e}"
            display.log_error(msg)
            erros.append(msg)
        except Exception as e:
            msg = f"Erro ao ler '{arquivo}': {e}"
            display.log_error(msg)
            erros.append(msg)

    if not biblioteca:
        msg = "Nenhuma ação com intencao_semantica foi encontrada nos roteiros."
        _log(f"\nAviso: {msg}")
        return {
            "status": "erro",
            "mensagem": msg,
            "total_roteiros": total_roteiros,
            "total_acoes_lidas": total_acoes_lidas,
            "total_acoes_novas": 0,
        }

    # Escrita atômica via safe_write_json
    try:
        safe_write_json(biblioteca_file, biblioteca)
    except Exception as e:
        msg = f"Falha ao salvar biblioteca: {e}"
        _log(f"Erro: {msg}")
        return {"status": "erro", "mensagem": msg}

    # Display final summary
    stats = {
        "total_roteiros": total_roteiros,
        "total_acoes_lidas": total_acoes_lidas,
        "total_acoes_novas": total_acoes_novas,
        "arquivo": biblioteca_file,
        "versao_biblioteca": versao_biblioteca,
        "erros": erros,
    }
    display.complete_execution(stats)

    return {
        "status": "sucesso",
        "arquivo": biblioteca_file,
        "total_roteiros": total_roteiros,
        "total_acoes_lidas": total_acoes_lidas,
        "total_acoes_novas": total_acoes_novas,
        "versao_biblioteca": versao_biblioteca,
        "erros": erros,
    }


def _log(msg: str) -> None:
    """Emite a mensagem tanto no logger (para app.py/uvicorn) quanto no stdout (para CLI)."""
    print(msg)
    logger.info(msg)


if __name__ == "__main__":
    # Parse command-line arguments
    verbosity: VerbosityLevel = "concise"
    if "--verbose" in sys.argv or "-v" in sys.argv:
        verbosity = "verbose"
    
    resultado = construir_biblioteca(verbosity=verbosity)
    if resultado["status"] == "erro":
        sys.exit(1)

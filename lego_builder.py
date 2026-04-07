"""
lego_builder.py — A Fábrica de Peças (Biblioteca de Ações)
===========================================================
Varre todos os treinamentos validados e extrai as ações técnicas
para criar o "Cérebro Montador" do Gerador por Prompt.

Pode ser executado diretamente:
    python lego_builder.py

Ou chamado programaticamente (ex: via endpoint /api/rebuild-library):
    from lego_builder import construir_biblioteca
    resultado = construir_biblioteca()
"""
import os
import copy     # FIX #1 — necessário para não mutar os dicts originais carregados do JSON
import json
import logging
from datetime import datetime

from utils import safe_write_json
import score_engine as _score_engine

logger = logging.getLogger("lego_builder")

ROTEIROS_DIR   = "roteiros_salvos"
BIBLIOTECA_FILE = "biblioteca_acoes.json"


def construir_biblioteca(roteiros_dir: str = ROTEIROS_DIR, biblioteca_file: str = BIBLIOTECA_FILE) -> dict:
    """
    Varre roteiros_dir, extrai ações técnicas únicas e salva em biblioteca_file.

    Retorna um dict de status com:
        status              : "sucesso" | "erro"
        total_roteiros      : int — quantos arquivos foram processados
        total_acoes_lidas   : int — total de ações encontradas (com duplicatas)
        total_acoes_novas   : int — peças únicas adicionadas à biblioteca
        arquivo             : str — caminho do arquivo gerado
        versao_biblioteca   : str — identificador de versão gerado neste rebuild (timestamp ISO)
        mensagem            : str — mensagem de erro (somente se status == "erro")
    """
    _log("=" * 50)
    _log("🧱 INICIANDO A EXTRAÇÃO DE PEÇAS DE LEGO...")
    _log("=" * 50)

    if not os.path.exists(roteiros_dir):
        msg = f"Pasta '{roteiros_dir}' não encontrada."
        _log(f"Erro: {msg}")
        return {"status": "erro", "mensagem": msg}

    biblioteca: dict = {}
    total_acoes_lidas = 0
    total_acoes_novas = 0
    total_roteiros    = 0
    erros             = []

    # Identificador de versão gerado a cada Rebuild bem-sucedido (Requisito 2.6.3)
    versao_biblioteca = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # FIX #2 — sorted() garante ordem determinística entre execuções e SOs.
    # Sem sorted(), os.listdir() tem ordem aleatória: se dois roteiros têm a mesma
    # intencao_semantica, o "vencedor" mudaria a cada run — difícil de reproduzir.
    arquivos = sorted(f for f in os.listdir(roteiros_dir) if f.endswith(".json"))
    _log(f"Encontrados {len(arquivos)} roteiros para análise.\n")

    for arquivo in arquivos:
        caminho = os.path.join(roteiros_dir, arquivo)
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                roteiro = json.load(f)

            total_roteiros += 1

            for passo in roteiro.get("passos", []):
                for acao in passo.get("acoes_tecnicas", []):
                    intencao = acao.get("intencao_semantica", "").strip()

                    # Ignora ações sem intenção semântica ou passos de encerramento
                    if not intencao or acao.get("acao") == "concluir_video":
                        continue

                    total_acoes_lidas += 1
                    chave = intencao.lower()

                    if chave not in biblioteca:
                        # FIX #3 — deepcopy antes de qualquer mutação para não alterar
                        # o dict original carregado do arquivo. Sem isso, a remoção do
                        # screenshot_referencia abaixo mutava o roteiro em memória.
                        acao_limpa = copy.deepcopy(acao)

                        # Remove screenshot Base64 — estouraria o context window do Gemini
                        if "elemento_alvo" in acao_limpa:
                            acao_limpa["elemento_alvo"].pop("screenshot_referencia", None)

                        # FIX #4 — adiciona proveniência para rastreabilidade.
                        # Se um roteiro for corrigido ou deletado, saberemos quais
                        # peças precisam ser revisadas na biblioteca.
                        acao_limpa["_source"] = arquivo

                        # Versão da biblioteca gerada neste Rebuild (Requisito 2.6.3)
                        acao_limpa["_versao_biblioteca"] = versao_biblioteca

                        # Score de confiabilidade da ação (Requisito 3.2.5)
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
                        _log(f"  + Peça catalogada: '{intencao}' (de {arquivo})")

        except json.JSONDecodeError as e:
            msg = f"JSON inválido em '{arquivo}': {e}"
            _log(f"  ⚠ {msg}")
            erros.append(msg)
        except Exception as e:
            msg = f"Erro ao ler '{arquivo}': {e}"
            _log(f"  ⚠ {msg}")
            erros.append(msg)

    if not biblioteca:
        msg = "Nenhuma ação com intencao_semantica foi encontrada nos roteiros."
        _log(f"\nAviso: {msg}")
        # Não é um erro fatal — pode ser que os roteiros não tenham sido capturados ainda
        return {
            "status": "erro",
            "mensagem": msg,
            "total_roteiros": total_roteiros,
            "total_acoes_lidas": total_acoes_lidas,
            "total_acoes_novas": 0,
        }

    # FIX #5 — escrita atômica via safe_write_json (canônica em utils.py):
    # grava em arquivo temporário e só então renomeia atomicamente.
    # Sem isso, uma interrupção no meio da escrita corrompe biblioteca_acoes.json,
    # derrubando toda a geração de IA até o próximo rebuild manual.
    try:
        safe_write_json(biblioteca_file, biblioteca)
    except Exception as e:
        msg = f"Falha ao salvar biblioteca: {e}"
        _log(f"Erro: {msg}")
        return {"status": "erro", "mensagem": msg}

    _log("\n" + "=" * 50)
    _log(f"✅ SUCESSO!")
    _log(f"   Roteiros processados : {total_roteiros}")
    _log(f"   Ações encontradas    : {total_acoes_lidas}")
    _log(f"   Peças únicas novas   : {total_acoes_novas}")   # FIX #6 — nome correto
    _log(f"   Arquivo salvo em     : {biblioteca_file}")
    if erros:
        _log(f"   ⚠ Arquivos com erro  : {len(erros)}")
    _log("=" * 50 + "\n")

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
    resultado = construir_biblioteca()
    if resultado["status"] == "erro":
        import sys
        sys.exit(1)

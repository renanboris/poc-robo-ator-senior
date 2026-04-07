"""
utils.py — Senior Training OS · Utilitários Compartilhados
===========================================================
FIX Bug #DRY-01: limpar_nome estava duplicada em 6 arquivos diferentes.
FIX Bug #PINECONE-01: Normalização ASCII pura para evitar crashes no banco vetorial.
FIX Bug #DRY-02: validar_roteiro centralizada — era duplicada em capture.py e app.py.
Task 3: safe_write_json e safe_resolve_path centralizadas para I/O seguro.
Task 7: configurar_logging centralizada — formato estruturado consistente.

Esta é agora a ÚNICA fonte de verdade. Todos os módulos devem importar daqui:

    from utils import limpar_nome, validar_roteiro, validar_roteiro_ia
    from utils import safe_write_json, safe_resolve_path
    from utils import configurar_logging
"""

import json
import logging
import os
import re
import tempfile
import time
import unicodedata

def limpar_nome(nome: str) -> str:
    """
    Sanitiza uma string para uso seguro como nome de arquivo/pasta e IDs Vetoriais.

    Remove acentos (garantindo ASCII puro), caracteres proibidos no Windows/Mac/Linux
    e limita a 40 caracteres. Espaços são convertidos em underscores.

    Parâmetros:
        nome (str): String de entrada a ser sanitizada.

    Retorna:
        str: String sanitizada, segura para uso como nome de arquivo ou ID vetorial.
             Máximo de 40 caracteres, sem underscores nas extremidades.

    Exemplos:
        >>> limpar_nome("Criação de Pasta")
        'Criacao_de_Pasta'
        >>> limpar_nome("GED: M01/A01 <Setup>")
        'GED_M01A01_Setup'
    """
    # 1. Normaliza a string e arranca os acentos (Ex: "Criação" -> "Criacao")
    nome_norm = unicodedata.normalize('NFKD', nome).encode('ASCII', 'ignore').decode('utf-8')

    # 2. Remove os caracteres proibidos de Sistema Operacional e formata os espaços
    return re.sub(r'[\\/*?:"<>|]', "", nome_norm).replace(" ", "_")[:40].strip("_")


def validar_roteiro(roteiro: dict) -> tuple[bool, str]:
    """
    Portão de qualidade centralizado para roteiros do Senior Training OS.
    Fonte canônica — não duplicar em outros módulos.

    Critérios mínimos:
      - >= 2 passos (1 real + 1 conclusão)
      - >= 50% das ações técnicas válidas com seletor_hint preenchido
      - <= 70% das ações técnicas válidas com confianca_captura == 'baixa'

    Ações com acao == 'concluir_video' são ignoradas nos cálculos.

    Parâmetros:
        roteiro (dict): Dicionário representando o roteiro JSON do treinamento.

    Retorna:
        tuple[bool, str]: Par (aprovado, motivo) onde:
            - aprovado (bool): True se o roteiro passou em todos os critérios.
            - motivo (str): Descrição legível do resultado — motivo de reprovação
              ou resumo de aprovação com métricas.

    Exceções:
        Não lança exceções. Entradas malformadas resultam em reprovação com motivo.
    """
    passos = roteiro.get("passos", [])
    if len(passos) < 2:
        return False, f"Apenas {len(passos)} passo(s) — mapeamento insuficiente."

    total_acoes = acoes_com_seletor = acoes_baixa_conf = 0

    for passo in passos:
        for acao in passo.get("acoes_tecnicas", []):
            if acao.get("acao") == "concluir_video":
                continue
            total_acoes += 1
            alvo = acao.get("elemento_alvo", {})
            if alvo.get("seletor_hint", "").strip():
                acoes_com_seletor += 1
            if alvo.get("confianca_captura") == "baixa":
                acoes_baixa_conf += 1

    if total_acoes == 0:
        return False, "Nenhuma ação técnica válida encontrada."

    pct_seletor = acoes_com_seletor / total_acoes
    pct_baixa   = acoes_baixa_conf  / total_acoes

    if pct_seletor < 0.50:
        return False, f"Apenas {pct_seletor:.0%} das ações tem seletor CSS válido."
    if pct_baixa > 0.70:
        return False, f"{pct_baixa:.0%} das ações com confiança baixa."

    return True, (
        f"OK — {len(passos)} passos, {total_acoes} ações, "
        f"{pct_seletor:.0%} com seletor, {pct_baixa:.0%} baixa confiança."
    )


def validar_roteiro_ia(roteiro: dict) -> tuple[bool, str]:
    """
    Portão de qualidade para roteiros gerados por IA.
    Fonte canônica — não duplicar em outros módulos.

    Critérios diferentes de validar_roteiro — não verifica seletor_hint
    (roteiros de IA não têm seletor_hint preenchido por design).

    Critérios:
      - >= 2 passos
      - Pelo menos 1 passo com ancora pedagógica preenchida
      - Pelo menos 1 ação técnica com elemento_alvo não vazio (excluindo concluir_video)
      - Nenhum passo não-conclusão com acoes_tecnicas completamente vazia

    Parâmetros:
        roteiro (dict): Dicionário representando o roteiro JSON gerado por IA.

    Retorna:
        tuple[bool, str]: Par (aprovado, motivo) onde:
            - aprovado (bool): True se o roteiro passou em todos os critérios de IA.
            - motivo (str): Descrição legível do resultado — motivo de reprovação
              ou resumo de aprovação com contagem de passos.

    Exceções:
        Não lança exceções. Entradas malformadas resultam em reprovação com motivo.
    """
    passos = roteiro.get("passos", [])
    if len(passos) < 2:
        return False, f"Apenas {len(passos)} passo(s) — roteiro insuficiente."

    # Pelo menos 1 passo com ancora pedagógica preenchida
    tem_ancora = any(
        p.get("pedagogia", {}).get("ancora", "").strip()
        for p in passos
    )
    if not tem_ancora:
        return False, "Nenhum passo possui âncora pedagógica (ancora) preenchida."

    # Pelo menos 1 ação com elemento_alvo não vazio (excluindo concluir_video)
    tem_elemento = any(
        bool(a.get("elemento_alvo"))
        for p in passos
        for a in p.get("acoes_tecnicas", [])
        if a.get("acao") != "concluir_video"
    )
    if not tem_elemento:
        return False, "Nenhuma ação técnica possui elemento_alvo definido."

    # Nenhum passo não-conclusão com acoes_tecnicas completamente vazia
    for passo in passos:
        if passo.get("is_conclusao"):
            continue
        acoes = [
            a for a in passo.get("acoes_tecnicas", [])
            if a.get("acao") != "concluir_video"
        ]
        if not acoes:
            return False, (
                f"Passo {passo.get('id_passo', '?')} não tem ações técnicas definidas."
            )

    return True, f"OK — {len(passos)} passos com conteúdo pedagógico e técnico."


def safe_write_json(path: str, data: dict) -> None:
    """
    Escreve dados JSON em disco de forma atômica via tempfile + os.replace().

    Garante que o arquivo destino nunca fique em estado parcialmente escrito:
    o arquivo temporário é criado no mesmo diretório (mesmo filesystem) para
    que o os.replace() seja uma operação atômica no nível do SO.

    Em caso de falha antes do replace, o arquivo temporário é removido e a
    exceção original é propagada — o arquivo destino permanece intacto.

    Parâmetros:
        path (str): Caminho absoluto ou relativo do arquivo JSON de destino.
        data (dict): Dados serializáveis em JSON a serem escritos.

    Retorna:
        None

    Exceções:
        OSError: Se não for possível criar o arquivo temporário ou fazer o replace.
        TypeError: Se `data` não for serializável em JSON.
    """
    dir_destino = os.path.dirname(os.path.abspath(path))
    os.makedirs(dir_destino, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_destino, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
            json.dump(data, tmp_f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        # Remove o temporário se algo falhar antes do replace
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def safe_resolve_path(base_dir: str, user_path: str) -> str:
    """
    Resolve e valida um caminho de arquivo fornecido pelo usuário contra um diretório base.

    Previne ataques de path traversal (ex: `../../etc/passwd`) garantindo que o
    caminho resolvido esteja contido dentro de `base_dir`.

    Parâmetros:
        base_dir (str): Diretório base permitido (absoluto ou relativo ao cwd).
        user_path (str): Caminho fornecido pelo usuário, relativo a base_dir.

    Retorna:
        str: Caminho absoluto resolvido, garantidamente dentro de base_dir.

    Exceções:
        ValueError: Se o caminho resolvido estiver fora de base_dir, com mensagem
                    descritiva indicando a tentativa de path traversal.

    Exemplos:
        >>> safe_resolve_path("roteiros_salvos", "aula.json")
        '/abs/path/roteiros_salvos/aula.json'
        >>> safe_resolve_path("roteiros_salvos", "../secrets.txt")
        ValueError: Caminho inválido: '../secrets.txt' resolve para fora do diretório base permitido.
    """
    base_abs = os.path.realpath(os.path.abspath(base_dir))
    resolved = os.path.realpath(os.path.join(base_abs, user_path))

    # O caminho resolvido deve começar com base_abs + separador (ou ser exatamente base_abs)
    if resolved != base_abs and not resolved.startswith(base_abs + os.sep):
        raise ValueError(
            f"Caminho inválido: '{user_path}' resolve para fora do diretório base permitido."
        )
    return resolved


def com_retry(fn, tentativas: int = 3, delays: list = None, excecoes: tuple = (Exception,)):
    """
    Executa fn com retry e exponential backoff.

    Parâmetros:
        fn (callable): Função sem argumentos a ser executada (use lambda para passar args).
        tentativas (int): Número total de tentativas, incluindo a primeira. Padrão: 3.
        delays (list): Lista de delays em segundos entre tentativas. Padrão: [1, 2, 4].
                       Para testes, use delays=[0, 0, 0] para não esperar.
        excecoes (tuple): Tuple de exceções que disparam retry. Padrão: (Exception,).

    Retorna:
        O resultado de fn() se bem-sucedido.

    Lança:
        A última exceção capturada se todas as tentativas falharem.

    Uso:
        resultado = com_retry(lambda: gemini_client.generate(...), tentativas=3)
    """
    if delays is None:
        delays = [1, 2, 4]

    ultimo_erro = None
    for i in range(tentativas):
        try:
            return fn()
        except excecoes as e:
            ultimo_erro = e
            if i < tentativas - 1:
                delay = delays[i] if i < len(delays) else delays[-1]
                if delay > 0:
                    time.sleep(delay)
    raise ultimo_erro


def configurar_logging(module_name: str) -> logging.Logger:
    """
    Configura e retorna um logger com formato estruturado padronizado.

    Garante que todos os módulos emitam logs com os campos obrigatórios:
    timestamp | level | module | message

    O formato usa o separador ` | ` para facilitar parsing por ferramentas de
    observabilidade. O timestamp segue o padrão ISO 8601 (YYYY-MM-DD HH:MM:SS,mmm).

    Esta função é idempotente: chamá-la múltiplas vezes com o mesmo module_name
    não duplica handlers — verifica se o logger já possui handlers antes de adicionar.

    Parâmetros:
        module_name (str): Nome do módulo/logger. Use __name__ ou um nome descritivo
                           como "capture", "generator_engine", "app".

    Retorna:
        logging.Logger: Logger configurado com o formato estruturado.

    Uso recomendado (no topo de cada módulo):
        from utils import configurar_logging
        logger = configurar_logging(__name__)

    Níveis disponíveis (usar de forma consistente):
        DEBUG    — detalhes internos úteis apenas em desenvolvimento
        INFO     — eventos normais do fluxo de operação
        WARNING  — situações inesperadas mas recuperáveis
        ERROR    — falhas que impedem uma operação específica
        CRITICAL — falhas que comprometem o sistema inteiro

    Nota: Esta função NÃO chama logging.basicConfig() — não interfere com
    configurações de logging já existentes em outros módulos ou no uvicorn.
    """
    logger = logging.getLogger(module_name)

    # Idempotente: não adiciona handler duplicado se já configurado
    if logger.handlers:
        return logger

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    return logger


# ==============================================================
# VERSIONAMENTO DE ROTEIROS (Task 16 — Requisitos 2.6.1–2.6.5)
# ==============================================================

import glob
from datetime import datetime


def salvar_versao_roteiro(caminho: str, dados: dict) -> str:
    """
    Salva o roteiro com versionamento: preserva versão anterior antes de sobrescrever.

    Cria arquivo de backup com sufixo timestamp: nome.json → nome.json.bak.20240101_120000
    Mantém apenas as 2 versões mais recentes (apaga versões mais antigas).

    Parâmetros:
        caminho (str): Caminho do arquivo JSON de destino.
        dados (dict): Dados do roteiro a serem escritos.

    Retorna:
        str: Caminho do arquivo de backup criado, ou "" se não havia versão anterior.
    """
    caminho_backup = ""

    # Preserva versão anterior se o arquivo já existir
    if os.path.exists(caminho):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        caminho_backup = f"{caminho}.bak.{timestamp}"
        try:
            import shutil
            shutil.copy2(caminho, caminho_backup)
        except Exception as e:
            logging.warning(f"[versioning] Não foi possível criar backup de '{caminho}': {e}")
            caminho_backup = ""

    # Escreve nova versão atomicamente
    safe_write_json(caminho, dados)

    # Mantém apenas as 2 versões de backup mais recentes
    if caminho_backup:
        _limpar_versoes_antigas(caminho, manter=2)

    return caminho_backup


def restaurar_versao_roteiro(caminho_backup: str, caminho_destino: str) -> tuple[bool, str]:
    """
    Restaura uma versão anterior de um roteiro.

    Executa validar_roteiro() na versão a restaurar antes de torná-la ativa.

    Parâmetros:
        caminho_backup (str): Caminho do arquivo de backup a restaurar.
        caminho_destino (str): Caminho do arquivo ativo de destino.

    Retorna:
        tuple[bool, str]: (True, motivo) se restaurado com sucesso, (False, motivo) se falhou.
    """
    if not os.path.exists(caminho_backup):
        return False, f"Arquivo de backup não encontrado: '{caminho_backup}'"

    try:
        with open(caminho_backup, "r", encoding="utf-8") as f:
            dados_backup = json.load(f)
    except Exception as e:
        return False, f"Erro ao ler backup '{caminho_backup}': {e}"

    aprovado, motivo = validar_roteiro(dados_backup)
    if not aprovado:
        return False, f"Versão de backup inválida — não restaurada: {motivo}"

    try:
        safe_write_json(caminho_destino, dados_backup)
    except Exception as e:
        return False, f"Erro ao restaurar versão: {e}"

    logging.info(f"[versioning] Versão restaurada de '{caminho_backup}' → '{caminho_destino}'")
    return True, f"Versão restaurada com sucesso. {motivo}"


def listar_versoes_roteiro(caminho: str) -> list[str]:
    """
    Lista os arquivos de backup de um roteiro, ordenados do mais recente ao mais antigo.

    Parâmetros:
        caminho (str): Caminho do arquivo JSON principal (sem sufixo .bak.*).

    Retorna:
        list[str]: Lista de caminhos de backup, do mais recente ao mais antigo.
    """
    padrao = f"{caminho}.bak.*"
    backups = glob.glob(padrao)
    # Ordena pelo sufixo de timestamp (YYYYMMDD_HHMMSS) — ordem lexicográfica = cronológica
    backups.sort(reverse=True)
    return backups


def _limpar_versoes_antigas(caminho: str, manter: int = 2) -> None:
    """Remove backups mais antigos, mantendo apenas os `manter` mais recentes."""
    backups = listar_versoes_roteiro(caminho)
    for antigo in backups[manter:]:
        try:
            os.remove(antigo)
            logging.debug(f"[versioning] Backup antigo removido: '{antigo}'")
        except Exception as e:
            logging.warning(f"[versioning] Não foi possível remover backup antigo '{antigo}': {e}")

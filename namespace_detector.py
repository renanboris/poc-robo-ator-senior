"""
namespace_detector.py — Detecção Automática de Namespace para RAG
===================================================================

Este módulo detecta automaticamente o namespace (módulo) correto para queries
RAG no Pinecone, melhorando a precisão da recuperação de documentação web
específica de módulos.

Estratégia de Detecção (prioridade decrescente):
  1. URL → extrai nivel_2 da URL (ex: /senior-x/hcm/admissao → "hcm")
  2. Metadata → busca em campos do roteiro (module, source_url, nome_aula)
  3. Keywords → matching case-insensitive com mapeamento configurável
  4. None → fallback para tenant_id no caller

Uso:
    from namespace_detector import detectar_namespace
    
    contexto = {"objetivo": "Criar admissão no HCM"}
    namespace = detectar_namespace(contexto)  # Retorna: "hcm"
    
    # Passa para buscar_contexto
    contexto_rag = dap_engine.buscar_contexto(
        objetivo, tenant_id, namespace=namespace
    )

Configuração:
    - Arquivo: namespace_keywords.json (opcional)
    - Env var: NAMESPACE_KEYWORDS (alternativa)
    - Hardcoded defaults (fallback)

Requirements: 1-14 (ver requirements.md)
"""

import os
import json
import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger("namespace_detector")

# =========================================================
# CACHE DE CONFIGURAÇÃO (MODULE-LEVEL)
# =========================================================
_keyword_mapping_cache: Optional[dict] = None
_keyword_mapping_mtime: Optional[float] = None

# =========================================================
# MAPEAMENTO PADRÃO DE KEYWORDS (HARDCODED FALLBACK)
# =========================================================
_DEFAULT_KEYWORD_MAPPING = {
    "hcm": [
        "recursos humanos", "admissao", "admissão", "folha", "folha de pagamento",
        "rh", "colaborador", "funcionario", "funcionário", "ponto", "ferias", "férias"
    ],
    "financeiro": [
        "contas a pagar", "contas a receber", "tesouraria", "financas", "finanças",
        "pagamento", "recebimento", "faturamento", "nota fiscal", "boleto"
    ],
    "ged": [
        "documentos", "arquivos", "pastas", "ged", "gestao documental",
        "gestão documental", "documento eletronico", "documento eletrônico"
    ],
    "compras": [
        "compras", "requisicao", "requisição", "pedido de compra", "cotacao",
        "cotação", "fornecedor", "ordem de compra"
    ],
    "estoque": [
        "estoque", "inventario", "inventário", "movimentacao", "movimentação",
        "armazem", "armazém", "produto", "item", "material"
    ],
}


def detectar_namespace(contexto: dict) -> Optional[str]:
    """Detecta namespace a partir do contexto disponível.
    
    Ordem de prioridade:
    1. URL extraction (se chave 'url' presente)
    2. Metadata extraction (se chave 'metadata' presente)
    3. Keyword matching (se 'objetivo' ou 'nome_aula' presente)
    4. Return None (fallback para tenant_id no caller)
    
    Args:
        contexto: Dicionário com chaves opcionais:
            - url: URL do Senior X (string)
            - metadata: Metadata do roteiro (dict)
            - objetivo: Objetivo do workflow (string)
            - nome_aula: Nome do roteiro (string)
    
    Returns:
        Namespace normalizado (lowercase kebab-case) ou None
        
    Examples:
        >>> detectar_namespace({"url": "https://...senior-x/hcm/admissao"})
        'hcm'
        >>> detectar_namespace({"objetivo": "Criar pasta no GED"})
        'ged'
        >>> detectar_namespace({"metadata": {"module": "financeiro"}})
        'financeiro'
        >>> detectar_namespace({})
        None
    
    Requirements: 8.1, 8.2, 8.3, 8.4
    """
    if not isinstance(contexto, dict):
        logger.debug("[Namespace] Contexto inválido (não é dict), retornando None")
        return None
    
    try:
        # Prioridade 1: URL extraction
        if "url" in contexto and contexto["url"]:
            namespace = _extrair_namespace_de_url(contexto["url"])
            if namespace:
                logger.info(f"[Namespace] Detectado: {namespace} (fonte: URL)")
                return namespace
        
        # Prioridade 2: Metadata extraction
        if "metadata" in contexto and contexto["metadata"]:
            namespace = _extrair_namespace_de_metadata(contexto["metadata"])
            if namespace:
                logger.info(f"[Namespace] Detectado: {namespace} (fonte: metadata)")
                return namespace
        
        # Prioridade 3: Keyword matching
        texto_busca = contexto.get("objetivo") or contexto.get("nome_aula")
        if texto_busca:
            namespace = _extrair_namespace_de_keywords(texto_busca)
            if namespace:
                logger.info(f"[Namespace] Detectado: {namespace} (fonte: keyword)")
                return namespace
        
        # Nenhuma detecção bem-sucedida
        logger.warning("[Namespace] Não detectado em nenhuma fonte, fallback para tenant_id")
        return None
        
    except Exception as e:
        logger.error(f"[Namespace] Erro na detecção: {e}")
        return None


def _extrair_namespace_de_url(url: str) -> Optional[str]:
    """Extrai namespace da URL usando lógica de nivel_2.
    
    Reutiliza Extractor.extract_breadcrumbs() e normalize_hierarchy()
    do ingestion_pipeline/extractor.py para consistência.
    
    Args:
        url: URL da documentação Senior X
        
    Returns:
        Namespace normalizado ou None
        
    Examples:
        >>> _extrair_namespace_de_url("https://...senior-x/hcm/admissao")
        'hcm'
        >>> _extrair_namespace_de_url("https://...seniorxplatform/manual-do-usuario/ged")
        'ged'
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 7.1, 7.2, 7.3, 7.4, 7.5
    """
    if not url or not isinstance(url, str):
        return None
    
    try:
        # Importa e reutiliza lógica do Extractor
        from ingestion_pipeline.extractor import SemanticExtractor
        
        extractor = SemanticExtractor()
        breadcrumbs = extractor.extract_breadcrumbs(url)
        
        # nivel_2 é o namespace (segundo segmento do path)
        namespace = breadcrumbs.get("nivel_2", "")
        
        if namespace:
            logger.debug(f"[Namespace] URL extraction: {url} → {namespace}")
            return namespace
        else:
            logger.debug(f"[Namespace] URL sem nivel_2: {url}")
            return None
            
    except ImportError as e:
        logger.error(f"[Namespace] Falha ao importar extractor: {e}")
        return None
    except Exception as e:
        logger.warning(f"[Namespace] Erro ao extrair de URL '{url}': {e}")
        return None


def _extrair_namespace_de_metadata(metadata: dict) -> Optional[str]:
    """Extrai namespace da metadata do roteiro.
    
    Ordem de prioridade:
    1. metadata['module'] (campo explícito)
    2. metadata['source_url'] (extração via URL)
    3. metadata['nome_aula'] (keyword matching)
    
    Args:
        metadata: Dicionário de metadata do roteiro
        
    Returns:
        Namespace normalizado ou None
    
    Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
    """
    if not isinstance(metadata, dict):
        return None
    
    try:
        # Prioridade 1: Campo explícito 'module'
        if "module" in metadata and metadata["module"]:
            namespace = str(metadata["module"]).strip().lower()
            if namespace:
                logger.debug(f"[Namespace] Metadata extraction: module field → {namespace}")
                return namespace
        
        # Prioridade 2: Extração de source_url
        if "source_url" in metadata and metadata["source_url"]:
            namespace = _extrair_namespace_de_url(metadata["source_url"])
            if namespace:
                logger.debug(f"[Namespace] Metadata extraction: source_url → {namespace}")
                return namespace
        
        # Prioridade 3: Keyword matching em nome_aula
        if "nome_aula" in metadata and metadata["nome_aula"]:
            namespace = _extrair_namespace_de_keywords(metadata["nome_aula"])
            if namespace:
                logger.debug(f"[Namespace] Metadata extraction: nome_aula keyword → {namespace}")
                return namespace
        
        return None
        
    except Exception as e:
        logger.warning(f"[Namespace] Erro ao extrair de metadata: {e}")
        return None


def _extrair_namespace_de_keywords(texto: str) -> Optional[str]:
    """Extrai namespace do texto usando keyword matching.
    
    Carrega mapeamento de keywords e faz matching case-insensitive.
    Retorna o primeiro namespace que tiver keyword match.
    
    Args:
        texto: Texto do objetivo ou nome_aula
        
    Returns:
        Primeiro namespace matched ou None
        
    Examples:
        >>> _extrair_namespace_de_keywords("Criar admissão no HCM")
        'hcm'
        >>> _extrair_namespace_de_keywords("Configurar contas a pagar")
        'financeiro'
    
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
    """
    if not texto or not isinstance(texto, str):
        return None
    
    try:
        # Carrega mapeamento de keywords
        keyword_mapping = _carregar_mapeamento_keywords()
        
        # Normaliza texto para lowercase
        texto_lower = texto.lower()
        
        # Itera por namespaces e keywords
        # Filtra chaves que começam com _ (metadados do JSON)
        for namespace, keywords in keyword_mapping.items():
            # Ignora chaves de metadados (_comment, _format, _usage, etc.)
            if namespace.startswith("_"):
                continue
            
            for keyword in keywords:
                if keyword.lower() in texto_lower:
                    logger.debug(f"[Namespace] Keyword match: '{keyword}' → {namespace}")
                    return namespace
        
        return None
        
    except Exception as e:
        logger.warning(f"[Namespace] Erro no keyword matching: {e}")
        return None


def _carregar_mapeamento_keywords() -> dict:
    """Carrega mapeamento de keywords para namespaces.
    
    Ordem de prioridade:
    1. namespace_keywords.json (arquivo local)
    2. NAMESPACE_KEYWORDS (environment variable)
    3. _DEFAULT_KEYWORD_MAPPING (hardcoded fallback)
    
    Implementa cache em memória para performance.
    Cache é invalidado se o arquivo JSON for modificado.
    
    Returns:
        Dicionário {namespace: [keywords]}
        
    Example:
        {
            "hcm": ["recursos humanos", "admissao", "folha"],
            "financeiro": ["contas a pagar", "tesouraria"],
            "ged": ["documentos", "arquivos", "pastas"]
        }
    
    Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 12.4
    """
    global _keyword_mapping_cache, _keyword_mapping_mtime
    
    config_file = "namespace_keywords.json"
    
    # Verifica se cache é válido
    if _keyword_mapping_cache is not None:
        if os.path.exists(config_file):
            current_mtime = os.path.getmtime(config_file)
            if current_mtime == _keyword_mapping_mtime:
                # Cache válido
                return _keyword_mapping_cache
        else:
            # Arquivo não existe, mas cache pode ser de env var ou default
            if _keyword_mapping_mtime is None:
                # Cache de env var ou default, ainda válido
                return _keyword_mapping_cache
    
    # Cache inválido ou não existe, recarrega
    mapping = None
    source = None
    
    # Prioridade 1: Arquivo JSON
    if os.path.exists(config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            source = config_file
            _keyword_mapping_mtime = os.path.getmtime(config_file)
        except Exception as e:
            logger.warning(f"[Namespace] Erro ao carregar {config_file}: {e}")
    
    # Prioridade 2: Environment variable
    if mapping is None:
        env_var = os.getenv("NAMESPACE_KEYWORDS")
        if env_var:
            try:
                mapping = json.loads(env_var)
                source = "NAMESPACE_KEYWORDS env var"
                _keyword_mapping_mtime = None
            except Exception as e:
                logger.warning(f"[Namespace] Erro ao parsear NAMESPACE_KEYWORDS: {e}")
    
    # Prioridade 3: Hardcoded default
    if mapping is None:
        mapping = _DEFAULT_KEYWORD_MAPPING
        source = "hardcoded defaults"
        _keyword_mapping_mtime = None
    
    # Valida estrutura
    if not isinstance(mapping, dict):
        logger.warning(f"[Namespace] Config inválida, usando defaults")
        mapping = _DEFAULT_KEYWORD_MAPPING
        source = "hardcoded defaults (fallback)"
    
    # Atualiza cache
    _keyword_mapping_cache = mapping
    
    # Log
    namespace_count = len(mapping)
    logger.info(f"[Namespace] Config carregado: {source} ({namespace_count} namespaces)")
    
    return mapping

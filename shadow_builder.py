"""
shadow_builder.py — Senior Training OS · Módulo Puro de Inferência Semântica
=============================================================================
Fonte canônica das funções de montagem e inferência do Shadow JSONL.

Este módulo é PURO: sem Playwright, Gemini, OpenAI, Pinecone, asyncio ou subprocess.
Pode ser importado e testado isoladamente.

Consumidores:
  - capture_dual_output.py  (importa todas as funções)
  - capture_hybrid_shadow.py (importa utc_now)

Funções exportadas:
  - utc_now
  - _infer_capture_scope
  - _infer_semantic_action_from_capture
  - _infer_business_entity_from_capture
  - _infer_pattern_from_capture
  - _is_noise_event
  - _montar_evento_shadow
  - _salvar_shadow_jsonl
"""

import json
import logging
import os
from datetime import datetime, timezone

from utils import limpar_nome

logger = logging.getLogger("shadow_builder")


def utc_now() -> str:
    """Retorna o timestamp atual em ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


def _infer_capture_scope(iframe_id: str | None) -> str:
    """Determina se o evento ocorreu no shell ou em um módulo iframe."""
    return "module_iframe" if iframe_id and iframe_id != "Pagina Principal" else "shell"


def _infer_semantic_action_from_capture(
    acao: str, label: str, seletor: str, tag: str, valor_input: str = ""
) -> str:
    """
    Classifica a intenção semântica do evento a partir dos dados brutos de captura.
    Retorna sempre um valor do vocabulário controlado:
      fill | search | confirm | delete | save | open | navigate | select | close
    """
    blob = f"{acao} {label} {seletor} {tag} {valor_input}".lower()

    if acao == "clique_direito":
        return "open"
    if acao == "duplo_clique":
        return "open"
    if acao in {"preencher_campo"}:
        return "fill"
    if acao == "digitar_e_enter":
        if any(k in blob for k in ["pesquisa", "pesquisar", "buscar", "filter", "filtro", "search"]):
            return "search"
        return "confirm"
    if "nova pasta" in blob or "novo" in blob or "criar" in blob:
        return "open"
    if any(k in blob for k in ["excluir", "remover", "apagar", "deletar"]):
        return "delete"
    if any(k in blob for k in ["sim", "confirmar", "ok", "aplicar"]):
        return "confirm"
    if any(k in blob for k in ["pesquisar", "buscar", "filtro", "filter", "search"]):
        return "search"
    if any(k in blob for k in ["salvar", "gravar", "save"]):
        return "save"
    return "navigate"


def _infer_business_entity_from_capture(
    label: str, seletor: str, tag: str, contexto_tela: str = ""
) -> str:
    """Identifica a entidade de negócio envolvida no evento."""
    blob = f"{label} {seletor} {tag} {contexto_tela}".lower()
    if "pasta" in blob:
        return "pasta"
    if "document" in blob or "ged" in blob:
        return "documento"
    if "menu" in blob:
        return "menu"
    if tag in {"input", "textarea", "select"}:
        return "campo"
    if "checkbox" in blob or "selecao" in blob:
        return "selecao"
    return "elemento"


def _infer_pattern_from_capture(
    acao: str, label: str, seletor: str, tag: str, capture_scope: str
) -> str:
    """Classifica o padrão de interação do evento."""
    blob = f"{label} {seletor} {tag}".lower()
    if any(k in blob for k in ["breadcrumb", "fa-home", "ui-breadcrumb"]):
        return "breadcrumb_navigation"
    if any(k in blob for k in ["apps-menu-item", "menu-item"]) or capture_scope == "shell":
        return "menu_navigation"
    if any(k in blob for k in ["newfolderbutton", "upload", "download", "toolbar", "dropdown-menu"]):
        return "toolbar_action"
    if any(k in blob for k in ["itemtitle", "folder", "list-item", "row", "tree"]) or acao == "duplo_clique":
        return "table_selection"
    if tag in {"input", "textarea", "select"} or acao in {"preencher_campo", "digitar_e_enter"}:
        return "form_fill"
    if tag in {"button", "a"}:
        return "button_click"
    return "unknown"


def _is_noise_event(
    label: str, seletor: str, acao: str, tag: str, capture_scope: str, valor_input: str = ""
) -> bool:
    """
    Retorna True para eventos que provavelmente não devem virar passo de treinamento.
    Critérios:
      - Clique em breadcrumb/home (navegação utilitária)
      - Enter isolado sem valor de input
      - Clique em ícone utilitário sem label semântico
    """
    label_l   = (label or "").strip().lower()
    seletor_l = (seletor or "").lower()
    if any(k in seletor_l for k in ["breadcrumb", "fa-home", "ui-breadcrumb"]):
        return True
    if acao == "digitar_e_enter" and not (valor_input or "").strip():
        return True
    if tag in {"i", "svg", "path"} and label_l in {"", "i", "svg", "path", "span", "div", "a"}:
        return True
    return False


def _montar_evento_shadow(
    *,
    id_acao: int,
    acao: str,
    label: str,
    dados: dict,
    analise: dict,
    iframe_id: str | None,
    coords: dict,
    screenshot_b64: str | None,
    page_title: str,
    page_url: str,
    vp_w: int,
    vp_h: int,
    valor_input: str,
) -> dict:
    """
    Monta o Evento_Shadow completo a partir dos dados brutos de captura e análise Gemini.
    Todos os campos obrigatórios do schema são sempre preenchidos.
    """
    capture_scope   = _infer_capture_scope(iframe_id)
    semantic_action = _infer_semantic_action_from_capture(
        acao, label, dados.get("seletor", ""), dados.get("tag", ""), valor_input
    )
    business_entity = _infer_business_entity_from_capture(
        label, dados.get("seletor", ""), dados.get("tag", ""), analise.get("contexto_tela", "")
    )
    pattern  = _infer_pattern_from_capture(
        acao, label, dados.get("seletor", ""), dados.get("tag", ""), capture_scope
    )
    is_noise = _is_noise_event(
        label, dados.get("seletor", ""), acao, dados.get("tag", ""), capture_scope, valor_input
    )

    # micro_narracao curta: máximo 60 chars
    _intencao_raw       = analise.get("intencao") or f"{acao} em {label}"
    micro_narracao_curta = _intencao_raw[:60].rstrip()

    # validacao_esperada varia por tipo de acao
    _validacoes = {
        "fill":    "Campo preenchido com o valor correto",
        "search":  "Resultados filtrados conforme o termo",
        "save":    "Registro salvo com sucesso",
        "delete":  "Item removido da listagem",
        "confirm": "Operação confirmada",
        "open":    "Conteúdo ou modal aberto",
    }
    validacao_alvo = _validacoes.get(semantic_action, "A tela mudou conforme esperado")

    return {
        "id_acao":            id_acao,
        "captured_at":        utc_now(),
        "acao":               acao,
        "capture_scope":      capture_scope,
        "is_noise":           is_noise,
        "intencao_semantica": analise.get("intencao") or f"{acao.capitalize()} em '{label}'",
        "semantic_action":    semantic_action,
        "business_entity":    business_entity,
        "business_target":    label,
        "pattern_detectado":  pattern,
        "valor_input":        valor_input,
        "micro_narracao":     micro_narracao_curta,
        "contexto_semantico": {
            "tela_atual": {
                "tela_id": page_title,
                "url":     page_url,
                "iframe":  iframe_id if iframe_id != "Pagina Principal" else None,
                "scope":   capture_scope,
            }
        },
        "validacao_esperada": {
            "alvo": validacao_alvo
        },
        "elemento_alvo": {
            "descricao_visual":      analise.get("descricao_visual", f"Elemento '{label}'"),
            "contexto_tela":         analise.get("contexto_tela", page_title or "Desconhecido"),
            "tipo_elemento":         analise.get("tipo_elemento", dados.get("tag", "button")),
            "confianca_captura":     analise.get("confianca", "media"),
            "label_curto":           label,
            "coordenadas_relativas": coords,
            "seletor_hint":          dados.get("seletor", ""),
            "iframe_hint":           iframe_id if iframe_id != "Pagina Principal" else None,
            "html_hint":             dados.get("html_snapshot", "")[:300],
            "screenshot_referencia": screenshot_b64,
        },
        "technical": {
            "acao":          acao,
            "tag":           dados.get("tag", ""),
            "text_hint":     label,
            "iframe_hint":   iframe_id,
            "seletor_css":   dados.get("seletor", ""),
            "html_snapshot": dados.get("html_snapshot", "")[:400],
            "x_pct":         coords.get("x_pct", 0.5),
            "y_pct":         coords.get("y_pct", 0.5),
            "w_pct":         coords.get("w_pct", 0.05),
            "h_pct":         coords.get("h_pct", 0.05),
            "viewport_w":    vp_w,
            "viewport_h":    vp_h,
            "page_title":    page_title,
            "url_hint":      page_url,
        },
    }


def _salvar_shadow_jsonl(
    nome_aula: str, objetivo_aula: str, eventos: list[dict]
) -> str | None:
    """
    Persiste a lista de eventos como Shadow JSONL em shadow_exports/.

    - Ordena por id_acao antes de gravar (garante ordem cronológica).
    - Emite SHADOW_GERADO:{caminho} no stdout em caso de sucesso.
    - Em caso de falha: logger.warning + retorna None (sem re-raise).
    """
    try:
        os.makedirs("shadow_exports", exist_ok=True)
        caminho = os.path.join("shadow_exports", f"{limpar_nome(nome_aula)}_shadow.jsonl")
        eventos_ordenados = sorted(eventos, key=lambda e: e.get("id_acao", 0))
        with open(caminho, "w", encoding="utf-8") as f:
            for evento in eventos_ordenados:
                f.write(json.dumps(evento, ensure_ascii=False) + "\n")
        logger.info(f"Shadow JSONL salvo em: {caminho}")
        print(f"SHADOW_GERADO:{caminho}", flush=True)
        return caminho
    except Exception as e:
        logger.warning(f"Falha ao salvar shadow JSONL: {e}")
        return None

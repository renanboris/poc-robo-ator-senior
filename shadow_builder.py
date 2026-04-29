"""
shadow_builder.py — Senior Training OS · Módulo Puro de Inferência Semântica
=============================================================================
Fonte canônica das funções de montagem e inferência do Shadow JSONL.

Este módulo é PURO: sem Playwright, Gemini, OpenAI, Pinecone, asyncio ou subprocess.
Pode ser importado e testado isoladamente.

Consumidores:
  - capture_dual_output.py  (importa todas as funções)
  - capture_hybrid_shadow.py (importa funções unificadas públicas)

Funções exportadas (API pública unificada — use estas):
  - utc_now
  - inferir_acao_semantica          ← substitui _infer_semantic_action_from_capture
  - inferir_entidade_negocio        ← substitui _infer_business_entity_from_capture
  - inferir_padrao_interacao        ← substitui _infer_pattern_from_capture
  - classificar_ruido               ← substitui _is_noise_event
  - _montar_evento_shadow
  - _salvar_shadow_jsonl

Funções privadas (mantidas para retrocompatibilidade interna):
  - _infer_capture_scope
  - _infer_semantic_action_from_capture
  - _infer_business_entity_from_capture
  - _infer_pattern_from_capture
  - _is_noise_event
"""

import json
import logging
import os
import re
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


# ──────────────────────────────────────────────────────────────
# API PÚBLICA UNIFICADA — use estas funções em código novo
# As funções privadas abaixo são mantidas para retrocompatibilidade
# ──────────────────────────────────────────────────────────────

def inferir_acao_semantica(
    acao: str,
    label: str,
    seletor: str,
    tag: str,
    valor_input: str = "",
    hints: dict | None = None,
) -> str:
    """
    Função unificada de inferência de ação semântica.

    Substitui _infer_semantic_action_from_capture() e infer_semantic_action_from_hints()
    do capture_hybrid_shadow.py. Aceita tanto a assinatura posicional original quanto
    um dict `hints` com o formato de payload do capture_hybrid_shadow.

    Retorna sempre um valor do vocabulário controlado:
      fill | search | confirm | delete | save | open | navigate | select | close

    Parâmetros:
        acao: ação bruta capturada (ex: "clique", "preencher_campo")
        label: texto do elemento (ex: "Salvar", "Pesquisar")
        seletor: seletor CSS capturado
        tag: tag HTML do elemento (ex: "button", "input")
        valor_input: valor digitado (para ações de preenchimento)
        hints: dict opcional com campos do payload do capture_hybrid_shadow
               (text_hint, acao, seletor_css, tag, valor_input, tecla,
               aria_hint, title_hint). Campos posicionais têm precedência
               sobre hints quando não-vazios.
    """
    if hints:
        acao = acao or hints.get("acao", "")
        label = label or hints.get("text_hint", "")
        seletor = seletor or hints.get("seletor_css", "")
        tag = tag or hints.get("tag", "")
        valor_input = valor_input or hints.get("valor_input", "")

        # ── Casos específicos do capture_hybrid_shadow ──────────────────────
        # acao == "selecionar_opcao" é exclusivo do hybrid (evento <select>)
        if acao == "selecionar_opcao":
            return "select"

        # acao == "tecla" captura atalhos de teclado funcionais (Ctrl+S, Escape, etc.)
        if acao == "tecla":
            tecla = hints.get("tecla", "").strip()
            tecla_lower = tecla.lower()
            if tecla_lower in {"ctrl+s", "meta+s"}:
                return "save"
            if tecla_lower in {"escape", "esc"}:
                return "close"
            if tecla_lower in {"delete", "del"}:
                return "delete"
            if tecla_lower in {"f2"}:
                return "open"
            if tecla_lower in {"enter"}:
                return "confirm"
            # Atalho genérico de teclado — trata como confirm
            return "confirm"

        # Enriquece label com aria_hint e title_hint quando text_hint está vazio
        aria_hint  = hints.get("aria_hint", "")
        title_hint = hints.get("title_hint", "")
        label = label or aria_hint or title_hint

    return _infer_semantic_action_from_capture(acao, label, seletor, tag, valor_input)


def inferir_entidade_negocio(
    label: str,
    seletor: str,
    tag: str,
    contexto_tela: str = "",
    hints: dict | None = None,
) -> str:
    """
    Função unificada de inferência de entidade de negócio.

    Substitui _infer_business_entity_from_capture() e infer_business_entity_from_hints()
    do capture_hybrid_shadow.py.

    Retorna o tipo de entidade:
      pasta | documento | cliente | pedido | menu | campo | selecao | elemento

    Parâmetros:
        label: texto do elemento
        seletor: seletor CSS capturado
        tag: tag HTML do elemento
        contexto_tela: contexto da tela (ex: título da página)
        hints: dict opcional com campos do payload (text_hint, seletor_css, tag,
               page_title, aria_hint, title_hint)
    """
    if hints:
        label = label or hints.get("text_hint", "")
        seletor = seletor or hints.get("seletor_css", "")
        tag = tag or hints.get("tag", "")
        contexto_tela = contexto_tela or hints.get("page_title", "")
        # Enriquece label com aria_hint e title_hint (exclusivos do hybrid)
        aria_hint  = hints.get("aria_hint", "")
        title_hint = hints.get("title_hint", "")
        label = label or aria_hint or title_hint

        # Entidades de negócio específicas do domínio Senior X (hybrid)
        blob_hints = f"{label} {seletor} {contexto_tela} {aria_hint} {title_hint}".lower()
        if any(k in blob_hints for k in ["cliente", "customer", "fornecedor"]):
            return "cliente"
        if any(k in blob_hints for k in ["pedido", "order", "nota fiscal", "nf-e"]):
            return "pedido"

    return _infer_business_entity_from_capture(label, seletor, tag, contexto_tela)


def inferir_padrao_interacao(
    acao: str,
    label: str,
    seletor: str,
    tag: str,
    capture_scope: str,
    hints: dict | None = None,
) -> str:
    """
    Função unificada de inferência de padrão de interação.

    Substitui _infer_pattern_from_capture() e infer_pattern_from_hints()
    do capture_hybrid_shadow.py.

    Retorna o padrão:
      breadcrumb_navigation | menu_navigation | toolbar_action | table_selection |
      form_fill | button_click | modal_action | tree_item_open | search_debounce |
      unknown

    Parâmetros:
        acao: ação bruta capturada
        label: texto do elemento
        seletor: seletor CSS capturado
        tag: tag HTML do elemento
        capture_scope: escopo da captura ("shell" ou "module_iframe")
        hints: dict opcional com campos do payload (acao, text_hint, seletor_css,
               tag, capture_scope, aria_hint, title_hint)
    """
    if hints:
        acao = acao or hints.get("acao", "")
        label = label or hints.get("text_hint", "")
        seletor = seletor or hints.get("seletor_css", "")
        tag = tag or hints.get("tag", "")
        capture_scope = capture_scope or hints.get("capture_scope", "shell")

        # ── Padrões exclusivos do capture_hybrid_shadow ─────────────────────
        blob_hints = f"{label} {seletor} {tag}".lower()
        aria_hint  = hints.get("aria_hint", "").lower()

        # modal_action: botões dentro de dialogs/modais
        if re.search(r"modal|dialog|p-dialog|overlay|confirmDialog", seletor, re.IGNORECASE):
            return "modal_action"

        # tree_item_open: duplo clique em nó de árvore ou item de lista hierárquica
        if acao == "duplo_clique" and re.search(
            r"tree|treenode|p-tree|folder|itemtitle", seletor, re.IGNORECASE
        ):
            return "tree_item_open"

        # search_debounce: input de busca com debounce (campo de filtro/pesquisa)
        if tag in {"input", "textarea"} and any(
            k in blob_hints or k in aria_hint
            for k in ["search", "filter", "pesquisa", "busca", "filtro"]
        ):
            return "search_debounce"

    return _infer_pattern_from_capture(acao, label, seletor, tag, capture_scope)


def classificar_ruido(
    label: str,
    seletor: str,
    acao: str,
    tag: str,
    capture_scope: str,
    valor_input: str = "",
    hints: dict | None = None,
) -> bool:
    """
    Função unificada de classificação de eventos de ruído.

    Substitui _is_noise_event() e is_noise_event() do capture_hybrid_shadow.py.

    Retorna True para eventos que provavelmente não devem virar passo de treinamento:
      - Clique em breadcrumb/home (navegação utilitária)
      - Enter isolado sem valor de input
      - Clique em ícone utilitário sem label semântico

    Parâmetros:
        label: texto do elemento
        seletor: seletor CSS capturado
        acao: ação bruta capturada
        tag: tag HTML do elemento
        capture_scope: escopo da captura
        valor_input: valor digitado (para ações de preenchimento)
        hints: dict opcional com campos do payload (text_hint, seletor_css, acao, tag, valor_input)
    """
    if hints:
        label = label or hints.get("text_hint", "")
        seletor = seletor or hints.get("seletor_css", "")
        acao = acao or hints.get("acao", "")
        tag = tag or hints.get("tag", "")
        valor_input = valor_input or hints.get("valor_input", "")
    return _is_noise_event(label, seletor, acao, tag, capture_scope, valor_input)


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

    # expected_effect: top-level field for the Next integration (Requirement 8.1)
    expected_effect = validacao_alvo

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
        "expected_effect":    expected_effect,
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

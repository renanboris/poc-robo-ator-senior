from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_GRAVACAO = {
    "gravar_video": True,
    "pasta_destino": "videos_gerados",
    "voz_ia": "pt-BR-FranciscaNeural",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def compact_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def has_module_iframe(actions: list[dict[str, Any]]) -> bool:
    return any(a.get("capture_scope") == "module_iframe" for a in actions)


def should_drop_action(action: dict[str, Any], drop_shell_when_iframe: bool, keep_noise: bool) -> bool:
    if not keep_noise and action.get("is_noise", False):
        return True

    scope = action.get("capture_scope", "")
    if drop_shell_when_iframe and scope == "shell":
        return True

    pattern = (action.get("pattern_detectado") or "").lower()
    if not keep_noise and pattern in {"breadcrumb_navigation"}:
        return True

    label = compact_spaces(
        action.get("business_target")
        or action.get("elemento_alvo", {}).get("label_curto")
        or action.get("elemento_alvo", {}).get("descricao_visual")
        or action.get("technical", {}).get("text_hint", "")
    ).lower()

    if not keep_noise and label in {"i", "span", "div", "a", "ação", "elemento"}:
        return True

    return False


def normalize_semantic_action(action: dict[str, Any]) -> str:
    sa = (action.get("semantic_action") or "").lower()
    target = compact_spaces(
        action.get("business_target")
        or action.get("elemento_alvo", {}).get("label_curto")
        or action.get("technical", {}).get("text_hint", "")
    ).lower()
    acao_bruta = (action.get("acao") or "").lower()
    pattern = (action.get("pattern_detectado") or "").lower()

    if sa == "navigate" and target in {"sim", "confirmar", "ok", "yes", "aplicar"}:
        return "confirm"
    if sa == "navigate" and target.startswith("nova pasta"):
        return "open"
    if sa == "navigate" and pattern == "modal_action":
        return "confirm"
    if sa == "navigate" and acao_bruta == "tecla":
        tecla = (action.get("technical", {}).get("tecla") or "").lower()
        if tecla == "enter":
            return "confirm"
    return sa or "navigate"


def build_anchor(action: dict[str, Any]) -> str:
    sa = normalize_semantic_action(action)
    target = compact_spaces(
        action.get("business_target")
        or action.get("elemento_alvo", {}).get("label_curto")
        or action.get("elemento_alvo", {}).get("descricao_visual")
        or action.get("technical", {}).get("text_hint", "")
    )

    if not target:
        target = "elemento"

    mapping = {
        "delete": f"Excluir {target}",
        "confirm": f"Confirmar {target}",
        "open": f"Abrir {target}",
        "search": f"Pesquisar {target}",
        "fill": f"Preencher {target}",
        "select": f"Selecionar {target}",
        "save": f"Salvar {target}",
        "close": f"Fechar {target}",
        "navigate": f"Acessar {target}",
    }
    return mapping.get(sa, action.get("intencao_semantica") or f"Interagir com {target}")


def build_micro_narration(action: dict[str, Any]) -> str:
    sa = normalize_semantic_action(action)
    target = compact_spaces(
        action.get("business_target")
        or action.get("elemento_alvo", {}).get("label_curto")
        or action.get("elemento_alvo", {}).get("descricao_visual")
        or action.get("technical", {}).get("text_hint", "")
    )
    if not target:
        target = "elemento"

    mapping = {
        "delete": f".excluímos {target.lower()}.",
        "confirm": f".confirmamos {target.lower()}.",
        "open": f".abrimos {target.lower()}.",
        "search": f".pesquisamos {target.lower()}.",
        "fill": f".preenchemos {target.lower()}.",
        "select": f".selecionamos {target.lower()}.",
        "save": f".salvamos {target.lower()}.",
        "close": f".fechamos {target.lower()}.",
        "navigate": f".acessamos {target.lower()}.",
    }
    return mapping.get(sa, action.get("micro_narracao") or f".interagimos com {target.lower()}.")


def build_validation(action: dict[str, Any]) -> dict[str, Any]:
    base = dict(action.get("validacao_esperada") or {})
    sa = normalize_semantic_action(action)
    target = compact_spaces(
        action.get("business_target")
        or action.get("elemento_alvo", {}).get("label_curto")
        or ""
    )
    ctx = action.get("contexto_semantico") or {}
    after = ctx.get("tela_depois") or {}
    change = compact_spaces(ctx.get("o_que_mudou", ""))

    if sa == "confirm":
        alvo = f"Confirmação concluída para {target}" if target else "Confirmação concluída"
    elif sa == "delete":
        alvo = f"Modal ou exclusão de {target}" if target else "Modal ou exclusão concluída"
    elif sa == "open":
        alvo = f"Abertura de {target}" if target else "Abertura concluída"
    elif sa == "search":
        alvo = f"Busca aplicada para {target}" if target else "Busca aplicada"
    else:
        alvo = base.get("alvo") or "A tela mudou conforme esperado"

    if change:
        alvo = change
    elif after.get("tela_id"):
        alvo = f"Tela após ação: {after.get('tela_id')}"

    return {
        "tipo": base.get("tipo", "estado_visual"),
        "alvo": alvo,
    }


def dedupe_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    last_key: tuple[Any, ...] | None = None

    for action in actions:
        tech = action.get("technical") or {}
        key = (
            action.get("acao"),
            normalize_semantic_action(action),
            compact_spaces(action.get("business_target") or ""),
            tech.get("seletor_css") or action.get("elemento_alvo", {}).get("seletor_hint"),
            action.get("capture_scope"),
        )
        if key == last_key:
            continue
        cleaned.append(action)
        last_key = key
    return cleaned


def action_to_executor(action: dict[str, Any], step_id: int) -> dict[str, Any]:
    tech = action.get("technical") or {}
    target_block = dict(action.get("elemento_alvo") or {})
    target_block["confianca_captura"] = target_block.get("confianca_captura", "media")

    acao_out = {
        "acao": action.get("acao", "clique"),
        "capture_scope": action.get("capture_scope", "shell"),
        "is_noise": action.get("is_noise", False),
        "intencao_semantica": build_anchor(action),
        "semantic_action": normalize_semantic_action(action),
        "pattern_detectado": action.get("pattern_detectado", ""),
        "business_entity": action.get("business_entity", ""),
        "business_target": action.get("business_target", ""),
        "elemento_alvo": target_block,
        "valor_input": action.get("valor_input", ""),
        "micro_narracao": build_micro_narration(action),
        "seletor_css": tech.get("seletor_css") or target_block.get("seletor_hint", ""),
        "validacao_esperada": build_validation(action),
    }

    if tech.get("tecla"):
        acao_out["tecla"] = tech.get("tecla")
    if tech.get("valor_selecionado"):
        acao_out["valor_selecionado"] = tech.get("valor_selecionado")
    if tech.get("iframe_hint"):
        acao_out["iframe_hint"] = tech.get("iframe_hint")
    if tech.get("seletor_fallback"):
        acao_out["seletor_fallback"] = tech.get("seletor_fallback")

    return {
        "id_passo": step_id,
        "tipo_passo": "action",
        "peso_narrativo": 2,
        "pause_sugerida": 2.5,
        "pedagogia": {
            "ancora": build_anchor(action),
            "tooltip_dap": "",
        },
        "alerta_instrutor": None,
        "is_conclusao": False,
        "acoes_tecnicas": [acao_out],
    }


def compile_hybrid_to_executor(
    hybrid_payload: dict[str, Any],
    *,
    keep_noise: bool = False,
    prefer_iframe_only: bool = True,
) -> dict[str, Any]:
    raw_steps = hybrid_payload.get("passos") or []
    actions: list[dict[str, Any]] = []

    for step in raw_steps:
        for action in step.get("acoes_tecnicas") or []:
            actions.append(action)

    drop_shell_when_iframe = prefer_iframe_only and has_module_iframe(actions)

    filtered = [
        a for a in actions
        if not should_drop_action(a, drop_shell_when_iframe=drop_shell_when_iframe, keep_noise=keep_noise)
    ]
    filtered = dedupe_actions(filtered)

    executor_steps = [
        action_to_executor(action, idx)
        for idx, action in enumerate(filtered, start=1)
    ]

    metadata = dict(hybrid_payload.get("metadata") or {})
    old_version = metadata.get("versao_schema", "HYBRID-v1")
    metadata["compiled_from"] = old_version
    metadata["versao_schema"] = "HYBRID-EXECUTOR-v1"

    return {
        "metadata": metadata,
        "configuracao_gravacao": hybrid_payload.get("configuracao_gravacao") or DEFAULT_GRAVACAO,
        "passos": executor_steps,
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso:")
        print("python scripts/compile_hybrid_to_executor.py roteiros_salvos/ARQUIVO_hybrid.json")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    if not input_path.exists():
        print(f"Arquivo não encontrado: {input_path}")
        sys.exit(1)

    payload = load_json(input_path)
    compiled = compile_hybrid_to_executor(payload)

    output_path = input_path.with_name(input_path.stem.replace("_hybrid", "_executor") + ".json")
    save_json(output_path, compiled)

    print("=" * 80)
    print(f"Entrada : {input_path}")
    print(f"Saída   : {output_path}")
    print(f"Passos originais : {sum(len(s.get('acoes_tecnicas') or []) for s in payload.get('passos') or [])}")
    print(f"Passos finais    : {len(compiled.get('passos') or [])}")


if __name__ == "__main__":
    main()

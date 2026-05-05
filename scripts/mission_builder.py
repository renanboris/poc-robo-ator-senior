"""
mission_builder.py — Senior Training OS
Converte os Roteiros de Gravação (JSON) em Simulações Práticas (Missões Pydantic).
"""

import glob
import json
import os
from typing import Optional

from contracts.mission import (
    MissionScoring,
    MissionStep,
    OperationalMission,
    ValidationRule,
)
from utils import limpar_nome

PASTA_ROTEIROS = "roteiros_salvos"
PASTA_MISSOES  = "missoes_ativas"

def calcular_xp_base(total_passos: int) -> int:
    """Calcula o XP base dependendo da complexidade do fluxo."""
    if total_passos <= 3: return 50
    if total_passos <= 7: return 100
    return 200

def extrair_modulo_do_titulo(titulo: str) -> str:
    """Tenta deduzir o módulo (Flow, HCM, ERP) a partir do nome da aula."""
    titulo_low = titulo.lower()
    if "flow" in titulo_low: return "Senior Flow"
    if "hcm" in titulo_low: return "HCM"
    if "erp" in titulo_low: return "ERP"
    if "ged" in titulo_low: return "GED"
    return "Senior X"

def converter_roteiro_para_missao(caminho_arquivo: str) -> Optional[OperationalMission]:
    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        dados_antigos = json.load(f)

    meta = dados_antigos.get("metadata", {})
    titulo_original = meta.get("nome_aula", "Missão Operacional")
    passos_brutos = dados_antigos.get("passos", [])

    if not passos_brutos:
        print(f"⚠️ Ignorado: {caminho_arquivo} não possui passos válidos.")
        return None

    mission_steps = []
    step_counter = 1

    for passo in passos_brutos:
        # Pula passos de conclusão que são apenas para o robô de vídeo
        if passo.get("is_conclusao"):
            continue

        for acao_tec in passo.get("acoes_tecnicas", []):
            if acao_tec.get("acao") == "concluir_video":
                continue

            intencao = acao_tec.get("intencao_semantica", "Interagir com o elemento")
            alvo = acao_tec.get("elemento_alvo", {})
            seletor = alvo.get("seletor_hint", "")
            texto_fallback = alvo.get("label_curto", "")
            tipo_acao = acao_tec.get("acao", "click")

            # Mapeamento do tipo de validação
            rule_type = "input_text" if tipo_acao in ["preencher_campo", "digitar_e_enter"] else "click"

            regra_validacao = ValidationRule(
                target_selector=seletor,
                fallback_text=texto_fallback,
                rule_type=rule_type
            )

            # Construção do Step do Jogo
            mission_step = MissionStep(
                step_id=step_counter,
                intent=intencao,
                validation=regra_validacao,
                help_tooltip=f"Precisa de ajuda? O próximo clique é em '{texto_fallback}'.",
                xp_penalty_per_hint=15,
                timeout_for_hint_sec=12 # 12 segundos ocioso = penalidade e dica ativada
            )

            mission_steps.append(mission_step)
            step_counter += 1

    total_acoes = len(mission_steps)
    xp_base = calcular_xp_base(total_acoes)

    missao = OperationalMission(
        mission_id=limpar_nome(titulo_original),
        title=titulo_original,
        module=extrair_modulo_do_titulo(titulo_original),
        difficulty="iniciante" if total_acoes <= 4 else "intermediario",
        scoring=MissionScoring(
            base_xp=xp_base,
            no_help_bonus=int(xp_base * 0.5), # 50% de bônus por autonomia
            time_target_sec=total_acoes * 15  # 15s por ação como meta
        ),
        steps=mission_steps
    )

    return missao

def compilar_todas_as_missoes():
    """Varre os roteiros antigos e gera o catálogo de missões."""
    os.makedirs(PASTA_MISSOES, exist_ok=True)
    arquivos = glob.glob(os.path.join(PASTA_ROTEIROS, "*.json"))

    sucessos = 0
    for arq in arquivos:
        try:
            missao = converter_roteiro_para_missao(arq)
            if missao:
                caminho_saida = os.path.join(PASTA_MISSOES, f"{missao.mission_id}.json")
                with open(caminho_saida, "w", encoding="utf-8") as f:
                    # O model_dump_json serializa garantindo validação Pydantic
                    f.write(missao.model_dump_json(indent=2))
                sucessos += 1
        except Exception as e:
            print(f"❌ Erro ao converter {arq}: {e}")

    print(f"\n✅ COMPILAÇÃO CONCLUÍDA: {sucessos} missões operacionais geradas em '{PASTA_MISSOES}/'.")

if __name__ == "__main__":
    print("Iniciando Mission Builder...")
    compilar_todas_as_missoes()

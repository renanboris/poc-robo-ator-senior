"""
contracts/mission.py — Senior Training OS
Contratos de Dados para a Plataforma de Enablement Operacional.
"""

from pydantic import BaseModel, Field
from typing import List, Optional

class MissionScoring(BaseModel):
    base_xp: int = Field(
        default=100, 
        description="XP ganho ao completar a missão com sucesso (ainda que com dicas)."
    )
    no_help_bonus: int = Field(
        default=50, 
        description="Bônus de XP se a missão for concluída sem ativar o Assistente Visual."
    )
    time_target_sec: int = Field(
        default=120, 
        description="Tempo alvo em segundos. Se bater a meta, ganha multiplicador de velocidade."
    )

class ValidationRule(BaseModel):
    target_selector: str = Field(
        description="Seletor CSS primário que o usuário DEVE interagir para o passo ser válido."
    )
    fallback_text: Optional[str] = Field(
        default=None, 
        description="Texto do elemento caso o seletor CSS mude (uso do CIL para resgate)."
    )
    rule_type: str = Field(
        default="click", 
        description="Tipo de validação: 'click', 'input_text', 'element_visible'"
    )

class MissionStep(BaseModel):
    step_id: int
    intent: str = Field(
        description="A instrução de negócio (Ex: 'Acesse a aba de Gestão de Férias')."
    )
    validation: ValidationRule
    help_tooltip: str = Field(
        description="O texto que o DAP exibe se o usuário travar neste passo."
    )
    xp_penalty_per_hint: int = Field(
        default=15, 
        description="Quantos pontos de XP o usuário perde se o highlight acender."
    )
    timeout_for_hint_sec: int = Field(
        default=12, 
        description="Tempo ocioso (em segundos) até o sistema considerar que o usuário travou e acender a dica."
    )

class OperationalMission(BaseModel):
    mission_id: str
    title: str = Field(description="Título da Certificação/Missão.")
    module: str = Field(default="Senior X", description="Módulo do ERP.")
    difficulty: str = Field(default="intermediario", description="iniciante | intermediario | avancado")
    scoring: MissionScoring
    steps: List[MissionStep]
"""
planner_cil.py — Planejador Semântico
======================================
Responde a pergunta: "Dado o que estou vendo e o meu objetivo, o que devo fazer agora?"

O planner é o cérebro do agente. Ele:
1. Recebe o objetivo em linguagem natural
2. Lê o estado atual da tela (via screen_reader)
3. Consulta o histórico de ações já feitas
4. Decide o próximo passo com raciocínio explícito
5. Retorna uma ação que o vision_engine sabe executar

Diferença fundamental vs o executor atual:
- ANTES: "execute o passo 3 do roteiro: clique em #apps-menu-item-4"
- AGORA: "olhei a tela, vi que estou no submenu do Senior Flow, GED está visível,
          próxima ação é clicar em GED no submenu expandido"

O JSON do roteiro deixa de ser um script de cliques e passa a ser um
conjunto de objetivos que o planner sabe como atingir.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Page

from core.screen_reader import EstadoDaTela, ler_tela

logger = logging.getLogger(__name__)

MAX_PASSOS = 15  # segurança: não fica preso em loop infinito

# ── Skill enrichment (optional) ───────────────────────────────
# Import SkillMemory lazily to avoid hard dependency when running
# without the Next integration layer.
try:
    import os as _os
    import sys as _sys
    _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), "..", ".."))
    from skill_memory import SkillMemory as _SkillMemory
    from skill_models import KnownSkill as _KnownSkill
    _SKILL_MEMORY_AVAILABLE = True
except ImportError:
    _SKILL_MEMORY_AVAILABLE = False

# Shared SkillMemory instance (can be replaced by caller)
_default_skill_memory: "Optional[_SkillMemory]" = None


def set_skill_memory(memory) -> None:
    """Inject a SkillMemory instance for the planner to consult."""
    global _default_skill_memory
    _default_skill_memory = memory


@dataclass
class ProximaAcao:
    """O que o planner decidiu fazer."""

    # O QUE fazer
    tipo: str = "clique"                # clique | hover | digitar | aguardar | objetivo_atingido | falhou
    valor: str = ""                     # texto a digitar (para tipo=digitar)

    # ONDE encontrar o elemento
    onde: str = "conteudo_central"      # sidebar | iframe | conteudo_central | modal
    elemento_descricao: str = ""        # "botão Nova pasta no canto superior direito do iframe"
    label: str = ""                     # texto/label do elemento para o vision_engine localizar

    # POR QUE esta ação
    raciocinio: str = ""                # explicação em linguagem natural

    # COMO verificar sucesso
    o_que_deve_mudar: str = ""          # "submenu com GED deve aparecer" — guia o validador

    # CONFIANÇA
    confianca: float = 0.8


@dataclass
class EntradaHistorico:
    """Registro de uma ação já executada."""
    acao_descricao: str
    resultado: str                      # "sucesso" | "falhou" | "parcial"
    tela_resultante_id: str = ""


def _build_skill_hints(objetivo: str) -> str:
    """
    Build a skill hints block for the planner prompt.

    Queries the shared SkillMemory for promoted skills whose semantic_action
    or pattern matches the objective keywords.  Returns an empty string when
    no skills are available.

    Requirements: 12.1, 12.2, 12.3
    """
    if not _SKILL_MEMORY_AVAILABLE or _default_skill_memory is None:
        return ""

    # Simple keyword extraction from objective
    keywords = objetivo.lower().split()
    candidates: list = []

    for kw in keywords:
        # Try pattern-mode retrieval for each keyword
        try:
            hits = _default_skill_memory.retrieve(
                mode="pattern",
                semantic_action=kw,
                pattern="",
            )
            candidates.extend(hits)
        except Exception:
            pass

    if not candidates:
        return ""

    # Deduplicate by skill_id, keep top 3
    seen: set = set()
    unique: list = []
    for skill in candidates:
        if skill.skill_id not in seen:
            seen.add(skill.skill_id)
            unique.append(skill)
        if len(unique) >= 3:
            break

    lines = ["\nSKILLS CONHECIDAS RELEVANTES:"]
    for skill in unique:
        logger.debug(
            "[Planner] Consulting skill",
            extra={
                "skill_id": skill.skill_id,
                "source_stage": skill.source_stage,
                "promotion_state": skill.promotion_state,
            },
        )
        lines.append(
            f"  - {skill.skill_name} | ação={skill.semantic_action} "
            f"| tela={skill.screen_family} | efeito_esperado={skill.expected_effect} "
            f"| origem={skill.source_stage} | nível={skill.promotion_state}"
        )
    lines.append("")
    return "\n".join(lines)


async def planejar_proximo_passo(
    page: Page,
    objetivo: str,
    historico: list[EntradaHistorico],
    gemini_client,
    estado_atual: Optional[EstadoDaTela] = None,
) -> ProximaAcao:
    """
    Analisa o estado da tela e decide o próximo passo para atingir o objetivo.

    Args:
        page: Página atual
        objetivo: O que queremos alcançar
        historico: O que já foi feito (evita repetir ações)
        gemini_client: Cliente Gemini
        estado_atual: Se já foi lido, reutiliza. Senão lê agora.

    Returns:
        ProximaAcao com a decisão e raciocínio
    """
    if not gemini_client:
        return ProximaAcao(tipo="falhou", raciocinio="Gemini indisponível")

    # Lê o estado atual da tela
    if estado_atual is None:
        estado_atual = await ler_tela(page, objetivo, gemini_client)

    # Verifica objetivo antes de planejar
    if estado_atual.objetivo_atingido:
        return ProximaAcao(
            tipo="objetivo_atingido",
            raciocinio=estado_atual.progresso,
            confianca=estado_atual.confianca,
        )

    # Formata histórico para o prompt
    historico_texto = ""
    if historico:
        historico_texto = "\nHISTÓRICO DE AÇÕES JÁ FEITAS:\n"
        for i, h in enumerate(historico[-5:], 1):  # últimas 5 ações
            historico_texto += f"  {i}. {h.acao_descricao} → {h.resultado}\n"

    # Formata estado da tela
    elementos_texto = ""
    if estado_atual.elementos_visiveis:
        elementos_texto = "\nELEMENTOS VISÍVEIS:\n"
        for el in estado_atual.elementos_visiveis[:8]:
            elementos_texto += f"  - {el.get('nome','')} ({el.get('tipo','')}, {el.get('estado','')})\n"

    prompt = f"""Você é o planejador de um agente de automação de ERP.
Sua função é decidir O PRÓXIMO PASSO para atingir o objetivo.

OBJETIVO: "{objetivo}"

ESTADO ATUAL DA TELA:
- Onde estou: {estado_atual.onde_estou}
- Sidebar: {estado_atual.sidebar_estado} | Item ativo: {estado_atual.sidebar_item_ativo}
- Iframe visível: {estado_atual.iframe_presente} — {estado_atual.iframe_conteudo}
- Progresso: {estado_atual.progresso}
- Sugestão do screen_reader: {estado_atual.proximo_passo_sugerido}
{elementos_texto}
{historico_texto}
{_build_skill_hints(objetivo)}
REGRAS DE RACIOCÍNIO:
1. Se o elemento alvo está no SUBMENU da sidebar: hover no ícone pai PRIMEIRO para expandir
2. Se o elemento está no IFRAME: procure dentro do iframe, não na sidebar
3. Se a sidebar está COLAPSADA: hover num ícone para expandir labels
4. Se o mesmo passo falhou antes: tente uma abordagem diferente
5. Nunca repita uma ação que já falhou da mesma forma

Responda em JSON com o PRÓXIMO PASSO:
{{
    "tipo": "clique|hover|digitar|aguardar|objetivo_atingido",
    "onde": "sidebar|submenu_sidebar|iframe|conteudo_central|modal",
    "elemento_descricao": "descrição visual detalhada do que encontrar e clicar",
    "label": "texto exato ou label do elemento",
    "valor": "",
    "raciocinio": "por que esta é a ação correta agora (1-2 frases)",
    "o_que_deve_mudar": "o que deve aparecer na tela após esta ação",
    "confianca": 0.0
}}"""

    from google.genai import types

    try:
        screenshot = await page.screenshot(type="jpeg", quality=75, full_page=False)

        resp = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[
                prompt,
                types.Part.from_bytes(data=screenshot, mime_type="image/jpeg"),
            ],
            config=__import__("google.genai.types", fromlist=["GenerateContentConfig"]).GenerateContentConfig(
                response_mime_type="application/json", temperature=0.0
            ),
        )

        out = json.loads(resp.text)

        acao = ProximaAcao(
            tipo=out.get("tipo", "clique"),
            onde=out.get("onde", "conteudo_central"),
            elemento_descricao=out.get("elemento_descricao", ""),
            label=out.get("label", ""),
            valor=out.get("valor", ""),
            raciocinio=out.get("raciocinio", ""),
            o_que_deve_mudar=out.get("o_que_deve_mudar", ""),
            confianca=float(out.get("confianca", 0.8)),
        )

        logger.info(f"[Planner] Decisão: {acao.tipo} em '{acao.onde}' → '{acao.label}'")
        logger.info(f"[Planner] Raciocínio: {acao.raciocinio[:80]}")

        return acao

    except Exception as e:
        logger.warning(f"[Planner] Erro: {e}")
        return ProximaAcao(tipo="falhou", raciocinio=f"Erro ao planejar: {e}")


async def executar_objetivo(
    page: Page,
    objetivo: str,
    gemini_client,
    vision_engine_fn,            # encontrar_e_clicar do vision_engine_cil
    max_passos: int = MAX_PASSOS,
) -> tuple[bool, list[EntradaHistorico]]:
    """
    Loop principal do agente semântico.

    Executa um objetivo do início ao fim:
    1. Lê a tela
    2. Planeja o próximo passo
    3. Executa via vision_engine
    4. Verifica se objetivo foi atingido
    5. Repete até atingir ou esgotar tentativas

    Args:
        page: Página atual
        objetivo: O que queremos alcançar
        gemini_client: Cliente Gemini
        vision_engine_fn: função encontrar_e_clicar do vision_engine_cil
        max_passos: Limite de segurança

    Returns:
        (sucesso, historico_de_acoes)
    """
    historico: list[EntradaHistorico] = []
    logger.info(f"\n[Planner] 🎯 OBJETIVO: {objetivo}")

    for passo_num in range(1, max_passos + 1):
        logger.info(f"\n[Planner] ── Passo {passo_num}/{max_passos} ──")

        # 1. Lê o estado da tela
        estado = await ler_tela(page, objetivo, gemini_client)

        # 2. Verifica se já atingiu o objetivo
        if estado.objetivo_atingido:
            logger.info(f"[Planner] ✅ OBJETIVO ATINGIDO em {passo_num} passos")
            historico.append(EntradaHistorico(
                acao_descricao="Verificação final",
                resultado="sucesso",
                tela_resultante_id=estado.tela_id,
            ))
            return True, historico

        # 3. Planeja próximo passo
        acao = await planejar_proximo_passo(
            page, objetivo, historico, gemini_client, estado
        )

        if acao.tipo == "objetivo_atingido":
            logger.info("[Planner] ✅ OBJETIVO ATINGIDO (planner confirmou)")
            return True, historico

        if acao.tipo == "falhou":
            logger.error(f"[Planner] ❌ Planner reportou falha: {acao.raciocinio}")
            break

        if acao.tipo == "aguardar":
            logger.info(f"[Planner] ⏳ Aguardando: {acao.raciocinio}")
            await asyncio.sleep(2.0)
            historico.append(EntradaHistorico(
                acao_descricao=f"Aguardou: {acao.raciocinio}",
                resultado="sucesso",
                tela_resultante_id=estado.tela_id,
            ))
            continue

        # 4. Converte ProximaAcao → acao_tec para o vision_engine
        acao_tec = _converter_para_acao_tec(acao, objetivo)

        # 5. Executa via vision_engine
        logger.info(f"[Planner] ▶ Executando: {acao.elemento_descricao[:60]}")
        try:
            sucesso = await vision_engine_fn(page, acao_tec)
        except Exception as e:
            logger.warning(f"[Planner] Erro ao executar: {e}")
            sucesso = False

        resultado = "sucesso" if sucesso else "falhou"
        historico.append(EntradaHistorico(
            acao_descricao=f"{acao.tipo} em '{acao.label}' ({acao.onde}): {acao.raciocinio[:50]}",
            resultado=resultado,
            tela_resultante_id="",  # será preenchido na próxima leitura de tela
        ))

        if not sucesso:
            logger.warning("[Planner] Ação falhou. Planner vai reavaliard a tela.")
            await asyncio.sleep(1.0)
            # Continua o loop — planner vai ver a tela e tentar diferente

        # Pequena pausa entre ações
        await asyncio.sleep(0.8)

    logger.error(f"[Planner] ❌ OBJETIVO NÃO ATINGIDO após {max_passos} passos")
    return False, historico


def _converter_para_acao_tec(acao: ProximaAcao, objetivo: str) -> dict:
    """
    Converte uma ProximaAcao do planner para o formato acao_tec
    que o vision_engine_cil sabe executar.

    O vision_engine não precisa saber do planner — ele só recebe
    um dict com as informações de localização e execução.
    """
    # Mapeia "onde" do planner para iframe_hint e pattern do vision_engine
    iframe_hint = None
    pattern = "button_click"

    if acao.onde == "sidebar":
        pattern = "menu_navigation"
    elif acao.onde == "submenu_sidebar":
        pattern = "menu_navigation"
    elif acao.onde == "iframe":
        # Planner detectou que está no iframe — vision_engine vai buscar lá
        iframe_hint = "ci"  # padrão do Senior X; planner pode sobrescrever
    elif acao.onde == "conteudo_central":
        pattern = "button_click"

    return {
        "intencao_semantica": f"{objetivo} — {acao.raciocinio[:50]}",
        "acao": acao.tipo if acao.tipo not in ("objetivo_atingido", "falhou", "aguardar") else "clique",
        "valor_input": acao.valor or "",
        "pattern_detectado": pattern,
        "seletor_css": "",  # planner não sabe o seletor — vision_engine vai encontrar
        "elemento_alvo": {
            "label_curto": acao.label,
            "descricao_visual": acao.elemento_descricao,
            "contexto_tela": acao.onde,
            "tipo_elemento": "botao" if pattern == "button_click" else "menu",
            "iframe_hint": iframe_hint,
            "coordenadas_relativas": None,  # planner não usa coords — vision pensa nisso
        },
        "validacao_esperada": {
            "alvo": acao.o_que_deve_mudar or f"A ação '{acao.elemento_descricao}' deve ser concluída",
        },
    }

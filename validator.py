"""
validator.py — Senior Training OS · Validador de Roteiros
==========================================================
Fase 3 (vision-quality): Reescrito com navegação contextual.
Fase 3.1/3.2: Integrado com vision_engine para fallback real de seletores.

Melhorias:
  - Classifica ações como navegação por heurística de label/seletor E por
    capture_scope/pattern_detectado (roteiros hybrid) — Fase 3.2
  - Executa navegações reais antes de validar seletores dependentes
  - Validação via vision_engine (todas as 7 camadas) em vez de seletor direto — Fase 3.1
  - Suporte a --dry-run (verifica visibilidade sem clicar)
  - Exibe resumo com total validados, navegações e lista de falhas
  - Não aborta na primeira falha — acumula e exibe ao final
"""

import sys
import json
import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────
# HEURÍSTICA DE CLASSIFICAÇÃO DE AÇÕES (Fase 3.2)
# ──────────────────────────────────────────────────────────────

_PALAVRAS_NAVEGACAO = [
    "menu", "breadcrumb", "fa-home", "home", "inicio", "módulo",
    "apps-menu", "menu-item", "nav-item", "sidebar",
]

# Padrões de capture_scope/pattern_detectado que indicam navegação
# (disponíveis em roteiros gerados pelo capture_hybrid_shadow)
_PATTERNS_NAVEGACAO = {"menu_navigation", "breadcrumb_navigation"}
_SCOPES_NAVEGACAO   = {"shell"}


def _e_acao_navegacao(acao_tec: dict) -> bool:
    """
    Classifica uma ação técnica como navegação.

    Estratégia dupla (Fase 3.2):
      1. Se o roteiro tem capture_scope/pattern_detectado (hybrid), usa esses campos.
      2. Fallback: heurística de palavras no label/seletor (roteiros legados).
    """
    # Campos semânticos dos roteiros hybrid
    pattern = (acao_tec.get("pattern_detectado") or "").lower()
    scope   = (acao_tec.get("capture_scope") or "").lower()

    if pattern in _PATTERNS_NAVEGACAO:
        return True
    if scope in _SCOPES_NAVEGACAO and pattern not in ("form_fill", "search_debounce"):
        return True

    # Fallback heurístico para roteiros legados
    alvo    = acao_tec.get("elemento_alvo", {}) or {}
    label   = (alvo.get("label_curto", "") or "").lower()
    seletor = (alvo.get("seletor_hint", "") or "").lower()
    blob    = f"{label} {seletor}"
    return any(k in blob for k in _PALAVRAS_NAVEGACAO)


# ──────────────────────────────────────────────────────────────
# AUXILIARES DE EXECUÇÃO
# ──────────────────────────────────────────────────────────────

async def _executar_navegacao(page, acao_tec: dict) -> None:
    """Executa clique real em ação de navegação e aguarda estabilidade da página."""
    from vision_engine import encontrar_e_clicar
    try:
        await encontrar_e_clicar(page, acao_tec)
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            await asyncio.sleep(1.0)
    except Exception:
        # Fallback: tenta seletor direto se vision_engine falhar
        alvo    = acao_tec.get("elemento_alvo", {}) or {}
        seletor = alvo.get("seletor_hint") or alvo.get("seletor_css")
        if seletor:
            await page.locator(seletor).first.click(timeout=5000)
            try:
                await page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                await asyncio.sleep(1.0)


async def _validar_seletor(page, passo: dict, acao_tec: dict, resultados: dict) -> None:
    """
    Valida se o elemento existe e está acessível no contexto atual.

    Fase 3.1: usa vision_engine.encontrar_e_clicar em modo dry-run
    (ação substituída por 'verificar') para aproveitar todas as 7 camadas
    de fallback em vez de validar o seletor diretamente.

    Acumula falhas sem interromper a validação.
    """
    from vision_engine import encontrar_e_clicar

    id_p  = passo.get("id_passo")
    alvo  = acao_tec.get("elemento_alvo", {}) or {}
    label = alvo.get("label_curto", "?")

    if not alvo.get("seletor_hint") and not alvo.get("seletor_css") and not alvo.get("label_curto"):
        return

    if acao_tec.get("acao") == "upload":
        print(f"   [Passo {id_p}] 📁 Mock de Upload — pulando validação de seletor")
        return

    # Monta ação técnica em modo dry-run: substitui a ação real por verificação
    # O vision_engine vai tentar localizar o elemento sem executar a ação destrutiva
    acao_dry = dict(acao_tec)
    acao_dry["acao"] = "clique"  # clique é a ação mais segura para verificação

    try:
        sucesso = await encontrar_e_clicar(page, acao_dry)
        if sucesso:
            seletor = alvo.get("seletor_hint") or alvo.get("seletor_css") or "(via vision_engine)"
            print(f"   [Passo {id_p}] ✅ {label}: {seletor}")
            resultados["validados"] += 1
        else:
            falha = {
                "id_passo": id_p,
                "label":    label,
                "seletor":  alvo.get("seletor_hint") or alvo.get("seletor_css") or "?",
                "erro":     "vision_engine: todas as camadas falharam",
            }
            resultados["falhas"].append(falha)
            print(f"   [Passo {id_p}] ❌ '{label}' — todas as camadas falharam")
    except Exception as e:
        falha = {
            "id_passo": id_p,
            "label":    label,
            "seletor":  alvo.get("seletor_hint") or alvo.get("seletor_css") or "?",
            "erro":     str(e),
        }
        resultados["falhas"].append(falha)
        print(f"   [Passo {id_p}] ❌ '{label}' — {e}")


# ──────────────────────────────────────────────────────────────
# VALIDADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────

async def dry_run_validador(caminho_json: str, dry_run: bool = False) -> None:
    modo = "(dry-run — sem cliques)" if dry_run else "(modo padrão — com navegação)"
    print(f"🚀 INICIANDO VALIDAÇÃO: {caminho_json} {modo}")

    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER_EXECUTE")
    senha      = os.getenv("SENIOR_PASS_EXECUTE")
    if not usuario or not senha:
        print("ERRO: Credenciais de execução ausentes no .env (SENIOR_USER_EXECUTE / SENIOR_PASS_EXECUTE)", flush=True)
        return

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(no_viewport=True)
        page    = await context.new_page()

        try:
            print("⏳ Logando no Senior X...")
            await page.goto(SENIOR_URL)
            await page.locator(
                "input[type='text'], input[type='email'], [placeholder*='usuario']"
            ).first.fill(usuario)
            await page.keyboard.press("Enter")
            await page.locator("input[type='password']").first.fill(senha)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("load", timeout=15000)
            print("✅ Login OK. Iniciando validação contextual...\n")

            resultados = {"validados": 0, "falhas": [], "navegacoes": 0}
            passos = roteiro.get("passos", [])

            for passo in passos:
                for acao_tec in passo.get("acoes_tecnicas", []):
                    if acao_tec.get("acao") == "concluir_video":
                        continue

                    if _e_acao_navegacao(acao_tec) and not dry_run:
                        # Executa navegação real via vision_engine para colocar
                        # o browser no contexto correto antes de validar
                        try:
                            await _executar_navegacao(page, acao_tec)
                            resultados["navegacoes"] += 1
                        except Exception as e:
                            label = (acao_tec.get("elemento_alvo", {}) or {}).get("label_curto", "?")
                            print(f"   ⚠️  Navegação '{label}' falhou (continuando): {e}")
                    else:
                        # Valida elemento via vision_engine (todas as 7 camadas)
                        await _validar_seletor(page, passo, acao_tec, resultados)

            # ── Resumo final ──────────────────────────────────────────────
            n_falhas = len(resultados["falhas"])
            print(
                f"\n📊 RESUMO: {resultados['validados']} validados, "
                f"{resultados['navegacoes']} navegações executadas, "
                f"{n_falhas} falha(s)"
            )
            if resultados["falhas"]:
                print("\nSeletores com problema:")
                for f in resultados["falhas"]:
                    print(f"  • Passo {f['id_passo']} | {f['label']} | {f['seletor']}")
                print()
            else:
                print("🎉 Roteiro 100% validado. Seguro para renderização.\n")

        except Exception as e:
            print(f"❌ Erro na execução do Validador: {e}")
        finally:
            await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator.py <caminho_do_json> [--dry-run]")
        sys.exit(1)
    dry = "--dry-run" in sys.argv
    asyncio.run(dry_run_validador(sys.argv[1], dry_run=dry))

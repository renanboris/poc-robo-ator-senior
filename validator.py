"""
validator.py — Senior Training OS · Validador de Roteiros
==========================================================
Fase 3 (vision-quality): Reescrito com navegação contextual.

Melhorias:
  - Classifica ações como navegação ou validáveis por heurística de label/seletor
  - Executa navegações reais antes de validar seletores dependentes
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
# HEURÍSTICA DE CLASSIFICAÇÃO DE AÇÕES
# ──────────────────────────────────────────────────────────────

_PALAVRAS_NAVEGACAO = [
    "menu", "breadcrumb", "fa-home", "home", "inicio", "módulo",
    "apps-menu", "menu-item", "nav-item", "sidebar",
]


def _e_acao_navegacao(acao_tec: dict) -> bool:
    """
    Classifica uma ação técnica como navegação por heurística de label/seletor.
    Não depende do campo tipo_passo — opera sobre o conteúdo do elemento_alvo.
    Retorna True se o label ou seletor indicar interação com menu, breadcrumb ou navegação.
    """
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
    alvo    = acao_tec.get("elemento_alvo", {}) or {}
    seletor = alvo.get("seletor_hint") or alvo.get("seletor_css")
    if not seletor:
        return
    await page.locator(seletor).first.click(timeout=5000)
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except Exception:
        await asyncio.sleep(1.0)


async def _validar_seletor(page, passo: dict, acao_tec: dict, resultados: dict) -> None:
    """
    Valida visibilidade e estado habilitado de um seletor no contexto atual.
    Acumula falhas em resultados["falhas"] sem interromper a validação.
    """
    id_p    = passo.get("id_passo")
    alvo    = acao_tec.get("elemento_alvo", {}) or {}
    seletor = alvo.get("seletor_hint") or alvo.get("seletor_css")
    label   = alvo.get("label_curto", seletor or "?")

    if not seletor:
        return

    if acao_tec.get("acao") == "upload":
        print(f"   [Passo {id_p}] 📁 Mock de Upload em: {seletor}")
        return

    try:
        locator = page.locator(seletor).first
        await locator.wait_for(state="visible", timeout=3000)
        await locator.wait_for(state="enabled", timeout=1000)
        print(f"   [Passo {id_p}] ✅ {label}: {seletor}")
        resultados["validados"] += 1
    except Exception as e:
        falha = {
            "id_passo": id_p,
            "label":    label,
            "seletor":  seletor,
            "erro":     str(e),
        }
        resultados["falhas"].append(falha)
        print(f"   [Passo {id_p}] ❌ '{label}' — {seletor}")


# ──────────────────────────────────────────────────────────────
# VALIDADOR PRINCIPAL
# ──────────────────────────────────────────────────────────────

async def dry_run_validador(caminho_json: str, dry_run: bool = False) -> None:
    modo = "(dry-run — sem cliques)" if dry_run else "(modo padrão — com navegação)"
    print(f"🚀 INICIANDO VALIDAÇÃO: {caminho_json} {modo}")

    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER")
    senha      = os.getenv("SENIOR_PASS")

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
                        # Executa navegação real para colocar o browser no contexto correto
                        try:
                            await _executar_navegacao(page, acao_tec)
                            resultados["navegacoes"] += 1
                        except Exception as e:
                            alvo  = acao_tec.get("elemento_alvo", {}) or {}
                            label = alvo.get("label_curto", "?")
                            print(f"   ⚠️  Navegação '{label}' falhou (continuando): {e}")
                    else:
                        # Valida seletor no contexto atual
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

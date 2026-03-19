"""
main_cil.py — Testador Isolado do CIL v2
"""
import sys
import json
import asyncio
import logging
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(message)s")

from vision_engine_cil import encontrar_e_clicar


async def esperar_spa_pronta(page):
    print("⏳ Aguardando Angular SPA inicializar completamente...")
    sinais = [
        "app-root",
        "[class*='sidebar']",
        "nav",
        "aside",
    ]
    for _ in range(30):
        for sel in sinais:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0 and await loc.is_visible():
                    print(f"   [SPA] Painel detectado via '{sel}'. Angular pronto. ✅")
                    await asyncio.sleep(2.0)
                    return
            except Exception:
                pass
        await asyncio.sleep(1)
    print("   [SPA] Timeout de inicialização. Seguindo com cautela...")


async def testar_roteiro_semantico(caminho_json):
    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    print(f"\n🚀 Iniciando Execução CIL-v2: {roteiro['metadata']['nome_aula']}\n")

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        try:
            print("⏳ Fazendo login automático...")
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2)
            await page.keyboard.press("Escape")

            await page.locator("input[type='text'], input[type='email'], [placeholder*='usuario'], [placeholder*='Usuário']").first.fill(usuario)
            await asyncio.sleep(0.5)
            try:
                await page.locator("button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')").first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")

            await page.locator("input[type='password']").first.fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await esperar_spa_pronta(page)
        except Exception as e:
            print(f"⚠️ Erro no auto-login: {e}. Faça o login manualmente rápido!")
            await asyncio.sleep(20)
            await esperar_spa_pronta(page)

        print("\n🎯 Iniciando passos do roteiro...\n")

        for passo in roteiro.get("passos", []):
            for acao in passo.get("acoes_tecnicas", []):
                if acao.get("acao") == "concluir_video":
                    continue

                max_tentativas = 2
                for tentativa in range(1, max_tentativas + 1):
                    sucesso = await encontrar_e_clicar(page, acao)
                    if sucesso:
                        break
                    if tentativa < max_tentativas:
                        print(f"   [Retry] Tentativa {tentativa+1}/{max_tentativas} para: '{acao.get('intencao_semantica')}'\n")
                        await asyncio.sleep(1.0)
                else:
                    print(f"\n❌ FALHA CRÍTICA no passo: {acao.get('intencao_semantica')}")
                    await browser.close()
                    return

        print("\n✅ Roteiro Semântico Executado com Sucesso Total!")
        await asyncio.sleep(2)
        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python main_cil_v2.py <caminho_do_json>")
    else:
        asyncio.run(testar_roteiro_semantico(sys.argv[1]))

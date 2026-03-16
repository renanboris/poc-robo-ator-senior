import sys
import json
import asyncio
import os
from playwright.async_api import async_playwright
from dotenv import load_dotenv

load_dotenv()

async def dry_run_validador(caminho_json: str):
    print(f"🚀 INICIANDO VALIDAÇÃO FANTASMA: {caminho_json}")
    
    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as pw:
        # HEADLESS=TRUE (Roda invisível e ultra rápido)
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        try:
            print("⏳ Logando no Senior X...")
            await page.goto(SENIOR_URL)
            await page.locator("input[type='text'], input[type='email'], [placeholder*='usuario']").first.fill(usuario)
            await page.keyboard.press("Enter")
            await page.locator("input[type='password']").first.fill(senha)
            await page.keyboard.press("Enter")
            await page.wait_for_load_state("load", timeout=15000)
            print("✅ Login OK. Testando seletores da aula...")

            passos = roteiro.get("passos", [])
            for passo in passos:
                id_p = passo.get("id_passo")
                
                for acao_tec in passo.get("acoes_tecnicas", []):
                    acao = acao_tec.get("acao")
                    if acao == "concluir_video":
                        continue
                        
                    alvo = acao_tec.get("elemento_alvo", {})
                    seletor = alvo.get("seletor_hint") or alvo.get("seletor_css")
                    
                    if not seletor:
                        continue

                    # Tenta encontrar e clicar na velocidade da luz (Timeout curto de 3s)
                    try:
                        locator = page.locator(seletor).first
                        if acao == "upload":
                            print(f"   [Passo {id_p}] 📁 Mock de Upload em: {seletor}")
                            continue  # Ignora upload real no dry-run

                        # FIX Bug #VAL-01: force=True foi removido.
                        # Com force=True, o Playwright bypassa verificações de visibilidade,
                        # habilitação e cobertura do elemento — um botão desabilitado ou
                        # escondido atrás de um modal passaria como "válido".
                        # Sem force=True, o dry-run valida o estado REAL do elemento.
                        await locator.wait_for(state="visible", timeout=3000)
                        await locator.wait_for(state="enabled", timeout=1000)
                        print(f"   [Passo {id_p}] ✅ Seletor válido e elemento visível: {seletor}")
                    except Exception as e:
                        print(f"\n❌ ERRO CRÍTICO NO PASSO {id_p}!")
                        print(f"   O botão '{alvo.get('label_curto', seletor)}' não foi encontrado, mudou ou está desabilitado.")
                        print(f"   Seletor: {seletor}")
                        print(f"   Detalhe: {e}")
                        await browser.close()
                        return

            print("\n🎉 SUCESSO! Roteiro 100% validado. Seguro para renderização.")
        except Exception as e:
            print(f"❌ Erro na execução do Validador: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python validator.py <caminho_do_json>")
    else:
        asyncio.run(dry_run_validador(sys.argv[1]))
import asyncio
import os
import re
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ==========================================
# 🔦 FUNÇÃO SÊNIOR: TOUR GUIADO (HOLOFOTE)
# ==========================================
async def tour_clique(locator, nome_etapa, cor_neon="#00ff00"):
    print(f"🔦 [Tour] Focando em: {nome_etapa}...")
    
    # Rola suavemente até o elemento
    await locator.scroll_into_view_if_needed()
    await asyncio.sleep(0.5)
    
    # O robô repousa o mouse em cima para ativar submenus
    await locator.hover()
    
    # Guarda o estilo original do sistema para não quebrar o layout
    estilo_original = await locator.evaluate("el => el.style.outline")
    sombra_original = await locator.evaluate("el => el.style.boxShadow")
    transicao_original = await locator.evaluate("el => el.style.transition")
    
    # Acende o HOLOFOTE NEON (Borda verde brilhante)
    await locator.evaluate("el => el.style.transition = 'all 0.3s ease'")
    await locator.evaluate(f"el => el.style.outline = '4px solid {cor_neon}'")
    await locator.evaluate(f"el => el.style.boxShadow = '0 0 20px {cor_neon}'")
    
    # Pausa dramática para o humano assistir ao Tour
    await asyncio.sleep(1.5)
    
    # Apaga a luz e clica suavemente
    await locator.evaluate(f"el => el.style.outline = '{estilo_original}'")
    await locator.evaluate(f"el => el.style.boxShadow = '{sombra_original}'")
    await locator.evaluate(f"el => el.style.transition = '{transicao_original}'")
    
    await locator.click()

# ==========================================
# 🤖 SCRIPT PRINCIPAL
# ==========================================
async def main():
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("❌ ERRO: Verifique as credenciais no .env")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("🚀 Acessando o portal da Senior...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        
        await page.wait_for_timeout(2000)
        await page.keyboard.press("Escape")

        print("📝 Login...")
        await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
        await page.wait_for_timeout(500)
        await page.get_by_role("button", name="Próximo").click()

        senha_input = page.locator("input[type='password']")
        await senha_input.wait_for(state="visible")
        await page.wait_for_timeout(500)
        await senha_input.fill(senha)

        await page.wait_for_timeout(500)
        await senha_input.press("Enter")

        print("⏳ Aguardando renderização do painel...")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(7000) 
        await page.keyboard.press("Escape")

        print("\n🎬 --- INICIANDO O TOUR VIRTUAL --- 🎬\n")
        
        # 1. Menu Senior Flow
        menu_senior_flow = page.locator("[id='menu-label-Senior Flow']").locator("..")
        await tour_clique(menu_senior_flow, "Menu Lateral: Senior Flow")

        # 2. Submenu GED
        await page.wait_for_timeout(1000)
        menu_ged = page.locator("span", has_text="GED").first.locator("..")
        await tour_clique(menu_ged, "Submenu: GED", cor_neon="#ff00ff") # Destaque Rosa/Roxo

        # 3. Opção Documentos
        await page.wait_for_timeout(1000)
        menu_documentos = page.locator("span", has_text="Documentos").first.locator("..")
        await tour_clique(menu_documentos, "Módulo: Documentos")

        print("⏳ Aguardando a interface pesada do Iframe carregar...")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(4000)

        # 4. Botão Nova Pasta (Dentro do Iframe!)
        frame_alvo = page.frame_locator('iframe[name="ci"]')
        btn_nova_pasta = frame_alvo.get_by_role("button", name="Nova pasta")
        await btn_nova_pasta.wait_for(state="visible", timeout=10000)
        
        await tour_clique(btn_nova_pasta, "Ação Principal: Criar Nova Pasta", cor_neon="#00ffff") # Ciano

        print("\n✍️ Criando a pasta raiz do curso...")
        await page.wait_for_timeout(1500) 
        
        # A sua lógica perfeita de renomear a pasta!
        nome_pasta_gerada = frame_alvo.get_by_role("heading", name="Nova pasta").first
        await nome_pasta_gerada.wait_for(state="visible", timeout=10000)
        await nome_pasta_gerada.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        
        print("🧹 Apagando o texto selecionado (Backspace)...")
        await page.keyboard.press("Backspace")
        
        print("⌨️ Renomeando para 'Universidade Corporativa'...")
        await page.wait_for_timeout(200)
        await page.keyboard.type("Universidade Corporativa", delay=50)

        print("💾 Salvando (Apertando ENTER)...")
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")

        print("✅ Tour e criação finalizados com sucesso!")
        await page.pause()

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

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
        print("🛡️ Disparando tecla 'ESC' para limpar pop-ups do navegador...")
        await page.keyboard.press("Escape")

        print("📝 Preenchendo usuário...")
        await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
        await page.wait_for_timeout(500)
        await page.get_by_role("button", name="Próximo").click()

        print("🔑 Preenchendo senha...")
        senha_input = page.locator("input[type='password']")
        await senha_input.wait_for(state="visible")
        await page.wait_for_timeout(500)
        await senha_input.fill(senha)

        print("🚪 Enviando comando de Login (Apertando ENTER)...")
        await page.wait_for_timeout(500)
        await senha_input.press("Enter")

        print("⏳ Aguardando painel carregar (7 segundos)...")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(7000) 
        
        await page.keyboard.press("Escape")

        print("🧍‍♂️ Simulando navegação humana no Menu Lateral...")
        
        menu_senior_flow = page.locator("[id='menu-label-Senior Flow']").locator("..")
        await menu_senior_flow.scroll_into_view_if_needed()
        await page.wait_for_timeout(1000) 
        await menu_senior_flow.hover()
        await page.wait_for_timeout(500)
        await menu_senior_flow.click()

        print("📂 Procurando submenu 'GED'...")
        await page.wait_for_timeout(1500)
        menu_ged = page.locator("span", has_text="GED").first.locator("..")
        await menu_ged.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await menu_ged.hover()
        await page.wait_for_timeout(500)
        await menu_ged.click()

        print("📄 Procurando opção 'Documentos'...")
        await page.wait_for_timeout(1500)
        menu_documentos = page.locator("span", has_text="Documentos").first.locator("..")
        await menu_documentos.scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await menu_documentos.hover()
        await page.wait_for_timeout(500)
        await menu_documentos.click()

        print("⏳ Aguardando a interface do GED carregar...")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(4000)

        print("🎯 Entrando no Iframe 'ci' e buscando botão 'Nova pasta'...")
        # AQUI ESTÁ A MÁGICA QUE VOCÊ DESCOBRIU!
        frame_alvo = page.frame_locator('iframe[name="ci"]')
        btn_nova_pasta = frame_alvo.get_by_role("button", name="Nova pasta")
        
        # Esperamos o botão existir dentro do iframe correto
        await btn_nova_pasta.wait_for(state="visible", timeout=10000)

        print("🤖 Movimento humano de clique...")
        await btn_nova_pasta.scroll_into_view_if_needed()
        await page.wait_for_timeout(1000)
        await btn_nova_pasta.hover()
        await page.wait_for_timeout(500)
        await btn_nova_pasta.click()

        print("✍️ Digitando 'Universidade Corporativa'...")
        await page.wait_for_timeout(1500) 
        
        # O campo de texto para o nome da pasta também está dentro desse iframe
        input_nome_pasta = frame_alvo.locator("input[type='text']:visible").first
        await input_nome_pasta.wait_for(state="visible")
        
        await page.wait_for_timeout(500)
        await input_nome_pasta.fill("Universidade Corporativa")

        print("💾 Salvando a pasta (Apertando ENTER)...")
        await page.wait_for_timeout(1000)
        await input_nome_pasta.press("Enter")

        print("✅ Operação concluída! O robô dominou o GED.")
        await page.pause()

if __name__ == "__main__":
    asyncio.run(main())
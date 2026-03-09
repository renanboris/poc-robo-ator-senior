import asyncio
import os
import re
import urllib.parse
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# Criação da Estrutura Oficial do SCORM
BASE_DIR = "clone_scorm"
FONTS_DIR = os.path.join(BASE_DIR, "assets", "fonts")
IMG_DIR = os.path.join(BASE_DIR, "assets", "images")

os.makedirs(FONTS_DIR, exist_ok=True)
os.makedirs(IMG_DIR, exist_ok=True)

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

        print("🕵️ Iniciando o Interceptador de SCORM (Baixando Fontes e Imagens)...")
        css_cache = []

        # A MÁGICA DO DOWNLOAD FÍSICO: Salva tudo no seu HD em tempo real
        async def intercept_response(response):
            if response.status >= 300: return # Ignora erros e redirecionamentos
            
            req_type = response.request.resource_type
            url = response.url
            
            if url.startswith("data:"): return # Ignora imagens embutidas nativamente
            
            # Limpa a URL (remove coisas como ?v=1.0) para pegar o nome real do arquivo
            filename = os.path.basename(urllib.parse.urlparse(url).path)
            if not filename: return
            
            try:
                if req_type == "stylesheet":
                    text = await response.text()
                    css_cache.append(text)
                
                elif req_type == "font":
                    body = await response.body() # Pega os bytes do arquivo .woff/.ttf
                    filepath = os.path.join(FONTS_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(body)
                    print(f"📥 Fonte salva: {filename}")
                
                elif req_type == "image":
                    body = await response.body() # Pega os bytes do .png/.svg
                    filepath = os.path.join(IMG_DIR, filename)
                    with open(filepath, "wb") as f:
                        f.write(body)
            except Exception:
                pass 

        page.on("response", intercept_response)

        print("🚀 Acessando o portal da Senior...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        
        await page.wait_for_timeout(2000)
        await page.keyboard.press("Escape")

        print("📝 Realizando Login...")
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

        print("📂 Navegando: Menu Senior Flow -> GED -> Documentos...")
        menu_senior_flow = page.locator("[id='menu-label-Senior Flow']").locator("..")
        await menu_senior_flow.scroll_into_view_if_needed()
        await menu_senior_flow.click()
        await page.wait_for_timeout(1000)
        
        menu_ged = page.locator("span", has_text="GED").first.locator("..")
        await menu_ged.scroll_into_view_if_needed()
        await menu_ged.click()
        await page.wait_for_timeout(1000)

        menu_documentos = page.locator("span", has_text="Documentos").first.locator("..")
        await menu_documentos.scroll_into_view_if_needed()
        await menu_documentos.click()

        print("⏳ Aguardando a interface do GED (Iframe) carregar...")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(4000)

        frame_alvo = page.frame_locator('iframe[name="ci"]')
        btn_nova_pasta = frame_alvo.get_by_role("button", name="Nova pasta")
        await btn_nova_pasta.wait_for(state="visible", timeout=15000)
        await page.wait_for_timeout(2000) 

        print("🔧 Tratando a fusão do Iframe com a Página Pai...")

        js_merge = """() => {
            document.querySelectorAll('link[rel="stylesheet"]').forEach(el => el.remove());
            document.querySelectorAll('script').forEach(el => el.remove());
            document.querySelectorAll('base').forEach(el => el.remove()); // Destrói o Base do Angular

            const iframe = document.querySelector('iframe[name="ci"]');
            if (iframe && iframe.contentDocument) {
                iframe.contentDocument.querySelectorAll('style').forEach(s => {
                    document.head.appendChild(s.cloneNode(true));
                });

                const div = document.createElement('div');
                div.innerHTML = iframe.contentDocument.body.innerHTML;
                div.style.width = '100%';
                div.style.height = '100vh';
                div.style.overflow = 'auto';
                div.style.backgroundColor = '#fff';
                iframe.parentNode.replaceChild(div, iframe);
            }
        }"""
        
        await page.evaluate(js_merge)
        html_final = await page.content()

        print("🧬 Traduzindo o CSS para apontar para a nossa pasta Assets local...")
        
        def fix_css_url(match):
            full_url = match.group(1).strip("'\" ")
            if full_url.startswith("data:"): return match.group(0)
            
            filename = os.path.basename(urllib.parse.urlparse(full_url).path)
            # Se for fonte, aponta para nossa pasta local de fontes
            if filename.endswith(('.woff', '.woff2', '.ttf', '.eot')):
                return f"url('./assets/fonts/{filename}')"
            # Se for imagem, aponta para imagens
            elif filename.endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                return f"url('./assets/images/{filename}')"
            return match.group(0)

        final_css = ""
        for css in css_cache:
            fixed_css = re.sub(r'url\(([^)]+)\)', fix_css_url, css)
            final_css += fixed_css + "\n"

        bloco_style = f"<style>\n{final_css}\n</style>"
        html_final = html_final.replace("</head>", f"{bloco_style}\n</head>")

        print("🖼️ Corrigindo imagens nas tags HTML...")
        def fix_html_img(match):
            attr = match.group(1)
            full_url = match.group(2)
            if full_url.startswith("data:"): return match.group(0)
            filename = os.path.basename(urllib.parse.urlparse(full_url).path)
            return f'{attr}="./assets/images/{filename}"'
            
        html_final = re.sub(r'(src|ng-src)=["\']([^"\']+)["\']', fix_html_img, html_final)

        print("💾 Salvando o index.html definitivo no diretório SCORM...")
        index_path = os.path.join(BASE_DIR, "index.html")
        with open(index_path, "w", encoding="utf-8") as arquivo:
            arquivo.write(html_final)
            
        print(f"✅ PACOTE SCORM GERADO COM SUCESSO na pasta '{BASE_DIR}'!")
        await page.wait_for_timeout(1000)

if __name__ == "__main__":
    asyncio.run(main())
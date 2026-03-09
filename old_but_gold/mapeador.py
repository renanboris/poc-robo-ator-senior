import asyncio
import os
import json
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ==============================================================
# 👁️ O VASCULHADOR DE DOM (UI EXPLORER) - COM GATILHO 'ALT' E ENCERRAMENTO SEGURO
# ==============================================================

async def injetar_radar(page):
    """Injeta o radar, mas ele só age se a tecla ALT estiver pressionada."""
    script_radar = """() => {
        if (window.__radarInjetado) return;
        window.__radarInjetado = true;

        // Efeito de Hover - Só acende se segurar ALT
        document.addEventListener('mouseover', (e) => {
            if (e.altKey) {
                e.target.setAttribute('data-original-outline', e.target.style.outline || '');
                e.target.setAttribute('data-original-bg', e.target.style.backgroundColor || '');
                e.target.style.outline = '3px solid #ff0055';
                e.target.style.backgroundColor = 'rgba(255, 0, 85, 0.15)';
            }
        }, true);

        // Remove o efeito ao sair ou ao soltar a tecla
        document.addEventListener('mouseout', (e) => {
            if (e.target.hasAttribute('data-original-outline')) {
                e.target.style.outline = e.target.getAttribute('data-original-outline');
                e.target.style.backgroundColor = e.target.getAttribute('data-original-bg');
            }
        }, true);

        // Captura o Clique APENAS se o ALT estiver pressionado
        document.addEventListener('click', (e) => {
            if (e.altKey) {
                e.preventDefault(); // Impede o clique real (não abre links)
                e.stopPropagation(); // Impede que o clique vaze para o sistema

                const el = e.target;
                
                let tag = el.tagName.toLowerCase();
                let texto = el.innerText ? el.innerText.trim().replace(/\\n/g, ' ') : '';
                let placeholder = el.placeholder ? el.placeholder : '';
                let role = el.getAttribute('role') || '';
                let id = el.id || '';

                // Se for um ícone, tenta pegar a intenção do pai
                if ((tag === 'svg' || tag === 'i' || tag === 'path') && !texto) {
                    const pai = el.closest('button, a, div');
                    if (pai && pai.innerText) {
                        texto = pai.innerText.trim().replace(/\\n/g, ' ');
                        tag = 'ícone_dentro_de_' + pai.tagName.toLowerCase();
                    }
                }

                let iframeNome = window.name || 'Página Principal';

                const relatorio = {
                    tag: tag,
                    texto_encontrado: texto,
                    placeholder: placeholder,
                    role: role,
                    id_html: id,
                    iframe: iframeNome
                };

                window.capturarElemento(JSON.stringify(relatorio));
                
                // Pisca a tela para dar feedback visual que capturou
                const originalBg = e.target.style.backgroundColor;
                e.target.style.backgroundColor = '#00ff00';
                setTimeout(() => e.target.style.backgroundColor = originalBg, 300);
            }
        }, true);
    }"""
    
    try:
        await page.evaluate(script_radar)
        for frame in page.frames:
            try:
                await frame.evaluate(script_radar)
            except:
                pass
    except Exception:
        pass # Ignora erros se a página estiver a fechar

async def main():
    usuario = os.getenv("SENIOR_USER")
    senha = os.getenv("SENIOR_PASS")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--start-maximized'])
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        async def on_capturar_elemento(dados_json):
            dados = json.loads(dados_json)
            print("\n" + "🟢 "*10)
            print("🎯 ELEMENTO CAPTURADO!")
            print(f"👉 Localização: {dados['iframe']}")
            print(f"👉 Tag HTML:    {dados['tag']}")
            
            if dados['id_html']:
                print(f"👉 ID:          '{dados['id_html']}'")
            if dados['texto_encontrado']:
                print(f"👉 Texto:       '{dados['texto_encontrado'][:50]}...'")
            if dados['placeholder']:
                print(f"👉 Placeholder: '{dados['placeholder']}'")
            if dados['role']:
                print(f"👉 Role:        '{dados['role']}'")
            
            print("\n💡 Copie isto para o seu roteiro.json (alvo_semantico):")
            sugestao = "{\n"
            if dados['iframe'] != 'Página Principal':
                sugestao += f'  "dentro_do_iframe": "{dados["iframe"]}",\n'
            
            # Hierarquia de força do seletor:
            if dados['id_html']:
                sugestao += f'  "seletor": "#{dados["id_html"]}",\n'
                sugestao += f'  "primeiro": true,\n'
                sugestao += f'  "pegar_pai": true\n'
            elif dados['placeholder']:
                sugestao += f'  "placeholder": "{dados["placeholder"]}",\n'
                sugestao += f'  "primeiro": true,\n'
                sugestao += f'  "pegar_pai": true\n'
            elif dados['role']:
                sugestao += f'  "role": "{dados["role"]}",\n'
                if dados['texto_encontrado']:
                    sugestao += f'  "nome": "{dados["texto_encontrado"]}",\n'
                sugestao += f'  "primeiro": true\n'
            elif dados['texto_encontrado']:
                sugestao += f'  "texto_contem": "{dados["texto_encontrado"]}",\n'
                sugestao += f'  "pegar_pai": true,\n'
                sugestao += f'  "primeiro": true\n'
            else:
                sugestao += f'  "seletor": "{dados["tag"]}",\n'
                sugestao += f'  "primeiro": true\n'
                
            sugestao += "}"
            print(sugestao)
            print("🟢 "*10 + "\n")

        await context.expose_binding("capturarElemento", lambda source, args: asyncio.create_task(on_capturar_elemento(args)))

        print("🔄 Realizando Login para o Modo de Mapeamento...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        await asyncio.sleep(2)
        await page.keyboard.press("Escape")
        await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
        await page.get_by_role("button", name="Próximo").click()
        await asyncio.sleep(0.5)
        await page.keyboard.press("Escape")
        senha_input = page.locator("input[type='password']")
        await senha_input.wait_for(state="visible")
        await senha_input.fill(senha)
        await asyncio.sleep(0.5)
        await senha_input.press("Enter")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(7) 
        
        print("\n" + "🚀"*15)
        print("MODO VASCULHADOR ATIVADO!")
        print("1. Navegue normalmente com o mouse pelo sistema.")
        print("2. Para mapear um elemento, SEGURE A TECLA 'ALT' e clique nele.")
        print("3. O elemento piscará verde e o código aparecerá aqui no terminal!")
        print("🚀"*15 + "\n")

        try:
            while True:
                if page.is_closed():
                    break
                await injetar_radar(page)
                await asyncio.sleep(2)
        except Exception:
            pass # Fecha de forma elegante e limpa
            
        print("\n🛑 Navegador fechado. Vasculhador encerrado com segurança. Até logo!\n")

if __name__ == "__main__":
    asyncio.run(main())
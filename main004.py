import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ==============================================================
# 🚀 MOTOR VISUAL BLAZE CODE - MODO INTERATIVO (HAND-HOLDING)
# ==============================================================
async def limpar_tour(page):
    """Limpeza global de segurança. Não usa locator para evitar erros de SPA."""
    script_limpeza = """() => {
        document.querySelectorAll('#blaze-animations, .blaze-ui-layer').forEach(e => e.remove());
    }"""
    try:
        # Tenta limpar na página principal
        await page.evaluate(script_limpeza)
        # E garante a limpeza varrendo todos os iframes ativos
        for frame in page.frames:
            try:
                await frame.evaluate(script_limpeza)
            except:
                pass
    except:
        pass


async def tour_interativo(page, locator, titulo, descricao, acao_esperada="clique", cor_tema="#2596be"):
    """
    Cria a cortina de foco e PAUSA O SCRIPT até o humano agir.
    """
    print(f"🎬 [Blaze Tour] Aguardando humano em: {titulo}...")
    
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    await asyncio.sleep(0.5) 
    
    # Injetamos a UI e a Lógica de Resolução Direto no JS
    await locator.evaluate(f"""(el, args) => {{
        return new Promise((resolve) => {{
            const [titulo, descricao, corTema, acaoEsperada] = args;
            
            // Limpeza de resquícios
            document.querySelectorAll('#blaze-animations, .blaze-ui-layer').forEach(e => e.remove());
            
            const style = document.createElement('style');
            style.id = 'blaze-animations';
            style.innerHTML = `
                @keyframes blazePulse {{
                    0% {{ box-shadow: 0 0 0 9999px rgba(0,0,0,0.75), 0 0 10px ${{corTema}}; }}
                    50% {{ box-shadow: 0 0 0 9999px rgba(0,0,0,0.75), 0 0 30px ${{corTema}}, inset 0 0 15px ${{corTema}}; }}
                    100% {{ box-shadow: 0 0 0 9999px rgba(0,0,0,0.75), 0 0 10px ${{corTema}}; }}
                }}
            `;
            document.head.appendChild(style);

            const rect = el.getBoundingClientRect();
            
            const focusRing = document.createElement('div');
            focusRing.className = 'blaze-ui-layer';
            focusRing.style.position = 'fixed';
            focusRing.style.top = (rect.top - 6) + 'px';
            focusRing.style.left = (rect.left - 6) + 'px';
            focusRing.style.width = (rect.width + 12) + 'px';
            focusRing.style.height = (rect.height + 12) + 'px';
            focusRing.style.borderRadius = '8px';
            focusRing.style.border = `2px solid ${{corTema}}`;
            focusRing.style.zIndex = '99998';
            focusRing.style.pointerEvents = 'none'; 
            focusRing.style.animation = 'blazePulse 2s infinite ease-in-out';

            let msgAcao = acaoEsperada === 'clique' ? '👆 Clique no item destacado para continuar' : '⌨️ Digite o texto e aperte ENTER';

            const tooltip = document.createElement('div');
            tooltip.className = 'blaze-ui-layer';
            tooltip.style.position = 'fixed';
            tooltip.style.zIndex = '99999';
            tooltip.style.background = '#1e1e1e';
            tooltip.style.color = '#ffffff';
            tooltip.style.padding = '18px 22px';
            tooltip.style.borderRadius = '10px';
            tooltip.style.borderLeft = `6px solid ${{corTema}}`;
            tooltip.style.fontFamily = 'Segoe UI, Roboto, sans-serif';
            tooltip.style.boxShadow = '0 12px 35px rgba(0,0,0,0.85)';
            tooltip.style.maxWidth = '340px';
            
            tooltip.innerHTML = `
                <div style="font-weight: 700; font-size: 16px; margin-bottom: 8px; color: ${{corTema}};">
                    ✨ ${{titulo}}
                </div>
                <div style="font-size: 14.5px; line-height: 1.6; color: #e2e8f0; margin-bottom: 12px;">
                    ${{descricao}}
                </div>
                <div style="font-size: 12px; font-weight: bold; color: #fff; background: ${{corTema}}; display: inline-block; padding: 6px 12px; border-radius: 4px;">
                    ${{msgAcao}}
                </div>
            `;

            tooltip.style.visibility = 'hidden';
            document.body.appendChild(focusRing);
            document.body.appendChild(tooltip);

            const tooltipRect = tooltip.getBoundingClientRect();
            tooltip.style.visibility = 'visible';

            let topPos = rect.bottom + 25; 
            let leftPos = rect.left;

            if (topPos + tooltipRect.height > window.innerHeight) {{ 
                topPos = rect.top - tooltipRect.height - 25; 
            }}
            if (leftPos + tooltipRect.width > window.innerWidth) {{
                leftPos = window.innerWidth - tooltipRect.width - 25;
            }}
            
            tooltip.style.top = topPos + 'px';
            tooltip.style.left = Math.max(20, leftPos) + 'px';
            
            tooltip.style.opacity = '0';
            tooltip.style.transform = 'translateY(10px)';
            tooltip.style.transition = 'all 0.4s ease';

            setTimeout(() => {{
                tooltip.style.opacity = '1';
                tooltip.style.transform = 'translateY(0)';
            }}, 50);

            // ==========================================
            // LÓGICA DE INTERAÇÃO (ESCUTA GLOBAL)
            // ==========================================
            // Chaves duplas aqui para o Python ignorar e passar o JS correto!
            const cleanupUI = () => {{
                if(focusRing) focusRing.remove();
                if(tooltip) tooltip.remove();
                if(style) style.remove();
            }};

            if (acaoEsperada === 'clique') {{
                const onClick = (e) => {{
                    el.removeEventListener('click', onClick);
                    cleanupUI(); 
                    resolve(); 
                }};
                el.addEventListener('click', onClick);
            }} else if (acaoEsperada === 'enter') {{
                // 🚀 ESCUTA GLOBAL: Não importa onde o foco esteja no Iframe, se bater Enter, avança.
                const onKey = (e) => {{
                    if (e.key === 'Enter') {{
                        document.removeEventListener('keydown', onKey);
                        cleanupUI(); // Destrói o balão instantaneamente
                        resolve(); 
                    }}
                }};
                document.addEventListener('keydown', onKey);
            }}
        }}); 
    }}""", [titulo, descricao, cor_tema, acao_esperada])

    await limpar_tour(page)
    print(f"✅ Humano interagiu com: {titulo}")


async def exibir_sucesso_interativo(page):
    """Exibe um modal de sucesso com resiliência a recarregamentos de página (SPA)."""
    print("⏳ Aguardando a plataforma processar a última ação...")
    
    await asyncio.sleep(2.5) 
    
    print("🎉 Injetando tela de sucesso final...")
    
    for tentativa in range(3):
        try:
            await page.evaluate("""() => {
                return new Promise((resolve) => {
                    const finalDiv = document.createElement('div');
                    finalDiv.id = 'blaze-success-modal';
                    finalDiv.style = `
                        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                        background: rgba(37, 150, 190, 0.2); padding: 40px; border-radius: 12px;
                        border: 2px solid #2596be; backdrop-filter: blur(15px);
                        color: #fff; font-family: sans-serif; text-align: center; z-index: 999999;
                        box-shadow: 0 0 50px rgba(37, 150, 190, 0.4);
                        cursor: pointer; transition: transform 0.2s ease;
                    `;
                    
                    finalDiv.onmouseover = () => finalDiv.style.transform = 'translate(-50%, -50%) scale(1.02)';
                    finalDiv.onmouseout = () => finalDiv.style.transform = 'translate(-50%, -50%) scale(1)';

                    finalDiv.innerHTML = `
                        <h1 style="margin:0 0 15px 0; color:#2596be; font-size: 28px;">🎉 Treinamento Concluído!</h1>
                        <p style="margin:0 0 25px 0; font-size:18px; color: #e2e8f0;">A estrutura foi criada. Parabéns pelo avanço!</p>
                        <div style="font-size: 14px; font-weight: bold; color: #fff; background: #2596be; display: inline-block; padding: 10px 20px; border-radius: 6px; box-shadow: 0 4px 15px rgba(0,0,0,0.3);">
                            👆 Clique aqui ou aperte ENTER para encerrar
                        </div>
                    `;
                    document.body.appendChild(finalDiv);

                    const encerrarTour = (e) => {
                        if (e.type === 'click' || (e.type === 'keydown' && e.key === 'Enter')) {
                            finalDiv.remove();
                            document.removeEventListener('keydown', encerrarTour);
                            resolve();
                        }
                    };

                    finalDiv.addEventListener('click', encerrarTour);
                    document.addEventListener('keydown', encerrarTour);
                });
            }""")
            print("🏁 Treinamento finalizado com sucesso. Encerrando navegador...")
            return 
            
        except Exception as e:
            print(f"⚠️ Página ainda carregando, tentando novamente em instantes... ({tentativa + 1}/3)")
            await asyncio.sleep(1.5)


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

        print("🚀 Automatizando Login (O Tour começa depois)...")
        await page.goto("https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
        
        await page.wait_for_timeout(2000)
        await page.keyboard.press("Escape")

        await page.get_by_placeholder("usuario@dominio.com.br").fill(usuario)
        await page.get_by_role("button", name="Próximo").click()
        senha_input = page.locator("input[type='password']")
        await senha_input.wait_for(state="visible")
        await senha_input.fill(senha)
        await page.wait_for_timeout(500)
        await senha_input.press("Enter")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(7000) 
        await page.keyboard.press("Escape")

        print("\n🎬 --- INICIANDO O TOUR INTERATIVO --- 🎬\n")
        
        menu_senior_flow = page.locator("[id='menu-label-Senior Flow']").locator("..")
        await tour_interativo(
            page, 
            menu_senior_flow, 
            "Módulo de Processos", 
            "Para começar, você precisa acessar o Senior Flow. É por ele que gerenciamos as aprovações.",
            acao_esperada="clique"
        )

        await page.wait_for_timeout(1000)
        menu_ged = page.locator("span", has_text="GED").first.locator("..")
        await tour_interativo(
            page, 
            menu_ged, 
            "Gestão Eletrônica", 
            "Excelente. Agora, abra o GED para acessarmos o repositório de arquivos.",
            acao_esperada="clique"
        )

        await page.wait_for_timeout(1000)
        menu_documentos = page.locator("span", has_text="Documentos").first.locator("..")
        await tour_interativo(
            page, 
            menu_documentos, 
            "Área de Documentos", 
            "Entre na área de Documentos principais.",
            acao_esperada="clique"
        )

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(4000)

        frame_alvo = page.frame_locator('iframe[name="ci"]')
        btn_nova_pasta = frame_alvo.get_by_role("button", name="Nova pasta")
        await btn_nova_pasta.wait_for(state="visible", timeout=10000)
        
        await tour_interativo(
            page, 
            btn_nova_pasta, 
            "Criando Estrutura", 
            "Vamos criar o diretório base para os materiais. Clique em 'Nova pasta'.",
            acao_esperada="clique"
        )

        nome_pasta_gerada = frame_alvo.get_by_role("heading", name="Nova pasta").first
        await nome_pasta_gerada.wait_for(state="visible", timeout=10000)
        
        await tour_interativo(
            page, 
            nome_pasta_gerada, 
            "Nomeando a Pasta", 
            "Apague o nome atual, digite a nomenclatura desejada e aperte a tecla ENTER para confirmar.",
            acao_esperada="enter"
        )

        await asyncio.sleep(1.0)
        
        await exibir_sucesso_interativo(page)

if __name__ == "__main__":
    asyncio.run(main())
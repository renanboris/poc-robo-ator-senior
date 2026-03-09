import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ==============================================================
# 🚀 MOTOR VISUAL BLAZE CODE - MODO INTERATIVO (HAND-HOLDING)
# ==============================================================
async def limpar_tour(page):
    """Limpeza global de segurança."""
    script_limpeza = """() => {
        document.querySelectorAll('#blaze-animations, .blaze-ui-layer, #blaze-error-toast').forEach(e => e.remove());
    }"""
    try:
        await page.evaluate(script_limpeza)
        for frame in page.frames:
            try:
                await frame.evaluate(script_limpeza)
            except:
                pass
    except:
        pass


async def tour_interativo(page, locator, titulo, descricao, acao_esperada="clique", cor_tema="#2596be"):
    """
    Cria a cortina de foco, BLOQUEIA cliques/scroll externos e PAUSA O SCRIPT até o humano agir.
    """
    print(f"🎬 [Blaze Tour] Aguardando humano em: {titulo}...")
    
    # Rola para o elemento antes de travar o scroll
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    await asyncio.sleep(0.5) 
    
    await locator.evaluate(f"""(el, args) => {{
        return new Promise((resolve) => {{
            const [titulo, descricao, corTema, acaoEsperada] = args;
            
            document.querySelectorAll('#blaze-animations, .blaze-ui-layer, #blaze-error-toast').forEach(e => e.remove());
            
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
            // 🛡️ ESCUDO 1: SISTEMA DE BLOQUEIO DE CLIQUES
            // ==========================================
            const showError = (msg) => {{
                let existing = document.getElementById('blaze-error-toast');
                if (existing) existing.remove();

                const toast = document.createElement('div');
                toast.id = 'blaze-error-toast';
                toast.style = `
                    position: fixed; bottom: 30px; right: 30px;
                    background: #ef4444; color: #fff; padding: 16px 24px;
                    border-radius: 8px; font-family: 'Segoe UI', sans-serif; font-weight: bold;
                    box-shadow: 0 10px 25px rgba(239, 68, 68, 0.4);
                    z-index: 9999999; border-left: 6px solid #b91c1c;
                    opacity: 0; transform: translateX(50px);
                    transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                    display: flex; align-items: center; gap: 12px;
                `;
                toast.innerHTML = `<span style="font-size: 22px;">🛑</span> <span>${{msg}}</span>`;
                document.body.appendChild(toast);

                setTimeout(() => {{
                    toast.style.opacity = '1';
                    toast.style.transform = 'translateX(0)';
                }}, 10);

                setTimeout(() => {{
                    toast.style.opacity = '0';
                    toast.style.transform = 'translateX(50px)';
                    setTimeout(() => toast.remove(), 300);
                }}, 3500);
            }};

            const blockOutsideClicks = (e) => {{
                const ringRect = focusRing.getBoundingClientRect();
                const isInside = e.clientX >= (ringRect.left - 5) && 
                                 e.clientX <= (ringRect.right + 5) && 
                                 e.clientY >= (ringRect.top - 5) && 
                                 e.clientY <= (ringRect.bottom + 5);

                const isTooltip = tooltip.contains(e.target);
                const isErrorToast = document.getElementById('blaze-error-toast')?.contains(e.target);

                if (!isInside && !isTooltip && !isErrorToast) {{
                    e.preventDefault();
                    e.stopPropagation();
                    showError("Ação bloqueada! Interaja apenas com o item destacado.");
                }}
            }};

            // ==========================================
            // 🛡️ ESCUDO 2: SISTEMA DE BLOQUEIO DE SCROLL
            // ==========================================
            const preventScroll = (e) => {{
                e.preventDefault();
                e.stopPropagation();
            }};

            const preventKeyScroll = (e) => {{
                // Bloqueia teclas que causam scroll, mas deixa o Enter e Tab livres
                const keysToBlock = ['Space', 'ArrowUp', 'ArrowDown', 'PageUp', 'PageDown', 'Home', 'End'];
                if (keysToBlock.includes(e.code)) {{
                    e.preventDefault();
                }}
            }};

            // Aplica os bloqueadores de scroll no documento inteiro (com passive: false para permitir preventDefault)
            window.addEventListener('wheel', preventScroll, {{ passive: false }});
            window.addEventListener('touchmove', preventScroll, {{ passive: false }});
            window.addEventListener('keydown', preventKeyScroll, {{ passive: false }});
            
            document.addEventListener('click', blockOutsideClicks, true);

            // ==========================================
            // LÓGICA DE INTERAÇÃO E AVANÇO
            // ==========================================
            const cleanupUI = () => {{
                // Remove todos os escudos
                document.removeEventListener('click', blockOutsideClicks, true);
                window.removeEventListener('wheel', preventScroll);
                window.removeEventListener('touchmove', preventScroll);
                window.removeEventListener('keydown', preventKeyScroll);
                
                if(focusRing) focusRing.remove();
                if(tooltip) tooltip.remove();
                if(style) style.remove();
                let err = document.getElementById('blaze-error-toast');
                if(err) err.remove();
            }};

            if (acaoEsperada === 'clique') {{
                const onClick = (e) => {{
                    el.removeEventListener('click', onClick);
                    cleanupUI(); 
                    resolve(); 
                }};
                el.addEventListener('click', onClick);
            }} else if (acaoEsperada === 'enter') {{
                const onKey = (e) => {{
                    if (e.key === 'Enter') {{
                        document.removeEventListener('keydown', onKey);
                        cleanupUI(); 
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
    """Exibe um modal CLEAN com entrada em Cascata (Lottie -> Texto -> Botão)."""
    print("⏳ Aguardando a plataforma processar a última ação...")
    await asyncio.sleep(0.8) 
    print("🎉 Injetando tela de sucesso final com animação Cascata...")
    
    for tentativa in range(3):
        try:
            await page.evaluate("""() => {
                return new Promise((resolve) => {
                    
                    if (!document.querySelector('script[src*="lottie-player"]')) {
                        const script = document.createElement('script');
                        script.src = 'https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js';
                        document.head.appendChild(script);
                    }

                    const style = document.createElement('style');
                    style.innerHTML = `
                        @keyframes cascadeFadeIn {
                            from { opacity: 0; transform: translateY(20px); }
                            to { opacity: 1; transform: translateY(0); }
                        }
                        .blaze-cascade-1 { opacity: 0; animation: cascadeFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
                        .blaze-cascade-2 { opacity: 0; animation: cascadeFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; animation-delay: 0.8s; }
                        .blaze-cascade-3 { opacity: 0; animation: cascadeFadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards; animation-delay: 1.5s; }
                    `;
                    document.head.appendChild(style);

                    const overlay = document.createElement('div');
                    overlay.id = 'blaze-success-overlay';
                    overlay.style = `
                        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
                        background: rgba(0, 0, 0, 0.75); backdrop-filter: blur(8px);
                        display: flex; flex-direction: column; align-items: center; justify-content: center;
                        z-index: 999999; cursor: pointer;
                        opacity: 0; transition: opacity 0.5s ease;
                    `;

                    overlay.innerHTML = `
                        <div class="blaze-cascade-1">
                            <lottie-player 
                                src="https://lottie.host/76846e87-566d-49b8-b3d0-90a6290d22ec/5sys94coTA.json" 
                                background="transparent" 
                                speed="1" 
                                style="width: 250px; height: 250px;" 
                                autoplay>
                            </lottie-player>
                        </div>

                        <h1 class="blaze-cascade-2" style="margin: -20px 0 40px 0; color: #ffffff; font-size: 36px; font-family: sans-serif; font-weight: bold; text-shadow: 0 4px 15px rgba(0,0,0,0.5);">
                            Treinamento Concluído!
                        </h1>

                        <div id="blaze-btn-encerra" class="blaze-cascade-3" style="font-size: 16px; font-family: sans-serif; font-weight: bold; color: #fff; background: #2596be; padding: 14px 28px; border-radius: 8px; box-shadow: 0 8px 25px rgba(37, 150, 190, 0.4); transition: transform 0.2s ease;">
                            👆 Clique aqui ou aperte ENTER para encerrar
                        </div>
                    `;
                    
                    document.body.appendChild(overlay);

                    const btn = document.getElementById('blaze-btn-encerra');
                    btn.onmouseover = () => btn.style.transform = 'scale(1.05)';
                    btn.onmouseout = () => btn.style.transform = 'scale(1)';

                    setTimeout(() => overlay.style.opacity = '1', 50);

                    const encerrarTour = (e) => {
                        if (e.type === 'click' || (e.type === 'keydown' && e.key === 'Enter')) {
                            overlay.style.opacity = '0';
                            setTimeout(() => {
                                overlay.remove();
                                style.remove();
                                document.removeEventListener('keydown', encerrarTour);
                                resolve();
                            }, 400); 
                        }
                    };

                    overlay.addEventListener('click', encerrarTour);
                    document.addEventListener('keydown', encerrarTour);
                });
            }""")
            print("🏁 Treinamento finalizado com sucesso. Encerrando navegador...")
            return 
            
        except Exception as e:
            print(f"⚠️ Página ainda carregando, tentando novamente em instantes... ({tentativa + 1}/3)")
            await asyncio.sleep(1.0)


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
        
        await page.wait_for_timeout(500)
        await page.keyboard.press("Escape")

        senha_input = page.locator("input[type='password']")
        await senha_input.wait_for(state="visible")
        await senha_input.fill(senha)
        await page.wait_for_timeout(500)
        await senha_input.press("Enter")

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(7000) 
        
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(300)
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

        await exibir_sucesso_interativo(page)

if __name__ == "__main__":
    asyncio.run(main())
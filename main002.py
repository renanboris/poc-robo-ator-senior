import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

# ==============================================================
# 🚀 MOTOR VISUAL BLAZE CODE (AJUSTE FINO DE UI)
# ==============================================================
async def limpar_tour(page, locator=None):
    """Remove os elementos visuais da tela/iframe atual."""
    script_limpeza = """() => {
        document.querySelectorAll('.blaze-ui-layer').forEach(e => e.remove());
    }"""
    if locator:
        await locator.evaluate(script_limpeza)
    else:
        await page.evaluate(script_limpeza)

async def tour_premium(page, locator, titulo, descricao, cor_tema="#00ff00", tempo_leitura=5.5):
    """
    Cria a experiência 'Foco Total'.
    (Tempo de leitura aumentado para melhor didática)
    """
    print(f"🎬 [Blaze Tour] Guiando para: {titulo}...")
    
    await locator.scroll_into_view_if_needed()
    await locator.hover()
    await asyncio.sleep(0.5)
    
    # Injeção de UI com cálculo dinâmico de colisão
    await locator.evaluate(f"""(el, args) => {{
        const [titulo, descricao, corTema] = args;
        
        document.querySelectorAll('.blaze-ui-layer').forEach(e => e.remove());
        const rect = el.getBoundingClientRect();
        
        // 1. CORTINA ESCURA (FOCUS RING)
        const focusRing = document.createElement('div');
        focusRing.className = 'blaze-ui-layer';
        focusRing.style.position = 'fixed';
        focusRing.style.top = (rect.top - 6) + 'px';
        focusRing.style.left = (rect.left - 6) + 'px';
        focusRing.style.width = (rect.width + 12) + 'px';
        focusRing.style.height = (rect.height + 12) + 'px';
        focusRing.style.borderRadius = '8px';
        focusRing.style.boxShadow = `0 0 0 9999px rgba(0,0,0,0.75), 0 0 25px ${{corTema}}`;
        focusRing.style.border = `2px solid ${{corTema}}`;
        focusRing.style.zIndex = '99998';
        focusRing.style.pointerEvents = 'none'; 
        focusRing.style.transition = 'all 0.3s ease';

        // 2. PAINEL DE INSTRUÇÕES (TOOLTIP)
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
            <div style="font-size: 14.5px; line-height: 1.6; color: #e2e8f0;">
                ${{descricao}}
            </div>
        `;

        // Renderiza invisível para medir o tamanho real do balão
        tooltip.style.visibility = 'hidden';
        document.body.appendChild(focusRing);
        document.body.appendChild(tooltip);

        const tooltipRect = tooltip.getBoundingClientRect();
        tooltip.style.visibility = 'visible';

        // LÓGICA ANTI-SOBREPOSIÇÃO: Decide dinamicamente onde colocar o balão
        let topPos = rect.bottom + 25; // Tenta por baixo com boa margem
        let leftPos = rect.left;

        // Se bater no fundo da tela, joga para CIMA do botão
        if (topPos + tooltipRect.height > window.innerHeight) {{ 
            topPos = rect.top - tooltipRect.height - 25; 
        }}
        
        // Se bater na lateral direita da tela, puxa para a esquerda
        if (leftPos + tooltipRect.width > window.innerWidth) {{
            leftPos = window.innerWidth - tooltipRect.width - 25;
        }}
        
        tooltip.style.top = topPos + 'px';
        tooltip.style.left = Math.max(20, leftPos) + 'px'; // Evita vazar na esquerda
        
        // Animação de entrada
        tooltip.style.opacity = '0';
        tooltip.style.transform = 'translateY(10px)';
        tooltip.style.transition = 'all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)';

        setTimeout(() => {{
            tooltip.style.opacity = '1';
            tooltip.style.transform = 'translateY(0)';
        }}, 50);

    }}""", [titulo, descricao, cor_tema])

    await asyncio.sleep(tempo_leitura)
    await limpar_tour(page, locator)
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

        # --- FLUXO DE LOGIN ---
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

        print("\n🎬 --- INICIANDO O TOUR GUIADO PREMIUM --- 🎬\n")
        
        # 1. Menu Senior Flow
        menu_senior_flow = page.locator("[id='menu-label-Senior Flow']").locator("..")
        await tour_premium(
            page, 
            menu_senior_flow, 
            "Módulo de Processos", 
            "Primeiro, vamos acessar o Senior Flow, que é o coração das aprovações e fluxos da plataforma.",
            cor_tema="#00ffcc"
        )

        # 2. Submenu GED
        await page.wait_for_timeout(1000)
        menu_ged = page.locator("span", has_text="GED").first.locator("..")
        await tour_premium(
            page, 
            menu_ged, 
            "Gestão Eletrônica", 
            "Dentro do Flow, encontramos o GED. É aqui que centralizamos todos os arquivos corporativos com segurança.",
            cor_tema="#a855f7"
        )

        # 3. Opção Documentos
        await page.wait_for_timeout(1000)
        menu_documentos = page.locator("span", has_text="Documentos").first.locator("..")
        await tour_premium(
            page, 
            menu_documentos, 
            "Área de Documentos", 
            "Clique em 'Documentos' para abrir o repositório principal de pastas.",
            cor_tema="#3b82f6"
        )

        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(4000)

        # 4. Botão Nova Pasta
        frame_alvo = page.frame_locator('iframe[name="ci"]')
        btn_nova_pasta = frame_alvo.get_by_role("button", name="Nova pasta")
        await btn_nova_pasta.wait_for(state="visible", timeout=10000)
        
        await tour_premium(
            page, 
            btn_nova_pasta, 
            "Criando Estrutura", 
            "Agora, vamos criar o diretório base para os materiais dos nossos alunos. Clique em 'Nova pasta'.",
            cor_tema="#f59e0b"
        )

        # 5. Renomeando a Pasta (COM LIMPEZA COMPLETA DO TEXTO)
        nome_pasta_gerada = frame_alvo.get_by_role("heading", name="Nova pasta").first
        await nome_pasta_gerada.wait_for(state="visible", timeout=10000)
        
        await tour_premium(
            page, 
            nome_pasta_gerada, 
            "Nomeando a Pasta", 
            "O sistema cria com o nome 'Nova pasta'. Vamos apagar tudo e digitar nossa nomenclatura padrão.",
            cor_tema="#ec4899",
            tempo_leitura=5.5
        )
        
        # Garante que o elemento está com foco para o teclado funcionar nele
        await nome_pasta_gerada.click()
        await page.wait_for_timeout(300)
        
        print("🧹 Selecionando e apagando o texto padrão...")
        await page.keyboard.press("Control+A") # Seleciona Tudo (No Mac, usar 'Meta+A' se der falha)
        await page.wait_for_timeout(200)
        await page.keyboard.press("Backspace") # Apaga a seleção inteira
        await page.wait_for_timeout(300)
        
        print("⌨️ Escrevendo o novo nome...")
        await page.keyboard.type("Universidade Corporativa - Turma A", delay=60)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Enter")

        print("✅ Tour finalizado com sucesso!")
        
        await page.evaluate("""() => {
            const finalDiv = document.createElement('div');
            finalDiv.style = `
                position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                background: rgba(0,255,100,0.15); padding: 40px; border-radius: 12px;
                border: 2px solid #00ff66; backdrop-filter: blur(10px);
                color: #fff; font-family: sans-serif; text-align: center; z-index: 999999;
                box-shadow: 0 0 50px rgba(0,255,100,0.2);
            `;
            finalDiv.innerHTML = `
                <h1 style="margin:0 0 10px 0; color:#00ff66;">🎉 Treinamento Concluído!</h1>
                <p style="margin:0; font-size:18px;">A estrutura da Universidade foi criada com sucesso.</p>
            `;
            document.body.appendChild(finalDiv);
        }""")
        
        await page.pause()

if __name__ == "__main__":
    asyncio.run(main())
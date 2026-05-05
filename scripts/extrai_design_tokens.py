"""
Extrai design tokens (CSS vars, cores, tipografia) do SmartPlayer ScaleUp.
Uso: python extrai_design_tokens.py
"""
import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

SMARTPLAYER_URLS = {
    "login":     "https://smartplayer.scaleup.com.br/smartplayer/auth/login",
    "conteudo":  "https://smartplayer.scaleup.com.br/smartplayer/conteudo",
    "dashboard": "https://smartplayer.scaleup.com.br/smartplayer/dashboard",
}

JS_EXTRATOR = """() => {
    const result = { variaveis: {}, cores: [], tipografia: {}, botao: null };

    // CSS custom properties do :root
    for (const sheet of document.styleSheets) {
        try {
            for (const rule of sheet.cssRules) {
                if (rule.selectorText === ':root') {
                    for (let i = 0; i < rule.style.length; i++) {
                        const p = rule.style[i];
                        if (p.startsWith('--'))
                            result.variaveis[p] = rule.style.getPropertyValue(p).trim();
                    }
                }
            }
        } catch(e) {} // ignora folhas cross-origin
    }

    // Cores computadas únicas (exclui transparente)
    const cores = new Set();
    document.querySelectorAll('*').forEach(el => {
        const s = getComputedStyle(el);
        ['color', 'background-color', 'border-color', 'outline-color'].forEach(prop => {
            const v = s.getPropertyValue(prop);
            if (v && v !== 'rgba(0, 0, 0, 0)' && v !== 'transparent') cores.add(v);
        });
    });
    result.cores = [...cores];

    // Tipografia por tag
    ['h1','h2','h3','h4','p','button','input','label','span','a'].forEach(tag => {
        const el = document.querySelector(tag);
        if (el) {
            const s = getComputedStyle(el);
            result.tipografia[tag] = {
                fontFamily:    s.fontFamily,
                fontSize:      s.fontSize,
                fontWeight:    s.fontWeight,
                lineHeight:    s.lineHeight,
                letterSpacing: s.letterSpacing,
            };
        }
    });

    // Estilo de botão primário
    const botao = document.querySelector('button');
    if (botao) {
        const s = getComputedStyle(botao);
        result.botao = {
            borderRadius: s.borderRadius,
            padding:      s.padding,
            fontSize:     s.fontSize,
            fontWeight:   s.fontWeight,
            background:   s.backgroundColor,
            color:        s.color,
        };
    }

    return result;
}"""


async def extrair_smartplayer(saida: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("Abrindo página de login do SmartPlayer...")
        await page.goto(SMARTPLAYER_URLS["login"])

        input("\n>> Faça login e aguarde a tela carregar. Pressione Enter quando estiver pronto.\n")

        resultado = {}

        for nome, url in SMARTPLAYER_URLS.items():
            if nome == "login":
                print(f"Extraindo tokens: {nome}")
                resultado[nome] = await page.evaluate(JS_EXTRATOR)
                continue

            print(f"Navegando para: {nome}")
            await page.goto(url)
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass  # continua mesmo se timeout
            resultado[nome] = await page.evaluate(JS_EXTRATOR)

        await browser.close()

    Path(saida).write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print()
    for nome, tokens in resultado.items():
        print(f"[{nome}] {len(tokens.get('variaveis', {}))} vars CSS | "
              f"{len(tokens.get('cores', []))} cores | "
              f"{len(tokens.get('tipografia', {}))} tags tipografia")

    print(f"\n✅ Salvo em: {saida}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extrai design tokens do SmartPlayer ScaleUp")
    parser.add_argument("--saida", default="smartplayer_tokens.json", help="Arquivo de saída JSON")
    args = parser.parse_args()

    asyncio.run(extrair_smartplayer(args.saida))

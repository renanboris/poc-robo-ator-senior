"""
capture_semantic.py — Senior Training OS · VLA Capture Engine
=============================================================
A Revolução Semântica (Fase 5). 
Zero dependência de CSS ou DOM complexo.
Baseado puramente em Visão (Screenshot) + Intenção (LLM) + Coordenadas Absolutas (W, H).
Inclui UX de gravação (Auto-Login e Badge REC Original).
"""

import asyncio
import json
import base64
import os
import sys
import logging
import re
import traceback
from dotenv import load_dotenv

from playwright.async_api import async_playwright, Error as PlaywrightError
from google import genai
from google.genai import types

load_dotenv()
logging.basicConfig(level=logging.INFO, format="[VLA CAPTURE] %(message)s")
logger = logging.getLogger(__name__)

# ==========================================
# CONFIGURAÇÃO DA IA (GEMINI 2.5 FLASH)
# ==========================================
_g_key = os.getenv("GOOGLE_API_KEY")
if not _g_key:
    logger.error("GOOGLE_API_KEY ausente. O Capturador Semântico requer Visão IA.")
    sys.exit(1)

gemini_client = genai.Client(api_key=_g_key)

cliques_capturados = []
_id_acao_global = 0
_lock_id = None

def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

# ==========================================
# O NOVO JAVASCRIPT (BURRO, MAS ELEGANTE)
# ==========================================
JS_INJECTION = """
() => {
    if (window.__radarSemanticoInjetado) return;
    window.__radarSemanticoInjetado = true;

    // 1. INJETAR O AVISO DE GRAVAÇÃO (Canto Inferior Direito - Estilo Original)
    if (window === window.top && !document.getElementById('senior-rec-widget')) {
        const recWidget = document.createElement('div');
        recWidget.id = 'senior-rec-widget';
        recWidget.style.cssText = 'position:fixed;bottom:30px;right:30px;background:rgba(15,23,42,0.85);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,0.1);border-radius:100px;padding:10px 20px;display:flex;align-items:center;gap:10px;z-index:2147483647;font-family:Segoe UI,sans-serif;box-shadow:0 10px 25px rgba(0,0,0,0.5);pointer-events:none;transition:opacity 0.1s ease;';
        recWidget.innerHTML = '<div style="width:12px;height:12px;background:#ef4444;border-radius:50%;animation:pulse-red 1.5s infinite;"></div><div style="color:white;font-size:13px;font-weight:bold;letter-spacing:1px;">MAPEAMENTO ATIVO (VLA)</div>';
        if (!document.getElementById('senior-rec-styles')) {
            const st = document.createElement('style'); st.id = 'senior-rec-styles';
            st.innerHTML = '@keyframes pulse-red{0%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(239,68,68,0.7)}70%{transform:scale(1);box-shadow:0 0 0 10px rgba(239,68,68,0)}100%{transform:scale(0.95);box-shadow:0 0 0 0 rgba(239,68,68,0)}}';
            document.head.appendChild(st);
        }
        document.documentElement.appendChild(recWidget);
    }

    // 2. CAPTURADOR FÍSICO (Apenas Bounding Box)
    document.addEventListener('mousedown', (e) => {
        if (e.button !== 0 && e.button !== 2) return; // Apenas Esq/Dir
        
        const rect = e.target.getBoundingClientRect();
        const vw = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
        const vh = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);

        const payload = {
            acao: e.button === 2 ? 'clique_direito' : 'clique',
            x_pct: (rect.left + rect.width / 2) / vw,
            y_pct: (rect.top + rect.height / 2) / vh,
            w_pct: rect.width / vw,
            h_pct: rect.height / vh,
            text_hint: e.target.innerText ? e.target.innerText.substring(0, 50).trim() : ''
        };

        // Atraso de 150ms no highlight para o Python conseguir tirar a foto perfeitamente limpa
        setTimeout(() => {
            const h = document.createElement('div');
            h.style.position = 'fixed'; h.style.left = rect.left + 'px'; h.style.top = rect.top + 'px';
            h.style.width = rect.width + 'px'; h.style.height = rect.height + 'px';
            h.style.border = '2px solid #00e5e5'; h.style.backgroundColor = 'rgba(0, 229, 229, 0.2)';
            h.style.zIndex = '999999'; h.style.pointerEvents = 'none'; h.style.transition = 'all 0.3s';
            document.body.appendChild(h);
            setTimeout(() => h.style.opacity = '0', 300);
            setTimeout(() => h.remove(), 600);
        }, 150);

        window.registrarCliqueSemantico(payload);
    }, true);
}
"""

async def analisar_semantica_gemini(b64_img: str, payload: dict) -> dict:
    """Envia o print e o Ponto X,Y para o Gemini extrair o significado do clique."""
    prompt = f"""
Você é o 'Semantic Capture Agent' (VLA) de um sistema de automação corporativa.
O utilizador acabou de clicar na interface do ecrã (imagem anexada).

📍 DADOS BRUTOS DO CLIQUE (Relativos ao ecrã):
- Eixo X (Horizontal): {payload['x_pct']*100:.1f}%
- Eixo Y (Vertical): {payload['y_pct']*100:.1f}%
- Dica de texto no HTML raso: "{payload['text_hint']}"

🎯 TAREFA:
Cruze a coordenada fornecida com a IMAGEM. O que é que o utilizador clicou?
Responda ESTRITAMENTE num formato JSON válido com as chaves exatas abaixo:

{{
  "intencao_desejada": "Frase direta do objetivo. Ex: 'Ativar a permissão de Download para a Adriana' ou 'Abrir o menu GED'.",
  "entidade": "Nome da pessoa, pasta ou item alvo. Ex: 'Adriana Conceição'. (Vazio se não houver).",
  "tipo_alvo": "Ex: 'checkbox', 'botão', 'input', 'ícone de menu'.",
  "contexto_coluna": "Se for uma tabela/grelha, qual é o nome do cabeçalho da coluna? (Vazio se não for tabela).",
  "validacao_esperada": "O que visualmente confirma o sucesso? Ex: 'O checkbox de Download da Adriana fica marcado'."
}}
"""
    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[prompt, types.Part.from_bytes(data=base64.b64decode(b64_img), mime_type="image/jpeg")],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Falha na IA Semântica: {e}")
        return {
            "intencao_desejada": f"Clicar em {payload['text_hint'] or 'elemento'}",
            "entidade": "", "tipo_alvo": "elemento visual", "contexto_coluna": "", "validacao_esperada": ""
        }

async def on_clique(source, payload, page):
    global _id_acao_global, _lock_id
    async with _lock_id:
        _id_acao_global += 1
        meu_id_acao = _id_acao_global

    logger.info(f"📸 [FOTO {meu_id_acao}] Capturando clique...")
    
    # 1. Esconde o Aviso de "Gravando" milissegundos antes do print
    await page.evaluate("() => { const w = document.getElementById('senior-rec-widget'); if(w) w.style.opacity = '0'; }")
    
    # 2. Tira a foto limpa
    screenshot_bytes = await page.screenshot(type="jpeg", quality=60, full_page=False)
    b64_img = base64.b64encode(screenshot_bytes).decode('utf-8')
    
    # 3. Devolve o Aviso de "Gravando"
    await page.evaluate("() => { const w = document.getElementById('senior-rec-widget'); if(w) w.style.opacity = '1'; }")
    
    # 4. IA processa a intenção em background
    semantica = await analisar_semantica_gemini(b64_img, payload)
    logger.info(f"🧠 [IA {meu_id_acao}] Intenção: {semantica['intencao_desejada']}")
    
    acao = {
        "id_acao": meu_id_acao,
        "acao": payload["acao"],
        "intencao_semantica": semantica["intencao_desejada"],
        "valor_input": "",
        "micro_narracao": f"...{semantica['intencao_desejada'].lower()}...",
        "seletor_css": "", # IA SEMÂNTICA: SEM CSS
        "elemento_alvo": {
            "descricao_visual": f"{semantica['tipo_alvo']} de {semantica['entidade']} na coluna {semantica['contexto_coluna']}",
            "contexto_tela": "Mapeado via VLA",
            "tipo_elemento": semantica["tipo_alvo"],
            "confianca_captura": "IA",
            "label_curto": semantica["entidade"] or semantica["tipo_alvo"],
            "coordenadas_relativas": {
                "x_pct": payload["x_pct"], "y_pct": payload["y_pct"],
                "w_pct": payload["w_pct"], "h_pct": payload["h_pct"]
            },
            "screenshot_referencia": b64_img
        },
        "validacao_esperada": {
            "tipo": "estado_visual",
            "alvo": semantica["validacao_esperada"]
        }
    }
    cliques_capturados.append(acao)


async def capturar_cliques_na_tela(nome_aula: str, objetivo: str):
    global _lock_id
    _lock_id = asyncio.Lock()

    SENIOR_URL = os.getenv("SENIOR_URL", "https://platform-homologx.senior.com.br/tecnologia/platform/senior-x/")
    usuario    = os.getenv("SENIOR_USER")
    senha      = os.getenv("SENIOR_PASS")

    if not usuario or not senha:
        print("ERRO FATAL: Credenciais ausentes no .env (SENIOR_USER / SENIOR_PASS).", flush=True)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True)
        page    = await context.new_page()

        await context.expose_binding("registrarCliqueSemantico", lambda source, payload: asyncio.ensure_future(on_clique(source, payload, page)))
        
        logger.info("Abrindo Senior X para Mapeamento VLA...")
        print("A iniciar o navegador e a tentar login...", flush=True)

        # ─── AUTO LOGIN SENIOR X ───
        try:
            await page.goto(SENIOR_URL)
            await asyncio.sleep(2.0)
            await page.keyboard.press("Escape")
            
            campo_usr = page.locator("input[type='text'], input[type='email'], [placeholder*='usuario']").first
            await campo_usr.wait_for(state="visible", timeout=10000)
            await campo_usr.fill(usuario)
            await asyncio.sleep(0.5)

            try:
                await page.locator("button:has-text('Próximo'), button:has-text('Proximo'), button:has-text('Continuar')").first.click(timeout=3000)
            except Exception:
                await page.keyboard.press("Enter")
            
            campo_senha = page.locator("input[type='password']").first
            await campo_senha.wait_for(state="visible", timeout=10000)
            await campo_senha.fill(senha)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            
            print("Login efetuado. A aguardar carregamento do painel...", flush=True)
            await page.wait_for_load_state("load", timeout=30_000)
            await asyncio.sleep(2.0)

        except Exception as e:
            logger.warning(f"O auto-login falhou/travou: {e}")
            print("AVISO: Conclua o login manualmente na janela do Chrome!", flush=True)
            try:
                await page.wait_for_load_state("networkidle", timeout=60000)
                await asyncio.sleep(3.0) 
            except Exception:
                print("ERRO FATAL: Tempo esgotado para login manual.", flush=True)
                await browser.close()
                return

        # ─── INJEÇÃO DO SCRIPT SEMÂNTICO ───
        await page.evaluate(JS_INJECTION)
        page.on("framenavigated", lambda frame: asyncio.create_task(page.evaluate(JS_INJECTION)) if frame == page.main_frame else None)

        # ─── BANNER DE INÍCIO ───
        try:
            await page.evaluate("""() => {
                if (!document.body) return;
                const d = document.createElement('div');
                d.innerHTML = 'GRAVAÇÃO VLA INICIADA!<br><span style="font-size:14px;font-weight:normal;">A IA está a mapear visualmente os seus cliques.</span>';
                d.style.cssText = 'position:fixed;top:20px;left:50%;transform:translateX(-50%);background:#e50914;color:white;padding:15px 30px;font-size:22px;font-weight:bold;font-family:sans-serif;z-index:999999;border-radius:8px;pointer-events:none;transition:opacity 1s ease;text-align:center;box-shadow:0 10px 25px rgba(229,9,20,0.5);';
                document.body.appendChild(d);
                setTimeout(() => d.style.opacity='0', 4000);
                setTimeout(() => d.remove(), 5000);
            }""")
        except Exception:
            pass

        print("\n" + "="*60)
        print("🔴 VLA CAPTURE ATIVO")
        print("Faça o mapeamento da sua aula de forma cadenciada.")
        print("Feche o navegador quando terminar para gerar o roteiro.")
        print("="*60 + "\n")
        
        # Mantém a janela aberta até o usuário fechar
        await page.wait_for_event("close", timeout=0)
        
        # ─── MONTAGEM DO ROTEIRO ───
        if cliques_capturados:
            os.makedirs("roteiros_salvos", exist_ok=True)
            caminho_arquivo = f"roteiros_salvos/{limpar_nome(nome_aula)}.json"
            
            roteiro = {
                "metadata": {"nome_aula": nome_aula, "id_treinamento": limpar_nome(nome_aula)},
                "passos": [
                    {
                        "id_passo": i + 1,
                        "tipo_passo": "action",
                        "pedagogia": {"ancora": acao["intencao_semantica"]},
                        "acoes_tecnicas": [acao]
                    } for i, acao in enumerate(cliques_capturados)
                ]
            }
            
            with open(caminho_arquivo, "w", encoding="utf-8") as f:
                json.dump(roteiro, f, indent=2, ensure_ascii=False)
                
            logger.info(f"✅ Roteiro Semântico guardado em {caminho_arquivo}")
        else:
            logger.warning("Nenhum clique registado.")


def iniciar_esteira_de_producao():
    try:
        print("\n" + "=" * 50 + "\nSENIOR SISTEMAS — TRAINING OS (VLA)\n" + "=" * 50, flush=True)

        is_auto = "--auto" in sys.argv

        if is_auto:
            args_posicionais = [a for a in sys.argv[1:] if not a.startswith("--")]
            if len(args_posicionais) < 2:
                print("ERRO FATAL: Modo --auto requer: capture_semantic.py <nome_aula> <objetivo> --auto", flush=True)
                sys.exit(1)
            nome_aula = args_posicionais[0]
            objetivo  = args_posicionais[1]
            logger.info(f"Iniciado via Dashboard | Aula: {nome_aula}")
        else:
            nome_aula = input("Qual e o nome desta aula? (Ex: Criar Pasta)\n> ")
            objetivo  = input("Qual e o objetivo do treinamento?\n> ")

        asyncio.run(capturar_cliques_na_tela(nome_aula, objetivo))

        if not cliques_capturados:
            print("AVISO: Nenhuma acao capturada. O navegador foi fechado sem interacoes.", flush=True)
            sys.exit(1)
            
        logger.info("Processo concluído com sucesso!")

    except Exception as e:
        print(f"ERRO FATAL DE EXECUCAO: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    iniciar_esteira_de_producao()
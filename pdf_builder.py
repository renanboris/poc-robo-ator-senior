import json
import sys
import os
import re
import base64
from io import BytesIO

# Bibliotecas para gerar PDF (ReportLab) e processar imagens (Pillow)
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib import colors
from PIL import Image as PILImage

def limpar_nome(nome: str) -> str:
    """Higieniza o nome para manter o padrão exato do app.py e scorm_builder.py"""
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")

def gerar_pdf(caminho_json, pasta_destino="documentacao_pdf"):
    """
    Lê o JSON do treinamento e gera um E-book (Playbook) em PDF 
    contendo os passos, telas e micro-narrações.
    """
    os.makedirs(pasta_destino, exist_ok=True)

    # 1. Carrega os dados do JSON
    with open(caminho_json, 'r', encoding='utf-8') as f:
        roteiro = json.load(f)

    metadata = roteiro.get("metadata", {})
    nome_aula_raw = metadata.get("nome_aula", "Treinamento Senior")
    id_treino = metadata.get("id_treinamento", nome_aula_raw)
    
    nome_arquivo_base = limpar_nome(id_treino)
    caminho_pdf = os.path.join(pasta_destino, f"{nome_arquivo_base}_Playbook.pdf")

    # 2. Configurações do Documento PDF (Paisagem/Landscape para caber as telas)
    doc = SimpleDocTemplate(
        caminho_pdf, 
        pagesize=landscape(A4),
        rightMargin=40, leftMargin=40,
        topMargin=40, bottomMargin=40
    )
    
    story = []
    styles = getSampleStyleSheet()

    # Estilos customizados
    title_style = ParagraphStyle(
        'TitleStyle', parent=styles['Heading1'], 
        fontSize=24, spaceAfter=20, textColor=colors.HexColor("#007a7a"), alignment=1
    )
    step_title_style = ParagraphStyle(
        'StepTitleStyle', parent=styles['Heading2'], 
        fontSize=16, spaceBefore=15, spaceAfter=10, textColor=colors.HexColor("#1f2937")
    )
    body_style = ParagraphStyle(
        'BodyStyle', parent=styles['Normal'], 
        fontSize=12, spaceAfter=10, leading=16, textColor=colors.HexColor("#475569")
    )
    action_style = ParagraphStyle(
        'ActionStyle', parent=styles['Normal'], 
        fontSize=11, spaceBefore=5, leading=14, textColor=colors.HexColor("#0f172a"), bulletIndent=10
    )

    # 3. Capa / Título
    story.append(Paragraph(f"Playbook de Treinamento", step_title_style))
    story.append(Paragraph(nome_aula_raw, title_style))
    story.append(Spacer(1, 0.5 * 72)) # Espaço

    # 4. Montagem dos Passos
    for idx, passo in enumerate(roteiro.get("passos", [])):
        id_p = passo.get("id_passo", idx + 1)
        ancora = passo.get("pedagogia", {}).get("ancora", "")
        
        # Procura a primeira imagem disponível no passo para ilustrar
        img_b64 = None
        acoes_texto = []
        
        for acao in passo.get("acoes_tecnicas", []):
            if acao.get("acao") == "concluir_video":
                continue
                
            if not img_b64:
                img_b64 = acao.get("elemento_alvo", {}).get("screenshot_referencia")
                
            micro = acao.get("micro_narracao", "")
            if micro:
                acoes_texto.append(micro)

        # Adiciona Título do Passo e Contexto (Âncora)
        story.append(Paragraph(f"Passo {id_p}", step_title_style))
        if ancora:
            story.append(Paragraph(f"<b>Contexto:</b> {ancora}", body_style))
            story.append(Spacer(1, 10))

        # Processa e Adiciona a Imagem da Tela
        if img_b64:
            try:
                img_data = base64.b64decode(img_b64)
                img_buffer = BytesIO(img_data)
                pil_img = PILImage.open(img_buffer)

                # Calcula o Aspect Ratio para caber na página PDF sem distorcer
                img_width, img_height = pil_img.size
                max_width = 650
                max_height = 320
                ratio = min(max_width / img_width, max_height / img_height)

                new_width = img_width * ratio
                new_height = img_height * ratio

                rl_img = RLImage(img_buffer, width=new_width, height=new_height)
                story.append(rl_img)
                story.append(Spacer(1, 15))
            except Exception as e:
                print(f"⚠️ Aviso: Não foi possível processar a imagem do Passo {id_p}: {e}")

        # Adiciona as micro-narrações / ações técnicas abaixo da imagem
        if acoes_texto:
            story.append(Paragraph("<b>Ações Necessárias:</b>", body_style))
            for txt in acoes_texto:
                story.append(Paragraph(f"• {txt}", action_style))

        # Quebra de página para o próximo passo (opcional, deixa mais organizado)
        story.append(PageBreak())

    # 5. Gera o arquivo físico
    try:
        doc.build(story)
        print(f"📔 Digital Playbook gerado com sucesso: {caminho_pdf}")
        return caminho_pdf
    except Exception as e:
        print(f"❌ Erro ao compilar o PDF: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        gerar_pdf(sys.argv[1])
    else:
        print("Uso: python pdf_builder.py <caminho_do_roteiro.json>")
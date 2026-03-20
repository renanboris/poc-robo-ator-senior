"""
pdf_builder.py  ·  Senior Training OS  ·  v2.2
─────────────────────────────────────────────
Gera um Playbook digital de alta fidelidade para cada treinamento gerado
pelo Training OS. Layout baseado em Dual Coding Theory + Cognitive Load
Tiering (peso_narrativo), com sistema de design corporativo Senior.
Inclui Motor de Zoom Inteligente e Auto-Highlight de ações.
"""

import json
import sys
import os
import re
import base64
import textwrap
from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Image as RLImage
from PIL import Image as PILImage, ImageDraw


# ─────────────────────────────────────────────
# DESIGN SYSTEM  ·  Senior Brand Tokens
# ─────────────────────────────────────────────

class DS:
    """Design System tokens — única fonte de verdade para cores e espaçamentos."""

    # Brand palette
    PRIMARY       = colors.HexColor("#009999")
    PRIMARY_DARK  = colors.HexColor("#006666")
    PRIMARY_LIGHT = colors.HexColor("#E6F7F7")
    PRIMARY_MUTED = colors.HexColor("#B3E0E0")

    DARK          = colors.HexColor("#0D1B2A")
    DARK_2        = colors.HexColor("#1E293B")
    DARK_3        = colors.HexColor("#334155")
    DARK_4        = colors.HexColor("#64748B")

    SURFACE       = colors.HexColor("#F8FAFC")
    CARD          = colors.HexColor("#FFFFFF")
    BORDER        = colors.HexColor("#E2E8F0")
    BORDER_DARK   = colors.HexColor("#CBD5E1")

    WHITE         = colors.HexColor("#FFFFFF")

    # Step-type semantic colors: (fg_hex, bg_hex, label)
    TYPE_COLORS = {
        "navigation":   ("#3B82F6", "#EFF6FF", "Navegação"),
        "form_fill":    ("#8B5CF6", "#F5F3FF", "Formulário"),
        "confirmation": ("#10B981", "#ECFDF5", "Confirmação"),
        "creation":     ("#F59E0B", "#FFFBEB", "Criação"),
        "deletion":     ("#EF4444", "#FEF2F2", "Exclusão"),
    }

    ALERT_BG     = colors.HexColor("#FFFBEB")
    ALERT_BORDER = colors.HexColor("#F59E0B")
    ALERT_TEXT   = colors.HexColor("#92400E")

    # Peso narrativo
    PESO_COLORS = {
        3: colors.HexColor("#009999"),
        2: colors.HexColor("#3B82F6"),
        1: colors.HexColor("#94A3B8"),
    }
    PESO_LABELS = {3: "Professor", 2: "Guia", 1: "Músculo"}

    # Ação type colors (fg, bg)
    ACAO_COLORS = {
        "clique":           ("#3B82F6", "#EFF6FF"),
        "duplo_clique":     ("#8B5CF6", "#F5F3FF"),
        "digitar_e_enter":  ("#10B981", "#ECFDF5"),
        "preencher_campo":  ("#F59E0B", "#FFFBEB"),
        "scroll":           ("#64748B", "#F1F5F9"),
    }

    # Typography scale (pt)
    T_HERO  = 32
    T_H1    = 18
    T_H2    = 14
    T_H3    = 11
    T_BODY  = 10
    T_SMALL = 8.5
    T_MICRO = 7.5

    # Spacing (8pt grid)
    S1, S2, S3, S4, S5, S6, S8 = 4, 8, 12, 16, 24, 32, 48

    # Page geometry
    PW, PH = landscape(A4)
    MARGIN  = 26 * mm
    HEADER_H = 13 * mm
    FOOTER_H = 7.5 * mm

    CW = PW - 2 * MARGIN
    CH = PH - MARGIN - HEADER_H - FOOTER_H - 6 * mm


# ─────────────────────────────────────────────
# DRAWING PRIMITIVES & IMAGE PROCESSING
# ─────────────────────────────────────────────

def hx(hex_str: str) -> colors.HexColor:
    return colors.HexColor(hex_str)


def limpar_nome(nome: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "", nome).replace(" ", "_")[:40].strip("_")


def truncate(text: str, n: int) -> str:
    return text[:n] + "…" if len(text) > n else text


def processar_imagem_com_zoom(b64_str: str, coords: dict) -> PILImage.Image | None:
    """
    Descodifica o print e aplica um "Zoom" croppando a imagem em torno do clique,
    além de desenhar um retângulo vermelho destacando a ação (Auto-Highlight).
    """
    if not b64_str:
        return None
    try:
        img = PILImage.open(BytesIO(base64.b64decode(b64_str))).convert("RGB")
        img_w, img_h = img.size
        draw = ImageDraw.Draw(img)
        pad = 8
        
        # 1. Pega nas coordenadas do clique
        cx = coords.get("x_pct", 0.5) * img_w
        cy = coords.get("y_pct", 0.5) * img_h
        tw = coords.get("w_pct", 0.05) * img_w
        th = coords.get("h_pct", 0.05) * img_h
        
        # Desenha a caixa vermelha de destaque
        box = [max(0, cx - tw/2 - pad), max(0, cy - th/2 - pad),
               min(img_w, cx + tw/2 + pad), min(img_h, cy + th/2 + pad)]
        draw.rectangle(box, outline="#EF4444", width=6)

        # 2. Define a janela de Zoom (Proporção ajustada para o painel lateral do PDF)
        crop_w, crop_h = 800, 1050 
        
        crop_w = max(crop_w, tw * 2.5)
        crop_h = max(crop_h, th * 2.5)

        left = cx - crop_w / 2
        top = cy - crop_h / 2
        right = cx + crop_w / 2
        bottom = cy + crop_h / 2

        # 3. Ajusta o "câmera pan" para não criar faixas pretas
        if left < 0:
            right += (0 - left)
            left = 0
        if right > img_w:
            left -= (right - img_w)
            right = img_w
        if top < 0:
            bottom += (0 - top)
            top = 0
        if bottom > img_h:
            top -= (bottom - img_h)
            bottom = img_h

        # Boundary check de segurança
        left = max(0, left)
        top = max(0, top)
        right = min(img_w, right)
        bottom = min(img_h, bottom)

        return img.crop((left, top, right, bottom))
    except Exception as e:
        print(f"Aviso: Não foi possível aplicar zoom na imagem: {e}")
        try:
            return PILImage.open(BytesIO(base64.b64decode(b64_str))).convert("RGB")
        except:
            return None


def pil_to_rl(pil_img: PILImage.Image, max_w: float, max_h: float) -> RLImage | None:
    try:
        buf = BytesIO()
        pil_img.convert("RGB").save(buf, format="PNG")
        buf.seek(0)
        w, h = pil_img.size
        ratio = min(max_w / w, max_h / h)
        return RLImage(buf, width=w * ratio, height=h * ratio)
    except Exception:
        return None


def rounded_rect(c, x, y, w, h, r=4, fill=None, stroke=None, sw=0.5):
    p = c.beginPath()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.arcTo(x + w - r, y, x + w, y + r, -90, 90)
    p.lineTo(x + w, y + h - r)
    p.arcTo(x + w - r, y + h - r, x + w, y + h, 0, 90)
    p.lineTo(x + r, y + h)
    p.arcTo(x, y + h - r, x + r, y + h, 90, 90)
    p.lineTo(x, y + r)
    p.arcTo(x, y, x + r, y + r, 180, 90)
    p.close()
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw)
    mode = (1 if fill else 0), (1 if stroke else 0)
    c.drawPath(p, fill=mode[0], stroke=mode[1])


def shadow(c, x, y, w, h, r=4, off=2, alpha=0.10):
    rounded_rect(c, x + off, y - off, w, h, r,
                 fill=colors.Color(0, 0, 0, alpha=alpha))


def tag(c, x, y, text, fg, bg, size=7.5):
    """Draw pill badge; returns consumed width."""
    px, py = 6, 3
    tw = c.stringWidth(text, "Helvetica-Bold", size)
    w = tw + 2 * px
    h = size + 2 * py + 2
    rounded_rect(c, x, y, w, h, 3, fill=hx(bg), stroke=hx(fg), sw=0.5)
    c.setFillColor(hx(fg))
    c.setFont("Helvetica-Bold", size)
    c.drawString(x + px, y + py + 1, text)
    return w + 3


def peso_dots(c, x, y, peso: int, size=5):
    """3-dot indicator for peso_narrativo."""
    for i in range(3):
        cx = x + i * (size + 3) + size / 2
        cy = y + size / 2
        c.setFillColor(DS.PESO_COLORS.get(peso) if i < peso else DS.BORDER_DARK)
        c.setStrokeColor(colors.Color(0, 0, 0, alpha=0))
        c.circle(cx, cy, size / 2, fill=1, stroke=0)
    return 3 * (size + 3)


def multiline(c, text, x, y, font, size, color, max_w, lh, max_lines=None):
    """Word-wrap + draw text; returns final y."""
    c.setFont(font, size)
    c.setFillColor(color)
    words = text.split()
    lines, cur = [], ""
    for word in words:
        test = (cur + " " + word).strip()
        if c.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        while lines[-1] and c.stringWidth(lines[-1] + "…", font, size) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
    for line in lines:
        c.drawString(x, y, line)
        y -= lh
    return y


def step_meta(tipo: str):
    return DS.TYPE_COLORS.get(tipo, ("#64748B", "#F1F5F9",
                                    tipo.replace("_", " ").title()))


# ─────────────────────────────────────────────
# PDF BUILDER CLASS
# ─────────────────────────────────────────────

class PDFBuilder:

    def __init__(self, roteiro: dict, pasta: str = "documentacao_pdf"):
        self.roteiro = roteiro
        self.meta    = roteiro.get("metadata", {})
        self.passos  = roteiro.get("passos", [])
        self.pasta   = pasta
        os.makedirs(pasta, exist_ok=True)

        # 🟢 AQUI GARANTIMOS QUE O BACKEND ENCONTRE O ARQUIVO:
        # Usa exatamente o mesmo padrão que app.py espera: id_treinamento_Playbook.pdf
        nome = limpar_nome(
            self.meta.get("id_treinamento") or self.meta.get("nome_aula", "Treinamento")
        )
        self.out_path = os.path.join(pasta, f"{nome}_Playbook.pdf")

        self.n_passos  = len([p for p in self.passos if not p.get("is_conclusao")])
        
        # 🟢 CORREÇÃO: Conta ações corretamente mesmo se "ids_acoes_tecnicas" estiver ausente
        self.n_acoes = sum(
            len(p.get("ids_acoes_tecnicas", p.get("acoes_tecnicas", []))) 
            for p in self.passos
        )
        
        self.data = datetime.now().strftime("%d/%m/%Y")

    # ─── Header ──────────────────────────────────────────────────────────────
    def _header(self, c, step_n=0, total=0):
        pw, ph, hh = DS.PW, DS.PH, DS.HEADER_H
        c.setFillColor(DS.DARK)
        c.rect(0, ph - hh, pw, hh, fill=1, stroke=0)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(DS.PRIMARY)
        c.drawString(DS.MARGIN, ph - hh + 5, "SENIOR")
        c.setFont("Helvetica", 9)
        c.setFillColor(hx("#94A3B8"))
        c.drawString(DS.MARGIN + 46, ph - hh + 5, "Training OS")

        c.setFillColor(DS.DARK_4)
        c.circle(DS.MARGIN + 110, ph - hh + 9, 1.5, fill=1, stroke=0)

        titulo = truncate(self.meta.get("titulo", self.meta.get("nome_aula", "")), 52)
        c.setFont("Helvetica", 8)
        c.setFillColor(hx("#64748B"))
        c.drawString(DS.MARGIN + 120, ph - hh + 5, titulo)

        if step_n and total:
            label = f"Passo {step_n} / {total}"
            lw = c.stringWidth(label, "Helvetica", 8)
            rx = DS.PW - DS.MARGIN
            c.setFont("Helvetica", 8)
            c.setFillColor(DS.WHITE)
            c.drawString(rx - lw, ph - hh + 5, label)
            bw = 80
            bx = rx - bw
            by = ph - hh + 3
            c.setFillColor(DS.DARK_3)
            c.rect(bx, by, bw, 2, fill=1, stroke=0)
            c.setFillColor(DS.PRIMARY)
            c.rect(bx, by, bw * step_n / total, 2, fill=1, stroke=0)

    # ─── Footer ──────────────────────────────────────────────────────────────
    def _footer(self, c, pg, total):
        pw, fh = DS.PW, DS.FOOTER_H
        c.setFillColor(DS.SURFACE)
        c.rect(0, 0, pw, fh, fill=1, stroke=0)
        c.setStrokeColor(DS.BORDER)
        c.setLineWidth(0.4)
        c.line(DS.MARGIN, fh, pw - DS.MARGIN, fh)

        c.setFont("Helvetica", 7)
        c.setFillColor(DS.DARK_4)
        c.drawString(DS.MARGIN, fh - 5, f"Gerado em {self.data}")

        titulo = truncate(self.meta.get("titulo", self.meta.get("nome_aula", "")), 58)
        tw = c.stringWidth(titulo, "Helvetica", 7)
        c.drawString((pw - tw) / 2, fh - 5, titulo)

        pg_label = f"{pg} / {total}"
        plw = c.stringWidth(pg_label, "Helvetica", 7)
        c.drawString(pw - DS.MARGIN - plw, fh - 5, pg_label)

    # ─── Cover ───────────────────────────────────────────────────────────────
    def _cover(self, c):
        pw, ph = DS.PW, DS.PH

        # Dark background
        c.setFillColor(DS.DARK)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        # Teal left edge accent
        c.setFillColor(DS.PRIMARY)
        c.rect(0, 0, 5, ph, fill=1, stroke=0)

        # Decorative concentric circles (brand atmosphere)
        for radius, alpha in [(340, 0.04), (240, 0.06), (150, 0.04)]:
            c.setFillColor(colors.Color(0, 0.6, 0.6, alpha=alpha))
            c.circle(pw, ph, radius, fill=1, stroke=0)

        # Senior wordmark
        c.setFont("Helvetica-Bold", 14)
        c.setFillColor(DS.PRIMARY)
        c.drawString(DS.MARGIN + 8, ph - 52, "SENIOR")
        c.setFont("Helvetica", 14)
        c.setFillColor(hx("#94A3B8"))
        c.drawString(DS.MARGIN + 68, ph - 52, "Training OS")

        # Thin divider
        c.setStrokeColor(hx("#1E3A4A"))
        c.setLineWidth(0.7)
        c.line(DS.MARGIN + 8, ph - 62, pw - DS.MARGIN, ph - 62)

        # Module + Level eyebrow
        modulo = self.meta.get("modulo", "Senior Flow")
        nivel  = self.meta.get("nivel", "Operacional")
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(DS.PRIMARY)
        c.drawString(DS.MARGIN + 8, ph - 82, modulo.upper())
        mw = c.stringWidth(modulo.upper(), "Helvetica-Bold", 9)
        c.setStrokeColor(DS.PRIMARY_MUTED)
        c.setLineWidth(0.7)
        c.line(DS.MARGIN + 8 + mw + 12, ph - 76,
               DS.MARGIN + 8 + mw + 12, ph - 86)
        c.setFont("Helvetica", 9)
        c.setFillColor(hx("#64748B"))
        c.drawString(DS.MARGIN + 8 + mw + 22, ph - 82, nivel)

        # Main title
        titulo = self.meta.get("titulo", self.meta.get("nome_aula", "Treinamento Senior"))
        multiline(c, titulo, DS.MARGIN + 8, ph - 110,
                  "Helvetica-Bold", DS.T_HERO, DS.WHITE,
                  pw * 0.60, DS.T_HERO * 1.30, max_lines=3)

        # Subtitle
        c.setFont("Helvetica", 13)
        c.setFillColor(hx("#94A3B8"))
        c.drawString(DS.MARGIN + 8, ph * 0.40, "Digital Playbook de Treinamento")

        # Stats row
        sy   = ph * 0.25
        data = [
            (str(self.n_passos), "passos"),
            (str(self.n_acoes), "ações gravadas"),
            (self.data, "data de geração"),
        ]
        sx = DS.MARGIN + 8
        for i, (val, lbl) in enumerate(data):
            c.setFont("Helvetica-Bold", 20)
            c.setFillColor(DS.WHITE)
            c.drawString(sx, sy + 14, val)
            vw = c.stringWidth(val, "Helvetica-Bold", 20)
            c.setFont("Helvetica", 8.5)
            c.setFillColor(hx("#64748B"))
            c.drawString(sx, sy, lbl)
            lw = c.stringWidth(lbl, "Helvetica", 8.5)
            col_w = max(vw, lw) + 30
            if i < len(data) - 1:
                c.setStrokeColor(hx("#1E3A4A"))
                c.setLineWidth(0.7)
                c.line(sx + col_w - 12, sy - 2, sx + col_w - 12, sy + 22)
            sx += col_w

        # Right info card
        cx  = pw * 0.68
        cw  = pw - cx - DS.MARGIN * 0.4
        cy  = ph * 0.18
        cht = ph * 0.60
        shadow(c, cx, cy, cw, cht, r=6, off=3)
        rounded_rect(c, cx, cy, cw, cht, 6,
                     fill=hx("#0A2A35"), stroke=DS.PRIMARY, sw=0.8)

        iy = cy + cht - 20
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(DS.PRIMARY)
        c.drawString(cx + 16, iy, "TIPOS DE PASSO")
        c.setStrokeColor(DS.PRIMARY_DARK)
        c.setLineWidth(0.4)
        c.line(cx + 16, iy - 4, cx + cw - 16, iy - 4)

        iy -= 20
        for k in ["navigation", "form_fill", "creation", "confirmation", "deletion"]:
            fg, _, lbl = step_meta(k)
            c.setFillColor(hx(fg))
            c.circle(cx + 22, iy + 4, 4.5, fill=1, stroke=0)
            c.setFont("Helvetica", 8.5)
            c.setFillColor(DS.WHITE)
            c.drawString(cx + 34, iy, lbl)
            iy -= 18

        iy -= 8
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(DS.PRIMARY)
        c.drawString(cx + 16, iy, "PESO NARRATIVO")
        c.line(cx + 16, iy - 4, cx + cw - 16, iy - 4)
        iy -= 20

        for p in [3, 2, 1]:
            peso_dots(c, cx + 16, iy, p, size=5)
            c.setFont("Helvetica", 8.5)
            c.setFillColor(DS.WHITE)
            c.drawString(cx + 38, iy, DS.PESO_LABELS[p])
            iy -= 17

        # Bottom teal bar
        c.setFillColor(DS.PRIMARY)
        c.rect(0, 0, pw, 4, fill=1, stroke=0)

    # ─── Table of contents ───────────────────────────────────────────────────
    def _toc(self, c, pg, total_pg):
        pw, ph = DS.PW, DS.PH
        c.setFillColor(DS.SURFACE)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)
        self._header(c)
        self._footer(c, pg, total_pg)

        y = ph - DS.HEADER_H - DS.S8
        c.setFont("Helvetica-Bold", DS.T_H1)
        c.setFillColor(DS.DARK_2)
        c.drawString(DS.MARGIN, y, "Índice de Passos")
        c.setStrokeColor(DS.PRIMARY)
        c.setLineWidth(2)
        c.line(DS.MARGIN, y - 7, DS.MARGIN + 150, y - 7)

        col_w  = (DS.CW - DS.S5) / 2
        col1_x = DS.MARGIN
        col2_x = DS.MARGIN + col_w + DS.S5
        row_h  = 42
        y -= DS.S8
        col = 0

        for passo in self.passos:
            x = col1_x if col == 0 else col2_x
            tipo = passo.get("tipo_passo", "navigation")
            fg, bg, lbl = step_meta(tipo)
            is_c = passo.get("is_conclusao", False)
            peso = passo.get("peso_narrativo", 2)

            card_fill   = DS.PRIMARY_LIGHT if is_c else DS.CARD
            card_stroke = DS.PRIMARY       if is_c else DS.BORDER

            shadow(c, x, y - row_h + 6, col_w, row_h, r=4, off=2)
            rounded_rect(c, x, y - row_h + 6, col_w, row_h, 4,
                         fill=card_fill, stroke=card_stroke, sw=0.5)

            # Circle with step number
            num = str(passo.get("id_passo", ""))
            cx2 = x + 18
            cy2 = y - row_h + 6 + row_h / 2
            c.setFillColor(DS.PRIMARY if is_c else hx(fg))
            c.circle(cx2, cy2, 9, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(DS.WHITE)
            nw = c.stringWidth(num, "Helvetica-Bold", 8)
            c.drawString(cx2 - nw / 2, cy2 - 3.5, num)

            # Anchor preview
            ancora = passo.get("pedagogia", {}).get("ancora", "")
            if is_c:
                ancora = "✓  " + ancora
            tx = x + 34
            tw = col_w - 34 - 6
            multiline(c, truncate(ancora, 95), tx, y - 10,
                      "Helvetica", 8, DS.DARK_2, tw, 10, max_lines=2)

            # Type tag
            tag(c, tx, y - row_h + 9, lbl, fg, bg, 6.5)
            # Peso dots
            pd_x = tx + c.stringWidth(lbl, "Helvetica-Bold", 6.5) + 22
            peso_dots(c, pd_x, y - row_h + 11, peso, size=4)

            y -= row_h + DS.S2
            if y < DS.FOOTER_H + DS.S8:
                col = 1 - col
                y = ph - DS.HEADER_H - DS.S8 - DS.S8

    # ─── Step page ───────────────────────────────────────────────────────────
    def _step(self, c, passo: dict, step_n: int, pg: int, total_pg: int):
        pw, ph = DS.PW, DS.PH

        tipo  = passo.get("tipo_passo", "navigation")
        fg, bg, lbl = step_meta(tipo)
        peso  = passo.get("peso_narrativo", 2)
        id_p  = passo.get("id_passo", step_n)
        ancora = passo.get("pedagogia", {}).get("ancora", "")
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        alerta  = passo.get("alerta_instrutor")
        micros  = passo.get("micro_narracoes", [])
        acoes   = passo.get("acoes_tecnicas", [])
        ids_t   = passo.get("ids_acoes_tecnicas", [])

        # Background
        c.setFillColor(DS.SURFACE)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        self._header(c, id_p, self.n_passos)
        self._footer(c, pg, total_pg)

        top = ph - DS.HEADER_H - DS.S4
        bot = DS.FOOTER_H + DS.S4

        # ── Left panel: screenshot ────────────────────────────────────────
        lw  = DS.CW * 0.44
        rw  = DS.CW * 0.53
        lx  = DS.MARGIN
        rx  = DS.MARGIN + lw + DS.S5
        ph_ = top - bot - DS.S2

        shadow(c, lx, bot, lw, ph_, r=6, off=3)
        rounded_rect(c, lx, bot, lw, ph_, 6,
                     fill=DS.CARD, stroke=DS.BORDER, sw=0.5)

        # 🟢 NOVA LÓGICA DE ZOOM NA IMAGEM
        screenshot = None
        for ac in acoes:
            b64 = ac.get("elemento_alvo", {}).get("screenshot_referencia")
            coords = ac.get("elemento_alvo", {}).get("coordenadas_relativas", {})
            if b64:
                screenshot = processar_imagem_com_zoom(b64, coords)
                if screenshot:
                    break

        img_pad = 10
        imax_w  = lw - 2 * img_pad
        imax_h  = ph_ - 62

        if screenshot:
            rl = pil_to_rl(screenshot, imax_w, imax_h)
            if rl:
                ix = lx + (lw - rl.drawWidth) / 2
                iy = bot + 48 + (imax_h - rl.drawHeight) / 2
                rl.drawOn(c, ix, iy)
        else:
            # Elegant placeholder
            px2 = lx + img_pad
            py2 = bot + 48
            rounded_rect(c, px2, py2, imax_w, imax_h, 4,
                         fill=hx(bg), stroke=DS.BORDER, sw=0.5)
            icon_txt = "Captura de Tela"
            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(hx(fg))
            iw = c.stringWidth(icon_txt, "Helvetica-Bold", 10)
            c.drawString(px2 + (imax_w - iw) / 2, py2 + imax_h / 2, icon_txt)
            sub_txt = "screenshot disponível após gravação"
            c.setFont("Helvetica", 8)
            c.setFillColor(DS.DARK_4)
            sw = c.stringWidth(sub_txt, "Helvetica", 8)
            c.drawString(px2 + (imax_w - sw) / 2, py2 + imax_h / 2 - 15, sub_txt)

        # Bottom of image card: badge + tags
        badge_r = 14
        bx = lx + 12
        by = bot + 12
        c.setFillColor(hx(fg))
        c.circle(bx + badge_r, by + badge_r, badge_r, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(DS.WHITE)
        ns = str(id_p)
        nw = c.stringWidth(ns, "Helvetica-Bold", 11)
        c.drawString(bx + badge_r - nw / 2, by + badge_r - 4.5, ns)

        tx_off = bx + badge_r * 2 + 8
        consumed = tag(c, tx_off, by + 4, lbl, fg, bg, 7.5)
        peso_lbl = DS.PESO_LABELS.get(peso, "")
        peso_dots(c, tx_off + consumed + DS.S1, by + 5, peso, size=4.5)
        c.setFont("Helvetica", 7)
        c.setFillColor(DS.DARK_4)
        c.drawString(tx_off + consumed + DS.S1 + 22, by + 5, peso_lbl)

        # ── Right panel: pedagogy ─────────────────────────────────────────
        ry = top - DS.S3

        # Section label + line
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(DS.PRIMARY)
        c.drawString(rx, ry, "CONTEXTO")
        line_start = rx + c.stringWidth("CONTEXTO", "Helvetica-Bold", 7) + 8
        c.setStrokeColor(DS.PRIMARY_MUTED)
        c.setLineWidth(1)
        c.line(line_start, ry + 2.5, rx + rw, ry + 2.5)
        ry -= DS.S3 + 2

        # Ancora — font size + style scales with peso
        if peso == 3:
            a_font, a_size, a_color, a_lines = "Helvetica-BoldOblique", DS.T_H2, DS.DARK_2, 6
        elif peso == 2:
            a_font, a_size, a_color, a_lines = "Helvetica", DS.T_H3 + 0.5, DS.DARK_3, 4
        else:
            a_font, a_size, a_color, a_lines = "Helvetica", DS.T_H3, DS.DARK_4, 2

        ry = multiline(c, ancora, rx, ry, a_font, a_size, a_color,
                       rw, a_size * 1.45, max_lines=a_lines)
        ry -= DS.S4

        # DAP tooltip chip
        if tooltip:
            chip_h = 16
            chip_txt = f"  ⚡  {tooltip}"
            chip_w = min(c.stringWidth(chip_txt, "Helvetica-Bold", 8) + 14, rw)
            rounded_rect(c, rx, ry - chip_h + 3, chip_w, chip_h, 8,
                         fill=DS.PRIMARY_LIGHT, stroke=DS.PRIMARY_MUTED, sw=0.6)
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(DS.PRIMARY_DARK)
            c.drawString(rx + 7, ry - 9, chip_txt)
            ry -= chip_h + DS.S4

        # Alert box
        if alerta:
            lh = 11
            lines = textwrap.wrap(alerta, 82)
            ah = min(len(lines) * lh + 20, 56)
            rounded_rect(c, rx, ry - ah + 4, rw, ah, 4,
                         fill=DS.ALERT_BG, stroke=DS.ALERT_BORDER, sw=1)
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(DS.ALERT_BORDER)
            c.drawString(rx + 8, ry - 10, "⚠")
            c.setFillColor(DS.ALERT_TEXT)
            c.drawString(rx + 22, ry - 10, "Atenção ao Instrutor:")
            ay = ry - 10 - lh
            c.setFont("Helvetica", 8)
            for line in lines[:3]:
                c.drawString(rx + 22, ay, line)
                ay -= lh
            ry -= ah + DS.S4

        # Micro-narrations / action list
        pairs = [(ac, m) for ac, m in zip(acoes, micros + [""] * len(acoes))]

        if peso == 1 and ids_t:
            c.setFont("Helvetica-BoldOblique", 8.5)
            c.setFillColor(DS.DARK_4)
            c.drawString(rx, ry, f"{len(ids_t)} ação(ões) — execução direta, sem narração.")

        elif pairs:
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(DS.DARK_4)
            
            # 🟢 CORREÇÃO: Fallback inteligente caso ids_t esteja vazio num roteiro manual
            num_acoes_reais = len(ids_t) if ids_t else len(acoes)
            c.drawString(rx, ry, f"AÇÕES  ({num_acoes_reais} no total)")
            ry -= DS.S3

            for ac_obj, micro in pairs[:7]:
                if ry < bot + 10:
                    break
                acao_tipo = ac_obj.get("acao", "clique")
                a_fg, a_bg = DS.ACAO_COLORS.get(acao_tipo, ("#64748B", "#F1F5F9"))
                acao_lbl = acao_tipo.replace("_", " ")

                row_h = 24
                rounded_rect(c, rx, ry - row_h + 4, rw, row_h, 3,
                             fill=DS.SURFACE, stroke=DS.BORDER, sw=0.35)

                consumed2 = tag(c, rx + 8, ry - row_h + 8, acao_lbl, a_fg, a_bg, 6.5)

                micro_disp = micro.strip("…. ") if micro else ac_obj.get("intencao_semantica", "")
                micro_x = rx + 8 + consumed2 + 5
                micro_w = rw - consumed2 - 24
                c.setFont("Helvetica", 8)
                c.setFillColor(DS.DARK_3)
                c.drawString(micro_x, ry - row_h + 13, truncate(micro_disp, 85))

                ry -= row_h + DS.S1

    # ─── Conclusion ──────────────────────────────────────────────────────────
    def _conclusion(self, c, passo: dict, pg: int, total_pg: int):
        pw, ph = DS.PW, DS.PH

        c.setFillColor(DS.DARK)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        c.setFillColor(DS.PRIMARY)
        c.rect(0, ph - 4, pw, 4, fill=1, stroke=0)

        for r, a in [(340, 0.04), (230, 0.06), (130, 0.04)]:
            c.setFillColor(colors.Color(0, 0.6, 0.6, alpha=a))
            c.circle(pw / 2, ph / 2, r, fill=1, stroke=0)

        # Checkmark
        cx, cy = pw / 2, ph * 0.70
        c.setFillColor(DS.PRIMARY)
        c.circle(cx, cy, 26, fill=1, stroke=0)
        c.setFillColor(DS.WHITE)
        c.setFont("Helvetica-Bold", 18)
        c.drawCentredString(cx, cy - 6, "✓")

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(DS.PRIMARY)
        c.drawCentredString(cx, cy - 44, "TREINAMENTO CONCLUÍDO")

        # Anchor
        ancora = passo.get("pedagogia", {}).get("ancora", "")
        multiline(c, ancora, DS.MARGIN, ph * 0.52,
                  "Helvetica-BoldOblique", DS.T_H1, DS.WHITE,
                  DS.CW, DS.T_H1 * 1.4, max_lines=4)

        # Stats row
        sy   = ph * 0.22
        data = [
            (str(self.n_passos), "passos realizados"),
            (str(self.n_acoes), "ações no sistema"),
            (self.meta.get("modulo", "Senior Flow"), "módulo"),
        ]
        cw2 = DS.CW / 3
        for i, (val, lbl) in enumerate(data):
            sx = DS.MARGIN + i * cw2
            rounded_rect(c, sx + 4, sy - 10, cw2 - 16, 52, 4,
                         fill=hx("#0A2A35"), stroke=DS.PRIMARY_DARK, sw=0.7)
            c.setFont("Helvetica-Bold", DS.T_H1)
            c.setFillColor(DS.PRIMARY)
            c.drawString(sx + 16, sy + 22, val)
            c.setFont("Helvetica", 8.5)
            c.setFillColor(hx("#64748B"))
            c.drawString(sx + 16, sy + 8, lbl)

        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(DS.PRIMARY)
        c.drawCentredString(pw / 2, 14,
            f"SENIOR TRAINING OS  ·  Universidade Corporativa Senior  ·  {self.data}")

    # ─── Build ───────────────────────────────────────────────────────────────
    def build(self) -> str:
        print(f"\n📔 Gerando Playbook Premium...")
        print(f"   {self.n_passos} passos  ·  {self.n_acoes} ações  ·  {self.meta.get('titulo', '')}")

        regular_passos  = [p for p in self.passos if not p.get("is_conclusao")]
        conclusao_passo = next((p for p in self.passos if p.get("is_conclusao")), None)

        total_pg = 1 + 1 + len(regular_passos) + (1 if conclusao_passo else 0)
        pg = 0

        c = rl_canvas.Canvas(self.out_path, pagesize=landscape(A4))
        c.setAuthor("Senior Training OS — Aura IA")
        c.setTitle(self.meta.get("titulo", "Playbook Senior"))
        c.setSubject(self.meta.get("modulo", "Senior Flow"))
        c.setCreator("pdf_builder.py v2.2")

        # 1 — Cover
        pg += 1
        self._cover(c)
        c.showPage()
        print(f"   ✓ Capa")

        # 2 — TOC
        pg += 1
        self._toc(c, pg, total_pg)
        c.showPage()
        print(f"   ✓ Índice ({len(self.passos)} entradas)")

        # 3 — Steps
        for i, passo in enumerate(regular_passos):
            pg += 1
            self._step(c, passo, i + 1, pg, total_pg)
            c.showPage()
            print(f"   ✓ Passo {passo.get('id_passo', i+1)}  [{passo.get('tipo_passo')}]  peso={passo.get('peso_narrativo', '?')}")

        # 4 — Conclusion
        if conclusao_passo:
            pg += 1
            self._conclusion(c, conclusao_passo, pg, total_pg)
            c.showPage()
            print(f"   ✓ Conclusão")

        c.save()
        kb = os.path.getsize(self.out_path) // 1024
        print(f"\n✅ Playbook gerado: {self.out_path}")
        print(f"   {total_pg} páginas  ·  {kb} KB")
        return self.out_path


# ─────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────

def gerar_pdf(caminho_json: str, pasta_destino: str = "documentacao_pdf") -> str:
    """
    Ponto de entrada principal — compatível com assinatura v1.
    Lê roteiro JSON e gera Playbook PDF premium.
    """
    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)
    return PDFBuilder(roteiro, pasta_destino).build()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        gerar_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "documentacao_pdf")
    else:
        print("Uso: python pdf_builder.py <roteiro.json> [pasta_destino]")
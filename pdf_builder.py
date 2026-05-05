
"""
pdf_builder.py  ·  Senior Playbook Engine  ·  v3.0
─────────────────────────────────────────────
Gera um Playbook digital premium para cada treinamento do Training OS.
Inclui:
- design editorial unificado
- tipografia de marca com fallback
- spotlight cinematográfico nas screenshots
- mapa do playbook
- cards da Aura
- fechamento com sensação de habilidade adquirida
"""

import base64
import json
import os
import sys
import textwrap
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Image as RLImage

from utils import limpar_nome

# ─────────────────────────────────────────────
# DESIGN SYSTEM · Senior Playbook Engine
# ─────────────────────────────────────────────

class DS:
    """Design System tokens — única fonte de verdade para o playbook."""

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

    # Editorial playbook tokens
    PAPER         = colors.HexColor("#F5F7FB")
    PAPER_2       = colors.HexColor("#EEF2F7")
    INK           = colors.HexColor("#0F172A")
    INK_2         = colors.HexColor("#1E293B")
    INK_3         = colors.HexColor("#475569")
    MUTED         = colors.HexColor("#94A3B8")

    CALLOUT_BG     = colors.HexColor("#ECFEFF")
    CALLOUT_BORDER = colors.HexColor("#99F6E4")
    ACTION_BG      = colors.HexColor("#FFFFFF")
    ACTION_BORDER  = colors.HexColor("#DCE7F2")
    SHADOW         = colors.Color(0, 0, 0, alpha=0.08)

    ALERT_BG      = colors.HexColor("#FFFBEB")
    ALERT_BORDER  = colors.HexColor("#F59E0B")
    ALERT_TEXT    = colors.HexColor("#92400E")

    # Semantic colors by step type: (fg_hex, bg_hex, label)
    TYPE_COLORS = {
        "navigation":   ("#3B82F6", "#EFF6FF", "Navegação"),
        "form_fill":    ("#8B5CF6", "#F5F3FF", "Formulário"),
        "confirmation": ("#10B981", "#ECFDF5", "Confirmação"),
        "creation":     ("#F59E0B", "#FFFBEB", "Criação"),
        "deletion":     ("#EF4444", "#FEF2F2", "Exclusão"),
    }

    PESO_COLORS = {
        3: colors.HexColor("#009999"),
        2: colors.HexColor("#3B82F6"),
        1: colors.HexColor("#94A3B8"),
    }
    PESO_LABELS = {3: "Professor", 2: "Guia", 1: "Músculo"}

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

    # Spacing
    S1, S2, S3, S4, S5, S6, S8 = 4, 8, 12, 16, 24, 32, 48

    # Radius
    R_CARD = 12
    R_SOFT = 18

    # Geometry
    PW, PH = landscape(A4)
    MARGIN = 26 * mm
    HEADER_H = 13 * mm
    FOOTER_H = 7.5 * mm
    CW = PW - 2 * MARGIN
    CH = PH - MARGIN - HEADER_H - FOOTER_H - 6 * mm


# ─────────────────────────────────────────────
# TYPOGRAPHY
# ─────────────────────────────────────────────

def register_brand_fonts() -> None:
    """
    Registra fontes customizadas se existirem.
    Tenta Inter/Geist em assets/fonts e cai para Helvetica quando ausentes.
    """
    font_dir = Path("assets/fonts")
    candidates = {
        "Brand-Regular": [
            font_dir / "Inter-Regular.ttf",
            font_dir / "Geist-Regular.ttf",
        ],
        "Brand-Medium": [
            font_dir / "Inter-Medium.ttf",
            font_dir / "Geist-Medium.ttf",
        ],
        "Brand-Semibold": [
            font_dir / "Inter-SemiBold.ttf",
            font_dir / "Geist-SemiBold.ttf",
            font_dir / "Inter-Semibold.ttf",
        ],
        "Brand-Bold": [
            font_dir / "Inter-Bold.ttf",
            font_dir / "Geist-Bold.ttf",
        ],
    }
    registered = set(pdfmetrics.getRegisteredFontNames())
    for font_name, paths in candidates.items():
        if font_name in registered:
            continue
        for path in paths:
            if path.exists():
                try:
                    pdfmetrics.registerFont(TTFont(font_name, str(path)))
                    break
                except Exception:
                    pass


def F(weight: str = "regular") -> str:
    mapping = {
        "regular": "Brand-Regular",
        "medium": "Brand-Medium",
        "semibold": "Brand-Semibold",
        "bold": "Brand-Bold",
    }
    desired = mapping.get(weight, "Brand-Regular")
    registered = set(pdfmetrics.getRegisteredFontNames())
    if desired in registered:
        return desired
    fallback = {
        "regular": "Helvetica",
        "medium": "Helvetica",
        "semibold": "Helvetica-Bold",
        "bold": "Helvetica-Bold",
    }
    return fallback.get(weight, "Helvetica")


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def hx(hex_str: str) -> colors.HexColor:
    return colors.HexColor(hex_str)


def truncate(text: str, n: int) -> str:
    if not text:
        return ""
    return text[:n] + "…" if len(text) > n else text


def step_meta(tipo: str):
    return DS.TYPE_COLORS.get(
        tipo, ("#64748B", "#F1F5F9", tipo.replace("_", " ").title())
    )


def rounded_rect(c, x, y, w, h, r=4, fill=None, stroke=None, sw=0.5):
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw)
    c.roundRect(x, y, w, h, r, fill=1 if fill else 0, stroke=1 if stroke else 0)


def shadow(c, x, y, w, h, r=4, off=2, alpha=0.10):
    rounded_rect(c, x + off, y - off, w, h, r, fill=colors.Color(0, 0, 0, alpha=alpha))


def multiline(c, text, x, y, font, size, color, max_w, lh, max_lines=None):
    """Word-wrap + draw text; returns final y."""
    text = (text or "").strip()
    if not text:
        return y
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


def draw_chip(c, x, y, text, *, fill, text_color, font="semibold", size=8.5, pad_x=10, h=18):
    w = c.stringWidth(text, F(font), size) + pad_x * 2
    rounded_rect(c, x, y, w, h, r=h / 2, fill=fill, stroke=None)
    c.setFillColor(text_color)
    c.setFont(F(font), size)
    c.drawString(x + pad_x, y + 5.2, text)
    return w


def draw_aura_callout(c, x, y, w, title, body, *, variant="info"):
    palette = {
        "info": {
            "bg": DS.CALLOUT_BG,
            "border": DS.CALLOUT_BORDER,
            "title": DS.PRIMARY_DARK,
            "body": DS.INK_2,
            "badge_bg": hx("#CCFBF1"),
        },
        "attention": {
            "bg": DS.ALERT_BG,
            "border": DS.ALERT_BORDER,
            "title": DS.ALERT_TEXT,
            "body": DS.INK_2,
            "badge_bg": hx("#FEF3C7"),
        },
        "success": {
            "bg": hx("#ECFDF5"),
            "border": hx("#86EFAC"),
            "title": hx("#166534"),
            "body": DS.INK_2,
            "badge_bg": hx("#DCFCE7"),
        },
    }[variant]

    est_chars = max(26, int(w / 8.5))
    body_lines = textwrap.wrap((body or "").strip(), width=est_chars)[:4]
    h = 54 + len(body_lines) * 14

    rounded_rect(c, x, y - h, w, h, r=14, fill=palette["bg"], stroke=palette["border"], sw=0.8)
    badge_w = 54
    rounded_rect(c, x + 12, y - 26, badge_w, 18, r=9, fill=palette["badge_bg"], stroke=None)

    c.setFillColor(palette["title"])
    c.setFont(F("bold"), 8.5)
    c.drawCentredString(x + 12 + badge_w / 2, y - 20.6, "AURA")

    c.setFillColor(palette["title"])
    c.setFont(F("semibold"), 11)
    c.drawString(x + 12, y - 42, title)

    multiline(
        c, body or "", x + 12, y - 57, F("regular"), 10,
        palette["body"], w - 24, 13, max_lines=4
    )
    return h


def draw_metric_card(c, x, y, w, h, label, value, *, accent=DS.PRIMARY):
    shadow(c, x, y, w, h, r=14, off=3, alpha=0.10)
    rounded_rect(c, x, y, w, h, r=14, fill=DS.WHITE, stroke=DS.BORDER, sw=0.7)

    c.setFillColor(DS.MUTED)
    c.setFont(F("semibold"), 8.5)
    c.drawString(x + 14, y + h - 18, label.upper())

    c.setFillColor(DS.INK)
    c.setFont(F("bold"), 18)
    c.drawString(x + 14, y + h - 42, str(value))

    c.setFillColor(accent)
    c.rect(x + 14, y + 12, 32, 4, fill=1, stroke=0)


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


def _classificar_alvo(coords: dict, img_w: int, img_h: int) -> str:
    """
    Classifica o alvo para escolher o modo de composição correto.
    Retorna: 'contextual' | 'focado' | 'detalhe'
    """
    if not coords:
        return "contextual"

    tw_pct = coords.get("w_pct", 0.05)
    th_pct = coords.get("h_pct", 0.05)
    area_pct = tw_pct * th_pct  # área relativa do alvo na tela

    # Alvo grande (botão largo, área de formulário, navegação principal)
    if area_pct > 0.015 or tw_pct > 0.25 or th_pct > 0.15:
        return "contextual"

    # Alvo médio (botão normal, campo de texto, item de menu)
    if area_pct > 0.003 or tw_pct > 0.08 or th_pct > 0.06:
        return "focado"

    # Alvo pequeno (ícone, checkbox, link, elemento periférico)
    return "detalhe"


def _compor_cena(
    img: PILImage.Image,
    coords: dict,
    modo: str,
) -> PILImage.Image:
    """
    Compõe a cena de acordo com o modo escolhido.
    Retorna a imagem processada (spotlight + crop).

    Modos:
    - contextual: mostra mais interface, spotlight leve, crop amplo
    - focado: alvo em escala relevante, contexto preservado, spotlight médio
    - detalhe: aproxima o alvo, evita área morta, spotlight sutil
    """
    img_w, img_h = img.size
    img_rgba = img.convert("RGBA")

    cx = coords.get("x_pct", 0.5) * img_w
    cy = coords.get("y_pct", 0.5) * img_h
    tw = max(20, coords.get("w_pct", 0.05) * img_w)
    th = max(20, coords.get("h_pct", 0.05) * img_h)

    # ── Parâmetros por modo ───────────────────────────────────────────────
    if modo == "contextual":
        # Mostra a interface quase inteira, spotlight muito leve
        overlay_alpha = 35          # ~14% — quase imperceptível
        clear_pad = max(tw, th) * 1.2
        crop_w = int(img_w * 0.85)
        crop_h = int(img_h * 0.85)
        corner_radius = 10
        glow_alpha = 80
        glow_width = 4

    elif modo == "focado":
        # Alvo ocupa ~35% do crop, contexto suficiente ao redor
        overlay_alpha = 50          # ~20%
        clear_pad = max(tw, th) * 1.8
        crop_w = max(int(tw * 5), int(img_w * 0.55))
        crop_h = max(int(th * 5), int(img_h * 0.55))
        corner_radius = 12
        glow_alpha = 90
        glow_width = 5

    else:  # detalhe
        # Aproxima o alvo, mas preserva contexto mínimo legível
        overlay_alpha = 45          # ~18%
        clear_pad = max(tw, th) * 2.5
        crop_w = max(int(tw * 8), int(img_w * 0.40))
        crop_h = max(int(th * 8), int(img_h * 0.40))
        corner_radius = 10
        glow_alpha = 100
        glow_width = 5

    # Limita crop ao tamanho da imagem
    crop_w = min(crop_w, img_w)
    crop_h = min(crop_h, img_h)

    # ── Janela de foco (área "clara" no overlay) ──────────────────────────
    left   = max(0, int(cx - tw / 2 - clear_pad))
    top    = max(0, int(cy - th / 2 - clear_pad))
    right  = min(img_w, int(cx + tw / 2 + clear_pad))
    bottom = min(img_h, int(cy + th / 2 + clear_pad))

    # ── Overlay sutil ─────────────────────────────────────────────────────
    dark_overlay = PILImage.new("RGBA", img.size, (10, 18, 30, overlay_alpha))
    mask = PILImage.new("L", img.size, 255)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([left, top, right, bottom], radius=corner_radius, fill=0)
    dark_overlay.putalpha(mask)
    composed = PILImage.alpha_composite(img_rgba, dark_overlay)

    # ── Glow teal sutil ───────────────────────────────────────────────────
    glow_mask = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_mask)
    glow_draw.rounded_rectangle(
        [left - 4, top - 4, right + 4, bottom + 4],
        radius=corner_radius + 3,
        outline=(0, 153, 153, glow_alpha),
        width=glow_width,
    )
    glow_mask = glow_mask.filter(ImageFilter.GaussianBlur(radius=2))
    composed = PILImage.alpha_composite(composed, glow_mask)

    # ── Contorno limpo ────────────────────────────────────────────────────
    contour = PILImage.new("RGBA", img.size, (0, 0, 0, 0))
    contour_draw = ImageDraw.Draw(contour)
    contour_draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=corner_radius,
        outline=(255, 255, 255, 160),
        width=2,
    )
    composed = PILImage.alpha_composite(composed, contour)

    # ── Crop centrado no alvo ─────────────────────────────────────────────
    crop_left = int(cx - crop_w / 2)
    crop_top  = int(cy - crop_h / 2)
    crop_right  = crop_left + crop_w
    crop_bottom = crop_top  + crop_h

    # Ajuste de borda sem faixas pretas
    if crop_left < 0:
        crop_right -= crop_left; crop_left = 0
    if crop_top < 0:
        crop_bottom -= crop_top; crop_top = 0
    if crop_right > img_w:
        crop_left -= (crop_right - img_w); crop_right = img_w
    if crop_bottom > img_h:
        crop_top -= (crop_bottom - img_h); crop_bottom = img_h

    crop_left = max(0, crop_left)
    crop_top  = max(0, crop_top)

    # ── Validação de integridade do crop ─────────────────────────────────
    # Se o crop ficou muito estreito ou muito alto (interface cortada),
    # faz fallback para mostrar a imagem inteira com spotlight leve.
    crop_actual_w = crop_right - crop_left
    crop_actual_h = crop_bottom - crop_top
    aspect = crop_actual_w / max(crop_actual_h, 1)

    # Aspect ratio muito fora do normal (< 0.5 ou > 4) indica crop quebrado
    if aspect < 0.5 or aspect > 4.0 or crop_actual_w < 200 or crop_actual_h < 150:
        # Fallback: imagem inteira com overlay mínimo
        return composed.convert("RGB")

    cropped = composed.crop((crop_left, crop_top, crop_right, crop_bottom))
    return cropped.convert("RGB")


def processar_imagem_com_zoom(
    b64_str: str,
    coords: dict,
    *,
    # Parâmetros mantidos para compatibilidade de assinatura, mas ignorados
    # — a lógica agora é controlada pelos modos de composição internos.
    overlay_alpha: int = 50,
    glow_padding: int = 48,
    corner_radius: int = 12,
) -> PILImage.Image | None:
    """
    Ponto de entrada para composição do hero visual.
    Classifica o alvo e delega para _compor_cena com o modo correto.
    """
    if not b64_str:
        return None
    try:
        img = PILImage.open(BytesIO(base64.b64decode(b64_str))).convert("RGBA")
        img_w, img_h = img.size

        modo = _classificar_alvo(coords, img_w, img_h)
        return _compor_cena(img, coords, modo)

    except Exception as e:
        print(f"[pdf_builder] erro ao processar imagem: {e}")
        try:
            return PILImage.open(BytesIO(base64.b64decode(b64_str))).convert("RGB")
        except Exception:
            return None


# ─────────────────────────────────────────────
# PDF BUILDER
# ─────────────────────────────────────────────

class PDFBuilder:

    def __init__(self, roteiro: dict, pasta: str = "documentacao_pdf"):
        self.roteiro = roteiro
        self.meta = roteiro.get("metadata", {})
        self.passos = roteiro.get("passos", [])
        self.pasta = pasta
        os.makedirs(pasta, exist_ok=True)
        register_brand_fonts()

        nome = limpar_nome(self.meta.get("id_treinamento") or self.meta.get("nome_aula", "Treinamento"))
        self.out_path = os.path.join(pasta, f"{nome}_Playbook.pdf")

        self.n_passos = len([p for p in self.passos if not p.get("is_conclusao")])
        self.n_acoes = sum(
            len(p.get("ids_acoes_tecnicas", p.get("acoes_tecnicas", [])))
            for p in self.passos
        )
        self.data = datetime.now().strftime("%d/%m/%Y")

    # ─── Header ──────────────────────────────────────────────────────────────
    def _header(self, c, step_n=0, total=0):
        pw, ph, hh = DS.PW, DS.PH, DS.HEADER_H
        c.setFillColor(DS.PAPER)
        c.rect(0, ph - hh, pw, hh, fill=1, stroke=0)
        c.setStrokeColor(DS.BORDER)
        c.setLineWidth(0.5)
        c.line(DS.MARGIN, ph - hh, pw - DS.MARGIN, ph - hh)

        c.setFillColor(DS.INK_3)
        c.setFont(F("semibold"), 8.5)
        c.drawString(DS.MARGIN, ph - 22, "Senior Playbook Engine")

        c.setFillColor(DS.MUTED)
        c.setFont(F("regular"), 8.5)
        c.drawRightString(
            DS.PW - DS.MARGIN,
            ph - 22,
            truncate(self.meta.get("titulo", self.meta.get("nome_aula", "Playbook")), 58),
        )

        # Indicador de progresso — só nas páginas de cena
        if step_n and total:
            label = f"{step_n} / {total}"
            lw = c.stringWidth(label, F("medium"), 8)
            rx = DS.PW - DS.MARGIN
            c.setFont(F("medium"), 8)
            c.setFillColor(DS.MUTED)
            c.drawString(rx - lw, ph - hh + 5, label)
            # Barra de progresso fina
            bar_w = 60
            bar_x = rx - lw - bar_w - 8
            c.setFillColor(DS.BORDER)
            c.rect(bar_x, ph - hh + 7, bar_w, 2, fill=1, stroke=0)
            c.setFillColor(DS.PRIMARY)
            c.rect(bar_x, ph - hh + 7, bar_w * step_n / total, 2, fill=1, stroke=0)

    # ─── Footer ──────────────────────────────────────────────────────────────
    def _footer(self, c, pg, total):
        pw, fh = DS.PW, DS.FOOTER_H
        c.setFillColor(DS.PAPER)
        c.rect(0, 0, pw, fh, fill=1, stroke=0)
        c.setStrokeColor(DS.BORDER)
        c.setLineWidth(0.4)
        c.line(DS.MARGIN, fh, pw - DS.MARGIN, fh)

        c.setFont(F("regular"), 7)
        c.setFillColor(DS.MUTED)
        c.drawString(DS.MARGIN, fh - 5, f"Gerado em {self.data}")

        titulo = truncate(self.meta.get("titulo", self.meta.get("nome_aula", "")), 58)
        tw = c.stringWidth(titulo, F("regular"), 7)
        c.drawString((pw - tw) / 2, fh - 5, titulo)

        pg_label = f"{pg} / {total}"
        plw = c.stringWidth(pg_label, F("regular"), 7)
        c.drawString(pw - DS.MARGIN - plw, fh - 5, pg_label)

    # ─── Cover ───────────────────────────────────────────────────────────────
    def _cover(self, c):
        pw, ph = DS.PW, DS.PH
        title = self.meta.get("nome_aula", self.meta.get("titulo", "Playbook Operacional"))
        module_name = self.meta.get("modulo", "Senior Training OS")
        subtitle = self.meta.get(
            "descricao_curta",
            "Aprendizado operacional guiado para execução com confiança."
        )

        c.setFillColor(DS.DARK)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        for radius, alpha in [(360, 0.05), (260, 0.05), (160, 0.04)]:
            c.setFillColor(colors.Color(0.0, 0.75, 0.75, alpha=alpha))
            c.circle(pw - 40, ph - 20, radius, fill=1, stroke=0)

        c.setFillColor(DS.PRIMARY)
        c.rect(0, 0, 7, ph, fill=1, stroke=0)

        c.setFillColor(DS.PRIMARY)
        c.setFont(F("bold"), 16)
        c.drawString(DS.MARGIN, ph - 48, "SENIOR")
        c.setFillColor(hx("#A5B4C3"))
        c.setFont(F("medium"), 16)
        c.drawString(DS.MARGIN + 70, ph - 48, "Playbook Engine")

        kicker_y = ph - 110
        c.setFillColor(hx("#7DD3FC"))
        c.setFont(F("semibold"), 10)
        c.drawString(DS.MARGIN, kicker_y, "PLAYBOOK OPERACIONAL")

        title_y = kicker_y - 36
        c.setFillColor(DS.WHITE)
        c.setFont(F("bold"), 28)
        title_lines = textwrap.wrap(title, width=28)[:3]
        for line in title_lines:
            c.drawString(DS.MARGIN, title_y, line)
            title_y -= 34

        c.setFillColor(hx("#CBD5E1"))
        c.setFont(F("regular"), 13)
        for line in textwrap.wrap(subtitle, width=54)[:3]:
            c.drawString(DS.MARGIN, title_y - 10, line)
            title_y -= 20

        card_x = DS.MARGIN
        card_y = 54
        card_w = 255
        card_h = 98
        rounded_rect(
            c, card_x, card_y, card_w, card_h,
            r=DS.R_CARD,
            fill=colors.Color(1, 1, 1, alpha=0.06),
            stroke=colors.Color(1, 1, 1, alpha=0.12),
            sw=0.8,
        )

        c.setFillColor(DS.WHITE)
        c.setFont(F("semibold"), 10)
        c.drawString(card_x + 16, card_y + card_h - 22, "MÓDULO")
        c.drawString(card_x + 16, card_y + card_h - 48, "CENAS")
        c.drawString(card_x + 16, card_y + card_h - 74, "AÇÕES")

        c.setFillColor(hx("#94A3B8"))
        c.setFont(F("regular"), 10)
        c.drawRightString(card_x + card_w - 16, card_y + card_h - 22, truncate(module_name, 34))
        c.drawRightString(card_x + card_w - 16, card_y + card_h - 48, str(self.n_passos))
        c.drawRightString(card_x + card_w - 16, card_y + card_h - 74, str(self.n_acoes))

        c.setFillColor(hx("#64748B"))
        c.setFont(F("regular"), 9)
        c.drawRightString(pw - DS.MARGIN, 34, f"Gerado em {self.data}")

    # ─── Table of contents ───────────────────────────────────────────────────
    def _toc(self, c, pg, total_pg):
        pw, ph = DS.PW, DS.PH
        # Apenas passos regulares — consistente com capa e header
        passos = [p for p in (self.passos or []) if not p.get("is_conclusao")]

        c.setFillColor(DS.PAPER)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)
        self._header(c)
        self._footer(c, pg, total_pg)

        top_y = ph - DS.HEADER_H - 14
        c.setFillColor(DS.INK)
        c.setFont(F("bold"), 24)
        c.drawString(DS.MARGIN, top_y, "Mapa do Playbook")

        desc = (
            "Uma visão rápida da jornada operacional que será praticada. "
            "Use este mapa como orientação antes de entrar nas cenas."
        )
        multiline(
            c, desc, DS.MARGIN, top_y - 18, F("regular"), 11,
            DS.INK_3, DS.CW * 0.52, 15, max_lines=3
        )

        metric_y = top_y - 78
        card_w = 92
        card_h = 56
        passos_count = len(passos)
        acoes_count = self.n_acoes
        peso_alto = sum(1 for p in passos if p.get("peso_narrativo", 2) >= 3)
        peso_medio = sum(1 for p in passos if p.get("peso_narrativo", 2) == 2)

        draw_metric_card(c, DS.MARGIN, metric_y, card_w, card_h, "Cenas", passos_count, accent=DS.PRIMARY)
        draw_metric_card(c, DS.MARGIN + 102, metric_y, card_w, card_h, "Ações", acoes_count, accent=hx("#3B82F6"))
        draw_metric_card(c, DS.MARGIN + 204, metric_y, card_w, card_h, "Guia", peso_medio, accent=hx("#8B5CF6"))
        draw_metric_card(c, DS.MARGIN + 306, metric_y, card_w, card_h, "Professor", peso_alto, accent=hx("#10B981"))

        draw_aura_callout(
            c,
            pw - DS.MARGIN - 260,
            top_y - 4,
            260,
            "Como usar este material",
            "Leia o contexto, observe a cena destacada e use a validação no fim de cada página para confirmar o entendimento.",
            variant="info",
        )

        list_top = metric_y - 26
        row_h = 30
        start_x = DS.MARGIN + 10
        dot_x = start_x + 8
        text_x = start_x + 28
        page_x = pw - DS.MARGIN - 18

        max_rows = max(1, int((list_top - 48) / row_h))
        shown = passos[:max_rows]

        if shown:
            c.setStrokeColor(hx("#CBD5E1"))
            c.setLineWidth(1.5)
            c.line(dot_x, list_top - 14, dot_x, list_top - (len(shown) - 1) * row_h - 12)

        for idx, passo in enumerate(shown, start=1):
            y = list_top - (idx - 1) * row_h
            tipo = passo.get("tipo_passo", "navigation")
            fg_hex, bg_hex, lbl = step_meta(tipo)
            fg = hx(fg_hex)
            bg = hx(bg_hex)

            c.setFillColor(fg)
            c.circle(dot_x, y - 8, 4.2, fill=1, stroke=0)

            label = passo.get("pedagogia", {}).get("ancora") or passo.get("titulo") or f"Passo {idx}"
            label = truncate(label, 82)
            c.setFillColor(DS.INK)
            c.setFont(F("semibold"), 10.5)
            c.drawString(text_x, y - 4.5, label)

            draw_chip(c, text_x + 280, y - 13, lbl, fill=bg, text_color=fg, size=7.8, pad_x=8, h=16)

            page_no = idx + 2
            c.setFillColor(DS.MUTED)
            c.setFont(F("medium"), 8.5)
            c.drawRightString(page_x, y - 4.5, f"p. {page_no}")

        if len(passos) > len(shown):
            c.setFillColor(DS.MUTED)
            c.setFont(F("regular"), 8.5)
            c.drawString(DS.MARGIN, 34, f"+ {len(passos) - len(shown)} cenas adicionais seguem nas páginas seguintes.")

    # ─── Step page ───────────────────────────────────────────────────────────
    def _step(self, c, passo: dict, step_n: int, pg: int, total_pg: int):
        pw, ph = DS.PW, DS.PH
        tipo = passo.get("tipo_passo", "navigation")
        fg_hex, bg_hex, lbl = step_meta(tipo)
        fg = hx(fg_hex)
        bg = hx(bg_hex)

        peso = passo.get("peso_narrativo", 2)
        id_p = passo.get("id_passo", step_n)

        ancora = passo.get("pedagogia", {}).get("ancora", "") or "Executamos este passo para manter o fluxo correto."
        tooltip = passo.get("pedagogia", {}).get("tooltip_dap", "")
        alerta = passo.get("alerta_instrutor")
        acoes = passo.get("acoes_tecnicas", [])
        ids_t = passo.get("ids_acoes_tecnicas", [])

        c.setFillColor(DS.PAPER)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        self._header(c, step_n, self.n_passos)
        self._footer(c, pg, total_pg)

        # ── Grid vertical fixo ────────────────────────────────────────────
        # Reservas: header=HEADER_H, footer=FOOTER_H
        # Zona útil: de FOOTER_H+8 até ph-HEADER_H-8
        FOOTER_SAFE = DS.FOOTER_H + 10   # margem acima do footer
        HEADER_SAFE = ph - DS.HEADER_H - 10

        # Bloco textual superior: badges + título + âncora + tooltip
        # Altura reservada: 90pt (suficiente para 3 linhas de âncora + tooltip)
        TEXT_BLOCK_H = 88
        text_top = HEADER_SAFE          # começa logo abaixo do header
        text_bot = text_top - TEXT_BLOCK_H

        # Faixa de validação/alerta: 28pt acima do footer
        VALIDATION_H = 28
        validation_top = FOOTER_SAFE + VALIDATION_H

        # Hero visual: ocupa o espaço entre bloco textual e faixa de validação
        HERO_GAP = 8                    # respiro entre texto e hero, e hero e validação
        hero_y = validation_top + HERO_GAP
        hero_h = text_bot - HERO_GAP - hero_y
        hero_x = DS.MARGIN
        hero_w = DS.CW

        # ── Bloco textual superior ────────────────────────────────────────
        # Badges de tipo e passo (linha única, compacta)
        badge_y = text_top - 18
        rounded_rect(c, DS.MARGIN, badge_y, 68, 18, r=9, fill=fg, stroke=None)
        c.setFillColor(DS.WHITE)
        c.setFont(F("bold"), 8)
        c.drawCentredString(DS.MARGIN + 34, badge_y + 5.5, f"CENA {step_n}")

        rounded_rect(c, DS.MARGIN + 76, badge_y, 100, 18, r=9, fill=bg, stroke=None)
        c.setFillColor(fg)
        c.setFont(F("semibold"), 8)
        c.drawCentredString(DS.MARGIN + 76 + 50, badge_y + 5.5, lbl.upper())

        # Âncora pedagógica
        ancora_y = badge_y - 10
        if peso == 3:
            a_font, a_size, a_lines = F("bold"), 13, 3
        elif peso == 2:
            a_font, a_size, a_lines = F("semibold"), 12, 3
        else:
            a_font, a_size, a_lines = F("regular"), 11, 2

        ancora_y = multiline(
            c, ancora, DS.MARGIN, ancora_y, a_font, a_size,
            DS.INK_2, DS.CW * 0.70, a_size * 1.4, max_lines=a_lines
        )

        # Tooltip Aura (chip compacto, só se existir)
        if tooltip:
            chip_txt = f"Aura  •  {truncate(tooltip, 72)}"
            chip_w = min(c.stringWidth(chip_txt, F("semibold"), 8) + 20, DS.CW * 0.55)
            chip_y = ancora_y - 6
            rounded_rect(
                c, DS.MARGIN, chip_y - 14, chip_w, 16,
                r=8, fill=DS.CALLOUT_BG, stroke=DS.CALLOUT_BORDER, sw=0.5
            )
            c.setFillColor(DS.PRIMARY_DARK)
            c.setFont(F("semibold"), 8)
            c.drawString(DS.MARGIN + 10, chip_y - 8, chip_txt)

        # ── Hero visual ───────────────────────────────────────────────────
        shadow(c, hero_x, hero_y, hero_w, hero_h, r=DS.R_SOFT, off=3, alpha=0.07)
        rounded_rect(c, hero_x, hero_y, hero_w, hero_h, r=DS.R_SOFT, fill=DS.WHITE, stroke=DS.BORDER, sw=0.6)

        # Chrome bar (dots de janela)
        chrome_h = 18
        rounded_rect(c, hero_x, hero_y + hero_h - chrome_h, hero_w, chrome_h, r=DS.R_SOFT, fill=DS.PAPER_2, stroke=None)
        for dot_x, dot_color in [(hero_x + 14, "#F87171"), (hero_x + 24, "#FBBF24"), (hero_x + 34, "#34D399")]:
            c.setFillColor(hx(dot_color))
            c.circle(dot_x, hero_y + hero_h - 9, 2.8, fill=1, stroke=0)

        # Screenshot com spotlight
        screenshot = None
        first_coords = {}
        for ac in acoes:
            b64 = ac.get("elemento_alvo", {}).get("screenshot_referencia")
            coords = ac.get("elemento_alvo", {}).get("coordenadas_relativas", {})
            if b64:
                screenshot = processar_imagem_com_zoom(b64, coords)
                first_coords = coords
                if screenshot:
                    break

        img_pad = 12
        imax_w = hero_w - 2 * img_pad
        imax_h = hero_h - chrome_h - 2 * img_pad

        if screenshot:
            rl = pil_to_rl(screenshot, imax_w, imax_h)
            if rl:
                ix = hero_x + (hero_w - rl.drawWidth) / 2
                iy = hero_y + img_pad + (imax_h - rl.drawHeight) / 2
                rl.drawOn(c, ix, iy)
        else:
            rounded_rect(
                c, hero_x + img_pad, hero_y + img_pad,
                imax_w, imax_h, r=10, fill=DS.PAPER_2, stroke=None,
            )
            c.setFillColor(DS.MUTED)
            c.setFont(F("medium"), 10)
            c.drawCentredString(hero_x + hero_w / 2, hero_y + hero_h / 2 - 5, "Screenshot indisponível para este passo")

        # ── Card de ação — posição heurística baseada no alvo ────────────
        # Evita cobrir a área mais útil da interface.
        # Heurística: se alvo está à esquerda (x < 0.5), card vai à direita e vice-versa.
        # Se alvo está embaixo (y > 0.6), card sobe. Caso contrário, fica no topo.
        x_pct = first_coords.get("x_pct", 0.5) if first_coords else 0.5
        y_pct = first_coords.get("y_pct", 0.5) if first_coords else 0.5

        card_w = min(210, hero_w * 0.26)
        card_h = 76
        card_margin = 12

        if x_pct < 0.5:
            # Alvo à esquerda → card à direita
            card_x = hero_x + hero_w - card_w - card_margin
        else:
            # Alvo à direita → card à esquerda
            card_x = hero_x + card_margin

        if y_pct > 0.6:
            # Alvo embaixo → card no topo
            card_y = hero_y + hero_h - chrome_h - card_h - card_margin
        else:
            # Alvo no topo ou centro → card no topo do lado oposto
            card_y = hero_y + card_margin

        # Fundo semi-opaco para não bloquear a UI
        rounded_rect(
            c, card_x, card_y, card_w, card_h, r=12,
            fill=colors.Color(1, 1, 1, alpha=0.93),
            stroke=DS.ACTION_BORDER, sw=0.6
        )

        c.setFillColor(DS.INK_3)
        c.setFont(F("semibold"), 7.5)
        c.drawString(card_x + 12, card_y + card_h - 14, "AÇÃO PRINCIPAL")

        c.setStrokeColor(DS.BORDER)
        c.setLineWidth(0.4)
        c.line(card_x + 12, card_y + card_h - 18, card_x + card_w - 12, card_y + card_h - 18)

        action_text = None
        if acoes and isinstance(acoes[0], dict):
            action_text = acoes[0].get("micro_narracao") or None
            if not action_text:
                lbl_curto = acoes[0].get("elemento_alvo", {}).get("label_curto")
                action_text = f"Interaja com {lbl_curto}" if lbl_curto else None
        action_text = action_text or "Observe a área destacada e avance."

        multiline(
            c, action_text, card_x + 12, card_y + card_h - 30,
            F("semibold"), 9.5, DS.INK, card_w - 24, 12, max_lines=3
        )

        # ── Faixa de validação/alerta ─────────────────────────────────────
        # Posicionada entre o hero e o footer, com respiro garantido
        val_y = FOOTER_SAFE + 6

        if alerta:
            alert_w = DS.CW * 0.52
            rounded_rect(
                c, DS.MARGIN, val_y, alert_w, 22,
                r=8, fill=DS.ALERT_BG, stroke=DS.ALERT_BORDER, sw=0.6
            )
            c.setFillColor(DS.ALERT_TEXT)
            c.setFont(F("medium"), 8.5)
            c.drawString(DS.MARGIN + 10, val_y + 7, f"Atenção: {truncate(alerta, 100)}")

        # Validação: usa micro_narracao da primeira ação como orientação real
        val_text = None
        if acoes and isinstance(acoes[0], dict):
            val_text = acoes[0].get("micro_narracao") or None
        if not val_text:
            val_text = "Confirme se a interface respondeu corretamente antes de avançar."

        c.setFillColor(DS.INK_3)
        c.setFont(F("semibold"), 8.5)
        c.drawRightString(pw - DS.MARGIN, val_y + 7, f"✓  {truncate(val_text, 95)}")

    # ─── Conclusion ──────────────────────────────────────────────────────────
    def _closing(self, c, pg: int, total_pg: int):
        pw, ph = DS.PW, DS.PH

        c.setFillColor(DS.DARK)
        c.rect(0, 0, pw, ph, fill=1, stroke=0)

        for radius, alpha in [(220, 0.06), (140, 0.05), (80, 0.04)]:
            c.setFillColor(colors.Color(0.0, 0.75, 0.75, alpha=alpha))
            c.circle(pw - 48, ph - 28, radius, fill=1, stroke=0)

        self._footer(c, pg, total_pg)

        c.setFillColor(hx("#7DD3FC"))
        c.setFont(F("semibold"), 10)
        c.drawString(DS.MARGIN, ph - 70, "ENCERRAMENTO")

        c.setFillColor(DS.WHITE)
        c.setFont(F("bold"), 28)
        c.drawString(DS.MARGIN, ph - 108, "Habilidade desbloqueada")

        nome = self.meta.get("nome_aula", self.meta.get("titulo", "Fluxo operacional"))
        resumo = f"Você concluiu o playbook “{nome}” e agora possui uma referência prática para repetir esse processo com mais confiança."
        multiline(
            c, resumo, DS.MARGIN, ph - 132, F("regular"), 12,
            hx("#CBD5E1"), DS.CW * 0.52, 17, max_lines=4
        )

        y_cards = ph - 232
        draw_metric_card(c, DS.MARGIN, y_cards, 110, 64, "Cenas", self.n_passos, accent=DS.PRIMARY)
        draw_metric_card(c, DS.MARGIN + 124, y_cards, 110, 64, "Ações", self.n_acoes, accent=hx("#3B82F6"))
        draw_metric_card(c, DS.MARGIN + 248, y_cards, 150, 64, "Status", "Concluído", accent=hx("#22C55E"))

        next_x = DS.MARGIN
        next_y = y_cards - 24
        next_w = DS.CW * 0.54
        next_h = 108

        rounded_rect(
            c, next_x, next_y - next_h, next_w, next_h,
            r=16,
            fill=colors.Color(1, 1, 1, alpha=0.06),
            stroke=colors.Color(1, 1, 1, alpha=0.10),
            sw=0.8,
        )

        c.setFillColor(DS.WHITE)
        c.setFont(F("semibold"), 11)
        c.drawString(next_x + 16, next_y - 22, "Próximos movimentos")

        bullets = [
            "Revise as cenas com maior peso narrativo para consolidar o raciocínio do fluxo.",
            "Repita a prática em ambiente seguro antes de executar em produção.",
            "Use este playbook como referência rápida nas primeiras execuções reais.",
        ]
        yy = next_y - 42
        for bullet in bullets:
            c.setFillColor(hx("#CBD5E1"))
            c.setFont(F("regular"), 10)
            c.drawString(next_x + 18, yy, "•")
            multiline(c, bullet, next_x + 30, yy + 4, F("regular"), 10, hx("#CBD5E1"), next_w - 44, 13, max_lines=2)
            yy -= 24

        draw_aura_callout(
            c,
            pw - DS.MARGIN - 270,
            ph - 84,
            270,
            "Conquista registrada",
            "Você concluiu o material principal. O próximo passo natural é praticar o fluxo em modo guiado para reforçar segurança operacional.",
            variant="success",
        )

        c.setFillColor(hx("#64748B"))
        c.setFont(F("regular"), 8.5)
        c.drawRightString(pw - DS.MARGIN, 28, "Senior Playbook Engine")

    # ─── Build ───────────────────────────────────────────────────────────────
    def build(self) -> str:
        print("\n📔 Gerando Playbook Premium...")
        print(f"   {self.n_passos} cenas  ·  {self.n_acoes} ações  ·  {self.meta.get('titulo', self.meta.get('nome_aula', ''))}")

        regular_passos = [p for p in self.passos if not p.get("is_conclusao")]
        total_pg = len(regular_passos) + 3  # capa + mapa + cenas + conclusão

        c = rl_canvas.Canvas(self.out_path, pagesize=landscape(A4))
        c.setAuthor("Senior Training OS — Aura IA")
        c.setTitle(self.meta.get("titulo", self.meta.get("nome_aula", "Playbook Senior")))
        c.setSubject(self.meta.get("modulo", "Senior Flow"))
        c.setCreator("pdf_builder.py v3.0")

        # 1 — Cover
        pg = 1
        self._cover(c)
        c.showPage()
        print("   ✓ Capa")

        # 2 — TOC / Mapa
        pg += 1
        self._toc(c, pg, total_pg)
        c.showPage()
        print(f"   ✓ Mapa do playbook ({len(self.passos)} entradas)")

        # 3 — Cenas
        for i, passo in enumerate(regular_passos, start=1):
            pg += 1
            self._step(c, passo, i, pg, total_pg)
            c.showPage()
            print(f"   ✓ Cena {passo.get('id_passo', i)}  [{passo.get('tipo_passo')}]  peso={passo.get('peso_narrativo', '?')}")

        # 4 — Closing
        pg += 1
        self._closing(c, pg, total_pg)
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
    Ponto de entrada principal.
    Lê um roteiro JSON e gera o playbook PDF premium.
    """
    with open(caminho_json, "r", encoding="utf-8") as f:
        roteiro = json.load(f)
    return PDFBuilder(roteiro, pasta_destino).build()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python pdf_builder.py <roteiro.json> [pasta_destino]")
        sys.exit(1)
    try:
        gerar_pdf(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "documentacao_pdf")
    except FileNotFoundError:
        print(f"ERRO: arquivo de roteiro não encontrado: {sys.argv[1]}")
        sys.exit(1)
    except Exception as e:
        print(f"ERRO: {e}")
        sys.exit(1)

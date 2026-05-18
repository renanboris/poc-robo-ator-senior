import io
import logging
import math
from typing import List, Optional, Dict
from PIL import Image, ImageDraw, ImageFont
from playwright.async_api import Page

logger = logging.getLogger(__name__)

async def get_som_boxes(page: Page) -> List[Dict]:
    """
    Consulta o DOM para obter bounding boxes de todos os elementos interativos visíveis.
    """
    script = """
    () => {
        const SELECTORS = [
            'button:not([disabled])',
            'a[href]',
            'input:not([type="hidden"]):not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            '[role="button"]:not([aria-disabled="true"])',
            '[role="menuitem"]',
            '[role="tab"]',
            '[role="checkbox"]',
            '[role="combobox"]',
            '[role="option"]',
            'p-button button',
            'p-dropdown .ui-dropdown-label',
            'p-checkbox .ui-chkbox-box',
            '.ui-inputswitch-slider'
        ];
        
        const elements = document.querySelectorAll(SELECTORS.join(', '));
        const boxes = [];
        const seen = new WeakSet();
        
        elements.forEach(el => {
            if (seen.has(el)) return;
            seen.add(el);
            
            // Check if descendant of aria-hidden
            let cur = el;
            let isHidden = false;
            while(cur) {
                if(cur.getAttribute && cur.getAttribute('aria-hidden') === 'true') {
                    isHidden = true;
                    break;
                }
                cur = cur.parentElement;
            }
            if (isHidden) return;
            
            const rect = el.getBoundingClientRect();
            if (rect.width >= 8 && rect.height >= 8 
                && rect.x >= 0 && rect.y >= 0 
                && rect.x + rect.width <= window.innerWidth + 20
                && rect.y + rect.height <= window.innerHeight + 20) {
                
                boxes.push({
                    x: Math.round(rect.x),
                    y: Math.round(rect.y),
                    w: Math.round(rect.width),
                    h: Math.round(rect.height),
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    label: (el.getAttribute('aria-label') || el.innerText || '').substring(0, 30).trim()
                });
            }
        });
        
        return boxes;
    }
    """
    try:
        raw_boxes = await page.evaluate(script)
        # Sort by y, then x
        raw_boxes.sort(key=lambda b: (b['y'], b['x']))
        
        # Take max 80 and assign idx
        som_boxes = []
        for idx, b in enumerate(raw_boxes[:80]):
            som_boxes.append({
                "idx": idx + 1,
                "x": b["x"],
                "y": b["y"],
                "w": b["w"],
                "h": b["h"],
                "role": b["role"],
                "label": b["label"]
            })
        return som_boxes
    except Exception as e:
        logger.warning(f"Erro em get_som_boxes: {e}")
        return []

def anotar_imagem(screenshot_bytes: bytes, boxes: List[Dict]) -> bytes:
    """
    Desenha bounding boxes numeradas na imagem usando PIL.
    """
    try:
        img = Image.open(io.BytesIO(screenshot_bytes))
        img = img.convert("RGB")
        draw = ImageDraw.Draw(img)
        
        try:
            # Pillow >= 10: load_default accepts size
            font = ImageFont.load_default(size=14)
        except TypeError:
            # Pillow < 10 fallback
            import os
            font = None
            for path in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arial.ttf"]:
                if os.path.exists(path):
                    font = ImageFont.truetype(path, 14)
                    break
            if not font:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()

        red_color = "#FF3B30"
        
        for box in boxes:
            x, y, w, h = box["x"], box["y"], box["w"], box["h"]
            idx = str(box["idx"])
            
            # Draw rectangle
            draw.rectangle([x, y, x + w, y + h], outline=red_color, width=2)
            
            # Draw badge
            # Calculate text size for badge width
            # load_default doesn't have getbbox in old PIL, fallback to getsize if needed
            # For modern Pillow (>=10), getbbox is used.
            if hasattr(font, 'getbbox'):
                bbox = font.getbbox(idx)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
            else:
                tw, th = 8 * len(idx), 11 # rough estimate
            
            badge_w = max(20, tw + 4)
            badge_h = max(14, th + 4)
            
            # Badge background
            draw.rectangle([x, y, x + badge_w, y + badge_h], fill=red_color)
            
            # Badge text
            draw.text((x + 2, y + 1), idx, fill="white", font=font)
            
        out_bytes = io.BytesIO()
        img.save(out_bytes, format="JPEG", quality=82)
        return out_bytes.getvalue()
    except Exception as e:
        logger.warning(f"Erro ao anotar imagem: {e}")
        return screenshot_bytes

def identificar_box_clicada(boxes: List[Dict], x: int, y: int) -> Optional[int]:
    """
    Dado o (x, y) do clique e a lista de boxes, retorna o idx da box.
    
    Usa uma estratégia de três fases:
    1. Matching estrito: verifica se o clique está dentro dos boundaries da box
    2. Matching com tolerância: encontra a box mais próxima dentro de uma tolerância dinâmica
    3. Fallback: retorna None se nenhuma box estiver dentro da tolerância
    
    Em caso de overlap ou múltiplos candidatos, retorna a menor (mais específica).
    """
    # Phase 1: Preserve strict matching (existing behavior)
    # If click is within box boundaries, return immediately (prioritize smallest box if multiple matches)
    strict_matches = []
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        if bx <= x <= bx + bw and by <= y <= by + bh:
            strict_matches.append(box)
    
    if strict_matches:
        # Sort by area (w * h) ascending to get the most specific
        strict_matches.sort(key=lambda b: b["w"] * b["h"])
        return strict_matches[0]["idx"]
    
    # Phase 2: Add tolerance-based matching (new behavior)
    # For each box, calculate distance to center and check if within tolerance
    tolerance_candidates = []
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        
        # Calculate distance to center
        center_x = bx + bw / 2
        center_y = by + bh / 2
        distance = math.sqrt((x - center_x)**2 + (y - center_y)**2)
        
        # Calculate dynamic tolerance: 30% of largest dimension
        tolerance = max(bw, bh) * 0.3
        
        # Collect boxes where distance <= tolerance as candidates
        if distance <= tolerance:
            tolerance_candidates.append({
                "box": box,
                "distance": distance,
                "area": bw * bh
            })
    
    if tolerance_candidates:
        # Sort candidates by distance (ascending), then by area (ascending) for tie-breaking
        tolerance_candidates.sort(key=lambda c: (c["distance"], c["area"]))
        
        # Return idx of closest box (smallest distance, smallest area if tied)
        matched_box = tolerance_candidates[0]["box"]
        matched_distance = tolerance_candidates[0]["distance"]
        
        # Add informative logging when tolerance matching is used
        logger.info(f"SoM tolerance match: click ({x}, {y}) matched box #{matched_box['idx']} at distance {matched_distance:.1f}px")
        
        return matched_box["idx"]
    
    # Phase 3: Fallback to None (preserved behavior)
    # If no candidates within tolerance, return None
    return None

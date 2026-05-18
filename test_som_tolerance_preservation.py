"""
Preservation Property Tests — som-box-matching-tolerance-fix
=============================================================
Estes testes CAPTURAM o comportamento existente no código NÃO-CORRIGIDO.

Metodologia:
  - Os testes observam e documentam o COMPORTAMENTO ATUAL para inputs não-buggy.
  - Quando os testes PASSAM no código não corrigido, significa que capturamos a baseline.
  - Após o fix, estes mesmos testes devem CONTINUAR PASSANDO (garantindo preservação).

Comportamento preservado:
  - Cliques exatamente dentro de boxes devem continuar retornando o idx correto
  - Cliques muito distantes devem continuar retornando None
  - Cliques dentro de múltiplas boxes devem continuar retornando a box com menor área

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import math
import os
import sys

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path — garante que o root do projeto está acessível
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from som_annotator import identificar_box_clicada


# ===========================================================================
# Helper Functions
# ===========================================================================

def is_bug_condition(boxes, click_x, click_y):
    """
    Retorna True quando o clique está próximo de uma box mas o matching estrito falha.
    
    Esta é a condição de bug: clique dentro de tolerância razoável mas fora dos
    boundaries estritos da box.
    """
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        
        # Verifica se o clique está dentro da box (matching estrito)
        if bx <= click_x <= bx + bw and by <= click_y <= by + bh:
            return False  # Matching estrito funciona, não é bug
        
        # Verifica se o clique está próximo da box (dentro de tolerância razoável)
        center_x = bx + bw / 2
        center_y = by + bh / 2
        distance_to_center = math.sqrt((click_x - center_x)**2 + (click_y - center_y)**2)
        max_dimension = max(bw, bh)
        tolerance = max_dimension * 0.3  # 30% da maior dimensão
        
        if distance_to_center <= tolerance:
            return True  # Clique próximo mas matching estrito falhou = BUG
    
    return False  # Clique muito distante de qualquer box, não é bug


# ===========================================================================
# Preservation Tests - Clicks Exactly Inside Boxes
# ===========================================================================

def test_preservation_click_inside_single_box():
    """
    Preservation Test: Clique exatamente dentro de uma box deve retornar o idx correto.
    
    Este teste captura o comportamento existente para cliques que estão dentro dos
    boundaries estritos de uma box.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.1
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Botão 1"},
        {"idx": 2, "x": 300, "y": 200, "w": 60, "h": 30, "role": "link", "label": "Link 1"},
    ]
    
    # Clique no centro da primeira box
    click_x, click_y = 140, 120  # Centro de box 1: (100+80/2, 100+40/2) = (140, 120)
    
    # Verifica que NÃO é uma condição de bug
    assert not is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este NÃO deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ATUAL: retornar o idx da box
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 1, (
        f"Preservation falhou: clique dentro da box ({click_x}, {click_y}) "
        f"deveria retornar idx=1 mas retornou {result}"
    )


def test_preservation_click_at_box_edge():
    """
    Preservation Test: Clique exatamente na borda de uma box deve retornar o idx correto.
    
    Este teste captura o comportamento existente para cliques que estão exatamente
    nos boundaries da box (edge case).
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.1
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Botão 1"},
    ]
    
    # Clique exatamente na borda direita da box (x = 100 + 80 = 180)
    click_x, click_y = 180, 120
    
    # Verifica que NÃO é uma condição de bug
    assert not is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este NÃO deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ATUAL: retornar o idx da box
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 1, (
        f"Preservation falhou: clique na borda da box ({click_x}, {click_y}) "
        f"deveria retornar idx=1 mas retornou {result}"
    )


@given(
    box_w=st.integers(min_value=50, max_value=200),
    box_h=st.integers(min_value=30, max_value=100),
    offset_x=st.integers(min_value=0, max_value=50),
    offset_y=st.integers(min_value=0, max_value=50),
)
@settings(max_examples=50, deadline=None)
def test_property_preservation_clicks_inside_boxes(box_w, box_h, offset_x, offset_y):
    """
    Property: Para todos os cliques exatamente dentro de uma box,
    o sistema DEVE continuar retornando o idx correto.
    
    Gera boxes e cliques aleatórios dentro dos boundaries estritos,
    verificando que o matching estrito continua funcionando.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.1
    """
    box_x, box_y = 100, 100
    boxes = [
        {"idx": 1, "x": box_x, "y": box_y, "w": box_w, "h": box_h, "role": "button", "label": "Test button"},
        {"idx": 2, "x": 500, "y": 500, "w": 80, "h": 30, "role": "button", "label": "Distant button"},
    ]
    
    # Clique dentro da box (offset_x e offset_y garantem que está dentro)
    click_x = box_x + min(offset_x, box_w)
    click_y = box_y + min(offset_y, box_h)
    
    # Verifica que NÃO é uma condição de bug
    if is_bug_condition(boxes, click_x, click_y):
        return  # Skip - este é um caso de bug condition
    
    # COMPORTAMENTO ATUAL: retornar o idx da box
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 1, (
        f"Preservation falhou: clique dentro da box ({click_x}, {click_y}) "
        f"deveria retornar idx=1 mas retornou {result}"
    )


# ===========================================================================
# Preservation Tests - Clicks Very Far From Any Box
# ===========================================================================

def test_preservation_click_very_far_from_boxes():
    """
    Preservation Test: Clique muito distante de qualquer box deve retornar None.
    
    Este teste captura o comportamento existente para cliques que estão muito
    distantes de qualquer box (fora de qualquer tolerância razoável).
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.3
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Botão 1"},
        {"idx": 2, "x": 300, "y": 200, "w": 60, "h": 30, "role": "link", "label": "Link 1"},
    ]
    
    # Clique muito distante de qualquer box
    click_x, click_y = 1000, 1000
    
    # Verifica que NÃO é uma condição de bug (muito distante)
    assert not is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este NÃO deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ATUAL: retornar None
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result is None, (
        f"Preservation falhou: clique muito distante ({click_x}, {click_y}) "
        f"deveria retornar None mas retornou {result}"
    )


@given(
    distance_multiplier=st.floats(min_value=2.0, max_value=10.0),
)
@settings(max_examples=30, deadline=None)
def test_property_preservation_clicks_far_from_boxes(distance_multiplier):
    """
    Property: Para todos os cliques muito distantes de qualquer box,
    o sistema DEVE continuar retornando None.
    
    Gera cliques aleatórios que estão muito distantes de qualquer box
    (fora de qualquer tolerância razoável), verificando que None é retornado.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.3
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Test button"},
        {"idx": 2, "x": 300, "y": 200, "w": 60, "h": 30, "role": "link", "label": "Test link"},
    ]
    
    # Calcula a maior tolerância possível entre todas as boxes
    max_tolerance = 0
    for box in boxes:
        max_dimension = max(box["w"], box["h"])
        tolerance = max_dimension * 0.3
        max_tolerance = max(max_tolerance, tolerance)
    
    # Clique muito distante (múltiplo da maior tolerância)
    # Coloca o clique à direita e abaixo de todas as boxes
    click_x = int(400 + max_tolerance * distance_multiplier)
    click_y = int(300 + max_tolerance * distance_multiplier)
    
    # Verifica que NÃO é uma condição de bug (muito distante)
    if is_bug_condition(boxes, click_x, click_y):
        return  # Skip - este é um caso de bug condition (não deveria acontecer)
    
    # COMPORTAMENTO ATUAL: retornar None
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result is None, (
        f"Preservation falhou: clique muito distante ({click_x}, {click_y}) "
        f"deveria retornar None mas retornou {result}"
    )


# ===========================================================================
# Preservation Tests - Clicks Inside Multiple Overlapping Boxes
# ===========================================================================

def test_preservation_click_inside_overlapping_boxes():
    """
    Preservation Test: Clique dentro de múltiplas boxes sobrepostas deve retornar
    a box com menor área (mais específica).
    
    Este teste captura o comportamento existente para cliques que estão dentro
    de múltiplas boxes simultaneamente.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.4
    """
    # Box 1: maior (área = 80 * 40 = 3200)
    # Box 2: menor (área = 50 * 25 = 1250)
    # Box 2 está completamente dentro de Box 1
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Botão grande"},
        {"idx": 2, "x": 110, "y": 110, "w": 50, "h": 25, "role": "button", "label": "Botão pequeno"},
    ]
    
    # Clique dentro de ambas as boxes (no centro da box menor)
    click_x, click_y = 135, 122  # Centro de box 2: (110+50/2, 110+25/2) = (135, 122.5)
    
    # Verifica que NÃO é uma condição de bug
    assert not is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este NÃO deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ATUAL: retornar a box com menor área (box 2)
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 2, (
        f"Preservation falhou: clique dentro de múltiplas boxes ({click_x}, {click_y}) "
        f"deveria retornar idx=2 (menor área) mas retornou {result}"
    )


def test_preservation_overlapping_boxes_prioritization():
    """
    Preservation Test: Quando múltiplas boxes se sobrepõem, o sistema deve
    priorizar a box com menor área.
    
    Este teste verifica que a priorização por área continua funcionando
    corretamente após o fix.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.4
    """
    # Três boxes sobrepostas com áreas diferentes
    # Box 1: área = 100 * 50 = 5000
    # Box 2: área = 70 * 35 = 2450
    # Box 3: área = 40 * 20 = 800 (menor)
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 100, "h": 50, "role": "button", "label": "Box grande"},
        {"idx": 2, "x": 110, "y": 110, "w": 70, "h": 35, "role": "button", "label": "Box média"},
        {"idx": 3, "x": 120, "y": 120, "w": 40, "h": 20, "role": "button", "label": "Box pequena"},
    ]
    
    # Clique dentro das três boxes (no centro da box menor)
    click_x, click_y = 140, 130  # Centro de box 3: (120+40/2, 120+20/2) = (140, 130)
    
    # Verifica que NÃO é uma condição de bug
    assert not is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este NÃO deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ATUAL: retornar a box com menor área (box 3)
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 3, (
        f"Preservation falhou: clique dentro de múltiplas boxes ({click_x}, {click_y}) "
        f"deveria retornar idx=3 (menor área) mas retornou {result}"
    )


@given(
    large_w=st.integers(min_value=100, max_value=200),
    large_h=st.integers(min_value=60, max_value=100),
    small_w=st.integers(min_value=40, max_value=80),
    small_h=st.integers(min_value=25, max_value=50),
)
@settings(max_examples=30, deadline=None)
def test_property_preservation_overlapping_boxes(large_w, large_h, small_w, small_h):
    """
    Property: Para todos os cliques dentro de múltiplas boxes sobrepostas,
    o sistema DEVE continuar retornando a box com menor área.
    
    Gera configurações aleatórias de boxes sobrepostas e verifica que a
    priorização por área continua funcionando.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.4
    """
    # Garante que a box pequena tem área menor que a box grande
    assume(small_w * small_h < large_w * large_h)
    
    # Box grande
    large_x, large_y = 100, 100
    # Box pequena dentro da box grande
    small_x = large_x + 10
    small_y = large_y + 10
    
    # Garante que a box pequena está completamente dentro da box grande
    assume(small_x + small_w <= large_x + large_w)
    assume(small_y + small_h <= large_y + large_h)
    
    boxes = [
        {"idx": 1, "x": large_x, "y": large_y, "w": large_w, "h": large_h, "role": "button", "label": "Large box"},
        {"idx": 2, "x": small_x, "y": small_y, "w": small_w, "h": small_h, "role": "button", "label": "Small box"},
    ]
    
    # Clique no centro da box pequena (dentro de ambas)
    click_x = small_x + small_w // 2
    click_y = small_y + small_h // 2
    
    # Verifica que NÃO é uma condição de bug
    if is_bug_condition(boxes, click_x, click_y):
        return  # Skip - este é um caso de bug condition
    
    # COMPORTAMENTO ATUAL: retornar a box com menor área (box 2)
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    assert result == 2, (
        f"Preservation falhou: clique dentro de múltiplas boxes ({click_x}, {click_y}) "
        f"deveria retornar idx=2 (menor área) mas retornou {result}"
    )


# ===========================================================================
# Comprehensive Preservation Test
# ===========================================================================

@given(
    num_boxes=st.integers(min_value=1, max_value=5),
    click_x=st.integers(min_value=0, max_value=800),
    click_y=st.integers(min_value=0, max_value=600),
)
@settings(max_examples=100, deadline=None)
def test_property_comprehensive_preservation(num_boxes, click_x, click_y):
    """
    Property: Para TODOS os inputs onde NOT isBugCondition(input),
    o comportamento DEVE ser idêntico antes e depois do fix.
    
    Este é um teste abrangente que gera muitos cenários aleatórios e verifica
    que o comportamento é preservado para todos os inputs não-buggy.
    
    **EXPECTED ON UNFIXED CODE**: Test PASSES (baseline behavior)
    **EXPECTED AFTER FIX**: Test PASSES (behavior preserved)
    
    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """
    # Gera boxes aleatórias
    boxes = []
    for i in range(num_boxes):
        box_x = (i * 150) % 700
        box_y = (i * 100) % 500
        box_w = 60 + (i * 20) % 80
        box_h = 30 + (i * 10) % 40
        boxes.append({
            "idx": i + 1,
            "x": box_x,
            "y": box_y,
            "w": box_w,
            "h": box_h,
            "role": "button",
            "label": f"Box {i+1}"
        })
    
    # Verifica se é uma condição de bug
    if is_bug_condition(boxes, click_x, click_y):
        return  # Skip - este é um caso de bug condition
    
    # COMPORTAMENTO ATUAL: captura o resultado no código não corrigido
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO PRESERVADO
    # Este teste simplesmente documenta o comportamento atual
    # Após o fix, o resultado deve ser idêntico para inputs não-buggy
    
    # Verifica consistência: se o resultado não é None, deve ser um idx válido
    if result is not None:
        assert any(box["idx"] == result for box in boxes), (
            f"Preservation falhou: resultado {result} não corresponde a nenhuma box válida"
        )
        
        # Verifica que o clique está dentro da box retornada (matching estrito)
        matched_box = next(box for box in boxes if box["idx"] == result)
        bx, by, bw, bh = matched_box["x"], matched_box["y"], matched_box["w"], matched_box["h"]
        assert bx <= click_x <= bx + bw and by <= click_y <= by + bh, (
            f"Preservation falhou: clique ({click_x}, {click_y}) não está dentro da box retornada "
            f"(idx={result}, boundaries=[{bx},{bx+bw}]x[{by},{by+bh}])"
        )

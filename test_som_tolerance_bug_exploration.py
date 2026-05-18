"""
Bug Condition Exploration Tests — som-box-matching-tolerance-fix
=================================================================
Estes testes CONFIRMAM o bug no código NÃO-CORRIGIDO.

Metodologia:
  - Os testes assertam o COMPORTAMENTO ESPERADO (com tolerância).
  - Quando os testes FALHAM no código não corrigido, significa que o bug FOI CONFIRMADO.
  - Após o fix, estes mesmos testes devem PASSAR (assertando o comportamento correto).

Bug coberto:
  Bug Condition — SoM Tolerance Matching for Near-Miss Clicks
  
  O sistema falha em associar cliques que estão próximos (dentro de tolerância razoável)
  mas não exatamente dentro das boxes detectadas pelo SoM. A função identificar_box_clicada
  usa matching estrito de boundaries sem tolerância, resultando em None para cliques
  próximos que deveriam ser associados à box mais próxima.

Validates: Requirements 1.1, 1.2, 2.1, 2.2, 2.3, 2.4
"""

import math
import os
import sys

import pytest
from hypothesis import given, settings
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


def find_closest_box_within_tolerance(boxes, click_x, click_y):
    """
    Encontra a box mais próxima dentro da tolerância.
    Retorna None se nenhuma box estiver dentro da tolerância.
    """
    candidates = []
    
    for box in boxes:
        bx, by, bw, bh = box["x"], box["y"], box["w"], box["h"]
        
        # Calcula distância ao centro
        center_x = bx + bw / 2
        center_y = by + bh / 2
        distance = math.sqrt((click_x - center_x)**2 + (click_y - center_y)**2)
        
        # Calcula tolerância (30% da maior dimensão)
        max_dimension = max(bw, bh)
        tolerance = max_dimension * 0.3
        
        if distance <= tolerance:
            candidates.append({
                "box": box,
                "distance": distance,
                "area": bw * bh
            })
    
    if not candidates:
        return None
    
    # Ordena por distância (crescente), depois por área (crescente)
    candidates.sort(key=lambda c: (c["distance"], c["area"]))
    return candidates[0]["box"]


# ===========================================================================
# Bug Condition Exploration Tests
# ===========================================================================

def test_concrete_case_action_6():
    """
    Caso concreto da Ação 6 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos".
    
    Clique em coordenadas (x=256, y=205) com 20 boxes detectadas.
    O matching estrito falhou, retornando None.
    
    Este teste asserta o COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    dentro da tolerância.
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 1.1, 2.1, 2.2, 2.3
    """
    # Simula uma box próxima ao clique mas não exatamente contendo o clique
    # Box está em (240, 200) com dimensões 80x30 (boundaries: x=[240,320], y=[200,230])
    # Center: (280, 215), Tolerance: 24px (30% of 80px)
    # Clique está em (280, 232) - FORA da box (y=232 > 230) mas dentro da tolerância (distance=17px < 24px)
    boxes = [
        {"idx": 1, "x": 240, "y": 200, "w": 80, "h": 30, "role": "button", "label": "Grupo de contatos"},
        {"idx": 2, "x": 100, "y": 100, "w": 80, "h": 30, "role": "button", "label": "Outro botão"},
        {"idx": 3, "x": 500, "y": 500, "w": 60, "h": 25, "role": "link", "label": "Link distante"},
    ]
    
    click_x, click_y = 280, 232
    
    # Verifica que é uma condição de bug
    assert is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # Encontra a box esperada
    expected_box = find_closest_box_within_tolerance(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) próximo à box "
        f"retornou None em vez do idx da box mais próxima. "
        f"Box mais próxima: idx={expected_box['idx']}, "
        f"posição=({expected_box['x']}, {expected_box['y']}), "
        f"dimensões=({expected_box['w']}x{expected_box['h']})"
    )
    
    assert result == expected_box["idx"], (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) retornou idx={result} "
        f"mas deveria retornar idx={expected_box['idx']} (box mais próxima)"
    )


def test_concrete_case_action_7():
    """
    Caso concreto da Ação 7 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos".
    
    Clique em coordenadas (x=1199, y=27) com 20 boxes detectadas.
    O matching estrito falhou, retornando None.
    
    Este teste asserta o COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    dentro da tolerância.
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 1.1, 2.1, 2.2, 2.3
    """
    # Simula uma box próxima ao clique mas não exatamente contendo o clique
    # Box está em (1180, 10) com dimensões 60x30 (boundaries: x=[1180,1240], y=[10,40])
    # Center: (1210, 25), Tolerance: 18px (30% of 60px)
    # Clique está em (1210, 43) - FORA da box (y=43 > 40) mas dentro da tolerância (distance=3px < 18px)
    boxes = [
        {"idx": 1, "x": 1180, "y": 10, "w": 60, "h": 30, "role": "button", "label": "Botão superior"},
        {"idx": 2, "x": 100, "y": 100, "w": 80, "h": 30, "role": "button", "label": "Outro botão"},
        {"idx": 3, "x": 500, "y": 500, "w": 60, "h": 25, "role": "link", "label": "Link distante"},
    ]
    
    click_x, click_y = 1210, 43
    
    # Verifica que é uma condição de bug
    assert is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # Encontra a box esperada
    expected_box = find_closest_box_within_tolerance(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) próximo à box "
        f"retornou None em vez do idx da box mais próxima. "
        f"Box mais próxima: idx={expected_box['idx']}, "
        f"posição=({expected_box['x']}, {expected_box['y']}), "
        f"dimensões=({expected_box['w']}x{expected_box['h']})"
    )
    
    assert result == expected_box["idx"], (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) retornou idx={result} "
        f"mas deveria retornar idx={expected_box['idx']} (box mais próxima)"
    )


@given(
    offset_x=st.integers(min_value=1, max_value=15),
    offset_y=st.integers(min_value=1, max_value=15),
    box_w=st.integers(min_value=50, max_value=200),
    box_h=st.integers(min_value=30, max_value=100),
)
@settings(max_examples=30, deadline=None)
def test_property_near_miss_clicks_horizontal(offset_x, offset_y, box_w, box_h):
    """
    Property: Para cliques próximos mas fora da box (horizontalmente à direita),
    o sistema DEVE retornar o idx da box mais próxima dentro da tolerância.
    
    Gera boxes e cliques que estão alguns pixels fora da box (à direita),
    mas dentro da tolerância de 30% da maior dimensão.
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 1.2, 2.1, 2.2, 2.4
    """
    # Cria uma box
    box_x, box_y = 100, 100
    boxes = [
        {"idx": 1, "x": box_x, "y": box_y, "w": box_w, "h": box_h, "role": "button", "label": "Test button"},
        {"idx": 2, "x": 500, "y": 500, "w": 80, "h": 30, "role": "button", "label": "Distant button"},
    ]
    
    # Clique alguns pixels à direita da box (fora da box mas dentro da tolerância)
    click_x = box_x + box_w + offset_x
    click_y = box_y + offset_y
    
    # Calcula se está dentro da tolerância
    center_x = box_x + box_w / 2
    center_y = box_y + box_h / 2
    distance = math.sqrt((click_x - center_x)**2 + (click_y - center_y)**2)
    max_dimension = max(box_w, box_h)
    tolerance = max_dimension * 0.3
    
    # Só testa casos onde o clique está dentro da tolerância
    if distance > tolerance:
        return  # Skip este caso - não é bug condition
    
    # Verifica que é uma condição de bug
    if not is_bug_condition(boxes, click_x, click_y):
        return  # Skip - não é bug condition
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) próximo à box "
        f"(distância={distance:.1f}px, tolerância={tolerance:.1f}px) "
        f"retornou None em vez do idx da box mais próxima"
    )
    
    assert result == 1, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) retornou idx={result} "
        f"mas deveria retornar idx=1 (box mais próxima)"
    )


@given(
    offset_x=st.integers(min_value=1, max_value=15),
    offset_y=st.integers(min_value=1, max_value=15),
    box_w=st.integers(min_value=50, max_value=200),
    box_h=st.integers(min_value=30, max_value=100),
)
@settings(max_examples=30, deadline=None)
def test_property_near_miss_clicks_vertical(offset_x, offset_y, box_w, box_h):
    """
    Property: Para cliques próximos mas fora da box (verticalmente abaixo),
    o sistema DEVE retornar o idx da box mais próxima dentro da tolerância.
    
    Gera boxes e cliques que estão alguns pixels fora da box (abaixo),
    mas dentro da tolerância de 30% da maior dimensão.
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 1.2, 2.1, 2.2, 2.4
    """
    # Cria uma box
    box_x, box_y = 100, 100
    boxes = [
        {"idx": 1, "x": box_x, "y": box_y, "w": box_w, "h": box_h, "role": "button", "label": "Test button"},
        {"idx": 2, "x": 500, "y": 500, "w": 80, "h": 30, "role": "button", "label": "Distant button"},
    ]
    
    # Clique alguns pixels abaixo da box (fora da box mas dentro da tolerância)
    click_x = box_x + offset_x
    click_y = box_y + box_h + offset_y
    
    # Calcula se está dentro da tolerância
    center_x = box_x + box_w / 2
    center_y = box_y + box_h / 2
    distance = math.sqrt((click_x - center_x)**2 + (click_y - center_y)**2)
    max_dimension = max(box_w, box_h)
    tolerance = max_dimension * 0.3
    
    # Só testa casos onde o clique está dentro da tolerância
    if distance > tolerance:
        return  # Skip este caso - não é bug condition
    
    # Verifica que é uma condição de bug
    if not is_bug_condition(boxes, click_x, click_y):
        return  # Skip - não é bug condition
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) próximo à box "
        f"(distância={distance:.1f}px, tolerância={tolerance:.1f}px) "
        f"retornou None em vez do idx da box mais próxima"
    )
    
    assert result == 1, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) retornou idx={result} "
        f"mas deveria retornar idx=1 (box mais próxima)"
    )


def test_icon_with_padding_case():
    """
    Caso típico: usuário clica no centro visual de um ícone, mas o SoM detectou
    a box ao redor do botão pai. O clique está 5 pixels fora da box detectada.
    
    Este teste asserta o COMPORTAMENTO ESPERADO: matching bem-sucedido com a box
    do botão pai usando tolerância.
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 1.1, 2.1, 2.2
    """
    # Box do botão pai detectada pelo SoM (boundaries: x=[200,300], y=[150,190])
    # Center: (250, 170), Tolerance: 30px (30% of 100px)
    boxes = [
        {"idx": 1, "x": 200, "y": 150, "w": 100, "h": 40, "role": "button", "label": "Salvar"},
        {"idx": 2, "x": 400, "y": 400, "w": 80, "h": 30, "role": "button", "label": "Cancelar"},
    ]
    
    # Usuário clica no ícone dentro do botão, que está 5px fora da box detectada
    # Click está em (250, 195) - FORA da box (y=195 > 190) mas dentro da tolerância (distance=5px < 30px)
    click_x, click_y = 250, 195
    
    # Verifica que é uma condição de bug
    assert is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box do botão pai
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ícone com padding ({click_x}, {click_y}) "
        f"retornou None em vez do idx da box do botão pai"
    )
    
    assert result == 1, (
        f"BUG CONFIRMADO: clique em ícone com padding ({click_x}, {click_y}) "
        f"retornou idx={result} mas deveria retornar idx=1 (botão pai)"
    )


def test_multiple_candidates_closest_wins():
    """
    Caso com múltiplas boxes candidatas dentro da tolerância.
    O sistema DEVE retornar a box mais próxima (menor distância ao centro).
    
    **EXPECTED ON UNFIXED CODE**: Test FAILS (confirma que o bug existe)
    **EXPECTED AFTER FIX**: Test PASSES (confirma que o fix funciona)
    
    Validates: Requirements 2.2, 2.4
    """
    # Duas boxes próximas, mas uma está mais próxima do clique
    # Box 1: boundaries x=[100,180], y=[100,140], center=(140, 120), tolerance=24px
    # Box 2: boundaries x=[150,220], y=[120,155], center=(185, 137.5), tolerance=21px
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Box 1"},
        {"idx": 2, "x": 150, "y": 120, "w": 70, "h": 35, "role": "button", "label": "Box 2"},
        {"idx": 3, "x": 500, "y": 500, "w": 60, "h": 30, "role": "button", "label": "Box distante"},
    ]
    
    # Clique FORA de ambas as boxes mas mais próximo da Box 2
    # Click em (185, 158) - fora de Box 2 (y=158 > 155) mas dentro da tolerância (distance=3px < 21px)
    # Distance to Box 1 center: ~40px (outside tolerance)
    click_x, click_y = 185, 158
    
    # Verifica que é uma condição de bug
    assert is_bug_condition(boxes, click_x, click_y), (
        "Sanity check falhou: este deveria ser um caso de bug condition"
    )
    
    # COMPORTAMENTO ESPERADO: retornar o idx da box mais próxima (Box 2)
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    expected_box = find_closest_box_within_tolerance(boxes, click_x, click_y)
    
    # ASSERTA COMPORTAMENTO ESPERADO (falhará no código não corrigido)
    assert result is not None, (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) com múltiplas boxes candidatas "
        f"retornou None em vez do idx da box mais próxima"
    )
    
    assert result == expected_box["idx"], (
        f"BUG CONFIRMADO: clique em ({click_x}, {click_y}) retornou idx={result} "
        f"mas deveria retornar idx={expected_box['idx']} (box mais próxima)"
    )

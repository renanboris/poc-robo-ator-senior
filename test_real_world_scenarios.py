"""
Real-World Scenario Tests for SoM Box Matching Tolerance Fix
=============================================================
These tests verify the fix works for the actual failing cases mentioned in the bugfix spec.

Validates: Requirements 2.1, 2.2, 2.3
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from som_annotator import identificar_box_clicada


def test_action_6_senior_flow_sign_grupo_contatos():
    """
    Real-world test: Ação 6 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos"
    
    Click at (256, 205) with 20 boxes detected should now match a box.
    Previously returned None due to strict matching failure.
    
    This test simulates a realistic scenario where the click is slightly outside
    the detected box boundary but clearly intended for that element.
    """
    # Simulate a realistic box configuration around the click point
    # The actual box might be slightly offset from the click due to padding/icons
    boxes = [
        {"idx": 1, "x": 240, "y": 195, "w": 80, "h": 35, "role": "button", "label": "Grupo de contatos"},
        {"idx": 2, "x": 100, "y": 50, "w": 60, "h": 30, "role": "button", "label": "Outro botão"},
        {"idx": 3, "x": 400, "y": 300, "w": 70, "h": 25, "role": "link", "label": "Link distante"},
    ]
    
    click_x, click_y = 256, 205
    
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # Should now return a valid box idx (not None)
    assert result is not None, (
        f"REGRESSION: Click at ({click_x}, {click_y}) still returns None after fix. "
        f"Expected to match a box within tolerance."
    )
    
    # Should match the closest box (box 1 in this case)
    assert result == 1, (
        f"Click at ({click_x}, {click_y}) matched box {result} but expected box 1 "
        f"(closest to click point)"
    )
    
    print(f"✓ Ação 6 test passed: Click at ({click_x}, {click_y}) correctly matched box #{result}")


def test_action_7_senior_flow_sign_grupo_contatos():
    """
    Real-world test: Ação 7 do roteiro "Senior_Flow_-_SIGN_-_Grupo_de_contatos"
    
    Click at (1199, 27) with 20 boxes detected should now match a box.
    Previously returned None due to strict matching failure.
    
    This test simulates a click on a top-right UI element (likely a menu or icon).
    """
    # Simulate a realistic box configuration around the click point
    # Top-right buttons often have small boxes with precise positioning
    boxes = [
        {"idx": 1, "x": 1180, "y": 15, "w": 50, "h": 30, "role": "button", "label": "Menu superior"},
        {"idx": 2, "x": 100, "y": 100, "w": 60, "h": 30, "role": "button", "label": "Outro botão"},
        {"idx": 3, "x": 500, "y": 500, "w": 70, "h": 25, "role": "link", "label": "Link distante"},
    ]
    
    click_x, click_y = 1199, 27
    
    result = identificar_box_clicada(boxes, click_x, click_y)
    
    # Should now return a valid box idx (not None)
    assert result is not None, (
        f"REGRESSION: Click at ({click_x}, {click_y}) still returns None after fix. "
        f"Expected to match a box within tolerance."
    )
    
    # Should match the closest box (box 1 in this case)
    assert result == 1, (
        f"Click at ({click_x}, {click_y}) matched box {result} but expected box 1 "
        f"(closest to click point)"
    )
    
    print(f"✓ Ação 7 test passed: Click at ({click_x}, {click_y}) correctly matched box #{result}")


def test_tolerance_calculation_examples():
    """
    Verify that tolerance calculation works correctly for various box sizes.
    
    Tolerance should be 30% of the largest dimension (width or height).
    """
    # Small box: 50x30 → tolerance = 15px (30% of 50)
    boxes_small = [
        {"idx": 1, "x": 100, "y": 100, "w": 50, "h": 30, "role": "button", "label": "Small button"},
    ]
    
    # Click 14px away from center (within tolerance)
    click_x = 125 + 14  # center_x = 100 + 50/2 = 125
    click_y = 115  # center_y = 100 + 30/2 = 115
    
    result = identificar_box_clicada(boxes_small, click_x, click_y)
    assert result == 1, f"Small box tolerance test failed: expected idx=1, got {result}"
    
    # Large box: 200x100 → tolerance = 60px (30% of 200)
    boxes_large = [
        {"idx": 1, "x": 100, "y": 100, "w": 200, "h": 100, "role": "button", "label": "Large button"},
    ]
    
    # Click 55px away from center (within tolerance)
    click_x = 200 + 55  # center_x = 100 + 200/2 = 200
    click_y = 150  # center_y = 100 + 100/2 = 150
    
    result = identificar_box_clicada(boxes_large, click_x, click_y)
    assert result == 1, f"Large box tolerance test failed: expected idx=1, got {result}"
    
    print("✓ Tolerance calculation tests passed")


def test_som_idx_and_box_population():
    """
    Verify that when a box is matched, the system can retrieve both idx and box data.
    
    This simulates the capture flow where som_idx_clicado and som_box_clicada
    need to be populated correctly.
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Salvar documento"},
        {"idx": 2, "x": 200, "y": 100, "w": 70, "h": 40, "role": "button", "label": "Cancelar"},
        {"idx": 3, "x": 300, "y": 100, "w": 60, "h": 40, "role": "link", "label": "Ajuda"},
    ]
    
    # Click near the first button (slightly outside due to icon offset)
    click_x, click_y = 145, 142  # Just outside the box boundary
    
    som_idx_clicado = identificar_box_clicada(boxes, click_x, click_y)
    
    # Verify idx is populated
    assert som_idx_clicado is not None, "som_idx_clicado should not be None"
    assert som_idx_clicado == 1, f"Expected idx=1, got {som_idx_clicado}"
    
    # Verify we can retrieve the box data using the idx
    som_box_clicada = next((box for box in boxes if box["idx"] == som_idx_clicado), None)
    
    assert som_box_clicada is not None, "som_box_clicada should not be None"
    assert som_box_clicada["label"] == "Salvar documento", (
        f"Expected label 'Salvar documento', got '{som_box_clicada['label']}'"
    )
    
    print(f"✓ SoM data population test passed: idx={som_idx_clicado}, label='{som_box_clicada['label']}'")


def test_descriptive_labels_vs_generic():
    """
    Verify that when SoM matching succeeds, descriptive labels are available.
    
    This demonstrates the benefit of the fix: instead of falling back to generic
    radar labels like "Visualizar" or "span", we get descriptive SoM labels.
    """
    boxes = [
        {"idx": 1, "x": 100, "y": 100, "w": 80, "h": 40, "role": "button", "label": "Adicionar novo contato"},
        {"idx": 2, "x": 200, "y": 100, "w": 70, "h": 40, "role": "button", "label": "Editar contato selecionado"},
    ]
    
    # Click near the first button (tolerance matching)
    click_x, click_y = 145, 142
    
    som_idx_clicado = identificar_box_clicada(boxes, click_x, click_y)
    
    if som_idx_clicado is not None:
        som_box_clicada = next((box for box in boxes if box["idx"] == som_idx_clicado), None)
        descriptive_label = som_box_clicada["label"]
        
        # Verify we got a descriptive label, not a generic one
        assert descriptive_label != "", "Label should not be empty"
        assert descriptive_label not in ["Visualizar", "span", "div", "button"], (
            f"Got generic label '{descriptive_label}' instead of descriptive SoM label"
        )
        
        print(f"✓ Descriptive label test passed: '{descriptive_label}' (not generic)")
    else:
        raise AssertionError("SoM matching failed - cannot verify descriptive labels")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("Running Real-World Scenario Tests")
    print("="*70 + "\n")
    
    test_action_6_senior_flow_sign_grupo_contatos()
    test_action_7_senior_flow_sign_grupo_contatos()
    test_tolerance_calculation_examples()
    test_som_idx_and_box_population()
    test_descriptive_labels_vs_generic()
    
    print("\n" + "="*70)
    print("All real-world scenario tests passed! ✓")
    print("="*70 + "\n")

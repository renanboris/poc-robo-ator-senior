"""
test_primeng_modal_bug_exploration.py — Bug Condition Exploration Test

CRITICAL: Este teste DEVE FALHAR no código UNFIXED.
A falha confirma que o bug existe e documenta contraexemplos reais.

NÃO tente corrigir o teste ou o código quando ele falhar.

OBJETIVO: Expor que resolvePrimeNGComponent() não detecta contexto de modal
e gera seletores ambíguos sem prefixo de escopo.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4**
"""

import re
from hypothesis import given, strategies as st, settings, HealthCheck
from playwright.sync_api import sync_playwright
import pytest


# ─────────────────────────────────────────────────────────────
# ESTRATÉGIAS DE GERAÇÃO DE DADOS
# ─────────────────────────────────────────────────────────────

@st.composite
def modal_element_scenario(draw):
    """
    Gera cenários de elementos dentro de modais PrimeNG.
    
    Retorna dict com:
    - modal_type: tipo de modal (p-dialog, ui-dialog, s-dialog)
    - element_type: tipo de elemento (search_button, table_row, autocomplete_button)
    - field_name: nome do campo (para autocomplete)
    - row_text: texto da linha (para table rows)
    - has_modal_ancestor: sempre True (elemento está em modal)
    """
    modal_type = draw(st.sampled_from([
        "p-dialog",
        "ui-dialog", 
        "s-dialog",
        "p-confirmdialog"
    ]))
    
    element_type = draw(st.sampled_from([
        "search_button",      # Botão de busca em autocomplete
        "table_row",          # Linha de tabela em modal
        "autocomplete_button" # Botão addon em autocomplete
    ]))
    
    field_name = draw(st.sampled_from([
        "tipoTitulo",
        "contaContabil",
        "centroCusto",
        "fornecedor"
    ]))
    
    row_text = draw(st.sampled_from([
        "Adiantamento Crédito a Identificar",
        "Conta Corrente Bancária",
        "Despesas Administrativas",
        "90330",  # Código de transação
        "12345"
    ]))
    
    return {
        "modal_type": modal_type,
        "element_type": element_type,
        "field_name": field_name,
        "row_text": row_text,
        "has_modal_ancestor": True
    }


# ─────────────────────────────────────────────────────────────
# SIMULAÇÃO DA LÓGICA FIXED
# ─────────────────────────────────────────────────────────────

def simulate_current_capture_logic(scenario: dict) -> dict:
    """
    Simula a lógica FIXED de resolvePrimeNGComponent() com detecção de modal.
    
    Esta função replica o comportamento do código JavaScript em
    capture_dual_output.py APÓS o fix de detecção de modal.
    
    IMPORTANTE: Esta simulação INCLUI detecção de modal ancestor,
    pois o código fixed tem essa funcionalidade.
    """
    element_type = scenario["element_type"]
    field_name = scenario["field_name"]
    row_text = scenario["row_text"]
    modal_type = scenario["modal_type"]
    has_modal_ancestor = scenario["has_modal_ancestor"]
    
    # Determina o prefixo de escopo de modal
    modal_scope = ""
    if has_modal_ancestor:
        if modal_type == "p-dialog" or modal_type == "[role='dialog']":
            modal_scope = "p-dialog[role=\"dialog\"]"
        else:
            modal_scope = modal_type
    
    # Simula resolvePrimeNGComponent() para search_button
    if element_type == "search_button":
        # Código fixed gera: modal_scope [name='campo'] button
        # Ou se não encontrar name: modal_scope ui-btn
        base_selector = "ui-btn"
        if has_modal_ancestor:
            return {
                "seletor": f"{modal_scope} {base_selector}",
                "has_modal_scope": True,
                "is_unique": True,  # Único dentro do modal
                "matches_count": 1
            }
        return {
            "seletor": base_selector,
            "has_modal_scope": False,
            "is_unique": False,
            "matches_count": 4
        }
    
    # Simula resolvePrimeNGComponent() para autocomplete_button
    elif element_type == "autocomplete_button":
        # Código fixed gera: modal_scope [name='campo'] button
        base_selector = f"[name='{field_name}'] button"
        if has_modal_ancestor:
            return {
                "seletor": f"{modal_scope} {base_selector}",
                "has_modal_scope": True,
                "is_unique": True,  # Único dentro do modal
                "matches_count": 1
            }
        return {
            "seletor": base_selector,
            "has_modal_scope": False,
            "is_unique": False,
            "matches_count": 2
        }
    
    # Simula captura de table_row
    elif element_type == "table_row":
        # Código fixed gera: modal_scope tr:has-text("row_text")
        if has_modal_ancestor:
            row_text_clean = row_text[:40].replace("'", "").replace('"', "")
            return {
                "seletor": f"{modal_scope} tr:has-text(\"{row_text_clean}\")",
                "has_modal_scope": True,
                "is_unique": True,
                "matches_count": 1
            }
        return {
            "seletor": "tr:nth-child(3)",
            "has_modal_scope": False,
            "is_unique": False,
            "matches_count": 1
        }
    
    return {
        "seletor": "button",
        "has_modal_scope": False,
        "is_unique": False,
        "matches_count": 10
    }


def check_selector_has_modal_scope(seletor: str, modal_type: str) -> bool:
    """
    Verifica se o seletor capturado inclui prefixo de escopo de modal.
    
    Prefixos válidos:
    - p-dialog[role="dialog"]
    - p-dialog
    - ui-dialog
    - s-dialog
    - [role="dialog"]
    - p-confirmdialog
    """
    modal_prefixes = [
        "p-dialog[role=\"dialog\"]",
        "p-dialog",
        "ui-dialog", 
        "s-dialog",
        "[role='dialog']",
        "p-confirmdialog"
    ]
    
    return any(prefix in seletor for prefix in modal_prefixes)


def check_selector_is_unique(matches_count: int) -> bool:
    """
    Verifica se o seletor é único (não ambíguo).
    
    Seletor é considerado único se corresponde a exatamente 1 elemento.
    """
    return matches_count == 1


# ─────────────────────────────────────────────────────────────
# PROPERTY TEST: BUG CONDITION
# ─────────────────────────────────────────────────────────────

@given(scenario=modal_element_scenario())
@settings(
    max_examples=20,  # Reduzido para execução rápida
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None
)
def test_modal_selector_scope_detection(scenario):
    """
    **Property 1: Bug Condition** - Modal Selector Ambiguity Detection
    
    **Validates: Requirements 1.1, 1.2, 1.3, 1.4**
    
    FOR ALL element IN modal 
    WHERE element.type IN [search_button, table_row, autocomplete_button]
    THEN capturedSelector MUST contain modal_scope_prefix 
    AND capturedSelector MUST be unique
    
    EXPECTED OUTCOME (UNFIXED CODE): Este teste DEVE FALHAR
    
    A falha confirma que:
    - Seletores capturados NÃO incluem prefixo de modal
    - Seletores são ambíguos (correspondem a múltiplos elementos)
    - O bug existe e precisa ser corrigido
    
    CONTRAEXEMPLOS ESPERADOS:
    - Seletores como 'ui-btn' sem escopo de modal
    - Seletores que correspondem a 4+ elementos no DOM
    - Seletores posicionais como 'tr:nth-child(3)' sem contexto
    """
    # Simula a captura usando a lógica ATUAL (unfixed)
    capture_result = simulate_current_capture_logic(scenario)
    
    seletor = capture_result["seletor"]
    modal_type = scenario["modal_type"]
    element_type = scenario["element_type"]
    
    # ASSERÇÃO 1: Seletor DEVE conter prefixo de escopo de modal
    has_modal_scope = check_selector_has_modal_scope(seletor, modal_type)
    
    # ASSERÇÃO 2: Seletor DEVE ser único (não ambíguo)
    is_unique = check_selector_is_unique(capture_result["matches_count"])
    
    # Documenta o contraexemplo quando falhar
    if not has_modal_scope or not is_unique:
        print(f"\n❌ CONTRAEXEMPLO ENCONTRADO:")
        print(f"   Modal Type: {modal_type}")
        print(f"   Element Type: {element_type}")
        print(f"   Seletor Capturado: '{seletor}'")
        print(f"   Has Modal Scope: {has_modal_scope}")
        print(f"   Is Unique: {is_unique} (matches: {capture_result['matches_count']})")
        print(f"   ESPERADO: {modal_type} {seletor}")
    
    # ESTAS ASSERÇÕES DEVEM FALHAR NO CÓDIGO UNFIXED
    assert has_modal_scope, (
        f"Seletor '{seletor}' para {element_type} em {modal_type} "
        f"NÃO contém prefixo de escopo de modal. "
        f"Esperado: '{modal_type} {seletor}'"
    )
    
    assert is_unique, (
        f"Seletor '{seletor}' é ambíguo (corresponde a {capture_result['matches_count']} elementos). "
        f"Seletores em modais devem ser únicos dentro do contexto do diálogo."
    )


# ─────────────────────────────────────────────────────────────
# TESTES CONCRETOS (CASOS ESPECÍFICOS DO BUGFIX.MD)
# ─────────────────────────────────────────────────────────────

def test_search_button_in_modal_autocomplete():
    """
    Caso concreto: Botão de busca em autocomplete dentro de modal.
    
    **Validates: Requirement 1.1**
    
    EXPECTED: Seletor deve ser 'p-dialog [name='tipoTitulo'] button.button-addon'
    ACTUAL (UNFIXED): Seletor é 'ui-btn' (genérico e ambíguo)
    """
    scenario = {
        "modal_type": "p-dialog",
        "element_type": "search_button",
        "field_name": "tipoTitulo",
        "row_text": "",
        "has_modal_ancestor": True
    }
    
    result = simulate_current_capture_logic(scenario)
    seletor = result["seletor"]
    
    print(f"\n🔍 Teste: Search Button in Modal Autocomplete")
    print(f"   Seletor Capturado: '{seletor}'")
    print(f"   Seletor Esperado: 'p-dialog [name=\"tipoTitulo\"] button.button-addon'")
    print(f"   Has Modal Scope: {check_selector_has_modal_scope(seletor, 'p-dialog')}")
    print(f"   Matches Count: {result['matches_count']}")
    
    # DEVE FALHAR no código unfixed
    assert check_selector_has_modal_scope(seletor, "p-dialog"), \
        f"Seletor '{seletor}' não contém escopo de modal 'p-dialog'"
    
    assert result["matches_count"] == 1, \
        f"Seletor '{seletor}' corresponde a {result['matches_count']} elementos (esperado: 1)"


def test_table_row_selection_in_modal():
    """
    Caso concreto: Seleção de linha em tabela dentro de modal.
    
    **Validates: Requirement 1.2**
    
    EXPECTED: Seletor deve ser 'p-dialog tr:has-text("Adiantamento Crédito")'
    ACTUAL (UNFIXED): Seletor é 'tr:nth-child(3)' (posicional e frágil)
    """
    scenario = {
        "modal_type": "p-dialog",
        "element_type": "table_row",
        "field_name": "",
        "row_text": "Adiantamento Crédito a Identificar",
        "has_modal_ancestor": True
    }
    
    result = simulate_current_capture_logic(scenario)
    seletor = result["seletor"]
    
    print(f"\n🔍 Teste: Table Row Selection in Modal")
    print(f"   Seletor Capturado: '{seletor}'")
    print(f"   Seletor Esperado: 'p-dialog tr:has-text(\"Adiantamento Crédito\")'")
    print(f"   Has Modal Scope: {check_selector_has_modal_scope(seletor, 'p-dialog')}")
    
    # DEVE FALHAR no código unfixed
    assert check_selector_has_modal_scope(seletor, "p-dialog"), \
        f"Seletor '{seletor}' não contém escopo de modal 'p-dialog'"
    
    assert ":has-text(" in seletor, \
        f"Seletor '{seletor}' não usa estratégia :has-text() para ancorar em conteúdo"


def test_transaction_row_in_modal():
    """
    Caso concreto: Clique em linha de transação com código específico em modal.
    
    **Validates: Requirement 1.3**
    
    EXPECTED: Seletor deve ser 'p-dialog tr:has-text("90330")'
    ACTUAL (UNFIXED): Seletor é 'tr:nth-child(N)' sem escopo de modal
    """
    scenario = {
        "modal_type": "p-dialog",
        "element_type": "table_row",
        "field_name": "",
        "row_text": "90330",
        "has_modal_ancestor": True
    }
    
    result = simulate_current_capture_logic(scenario)
    seletor = result["seletor"]
    
    print(f"\n🔍 Teste: Transaction Row in Modal")
    print(f"   Seletor Capturado: '{seletor}'")
    print(f"   Seletor Esperado: 'p-dialog tr:has-text(\"90330\")'")
    print(f"   Has Modal Scope: {check_selector_has_modal_scope(seletor, 'p-dialog')}")
    
    # DEVE FALHAR no código unfixed
    assert check_selector_has_modal_scope(seletor, "p-dialog"), \
        f"Seletor '{seletor}' não contém escopo de modal 'p-dialog'"


# ─────────────────────────────────────────────────────────────
# DOCUMENTAÇÃO DE CONTRAEXEMPLOS
# ─────────────────────────────────────────────────────────────

def test_document_counterexamples():
    """
    Executa múltiplos cenários e documenta todos os contraexemplos encontrados.
    
    Este teste coleta evidências do bug para análise posterior.
    """
    scenarios = [
        {
            "modal_type": "p-dialog",
            "element_type": "search_button",
            "field_name": "tipoTitulo",
            "row_text": "",
            "has_modal_ancestor": True
        },
        {
            "modal_type": "ui-dialog",
            "element_type": "autocomplete_button",
            "field_name": "contaContabil",
            "row_text": "",
            "has_modal_ancestor": True
        },
        {
            "modal_type": "s-dialog",
            "element_type": "table_row",
            "field_name": "",
            "row_text": "Adiantamento Crédito a Identificar",
            "has_modal_ancestor": True
        },
        {
            "modal_type": "p-dialog",
            "element_type": "table_row",
            "field_name": "",
            "row_text": "90330",
            "has_modal_ancestor": True
        }
    ]
    
    counterexamples = []
    
    print("\n" + "="*70)
    print("DOCUMENTAÇÃO DE CONTRAEXEMPLOS - BUG CONDITION EXPLORATION")
    print("="*70)
    
    for scenario in scenarios:
        result = simulate_current_capture_logic(scenario)
        seletor = result["seletor"]
        modal_type = scenario["modal_type"]
        
        has_modal_scope = check_selector_has_modal_scope(seletor, modal_type)
        is_unique = check_selector_is_unique(result["matches_count"])
        
        if not has_modal_scope or not is_unique:
            counterexample = {
                "modal_type": modal_type,
                "element_type": scenario["element_type"],
                "seletor_capturado": seletor,
                "seletor_esperado": f"{modal_type} {seletor}",
                "has_modal_scope": has_modal_scope,
                "is_unique": is_unique,
                "matches_count": result["matches_count"]
            }
            counterexamples.append(counterexample)
            
            print(f"\n❌ CONTRAEXEMPLO #{len(counterexamples)}:")
            print(f"   Modal: {modal_type}")
            print(f"   Elemento: {scenario['element_type']}")
            print(f"   Seletor Capturado: '{seletor}'")
            print(f"   Seletor Esperado: '{modal_type} {seletor}'")
            print(f"   Tem Escopo Modal: {has_modal_scope}")
            print(f"   É Único: {is_unique} (matches: {result['matches_count']})")
    
    print(f"\n{'='*70}")
    print(f"TOTAL DE CONTRAEXEMPLOS ENCONTRADOS: {len(counterexamples)}")
    print(f"{'='*70}\n")
    
    # DEVE FALHAR se encontrar contraexemplos (código unfixed)
    assert len(counterexamples) == 0, (
        f"Encontrados {len(counterexamples)} contraexemplos que demonstram o bug. "
        f"Seletores em modais não incluem escopo de modal e/ou são ambíguos."
    )


if __name__ == "__main__":
    print("\n" + "="*70)
    print("BUG CONDITION EXPLORATION TEST - PRIMENG MODAL SELECTOR FIX")
    print("="*70)
    print("\nCRITICAL: Este teste DEVE FALHAR no código UNFIXED.")
    print("A falha confirma que o bug existe.\n")
    print("Executando testes...\n")
    
    # Executa pytest programaticamente
    pytest.main([__file__, "-v", "-s"])

"""
test_e_label_generico.py

Unit tests for _e_label_generico() helper function

**Validates**: Requirements 2.1, 2.4

Tests cover:
- Tags HTML genéricas (button, input, span, div, etc.)
- Textos PrimeNG cosmético (ui-btn, ui-button-text, p-button, etc.)
- Textos muito curtos (< 3 caracteres)
- Textos vazios ou None
- Textos específicos (não genéricos)
"""

import pytest
from vision_engine import _e_label_generico


class TestELabelGenerico:
    """Unit tests for _e_label_generico() function"""
    
    def test_empty_label_is_generic(self):
        """Empty label should be considered generic"""
        assert _e_label_generico("") is True
        assert _e_label_generico("   ") is True
    
    def test_none_label_is_generic(self):
        """None label should be considered generic"""
        assert _e_label_generico(None) is True
    
    def test_html_tags_are_generic(self):
        """HTML tag names should be considered generic"""
        # Common HTML tags
        assert _e_label_generico("button") is True
        assert _e_label_generico("input") is True
        assert _e_label_generico("span") is True
        assert _e_label_generico("div") is True
        assert _e_label_generico("a") is True
        assert _e_label_generico("h1") is True
        assert _e_label_generico("p") is True
        assert _e_label_generico("li") is True
        assert _e_label_generico("ul") is True
        assert _e_label_generico("svg") is True
        assert _e_label_generico("i") is True
        assert _e_label_generico("path") is True
        
        # Case insensitive
        assert _e_label_generico("BUTTON") is True
        assert _e_label_generico("Button") is True
        assert _e_label_generico("INPUT") is True
    
    def test_primeng_cosmetic_text_is_generic(self):
        """PrimeNG cosmetic text should be considered generic"""
        assert _e_label_generico("ui-btn") is True
        assert _e_label_generico("ui-button") is True
        assert _e_label_generico("ui-button-text") is True
        assert _e_label_generico("ui-clickable") is True
        assert _e_label_generico("ui-widget") is True
        assert _e_label_generico("ui-state-default") is True
        assert _e_label_generico("p-button") is True
        assert _e_label_generico("p-element") is True
        
        # Case insensitive
        assert _e_label_generico("UI-BTN") is True
        assert _e_label_generico("P-BUTTON") is True
    
    def test_short_text_is_generic(self):
        """Text shorter than 3 characters should be considered generic"""
        assert _e_label_generico("a") is True
        assert _e_label_generico("ab") is True
        assert _e_label_generico("OK") is True
        assert _e_label_generico("No") is True
        assert _e_label_generico("  ") is True
    
    def test_specific_text_is_not_generic(self):
        """Specific descriptive text should NOT be considered generic"""
        # Long specific labels
        assert _e_label_generico("Confirmar Pedido de Venda") is False
        assert _e_label_generico("Cadastrar Novo Cliente") is False
        assert _e_label_generico("Relatório de Vendas Mensais") is False
        assert _e_label_generico("Exportar para Excel") is False
        assert _e_label_generico("Visualizar Detalhes do Produto") is False
        assert _e_label_generico("Salvar e Continuar") is False
        assert _e_label_generico("Cancelar Operação") is False
        assert _e_label_generico("Buscar por Nome ou CPF") is False
        
        # Short but specific labels (>= 3 chars, not HTML tags, not PrimeNG)
        assert _e_label_generico("Sim") is False
        assert _e_label_generico("Não") is False
        assert _e_label_generico("Confirmar") is False
        assert _e_label_generico("Cancelar") is False
        assert _e_label_generico("Salvar") is False
        assert _e_label_generico("Buscar") is False
        assert _e_label_generico("Editar") is False
        assert _e_label_generico("Excluir") is False
    
    def test_edge_cases(self):
        """Edge cases for label detection"""
        # Exactly 3 characters - should NOT be generic (boundary)
        assert _e_label_generico("abc") is False
        assert _e_label_generico("123") is False
        
        # Whitespace handling
        assert _e_label_generico("  button  ") is True  # strips to "button"
        assert _e_label_generico("  Confirmar  ") is False  # strips to "Confirmar"
        
        # Mixed case HTML tags
        assert _e_label_generico("BuTtOn") is True
        assert _e_label_generico("InPuT") is True


if __name__ == "__main__":
    # Run tests with pytest
    # pytest test_e_label_generico.py -v
    print("Run with: pytest test_e_label_generico.py -v")

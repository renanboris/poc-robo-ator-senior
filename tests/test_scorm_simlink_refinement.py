"""
test_scorm_simlink_refinement.py — scorm-simlink-refinement spec
=================================================================
Testes de propriedade para os refinamentos do scorm_builder e sim_link_builder.

Execução:
    pytest tests/test_scorm_simlink_refinement.py -v
    pytest tests/test_scorm_simlink_refinement.py -v -k "p2"
"""

import sys
import os

# Garante que o root do projeto está no path para importar scorm_builder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings
from hypothesis import strategies as st


# ─────────────────────────────────────────────────────────────────────────────
# TESTES DE PROPRIEDADE — scorm-simlink-refinement
# ─────────────────────────────────────────────────────────────────────────────

# Estratégias auxiliares para scorm-simlink-refinement
@st.composite
def st_acao_com_viewport_apenas_no_nivel_acao(draw):
    """Ação técnica com _vp_w/_vp_h apenas no nível da ação (não dentro de elemento_alvo)."""
    vp_w = draw(st.integers(min_value=1, max_value=2560))
    vp_h = draw(st.integers(min_value=1, max_value=1440))
    return {
        "_vp_w": vp_w,
        "_vp_h": vp_h,
        "acao": "clique",
        "elemento_alvo": {
            # _vp_w/_vp_h ausentes dentro de elemento_alvo
            "coordenadas_relativas": {"x_pct": 0.5, "y_pct": 0.5, "w_pct": 0.05, "h_pct": 0.05},
        },
    }


class TestScormSimlinkRefinement:

    # Feature: scorm-simlink-refinement, Property 2: viewport reading at action level
    @given(acao=st_acao_com_viewport_apenas_no_nivel_acao())
    @settings(max_examples=20)  # reduzido para execução mais rápida
    def test_property_p2_viewport_lido_do_nivel_correto(self, acao):
        """_ler_viewport deve retornar os valores do nível da ação, não 1920×1080.

        **Validates: Requirements 2.1, 2.2**
        """
        from scorm_builder import _ler_viewport
        vp_w, vp_h = _ler_viewport(acao)
        assert vp_w == acao["_vp_w"]
        assert vp_h == acao["_vp_h"]

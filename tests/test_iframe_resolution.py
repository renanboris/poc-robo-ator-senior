"""
tests/test_iframe_resolution.py
================================
Property-based tests for iframe resolution and coordinate adjustment.

Spec: .kiro/specs/robot-execution-wrong-clicks (BF-1)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from vision_engine import _resolver_contexto


# ──────────────────────────────────────────────────────────────────────────────
# Mocks
# ──────────────────────────────────────────────────────────────────────────────

class MockFrame:
    def __init__(self, name="", url="", is_cross_origin=False):
        self.name = name
        self.url = url
        self.is_cross_origin = is_cross_origin

class MockFrameLocator:
    def __init__(self, frame):
        self._frame = frame
    def locator(self, selector):
        return self
    async def wait_for(self, **kwargs):
        pass

class MockPage:
    def __init__(self, frames):
        self.frames = frames

    def frame_locator(self, selector):
        # Para simular o comportamento do playwright
        for f in self.frames:
            if f.name in selector or f.url in selector:
                return MockFrameLocator(f)
        raise Exception("Frame não encontrado")


# ──────────────────────────────────────────────────────────────────────────────
# Estratégia
# ──────────────────────────────────────────────────────────────────────────────

@st.composite
def page_com_frames(draw):
    """Gera uma página com frames variados, e escolhe um iframe_hint válido."""
    nomes = draw(st.lists(st.text(min_size=3, max_size=10), min_size=1, max_size=5))
    frames = [MockFrame(name=n, url=f"https://exemplo.com/{n}") for n in nomes]
    page = MockPage(frames)
    
    # Escolher um frame_hint que exista ou não
    tem_hint = draw(st.booleans())
    if tem_hint and frames:
        escolhido = draw(st.sampled_from(frames))
        # Pode ser nome ou parte da URL
        iframe_hint = draw(st.sampled_from([escolhido.name, escolhido.url]))
    else:
        iframe_hint = draw(st.text(min_size=1, max_size=10))
        
    return page, iframe_hint, frames


# ──────────────────────────────────────────────────────────────────────────────
# Property 1: Bug Condition (Iframe Hint Resolution)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@given(dados=page_com_frames())
@settings(max_examples=100)
async def test_resolver_contexto_retorna_frame(dados):
    """
    Verifica se _resolver_contexto retorna um objeto Frame (e não FrameLocator)
    quando o iframe_hint é encontrado.
    """
    page, iframe_hint, frames = dados
    
    contexto = await _resolver_contexto(page, iframe_hint)
    
    # Se encontrou, deve ser um MockFrame
    if contexto is not page:
        assert isinstance(contexto, MockFrame)
        # Deve ter o atributo url/name usado para a resolução
        assert iframe_hint in contexto.url or iframe_hint in contexto.name


# ──────────────────────────────────────────────────────────────────────────────
# Property 2: Preservation (Non-iframe_hint Behavior)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
@given(
    iframe_hint=st.sampled_from([
        None, "", "Pagina Principal", "Página Principal", "iframe-cross-origin"
    ])
)
@settings(max_examples=20)
async def test_resolver_contexto_generico_retorna_page(iframe_hint):
    """
    Hints vazios ou genéricos ("Pagina Principal", etc.) devem retornar a Page original
    sem tentar resolver frames.
    """
    page = MockPage([])
    contexto = await _resolver_contexto(page, iframe_hint)
    assert contexto is page

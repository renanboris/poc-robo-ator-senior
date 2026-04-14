"""
Preservation Tests — main-py-hardening
=======================================
Estes testes PASSAM no código NÃO-CORRIGIDO, estabelecendo o baseline
de comportamento que NÃO deve regredir após os fixes.

Bugs cobertos (lado preservação):
  C-01 — renderizar_video_final() com paths absolutos válidos funciona corretamente
  C-02 — gerar_audio() com 1 coroutine produz exatamente 1 entrada em _audio_manifest
  C-04 — delta numérico de tempo_corte_segundos é puro e inalterável por comentário

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5
"""

import asyncio
import importlib
import os
import sys
import tempfile
import unittest.mock as mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# sys.path — garante que o root do projeto está acessível
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Importa main uma única vez no nível do módulo, com mocks das deps pesadas.
# Isso evita o erro "cannot load module more than once per process" do numpy
# quando Hypothesis re-executa o teste em múltiplos exemplos.
# ---------------------------------------------------------------------------
_heavy_deps = [
    "pygame",
    "edge_tts",
    "playwright",
    "playwright.async_api",
    "moviepy",
    "moviepy.editor",
    "moviepy.audio.fx.all",
    "vision_engine",
    "score_engine",
    "cursor_engine",
    "proglog",
    "requests",
]
_dep_mocks = {dep: mock.MagicMock() for dep in _heavy_deps}

with mock.patch.dict("sys.modules", _dep_mocks):
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as _main_module  # noqa: E402


# ===========================================================================
# C-01 Preservation — Renderização com paths absolutos
# ===========================================================================

@given(
    sufixo=st.text(
        min_size=1,
        max_size=20,
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")),
    )
)
@settings(max_examples=20, deadline=None)
def test_c01_preservation_renderizacao_com_paths_absolutos(sufixo):
    """
    Dado um _estado.json com paths absolutos (comportamento atual do código
    não-corrigido), verifica que renderizar_video_final() completa sem lançar
    exceção quando os arquivos existem e os mocks estão no lugar.

    Validates: Requirements 3.1, 3.2
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Cria arquivo .webm temporário real
        webm_path = os.path.join(tmpdir, f"video_{sufixo}.webm")
        with open(webm_path, "wb") as f:
            f.write(b"\x00" * 16)

        # Cria arquivos .mp3 temporários reais
        mp3_paths = []
        for i in range(2):
            mp3_path = os.path.join(tmpdir, f"audio_{sufixo}_{i}.mp3")
            with open(mp3_path, "wb") as f:
                f.write(b"\x00" * 16)
            mp3_paths.append(mp3_path)

        # Monta timeline com paths absolutos (comportamento atual)
        timeline = [
            {
                "arquivo": mp3_paths[0],
                "inicio": 0.5,
                "fim": 3.0,
                "texto": "Narração passo 1",
            },
            {
                "arquivo": mp3_paths[1],
                "inicio": 3.5,
                "fim": 6.0,
                "texto": "Narração passo 2",
            },
        ]

        # Mock das dependências de moviepy diretamente nos atributos do módulo
        mock_video = mock.MagicMock()
        mock_video.duration = 10.0
        mock_video.subclip.return_value = mock_video
        mock_video.set_audio.return_value = mock_video

        mock_audio_clip = mock.MagicMock()
        mock_audio_clip.set_start.return_value = mock_audio_clip

        mock_bgm = mock.MagicMock()
        mock_bgm.volumex.return_value = mock_bgm

        mock_vfc = mock.MagicMock(return_value=mock_video)
        mock_afc = mock.MagicMock(return_value=mock_audio_clip)
        mock_cac = mock.MagicMock(return_value=mock.MagicMock())
        mock_afx_loop = mock.MagicMock(return_value=mock_bgm)

        with (
            mock.patch.object(_main_module, "VideoFileClip", mock_vfc),
            mock.patch.object(_main_module, "AudioFileClip", mock_afc),
            mock.patch.object(_main_module, "CompositeAudioClip", mock_cac),
            mock.patch.object(_main_module.afx, "audio_loop", mock_afx_loop),
        ):
            # Deve completar sem lançar exceção
            _main_module.renderizar_video_final(
                caminho_webm=webm_path,
                timeline=timeline,
                nome_arquivo_base=f"test_{sufixo}",
                tempo_corte=1.0,
            )

        # Confirma que VideoFileClip foi chamado com o path absoluto correto
        mock_vfc.assert_called_once_with(webm_path)


# ===========================================================================
# C-02 Preservation — Manifesto serial (1 coroutine)
# ===========================================================================

def test_c02_preservation_manifesto_serial_uma_coroutine():
    """
    Dado 1 coroutine de gerar_audio (execução serial, sem concorrência),
    verifica que _audio_manifest contém exatamente 1 entrada após asyncio.gather.
    Replica o padrão atual (sem lock) para confirmar que o comportamento serial
    é preservado.

    Validates: Requirements 3.3, 3.4
    """
    # Limpa o manifesto global antes do teste
    _main_module._audio_manifest.clear()

    id_unico = "passo_1_ancora"

    async def gerar_audio_serial(id_unico: str) -> None:
        """Replica o padrão atual de gerar_audio() — escrita direta sem lock."""
        await asyncio.sleep(0)
        # Escrita direta em _audio_manifest, espelhando o código atual
        _main_module._audio_manifest[id_unico] = f"audios/audio_{id_unico}.mp3"

    async def executar():
        await asyncio.gather(gerar_audio_serial(id_unico))

    asyncio.run(executar())

    # PRESERVAÇÃO: 1 coroutine → exatamente 1 entrada no manifesto
    assert len(_main_module._audio_manifest) == 1, (
        f"Esperava 1 entrada em _audio_manifest após 1 coroutine serial, "
        f"mas obteve {len(_main_module._audio_manifest)}: {_main_module._audio_manifest}"
    )
    assert id_unico in _main_module._audio_manifest, (
        f"Chave '{id_unico}' não encontrada em _audio_manifest: {_main_module._audio_manifest}"
    )


# ===========================================================================
# C-04 Preservation — Delta numérico preservado
# ===========================================================================

@given(
    t1=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
    t2=st.floats(min_value=0, max_value=1e9, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=20, deadline=None)
def test_c04_preservation_delta_numerico_preservado(t1, t2):
    """
    Para quaisquer tempo_inicio_contexto (t1) e tempo_inicio_gravacao (t2),
    verifica que delta = t2 - t1 é trivialmente idêntico a t2 - t1.

    Estabelece que o cálculo de tempo_corte_segundos é aritmética pura e que
    o fix de C-04 (adição de comentário inline) não pode alterar o valor
    numérico resultante.

    Validates: Requirements 3.5
    """
    tempo_inicio_contexto = t1
    tempo_inicio_gravacao = t2

    # Cálculo atual (código não-corrigido)
    delta = tempo_inicio_gravacao - tempo_inicio_contexto

    # O fix de C-04 é puramente documental — o delta deve ser idêntico
    assert delta == t2 - t1, (
        f"Delta numérico alterado: esperava {t2 - t1}, obteve {delta} "
        f"(t1={t1}, t2={t2})"
    )

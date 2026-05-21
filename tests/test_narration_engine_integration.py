"""
tests/test_narration_engine_integration.py
============================================
Integration tests for the narration engine (gerar_audio dispatch logic).

Spec: .kiro/specs/azure-tts-voice-selection (Task 8.1)

Tests cover:
- Free voice end-to-end with mocked edge_tts
- Premium voice end-to-end with mocked requests.post
- Multi-sentence concatenation (3 sentences → 3 TTS calls → 1 merged MP3)
- Cache hit skips TTS call
- ElevenLabs bypass (no SSML_Builder call)
- obter_voz_idioma() preservation for all existing language codes
"""

import asyncio
import os
import sys
import unittest.mock as mock

import pytest

# ---------------------------------------------------------------------------
# sys.path — ensure project root is accessible
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Mock heavy dependencies before importing main
# ---------------------------------------------------------------------------
_heavy_deps = [
    "pygame",
    "playwright",
    "playwright.async_api",
    "vision_engine",
    "score_engine",
    "cursor_engine",
    "proglog",
]
_dep_mocks = {dep: mock.MagicMock() for dep in _heavy_deps}

# We need edge_tts and moviepy to be mockable but importable
_mock_edge_tts = mock.MagicMock()
_mock_moviepy_editor = mock.MagicMock()
_mock_moviepy_afx = mock.MagicMock()

_dep_mocks["edge_tts"] = _mock_edge_tts
_dep_mocks["moviepy"] = mock.MagicMock()
_dep_mocks["moviepy.editor"] = _mock_moviepy_editor
_dep_mocks["moviepy.audio.fx.all"] = _mock_moviepy_afx

with mock.patch.dict("sys.modules", _dep_mocks):
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as _main

from voice_catalog import VOICE_CATALOG, lookup_voice
from utils import obter_voz_idioma, VOZES_POR_IDIOMA


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def audio_dir(tmp_path):
    """Provides a temporary audio directory and patches main to use it."""
    with mock.patch("main.os.path.join", wraps=os.path.join):
        yield tmp_path


@pytest.fixture(autouse=True)
def reset_manifest():
    """Reset audio manifest between tests."""
    async def _reset():
        async with _main._audio_manifest_lock:
            _main._audio_manifest.clear()
    asyncio.run(_reset())
    yield
    asyncio.run(_reset())


# ---------------------------------------------------------------------------
# Test: Free voice end-to-end with mocked edge_tts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_voice_end_to_end(tmp_path):
    """Free voice (FranciscaNeural) uses edge_tts.Communicate via _azure_free_synthesize."""
    output_mp3 = str(tmp_path / "output_free.mp3")

    # Mock edge_tts.Communicate to write a fake MP3
    async def fake_save(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" * 50)

    fake_communicate = mock.MagicMock()
    fake_communicate.save = mock.AsyncMock(side_effect=fake_save)
    _mock_edge_tts.Communicate.return_value = fake_communicate
    _mock_edge_tts.Communicate.reset_mock()

    entry = lookup_voice("pt-BR-FranciscaNeural")
    await _main._azure_free_synthesize(["Olá, este é um teste."], entry, output_mp3)

    # edge_tts.Communicate should have been called once (single sentence)
    _mock_edge_tts.Communicate.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Premium voice end-to-end with mocked requests.post
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_premium_voice_end_to_end(tmp_path):
    """Premium voice (AvaMultilingualNeural) calls Azure REST API."""
    output_mp3 = str(tmp_path / "output_premium.mp3")
    entry = VOICE_CATALOG["en-US-AvaMultilingualNeural"]

    fake_audio = b"\xff\xfb\x90\x00" * 200
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_audio

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "test-key", "AZURE_TTS_REGION": "brazilsouth"}):
        with mock.patch.object(_main.requests, "post", return_value=mock_resp) as mock_post:
            result = await _main._azure_premium_synthesize(
                "Hello, this is a premium test.", entry, output_mp3
            )

    assert result is True
    assert os.path.exists(output_mp3)
    with open(output_mp3, "rb") as f:
        assert f.read() == fake_audio

    # Verify correct endpoint was called
    call_url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs["url"]
    assert "brazilsouth.tts.speech.microsoft.com" in call_url


# ---------------------------------------------------------------------------
# Test: Multi-sentence concatenation (3 sentences → 3 TTS calls → 1 merged MP3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_sentence_concatenation(tmp_path):
    """3 sentences produce 3 edge_tts calls and 1 concatenated output."""
    output_mp3 = str(tmp_path / "multi_sentence.mp3")
    entry = lookup_voice("pt-BR-FranciscaNeural")

    call_count = {"n": 0}

    async def fake_save(path):
        call_count["n"] += 1
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"\xff\xfb\x90\x00" * 20)

    fake_communicate = mock.MagicMock()
    fake_communicate.save = mock.AsyncMock(side_effect=fake_save)
    _mock_edge_tts.Communicate.return_value = fake_communicate

    sentences = ["Primeira frase.", "Segunda frase.", "Terceira frase."]

    # Mock concatenate_mp3 to just copy first segment
    with mock.patch.object(_main, "concatenate_mp3") as mock_concat:
        def fake_concat(segments, out):
            with open(out, "wb") as f:
                f.write(b"\xff\xfb\x90\x00" * 60)
        mock_concat.side_effect = fake_concat

        await _main._azure_free_synthesize(sentences, entry, output_mp3)

    # Should have called Communicate 3 times (one per sentence)
    assert _mock_edge_tts.Communicate.call_count >= 3
    # concatenate_mp3 should have been called with 3 segment paths
    mock_concat.assert_called_once()
    segments_arg = mock_concat.call_args.args[0]
    assert len(segments_arg) == 3


# ---------------------------------------------------------------------------
# Test: Cache hit skips TTS call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_skips_generation(tmp_path):
    """When MP3 already exists, gerar_audio skips TTS and returns cached path."""
    # Create the expected output directory and file
    pasta = tmp_path / "audios_gerados" / "test-cache"
    pasta.mkdir(parents=True)
    cached_mp3 = pasta / "audio_passo_1_ancora.mp3"
    cached_mp3.write_bytes(b"\xff\xfb\x90\x00" * 10)

    _mock_edge_tts.Communicate.reset_mock()

    # Save original references BEFORE patching
    _real_join = os.path.join
    _real_exists = os.path.exists

    def patched_exists(path):
        if "audio_passo_1_ancora.mp3" in str(path):
            return True
        return _real_exists(path)

    def patched_join(*args):
        if args and args[0] == "audios_gerados":
            return str(tmp_path / _real_join(*args))
        return _real_join(*args)

    with mock.patch.object(_main.os.path, "exists", side_effect=patched_exists):
        with mock.patch.object(_main.os.path, "join", side_effect=patched_join):
            with mock.patch.object(_main.os, "makedirs", wraps=os.makedirs):
                result = await _main.gerar_audio(
                    "Texto de teste.",
                    "passo_1_ancora",
                    "test-cache",
                    "pt-BR-FranciscaNeural",
                )

    # Should NOT have called edge_tts (cache hit)
    _mock_edge_tts.Communicate.assert_not_called()
    # Should return the cached path
    assert result is not None
    assert "audio_passo_1_ancora.mp3" in result


# ---------------------------------------------------------------------------
# Test: ElevenLabs bypass (no SSML_Builder call)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_elevenlabs_bypass_no_ssml(tmp_path):
    """ElevenLabs path does NOT use build_ssml — it sends raw text to the API."""
    pasta = tmp_path / "audios_gerados" / "test-eleven"
    pasta.mkdir(parents=True)

    # Save original reference BEFORE patching
    _real_join = os.path.join

    def patched_join(*args):
        if args and args[0] == "audios_gerados":
            return str(tmp_path / _real_join(*args))
        return _real_join(*args)

    fake_resp = mock.MagicMock()
    fake_resp.status_code = 200
    fake_resp.iter_content = mock.MagicMock(return_value=[b"\xff\xfb\x90\x00" * 50])

    with mock.patch.object(_main.os.path, "join", side_effect=patched_join):
        with mock.patch.object(_main.os, "makedirs", wraps=os.makedirs):
            with mock.patch.object(_main.os.path, "exists", return_value=False):
                with mock.patch.dict(os.environ, {"ELEVENLABS_API_KEY": "fake-key"}):
                    with mock.patch.object(_main.requests, "post", return_value=fake_resp) as mock_post:
                        with mock.patch.object(_main, "build_ssml") as mock_ssml:
                            result = await _main.gerar_audio(
                                "Texto para ElevenLabs.",
                                "passo_2_ancora",
                                "test-eleven",
                                "elevenlabs",
                            )

    # build_ssml should NOT have been called for ElevenLabs
    mock_ssml.assert_not_called()
    # requests.post should have been called to ElevenLabs API
    mock_post.assert_called_once()
    call_url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs["url"]
    assert "elevenlabs.io" in call_url


# ---------------------------------------------------------------------------
# Test: obter_voz_idioma() preservation for all existing language codes
# ---------------------------------------------------------------------------


class TestObterVozIdiomaPreservation:
    """Ensures obter_voz_idioma() returns correct voices for all known languages."""

    @pytest.mark.parametrize("idioma,expected_voice", list(VOZES_POR_IDIOMA.items()))
    def test_exact_match_all_languages(self, idioma, expected_voice):
        """Each language code in VOZES_POR_IDIOMA returns its mapped voice."""
        assert obter_voz_idioma(idioma) == expected_voice

    def test_prefix_match_en(self):
        """Prefix 'en' matches first en-* entry."""
        result = obter_voz_idioma("en")
        assert result.startswith("en-")

    def test_prefix_match_es(self):
        """Prefix 'es' matches first es-* entry."""
        result = obter_voz_idioma("es")
        assert result.startswith("es-")

    def test_prefix_match_pt(self):
        """Prefix 'pt' matches first pt-* entry."""
        result = obter_voz_idioma("pt")
        assert result.startswith("pt-")

    def test_unknown_language_falls_back_to_pt_br(self):
        """Unknown language code falls back to pt-BR-FranciscaNeural."""
        result = obter_voz_idioma("xx-YY")
        assert result == "pt-BR-FranciscaNeural"

    def test_empty_string_falls_back(self):
        """Empty string falls back to pt-BR."""
        result = obter_voz_idioma("")
        assert result == "pt-BR-FranciscaNeural"

    def test_all_voices_are_neural(self):
        """All mapped voices end with 'Neural' (Azure Neural TTS requirement)."""
        for idioma, voz in VOZES_POR_IDIOMA.items():
            assert voz.endswith("Neural"), f"Voice for {idioma} is not Neural: {voz}"

    def test_catalog_count_unchanged(self):
        """VOZES_POR_IDIOMA has exactly 11 entries (preservation check)."""
        assert len(VOZES_POR_IDIOMA) == 11

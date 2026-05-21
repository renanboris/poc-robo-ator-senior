"""
Unit tests for _azure_premium_synthesize() in main.py.
Tests cover: missing credentials fallback, successful synthesis, HTTP error fallback,
network exception fallback, and security (no credential logging).
"""

import importlib
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
]
_dep_mocks = {dep: mock.MagicMock() for dep in _heavy_deps}

with mock.patch.dict("sys.modules", _dep_mocks):
    if "main" in sys.modules:
        del sys.modules["main"]
    import main as _main_module

from voice_catalog import VoiceEntry, VOICE_CATALOG

# Use the premium voice entry for tests
_PREMIUM_ENTRY = VOICE_CATALOG["en-US-AvaMultilingualNeural"]
_SAMPLE_TEXT = "Hello, this is a test."


@pytest.fixture
def output_path(tmp_path):
    return str(tmp_path / "output.mp3")


@pytest.mark.asyncio
async def test_returns_false_when_key_missing(output_path):
    """When AZURE_TTS_KEY is missing, function returns False (fallback)."""
    env = os.environ.copy()
    env.pop("AZURE_TTS_KEY", None)
    env.pop("AZURE_TTS_REGION", None)
    env["AZURE_TTS_REGION"] = "eastus"
    with mock.patch.dict(os.environ, env, clear=True):
        result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)
    assert result is False
    assert not os.path.exists(output_path)


@pytest.mark.asyncio
async def test_returns_false_when_region_missing(output_path):
    """When AZURE_TTS_REGION is missing, function returns False (fallback)."""
    env = os.environ.copy()
    env.pop("AZURE_TTS_KEY", None)
    env.pop("AZURE_TTS_REGION", None)
    env["AZURE_TTS_KEY"] = "fake-key"
    with mock.patch.dict(os.environ, env, clear=True):
        result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)
    assert result is False
    assert not os.path.exists(output_path)


@pytest.mark.asyncio
async def test_returns_false_when_both_missing(output_path):
    """When both credentials are missing, function returns False."""
    env = os.environ.copy()
    env.pop("AZURE_TTS_KEY", None)
    env.pop("AZURE_TTS_REGION", None)
    with mock.patch.dict(os.environ, env, clear=True):
        result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)
    assert result is False


@pytest.mark.asyncio
async def test_returns_true_on_http_200(output_path):
    """On HTTP 200, writes response content to output_path and returns True."""
    fake_audio = b"\xff\xfb\x90\x00" * 100  # fake MP3 bytes

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_audio

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "test-key", "AZURE_TTS_REGION": "eastus"}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp):
            result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    assert result is True
    assert os.path.exists(output_path)
    with open(output_path, "rb") as f:
        assert f.read() == fake_audio


@pytest.mark.asyncio
async def test_returns_false_on_http_error(output_path):
    """On non-200 HTTP status, returns False without writing file."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 401
    mock_resp.content = b"Unauthorized"

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "test-key", "AZURE_TTS_REGION": "eastus"}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp):
            result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    assert result is False
    assert not os.path.exists(output_path)


@pytest.mark.asyncio
async def test_returns_false_on_network_exception(output_path):
    """On network/timeout exception, returns False without writing file."""
    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "test-key", "AZURE_TTS_REGION": "eastus"}):
        with mock.patch.object(_main_module.requests, "post", side_effect=ConnectionError("Network unreachable")):
            result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    assert result is False
    assert not os.path.exists(output_path)


@pytest.mark.asyncio
async def test_returns_false_on_timeout(output_path):
    """On timeout exception, returns False."""
    import requests as req

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "test-key", "AZURE_TTS_REGION": "brazilsouth"}):
        with mock.patch.object(_main_module.requests, "post", side_effect=req.exceptions.Timeout("Request timed out")):
            result = await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    assert result is False


@pytest.mark.asyncio
async def test_never_logs_credential_values(output_path, caplog):
    """Credential values must never appear in log messages."""
    import logging

    secret_key = "super-secret-key-12345"
    secret_region = "my-secret-region"

    mock_resp = mock.MagicMock()
    mock_resp.status_code = 500
    mock_resp.content = b"Internal Server Error"

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": secret_key, "AZURE_TTS_REGION": secret_region}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp):
            with caplog.at_level(logging.DEBUG):
                await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    # Check that neither the key nor region value appears in any log record
    full_log = caplog.text
    assert secret_key not in full_log, "AZURE_TTS_KEY value was logged!"
    assert secret_region not in full_log, "AZURE_TTS_REGION value was logged!"


@pytest.mark.asyncio
async def test_posts_correct_headers(output_path):
    """Verifies the correct headers are sent to Azure endpoint."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake-audio"

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "my-key", "AZURE_TTS_REGION": "brazilsouth"}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp) as mock_post:
            await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
    assert headers["Ocp-Apim-Subscription-Key"] == "my-key"
    assert headers["Content-Type"] == "application/ssml+xml"
    assert headers["X-Microsoft-OutputFormat"] == "audio-16khz-128kbitrate-mono-mp3"


@pytest.mark.asyncio
async def test_posts_to_correct_url(output_path):
    """Verifies the URL uses the region from environment."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake-audio"

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "my-key", "AZURE_TTS_REGION": "brazilsouth"}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp) as mock_post:
            await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    # requests.post is called positionally or with url kwarg
    call_args = mock_post.call_args
    url = call_args.args[0] if call_args.args else call_args.kwargs.get("url")
    assert url == "https://brazilsouth.tts.speech.microsoft.com/cognitiveservices/v1"


@pytest.mark.asyncio
async def test_posts_ssml_encoded_as_utf8(output_path):
    """Verifies the SSML body is sent as UTF-8 encoded bytes."""
    mock_resp = mock.MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"fake-audio"

    with mock.patch.dict(os.environ, {"AZURE_TTS_KEY": "my-key", "AZURE_TTS_REGION": "eastus"}):
        with mock.patch.object(_main_module.requests, "post", return_value=mock_resp) as mock_post:
            await _main_module._azure_premium_synthesize(_SAMPLE_TEXT, _PREMIUM_ENTRY, output_path)

    call_args = mock_post.call_args
    data = call_args.kwargs.get("data") or call_args[1].get("data")
    assert isinstance(data, bytes)
    # Should be valid UTF-8
    decoded = data.decode("utf-8")
    assert "<speak" in decoded
    assert _PREMIUM_ENTRY.voice_id in decoded

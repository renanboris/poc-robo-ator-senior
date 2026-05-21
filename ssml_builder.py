"""
SSML Builder module for Azure TTS voice selection.

Handles SSML document construction and sentence segmentation for
natural-sounding narration generation with Azure Neural voices.
"""

import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Optional

from voice_catalog import VoiceEntry, lookup_voice

_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?;])\s+')


def segment_sentences(text: str) -> list[str]:
    """
    Splits text into sentences at .!?; boundaries.
    Punctuation is preserved as part of the preceding segment.
    Returns a list of non-empty stripped segments.
    """
    raw = _SENTENCE_BOUNDARY.split(text.strip())
    return [s.strip() for s in raw if s.strip()]


def build_ssml(
    text: str,
    voice_entry: VoiceEntry,
    style_override: Optional[str] = None,
) -> str:
    """
    Builds a well-formed SSML document for the given text and voice.

    Raises ValueError if text is empty/whitespace or voice_entry is None.
    Logs a warning and omits <mstts:express-as> if the requested style
    is not supported by the voice.
    """
    if not text or not text.strip():
        raise ValueError("build_ssml: text must be non-empty.")
    if voice_entry is None:
        raise ValueError("build_ssml: voice_entry must not be None (unknown voice_id).")

    # Determine effective style:
    # - If style_override is provided but voice doesn't support styles at all, ignore it
    # - If style_override is provided and voice supports styles, use it (validated below)
    # - If no override, use default_style only if voice supports styles
    if voice_entry.supports_styles:
        style = style_override or voice_entry.default_style
    else:
        style = None

    # Validate that the effective style is in the voice's supported_styles list
    if style and voice_entry.supports_styles and style not in voice_entry.supported_styles:
        logging.warning(
            f"[ssml_builder] Style '{style}' not supported by '{voice_entry.voice_id}'. "
            "Omitting <mstts:express-as>."
        )
        style = None

    sentences = segment_sentences(text)
    if not sentences:
        sentences = [text.strip()]

    # Build inner content: sentences joined by <break time="300ms"/>
    parts = []
    for i, sentence in enumerate(sentences):
        escaped = html.escape(sentence)
        if i > 0:
            parts.append('<break time="300ms"/>')
        parts.append(escaped)
    inner_text = "".join(parts)

    # Wrap in prosody
    prosody_open = (
        f'<prosody rate="{voice_entry.default_rate}" '
        f'pitch="{voice_entry.default_pitch}">'
    )
    prosody_close = "</prosody>"

    # Optionally wrap in express-as
    if style and voice_entry.supports_styles:
        degree = getattr(voice_entry, "default_styledegree", 1.0)
        express_open = (
            f'<mstts:express-as style="{style}" styledegree="{degree:.2f}">'
        )
        express_close = "</mstts:express-as>"
        body = f"{express_open}{prosody_open}{inner_text}{prosody_close}{express_close}"
    else:
        body = f"{prosody_open}{inner_text}{prosody_close}"

    ssml = (
        '<speak version="1.0" '
        f'xml:lang="{voice_entry.locale}" '
        'xmlns="http://www.w3.org/2001/10/synthesis" '
        'xmlns:mstts="http://www.w3.org/2001/mstts">'
        f'<voice name="{voice_entry.voice_id}">'
        f'{body}'
        '</voice>'
        '</speak>'
    )

    # Validate XML before returning
    ET.fromstring(ssml)  # raises xml.etree.ElementTree.ParseError if malformed
    return ssml

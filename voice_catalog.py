"""
Voice Catalog module for Azure TTS voice selection.

Defines the authoritative list of supported Azure Neural voices, their tiers,
SSML style capabilities, and default prosody settings.
"""

from dataclasses import dataclass
from typing import Optional


class ConfigurationError(Exception):
    """Raised when a voice catalog entry has missing or invalid required fields."""

    def __init__(self, voice_id: str, field_name: str):
        self.voice_id = voice_id
        self.field_name = field_name
        super().__init__(
            f"Voice '{voice_id}' is missing required field: '{field_name}'"
        )


UNKNOWN_VOICE_SENTINEL = None  # returned by lookup when voice_id not found


@dataclass(frozen=True)
class VoiceEntry:
    """Immutable representation of an Azure Neural voice configuration."""

    voice_id: str
    display_name: str
    tier: str  # "free" | "premium"
    gender: str  # "female" | "male"
    locale: str  # BCP-47, e.g. "pt-BR"
    supported_styles: tuple[str, ...]
    supports_styles: bool
    default_style: str
    default_styledegree: float  # 0.01–2.0; ignored when supports_styles=False
    default_rate: str  # e.g. "93%"
    default_pitch: str  # e.g. "-2%"


VOICE_CATALOG: dict[str, VoiceEntry] = {
    "pt-BR-FranciscaNeural": VoiceEntry(
        voice_id="pt-BR-FranciscaNeural",
        display_name="Francisca (pt-BR) — Gratuito",
        tier="free",
        gender="female",
        locale="pt-BR",
        supported_styles=("chat", "customerservice"),
        supports_styles=True,
        default_style="chat",
        default_styledegree=1.0,
        default_rate="93%",
        default_pitch="-2%",
    ),
    "pt-BR-BrendaNeural": VoiceEntry(
        voice_id="pt-BR-BrendaNeural",
        display_name="Brenda (pt-BR) — Gratuito",
        tier="free",
        gender="female",
        locale="pt-BR",
        supported_styles=(),
        supports_styles=False,
        default_style="",
        default_styledegree=1.0,
        default_rate="95%",
        default_pitch="0%",
    ),
    "pt-BR-AntonioNeural": VoiceEntry(
        voice_id="pt-BR-AntonioNeural",
        display_name="Antônio (pt-BR) — Gratuito",
        tier="free",
        gender="male",
        locale="pt-BR",
        supported_styles=(),
        supports_styles=False,
        default_style="",
        default_styledegree=1.0,
        default_rate="95%",
        default_pitch="0%",
    ),
    "en-US-AndrewMultilingualNeural": VoiceEntry(
        voice_id="en-US-AndrewMultilingualNeural",
        display_name="Andrew Multilingual (en-US) — Gratuito",
        tier="free",
        gender="male",
        locale="en-US",
        supported_styles=("friendly", "chat"),
        supports_styles=True,
        default_style="friendly",
        default_styledegree=1.0,
        default_rate="95%",
        default_pitch="0%",
    ),
    "en-US-AvaMultilingualNeural": VoiceEntry(
        voice_id="en-US-AvaMultilingualNeural",
        display_name="Ava Multilingual (en-US) — Premium Azure",
        tier="premium",
        gender="female",
        locale="en-US",
        supported_styles=(
            "chat",
            "customerservice",
            "cheerful",
            "empathetic",
            "assistant",
            "narration-professional",
            "newscast-casual",
        ),
        supports_styles=True,
        default_style="narration-professional",
        default_styledegree=1.0,
        default_rate="95%",
        default_pitch="0%",
    ),
}


def lookup_voice(voice_id: str) -> Optional[VoiceEntry]:
    """
    Returns the VoiceEntry for voice_id, or None (UNKNOWN_VOICE_SENTINEL)
    if the voice_id is not found in the catalog.
    """
    return VOICE_CATALOG.get(voice_id, UNKNOWN_VOICE_SENTINEL)


def validate_catalog_entry(entry: VoiceEntry) -> None:
    """
    Validates that a VoiceEntry has all required fields populated.

    Raises ConfigurationError if:
    - supports_styles is not a bool
    - default_style is empty when supports_styles is True
    - default_rate is empty
    - default_pitch is empty

    This is called before audio generation to catch misconfigured entries early.
    """
    if not isinstance(entry.supports_styles, bool):
        raise ConfigurationError(entry.voice_id, "supports_styles")

    if entry.supports_styles and not entry.default_style:
        raise ConfigurationError(entry.voice_id, "default_style")

    if not entry.default_rate:
        raise ConfigurationError(entry.voice_id, "default_rate")

    if not entry.default_pitch:
        raise ConfigurationError(entry.voice_id, "default_pitch")

# Design Document — azure-tts-voice-selection

## Overview

This feature replaces the binary free/paid voice model (edge-tts vs ElevenLabs) with a
structured Azure Neural voice catalog. The new pipeline introduces five voices — four free
(edge-tts) and one premium (Azure Cognitive Services REST API) — and adds SSML-based
synthesis for more natural narration. All changes are additive patches to `main.py` and
`dashboard.html`; the roteiro contract, ElevenLabs path, and audio cache are preserved.

### Key Design Decisions

- **No new heavy SDK dependency.** The premium voice uses the Azure Cognitive Services
  Speech REST API directly (`requests`), which is already a project dependency. This avoids
  adding the `azure-cognitiveservices-speech` SDK (~50 MB).
- **New module `voice_catalog.py`** holds the catalog and lookup logic, keeping `main.py`
  focused on orchestration.
- **New module `ssml_builder.py`** handles all SSML construction, making it independently
  testable.
- **`segment_sentences()` and `concatenate_mp3()`** are added to `ssml_builder.py` and
  `main.py` respectively, co-located with their consumers.
- **`moviepy`** (already available) is used for MP3 concatenation via `AudioFileClip`.
- **Backward compatibility** is enforced at the `gerar_audio()` dispatch layer: `elevenlabs`
  routes unchanged; unknown voices fall back to `pt-BR-FranciscaNeural` with a warning.

---

## Architecture

```
dashboard.html (UI)
    │  voice selector change → mudarVozIA()
    │  salvarRoteiro() → POST /api/roteiros/{arquivo}
    ▼
app.py (FastAPI)
    │  salvar_roteiro() → validates + writes roteiro JSON
    ▼
main.py — gerar_audio()
    │
    ├─ voz == "elevenlabs"  ──────────────────────────────► ElevenLabs API (unchanged)
    │
    ├─ voz in VOICE_CATALOG (free tier)
    │       │
    │       ├─ validate_catalog_entry()  ◄── voice_catalog.py
    │       ├─ preprocess_text()         (existing pronunciation rules)
    │       ├─ segment_sentences()       ◄── ssml_builder.py
    │       ├─ for each sentence:
    │       │     build_ssml()           ◄── ssml_builder.py
    │       │     edge_tts.Communicate(ssml, voice_id).save(tmp_mp3)
    │       └─ concatenate_mp3()  (moviepy)  ──► arquivo_mp3
    │
    ├─ voz in VOICE_CATALOG (premium tier)
    │       │
    │       ├─ read AZURE_TTS_KEY / AZURE_TTS_REGION from env
    │       ├─ if missing → fallback to FranciscaNeural (free path)
    │       ├─ build_ssml()              ◄── ssml_builder.py
    │       ├─ POST https://{region}.tts.speech.microsoft.com/...
    │       └─ on failure → fallback to FranciscaNeural (free path)
    │
    └─ voz unknown (not catalog, not elevenlabs)
            └─ log warning → fallback to FranciscaNeural (free path)
```

---

## Components and Interfaces

### 2.1 `voice_catalog.py` — Voice_Catalog

A new module at the project root. Contains the catalog as a module-level dict and a
lookup function.

```python
from dataclasses import dataclass, field
from typing import Optional

UNKNOWN_VOICE_SENTINEL = None  # returned by lookup when voice_id not found

@dataclass(frozen=True)
class VoiceEntry:
    voice_id:          str
    display_name:      str
    tier:              str          # "free" | "premium"
    gender:            str          # "female" | "male"
    locale:            str          # BCP-47, e.g. "pt-BR"
    supported_styles:  tuple[str, ...]
    supports_styles:   bool
    default_style:     str
    default_styledegree: float      # 0.01–2.0; ignored when supports_styles=False
    default_rate:      str          # e.g. "93%"
    default_pitch:     str          # e.g. "-2%"

VOICE_CATALOG: dict[str, VoiceEntry] = {
    "pt-BR-FranciscaNeural": VoiceEntry(
        voice_id="pt-BR-FranciscaNeural",
        display_name="Francisca (pt-BR) — Gratuito",
        tier="free", gender="female", locale="pt-BR",
        supported_styles=("chat", "customerservice"),
        supports_styles=True,
        default_style="chat", default_styledegree=1.0,
        default_rate="93%", default_pitch="-2%",
    ),
    "pt-BR-BrendaNeural": VoiceEntry(
        voice_id="pt-BR-BrendaNeural",
        display_name="Brenda (pt-BR) — Gratuito",
        tier="free", gender="female", locale="pt-BR",
        supported_styles=(),
        supports_styles=False,
        default_style="", default_styledegree=1.0,
        default_rate="95%", default_pitch="0%",
    ),
    "pt-BR-AntonioNeural": VoiceEntry(
        voice_id="pt-BR-AntonioNeural",
        display_name="Antônio (pt-BR) — Gratuito",
        tier="free", gender="male", locale="pt-BR",
        supported_styles=(),
        supports_styles=False,
        default_style="", default_styledegree=1.0,
        default_rate="95%", default_pitch="0%",
    ),
    "en-US-AndrewMultilingualNeural": VoiceEntry(
        voice_id="en-US-AndrewMultilingualNeural",
        display_name="Andrew Multilingual (en-US) — Gratuito",
        tier="free", gender="male", locale="en-US",
        supported_styles=("friendly", "chat"),
        supports_styles=True,
        default_style="friendly", default_styledegree=1.0,
        default_rate="95%", default_pitch="0%",
    ),
    "en-US-AvaMultilingualNeural": VoiceEntry(
        voice_id="en-US-AvaMultilingualNeural",
        display_name="Ava Multilingual (en-US) — Premium Azure",
        tier="premium", gender="female", locale="en-US",
        supported_styles=("chat", "customerservice", "cheerful", "empathetic",
                          "assistant", "narration-professional", "newscast-casual"),
        supports_styles=True,
        default_style="narration-professional", default_styledegree=1.0,
        default_rate="95%", default_pitch="0%",
    ),
}

def lookup_voice(voice_id: str) -> VoiceEntry | None:
    """Returns the VoiceEntry for voice_id, or UNKNOWN_VOICE_SENTINEL if not found."""
    return VOICE_CATALOG.get(voice_id, UNKNOWN_VOICE_SENTINEL)
```

### 2.2 `ssml_builder.py` — SSML_Builder + Sentence_Segmenter

A new module at the project root.

```python
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

    style = style_override or (voice_entry.default_style if voice_entry.supports_styles else None)

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
```

### 2.3 `concatenate_mp3()` — Audio_Concatenator

Added to `main.py` (or a small helper imported by it). Uses `moviepy`, already available.

```python
import os
import tempfile
from moviepy.editor import AudioFileClip, concatenate_audioclips

def concatenate_mp3(segments: list[str], output_path: str) -> None:
    """
    Merges a list of MP3 file paths into a single MP3 at output_path.
    Uses moviepy AudioFileClip. Cleans up clips after writing.
    """
    clips = []
    try:
        for seg in segments:
            clips.append(AudioFileClip(seg))
        final = concatenate_audioclips(clips)
        final.write_audiofile(output_path, logger=None)
    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass
```

### 2.4 `gerar_audio()` — Narration_Engine patches in `main.py`

The existing `gerar_audio()` function is patched at the dispatch layer. The ElevenLabs
branch is untouched. The old plain edge-tts branch is replaced by the new SSML path.

**New dispatch logic (pseudocode):**

```
if voz == "elevenlabs":
    → existing ElevenLabs branch (no changes)

elif lookup_voice(voz) is not None:
    entry = lookup_voice(voz)
    validate_catalog_entry(entry)          # raises ConfigurationError if field missing
    texto_falado = preprocess(texto)       # existing pronunciation rules
    sentences = segment_sentences(texto_falado)
    if not sentences:
        sentences = [texto_falado]

    if entry.tier == "premium":
        → azure_premium_synthesize(texto_falado, entry, arquivo_mp3)
        # on failure → fallback to FranciscaNeural free path
    else:
        → azure_free_synthesize(sentences, entry, arquivo_mp3)

else:
    logging.warning(f"Unknown voz_ia '{voz}', falling back to pt-BR-FranciscaNeural")
    entry = lookup_voice("pt-BR-FranciscaNeural")
    → azure_free_synthesize(sentences, entry, arquivo_mp3)
```

**`azure_free_synthesize()` (new async helper):**

```python
async def _azure_free_synthesize(
    sentences: list[str], entry: VoiceEntry, output_path: str
) -> None:
    if len(sentences) == 1:
        ssml = build_ssml(sentences[0], entry)
        await edge_tts.Communicate(ssml, entry.voice_id).save(output_path)
        return

    tmp_dir = tempfile.mkdtemp()
    segment_paths = []
    try:
        for i, sentence in enumerate(sentences):
            try:
                ssml = build_ssml(sentence, entry)
                seg_path = os.path.join(tmp_dir, f"seg_{i}.mp3")
                await edge_tts.Communicate(ssml, entry.voice_id).save(seg_path)
                segment_paths.append(seg_path)
            except Exception as e:
                logging.error(f"[audio] Segment {i} failed: '{sentence[:40]}' — {e}")
        if segment_paths:
            concatenate_mp3(segment_paths, output_path)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
```

**`azure_premium_synthesize()` (new async helper):**

```python
async def _azure_premium_synthesize(
    text: str, entry: VoiceEntry, output_path: str
) -> bool:
    """Returns True on success, False on failure (caller falls back)."""
    key    = os.getenv("AZURE_TTS_KEY", "")
    region = os.getenv("AZURE_TTS_REGION", "")
    if not key or not region:
        logging.warning(
            "[audio] AZURE_TTS_KEY or AZURE_TTS_REGION missing. "
            "Falling back to pt-BR-FranciscaNeural."
        )
        return False
    try:
        ssml = build_ssml(text, entry)
        url  = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        headers = {
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
        }
        resp = requests.post(url, data=ssml.encode("utf-8"), headers=headers, timeout=30)
        if resp.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return True
        else:
            logging.error(
                f"[audio] Azure premium TTS failed: HTTP {resp.status_code}. "
                "Falling back to pt-BR-FranciscaNeural."
            )
            return False
    except Exception as e:
        logging.error(
            f"[audio] Azure premium TTS exception: {type(e).__name__}. "
            "Falling back to pt-BR-FranciscaNeural."
        )
        return False
```

### 2.5 Dashboard UI — `dashboard.html`

The `renderizarPassos()` function's "Estúdio de Locução" card is updated. The `mudarVozIA()`
function gains a revert-on-failure path.

**New voice selector HTML (inside `cfgDiv.innerHTML`):**

```html
<select class="field-select" id="voz-ia-select" style="max-width:320px;"
        onchange="mudarVozIA(this.value)">
  <optgroup label="Gratuito">
    <option value="pt-BR-FranciscaNeural">Francisca (pt-BR) — Gratuito</option>
    <option value="pt-BR-BrendaNeural">Brenda (pt-BR) — Gratuito</option>
    <option value="pt-BR-AntonioNeural">Antônio (pt-BR) — Gratuito</option>
    <option value="en-US-AndrewMultilingualNeural">Andrew Multilingual (en-US) — Gratuito</option>
  </optgroup>
  <optgroup label="Premium Azure">
    <option value="en-US-AvaMultilingualNeural">Ava Multilingual (en-US) — Premium Azure</option>
  </optgroup>
</select>
<div id="premium-cost-notice" style="display:none; margin-top:8px; font-size:11px;
     color:var(--amber); background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.2);
     border-radius:6px; padding:6px 10px;">
  ⚠️ Esta voz requer uma chave Azure Cognitive Services (<code>AZURE_TTS_KEY</code>
  e <code>AZURE_TTS_REGION</code> no <code>.env</code>). Pode gerar custos de uso.
</div>
```

**Updated `mudarVozIA()` JS:**

```javascript
async function mudarVozIA(valor) {
  const select = document.getElementById('voz-ia-select');
  const previousValue = select.value;  // capture before mutation

  if (!roteiroAtual.configuracao_gravacao) {
    roteiroAtual.configuracao_gravacao = {
      gravar_video: true, pasta_destino: "videos_gerados",
      voz_ia: "pt-BR-FranciscaNeural"
    };
  }
  roteiroAtual.configuracao_gravacao.voz_ia = valor;

  const notice = document.getElementById('premium-cost-notice');
  if (notice) notice.style.display = valor === 'en-US-AvaMultilingualNeural' ? 'block' : 'none';

  try {
    await salvarRoteiro(false);
    toast('🎙️ Voz atualizada!', 'success');
  } catch (e) {
    // Revert on failure
    roteiroAtual.configuracao_gravacao.voz_ia = previousValue;
    select.value = previousValue;
    if (notice) notice.style.display = previousValue === 'en-US-AvaMultilingualNeural' ? 'block' : 'none';
    toast('Erro ao salvar voz: ' + e.message, 'error');
  }
}
```

**Selector initialization on roteiro load** (inside `carregarRoteiro()` or equivalent):

```javascript
const vozAtual = roteiroAtual?.configuracao_gravacao?.voz_ia || 'pt-BR-FranciscaNeural';
const select = document.getElementById('voz-ia-select');
if (select) {
  // If voz_ia is not a known option, default to FranciscaNeural display
  const knownValues = Array.from(select.options).map(o => o.value);
  select.value = knownValues.includes(vozAtual) ? vozAtual : 'pt-BR-FranciscaNeural';
  const notice = document.getElementById('premium-cost-notice');
  if (notice) notice.style.display = select.value === 'en-US-AvaMultilingualNeural' ? 'block' : 'none';
}
```

---

## Data Models

### VoiceEntry (dataclass)

| Field | Type | Description |
|---|---|---|
| `voice_id` | `str` | Azure Neural voice identifier (e.g. `pt-BR-FranciscaNeural`) |
| `display_name` | `str` | Human-readable label shown in the UI |
| `tier` | `str` | `"free"` or `"premium"` |
| `gender` | `str` | `"female"` or `"male"` |
| `locale` | `str` | BCP-47 locale (e.g. `pt-BR`, `en-US`) |
| `supported_styles` | `tuple[str, ...]` | SSML styles accepted by this voice |
| `supports_styles` | `bool` | Whether `<mstts:express-as>` is supported |
| `default_style` | `str` | Default SSML style (empty string when `supports_styles=False`) |
| `default_styledegree` | `float` | Style intensity in `[0.01, 2.0]` |
| `default_rate` | `str` | Prosody rate as percentage string (e.g. `"93%"`) |
| `default_pitch` | `str` | Prosody pitch as relative percentage string (e.g. `"-2%"`) |

### Roteiro `configuracao_gravacao.voz_ia` field

No schema change. The field already exists as `str` with default `"pt-BR-FranciscaNeural"`.
Valid values after this feature: any `voice_id` in `VOICE_CATALOG`, or `"elevenlabs"`.

### Environment Variables (new)

| Variable | Required for | Description |
|---|---|---|
| `AZURE_TTS_KEY` | Premium voice only | Azure Cognitive Services subscription key |
| `AZURE_TTS_REGION` | Premium voice only | Azure region (e.g. `eastus`, `brazilsouth`) |

Both must be added to `.env.example` with placeholder values. Neither is ever logged or
written to any file.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Lookup sentinel for unknown voice identifiers

*For any* string that is not a key in `VOICE_CATALOG`, calling `lookup_voice()` with that string SHALL return `None` (the sentinel value) without raising an exception.

**Validates: Requirements 1.6**

### Property 2: SSML well-formedness

*For any* non-empty text string and *any* valid `VoiceEntry` from the catalog, `build_ssml(text, voice_entry)` SHALL produce output that is parseable by `xml.etree.ElementTree.fromstring()` without raising a `ParseError`.

**Validates: Requirements 3.1, 3.7**

### Property 3: Express-as wrapper presence when style is supported

*For any* non-empty text and *any* `VoiceEntry` where `supports_styles=True` and the effective style is in `supported_styles`, the SSML output SHALL contain an `<mstts:express-as>` element with the correct `style` and `styledegree` attributes.

**Validates: Requirements 3.2, 5.5**

### Property 4: Prosody attributes always present

*For any* non-empty text and *any* valid `VoiceEntry`, the SSML output SHALL contain a `<prosody>` element with `rate` equal to the voice entry's `default_rate` and `pitch` equal to the voice entry's `default_pitch`.

**Validates: Requirements 3.3**

### Property 5: Break tags between sentences

*For any* text containing N sentences (where N > 1, as determined by `segment_sentences()`), the SSML output SHALL contain exactly N − 1 occurrences of `<break time="300ms"/>`.

**Validates: Requirements 3.4**

### Property 6: xml:lang matches voice locale

*For any* non-empty text and *any* valid `VoiceEntry`, the SSML output's root `<speak>` element SHALL have `xml:lang` equal to the voice entry's `locale` field.

**Validates: Requirements 3.5**

### Property 7: Express-as omitted when style is unsupported

*For any* non-empty text and *any* `VoiceEntry` where either `supports_styles=False` or the requested style is not in `supported_styles`, the SSML output SHALL NOT contain an `<mstts:express-as>` element.

**Validates: Requirements 3.6, 5.7**

### Property 8: Sentence segmentation preserves punctuation

*For any* text string containing sentence-ending punctuation (`.`, `!`, `?`, `;`) followed by whitespace, `segment_sentences()` SHALL produce segments where each segment (except possibly the last) ends with one of those punctuation characters, and the concatenation of all segments (with single space between them) reconstructs the original text content.

**Validates: Requirements 4.1**

### Property 9: SSML_Builder text preservation (no pronunciation substitution, only XML escaping)

*For any* text containing arbitrary characters (including XML-special characters `<`, `>`, `&`, `"`, `'`), `build_ssml()` SHALL embed the text in the SSML output using only XML entity escaping — it SHALL NOT apply pronunciation substitutions (e.g., "GED" remains "GED", "X" remains "X" in the SSML text content).

**Validates: Requirements 8.2, 8.3**

### Property 10: Unknown voz_ia triggers fallback to FranciscaNeural

*For any* string that is not a key in `VOICE_CATALOG` and is not `"elevenlabs"`, the Narration_Engine dispatch logic SHALL route to the `pt-BR-FranciscaNeural` catalog entry for synthesis.

**Validates: Requirements 7.3**

### Property 11: Known voz_ia uses catalog entry directly

*For any* `voice_id` that is a key in `VOICE_CATALOG`, the Narration_Engine dispatch logic SHALL use that catalog entry for synthesis without triggering any fallback path.

**Validates: Requirements 7.4**

### Property 12: Audio cache hit skips generation

*For any* `id_unico` and `id_treinamento` where the file `audios_gerados/{limpar_nome(id_treinamento)}/audio_{id_unico}.mp3` already exists on disk, `gerar_audio()` SHALL return that file path without invoking any TTS synthesis call.

**Validates: Requirements 9.1, 9.2**

---

## Error Handling

### SSML_Builder Errors

| Condition | Behavior |
|---|---|
| Empty/whitespace text | `build_ssml()` raises `ValueError` with descriptive message |
| `voice_entry` is `None` | `build_ssml()` raises `ValueError` with descriptive message |
| Requested style not in `supported_styles` | Log warning, omit `<mstts:express-as>`, continue with plain prosody |
| Generated SSML fails XML validation | `xml.etree.ElementTree.ParseError` propagates to caller (indicates a bug) |

### Voice_Catalog Errors

| Condition | Behavior |
|---|---|
| `voice_id` not found | `lookup_voice()` returns `None` (sentinel) |
| Required field missing from entry | `validate_catalog_entry()` raises `ConfigurationError` with voice_id and field name |

### Narration_Engine Errors

| Condition | Behavior |
|---|---|
| `voz_ia` unknown (not catalog, not elevenlabs) | Log warning → fallback to `pt-BR-FranciscaNeural` |
| `AZURE_TTS_KEY` or `AZURE_TTS_REGION` missing for premium | Log warning (no credential values) → fallback to `pt-BR-FranciscaNeural` |
| Premium REST API returns non-200 | Log error (status code only, no key) → fallback to `pt-BR-FranciscaNeural` |
| Premium REST API network/timeout error | Log error (exception type only) → fallback to `pt-BR-FranciscaNeural` |
| Individual sentence segment fails synthesis | Log error (segment index + truncated text) → skip segment, continue concatenation |
| All segments fail synthesis | No output file produced; `gerar_audio()` returns `None` |
| Pronunciation preprocessor raises exception | Log error + original text → do NOT pass to SSML_Builder; `gerar_audio()` returns `None` |
| `_audio_manifest_lock` cannot be acquired (non-blocking) | Skip manifest update silently; no exception, no partial write |

### Dashboard UI Errors

| Condition | Behavior |
|---|---|
| `salvarRoteiro()` fails after voice change | Display error toast → revert selector to previous value |
| `voz_ia` in roteiro not in catalog | Display selector defaulted to `pt-BR-FranciscaNeural` without modifying stored roteiro |

### Security Invariants

- `AZURE_TTS_KEY` and `AZURE_TTS_REGION` values are NEVER included in log messages, generated files, or roteiro artifacts.
- All error messages reference the variable name (e.g., "AZURE_TTS_KEY missing") but never the value.

---

## Testing Strategy

### Property-Based Tests (Hypothesis)

The project already uses [Hypothesis](https://hypothesis.readthedocs.io/) (evidenced by `.hypothesis/` directory in the workspace). Each correctness property maps to one property-based test with a minimum of 100 iterations.

**Library:** `hypothesis` (already installed)

**Test file:** `tests/test_ssml_properties.py`

| Property | Test Function | Key Generators |
|---|---|---|
| 1 — Lookup sentinel | `test_lookup_unknown_voice_returns_none` | `st.text()` filtered to exclude catalog keys |
| 2 — SSML well-formedness | `test_build_ssml_produces_valid_xml` | `st.text(min_size=1)` × catalog entries |
| 3 — Express-as presence | `test_express_as_present_when_style_supported` | `st.text(min_size=1)` × entries with `supports_styles=True` |
| 4 — Prosody attributes | `test_prosody_rate_and_pitch_present` | `st.text(min_size=1)` × all catalog entries |
| 5 — Break tags count | `test_break_tags_equal_sentence_count_minus_one` | `st.text()` with injected `.!?;` + whitespace |
| 6 — xml:lang matches locale | `test_xml_lang_matches_voice_locale` | `st.text(min_size=1)` × all catalog entries |
| 7 — Express-as omitted | `test_express_as_omitted_when_unsupported` | `st.text(min_size=1)` × entries with `supports_styles=False` + random unsupported styles |
| 8 — Segmentation preserves punctuation | `test_segment_sentences_preserves_punctuation` | `st.text()` with injected sentence-ending punctuation |
| 9 — Text preservation (no substitution) | `test_ssml_builder_preserves_text_content` | `st.text(min_size=1, alphabet=st.characters(whitelist_categories=('L','N','P','S','Z')))` |
| 10 — Unknown voz_ia fallback | `test_unknown_voz_ia_triggers_fallback` | `st.text()` filtered to exclude catalog keys and "elevenlabs" |
| 11 — Known voz_ia direct use | `test_known_voz_ia_uses_catalog_entry` | `st.sampled_from(list(VOICE_CATALOG.keys()))` |
| 12 — Cache hit skips generation | `test_cache_hit_skips_tts_call` | `st.text(min_size=1)` for id_unico × mock filesystem |

**Tag format:** Each test is annotated with:
```python
# Feature: azure-tts-voice-selection, Property {N}: {property_text}
```

**Configuration:** Each property test uses `@settings(max_examples=100)`.

### Unit Tests (pytest)

**Test file:** `tests/test_voice_catalog.py`, `tests/test_ssml_builder.py`

| Area | Test Cases |
|---|---|
| Voice_Catalog structure | 5 entries exist; 4 free + 1 premium; all fields populated; rate/pitch format valid |
| `build_ssml()` edge cases | Empty text → ValueError; None voice → ValueError; single sentence → no break tag |
| `segment_sentences()` examples | "Hello. World" → 2 segments; "No punctuation" → 1 segment; "A! B? C." → 3 segments |
| `concatenate_mp3()` | Single file → copy; multiple files → merged output exists |
| Pronunciation preprocessing | "GED" → "gédi"; "X" → "Éks"; underscores → spaces; pipes → commas |
| Premium fallback | Missing key → fallback; HTTP 401 → fallback; timeout → fallback |
| ElevenLabs bypass | `voz_ia="elevenlabs"` → ElevenLabs branch, no SSML_Builder call |
| `obter_voz_idioma()` preservation | All existing language codes still return valid voice strings |

### Integration Tests

**Test file:** `tests/test_narration_integration.py`

| Scenario | Description |
|---|---|
| Free voice end-to-end | Mock `edge_tts.Communicate`, verify SSML passed, MP3 written |
| Premium voice end-to-end | Mock `requests.post`, verify correct URL/headers, MP3 written |
| Multi-sentence concatenation | 3-sentence text → 3 TTS calls → 1 merged MP3 |
| Cache hit | Pre-create MP3 file → verify no TTS call made |
| Manifest lock contention | Hold lock → verify manifest update skipped gracefully |

### Manual Validation

| Scenario | Steps |
|---|---|
| Dashboard voice selector | Open roteiro editor → verify optgroups, cost notice toggle, save/revert |
| Audio quality | Generate audio with each voice → listen for natural prosody and breaks |
| Premium voice with real key | Set `AZURE_TTS_KEY`/`AZURE_TTS_REGION` → select Ava → verify audio generated |
| Backward compatibility | Load old roteiro with `voz_ia: "pt-BR-FranciscaNeural"` → verify works unchanged |

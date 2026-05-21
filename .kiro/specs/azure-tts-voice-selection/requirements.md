# Requirements Document

## Introduction

This feature enhances the Azure TTS (edge-tts) narration pipeline in Senior Training OS. The current system offers a single free Azure voice (`pt-BR-FranciscaNeural`) and one paid ElevenLabs option. The goal is to replace that binary choice with a richer set of Azure Neural voices — multiple free options plus one premium Azure option — and to introduce SSML-based audio generation to produce more natural, human-sounding narration. All changes must preserve the roteiro as the central contract and remain compatible with the video, SCORM, and PDF output pipelines.

## Glossary

- **Narration_Engine**: The component in `main.py` responsible for generating MP3 audio from narration text using edge-tts or external TTS APIs.
- **SSML_Builder**: The new module responsible for constructing well-formed SSML documents from plain narration text and voice configuration.
- **Voice_Catalog**: The authoritative list of supported Azure Neural voices, their tiers (free/premium), and their associated SSML style capabilities.
- **Roteiro**: The central JSON artifact that drives all pipeline outputs. Contains `configuracao_gravacao.voz_ia` to specify the selected voice.
- **Dashboard**: The FastAPI-backed web UI (`app.py` + `dashboard.html`) where users configure and edit roteiros.
- **Sentence_Segmenter**: The sub-component that splits narration text into individual sentences before per-sentence audio generation.
- **Audio_Concatenator**: The sub-component that merges per-sentence MP3 segments into a single MP3 file for a narration unit.
- **SSML_Style**: An Azure-specific speech style applied via `<mstts:express-as>`, such as `chat`, `friendly`, `customerservice`, `cheerful`, `empathetic`, `assistant`, `narration-professional`, or `newscast-casual`.
- **Free_Voice**: An Azure Neural voice available via edge-tts without an Azure Cognitive Services subscription key.
- **Premium_Voice**: An Azure Neural voice that requires an Azure Cognitive Services subscription key (e.g., `en-US-AvaMultilingualNeural`).
- **voz_ia**: The field in `configuracao_gravacao` that stores the selected voice identifier for a roteiro.
- **Pronunciation_Preprocessor**: The existing text normalization logic in `gerar_audio()` that corrects pronunciation before synthesis.

---

## Requirements

### Requirement 1: Expanded Voice Catalog

**User Story:** As a training author, I want to choose from multiple Azure Neural voices with clear free/premium labeling, so that I can select the best voice for my audience without being forced into ElevenLabs.

#### Acceptance Criteria

1. THE Voice_Catalog SHALL contain exactly five distinct Azure Neural voice entries: `pt-BR-FranciscaNeural`, `pt-BR-BrendaNeural`, `pt-BR-AntonioNeural`, `en-US-AndrewMultilingualNeural`, and `en-US-AvaMultilingualNeural`.
2. THE Voice_Catalog SHALL classify `pt-BR-FranciscaNeural`, `pt-BR-BrendaNeural`, `pt-BR-AntonioNeural`, and `en-US-AndrewMultilingualNeural` as Free_Voice entries.
3. THE Voice_Catalog SHALL classify `en-US-AvaMultilingualNeural` as a Premium_Voice entry.
4. THE Voice_Catalog SHALL expose, for each entry, the voice identifier, display name, tier (free or premium), gender, and a non-empty list of at least one supported SSML_Style.
5. WHEN a new voice is added to the Voice_Catalog, THE Voice_Catalog SHALL ensure that all previously valid `voz_ia` values continue to resolve to a valid catalog entry without modification.
6. IF a roteiro references a `voz_ia` value that is not present in the Voice_Catalog, THEN THE Voice_Catalog lookup SHALL return a defined sentinel value indicating an unknown voice, rather than raising an unhandled exception.

---

### Requirement 2: Voice Selection UI in the Dashboard

**User Story:** As a training author, I want the "Estúdio de Locução" card in the roteiro editor to show all available Azure voices grouped by tier, so that I can make an informed choice before generating audio.

#### Acceptance Criteria

1. WHEN the roteiro editor renders the "Estúdio de Locução" card, THE Dashboard SHALL display a voice selector containing one `<option>` element per Voice_Catalog entry, where each option's visible text is the entry's display name and its value is the entry's voice identifier.
2. WHEN the roteiro editor renders the "Estúdio de Locução" card, THE Dashboard SHALL render two labeled `<optgroup>` elements within the voice selector: one with the label "Gratuito" containing all Free_Voice entries, and one with the label "Premium Azure" containing all Premium_Voice entries.
3. WHEN a Free_Voice is selected, THE Dashboard SHALL display the entry's display name without any cost warning element being visible.
4. WHEN the Premium_Voice (`en-US-AvaMultilingualNeural`) is selected, THE Dashboard SHALL display a cost notice informing the user that an Azure Cognitive Services key is required.
5. WHEN the user selects a voice, THE Dashboard SHALL update `configuracao_gravacao.voz_ia` in the roteiro and persist the change via the existing `salvarRoteiro` flow, regardless of whether the cost notice rendered successfully.
6. WHEN the roteiro editor loads a roteiro whose `voz_ia` value matches a Voice_Catalog entry's voice identifier, THE Dashboard SHALL set the voice selector's displayed value to that entry's display name.
7. IF the roteiro's `voz_ia` value does not match any Voice_Catalog entry, THEN THE Dashboard SHALL set the selector's displayed value to `pt-BR-FranciscaNeural`'s display name without modifying the stored roteiro.
8. IF the `salvarRoteiro` call fails after a voice selection change, THEN THE Dashboard SHALL display an error notification to the user and revert the selector to its previous value.

---

### Requirement 3: SSML Document Construction

**User Story:** As a training author, I want narration audio to be generated using SSML so that the output sounds more natural and expressive.

#### Acceptance Criteria

1. THE SSML_Builder SHALL produce a well-formed SSML document for any non-empty narration text and a valid voice identifier, where "valid" means the identifier is present in the Voice_Catalog.
2. THE SSML_Builder SHALL wrap narration content in `<mstts:express-as style="{style}" styledegree="{degree}">` when the selected voice's catalog entry lists the requested SSML_Style as supported, where `{degree}` is a decimal value in the range 0.01–2.00.
3. THE SSML_Builder SHALL apply `<prosody rate="{rate}" pitch="{pitch}">` to the narration content, where `{rate}` is expressed as a percentage string (e.g., `"93%"`) and `{pitch}` is expressed as a relative percentage string (e.g., `"-2%"`).
4. WHEN the narration text contains multiple sentences, THE SSML_Builder SHALL insert a `<break time="300ms"/>` tag between consecutive sentences, where sentence boundaries are detected at occurrences of `.`, `!`, or `?` followed by whitespace or end-of-string.
5. THE SSML_Builder SHALL include the correct `xml:lang` attribute matching the voice's locale (e.g., `pt-BR` for `pt-BR-FranciscaNeural`, `en-US` for `en-US-AvaMultilingualNeural`).
6. IF the selected voice does not support a requested SSML_Style, THEN THE SSML_Builder SHALL omit the `<mstts:express-as>` wrapper, log a warning to the application log, and generate plain prosody-wrapped SSML without raising an error to the caller.
7. THE SSML_Builder SHALL produce output that is valid XML and parseable by a standard XML parser.
8. IF the narration text is empty or the voice identifier is absent from the Voice_Catalog, THEN THE SSML_Builder SHALL raise a `ValueError` identifying the invalid input before producing any output.

---

### Requirement 4: Sentence-by-Sentence Audio Generation

**User Story:** As a training author, I want each narration unit to be synthesized sentence by sentence and then concatenated, so that emotional consistency and prosody are improved across longer narration blocks.

#### Acceptance Criteria

1. WHEN generating audio for a narration unit, THE Sentence_Segmenter SHALL split the text into individual sentences at punctuation boundaries (`.`, `!`, `?`, `;`), preserving the punctuation character as part of the preceding sentence segment.
2. WHEN a sentence segment is non-empty after trimming whitespace, THE Narration_Engine SHALL generate a separate temporary MP3 segment for that sentence using the SSML_Builder.
3. WHEN all sentence segments for a narration unit have been synthesized, THE Audio_Concatenator SHALL merge the segments in their original order into a single MP3 file at the target output path.
4. THE Audio_Concatenator SHALL produce an output MP3 file that is playable by a standard MP3 decoder and whose total duration equals the sum of all individual segment durations within a tolerance of ±100 milliseconds.
5. IF a sentence segment fails to synthesize, THEN THE Narration_Engine SHALL log the failure including the segment index and text, skip that segment, and continue concatenating the remaining successfully synthesized segments.
6. WHEN the narration text contains only one sentence after segmentation, THE Narration_Engine SHALL write the single synthesized MP3 directly to the target output path without invoking the Audio_Concatenator merge step.
7. WHEN sentence segmentation produces zero non-empty segments from a non-empty input text, THE Narration_Engine SHALL treat the entire input text as a single segment and attempt synthesis without raising an unhandled exception.

---

### Requirement 5: Default SSML Style Configuration per Voice

**User Story:** As a training author, I want each voice to have a sensible default SSML style and prosody so that I get good results without manual tuning.

#### Acceptance Criteria

1. THE Voice_Catalog SHALL define a `default_style` field for each voice entry whose value is a style name accepted by the Azure edge-tts engine for that specific voice (e.g., `chat` for `pt-BR-FranciscaNeural`, `friendly` for `en-US-AndrewMultilingualNeural`).
2. THE Voice_Catalog SHALL define `default_rate` and `default_pitch` fields for each voice entry, where `default_rate` is a percentage string in the range `1%`–`200%` and `default_pitch` is a relative percentage string in the range `-50%`–`+50%`.
3. THE Voice_Catalog SHALL define a `supports_styles` boolean field for each voice entry, set to `true` if the voice supports `<mstts:express-as>` styles via edge-tts and `false` otherwise.
4. THE Voice_Catalog SHALL define a `default_styledegree` field for each voice entry where `supports_styles` is `true`, with a value in the range `0.01`–`2.0`.
5. WHEN the Narration_Engine generates audio and no explicit style override is provided, THE SSML_Builder SHALL use the `default_style`, `default_rate`, `default_pitch`, and `default_styledegree` from the Voice_Catalog entry for the selected voice.
6. IF any required catalog field (`default_style`, `default_rate`, `default_pitch`, or `supports_styles`) is absent for a voice entry, THEN THE Narration_Engine SHALL raise a configuration error identifying the voice and the missing field before attempting audio generation.
7. WHEN the selected voice entry has `supports_styles` set to `false`, THE Narration_Engine SHALL invoke plain edge-tts `Communicate` with the voice's `default_rate` and `default_pitch` parameters and SHALL NOT include any `<mstts:express-as>` wrapper in the SSML output.

---

### Requirement 6: Premium Voice Authentication

**User Story:** As a training author, I want the system to use my Azure Cognitive Services key when I select the premium voice, so that the premium voice is accessible without hardcoding credentials.

#### Acceptance Criteria

1. WHEN `en-US-AvaMultilingualNeural` is selected as `voz_ia`, THE Narration_Engine SHALL read the Azure subscription key from the environment variable `AZURE_TTS_KEY` and the region from `AZURE_TTS_REGION`.
2. IF `AZURE_TTS_KEY` or `AZURE_TTS_REGION` is absent or empty when the Premium_Voice is selected, THEN THE Narration_Engine SHALL log a warning, fall back to `pt-BR-FranciscaNeural`, and return a result object that indicates the fallback voice was used instead of the requested premium voice.
3. THE Narration_Engine SHALL never embed the value of `AZURE_TTS_KEY` or `AZURE_TTS_REGION` in any log output, generated file, or roteiro artifact.
4. WHEN the Premium_Voice is used successfully, THE Narration_Engine SHALL generate audio using the Azure Cognitive Services Speech SDK or REST API with SSML input.
5. WHEN valid credentials are present but the Premium_Voice synthesis fails for any reason, including network errors, service limits, authentication rejection, or invalid region, THE Narration_Engine SHALL fall back to `pt-BR-FranciscaNeural`, log the failure reason without including credential values, and return a result object indicating the fallback was used.

---

### Requirement 7: Backward Compatibility with Existing Roteiros

**User Story:** As a training author, I want existing roteiros that reference `pt-BR-FranciscaNeural` or `elevenlabs` to continue working after the update, so that I do not need to manually migrate saved roteiros.

#### Acceptance Criteria

1. WHEN the Narration_Engine receives `voz_ia = "pt-BR-FranciscaNeural"`, THE Narration_Engine SHALL generate audio using the SSML-enhanced edge-tts path with the catalog's default style, rate, and pitch for that voice.
2. WHEN the Narration_Engine receives `voz_ia = "elevenlabs"`, THE Narration_Engine SHALL route the request to the ElevenLabs API branch without invoking the SSML_Builder or the Voice_Catalog lookup.
3. WHEN the Narration_Engine receives a `voz_ia` value that is not present in the Voice_Catalog and is not `"elevenlabs"`, THE Narration_Engine SHALL write a warning to the application log identifying the unrecognized value and fall back to `pt-BR-FranciscaNeural`.
4. WHEN the Narration_Engine receives a `voz_ia` value that is present in the Voice_Catalog, THE Narration_Engine SHALL use that catalog entry directly and SHALL NOT trigger any fallback path.
5. WHEN `obter_voz_idioma()` in `utils.py` is called with any language code that was valid before this feature was introduced, THE function SHALL return a non-empty string that is a valid voice identifier accepted by the Narration_Engine.
6. WHEN the translation endpoint updates `voz_ia` for a translated roteiro and the Narration_Engine subsequently processes that roteiro, THE Narration_Engine SHALL produce an MP3 file at the expected output path without raising an unhandled exception.

---

### Requirement 8: Pronunciation Preprocessing Compatibility

**User Story:** As a training author, I want the existing pronunciation corrections (e.g., "GED" → "gédi", "X" → "Éks") to be applied before SSML generation, so that audio quality is not degraded by the new pipeline.

#### Acceptance Criteria

1. WHEN the Narration_Engine processes narration text, THE Pronunciation_Preprocessor SHALL apply pronunciation substitution rules (e.g., "GED" → "gédi", "X" → "Éks") first, followed by structural normalization rules (underscore-to-space, pipe-to-comma, multi-space collapse), before passing the result to the SSML_Builder.
2. THE SSML_Builder SHALL receive pre-processed plain text and SHALL NOT apply text-level pronunciation substitutions; structural SSML markup added by the SSML_Builder is explicitly excluded from this prohibition.
3. WHEN the Pronunciation_Preprocessor produces output containing XML-special characters (`<`, `>`, `&`, `"`, `'`), THE SSML_Builder SHALL escape those characters using their XML entity equivalents before embedding them in the SSML document, including characters introduced by the preprocessing rules themselves.
4. THE Narration_Engine SHALL preserve the existing underscore-to-space, pipe-to-comma, and multi-space normalization rules in the preprocessing step.
5. IF the Pronunciation_Preprocessor raises an exception during text normalization, THEN THE Narration_Engine SHALL log the error and the original narration text, and SHALL NOT pass partial or unprocessed text to the SSML_Builder.

---

### Requirement 9: Audio Cache Compatibility

**User Story:** As a training author, I want the audio caching behavior to remain unchanged so that re-runs do not regenerate audio that already exists on disk.

#### Acceptance Criteria

1. WHEN an MP3 file already exists at the path constructed using the naming convention `audios_gerados/{nome_pasta}/audio_{id_unico}.mp3`, THE Narration_Engine SHALL skip generation and return that path, regardless of whether SSML is enabled.
2. THE Narration_Engine SHALL use the file naming convention `audio_{id_unico}.mp3` and the directory structure `audios_gerados/{nome_pasta}/` for all generated audio files.
3. WHEN the audio manifest is updated after generation, THE Narration_Engine SHALL attempt to acquire `_audio_manifest_lock` using a non-blocking acquire (timeout=0).
4. IF `_audio_manifest_lock` cannot be acquired within the non-blocking attempt, THEN THE Narration_Engine SHALL skip the manifest update without raising an exception and without writing any partial entry to the manifest dictionary.

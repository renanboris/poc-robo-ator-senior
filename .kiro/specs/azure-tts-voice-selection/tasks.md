# Implementation Plan: Azure TTS Voice Selection

## Overview

This plan implements a structured Azure Neural voice catalog with five voices (four free, one premium), SSML-based synthesis for natural narration, sentence-by-sentence audio generation with concatenation, and a dashboard voice selector UI. The implementation is additive — patching `main.py` and `dashboard.html` while introducing two new modules (`voice_catalog.py` and `ssml_builder.py`).

## Tasks

- [x] 1. Create Voice Catalog module and core interfaces
  - [x] 1.1 Create `voice_catalog.py` with VoiceEntry dataclass and VOICE_CATALOG dict
    - Define the frozen `VoiceEntry` dataclass with all fields (voice_id, display_name, tier, gender, locale, supported_styles, supports_styles, default_style, default_styledegree, default_rate, default_pitch)
    - Populate `VOICE_CATALOG` with all five entries: pt-BR-FranciscaNeural, pt-BR-BrendaNeural, pt-BR-AntonioNeural, en-US-AndrewMultilingualNeural, en-US-AvaMultilingualNeural
    - Implement `lookup_voice()` returning the entry or `None` sentinel
    - Implement `validate_catalog_entry()` raising `ConfigurationError` if required fields are missing
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 5.1, 5.2, 5.3, 5.4, 5.6_

  - [x]* 1.2 Write property test for unknown voice lookup (Property 1)
    - **Property 1: Lookup sentinel for unknown voice identifiers**
    - **Validates: Requirements 1.6**

  - [x]* 1.3 Write unit tests for voice catalog structure
    - Verify 5 entries exist (4 free + 1 premium)
    - Verify all fields are populated and rate/pitch format is valid
    - Verify `validate_catalog_entry()` raises on missing fields
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 5.6_

- [x] 2. Create SSML Builder module
  - [x] 2.1 Create `ssml_builder.py` with `segment_sentences()` function
    - Implement regex-based sentence splitting at `.!?;` boundaries
    - Preserve punctuation as part of the preceding segment
    - Return list of non-empty stripped segments
    - _Requirements: 4.1, 4.7_

  - [x]* 2.2 Write property test for sentence segmentation (Property 8)
    - **Property 8: Sentence segmentation preserves punctuation**
    - **Validates: Requirements 4.1**

  - [x] 2.3 Implement `build_ssml()` function in `ssml_builder.py`
    - Accept text, voice_entry, and optional style_override
    - Raise ValueError for empty text or None voice_entry
    - Build SSML with `<speak>`, `<voice>`, `<prosody>`, and optional `<mstts:express-as>`
    - Insert `<break time="300ms"/>` between sentences
    - Apply XML entity escaping for special characters
    - Validate output with `xml.etree.ElementTree.fromstring()`
    - Log warning and omit express-as when style is unsupported
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 8.2, 8.3_

  - [x]* 2.4 Write property test for SSML well-formedness (Property 2)
    - **Property 2: SSML well-formedness**
    - **Validates: Requirements 3.1, 3.7**

  - [x]* 2.5 Write property test for express-as presence (Property 3)
    - **Property 3: Express-as wrapper presence when style is supported**
    - **Validates: Requirements 3.2, 5.5**

  - [x]* 2.6 Write property test for prosody attributes (Property 4)
    - **Property 4: Prosody attributes always present**
    - **Validates: Requirements 3.3**

  - [x]* 2.7 Write property test for break tags between sentences (Property 5)
    - **Property 5: Break tags between sentences**
    - **Validates: Requirements 3.4**

  - [x]* 2.8 Write property test for xml:lang matching locale (Property 6)
    - **Property 6: xml:lang matches voice locale**
    - **Validates: Requirements 3.5**

  - [x]* 2.9 Write property test for express-as omitted when unsupported (Property 7)
    - **Property 7: Express-as omitted when style is unsupported**
    - **Validates: Requirements 3.6, 5.7**

  - [x]* 2.10 Write property test for text preservation (Property 9)
    - **Property 9: SSML_Builder text preservation (no pronunciation substitution, only XML escaping)**
    - **Validates: Requirements 8.2, 8.3**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement audio concatenation and narration engine patches
  - [x] 4.1 Add `concatenate_mp3()` helper to `main.py`
    - Use moviepy `AudioFileClip` and `concatenate_audioclips`
    - Handle single-file case (direct copy) and multi-file merge
    - Ensure proper cleanup of clips in finally block
    - _Requirements: 4.3, 4.4_

  - [x] 4.2 Implement `_azure_free_synthesize()` async helper in `main.py`
    - For single sentence: build SSML and call edge_tts.Communicate directly
    - For multiple sentences: synthesize each to temp MP3, then concatenate
    - Log and skip failed segments, continue with remaining
    - Clean up temp directory in finally block
    - _Requirements: 4.2, 4.3, 4.5, 4.6, 4.7, 5.5, 5.7_

  - [x] 4.3 Implement `_azure_premium_synthesize()` async helper in `main.py`
    - Read AZURE_TTS_KEY and AZURE_TTS_REGION from environment
    - Return False (triggering fallback) if credentials missing
    - Build SSML and POST to Azure Cognitive Services REST endpoint
    - Return True on success (HTTP 200), False on any failure
    - Never log credential values
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [x] 4.4 Patch `gerar_audio()` dispatch logic in `main.py`
    - Preserve ElevenLabs branch unchanged
    - Add catalog lookup branch: validate entry, preprocess text, segment, route by tier
    - Add unknown voice fallback to pt-BR-FranciscaNeural with warning log
    - Preserve audio cache check (skip if MP3 already exists)
    - Preserve pronunciation preprocessing before SSML generation
    - Handle preprocessing exceptions (log error, return None)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 8.1, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4_

  - [x]* 4.5 Write property test for unknown voz_ia fallback (Property 10)
    - **Property 10: Unknown voz_ia triggers fallback to FranciscaNeural**
    - **Validates: Requirements 7.3**

  - [x]* 4.6 Write property test for known voz_ia direct use (Property 11)
    - **Property 11: Known voz_ia uses catalog entry directly**
    - **Validates: Requirements 7.4**

  - [x]* 4.7 Write property test for audio cache hit (Property 12)
    - **Property 12: Audio cache hit skips generation**
    - **Validates: Requirements 9.1, 9.2**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Update Dashboard UI for voice selection
  - [x] 6.1 Update voice selector HTML in `dashboard.html`
    - Replace existing voice selector with `<select>` containing two `<optgroup>` elements
    - "Gratuito" group: FranciscaNeural, BrendaNeural, AntonioNeural, AndrewMultilingualNeural
    - "Premium Azure" group: AvaMultilingualNeural
    - Add premium cost notice div (hidden by default)
    - Wire `onchange` to `mudarVozIA(this.value)`
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [x] 6.2 Implement updated `mudarVozIA()` JavaScript function
    - Capture previous value before mutation
    - Update `configuracao_gravacao.voz_ia` in roteiro object
    - Toggle premium cost notice visibility
    - Call `salvarRoteiro(false)` and show success toast
    - On failure: revert selector, revert roteiro field, show error toast
    - _Requirements: 2.5, 2.8_

  - [x] 6.3 Add voice selector initialization on roteiro load
    - Set selector value from `configuracao_gravacao.voz_ia` on load
    - Default to pt-BR-FranciscaNeural if stored value not in known options
    - Toggle premium cost notice based on initial value
    - _Requirements: 2.6, 2.7_

- [x] 7. Environment configuration and documentation
  - [x] 7.1 Update `.env.example` with Azure TTS variables
    - Add `AZURE_TTS_KEY=your_azure_tts_key_here` placeholder
    - Add `AZURE_TTS_REGION=brazilsouth` placeholder
    - Add comments explaining these are only needed for premium voice
    - _Requirements: 6.1, 6.3_

- [x] 8. Integration tests and final validation
  - [x]* 8.1 Write integration tests for narration engine
    - Test free voice end-to-end with mocked edge_tts
    - Test premium voice end-to-end with mocked requests.post
    - Test multi-sentence concatenation (3 sentences → 3 TTS calls → 1 merged MP3)
    - Test cache hit skips TTS call
    - Test ElevenLabs bypass (no SSML_Builder call)
    - Test `obter_voz_idioma()` preservation for all existing language codes
    - _Requirements: 4.2, 4.3, 6.4, 7.1, 7.2, 7.5, 9.1_

- [x] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with existing project dependencies (edge-tts, moviepy, requests)
- No new heavy SDK dependencies are introduced (Azure REST API via requests)
- All changes are additive patches preserving backward compatibility

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["2.4", "2.5", "2.6", "2.7", "2.8", "2.9", "2.10"] },
    { "id": 4, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 5, "tasks": ["4.4"] },
    { "id": 6, "tasks": ["4.5", "4.6", "4.7", "6.1"] },
    { "id": 7, "tasks": ["6.2", "6.3", "7.1"] },
    { "id": 8, "tasks": ["8.1"] }
  ]
}
```

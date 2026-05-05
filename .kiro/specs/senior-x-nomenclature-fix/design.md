# Senior X Nomenclature Fix - Bugfix Design

## Overview

This bugfix addresses incorrect nomenclature where "X Platform" appears in system-critical data files when the correct terminology is simply "X". The bug manifests in two key locations: `biblioteca_acoes.json` (the reusable action memory) and `shadow_exports/*.jsonl` files (shadow capture exports). These files contain captured UI context data where the browser page title "GED | X Platform" was recorded during workflow capture sessions.

The fix strategy is a targeted text replacement in JSON data files, preserving all structural integrity while correcting only the nomenclature. This is a low-risk cosmetic fix that improves branding consistency without affecting system functionality.

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug - when JSON data files contain the text "X Platform" in string values
- **Property (P)**: The desired behavior - all references should use "X" instead of "X Platform"
- **Preservation**: All JSON structure, functionality, and non-nomenclature content must remain unchanged
- **biblioteca_acoes.json**: The reusable action memory file generated from saved roteiros, containing captured UI context data
- **shadow_exports/**: Directory containing JSONL files with shadow capture data from workflow recording sessions
- **contexto_tela**: JSON field that stores the browser page title or screen context during capture

## Bug Details

### Bug Condition

The bug manifests when JSON data files contain the string "X Platform" in captured UI context fields. This occurs because during workflow capture in Senior X, the browser page title for certain modules (like GED) displays as "GED | X Platform", and this title is recorded verbatim into the action memory and shadow export files.

**Formal Specification:**
```
FUNCTION isBugCondition(input)
  INPUT: input of type JSONFile
  OUTPUT: boolean
  
  RETURN input.fileExtension IN ['.json', '.jsonl']
         AND input.filePath IN ['biblioteca_acoes.json', 'shadow_exports/*.jsonl']
         AND input.content CONTAINS "X Platform"
END FUNCTION
```

### Examples

- **biblioteca_acoes.json line 6299**: `"contexto_tela": "GED | X Platform"` should be `"contexto_tela": "GED | X"`
- **biblioteca_acoes.json line 6332**: `"contexto_tela": "GED | X Platform"` should be `"contexto_tela": "GED | X"`
- **shadow_exports/GED_HYBRID_-_TESTE_005_shadow.jsonl**: Multiple instances of `"tela_id": "GED | X Platform"` should be `"tela_id": "GED | X"`
- **Edge case**: Files that already use "X" without "Platform" should remain unchanged

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All JSON structure and syntax must remain valid and unchanged
- All non-nomenclature string values must remain unchanged
- All numeric values, boolean values, and null values must remain unchanged
- All object keys and array structures must remain unchanged
- File encoding and line endings must remain unchanged
- All functionality that reads or processes these files must continue to work identically

**Scope:**
All content that does NOT involve the specific text pattern "X Platform" should be completely unaffected by this fix. This includes:
- All other string values in the JSON files
- All structural elements (objects, arrays, keys)
- All other files in the project (Python code, templates, etc.)
- All runtime behavior and system functionality

## Hypothesized Root Cause

Based on the bug description and search results, the root cause is clear:

1. **Capture-Time Recording**: During workflow capture sessions in Senior X, the browser page title is recorded verbatim into the capture data. The GED module's page title in Senior X is "GED | X Platform", which gets captured as-is.

2. **Propagation to Action Memory**: When `lego_builder.py` rebuilds `biblioteca_acoes.json` from saved roteiros, it includes the captured page titles in the `contexto_tela` field, perpetuating the incorrect nomenclature.

3. **Shadow Export Persistence**: Shadow export JSONL files contain raw capture data with the same page title pattern in `tela_id` and `contexto_tela` fields.

4. **No Normalization Layer**: There is no normalization or sanitization step that corrects the nomenclature during capture, generation, or export processes.

## Correctness Properties

Property 1: Bug Condition - Nomenclature Correction

_For any_ JSON file where the bug condition holds (file contains "X Platform" in string values), the fixed content SHALL replace all instances of "X Platform" with "X", resulting in correct nomenclature that aligns with official Senior X branding.

**Validates: Requirements 2.1, 2.2**

Property 2: Preservation - JSON Structure and Non-Nomenclature Content

_For any_ content in the JSON files that is NOT the specific text "X Platform" (all other strings, all structural elements, all keys, all non-string values), the fixed files SHALL contain exactly the same content as the original files, preserving all functionality and data integrity.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**

## Fix Implementation

### Changes Required

This is a straightforward text replacement operation on data files. No code changes are required.

**Files to Modify**:
1. `biblioteca_acoes.json`
2. All `*.jsonl` files in `shadow_exports/` directory

**Specific Changes**:

1. **Text Replacement**: Replace all instances of the exact string `"X Platform"` with `"X"` in the target files
   - Use case-sensitive exact match to avoid unintended replacements
   - Preserve all surrounding JSON syntax (quotes, commas, brackets)
   - Maintain file encoding and line endings

2. **Validation After Replacement**: Verify JSON validity after changes
   - Ensure `biblioteca_acoes.json` is valid JSON
   - Ensure all JSONL files have valid JSON on each line
   - Confirm no syntax errors were introduced

3. **Scope Limitation**: Only modify the two identified file locations
   - Do not modify Python code files
   - Do not modify template files
   - Do not modify configuration files
   - Do not modify roteiro files in `roteiros_salvos/` (these are production artifacts and should be preserved as-is unless explicitly requested)

4. **Atomic Operation**: Perform replacements atomically to avoid partial updates
   - Read entire file content
   - Perform replacement in memory
   - Write complete updated content

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, verify the bug exists in the current files (exploratory), then verify the fix corrects the nomenclature while preserving all other content (fix checking and preservation checking).

### Exploratory Bug Condition Checking

**Goal**: Confirm the bug exists in the identified files BEFORE implementing the fix. Document the exact locations and patterns of incorrect nomenclature.

**Test Plan**: Search for "X Platform" in the target files and document all occurrences. Verify that these are indeed in JSON string values and not in structural elements.

**Test Cases**:
1. **biblioteca_acoes.json Search**: Search for "X Platform" and count occurrences (expected: multiple instances in `contexto_tela` fields)
2. **shadow_exports JSONL Search**: Search for "X Platform" in all JSONL files (expected: multiple instances in `tela_id` and `contexto_tela` fields)
3. **Context Verification**: Verify that all instances are in string values, not in keys or structural elements (expected: all in string values)
4. **Baseline JSON Validity**: Verify that all files are valid JSON/JSONL before any changes (expected: all valid)

**Expected Counterexamples**:
- Multiple instances of `"contexto_tela": "GED | X Platform"` in biblioteca_acoes.json
- Multiple instances of `"tela_id": "GED | X Platform"` in shadow export JSONL files
- All instances are in captured UI context fields from the GED module

### Fix Checking

**Goal**: Verify that for all files where the bug condition holds, the fixed content contains "X" instead of "X Platform".

**Pseudocode:**
```
FOR ALL file WHERE isBugCondition(file) DO
  fixedContent := replaceAll(file.content, "X Platform", "X")
  ASSERT fixedContent DOES NOT CONTAIN "X Platform"
  ASSERT fixedContent CONTAINS "X" in the corrected locations
  ASSERT isValidJSON(fixedContent) = true
END FOR
```

**Test Cases**:
1. **Complete Replacement**: Verify no instances of "X Platform" remain in any target file
2. **Correct Replacement**: Verify "X" appears in the expected locations (where "X Platform" was)
3. **JSON Validity**: Verify all files remain valid JSON/JSONL after replacement
4. **File Count**: Verify the same number of files exist before and after (no files deleted or added)

### Preservation Checking

**Goal**: Verify that for all content that does NOT match "X Platform", the fixed files contain exactly the same content as the original files.

**Pseudocode:**
```
FOR ALL file WHERE isBugCondition(file) DO
  originalContent := readFile(file)
  fixedContent := replaceAll(originalContent, "X Platform", "X")
  
  ASSERT fixedContent.length = originalContent.length - (countOccurrences(originalContent, "X Platform") * 9)
  ASSERT fixedContent.structure = originalContent.structure
  ASSERT fixedContent.keys = originalContent.keys
  ASSERT fixedContent.nonNomenclatureValues = originalContent.nonNomenclatureValues
END FOR
```

**Testing Approach**: Manual verification is sufficient for this low-risk cosmetic fix because:
- The change is a simple text replacement with no logic involved
- The files are data files, not executable code
- JSON validity can be easily verified after the change
- The scope is limited to two specific file locations

**Test Cases**:
1. **JSON Structure Preservation**: Parse JSON before and after, verify same structure (same keys, same nesting, same array lengths)
2. **Non-Nomenclature String Preservation**: Verify other string values remain unchanged (e.g., action descriptions, selectors, URLs)
3. **Numeric Value Preservation**: Verify all numeric values remain unchanged (e.g., coordinates, viewport dimensions)
4. **File Encoding Preservation**: Verify file encoding remains UTF-8 and line endings remain consistent

### Unit Tests

Not applicable for this bugfix. This is a data file correction, not a code change. Manual verification is sufficient.

### Property-Based Tests

Not applicable for this bugfix. The change is deterministic (exact string replacement) and does not involve complex logic or edge cases that would benefit from property-based testing.

### Integration Tests

**Manual Integration Verification**:
1. **Action Memory Functionality**: After fixing `biblioteca_acoes.json`, verify that the system can still load and use the action memory correctly
   - Start the application (`python app.py`)
   - Verify no JSON parsing errors in logs
   - Verify the dashboard loads successfully
   - Verify action reuse functionality works (if testable through UI)

2. **Shadow Export Functionality**: After fixing shadow export JSONL files, verify that any tools that read these files still work correctly
   - Verify no parsing errors when reading JSONL files
   - Verify any reprocessing or analysis tools still function

3. **Visual Verification**: Manually inspect a sample of the fixed files to confirm:
   - "X Platform" has been replaced with "X"
   - No unintended changes occurred
   - JSON structure remains intact

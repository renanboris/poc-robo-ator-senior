# Design Document: Lego Builder Display Optimization

## Overview

The Lego Builder module (`lego_builder.py`) is a critical component of the Senior Training OS pipeline that extracts reusable technical actions from saved training scripts (`roteiros_salvos/`) to build the action library (`biblioteca_acoes.json`). Currently, the display output is verbose and could be optimized for better readability while maintaining usefulness for debugging and monitoring.

This design addresses the optimization of display output to make it more concise while preserving essential information for different user roles (developers, operators, system administrators). The optimization focuses on visual clarity, progress reporting, summary statistics, and configurable verbosity levels.

### Problem Statement

The current `lego_builder.py` implementation produces verbose console output that:
- Uses 50-character separator lines creating excessive visual noise
- Shows individual "Peça catalogada" messages for each new action, overwhelming users during large batch processing
- Lacks configurable verbosity levels, forcing all users to see detailed debugging information
- Shows progress at individual file level rather than batch level
- Presents summary statistics across multiple lines instead of a consolidated view

### Design Goals

1. **Improved Readability**: Cleaner visual separators and organized output structure
2. **Configurable Verbosity**: Support for concise (default) and verbose modes
3. **Batch Progress Reporting**: Consolidated progress updates for large operations
4. **Consolidated Summaries**: Single-block summary with essential statistics
5. **Backward Compatibility**: Maintain existing API return structure and functionality
6. **Role-Based Output**: Different display levels for developers, operators, and administrators

## Architecture

### Current Architecture

The current `lego_builder.py` architecture follows a simple linear processing model:
1. Initialize with header and separator lines
2. Scan `roteiros_salvos/` directory for JSON files
3. Process each file sequentially
4. Extract technical actions from each roteiro
5. Catalog unique actions into memory
6. Save to `biblioteca_acoes.json`
7. Display summary statistics

### Optimized Architecture

The optimized architecture introduces a layered display system:

```
┌─────────────────────────────────────────────────────────────┐
│                    Display Controller                        │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Verbosity Manager                                   │    │
│  │ • Concise Mode (default)                            │    │
│  │ • Verbose Mode (debug)                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Progress Tracker                                    │    │
│  │ • Batch progress updates                            │    │
│  │ • Real-time progress indication                     │    │
│  │ • Error/warning aggregation                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Output Formatter                                    │    │
│  │ • Section separators (30-40 chars)                  │    │
│  │ • Consolidated summaries                            │    │
│  │ • Highlighted critical information                  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│                    Core Processing Logic                     │
│  (Existing lego_builder.py functionality unchanged)         │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Changes

1. **Display Controller**: Centralizes all output logic, separating display concerns from business logic
2. **Verbosity Manager**: Handles different logging levels based on configuration
3. **Progress Tracker**: Manages batch progress reporting and real-time updates
4. **Output Formatter**: Standardizes visual presentation and formatting

## Components and Interfaces

### 1. Display Controller (`_DisplayController` class)

**Purpose**: Central coordination of all display-related functionality

**Responsibilities**:
- Initialize display based on verbosity configuration
- Route messages to appropriate formatters
- Manage progress tracking
- Generate final summary

**Interface**:
```python
class _DisplayController:
    def __init__(self, verbosity: str = "concise"):
        self.verbosity = verbosity
        self.progress_tracker = _ProgressTracker()
        self.formatter = _OutputFormatter()
        
    def start_execution(self, total_files: int) -> None
    def log_progress(self, current: int, total: int) -> None
    def log_new_action(self, intencao: str, arquivo: str) -> None
    def log_error(self, message: str) -> None
    def complete_execution(self, stats: dict) -> None
```

### 2. Verbosity Manager (`_VerbosityManager` class)

**Purpose**: Manage different verbosity levels and filtering

**Responsibilities**:
- Determine which messages to display based on verbosity level
- Store verbose messages for debugging when needed
- Provide consistent verbosity level checking

**Interface**:
```python
class _VerbosityManager:
    def __init__(self, level: str = "concise"):
        self.level = level
        
    def should_show_detail(self) -> bool
    def should_show_individual_actions(self) -> bool
    def should_show_batch_progress(self) -> bool
```

### 3. Progress Tracker (`_ProgressTracker` class)

**Purpose**: Track and report progress during batch processing

**Responsibilities**:
- Maintain batch progress counters
- Calculate and format progress percentages
- Determine when to emit progress updates
- Aggregate error and warning counts

**Interface**:
```python
class _ProgressTracker:
    def __init__(self):
        self.total_files = 0
        self.processed_files = 0
        self.new_actions = 0
        self.errors = []
        
    def update_progress(self, files_processed: int) -> None
    def add_error(self, error_message: str) -> None
    def get_progress_string(self) -> str
    def get_summary_stats(self) -> dict
```

### 4. Output Formatter (`_OutputFormatter` class)

**Purpose**: Standardize visual presentation of output

**Responsibilities**:
- Generate consistent separators and headers
- Format summary blocks
- Highlight critical information
- Ensure consistent column alignment

**Interface**:
```python
class _OutputFormatter:
    def __init__(self, separator_length: int = 35):
        self.separator_length = separator_length
        
    def create_header(self, title: str) -> str
    def create_separator(self) -> str
    def format_summary_block(self, stats: dict) -> str
    def highlight_critical(self, message: str) -> str
```

### 5. Updated `construir_biblioteca()` Function

**Purpose**: Main entry point with optimized display

**Changes**:
- Accept `verbosity` parameter (default: "concise")
- Use `_DisplayController` for all output
- Maintain backward compatibility for return dictionary

**Updated Interface**:
```python
def construir_biblioteca(
    roteiros_dir: str = ROTEIROS_DIR,
    biblioteca_file: str = BIBLIOTECA_FILE,
    verbosity: str = "concise"
) -> dict:
```

## Data Models

### 1. Verbosity Configuration

```python
from typing import Literal

VerbosityLevel = Literal["concise", "verbose"]
```

### 2. Display Statistics

```python
from typing import TypedDict, List

class DisplayStats(TypedDict):
    total_roteiros: int
    total_acoes_lidas: int
    total_acoes_novas: int
    versao_biblioteca: str
    arquivo: str
    erros: List[str]
    warnings: List[str]
    processing_time_seconds: float
```

### 3. Progress State

```python
class ProgressState:
    total_files: int
    processed_files: int
    current_batch: int
    batch_size: int = 10  # Emit progress every 10 files
    last_progress_update: int = 0
```

### 4. Configuration Sources

The verbosity level can be configured from multiple sources with the following precedence (highest to lowest):

1. **Function Parameter**: Direct parameter to `construir_biblioteca()`
2. **Environment Variable**: `LEGO_BUILDER_VERBOSITY` (concise|verbose)
3. **Command-line Argument**: When run as CLI script
4. **Default**: "concise"

### 5. Output Format Specifications

**Separators**: 35-character lines using `"="` character
**Headers**: Title centered within separators
**Progress Updates**: Format: `"[Progress] Processed X/Y files (Z%)"`
**Summary Block**: Single consolidated block with aligned columns
**Error Display**: Always shown regardless of verbosity level
**Verbose Mode**: Includes all individual action logging

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

*Note: Before writing correctness properties, I need to assess if Property-Based Testing (PBT) is applicable to this feature. This feature involves display formatting and logging optimization, which is primarily about UI/console output formatting rather than pure business logic with universal properties. However, there are some testable properties related to the display logic.*

*I will now use the prework tool to analyze acceptance criteria before writing correctness properties.*

### Property 1: Separator Length Constraint

*For any* execution of the Lego Builder, all separator lines in the display output shall be between 30 and 40 characters in length.

**Validates: Requirements 1.2**

### Property 2: Batch Progress Reporting

*For any* batch processing of N roteiro files in concise mode, progress updates shall be shown at batch intervals rather than for individual file processing messages.

**Validates: Requirements 2.1**

### Property 3: Verbosity Mode Display Behavior

*For any* execution with verbosity mode V, where V is either "concise" or "verbose", the display output shall conform to the following rules:
- If V = "concise": Show summary counts of new unique actions instead of individual "Peça catalogada" messages
- If V = "verbose": Show individual "Peça catalogada" messages for each new unique action

**Validates: Requirements 2.2, 2.3, 4.1, 4.3**

### Property 4: Summary Statistics Completeness

*For any* successful execution of the Lego Builder, the final summary block shall include all of the following statistics: roteiros processed, total actions found, new unique actions added, file location, and version.

**Validates: Requirements 3.2**

### Property 5: Error Visibility Guarantee

*For any* execution where errors occur during processing, detailed error information shall be shown in the display output regardless of the configured verbosity level.

**Validates: Requirements 4.2**

### Property 6: API Compatibility Preservation

*For any* execution of the optimized Lego Builder, the return dictionary structure shall be identical to the pre-optimization implementation, including all existing fields with their original types and meanings.

**Validates: Requirements 5.1, 5.2, 5.3, 5.4**

### Property 7: Configurable Verbosity Levels

*For any* configuration method M (function parameter, environment variable, or command-line argument), where M specifies verbosity level L, the Lego Builder shall operate with verbosity level L, and the default verbosity level when no configuration is provided shall be "concise".

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

### Property 8: Machine-Readable Output Structure

*For any* execution of the Lego Builder, the programmatic return value shall maintain a machine-readable structure suitable for API consumption, independent of display optimizations.

**Validates: Requirements 3.4**

## Error Handling

### Display-Specific Error Categories

1. **Configuration Errors**
   - Invalid verbosity level specified
   - Unreadable roteiros directory
   - Invalid biblioteca_acoes.json file path

2. **Processing Errors**
   - JSON decoding failures in roteiro files
   - File system permission errors
   - Memory allocation issues during large batch processing

3. **Output Errors**
   - Console encoding issues (Unicode handling)
   - Progress tracking calculation errors
   - Summary formatting failures

### Error Display Strategy

**Concise Mode Error Display**:
```
[ERROR] Category: Brief description (File: filename.json)
```

**Verbose Mode Error Display**:
```
═══════════════════════════════════
❌ ERROR DETAILS
═══════════════════════════════════
Category: Detailed category
File: filename.json
Message: Full error message
Traceback: Relevant traceback (if available)
Timestamp: YYYY-MM-DD HH:MM:SS
═══════════════════════════════════
```

### Error Recovery

1. **Non-Fatal Errors**: Continue processing with error aggregation
2. **Fatal Errors**: Halt processing with clear exit message
3. **Partial Success**: Return partial results with error list

## Testing Strategy

### Dual Testing Approach

**Unit Tests** (Example-based):
- Verify specific display formatting scenarios
- Test error handling edge cases
- Validate configuration parsing
- Test individual component behavior

**Property Tests** (Property-based):
- Verify universal properties across all valid inputs
- Test edge cases through randomized input generation
- Validate consistency rules across different configurations

### Property-Based Testing Configuration

**Library Selection**: Hypothesis (Python property-based testing library)
**Minimum Iterations**: 100 per property test
**Test Tagging Format**: `Feature: lego-builder-display-optimization, Property {N}: {property_text}`

### Test Coverage Areas

1. **Display Formatting Tests**
   - Separator length validation (Property 1)
   - Header formatting (Example test)
   - Summary block structure (Example test)

2. **Verbosity Mode Tests**
   - Concise mode behavior (Property 3)
   - Verbose mode behavior (Property 3)
   - Configuration precedence (Property 7)

3. **Progress Reporting Tests**
   - Batch progress updates (Property 2)
   - Real-time progress indication (Manual test)

4. **Error Handling Tests**
   - Error visibility (Property 5)
   - Error formatting (Example tests)
   - Error recovery (Example tests)

5. **API Compatibility Tests**
   - Return structure validation (Property 6)
   - Machine-readable output (Property 8)
   - Backward compatibility (Property 6)

6. **Configuration Tests**
   - Environment variable parsing (Property 7)
   - Command-line argument handling (Property 7)
   - Function parameter validation (Property 7)

### Integration Testing

**CLI Integration Tests**:
- Verify command-line argument parsing
- Test stdout output formatting
- Validate exit codes

**API Integration Tests**:
- Verify programmatic consumption still works
- Test return dictionary structure
- Validate error propagation

### Manual Testing Scenarios

1. **Large Batch Processing**: Process 100+ roteiros to verify progress reporting
2. **Empty Directory**: Test behavior with no roteiros
3. **Mixed Content**: Test with valid and invalid roteiro files
4. **Unicode Handling**: Test with special characters in action intents
5. **Long-Running Operations**: Verify real-time progress updates

### Performance Considerations

1. **Display Overhead**: Ensure display logic doesn't significantly impact processing performance
2. **Memory Usage**: Monitor memory consumption during large batch processing
3. **Progress Update Frequency**: Balance between real-time feedback and performance

### Regression Testing

1. **Backward Compatibility**: Verify existing integrations continue to work
2. **Output Consistency**: Ensure essential information is still presented
3. **Error Handling**: Confirm all previous error scenarios are still handled
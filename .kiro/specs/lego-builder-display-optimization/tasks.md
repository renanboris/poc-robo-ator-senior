# Implementation Plan: Lego Builder Display Optimization

## Overview

This implementation plan converts the feature design for optimizing lego_builder.py display output into a series of coding tasks. The optimization focuses on making console output more concise while maintaining usefulness, with configurable verbosity levels, batch progress reporting, and consolidated summaries.

## Tasks

- [x] 1. Set up display controller architecture and core interfaces
  - Create `_DisplayController` class with verbosity management
  - Implement `_VerbosityManager` class for level-based filtering
  - Create `_ProgressTracker` class for batch progress reporting
  - Implement `_OutputFormatter` class for consistent visual presentation
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 1.1 Write property test for separator length constraint
  - **Property 1: Separator Length Constraint**
  - **Validates: Requirements 1.2**
  - Test that all separator lines are between 30-40 characters

- [ ]* 1.2 Write property test for configurable verbosity levels
  - **Property 7: Configurable Verbosity Levels**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**
  - Test verbosity configuration from function parameters, environment variables, and command-line arguments

- [x] 2. Implement verbosity configuration system
  - Add `verbosity` parameter to `construir_biblioteca()` function with default "concise"
  - Implement environment variable support (`LEGO_BUILDER_VERBOSITY`)
  - Add command-line argument parsing for CLI execution
  - Update function signature and parameter validation
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ]* 2.1 Write property test for verbosity mode display behavior
  - **Property 3: Verbosity Mode Display Behavior**
  - **Validates: Requirements 2.2, 2.3, 4.1, 4.3**
  - Test that concise mode shows summary counts and verbose mode shows individual action messages

- [x] 3. Replace existing logging with display controller
  - Replace `_log()` function calls with `_DisplayController` methods
  - Implement batch progress updates every 10 files in concise mode
  - Maintain individual file logging in verbose mode
  - Preserve error logging at all verbosity levels
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 4.1, 4.2, 4.3, 4.4_

- [ ]* 3.1 Write property test for batch progress reporting
  - **Property 2: Batch Progress Reporting**
  - **Validates: Requirements 2.1**
  - Test that progress updates are shown at batch intervals in concise mode

- [ ]* 3.2 Write property test for error visibility guarantee
  - **Property 5: Error Visibility Guarantee**
  - **Validates: Requirements 4.2**
  - Test that error information is shown regardless of verbosity level

- [x] 4. Implement consolidated summary statistics
  - Create single summary block with aligned columns
  - Include all essential statistics: roteiros processed, total actions found, new unique actions added, file location, version
  - Highlight critical information (errors, warnings) prominently
  - Maintain machine-readable structure for API consumption
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ]* 4.1 Write property test for summary statistics completeness
  - **Property 4: Summary Statistics Completeness**
  - **Validates: Requirements 3.2**
  - Test that final summary includes all required statistics

- [ ]* 4.2 Write property test for machine-readable output structure
  - **Property 8: Machine-Readable Output Structure**
  - **Validates: Requirements 3.4**
  - Test that programmatic return value maintains machine-readable structure

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement optimized visual formatting
  - Replace 50-character separators with 35-character separators
  - Create concise headers with version and timestamp
  - Implement clear visual distinction between sections
  - Maintain ability to visually parse progress stages
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 7. Ensure API compatibility and backward compatibility
  - Verify return dictionary structure remains identical to pre-optimization
  - Ensure all existing fields maintain original types and meanings
  - Test programmatic consumption still works correctly
  - Validate error propagation in return dictionary
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ]* 7.1 Write property test for API compatibility preservation
  - **Property 6: API Compatibility Preservation**
  - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**
  - Test that return dictionary structure is identical to pre-optimization implementation

- [x] 8. Integration and CLI support
  - Update CLI script to accept `--verbose` flag
  - Ensure environment variable integration works correctly
  - Test both concise and verbose modes in CLI execution
  - Validate exit codes and stdout formatting
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [ ] 9. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from design document
- Unit tests validate specific examples and edge cases
- All implementation must maintain backward compatibility with existing integrations
- The display optimization should not significantly impact processing performance
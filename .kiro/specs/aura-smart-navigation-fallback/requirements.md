# Requirements Document

## Introduction

The AURA Smart Navigation Fallback feature enhances AURA's ability to guide users to UI elements that are not currently visible in the DOM. Currently, AURA can only highlight elements that are already rendered and visible. When a user asks how to access a feature that requires navigation through nested menus or collapsed sections, AURA provides generic responses instead of actionable guidance.

This feature implements a hierarchical fallback strategy that leverages saved roteiros to extract navigation paths and offer step-by-step guided navigation when direct DOM highlighting is not possible.

## Glossary

- **AURA**: AI-powered Digital Adoption Platform assistant that helps users navigate Senior X
- **DOM**: Document Object Model, the rendered HTML structure of the current page
- **Roteiro**: Structured workflow artifact containing step-by-step navigation and action sequences
- **Navigation_Path**: Hierarchical sequence of UI elements leading to a target feature (e.g., "Senior Flow > SIGN")
- **Guided_Mode**: Step-by-step navigation assistance with visual highlights at each step
- **Fallback_Strategy**: Hierarchical approach to finding and presenting navigation options
- **Senior_X**: The ERP system where AURA operates
- **DAP_Engine**: The retrieval and question-answering system powering AURA

## Requirements

### Requirement 1: Detect Element Visibility

**User Story:** As AURA, I want to detect when a requested element is not visible in the current DOM, so that I can activate the appropriate fallback strategy.

#### Acceptance Criteria

1. WHEN a user query references a UI element, THE AURA SHALL check if the element exists in the current DOM
2. WHEN the element is found in the DOM, THE AURA SHALL use the existing direct highlight behavior
3. WHEN the element is not found in the DOM, THE AURA SHALL activate the navigation fallback strategy
4. THE AURA SHALL complete the visibility check within 500ms to maintain response performance

### Requirement 2: Extract Navigation Paths from Roteiros

**User Story:** As AURA, I want to search saved roteiros for navigation paths to hidden elements, so that I can guide users to their destination.

#### Acceptance Criteria

1. WHEN an element is not visible in the DOM, THE AURA SHALL search roteiros in the `roteiros_salvos/` directory
2. THE AURA SHALL extract hierarchical navigation sequences from matching roteiros
3. THE AURA SHALL identify the breadcrumb path (e.g., "Senior Flow > SIGN > Cancelar Envelopes")
4. WHEN multiple roteiros contain the target element, THE AURA SHALL prioritize the shortest navigation path
5. THE AURA SHALL complete the roteiro search within 2 seconds to maintain acceptable response time

### Requirement 3: Format Conversational Navigation Offer

**User Story:** As a user, I want AURA to tell me where a feature is located and offer to guide me there, so that I can decide whether to accept the guided navigation.

#### Acceptance Criteria

1. WHEN a navigation path is found, THE AURA SHALL format a conversational response including the navigation hierarchy
2. THE AURA SHALL use the pattern "Ele fica dentro do X > Y, quer que eu te guie para lá?"
3. THE AURA SHALL present the full breadcrumb path in the response
4. WHEN no navigation path is found in roteiros, THE AURA SHALL fall back to general knowledge-based responses
5. THE AURA SHALL maintain a natural, helpful tone consistent with existing AURA behavior

### Requirement 4: Execute Guided Navigation

**User Story:** As a user, I want AURA to guide me step-by-step to a hidden feature with visual highlights, so that I can learn the navigation path.

#### Acceptance Criteria

1. WHEN the user accepts the guided navigation offer, THE AURA SHALL execute the navigation sequence step-by-step
2. THE AURA SHALL highlight each intermediate element in the navigation path
3. WHEN an intermediate element requires interaction (e.g., expanding a menu), THE AURA SHALL wait for the interaction to complete before proceeding
4. THE AURA SHALL wait for each step's DOM changes to stabilize before highlighting the next element
5. WHEN the final target element becomes visible, THE AURA SHALL highlight it and confirm completion
6. IF any step in the navigation sequence fails, THE AURA SHALL report which step failed and stop the guided navigation

### Requirement 5: Preserve Existing Direct Highlight Behavior

**User Story:** As a user, I want AURA to continue highlighting visible elements immediately, so that the new fallback strategy does not slow down the common case.

#### Acceptance Criteria

1. WHEN a requested element is visible in the DOM, THE AURA SHALL use direct highlight without searching roteiros
2. THE AURA SHALL maintain the current response time for visible elements (under 1 second)
3. THE AURA SHALL not introduce additional latency to the existing direct highlight flow
4. THE AURA SHALL preserve all existing highlight visual effects and behaviors

### Requirement 6: Handle Navigation Failures Gracefully

**User Story:** As a user, I want AURA to inform me clearly when guided navigation cannot be completed, so that I understand what went wrong.

#### Acceptance Criteria

1. WHEN a navigation step fails due to a missing element, THE AURA SHALL report the specific step that failed
2. WHEN a navigation step fails due to a timeout, THE AURA SHALL report the timeout and suggest manual navigation
3. WHEN the UI structure has changed since the roteiro was created, THE AURA SHALL detect the mismatch and inform the user
4. THE AURA SHALL provide the partial navigation path that was successfully completed
5. WHEN navigation fails, THE AURA SHALL offer to show the original conversational guidance again

### Requirement 7: Optimize Roteiro Search Performance

**User Story:** As AURA, I want to search roteiros efficiently, so that users receive navigation guidance without noticeable delay.

#### Acceptance Criteria

1. THE AURA SHALL index roteiro navigation paths at startup or when roteiros are modified
2. THE AURA SHALL use the index to perform O(log n) or better lookup by element name
3. THE AURA SHALL cache frequently accessed navigation paths in memory
4. WHEN the `roteiros_salvos/` directory is modified, THE AURA SHALL invalidate and rebuild the relevant index entries
5. THE AURA SHALL complete indexed lookups within 200ms for 95% of queries

### Requirement 8: Parse Roteiro Navigation Structure

**User Story:** As AURA, I want to parse roteiro JSON files to extract navigation sequences, so that I can build accurate navigation paths.

#### Acceptance Criteria

1. THE AURA SHALL parse the `passos` array from roteiro JSON files
2. THE AURA SHALL extract `ancora` (anchor text) and `acao` (action type) from each step
3. THE AURA SHALL identify navigation-relevant actions (click, expand, navigate)
4. THE AURA SHALL construct hierarchical paths from sequential navigation steps
5. THE AURA SHALL handle malformed or incomplete roteiro files without crashing
6. FOR ALL valid roteiro files, parsing then reconstructing the navigation path SHALL preserve the original sequence

### Requirement 9: Integrate with Existing DAP Engine

**User Story:** As a developer, I want the navigation fallback to integrate seamlessly with the existing DAP engine, so that AURA's behavior remains consistent.

#### Acceptance Criteria

1. THE Navigation_Fallback SHALL be invoked by the DAP_Engine when element visibility check fails
2. THE Navigation_Fallback SHALL return responses in the same format as existing DAP responses
3. THE Navigation_Fallback SHALL use the same Pinecone retrieval context as the existing DAP flow
4. THE Navigation_Fallback SHALL log navigation attempts to the same logging system as other DAP operations
5. THE Navigation_Fallback SHALL respect the same timeout and error handling contracts as the DAP_Engine

### Requirement 10: Support User Confirmation Flow

**User Story:** As a user, I want to explicitly confirm before AURA starts automated navigation, so that I maintain control over the interaction.

#### Acceptance Criteria

1. WHEN AURA offers guided navigation, THE AURA SHALL wait for explicit user confirmation
2. THE AURA SHALL recognize affirmative responses ("sim", "yes", "pode", "quero", "vamos")
3. THE AURA SHALL recognize negative responses ("não", "no", "agora não", "depois")
4. WHEN the user declines, THE AURA SHALL acknowledge and remain available for further questions
5. WHEN the user's response is ambiguous, THE AURA SHALL ask for clarification before proceeding

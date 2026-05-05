# Implementation Plan: Dashboard Overview Page Redesign (v2)

## Overview

Este plano implementa o Dashboard Overview Page Redesign (v2) como uma versão completamente isolada do dashboard legado, permitindo desenvolvimento paralelo, testes seguros e rollback sem riscos. A implementação segue estratégia de isolamento total com novos arquivos (templates/dashboard_v2.html, static/dashboard-v2.css, static/dashboard-v2.js) e nova rota (/dashboard/v2).

A arquitetura utiliza Python/FastAPI no backend, mantendo compatibilidade com o stack existente (Jinja2, SQLite, design tokens), e implementa componentes modernos no frontend com microinterações performáticas, responsividade adaptativa e acessibilidade WCAG 2.1 AA.

## Tasks

### Phase 1: Foundation Setup

- [x] 1. Setup project structure and base files
  - Create `templates/dashboard_v2.html` template file
  - Create `static/dashboard-v2.css` stylesheet file  
  - Create `static/dashboard-v2.js` script file
  - Verify `static/os-tokens.css` exists and is accessible
  - _Requirements: 16.1, 16.2, 16.3, 16.5_

- [x] 2. Implement backend route and data endpoints
  - [x] 2.1 Add `/dashboard/v2` route in `app.py`
    - Create new route handler that renders `dashboard_v2.html`
    - Reuse existing dashboard data fetching logic
    - Add toggle links between v1 ↔ v2 versions
    - _Requirements: 16.2, 16.7, 16.11_
  
  - [ ]* 2.2 Write unit tests for new route
    - Test route accessibility and template rendering
    - Test data fetching and JSON serialization
    - Test toggle link functionality
    - _Requirements: 16.2_

- [x] 3. Create base HTML structure and design token integration
  - [x] 3.1 Build semantic HTML structure in `dashboard_v2.html`
    - Implement hero section, KPI grid, activity feed, quick stats containers
    - Add proper ARIA landmarks and semantic elements
    - Include meta tags for responsive viewport
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 10.3_
  
  - [x] 3.2 Setup CSS architecture in `dashboard-v2.css`
    - Import `os-tokens.css` design tokens
    - Create component-specific CSS classes with BEM methodology
    - Implement CSS Grid and Flexbox layouts
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

### Phase 2: Hero Section Implementation

- [x] 4. Implement Hero Section component
  - [x] 4.1 Create hero typography and layout
    - Implement hero title with 56-72px font size using `var(--os-font-display)`
    - Add subtitle and system status indicator with live pulse animation
    - Apply vertical spacing of 48px (`var(--os-space-8)`) between elements
    - _Requirements: 1.1, 1.3, 1.5, 5.2, 5.3_
  
  - [x] 4.2 Implement quick action buttons
    - Create "Novo Roteiro", "Importar", "Templates" buttons with visual prominence
    - Add hover states with `transform: translateY(-2px)` and enhanced shadows
    - Use `var(--os-accent)` color for primary call-to-action elements
    - _Requirements: 1.2, 1.4, 1.6, 7.1_
  
  - [ ]* 4.3 Write unit tests for hero section
    - Test typography rendering and font size calculations
    - Test button hover states and CSS transforms
    - Test pulse animation functionality
    - _Requirements: 1.1, 1.4_

### Phase 3: KPI Cards Implementation

- [ ] 5. Implement KPI Cards with sparklines
  - [ ] 5.1 Create KPI card structure and styling
    - Build 3-column grid layout for KPI cards
    - Implement card elevation with box-shadow on hover
    - Display metric value (32px, weight 700) and label (12px, uppercase, 1.5px letter-spacing)
    - _Requirements: 2.1, 2.6, 2.7, 2.8_
  
  - [ ] 5.2 Implement SVG sparkline rendering
    - Create Python function to generate SVG sparkline paths from data arrays
    - Render sparklines with `var(--os-accent)` stroke color and 2px width
    - Add draw animation with 800ms duration using `var(--os-ease-out)`
    - _Requirements: 2.2, 2.5_
  
  - [ ] 5.3 Add progressive disclosure hover effects
    - Show only primary metric by default
    - Reveal secondary metrics on hover with opacity 0→1 transition in 200ms
    - Implement smooth hover state transitions within 150ms
    - _Requirements: 2.3, 8.1, 8.2, 7.1_
  
  - [ ]* 5.4 Write property test for KPI sparkline animation
    - **Property 3: KPI Card Sparkline Animation Consistency**
    - **Validates: Requirements 2.2**
  
  - [ ]* 5.5 Write property test for progressive disclosure
    - **Property 4: Progressive Disclosure in KPI Cards**
    - **Validates: Requirements 2.3, 8.1, 8.2**

- [ ] 6. Implement drill-down modal functionality
  - [ ] 6.1 Create drill-down modal component
    - Build modal with backdrop overlay (opacity 0.6, backdrop-filter blur(8px))
    - Display metric name as heading (24px) and detailed chart (320px height)
    - Include time range selector: "7 days", "30 days", "90 days"
    - _Requirements: 2.4, 8.3, 8.6, 14.1, 14.2, 14.3, 14.4_
  
  - [ ] 6.2 Add modal interaction and keyboard support
    - Open modal on KPI card click within 200ms
    - Close modal on ESC key or outside click with fade-out animation
    - Trap keyboard focus within modal while open
    - Include export button for CSV data download
    - _Requirements: 8.5, 14.5, 14.6, 14.7, 14.8_
  
  - [ ]* 6.3 Write integration tests for drill-down modal
    - Test KPI card click → modal open → data fetch → chart render flow
    - Test keyboard navigation and focus trapping
    - Test time range changes and data updates
    - _Requirements: 14.1, 14.8_

### Phase 4: Activity Feed Implementation

- [ ] 7. Implement Activity Feed component
  - [ ] 7.1 Create activity timeline structure
    - Build vertical timeline layout with connector line (`var(--os-border-2)`)
    - Display activities in reverse chronological order (most recent first)
    - Show activity type icons (16px, `var(--os-accent)`) and relative timestamps
    - Limit display to 10 most recent activities with lazy loading
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.7, 3.8_
  
  - [ ] 7.2 Implement activity filtering system
    - Create filter buttons: "Todos", "Captura", "Geração", "Execução"
    - Update feed within 300ms on filter selection
    - Highlight active filter with `var(--os-accent-dim)` background
    - Display item count badge next to filter labels
    - _Requirements: 3.5, 15.1, 15.2, 15.3, 15.4_
  
  - [ ] 7.3 Add activity interaction features
    - Show inline preview on hover over activity items
    - Navigate to detailed roteiro view on activity click
    - Persist filter selection in sessionStorage
    - Restore filter on page reload
    - _Requirements: 3.6, 3.9, 15.5, 15.6_
  
  - [ ]* 7.4 Write property test for chronological ordering
    - **Property 5: Activity Feed Chronological Ordering**
    - **Validates: Requirements 3.2**
  
  - [ ]* 7.5 Write property test for filtering consistency
    - **Property 6: Activity Feed Filtering Consistency**
    - **Validates: Requirements 3.5, 15.1, 15.2, 15.5**

### Phase 5: Quick Stats Dashboard Implementation

- [ ] 8. Implement Quick Stats visualizations
  - [ ] 8.1 Create velocity chart component
    - Render velocity chart with minimum 240px height
    - Implement scroll-triggered animation when entering viewport
    - Display chart legends (11px, `var(--os-text-3)`)
    - _Requirements: 4.1, 4.5, 4.6_
  
  - [ ] 8.2 Implement weekly activity heatmap
    - Create 7-column heatmap grid for days of week
    - Use color scale from `var(--os-surface-2)` to `var(--os-accent)`
    - Show tooltip on hover with activity count and date
    - _Requirements: 4.2, 4.4, 4.7_
  
  - [ ] 8.3 Add top roteiros ranking display
    - Show top 5 roteiros ranked by views/executions
    - Implement responsive layout for different screen sizes
    - _Requirements: 4.3_
  
  - [ ]* 8.4 Write integration tests for chart rendering
    - Test velocity chart data loading and rendering
    - Test heatmap color calculations and tooltip display
    - Test scroll-triggered animations with intersection observer
    - _Requirements: 4.1, 4.2, 4.5_

### Phase 6: Responsive Design and Accessibility

- [ ] 9. Implement responsive layout system
  - [ ] 9.1 Create responsive grid breakpoints
    - 3-column KPI grid for viewport >1280px
    - 2-column KPI grid for 768-1280px viewport
    - 1-column stack for <768px viewport
    - Reduce hero title to 36px on mobile (<768px)
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  
  - [ ] 9.2 Optimize mobile experience
    - Hide sparklines on viewport <640px
    - Ensure 44px minimum touch targets for interactive elements
    - Test responsive behavior across device sizes
    - _Requirements: 9.5, 9.6_
  
  - [ ]* 9.3 Write property test for responsive grid adaptation
    - **Property 7: Responsive Grid Layout Adaptation**
    - **Validates: Requirements 9.1, 9.2, 9.3**

- [ ] 10. Implement accessibility features
  - [ ] 10.1 Add WCAG 2.1 AA compliance
    - Ensure 4.5:1 contrast ratio for normal text, 3:1 for large text
    - Provide keyboard navigation with visible focus indicators
    - Add ARIA labels for icon-only buttons
    - _Requirements: 10.1, 10.2, 10.3_
  
  - [ ] 10.2 Add screen reader and motion support
    - Implement ARIA live regions for dynamic content updates
    - Support `prefers-reduced-motion` media query
    - Provide alt text for informational images and icons
    - _Requirements: 10.4, 10.5, 10.6, 10.7_
  
  - [ ]* 10.3 Write property test for keyboard navigation
    - **Property 10: Keyboard Navigation Support**
    - **Validates: Requirements 10.2**

### Phase 7: Performance Optimization

- [ ] 11. Implement performance optimizations
  - [ ] 11.1 Optimize loading and rendering performance
    - Achieve First Contentful Paint (FCP) <1.5s on 3G
    - Achieve Time to Interactive (TTI) <3s on 3G
    - Lazy-load Activity Feed items beyond initial 10
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ] 11.2 Optimize animations and interactions
    - Use CSS transforms instead of position changes for animations
    - Apply `will-change` only during active animations
    - Maintain 60fps frame rate for all animations
    - Debounce scroll event listeners with 100ms delay
    - _Requirements: 7.2, 7.3, 7.5, 12.4_
  
  - [ ] 11.3 Add CSS containment and font optimization
    - Use CSS containment (`contain: layout style paint`) for components
    - Preload critical fonts with `link rel="preload"`
    - Minimize layout shifts with explicit dimensions
    - _Requirements: 12.5, 12.6, 12.7_

### Phase 8: Empty States and Error Handling

- [ ] 12. Implement empty states and error handling
  - [ ] 12.1 Create informative empty states
    - Activity Feed empty state with illustration and CTA
    - Quick Stats placeholder with instructional text
    - Center-align empty state content with `var(--os-text-3)` color
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 12.2 Add error handling and fallbacks
    - Graceful API failure handling with retry mechanisms
    - Fallback to cached data when network unavailable
    - Progressive enhancement (core functionality without JavaScript)
    - _Requirements: 16.12_

### Phase 9: Design Token Compliance and Theming

- [ ] 13. Ensure design token compliance
  - [ ] 13.1 Audit and validate design token usage
    - Use only colors from `os-tokens.css`
    - Use spacing variables `var(--os-space-*)` for all spacing
    - Use font variables `var(--os-font-*)` for typography
    - Use easing variables `var(--os-ease-*)` for transitions
    - _Requirements: 11.1, 11.2, 11.3, 11.5_
  
  - [ ] 13.2 Support dark and light themes
    - Test both themes using existing `html.light` selector
    - Ensure proper contrast ratios in both themes
    - _Requirements: 11.7_
  
  - [ ]* 13.3 Write property test for design token compliance
    - **Property 8: Design Token Compliance**
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

### Phase 10: Testing Suite Implementation

- [ ] 14. Implement comprehensive testing suite
  - [ ]* 14.1 Write property test for hero typography
    - **Property 1: Hero Section Typography Consistency**
    - **Validates: Requirements 1.1, 5.2**
  
  - [ ]* 14.2 Write property test for hover interactions
    - **Property 2: Interactive Element Hover Response**
    - **Validates: Requirements 1.4, 7.1**
  
  - [ ]* 14.3 Write property test for accessibility contrast
    - **Property 9: Accessibility Contrast Requirements**
    - **Validates: Requirements 10.1**
  
  - [ ]* 14.4 Write property test for file isolation
    - **Property 11: File Isolation Preservation**
    - **Validates: Requirements 16.1, 16.2, 16.3, 16.4**
  
  - [ ]* 14.5 Write property test for spacing consistency
    - **Property 12: Spacing Consistency**
    - **Validates: Requirements 6.1**

- [ ] 15. Visual regression and performance testing
  - [ ]* 15.1 Setup visual regression tests
    - Capture screenshots at 1920px, 1280px, 768px, 375px widths
    - Test hero section, KPI cards, activity feed in different states
    - Test both dark and light theme variations
    - _Requirements: Visual regression testing strategy_
  
  - [ ]* 15.2 Performance testing with Lighthouse
    - Measure FCP, LCP, TTI with 3G throttling
    - Achieve Lighthouse Performance score ≥90
    - Test animation frame rates and memory usage
    - _Requirements: 12.1, 12.2, Performance testing strategy_

### Phase 11: Integration and Deployment

- [ ] 16. Final integration and deployment preparation
  - [ ] 16.1 Integration testing and validation
    - Test complete user flows: page load → interactions → navigation
    - Validate data consistency between v1 and v2 dashboards
    - Test toggle functionality between versions
    - _Requirements: 16.7, 16.11, 16.12_
  
  - [ ] 16.2 Deployment strategy implementation
    - Implement feature flag/toggle mechanism for v1 ↔ v2 switching
    - Add user preference persistence (localStorage or user profile)
    - Create rollback plan and monitoring strategy
    - _Requirements: 16.8, 16.11_

- [ ] 17. Final checkpoint and documentation
  - Ensure all tests pass and performance metrics are met
  - Verify WCAG 2.1 AA compliance with automated tools
  - Document toggle mechanism and rollout strategy
  - Ask the user if questions arise before deployment

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP delivery
- Each task references specific requirements for traceability and validation
- Property-based tests validate universal correctness properties using Jest + fast-check
- Implementation uses Python/FastAPI backend with modern frontend techniques
- Complete file isolation ensures zero risk to existing v1 dashboard functionality
- Progressive enhancement ensures core functionality works without JavaScript
- Responsive design supports desktop (3-col), tablet (2-col), and mobile (1-col) layouts

## Property-Based Testing Configuration

**Framework**: Jest + fast-check for JavaScript property testing
**Test Location**: `static/dashboard-v2.test.js`
**Minimum Iterations**: 100 per property test
**Timeout**: 30 seconds per property test
**Tag Format**: **Feature: dashboard-overview-redesign, Property {number}: {property_text}**

## Success Criteria

- [ ] First Contentful Paint (FCP) < 1.5 seconds on 3G connection
- [ ] Time to Interactive (TTI) < 3 seconds on 3G connection  
- [ ] Lighthouse Performance score ≥ 90
- [ ] Zero critical accessibility violations in automated audits
- [ ] All 12 correctness properties pass with 100+ test iterations
- [ ] Responsive layout works correctly on desktop, tablet, and mobile
- [ ] Complete file isolation with zero modifications to v1 files
- [ ] Successful toggle functionality between v1 and v2 versions
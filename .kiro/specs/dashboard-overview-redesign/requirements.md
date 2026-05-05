# Requirements Document

## Introduction

O Dashboard Overview Page Redesign moderniza a página principal do Training OS seguindo padrões de design contemporâneos identificados na análise do site Foccum. O objetivo é melhorar a hierarquia visual, densidade de informação, microinterações e experiência geral do usuário, transformando o dashboard atual em uma interface moderna, profissional e engajadora.

Este redesign foca no MVP da Overview Page, incluindo Hero Section impactante, KPI Cards melhorados, Activity Feed visual e Quick Stats Dashboard aprimorado.

## Glossary

- **Dashboard_System**: Sistema de interface do usuário responsável pela página Overview do Training OS
- **Hero_Section**: Área de destaque no topo da página contendo título principal e quick actions
- **KPI_Card**: Componente visual que exibe uma métrica-chave de performance com sparkline e interatividade
- **Activity_Feed**: Timeline visual cronológica de atividades recentes do sistema
- **Quick_Stats**: Painel de estatísticas rápidas com gráficos e visualizações
- **Sparkline**: Gráfico de linha minimalista inline que mostra tendência de dados
- **Drill_Down_Modal**: Modal que exibe detalhes expandidos de uma métrica quando o usuário clica em um KPI Card
- **Hover_State**: Estado visual de um componente quando o cursor está sobre ele
- **Scroll_Triggered_Animation**: Animação que inicia quando o elemento entra no viewport durante scroll
- **Design_Token**: Variável CSS reutilizável definida em os-tokens.css
- **Breathing_Room**: Espaçamento generoso entre elementos para reduzir densidade visual
- **Progressive_Disclosure**: Padrão UX onde informação adicional é revelada sob demanda
- **Roteiro**: Artefato central do Training OS representando um workflow estruturado
- **Captura**: Processo de gravação de workflow do usuário
- **Geração**: Processo de criação de roteiro via IA
- **Execução**: Processo de replay automatizado de roteiro

## Requirements

### Requirement 1: Hero Section Impactante

**User Story:** Como um trainer, eu quero ver um título grande e impactante com quick actions em destaque, para que eu possa rapidamente entender o propósito da página e iniciar ações principais.

#### Acceptance Criteria

1. THE Dashboard_System SHALL render a hero title with font size between 56px and 72px using var(--os-font-display)
2. THE Dashboard_System SHALL display quick action buttons for "Novo Roteiro", "Importar" and "Templates" with visual prominence
3. THE Dashboard_System SHALL show system status indicator with live pulse animation
4. WHEN a user hovers over a quick action button, THE Dashboard_System SHALL display a hover state with transform translateY(-2px) and enhanced shadow
5. THE Dashboard_System SHALL apply vertical spacing of at least 48px (var(--os-space-8)) between hero title and quick actions
6. THE Dashboard_System SHALL use color var(--os-accent) for primary call-to-action elements in the hero section

### Requirement 2: KPI Cards com Sparklines Animados

**User Story:** Como um operations manager, eu quero visualizar métricas-chave com sparklines animados e interatividade, para que eu possa rapidamente avaliar performance e acessar detalhes sob demanda.

#### Acceptance Criteria

1. THE Dashboard_System SHALL display exactly 3 KPI cards in a horizontal grid layout
2. WHEN the page loads, THE Dashboard_System SHALL animate each sparkline with a draw animation duration of 800ms using var(--os-ease-out)
3. WHEN a user hovers over a KPI_Card, THE Dashboard_System SHALL reveal additional metric details with opacity transition from 0 to 1 in 200ms
4. WHEN a user clicks a KPI_Card, THE Dashboard_System SHALL open a Drill_Down_Modal with expanded metric visualization
5. THE Dashboard_System SHALL render sparklines using SVG with stroke color var(--os-accent) and stroke-width of 2px
6. THE Dashboard_System SHALL apply card elevation with box-shadow on hover state
7. THE Dashboard_System SHALL display metric value with font size 32px and font weight 700
8. THE Dashboard_System SHALL show metric label with font size 12px, text-transform uppercase, and letter-spacing 1.5px

### Requirement 3: Activity Feed Visual

**User Story:** Como um designer, eu quero ver uma timeline visual de atividades recentes com preview inline, para que eu possa acompanhar o histórico de trabalho sem sair da overview.

#### Acceptance Criteria

1. THE Dashboard_System SHALL render an Activity_Feed component with vertical timeline layout
2. THE Dashboard_System SHALL display activity items in reverse chronological order (most recent first)
3. WHEN the Activity_Feed contains items, THE Dashboard_System SHALL show a visual timeline connector line with color var(--os-border-2)
4. THE Dashboard_System SHALL display activity type icons with size 16px and color var(--os-accent)
5. THE Dashboard_System SHALL support filtering by activity type: "captura", "geração", "execução"
6. WHEN a user hovers over an activity item, THE Dashboard_System SHALL display inline preview of the associated roteiro
7. THE Dashboard_System SHALL show activity timestamp using relative time format (e.g., "2h ago", "1 day ago")
8. THE Dashboard_System SHALL limit the Activity_Feed to display the 10 most recent activities
9. WHEN a user clicks an activity item, THE Dashboard_System SHALL navigate to the detailed view of that roteiro

### Requirement 4: Quick Stats Dashboard Aprimorado

**User Story:** Como um trainer, eu quero visualizar estatísticas rápidas com gráficos maiores e mais visuais, para que eu possa entender tendências e performance de forma imediata.

#### Acceptance Criteria

1. THE Dashboard_System SHALL render a velocity chart with minimum height of 240px
2. THE Dashboard_System SHALL display a weekly activity heatmap with 7 columns (days) and color intensity based on activity count
3. THE Dashboard_System SHALL show top 5 roteiros ranked by views or executions
4. WHEN rendering the heatmap, THE Dashboard_System SHALL use color scale from var(--os-surface-2) (low activity) to var(--os-accent) (high activity)
5. THE Dashboard_System SHALL animate chart elements with scroll-triggered animation when entering viewport
6. THE Dashboard_System SHALL display chart legends with font size 11px and color var(--os-text-3)
7. WHEN a user hovers over a heatmap cell, THE Dashboard_System SHALL display a tooltip with exact activity count and date

### Requirement 5: Hierarquia Tipográfica Moderna

**User Story:** Como um usuário, eu quero ver uma hierarquia tipográfica clara e moderna, para que eu possa escanear informação rapidamente e entender a estrutura da página.

#### Acceptance Criteria

1. THE Dashboard_System SHALL use font family var(--os-font-display) for all heading elements (h1, h2, h3)
2. THE Dashboard_System SHALL apply font size 56px for h1 elements in hero section
3. THE Dashboard_System SHALL apply font size 32px for h2 section headings
4. THE Dashboard_System SHALL apply font size 18px for h3 subsection headings
5. THE Dashboard_System SHALL use font weight 700 or 800 for all heading elements
6. THE Dashboard_System SHALL apply letter-spacing -0.02em for headings larger than 32px
7. THE Dashboard_System SHALL use line-height 1.2 for display headings and 1.5 for body text

### Requirement 6: Espaçamento Generoso e Breathing Room

**User Story:** Como um usuário, eu quero ver espaçamento generoso entre elementos, para que a interface não pareça sobrecarregada e eu possa focar em cada seção.

#### Acceptance Criteria

1. THE Dashboard_System SHALL apply minimum vertical spacing of 48px (var(--os-space-8)) between major sections
2. THE Dashboard_System SHALL apply minimum vertical spacing of 24px (var(--os-space-5)) between subsections
3. THE Dashboard_System SHALL apply minimum horizontal gap of 24px (var(--os-space-5)) between grid columns
4. THE Dashboard_System SHALL apply padding of at least 32px (var(--os-space-6)) to container elements
5. THE Dashboard_System SHALL use 8pt grid system for all spacing values (multiples of 4px)

### Requirement 7: Microinterações e Animações Performáticas

**User Story:** Como um usuário, eu quero ver microinterações suaves e animações performáticas, para que a interface pareça moderna e responsiva sem comprometer performance.

#### Acceptance Criteria

1. WHEN a user hovers over an interactive element, THE Dashboard_System SHALL apply hover state transition within 150ms
2. THE Dashboard_System SHALL use CSS transform properties (translate, scale) instead of position properties for animations
3. THE Dashboard_System SHALL apply will-change CSS property only during active animations
4. THE Dashboard_System SHALL use requestAnimationFrame for JavaScript-driven animations
5. THE Dashboard_System SHALL maintain 60fps frame rate for all animations
6. WHEN an element enters viewport, THE Dashboard_System SHALL trigger scroll-triggered animation with intersection observer API
7. THE Dashboard_System SHALL use easing function var(--os-ease-out) for exit animations and var(--os-ease-spring) for emphasis animations

### Requirement 8: Progressive Disclosure em KPI Cards

**User Story:** Como um operations manager, eu quero ver informação básica por padrão e detalhes sob demanda, para que eu não seja sobrecarregado com dados desnecessários.

#### Acceptance Criteria

1. WHEN a KPI_Card is in default state, THE Dashboard_System SHALL display only primary metric value and label
2. WHEN a user hovers over a KPI_Card, THE Dashboard_System SHALL reveal secondary metrics with fade-in animation
3. WHEN a user clicks a KPI_Card, THE Dashboard_System SHALL open Drill_Down_Modal with complete metric breakdown
4. THE Drill_Down_Modal SHALL display historical data chart with minimum 30 data points
5. THE Drill_Down_Modal SHALL include close button with keyboard shortcut ESC
6. WHEN Drill_Down_Modal is open, THE Dashboard_System SHALL apply backdrop overlay with opacity 0.6 and backdrop-filter blur(8px)

### Requirement 9: Responsividade e Layout Adaptativo

**User Story:** Como um usuário em diferentes dispositivos, eu quero que o dashboard se adapte ao tamanho da tela, para que eu possa usar a plataforma em desktop, tablet ou mobile.

#### Acceptance Criteria

1. WHEN viewport width is greater than 1280px, THE Dashboard_System SHALL display KPI cards in 3-column grid
2. WHEN viewport width is between 768px and 1280px, THE Dashboard_System SHALL display KPI cards in 2-column grid
3. WHEN viewport width is less than 768px, THE Dashboard_System SHALL display KPI cards in 1-column stack
4. THE Dashboard_System SHALL reduce hero title font size to 36px when viewport width is less than 768px
5. THE Dashboard_System SHALL hide sparklines in KPI cards when viewport width is less than 640px
6. THE Dashboard_System SHALL maintain minimum touch target size of 44px for interactive elements on mobile

### Requirement 10: Acessibilidade WCAG 2.1 AA

**User Story:** Como um usuário com necessidades de acessibilidade, eu quero que o dashboard seja navegável e compreensível, para que eu possa usar a plataforma independentemente de minhas capacidades.

#### Acceptance Criteria

1. THE Dashboard_System SHALL maintain color contrast ratio of at least 4.5:1 for normal text and 3:1 for large text
2. THE Dashboard_System SHALL provide keyboard navigation for all interactive elements with visible focus indicators
3. THE Dashboard_System SHALL include ARIA labels for icon-only buttons
4. THE Dashboard_System SHALL announce dynamic content updates to screen readers using ARIA live regions
5. THE Dashboard_System SHALL support prefers-reduced-motion media query to disable animations
6. WHEN prefers-reduced-motion is enabled, THE Dashboard_System SHALL replace animations with instant state changes
7. THE Dashboard_System SHALL provide alt text for all informational images and icons

### Requirement 11: Compatibilidade com Design Tokens Existentes

**User Story:** Como um desenvolvedor, eu quero que o redesign use os design tokens existentes, para que a implementação seja consistente com o sistema de design atual.

#### Acceptance Criteria

1. THE Dashboard_System SHALL use only color variables defined in os-tokens.css
2. THE Dashboard_System SHALL use spacing variables var(--os-space-*) for all spacing values
3. THE Dashboard_System SHALL use font family variables var(--os-font-*) for all typography
4. THE Dashboard_System SHALL use border radius variables var(--os-radius-*) for all rounded corners
5. THE Dashboard_System SHALL use easing variables var(--os-ease-*) for all transitions
6. IF a required design token does not exist, THE Dashboard_System SHALL add it to os-tokens.css following existing naming conventions
7. THE Dashboard_System SHALL support both dark and light themes using existing html.light selector

### Requirement 12: Performance e Otimização

**User Story:** Como um usuário, eu quero que o dashboard carregue rapidamente e responda instantaneamente, para que eu possa trabalhar de forma eficiente.

#### Acceptance Criteria

1. THE Dashboard_System SHALL achieve First Contentful Paint (FCP) within 1.5 seconds on 3G connection
2. THE Dashboard_System SHALL achieve Time to Interactive (TTI) within 3 seconds on 3G connection
3. THE Dashboard_System SHALL lazy-load Activity_Feed items beyond the initial 10 visible items
4. THE Dashboard_System SHALL debounce scroll event listeners with minimum 100ms delay
5. THE Dashboard_System SHALL use CSS containment (contain: layout style paint) for isolated components
6. THE Dashboard_System SHALL preload critical fonts using link rel="preload"
7. THE Dashboard_System SHALL minimize layout shifts with explicit width and height for dynamic content areas

### Requirement 13: Empty States Informativos

**User Story:** Como um novo usuário, eu quero ver mensagens claras quando não há dados, para que eu entenda o que fazer a seguir.

#### Acceptance Criteria

1. WHEN Activity_Feed has no items, THE Dashboard_System SHALL display an empty state message with illustration
2. WHEN Quick_Stats has no data, THE Dashboard_System SHALL display placeholder visualization with instructional text
3. THE Dashboard_System SHALL include a primary call-to-action button in empty states
4. THE Dashboard_System SHALL use color var(--os-text-3) for empty state text
5. THE Dashboard_System SHALL center-align empty state content within its container

### Requirement 14: Drill-Down Modal Interativo

**User Story:** Como um operations manager, eu quero explorar métricas em profundidade através de modais interativos, para que eu possa analisar dados sem sair da overview.

#### Acceptance Criteria

1. WHEN a user clicks a KPI_Card, THE Dashboard_System SHALL open Drill_Down_Modal within 200ms
2. THE Drill_Down_Modal SHALL display metric name as heading with font size 24px
3. THE Drill_Down_Modal SHALL render a detailed chart with minimum height 320px
4. THE Drill_Down_Modal SHALL include time range selector with options: "7 days", "30 days", "90 days"
5. WHEN a user changes time range, THE Drill_Down_Modal SHALL update chart data within 500ms
6. THE Drill_Down_Modal SHALL include export button to download data as CSV
7. WHEN a user clicks outside the modal or presses ESC, THE Dashboard_System SHALL close Drill_Down_Modal with fade-out animation
8. THE Drill_Down_Modal SHALL trap keyboard focus within modal while open

### Requirement 15: Activity Feed Filtering

**User Story:** Como um designer, eu quero filtrar atividades por tipo, para que eu possa focar em eventos relevantes para meu trabalho.

#### Acceptance Criteria

1. THE Dashboard_System SHALL display filter buttons for "Todos", "Captura", "Geração", "Execução"
2. WHEN a user clicks a filter button, THE Dashboard_System SHALL update Activity_Feed within 300ms
3. THE Dashboard_System SHALL highlight the active filter button with background var(--os-accent-dim) and color var(--os-accent)
4. WHEN a filter is active, THE Dashboard_System SHALL display item count badge next to filter label
5. THE Dashboard_System SHALL persist filter selection in sessionStorage
6. WHEN the page reloads, THE Dashboard_System SHALL restore the previously selected filter

### Requirement 16: Implementação Isolada Sem Modificar Legado

**User Story:** Como um desenvolvedor, eu quero implementar o novo dashboard sem modificar os arquivos legados, para que possamos manter a versão antiga funcionando e fazer rollback se necessário.

#### Acceptance Criteria

1. THE Dashboard_System SHALL create new template file `templates/dashboard_v2.html` without modifying `templates/dashboard.html`
2. THE Dashboard_System SHALL create new route `/dashboard/v2` in `app.py` without modifying existing `/dashboard` route
3. THE Dashboard_System SHALL create new CSS file `static/dashboard-v2.css` without modifying existing stylesheets
4. THE Dashboard_System SHALL create new JavaScript file `static/dashboard-v2.js` without modifying existing scripts
5. THE Dashboard_System SHALL reuse existing design tokens from `static/os-tokens.css` without modification
6. THE Dashboard_System SHALL add new design tokens to `static/os-tokens-v2.css` if needed, extending (not replacing) base tokens
7. THE Dashboard_System SHALL maintain backward compatibility by keeping all existing routes and templates functional
8. THE Dashboard_System SHALL provide a feature flag or configuration option to switch between v1 and v2 dashboards
9. WHEN accessing `/dashboard`, THE Dashboard_System SHALL continue serving the legacy dashboard (v1)
10. WHEN accessing `/dashboard/v2`, THE Dashboard_System SHALL serve the new redesigned dashboard (v2)
11. THE Dashboard_System SHALL include a toggle link in both versions to switch between v1 and v2
12. THE Dashboard_System SHALL share backend API endpoints between v1 and v2 without breaking changes

## Non-Functional Requirements

### Performance

1. THE Dashboard_System SHALL render initial view within 1.5 seconds on 3G connection
2. THE Dashboard_System SHALL maintain 60fps during scroll and animations
3. THE Dashboard_System SHALL limit JavaScript bundle size increase to maximum 50KB (gzipped)
4. THE Dashboard_System SHALL achieve Lighthouse Performance score of at least 90

### Accessibility

1. THE Dashboard_System SHALL comply with WCAG 2.1 Level AA standards
2. THE Dashboard_System SHALL support keyboard-only navigation
3. THE Dashboard_System SHALL provide screen reader announcements for dynamic updates
4. THE Dashboard_System SHALL respect user's prefers-reduced-motion preference

### Browser Compatibility

1. THE Dashboard_System SHALL support Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
2. THE Dashboard_System SHALL gracefully degrade features in older browsers
3. THE Dashboard_System SHALL use CSS feature queries (@supports) for progressive enhancement

### Maintainability

1. THE Dashboard_System SHALL use only design tokens from os-tokens.css
2. THE Dashboard_System SHALL follow existing CSS naming conventions
3. THE Dashboard_System SHALL document all new JavaScript functions with JSDoc comments
4. THE Dashboard_System SHALL maintain separation between presentation and business logic

### Security

1. THE Dashboard_System SHALL sanitize all user-generated content before rendering
2. THE Dashboard_System SHALL validate all data from backend APIs before display
3. THE Dashboard_System SHALL not expose sensitive system information in client-side code

### Compatibility

1. THE Dashboard_System SHALL preserve existing FastAPI backend routes
2. THE Dashboard_System SHALL maintain compatibility with Jinja2 template rendering
3. THE Dashboard_System SHALL not break existing dashboard functionality during rollout
4. THE Dashboard_System SHALL support progressive enhancement (core functionality works without JavaScript)
5. THE Dashboard_System SHALL implement v2 as completely separate files (templates/dashboard_v2.html, static/dashboard-v2.css, static/dashboard-v2.js)
6. THE Dashboard_System SHALL keep legacy dashboard (v1) fully functional at `/dashboard` route
7. THE Dashboard_System SHALL serve new dashboard (v2) at `/dashboard/v2` route
8. THE Dashboard_System SHALL allow seamless switching between v1 and v2 via toggle link

## Testing Strategy

### Unit Testing

- Test sparkline SVG generation with various data inputs
- Test filter logic for Activity_Feed
- Test time range calculations for charts
- Test responsive breakpoint logic

### Integration Testing

- Test KPI card click → modal open → data fetch → chart render flow
- Test Activity_Feed load → filter → item click navigation flow
- Test scroll-triggered animations with intersection observer

### Visual Regression Testing

- Capture screenshots of hero section at 1920px, 1280px, 768px, 375px widths
- Capture screenshots of KPI cards in default, hover, and active states
- Capture screenshots of Activity_Feed with 0, 5, and 10+ items
- Capture screenshots in both dark and light themes

### Accessibility Testing

- Test keyboard navigation through all interactive elements
- Test screen reader announcements with NVDA and VoiceOver
- Test color contrast ratios with automated tools
- Test with prefers-reduced-motion enabled

### Performance Testing

- Measure FCP, LCP, TTI with Lighthouse on 3G throttling
- Measure animation frame rate during scroll with Chrome DevTools
- Measure JavaScript execution time for chart rendering
- Measure memory usage during extended session

## Success Metrics

1. **User Engagement**: 30% increase in quick action button clicks
2. **Information Discovery**: 50% increase in KPI card drill-down interactions
3. **Performance**: Lighthouse Performance score ≥ 90
4. **Accessibility**: Zero critical accessibility violations in automated audits
5. **User Satisfaction**: Positive feedback from 80% of beta testers on visual hierarchy and clarity

## Out of Scope (Future Phases)

- Studio Transformation (separate feature)
- Customizable dashboard layouts
- Real-time collaborative features
- Advanced data export formats beyond CSV
- Mobile native app optimization
- Dashboard widget marketplace
- AI-powered insights and recommendations

## Dependencies

- Existing design tokens in os-tokens.css (reused without modification)
- FastAPI backend routes for dashboard data (shared between v1 and v2)
- Jinja2 template rendering system
- Browser support for CSS Grid, Flexbox, CSS Custom Properties
- Intersection Observer API for scroll-triggered animations

## Implementation Strategy

### File Structure

```
templates/
  ├── dashboard.html          # Legacy v1 (untouched)
  └── dashboard_v2.html        # New redesigned version

static/
  ├── os-tokens.css           # Base tokens (untouched)
  ├── os-tokens-v2.css        # Extended tokens for v2 (optional)
  ├── dashboard-v2.css        # New dashboard styles
  └── dashboard-v2.js         # New dashboard scripts

app.py
  ├── /dashboard              # Legacy route (untouched)
  └── /dashboard/v2           # New route for v2
```

### Rollout Strategy

1. **Phase 1 - Development**: Build v2 at `/dashboard/v2` route
2. **Phase 2 - Beta Testing**: Internal team tests v2 while v1 remains default
3. **Phase 3 - Opt-in**: Users can toggle to v2 via preference setting
4. **Phase 4 - Gradual Rollout**: Percentage-based rollout (10% → 50% → 100%)
5. **Phase 5 - Default Switch**: Make v2 default, keep v1 accessible
6. **Phase 6 - Deprecation**: After stability period, deprecate v1

### Toggle Implementation

- Add "Try New Dashboard" link in v1 header → redirects to `/dashboard/v2`
- Add "Back to Classic Dashboard" link in v2 header → redirects to `/dashboard`
- Store user preference in localStorage or user profile
- Respect user preference on subsequent visits

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance degradation with animations | High | Use CSS transforms, will-change, requestAnimationFrame; measure with Lighthouse |
| Breaking existing dashboard functionality | High | **ELIMINATED**: Implement v2 as separate files; keep v1 untouched at `/dashboard` |
| Accessibility violations | Medium | Follow WCAG 2.1 AA checklist; automated and manual testing |
| Browser compatibility issues | Medium | Use feature detection; provide fallbacks; test on target browsers |
| Design token conflicts | Low | Create os-tokens-v2.css for new tokens; extend (not replace) base tokens |
| Code duplication between v1 and v2 | Low | Share backend APIs; extract reusable components; plan migration path |
| User confusion with two versions | Medium | Clear toggle UI; user preference persistence; gradual rollout strategy |

## Appendix: Design Patterns from Foccum Analysis

### Identified Patterns Applied to This Redesign

1. **Hero Sections**: Large, impactful typography (56-72px) with clear CTAs
2. **Microinterações**: Hover states with subtle transforms and shadow enhancements
3. **Hierarquia Visual**: Strong typographic scale with generous spacing
4. **Progressive Disclosure**: Show essential info by default, reveal details on interaction
5. **Scroll-Triggered Animations**: Fade-in and slide-up animations as elements enter viewport
6. **Breathing Room**: Minimum 48px vertical spacing between major sections
7. **Sparklines**: Inline data visualization for quick trend comprehension
8. **Activity Timelines**: Vertical timeline with visual connectors and type indicators
9. **Heatmaps**: Color-coded intensity visualization for temporal data
10. **Empty States**: Informative placeholders with clear next actions

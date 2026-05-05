# Design Document: Dashboard Overview Page Redesign (v2)

## Overview

O Dashboard Overview Page Redesign (v2) moderniza a interface principal do Training OS seguindo padrões de design contemporâneos identificados na análise do site Foccum. Esta implementação cria uma versão completamente isolada (v2) sem modificar o dashboard legado (v1), permitindo rollback seguro e transição gradual.

O redesign foca em hierarquia visual aprimorada, densidade de informação otimizada, microinterações suaves e experiência do usuário moderna. Os componentes principais incluem Hero Section impactante, KPI Cards com sparklines animados, Activity Feed visual e Quick Stats Dashboard aprimorado.

### Objetivos de Design

1. **Hierarquia Visual Moderna**: Tipografia display de 56-72px, espaçamento generoso (48px+ entre seções)
2. **Progressive Disclosure**: Informação essencial por padrão, detalhes sob demanda via hover/click
3. **Microinterações Performáticas**: Animações 60fps usando CSS transforms, scroll-triggered animations
4. **Responsividade Adaptativa**: 3/2/1 colunas baseado em viewport, touch targets 44px+ em mobile
5. **Acessibilidade WCAG 2.1 AA**: Contraste 4.5:1, navegação por teclado, screen reader support

## Architecture

### File Structure Strategy

A implementação v2 utiliza estratégia de isolamento completo para permitir desenvolvimento paralelo e rollback seguro:

```
templates/
  ├── dashboard.html          # Legacy v1 (untouched)
  └── dashboard_v2.html       # New redesigned version

static/
  ├── os-tokens.css           # Base tokens (shared, untouched)
  ├── dashboard-v2.css        # New dashboard styles
  └── dashboard-v2.js         # New dashboard scripts

app.py
  ├── /dashboard              # Legacy route (untouched)
  └── /dashboard/v2           # New route for v2
```

### Backend Architecture

**Route Isolation**:
- `/dashboard` → `templates/dashboard.html` (legacy v1)
- `/dashboard/v2` → `templates/dashboard_v2.html` (new v2)
- Shared backend APIs sem breaking changes
- Toggle links entre v1 ↔ v2 para user testing

**Data Layer Compatibility**:
- Reutiliza endpoints existentes do FastAPI
- Mantém contratos de API entre v1 e v2
- Preserva estrutura de dados de roteiros, KPIs, atividades
- Suporte a WebSocket para updates em tempo real

### Frontend Architecture

**Component-Based Structure**:
```javascript
// dashboard-v2.js
class DashboardV2 {
  constructor() {
    this.components = {
      heroSection: new HeroSection(),
      kpiCards: new KPICards(),
      activityFeed: new ActivityFeed(),
      quickStats: new QuickStats()
    };
  }
}

class KPICards {
  constructor() {
    this.sparklines = new SparklineRenderer();
    this.drillDownModal = new DrillDownModal();
  }
}
```

**CSS Architecture**:
```css
/* dashboard-v2.css */
/* Extends os-tokens.css without modification */
@import url('/static/os-tokens.css');

/* V2-specific components */
.dashboard-v2 { /* container */ }
.hero-v2 { /* hero section */ }
.kpi-grid-v2 { /* KPI cards */ }
.activity-feed-v2 { /* activity timeline */ }
.quick-stats-v2 { /* charts and heatmap */ }
```

## Components and Interfaces

### 1. Hero Section Component

**Purpose**: Impactful entry point com título display e quick actions

**Structure**:
```html
<section class="hero-v2">
  <div class="hero-content">
    <h1 class="hero-title">Training OS</h1>
    <p class="hero-subtitle">Knowledge Platform</p>
    <div class="hero-actions">
      <button class="btn-primary">Novo Roteiro</button>
      <button class="btn-secondary">Importar</button>
      <button class="btn-secondary">Templates</button>
    </div>
  </div>
  <div class="hero-status">
    <div class="status-indicator live">
      <div class="pulse-dot"></div>
      <span>Sistema Ativo</span>
    </div>
  </div>
</section>
```

**CSS Specifications**:
- Hero title: `font-size: 56px-72px`, `font-family: var(--os-font-display)`
- Vertical spacing: `margin-bottom: var(--os-space-8)` (48px)
- Quick actions: `transform: translateY(-2px)` on hover
- Status indicator: CSS pulse animation `@keyframes pulse`

**JavaScript Interface**:
```javascript
class HeroSection {
  constructor(container) {
    this.container = container;
    this.bindEvents();
  }
  
  bindEvents() {
    // Hover effects for quick actions
    // Status indicator pulse animation
  }
}
```

### 2. KPI Cards Component

**Purpose**: Métricas-chave com sparklines animados e drill-down interativo

**Structure**:
```html
<div class="kpi-grid-v2">
  <div class="kpi-card" data-metric="roteiros-criados">
    <div class="kpi-header">
      <span class="kpi-label">Roteiros Criados</span>
      <div class="kpi-sparkline">
        <svg class="sparkline-svg"></svg>
      </div>
    </div>
    <div class="kpi-value">
      <span class="metric-number">127</span>
      <span class="metric-unit">total</span>
    </div>
    <div class="kpi-details hidden">
      <span class="metric-delta positive">+12%</span>
      <span class="metric-period">vs. mês anterior</span>
    </div>
  </div>
  <!-- Repeat for 3 KPI cards total -->
</div>
```

**Sparkline Implementation**:
```javascript
class SparklineRenderer {
  constructor() {
    this.animationDuration = 800; // ms
    this.easing = 'var(--os-ease-out)';
  }
  
  render(container, data) {
    const svg = this.createSVG(container);
    const path = this.generatePath(data);
    this.animateDrawing(path);
  }
  
  animateDrawing(path) {
    // CSS animation: stroke-dasharray + stroke-dashoffset
    // Duration: 800ms, Easing: var(--os-ease-out)
  }
}
```

**Drill-Down Modal**:
```javascript
class DrillDownModal {
  constructor() {
    this.isOpen = false;
    this.timeRanges = ['7 days', '30 days', '90 days'];
  }
  
  open(metricData) {
    // Backdrop overlay: opacity 0.6, backdrop-filter blur(8px)
    // Modal animation: fade-in 200ms
    // Chart rendering: minimum height 320px
  }
  
  close() {
    // ESC key support, click outside to close
    // Fade-out animation
  }
}
```

### 3. Activity Feed Component

**Purpose**: Timeline visual de atividades recentes com filtros e preview

**Structure**:
```html
<div class="activity-feed-v2">
  <div class="feed-header">
    <h3 class="feed-title">Atividades Recentes</h3>
    <div class="feed-filters">
      <button class="filter-btn active" data-type="todos">Todos</button>
      <button class="filter-btn" data-type="captura">Captura</button>
      <button class="filter-btn" data-type="geracao">Geração</button>
      <button class="filter-btn" data-type="execucao">Execução</button>
    </div>
  </div>
  <div class="feed-timeline">
    <div class="timeline-connector"></div>
    <div class="activity-item" data-type="captura">
      <div class="activity-icon">
        <svg class="icon-captura"></svg>
      </div>
      <div class="activity-content">
        <h4 class="activity-title">Workflow Capturado</h4>
        <p class="activity-description">Roteiro "Login Senior X"</p>
        <time class="activity-timestamp">2h ago</time>
      </div>
      <div class="activity-preview hidden">
        <!-- Inline preview content -->
      </div>
    </div>
    <!-- Repeat for up to 10 activities -->
  </div>
</div>
```

**Filtering Logic**:
```javascript
class ActivityFeed {
  constructor() {
    this.activities = [];
    this.activeFilter = 'todos';
    this.maxItems = 10;
  }
  
  applyFilter(type) {
    // Update within 300ms
    // Persist in sessionStorage
    // Update item count badge
    const filtered = this.activities.filter(item => 
      type === 'todos' || item.type === type
    );
    this.renderItems(filtered);
  }
  
  renderItems(items) {
    // Reverse chronological order (most recent first)
    // Timeline connector: color var(--os-border-2)
    // Activity icons: size 16px, color var(--os-accent)
  }
}
```

### 4. Quick Stats Component

**Purpose**: Visualizações de dados com velocity chart e heatmap

**Structure**:
```html
<div class="quick-stats-v2">
  <div class="stats-grid">
    <div class="velocity-chart-container">
      <h3 class="chart-title">Velocity de Produção</h3>
      <div class="velocity-chart" style="min-height: 240px;">
        <canvas id="velocityChart"></canvas>
      </div>
      <div class="chart-legend">
        <!-- Legend items -->
      </div>
    </div>
    <div class="heatmap-container">
      <h3 class="chart-title">Atividade Semanal</h3>
      <div class="activity-heatmap">
        <div class="heatmap-grid">
          <!-- 7 columns for days -->
          <div class="heatmap-cell" data-day="0" data-count="5"></div>
          <!-- ... -->
        </div>
      </div>
      <div class="heatmap-scale">
        <!-- Color scale legend -->
      </div>
    </div>
  </div>
  <div class="top-roteiros">
    <h3 class="section-title">Top 5 Roteiros</h3>
    <div class="roteiros-list">
      <!-- Ranked list by views/executions -->
    </div>
  </div>
</div>
```

**Chart Implementation**:
```javascript
class QuickStats {
  constructor() {
    this.velocityChart = null;
    this.heatmapData = [];
  }
  
  renderVelocityChart(data) {
    // Minimum height: 240px
    // Scroll-triggered animation with Intersection Observer
    // Chart legends: font-size 11px, color var(--os-text-3)
  }
  
  renderHeatmap(weeklyData) {
    // 7 columns (days)
    // Color scale: var(--os-surface-2) to var(--os-accent)
    // Tooltip on hover: activity count + date
  }
}
```

## Data Models

### Dashboard Data Structure

```typescript
interface DashboardData {
  kpis: KPIMetric[];
  activities: ActivityItem[];
  stats: QuickStatsData;
  user: UserInfo;
}

interface KPIMetric {
  id: string;
  label: string;
  value: number;
  unit: string;
  delta: {
    value: number;
    type: 'positive' | 'negative' | 'neutral';
    period: string;
  };
  sparkline: number[];
  drillDown: {
    chartData: ChartDataPoint[];
    timeRanges: string[];
  };
}

interface ActivityItem {
  id: string;
  type: 'captura' | 'geracao' | 'execucao';
  title: string;
  description: string;
  timestamp: Date;
  roteiroId?: string;
  preview?: {
    thumbnail: string;
    summary: string;
  };
}

interface QuickStatsData {
  velocity: {
    chartData: ChartDataPoint[];
    period: string;
  };
  heatmap: {
    weeklyData: HeatmapCell[];
    scale: { min: number; max: number; };
  };
  topRoteiros: {
    id: string;
    title: string;
    views: number;
    executions: number;
  }[];
}
```

### API Endpoints

```typescript
// Existing endpoints (shared with v1)
GET /api/dashboard/kpis -> KPIMetric[]
GET /api/dashboard/activities -> ActivityItem[]
GET /api/dashboard/stats -> QuickStatsData

// New v2-specific endpoints (if needed)
GET /api/dashboard/v2/heatmap -> HeatmapData
GET /api/dashboard/v2/velocity -> VelocityData
```

### Data Flow Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Backend APIs  │───▶│  Dashboard V2 JS │───▶│  UI Components  │
│   (FastAPI)     │    │   (Controller)   │    │   (Rendering)   │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Database      │    │   State Mgmt     │    │   DOM Updates   │
│   (SQLite)      │    │   (Local)        │    │   (Reactive)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

**Data Loading Strategy**:
1. **Initial Load**: Fetch all dashboard data on page load
2. **Lazy Loading**: Activity feed items beyond initial 10
3. **Real-time Updates**: WebSocket for live metrics updates
4. **Caching**: SessionStorage for filter states, localStorage for user preferences

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system-essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Hero Section Typography Consistency

*For any* hero section rendering, the title element should use font-family var(--os-font-display) and font-size between 56px and 72px

**Validates: Requirements 1.1, 5.2**

### Property 2: Interactive Element Hover Response

*For any* interactive element (buttons, cards, links), hovering should trigger visual feedback within 150ms using CSS transforms rather than position changes

**Validates: Requirements 1.4, 7.1**

### Property 3: KPI Card Sparkline Animation Consistency

*For any* KPI card with sparkline data, the draw animation should complete in 800ms using var(--os-ease-out) easing function

**Validates: Requirements 2.2**

### Property 4: Progressive Disclosure in KPI Cards

*For any* KPI card, the default state should show only primary metric value and label, with secondary details revealed on hover with opacity transition 0→1 in 200ms

**Validates: Requirements 2.3, 8.1, 8.2**

### Property 5: Activity Feed Chronological Ordering

*For any* set of activity items with timestamps, they should display in reverse chronological order (most recent first)

**Validates: Requirements 3.2**

### Property 6: Activity Feed Filtering Consistency

*For any* activity filter selection, the feed should update within 300ms showing only items matching the selected type, with filter state persisted in sessionStorage

**Validates: Requirements 3.5, 15.1, 15.2, 15.5**

### Property 7: Responsive Grid Layout Adaptation

*For any* viewport width change, KPI cards should display in 3 columns (>1280px), 2 columns (768-1280px), or 1 column (<768px) with appropriate spacing

**Validates: Requirements 9.1, 9.2, 9.3**

### Property 8: Design Token Compliance

*For any* styled element, all color, spacing, typography, and easing values should use CSS variables from os-tokens.css

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 9: Accessibility Contrast Requirements

*For any* text element, the color contrast ratio should meet WCAG 2.1 AA standards (4.5:1 for normal text, 3:1 for large text)

**Validates: Requirements 10.1**

### Property 10: Keyboard Navigation Support

*For any* interactive element, it should be reachable via keyboard navigation with visible focus indicators

**Validates: Requirements 10.2**

### Property 11: File Isolation Preservation

*For any* v2 implementation file, it should not modify existing v1 files (dashboard.html, existing CSS/JS)

**Validates: Requirements 16.1, 16.2, 16.3, 16.4**

### Property 12: Spacing Consistency

*For any* pair of adjacent major sections, the vertical spacing should be at least 48px (var(--os-space-8))

**Validates: Requirements 6.1**

## Error Handling

### Client-Side Error Handling

**API Failure Scenarios**:
```javascript
class DashboardV2 {
  async loadDashboardData() {
    try {
      const data = await this.fetchDashboardData();
      this.renderComponents(data);
    } catch (error) {
      this.handleLoadError(error);
    }
  }
  
  handleLoadError(error) {
    // Show graceful error state
    // Retry mechanism with exponential backoff
    // Fallback to cached data if available
  }
}
```

**Empty State Handling**:
- Activity Feed: Informative empty state with illustration and CTA
- KPI Cards: Placeholder values with loading skeletons
- Charts: "No data available" message with setup instructions

**Network Connectivity**:
- Offline detection with service worker
- Cached data display when offline
- Reconnection handling with data sync

### Animation Error Handling

**Performance Degradation**:
```css
/* Respect user preferences */
@media (prefers-reduced-motion: reduce) {
  .sparkline-animation,
  .hover-transform,
  .scroll-triggered {
    animation: none !important;
    transition: none !important;
  }
}
```

**Browser Compatibility**:
```javascript
// Feature detection for CSS Grid, Flexbox, Custom Properties
if (!CSS.supports('display', 'grid')) {
  // Fallback to flexbox layout
}

if (!CSS.supports('backdrop-filter', 'blur(8px)')) {
  // Fallback modal backdrop
}
```

### Data Validation

**Input Sanitization**:
```javascript
class DataValidator {
  validateKPIData(data) {
    // Ensure numeric values are valid
    // Sanitize text content
    // Validate date formats
  }
  
  validateActivityData(activities) {
    // Ensure required fields exist
    // Validate activity types
    // Sanitize user-generated content
  }
}
```

## Testing Strategy

### Unit Testing

**Component Testing**:
- Hero Section: Typography rendering, button interactions
- KPI Cards: Sparkline generation, hover states, modal opening
- Activity Feed: Filtering logic, chronological sorting
- Quick Stats: Chart rendering, heatmap color mapping

**Utility Testing**:
- Data validation functions
- Animation timing calculations
- Responsive breakpoint logic
- Design token usage verification

### Integration Testing

**User Flow Testing**:
1. Page load → data fetch → component rendering → animations
2. KPI card click → modal open → time range change → chart update
3. Activity filter → feed update → item click → navigation
4. Viewport resize → responsive layout → component reflow

**API Integration**:
- Dashboard data loading with various response scenarios
- WebSocket connection for real-time updates
- Error handling for network failures

### Visual Regression Testing

**Screenshot Comparison**:
- Hero section at 1920px, 1280px, 768px, 375px widths
- KPI cards in default, hover, and modal states
- Activity feed with 0, 5, and 10+ items
- Dark and light theme variations
- Empty states for all components

**Animation Testing**:
- Sparkline draw animations
- Hover state transitions
- Scroll-triggered animations
- Modal open/close animations

### Accessibility Testing

**Automated Testing**:
- axe-core integration for WCAG compliance
- Color contrast ratio validation
- Keyboard navigation flow testing
- Screen reader announcement verification

**Manual Testing**:
- NVDA and VoiceOver compatibility
- Keyboard-only navigation
- High contrast mode support
- Reduced motion preference respect

### Performance Testing

**Core Web Vitals**:
- First Contentful Paint (FCP) < 1.5s on 3G
- Largest Contentful Paint (LCP) < 2.5s
- Cumulative Layout Shift (CLS) < 0.1
- First Input Delay (FID) < 100ms

**Animation Performance**:
- 60fps maintenance during scroll
- Memory usage during extended sessions
- CPU usage for chart rendering
- Battery impact on mobile devices

**Load Testing**:
```javascript
// Performance measurement
const observer = new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.entryType === 'paint') {
      console.log(`${entry.name}: ${entry.startTime}ms`);
    }
  }
});
observer.observe({ entryTypes: ['paint'] });
```

### Property-Based Testing Configuration

**Test Framework**: Jest + fast-check for JavaScript property testing

**Property Test Examples**:
```javascript
// Property 1: Hero Typography
fc.assert(fc.property(
  fc.string({ minLength: 1, maxLength: 100 }), // Random title text
  (titleText) => {
    const heroElement = renderHeroSection(titleText);
    const titleElement = heroElement.querySelector('.hero-title');
    
    const computedStyle = getComputedStyle(titleElement);
    const fontSize = parseInt(computedStyle.fontSize);
    const fontFamily = computedStyle.fontFamily;
    
    return fontSize >= 56 && fontSize <= 72 && 
           fontFamily.includes('Outfit');
  }
), { numRuns: 100 });

// Property 4: Progressive Disclosure
fc.assert(fc.property(
  fc.array(fc.record({
    label: fc.string(),
    value: fc.nat(),
    delta: fc.float()
  }), { minLength: 1, maxLength: 10 }), // Random KPI data
  (kpiData) => {
    const kpiCards = renderKPICards(kpiData);
    
    return kpiCards.every(card => {
      const details = card.querySelector('.kpi-details');
      const defaultOpacity = getComputedStyle(details).opacity;
      
      // Simulate hover
      card.dispatchEvent(new Event('mouseenter'));
      
      const hoverOpacity = getComputedStyle(details).opacity;
      
      return defaultOpacity === '0' && hoverOpacity === '1';
    });
  }
), { numRuns: 100 });
```

**Test Configuration**:
- Minimum 100 iterations per property test
- Tag format: **Feature: dashboard-overview-redesign, Property {number}: {property_text}**
- Timeout: 30 seconds per property test
- Shrinking enabled for counterexample minimization

### Test Environment Setup

**Browser Testing Matrix**:
- Chrome 90+ (primary)
- Firefox 88+ (secondary)
- Safari 14+ (WebKit)
- Edge 90+ (Chromium)

**Device Testing**:
- Desktop: 1920x1080, 1366x768
- Tablet: 1024x768, 768x1024
- Mobile: 375x667, 414x896

**Network Conditions**:
- Fast 3G (1.6 Mbps down, 750 Kbps up, 150ms RTT)
- Slow 3G (400 Kbps down, 400 Kbps up, 400ms RTT)
- Offline scenarios

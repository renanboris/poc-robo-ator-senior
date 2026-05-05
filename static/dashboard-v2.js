/**
 * Dashboard v2 JavaScript
 * =======================
 * Modern dashboard functionality following component-based architecture
 */

'use strict';

// ═══════════════════════════════════════════════════════════
// DASHBOARD V2 MAIN CLASS
// ═══════════════════════════════════════════════════════════

class DashboardV2 {
  constructor() {
    this.components = {
      heroSection: new HeroSection(),
      kpiCards: new KPICards(),
      activityFeed: new ActivityFeed(),
      quickStats: new QuickStats()
    };
    
    this.init();
  }
  
  async init() {
    try {
      // Initialize all components
      await this.loadDashboardData();
      this.setupEventListeners();
      this.initializeComponents();
      
      console.log('Dashboard v2 initialized successfully');
    } catch (error) {
      console.error('Dashboard v2 initialization failed:', error);
      this.handleInitError(error);
    }
  }
  
  async loadDashboardData() {
    // Mock data for now - will be replaced with actual API calls
    this.data = {
      kpis: [
        {
          id: 'roteiros-criados',
          label: 'Roteiros Criados',
          value: 127,
          unit: 'total',
          delta: { value: 12, type: 'positive', period: 'vs. mês anterior' },
          sparkline: [45, 52, 48, 61, 55, 67, 59, 73, 68, 82, 78, 89, 85, 97, 92, 105, 101, 114, 110, 127]
        },
        {
          id: 'execucoes',
          label: 'Execuções',
          value: 2400,
          unit: 'runs',
          delta: { value: 8, type: 'positive', period: 'vs. mês anterior' },
          sparkline: [1800, 1950, 1850, 2100, 1980, 2250, 2150, 2400, 2300, 2400]
        },
        {
          id: 'taxa-sucesso',
          label: 'Taxa de Sucesso',
          value: 94.2,
          unit: '%',
          delta: { value: 2.1, type: 'positive', period: 'vs. mês anterior' },
          sparkline: [89.5, 90.2, 91.1, 92.3, 91.8, 93.1, 92.7, 94.2, 93.8, 94.2]
        }
      ],
      activities: [
        {
          id: '1',
          type: 'captura',
          title: 'Workflow Capturado',
          description: 'Roteiro "Login Senior X" criado com sucesso',
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000), // 2h ago
          preview: '15 passos capturados, 3 validações incluídas'
        },
        {
          id: '2',
          type: 'geracao',
          title: 'Roteiro Gerado',
          description: 'IA processou "Cadastro de Cliente" automaticamente',
          timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000), // 3h ago
          preview: 'Geração completa em 45s, 98% de confiança'
        },
        {
          id: '3',
          type: 'execucao',
          title: 'Execução Realizada',
          description: 'Roteiro "Emissão NF-e" executado com sucesso',
          timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000), // 4h ago
          preview: 'Execução em 2m 34s, todos os passos validados'
        }
      ],
      stats: {
        velocity: {
          chartData: Array.from({ length: 30 }, (_, i) => ({
            date: new Date(Date.now() - (29 - i) * 24 * 60 * 60 * 1000),
            value: Math.floor(Math.random() * 10) + 5
          }))
        },
        heatmap: {
          weeklyData: [5, 8, 12, 7, 15, 3, 1] // Mon-Sun activity counts
        }
      }
    };
  }
  
  setupEventListeners() {
    // Global keyboard shortcuts
    document.addEventListener('keydown', this.handleKeyboardShortcuts.bind(this));
    
    // Intersection Observer for scroll-triggered animations
    this.setupScrollAnimations();
  }
  
  initializeComponents() {
    this.components.kpiCards.render(this.data.kpis);
    this.components.activityFeed.render(this.data.activities);
    this.components.quickStats.render(this.data.stats);
  }
  
  handleKeyboardShortcuts(event) {
    // ESC key handling
    if (event.key === 'Escape') {
      this.components.kpiCards.closeModal();
    }
  }
  
  setupScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.style.animationPlayState = 'running';
        }
      });
    }, { threshold: 0.1 });
    
    // Observe animated elements
    document.querySelectorAll('[class*="fade-up"]').forEach(el => {
      observer.observe(el);
    });
  }
  
  handleInitError(error) {
    // Show user-friendly error message
    const container = document.querySelector('.dashboard-container');
    if (container) {
      container.innerHTML = `
        <div class="error-state">
          <h2>Erro ao carregar dashboard</h2>
          <p>Ocorreu um problema ao inicializar o dashboard. Tente recarregar a página.</p>
          <button onclick="window.location.reload()" class="btn-primary">Recarregar</button>
        </div>
      `;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// HERO SECTION COMPONENT
// ═══════════════════════════════════════════════════════════

class HeroSection {
  constructor() {
    this.container = document.querySelector('.hero-v2');
    this.bindEvents();
  }
  
  bindEvents() {
    if (!this.container) return;
    
    // Quick action button handlers
    const buttons = this.container.querySelectorAll('button');
    buttons.forEach(button => {
      button.addEventListener('click', this.handleButtonClick.bind(this));
    });
  }
  
  handleButtonClick(event) {
    const button = event.currentTarget;
    const text = button.textContent.trim();
    
    // Add click animation
    button.style.transform = 'translateY(-2px) scale(0.98)';
    setTimeout(() => {
      button.style.transform = '';
    }, 150);
    
    // Handle different actions
    switch (text) {
      case 'Novo Roteiro':
        window.location.href = '/';
        break;
      case 'Importar':
        console.log('Import functionality not implemented yet');
        break;
      case 'Templates':
        console.log('Templates functionality not implemented yet');
        break;
    }
  }
}

// ═══════════════════════════════════════════════════════════
// KPI CARDS COMPONENT
// ═══════════════════════════════════════════════════════════

class KPICards {
  constructor() {
    this.container = document.querySelector('.kpi-grid-v2');
    this.modal = null;
    this.sparklineRenderer = new SparklineRenderer();
    this.bindEvents();
  }
  
  bindEvents() {
    if (!this.container) return;
    
    // Card click handlers
    this.container.addEventListener('click', this.handleCardClick.bind(this));
    
    // Card keyboard handlers (Enter and Space)
    this.container.addEventListener('keydown', this.handleCardKeydown.bind(this));
    
    // Card hover handlers
    this.container.addEventListener('mouseenter', this.handleCardHover.bind(this), true);
    this.container.addEventListener('mouseleave', this.handleCardLeave.bind(this), true);
  }
  
  handleCardKeydown(event) {
    const card = event.target.closest('.kpi-card');
    if (!card) return;
    
    // Activate on Enter or Space
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      const metricId = card.dataset.metric;
      this.openDrillDownModal(metricId);
    }
  }
  
  render(kpiData) {
    if (!this.container || !kpiData) return;
    
    const cards = this.container.querySelectorAll('.kpi-card');
    cards.forEach((card, index) => {
      if (kpiData[index]) {
        this.updateCard(card, kpiData[index]);
      }
    });
  }
  
  updateCard(card, data) {
    // Update metric value
    const numberEl = card.querySelector('.metric-number');
    const unitEl = card.querySelector('.metric-unit');
    if (numberEl) numberEl.textContent = this.formatNumber(data.value);
    if (unitEl) unitEl.textContent = data.unit;
    
    // Update delta
    const deltaEl = card.querySelector('.metric-delta');
    if (deltaEl && data.delta) {
      deltaEl.textContent = `${data.delta.value > 0 ? '+' : ''}${data.delta.value}%`;
      deltaEl.className = `metric-delta ${data.delta.type}`;
    }
    
    // Render sparkline
    const sparklineEl = card.querySelector('.sparkline-svg');
    if (sparklineEl && data.sparkline) {
      this.sparklineRenderer.render(sparklineEl, data.sparkline);
    }
  }
  
  formatNumber(value) {
    if (value >= 1000) {
      return (value / 1000).toFixed(1) + 'k';
    }
    return value.toString();
  }
  
  handleCardClick(event) {
    const card = event.target.closest('.kpi-card');
    if (!card) return;
    
    const metricId = card.dataset.metric;
    this.openDrillDownModal(metricId);
  }
  
  handleCardHover(event) {
    const card = event.target.closest('.kpi-card');
    if (!card) return;
    
    const details = card.querySelector('.kpi-details');
    if (details) {
      details.classList.remove('hidden');
    }
  }
  
  handleCardLeave(event) {
    const card = event.target.closest('.kpi-card');
    if (!card) return;
    
    const details = card.querySelector('.kpi-details');
    if (details) {
      details.classList.add('hidden');
    }
  }
  
  openDrillDownModal(metricId) {
    // Create modal if it doesn't exist
    if (!this.modal) {
      this.createModal();
    }
    
    // Show modal with metric data
    this.modal.style.display = 'flex';
    this.modal.setAttribute('aria-hidden', 'false');
    
    // Focus trap
    const firstFocusable = this.modal.querySelector('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
    if (firstFocusable) {
      firstFocusable.focus();
    }
    
    console.log(`Opening drill-down modal for metric: ${metricId}`);
  }
  
  createModal() {
    this.modal = document.createElement('div');
    this.modal.className = 'drill-down-modal';
    this.modal.innerHTML = `
      <div class="modal-backdrop"></div>
      <div class="modal-content">
        <div class="modal-header">
          <h2 class="modal-title">Detalhes da Métrica</h2>
          <button class="modal-close" aria-label="Fechar modal">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
        <div class="modal-body">
          <p>Funcionalidade de drill-down será implementada em breve.</p>
        </div>
      </div>
    `;
    
    // Add modal styles
    this.modal.style.cssText = `
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.6); backdrop-filter: blur(8px);
      display: none; align-items: center; justify-content: center;
      z-index: 1000;
    `;
    
    // Modal content styles
    const content = this.modal.querySelector('.modal-content');
    content.style.cssText = `
      background: var(--os-surface); border: 1px solid var(--os-border-2);
      border-radius: var(--os-radius); padding: var(--os-space-5);
      max-width: 600px; width: 90%; max-height: 80vh; overflow-y: auto;
    `;
    
    // Close button handler
    this.modal.querySelector('.modal-close').addEventListener('click', () => {
      this.closeModal();
    });
    
    // Backdrop click handler
    this.modal.querySelector('.modal-backdrop').addEventListener('click', () => {
      this.closeModal();
    });
    
    document.body.appendChild(this.modal);
  }
  
  closeModal() {
    if (this.modal) {
      this.modal.style.display = 'none';
      this.modal.setAttribute('aria-hidden', 'true');
    }
  }
}

// ═══════════════════════════════════════════════════════════
// SPARKLINE RENDERER
// ═══════════════════════════════════════════════════════════

class SparklineRenderer {
  constructor() {
    this.animationDuration = 800; // ms
  }
  
  render(svg, data) {
    if (!svg || !data || data.length === 0) return;
    
    const width = 80;
    const height = 24;
    const padding = 2;
    
    // Clear existing content
    svg.innerHTML = '';
    
    // Calculate path
    const path = this.generatePath(data, width, height, padding);
    
    // Create path element
    const pathElement = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathElement.setAttribute('d', path);
    pathElement.setAttribute('stroke', 'var(--os-accent)');
    pathElement.setAttribute('stroke-width', '2');
    pathElement.setAttribute('fill', 'none');
    pathElement.setAttribute('stroke-linecap', 'round');
    pathElement.setAttribute('stroke-linejoin', 'round');
    
    // Add animation
    const pathLength = pathElement.getTotalLength ? pathElement.getTotalLength() : 200;
    pathElement.style.strokeDasharray = pathLength;
    pathElement.style.strokeDashoffset = pathLength;
    pathElement.style.animation = `draw-sparkline ${this.animationDuration}ms var(--os-ease-out) forwards`;
    
    svg.appendChild(pathElement);
  }
  
  generatePath(data, width, height, padding) {
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    
    const stepX = (width - 2 * padding) / (data.length - 1);
    
    let path = '';
    
    data.forEach((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - ((value - min) / range) * (height - 2 * padding);
      
      if (index === 0) {
        path += `M ${x} ${y}`;
      } else {
        path += ` L ${x} ${y}`;
      }
    });
    
    return path;
  }
}

// ═══════════════════════════════════════════════════════════
// ACTIVITY FEED COMPONENT
// ═══════════════════════════════════════════════════════════

class ActivityFeed {
  constructor() {
    this.container = document.querySelector('.activity-feed-v2');
    this.timeline = document.querySelector('.feed-timeline');
    this.filters = document.querySelector('.feed-filters');
    this.activeFilter = 'todos';
    this.activities = [];
    
    this.bindEvents();
  }
  
  bindEvents() {
    if (!this.filters) return;
    
    // Filter button handlers
    this.filters.addEventListener('click', this.handleFilterClick.bind(this));
  }
  
  render(activities) {
    this.activities = activities || [];
    this.updateTimeline();
  }
  
  handleFilterClick(event) {
    const button = event.target.closest('.filter-btn');
    if (!button) return;
    
    // Update active filter
    this.filters.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.remove('active');
      btn.setAttribute('aria-pressed', 'false');
    });
    button.classList.add('active');
    button.setAttribute('aria-pressed', 'true');
    
    this.activeFilter = button.dataset.type;
    this.updateTimeline();
    
    // Persist filter in sessionStorage
    sessionStorage.setItem('dashboard-v2-activity-filter', this.activeFilter);
  }
  
  updateTimeline() {
    if (!this.timeline) return;
    
    // Filter activities
    const filteredActivities = this.activeFilter === 'todos' 
      ? this.activities 
      : this.activities.filter(activity => activity.type === this.activeFilter);
    
    // Clear existing items (except connector)
    const connector = this.timeline.querySelector('.timeline-connector');
    this.timeline.innerHTML = '';
    if (connector) {
      this.timeline.appendChild(connector);
    }
    
    // Render filtered activities
    filteredActivities.forEach(activity => {
      const item = this.createActivityItem(activity);
      this.timeline.appendChild(item);
    });
    
    // Show empty state if no activities
    if (filteredActivities.length === 0) {
      this.showEmptyState();
    }
  }
  
  createActivityItem(activity) {
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.dataset.type = activity.type;
    
    item.innerHTML = `
      <div class="activity-icon">
        ${this.getActivityIcon(activity.type)}
      </div>
      <div class="activity-content">
        <h4 class="activity-title">${activity.title}</h4>
        <p class="activity-description">${activity.description}</p>
        <time class="activity-timestamp">${this.formatRelativeTime(activity.timestamp)}</time>
      </div>
    `;
    
    // Add hover preview
    if (activity.preview) {
      item.addEventListener('mouseenter', () => {
        this.showPreview(item, activity.preview);
      });
      
      item.addEventListener('mouseleave', () => {
        this.hidePreview(item);
      });
    }
    
    return item;
  }
  
  getActivityIcon(type) {
    const icons = {
      captura: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M12 1v6m0 6v6m11-7h-6m-6 0H1"/></svg>',
      geracao: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>',
      execucao: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5,3 19,12 5,21"/></svg>'
    };
    
    return icons[type] || icons.captura;
  }
  
  formatRelativeTime(timestamp) {
    const now = new Date();
    const diff = Math.floor((now - timestamp) / 1000);
    
    if (diff < 60) return 'agora';
    if (diff < 3600) return `${Math.floor(diff / 60)}m atrás`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h atrás`;
    return `${Math.floor(diff / 86400)}d atrás`;
  }
  
  showPreview(item, previewText) {
    let preview = item.querySelector('.activity-preview');
    if (!preview) {
      preview = document.createElement('div');
      preview.className = 'activity-preview';
      preview.style.cssText = `
        position: absolute; right: 0; top: 0;
        background: var(--os-bg-3); border: 1px solid var(--os-border-2);
        border-radius: var(--os-radius-xs); padding: var(--os-space-2);
        font-size: 11px; color: var(--os-text-2);
        max-width: 200px; z-index: 10;
        opacity: 0; transform: translateX(10px);
        transition: all 0.2s var(--os-ease-out);
      `;
      preview.textContent = previewText;
      item.appendChild(preview);
    }
    
    // Animate in
    requestAnimationFrame(() => {
      preview.style.opacity = '1';
      preview.style.transform = 'translateX(0)';
    });
  }
  
  hidePreview(item) {
    const preview = item.querySelector('.activity-preview');
    if (preview) {
      preview.style.opacity = '0';
      preview.style.transform = 'translateX(10px)';
    }
  }
  
  showEmptyState() {
    const emptyState = document.createElement('div');
    emptyState.className = 'activity-empty-inline';
    emptyState.innerHTML = `
      <div style="text-align: center; padding: var(--os-space-6); color: var(--os-text-3);">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="margin-bottom: var(--os-space-2); opacity: 0.5;">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <p style="margin: 0; font-size: 13px;">Nenhuma atividade encontrada</p>
      </div>
    `;
    
    this.timeline.appendChild(emptyState);
  }
}

// ═══════════════════════════════════════════════════════════
// QUICK STATS COMPONENT
// ═══════════════════════════════════════════════════════════

class QuickStats {
  constructor() {
    this.container = document.querySelector('.quick-stats-v2');
    this.velocityChart = null;
  }
  
  render(statsData) {
    if (!statsData) return;
    
    this.renderVelocityChart(statsData.velocity);
    this.renderHeatmap(statsData.heatmap);
  }
  
  renderVelocityChart(velocityData) {
    const canvas = document.getElementById('velocityChart');
    if (!canvas || !velocityData) return;
    
    // Simple canvas-based chart (placeholder)
    const ctx = canvas.getContext('2d');
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = width * devicePixelRatio;
    canvas.height = height * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Draw simple line chart
    ctx.strokeStyle = 'var(--os-accent)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    
    const data = velocityData.chartData || [];
    const stepX = width / (data.length - 1);
    const maxValue = Math.max(...data.map(d => d.value));
    
    data.forEach((point, index) => {
      const x = index * stepX;
      const y = height - (point.value / maxValue) * height * 0.8 - height * 0.1;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
  }
  
  renderHeatmap(heatmapData) {
    const grid = document.querySelector('.heatmap-grid');
    if (!grid || !heatmapData) return;
    
    const cells = grid.querySelectorAll('.heatmap-cell');
    const weeklyData = heatmapData.weeklyData || [];
    
    cells.forEach((cell, index) => {
      if (weeklyData[index] !== undefined) {
        cell.dataset.count = weeklyData[index];
        cell.title = `${this.getDayName(index)}: ${weeklyData[index]} atividades`;
      }
    });
  }
  
  getDayName(index) {
    const days = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
    return days[index] || '';
  }
}

// ═══════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Check if we're on the dashboard v2 page
  if (document.body.classList.contains('dashboard-v2')) {
    window.dashboardV2 = new DashboardV2();
  }
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DashboardV2, KPICards, ActivityFeed, QuickStats, SparklineRenderer };
}
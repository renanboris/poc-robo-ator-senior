/**
 * NavigationHighlighter - Visual feedback for guided navigation
 * 
 * Provides step-by-step visual highlights during AURA's guided navigation mode.
 * Highlights elements with borders, shadows, and tooltips to guide users through
 * navigation sequences.
 * 
 * Features:
 * - Element highlighting with customizable styles
 * - Step tooltips with breadcrumb information
 * - Automatic cleanup between steps
 * - Fallback selector strategies
 */

class NavigationHighlighter {
    constructor() {
        this.currentHighlight = null;
        this.currentTooltip = null;
        
        // Highlight style configuration
        this.highlightStyle = {
            border: '3px solid #FFD700',
            boxShadow: '0 0 15px rgba(255, 215, 0, 0.8), 0 0 30px rgba(255, 215, 0, 0.4)',
            zIndex: '10000',
            position: 'relative',
            transition: 'all 0.3s ease'
        };
        
        // Tooltip style configuration
        this.tooltipStyle = {
            position: 'absolute',
            backgroundColor: '#2C3E50',
            color: '#ECF0F1',
            padding: '12px 16px',
            borderRadius: '8px',
            fontSize: '14px',
            fontFamily: 'system-ui, -apple-system, sans-serif',
            zIndex: '10001',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
            maxWidth: '300px',
            pointerEvents: 'none',
            animation: 'fadeIn 0.3s ease'
        };
        
        // Inject CSS animations
        this._injectStyles();
    }
    
    /**
     * Inject CSS animations and styles into the page
     * @private
     */
    _injectStyles() {
        if (document.getElementById('aura-navigation-styles')) {
            return; // Already injected
        }
        
        const style = document.createElement('style');
        style.id = 'aura-navigation-styles';
        style.textContent = `
            @keyframes fadeIn {
                from {
                    opacity: 0;
                    transform: translateY(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            @keyframes pulse {
                0%, 100% {
                    box-shadow: 0 0 15px rgba(255, 215, 0, 0.8), 0 0 30px rgba(255, 215, 0, 0.4);
                }
                50% {
                    box-shadow: 0 0 25px rgba(255, 215, 0, 1), 0 0 50px rgba(255, 215, 0, 0.6);
                }
            }
            
            .aura-navigation-highlight {
                animation: pulse 2s infinite;
            }
        `;
        document.head.appendChild(style);
    }
    
    /**
     * Highlight a navigation step element
     * @param {string} elementSelector - CSS selector or data-aura-map ID
     * @param {object} stepInfo - Step information for tooltip
     * @param {string} stepInfo.label - Element label
     * @param {string} stepInfo.breadcrumb - Full breadcrumb path
     * @param {number} stepInfo.stepNumber - Current step number
     * @param {number} stepInfo.totalSteps - Total number of steps
     * @returns {boolean} - Success status
     */
    highlightStep(elementSelector, stepInfo = {}) {
        try {
            // Clear any existing highlight
            this.clearHighlight();
            
            // Find the element using multiple strategies
            const element = this._findElement(elementSelector);
            
            if (!element) {
                console.warn(`[NavigationHighlighter] Element not found: ${elementSelector}`);
                return false;
            }
            
            // Store original styles
            const originalStyles = {
                border: element.style.border,
                boxShadow: element.style.boxShadow,
                zIndex: element.style.zIndex,
                position: element.style.position,
                transition: element.style.transition
            };
            
            // Apply highlight styles
            Object.assign(element.style, this.highlightStyle);
            element.classList.add('aura-navigation-highlight');
            
            // Store reference for cleanup
            this.currentHighlight = {
                element: element,
                originalStyles: originalStyles
            };
            
            // Show tooltip if step info provided
            if (stepInfo.label || stepInfo.breadcrumb) {
                this.showStepTooltip(element, stepInfo);
            }
            
            // Scroll element into view
            element.scrollIntoView({
                behavior: 'smooth',
                block: 'center',
                inline: 'center'
            });
            
            console.log(`[NavigationHighlighter] Highlighted: ${stepInfo.label || elementSelector}`);
            return true;
            
        } catch (error) {
            console.error('[NavigationHighlighter] Failed to highlight element:', error);
            return false;
        }
    }
    
    /**
     * Find element using multiple fallback strategies
     * @param {string} selector - CSS selector, data-aura-map ID, or element label
     * @returns {HTMLElement|null} - Found element or null
     * @private
     */
    _findElement(selector) {
        if (!selector) return null;
        
        // Strategy 1: Try as CSS selector
        try {
            const element = document.querySelector(selector);
            if (element) return element;
        } catch (e) {
            // Invalid CSS selector, try other strategies
        }
        
        // Strategy 2: Try as data-aura-map ID
        const byAuraId = document.querySelector(`[data-aura-map="${selector}"]`);
        if (byAuraId) return byAuraId;
        
        // Strategy 3: Try to find by ID attribute
        if (selector.startsWith('[id=') || selector.startsWith('#')) {
            const id = selector.replace(/[\[\]#'\"]/g, '').replace('id=', '');
            const byId = document.getElementById(id);
            if (byId) return byId;
        }
        
        // Strategy 4: Try to find by aria-label
        const byAriaLabel = document.querySelector(`[aria-label*="${selector}"]`);
        if (byAriaLabel) return byAriaLabel;
        
        // Strategy 5: Try to find by text content (case-insensitive)
        const allElements = document.querySelectorAll('button, a, [role="button"], [role="link"], [role="menuitem"]');
        for (const el of allElements) {
            if (el.textContent.trim().toLowerCase().includes(selector.toLowerCase())) {
                return el;
            }
        }
        
        return null;
    }
    
    /**
     * Show tooltip with step information
     * @param {HTMLElement} element - Element to attach tooltip to
     * @param {object} stepInfo - Step information
     * @private
     */
    showStepTooltip(element, stepInfo) {
        try {
            // Create tooltip element
            const tooltip = document.createElement('div');
            tooltip.className = 'aura-navigation-tooltip';
            
            // Build tooltip content
            let content = '';
            
            if (stepInfo.stepNumber && stepInfo.totalSteps) {
                content += `<div style="font-size: 12px; opacity: 0.8; margin-bottom: 4px;">
                    Passo ${stepInfo.stepNumber} de ${stepInfo.totalSteps}
                </div>`;
            }
            
            if (stepInfo.breadcrumb) {
                content += `<div style="font-weight: 600; margin-bottom: 4px;">
                    ${stepInfo.breadcrumb}
                </div>`;
            }
            
            if (stepInfo.label) {
                content += `<div style="font-size: 13px;">
                    Clique em: <strong>${stepInfo.label}</strong>
                </div>`;
            }
            
            tooltip.innerHTML = content;
            
            // Apply tooltip styles
            Object.assign(tooltip.style, this.tooltipStyle);
            
            // Position tooltip above element
            document.body.appendChild(tooltip);
            const rect = element.getBoundingClientRect();
            const tooltipRect = tooltip.getBoundingClientRect();
            
            // Calculate position (above element, centered)
            let top = rect.top - tooltipRect.height - 10;
            let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
            
            // Adjust if tooltip would be off-screen
            if (top < 10) {
                // Show below element instead
                top = rect.bottom + 10;
            }
            
            if (left < 10) {
                left = 10;
            } else if (left + tooltipRect.width > window.innerWidth - 10) {
                left = window.innerWidth - tooltipRect.width - 10;
            }
            
            tooltip.style.top = `${top + window.scrollY}px`;
            tooltip.style.left = `${left + window.scrollX}px`;
            
            // Store reference for cleanup
            this.currentTooltip = tooltip;
            
            // Auto-hide after 5 seconds
            setTimeout(() => {
                if (this.currentTooltip === tooltip) {
                    this._removeTooltip();
                }
            }, 5000);
            
        } catch (error) {
            console.error('[NavigationHighlighter] Failed to show tooltip:', error);
        }
    }
    
    /**
     * Remove current tooltip
     * @private
     */
    _removeTooltip() {
        if (this.currentTooltip && this.currentTooltip.parentNode) {
            this.currentTooltip.parentNode.removeChild(this.currentTooltip);
            this.currentTooltip = null;
        }
    }
    
    /**
     * Clear current highlight and tooltip
     */
    clearHighlight() {
        try {
            // Remove tooltip
            this._removeTooltip();
            
            // Restore original element styles
            if (this.currentHighlight) {
                const { element, originalStyles } = this.currentHighlight;
                
                if (element && element.parentNode) {
                    // Restore original styles
                    Object.assign(element.style, originalStyles);
                    element.classList.remove('aura-navigation-highlight');
                }
                
                this.currentHighlight = null;
            }
            
        } catch (error) {
            console.error('[NavigationHighlighter] Failed to clear highlight:', error);
        }
    }
    
    /**
     * Highlight multiple steps in sequence
     * @param {Array} steps - Array of step objects with selector and info
     * @param {number} delayMs - Delay between steps in milliseconds
     * @returns {Promise} - Resolves when all steps are highlighted
     */
    async highlightSequence(steps, delayMs = 2000) {
        for (let i = 0; i < steps.length; i++) {
            const step = steps[i];
            const stepInfo = {
                ...step.info,
                stepNumber: i + 1,
                totalSteps: steps.length
            };
            
            this.highlightStep(step.selector, stepInfo);
            
            // Wait before next step
            if (i < steps.length - 1) {
                await new Promise(resolve => setTimeout(resolve, delayMs));
            }
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NavigationHighlighter;
}

// Make available globally for extension context
if (typeof window !== 'undefined') {
    window.NavigationHighlighter = NavigationHighlighter;
}

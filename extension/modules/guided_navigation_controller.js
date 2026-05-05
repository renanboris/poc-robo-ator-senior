/**
 * GuidedNavigationController - Manages automatic step-by-step navigation
 * 
 * Coordinates between AURA's backend and the NavigationHighlighter to provide
 * seamless guided navigation through multi-step paths.
 * 
 * Features:
 * - Automatic step progression after user clicks
 * - DOM change detection and stabilization waiting
 * - Error handling and recovery
 * - Progress tracking
 */

class GuidedNavigationController {
    constructor() {
        this.navigationPath = null;
        this.currentStep = 0;
        this.isNavigating = false;
        this.highlighter = new NavigationHighlighter();
        this.clickListener = null;
        this.domObserver = null;
        
        // Configuration
        this.config = {
            domStabilizationDelay: 1000,  // Wait 1s for DOM to stabilize
            stepTimeout: 5000,  // 5s timeout per step
            autoAdvance: true  // Automatically advance after click
        };
    }
    
    /**
     * Start guided navigation with a navigation path
     * @param {Array} navigationPath - Array of navigation steps
     * @param {string} breadcrumb - Full breadcrumb path
     * @returns {Promise<boolean>} - Success status
     */
    async startNavigation(navigationPath, breadcrumb = "") {
        if (!navigationPath || navigationPath.length === 0) {
            console.error('[GuidedNav] No navigation path provided');
            return false;
        }
        
        console.log(`[GuidedNav] Starting navigation: ${breadcrumb}`);
        console.log(`[GuidedNav] Total steps: ${navigationPath.length}`);
        
        this.navigationPath = navigationPath;
        this.currentStep = 0;
        this.isNavigating = true;
        
        // Highlight first step
        await this.highlightCurrentStep();
        
        // Set up click listener for auto-advance
        if (this.config.autoAdvance) {
            this.setupClickListener();
        }
        
        return true;
    }
    
    /**
     * Highlight the current step
     * @returns {Promise<boolean>} - Success status
     */
    async highlightCurrentStep() {
        if (!this.navigationPath || this.currentStep >= this.navigationPath.length) {
            console.log('[GuidedNav] Navigation complete');
            this.stopNavigation();
            return false;
        }
        
        const step = this.navigationPath[this.currentStep];
        const element = step.element || {};
        
        // Build step info for tooltip
        const stepInfo = {
            label: element.label || `Passo ${this.currentStep + 1}`,
            breadcrumb: step.tooltip || "",
            stepNumber: this.currentStep + 1,
            totalSteps: this.navigationPath.length
        };
        
        // Get selector
        const selector = element.selector_hint || element.label;
        
        console.log(`[GuidedNav] Highlighting step ${this.currentStep + 1}/${this.navigationPath.length}: ${element.label}`);
        
        // Highlight the element
        const success = this.highlighter.highlightStep(selector, stepInfo);
        
        if (!success) {
            console.warn(`[GuidedNav] Failed to highlight step ${this.currentStep + 1}`);
        }
        
        return success;
    }
    
    /**
     * Set up click listener to detect when user clicks highlighted element
     */
    setupClickListener() {
        // Remove existing listener
        this.removeClickListener();
        
        // Add new listener
        this.clickListener = async (event) => {
            if (!this.isNavigating) return;
            
            // Check if clicked element is the highlighted one
            const highlightedElement = this.highlighter.currentHighlight?.element;
            
            if (!highlightedElement) return;
            
            // Check if click was on highlighted element or its children
            if (event.target === highlightedElement || highlightedElement.contains(event.target)) {
                console.log('[GuidedNav] User clicked highlighted element, advancing...');
                
                // Wait for DOM to stabilize after click
                await this.waitForDOMStabilization();
                
                // Advance to next step
                await this.advanceToNextStep();
            }
        };
        
        document.addEventListener('click', this.clickListener, true);
        console.log('[GuidedNav] Click listener activated');
    }
    
    /**
     * Remove click listener
     */
    removeClickListener() {
        if (this.clickListener) {
            document.removeEventListener('click', this.clickListener, true);
            this.clickListener = null;
            console.log('[GuidedNav] Click listener removed');
        }
    }
    
    /**
     * Wait for DOM to stabilize after interaction
     * @returns {Promise<void>}
     */
    async waitForDOMStabilization() {
        console.log(`[GuidedNav] Waiting ${this.config.domStabilizationDelay}ms for DOM stabilization...`);
        
        return new Promise((resolve) => {
            let changeCount = 0;
            let stabilizationTimer = null;
            
            // Set up mutation observer
            const observer = new MutationObserver(() => {
                changeCount++;
                
                // Reset timer on each change
                if (stabilizationTimer) {
                    clearTimeout(stabilizationTimer);
                }
                
                // Wait for changes to stop
                stabilizationTimer = setTimeout(() => {
                    observer.disconnect();
                    console.log(`[GuidedNav] DOM stabilized after ${changeCount} changes`);
                    resolve();
                }, this.config.domStabilizationDelay);
            });
            
            // Start observing
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true
            });
            
            // Fallback timeout
            setTimeout(() => {
                observer.disconnect();
                console.log('[GuidedNav] DOM stabilization timeout reached');
                resolve();
            }, this.config.stepTimeout);
        });
    }
    
    /**
     * Advance to the next step in navigation
     * @returns {Promise<boolean>} - Success status
     */
    async advanceToNextStep() {
        if (!this.isNavigating) {
            console.log('[GuidedNav] Navigation not active');
            return false;
        }
        
        // Increment step
        this.currentStep++;
        
        // Check if navigation is complete
        if (this.currentStep >= this.navigationPath.length) {
            console.log('[GuidedNav] ✅ Navigation completed successfully!');
            this.stopNavigation();
            this.showCompletionMessage();
            return true;
        }
        
        // Highlight next step
        await this.highlightCurrentStep();
        
        return true;
    }
    
    /**
     * Stop navigation and cleanup
     */
    stopNavigation() {
        console.log('[GuidedNav] Stopping navigation');
        
        this.isNavigating = false;
        this.removeClickListener();
        this.highlighter.clearHighlight();
        
        if (this.domObserver) {
            this.domObserver.disconnect();
            this.domObserver = null;
        }
    }
    
    /**
     * Show completion message
     */
    showCompletionMessage() {
        // Create completion notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            font-family: system-ui, -apple-system, sans-serif;
            font-size: 15px;
            font-weight: 600;
            z-index: 10002;
            animation: slideIn 0.3s ease, fadeOut 0.3s ease 2.7s;
        `;
        
        notification.innerHTML = `
            <div style="display: flex; align-items: center; gap: 12px;">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
                <span>Navegação concluída com sucesso!</span>
            </div>
        `;
        
        // Inject animation styles
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from {
                    transform: translateX(400px);
                    opacity: 0;
                }
                to {
                    transform: translateX(0);
                    opacity: 1;
                }
            }
            @keyframes fadeOut {
                to {
                    opacity: 0;
                    transform: translateX(400px);
                }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(notification);
        
        // Remove after animation
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
            if (style.parentNode) {
                style.parentNode.removeChild(style);
            }
        }, 3000);
    }
    
    /**
     * Get current navigation status
     * @returns {object} - Status object
     */
    getStatus() {
        return {
            isNavigating: this.isNavigating,
            currentStep: this.currentStep,
            totalSteps: this.navigationPath ? this.navigationPath.length : 0,
            progress: this.navigationPath ? (this.currentStep / this.navigationPath.length) * 100 : 0
        };
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = GuidedNavigationController;
}

// Make available globally for extension context
if (typeof window !== 'undefined') {
    window.GuidedNavigationController = GuidedNavigationController;
}


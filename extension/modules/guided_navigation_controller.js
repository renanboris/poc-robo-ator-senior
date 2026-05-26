/**
 * GuidedNavigationController - Manages automatic step-by-step navigation
 */

(function() {
    'use strict';
    
    console.log('[GuidedNavigationController] Loading...');
    
    // Constructor
    window.GuidedNavigationController = function() {
        this.navigationPath = null;
        this.currentStep = 0;
        this.isNavigating = false;
        this.highlighter = null;
        this.clickListener = null;
        
        this.config = {
            domStabilizationDelay: 1500,
            stepTimeout: 5000,
            autoAdvance: true
        };
        
        console.log('[GuidedNavigationController] Initialized');
    };
    
    // Get or create highlighter
    window.GuidedNavigationController.prototype._getHighlighter = function() {
        if (!this.highlighter) {
            if (typeof NavigationHighlighter === 'undefined') {
                console.error('[GuidedNav] NavigationHighlighter not available');
                return null;
            }
            this.highlighter = new NavigationHighlighter();
        }
        return this.highlighter;
    };
    
    // Start navigation
    window.GuidedNavigationController.prototype.startNavigation = function(navigationPath, breadcrumb) {
        if (!navigationPath || navigationPath.length === 0) {
            console.error('[GuidedNav] No navigation path provided');
            return Promise.resolve(false);
        }
        
        console.log('[GuidedNav] Starting navigation:', breadcrumb);
        console.log('[GuidedNav] Total steps:', navigationPath.length);
        
        this.navigationPath = navigationPath;
        this.currentStep = 0;
        this.isNavigating = true;
        
        // Highlight first step
        this.highlightCurrentStep();
        
        // Set up click listener
        if (this.config.autoAdvance) {
            this.setupClickListener();
        }
        
        return Promise.resolve(true);
    };
    
    // Highlight current step (with retry for SPA navigation)
    window.GuidedNavigationController.prototype.highlightCurrentStep = function() {
        if (!this.navigationPath || this.currentStep >= this.navigationPath.length) {
            console.log('[GuidedNav] Navigation complete');
            this.stopNavigation();
            this.showCompletionMessage();
            return false;
        }
        
        var step = this.navigationPath[this.currentStep];
        var element = step.element || {};
        
        var stepInfo = {
            label: element.label || 'Passo ' + (this.currentStep + 1),
            breadcrumb: step.tooltip || '',
            stepNumber: this.currentStep + 1,
            totalSteps: this.navigationPath.length
        };
        
        var selector = element.selector_hint || element.label;
        
        console.log('[GuidedNav] Highlighting step ' + (this.currentStep + 1) + '/' + this.navigationPath.length + ':', element.label);
        
        var highlighter = this._getHighlighter();
        if (!highlighter) {
            console.error('[GuidedNav] Highlighter not available');
            return false;
        }
        
        var success = highlighter.highlightStep(selector, stepInfo);
        
        if (!success) {
            // Element not found — SPA may still be loading. Start polling.
            console.log('[GuidedNav] Element not found yet, starting retry polling for:', selector);
            this._retryHighlight(selector, stepInfo, 0);
        }
        
        return success;
    };
    
    // Retry highlighting with polling (for SPA navigation delays)
    window.GuidedNavigationController.prototype._retryHighlight = function(selector, stepInfo, attempt) {
        var self = this;
        var maxAttempts = 10;
        var retryInterval = 500; // 500ms between retries (total: 5s max wait)
        
        if (!self.isNavigating) {
            console.log('[GuidedNav] Navigation stopped during retry');
            return;
        }
        
        if (attempt >= maxAttempts) {
            console.warn('[GuidedNav] Element not found after ' + maxAttempts + ' retries:', selector);
            // Show a helpful message instead of silently dying
            if (window.AuraUI && typeof window.AuraUI.exibirBalao === 'function') {
                window.AuraUI.exibirBalao(
                    'Não encontrei o elemento "' + stepInfo.label + '" na tela. A página pode ter mudado. Tente novamente.',
                    [],
                    false
                );
            }
            self.stopNavigation();
            return;
        }
        
        setTimeout(function() {
            if (!self.isNavigating) return;
            
            var highlighter = self._getHighlighter();
            if (!highlighter) return;
            
            var success = highlighter.highlightStep(selector, stepInfo);
            if (success) {
                console.log('[GuidedNav] Element found on retry ' + (attempt + 1) + ':', selector);
                // Re-setup click listener since element changed
                self.setupClickListener();
            } else {
                self._retryHighlight(selector, stepInfo, attempt + 1);
            }
        }, retryInterval);
    };
    
    // Setup click listener
    window.GuidedNavigationController.prototype.setupClickListener = function() {
        var self = this;
        
        this.removeClickListener();
        
        this.clickListener = function(event) {
            if (!self.isNavigating) return;
            
            var highlighter = self._getHighlighter();
            if (!highlighter) return;
            
            var highlightedElement = highlighter.currentHighlight ? highlighter.currentHighlight.element : null;
            if (!highlightedElement) return;
            
            if (event.target === highlightedElement || highlightedElement.contains(event.target)) {
                console.log('[GuidedNav] User clicked highlighted element, advancing...');
                
                setTimeout(function() {
                    self.advanceToNextStep();
                }, self.config.domStabilizationDelay);
            }
        };
        
        document.addEventListener('click', this.clickListener, true);
        console.log('[GuidedNav] Click listener activated');
    };
    
    // Remove click listener
    window.GuidedNavigationController.prototype.removeClickListener = function() {
        if (this.clickListener) {
            document.removeEventListener('click', this.clickListener, true);
            this.clickListener = null;
            console.log('[GuidedNav] Click listener removed');
        }
    };
    
    // Advance to next step
    window.GuidedNavigationController.prototype.advanceToNextStep = function() {
        if (!this.isNavigating) {
            console.log('[GuidedNav] Navigation not active');
            return false;
        }
        
        this.currentStep++;
        
        if (this.currentStep >= this.navigationPath.length) {
            console.log('[GuidedNav] Navigation completed successfully!');
            this.stopNavigation();
            this.showCompletionMessage();
            return true;
        }
        
        this.highlightCurrentStep();
        return true;
    };
    
    // Stop navigation
    window.GuidedNavigationController.prototype.stopNavigation = function() {
        console.log('[GuidedNav] Stopping navigation');
        
        this.isNavigating = false;
        this.removeClickListener();
        
        var highlighter = this._getHighlighter();
        if (highlighter) {
            highlighter.clearHighlight();
        }
    };
    
    // Show completion message
    window.GuidedNavigationController.prototype.showCompletionMessage = function() {
        var notification = document.createElement('div');
        notification.style.cssText = 'position: fixed; top: 20px; right: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px 24px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3); font-family: system-ui; font-size: 15px; font-weight: 600; z-index: 10002;';
        notification.innerHTML = '<div style="display: flex; align-items: center; gap: 12px;"><span>✓</span><span>Navegação concluída com sucesso!</span></div>';
        
        document.body.appendChild(notification);
        
        setTimeout(function() {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    };
    
    // Expose to window
    console.log('[GuidedNavigationController] Loaded successfully');
    console.log('[GuidedNavigationController] Available at window.GuidedNavigationController:', typeof window.GuidedNavigationController);
})();

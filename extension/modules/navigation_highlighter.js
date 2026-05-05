/**
 * NavigationHighlighter - Visual feedback for guided navigation
 */

(function() {
    'use strict';
    
    console.log('[NavigationHighlighter] Loading...');
    
    // Constructor
    window.NavigationHighlighter = function() {
        this.currentHighlight = null;
        this.currentTooltip = null;
        
        this.highlightStyle = {
            border: '3px solid #FFD700',
            boxShadow: '0 0 15px rgba(255, 215, 0, 0.8)',
            zIndex: '10000',
            position: 'relative',
            transition: 'all 0.3s ease'
        };
        
        this._injectStyles();
        console.log('[NavigationHighlighter] Initialized');
    };
    
    // Inject CSS styles
    window.NavigationHighlighter.prototype._injectStyles = function() {
        if (document.getElementById('aura-navigation-styles')) {
            return;
        }
        
        var style = document.createElement('style');
        style.id = 'aura-navigation-styles';
        style.textContent = '@keyframes pulse { 0%, 100% { box-shadow: 0 0 15px rgba(255, 215, 0, 0.8); } 50% { box-shadow: 0 0 25px rgba(255, 215, 0, 1); } } .aura-navigation-highlight { animation: pulse 2s infinite; }';
        document.head.appendChild(style);
    };
    
    // Find element with fallback strategies
    window.NavigationHighlighter.prototype._findElement = function(selector) {
        if (!selector) return null;
        
        // Try CSS selector
        try {
            var el = document.querySelector(selector);
            if (el) return el;
        } catch (e) {}
        
        // Try data-aura-map
        var byAuraId = document.querySelector('[data-aura-map="' + selector + '"]');
        if (byAuraId) return byAuraId;
        
        // Try by text content
        var buttons = document.querySelectorAll('button, a, [role="button"]');
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim().toLowerCase().indexOf(selector.toLowerCase()) !== -1) {
                return buttons[i];
            }
        }
        
        return null;
    };
    
    // Highlight a step
    window.NavigationHighlighter.prototype.highlightStep = function(selector, stepInfo) {
        try {
            this.clearHighlight();
            
            var element = this._findElement(selector);
            if (!element) {
                console.warn('[NavigationHighlighter] Element not found:', selector);
                return false;
            }
            
            var originalStyles = {
                border: element.style.border,
                boxShadow: element.style.boxShadow,
                zIndex: element.style.zIndex,
                position: element.style.position,
                transition: element.style.transition
            };
            
            // Apply highlight
            for (var key in this.highlightStyle) {
                element.style[key] = this.highlightStyle[key];
            }
            element.classList.add('aura-navigation-highlight');
            
            this.currentHighlight = {
                element: element,
                originalStyles: originalStyles
            };
            
            // Scroll into view
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            console.log('[NavigationHighlighter] Highlighted:', stepInfo.label || selector);
            return true;
            
        } catch (error) {
            console.error('[NavigationHighlighter] Error:', error);
            return false;
        }
    };
    
    // Clear highlight
    window.NavigationHighlighter.prototype.clearHighlight = function() {
        try {
            if (this.currentHighlight) {
                var el = this.currentHighlight.element;
                var orig = this.currentHighlight.originalStyles;
                
                if (el && el.parentNode) {
                    for (var key in orig) {
                        el.style[key] = orig[key];
                    }
                    el.classList.remove('aura-navigation-highlight');
                }
                
                this.currentHighlight = null;
            }
        } catch (error) {
            console.error('[NavigationHighlighter] Clear error:', error);
        }
    };
    
    console.log('[NavigationHighlighter] Loaded successfully');
})();

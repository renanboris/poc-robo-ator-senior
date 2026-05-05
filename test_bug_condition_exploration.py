"""
Bug Condition Exploration Test for DAP Like/Dislike Icons Fix

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
**DO NOT attempt to fix the test or the code when it fails**
**EXPECTED OUTCOME**: Test FAILS (this proves the bug exists)

This test validates Requirements 1.1, 1.2, 1.3 from bugfix.md:
- SVG icons have fill="currentColor" conflicting with CSS fill: none !important
- Icons render as unrecognizable shapes instead of proper thumbs up/down
- Visual bug prevents clear representation of like/dislike actions

**Validates: Requirements 1.1, 1.2, 1.3**
"""

import pytest
from hypothesis import given, strategies as st, settings
from playwright.sync_api import sync_playwright
import tempfile
import os


def create_test_html_with_aura_feedback():
    """Create a test HTML page that loads the aura_feedback.js module and CSS"""
    
    # Read the actual CSS and JS files
    with open('extension/style.css', 'r', encoding='utf-8') as f:
        css_content = f.read()
    
    with open('extension/modules/aura_feedback.js', 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Aura Feedback Bug Test</title>
        <style>
        {css_content}
        </style>
    </head>
    <body>
        <div id="test-container"></div>
        
        <script>
        {js_content}
        </script>
        
        <script>
        // Create feedback bar for testing
        function createTestFeedback() {{
            const container = document.getElementById('test-container');
            const feedbackBar = AuraFeedback.criar('test prompt', 'test response');
            container.appendChild(feedbackBar);
            return feedbackBar;
        }}
        
        // Expose for testing
        window.createTestFeedback = createTestFeedback;
        </script>
    </body>
    </html>
    """
    
    return html_content


def is_bug_condition(svg_element, computed_style):
    """
    Bug condition from design.md:
    SVG has fill="currentColor" but computed style is fill: none
    AND element is in a feedback button
    """
    has_fill_attr = svg_element.get_attribute('fill') == 'currentColor'
    computed_fill_none = computed_style.get('fill') == 'none'
    is_in_feedback_btn = '.aura-fb-btn' in svg_element.locator('xpath=ancestor::*[@class]').get_attribute('class') or ''
    
    return has_fill_attr and computed_fill_none and is_in_feedback_btn


class TestBugConditionExploration:
    """
    Property 1: Bug Condition - SVG Fill/Stroke Conflict Detection
    
    This test encodes the EXPECTED behavior (stroke-based rendering) but will FAIL
    on unfixed code because the current implementation has fill conflicts.
    """
    
    def test_svg_fill_attribute_conflicts_with_css(self):
        """
        Test that SVG icons have fill="currentColor" conflicting with CSS fill: none
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists
        """
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            # Create temporary HTML file
            html_content = create_test_html_with_aura_feedback()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_file = f.name
            
            try:
                # Load the test page
                page.goto(f'file://{temp_file}')
                
                # Create feedback bar
                page.evaluate('createTestFeedback()')
                
                # Get SVG elements from both like and dislike buttons
                like_svg = page.locator('.aura-fb-like svg').first
                dislike_svg = page.locator('.aura-fb-dislike svg').first
                
                # Wait for elements to be visible
                like_svg.wait_for(state='visible')
                dislike_svg.wait_for(state='visible')
                
                # Check like button SVG
                like_fill_attr = like_svg.get_attribute('fill')
                like_computed_style = page.evaluate('''
                    (svg) => {
                        const computedStyle = window.getComputedStyle(svg);
                        return {
                            fill: computedStyle.fill,
                            stroke: computedStyle.stroke
                        };
                    }
                ''', like_svg.element_handle())
                
                # Check dislike button SVG  
                dislike_fill_attr = dislike_svg.get_attribute('fill')
                dislike_computed_style = page.evaluate('''
                    (svg) => {
                        const computedStyle = window.getComputedStyle(svg);
                        return {
                            fill: computedStyle.fill,
                            stroke: computedStyle.stroke
                        };
                    }
                ''', dislike_svg.element_handle())
                
                # BUG CONDITION: SVG has fill="currentColor" but CSS enforces fill: none
                # This WILL FAIL on unfixed code, proving the bug exists
                
                # Expected behavior (will fail on unfixed code):
                # SVG should NOT have fill attribute conflicts
                assert like_fill_attr != 'currentColor', f"Like SVG has fill='currentColor' conflicting with CSS - Bug detected! fill='{like_fill_attr}', computed fill='{like_computed_style['fill']}'"
                assert dislike_fill_attr != 'currentColor', f"Dislike SVG has fill='currentColor' conflicting with CSS - Bug detected! fill='{dislike_fill_attr}', computed fill='{dislike_computed_style['fill']}'"
                
                # Expected behavior (will fail on unfixed code):
                # CSS should apply stroke-based rendering properly
                assert like_computed_style['fill'] != 'none' or like_computed_style['stroke'] != 'none', f"Like icon has both fill: none and stroke: none - renders as unrecognizable shape! Computed: {like_computed_style}"
                assert dislike_computed_style['fill'] != 'none' or dislike_computed_style['stroke'] != 'none', f"Dislike icon has both fill: none and stroke: none - renders as unrecognizable shape! Computed: {dislike_computed_style}"
                
            finally:
                browser.close()
                os.unlink(temp_file)
    
    @given(st.text(min_size=1, max_size=50))
    @settings(max_examples=10, deadline=30000)  # Reduced examples for faster execution
    def test_bug_condition_property_across_prompts(self, prompt_text):
        """
        Property-based test: For any prompt text, feedback buttons should render 
        recognizable icons without fill/stroke conflicts
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists across inputs
        """
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            html_content = create_test_html_with_aura_feedback()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_file = f.name
            
            try:
                page.goto(f'file://{temp_file}')
                
                # Create feedback with the generated prompt
                page.evaluate(f'createTestFeedback()')
                
                # Check both SVG icons
                svgs = page.locator('.aura-fb-btn svg').all()
                
                for i, svg in enumerate(svgs):
                    svg.wait_for(state='visible')
                    
                    fill_attr = svg.get_attribute('fill')
                    computed_style = page.evaluate('''
                        (svg) => {
                            const style = window.getComputedStyle(svg);
                            return {
                                fill: style.fill,
                                stroke: style.stroke,
                                strokeWidth: style.strokeWidth
                            };
                        }
                    ''', svg.element_handle())
                    
                    # Bug condition check - this WILL FAIL on unfixed code
                    button_type = "like" if i == 0 else "dislike"
                    
                    # Expected: No fill attribute conflicts (will fail on unfixed code)
                    if fill_attr == 'currentColor' and computed_style['fill'] == 'none':
                        pytest.fail(f"Bug detected in {button_type} button: SVG fill='currentColor' conflicts with CSS fill: none. "
                                   f"This causes unrecognizable icon rendering. Computed style: {computed_style}")
                    
                    # Expected: Icons should be visually renderable (will fail on unfixed code)
                    if computed_style['fill'] == 'none' and (computed_style['stroke'] == 'none' or not computed_style['stroke']):
                        pytest.fail(f"Bug detected in {button_type} button: Both fill and stroke are none, "
                                   f"causing icon to render as unrecognizable shape. Computed style: {computed_style}")
                        
            finally:
                browser.close()
                os.unlink(temp_file)
    
    def test_visual_icon_recognition_bug(self):
        """
        Test that current icons render as unrecognizable shapes instead of thumbs up/down
        
        **EXPECTED TO FAIL on unfixed code** - this documents the visual bug
        """
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            
            html_content = create_test_html_with_aura_feedback()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
                f.write(html_content)
                temp_file = f.name
            
            try:
                page.goto(f'file://{temp_file}')
                page.evaluate('createTestFeedback()')
                
                # Get the SVG paths to analyze their complexity
                like_path = page.locator('.aura-fb-like svg path').get_attribute('d')
                dislike_path = page.locator('.aura-fb-dislike svg path').get_attribute('d')
                
                # Check if these are complex filled paths (not stroke-optimized)
                # Complex filled paths become unrecognizable when only stroked
                like_is_complex_filled = 'c' in like_path.lower() and len(like_path) > 100  # Bezier curves + long path = filled icon
                dislike_is_complex_filled = 'c' in dislike_path.lower() and len(dislike_path) > 100
                
                # Get computed styles
                like_computed = page.evaluate('''
                    () => {
                        const svg = document.querySelector('.aura-fb-like svg');
                        const style = window.getComputedStyle(svg);
                        return {
                            fill: style.fill,
                            stroke: style.stroke,
                            strokeWidth: style.strokeWidth
                        };
                    }
                ''')
                
                dislike_computed = page.evaluate('''
                    () => {
                        const svg = document.querySelector('.aura-fb-dislike svg');
                        const style = window.getComputedStyle(svg);
                        return {
                            fill: style.fill,
                            stroke: style.stroke,
                            strokeWidth: style.strokeWidth
                        };
                    }
                ''')
                
                # Expected behavior: Icons should be stroke-optimized, not complex filled paths
                # This WILL FAIL on unfixed code because current icons are filled paths
                assert not (like_is_complex_filled and like_computed['fill'] == 'none'), \
                    f"Like icon uses complex filled path but CSS forces fill: none - renders as unrecognizable shape! " \
                    f"Path length: {len(like_path)}, Computed: {like_computed}"
                
                assert not (dislike_is_complex_filled and dislike_computed['fill'] == 'none'), \
                    f"Dislike icon uses complex filled path but CSS forces fill: none - renders as unrecognizable shape! " \
                    f"Path length: {len(dislike_path)}, Computed: {dislike_computed}"
                
            finally:
                browser.close()
                os.unlink(temp_file)


if __name__ == '__main__':
    # Run the tests to demonstrate the bug on unfixed code
    pytest.main([__file__, '-v', '--tb=short'])
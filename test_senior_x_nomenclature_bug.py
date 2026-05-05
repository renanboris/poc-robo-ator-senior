"""
Bug Condition Exploration Test for Senior X Nomenclature Fix

**CRITICAL**: This test MUST FAIL on unfixed code - failure confirms the bug exists
**DO NOT attempt to fix the test or the code when it fails**
**EXPECTED OUTCOME**: Test FAILS (this proves the bug exists)

This test validates Requirements 1.1, 1.2 from bugfix.md:
- Files contain "X Platform" when they should contain "X"
- Incorrect nomenclature appears in biblioteca_acoes.json and shadow_exports/*.jsonl

**Validates: Requirements 1.1, 1.2**
"""

import json
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


def is_bug_condition_json(file_path):
    """
    Bug condition from design.md:
    JSON file contains "X Platform" in string values
    
    FUNCTION isBugCondition(input)
      INPUT: input of type JSONFile
      OUTPUT: boolean
      
      RETURN input.fileExtension IN ['.json', '.jsonl']
             AND input.filePath IN ['biblioteca_acoes.json', 'shadow_exports/*.jsonl']
             AND input.content CONTAINS "X Platform"
    END FUNCTION
    """
    if file_path == 'biblioteca_acoes.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return "X Platform" in content
    return False


def is_bug_condition_jsonl(file_path):
    """Check if JSONL file contains "X Platform" in any line"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        return "X Platform" in content


def find_x_platform_instances_json(file_path):
    """Find all instances of "X Platform" in JSON file with context"""
    instances = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        for line_num, line in enumerate(lines, 1):
            if "X Platform" in line:
                instances.append({
                    'line_number': line_num,
                    'content': line.strip()[:200]  # First 200 chars for context
                })
    return instances


def find_x_platform_instances_jsonl(file_path):
    """Find all instances of "X Platform" in JSONL file with context"""
    instances = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            if "X Platform" in line:
                try:
                    data = json.loads(line)
                    # Extract relevant fields that might contain the bug
                    context = {}
                    if 'contexto_tela' in data:
                        context['contexto_tela'] = data['contexto_tela']
                    if 'tela_id' in data:
                        context['tela_id'] = data['tela_id']

                    instances.append({
                        'line_number': line_num,
                        'context': context,
                        'file': Path(file_path).name
                    })
                except json.JSONDecodeError:
                    instances.append({
                        'line_number': line_num,
                        'error': 'Invalid JSON',
                        'file': Path(file_path).name
                    })
    return instances


class TestBugConditionExploration:
    """
    Property 1: Bug Condition - X Platform Nomenclature Detection
    
    This test encodes the EXPECTED behavior (no "X Platform" should exist) but will FAIL
    on unfixed code because the current files contain "X Platform".
    
    **Validates: Requirements 1.1, 1.2**
    """

    def test_biblioteca_acoes_contains_x_platform(self):
        """
        Test that biblioteca_acoes.json contains "X Platform" in string values
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists
        
        From design.md examples:
        - Line 6299: "contexto_tela": "GED | X Platform" should be "GED | X"
        - Line 6332: "contexto_tela": "GED | X Platform" should be "GED | X"
        """
        file_path = 'biblioteca_acoes.json'

        # Check if file exists
        assert Path(file_path).exists(), f"Target file {file_path} not found"

        # Find all instances of "X Platform"
        instances = find_x_platform_instances_json(file_path)

        # Document the counterexamples
        if instances:
            print(f"\n{'='*80}")
            print(f"BUG DETECTED: Found {len(instances)} instances of 'X Platform' in {file_path}")
            print(f"{'='*80}")
            for i, instance in enumerate(instances[:10], 1):  # Show first 10
                print(f"\nCounterexample {i}:")
                print(f"  Line {instance['line_number']}: {instance['content']}")
            if len(instances) > 10:
                print(f"\n... and {len(instances) - 10} more instances")
            print(f"\n{'='*80}\n")

        # Expected behavior: No "X Platform" should exist (will fail on unfixed code)
        assert len(instances) == 0, (
            f"Bug condition detected: Found {len(instances)} instances of 'X Platform' in {file_path}. "
            f"Expected behavior: All instances should be 'X' instead of 'X Platform'. "
            f"This failure confirms the bug exists. "
            f"First instance at line {instances[0]['line_number']}: {instances[0]['content'][:100]}"
        )

    def test_shadow_exports_contain_x_platform(self):
        """
        Test that shadow_exports/*.jsonl files contain "X Platform" in string values
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists
        
        From design.md:
        - Multiple instances of "tela_id": "GED | X Platform" should be "tela_id": "GED | X"
        - Multiple instances of "contexto_tela": "GED | X Platform" should be "contexto_tela": "GED | X"
        """
        shadow_exports_dir = Path('shadow_exports')

        # Check if directory exists
        assert shadow_exports_dir.exists(), "shadow_exports directory not found"

        # Get all JSONL files
        jsonl_files = list(shadow_exports_dir.glob('*.jsonl'))
        assert len(jsonl_files) > 0, "No JSONL files found in shadow_exports directory"

        # Find all instances across all files
        all_instances = []
        files_with_bug = []

        for jsonl_file in jsonl_files:
            instances = find_x_platform_instances_jsonl(jsonl_file)
            if instances:
                files_with_bug.append(jsonl_file.name)
                all_instances.extend(instances)

        # Document the counterexamples
        if all_instances:
            print(f"\n{'='*80}")
            print(f"BUG DETECTED: Found {len(all_instances)} instances of 'X Platform' across {len(files_with_bug)} JSONL files")
            print(f"{'='*80}")
            print(f"Files affected: {', '.join(files_with_bug)}")
            print("\nSample counterexamples:")
            for i, instance in enumerate(all_instances[:10], 1):  # Show first 10
                print(f"\nCounterexample {i}:")
                print(f"  File: {instance['file']}, Line: {instance['line_number']}")
                if 'context' in instance:
                    print(f"  Context: {instance['context']}")
                elif 'error' in instance:
                    print(f"  Error: {instance['error']}")
            if len(all_instances) > 10:
                print(f"\n... and {len(all_instances) - 10} more instances")
            print(f"\n{'='*80}\n")

        # Expected behavior: No "X Platform" should exist (will fail on unfixed code)
        assert len(all_instances) == 0, (
            f"Bug condition detected: Found {len(all_instances)} instances of 'X Platform' "
            f"across {len(files_with_bug)} JSONL files in shadow_exports/. "
            f"Expected behavior: All instances should be 'X' instead of 'X Platform'. "
            f"This failure confirms the bug exists. "
            f"Files affected: {', '.join(files_with_bug[:5])}"
        )

    @given(st.sampled_from(['biblioteca_acoes.json']))
    @settings(max_examples=1)
    def test_bug_condition_property_json(self, file_path):
        """
        Property-based test: For the target JSON file, verify no "X Platform" exists
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists
        
        Property: For any file where isBugCondition(file) holds, 
        the content should NOT contain "X Platform"
        """
        # This is the bug condition check
        has_bug = is_bug_condition_json(file_path)

        if has_bug:
            instances = find_x_platform_instances_json(file_path)
            pytest.fail(
                f"Bug condition detected in {file_path}: "
                f"Found {len(instances)} instances of 'X Platform'. "
                f"Expected: All instances should be 'X' instead. "
                f"First instance at line {instances[0]['line_number']}"
            )

    @given(st.sampled_from(list(Path('shadow_exports').glob('*.jsonl'))))
    @settings(max_examples=5)
    def test_bug_condition_property_jsonl(self, file_path):
        """
        Property-based test: For any JSONL file in shadow_exports, verify no "X Platform" exists
        
        **EXPECTED TO FAIL on unfixed code** - this proves the bug exists
        
        Property: For any JSONL file where isBugCondition(file) holds,
        the content should NOT contain "X Platform"
        """
        has_bug = is_bug_condition_jsonl(file_path)

        if has_bug:
            instances = find_x_platform_instances_jsonl(file_path)
            pytest.fail(
                f"Bug condition detected in {file_path.name}: "
                f"Found {len(instances)} instances of 'X Platform'. "
                f"Expected: All instances should be 'X' instead. "
                f"First instance at line {instances[0]['line_number']}"
            )

    def test_json_validity_baseline(self):
        """
        Baseline test: Verify that all target files are valid JSON/JSONL before any changes
        
        This should PASS on unfixed code - it confirms files are structurally valid
        """
        # Test biblioteca_acoes.json
        with open('biblioteca_acoes.json', 'r', encoding='utf-8') as f:
            try:
                json.load(f)
                print("✓ biblioteca_acoes.json is valid JSON")
            except json.JSONDecodeError as e:
                pytest.fail(f"biblioteca_acoes.json is not valid JSON: {e}")

        # Test all JSONL files
        jsonl_files = list(Path('shadow_exports').glob('*.jsonl'))
        for jsonl_file in jsonl_files:
            with open(jsonl_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():  # Skip empty lines
                        try:
                            json.loads(line)
                        except json.JSONDecodeError as e:
                            pytest.fail(f"{jsonl_file.name} line {line_num} is not valid JSON: {e}")

        print(f"✓ All {len(jsonl_files)} JSONL files are valid")


if __name__ == '__main__':
    # Run the tests to demonstrate the bug on unfixed code
    pytest.main([__file__, '-v', '--tb=short'])

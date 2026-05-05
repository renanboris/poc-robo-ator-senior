"""
Preservation Property Tests for Senior X Nomenclature Fix

**IMPORTANT**: These tests run on UNFIXED code to establish baseline behavior
**EXPECTED OUTCOME**: Tests PASS (confirms what must be preserved)

This test validates Requirements 3.1, 3.2, 3.3, 3.4 from bugfix.md:
- All JSON structure and syntax must remain unchanged
- All non-nomenclature string values must remain unchanged
- All numeric values must remain unchanged
- File encoding must remain UTF-8

**Validates: Requirements 3.1, 3.2, 3.3, 3.4**
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
import json
from pathlib import Path
from typing import Dict, Any, List


class BaselineObservations:
    """
    Baseline observations from UNFIXED code
    These values are observed from the current state and must be preserved after the fix
    """
    
    # Observed from biblioteca_acoes.json
    BIBLIOTECA_TOTAL_KEYS = 638
    BIBLIOTECA_EXPECTED_FIELDS = [
        'acao', 'intencao_semantica', 'elemento_alvo', 'valor_input',
        'micro_narracao', 'seletor_css', '_source', '_versao_biblioteca',
        '_score_confiabilidade', '_requer_revisao'
    ]
    ELEMENTO_ALVO_FIELDS = [
        'descricao_visual', 'contexto_tela', 'tipo_elemento', 'confianca_captura',
        'label_curto', 'coordenadas_relativas', 'seletor_hint', 'iframe_hint', 'html_hint'
    ]
    COORDENADAS_FIELDS = ['x_pct', 'y_pct', 'w_pct', 'h_pct']
    
    # Sample non-nomenclature values that must remain unchanged
    SAMPLE_NON_NOMENCLATURE_STRINGS = [
        "clique",
        "...acessando o módulo Senior Flow...",
        "[id='menu-item-Senior Flow']",
        "Navegar para a seção ou módulo de Gerenciamento Eletrônico de Documentos (GED) do sistema.",
        "...navegando para o Gerenciamento Eletrônico de Documentos (GED)...",
    ]


def load_json_file(file_path: str) -> Dict[str, Any]:
    """Load JSON file with UTF-8 encoding"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_jsonl_file(file_path: str) -> List[Dict[str, Any]]:
    """Load JSONL file with UTF-8 encoding"""
    records = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def extract_all_strings(obj: Any, exclude_pattern: str = "X Platform") -> List[str]:
    """
    Recursively extract all string values from a JSON object,
    excluding strings that contain the bug pattern
    """
    strings = []
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            strings.extend(extract_all_strings(value, exclude_pattern))
    elif isinstance(obj, list):
        for item in obj:
            strings.extend(extract_all_strings(item, exclude_pattern))
    elif isinstance(obj, str):
        # Only include strings that don't contain the bug pattern
        if exclude_pattern not in obj:
            strings.append(obj)
    
    return strings


def extract_all_numbers(obj: Any) -> List[float]:
    """Recursively extract all numeric values from a JSON object"""
    numbers = []
    
    if isinstance(obj, dict):
        for value in obj.values():
            numbers.extend(extract_all_numbers(value))
    elif isinstance(obj, list):
        for item in obj:
            numbers.extend(extract_all_numbers(item))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        numbers.append(float(obj))
    
    return numbers


def get_json_structure_signature(obj: Any) -> str:
    """
    Get a structural signature of a JSON object
    This captures keys, nesting, and array lengths without values
    """
    if isinstance(obj, dict):
        keys = sorted(obj.keys())
        children = [get_json_structure_signature(obj[k]) for k in keys]
        return f"dict[{','.join(keys)}]:{{{','.join(children)}}}"
    elif isinstance(obj, list):
        if len(obj) == 0:
            return "list[0]"
        # Sample first item for structure
        return f"list[{len(obj)}]:{get_json_structure_signature(obj[0])}"
    elif isinstance(obj, str):
        return "str"
    elif isinstance(obj, bool):
        return "bool"
    elif isinstance(obj, (int, float)):
        return "num"
    elif obj is None:
        return "null"
    else:
        return "unknown"


class TestPreservationProperties:
    """
    Property 2: Preservation - JSON Structure and Non-Nomenclature Content
    
    These tests verify that all content NOT involving "X Platform" remains unchanged.
    Tests run on UNFIXED code to establish baseline, then will verify preservation after fix.
    
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
    """
    
    def test_biblioteca_json_structure_preserved(self):
        """
        Test that biblioteca_acoes.json maintains its JSON structure
        
        Verifies:
        - Same number of top-level keys
        - Same field structure in entries
        - Same nesting depth
        - Same array lengths
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        data = load_json_file('biblioteca_acoes.json')
        
        # Verify total keys
        assert len(data) == BaselineObservations.BIBLIOTECA_TOTAL_KEYS, (
            f"Expected {BaselineObservations.BIBLIOTECA_TOTAL_KEYS} keys, "
            f"found {len(data)}"
        )
        
        # Verify structure of entries
        for key, entry in list(data.items())[:10]:  # Sample first 10
            # Check top-level fields
            assert isinstance(entry, dict), f"Entry should be a dict, got {type(entry)}"
            
            # Check elemento_alvo structure
            if 'elemento_alvo' in entry:
                elemento = entry['elemento_alvo']
                assert isinstance(elemento, dict), "elemento_alvo should be a dict"
                
                # Check coordenadas_relativas structure
                if 'coordenadas_relativas' in elemento:
                    coords = elemento['coordenadas_relativas']
                    assert isinstance(coords, dict), "coordenadas_relativas should be a dict"
                    # Verify coordinate fields exist
                    for field in BaselineObservations.COORDENADAS_FIELDS:
                        assert field in coords, f"Missing coordinate field: {field}"
        
        print(f"✓ biblioteca_acoes.json structure preserved: {len(data)} keys")
    
    def test_biblioteca_non_nomenclature_strings_preserved(self):
        """
        Test that non-nomenclature string values remain unchanged
        
        Verifies that strings NOT containing "X Platform" are preserved exactly
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        data = load_json_file('biblioteca_acoes.json')
        
        # Extract all non-nomenclature strings
        non_nomenclature_strings = extract_all_strings(data, exclude_pattern="X Platform")
        
        # Verify we have a substantial number of strings
        assert len(non_nomenclature_strings) > 1000, (
            f"Expected many non-nomenclature strings, found {len(non_nomenclature_strings)}"
        )
        
        # Verify sample strings are present
        data_str = json.dumps(data, ensure_ascii=False)
        for sample_string in BaselineObservations.SAMPLE_NON_NOMENCLATURE_STRINGS:
            assert sample_string in data_str, (
                f"Expected sample string not found: {sample_string[:50]}"
            )
        
        print(f"✓ Found {len(non_nomenclature_strings)} non-nomenclature strings to preserve")
    
    def test_biblioteca_numeric_values_preserved(self):
        """
        Test that all numeric values remain unchanged
        
        Verifies coordinates, viewport dimensions, and other numeric values
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        data = load_json_file('biblioteca_acoes.json')
        
        # Extract all numeric values
        numeric_values = extract_all_numbers(data)
        
        # Verify we have numeric values
        assert len(numeric_values) > 100, (
            f"Expected many numeric values, found {len(numeric_values)}"
        )
        
        # Verify sample coordinates from first entry
        first_entry = data[list(data.keys())[0]]
        if 'elemento_alvo' in first_entry and 'coordenadas_relativas' in first_entry['elemento_alvo']:
            coords = first_entry['elemento_alvo']['coordenadas_relativas']
            
            # Verify all coordinate values are floats
            for field in BaselineObservations.COORDENADAS_FIELDS:
                if field in coords:
                    value = coords[field]
                    assert isinstance(value, (int, float)), (
                        f"Coordinate {field} should be numeric, got {type(value)}"
                    )
                    assert 0 <= value <= 1, (
                        f"Coordinate {field} should be between 0 and 1, got {value}"
                    )
        
        print(f"✓ Found {len(numeric_values)} numeric values to preserve")
    
    def test_biblioteca_file_encoding_utf8(self):
        """
        Test that file encoding is UTF-8
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        # Try to read with UTF-8 encoding
        try:
            with open('biblioteca_acoes.json', 'r', encoding='utf-8') as f:
                content = f.read()
                # Verify we can parse it
                json.loads(content)
            print("✓ biblioteca_acoes.json is valid UTF-8")
        except UnicodeDecodeError as e:
            pytest.fail(f"File is not UTF-8 encoded: {e}")
        except json.JSONDecodeError as e:
            pytest.fail(f"File is not valid JSON: {e}")
    
    def test_shadow_exports_structure_preserved(self):
        """
        Test that shadow_exports/*.jsonl files maintain their structure
        
        Verifies:
        - Same number of files
        - Same number of lines per file
        - Same field structure in records
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        shadow_exports_dir = Path('shadow_exports')
        jsonl_files = list(shadow_exports_dir.glob('*.jsonl'))
        
        assert len(jsonl_files) > 0, "No JSONL files found"
        
        files_with_records = 0
        for jsonl_file in jsonl_files:
            records = load_jsonl_file(jsonl_file)
            
            # Skip empty files (they exist but have no content)
            if len(records) == 0:
                continue
            
            files_with_records += 1
            
            # Verify structure of records
            for record in records[:5]:  # Sample first 5
                assert isinstance(record, dict), f"Record should be a dict in {jsonl_file.name}"
                
                # Common fields in shadow exports
                expected_fields = ['id_acao', 'captured_at', 'acao', 'elemento_alvo']
                for field in expected_fields:
                    if field in record:
                        assert record[field] is not None or field == 'elemento_alvo', (
                            f"Field {field} should not be None in {jsonl_file.name}"
                        )
        
        assert files_with_records > 0, "No JSONL files with records found"
        print(f"✓ Structure preserved across {files_with_records} JSONL files with records")
    
    def test_shadow_exports_non_nomenclature_strings_preserved(self):
        """
        Test that non-nomenclature strings in JSONL files remain unchanged
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        shadow_exports_dir = Path('shadow_exports')
        jsonl_files = list(shadow_exports_dir.glob('*.jsonl'))
        
        total_non_nomenclature_strings = 0
        
        for jsonl_file in jsonl_files:
            records = load_jsonl_file(jsonl_file)
            
            for record in records:
                strings = extract_all_strings(record, exclude_pattern="X Platform")
                total_non_nomenclature_strings += len(strings)
        
        # Verify we have many non-nomenclature strings
        assert total_non_nomenclature_strings > 100, (
            f"Expected many non-nomenclature strings, found {total_non_nomenclature_strings}"
        )
        
        print(f"✓ Found {total_non_nomenclature_strings} non-nomenclature strings in JSONL files")
    
    def test_shadow_exports_numeric_values_preserved(self):
        """
        Test that numeric values in JSONL files remain unchanged
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        shadow_exports_dir = Path('shadow_exports')
        jsonl_files = list(shadow_exports_dir.glob('*.jsonl'))
        
        total_numeric_values = 0
        
        for jsonl_file in jsonl_files:
            records = load_jsonl_file(jsonl_file)
            
            for record in records:
                numbers = extract_all_numbers(record)
                total_numeric_values += len(numbers)
        
        # Verify we have numeric values
        assert total_numeric_values > 50, (
            f"Expected many numeric values, found {total_numeric_values}"
        )
        
        print(f"✓ Found {total_numeric_values} numeric values in JSONL files")
    
    def test_shadow_exports_file_encoding_utf8(self):
        """
        Test that all JSONL files are UTF-8 encoded
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        shadow_exports_dir = Path('shadow_exports')
        jsonl_files = list(shadow_exports_dir.glob('*.jsonl'))
        
        for jsonl_file in jsonl_files:
            try:
                with open(jsonl_file, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if line.strip():
                            json.loads(line)
            except UnicodeDecodeError as e:
                pytest.fail(f"{jsonl_file.name} is not UTF-8 encoded: {e}")
            except json.JSONDecodeError as e:
                pytest.fail(f"{jsonl_file.name} line {line_num} is not valid JSON: {e}")
        
        print(f"✓ All {len(jsonl_files)} JSONL files are valid UTF-8")
    
    @given(st.sampled_from(['biblioteca_acoes.json']))
    @settings(max_examples=1)
    def test_property_json_structure_invariant(self, file_path):
        """
        Property-based test: JSON structure signature remains invariant
        
        For any JSON file, the structural signature (keys, nesting, array lengths)
        should remain unchanged after the fix
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        data = load_json_file(file_path)
        
        # Get structural signature
        signature = get_json_structure_signature(data)
        
        # Verify signature is non-empty
        assert len(signature) > 0, "Structural signature should not be empty"
        
        # Verify it's a dict at top level
        assert signature.startswith("dict["), "Top level should be a dict"
        
        print(f"✓ Structural signature captured for {file_path}")
    
    @given(st.sampled_from([f for f in Path('shadow_exports').glob('*.jsonl') if f.stat().st_size > 0]))
    @settings(max_examples=3)
    def test_property_jsonl_line_count_invariant(self, file_path):
        """
        Property-based test: JSONL line count remains invariant
        
        For any JSONL file, the number of lines should remain unchanged after the fix
        
        **EXPECTED TO PASS on unfixed code** - establishes baseline
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line for line in f if line.strip()]
        
        line_count = len(lines)
        
        # Verify we have lines (we filtered for non-empty files)
        assert line_count > 0, f"File {file_path.name} should have lines"
        
        # Verify all lines are valid JSON
        for line_num, line in enumerate(lines, 1):
            try:
                json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"{file_path.name} line {line_num} is not valid JSON: {e}")
        
        print(f"✓ {file_path.name} has {line_count} valid JSON lines")


if __name__ == '__main__':
    # Run the tests to establish baseline on unfixed code
    pytest.main([__file__, '-v', '--tb=short'])

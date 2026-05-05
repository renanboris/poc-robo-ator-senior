"""
Simple test suite for AURA Smart Navigation Fallback

Run with: pytest test_navigation_fallback.py -v
"""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_roteiro():
    """Create a sample roteiro for testing."""
    return {
        "metadata": {
            "id_treinamento": "TEST_ROTEIRO_001",
            "nome_aula": "Test Navigation Flow"
        },
        "passos": [
            {
                "id_passo": 1,
                "tipo_passo": "navigation",
                "pedagogia": {
                    "ancora": "Click on Senior Flow menu",
                    "tooltip_dap": "Senior Flow"
                },
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "label_curto": "Senior Flow",
                            "seletor_hint": "[id='menu-item-Senior Flow']",
                            "descricao_visual": "Menu item on left sidebar"
                        }
                    }
                ]
            },
            {
                "id_passo": 2,
                "tipo_passo": "navigation",
                "pedagogia": {
                    "ancora": "Click on SIGN submenu",
                    "tooltip_dap": "Senior Flow > SIGN"
                },
                "acoes_tecnicas": [
                    {
                        "acao": "clique",
                        "elemento_alvo": {
                            "label_curto": "SIGN",
                            "seletor_hint": "[aria-label='SIGN menu']",
                            "descricao_visual": "Submenu under Senior Flow"
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def temp_roteiros_dir(sample_roteiro):
    """Create a temporary directory with sample roteiros."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create sample roteiro file
        roteiro_path = Path(tmpdir) / "test_roteiro.json"
        with open(roteiro_path, 'w', encoding='utf-8') as f:
            json.dump(sample_roteiro, f, ensure_ascii=False, indent=2)

        yield tmpdir


def test_roteiro_indexer_initialization():
    """Test RoteiroIndexer initialization."""
    from navigation_fallback import RoteiroIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_index.db"
        indexer = RoteiroIndexer(roteiros_dir=tmpdir, index_db=str(db_path))

        assert indexer is not None
        assert indexer.cache is not None
        assert db_path.exists()


def test_navigation_path_extraction(sample_roteiro):
    """Test NavigationPathExtractor."""
    from navigation_fallback import NavigationPathExtractor

    extractor = NavigationPathExtractor()
    result = extractor.extract_navigation_path(sample_roteiro)

    assert result is not None
    assert "breadcrumb" in result
    assert "steps" in result
    assert "target_element" in result
    assert len(result["steps"]) == 2
    assert result["target_element"] == "SIGN"


def test_index_building(temp_roteiros_dir):
    """Test index building from roteiros."""
    from navigation_fallback import RoteiroIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_index.db"
        indexer = RoteiroIndexer(roteiros_dir=temp_roteiros_dir, index_db=str(db_path))

        result = indexer.build_index()

        assert result["status"] == "success"
        assert result["indexed_count"] >= 1
        assert result["failed_count"] == 0
        assert indexer.get_index_size() >= 1


def test_search_functionality(temp_roteiros_dir):
    """Test search functionality."""
    from navigation_fallback import RoteiroIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_index.db"
        indexer = RoteiroIndexer(roteiros_dir=temp_roteiros_dir, index_db=str(db_path))

        # Build index
        indexer.build_index()

        # Search for navigation path
        results = indexer.search("senior flow sign", tenant_id="test_tenant")

        assert len(results) > 0
        assert "roteiro_name" in results[0]
        assert "navigation_path" in results[0]
        assert "breadcrumb" in results[0]
        assert "confidence_score" in results[0]


def test_query_normalization():
    """Test query normalization."""
    from navigation_fallback import RoteiroIndexer

    indexer = RoteiroIndexer()

    # Test normalization
    query1 = indexer._normalize_query("Como faço para acessar o SIGN?")
    query2 = indexer._normalize_query("ACESSAR SIGN")

    # Both should normalize to similar form
    assert "sign" in query1.lower()
    assert "acessar" in query1.lower()
    assert "sign" in query2.lower()


def test_cache_functionality():
    """Test LRU cache."""
    from navigation_fallback import LRUCache

    cache = LRUCache(capacity=3)

    # Add items
    cache.put("key1", {"value": 1})
    cache.put("key2", {"value": 2})
    cache.put("key3", {"value": 3})

    # Check retrieval
    assert cache.get("key1") == {"value": 1}
    assert cache.get("key2") == {"value": 2}

    # Add fourth item (should evict key3 as it's least recently used)
    cache.put("key4", {"value": 4})

    assert cache.get("key3") is None
    assert cache.get("key4") == {"value": 4}
    assert cache.size() == 3


def test_confirmation_parsing():
    """Test user confirmation response parsing."""
    from navigation_fallback import parse_confirmation_response

    # Test affirmative responses
    assert parse_confirmation_response("sim") == True
    assert parse_confirmation_response("Sim, me guie") == True
    assert parse_confirmation_response("pode") == True
    assert parse_confirmation_response("quero") == True

    # Test negative responses
    assert parse_confirmation_response("não") == False
    assert parse_confirmation_response("agora não") == False
    assert parse_confirmation_response("depois") == False

    # Test ambiguous responses
    assert parse_confirmation_response("talvez") is None
    assert parse_confirmation_response("não sei") is None


def test_navigation_metrics():
    """Test navigation metrics tracking."""
    from navigation_fallback import NavigationMetrics

    metrics = NavigationMetrics()

    # Record some events
    metrics.record_fallback_activation()
    metrics.record_navigation_success(1500.0)
    metrics.record_navigation_success(1200.0)
    metrics.record_navigation_failure()
    metrics.record_cache_hit()
    metrics.record_cache_hit()
    metrics.record_cache_miss()

    # Get metrics
    result = metrics.get_metrics()

    assert result["fallback_activations"] == 1
    assert result["navigation_successes"] == 2
    assert result["navigation_failures"] == 1
    assert result["success_rate"] == 2/3
    assert result["average_navigation_time_ms"] == 1350.0
    assert result["cache_hit_rate"] == 2/3


@pytest.mark.asyncio
async def test_navigation_fallback_engine(temp_roteiros_dir):
    """Test NavigationFallbackEngine integration."""
    from navigation_fallback import NavigationFallbackEngine, RoteiroIndexer

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_index.db"
        indexer = RoteiroIndexer(roteiros_dir=temp_roteiros_dir, index_db=str(db_path))
        indexer.build_index()

        engine = NavigationFallbackEngine(indexer)

        # Test handle_invisible_element
        result = await engine.handle_invisible_element(
            user_query="como acessar sign",
            dom_context="<html></html>",
            tenant_id="test_tenant"
        )

        assert "mensagem" in result
        assert "fallback_type" in result
        assert result["fallback_type"] in ["navigation", "general"]


def test_element_visibility_check():
    """Test element visibility check."""
    from dap_engine import _check_element_visibility

    # Test with visible element
    dom_context = """
    <div id="menu-item-Senior Flow">Senior Flow</div>
    <div id="sign-menu">SIGN</div>
    """

    assert _check_element_visibility("Senior Flow", dom_context) == True
    assert _check_element_visibility("SIGN", dom_context) == True
    assert _check_element_visibility("NonExistent", dom_context) == False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

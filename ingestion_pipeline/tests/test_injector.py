"""Tests for the VectorInjector component."""

from unittest.mock import Mock, patch

from ingestion_pipeline.injector import VectorInjector


class TestVectorInjectorInit:
    """Test VectorInjector initialization."""

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_init(self, mock_pinecone):
        """Test VectorInjector initialization."""
        mock_pc = Mock()
        mock_index = Mock()
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector(
            api_key="test-api-key",
            index_name="test-index"
        )

        assert injector.api_key == "test-api-key"
        assert injector.index_name == "test-index"
        assert injector.index == mock_index
        mock_pinecone.assert_called_once_with(api_key="test-api-key")
        mock_pc.Index.assert_called_once_with("test-index")


class TestDeriveNamespace:
    """Test namespace derivation from nivel_2."""

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_derive_namespace_normal(self, mock_pinecone):
        """Test namespace derivation with normal nivel_2."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        namespace = injector._derive_namespace("hcm")
        assert namespace == "hcm"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_derive_namespace_with_spaces(self, mock_pinecone):
        """Test namespace derivation with spaces."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        namespace = injector._derive_namespace("human capital")
        assert namespace == "human_capital"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_derive_namespace_with_special_chars(self, mock_pinecone):
        """Test namespace derivation with special characters."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        namespace = injector._derive_namespace("hcm-módulo")
        assert namespace == "hcm_m_dulo"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_derive_namespace_empty(self, mock_pinecone):
        """Test namespace derivation with empty nivel_2."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        namespace = injector._derive_namespace("")
        assert namespace == "senior_default"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_derive_namespace_whitespace_only(self, mock_pinecone):
        """Test namespace derivation with whitespace-only nivel_2."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        namespace = injector._derive_namespace("   ")
        assert namespace == "senior_default"


class TestGenerateVectorId:
    """Test vector ID generation."""

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_generate_vector_id_normal(self, mock_pinecone):
        """Test vector ID generation with normal inputs."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vector_id = injector._generate_vector_id(
            nivel_2="hcm",
            titulo="Admissão de Colaborador",
            chunk_index=0
        )

        # Note: sanitize_filename removes accented characters
        assert vector_id == "hcm_admiss_o_de_colaborador_0"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_generate_vector_id_with_special_chars(self, mock_pinecone):
        """Test vector ID generation with special characters."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vector_id = injector._generate_vector_id(
            nivel_2="hcm",
            titulo="Admissão & Demissão",
            chunk_index=5
        )

        # Note: sanitize_filename removes accented characters and special chars
        assert vector_id == "hcm_admiss_o_demiss_o_5"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_generate_vector_id_empty_nivel_2(self, mock_pinecone):
        """Test vector ID generation with empty nivel_2."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vector_id = injector._generate_vector_id(
            nivel_2="",
            titulo="Test Title",
            chunk_index=0
        )

        assert vector_id == "default_test_title_0"

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_generate_vector_id_empty_titulo(self, mock_pinecone):
        """Test vector ID generation with empty titulo."""
        mock_pc = Mock()
        mock_pc.Index.return_value = Mock()
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vector_id = injector._generate_vector_id(
            nivel_2="hcm",
            titulo="",
            chunk_index=0
        )

        assert vector_id == "hcm_untitled_0"


class TestInjectVector:
    """Test single vector injection."""

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_inject_vector_success(self, mock_pinecone):
        """Test successful vector injection."""
        mock_pc = Mock()
        mock_index = Mock()
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        embedding = [0.1] * 3072
        metadata = {
            "url": "https://example.com/test",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "titulo": "Test Page",
            "text": "Test content"
        }

        result = injector.inject_vector(
            embedding=embedding,
            metadata=metadata,
            chunk_index=0
        )

        assert result is True
        mock_index.upsert.assert_called_once()

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_inject_vector_failure(self, mock_pinecone):
        """Test vector injection failure."""
        mock_pc = Mock()
        mock_index = Mock()
        mock_index.upsert.side_effect = Exception("Upsert failed")
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        embedding = [0.1] * 3072
        metadata = {
            "url": "https://example.com/test",
            "nivel_1": "senior-x",
            "nivel_2": "hcm",
            "titulo": "Test Page",
            "text": "Test content"
        }

        result = injector.inject_vector(
            embedding=embedding,
            metadata=metadata,
            chunk_index=0
        )

        assert result is False


class TestInjectBatch:
    """Test batch vector injection."""

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_inject_batch_success(self, mock_pinecone):
        """Test successful batch injection."""
        mock_pc = Mock()
        mock_index = Mock()
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vectors = [
            {
                "embedding": [0.1] * 3072,
                "metadata": {
                    "url": f"https://example.com/test{i}",
                    "nivel_1": "senior-x",
                    "nivel_2": "hcm",
                    "titulo": f"Test Page {i}",
                    "text": f"Test content {i}"
                },
                "chunk_index": i
            }
            for i in range(5)
        ]

        result = injector.inject_batch(vectors, batch_size=100)

        assert result["success"] == 5
        assert result["failed"] == 0
        mock_index.upsert.assert_called_once()

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_inject_batch_multiple_namespaces(self, mock_pinecone):
        """Test batch injection with multiple namespaces."""
        mock_pc = Mock()
        mock_index = Mock()
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vectors = [
            {
                "embedding": [0.1] * 3072,
                "metadata": {
                    "url": "https://example.com/test1",
                    "nivel_1": "senior-x",
                    "nivel_2": "hcm",
                    "titulo": "Test Page 1",
                    "text": "Test content 1"
                },
                "chunk_index": 0
            },
            {
                "embedding": [0.2] * 3072,
                "metadata": {
                    "url": "https://example.com/test2",
                    "nivel_1": "senior-x",
                    "nivel_2": "financeiro",
                    "titulo": "Test Page 2",
                    "text": "Test content 2"
                },
                "chunk_index": 0
            }
        ]

        result = injector.inject_batch(vectors, batch_size=100)

        assert result["success"] == 2
        assert result["failed"] == 0
        # Should be called twice (once per namespace)
        assert mock_index.upsert.call_count == 2

    @patch('ingestion_pipeline.injector.Pinecone')
    def test_inject_batch_with_failures(self, mock_pinecone):
        """Test batch injection with some failures."""
        mock_pc = Mock()
        mock_index = Mock()
        # First call succeeds, second fails
        mock_index.upsert.side_effect = [None, Exception("Upsert failed")]
        mock_pc.Index.return_value = mock_index
        mock_pinecone.return_value = mock_pc

        injector = VectorInjector("test-key", "test-index")

        vectors = [
            {
                "embedding": [0.1] * 3072,
                "metadata": {
                    "url": "https://example.com/test1",
                    "nivel_1": "senior-x",
                    "nivel_2": "hcm",
                    "titulo": "Test Page 1",
                    "text": "Test content 1"
                },
                "chunk_index": 0
            },
            {
                "embedding": [0.2] * 3072,
                "metadata": {
                    "url": "https://example.com/test2",
                    "nivel_1": "senior-x",
                    "nivel_2": "financeiro",
                    "titulo": "Test Page 2",
                    "text": "Test content 2"
                },
                "chunk_index": 0
            }
        ]

        result = injector.inject_batch(vectors, batch_size=100)

        assert result["success"] == 1
        assert result["failed"] == 1

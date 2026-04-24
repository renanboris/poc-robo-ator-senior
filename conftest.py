# conftest.py
import pytest


def pytest_configure(config):
    """Registra markers customizados do projeto."""
    config.addinivalue_line(
        "markers",
        "integration: marca testes que dependem de serviços externos "
        "(Gemini, OpenAI, Playwright, Pinecone). "
        "Excluídos da execução no CI com: pytest -m 'not integration'",
    )

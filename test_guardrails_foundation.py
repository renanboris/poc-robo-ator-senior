"""
Unit tests for guardrails module foundation (Task 1).

Tests the GuardrailResult dataclass and GuardrailConfig class.
"""

import os

import pytest

from guardrails import GuardrailConfig, GuardrailResult


class TestGuardrailResult:
    """Test GuardrailResult dataclass."""

    def test_guardrail_result_creation_minimal(self):
        """Test creating GuardrailResult with minimal required fields."""
        result = GuardrailResult(
            passed=True,
            guardrail_name="test_guardrail",
            severity="low"
        )

        assert result.passed is True
        assert result.guardrail_name == "test_guardrail"
        assert result.severity == "low"
        assert result.message is None
        assert result.details is None

    def test_guardrail_result_creation_full(self):
        """Test creating GuardrailResult with all fields."""
        result = GuardrailResult(
            passed=False,
            guardrail_name="sql_injection",
            severity="critical",
            message="SQL injection detected",
            details={"pattern": "SELECT.*FROM", "location": "prompt"}
        )

        assert result.passed is False
        assert result.guardrail_name == "sql_injection"
        assert result.severity == "critical"
        assert result.message == "SQL injection detected"
        assert result.details == {"pattern": "SELECT.*FROM", "location": "prompt"}

    def test_guardrail_result_severity_levels(self):
        """Test all severity levels are supported."""
        severities = ["low", "medium", "high", "critical"]

        for severity in severities:
            result = GuardrailResult(
                passed=False,
                guardrail_name="test",
                severity=severity
            )
            assert result.severity == severity


class TestGuardrailConfig:
    """Test GuardrailConfig class."""

    def test_guardrail_config_creation(self):
        """Test creating GuardrailConfig with explicit values."""
        config = GuardrailConfig(
            enable_sql_injection=True,
            enable_prompt_injection=False,
            enable_offensive_content=True,
            enable_competitor_filter=False,
            enable_vector_store_only=True
        )

        assert config.enable_sql_injection is True
        assert config.enable_prompt_injection is False
        assert config.enable_offensive_content is True
        assert config.enable_competitor_filter is False
        assert config.enable_vector_store_only is True

    def test_guardrail_config_from_env_defaults(self):
        """Test loading config from environment with default values."""
        # Clear any existing environment variables
        env_vars = [
            "ENABLE_SQL_INJECTION_CHECK",
            "ENABLE_PROMPT_INJECTION_CHECK",
            "ENABLE_OFFENSIVE_CONTENT_FILTER",
            "ENABLE_COMPETITOR_FILTER",
            "ENABLE_VECTOR_STORE_ONLY"
        ]
        for var in env_vars:
            if var in os.environ:
                del os.environ[var]

        config = GuardrailConfig.from_env()

        # All should default to True
        assert config.enable_sql_injection is True
        assert config.enable_prompt_injection is True
        assert config.enable_offensive_content is True
        assert config.enable_competitor_filter is True
        assert config.enable_vector_store_only is True

    def test_guardrail_config_from_env_custom(self):
        """Test loading config from environment with custom values."""
        # Set custom environment variables
        os.environ["ENABLE_SQL_INJECTION_CHECK"] = "false"
        os.environ["ENABLE_PROMPT_INJECTION_CHECK"] = "true"
        os.environ["ENABLE_OFFENSIVE_CONTENT_FILTER"] = "FALSE"
        os.environ["ENABLE_COMPETITOR_FILTER"] = "True"
        os.environ["ENABLE_VECTOR_STORE_ONLY"] = "false"

        config = GuardrailConfig.from_env()

        assert config.enable_sql_injection is False
        assert config.enable_prompt_injection is True
        assert config.enable_offensive_content is False
        assert config.enable_competitor_filter is True
        assert config.enable_vector_store_only is False

        # Cleanup
        for var in ["ENABLE_SQL_INJECTION_CHECK", "ENABLE_PROMPT_INJECTION_CHECK",
                    "ENABLE_OFFENSIVE_CONTENT_FILTER", "ENABLE_COMPETITOR_FILTER",
                    "ENABLE_VECTOR_STORE_ONLY"]:
            if var in os.environ:
                del os.environ[var]

    def test_guardrail_config_from_env_case_insensitive(self):
        """Test that environment variable values are case-insensitive."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("yes", False),  # Only "true" should enable
            ("1", False),    # Only "true" should enable
        ]

        for env_value, expected in test_cases:
            os.environ["ENABLE_SQL_INJECTION_CHECK"] = env_value
            config = GuardrailConfig.from_env()
            assert config.enable_sql_injection is expected, \
                f"Expected {expected} for env value '{env_value}'"

        # Cleanup
        if "ENABLE_SQL_INJECTION_CHECK" in os.environ:
            del os.environ["ENABLE_SQL_INJECTION_CHECK"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

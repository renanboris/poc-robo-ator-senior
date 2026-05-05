"""Unit tests for utils module."""

import json
import logging
import time
from unittest.mock import Mock, patch

import pytest

from ingestion_pipeline.utils import (
    JSONFormatter,
    log_chunk_processing,
    log_error,
    log_stage_complete,
    log_stage_start,
    log_url_processing,
    log_with_context,
    retry_with_backoff,
    sanitize_filename,
    setup_logging,
)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_success_on_first_attempt(self):
        """Should return result on first successful attempt."""
        mock_func = Mock(return_value="success")
        result = retry_with_backoff(mock_func)

        assert result == "success"
        assert mock_func.call_count == 1

    def test_success_after_retries(self):
        """Should retry and eventually succeed."""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])
        result = retry_with_backoff(mock_func, max_retries=3, delays=[0.01, 0.01, 0.01])

        assert result == "success"
        assert mock_func.call_count == 3

    def test_failure_after_max_retries(self):
        """Should raise exception after max retries exhausted."""
        mock_func = Mock(side_effect=Exception("persistent failure"))

        with pytest.raises(Exception, match="persistent failure"):
            retry_with_backoff(mock_func, max_retries=3, delays=[0.01, 0.01, 0.01])

        assert mock_func.call_count == 3

    def test_custom_delays(self):
        """Should use custom delay values."""
        mock_func = Mock(side_effect=[Exception("fail"), "success"])

        start_time = time.time()
        result = retry_with_backoff(mock_func, max_retries=2, delays=[0.1])
        duration = time.time() - start_time

        assert result == "success"
        assert duration >= 0.1  # Should have waited at least 0.1 seconds

    def test_specific_exception_types(self):
        """Should only catch specified exception types."""
        mock_func = Mock(side_effect=ValueError("wrong type"))

        # Should not catch ValueError when only RuntimeError is specified
        with pytest.raises(ValueError):
            retry_with_backoff(mock_func, exceptions=(RuntimeError,))

    def test_default_delays(self):
        """Should use default delays [1, 2, 4] when not specified."""
        mock_func = Mock(side_effect=[Exception("fail"), Exception("fail"), "success"])

        with patch('time.sleep') as mock_sleep:
            result = retry_with_backoff(mock_func)

            assert result == "success"
            # Should have called sleep with 1 and 2 seconds
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(1)
            mock_sleep.assert_any_call(2)


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_basic_sanitization(self):
        """Should convert to lowercase and replace special chars."""
        assert sanitize_filename("Hello World!") == "hello_world"

    def test_multiple_special_chars(self):
        """Should collapse multiple special chars into single underscore."""
        assert sanitize_filename("test---file___name") == "test_file_name"

    def test_leading_trailing_underscores(self):
        """Should remove leading and trailing underscores."""
        assert sanitize_filename("__test__") == "test"

    def test_unicode_characters(self):
        """Should handle unicode characters."""
        assert sanitize_filename("café-résumé") == "caf_r_sum"

    def test_numbers_preserved(self):
        """Should preserve numbers."""
        assert sanitize_filename("test123file") == "test123file"

    def test_empty_string(self):
        """Should handle empty string."""
        assert sanitize_filename("") == ""


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_basic_formatting(self):
        """Should format basic log record as JSON."""
        formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        data = json.loads(result)

        assert data["level"] == "INFO"
        assert data["logger"] == "test_logger"
        assert data["message"] == "Test message"
        assert "timestamp" in data

    def test_context_fields(self):
        """Should include context fields when present."""
        formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None
        )
        record.stage = "extraction"
        record.url = "https://example.com"
        record.chunk_index = 5

        result = formatter.format(record)
        data = json.loads(result)

        assert data["stage"] == "extraction"
        assert data["url"] == "https://example.com"
        assert data["chunk_index"] == 5


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_creates_log_directory(self, tmp_path):
        """Should create log directory if it doesn't exist."""
        log_dir = tmp_path / "test_logs"
        setup_logging(log_dir=str(log_dir))

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_creates_log_file(self, tmp_path):
        """Should create log file."""
        log_dir = tmp_path / "test_logs"
        log_file = "test.log"
        setup_logging(log_dir=str(log_dir), log_file=log_file)

        log_path = log_dir / log_file
        assert log_path.exists()

    def test_json_format(self, tmp_path):
        """Should write JSON-formatted logs when json_format=True."""
        log_dir = tmp_path / "test_logs"
        log_file = "test.log"
        setup_logging(log_dir=str(log_dir), log_file=log_file, json_format=True)

        # Write a test log
        logger = logging.getLogger("test")
        logger.info("Test message")

        # Read log file and verify JSON format
        log_path = log_dir / log_file
        with open(log_path, 'r') as f:
            log_line = f.readline()
            data = json.loads(log_line)
            assert data["message"] == "Test message"
            assert data["level"] == "INFO"


class TestLogHelpers:
    """Tests for logging helper functions."""

    def test_log_with_context(self, caplog):
        """Should log with context fields."""
        with caplog.at_level(logging.INFO):
            log_with_context(
                "info",
                "Test message",
                stage="extraction",
                url="https://example.com",
                chunk_index=5
            )

        assert "Test message" in caplog.text

    def test_log_stage_start(self, caplog):
        """Should log stage start."""
        with caplog.at_level(logging.INFO):
            log_stage_start("extraction")

        assert "Starting stage: extraction" in caplog.text

    def test_log_stage_complete(self, caplog):
        """Should log stage completion with metrics."""
        with caplog.at_level(logging.INFO):
            log_stage_complete("extraction", count=10, duration=5.5)

        assert "Completed stage: extraction" in caplog.text
        assert "10 items" in caplog.text
        assert "5.50s" in caplog.text

    def test_log_url_processing(self, caplog):
        """Should log URL processing status."""
        with caplog.at_level(logging.INFO):
            log_url_processing("https://example.com", "extraction", "success")

        assert "https://example.com" in caplog.text
        assert "success" in caplog.text

    def test_log_chunk_processing(self, caplog):
        """Should log chunk processing status."""
        with caplog.at_level(logging.INFO):
            log_chunk_processing("https://example.com", 5, "embedding", "processing")

        assert "Chunk 5" in caplog.text
        assert "processing" in caplog.text

    def test_log_error(self, caplog):
        """Should log error with full context."""
        error = ValueError("Test error")

        with caplog.at_level(logging.ERROR):
            log_error(
                "Processing failed",
                stage="extraction",
                error=error,
                url="https://example.com",
                chunk_index=5
            )

        assert "Processing failed" in caplog.text

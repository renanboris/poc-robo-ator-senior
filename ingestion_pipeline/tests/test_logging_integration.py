"""Integration test for logging functionality."""

import json
import logging

from ingestion_pipeline.utils import (
    log_chunk_processing,
    log_error,
    log_stage_complete,
    log_stage_start,
    log_url_processing,
    setup_logging,
)


def test_logging_integration(tmp_path):
    """Test complete logging workflow with JSON format and rotation."""
    # Setup logging with larger file size to avoid premature rotation
    log_dir = tmp_path / "logs"
    log_file = "test_pipeline.log"

    setup_logging(
        level="INFO",
        log_dir=str(log_dir),
        log_file=log_file,
        json_format=True,
        max_bytes=10240,  # 10KB for testing
        backup_count=3
    )

    # Simulate pipeline execution with logging
    log_stage_start("discovery")
    log_url_processing("https://example.com/page1", "discovery", "processing")
    log_url_processing("https://example.com/page1", "discovery", "success")
    log_stage_complete("discovery", count=1, duration=2.5)

    log_stage_start("extraction")
    log_url_processing("https://example.com/page1", "extraction", "processing")
    log_chunk_processing("https://example.com/page1", 0, "chunking", "success")
    log_chunk_processing("https://example.com/page1", 1, "chunking", "success")
    log_stage_complete("extraction", count=2, duration=5.3)

    # Test error logging
    try:
        raise ValueError("Test error")
    except ValueError as e:
        log_error(
            "Failed to process chunk",
            stage="embedding",
            error=e,
            url="https://example.com/page1",
            chunk_index=1
        )

    # Flush all handlers to ensure logs are written
    for handler in logging.getLogger().handlers:
        handler.flush()

    # Verify log file exists
    log_path = log_dir / log_file
    assert log_path.exists()

    # Verify log content is valid JSON
    with open(log_path, 'r') as f:
        lines = f.readlines()
        assert len(lines) > 0

        # Parse first line as JSON
        first_log = json.loads(lines[0])
        assert "timestamp" in first_log
        assert "level" in first_log
        assert "message" in first_log

        # Parse all logs
        all_logs = [json.loads(line) for line in lines]

        # Verify stage context is present
        stage_logs = [log for log in all_logs if "stage" in log]
        assert len(stage_logs) > 0
        assert any(log["stage"] == "discovery" for log in stage_logs)
        assert any(log["stage"] == "extraction" for log in stage_logs)

        # Verify URL context is present
        url_logs = [log for log in all_logs if "url" in log]
        assert len(url_logs) > 0
        assert any("example.com" in log["url"] for log in url_logs)

        # Verify error log
        error_logs = [log for log in all_logs if log["level"] == "ERROR"]
        assert len(error_logs) > 0
        error_log = error_logs[0]
        assert "context" in error_log
        assert error_log["context"]["error_type"] == "ValueError"


def test_log_rotation(tmp_path):
    """Test that log rotation works correctly."""
    log_dir = tmp_path / "logs"
    log_file = "rotation_test.log"

    # Setup with very small max_bytes to trigger rotation
    setup_logging(
        level="INFO",
        log_dir=str(log_dir),
        log_file=log_file,
        json_format=True,
        max_bytes=500,  # 500 bytes
        backup_count=2
    )

    logger = logging.getLogger("test")

    # Write many log entries to trigger rotation
    for i in range(50):
        logger.info(f"Test log entry number {i} with some additional text to increase size")

    # Check that rotation occurred
    log_path = log_dir / log_file
    assert log_path.exists()

    # Check for backup files
    backup_files = list(log_dir.glob(f"{log_file}.*"))
    # Should have at least one backup file
    assert len(backup_files) > 0
    # Should not exceed backup_count
    assert len(backup_files) <= 2

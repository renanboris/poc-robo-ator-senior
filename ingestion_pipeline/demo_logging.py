"""Demonstration of structured logging functionality."""

from ingestion_pipeline.utils import (
    setup_logging,
    log_stage_start,
    log_stage_complete,
    log_url_processing,
    log_chunk_processing,
    log_error,
    retry_with_backoff
)


def main():
    """Demonstrate logging features."""
    # Setup structured logging with JSON format and rotation
    setup_logging(
        level="INFO",
        log_dir="logs",
        log_file="demo_pipeline.log",
        json_format=True,
        max_bytes=10 * 1024 * 1024,  # 10MB
        backup_count=5
    )
    
    print("Demonstrating structured logging...")
    print("Logs are being written to: logs/demo_pipeline.log")
    print()
    
    # Simulate pipeline stages
    log_stage_start("discovery")
    log_url_processing("https://example.com/docs/page1", "discovery", "processing")
    log_url_processing("https://example.com/docs/page1", "discovery", "success")
    log_url_processing("https://example.com/docs/page2", "discovery", "processing")
    log_url_processing("https://example.com/docs/page2", "discovery", "success")
    log_stage_complete("discovery", count=2, duration=3.5)
    
    log_stage_start("extraction")
    log_url_processing("https://example.com/docs/page1", "extraction", "processing")
    log_chunk_processing("https://example.com/docs/page1", 0, "chunking", "success")
    log_chunk_processing("https://example.com/docs/page1", 1, "chunking", "success")
    log_stage_complete("extraction", count=2, duration=5.2)
    
    # Demonstrate retry with backoff
    log_stage_start("embedding")
    
    attempt_count = [0]
    
    def flaky_operation():
        """Simulates an operation that fails twice then succeeds."""
        attempt_count[0] += 1
        if attempt_count[0] < 3:
            raise ConnectionError(f"Temporary failure (attempt {attempt_count[0]})")
        return "success"
    
    try:
        result = retry_with_backoff(
            flaky_operation,
            max_retries=3,
            delays=[0.1, 0.2, 0.4],
            exceptions=(ConnectionError,)
        )
        print(f"Retry succeeded: {result}")
    except Exception as e:
        log_error(
            "Embedding generation failed",
            stage="embedding",
            error=e,
            url="https://example.com/docs/page1",
            chunk_index=0
        )
    
    log_stage_complete("embedding", count=2, duration=1.8)
    
    print()
    print("Demo complete! Check logs/demo_pipeline.log for JSON-formatted logs.")
    print("Each log entry includes:")
    print("  - timestamp")
    print("  - level (INFO, WARNING, ERROR)")
    print("  - stage (pipeline stage name)")
    print("  - context (url, chunk_index, etc.)")


if __name__ == "__main__":
    main()

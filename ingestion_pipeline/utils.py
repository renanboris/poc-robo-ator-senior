"""Shared utilities for the ingestion pipeline."""

import time
import logging
import logging.handlers
import json
from typing import Callable, Any, Tuple, Type, Optional, Dict
from functools import wraps
from pathlib import Path

logger = logging.getLogger(__name__)


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    delays: list[int] = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Any:
    """Execute function with exponential backoff retry.
    
    Args:
        func: Function to execute
        max_retries: Maximum number of retry attempts
        delays: List of delay seconds between retries (default: [1, 2, 4])
        exceptions: Tuple of exception types to catch and retry
        
    Returns:
        Result of successful function execution
        
    Raises:
        Exception: If all retry attempts fail, raises the last exception
    """
    if delays is None:
        delays = [1, 2, 4]
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            return func()
        except exceptions as e:
            last_exception = e
            if attempt == max_retries - 1:
                # Last attempt failed, raise the exception
                raise
            
            # Calculate delay for this attempt
            delay = delays[attempt] if attempt < len(delays) else delays[-1]
            
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            time.sleep(delay)
    
    # Should never reach here, but just in case
    if last_exception:
        raise last_exception


def sanitize_filename(text: str) -> str:
    """Sanitize text for use in filenames and IDs.
    
    Args:
        text: Text to sanitize
        
    Returns:
        Sanitized text with special characters replaced
    """
    # Convert to lowercase
    text = text.lower()
    
    # Replace spaces and special characters with underscores
    import re
    text = re.sub(r'[^a-z0-9]+', '_', text)
    
    # Remove leading/trailing underscores
    text = text.strip('_')
    
    # Collapse multiple underscores
    text = re.sub(r'_+', '_', text)
    
    return text


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.
        
        Args:
            record: Log record to format
            
        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add context fields if present
        if hasattr(record, "stage"):
            log_data["stage"] = record.stage
        if hasattr(record, "url"):
            log_data["url"] = record.url
        if hasattr(record, "chunk_index"):
            log_data["chunk_index"] = record.chunk_index
        if hasattr(record, "context"):
            log_data["context"] = record.context
            
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    log_file: str = "ingestion_pipeline.log",
    json_format: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """Configure structured logging with rotation for the pipeline.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_dir: Directory for log files
        log_file: Name of the log file
        json_format: Use JSON formatting if True, plain text if False
        max_bytes: Maximum size per log file (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)
    """
    # Create log directory if it doesn't exist
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Create rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_path / log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    
    # Set formatters
    if json_format:
        formatter = JSONFormatter(datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        # Use plain format for console for readability
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def log_with_context(
    level: str,
    message: str,
    stage: Optional[str] = None,
    url: Optional[str] = None,
    chunk_index: Optional[int] = None,
    context: Optional[Dict[str, Any]] = None
) -> None:
    """Log message with structured context fields.
    
    Args:
        level: Log level (debug, info, warning, error, critical)
        message: Log message
        stage: Pipeline stage name (e.g., "discovery", "extraction")
        url: URL being processed
        chunk_index: Index of chunk being processed
        context: Additional context dictionary
    """
    log_func = getattr(logger, level.lower())
    
    # Create extra dict with context fields
    extra = {}
    if stage is not None:
        extra["stage"] = stage
    if url is not None:
        extra["url"] = url
    if chunk_index is not None:
        extra["chunk_index"] = chunk_index
    if context is not None:
        extra["context"] = context
    
    log_func(message, extra=extra)


def log_stage_start(stage_name: str) -> None:
    """Log the start of a pipeline stage.
    
    Args:
        stage_name: Name of the stage starting
    """
    log_with_context("info", f"Starting stage: {stage_name}", stage=stage_name)


def log_stage_complete(stage_name: str, count: int, duration: float) -> None:
    """Log the completion of a pipeline stage.
    
    Args:
        stage_name: Name of the stage completed
        count: Number of items processed
        duration: Duration in seconds
    """
    log_with_context(
        "info",
        f"Completed stage: {stage_name} - Processed {count} items in {duration:.2f}s",
        stage=stage_name,
        context={"count": count, "duration_seconds": duration}
    )


def log_url_processing(url: str, stage: str, status: str = "processing") -> None:
    """Log URL processing status.
    
    Args:
        url: URL being processed
        stage: Current pipeline stage
        status: Processing status (processing, success, failed, skipped)
    """
    log_with_context(
        "info" if status in ["processing", "success"] else "warning",
        f"URL {status}: {url}",
        stage=stage,
        url=url,
        context={"status": status}
    )


def log_chunk_processing(
    url: str,
    chunk_index: int,
    stage: str,
    status: str = "processing"
) -> None:
    """Log chunk processing status.
    
    Args:
        url: Source URL of the chunk
        chunk_index: Index of the chunk
        stage: Current pipeline stage
        status: Processing status (processing, success, failed)
    """
    log_with_context(
        "info" if status in ["processing", "success"] else "warning",
        f"Chunk {chunk_index} {status}",
        stage=stage,
        url=url,
        chunk_index=chunk_index,
        context={"status": status}
    )


def log_error(
    message: str,
    stage: str,
    error: Exception,
    url: Optional[str] = None,
    chunk_index: Optional[int] = None
) -> None:
    """Log error with full context.
    
    Args:
        message: Error message
        stage: Pipeline stage where error occurred
        error: Exception object
        url: URL being processed when error occurred
        chunk_index: Chunk index being processed when error occurred
    """
    context = {
        "error_type": type(error).__name__,
        "error_message": str(error)
    }
    
    log_with_context(
        "error",
        message,
        stage=stage,
        url=url,
        chunk_index=chunk_index,
        context=context
    )

"""
Logging configuration for BOUT.

Provides:
- Rich console output with colors and formatting
- Rotating file logs with JSON structure
- Per-job log files for detailed debugging
"""
import logging
import json
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

try:
    from rich.console import Console
    from rich.logging import RichHandler
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

from ..core.config import get_config


# Global console instance (shared with progress bars)
console = Console(stderr=True) if RICH_AVAILABLE else None


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "job_id"):
            log_data["job_id"] = record.job_id
        if hasattr(record, "chunk"):
            log_data["chunk"] = record.chunk
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class HumanFormatter(logging.Formatter):
    """Human-readable formatter for file logs."""

    def __init__(self):
        super().__init__(
            fmt="%(asctime)s | %(name)-30s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )


def setup_logging(
    level: str = "INFO",
    enable_file_logging: bool = True,
    log_file: Optional[Path] = None,
    json_format: bool = False,
) -> None:
    """
    Initialize the logging system.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to write logs to files
        log_file: Custom log file path (uses default if None)
        json_format: Use JSON format for file logs
    """
    config = get_config()

    # Ensure logs directory exists
    config.logs_dir.mkdir(parents=True, exist_ok=True)
    (config.logs_dir / "jobs").mkdir(exist_ok=True)

    # Root logger for the application
    root_logger = logging.getLogger("bout")
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    if RICH_AVAILABLE:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
        )
        console_handler.setLevel(logging.INFO)
    else:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(HumanFormatter())
        console_handler.setLevel(logging.INFO)

    root_logger.addHandler(console_handler)

    # File handler with rotation
    if enable_file_logging:
        log_path = log_file or (config.logs_dir / "bout.log")

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=config.log.max_file_size,
            backupCount=config.log.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File captures everything

        if json_format:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(HumanFormatter())

        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Module name (will be prefixed with 'bout.')

    Returns:
        Logger instance
    """
    return logging.getLogger(f"bout.{name}")


class JobLogger:
    """
    Context-managed logger for individual transcription jobs.

    Creates a per-job log file for detailed debugging.
    """

    def __init__(self, job_id: str, video_name: str):
        self.job_id = job_id
        self.video_name = video_name
        self.logger = logging.getLogger(f"bout.job.{job_id}")
        self.job_log_path: Optional[Path] = None
        self._file_handler: Optional[logging.Handler] = None

    def __enter__(self) -> "JobLogger":
        config = get_config()

        # Create per-job log file
        safe_name = self._sanitize_name(self.video_name)
        self.job_log_path = config.logs_dir / "jobs" / f"{self.job_id}_{safe_name}.log"
        self.job_log_path.parent.mkdir(parents=True, exist_ok=True)

        # Add file handler for this job
        self._file_handler = logging.FileHandler(
            self.job_log_path, encoding="utf-8"
        )
        self._file_handler.setFormatter(HumanFormatter())
        self._file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(self._file_handler)

        self.logger.info(f"Job started: {self.video_name}")

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.logger.error(f"Job failed with error: {exc_val}", exc_info=True)
        else:
            self.logger.info("Job completed successfully")

        if self._file_handler:
            self.logger.removeHandler(self._file_handler)
            self._file_handler.close()

    def _sanitize_name(self, name: str) -> str:
        """Create safe filename from video name."""
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        return safe[:50]

    def info(self, message: str, **kwargs):
        """Log info message with optional extra fields."""
        extra = {"job_id": self.job_id, **kwargs}
        self.logger.info(message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message with optional extra fields."""
        extra = {"job_id": self.job_id, **kwargs}
        self.logger.debug(message, extra=extra)

    def warning(self, message: str, **kwargs):
        """Log warning message with optional extra fields."""
        extra = {"job_id": self.job_id, **kwargs}
        self.logger.warning(message, extra=extra)

    def error(self, message: str, **kwargs):
        """Log error message with optional extra fields."""
        extra = {"job_id": self.job_id, **kwargs}
        self.logger.error(message, extra=extra)

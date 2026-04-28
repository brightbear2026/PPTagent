"""
Central logging configuration using structlog.

Configures structlog to output JSON-formatted logs for production,
human-readable console output for development.
"""

import logging
import os
import sys


def setup_logging() -> None:
    """Configure structlog for the application."""
    try:
        import structlog
    except ImportError:
        # structlog not installed — keep basic logging
        return

    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level, logging.INFO),
    )

    # Quiet down noisy libraries
    for name in ("uvicorn", "uvicorn.access", "fastapi", "httpx", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)

    # Configure structlog
    env = os.environ.get("ENV", "development")
    if env == "production":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """Get a structlog logger, falling back to stdlib if structlog not available."""
    try:
        import structlog
        return structlog.get_logger(name)
    except ImportError:
        return logging.getLogger(name)

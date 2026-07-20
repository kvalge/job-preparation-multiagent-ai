"""Structured logging for analysis pipeline failures and retries."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "analysis.log")

_logger: logging.Logger | None = None


def get_analysis_logger() -> logging.Logger:
    """Return a module logger that writes to logs/analysis.log and the console."""
    global _logger
    if _logger is not None:
        return _logger

    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger("jobprep.analysis")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _logger = logger
    return logger


def log_stage_failure(stage: str, error: Exception | str, *, job_post_id: int | None = None) -> None:
    """Log a failed pipeline stage for later diagnosis / retry (with traceback when possible)."""
    import traceback

    where = f" job_post_id={job_post_id}" if job_post_id is not None else ""
    logger = get_analysis_logger()
    if isinstance(error, BaseException):
        logger.error(
            "Stage '%s' failed%s: %s\n%s",
            stage,
            where,
            error,
            traceback.format_exc(),
        )
    else:
        logger.error("Stage '%s' failed%s: %s", stage, where, error)


def log_stage_info(message: str) -> None:
    get_analysis_logger().info(message)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

"""Centralized logging configuration."""

import logging
from typing import Optional

from tools.utils.config import LOG_FORMAT, LOG_LEVEL


def setup_logging(level: Optional[str] = None) -> None:
    """Configure root logging once for the whole app."""
    effective_level = (level or LOG_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, effective_level, logging.INFO),
        format=LOG_FORMAT,
    )



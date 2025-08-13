"""Logging utilities for the tournament display application."""

import sys
import logging
from datetime import datetime


# Set up file-only logging to avoid interfering with TUI
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/tmp/tournament_debug.log"),
    ],
)
logger = logging.getLogger(__name__)


def log(message):
    """Log to file only (no console output to avoid TUI interference)"""
    logger.info(message)
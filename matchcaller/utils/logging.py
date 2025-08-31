"""Logging utilities for the tournament display application."""

import logging

# Global state
_console_logging_enabled = None
_file_logger = None

def _is_tui_running() -> bool:
    """Detect if we're running in TUI mode vs CLI mode"""
    global _console_logging_enabled
    
    if _console_logging_enabled is not None:
        return not _console_logging_enabled
    
    # Default to console output unless explicitly disabled
    return False

def set_console_logging(enabled: bool):
    """Explicitly enable/disable console logging"""
    global _console_logging_enabled
    _console_logging_enabled = enabled

def log(message: str):
    """
    Smart logging that adapts to context:
    - Always logs to file for debugging
    - Also logs to console for CLI operations (cloning, etc.)
    - Skips console output during TUI operations
    """
    global _file_logger
    
    # Initialize file logger once
    if _file_logger is None:
        _file_logger = logging.getLogger('tournament_file')
        _file_logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler("/tmp/tournament_debug.log")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        _file_logger.addHandler(file_handler)
        _file_logger.propagate = False
    
    # Always log to file
    _file_logger.info(message)
    
    # Also log to console if appropriate
    if not _is_tui_running():
        print(message)

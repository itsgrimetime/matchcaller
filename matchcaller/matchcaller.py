"""
Tournament Display TUI - A terminal-based tournament viewer
Designed for Raspberry Pi Zero 2W - no X11/browser required!

This module provides backward compatibility imports for legacy code.
New code should import directly from the specific modules:
- TournamentAPI from .api.tournament_api
- TournamentDisplay from .ui.tournament_display
- MatchRow from .models.match
- MOCK_TOURNAMENT_DATA from .models.mock_data
"""

# Re-export main classes and data for backward compatibility
from .api.tournament_api import TournamentAPI
from .models.match import MatchRow
from .models.mock_data import MOCK_TOURNAMENT_DATA, MOCK_BASE_TIME
from .ui.tournament_display import TournamentDisplay
from .utils.logging import log

# Re-export main entry point
from .__main__ import main

__all__ = [
    "TournamentAPI",
    "TournamentDisplay", 
    "MatchRow",
    "MOCK_TOURNAMENT_DATA",
    "MOCK_BASE_TIME",
    "log",
    "main",
]
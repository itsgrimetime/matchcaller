"""Tournament Display TUI - A terminal-based tournament viewer for Raspberry Pi Zero 2W."""

from .api import TournamentAPI
from .models import MatchRow
from .ui import TournamentDisplay

__version__ = "1.0.0"
__all__ = ["TournamentAPI", "MatchRow", "TournamentDisplay"]
"""Protocols for injectable tournament display dependencies."""

from collections.abc import Callable
from typing import Protocol

from textual.app import App

from ..api.jsonbin_api import AlertData
from ..models.match import TournamentState
from .refresh_controller import RefreshController


class TournamentDataSource(Protocol):
    """Source of tournament state snapshots for the display."""

    async def fetch_sets(self) -> TournamentState:
        """Fetch the current tournament state."""


class AlertSource(Protocol):
    """Source of alert metadata for highlighted players."""

    async def fetch_alerts(self) -> AlertData:
        """Fetch late-arrival / DQ alert data."""


RefreshControllerFactory = Callable[[App[None], float], RefreshController]

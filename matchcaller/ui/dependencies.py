"""Protocols for injectable tournament display dependencies."""

from collections.abc import Callable
from typing import Protocol

from textual.app import App

from ..api.jsonbin_api import AlertData
from ..models.dashboard import DashboardState
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


class DashboardDataSource(Protocol):
    """Source of combined main/ladder dashboard snapshots."""

    async def fetch_dashboard_state(
        self,
        previous_state: DashboardState | None = None,
    ) -> DashboardState:
        """Fetch the current dashboard state."""


RefreshControllerFactory = Callable[[App[None], float], RefreshController]

"""Focused tests for injected tournament-display dependencies."""

import pytest

from matchcaller.api.jsonbin_api import AlertData
from matchcaller.models.match import MatchData, PlayerData, TournamentState
from matchcaller.ui.refresh_controller import RefreshController
from matchcaller.ui.tournament_display import TournamentDisplay


class StubTournamentSource:
    """Deterministic tournament source for Textual tests."""

    def __init__(self, snapshots: list[TournamentState]) -> None:
        self.snapshots = list(snapshots)
        self.calls = 0

    async def fetch_sets(self) -> TournamentState:
        self.calls += 1
        index = min(self.calls - 1, len(self.snapshots) - 1)
        return self.snapshots[index]


class StubAlertSource:
    """Deterministic alert source for Textual tests."""

    def __init__(self, alerts: list[AlertData]) -> None:
        self.alerts = list(alerts)
        self.calls = 0

    async def fetch_alerts(self) -> AlertData:
        self.calls += 1
        index = min(self.calls - 1, len(self.alerts) - 1)
        return self.alerts[index]


class PassiveRefreshController(RefreshController):
    """Refresh controller variant that skips background timers in tests."""

    def start(
        self,
        *,
        update_display,
        fetch_tournament_data,
        fetch_alerts=None,
    ) -> None:
        if fetch_alerts is not None:
            fetch_alerts()


def passive_refresh_controller_factory(app, poll_interval: float) -> RefreshController:
    """Build a refresh controller without interval registration."""
    return PassiveRefreshController(app, poll_interval=poll_interval)


def _single_match_state(*, state: int, started_at: int | None = None) -> TournamentState:
    return TournamentState(
        event_name="Injected Event",
        tournament_name="Injected Tournament",
        sets=[
            MatchData(
                id=1,
                displayName="Winners Round 1",
                player1=PlayerData(tag="Alice", discord_id="123"),
                player2=PlayerData(tag="Bob"),
                state=state,
                updatedAt=1640995200,
                startedAt=started_at,
                poolName="Pool A",
            )
        ],
    )


@pytest.mark.ui
class TestDisplayInjection:
    """Verify smaller Textual tests can use injected stubs directly."""

    @pytest.mark.asyncio
    async def test_app_uses_injected_tournament_source(self):
        source = StubTournamentSource([_single_match_state(state=2)])
        app = TournamentDisplay(
            api=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert app.event_name == "Injected Event"
            assert app.total_sets == 1
            assert source.calls == 1

    @pytest.mark.asyncio
    async def test_manual_refresh_uses_injected_source_without_patching(self):
        source = StubTournamentSource(
            [
                _single_match_state(state=2),
                _single_match_state(state=6, started_at=1640995300),
            ]
        )
        app = TournamentDisplay(
            api=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)
            assert app.ready_sets == 1

            await pilot.press("r")
            await pilot.pause(0.5)

            assert source.calls == 2
            assert app.in_progress_sets == 1

    @pytest.mark.asyncio
    async def test_app_uses_injected_alert_source(self):
        source = StubTournamentSource([_single_match_state(state=2)])
        alert_source = StubAlertSource([AlertData({"lateArrivals": ["123"]})])
        app = TournamentDisplay(
            api=source,
            alert_source=alert_source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert source.calls == 1
            assert alert_source.calls == 1
            assert app.alerts.late_arrivals == {"123"}

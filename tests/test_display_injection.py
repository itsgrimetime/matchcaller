"""Focused tests for injected tournament-display dependencies."""

import pytest
from rich.console import Console
from textual.widgets import DataTable, Static

from matchcaller.api.jsonbin_api import AlertData
from matchcaller.models.dashboard import DashboardState, ViewMode
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


class StubDashboardSource:
    def __init__(self, snapshots: list[DashboardState]) -> None:
        self.snapshots = list(snapshots)
        self.calls = 0
        self.previous_states: list[DashboardState | None] = []

    async def fetch_dashboard_state(self, previous_state=None) -> DashboardState:
        self.calls += 1
        self.previous_states.append(previous_state)
        index = min(self.calls - 1, len(self.snapshots) - 1)
        return self.snapshots[index]


class StubDashboardGrid:
    def __init__(self) -> None:
        self.reset_calls = 0

    def reset(self) -> None:
        self.reset_calls += 1


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


def _dashboard_state_with_main_match(
    *,
    view: ViewMode,
    updated_at: int,
) -> DashboardState:
    return DashboardState(
        tournament_name="Injected Tournament",
        main=TournamentState(
            event_name="Injected Event",
            tournament_name="Injected Tournament",
            sets=[
                MatchData(
                    id=1,
                    displayName="Top 8 - Winners Round 1",
                    player1=PlayerData(tag="Alice"),
                    player2=PlayerData(tag="Bob"),
                    state=2,
                    updatedAt=updated_at,
                    startedAt=None,
                    poolName="Top 8",
                )
            ],
        ),
        ladder=None,
        stations=None,
        requested_view=view,
        resolved_view=view,
        ladder_was_visible=view != ViewMode.MAIN,
        last_update="12:00:00",
    )


@pytest.mark.ui
class TestDisplayInjection:
    """Verify smaller Textual tests can use injected stubs directly."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "slug_kwargs, expected_theme",
        [
            (
                {"tournament_slug": "melee-abbey-tavern-164-halloween-edition"},
                "halloween",
            ),
            ({"tournament_slug": "melee-abbey-tavern-165"}, "textual-dark"),
            (
                {"tournament_slug": "halloween-at-abbey-2027"},
                "halloween",
            ),
            (
                {"tournament_slug": "melee-abbey-tavern-216-HALLOWEEN-bash"},
                "halloween",
            ),
            (
                {
                    "event_slug": (
                        "tournament/melee-abbey-tavern-164-halloween-edition"
                        "/event/melee-doubles"
                    )
                },
                "halloween",
            ),
            (
                {
                    "tournament_slug": "melee-abbey-tavern-216",
                    "event_slug": (
                        "tournament/melee-abbey-tavern-216/event/halloween-doubles"
                    ),
                },
                "halloween",
            ),
            (
                {"event_slug": "tournament/melee-abbey-tavern-217/event/melee-doubles"},
                "textual-dark",
            ),
            ({}, "textual-dark"),
        ],
    )
    async def test_tournament_selects_seasonal_theme(self, slug_kwargs, expected_theme):
        app = TournamentDisplay(
            **slug_kwargs,
            api=StubTournamentSource([_single_match_state(state=2)]),
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.theme == expected_theme
            assert app.total_sets == 1

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
    async def test_round_robin_call_board_updates_then_switches_to_seeded_elimination(self):
        pool_state = _single_match_state(state=1)
        pool_state.finals_pending = True
        pool_match = pool_state.sets[0].model_copy(update={
            "pool_label": "Round Robin - Pool A",
            "bracket_type": "ROUND_ROBIN",
            "player1": PlayerData(tag="AliceTeam / AlexTeam", team_tags=["AliceTeam", "AlexTeam"]),
        })
        first = pool_match.model_copy(update={"round_number": 1})
        second = pool_match.model_copy(update={
            "id": 2, "round_number": 2, "player2": PlayerData(tag="Later Team"),
        })
        ready = pool_match.model_copy(update={
            "id": 3, "round_number": 3, "state": 2, "player2": PlayerData(tag="Ready Team"),
        })
        playing = pool_match.model_copy(update={"id": 4, "state": 6, "station": 3})
        pool_state.sets = [second, first, ready, playing]
        fewer_matches = pool_state.model_copy(update={"sets": [first, second]})
        between_stages = pool_state.model_copy(update={"sets": []})
        elimination_state = _single_match_state(state=2)
        elimination_state.sets[0].poolName = "Elimination Bracket"
        elimination_state.sets[0].pool_label = "Double Elim - Bracket 1"
        elimination_state.sets[0].bracket_type = "DOUBLE_ELIMINATION"
        regular_state = _single_match_state(state=2)
        regular_state.sets[0].bracket_type = "DOUBLE_ELIMINATION"
        app = TournamentDisplay(
            api=StubTournamentSource([
                pool_state, fewer_matches, between_stages, elimination_state, regular_state,
            ]),
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        console = Console(width=116, color_system=None)

        def board_text() -> str:
            with console.capture() as capture:
                console.print(app.query_one("#call-board-content", Static).renderable)
            return capture.get()

        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            board = app.query_one("#call-board-content", Static)
            rendered = board_text()
            assert "Pool A · 4 sets left" in rendered
            assert rendered.index("PLAYING NOW") < rendered.index("Station 3")
            assert rendered.index("Station 3") < rendered.index("READY TO CALL")
            assert "AliceTeam / AlexTeam  vs  Ready Team" in rendered
            assert "Pool A · R1" in rendered
            assert "Later Team" not in rendered
            assert "Double-elimination finals · awaiting seeds" in rendered

            await pilot.press("r")
            await pilot.pause()
            assert app.query_one("#call-board-content", Static) is board
            assert "Pool A · 2 sets left" in board_text()
            assert "No sets marked ready" in board_text()

            await pilot.press("r")
            await pilot.pause()
            assert "Double-elimination finals · awaiting seeds" in board_text()

            await pilot.press("r")
            await pilot.pause()
            title = app.query_one("#pool-elimination-bracket .pool-title", Static)
            assert "Double Elim - Bracket 1" in str(title.render())
            table = app.query_one("#pool-elimination-bracket DataTable", DataTable)
            assert table.get_cell("1", "match") == "[bold]Alice vs Bob[/bold]"
            assert not app.query("#call-board-content")

            await pilot.press("r")
            await pilot.pause()
            assert app.query_one("#pool-pool-a DataTable", DataTable)
            assert not app.query("#call-board-content")

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

    @pytest.mark.asyncio
    async def test_app_uses_injected_dashboard_source(self):
        dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=None,
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.MAIN,
            ladder_was_visible=False,
            last_update="12:00:00",
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="auto",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert source.calls == 1
            assert app.dashboard_state is dashboard_state
            assert app.event_name == "Injected Event"

    @pytest.mark.asyncio
    async def test_split_dashboard_mounts_dashboard_container(self):
        from matchcaller.models.dashboard import (
            DashboardState,
            LadderDisplayStatus,
            LadderState,
            ViewMode,
        )

        dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=LadderState(
                display_status=LadderDisplayStatus.ACTIVE,
                event_name="Injected Ladder",
                event_state="ACTIVE",
                sets=[],
                standings=[],
                auto_should_show=True,
            ),
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.SPLIT,
            ladder_was_visible=True,
            last_update="12:00:00",
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="auto",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert app.query_one("#dashboard-container")
            assert app.query_one("#main-dashboard-table")
            assert app.query_one("#ladder-dashboard-table")

    @pytest.mark.asyncio
    async def test_ladder_dashboard_mounts_dashboard_container(self):
        from matchcaller.models.dashboard import (
            DashboardState,
            LadderDisplayStatus,
            LadderState,
            LadderStanding,
            ViewMode,
        )

        dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=LadderState(
                display_status=LadderDisplayStatus.ACTIVE,
                event_name="Injected Ladder",
                event_state="ACTIVE",
                sets=[],
                standings=[
                    LadderStanding(
                        placement=1,
                        entrant_name="Alice",
                        wins=3,
                        losses=0,
                    )
                ],
                auto_should_show=True,
            ),
            stations=None,
            requested_view=ViewMode.LADDER,
            resolved_view=ViewMode.LADDER,
            ladder_was_visible=True,
            last_update="12:00:00",
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="ladder",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            assert app.query_one("#dashboard-container")
            assert app.query_one("#ladder-dashboard-table")
            assert app.query_one("#ladder-standings-table")

    @pytest.mark.asyncio
    async def test_split_dashboard_updates_duration_cell_between_refreshes(
        self,
        monkeypatch,
    ):
        from matchcaller.models import match as match_model

        base_time = 1_700_000_000
        monkeypatch.setattr(match_model.time, "time", lambda: base_time)
        dashboard_state = _dashboard_state_with_main_match(
            view=ViewMode.SPLIT,
            updated_at=base_time - 61,
        )
        source = StubDashboardSource([dashboard_state])
        app = TournamentDisplay(
            view_mode="split",
            dashboard_source=source,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )

        async with app.run_test() as pilot:
            await pilot.pause(0.5)

            table = app.query_one("#main-dashboard-table", DataTable)
            assert table.get_cell("0", "duration") == "1m 1s"

            monkeypatch.setattr(match_model.time, "time", lambda: base_time + 2)
            app.update_display()
            await pilot.pause(0.1)

            assert table.get_cell("0", "duration") == "1m 3s"

    def test_loading_state_resets_injected_dashboard_grid(self):
        dashboard_grid = StubDashboardGrid()
        app = TournamentDisplay(
            dashboard_grid=dashboard_grid,
            poll_interval=999.0,
            refresh_controller_factory=passive_refresh_controller_factory,
        )
        app.dashboard_state = DashboardState(
            tournament_name="Injected Tournament",
            main=_single_match_state(state=2),
            ladder=None,
            stations=None,
            requested_view=ViewMode.AUTO,
            resolved_view=ViewMode.MAIN,
            ladder_was_visible=False,
            last_update="12:00:00",
        )

        app.show_loading_state()

        assert app.dashboard_state is None
        assert dashboard_grid.reset_calls == 1

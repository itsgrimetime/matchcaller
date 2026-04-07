"""Unit tests for refresh coordination helpers."""

from unittest.mock import Mock

import pytest

from matchcaller.models.match import MatchData, PlayerData, TournamentState
from matchcaller.ui.refresh_controller import (
    RefreshController,
    build_display_snapshot,
    build_error_timestamp,
)


class DummyApp:
    """Minimal app stub for refresh-controller unit tests."""

    def __init__(self) -> None:
        self.intervals: list[tuple[float, object]] = []
        self.deferred_calls: list[object] = []
        self.notifications: list[str] = []

    def set_interval(self, interval: float, callback: object) -> None:
        self.intervals.append((interval, callback))

    def call_later(self, callback: object) -> None:
        self.deferred_calls.append(callback)

    def notify(self, message: str) -> None:
        self.notifications.append(message)


@pytest.mark.unit
class TestDisplaySnapshot:
    """Test pure snapshot helpers."""

    def test_build_display_snapshot_counts_effective_states(self):
        data = TournamentState(
            event_name="Test Event",
            tournament_name="Test Tournament",
            sets=[
                MatchData(
                    id=1,
                    displayName="Ready Match",
                    player1=PlayerData(tag="Alice"),
                    player2=PlayerData(tag="Bob"),
                    state=2,
                    updatedAt=100,
                    poolName="Pool A",
                ),
                MatchData(
                    id=2,
                    displayName="Started Match",
                    player1=PlayerData(tag="Carol"),
                    player2=PlayerData(tag="Dave"),
                    state=2,
                    updatedAt=200,
                    startedAt=150,
                    poolName="Pool A",
                ),
                MatchData(
                    id=3,
                    displayName="In Progress Match",
                    player1=PlayerData(tag="Eve"),
                    player2=PlayerData(tag="Frank"),
                    state=6,
                    updatedAt=300,
                    startedAt=250,
                    poolName="Pool B",
                ),
            ],
        )

        snapshot = build_display_snapshot(data)

        assert snapshot.title == "Test Tournament - Test Event"
        assert snapshot.total_sets == 3
        assert snapshot.ready_sets == 1
        assert snapshot.in_progress_sets == 2

    def test_build_error_timestamp(self):
        assert build_error_timestamp().startswith("Error at ")


@pytest.mark.unit
class TestRefreshController:
    """Test refresh scheduling and queued update behavior."""

    def test_start_registers_intervals_and_initial_alert_fetch(self):
        app = DummyApp()
        controller = RefreshController(app, poll_interval=30.0)
        fetch_alerts = Mock()

        controller.start(
            update_display=lambda: None,
            fetch_tournament_data=lambda: None,
            fetch_alerts=fetch_alerts,
        )

        assert [interval for interval, _callback in app.intervals] == [1.0, 30.0, 15.0]
        fetch_alerts.assert_called_once()

    def test_finish_ui_mutation_flushes_pending_update(self):
        app = DummyApp()
        controller = RefreshController(app, poll_interval=30.0)
        flush_update = Mock()
        log_fn = Mock()

        controller.begin_ui_mutation()
        controller.mark_ui_update_pending("test", log_fn=log_fn)
        controller.finish_ui_mutation(flush_update=flush_update)

        assert app.deferred_calls == [flush_update]
        assert not controller.ui_busy

    def test_refresh_now_triggers_fetch_and_notification(self):
        app = DummyApp()
        controller = RefreshController(app, poll_interval=30.0)
        fetch_tournament_data = Mock()

        controller.refresh_now(fetch_tournament_data=fetch_tournament_data)

        fetch_tournament_data.assert_called_once()
        assert app.notifications == ["Refreshing tournament data..."]

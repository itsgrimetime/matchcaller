"""Refresh coordination helpers for the tournament display."""

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Sequence

from textual.app import App

from ..models.match import MatchRow, MatchState, TournamentState


@dataclass(frozen=True)
class DisplaySnapshot:
    """Display state derived from a tournament state payload."""

    event_name: str
    title: str
    matches: list[MatchRow]
    total_sets: int
    ready_sets: int
    in_progress_sets: int
    last_update: str


def _count_matches(matches: Sequence[MatchRow], state: MatchState) -> int:
    """Count matches in the given effective display state."""
    return sum(1 for match in matches if match.effective_state == state)


def build_display_snapshot(
    data: TournamentState,
    *,
    timestamp: datetime | None = None,
) -> DisplaySnapshot:
    """Build a display snapshot from API/simulator tournament data."""
    now = timestamp or datetime.now()
    matches = [MatchRow(set_data) for set_data in data.sets]
    event_name = data.event_name
    tournament_name = data.tournament_name
    return DisplaySnapshot(
        event_name=event_name,
        title=f"{tournament_name} - {event_name}",
        matches=matches,
        total_sets=len(matches),
        ready_sets=_count_matches(matches, MatchState.READY),
        in_progress_sets=_count_matches(matches, MatchState.IN_PROGRESS),
        last_update=now.strftime("%H:%M:%S"),
    )


def build_error_timestamp(*, timestamp: datetime | None = None) -> str:
    """Build the last-update string for a failed fetch."""
    now = timestamp or datetime.now()
    return f"Error at {now.strftime('%H:%M:%S')}"


class RefreshController:
    """Own refresh scheduling and queued UI update bookkeeping."""

    def __init__(self, app: App[None], *, poll_interval: float) -> None:
        self.app = app
        self.poll_interval = poll_interval
        self._ui_mutation_in_progress = False
        self._ui_update_pending = False

    @property
    def ui_busy(self) -> bool:
        """Return True while a UI mutation is in progress."""
        return self._ui_mutation_in_progress

    def start(
        self,
        *,
        update_display: Callable[[], None],
        fetch_tournament_data: Callable[[], None],
        fetch_alerts: Callable[[], None] | None = None,
    ) -> None:
        """Register periodic refresh timers with the Textual app."""
        self.app.set_interval(1.0, update_display)
        self.app.set_interval(self.poll_interval, fetch_tournament_data)
        if fetch_alerts is not None:
            self.app.set_interval(15.0, fetch_alerts)
            fetch_alerts()

    def begin_ui_mutation(self) -> None:
        """Mark a UI mutation as active."""
        self._ui_mutation_in_progress = True

    def mark_ui_update_pending(
        self,
        reason: str,
        *,
        log_fn: Callable[[str], None],
    ) -> None:
        """Queue one follow-up UI update when the current mutation completes."""
        if not self._ui_update_pending:
            log_fn(f"⏳ Deferring UI update while table mutation is active: {reason}")
        self._ui_update_pending = True

    def finish_ui_mutation(self, *, flush_update: Callable[[], None]) -> None:
        """Release the mutation lock and flush any queued UI update."""
        self._ui_mutation_in_progress = False
        if self._ui_update_pending:
            self._ui_update_pending = False
            self.app.call_later(flush_update)

    def refresh_now(self, *, fetch_tournament_data: Callable[[], None]) -> None:
        """Trigger an immediate refresh and notify the user."""
        fetch_tournament_data()
        self.app.notify("Refreshing tournament data...")

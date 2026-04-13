"""Dashboard data models and pure helper functions."""

from enum import Enum
from typing import Sequence

from pydantic import Field

from .match import DictCompatibleBaseModel, MatchData, MatchRow, TournamentState


class ViewMode(str, Enum):
    """Supported runtime display modes."""

    AUTO = "auto"
    MAIN = "main"
    SPLIT = "split"
    LADDER = "ladder"


class LadderDisplayStatus(str, Enum):
    """Render status for the ladder portion of the dashboard."""

    NOT_FOUND = "not_found"
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"


class LadderStanding(DictCompatibleBaseModel):
    """One row in the ladder standings table."""

    placement: int
    entrant_name: str
    wins: int | None = None
    losses: int | None = None
    win_percentage: str | None = None

    @property
    def record_text(self) -> str:
        """Return the W-L record for compact display."""
        if self.wins is None or self.losses is None:
            return "-"
        return f"{self.wins}-{self.losses}"


class Station(DictCompatibleBaseModel):
    """Tournament setup/station metadata."""

    id: str | int
    number: int
    enabled: bool | None = None


class StationState(DictCompatibleBaseModel):
    """Available and occupied station numbers."""

    stations: list[Station]
    occupied_numbers: set[int] = Field(default_factory=set)
    available_numbers: list[int] = Field(default_factory=list)


class LadderState(DictCompatibleBaseModel):
    """Current ladder event state."""

    display_status: LadderDisplayStatus
    event_id: str | int | None = None
    event_name: str | None = None
    event_slug: str | None = None
    event_state: str | None = None
    start_at: int | None = None
    entrants_count: int = 0
    sets: list[MatchData] = Field(default_factory=list)
    standings: list[LadderStanding] = Field(default_factory=list)
    auto_should_show: bool = False
    waiting_reason: str | None = None


class DashboardState(DictCompatibleBaseModel):
    """Combined main bracket and ladder dashboard state."""

    tournament_name: str
    main: TournamentState | None = None
    ladder: LadderState | None = None
    stations: StationState | None = None
    requested_view: ViewMode = ViewMode.AUTO
    resolved_view: ViewMode = ViewMode.MAIN
    ladder_was_visible: bool = False
    last_update: str


def derive_ladder_display_status(
    event_state: str | None,
    active_set_count: int,
) -> LadderDisplayStatus:
    """Derive the ladder display status from public start.gg fields."""
    if event_state is None:
        return LadderDisplayStatus.NOT_FOUND

    normalized_state = event_state.upper()
    if normalized_state == "COMPLETED":
        return LadderDisplayStatus.COMPLETED
    if normalized_state == "ACTIVE":
        return LadderDisplayStatus.ACTIVE
    if normalized_state != "INVALID" and active_set_count > 0:
        return LadderDisplayStatus.ACTIVE
    return LadderDisplayStatus.WAITING


def resolve_dashboard_view(
    requested_view: ViewMode,
    ladder: LadderState | None,
    *,
    ladder_was_visible: bool = False,
) -> ViewMode:
    """Resolve the actual view to render for a dashboard refresh."""
    if requested_view == ViewMode.MAIN:
        return ViewMode.MAIN
    if requested_view in {ViewMode.SPLIT, ViewMode.LADDER}:
        return requested_view

    if ladder is None:
        return ViewMode.MAIN
    if ladder.display_status == LadderDisplayStatus.ACTIVE:
        return ViewMode.SPLIT
    if ladder.display_status == LadderDisplayStatus.COMPLETED and ladder_was_visible:
        return ViewMode.SPLIT
    return ViewMode.MAIN


def derive_station_state(
    stations: Sequence[Station],
    active_matches: Sequence[MatchRow],
) -> StationState:
    """Build station availability from configured stations and active matches."""
    occupied_numbers = {
        match.station
        for match in active_matches
        if match.station is not None
    }
    station_numbers = [
        station.number
        for station in stations
        if station.enabled is not False
    ]
    available_numbers = [
        number
        for number in sorted(station_numbers)
        if number not in occupied_numbers
    ]
    return StationState(
        stations=list(stations),
        occupied_numbers=occupied_numbers,
        available_numbers=available_numbers,
    )


def filter_late_bracket_matches(matches: Sequence[MatchRow]) -> list[MatchRow]:
    """Prefer Top 24/Top 8 matches in split view, falling back to all matches."""
    late_matches = [
        match
        for match in matches
        if _has_late_bracket_label(match.bracket) or _has_late_bracket_label(match.pool)
    ]
    return late_matches or list(matches)


def _has_late_bracket_label(value: str) -> bool:
    normalized = value.lower()
    return "top 24" in normalized or "top 8" in normalized

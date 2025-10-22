"""Match data model and related utilities."""

import time
from enum import IntEnum
from typing import Any

from pydantic import BaseModel


class DictCompatibleBaseModel(BaseModel):
    """Custom BaseModel with dictionary-style access for backward compatibility"""

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access"""
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dictionary-style assignment"""
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        """Allow .get() method like dictionaries"""
        return getattr(self, key, default)

    model_config = {"extra": "allow"}


class MatchState(IntEnum):
    """Match state enum based on start.gg API values"""

    WAITING = 1  # Not started/Waiting for previous matches
    READY = 2  # Ready to be called (or In Progress if startedAt is set)
    COMPLETED = 3  # Completed
    IN_PROGRESS = 6  # In progress
    INVALID = 7  # Completed (alternative state)


# Unified data models for both real tournament data and simulation data
class PlayerData(DictCompatibleBaseModel):
    """Player information"""

    tag: str
    id: int | None = None


class EntrantSource(DictCompatibleBaseModel):
    """Source information for tournament entrants (used for bracket dependencies)"""

    type: str
    typeId: str | int | None = None


class MatchData(DictCompatibleBaseModel):
    """Complete match/set data structure that works for both API and simulation"""

    # Core identifiers
    id: str | int

    # Display information
    display_name: str | None = None
    displayName: str | None = None
    poolName: str | None = None
    phase_group: str | None = None
    phase_name: str | None = None

    # Players
    player1: PlayerData
    player2: PlayerData

    # Match state
    state: int

    # Timestamps (both formats for compatibility)
    created_at: int | None = None
    started_at: int | None = None
    completed_at: int | None = None
    updated_at: int | None = None
    updatedAt: int | None = None
    startedAt: int | None = None

    # Bracket dependencies (for simulation)
    entrant1_source: EntrantSource | None = None
    entrant2_source: EntrantSource | None = None

    # Station/stream information
    station: int | None = None
    stream: str | None = None

    # Simulation context
    simulation_context: dict[str, int] | None = None


# Alias for backward compatibility
SetData = MatchData


class TournamentMetadata(DictCompatibleBaseModel):
    """Tournament metadata for simulation data"""

    event_name: str
    tournament_name: str
    total_matches: int


class TournamentData(DictCompatibleBaseModel):
    """Tournament data structure for simulation files"""

    metadata: TournamentMetadata
    matches: list[MatchData]
    duration_minutes: int


class TournamentState(DictCompatibleBaseModel):
    """Tournament state as returned by API or simulator"""

    event_name: str
    tournament_name: str
    sets: list[MatchData]


class TimelineEvent(DictCompatibleBaseModel):
    """Timeline event for simulation"""

    timestamp: int
    type: str
    match_id: int
    state: int
    match: MatchData


class SimulationProgress(DictCompatibleBaseModel):
    """Simulation progress information"""

    progress: float
    current_time: int
    start_time: int
    end_time: int
    current_time_str: str
    active_matches: int


class MatchRow:
    """Represents a single match/set"""

    STATE_COLORS: dict[MatchState, str] = {
        MatchState.WAITING: "[dim]⚪[/dim]",  # Not started/Waiting - white
        MatchState.READY: "[red]🔴[/red]",  # Ready to be called - red
        MatchState.COMPLETED: "[green]✅[/green]",  # Completed - green
        MatchState.IN_PROGRESS: "[yellow]🟡[/yellow]",  # In progress - yellow
        MatchState.INVALID: "[green]✅[/green]",  # Completed (alternative) - green
    }

    STATE_NAMES: dict[MatchState, str] = {
        MatchState.WAITING: "Waiting",
        MatchState.READY: "Ready",
        MatchState.COMPLETED: "Completed",
        MatchState.IN_PROGRESS: "In Progress",
        MatchState.INVALID: "Completed",
    }

    def __init__(self, set_data: MatchData):
        self.id: int | str = set_data.id
        self.bracket: str = (
            set_data.displayName or set_data.display_name or "Unknown Match"
        )
        self.pool: str = set_data.poolName or "Unknown Pool"
        self.player1: str = set_data.player1.tag if set_data.player1 else "TBD"
        self.player2: str = set_data.player2.tag if set_data.player2 else "TBD"
        self.state: int = set_data.state
        # Try both timestamp formats for compatibility
        self.updated_at: int = set_data.updatedAt or set_data.updated_at or 0
        self.started_at: int | None = set_data.startedAt or set_data.started_at
        self.station: int | None = set_data.station
        self.stream: str | None = set_data.stream

        # Store simulation context for normalized time calculations
        self.simulation_context: dict[str, int] | None = set_data.simulation_context

    @property
    def status_icon(self) -> str:
        # Check if match has actually started based on startedAt timestamp
        if self.state == MatchState.READY and self.started_at:
            # State READY but has startedAt - it's actually in progress
            return "[yellow]🟡[/yellow]"
        else:
            return self.STATE_COLORS.get(MatchState(self.state), "⚪")

    @property
    def status_text(self) -> str:
        # Check if match has actually started based on startedAt timestamp
        if self.state == MatchState.READY and self.started_at:
            # State READY but has startedAt - it's actually in progress
            status = "In Progress"
        else:
            status = self.STATE_NAMES.get(MatchState(self.state), "Unknown")

        # Add station info if available
        if self.station:
            status += f" (Station {self.station})"
        elif self.stream:
            status += f" (Stream: {self.stream})"

        return status

    @property
    def match_name(self) -> str:
        """Return normalized match name with TBD players at the end"""
        # Normalize TBD matches to always show <player> vs TBD
        if self.player1 == "TBD" and self.player2 != "TBD":
            return f"{self.player2[:12]} vs TBD"
        elif self.player1 == "" and self.player2 != "" and self.player2 != "TBD":
            return f"{self.player2[:24]} vs TBD"
        elif self.player2 == "" and self.player1 != "" and self.player1 != "TBD":
            return f"{self.player1[:24]} vs TBD"
        else:
            return f"{self.player1[:12]} vs {self.player2[:12]}"

    @property
    def has_tbd_player(self) -> bool:
        """Check if match has any TBD or empty players"""
        return (
            self.player1 == "TBD" or self.player1 == "" or 
            self.player2 == "TBD" or self.player2 == ""
        )

    @property
    def time_since_ready(self) -> str:
        """Calculate time since match became ready, started, or was last updated"""
        # Use simulation time if available, otherwise use real time
        if self.simulation_context and self.simulation_context.get("is_simulation"):
            now = self.simulation_context["current_time"]
            start_time = self.simulation_context["start_time"]
        else:
            now = int(time.time())
            start_time = None

        if self.state == MatchState.READY:  # Ready to be called or In Progress
            # Use startedAt if available (match is actually in progress)
            # Otherwise use updatedAt (match is just ready)
            timestamp = self.started_at if self.started_at else self.updated_at

            if timestamp:
                if start_time:
                    # For simulation: calculate relative time from tournament start
                    # Original timestamp relative to tournament start
                    original_offset = timestamp - start_time
                    # Apply to current simulation timeline
                    sim_timestamp = start_time + original_offset
                    diff = now - sim_timestamp
                else:
                    # For real tournaments
                    diff = now - timestamp

                # Only show positive durations
                if diff >= 0:
                    return self._format_duration(diff)
                else:
                    return "-"
            else:
                return "-"

        elif self.state == MatchState.IN_PROGRESS and self.started_at:  # In progress
            if start_time:
                # For simulation: calculate relative time
                original_offset = self.started_at - start_time
                sim_timestamp = start_time + original_offset
                diff = now - sim_timestamp
            else:
                diff = now - self.started_at

            if diff >= 0:
                return self._format_duration(diff)
            else:
                return "-"

        elif self.state == MatchState.WAITING:  # Waiting - show time since last updated
            if self.updated_at:
                if start_time:
                    # For simulation: calculate time since tournament start
                    # Since we set updatedAt to start_time for initial matches,
                    # this shows time since tournament began
                    diff = now - self.updated_at
                else:
                    diff = now - self.updated_at

                if diff >= 0:
                    return self._format_duration(diff)
                else:
                    return "-"
            else:
                return "-"

        return "-"

    def _format_duration(self, diff: int, suffix: str = "") -> str:
        """Format duration in seconds to human readable format"""
        if diff < 60:
            return f"{diff}s{suffix}"
        elif diff < 3600:
            minutes = diff // 60
            seconds = diff % 60
            if seconds > 0:
                return f"{minutes}m {seconds}s{suffix}"
            else:
                return f"{minutes}m{suffix}"
        else:
            hours = diff // 3600
            minutes = (diff % 3600) // 60
            if minutes > 0:
                return f"{hours}h {minutes}m{suffix}"
            else:
                return f"{hours}h{suffix}"
